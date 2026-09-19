#!/usr/bin/env python3
"""Verify retained FND-02 inputs; fetch/extract only when explicitly requested.

No compilation or dependency resolution occurs here. Python >= 3.12 is needed
for tarfile's data extraction filter. Source archives stay outside the checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
from urllib.parse import urlparse
import urllib.request


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"Unsafe relative path: {value!r}")
    return path


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("inputs"), list):
        raise ValueError("Unsupported input manifest")
    names, artifacts, roots = set(), set(), set()
    for item in manifest["inputs"]:
        for key, seen in (("name", names), ("artifact", artifacts), ("archive_root", roots)):
            value = item[key]
            parsed = relative_path(value)
            if len(parsed.parts) != 1 or value in seen:
                raise ValueError(f"Duplicate or non-basename {key}: {value}")
            seen.add(value)
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Invalid SHA256")
        if not isinstance(item["bytes"], int) or item["bytes"] <= 0:
            raise ValueError("Invalid artifact size")
        if urlparse(item["source_url"]).scheme != "https":
            raise ValueError("Only HTTPS acquisition URLs are allowed")
        if item.get("owned_repository"):
            if item["owned_repository"] not in ("ambisgis-postgresql", "ambisgis-postgis"):
                raise ValueError("Owned source is outside the authorized slice")
            if not re.fullmatch(r"[0-9a-f]{40}", item.get("commit", "")):
                raise ValueError("Owned source needs an exact commit")
        for notice in item["license_evidence"]:
            relative_path(notice["original_path"])
            relative_path(notice["retained_path"])
            if not re.fullmatch(r"[0-9a-f]{64}", notice["sha256"]):
                raise ValueError("Invalid notice SHA256")
    return manifest


def verify_artifact(path: Path, item: dict) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Missing or symlinked archive: {path.name}")
    if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
        raise ValueError(f"Archive integrity mismatch: {path.name}")


def checked_members(archive: tarfile.TarFile, root: str) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    files = set()
    for member in members:
        path = relative_path(member.name)
        if path.parts[0] != root:
            raise ValueError(f"Unexpected archive root: {member.name}")
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError(f"Unsupported archive entry: {member.name}")
        if not member.isdir():
            if member.name in files:
                raise ValueError(f"Duplicate archive entry: {member.name}")
            files.add(member.name)
    return members


def extract_input(custody: Path, destination: Path, item: dict) -> Path:
    archive_path = custody / item["artifact"]
    verify_artifact(archive_path, item)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / item["archive_root"]
    # Never trust or overwrite a previously extracted/build-mutated source tree.
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Extraction destination already exists: {target}")
    with tempfile.TemporaryDirectory(prefix=".extract-", dir=destination) as scratch:
        with tarfile.open(archive_path) as archive:
            members = checked_members(archive, item["archive_root"])
            archive.extractall(scratch, members=members, filter="data")
        source = Path(scratch) / item["archive_root"]
        if not source.is_dir() or source.is_symlink():
            raise ValueError("Archive root must be a directory")
        source.rename(target)
    return target


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != "https":
            raise ValueError("Refusing a redirect outside HTTPS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_input(custody: Path, item: dict, source_workspace: Path | None = None) -> None:
    target = custody / item["artifact"]
    if target.exists() or target.is_symlink():
        verify_artifact(target, item)
        return
    custody.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".acquire-", dir=custody) as scratch:
        pending = Path(scratch) / item["artifact"]
        if item.get("owned_repository"):
            if source_workspace is None:
                raise ValueError("Owned archive recovery requires --source-workspace")
            repo = source_workspace / item["owned_repository"]
            origin = subprocess.check_output(["git", "-C", str(repo), "remote", "get-url", "origin"], text=True).strip()
            expected = "https://github.com/aloerch/" + item["owned_repository"] + ".git"
            if origin != expected:
                raise ValueError("Owned clone origin differs from recorded authority")
            commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", item["commit"] + "^{commit}"], text=True).strip()
            if commit != item["commit"]:
                raise ValueError("Owned commit identity mismatch")
            subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", "--prefix=" + item["archive_root"] + "/", "-o", str(pending), commit], check=True)
        else:
            request = urllib.request.Request(item["source_url"], headers={"User-Agent": "AmbisGIS-FND02-source-custody"})
            opener = urllib.request.build_opener(HTTPSOnlyRedirect())
            with opener.open(request, timeout=90) as response, pending.open("wb") as output:
                if urlparse(response.geturl()).scheme != "https":
                    raise ValueError("Only HTTPS responses are accepted")
                copied = 0
                while chunk := response.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > item["bytes"]:
                        raise ValueError("Downloaded archive exceeds recorded size")
                    output.write(chunk)
        verify_artifact(pending, item)
        os.replace(pending, target)


def retain_licenses(custody: Path, item: dict) -> None:
    verify_artifact(custody / item["artifact"], item)
    with tarfile.open(custody / item["artifact"]) as archive:
        checked_members(archive, item["archive_root"])
        for notice in item["license_evidence"]:
            member = archive.getmember(item["archive_root"] + "/" + notice["original_path"])
            if not member.isfile():
                raise ValueError("License evidence must be a regular source file")
            with archive.extractfile(member) as source:
                content = source.read()
            if hashlib.sha256(content).hexdigest() != notice["sha256"]:
                raise ValueError("Original license evidence hash mismatch")
            target = custody / notice["retained_path"]
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_file() or sha256(target) != notice["sha256"]:
                    raise ValueError("Existing retained license evidence differs")
            else:
                if not target.parent.resolve().is_relative_to(custody.resolve()):
                    raise ValueError("License directory escapes custody")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)


def verify_input(custody: Path, item: dict) -> None:
    verify_artifact(custody / item["artifact"], item)
    for notice in item["license_evidence"]:
        path = custody / notice["retained_path"]
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(custody.resolve()):
            raise ValueError("Missing or unsafe retained license evidence")
        if sha256(path) != notice["sha256"]:
            raise ValueError("Retained license evidence hash mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("inputs.json"))
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true", help="explicitly acquire missing pinned inputs and original license copies")
    parser.add_argument("--extract", type=Path, help="extract verified archives into a fresh destination")
    parser.add_argument("--source-workspace", type=Path, help="owned clone directory, only needed to recreate missing owned archives")
    parser.add_argument("--only", action="append", default=[], help="limit to an exact manifest input name (repeatable)")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    known = {item["name"] for item in manifest["inputs"]}
    if set(args.only) - known:
        parser.error("Unknown input selection")
    for item in manifest["inputs"]:
        if args.only and item["name"] not in args.only:
            continue
        if args.fetch:
            fetch_input(args.custody, item, args.source_workspace)
            retain_licenses(args.custody, item)
        verify_input(args.custody, item)
        if args.extract:
            extract_input(args.custody, args.extract, item)
        print(json.dumps({"name": item["name"], "sha256": item["sha256"], "verified": True}))


if __name__ == "__main__":
    main()
