"""Failure evidence survives removed one-shot services without reflecting child text."""
import io
import copy
import importlib.util
import errno
from types import SimpleNamespace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from installer import runtime, diagnostics, __main__ as cli
from installer.state import InstallError

RECORD = {"event": "service_start_failed", "detail": "Inspect installation state and owned dependency readiness.",
          "stage": "entrypoint", "code": "unexpected", "category": "unexpected"}

class InitializerFailureReporting(unittest.TestCase):
    def test_removed_initializer_failure_keeps_only_finite_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = runtime.Runtime.__new__(runtime.Runtime)
            rt.paths = {"tmp": Path(tmp)}; rt.environment = {}; rt.root = Path(tmp)
            def child(arguments, **kwargs):
                kwargs["stdout"].write(b"private-credential-not-for-evidence\n")
                kwargs["stderr"].write((json.dumps(RECORD) + "\n").encode())
                return type("Result", (), {"returncode": 1})()
            with patch.object(runtime.subprocess, "run", side_effect=child):
                with self.assertRaises(InstallError) as caught:
                    rt.run(["inert-producer-double"])
            self.assertEqual(getattr(caught.exception, "startup_failure", None),
                             {"stage": "entrypoint", "code": "unexpected", "category": "unexpected"})
            self.assertNotIn("private-credential", str(caught.exception))
            self.assertEqual(list(Path(tmp).iterdir()), [])

