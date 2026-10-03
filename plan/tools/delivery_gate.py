#!/usr/bin/env python3
"""Read-only eligibility gate; never merge, publish a status, or bypass protection.

Run trusted baseline bytes, with integrator-curated private policy/evidence files
OUTSIDE Git checkouts. These local files are trust inputs, not PR-authored claims.
Policy pins repository/id/PR, required_checks (name, kind, app_id or creator), and
required_tests (command argv, kind). Evidence binds repository/id/PR/base_sha/
head_sha/files_sha256 and contains review + tests; tests/test_delivery_gate.py
shows the schema. Review/test transcript paths are relative to the evidence file.
The integrator must inspect actual transcripts and select applicable tests from
the unchanged acceptance requirements before creating these files. This tool
validates bindings, not the truth of arbitrary prose or a compromised runner.

First installation only: an independently reviewed external policy may pin
bootstrap_gate_sha256 when no gate exists at base. Later changes run the gate
from base; a candidate cannot select its own weaker gate. Re-run immediately
before normal GitHub merge with --match-head-commit; recheck base then as well.
API: docs.github.com/en/rest/{pulls/pulls,checks/runs,branches/branch-protection}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

# Deliberately embedded: a PR cannot expand the boundary via its manifest.
REPOSITORIES = {"aloerch/ambisgis-" + name for name in (
    "platform", "geodb", "qgis-plugin", "notebooks", "postgresql", "postgis", "qgis",
    "jupyterhub", "jupyterlab", "geotools", "geowebcache", "geoserver", "geonode",
    "mapstore-client", "mapstore")}
GATE_PATH = "plan/tools/delivery_gate.py"


class Denied(RuntimeError):
    """Eligibility is unknown or false; do not merge."""


def require(condition, message):
    if not condition:
        raise Denied(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def files_digest(files):
    return digest(json.dumps(sorted(files), separators=(",", ":")).encode())


def command(args, *, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Denied("Local verification command unavailable.") from None
    require(result.returncode == 0, "Local verification command failed.")
    return result.stdout


def private_file(path):
    path = Path(path).absolute()
    require(path.resolve() == path, "Trust input must not traverse symlinks.")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
            "Trust input must be a private, integrator-owned regular file.")
    require(path.parent.stat().st_uid == os.getuid() and not path.parent.stat().st_mode & 0o077,
            "Trust input directory must be private and integrator-owned.")
    # Git worktrees can use a .git file; reject either form, including ancestors.
    require(not any((parent / ".git").exists() for parent in path.parents),
            "PR checkout content cannot serve as trusted eligibility evidence.")
    return path.read_bytes()


def verify_artifact(root, ref):
    relative = Path(ref["path"])
    require(not relative.is_absolute() and ".." not in relative.parts, "Evidence path escaped its trust directory.")
    data = private_file(root / relative)
    require(bool(data.strip()) and digest(data) == ref["sha256"], "Missing or changed transcript/log evidence.")


class GitHub:
    def __init__(self, *, runner=subprocess.run, host_gh=False):
        self.runner = runner
        self.prefix = ["flatpak-spawn", "--host"] if host_gh else []

    def read(self, endpoint, payload=None):
        if payload is not None:
            require(endpoint == "graphql" and payload.get("query", "").lstrip().startswith("query ")
                    and not re.search(r"\bmutation\b", payload["query"]), "Only read queries are permitted.")
        args = self.prefix + ["gh", "api", "--hostname", "github.com", "--method",
                              "POST" if payload is not None else "GET", endpoint]
        if payload is not None:
            args += ["--input", "-"]
        try:
            result = self.runner(args, input=json.dumps(payload) if payload is not None else None,
                                 text=True, capture_output=True, timeout=45, check=False)
            require(result.returncode == 0, "GitHub read failed; permissions were not escalated.")
            data = json.loads(result.stdout)
            require(not isinstance(data, dict) or not data.get("errors"), "GitHub returned partial/error data.")
            return data
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            raise Denied("GitHub state could not be read completely.") from None

    def pages(self, endpoint, key=None):
        rows = []
        for page in range(1, 101):
            data = self.read(endpoint + ("&" if "?" in endpoint else "?") + f"per_page=100&page={page}")
            batch = data[key] if key else data
            require(isinstance(batch, list), "Malformed GitHub collection.")
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise Denied("GitHub pagination exceeded its bound.")

    def snapshot(self, policy):
        repo, number = policy["repository"], policy["pr"]
        require(repo in REPOSITORIES and type(number) is int and number > 0, "Unapproved repository/PR.")
        path = f"repos/{repo}"
        user, repository = self.read("user"), self.read(path)
        pr = self.read(f"{path}/pulls/{number}")
        branch = self.read(f"{path}/branches/ambisgis%2Fmain")
        required = []
        if branch["protected"]:
            protection = self.read(f"{path}/branches/ambisgis%2Fmain/protection")
            checks = protection.get("required_status_checks") or {}
            required += checks.get("checks") or [{"context": name} for name in checks.get("contexts", [])]
        for rule in self.pages(f"{path}/rules/branches/ambisgis%2Fmain"):
            if rule["type"] == "required_status_checks":
                required += [{"context": row["context"], "app_id": row.get("integration_id")}
                             for row in rule["parameters"]["required_status_checks"]]
        threads, cursor = [], None
        for unused in range(100):
            response = self.read("graphql", {"query": "query Threads($name:String!,$number:Int!,$after:String) { "
                "repository(owner:\"aloerch\",name:$name) { pullRequest(number:$number) { "
                "reviewThreads(first:100,after:$after) { nodes { isResolved isOutdated } "
                "pageInfo { hasNextPage endCursor } } } } }",
                "variables": {"name": repo.split("/")[1], "number": number, "after": cursor}})
            connection = response["data"]["repository"]["pullRequest"]["reviewThreads"]
            threads.extend(connection["nodes"])
            page = connection["pageInfo"]
            if not page["hasNextPage"]:
                break
            require(page["endCursor"] and page["endCursor"] != cursor, "Invalid review pagination.")
            cursor = page["endCursor"]
        else:
            raise Denied("Review pagination exceeded its bound.")
        head = pr["head"]["sha"]
        require(re.fullmatch(r"[0-9a-f]{40}", head), "Invalid PR head.")
        state = {"user": user, "repository": repository, "pr": pr, "base_sha": branch["commit"]["sha"],
                 "files": [row["filename"] for row in self.pages(f"{path}/pulls/{number}/files")],
                 "checks": self.pages(f"{path}/commits/{head}/check-runs?filter=latest", "check_runs"),
                 "statuses": self.pages(f"{path}/commits/{head}/statuses"), "required": required,
                 "reviews": self.pages(f"{path}/pulls/{number}/reviews"), "threads": threads}
        after = self.read(f"{path}/pulls/{number}")
        tip = self.read(f"{path}/branches/ambisgis%2Fmain")["commit"]["sha"]
        require(after == pr and tip == state["base_sha"], "PR/base changed during verification; retry from fresh evidence.")
        return state


def control_file(name):
    return (name.startswith(".github/") or any(part in {"tests", "schemas", "contracts"} for part in Path(name).parts)
            or bool(re.search(r"(AGENTS|requirements|backlog|acceptance|delivery|workflow|validate_|lock)", name)))


def evaluate(policy, evidence, state):
    repo, pr = state["repository"], state["pr"]
    expected = policy["repository"]
    require(expected in REPOSITORIES and type(policy["repository_id"]) is int, "Repository outside verified boundary.")
    require(state["user"]["login"] == "aloerch" and repo["owner"]["login"] == "aloerch", "Wrong authenticated owner.")
    for observed in (repo, pr["base"]["repo"], pr["head"]["repo"]):
        require(observed["id"] == policy["repository_id"] and observed["full_name"] == expected,
                "Repository ID/name collision or outside fork.")
    require(pr["user"]["login"] == "aloerch" and pr["number"] == policy["pr"], "PR is not delegated owner work.")
    require(pr["state"] == "open" and pr["draft"] is False and pr["merged"] is False and pr["mergeable"] is True,
            "PR is not open, ready and mergeable.")
    require(pr["base"]["ref"] == "ambisgis/main" and pr["head"]["ref"] != "ambisgis/main", "Unexpected PR branches.")
    base, head = pr["base"]["sha"], pr["head"]["sha"]
    require(all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (base, head)) and state["base_sha"] == base,
            "Base moved or commit identity is incomplete.")
    require(len(state["files"]) == pr["changed_files"] and len(set(state["files"])) == len(state["files"]),
            "Changed-file enumeration is incomplete.")
    binding = dict(repository=expected, repository_id=repo["id"], pr=pr["number"], base_sha=base,
                   head_sha=head, files_sha256=files_digest(state["files"]))
    require(all(evidence.get(key) == value for key, value in binding.items()), "Review/test evidence is stale or unrelated.")
    require(all(thread["isResolved"] is True for thread in state["threads"]), "Unresolved GitHub review thread.")
    latest = {}
    for review in sorted(state["reviews"], key=lambda row: row["id"]):
        if review["state"] in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[review["user"]["login"]] = review["state"]
    require("CHANGES_REQUESTED" not in latest.values(), "Outstanding requested changes.")
    review = evidence["review"]
    require(review["mechanism"] in {"separate-agent", "separate-session"} and review["reviewer"]
            and review["implementer"] and review["reviewer"] != review["implementer"], "Review is not independent.")
    require(review["findings"] == [] and review["concerns"] == [], "Unresolved material finding or scope/source/rights/security concern.")
    require({"scope", "source", "rights", "secrets", "destructive-actions"} <= set(review["checked_boundaries"]),
            "Review did not inspect all delegated boundaries.")
    controls = {name for name in state["files"] if control_file(name)}
    require(review["prior_acceptance_sha"] == base and controls <= set(review["scrutinized_controls"]),
            "Changed controls lack explicit scrutiny against prior acceptance.")
    require(isinstance(review["transcript"], dict), "Independent review transcript missing.")
    checks = policy["required_checks"]
    require(isinstance(checks, list) and checks, "No trusted required check policy.")
    for remote in state["required"]:
        require(any(row["name"] == remote["context"] and (remote.get("app_id") in (None, -1)
                    or row.get("app_id") == remote["app_id"]) for row in checks), "Live required check is not pinned in policy.")
    for check in checks:
        if check["kind"] == "check":
            require(type(check["app_id"]) is int and check["app_id"] > 0, "Check requires a verified GitHub App ID.")
            runs = [row for row in state["checks"] if row["name"] == check["name"] and row["app"]["id"] == check["app_id"]]
            require(runs, "Missing required check.")
            run = max(runs, key=lambda row: row["id"])
            require(run["head_sha"] == head and run["status"] == "completed" and run["conclusion"] == "success",
                    "Required check failed, stale, pending or skipped.")
        else:
            require(check["kind"] == "status" and check["creator"] == "aloerch", "Untrusted status authority.")
            runs = [row for row in state["statuses"] if row["context"] == check["name"]]
            require(runs, "Missing required status.")
            run = max(runs, key=lambda row: row["id"])
            require(run["creator"]["login"] == check["creator"] and run["state"] == "success", "Untrusted or unsuccessful status.")
    require(policy["required_tests"], "Applicable acceptance tests must be specified independently.")
    for required in policy["required_tests"]:
        tests = [row for row in evidence["tests"] if row["command"] == required["command"] and row["kind"] == required["kind"]]
        require(len(tests) == 1, "Applicable test evidence missing or ambiguous.")
        test = tests[0]
        require(type(test["exit_code"]) is int and test["exit_code"] == 0 and type(test["skipped"]) is int
                and test["skipped"] == 0 and isinstance(test["log"], dict), "Tests failed, skipped or lack logs.")
        require(test["mocked"] is False or required["kind"] in {"unit", "package"}, "Mock evidence cannot satisfy product acceptance.")
    return {"eligible": True, **binding, "limitations": "Read-only snapshot; recheck base/head immediately before normal protected merge."}


def verify_checkout(checkout, state, policy):
    def git(*args):
        return command(["git", "-C", str(checkout), *args])
    repo, pr = policy["repository"], state["pr"]
    remote = git("remote", "get-url", "origin").decode().strip()
    require(remote in {f"https://github.com/{repo}.git", f"https://github.com/{repo}", f"git@github.com:{repo}.git"}, "Unexpected checkout remote.")
    require(git("rev-parse", "HEAD").decode().strip() == pr["head"]["sha"], "Checkout is not the reviewed head.")
    require(git("branch", "--show-current").decode().strip() == pr["head"]["ref"], "Checkout branch differs from PR.")
    require(not git("status", "--porcelain", "--untracked-files=normal").strip(), "Checkout contains unreviewed changes.")
    base = pr["base"]["sha"]
    require(re.fullmatch(r"[0-9a-f]{40}", base), "Invalid live base commit.")
    paths = git("ls-tree", "--name-only", base, "--", GATE_PATH).decode().splitlines()
    running = Path(__file__).read_bytes()
    if paths:
        require(git("show", f"{base}:{GATE_PATH}") == running, "Run the gate from live base; PR gate cannot authorize itself.")
    else:
        require(policy.get("bootstrap_gate_sha256") == digest(running), "Initial gate requires independently reviewed external bootstrap pin.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--host-gh", action="store_true")
    args = parser.parse_args(argv)
    try:
        policy = json.loads(private_file(args.policy))
        evidence = json.loads(private_file(args.evidence))
        verify_artifact(args.evidence.parent, evidence["review"]["transcript"])
        for test in evidence["tests"]:
            verify_artifact(args.evidence.parent, test["log"])
        state = GitHub(host_gh=args.host_gh).snapshot(policy)
        verify_checkout(args.checkout, state, policy)
        decision = evaluate(policy, evidence, state)
    except Denied as error:
        print(json.dumps({"eligible": False, "reason": str(error)}))
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # No arbitrary API/process/schema text can leak credentials into output.
        print(json.dumps({"eligible": False, "reason": "Verification denied; inspect identity, live checks, trusted evidence and baseline gate."}))
        return 1
    print(json.dumps(decision, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
