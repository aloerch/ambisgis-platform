#!/usr/bin/env python3
"""Run a trusted local build with Linux x86-64 Internet socket creation denied.

Usage: python3 offline_exec.py --evidence /new/path.json -- COMMAND ARG ...

This is a process-local seccomp filter, not a filesystem, toolchain or hostile
code sandbox. AF_UNIX is allowed for disposable PostgreSQL clusters. Local
services (including proxies), shared memory and host files remain accessible;
callers must not use a local service to fetch build inputs. No host firewall,
privilege escalation or other process's settings are changed.

The command and descendants inherit no_new_privs and the filter. Kernel API:
https://docs.kernel.org/userspace-api/seccomp_filter.html
The x86-64 constants below were verified against Linux UAPI headers
asm/unistd_64.h, linux/{audit,elf-em,seccomp,prctl,bpf_common}.h.
"""

import argparse
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import stat
import subprocess
import sys


SYSCALLS = {"socket": 41, "socketpair": 53, "ptrace": 101,
            "io_uring_setup": 425, "io_uring_enter": 426,
            "io_uring_register": 427, "pidfd_getfd": 438}
AUDIT_ARCH_X86_64 = 0xC000003E
X32_SYSCALL_BIT = 0x40000000
RET_KILL_PROCESS = 0x80000000
RET_ERRNO = 0x00050000
RET_ALLOW = 0x7FFF0000


class OfflineError(RuntimeError):
    """The required process-local restriction could not be established."""


class SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]


class SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort),
                ("filter", ctypes.POINTER(SockFilter))]


def check_platform():
    if (sys.platform != "linux" or platform.machine() != "x86_64"
            or ctypes.sizeof(ctypes.c_void_p) != 8 or sys.byteorder != "little"):
        raise OfflineError("Only Linux x86_64 with the 64-bit little-endian ABI is supported")
    available = Path("/proc/sys/kernel/seccomp/actions_avail").read_text().split()
    if not {"kill_process", "errno", "allow"}.issubset(available):
        raise OfflineError("Required seccomp actions are unavailable on this kernel")
    if len(list(Path("/proc/self/task").iterdir())) != 1:
        raise OfflineError("Filter installation requires a single-threaded process")


