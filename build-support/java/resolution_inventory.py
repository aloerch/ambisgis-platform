#!/usr/bin/env python3
"""Verify retained Maven inputs and report candidate source/license coverage.

Default operation reads custody only. --acquire-sources explicitly adds exact
base-GAV sources and POMs through maven_proxy, from each binary's recorded origin.
The 19 narrowly reviewed schema resource capsules are independently revalidated
and serve as their own XML/XSD source candidates; their POMs are still retained.
Neither a sources classifier nor a declared license proves binary correspondence,
complete build inputs, license compatibility, or permission to redistribute.
Reports and their sibling <report-stem>.notices directory must be fresh.
Exit: 0 = integrity and candidate source coverage; 1 = integrity/report error;
2 = verified custody with explicit source/POM gaps. build_ready is always false.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Callable
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile
import zlib

REPOSITORIES = {
    "central": "https://repo.maven.apache.org/maven2",
    "osgeo": "https://repo.osgeo.org/repository/release",
}
_SEGMENT = re.compile(r"[A-Za-z0-9_.+~-]+\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_NS = {"m": "http://maven.apache.org/POM/4.0.0"}
_MAX_NOTICE = 16 * 1024 * 1024
_MAX_NOTICE_TOTAL = 64 * 1024 * 1024


class InventoryError(Exception):
    pass


def checked_path(path: Path, *, directory: bool = False) -> None:
    """Reject symlinks in every component, including ancestors outside custody."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise InventoryError("symlink component is forbidden")
        if current != path and not stat.S_ISDIR(mode):
            raise InventoryError("non-directory path component")
    mode = path.lstat().st_mode
    if directory and not stat.S_ISDIR(mode):
        raise InventoryError("expected a directory")
    if not directory and not stat.S_ISREG(mode):
        raise InventoryError("expected a regular file")


def read_file(path: Path) -> bytes:
    checked_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise InventoryError("expected a regular file")
        return stream.read()


def walk_files(root: Path, errors: list[dict]) -> list[Path]:
    result = []
    try:
        checked_path(root, directory=True)
    except (InventoryError, OSError) as exc:
        errors.append({"path": str(root), "error": str(exc)})
        return result
    def inaccessible(exc):
        errors.append({"path": str(exc.filename), "error": "cannot enumerate custody directory"})
    for folder, directories, files in os.walk(root, followlinks=False, onerror=inaccessible):
        for name in list(directories):
            path = Path(folder) / name
            if path.is_symlink():
                errors.append({"path": str(path), "error": "symlink directory is forbidden"})
                directories.remove(name)
        result.extend(Path(folder) / name for name in files)
    return sorted(result)


def schema_api(path: str):
    """Require the reviewed validator only when schema jar/sidecar inputs occur."""
    if path.startswith("org/geotools/schemas/") and ".jar" in path.rsplit("/", 1)[-1]:
        try:
            import schema_resources
        except ImportError as exc:
            raise InventoryError("schema resource validator is required for schema jar custody") from exc
        return schema_resources
    return None


def classification(path: str) -> str:
    schema = schema_api(path)
    if schema is not None:
        if schema.schema_coordinate(path) is not None:
            return "source-resource-archive"
        if schema.schema_checksum(path) is not None:
            return "source-resource-checksum"
    name = path.rsplit("/", 1)[-1]
    while any(name.endswith(x) for x in (".sha1", ".sha256", ".sha512", ".md5", ".asc")):
        name = name.rsplit(".", 1)[0]
    if name == "maven-metadata.xml":
        return "mutable-discovery-metadata"
    return "upstream-pom-metadata" if name.endswith(".pom") else "artifact"


def validate_maven_path(path: str) -> None:
    if not isinstance(path, str) or not path or len(path) > 4096:
        raise InventoryError("invalid Maven path")
    parts = path.split("/")
    if any(x in {"", ".", ".."} or not _SEGMENT.fullmatch(x) for x in parts):
        raise InventoryError("unsafe Maven path")
    version = parts[-2] if len(parts) >= 4 else ""
    if "SNAPSHOT" in version.upper() or version in {"LATEST", "RELEASE"}:
        raise InventoryError("moving snapshot/latest/release coordinates are forbidden")


