#!/usr/bin/env python3
"""Disposable loopback Jupyter candidate check; never a deployment profile.

The Hub fixture refuses interactive authentication. Its ephemeral service has
only server lifecycle/read/access scopes for the invoking OS user. Every process
runs as that same user. This provides NO multi-user security isolation.
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile


class ProbeError(RuntimeError):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def redact(text, credentials=()):
    for secret in sorted(credentials, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)([?&](?:token|code|auth|key)=)[^\s&\"'<>]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*(?:token|bearer)\s+)\S+", r"\1[REDACTED]", text)
    return text


def loopback_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in {"http", "ws"} or parts.hostname != "127.0.0.1":
        raise ProbeError("runtime requests must use IPv4 loopback")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ProbeError("runtime URLs must not contain credentials, queries or fragments")
    return parts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, token=None, method="GET", body=None, expected=(200,), timeout=10):
    loopback_url(url)
    headers = {}
    if token:
        headers["Authorization"] = "token " + token
    if body is not None:
        body = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            status, data = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, data = exc.code, exc.read()
    if status not in expected:
        # Server error bodies may contain credentials; do not put them in reports.
        raise ProbeError(f"unexpected HTTP status {status} for {method} {urllib.parse.urlsplit(url).path}")
    return status, data


def request_json(*args, **kwargs):
    status, data = request(*args, **kwargs)
    return json.loads(data) if data else None


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def is_listening(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_until(check, *, timeout=60, process=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.proc.poll() is not None:
            raise ProbeError(f"{process.name} exited before readiness; inspect sanitized log")
        try:
            result = check()
            if result:
                return result
        except (OSError, urllib.error.URLError, ProbeError):
            pass
        time.sleep(0.15)
    raise ProbeError("runtime readiness timed out")


def process_identity(pid):
    """Linux PID start time prevents accidentally signalling a reused PID."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(stat[1]), int(stat[19]), stat[0]
    except (FileNotFoundError, ProcessLookupError):
        return None


class Process:
    def __init__(self, name, command, env, cwd, log, credentials=()):
        self.name = name
        self.log = Path(log)
        self.credentials = tuple(credentials)
        self.proc = subprocess.Popen(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     start_new_session=True, text=True, errors="replace")
        self.identities = {}
        identity = process_identity(self.proc.pid)
        if identity:
            self.identities[self.proc.pid] = identity[1]
        self.stop_tracking = threading.Event()
        self.reader = threading.Thread(target=self._drain, daemon=True)
        self.tracker = threading.Thread(target=self._track, daemon=True)
        self.reader.start()
        self.tracker.start()

    def _drain(self):
        with self.log.open("w") as stream:
            for line in self.proc.stdout:
                stream.write(redact(line, self.credentials))
                stream.flush()

    def _track(self):
        while not self.stop_tracking.wait(0.1):
            snapshot = {}
            for entry in Path("/proc").iterdir():
                if entry.name.isdigit():
                    identity = process_identity(int(entry.name))
                    if identity:
                        snapshot[int(entry.name)] = identity
            changed = True
            while changed:
                changed = False
                for pid, (parent, started, state) in snapshot.items():
                    if pid not in self.identities and parent in self.identities:
                        parent_identity = snapshot.get(parent)
                        if parent_identity and parent_identity[1] == self.identities[parent]:
                            self.identities[pid] = started
                            changed = True

    def alive(self):
        return [pid for pid, started in tuple(self.identities.items())
                if (identity := process_identity(pid)) and identity[1] == started and identity[2] != "Z"]

    def loopback_listeners(self):
        inodes = set()
        for pid in self.alive():
            try:
                descriptors = list(Path(f"/proc/{pid}/fd").iterdir())
            except FileNotFoundError:
                continue
            for descriptor in descriptors:
                try:
                    target = os.readlink(descriptor)
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if target.startswith("socket:["):
                    inodes.add(target[8:-1])
        listeners = []
        for table in ("tcp", "tcp6"):
            for line in Path("/proc/net/" + table).read_text().splitlines()[1:]:
                fields = line.split()
                if fields[3] != "0A" or fields[9] not in inodes:
                    continue
                address, port = fields[1].split(":")
                if table != "tcp" or address != "0100007F":
                    raise ProbeError("fixture process has a non-IPv4-loopback TCP listener")
                listeners.append({"address": "127.0.0.1", "port": int(port, 16)})
        if not listeners:
            raise ProbeError("no runtime TCP listeners observed")
        return sorted(listeners, key=lambda item: item["port"])

    def close(self, grace=15):
        forced = False
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                forced = True
        # Kernels and single-user servers can create their own process sessions.
        # Record their identities while running, then clean up only this tree.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            pids = self.alive()
            if pids:
                forced = True
            for pid in reversed(pids):
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
            deadline = time.monotonic() + 3
            while self.alive() and time.monotonic() < deadline:
                time.sleep(0.05)
        self.proc.wait(timeout=5)
        self.stop_tracking.set()
        self.tracker.join(timeout=3)
        self.reader.join(timeout=3)
        if not self.reader.is_alive():
            self.proc.stdout.close()
        if self.alive() or self.reader.is_alive():
            raise ProbeError(f"{self.name} process cleanup incomplete")
        return {"exit_code": self.proc.returncode, "forced_cleanup": forced,
                "remaining_processes": 0}


