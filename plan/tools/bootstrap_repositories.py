#!/usr/bin/env python3
"""Create only the AmbisGIS manifest repositories. Default: GitHub GET requests only.

Requires Python 3.10+ and an authenticated GitHub CLI. Does not clone, push,
configure secrets, enable workflows, delete repositories, or alter existing repos.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable
from urllib.parse import quote

EXPECTED: dict[str, tuple[str, str | None]] = {
    'ambisgis-platform': ('new', None),
    'ambisgis-geodb': ('new', None),
    'ambisgis-qgis-plugin': ('new', None),
    'ambisgis-notebooks': ('new', None),
    'ambisgis-postgresql': ('fork', 'postgres/postgres'),
    'ambisgis-postgis': ('fork', 'postgis/postgis'),
    'ambisgis-qgis': ('fork', 'qgis/QGIS'),
    'ambisgis-jupyterhub': ('fork', 'jupyterhub/jupyterhub'),
    'ambisgis-jupyterlab': ('fork', 'jupyterlab/jupyterlab'),
    'ambisgis-geotools': ('fork', 'geotools/geotools'),
    'ambisgis-geowebcache': ('fork', 'GeoWebCache/geowebcache'),
    'ambisgis-geoserver': ('fork', 'geoserver/geoserver'),
    'ambisgis-geonode': ('fork', 'GeoNode/geonode'),
    'ambisgis-mapstore-client': ('fork', 'GeoNode/geonode-mapstore-client'),
    'ambisgis-mapstore': ('fork', 'geosolutions-it/MapStore2'),
}


class BootstrapError(RuntimeError):
    """A condition requiring inspection, never automatic destructive recovery."""


class ApiError(BootstrapError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def parse_http_output(stdout: str) -> tuple[int, dict[str, Any]]:
    """Parse `gh api --include`; no header means status cannot be trusted."""
    normalized = stdout.replace("\r\n", "\n")
    matches = list(re.finditer(r"(?m)^HTTP/[0-9.]+\s+(\d{3})[^\n]*\n", normalized))
    if not matches:
        raise ApiError("GitHub CLI returned no recognizable HTTP status; no action is safe.")
    last = matches[-1]
    status = int(last.group(1))
    boundary = normalized.find("\n\n", last.start())
    if boundary < 0:
        raise ApiError("GitHub CLI returned incomplete HTTP headers.", status)
    body = normalized[boundary + 2:].strip()
    if not body:
        return status, {}
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ApiError("GitHub returned non-JSON data; no action is safe.", status) from exc
    if not isinstance(value, dict):
        raise ApiError("Expected a GitHub object response, not a collection.", status)
    return status, value


class GitHubCLI:
    def __init__(self, runner: Callable[..., Any] = subprocess.run):
        self.runner = runner

    def request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None,
                *, missing_ok: bool = False) -> dict[str, Any] | None:
        if method not in {"GET", "POST"}:
            raise BootstrapError("This bootstrap permits GET and create-only POST calls.")
        args = ["gh", "api", "--include", "--method", method,
                "-H", "Accept: application/vnd.github+json", endpoint]
        data = None
        if payload is not None:
            args += ["--input", "-"]
            data = json.dumps(payload)
        try:
            result = self.runner(args, input=data, text=True, capture_output=True,
                                 timeout=45, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ApiError(f"GitHub CLI could not complete {method} {endpoint}.") from exc
        status, body = parse_http_output(result.stdout)
        if status == 404 and missing_ok:
            return None
        if not 200 <= status < 300 or result.returncode != 0:
            # Do not print raw response headers, bodies, or credential-bearing stderr.
            raise ApiError(f"GitHub {method} {endpoint} failed (HTTP {status}); no automatic escalation.", status)
        return body


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"Cannot read valid JSON from {path}.") from exc
    if not isinstance(value, dict):
        raise BootstrapError(f"Expected a JSON object in {path}.")
    return value


def validate_manifest(manifest: dict[str, Any], owner: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
        raise BootstrapError("Owner must be a valid personal GitHub login.")
    if manifest.get("manifest_version") != 1 or manifest.get("visibility") != "public":
        raise BootstrapError("Only manifest v1 with public visibility is supported.")
    if manifest.get("owner") != owner:
        raise BootstrapError("Manifest owner and --owner differ; inspect rather than guessing.")
    specs = manifest.get("repositories")
    if not isinstance(specs, list) or len(specs) != len(EXPECTED):
        raise BootstrapError("Manifest must contain exactly the fifteen approved repositories.")
    seen: set[str] = set()
    for spec in specs:
        if not isinstance(spec, dict):
            raise BootstrapError("Invalid repository entry.")
        name = spec.get("name")
        if name not in EXPECTED or name in seen:
            raise BootstrapError(f"Unexpected or duplicate repository name: {name!r}.")
        seen.add(name)
        if (spec.get("kind"), spec.get("upstream")) != EXPECTED[name]:
            raise BootstrapError(f"Kind/upstream for {name} is outside the approved allow-list.")
        description = spec.get("description")
        if not isinstance(description, str) or not 1 <= len(description) <= 350 or "\n" in description:
            raise BootstrapError(f"Invalid one-line description for {name}.")
    return specs


def load_receipt(path: Path, owner: str) -> dict[str, Any]:
    if path.is_symlink():
        raise BootstrapError("Receipt path must not be a symlink.")
    if not path.exists():
        return {"receipt_version": 1, "owner": owner, "managed_repositories": {}}
    receipt = load_json(path)
    if (receipt.get("receipt_version") != 1 or receipt.get("owner") != owner
            or not isinstance(receipt.get("managed_repositories"), dict)):
        raise BootstrapError("Receipt has wrong version/owner or invalid repository records.")
    return receipt


def save_receipt(path: Path, receipt: dict[str, Any]) -> None:
    if path.is_symlink() or not path.parent.is_dir():
        raise BootstrapError("Unsafe/missing receipt directory; inspect it before continuing.")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".ambisgis-receipt-", delete=False) as stream:
            temporary = stream.name
            json.dump(receipt, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def verify_target(repo: dict[str, Any], owner: str, spec: dict[str, Any],
                  *, require_parent: bool = True) -> None:
    full = f"{owner}/{spec['name']}"
    if repo.get("full_name", "").lower() != full.lower() or repo.get("private") is not False:
        raise BootstrapError(f"Unexpected identity/visibility for {full}.")
    if not isinstance(repo.get("id"), int) or isinstance(repo.get("id"), bool):
        raise BootstrapError(f"Missing numeric GitHub repository ID for {full}.")
    if repo.get("archived") or repo.get("disabled"):
        raise BootstrapError(f"Repository {full} is archived/disabled; no changes attempted.")
    if spec["kind"] == "fork":
        if repo.get("fork") is not True:
            raise BootstrapError(f"{full} exists but is not the expected fork.")
        parent = repo.get("parent", {}).get("full_name")
        if parent is None and not require_parent:
            return
        if not isinstance(parent, str) or parent.lower() != spec["upstream"].lower():
            raise BootstrapError(f"{full} has the wrong/unverified upstream parent.")
    elif repo.get("fork") is not False:
        raise BootstrapError(f"{full} exists as a fork, not an approved new project.")


def preflight(client: Any, manifest: dict[str, Any], owner: str,
              receipt: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    specs = validate_manifest(manifest, owner)
    user = client.request("GET", "user")
    if not user or user.get("login", "").lower() != owner.lower() or user.get("type", "User") != "User":
        raise BootstrapError("Authenticated account is not the requested personal owner; no writes performed.")
    plan: list[tuple[dict[str, Any], str]] = []
    for spec in specs:
        if spec["kind"] == "fork":
            upstream = client.request("GET", f"repos/{spec['upstream']}")
            if (not upstream or upstream.get("private") is not False
                    or upstream.get("full_name", "").lower() != spec["upstream"].lower()
                    or upstream.get("archived") or upstream.get("disabled")):
                raise BootstrapError(f"Upstream {spec['upstream']} is not a verified active public repository.")
        full = f"{owner}/{spec['name']}"
        existing = client.request("GET", f"repos/{full}", missing_ok=True)
        if existing is None:
            plan.append((spec, "create"))
            continue
        verify_target(existing, owner, spec)
        if spec["kind"] == "new":
            managed = receipt["managed_repositories"].get(full, {})
            if managed.get("id") != existing["id"]:
                raise BootstrapError(f"Collision: {full} exists without a matching creation receipt. Left untouched.")
        managed = receipt["managed_repositories"].get(full, {})
        action = "verify_readiness" if (managed.get("id") == existing["id"]
                    and managed.get("status") == "created_pending_readiness") else "leave_unchanged"
        plan.append((spec, action))
    return plan


def wait_ready(client: Any, owner: str, spec: dict[str, Any], attempts: int,
               sleep: Callable[[float], None]) -> tuple[dict[str, Any], str]:
    full = f"{owner}/{spec['name']}"
    for index in range(attempts):
        repo = client.request("GET", f"repos/{full}", missing_ok=True)
        if repo is not None:
            verify_target(repo, owner, spec, require_parent=False)
            parent_ready = spec["kind"] == "new" or bool(repo.get("parent", {}).get("full_name"))
            branch = repo.get("default_branch")
            if parent_ready and isinstance(branch, str) and branch:
                verify_target(repo, owner, spec)
                ref = client.request("GET", f"repos/{full}/branches/{quote(branch, safe='')}", missing_ok=True)
                sha = (ref or {}).get("commit", {}).get("sha", "")
                if isinstance(sha, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha):
                    return repo, sha
        if index + 1 < attempts:
            sleep(min(0.5 * (2 ** index), 8.0))
    raise BootstrapError(f"{full} may exist but readiness was not verified. Receipt retained; inspect before cloning.")


def execute(client: Any, manifest: dict[str, Any], owner: str, receipt_path: Path,
            *, apply: bool = False, attempts: int = 12,
            sleep: Callable[[float], None] = time.sleep) -> list[tuple[dict[str, Any], str]]:
    if not 1 <= attempts <= 60:
        raise BootstrapError("Poll attempts must be between 1 and 60.")
    receipt = load_receipt(receipt_path, owner)
    if apply and not receipt_path.parent.is_dir():
        raise BootstrapError("Receipt directory must exist before any repository creation.")
    plan = preflight(client, manifest, owner, receipt)  # All checks before any POST.
    print("APPLY: create missing repositories only" if apply else "DRY RUN: GitHub GET requests only; no local receipt written")
    for spec, action in plan:
        suffix = f" (upstream {spec['upstream']})" if spec["kind"] == "fork" else ""
        print(f"  {action}: {owner}/{spec['name']}{suffix}")
    if not apply:
        return plan
    for spec, action in plan:
        full = f"{owner}/{spec['name']}"
        if action == "verify_readiness":
            ready, sha = wait_ready(client, owner, spec, attempts, sleep)
            receipt["managed_repositories"][full].update({
                "status": "ready", "default_branch": ready["default_branch"],
                "observed_default_commit": sha,
            })
            save_receipt(receipt_path, receipt)
            print(f"  Verified previously pending repository: {full}")
            continue
        if action != "create":
            continue
        if client.request("GET", f"repos/{full}", missing_ok=True) is not None:
            raise BootstrapError(f"Race/collision: {full} appeared after preflight; left untouched.")
        if spec["kind"] == "new":
            created = client.request("POST", "user/repos", {
                "name": spec["name"], "description": spec["description"],
                "private": False, "auto_init": True, "has_issues": True,
            })
        else:
            created = client.request("POST", f"repos/{spec['upstream']}/forks", {
                "name": spec["name"], "default_branch_only": False,
            })
        if created is None:
            raise BootstrapError(f"No creation response for {full}; inspect GitHub before retrying.")
        verify_target(created, owner, spec, require_parent=False)
        receipt["managed_repositories"][full] = {
            "id": created["id"], "kind": spec["kind"], "upstream": spec["upstream"],
            "status": "created_pending_readiness",
        }
        save_receipt(receipt_path, receipt)  # Persist partial progress before polling.
        ready, sha = wait_ready(client, owner, spec, attempts, sleep)
        receipt["managed_repositories"][full].update({
            "status": "ready", "default_branch": ready["default_branch"],
            "observed_default_commit": sha,
        })
        save_receipt(receipt_path, receipt)
        print(f"  Verified created repository: {full}")
    print(f"Receipt: {receipt_path}. No code pushed, workflows enabled, or existing repositories modified.")
    return plan


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=root / "repositories.json")
    parser.add_argument("--owner", default="aloerch")
    parser.add_argument("--receipt", type=Path, default=Path(".bootstrap-receipt.json"))
    parser.add_argument("--apply", action="store_true", help="Create only missing approved public repositories/forks.")
    parser.add_argument("--poll-attempts", type=int, default=12)
    args = parser.parse_args(argv)
    try:
        if shutil.which("gh") is None:
            raise BootstrapError("GitHub CLI (gh) is missing. Install it and authenticate explicitly before running this tool.")
        execute(GitHubCLI(), load_json(args.manifest), args.owner, args.receipt,
                apply=args.apply, attempts=args.poll_attempts)
        return 0
    except BootstrapError as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        print("No destructive recovery attempted. A partial create may exist; inspect GitHub and any receipt.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