class FiniteDiagnosticProjection(unittest.TestCase):
    def fields(self): return {key: RECORD[key] for key in ("stage", "code", "category")}

    def test_current_isolated_service_contract_is_bound(self):
        path = ROOT / "services/development/ambisgis_development/startup_diagnostics.py"
        spec = importlib.util.spec_from_file_location("reporting_service_contract", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual(diagnostics.STAGES, module.STAGES)
        self.assertEqual(diagnostics.CATEGORIES, module.CATEGORIES)
        for stage in module.STAGES:
            for error in (ValueError("secret"), FileNotFoundError(errno.ENOENT, "secret"),
                          module.ChildFailure(17), TimeoutError("secret"), RuntimeError("secret"), Exception("secret")):
                record = module.failure_record(module.StartupFailure(stage, error))
                result = diagnostics.from_streams(b"", json.dumps(record).encode())
                self.assertEqual(result, {k: v for k, v in record.items() if k not in ("event", "detail")})
                self.assertNotIn("secret", json.dumps(result))

    def test_noise_and_exception_text_never_cross_projection(self):
        raw = b"password=secret-value\npostgres://user:secret-value@database/catalog\nTraceback: secret-value\n"
        result = diagnostics.from_streams(raw, json.dumps(RECORD).encode() + b"\nBearer secret-value")
        self.assertEqual(result, self.fields())
        self.assertNotIn("secret-value", json.dumps(result))
        self.assertIsNone(diagnostics.from_streams(raw, raw))

    def test_ambiguous_or_foreign_records_withhold_metadata(self):
        encoded = json.dumps(RECORD).encode()
        self.assertIsNone(diagnostics.from_streams(encoded, encoded))
        for update in ({"detail": "password=secret-value"}, {"stage": "secret-value"},
                       {"extra": "secret-value"}, {"event": "unrelated"}, {"code": "arbitrary"}):
            with self.subTest(update=update):
                record = dict(RECORD, **update)
                self.assertIsNone(diagnostics.from_streams(b"", json.dumps(record).encode()))
        self.assertIsNone(diagnostics.from_streams(encoded, json.dumps(dict(RECORD, extra="bad")).encode()))

    def test_duplicate_keys_constants_and_nonobjects_are_rejected(self):
        duplicate = json.dumps(RECORD)[:-1] + ', "stage": "entrypoint"}'
        for raw in (duplicate.encode(), b'{"x":NaN}', b'[]', b'null', b'"text"', b'{', b'\xff'):
            with self.subTest(raw=raw):
                self.assertIsNone(diagnostics.from_streams(b"", raw))
        self.assertIsNone(diagnostics.from_streams(b"", b" " * 1025 + json.dumps(RECORD).encode()))
        self.assertIsNone(diagnostics.from_streams(b"x" * (diagnostics.LIMIT + 1), b""))

    def test_malformed_json_record_and_valid_record_are_ambiguous(self):
        valid = json.dumps(RECORD).encode()
        duplicate = (json.dumps(RECORD)[:-1] + ', "stage": "entrypoint"}').encode()
        oversized = b" " * 1025 + valid
        for malformed in (duplicate, oversized, b'{"event":"service_start_failed",',
                          b'{"event":"service_start_failed","stage":NaN}', b'{"event": "\\xff"}'):
            for output, diagnostic in ((malformed, valid), (valid, malformed),
                                       (b"", malformed + b"\n" + valid)):
                with self.subTest(malformed=malformed[:80], output_length=len(output)):
                    self.assertIsNone(diagnostics.from_streams(output, diagnostic))

    def test_metadata_types_and_bounds_cannot_carry_payloads(self):
        for field, values in {"stage": [[], {}, True, "secret"], "code": [[], None, "secret"],
                              "category": [[], False, "secret"], "errno": [True, "secret", -1],
                              "child_returncode": [True, "secret", -65, 256],
                              "cleanup_failed": [False, "secret", 1]}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    record = self.fields(); record[field] = value
                    self.assertIsNone(diagnostics.startup_fields(record))
        for returncode in (-64, 0, 255):
            value = {"stage": "initdb", "code": "child_failed", "category": "child_exit", "child_returncode": returncode}
            self.assertEqual(diagnostics.startup_fields(value), value)
        value = {"stage": "storage", "code": "os_failure", "category": "os_error", "errno": errno.EACCES, "cleanup_failed": True}
        self.assertEqual(diagnostics.startup_fields(value), value)

    def test_cli_revalidates_exception_metadata(self):
        for fields in (self.fields(), dict(self.fields(), extra="secret")):
            error = diagnostics.OperationFailure(1, b"", b""); error.startup_failure = fields
            stderr = io.StringIO()
            with patch.object(runtime, "up", side_effect=error), patch.object(sys, "stderr", stderr):
                result = cli.main(["up", "--directory", "/synthetic/installation"])
            self.assertEqual(result, 1)
            value = json.loads(stderr.getvalue())
            if "extra" in fields: self.assertNotIn("startup_failure", value)
            else: self.assertEqual(value["startup_failure"], fields)
            self.assertNotIn("secret", stderr.getvalue())

    def test_cli_evidence_requires_exact_failed_command_envelope(self):
        row = {"command": "up", "ok": False, "error": "secret-value", "startup_failure": self.fields()}
        self.assertEqual(diagnostics.from_cli(json.dumps(row).encode(), "up"), self.fields())
        for update in ({"command": "doctor"}, {"ok": True}, {"extra": "secret-value"}, {"error": []},
                       {"startup_failure": dict(self.fields(), stage="secret-value")}):
            self.assertIsNone(diagnostics.from_cli(json.dumps(dict(row, **update)).encode(), "up"))
        self.assertIsNone(diagnostics.from_cli(json.dumps(row).encode() * 2, "up"))

    def test_actual_lifecycle_failure_receipt_contains_only_validated_metadata(self):
        path = ROOT / "deploy/development/lifecycle_check.py"
        spec = importlib.util.spec_from_file_location("reporting_lifecycle", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            check = module.Check(Path(tmp) / "installation", Path(tmp))
            check.launcher = Path(tmp) / "ambisgis"
            stderr = json.dumps({"command": "up", "ok": False, "error": "not copied", "startup_failure": self.fields()}).encode()
            with patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=b"", stderr=stderr)):
                with self.assertRaises(RuntimeError): check.cli("up")
            self.assertEqual(check.record["cli_failure"]["startup_failure"], self.fields())
            self.assertNotIn("not copied", json.dumps(check.record))
            self.assertEqual(list(Path(tmp).iterdir()), [])

if __name__ == "__main__": unittest.main()

