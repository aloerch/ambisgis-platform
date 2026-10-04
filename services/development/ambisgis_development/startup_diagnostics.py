"""Finite startup failure metadata. Never format exception values or child output."""
import errno
import json
import subprocess

STAGES = frozenset({"entrypoint", "input", "identity", "storage", "password",
                    "password_cleanup", "initdb", "server", "readiness", "bootstrap"})
CATEGORIES = {"invalid_input": "validation", "os_failure": "os_error",
              "child_failed": "child_exit", "timeout": "timeout",
              "operation_failed": "runtime", "unexpected": "unexpected"}
OS_ERRORS = (OSError, FileNotFoundError, FileExistsError, PermissionError,
             NotADirectoryError, IsADirectoryError, BlockingIOError, InterruptedError,
             ConnectionError, BrokenPipeError, ConnectionRefusedError,
             ConnectionAbortedError, ConnectionResetError, ChildProcessError,
             ProcessLookupError)
ERRNOS = frozenset(errno.errorcode)


def valid_exit(value):
    return type(value) is int and -64 <= value <= 255


def valid(fields):
    if type(fields) is not dict or not 3 <= len(fields) <= 6:
        return False
    if any(type(key) is not str for key in fields) or not {"stage", "code", "category"} <= fields.keys():
        return False
    if fields.keys() - {"stage", "code", "category", "errno", "child_returncode", "cleanup_failed"}:
        return False
    if any(type(fields[key]) is not str for key in ("stage", "code", "category")):
        return False
    if fields["stage"] not in STAGES or CATEGORIES.get(fields["code"]) != fields["category"]:
        return False
    if "errno" in fields and not (fields["category"] == "os_error"
            and type(fields["errno"]) is int and fields["errno"] in ERRNOS):
        return False
    if "child_returncode" in fields and not (fields["category"] == "child_exit"
            and valid_exit(fields["child_returncode"])):
        return False
    return "cleanup_failed" not in fields or fields["cleanup_failed"] is True


class ChildFailure(RuntimeError):
    def __init__(self, returncode):
        super().__init__("owned database command failed")
        self.returncode = returncode


def fields_for(stage, error):
    generic = {"stage": "entrypoint", "code": "unexpected", "category": "unexpected"}
    if type(error) is StartupFailure:
        fields = getattr(error, "fields", None)
        return dict(fields) if valid(fields) else generic
    if type(stage) is not str or stage not in STAGES:
        return generic
    fields = {"stage": stage, "code": "unexpected", "category": "unexpected"}
    kind = type(error)
    returncode = getattr(error, "returncode", None) if kind is ChildFailure else None
    if kind is ChildFailure and valid_exit(returncode):
        fields.update(code="child_failed", category="child_exit", child_returncode=returncode)
    elif kind in (TimeoutError, subprocess.TimeoutExpired):
        fields.update(code="timeout", category="timeout")
    elif kind in (ValueError, TypeError, KeyError, json.JSONDecodeError):
        fields.update(code="invalid_input", category="validation")
    elif kind in OS_ERRORS:
        fields.update(code="os_failure", category="os_error")
        if type(error.errno) is int and error.errno in ERRNOS:
            fields["errno"] = error.errno
    elif kind is RuntimeError:
        fields.update(code="operation_failed", category="runtime")
    return fields


class StartupFailure(RuntimeError):
    def __init__(self, stage, error, *, cleanup_failed=False):
        super().__init__("service startup failed")
        self.fields = fields_for(stage, error)
        if cleanup_failed is True:
            self.fields["cleanup_failed"] = True


def failure_record(error):
    fields = fields_for("entrypoint", error)
    return {"event": "service_start_failed",
            "detail": "Inspect installation state and owned dependency readiness.",
            **fields}
