"""Harness safeguards. Real notebook acceptance is runtime_probe.py, not mocks."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import zipfile
from unittest import mock

import runtime_probe as probe


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "https://example.invalid/secret")
            self.end_headers()
            return
        status = 200 if self.headers.get("Authorization") == "token disposable" else 403
        self.send_response(status)
        self.end_headers()
        self.wfile.write(json.dumps({"status": status}).encode())

    def log_message(self, *args):
        pass


class RuntimeHarnessTests(unittest.TestCase):
    def test_url_boundary_rejects_external_and_embedded_credentials(self):
        for url in ("https://127.0.0.1/", "http://localhost/", "http://0.0.0.0/",
                    "http://127.0.0.1.evil/", "http://user:pass@127.0.0.1/",
                    "http://127.0.0.1/?token=secret", "http://127.0.0.1/#secret",
                    "http://[::1]/"):
            with self.subTest(url=url), self.assertRaises(probe.ProbeError):
                probe.loopback_url(url)
        self.assertEqual(probe.loopback_url("http://127.0.0.1:1234/api").port, 1234)

    def test_redacts_known_and_structured_credentials(self):
        text = "literal_secret token URL http://127.0.0.1/?token=unknown&code=other\nAuthorization: Bearer abc"
        result = probe.redact(text, ("literal_secret",))
        for value in ("literal_secret", "unknown", "other", "abc"):
            self.assertNotIn(value, result)
        self.assertIn("[REDACTED]", result)

    def test_requests_reject_missing_tokens_and_do_not_follow_redirects(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with mock.patch.dict(os.environ, {"http_proxy": "http://192.0.2.1:1"}):
                self.assertEqual(probe.request(base, expected=(403,))[0], 403)
                self.assertEqual(probe.request_json(base, "disposable"), {"status": 200})
                self.assertEqual(probe.request(base + "/redirect", expected=(302,))[0], 302)
                with self.assertRaises(probe.ProbeError):
                    probe.request(base + "/redirect")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_environment_does_not_inherit_credentials_or_python_paths(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(os.environ, {"SECRET_TEST_TOKEN": "secret", "PYTHONPATH": "/host/packages", "LD_LIBRARY_PATH": "/unrecorded/native"}):
                env = probe.isolated_env(root, Path(root) / "venv")
            self.assertNotIn("SECRET_TEST_TOKEN", env)
            self.assertNotIn("PYTHONPATH", env)
            self.assertNotIn("LD_LIBRARY_PATH", env)
            self.assertEqual(env["PYTHONNOUSERSITE"], "1")
            self.assertEqual(Path(env["JUPYTER_RUNTIME_DIR"]).stat().st_mode & 0o777, 0o700)

    def test_hub_fixture_denies_login_and_scopes_existing_user(self):
        with tempfile.TemporaryDirectory() as root:
            args = argparse.Namespace(user_env=Path(root) / "venv", node_bin=Path(root) / "node/bin",
                                      proxy=Path(root) / "proxy/bin/configurable-http-proxy")
            config = probe.hub_config("existing-user", args, root, (2000, 2001, 2002))
            compile(config, "fixture_config", "exec")
            self.assertIn("return None", config)
            self.assertIn("servers!user=existing-user", config)
            self.assertIn("c.Spawner.ip = '127.0.0.1'", config)
            self.assertNotIn("DummyAuthenticator", config)
            self.assertNotIn("admin:users", config)
            self.assertNotIn("sudo", config)
            self.assertIn("os.environ.pop('AMBISGIS_PROBE_TOKEN')", config)

    def test_missing_proxy_reports_explicit_integration_gap(self):
        args = argparse.Namespace(proxy=None)
        result = probe.hub_probe(args, None, None)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("not tested", result["reason"])

    def test_process_logs_are_sanitized_before_persistence(self):
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / "process.log"
            process = probe.Process("test", [sys.executable, "-c", "print('private-value')"],
                probe.isolated_env(root, Path(sys.prefix)), root, log, ("private-value",))
            process.proc.wait(timeout=5)
            report = process.close()
            self.assertEqual(report["remaining_processes"], 0)
            self.assertFalse(report["forced_cleanup"])
            self.assertNotIn("private-value", log.read_text())
            self.assertIn("[REDACTED]", log.read_text())

    def test_process_cleanup_reaps_detached_child(self):
        with tempfile.TemporaryDirectory() as root:
            child_path = Path(root) / "child.pid"
            script = ("import pathlib, subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], start_new_session=True)\n"
                f"pathlib.Path({str(child_path)!r}).write_text(str(child.pid))\n"
                "time.sleep(120)\n")
            process = probe.Process("tree", [sys.executable, "-c", script],
                probe.isolated_env(root, Path(sys.prefix)), root, Path(root) / "tree.log")
            try:
                probe.wait_until(child_path.exists, timeout=5)
                pid = int(child_path.read_text())
                probe.wait_until(lambda: pid in process.identities, timeout=5)
            finally:
                report = process.close(grace=1)
            identity = probe.process_identity(pid)
            self.assertTrue(identity is None or identity[2] == "Z")
            self.assertTrue(report["forced_cleanup"])
            self.assertEqual(report["remaining_processes"], 0)

    def test_readiness_fails_for_dead_process(self):
        with tempfile.TemporaryDirectory() as root:
            process = probe.Process("exited", [sys.executable, "-c", "raise SystemExit(2)"],
                probe.isolated_env(root, Path(sys.prefix)), root, Path(root) / "exit.log")
            try:
                process.proc.wait(timeout=5)
                with self.assertRaisesRegex(probe.ProbeError, "exited before readiness"):
                    probe.wait_until(lambda: False, process=process)
            finally:
                process.close()

    def test_notebook_trust_annotation_preserves_exact_code_and_outputs(self):
        expected = {"cells": [{"metadata": {}, "source": "print(1)", "outputs": ["1"]}]}
        reopened = {"cells": [{"metadata": {"trusted": True}, "source": "print(1)", "outputs": ["1"]}]}
        self.assertEqual(probe.validate_reopened_notebook(reopened, expected), [True])
        for field, value in (("source", "print(2)"), ("outputs", ["2"]), ("metadata", {"unrecognized": True})):
            changed = json.loads(json.dumps(reopened))
            changed["cells"][0][field] = value
            with self.subTest(field=field), self.assertRaises(probe.ProbeError):
                probe.validate_reopened_notebook(changed, expected)

    def test_owned_build_hash_and_installed_origin_are_bound(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            wheels = []
            for name in ("jupyterhub", "jupyterlab"):
                wheel = root / (name + "-1.0-py3-none-any.whl")
                with zipfile.ZipFile(wheel, "w") as archive:
                    archive.writestr(name + "-1.0.dist-info/METADATA", "Name: " + name + "\nVersion: 1.0\n")
                    archive.writestr(name + "/__init__.py", "# owned module\n")
                wheels.append({"path": wheel.name, "sha256": probe.sha256(wheel)})
            receipt = root / "build-report.json"
            receipt.write_text(json.dumps({"status": "passed", "wheels": wheels}))
            expected = probe.owned_build_wheels(receipt)
            module = root / "__init__.py"
            module.write_text("# owned module\n")
            package = {"version": "1.0", "module": str(module), "direct_url": {
                "url": expected["jupyterhub"]["path"].as_uri(), "archive_info": {
                    "hashes": {"sha256": expected["jupyterhub"]["sha256"]}}}}
            probe.verify_installed_origin("jupyterhub", package, expected)
            package["version"] = "2.0"
            with self.assertRaisesRegex(probe.ProbeError, "differs"):
                probe.verify_installed_origin("jupyterhub", package, expected)
            package["version"] = "1.0"
            module.write_text("# changed module\n")
            with self.assertRaisesRegex(probe.ProbeError, "imported module"):
                probe.verify_installed_origin("jupyterhub", package, expected)
            expected["jupyterhub"]["path"].write_bytes(b"substituted wheel")
            with self.assertRaisesRegex(probe.ProbeError, "hash"):
                probe.owned_build_wheels(receipt)

    def test_native_loader_directory_is_bound_to_receipt_and_artifacts(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            libdir = root / "pam/prefix/lib"
            libdir.mkdir(parents=True)
            artifacts = []
            for name in ("libpam", "libpam_misc"):
                path = libdir / (name + ".so.0.1")
                path.write_bytes(b"synthetic library for receipt safeguard test")
                (libdir / (name + ".so.0")).symlink_to(path.name)
                artifacts.append({"path": "prefix/lib/" + path.name, "sha256": probe.sha256(path)})
            native_report = root / "pam/report.json"
            native_report.write_text(json.dumps({"status": "passed", "artifacts": artifacts}))
            receipt = root / "build-report.json"
            receipt.write_text(json.dumps({"status": "passed", "native_library_dir": "pam/prefix/lib",
                                           "pam_report_sha256": probe.sha256(native_report)}))
            verified, evidence = probe.owned_native_libraries(receipt)
            self.assertEqual(verified, libdir)
            self.assertEqual(len(evidence["artifacts"]), 2)
            (libdir / "libunrecorded.so.0").write_bytes(b"unexpected")
            with self.assertRaisesRegex(probe.ProbeError, "unrecorded"):
                probe.owned_native_libraries(receipt)
            (libdir / "libunrecorded.so.0").unlink()
            (libdir / "libpam.so.0.1").write_bytes(b"changed")
            with self.assertRaisesRegex(probe.ProbeError, "path/hash"):
                probe.owned_native_libraries(receipt)

    def test_pid_reuse_is_not_signalled(self):
        process = object.__new__(probe.Process)
        process.identities = {1234: 100}
        with mock.patch.object(probe, "process_identity", return_value=(1, 200, "S")):
            self.assertEqual(process.alive(), [])


if __name__ == "__main__":
    unittest.main()