def isolated_env(scratch, python_env, node_bin=None, native_library_dir=None):
    scratch = Path(scratch)
    for child in ("home", "config", "data", "runtime", "ipython", "tmp"):
        (scratch / child).mkdir(parents=True, exist_ok=True, mode=0o700)
    search_path = [str(Path(python_env) / "bin")]
    if node_bin:
        search_path.append(str(node_bin))
    search_path.extend(["/usr/bin", "/bin"])
    env = {"PATH": os.pathsep.join(search_path), "HOME": str(scratch / "home"),
            "JUPYTER_CONFIG_DIR": str(scratch / "config"),
            "JUPYTER_DATA_DIR": str(scratch / "data"),
            "JUPYTER_RUNTIME_DIR": str(scratch / "runtime"),
            "IPYTHONDIR": str(scratch / "ipython"), "TMPDIR": str(scratch / "tmp"),
            "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1", "LANG": "C.UTF-8",
            "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    if native_library_dir is not None:
        env["LD_LIBRARY_PATH"] = str(native_library_dir)
    return env


INSPECT_CODE = r'''
import hashlib, importlib, importlib.metadata as md, json, pathlib, sys
names = json.loads(sys.argv[1])
result = {"python": sys.version, "prefix": sys.prefix, "packages": {}}
for distribution, module in names.items():
    dist = md.distribution(distribution)
    imported = importlib.import_module(module)
    origin = pathlib.Path(imported.__file__).resolve()
    if not origin.is_relative_to(pathlib.Path(sys.prefix).resolve()):
        raise RuntimeError("package imported from outside requested environment")
    direct = dist.read_text("direct_url.json")
    result["packages"][distribution] = {"version": dist.version, "module": str(origin),
        "direct_url": json.loads(direct) if direct else None}
if "jupyterlab" in names:
    from jupyterlab.commands import get_app_dir
    static = (pathlib.Path(get_app_dir()) / "static").resolve()
    if not static.is_relative_to(pathlib.Path(sys.prefix).resolve()):
        raise RuntimeError("Lab assets outside requested environment")
    files = sorted(p for p in static.rglob("*") if p.is_file())
    if not files or not any(p.suffix == ".js" for p in files):
        raise RuntimeError("built Lab frontend assets missing")
    records = [{"path": str(p.relative_to(static)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in files]
    result["lab_assets"] = {"directory": str(static), "file_count": len(files),
        "sha256": hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
        "files": records}
print(json.dumps(result))
'''


def owned_build_wheels(report_path):
    report_path = Path(report_path).resolve()
    receipt = json.loads(report_path.read_text())
    if receipt.get("status") != "passed":
        raise ProbeError("selected owned build receipt did not pass")
    expected = {}
    for item in receipt["wheels"]:
        wheel = (report_path.parent / item["path"]).resolve()
        if not wheel.is_relative_to(report_path.parent):
            raise ProbeError("owned wheel escapes build receipt directory")
        if sha256(wheel) != item["sha256"]:
            raise ProbeError("owned wheel hash does not match build receipt")
        with zipfile.ZipFile(wheel) as archive:
            metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise ProbeError("owned wheel metadata missing or ambiguous")
            metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
        name = metadata["Name"].lower().replace("-", "_")
        if name in expected:
            raise ProbeError("duplicate owned wheel in build receipt")
        expected[name] = {"path": wheel, "sha256": item["sha256"], "version": metadata["Version"]}
    if set(expected) != {"jupyterhub", "jupyterlab"}:
        raise ProbeError("build receipt must identify exactly the owned Hub and Lab wheels")
    return expected


def owned_native_libraries(build_report):
    build_report = Path(build_report).resolve()
    build = json.loads(build_report.read_text())
    relative = build.get("native_library_dir")
    if relative is None:
        return None, None
    if build.get("status") != "passed":
        raise ProbeError("native library build receipt did not pass")
    library_dir = (build_report.parent / relative).resolve()
    receipt_path = build_report.parent / "pam/report.json"
    if library_dir != (receipt_path.parent / "prefix/lib").resolve():
        raise ProbeError("native library directory differs from run-local PAM output")
    if not library_dir.is_relative_to(build_report.parent):
        raise ProbeError("native library directory escapes selected build")
    if sha256(receipt_path) != build.get("pam_report_sha256"):
        raise ProbeError("native library receipt hash differs from selected build")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("status") != "passed":
        raise ProbeError("native library receipt did not pass")
    verified = set()
    for artifact in receipt["artifacts"]:
        path = (receipt_path.parent / artifact["path"]).resolve()
        if path.parent != library_dir or sha256(path) != artifact["sha256"]:
            raise ProbeError("native library artifact path/hash differs from receipt")
        verified.add(path)
    for path in library_dir.glob("*.so*"):
        if path.resolve() not in verified:
            raise ProbeError("unrecorded native library in runtime loader directory")
    for name in ("libpam.so.0", "libpam_misc.so.0"):
        if (library_dir / name).resolve() not in verified:
            raise ProbeError("required PAM loader symlink does not target a verified artifact")
    return library_dir, {"directory": str(library_dir), "receipt": str(receipt_path),
        "receipt_sha256": sha256(receipt_path), "artifacts": receipt["artifacts"],
        "scope": "test-only libpam/libpam_misc; no host PAM configuration or authentication"}


def verify_installed_origin(name, package, expected):
    origin = package.get("direct_url")
    wanted = expected[name]
    if not origin:
        raise ProbeError(f"{name} missing local build origin")
    url = urllib.parse.urlsplit(origin.get("url", ""))
    actual_hash = origin.get("archive_info", {}).get("hashes", {}).get("sha256")
    if (url.scheme != "file" or url.netloc or url.query or url.fragment
            or Path(urllib.parse.unquote(url.path)).resolve() != wanted["path"]
            or actual_hash != wanted["sha256"] or package["version"] != wanted["version"]):
        raise ProbeError(f"{name} installed origin/version differs from selected owned build")
    with zipfile.ZipFile(wanted["path"]) as archive:
        wheel_module = archive.read(name + "/__init__.py")
    if Path(package["module"]).read_bytes() != wheel_module:
        raise ProbeError(f"{name} imported module differs from selected owned wheel")


def inspect_environment(prefix, packages, expected, native_library_dir=None):
    with tempfile.TemporaryDirectory(prefix="ambisgis-inspect-") as scratch:
        proc = subprocess.run([str(Path(prefix) / "bin/python"), "-I", "-c", INSPECT_CODE,
                               json.dumps(packages)], env=isolated_env(scratch, prefix, native_library_dir=native_library_dir),
                              capture_output=True, text=True, timeout=90)
    if proc.returncode:
        raise ProbeError("installed-origin/assets inspection failed")
    result = json.loads(proc.stdout)
    for name in ("jupyterhub", "jupyterlab"):
        package = result["packages"].get(name)
        if not package:
            continue
        verify_installed_origin(name, package, expected)
    if "lab_assets" in result:
        with zipfile.ZipFile(expected["jupyterlab"]["path"]) as archive:
            marker = ".data/data/share/jupyter/lab/static/"
            wheel_assets = sorted(({"path": name.split(marker, 1)[1],
                "sha256": hashlib.sha256(archive.read(name)).hexdigest()}
                for name in archive.namelist() if marker in name and not name.endswith("/")),
                key=lambda item: item["path"])
        if result["lab_assets"]["files"] != wheel_assets:
            raise ProbeError("installed Lab frontend assets differ from selected owned wheel")
    result["owned_wheel_binding"] = "versions, local wheel paths/hashes, imported module bytes and Lab assets match selected build"
    return result


KERNEL_CODE = r'''
import datetime, json, os, sys, time, uuid
import websocket
settings = json.load(sys.stdin)
base = settings["base"]
headers = ["Authorization: token " + settings["token"]]
ws = websocket.create_connection(base.replace("http://", "ws://", 1) +
    "api/kernels/" + settings["kernel"] + "/channels", header=headers,
    origin="http://" + base.split("/")[2], timeout=30, http_no_proxy=["127.0.0.1"])
msgid = uuid.uuid4().hex
message = {"header": {"msg_id": msgid, "username": "runtime-probe", "session": uuid.uuid4().hex,
    "date": datetime.datetime.now(datetime.timezone.utc).isoformat(), "msg_type": "execute_request",
    "version": "5.3"}, "parent_header": {}, "metadata": {}, "channel": "shell", "buffers": [],
    "content": {"code": settings["code"], "silent": False, "store_history": True,
    "user_expressions": {}, "allow_stdin": False, "stop_on_error": True}}
ws.send(json.dumps(message))
reply = None
execution_count = None
idle = False
output = ""
deadline = time.monotonic() + 45
try:
    while time.monotonic() < deadline and not (idle and reply):
        incoming = json.loads(ws.recv())
        if incoming.get("parent_header", {}).get("msg_id") != msgid:
            continue
        kind = incoming["msg_type"]
        content = incoming["content"]
        if kind == "execute_reply":
            reply = content["status"]
            execution_count = content["execution_count"]
        elif kind == "stream":
            output += content["text"]
        elif kind == "error":
            raise RuntimeError("kernel reported execution error")
        elif kind == "status" and content["execution_state"] == "idle":
            idle = True
    if reply != "ok" or not idle or settings["expected"] not in output:
        raise RuntimeError("missing successful execute reply, idle status or expected output")
    print(json.dumps({"execute_reply": reply, "execution_count": execution_count, "idle_received": idle, "stdout": output}))
finally:
    ws.close()
'''


def validate_reopened_notebook(reopened, expected):
    # Contents API reports server trust separately from stored notebook source.
    # Permit only that documented boolean annotation; compare every other cell field.
    cells = json.loads(json.dumps(reopened["cells"]))
    trusted = []
    for cell in cells:
        marker = cell["metadata"].pop("trusted", None)
        if marker is not None and not isinstance(marker, bool):
            raise ProbeError("invalid server notebook trust annotation")
        trusted.append(marker)
    if cells != expected["cells"]:
        raise ProbeError("saved/reopened notebook cell source, outputs or structure differ")
    return trusted


def notebook_probe(base, token, user_env, env, evidence_dir, process):
    loopback_url(base)
    request(base + "api/contents", expected=(401, 403, 302))
    request(base + "api/contents", token="invalid-disposable-token", expected=(401, 403, 302))
    lab_status, lab = request(base + "lab", token=token)
    if b"jupyter" not in lab.lower():
        raise ProbeError("Lab page did not contain expected application content")
    specs = request_json(base + "api/kernelspecs", token)
    if "python3" not in specs["kernelspecs"]:
        raise ProbeError("python3 kernel not registered")
    kernel = request_json(base + "api/kernels", token, method="POST",
                          body={"name": "python3"}, expected=(201,))
    code = "import sys\nassert sys.prefix == " + repr(str(Path(user_env).resolve())) + "\nprint('AMBISGIS_KERNEL_RESULT=' + str(sum(i*i for i in range(10))))"
    expected = "AMBISGIS_KERNEL_RESULT=285\n"
    try:
        proc = subprocess.run([str(Path(user_env) / "bin/python"), "-I", "-c", KERNEL_CODE],
            input=json.dumps({"base": base, "token": token, "kernel": kernel["id"],
                              "code": code, "expected": expected}),
            env=env, capture_output=True, text=True, timeout=60)
        if proc.returncode:
            raise ProbeError("kernel WebSocket execution failed: " + redact(proc.stderr[-2000:], (token,)))
        execution = json.loads(proc.stdout)
        listeners = process.loopback_listeners()
        notebook = {"cells": [{"cell_type": "code", "id": "runtime-probe", "execution_count": execution["execution_count"],
            "metadata": {}, "source": code, "outputs": [{"output_type": "stream", "name": "stdout",
            "text": execution["stdout"]}]}], "metadata": {"kernelspec": {"display_name": "Python 3",
            "language": "python", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 5}
        path = "api/contents/ambisgis-runtime-probe.ipynb"
        request(base + path, token, method="PUT", body={"type": "notebook", "format": "json",
                "content": notebook}, expected=(200, 201))
        reopened = request_json(base + path, token)
        trusted = validate_reopened_notebook(reopened["content"], notebook)
        notebook_path = Path(evidence_dir) / "executed-notebook.ipynb"
        notebook_path.write_text(json.dumps(reopened["content"], indent=2) + "\n")
        return {"authentication": "missing and invalid tokens rejected", "lab_http_status": lab_status,
                "execution": execution, "notebook_save_reopen": "passed",
                "notebook_sha256": sha256(notebook_path), "server_trust_annotations": trusted,
                "observed_tcp_listeners": listeners}
    finally:
        request(base + "api/kernels/" + kernel["id"], token, method="DELETE", expected=(204,))


def standalone_lab(args, scratch, output):
    port = free_port()
    token = secrets.token_hex(32)
    env = isolated_env(scratch, args.user_env, args.node_bin, getattr(args, "native_library_dir", None))
    env["AMBISGIS_PROBE_TOKEN"] = token
    config = Path(scratch) / "lab_config.py"
    config.write_text("import os\nc = get_config()\n"
        "c.ServerApp.ip = '127.0.0.1'\n"
        f"c.ServerApp.port = {port}\n"
        "c.ServerApp.port_retries = 0\nc.ServerApp.open_browser = False\n"
        "c.ServerApp.log_level = 'WARN'\nc.ServerApp.root_dir = " + repr(str(Path(scratch) / "home")) + "\n"
        "c.IdentityProvider.token = os.environ.pop('AMBISGIS_PROBE_TOKEN')\n"
        "c.ServerApp.allow_remote_access = False\n"
        "c.LabApp.extension_manager = 'readonly'\n"
        "c.KernelSpecManager.allowed_kernelspecs = {'python3'}\n")
    process = Process("lab", [str(args.user_env / "bin/python"), "-I", "-m", "jupyterlab", "--config", str(config)],
                      env, scratch, output / "lab.log", (token,))
    env.pop("AMBISGIS_PROBE_TOKEN")
    base = f"http://127.0.0.1:{port}/"
    result = {}
    try:
        wait_until(lambda: request_json(base + "api/status", token), process=process)
        result.update(notebook_probe(base, token, args.user_env, env, output, process))
        request(base + "api/shutdown", token, method="POST", expected=(200, 202))
        process.proc.wait(timeout=20)
    finally:
        result["shutdown"] = process.close()
    if is_listening(port):
        raise ProbeError("Lab listener remained after shutdown")
    if result["shutdown"]["forced_cleanup"]:
        raise ProbeError("Lab required forced cleanup instead of orderly shutdown")
    return result


def hub_config(user, args, scratch, ports):
    public, internal, proxy_api = ports
    user_root = Path(scratch) / "user"
    user_root.mkdir(mode=0o700)
    user_env = isolated_env(user_root, args.user_env, args.node_bin, getattr(args, "native_library_dir", None))
    proxy_command = [str(args.proxy)]
    if args.node_bin:
        proxy_command.insert(0, str(args.node_bin / "node"))
    return "\n".join([
        "import os", "from jupyterhub.auth import Authenticator", "c = get_config()",
        "class ClosedFixtureAuthenticator(Authenticator):",
        "    async def authenticate(self, handler, data):", "        return None",
        "c.JupyterHub.authenticator_class = ClosedFixtureAuthenticator",
        f"c.Authenticator.allowed_users = {{{user!r}}}",
        f"c.JupyterHub.bind_url = 'http://127.0.0.1:{public}'",
        f"c.JupyterHub.hub_bind_url = 'http://127.0.0.1:{internal}'",
        f"c.ConfigurableHTTPProxy.api_url = 'http://127.0.0.1:{proxy_api}'",
        f"c.ConfigurableHTTPProxy.command = {proxy_command!r}",
        "c.ConfigurableHTTPProxy.log_level = 'warn'",
        "c.ConfigurableHTTPProxy.auth_token = os.environ.pop('AMBISGIS_PROXY_TOKEN')",
        "c.JupyterHub.log_level = 'WARN'",
        "c.JupyterHub.db_url = 'sqlite:///" + str(Path(scratch) / "hub.sqlite") + "'",
        f"c.JupyterHub.cookie_secret_file = {str(Path(scratch) / 'cookie-secret')!r}",
        "c.JupyterHub.services = [{'name': 'runtime-probe', 'api_token': os.environ.pop('AMBISGIS_PROBE_TOKEN')}]",
        f"c.JupyterHub.load_roles = [{{'name': 'runtime-probe', 'services': ['runtime-probe'], 'scopes': "
        f"['read:users!user={user}', 'servers!user={user}', 'access:servers!user={user}']}}]",
        "c.JupyterHub.spawner_class = 'jupyterhub.spawner.SimpleLocalProcessSpawner'",
        f"c.SimpleLocalProcessSpawner.home_dir_template = {str(user_root / 'home')!r}",
        "c.Spawner.ip = '127.0.0.1'", "c.Spawner.default_url = '/lab'",
        f"c.Spawner.cmd = [{str(args.user_env / 'bin/jupyterhub-singleuser')!r}]",
        "c.Spawner.args = ['--ServerApp.log_level=WARN', '--ServerApp.open_browser=False', '--LabApp.extension_manager=readonly']",
        "c.Spawner.env_keep = []", f"c.Spawner.environment = {user_env!r}",
        "c.LocalProcessSpawner.popen_kwargs = {'start_new_session': False}",
        "c.Spawner.start_timeout = 60", "c.Spawner.http_timeout = 45",
        "c.JupyterHub.cleanup_servers = True", "c.JupyterHub.cleanup_proxy = True", ""])


def hub_probe(args, scratch, output):
    if not args.proxy:
        return {"status": "skipped", "reason": "--proxy was not provided; Hub/proxy integration not tested"}
    user = pwd.getpwuid(os.getuid()).pw_name
    token, proxy_token = secrets.token_hex(32), secrets.token_hex(32)
    ports = set()
    while len(ports) < 3:
        ports.add(free_port())
    public, internal, proxy_api = list(ports)
    env = isolated_env(scratch, args.hub_env, args.node_bin, getattr(args, "native_library_dir", None))
    env.update(AMBISGIS_PROBE_TOKEN=token, AMBISGIS_PROXY_TOKEN=proxy_token)
    config = Path(scratch) / "hub_config.py"
    config.write_text(hub_config(user, args, scratch, (public, internal, proxy_api)))
    process = Process("hub", [str(args.hub_env / "bin/python"), "-I", "-m", "jupyterhub", "--config", str(config)],
                      env, scratch, output / "hub.log", (token, proxy_token))
    env.pop("AMBISGIS_PROBE_TOKEN")
    env.pop("AMBISGIS_PROXY_TOKEN")
    api = f"http://127.0.0.1:{internal}/hub/api/"
    quoted_user = urllib.parse.quote(user, safe="")
    user_api = api + "users/" + quoted_user
    result = {"status": "passed", "profile": "one trusted OS user; no multi-user isolation"}
    spawned = False
    try:
        wait_until(lambda: request_json(user_api, token), process=process)
        # Scope confinement: fixture token cannot list users or create new users.
        request(api + "users", token, expected=(403,))
        request(user_api + "/server", token, method="POST", expected=(201, 202))
        spawned = True
        wait_until(lambda: request_json(user_api, token).get("servers", {}).get("", {}).get("ready"),
                   process=process, timeout=90)
        base = f"http://127.0.0.1:{public}/user/{quoted_user}/"
        wait_until(lambda: request_json(base + "api/status", token), process=process)
        result.update(notebook_probe(base, token, args.user_env, env, output, process))
        request(user_api + "/server", token, method="DELETE", expected=(204, 202))
        spawned = False
        wait_until(lambda: not request_json(user_api, token).get("servers"), process=process)
        result["singleuser_stopped"] = True
    finally:
        if spawned and process.proc.poll() is None:
            try:
                request(user_api + "/server", token, method="DELETE", expected=(204, 202))
            except (ProbeError, OSError):
                pass
        result["shutdown"] = process.close(grace=25)
    if any(is_listening(port) for port in (public, internal, proxy_api)):
        raise ProbeError("Hub/proxy listener remained after shutdown")
    if result["shutdown"]["forced_cleanup"]:
        raise ProbeError("Hub required forced cleanup instead of orderly shutdown")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub-env", type=Path, required=True)
    parser.add_argument("--user-env", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--node-bin", type=Path)
    parser.add_argument("--proxy", type=Path)
    parser.add_argument("--build-report", type=Path, help="default: build-report.json alongside requested environments")
    args = parser.parse_args(argv)
    if os.geteuid() == 0:
        parser.error("run this disposable fixture as an unprivileged existing OS user")
    if not Path("/proc/self/stat").exists():
        parser.error("this process-cleanup fixture requires Linux /proc")
    for name in ("hub_env", "user_env", "work_root", "node_bin", "proxy", "build_report"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.absolute())
    if args.hub_env.resolve() == args.user_env.resolve():
        parser.error("Hub and user environments must be separate")
    args.work_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="runtime-", dir=args.work_root))
    os.chmod(output, 0o700)
    report = {"schema": 1, "status": "failed", "profile": "disposable IPv4-loopback trusted-user development",
              "network_boundary": "loopback listeners; outbound network isolation not claimed",
              "not_covered": ["multi-user isolation", "production SSO", "browser execution/accessibility",
                              "GIS native profiles", "scheduler", "quotas", "host restart/restore"]}
    try:
        build_report = args.build_report or args.hub_env.parent / "build-report.json"
        expected = owned_build_wheels(build_report)
        args.native_library_dir, native_receipt = owned_native_libraries(build_report)
        if native_receipt is not None:
            report["native_libraries"] = native_receipt
        report["build_receipt"] = {"path": str(build_report), "sha256": sha256(build_report)}
        report["runtime_executables"] = {}
        for name, path in (("node", args.node_bin / "node" if args.node_bin else None), ("proxy", args.proxy)):
            if path:
                report["runtime_executables"][name] = {"path": str(path), "resolved": str(path.resolve()),
                                                       "sha256": sha256(path)}
        report["hub_environment"] = inspect_environment(args.hub_env, {"jupyterhub": "jupyterhub"}, expected, getattr(args, "native_library_dir", None))
        report["user_environment"] = inspect_environment(args.user_env, {
            "jupyterhub": "jupyterhub", "jupyterlab": "jupyterlab", "jupyter_server": "jupyter_server",
            "ipykernel": "ipykernel", "jupyter_client": "jupyter_client", "websocket-client": "websocket"}, expected, getattr(args, "native_library_dir", None))
        with tempfile.TemporaryDirectory(prefix="private-", dir=output) as private:
            private = Path(private)
            for name, callback in (("standalone", standalone_lab), ("hub", hub_probe)):
                scratch, evidence = private / name, output / name
                scratch.mkdir(mode=0o700)
                evidence.mkdir(mode=0o700)
                report[name] = callback(args, scratch, evidence)
        report["status"] = "passed"
    except Exception as exc:
        report["error"] = str(exc)
    report["artifacts"] = [{"path": str(path.relative_to(output)), "sha256": sha256(path)}
        for path in sorted(output.rglob("*")) if path.is_file()]
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "report": str(report_path), "sha256": sha256(report_path)}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