def validate_url(url: str) -> None:
    if not isinstance(url, str):
        raise InventoryError("invalid artifact URL")
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.username is None and parsed.password is None
                 and not parsed.query and not parsed.fragment and parsed.port in (None, 443))
    except ValueError as exc:
        raise InventoryError("invalid artifact URL") from exc
    bases = [base for base in REPOSITORIES.values() if url.startswith(base + "/")]
    if not valid or not bases:
        raise InventoryError("URL is outside approved HTTPS release repositories")
    validate_maven_path(url[len(bases[0]) + 1:])


def hash_file(path: Path) -> tuple[str, int]:
    checked_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    digest, size = hashlib.sha256(), 0
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise InventoryError("expected a regular file")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError("duplicate JSON object key")
        result[key] = value
    return result


def verify_custody(custody: Path | str) -> dict:
    root = Path(os.path.abspath(custody))
    errors, records, blobs = [], [], {}
    record_files = walk_files(root / "records", errors)
    for path in walk_files(root / "blobs" / "sha256", errors):
        relative = path.relative_to(root / "blobs" / "sha256")
        try:
            if len(relative.parts) != 1 or not _HASH.fullmatch(relative.name):
                raise InventoryError("unexpected blob path")
            digest, size = hash_file(path)
            if digest != relative.name:
                raise InventoryError("blob SHA256 differs from its content address")
            blobs[digest] = size
        except (OSError, InventoryError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
    for path in record_files:
        try:
            relative = path.relative_to(root / "records")
            if len(relative.parts) < 2 or path.suffix != ".json":
                raise InventoryError("unexpected record path")
            record = json.loads(read_file(path), object_pairs_hook=unique_object)
            if not isinstance(record, dict):
                raise InventoryError("record must be an object")
            if any(key in record for key in ("source_resource_verified", "source_resource_checksum_verified")):
                raise InventoryError("record must not supply derived resource verification flags")
            repository = record["repository"]
            maven_path = record["maven_path"]
            validate_maven_path(maven_path)
            if repository not in REPOSITORIES:
                raise InventoryError("unknown repository")
            expected = PurePosixPath(repository) / (maven_path + ".json")
            if relative.as_posix() != str(expected):
                raise InventoryError("record filesystem path differs from Maven identity")
            if (record.get("schema_version") != 1 or type(record.get("schema_version")) is not int
                    or record.get("status") != 200 or type(record.get("status")) is not int
                    or type(record.get("size")) is not int or record["size"] < 0
                    or record.get("classification") != classification(maven_path)
                    or record.get("original_url") != REPOSITORIES[repository] + "/" + maven_path):
                raise InventoryError("record identity/status/classification mismatch")
            validate_url(record["final_url"])
            digest = record["sha256"]
            if not isinstance(digest, str) or not _HASH.fullmatch(digest):
                raise InventoryError("invalid SHA256 field")
            if digest not in blobs or blobs[digest] != record["size"]:
                raise InventoryError("record has no verified blob of the recorded size")
            extra = {}
            if record["classification"] == "source-resource-archive":
                observed = schema_api(maven_path).validate_schema_archive(
                    maven_path, read_file(root / "blobs" / "sha256" / digest))
                if (observed != record.get("source_resource_validation")
                        or observed["artifact_sha256"] != digest
                        or observed["artifact_size"] != record["size"]):
                    raise InventoryError("schema resource validation differs from retained manifest")
                extra["source_resource_verified"] = True
            records.append({**record, **extra, "record_path": str(path.relative_to(root)),
                            "blob_path": "blobs/sha256/" + digest})
        except (OSError, InventoryError, ValueError, KeyError, TypeError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
    indexed = {(r["repository"], r["maven_path"]): r for r in records}
    checked_records = []
    for record in records:
        try:
            if record["classification"] == "source-resource-checksum":
                source_path, algorithm = schema_api(record["maven_path"]).schema_checksum(record["maven_path"])
                source = indexed.get((record["repository"], source_path))
                if source is None or not source.get("source_resource_verified"):
                    raise InventoryError("schema checksum lacks validated same-origin source archive")
                source_bytes = read_file(root / source["blob_path"])
                if hashlib.sha256(source_bytes).hexdigest() != source["sha256"]:
                    raise InventoryError("schema archive changed during checksum verification")
                actual = hashlib.new(algorithm, source_bytes).hexdigest()
                text = read_file(root / record["blob_path"]).decode("ascii").strip().split()
                if (len(text) not in (1, 2) or text[0].lower() != actual
                        or (len(text) == 2 and text[1].lstrip("*") != source_path.rsplit("/", 1)[-1])):
                    raise InventoryError("schema checksum bytes disagree with source archive")
                observed = {"schema_version": 1, "source_archive_path": source_path,
                            "source_archive_sha256": source["sha256"],
                            "checksum_algorithm": algorithm, "checksum": actual}
                if observed != record.get("source_resource_validation"):
                    raise InventoryError("schema checksum validation differs from retained manifest")
                record["source_resource_checksum_verified"] = True
            checked_records.append(record)
        except (OSError, InventoryError, ValueError, KeyError, TypeError) as exc:
            errors.append({"path": str(root / record["record_path"]), "error": str(exc)})
    records = checked_records
    referenced = {r["sha256"] for r in records}
    return {"custody_root": str(root), "artifacts": records,
            "verification": {"valid": not errors, "record_count": len(record_files),
                "verified_record_count": len(records), "verified_blob_count": len(blobs),
                "orphan_blobs": sorted(set(blobs) - referenced), "errors": errors}}


def jar_coordinate(path: str) -> dict | None:
    if not path.endswith(".jar"):
        return None
    parts = path.split("/")
    if len(parts) < 4:
        raise InventoryError("jar path has no complete Maven GAV")
    artifact, version, filename = parts[-3:]
    prefix = artifact + "-" + version
    stem = filename[:-4]
    if stem != prefix and not stem.startswith(prefix + "-"):
        raise InventoryError("jar filename does not match its artifact and base version")
    classifier = stem[len(prefix):].removeprefix("-")
    if classifier in {"sources", "javadoc"} or classifier.endswith(("-sources", "-javadoc")):
        return None
    directory = "/".join(parts[:-1])
    return {"group": ".".join(parts[:-3]), "artifact": artifact, "version": version,
            "classifier": classifier or None, "gav": ":".join((".".join(parts[:-3]), artifact, version)),
            "sources_path": directory + "/" + prefix + "-sources.jar",
            "pom_path": directory + "/" + prefix + ".pom"}


def acquire_sources(custody: Path | str, records: list[dict], fetch: Callable | None = None) -> list[dict]:
    """Acquire candidate sources/POM once per origin/GAV; never start an HTTP listener."""
    if fetch is None:
        from maven_proxy import MavenCustodyProxy
        fetch = MavenCustodyProxy(custody).fetch
    results, attempted = [], set()
    for record in records:
        try:
            coordinate = jar_coordinate(record["maven_path"])
        except InventoryError:
            continue  # The final coverage report records unrecognizable binary paths.
        if coordinate is None:
            continue
        keys = ("pom_path",) if record.get("source_resource_verified") else ("pom_path", "sources_path")
        for key in keys:
            path = coordinate[key]
            identity = (record["repository"], path)
            if identity in attempted:
                continue
            attempted.add(identity)
            result = {"repository": identity[0], "maven_path": path}
            try:
                retained = fetch(path, repository=identity[0])
                result.update(status="retained", sha256=retained.record["sha256"])
            except Exception as exc:
                result.update(status="gap", error_type=type(exc).__name__, error=str(exc))
            results.append(result)
    return results


def pom_licenses(data: bytes) -> dict:
    # Inspect declarations through XML callbacks before building the tree so the
    # refusal also applies to UTF-16 and other encodings recognized by Expat.
    parser = expat.ParserCreate()

    def refuse_declaration(*unused):
        raise ValueError("DTD/entity declarations are not interpreted")

    parser.StartDoctypeDeclHandler = refuse_declaration
    parser.EntityDeclHandler = refuse_declaration
    parser.ExternalEntityRefHandler = refuse_declaration
    try:
        parser.Parse(data, True)
        root = ET.fromstring(data)
        if root.tag == "{http://maven.apache.org/POM/4.0.0}project":
            licenses = root.findall("m:licenses/m:license", _NS)
        elif root.tag == "project":
            licenses = root.findall("licenses/license")
        else:
            raise ValueError("POM root is not Maven project")
        return {"declarations": [{child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
                                  for child in license_element}
                                 for license_element in licenses],
                "inherited_licenses_resolved": False, "license_approval": False}
    except (expat.ExpatError, ET.ParseError, ValueError) as exc:
        return {"declarations": [], "error": str(exc), "license_approval": False}


def archive_notices(path: Path) -> tuple[list[dict], dict[str, bytes], list[str]]:
    notices, content, errors = [], {}, []
    try:
        checked_path(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream, zipfile.ZipFile(stream) as archive:
            total = 0
            if len(archive.infolist()) > 200000:
                raise InventoryError("archive entry count exceeds inspection bound")
            for index, entry in enumerate(archive.infolist()):
                basename = entry.filename.replace("\\", "/").rsplit("/", 1)[-1].upper()
                if entry.is_dir() or not re.match(r"^(LICENSE|LICENCE|NOTICE|COPYING)(?:$|[._-])", basename):
                    continue
                if entry.file_size > _MAX_NOTICE or total + entry.file_size > _MAX_NOTICE_TOTAL:
                    errors.append("notice size bound exceeded: " + entry.filename)
                    continue
                data = archive.read(entry)
                total += len(data)
                digest = hashlib.sha256(data).hexdigest()
                content[digest] = data
                notices.append({"entry": entry.filename, "entry_index": index,
                                "size": len(data), "sha256": digest})
    except (OSError, zipfile.BadZipFile, RuntimeError, InventoryError, NotImplementedError, zlib.error, EOFError) as exc:
        errors.append(str(exc))
    return notices, content, errors


def make_report(custody: Path | str, acquisition: list[dict] | None = None) -> tuple[dict, dict[str, bytes]]:
    report = verify_custody(custody)
    report.update(schema_version=1, generated_at=datetime.now(timezone.utc).isoformat(),
        build_ready=False, source_binary_correspondence_established=False, license_approval=False,
        repository_policy={"allowed_release_bases": REPOSITORIES, "snapshot_coordinates": "denied",
            "snapshot_repository_urls": "denied", "discovery_metadata": "retained but not a version lock",
            "records_checked": report["verification"]["valid"]},
        limitations=["Candidate sources do not establish binary correspondence or complete build inputs.",
            "Base sources may omit tests or native code for classified binaries.",
            "POM licenses are declarations only; parent inheritance and compatibility remain unreviewed.",
            "Notice discovery is a filename heuristic; absent notices do not imply absent obligations."],
        acquisition=acquisition or [], source_coverage=[], missing_sources=[], pom_licenses=[], notices=[],
        license_notice_gaps=[])
    root = Path(report["custody_root"])
    records = {(r["repository"], r["maven_path"]): r for r in report["artifacts"]}
    contents, zip_errors, pom_errors, parsed_poms = {}, {}, {}, {}
    for record in report["artifacts"]:
        path = record["maven_path"]
        identity = (record["repository"], path)
        if path.endswith(".pom"):
            parsed = pom_licenses(read_file(root / record["blob_path"]))
            parsed_poms[identity] = parsed
            report["pom_licenses"].append({"repository": identity[0], "maven_path": path,
                "sha256": record["sha256"], **parsed})
            if parsed.get("error"):
                pom_errors[identity] = parsed["error"]
        if path.endswith((".jar", ".zip")):
            found, data, errors = archive_notices(root / record["blob_path"])
            contents.update(data)
            report["notices"].append({"repository": identity[0], "maven_path": path,
                "artifact_sha256": record["sha256"], "entries": found, "inspection_errors": errors})
            if errors:
                zip_errors[identity] = errors
    for record in report["artifacts"]:
        path, repository = record["maven_path"], record["repository"]
        try:
            coordinate = jar_coordinate(path)
        except InventoryError as exc:
            report["missing_sources"].append({"repository": repository, "binary_path": path, "reason": str(exc)})
            continue
        if coordinate is None:
            continue
        row = {**coordinate, "repository": repository, "binary_path": path,
               "binary_sha256": record["sha256"], "binary_size": record["size"],
               "binary_original_url": record["original_url"], "binary_final_url": record["final_url"],
               "coverage_scope": "base-GAV source candidate; classifier contents and correspondence unverified"}
        resource_source = record.get("source_resource_verified", False)
        if resource_source:
            row["sources_path"] = path
            row["coverage_scope"] = "validated XML/XSD source-data capsule; owned offline repackaging remains unverified"
            row["source_resource_validation"] = record["source_resource_validation"]
            for resource in record["source_resource_validation"].get("missing_resources", []):
                report["missing_sources"].append({"repository": repository, "binary_path": path,
                    "required_path": resource, "kind": "schema-resource",
                    "reason": "validated capsule omits a resource declared by the owned packaging recipe"})
            row["sources"] = {"status": "retained-source-resource-candidate", "maven_path": path,
                              **{k: record[k] for k in ("sha256", "size", "original_url", "final_url", "blob_path")}}
            if not record["source_resource_validation"].get("notices"):
                report["license_notice_gaps"].append({"repository": repository, "maven_path": path,
                    "reason": "no separately named notice/license files; XML-embedded notices require file review"})
            if not parsed_poms.get((repository, coordinate["pom_path"]), {}).get("declarations"):
                report["license_notice_gaps"].append({"repository": repository, "maven_path": path,
                    "reason": "no POM license declaration retained; schema terms remain unreviewed"})
        requirements = [("pom_path", "pom", pom_errors)] if resource_source else [
            ("sources_path", "sources", zip_errors), ("pom_path", "pom", pom_errors)]
        for key, label, parse_errors in requirements:
            identity = (repository, coordinate[key])
            retained = records.get(identity)
            valid = retained is not None and identity not in parse_errors
            row[label] = {"status": "retained-candidate" if valid else "gap", "maven_path": coordinate[key]}
            if retained:
                row[label].update({k: retained[k] for k in ("sha256", "size", "original_url", "final_url", "blob_path")})
            if not valid:
                reason = "not retained from binary origin" if retained is None else "retained input could not be interpreted"
                row[label]["reason"] = reason
                report["missing_sources"].append({"repository": repository, "binary_path": path,
                    "required_path": coordinate[key], "kind": label, "reason": reason})
        report["source_coverage"].append(row)
    report["archive_notice_inspection_complete"] = not zip_errors
    report["source_coverage_binary_count"] = len(report["source_coverage"])
    report["source_coverage_complete"] = report["verification"]["valid"] and not report["missing_sources"]
    return report, contents


def fresh_output(output: Path) -> Path:
    output = Path(os.path.abspath(output))
    checked_path(output.parent, directory=True)
    notices = output.with_name(output.stem + ".notices")
    if output.exists() or output.is_symlink() or notices.exists() or notices.is_symlink():
        raise InventoryError("report and notice directory must both be fresh")
    return notices


def write_report(output: Path, report: dict, contents: dict[str, bytes]) -> None:
    notices = fresh_output(output)
    notices.mkdir(mode=0o700)
    for digest, data in sorted(contents.items()):
        with (notices / digest).open("xb") as stream:
            stream.write(data)
    for archive in report["notices"]:
        for notice in archive["entries"]:
            notice["retained_path"] = notices.name + "/" + notice["sha256"]
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--acquire-sources", action="store_true")
    args = parser.parse_args(argv)
    try:
        fresh_output(args.output)
        acquisition = []
        if args.acquire_sources:
            initial = verify_custody(args.custody)
            if initial["verification"]["valid"]:
                acquisition = acquire_sources(args.custody, initial["artifacts"])
        report, contents = make_report(args.custody, acquisition)
        write_report(args.output, report, contents)
        print(json.dumps({"output": str(args.output), "verification": report["verification"],
                          "source_gap_count": len(report["missing_sources"]), "build_ready": False}, sort_keys=True))
        if not report["verification"]["valid"]:
            return 1
        return 2 if report["missing_sources"] else 0
    except (InventoryError, OSError, ImportError) as exc:
        parser.exit(1, "inventory refused: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
