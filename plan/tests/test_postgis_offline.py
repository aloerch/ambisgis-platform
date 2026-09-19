"""Real subprocess seccomp checks; never restrict the unittest process itself."""

import ctypes
import errno
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


RUNNER = Path(__file__).resolve().parents[2] / "build-support/postgis/offline_exec.py"
SPEC = importlib.util.spec_from_file_location("postgis_offline_exec", RUNNER)
OFFLINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OFFLINE)
SUPPORTED = sys.platform == "linux" and platform.machine() == "x86_64" and ctypes.sizeof(ctypes.c_void_p) == 8


class PlatformChecks(unittest.TestCase):
    def test_unsupported_architecture_refused(self):
        with patch.object(OFFLINE.platform, "machine", return_value="aarch64"):
            with self.assertRaisesRegex(OFFLINE.OfflineError, "Only Linux x86_64"):
                OFFLINE.check_platform()

    def test_unsupported_kernel_refused(self):
        with patch.object(OFFLINE.platform, "machine", return_value="x86_64"), \
                patch.object(OFFLINE.Path, "read_text", return_value="allow errno"):
            with self.assertRaisesRegex(OFFLINE.OfflineError, "Required seccomp actions"):
                OFFLINE.check_platform()


@unittest.skipUnless(SUPPORTED, "Real seccomp execution requires Linux x86_64")
class OfflineExecution(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ambisgis-offline-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.evidence = self.root / "evidence.json"

    def run_command(self, command, **kwargs):
        return subprocess.run([sys.executable, str(RUNNER), "--evidence",
                               str(self.evidence), "--", *command],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=30, **kwargs)

    def run_python(self, code, **kwargs):
        return self.run_command([sys.executable, "-c", code], **kwargs)

    def test_real_socket_filter_and_child_inheritance(self):
        probe = '''
import errno, json, socket
results = {}
for family in (socket.AF_INET, socket.AF_INET6, socket.AF_NETLINK, socket.AF_PACKET):
    try:
        socket.socket(family, socket.SOCK_DGRAM).close()
        results[family.name] = 0
    except OSError as exc:
        results[family.name] = exc.errno
assert all(value == errno.EPERM for value in results.values()), results
left, right = socket.socketpair()
with left, right:
    left.sendall(b"inherited-local")
    assert right.recv(64) == b"inherited-local"
print(json.dumps(results))
'''
        code = f"import subprocess,sys; subprocess.run([sys.executable, '-c', {probe!r}], check=True)"
        result = self.run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(json.loads(result.stdout).values()), {errno.EPERM})
        evidence = json.loads(self.evidence.read_text())
        self.assertEqual(evidence["status"], "completed")
        self.assertEqual(evidence["command_exit_code"], 0)
        self.assertEqual(evidence["kernel_state"]["no_new_privs"], 1)
        self.assertEqual(evidence["kernel_state"]["seccomp_mode"], 2)
        self.assertTrue(all(probe["passed"] for probe in evidence["probes"]))
        self.assertEqual([p["errno"] for p in evidence["probes"][:3]], [1, 1, 0])

    def test_unix_path_server_connections_still_work(self):
        path = str(self.root / "postgres-like.sock")
        code = f'''
import socket
with socket.socket(socket.AF_UNIX) as server, socket.socket(socket.AF_UNIX) as client:
    server.bind({path!r})
    server.listen(1)
    client.connect({path!r})
    accepted, _ = server.accept()
    with accepted:
        client.sendall(b"query")
        assert accepted.recv(64) == b"query"
'''
        result = self.run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_network_capable_auxiliary_syscalls_denied(self):
        numbers = [OFFLINE.SYSCALLS[name] for name in (
            "io_uring_setup", "io_uring_enter", "io_uring_register", "pidfd_getfd", "ptrace")]
        code = f'''
import ctypes, errno
libc = ctypes.CDLL(None, use_errno=True)
for number in {numbers!r}:
    ctypes.set_errno(0)
    result = libc.syscall(number, -1, 0, 0, 0, 0, 0)
    assert result == -1 and ctypes.get_errno() == errno.EPERM, (number, result, ctypes.get_errno())
'''
        result = self.run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_x32_syscall_abi_is_killed(self):
        result = self.run_python("import ctypes; ctypes.CDLL(None).syscall(0x40000000 | 39)")
        self.assertEqual(result.returncode, 128 + signal.SIGSYS, result.stderr)
        self.assertEqual(json.loads(self.evidence.read_text())["command_exit_code"], -signal.SIGSYS)

    def test_inherited_descriptor_closed(self):
        import fcntl
        with socket.socket(socket.AF_INET) as inherited:
            descriptor = fcntl.fcntl(inherited.fileno(), fcntl.F_DUPFD, 1000)
            self.addCleanup(os.close, descriptor)
            result = self.run_python(f'''
import errno, os
try:
    os.fstat({descriptor})
except OSError as exc:
    assert exc.errno == errno.EBADF
else:
    raise AssertionError("inherited descriptor remains open")
''', pass_fds=(descriptor,))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(descriptor, json.loads(self.evidence.read_text())["closed_inherited_fds"])

    def test_socket_standard_input_refused_before_command(self):
        marker = self.root / "must-not-exist"
        left, right = socket.socketpair()
        with left, right:
            result = self.run_python(f"open({str(marker)!r}, 'w').close()", stdin=left)
        self.assertEqual(result.returncode, 125)
        self.assertIn("Standard descriptor 0 is a socket", result.stderr)
        self.assertFalse(marker.exists())

    def test_command_failure_is_preserved(self):
        result = self.run_python("raise SystemExit(17)")
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertEqual(json.loads(self.evidence.read_text())["command_exit_code"], 17)

    def test_missing_executable_refused(self):
        result = self.run_command([str(self.root / "missing-build")])
        self.assertEqual(result.returncode, 125)
        self.assertIn("Command executable not found", result.stderr)
        self.assertFalse(self.evidence.exists())

    def test_existing_evidence_preserved_and_command_not_run(self):
        self.evidence.write_text("existing evidence\n")
        marker = self.root / "must-not-exist"
        result = self.run_python(f"open({str(marker)!r}, 'w').close()")
        self.assertEqual(result.returncode, 125)
        self.assertEqual(self.evidence.read_text(), "existing evidence\n")
        self.assertFalse(marker.exists())

    def test_filter_install_failure_never_launches_command(self):
        marker = self.root / "must-not-exist"
        # Run main in its own process because main intentionally closes inherited fds.
        code = f'''
import importlib.util
spec = importlib.util.spec_from_file_location("offline", {str(RUNNER)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def fail():
    raise module.OfflineError("simulated unavailable seccomp")
module.install_filter = fail
raise SystemExit(module.main(["--evidence", {str(self.evidence)!r}, "--",
    {sys.executable!r}, "-c", {f"open({str(marker)!r}, 'w').close()"!r}]))
'''
        result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 125)
        self.assertFalse(marker.exists())
        self.assertEqual(json.loads(self.evidence.read_text())["status"], "refused")


if __name__ == "__main__":
    unittest.main()
