"""Initial native contract validation; no policy authority, SQL or HTTP handlers.

The caller authenticates and obtains current catalog authorization before using
this module, including before cursor verification, counts and extent queries.
Schema resources are resolved from this package only, never from the network.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
import hmac
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent.parent
MAX_REQUEST_BYTES = 32768
MAX_FILTER_DEPTH = 8
MAX_FILTER_NODES = 128


class ContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        # Never include raw values, SQL, schema contents or credentials in errors.
        super().__init__(code)


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise ContractError("INVALID_REQUEST") from None


def _shape_budget(value, depth=0):
    if depth > 32:
        raise ContractError("LIMIT_EXCEEDED")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ContractError("INVALID_REQUEST")
            _shape_budget(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > 1000:
            raise ContractError("LIMIT_EXCEEDED")
        for child in value:
            _shape_budget(child, depth + 1)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ContractError("INVALID_REQUEST")


def validate_schema(name, instance, root=ROOT):
    """Validate trusted package schemas with an offline reference registry."""
    from jsonschema import Draft202012Validator, FormatChecker, ValidationError
    from referencing import Registry, Resource
    _shape_budget(instance)
    if len(_canonical(instance)) > MAX_REQUEST_BYTES:
        raise ContractError("LIMIT_EXCEEDED")
    schemas = {}
    resources = []
    for path in sorted((root / "contracts").glob("*.schema.json")):
        schema = json.loads(path.read_text())
        schemas[path.name.removesuffix(".schema.json")] = schema
        if "$id" in schema:
            resources.append((schema["$id"], Resource.from_contents(schema)))
    if name not in schemas:
        raise ValueError("Unknown package schema")
    try:
        Draft202012Validator(schemas[name], registry=Registry().with_resources(resources),
                             format_checker=FormatChecker()).validate(instance)
    except ValidationError as exc:
        raise ContractError("INVALID_REQUEST") from None


def _check_literal(literal, field):
    if literal["type"] != field["type"]:
        raise ContractError("INVALID_REQUEST")
    value = literal["value"]
    if field["type"] == "int32" and type(value) is not int:
        raise ContractError("INVALID_REQUEST")
    if field["type"] == "int64" and not -(2**63) <= int(value) < 2**63:
        raise ContractError("INVALID_REQUEST")
    if field["type"] == "decimal":
        dec = Decimal(value)
        scale = max(0, -dec.as_tuple().exponent)
        integral = 0 if dec.is_zero() else max(0, dec.adjusted() + 1)
        if scale > field["scale"] or integral > field["precision"] - field["scale"]:
            raise ContractError("INVALID_REQUEST")
    if field["type"] == "string" and len(value) > field["max_length"]:
        raise ContractError("INVALID_REQUEST")
    if field["type"] == "timestamp":
        # RFC3339 permits lowercase t/z, while fromisoformat rejects terminal z.
        normalized = value[:-1] + "+00:00" if value[-1:].upper() == "Z" else value
        try:
            parsed = datetime.fromisoformat(normalized.replace("t", "T"))
        except ValueError:
            raise ContractError("INVALID_REQUEST") from None
        if parsed.tzinfo is None:
            raise ContractError("INVALID_REQUEST")
    if "domain" in field and literal not in field["domain"]:
        raise ContractError("INVALID_REQUEST")


def _check_filter(node, fields, budget, depth=1):
    budget[0] += 1
    if depth > MAX_FILTER_DEPTH or budget[0] > MAX_FILTER_NODES:
        raise ContractError("LIMIT_EXCEEDED")
    if node["op"] in ("and", "or"):
        for child in node["args"]:
            _check_filter(child, fields, budget, depth + 1)
        return
    field = fields.get(node["field"])
    if field is None:
        raise ContractError("INVALID_REQUEST")
    if "value" in node:
        _check_literal(node["value"], field)
        if field["type"] in ("boolean", "uuid") and node["op"] not in ("eq", "ne"):
            raise ContractError("UNSUPPORTED_CAPABILITY")


def validate_layer(layer):
    validate_schema("layer", layer)
    fields = {field["name"]: field for field in layer["fields"]}
    if len(fields) != len(layer["fields"]):
        raise ContractError("SCHEMA_MISMATCH")
    for field in fields.values():
        if field["type"] == "decimal":
            if not {"precision", "scale"} <= field.keys() or field["scale"] > field["precision"]:
                raise ContractError("SCHEMA_MISMATCH")
        elif "precision" in field or "scale" in field:
            raise ContractError("SCHEMA_MISMATCH")
        if (field["type"] == "string") != ("max_length" in field):
            raise ContractError("SCHEMA_MISMATCH")
        for value in field.get("domain", []):
            _check_literal(value, {k: v for k, v in field.items() if k != "domain"})
    identity = fields.get(layer["identity_field"])
    object_id = fields.get(layer["object_id_field"])
    if (identity is None or identity["type"] != "uuid" or identity["nullable"] or
            object_id is None or object_id["type"] != "int32" or object_id["nullable"]):
        raise ContractError("SCHEMA_MISMATCH")
    return fields


def validate_query(request, layer):
    """Validate the bounded spike profile; returns a separate normalized value.

    A service revision and data revision identify immutable retained state.
    Callers must never replace a missing revision with the latest state. Text
    ordering uses PostgreSQL C collation and NULLS LAST in either direction.
    SQL operators retain three-valued null semantics; null tests are explicit.
    """
    validate_schema("native-query", request)
    fields = validate_layer(layer)
    if request["layer_id"] != layer["layer_id"]:
        raise ContractError("INVALID_REQUEST")
    if any(request[key] != layer[key] for key in ("service_revision", "data_revision")):
        raise ContractError("REVISION_UNAVAILABLE")
    if (layer["policy_mode"] != "object" or
            layer["geometry"] != {"type": "Point", "crs": "EPSG:4326",
                                  "dimensions": "XY", "nullable": False}):
        raise ContractError("UNSUPPORTED_CAPABILITY")
    if request.get("output_crs", "EPSG:4326") != "EPSG:4326":
        raise ContractError("TRANSFORM_UNAVAILABLE")
    if "bbox" in request:
        bbox = request["bbox"]
        if bbox["crs"] != "EPSG:4326":
            raise ContractError("TRANSFORM_UNAVAILABLE")
        x0, y0, x1, y1 = bbox["bounds"]
        if not (-180 <= x0 <= x1 <= 180 and -90 <= y0 <= y1 <= 90):
            raise ContractError("INVALID_REQUEST")
    if "filter" in request:
        _check_filter(request["filter"], fields, [0])
    result = deepcopy(request)
    result["output_crs"] = "EPSG:4326"
    if request["mode"] != "features":
        if {"fields", "order_by", "page_size", "cursor"} & request.keys():
            raise ContractError("INVALID_REQUEST")
        return result
    selected = request.get("fields", list(fields))
    if len(set(selected)) != len(selected) or not set(selected) <= fields.keys():
        raise ContractError("INVALID_REQUEST")
    order = deepcopy(request.get("order_by", []))
    names = [entry["field"] for entry in order]
    if len(set(names)) != len(names) or not set(names) <= fields.keys():
        raise ContractError("INVALID_REQUEST")
    oid = layer["object_id_field"]
    if oid in names and names[-1] != oid:
        raise ContractError("INVALID_REQUEST")
    if oid not in names:
        if len(order) >= 4:
            raise ContractError("LIMIT_EXCEEDED")
        order.append({"field": oid, "direction": "asc"})
    result.update(fields=selected, order_by=order, page_size=request.get("page_size", 100))
    return result


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value):
    raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _b64(raw) != value:
        raise ValueError("Non-canonical encoding")
    return raw


def query_digest(query):
    return hashlib.sha256(_canonical({k: v for k, v in query.items() if k != "cursor"})).hexdigest()


class CursorCodec:
    """Integrity-only cursor prototype. Not encryption or authorization.

    Keys are ephemeral runtime secrets, never a checked-in default. Production
    key rotation/storage belongs to API-01/SEC-01. Principal and policy bindings
    are HMACs to avoid exposing identity references. Ordering values remain
    readable; the provider must not put restricted data in the cursor.
    """
    def __init__(self, key: bytes, layer=None, lifetime_seconds: int = 300):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Cursor keys require at least 32 bytes")
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= 300:
            raise ValueError("Invalid cursor lifetime")
        if layer is None:
            raise ValueError("A validated layer descriptor is required")
        self.fields = validate_layer(layer)
        self.layer = deepcopy(layer)
        self.key = key
        self.lifetime = lifetime_seconds

    def _binding(self, principal, policy_revision):
        if not isinstance(principal, str) or not principal or not isinstance(policy_revision, str) or not policy_revision:
            raise ContractError("INVALID_CURSOR")
        return hmac.new(self.key, b"binding\0" + _canonical([principal, policy_revision]), hashlib.sha256).hexdigest()

    def _position(self, query, position):
        if query.get("mode") != "features" or not isinstance(position, list) or len(position) != len(query["order_by"]):
            raise ContractError("INVALID_CURSOR")
        from jsonschema import Draft202012Validator, FormatChecker, ValidationError
        common = json.loads((ROOT / "contracts/common.schema.json").read_text())
        # Only literals/nulls, with no user-controlled references.
        literal = common["$defs"]["literal"]
        normalized = validate_query(query, self.layer)
        if normalized != query:
            raise ContractError("INVALID_CURSOR")
        for ordering, value in zip(query["order_by"], position):
            field = self.fields[ordering["field"]]
            if value is None:
                if not field["nullable"]:
                    raise ContractError("INVALID_CURSOR")
                continue
            try:
                Draft202012Validator(literal, format_checker=FormatChecker()).validate(value)
                _check_literal(value, field)
            except ValidationError as exc:
                raise ContractError("INVALID_CURSOR") from None
        if position[-1] is None or position[-1].get("type") != "int32" or position[-1]["value"] <= 0:
            raise ContractError("INVALID_CURSOR")

    def issue(self, query, principal, policy_revision, position, *, now=None):
        self._position(query, position)
        now = int(time.time()) if now is None else now
        if type(now) is not int or now < 0:
            raise ContractError("INVALID_CURSOR")
        payload = {"v": 1, "query": query_digest(query), "scope": self._binding(principal, policy_revision),
                   "iat": now, "exp": now + self.lifetime, "after": position}
        encoded = _b64(_canonical(payload))
        token = encoded + "." + _b64(hmac.new(self.key, b"cursor\0" + encoded.encode(), hashlib.sha256).digest())
        if len(token) > 4096:
            raise ContractError("LIMIT_EXCEEDED")
        return token

    def verify(self, token, query, principal, policy_revision, *, now=None):
        try:
            if not isinstance(token, str) or len(token) > 4096:
                raise ValueError("Invalid size")
            encoded, signature = token.split(".")
            expected = hmac.new(self.key, b"cursor\0" + encoded.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(_unb64(signature), expected):
                raise ValueError("Bad signature")
            payload = json.loads(_unb64(encoded))
            if _b64(_canonical(payload)) != encoded:
                raise ValueError("Non-canonical payload")
            now = int(time.time()) if now is None else now
            if (set(payload) != {"v", "query", "scope", "iat", "exp", "after"} or payload["v"] != 1
                    or type(now) is not int or type(payload["iat"]) is not int or type(payload["exp"]) is not int
                    or not payload["iat"] <= now < payload["exp"]
                    or payload["exp"] - payload["iat"] != self.lifetime
                    or payload["query"] != query_digest(query)
                    or not hmac.compare_digest(payload["scope"], self._binding(principal, policy_revision))):
                raise ValueError("Invalid context")
            self._position(query, payload["after"])
            return payload["after"]
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
            raise ContractError("INVALID_CURSOR") from None
