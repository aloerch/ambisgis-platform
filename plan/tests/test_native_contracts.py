from copy import deepcopy
import json
from pathlib import Path
import unittest
from tools.native_contracts import ContractError, CursorCodec, validate_query, validate_schema

ROOT = Path(__file__).resolve().parent.parent

class NativeContractTests(unittest.TestCase):
    def setUp(self):
        self.layer = json.loads((ROOT / "examples/layer.json").read_text())
        self.query = json.loads((ROOT / "examples/native-query.json").read_text())
    def reject(self, query, code):
        with self.assertRaises(ContractError) as cm:
            validate_query(query, self.layer)
        self.assertEqual(cm.exception.code, code)
    def test_normalize_stable_sort_without_changing_input(self):
        before = deepcopy(self.query)
        got = validate_query(self.query, self.layer)
        self.assertEqual(got["order_by"][-1], {"field": "object_id", "direction": "asc"})
        self.assertEqual(self.query, before)
    def test_all_contract_examples_validate_offline(self):
        for name in ["native-query", "layer", "native-error", "job", "notebook-run", "app-event"]:
            validate_schema(name, json.loads((ROOT / "examples" / (name + ".json")).read_text()))
    def test_raw_sql_and_unknown_parameter_rejected(self):
        for key, value in [("where", "1=1; DROP TABLE addresses"), ("filtersApplied", {"all": True}), ("token", "forged"), ("offset", 100)]:
            q = deepcopy(self.query); q[key] = value
            self.reject(q, "INVALID_REQUEST")
    def test_injection_identifier_rejected(self):
        q = deepcopy(self.query); q["order_by"][0]["field"] = "name;SELECT pg_sleep(10)"
        self.reject(q, "INVALID_REQUEST")
    def test_unknown_field_and_duplicate_projection_rejected(self):
        for fields in [["secret"], ["name", "name"]]:
            q = deepcopy(self.query); q["fields"] = fields
            self.reject(q, "INVALID_REQUEST")
    def test_wrong_literal_type_and_out_of_range_integer_rejected(self):
        for val in [{"type": "string", "value": "123"}, {"type": "int32", "value": 2 ** 31}, {"type": "int32", "value": True}]:
            q = deepcopy(self.query); q["filter"] = {"op": "eq", "field": "population", "value": val}
            self.reject(q, "INVALID_REQUEST")
    def test_sql_string_payload_remains_data(self):
        q = deepcopy(self.query); payload = "x' OR 1=1 --"
        q["filter"] = {"op": "eq", "field": "name", "value": {"type": "string", "value": payload}}
        self.assertEqual(validate_query(q, self.layer)["filter"]["value"]["value"], payload)
    def test_null_requires_explicit_operator(self):
        q = deepcopy(self.query); q["filter"] = {"op": "eq", "field": "name", "value": None}
        self.reject(q, "INVALID_REQUEST")
        q["filter"] = {"op": "is_null", "field": "name"}
        validate_query(q, self.layer)
    def test_nonfinite_and_invalid_bbox_rejected(self):
        for bounds in [[0,0,float("nan"),1], [5,0,4,1], [0,-91,1,1], [0,0,1,float("inf")]]:
            q = deepcopy(self.query); q["bbox"] = {"crs":"EPSG:4326", "bounds":bounds}
            self.reject(q, "INVALID_REQUEST")
    def test_unknown_transform_fails_explicitly(self):
        q = deepcopy(self.query); q["output_crs"] = "EPSG:2230"
        self.reject(q, "TRANSFORM_UNAVAILABLE")
    def test_filter_depth_and_total_node_limits(self):
        q = deepcopy(self.query); node = {"op":"is_null", "field":"name"}
        for _ in range(9): node = {"op":"and", "args":[node, {"op":"is_null", "field":"name"}]}
        q["filter"] = node; self.reject(q, "LIMIT_EXCEEDED")
        node = {"op":"is_null", "field":"name"}
        q["filter"] = {"op":"and", "args":[{"op":"or", "args":[node]*16}]*16}
        self.reject(q, "LIMIT_EXCEEDED")
    def test_aggregate_cannot_accept_page_or_projection(self):
        for key,value in [("cursor","abcdef"),("fields",["name"]),("page_size",10),("order_by",[{"field":"name","direction":"asc"}])]:
            q = {k:v for k,v in self.query.items() if k not in {"fields","order_by","page_size"}}
            q["mode"] = "count"; q[key] = value
            self.reject(q, "INVALID_REQUEST")
    def test_stale_revisions_and_cross_layer_rejected(self):
        for key in ["layer_id", "service_revision", "data_revision"]:
            q = deepcopy(self.query); q[key] = "00000000-0000-4000-8000-000000000001"
            self.reject(q, "REVISION_UNAVAILABLE" if key != "layer_id" else "INVALID_REQUEST")
    def test_row_or_field_policy_not_silently_dropped(self):
        self.layer["policy_mode"] = "row-field"
        self.reject(self.query, "UNSUPPORTED_CAPABILITY")
    def test_empty_geometry_or_unimplemented_geometry_rejected(self):
        self.layer["geometry"]["dimensions"] = "XYZ"
        self.reject(self.query, "UNSUPPORTED_CAPABILITY")
    def test_duplicate_sort_and_unbounded_page_rejected(self):
        q = deepcopy(self.query); q["order_by"] *= 2
        self.reject(q, "INVALID_REQUEST")
        for value in [0,1001,True]:
            q = deepcopy(self.query); q["page_size"] = value
            self.reject(q, "INVALID_REQUEST")
    def test_cursor_tampering_expiry_principal_query_and_revision_binding(self):
        query = validate_query(self.query, self.layer)
        codec = CursorCodec(b"a"*32, self.layer)
        cursor = codec.issue(query, "subject-a", "policy-1", [{"type":"int32","value":100},{"type":"int32","value":8}], now=1000)
        self.assertEqual(codec.verify(cursor, query, "subject-a", "policy-1", now=1001)[-1]["value"], 8)
        bads = [(cursor[:-2]+"xx",query,"subject-a","policy-1",1001), (cursor,query,"subject-b","policy-1",1001), (cursor,query,"subject-a","policy-2",1001), (cursor,query,"subject-a","policy-1",1300)]
        changed = deepcopy(query); changed["data_revision"] = "00000000-0000-4000-8000-000000000001"
        bads.append((cursor,changed,"subject-a","policy-1",1001))
        changed = deepcopy(query); changed["fields"] = ["name"]
        bads.append((cursor,changed,"subject-a","policy-1",1001))
        for args in bads:
            with self.assertRaises(ContractError): codec.verify(*args[:4],now=args[4])
    def test_cursor_key_and_position_shape(self):
        with self.assertRaises(ValueError): CursorCodec(b"short")
        codec = CursorCodec(b"a"*32, self.layer); query = validate_query(self.query,self.layer)
        with self.assertRaises(ContractError): codec.issue(query,"subject-a","policy-1",[],now=1000)
    def test_rfc3339_case_and_safe_timestamp_errors(self):
        q = deepcopy(self.query)
        q["order_by"] = [{"field":"observed_at", "direction":"asc"}]
        q["filter"] = {"op":"eq", "field":"observed_at", "value":{"type":"timestamp", "value":"2026-10-03t12:00:00z"}}
        normalized = validate_query(q, self.layer)
        codec = CursorCodec(b"a"*32, self.layer)
        position = [q["filter"]["value"], {"type":"int32","value":1}]
        token = codec.issue(normalized, "subject-a", "policy-1", position, now=1000)
        self.assertEqual(codec.verify(token, normalized, "subject-a", "policy-1", now=1001), position)
        for bad in ["2026-13-03T12:00:00Z", "2026-10-03T12:00:00", "private-bad-timestamp"]:
            q["filter"]["value"]["value"] = bad
            self.reject(q, "INVALID_REQUEST")
            position[0]["value"] = bad
            with self.assertRaises(ContractError) as cm:
                codec.issue(normalized, "subject-a", "policy-1", position, now=1000)
            self.assertNotIn(bad, str(cm.exception))
    def test_cursor_rejects_null_nonnullable_or_wrong_sort_type(self):
        q = validate_query(self.query,self.layer)
        codec = CursorCodec(b"a"*32,self.layer)
        for first in [None,{"type":"string","value":"100"},{"type":"int32","value":100.0}]:
            with self.assertRaises(ContractError):
                codec.issue(q,"subject-a","policy-1",[first,{"type":"int32","value":1}],now=1000)
    def test_publication_job_cannot_succeed_before_active(self):
        doc = json.loads((ROOT / "examples/job.json").read_text())
        doc["state"] = "succeeded"
        with self.assertRaises(ContractError): validate_schema("job",doc)
        doc["publication_stage"] = "ACTIVE"
        validate_schema("job",doc)
    def test_dependency_failure_requires_complete_safe_native_error_envelope(self):
        doc = json.loads((ROOT / "examples/native-error.json").read_text())
        doc["error"].update(code="BACKEND_UNAVAILABLE", message="Query dependency unavailable",
                            retryable=True, remediation="retry_later")
        validate_schema("native-error", doc)
        for key in ["code", "message", "correlation_id", "retryable", "remediation"]:
            missing = deepcopy(doc)
            del missing["error"][key]
            with self.assertRaises(ContractError):
                validate_schema("native-error", missing)
        leaked = deepcopy(doc)
        leaked["error"]["backend_trace"] = "SELECT private_table"
        with self.assertRaises(ContractError):
            validate_schema("native-error", leaked)
    def test_no_credentials_or_arbitrary_code_in_new_envelopes(self):
        for name,key in [("notebook-run","token"),("app-event","javascript"),("job","database_password")]:
            doc = json.loads((ROOT / "examples" / (name + ".json")).read_text())
            doc[key] = "must-never-be-accepted"
            with self.assertRaises(ContractError): validate_schema(name,doc)
    def test_decimal_zero_and_precision_scale_boundaries(self):
        elevation = next(f for f in self.layer["fields"] if f["name"] == "elevation")
        elevation.update(precision=2,scale=2)
        q = deepcopy(self.query)
        q["order_by"] = [{"field":"elevation", "direction":"asc"}]
        for value in ["0","-0","0.0","0.00","0.01","-0.99","0.99"]:
            q["filter"] = {"op":"eq", "field":"elevation", "value":{"type":"decimal", "value":value}}
            normalized = validate_query(q,self.layer)
            CursorCodec(b"a"*32,self.layer).issue(normalized,"subject-a","policy-1",[q["filter"]["value"],{"type":"int32","value":1}],now=1000)
        for value in ["1","-1","0.001","0.000","-1.00"]:
            q["filter"]["value"]["value"] = value
            self.reject(q,"INVALID_REQUEST")

if __name__ == "__main__": unittest.main()
