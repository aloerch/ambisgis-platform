#!/usr/bin/env python3
"""Inventory pinned Maven declarations without resolving or executing Maven.

All inputs come from Git objects, never the checkout. Properties, inheritance,
profiles, plugin configuration and repository policies remain unevaluated.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


class AuditError(Exception):
    """An input cannot be inventoried faithfully."""


# Tag objects were inspected from the retained owned repositories. All four
# selected tags are lightweight; tag object and commit identity are identical.
PINS = (
    ("ambisgis-geotools", "34.5", "aac73e9b89821331e77f67f1dd0921e541a78cfc"),
    ("ambisgis-geowebcache", "1.28.5", "59640420454b73f1e04e8409cc6ed43f4b24fed2"),
    ("ambisgis-geoserver", "2.28.5", "e0673323400321c0f3409fbae68b4871dc328d8a"),
    ("ambisgis-geonode", "5.1.0", "a1db97e81dfc26c16bb4ee1a5d2b408877af66c9"),
)
MAVEN_NS = "http://maven.apache.org/POM/4.0.0"
EXPRESSION = re.compile(r"\$\{([^{}]+)\}")


def git(repo: Path, *args: str, optional: bool = False) -> bytes:
    # No external credential helper, hooks, replacement objects, lazy object
    # fetch or protocol is needed for these local config/object reads.
    env = {
        "PATH": os.defpath, "LANG": "C", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1",
        "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
    }
    result = subprocess.run(
        ["git", "-c", "protocol.allow=never", "-c", "core.hooksPath=" + os.devnull,
         "-C", str(repo), *args], env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if optional and result.returncode == 1:
        return b""
    if result.returncode:
        # Git diagnostics can contain local URLs with embedded credentials.
        raise AuditError(f"{repo.name}: local git {args[0]} failed ({result.returncode})")
    return result.stdout


def verify_source(repo: Path, name: str, tag: str, commit: str) -> dict:
    expected = f"https://github.com/aloerch/{name}.git"
    origins = git(repo, "config", "--get-all", "remote.origin.url").decode().splitlines()
    push = git(repo, "config", "--get-all", "remote.origin.pushurl", optional=True).decode().splitlines()
    if origins != [expected] or (push and push != [expected]):
        raise AuditError(f"{name}: owned origin identity mismatch")
    if git(repo, "config", "--get-regexp", r"^(extensions\.partialclone|remote\..*\.promisor)$", optional=True):
        raise AuditError(f"{name}: partial/promisor repositories are not accepted")
    actual = git(repo, "rev-parse", "--verify", "refs/tags/" + tag).decode().strip()
    peeled = git(repo, "rev-parse", "--verify", "refs/tags/" + tag + "^{commit}").decode().strip()
    if actual != commit or peeled != commit:
        raise AuditError(f"{name}: selected tag object or commit identity mismatch")
    if git(repo, "cat-file", "-t", commit).strip() != b"commit":
        raise AuditError(f"{name}: selected object is not a commit")
    return {"repository": "aloerch/" + name, "origin": expected,
            "tag": tag, "tag_object": actual, "commit": commit}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def xml_tree(node: ET.Element) -> dict:
    """Retain ordered children and duplicate fields; do not apply Maven defaults."""
    result = {"name": node.tag}
    if node.attrib:
        result["attributes"] = dict(sorted(node.attrib.items()))
    if node.text and node.text.strip():
        result["text"] = node.text.strip()
    if list(node):
        result["children"] = [xml_tree(child) for child in node]
    if node.tail and node.tail.strip():
        result["tail"] = node.tail.strip()
    return result


def walk_xml(node: ET.Element, path: str = ""):
    path = path or "/" + local_name(node.tag) + "[1]"
    yield path, node
    counts: dict[str, int] = {}
    for child in node:
        name = local_name(child.tag)
        counts[name] = counts.get(name, 0) + 1
        yield from walk_xml(child, path + f"/{name}[{counts[name]}]")


def parse_xml(data: bytes, source_path: str) -> ET.Element:
    # ElementTree does not fetch external entities, but reject DTDs/entities
    # entirely, including UTF-16/32 spellings, before parsing untrusted XML.
    declaration_probe = data.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in declaration_probe or b"<!ENTITY" in declaration_probe:
        raise AuditError(f"{source_path}: DTD/entity declarations are unsupported")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise AuditError(f"{source_path}: malformed XML: {exc}") from exc


def parse_pom(data: bytes, source_path: str) -> dict:
    root = parse_xml(data, source_path)
    if root.tag not in ("project", "{" + MAVEN_NS + "}project"):
        raise AuditError(f"{source_path}: unsupported POM root or namespace")
    namespace = root.tag[:-len("project")]
    def child_text(parent: ET.Element, name: str):
        found = parent.find(namespace + name)
        return None if found is None else (found.text or "").strip()
    def coordinates(parent: ET.Element):
        names = ("groupId", "artifactId", "version", "packaging", "relativePath")
        return {name: child_text(parent, name) for name in names
                if parent.find(namespace + name) is not None}
    parent = root.find(namespace + "parent")
    result = {
        "project": coordinates(root),
        "parent": None if parent is None else coordinates(parent),
        "properties": [], "modules": [], "profiles": [], "dependencies": [],
        "plugins": [], "repositories": [], "extensions": [], "distribution_management": [], "findings": [],
    }
    for path, node in walk_xml(root):
        name = local_name(node.tag)
        value = (node.text or "").strip()
        parent_path = path.rsplit("/", 1)[0]
        record = {"xml_path": path, "declaration": xml_tree(node)}
        if re.search(r"/properties\[\d+\]$", parent_path):
            result["properties"].append({"xml_path": path, "name": name, "value": value})
        if name == "module" and re.search(r"/modules\[\d+\]$", parent_path):
            result["modules"].append({"xml_path": path, "value": value})
        if name == "profile" and re.search(r"/profiles\[\d+\]$", parent_path):
            activation = node.find(namespace + "activation")
            result["profiles"].append({"xml_path": path, "id": child_text(node, "id"),
                                      "activation": None if activation is None else xml_tree(activation)})
        if name == "distributionManagement" and re.search(r"/(project|profile)\[\d+\]$", parent_path):
            result["distribution_management"].append(record)
        for category, item, container in (
            ("dependencies", "dependency", "dependencies"),
            ("plugins", "plugin", "plugins"),
            ("repositories", "repository", "repositories"),
            ("repositories", "pluginRepository", "pluginRepositories"),
            ("extensions", "extension", "extensions"),
        ):
            if name == item and re.search(r"/" + container + r"\[\d+\]$", parent_path):
                result[category].append(record)
        expressions = sorted(set(EXPRESSION.findall(value)))
        if expressions:
            result["findings"].append({"kind": "unevaluated_expression", "xml_path": path,
                                       "value": value, "symbols": expressions})
        # A property may later be a version through indirection; report its
        # literal without assuming that any profile/property is effective.
        version_context = name == "version" or re.search(r"/properties\[\d+\]$", parent_path)
        if version_context and value:
            kinds = []
            if "SNAPSHOT" in value:
                kinds.append("snapshot_literal")
            if value in ("LATEST", "RELEASE"):
                kinds.append("floating_version_literal")
            if re.fullmatch(r"[\[(].*[\])]", value):
                kinds.append("version_range_candidate")
            for kind in kinds:
                result["findings"].append({"kind": kind, "xml_path": path, "value": value})
    return result


def inventory_source(owned_root: Path, pin: tuple[str, str, str]) -> dict:
    name, tag, commit = pin
    repo = owned_root / name
    result = verify_source(repo, name, tag, commit)
    result.update({"poms": [], "maven_configs": [], "gitlinks": [], "parse_errors": []})
    entries = git(repo, "ls-tree", "-rz", commit).split(b"\x00")
    for entry in entries:
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        path = path_bytes.decode("utf-8")
        parts = PurePosixPath(path).parts
        if kind == "commit":
            result["gitlinks"].append({"source_path": path, "commit": blob,
                                       "status": "not_recursively_inventoried"})
            continue
        is_pom = parts[-1] == "pom.xml"
        is_config = ".mvn" in parts or parts[-1] in ("settings.xml", "toolchains.xml", "extensions.xml")
        if not (is_pom or is_config):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise AuditError(f"{name}/{path}: Maven input is not a regular tracked file")
        data = git(repo, "cat-file", "blob", blob)
        record = {"source_path": path, "git_blob": blob, "mode": mode,
                  "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
        if is_pom:
            try:
                record.update(parse_pom(data, f"{name}/{path}"))
            except AuditError as exc:
                record.update({"parse_error": str(exc), "encoding": "base64",
                               "content": base64.b64encode(data).decode("ascii")})
                result["parse_errors"].append({"source_path": path, "error": str(exc)})
            result["poms"].append(record)
        else:
            try:
                record.update({"encoding": "utf-8", "content": data.decode("utf-8")})
            except UnicodeDecodeError:
                record.update({"encoding": "base64", "content": base64.b64encode(data).decode("ascii")})
            if parts[-1].endswith(".xml"):
                try:
                    record["declaration"] = xml_tree(parse_xml(data, f"{name}/{path}"))
                except AuditError as exc:
                    record["parse_error"] = str(exc)
                    result["parse_errors"].append({"source_path": path, "error": str(exc)})
            result["maven_configs"].append(record)
    result["tracked_file_enumeration_complete"] = True
    result["xml_interpretation_complete"] = not result["parse_errors"]
    return result


def create_inventory(owned_root: Path, pins=PINS) -> dict:
    sources = [inventory_source(owned_root, pin) for pin in pins]
    complete = all(source["xml_interpretation_complete"] for source in sources)
    return {
        "format_version": 1,
        "status": "static_declarations_only" if complete else "static_declarations_with_parse_errors",
        "tracked_file_enumeration_complete": True, "xml_interpretation_complete": complete,
        "effective_poms_resolved": False, "transitive_closure_resolved": False,
        "donor_scripts_executed": False,
        "semantics": [
            "All tracked pom.xml files at the pinned Git commits, including fixtures and inactive modules.",
            "XML paths preserve declaration context; dependencies include management, profile and plugin contexts.",
            "Distribution management retains publication repositories, snapshot repositories, relocation and site declarations without executing them.",
            "No inheritance, property interpolation, profile activation, Maven defaults or repository resolution is evaluated.",
            "Findings describe unevaluated declarations, not the selected build's effective dependency graph.",
            "Configurations include all tracked .mvn files and settings.xml, toolchains.xml and extensions.xml at any path.",
            "Gitlinks are listed but not traversed; arbitrary build scripts and external/user/global Maven settings are outside this inventory.",
            "Local origin and tag checks do not authenticate current GitHub repository identity or license/security approval.",
        ],
        "sources": sources,
    }


def write_inventory(output: Path, inventory: dict) -> None:
    encoded = json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    # Exclusive creation prevents both accidental overwrite and symlink following.
    with output.open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owned-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise AuditError("output already exists; choose a new path")
        inventory = create_inventory(args.owned_root)
        write_inventory(args.output, inventory)
    except (AuditError, OSError, UnicodeError, ValueError) as exc:
        print(f"audit failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote static declaration inventory to {args.output}")
    if not inventory["xml_interpretation_complete"]:
        print("audit incomplete: malformed/unsupported XML retained as diagnostics", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
