#!/usr/bin/env python3
"""Verify retained, fixed Java tool inputs; optional hash-locked acquisition/extract.

No tool executable or Maven goal is run. Discovery endpoints are never queried.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class CustodyError(ValueError):
    pass


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def entries(manifest: dict) -> list[dict]:
    if manifest.get("schema_version") != 1:
        raise CustodyError("unsupported manifest schema")
    result = manifest.get("files", [])
    if not result:
        raise CustodyError("empty manifest")
    seen = set()
    for item in result:
        name = item.get("path", "")
        if not name or PurePosixPath(name).name != name or name in (".", "..") or "\\" in name:
            raise CustodyError(f"unsafe custody path: {name!r}")
        if name in seen:
            raise CustodyError(f"duplicate custody path: {name}")
        seen.add(name)
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            raise CustodyError(f"invalid SHA256: {name}")
        if type(item.get("bytes")) is not int or item["bytes"] < 0:
            raise CustodyError(f"invalid size: {name}")
        url = item.get("acquire_url")
        if url:
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise CustodyError(f"unsafe acquisition URL: {name}")
            if parsed.hostname not in {"github.com", "downloads.apache.org", "codeload.github.com"}:
                raise CustodyError(f"unapproved acquisition host: {name}")
            if "latest" in parsed.path.split("/"):
                raise CustodyError(f"floating acquisition URL: {name}")
    for archive in manifest.get("archives", []):
        if archive.get("path") not in seen or archive.get("publisher_checksum") not in seen:
            raise CustodyError("archive or publisher checksum absent from retained files")
        if archive.get("algorithm") not in {"sha256", "sha512"}:
            raise CustodyError("unsupported publisher checksum algorithm")
        root = archive.get("root", "")
        if not root or PurePosixPath(root).name != root or root in {".", ".."} or "\\" in root:
            raise CustodyError("unsafe archive root")
        if archive.get("role") not in {"distribution", "source"}:
            raise CustodyError("unknown archive role")
    return result


def check_file(root: Path, item: dict) -> None:
    path = root / item["path"]
    if path.is_symlink() or not path.is_file():
        raise CustodyError(f"missing/nonregular retained file: {item['path']}")
    if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
        raise CustodyError(f"changed retained file: {item['path']}")


def acquire(root: Path, manifest: dict) -> None:
    """Acquire only missing fixed-URL files; existing changed inputs stop first."""
    rows = entries(manifest)
    for item in rows:
        path = root / item["path"]
        if path.exists() or path.is_symlink():
            check_file(root, item)
    for item in rows:
        path = root / item["path"]
        if path.exists() or not item.get("acquire_url"):
            continue
        temporary = None
        try:
            request = Request(item["acquire_url"], headers={"User-Agent": "AmbisGIS-FND02-custody"})
            with urlopen(request, timeout=60) as response, tempfile.NamedTemporaryFile(dir=root, prefix=".toolchain-", delete=False) as stream:
                temporary = Path(stream.name)
                if urlparse(response.url).scheme != "https":
                    raise CustodyError("refusing non-HTTPS redirect")
                total = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    total += len(chunk)
                    if total > item["bytes"]:
                        raise CustodyError(f"download exceeds locked size: {item['path']}")
                    stream.write(chunk)
            if temporary.stat().st_size != item["bytes"] or digest(temporary) != item["sha256"]:
                raise CustodyError(f"download does not match lock: {item['path']}")
            # Link is atomic and refuses existing destinations; never overwrite.
            os.link(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def verify(root: Path, manifest: dict) -> dict:
    rows = entries(manifest)
    if root.is_symlink() or not root.is_dir():
        raise CustodyError("custody must be an existing real directory")
    expected = {item["path"] for item in rows}
    unexpected = {p.name for p in root.iterdir()} - expected
    if unexpected:
        raise CustodyError(f"unrecorded custody entries: {sorted(unexpected)}")
    for item in rows:
        check_file(root, item)
    for archive in manifest["archives"]:
        checksum = root / archive["publisher_checksum"]
        declared = checksum.read_text().split()[0].lower()
        if digest(root / archive["path"], archive["algorithm"]) != declared:
            raise CustodyError(f"publisher checksum mismatch: {archive['path']}")
    return {"files": len(rows), "bytes": sum(item["bytes"] for item in rows),
            "publisher_checksums": len(manifest["archives"]), "verified": True,
            "signature_trust_verified": False, "toolchain_rebuild_closure_complete": False}


def extract(root: Path, manifest: dict, destination: Path) -> None:
    verify(root, manifest)
    if not hasattr(tarfile, "data_filter"):
        raise CustodyError("safe extraction requires tarfile.data_filter (Python 3.12+ or backport)")
    if destination.exists() or destination.is_symlink():
        raise CustodyError("extract destination must not already exist")
    destination.mkdir(parents=True)
    for archive in manifest["archives"]:
        if archive["role"] != "distribution":
            continue
        with tarfile.open(root / archive["path"]) as stream:
            members = stream.getmembers()
            seen = {}
            for member in members:
                parts = PurePosixPath(member.name).parts
                if not parts or parts[0] != archive["root"] or ".." in parts or (member.name in seen and not (member.isdir() and seen[member.name])):
                    raise CustodyError(f"unsafe/duplicate archive member: {member.name}")
                seen[member.name] = member.isdir()
                # Validate the entire archive before extracting any of its members.
                tarfile.data_filter(member, str(destination))
            stream.extractall(destination, members=members, filter="data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("toolchain-inputs.json"))
    parser.add_argument("--acquire", action="store_true", help="download missing hash-locked inputs only; restore metadata/receipts from backup")
    parser.add_argument("--extract", type=Path, help="extract distributions to a NEW directory after complete verification")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text())
        entries(manifest)
        if args.custody.is_symlink():
            raise CustodyError("custody cannot be a symlink")
        if args.acquire:
            args.custody.mkdir(parents=True, exist_ok=True)
            acquire(args.custody, manifest)
        result = verify(args.custody, manifest)
        if args.extract:
            extract(args.custody, manifest, args.extract)
            result["extracted_to"] = str(args.extract)
        print(json.dumps(result, indent=2))
        return 0
    except (CustodyError, OSError, ValueError, tarfile.TarError) as error:
        print(json.dumps({"verified": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
