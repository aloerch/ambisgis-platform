"""Inert fixed startup diagnostics; no native services or database execution."""
from contextlib import redirect_stderr, redirect_stdout
import errno
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/development"))
from ambisgis_development import database

SECRET = "fixture-only-private-password-SQL-argv-traceback"


class StartupDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.data = self.root / "data"; self.data.mkdir()
        self.password = self.root / "password"
        self.config = {"install_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"}
        self.secrets = {"database_admin": SECRET}
        self.process = SimpleNamespace(poll=lambda: None, wait=lambda **kw: 0,
                                       send_signal=lambda number: None)
        self.stack = []
        for target, value in (
            ("DATA", self.data), ("inputs", lambda: (self.config, self.secrets)),
            ("Path", lambda name: self.password if name == "/tmp/initial-database-password" else Path(name)),
        ):
            item = patch.object(database, target, value); item.start(); self.addCleanup(item.stop)
        self.native = patch.object(database.subprocess, "run", side_effect=AssertionError("native forbidden"))
        self.native_mock = self.native.start(); self.addCleanup(self.native.stop)
        self.popen = patch.object(database.subprocess, "Popen", side_effect=AssertionError("native forbidden"))
        self.popen_mock = self.popen.start(); self.addCleanup(self.popen.stop)
        signals = patch.object(database.signal, "signal"); signals.start(); self.addCleanup(signals.stop)

    def invoke(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["entrypoint", "database"]), redirect_stdout(output), redirect_stderr(errors):
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_module("ambisgis_development.entrypoint", run_name="__main__")
        self.assertEqual(stopped.exception.code, 1)
        self.assertNotIn(SECRET, output.getvalue() + errors.getvalue())
        value = json.loads(errors.getvalue())
        self.assertEqual(value["event"], "service_start_failed")
        return value

    def marker(self):
        path = self.data / "installation.json"
        path.write_text(json.dumps({"schema_version": 1, "install_id": self.config["install_id"],
                                    "purpose": "developer-database"}))
        path.chmod(0o600)

    def existing(self):
        self.marker()
        (self.data / "pgdata").mkdir()
        (self.data / "pgdata/PG_VERSION").write_text("17")

    def test_input_error_has_fixed_stage_without_value(self):
        with patch.object(database, "inputs", side_effect=ValueError(SECRET)):
            value = self.invoke()
        self.assertEqual((value["stage"], value["code"]), ("input", "invalid_input"))
        self.popen_mock.assert_not_called()

    def test_identity_failure_preserves_existing_marker(self):
        marker = self.data / "installation.json"; marker.write_text(json.dumps({"wrong": SECRET})); marker.chmod(0o600)
        original = marker.read_bytes()
        value = self.invoke()
        self.assertEqual(value["stage"], "identity")
        self.assertEqual(marker.read_bytes(), original)
        self.native_mock.assert_not_called()

    def test_storage_failure_stays_nonzero_without_native_call(self):
        self.existing()
        (self.data / "socket").symlink_to(self.root)
        value = self.invoke()
        self.assertEqual(value["stage"], "storage")
        self.native_mock.assert_not_called()

    def test_preexisting_password_is_not_deleted_or_read(self):
        self.password.write_text(SECRET)
        value = self.invoke()
        self.assertEqual(value["stage"], "password")
        self.assertEqual(value["errno"], errno.EEXIST)
        self.assertEqual(self.password.read_text(), SECRET)
        self.native_mock.assert_not_called()

    def test_initdb_exit_is_reported_without_child_output(self):
        self.native_mock.side_effect = None
        self.native_mock.return_value = SimpleNamespace(returncode=7, stdout=SECRET.encode(), stderr=SECRET.encode())
        value = self.invoke()
        self.assertEqual((value["stage"], value["code"], value["child_returncode"]), ("initdb", "child_failed", 7))
        self.assertFalse(self.password.exists())

    def test_initdb_timeout_never_emits_command_output(self):
        self.native_mock.side_effect = subprocess.TimeoutExpired([SECRET], 60, output=SECRET, stderr=SECRET)
        value = self.invoke()
        self.assertEqual((value["stage"], value["code"]), ("initdb", "timeout"))
        self.assertFalse(self.password.exists())

    def test_password_write_failure_removes_owned_file(self):
        self.marker()
        original = os.fdopen
        class WriteFailure:
            def __init__(inner, fd, mode): inner.file = original(fd, mode)
            def __enter__(inner): return inner
            def write(inner, value): raise OSError(errno.ENOSPC, SECRET)
            def __exit__(inner, *args): inner.file.close()
        def opened(fd, mode):
            return WriteFailure(fd, mode) if mode == "w" else original(fd, mode)
        with patch.object(database.os, "fdopen", opened):
            value = self.invoke()
        self.assertFalse(self.password.exists())
        self.assertEqual(value["stage"], "password")
        self.assertEqual(value["errno"], errno.ENOSPC)
        self.native_mock.assert_not_called()

    def test_child_failure_survives_password_cleanup_failure(self):
        self.native_mock.side_effect = None
        self.native_mock.return_value = SimpleNamespace(returncode=9, stdout=SECRET.encode())
        original = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == self.password: raise PermissionError(errno.EACCES, SECRET)
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", unlink):
            value = self.invoke()
        self.assertEqual((value["stage"], value["child_returncode"]), ("initdb", 9))
        self.assertIs(value["cleanup_failed"], True)
        self.assertTrue(self.password.exists())

    def test_server_launch_errno_is_fixed(self):
        self.existing()
        self.popen_mock.side_effect = FileNotFoundError(errno.ENOENT, SECRET, SECRET)
        value = self.invoke()
        self.assertEqual((value["stage"], value["errno"]), ("server", errno.ENOENT))

    def test_readiness_exited_child_code_is_available(self):
        self.existing()
        self.process.poll = lambda: 13
        self.popen_mock.side_effect = None; self.popen_mock.return_value = self.process
        with patch.object(database, "sql", side_effect=RuntimeError(SECRET)):
            value = self.invoke()
        self.assertEqual((value["stage"], value["child_returncode"]), ("readiness", 13))

    def test_bootstrap_failure_does_not_emit_sql_or_secrets(self):
        self.existing()
        self.popen_mock.side_effect = None; self.popen_mock.return_value = self.process
        with patch.object(database, "sql", return_value="1"), patch.object(database, "bootstrap", side_effect=ValueError(SECRET)):
            value = self.invoke()
        self.assertEqual(value["stage"], "bootstrap")

    def test_unknown_exception_type_and_values_stay_generic(self):
        class Hostile(Exception):
            def __str__(self): raise AssertionError("exception text must never be formatted")
        Hostile.__name__ = SECRET
        with patch.object(database, "inputs", side_effect=Hostile(SECRET)):
            value = self.invoke()
        self.assertEqual((value["stage"], value["code"], value["category"]),
                         ("input", "unexpected", "unexpected"))

    def test_cleanup_only_failure_is_labelled_and_nonzero(self):
        self.native_mock.side_effect = None
        self.native_mock.return_value = SimpleNamespace(returncode=0, stdout=b"")
        original = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == self.password: raise PermissionError(errno.EACCES, SECRET)
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", unlink):
            value = self.invoke()
        self.assertEqual((value["stage"], value["code"], value["errno"]),
                         ("password_cleanup", "os_failure", errno.EACCES))
        self.assertIs(value["cleanup_failed"], True)
        self.popen_mock.assert_not_called()

    def test_readiness_deadline_retains_existing_retry_and_shutdown(self):
        self.existing()
        self.popen_mock.side_effect = None; self.popen_mock.return_value = self.process
        with patch.object(database, "sql", side_effect=subprocess.TimeoutExpired(SECRET, 4, output=SECRET)), \
                patch.object(database.time, "monotonic", side_effect=[0, 61]), \
                patch.object(database.time, "sleep") as sleep:
            value = self.invoke()
        self.assertEqual((value["stage"], value["code"]), ("readiness", "timeout"))
        sleep.assert_not_called()

    def test_malformed_child_metadata_is_generic_including_missing_attribute(self):
        from ambisgis_development.startup_diagnostics import ChildFailure
        for invalid in (SECRET, True, None, -65, 256, object()):
            with self.subTest(kind=type(invalid).__name__):
                with patch.object(database, "inputs", side_effect=ChildFailure(invalid)):
                    value = self.invoke()
                self.assertEqual(value["code"], "unexpected")
                self.assertNotIn("child_returncode", value)
        malformed = ChildFailure(5); del malformed.returncode
        with patch.object(database, "inputs", side_effect=malformed):
            value = self.invoke()
        self.assertEqual(value["code"], "unexpected")

    def test_malformed_failure_metadata_cannot_be_serialized(self):
        from ambisgis_development.startup_diagnostics import StartupFailure, failure_record
        for fields in (None, SECRET, [], {"stage":SECRET,"code":"unexpected","category":"unexpected"},
                       {"stage":"input","code":"unexpected","category":SECRET},
                       {"stage":"input","code":"unexpected","category":"unexpected","extra":SECRET},
                       {"stage":"input","code":"unexpected","category":"unexpected","errno":SECRET},
                       {"stage":"input","code":"unexpected","category":"unexpected","cleanup_failed":SECRET}):
            with self.subTest(fields_type=type(fields).__name__):
                error = StartupFailure("input", ValueError(SECRET)); error.fields = fields
                value = failure_record(error)
                self.assertNotIn(SECRET, json.dumps(value))
                self.assertEqual((value["stage"], value["code"]), ("entrypoint","unexpected"))

    def test_malformed_os_errno_is_omitted(self):
        for invalid in (SECRET, True, -1, 10**20):
            error = OSError(errno.EACCES, SECRET, SECRET); error.errno = invalid
            with patch.object(database, "inputs", side_effect=error):
                value = self.invoke()
            self.assertEqual(value["code"], "os_failure")
            self.assertNotIn("errno", value)

    def test_success_preserves_native_invocation_and_exit(self):
        self.existing()
        self.process.wait = lambda **kwargs: 23
        self.popen_mock.side_effect = None; self.popen_mock.return_value = self.process
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(database, "sql", return_value="1"), patch.object(database, "bootstrap") as bootstrap, \
                patch.object(sys, "argv", ["entrypoint", "database"]), \
                redirect_stdout(output), redirect_stderr(errors):
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_module("ambisgis_development.entrypoint", run_name="__main__")
        self.assertEqual(stopped.exception.code, 23)
        self.assertEqual(errors.getvalue(), "")
        bootstrap.assert_called_once_with(self.config, self.secrets)
        argv = self.popen_mock.call_args.args[0]
        self.assertEqual(argv[:5], ["/opt/ambisgis/postgres/bin/postgres","-D",
                                   str(self.data/"pgdata"),"-p","5432"])
        self.assertEqual(self.popen_mock.call_args.kwargs,
                         {"stdout":subprocess.DEVNULL,"stderr":subprocess.DEVNULL})
        self.assertEqual(json.loads(output.getvalue()),
                         {"event":"database_ready","install_id":self.config["install_id"]})

    def test_final_projection_handles_missing_child_metadata_directly(self):
        from ambisgis_development.startup_diagnostics import ChildFailure, failure_record
        malformed = ChildFailure(3); del malformed.returncode
        value = failure_record(malformed)
        self.assertEqual(value["code"], "unexpected")
        self.assertNotIn("child_returncode", value)


if __name__ == "__main__":
    unittest.main()