def close_inherited_descriptors():
    """Refuse socket stdio and close every other inherited fd, even above rlimit."""
    for fd in (0, 1, 2):
        try:
            mode = os.fstat(fd).st_mode
        except OSError as exc:
            if exc.errno == errno.EBADF:
                raise OfflineError(f"Standard descriptor {fd} is closed; attach files or pipes") from exc
            raise
        if stat.S_ISSOCK(mode):
            raise OfflineError(f"Standard descriptor {fd} is a socket; use files or pipes")
    # /proc enumeration includes its own transient directory fd; EBADF is fine.
    closed = []
    for name in os.listdir("/proc/self/fd"):
        fd = int(name)
        if fd <= 2:
            continue
        try:
            os.close(fd)
            closed.append(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise
    return sorted(closed)


def filter_instructions():
    # sock_filter: BPF_LD|BPF_W|BPF_ABS=0x20, JMP|JEQ|K=0x15,
    # JMP|JSET|K=0x45, RET|K=0x06. seccomp_data arch/nr/args[0]
    # offsets are 4/0/16; arguments are 64-bit, domain uses the low word.
    deny = RET_ERRNO | errno.EPERM
    insns = [(0x20, 0, 0, 4), (0x15, 1, 0, AUDIT_ARCH_X86_64),
             (0x06, 0, 0, RET_KILL_PROCESS), (0x20, 0, 0, 0),
             (0x45, 0, 1, X32_SYSCALL_BIT), (0x06, 0, 0, RET_KILL_PROCESS)]
    # io_uring can perform networking without socket syscalls in the process;
    # pidfd_getfd can import existing sockets; tracing must not change a sibling.
    for name in ("io_uring_setup", "io_uring_enter", "io_uring_register",
                 "pidfd_getfd", "ptrace"):
        insns.extend([(0x15, 0, 1, SYSCALLS[name]), (0x06, 0, 0, deny)])
    insns.extend([(0x15, 1, 0, SYSCALLS["socket"]),
                  (0x15, 0, 4, SYSCALLS["socketpair"]),
                  (0x20, 0, 0, 16), (0x15, 1, 0, socket.AF_UNIX),
                  (0x06, 0, 0, deny), (0x06, 0, 0, RET_ALLOW),
                  (0x06, 0, 0, RET_ALLOW)])
    return insns


def install_filter():
    """Permanently restrict the calling process; never call in a test runner."""
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = libc.prctl
    prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    prctl.restype = ctypes.c_int

    def invoke(option, arg=0):
        result = prctl(option, arg, 0, 0, 0)
        if result == -1:
            number = ctypes.get_errno()
            raise OfflineError(f"prctl({option}) failed: errno {number}: {os.strerror(number)}")
        return result

    insns = filter_instructions()
    program = (SockFilter * len(insns))(*(SockFilter(*row) for row in insns))
    descriptor = SockFprog(len(insns), program)
    invoke(38, 1)  # PR_SET_NO_NEW_PRIVS
    # PR_SET_SECCOMP takes mode and a pointer, unlike the simpler calls above.
    if prctl(22, 2, ctypes.addressof(descriptor), 0, 0) != 0:
        number = ctypes.get_errno()
        raise OfflineError(f"Seccomp filter installation failed: errno {number}: {os.strerror(number)}")
    if invoke(39) != 1 or invoke(21) != 2:  # PR_GET_NO_NEW_PRIVS / PR_GET_SECCOMP
        raise OfflineError("Kernel did not report no_new_privs=1 and seccomp filter mode=2")
    return {"no_new_privs": 1, "seccomp_mode": 2,
            "filter_sha256": hashlib.sha256(bytes(program)).hexdigest()}


def probe_sockets():
    results = []
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            with socket.socket(family, socket.SOCK_STREAM):
                number = 0
        except OSError as exc:
            number = exc.errno
        expected = 0 if family == socket.AF_UNIX else errno.EPERM
        results.append({"family": family.name, "operation": "socket(SOCK_STREAM)",
                        "errno": number, "errno_name": errno.errorcode.get(number, "SUCCESS"),
                        "expected_errno": expected, "passed": number == expected})
    # Exercise actual local communication, not just construction of a descriptor.
    left, right = socket.socketpair(socket.AF_UNIX)
    with left, right:
        left.sendall(b"local-build-probe")
        local_ok = right.recv(64) == b"local-build-probe"
    results.append({"family": "AF_UNIX", "operation": "socketpair send/recv",
                    "errno": 0, "passed": local_ok})
    return results


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True,
                        help="New JSON evidence file (existing files are never overwritten)")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("an explicit command is required after --")
    evidence = {"schema_version": 1, "started_utc": utc_now(), "cwd": os.getcwd(),
                "command": command, "platform": platform.platform(),
                "mechanism": "Linux seccomp BPF with PR_SET_NO_NEW_PRIVS",
                "scope": "calling process and descendants; non-AF_UNIX socket creation denied",
                "limitations": ["Host filesystem, tools and libraries are not isolated or retained by this wrapper",
                                "AF_UNIX services remain accessible, including any local proxy or descriptor broker",
                                "This is a trusted build check, not a hostile-code sandbox or whole-product independence proof"],
                "status": "preflight"}
    output = None
    try:
        check_platform()
        executable = shutil.which(command[0])
        if executable is None:
            raise OfflineError(f"Command executable not found: {command[0]}")
        executable = os.path.abspath(executable)
        evidence["resolved_executable"] = executable
        evidence["closed_inherited_fds"] = close_inherited_descriptors()
        output = args.evidence.open("x", encoding="utf-8")
        evidence["kernel_state"] = install_filter()
        evidence["probes"] = probe_sockets()
        if not all(item["passed"] for item in evidence["probes"]):
            raise OfflineError("A required network-denial/local-socket probe failed")
        evidence["status"] = "running"
        json.dump(evidence, output, indent=2)
        output.write("\n")
        output.flush()
        # No shell interpretation; subprocess exec and every descendant inherit
        # the calling thread's installed filter. The evidence fd is not inherited.
        result = subprocess.run([executable, *command[1:]], close_fds=True)
        evidence.update(status="completed", command_exit_code=result.returncode,
                        finished_utc=utc_now())
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except (OfflineError, OSError) as exc:
        evidence.update(status="refused", error=str(exc), finished_utc=utc_now())
        print(f"offline_exec: {exc}", file=sys.stderr)
        return 125
    except KeyboardInterrupt:
        evidence.update(status="interrupted", finished_utc=utc_now())
        return 130
    finally:
        if output is not None:
            output.seek(0)
            json.dump(evidence, output, indent=2)
            output.write("\n")
            output.truncate()
            output.close()


if __name__ == "__main__":
    raise SystemExit(main())
