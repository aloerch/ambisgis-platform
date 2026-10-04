"""Bounded, read-only observations of this installation's native direct DNS."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

MAX_FILE = 1024 * 1024
MAX_EXE = 64 * 1024 * 1024
TRANSIENT_CLEANUP = frozenset({"live_retained", "pidfile_retained", "config_retained"})


class ObservationError(ValueError):
    """A fixed classification; never include raw process/configuration contents."""


def require(condition, code):
    if not condition:
        raise ObservationError(code)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def clean_path(value):
    value = str(value)
    p = Path(value)
    require(p.is_absolute() and str(p) == value and value != "/" and
            ".." not in p.parts and "\x00" not in value, "invalid_binding")
    return p


@dataclass(frozen=True)
class Expectation:
    root: Path
    bundle_root: Path
    install_id: str
    executable_sha256: str
    host_uid: int

    @property
    def directory(self):
        return self.root / "runtime/run/networks/aardvark-dns"

    @property
    def pidfile(self):
        return self.directory / "aardvark.pid"

    @property
    def entry(self):
        return self.directory / ("ambisgis-" + self.install_id.replace("-", "") + "_internal%int")

    @property
    def netns(self):
        return self.root / "runtime/run/networks/rootless-netns/rootless-netns"

    @property
    def executable(self):
        return self.bundle_root / "runtime/helpers/aardvark-dns"

    @property
    def binding(self):
        return digest(json.dumps([str(self.root), str(self.bundle_root), self.install_id,
                                  self.executable_sha256, self.host_uid],
                                 separators=(",", ":")).encode())


def from_verified(directory, product, bundle_root, runtime_files_manifest, host_uid):
    """Caller already verified the installation, bundle and its files manifest."""
    root, bundle = clean_path(directory), clean_path(bundle_root)
    require(type(host_uid) is int and 0 < host_uid < 2**32, "invalid_binding")
    try:
        install_id = product["install_id"]
        require(str(uuid.UUID(install_id)) == install_id, "invalid_binding")
        require(product["bundle"]["path"] == str(bundle / "bundle.json"), "invalid_binding")
        entries = [f for f in runtime_files_manifest["files"]
                   if f["path"] == "runtime/helpers/aardvark-dns"]
        require(len(entries) == 1 and
                re.fullmatch("[0-9a-f]{64}", entries[0]["sha256"]) is not None,
                "invalid_binding")
        return Expectation(root, bundle, install_id, entries[0]["sha256"], host_uid)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ObservationError("invalid_binding") from None


def parse_pid(raw):
    require(re.fullmatch(rb"[1-9][0-9]{0,9}\n?", raw) is not None, "invalid_pidfile")
    pid = int(raw)
    require(1 < pid < 2**31, "invalid_pidfile")
    return pid


def parse_stat(raw, pid):
    try:
        first, tail = raw.split(b" (", 1)
        fields = tail.rsplit(b") ", 1)[1].split()
        require(int(first) == pid and len(fields) >= 20, "process_changed")
        ticks = int(fields[19])
        state = fields[0].decode("ascii")
        require(ticks > 0 and len(state) == 1 and state in "RSDZTtXxKWPI", "invalid_process_stat")
        return ticks, state
    except (IndexError, ValueError, UnicodeError):
        raise ObservationError("invalid_process_stat") from None


def parse_session(raw, pid):
    parse_stat(raw, pid)
    try:
        fields = raw.rsplit(b") ", 1)[1].split()
        pgrp, session = int(fields[2]), int(fields[3])
        require(0 < pgrp < 2**31 and 0 < session < 2**31, "invalid_process_session")
        return pgrp, session
    except (IndexError, ValueError):
        raise ObservationError("invalid_process_session") from None


def parse_map(raw):
    try:
        rows = [[int(v) for v in line.split()] for line in raw.splitlines()]
        require(0 < len(rows) <= 32 and all(
            len(row) == 3 and 0 <= row[0] < 2**32 and 0 <= row[1] < 2**32
            and 0 < row[2] <= 2**32 and row[0] + row[2] <= 2**32
            and row[1] + row[2] <= 2**32 for row in rows), "invalid_uid_mapping")
        return rows
    except ValueError:
        raise ObservationError("invalid_uid_mapping") from None


class FilesystemReader:
    """Fixed files and one anchored PID only. No enumeration of host processes."""
    @staticmethod
    def _no_links(path):
        path = Path(path)
        for component in reversed((path, *path.parents)):
            require(not stat.S_ISLNK(os.lstat(component).st_mode), "symlink_rejected")

    def metadata(self, path):
        self._no_links(path)
        st = os.stat(path, follow_symlinks=False)
        return {"mode": st.st_mode, "uid": st.st_uid, "dev": st.st_dev, "ino": st.st_ino}

    @staticmethod
    def _read_fd(fd, limit):
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), "nonregular_input")
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, min(65536, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            require(total <= limit, "input_too_large")
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                "input_changed")
        return b"".join(chunks)

    def read(self, path, limit):
        self._no_links(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            return self._read_fd(fd, limit)
        finally:
            os.close(fd)

    def names(self, path):
        self._no_links(path)
        with os.scandir(path) as entries:
            result = set()
            for entry in entries:
                require(len(result) < 8, "unexpected_config_entries")
                result.add(entry.name)
            return result

    def identity(self, pid):
        """Only PID/start time for cleanup, including zombies and replaced executables."""
        proc = os.open("/proc/" + str(pid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            def selected_stat():
                fd = os.open("stat", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=proc)
                try:
                    return parse_stat(self._read_fd(fd, 65536), pid)
                finally:
                    os.close(fd)
            start, _ = selected_stat()
            require(selected_stat()[0] == start, "process_changed")
            return {"pid": pid, "start_ticks": start}
        except (FileNotFoundError, ProcessLookupError):
            raise ObservationError("process_changed") from None
        finally:
            os.close(proc)

    def process(self, pid):
        # ENOENT opening this directory alone means the selected PID is absent.
        proc = os.open("/proc/" + str(pid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            def read(name, limit=65536):
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=proc)
                try:
                    return self._read_fd(fd, limit)
                finally:
                    os.close(fd)

            def ns(name, fd):
                target = os.readlink("ns/" + name, dir_fd=fd)
                require(re.fullmatch(name + r":\[[0-9]+\]", target) is not None,
                        "invalid_namespace")
                st = os.stat("ns/" + name, dir_fd=fd)
                return [st.st_dev, st.st_ino]

            first_stat = read("stat")
            start, state = parse_stat(first_stat, pid)
            pgrp, session = parse_session(first_stat, pid)
            command = read("cmdline")
            require(command.endswith(b"\0"), "invalid_cmdline")
            arguments = [v.decode("utf-8") for v in command[:-1].split(b"\0")]
            status = read("status")
            uid_lines = [l.split()[1:] for l in status.splitlines() if l.startswith(b"Uid:")]
            require(len(uid_lines) == 1 and len(uid_lines[0]) == 4, "invalid_uid")
            uid = [int(v) for v in uid_lines[0]]
            uid_map, gid_map = parse_map(read("uid_map")), parse_map(read("gid_map"))
            cgroup = read("cgroup").decode("utf-8")
            require(cgroup and all(c == "\n" or ord(c) >= 32 for c in cgroup),
                    "invalid_cgroup")
            executable = os.readlink("exe", dir_fd=proc)
            # Deliberate kernel magic-link dereference; never execute this file.
            exefd = os.open("exe", os.O_RDONLY, dir_fd=proc)
            try:
                st = os.fstat(exefd)
                executable_hash = digest(self._read_fd(exefd, MAX_EXE))
            finally:
                os.close(exefd)
            namespaces = {name: ns(name, proc) for name in ("net", "user", "mnt")}
            own = os.open("/proc/self", os.O_RDONLY | os.O_DIRECTORY)
            try:
                observer = {name: ns(name, own) for name in ("net", "user", "mnt")}
            finally:
                os.close(own)
            final_exe = os.stat("exe", dir_fd=proc)
            final_stat = read("stat")
            require(parse_stat(final_stat, pid)[0] == start and
                    parse_session(final_stat, pid) == (pgrp, session) and
                    read("cmdline") == command and
                    [l.split()[1:] for l in read("status").splitlines()
                     if l.startswith(b"Uid:")] == uid_lines and
                    parse_map(read("uid_map")) == uid_map and
                    parse_map(read("gid_map")) == gid_map and
                    read("cgroup").decode("utf-8") == cgroup and
                    os.readlink("exe", dir_fd=proc) == executable and
                    (final_exe.st_dev, final_exe.st_ino) == (st.st_dev, st.st_ino) and
                    all(ns(name, proc) == value for name, value in namespaces.items()),
                    "process_changed")
            return {"pid": pid, "start_ticks": start, "state": state,
                    "pgrp": pgrp, "session": session, "uid": uid,
                    "uid_map": uid_map, "gid_map": gid_map, "exe_path": executable,
                    "exe_sha256": executable_hash, "exe_identity": [st.st_dev, st.st_ino],
                    "arguments": arguments, "namespaces": namespaces,
                    "observer_namespaces": observer, "cgroup": cgroup}
        except (FileNotFoundError, ProcessLookupError):
            raise ObservationError("process_changed") from None
        except (UnicodeError, IndexError, ValueError) as exc:
            if isinstance(exc, ObservationError):
                raise
            raise ObservationError("invalid_process_fields") from None
        finally:
            os.close(proc)


def receipt(expect, phase, status, classification, **fields):
    return {"schema_version": 1, "phase": phase, "status": status,
            "classification": classification, "binding": expect.binding,
            "cleanup_verified": False, **fields}


def failure(expect, phase, exc):
    if isinstance(exc, PermissionError):
        status, code = "unsupported", "observation_permission"
    elif isinstance(exc, ObservationError):
        status, code = "failed", str(exc)
    elif isinstance(exc, (FileNotFoundError, ProcessLookupError)):
        status, code = "failed", "required_input_absent"
    else:
        status, code = "unsupported", "observation_unavailable"
    return receipt(expect, phase, status, code)


def private_root(expect, reader):
    m = reader.metadata(expect.root)
    require(stat.S_ISDIR(m["mode"]) and stat.S_IMODE(m["mode"]) == 0o700 and
            m["uid"] == expect.host_uid, "installation_not_private")


def config_state(expect, reader, missing=False):
    try:
        m = reader.metadata(expect.directory)
    except FileNotFoundError:
        if missing:
            return set(), None, None
        raise
    require(stat.S_ISDIR(m["mode"]) and m["uid"] == expect.host_uid and
            not (m["mode"] & 0o022), "configuration_not_private")
    names = reader.names(expect.directory)
    require(names <= {"aardvark.pid", expect.entry.name}, "unexpected_config_entries")
    values = []
    for path in (expect.pidfile, expect.entry):
        if path.name not in names:
            values.append(None)
            continue
        m = reader.metadata(path)
        require(stat.S_ISREG(m["mode"]) and m["uid"] == expect.host_uid and
                not (m["mode"] & 0o022), "configuration_not_private")
        values.append(reader.read(path, 32 if path == expect.pidfile else MAX_FILE))
    return names, values[0], values[1]


def observe_running(expect, *, reader=None):
    reader = reader if reader is not None else FilesystemReader()
    try:
        private_root(expect, reader)
        before = config_state(expect, reader)
        require(before[1] is not None and before[2], "required_input_absent")
        pid = parse_pid(before[1])
        p = reader.process(pid)
        executable = reader.metadata(expect.executable)
        require(stat.S_ISREG(executable["mode"]) and
                p["exe_identity"] == [executable["dev"], executable["ino"]] and
                p["exe_path"] == str(expect.executable) and
                p["exe_sha256"] == expect.executable_sha256, "executable_mismatch")
        require(p["arguments"] == [str(expect.executable), "--config",
                str(expect.directory), "-p", "53", "run"], "cmdline_mismatch")
        require(p["pid"] == pid and type(p["start_ticks"]) is int and p["start_ticks"] > 0
                and p["state"] not in ("Z", "X", "x"), "process_not_running")
        require(p["uid"] == [expect.host_uid] * 4 and
                [0, expect.host_uid, 1] in p["uid_map"], "uid_mapping_mismatch")
        require(all(p["namespaces"][name] != p["observer_namespaces"][name]
                    for name in ("net", "user", "mnt")), "namespace_not_isolated")
        require(config_state(expect, reader) == before, "configuration_changed")
        identity = {k: p[k] for k in ("pid", "start_ticks", "state", "pgrp", "session", "uid", "uid_map",
                    "gid_map", "exe_path", "exe_sha256", "exe_identity",
                    "namespaces", "observer_namespaces", "cgroup")}
        fields = {"identity": identity, "identity_verified": True, "cmdline_match": True,
                  "config_sha256": digest(before[2]), "namespace_binding_verified": False}
        try:
            ns = reader.metadata(expect.netns)
        except (FileNotFoundError, PermissionError):
            return receipt(expect, "running", "unsupported", "namespace_binding_unavailable",
                           **fields)
        fields["netns_binding"] = [ns["dev"], ns["ino"]]
        if ns["dev"] != p["namespaces"]["net"][0]:
            # A host mount namespace may see only the backing filesystem placeholder.
            return receipt(expect, "running", "unsupported", "namespace_binding_unavailable",
                           **fields)
        if ns["ino"] != p["namespaces"]["net"][1]:
            return receipt(expect, "running", "failed", "namespace_binding_mismatch", **fields)
        fields["namespace_binding_verified"] = True
        return receipt(expect, "running", "verified", "running", **fields)
    except (OSError, ObservationError) as exc:
        return failure(expect, "running", exc)


def observe_stopped(expect, prior, *, reader=None):
    try:
        identity = prior["identity"]
        namespace_verified = prior["namespace_binding_verified"] is True
        acceptable = ((prior["status"] == "verified" and prior["classification"] == "running"
                       and namespace_verified) or
                      (prior["status"] == "unsupported" and
                       prior["classification"] == "namespace_binding_unavailable" and
                       not namespace_verified))
        require(acceptable and prior["identity_verified"] is True and
                prior["phase"] == "running" and prior["binding"] == expect.binding and
                type(identity["pid"]) is int and 1 < identity["pid"] < 2**31 and
                type(identity["start_ticks"]) is int and identity["start_ticks"] > 0,
                "prior_identity_required")
    except (KeyError, TypeError, ObservationError):
        return receipt(expect, "stopped", "failed", "prior_identity_required")
    reader = reader if reader is not None else FilesystemReader()
    try:
        private_root(expect, reader)
        before = config_state(expect, reader, missing=True)
        if before[1] is not None:
            require(parse_pid(before[1]) == identity["pid"], "pidfile_changed")
        try:
            current = reader.identity(identity["pid"])
        except FileNotFoundError:
            current = None
        require(config_state(expect, reader, missing=True) == before, "configuration_changed")
        if current is not None:
            require(current["pid"] == identity["pid"], "process_changed")
            code = ("live_retained" if current["start_ticks"] == identity["start_ticks"]
                    else "pid_reused")
        elif before[1] is not None:
            code = "pidfile_retained"
        elif before[2] is not None:
            code = "config_retained"
        else:
            code = "gone"
        status = "failed" if code != "gone" else ("verified" if namespace_verified else "unsupported")
        classification = "namespace_binding_unavailable" if code == "gone" and not namespace_verified else code
        return receipt(expect, "stopped", status, classification,
                       cleanup_verified=code == "gone" and namespace_verified,
                       daemon_cleanup_verified=code == "gone",
                       namespace_binding_verified=namespace_verified,
                       prior_pid=identity["pid"], prior_start_ticks=identity["start_ticks"])
    except (OSError, ObservationError) as exc:
        return failure(expect, "stopped", exc)
