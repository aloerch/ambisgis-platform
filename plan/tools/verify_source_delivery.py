#!/usr/bin/env python3
"""Fetch approved published refs into fresh independent stores, from owned HTTPS only.

This adds remote-delivery evidence to PR69 recovery; it never pushes or changes GitHub.
Held rows are not fetched. No donor fallback, shallow history, alternates or shared store.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

PLAN_SHA256 = "a9477bbdcab4f85fad69cbf77ed04ed76de92efd63d3d663054bda34e4b573a6"
PLATFORM = Path(__file__).resolve().parents[2]
REF = "refs/heads/ambisgis/review/fnd-07-baseline-v4"


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo, *args, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")
    argv = ["git", "-c", "core.hooksPath=" + os.devnull,
            "-c", "protocol.file.allow=never", "-c", "protocol.ext.allow=never",
            "-c", "fetch.recurseSubmodules=false", "-c", "maintenance.auto=false",
            "-c", "gc.auto=0", "-C", str(repo), *args]
    result = subprocess.run(argv, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=1800)
    if check and result.returncode:
        raise RuntimeError("Git command failed: " + json.dumps({"argv": argv, "exit_code": result.returncode,
                           "stderr": result.stderr.decode(errors="replace")[-4000:]}))
    return result


def text(repo, *args):
    return git(repo, *args).stdout.decode().strip()


def tree_entry(repo, commit, path):
    result = git(repo, "ls-tree", "-z", commit, "--", path).stdout
    require(result.endswith(b"\0") and result.count(b"\0") == 1, "Missing or ambiguous notice: " + path)
    header, actual = result[:-1].split(b"\t", 1)
    require(actual.decode() == path, "Wrong notice path")
    return header.decode()


def verify_objects(repo, row):
    require(not (repo / "objects").is_symlink(), "Symlinked object store")
    require(not (repo / "objects/info/alternates").exists() and not (repo / "objects/info/http-alternates").exists(), "Shared object store")
    require(not list((repo / "objects").rglob("*.promisor")), "Partial/promisor object store")
    require(not (repo / "shallow").exists(), "Shallow history")
    for parent in (repo / "objects").rglob("*"):
        require(not parent.is_symlink(), "Symlink in object store")
        if parent.is_file():
            require(parent.stat().st_nlink == 1, "Shared hardlinked object")
    commit = text(repo, "rev-parse", REF + "^{commit}")
    require(commit == row["proposed_commit"], "Remote commit mismatch")
    tree = text(repo, "rev-parse", commit + "^{tree}")
    require(tree == row["proposed_tree"], "Remote tree mismatch")
    require(text(repo, "rev-parse", row["accepted_base_commit"] + "^{tree}") == row["accepted_base_tree"], "Base tree mismatch")
    git(repo, "merge-base", "--is-ancestor", row["accepted_base_commit"], commit)
    changed = text(repo, "diff", "--name-status", row["accepted_base_commit"], commit).splitlines()
    require(changed == row["changed_paths"], "Source diff differs from immutable plan")
    notices = []
    for path in row["notice_paths"]:
        before = tree_entry(repo, row["accepted_base_commit"], path)
        after = tree_entry(repo, commit, path)
        require(before == after, "Notice blob/mode changed: " + path)
        notices.append({"path": path, "entry": after})
    links = []
    for line in git(repo, "ls-tree", "-rz", commit).stdout.split(b"\0"):
        if line.startswith(b"160000 "):
            head, path = line.split(b"\t", 1)
            links.append({"path": path.decode(), "commit": head.decode().split()[2]})
    fsck = git(repo, "fsck", "--full", "--no-reflogs")
    return {"commit": commit, "tree": tree, "changed_paths": changed,
            "notices": notices, "gitlinks": links,
            "history_commits": int(text(repo, "rev-list", "--count", commit)),
            "fsck_exit_code": fsck.returncode,
            "fsck_stdout": fsck.stdout.decode(), "fsck_stderr": fsck.stderr.decode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--publication-evidence", type=Path, required=True)
    parser.add_argument("--publication-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan_path = PLATFORM / "plan/verification/source-baseline-restore/promotion-plan.json"
    require(digest(plan_path) == PLAN_SHA256, "Immutable promotion plan changed")
    require(digest(args.publication_evidence) == args.publication_sha256, "Publication evidence changed")
    plan = json.loads(plan_path.read_text())
    publication = json.loads(args.publication_evidence.read_text())
    require(publication["plan_sha256"] == PLAN_SHA256, "Publication plan mismatch")
    verdicts = {r["root_id"]: r for r in publication["repositories"]}
    require(len(verdicts) == len(publication["repositories"]) == 11, "Publication membership mismatch")
    require(set(verdicts) == {r["root_id"] for r in plan["repositories"]}, "Publication roots mismatch")
    output = args.output.absolute()
    root = args.workspace_root.resolve() / "build-worktrees/source-ref-promotion"
    require(output.resolve().is_relative_to(root) and output != root, "Output outside task retention root")
    require(output.parent.resolve() == output.parent and not output.exists(), "Output must be fresh and non-symlinked")
    output.mkdir(parents=True, exist_ok=False)
    (output / "verify_source_delivery.py").write_bytes(Path(__file__).read_bytes())
    result = {"started_at": datetime.now(timezone.utc).isoformat(), "plan_sha256": PLAN_SHA256,
              "publication_sha256": args.publication_sha256,
              "tool_sha256": digest(Path(__file__)), "repositories": []}
    # Publish/verify the owned child before inspecting the parent gitlink.
    rows = sorted(plan["repositories"], key=lambda r: r["root_id"] == "mapstore-client")
    for row in rows:
        entry = {"root_id": row["root_id"], "repository": row["repository"], "repository_id": row["repository_id"]}
        result["repositories"].append(entry)
        try:
            verdict = verdicts[row["root_id"]]
            require(all(verdict[k] == row[k] for k in ("repository", "repository_id", "proposed_commit", "proposed_tree")), "Publication identity mismatch")
            if verdict["disposition"] != "publishable":
                require(verdict["disposition"] == "held", "Unknown publication disposition")
                entry.update(status="held-not-fetched", basis=verdict["basis"])
                continue
            repo = output / row["root_id"]
            repo.mkdir()
            git(repo, "init", "--bare", "--template=")
            url = "https://github.com/" + row["repository"] + ".git"
            observed = text(repo, "ls-remote", "--exit-code", "--refs", url, REF)
            require(observed == row["proposed_commit"] + "\t" + REF, "Published ref absent or different")
            fetch_args = ["fetch", "--no-tags", "--no-recurse-submodules", url, REF + ":" + REF]
            entry["fetch_argv"] = ["git", *fetch_args]
            fetch = git(repo, *fetch_args)
            (output / (row["root_id"] + "-fetch.txt")).write_bytes(fetch.stdout + fetch.stderr)
            entry.update(verify_objects(repo, row))
            require(text(repo, "for-each-ref", "--format=%(refname)") == REF, "Unexpected fetched refs")
            if row["root_id"] == "mapstore-client":
                child = next(r for r in result["repositories"] if r["root_id"] == "mapstore")
                require(child["status"] == "verified", "Required MapStore remote delivery unavailable")
                require(entry["gitlinks"] == [{"path": "geonode_mapstore_client/client/MapStore2", "commit": child["commit"]}], "Client gitlink mismatch")
                entry["gitmodules"] = text(repo, "show", row["proposed_commit"] + ":.gitmodules")
                donor_url = "https://github.com/geosolutions-it/MapStore2.git"
                owned_url = "https://github.com/aloerch/ambisgis-mapstore.git"
                declarations = text(repo, "config", "--blob", row["proposed_commit"] + ":.gitmodules", "--get-regexp", r"^submodule\..*\.url$").splitlines()
                require(len(declarations) == 1, "Unexpected submodule URL declarations")
                key, declared_url = declarations[0].split(" ", 1)
                require(declared_url == donor_url, "Unreviewed submodule URL")
                declared_path = text(repo, "config", "--blob", row["proposed_commit"] + ":.gitmodules", "--get", key[:-3] + "path")
                require(declared_path == entry["gitlinks"][0]["path"], "Submodule path mismatch")
                mapping_args = ["-c", "url." + owned_url + ".insteadOf=" + donor_url,
                                "ls-remote", "--exit-code", "--refs", donor_url, REF]
                mapped = text(repo, *mapping_args)
                require(mapped == child["commit"] + "\t" + REF, "Owned submodule URL override readback mismatch")
                entry["required_local_url_mapping"] = {"from": donor_url, "to": owned_url,
                    "gitmodules_key": key, "path": declared_path, "argv": ["git", *mapping_args],
                    "readback": mapped, "scope": "process-only exact donor URL rewrite to owned remote; child fetched separately into independent store; no ordinary recursive clone claimed"}
            entry["status"] = "verified"
        except Exception as exc:
            entry.update(status="failed", error=str(exc))
        finally:
            entry["observed_at"] = datetime.now(timezone.utc).isoformat()
            temp = output / "delivery.json.tmp"
            temp.write_text(json.dumps(result, indent=2) + "\n")
            os.replace(temp, output / "delivery.json")
            print(entry["root_id"], entry["status"], flush=True)
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    (output / "delivery.json").write_text(json.dumps(result, indent=2) + "\n")
    return 1 if any(r["status"] == "failed" for r in result["repositories"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
