"""Keep finite owned startup metadata; discard all arbitrary native output."""
import errno
import json

from .state import InstallError

# The isolated service emits the same finite contract. A cross-module test
# binds these sets; no service package or native library is imported by the CLI.
STAGES = frozenset({"entrypoint", "input", "identity", "storage", "password",
                    "password_cleanup", "initdb", "server", "readiness", "bootstrap",
                    "catalog_input", "catalog_identity", "catalog_setup", "catalog_models",
                    "catalog_lock", "catalog_migrations", "catalog_bootstrap", "catalog_static", "catalog_unlock"})
CATEGORIES = {"invalid_input": "validation", "os_failure": "os_error",
              "child_failed": "child_exit", "timeout": "timeout",
              "operation_failed": "runtime", "unexpected": "unexpected",
              "module_missing": "import", "import_failed": "import",
              "gdal_extension_missing": "import", "gdal_extension_import_failed": "import",
              "attribute_missing": "attribute", "name_missing": "name",
              "configuration_failed": "configuration"}
DETAIL = "Inspect installation state and owned dependency readiness."
LIMIT = 4 * 1024 * 1024


def startup_fields(value):
    if type(value) is not dict or not 3 <= len(value) <= 6:
        return None
    if any(type(key) is not str for key in value):
        return None
    if not {"stage", "code", "category"} <= value.keys():
        return None
    if value.keys() - {"stage", "code", "category", "errno", "child_returncode", "cleanup_failed"}:
        return None
    if any(type(value[key]) is not str for key in ("stage", "code", "category")):
        return None
    if value["stage"] not in STAGES or CATEGORIES.get(value["code"]) != value["category"]:
        return None
    if "errno" in value and not (value["category"] == "os_error"
            and type(value["errno"]) is int and value["errno"] in errno.errorcode):
        return None
    if "child_returncode" in value and not (value["category"] == "child_exit"
            and type(value["child_returncode"]) is int and -64 <= value["child_returncode"] <= 255):
        return None
    if "cleanup_failed" in value and value["cleanup_failed"] is not True:
        return None
    return dict(value)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("ambiguous diagnostic object")
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError("invalid constant")


def document(raw):
    try:
        return json.loads(raw, object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        return None


def from_streams(output, diagnostic):
    if any(type(raw) is not bytes for raw in (output, diagnostic)) or len(output) + len(diagnostic) > LIMIT:
        return None
    found = []
    for stream in (output, diagnostic):
        for line in stream.splitlines():
            # Ignore ordinary warning text, but withhold metadata if any JSON
            # object record is malformed or too large to validate. It could be
            # a second startup failure, so accepting another record is unsafe.
            if not line.lstrip().startswith(b"{"):
                continue
            if not 2 <= len(line) <= 1024:
                return None
            value = document(line)
            if type(value) is not dict:
                return None
            if value.get("event") != "service_start_failed":
                continue
            if value.get("detail") != DETAIL:
                return None
            fields = startup_fields({key: item for key, item in value.items() if key not in {"event", "detail"}})
            if fields is None:
                return None
            found.append(fields)
    return found[0] if len(found) == 1 else None


def from_cli(raw, command):
    if type(raw) is not bytes or len(raw) > 4096:
        return None
    value = document(raw)
    if (type(value) is not dict or set(value) != {"command", "ok", "error", "startup_failure"}
            or value["command"] != command or value["ok"] is not False or type(value["error"]) is not str):
        return None
    return startup_fields(value["startup_failure"])


class OperationFailure(InstallError):
    def __init__(self, returncode, output, diagnostic):
        super().__init__("Local runtime operation failed (exit " + str(returncode) + "); use doctor.")
        self.startup_failure = from_streams(output, diagnostic)
