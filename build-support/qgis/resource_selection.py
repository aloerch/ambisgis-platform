#!/usr/bin/env python3
"""Replayable private QGIS external-resource selection; never edits its baseline."""
import argparse
import copy
from collections import Counter
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import time
import xml.etree.ElementTree as ET

from common import inventory, require, save, sha, verify_inventory

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1]
RESOURCE = "share/qgis/resources/cpt-city-qgis-min/"
SOURCE_RESOURCE = "resources/cpt-city-qgis-min/"
EXPECTED = {"SRC-01":256, "SRC-02":138, "SRC-03":690, "SRC-04":45}
BASELINE_SHA = "931e5f0523e1d9bdba6b2fbd27e6c208297456db696265beb961a57e77ed82c9"
SOURCE_SHA = "229ce420ccf5f993eff29e58dc500f2fe7337395595989f947481c34c8cfb875"
NOTICE_ROOT = "share/qgis/doc/ambisgis-resource-selection/"
PARENT_MANIFEST_SHA = "4e65c76d2af1bc811dca913d0450d4ab614f5cf14c3c9022d544796e5130a8a3"
PARENT_SELECTION_SHA = "b420a3e29ae619d0a17e1ff4991a45559b65c284f527f14c3915d72bb924c2fd"
GMT_ALIAS = {"path":RESOURCE+"gmt/GMT_dem1.svg", "bytes":591,
             "sha256":"0ba1cad3e42202036ab6a86663a09d377eb84eb22584df0e4dbc9fdee54cf602"}
GMT_AUTHORIZATION = "Current owner Java/GMT remediation prompt section 2.A/5 explicitly authorizes only gmt/GMT_dem1.svg exclusion; PR #66 merge alone does not."


def derive_gmt_successor(rows, parent):
    """Extend the pinned selection-03 inventory by the single authorized alias."""
    by_path = {row["path"]:row for row in rows}
    require(len(by_path) == len(rows), "duplicate parent stage path")
    for row in rows: safe_path(row["path"])
    require(by_path.get(GMT_ALIAS["path"]) == GMT_ALIAS, "recorded GMT alias identity mismatch")
    require(len(parent["exclusions"]) == 1129 and not set(parent["exclusions"]) & set(by_path),
            "parent exclusions not preserved")
    require({k:v["count"] for k,v in parent["groups"].items()} == EXPECTED, "parent grouping changed")
    require(len(parent["colorbrewer"]) == 265 and all(by_path.get(row["path"]) == row for row in parent["colorbrewer"]),
            "parent ColorBrewer identity changed")
    selected = copy.deepcopy(parent)
    selected["exclusions"][GMT_ALIAS["path"]] = "SRC-02"
    selected["groups"]["SRC-02"]["files"].append(dict(GMT_ALIAS))
    selected["groups"]["SRC-02"]["count"] += 1
    selected["additional_exclusion_authorization"] = GMT_AUTHORIZATION
    require(len(selected["exclusions"]) == 1130, "successor cumulative exclusion mismatch")
    return selected


def safe_path(value):
    p = PurePosixPath(value)
    require(not p.is_absolute() and value and ".." not in p.parts and str(p) == value, "unsafe manifest path")
    return p


def derive_selection(rows, findings):
    """Resolve the recorded notice scopes against exact baseline inventory rows."""
    by_path = {r["path"]:r for r in rows}
    require(len(by_path) == len(rows), "duplicate baseline path")
    for row in rows: safe_path(row["path"])
    selected = {}; groups = {}; notices = {}
    for key, expected in EXPECTED.items():
        matches = [f for f in findings if f["id"] == key]
        require(len(matches) == 1, "missing or duplicate targeted finding")
        finding = matches[0]
        scope_notices = finding.get("notice_files", finding.get("notices", [finding.get("notice")]))
        require(len(scope_notices) == {"SRC-01":19,"SRC-02":2,"SRC-03":1,"SRC-04":1}[key], "notice scope count mismatch")
        group = []
        for notice in scope_notices:
            source_path = notice["source_path"]
            require(source_path.startswith(SOURCE_RESOURCE) and source_path.endswith("/COPYING.xml"), "unexpected notice scope")
            staged_notice = "share/qgis/" + source_path
            require(by_path[staged_notice]["sha256"] == notice["sha256"], "notice binding mismatch")
            scope = str(PurePosixPath(staged_notice).parent) + "/"
            subset = [r for r in rows if r["path"].startswith(scope) and r["path"].endswith(".svg")]
            if "selected_svg_files" in notice:
                require(len(subset) == notice["selected_svg_files"], "individual notice scope count mismatch")
            notices[staged_notice] = notice["sha256"]
            for row in subset:
                require(row["path"] not in selected, "overlapping exclusion scopes")
                selected[row["path"]] = key
            group.extend(subset)
        require(len(group) == expected, "targeted palette count mismatch: " + key)
        groups[key] = {"count":len(group), "reason":finding["subject"], "files":group}
    require(len(selected) == 1129, "total exclusion mismatch")
    cb = [r for r in rows if r["path"].startswith(RESOURCE+"cb/") and r["path"].endswith(".svg")]
    require(len(cb) == 265 and not (set(selected) & {r["path"] for r in cb}), "ColorBrewer count or overlap mismatch")
    # Derive maximal now-empty collections from exact SVG memberships. Moving
    # their metadata out of the active archive removes empty collection entries.
    dirs = {}
    for row in rows:
        name = row["path"]
        if name.startswith(RESOURCE) and name.endswith(".svg"):
            for parent in PurePosixPath(name).parents:
                if str(parent)+"/" == RESOURCE: break
                dirs.setdefault(str(parent), set()).add(name)
    empty = {d for d, members in dirs.items() if members <= set(selected)}
    roots = sorted(d for d in empty if not any(str(p) in empty for p in PurePosixPath(d).parents))
    return {"groups":groups, "exclusions":selected, "omitted_collection_roots":roots,
            "notice_hashes":notices, "colorbrewer":cb}


def trim_catalogue(data, omitted_roots, omitted_schemes=()):
    root = ET.fromstring(data); removed = []
    for parent in root.iter():
        for element in list(parent):
            directory = element.get("dir")
            if directory and (any(directory == p or directory.startswith(p+"/") for p in omitted_roots)
                              or directory+"/"+element.get("file", "") in omitted_schemes):
                require(element.tag in ("gradient", "collect"), "unexpected omitted-resource XML reference")
                removed.append({"tag":element.tag,"attributes":dict(element.attrib)})
                parent.remove(element)
    if not removed: return data, []
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)+b"\n", removed


def file_ref(path):
    path = Path(path)
    return {"path":str(path), "sha256":sha(path), "bytes":path.stat().st_size}


def source_audit(source_archive, selection):
    require(sha(source_archive) == SOURCE_SHA, "owned source archive changed")
    required = {"resources/CMakeLists.txt", "src/core/qgscolorrampimpl.cpp", "src/core/symbology/qgscptcityarchive.cpp"}
    qrc = []; source = {}; palette_members = {}
    wanted = {p.removeprefix("share/qgis/"):p for p in selection["exclusions"]}
    with tarfile.open(source_archive) as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            relative = "/".join(parts[1:])
            if not member.isfile(): continue
            if relative in required or relative.endswith(".qrc") or relative in wanted:
                data = archive.extractfile(member).read()
                import hashlib
                digest = hashlib.sha256(data).hexdigest()
                if relative in required: source[relative] = {"sha256":digest,"bytes":len(data)}
                if relative in wanted: palette_members[wanted[relative]] = digest
                if relative.endswith(".qrc"):
                    tree = ET.fromstring(data)
                    entries = [el.text or "" for el in tree.iter("file")]
                    # Any cpt-city embedding requires a revised build, not loose-file selection.
                    require(not any("cpt-city" in entry for entry in entries), "palette resource compiled into Qt resource collection")
                    qrc.append({"path":relative,"sha256":digest,"entries":len(entries)})
    require(set(source) == required, "required resource-loading source absent")
    for group in selection["groups"].values():
        for row in group["files"]: require(palette_members.get(row["path"]) == row["sha256"], "staged palette differs from owned source")
    return {"archive":file_ref(source_archive), "selected_palette_members_verified":len(palette_members),
            "source_contracts":source,"qrc_files":qrc,"cpt_city_qrc_entries":0,
            "interpretation":"CMake installs external files; QgsCptCityColorRamp::fileName resolves the selected archive and gradientColorMap reads QFile. No cpt-city Qt resource entry."}



def audit_packaged_references(prefix, selection):
    """Inspect active XML, SQLite payloads and container magic, not filenames alone."""
    import re
    import sqlite3
    omitted = {p.removeprefix(RESOURCE).removesuffix(".svg") for p in selection["exclusions"]}
    omitted_dirs = [r.removeprefix(RESOURCE) for r in selection["omitted_collection_roots"]]
    expression = re.compile("|".join(re.escape(name) for name in sorted(omitted)))
    databases = []; xml_files = 0; files = 0; containers = []
    for path in sorted(prefix.rglob("*")):
        if not path.is_file() or path.is_symlink(): continue
        files += 1
        with path.open("rb") as stream: head = stream.read(512)
        relative = str(path.relative_to(prefix))
        if head.startswith((b"PK\x03\x04", b"\x1f\x8b", b"\xfd7zXZ", b"RCC")) or head[257:262] == b"ustar":
            containers.append(relative)
        if head.startswith(b"SQLite format 3\x00"):
            connection = sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)
            text_values = 0
            try:
                for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                    quoted = '"'+table.replace('"','""')+'"'
                    for row in connection.execute("SELECT * FROM "+quoted):
                        for value in row:
                            if isinstance(value, bytes): value = value.decode("utf-8", errors="ignore")
                            if isinstance(value, str):
                                text_values += 1
                                require(expression.search(value) is None, "omitted scheme embedded in database: "+relative)
                databases.append({"path":relative,"sha256":sha(path),"text_values_scanned":text_values})
            finally: connection.close()
        if path.suffix == ".xml" and not relative.startswith(NOTICE_ROOT):
            try: tree = ET.fromstring(path.read_bytes())
            except ET.ParseError: continue
            xml_files += 1
            for element in tree.iter():
                values = element.attrib
                # Native style XML and cpt-city catalogue semantic references.
                if values.get("k", values.get("name")) == "schemeName":
                    value = values.get("v", values.get("value", ""))
                    require(value not in omitted and not any(value == d or value.startswith(d+"/") for d in omitted_dirs), "omitted ramp in packaged style")
                if element.tag == "gradient" and "dir" in values and "file" in values:
                    require(values["dir"]+"/"+values["file"] not in omitted, "omitted ramp in packaged catalogue")
    require(not containers, "packaged container needs explicit member audit")
    return {"regular_files_magic_scanned":files,"packaged_containers":containers,
            "active_xml_documents_scanned":xml_files,"sqlite_databases":databases,
            "omitted_scheme_references":[],"scope":"Qt embedding independently checked against every source qrc and native runtime resource enumeration."}


def run(args):
    started = time.monotonic(); output = args.output.resolve()
    followup = bool(args.parent_selection)
    require(not output.exists() and not output.is_relative_to(args.baseline.resolve()), "fresh output outside baseline required")
    output.mkdir(parents=True, mode=0o700); output.chmod(0o700)
    report = {"result_exit_code":1,"authorization":GMT_AUTHORIZATION if followup else "Current owner remediation prompt; PR #65 accepted only the consolidation baseline.",
              "scope":"New private external-resource variant; no source rewrite, compile, distribution permission or owner adoption."}
    producer = {name:file_ref(HERE/name) for name in ("resource_selection.py","common.py")}
    report["executed_recipe"] = {"command":[sys.executable,*sys.argv],"files_before":producer}
    try:
        require(sha(args.manifest) == (PARENT_MANIFEST_SHA if followup else BASELINE_SHA), "baseline manifest identity mismatch")
        rows = json.loads(args.manifest.read_text())["files"]
        verify_inventory(args.baseline, rows)
        rights_path = args.rights
        require(sha(rights_path) == "06718c9ed6178558bd6a846b9e403d9723d0202ca22bb7638ef564147156e751", "rights authority changed")
        rights = json.loads(rights_path.read_text())
        if followup:
            require(sha(args.parent_selection) == PARENT_SELECTION_SHA, "parent selection identity mismatch")
            selection = derive_gmt_successor(rows, json.loads(args.parent_selection.read_text()))
            report["parent_selection"] = file_ref(args.parent_selection)
            report["excluded_alias"] = dict(GMT_ALIAS)
            report["preserved_alias_scope_notice"] = file_ref(args.baseline/(RESOURCE+"gmt/COPYING.xml"))
            report["original_provenance_limitation"] = "Identical bytes do not establish identical licensing; exclusion avoids unresolved provenance without invalidating the recorded GMT grant."
        else:
            selection = derive_selection(rows, rights["qgis_resources"])
        report["source_audit"] = source_audit(args.source_archive, selection)
        report["baseline_manifest"] = file_ref(args.manifest)
        report["rights_evidence"] = file_ref(rights_path)
        save(output/"selection.json",selection); save(output/"before-manifest.json", {"prefix":str(args.baseline),"files":rows})
        tooling = output/"tooling"; tooling.mkdir()
        for name in ("resource_selection.py","common.py"): shutil.copyfile(HERE/name,tooling/name)
        save(output/"tooling.json", inventory(tooling))
        prefix = output/"prefix"
        shutil.copytree(args.baseline, prefix, symlinks=True)
        for path in prefix.rglob("*"):
            if path.is_symlink(): require(path.resolve().is_relative_to(prefix), "stage symlink escapes new prefix")
        removed = {GMT_ALIAS["path"]} if followup else set(selection["exclusions"])
        for path in sorted(removed): (prefix/path).unlink()
        relocations = []
        for root in ([] if followup else selection["omitted_collection_roots"]):
            for path in sorted((prefix/root).rglob("*")):
                if path.is_file():
                    relative = str(path.relative_to(prefix)); target = NOTICE_ROOT+"omitted-metadata/"+relative.removeprefix(RESOURCE)
                    require(path.suffix in (".xml", ".txt"), "unexpected extra content in omitted collection")
                    (prefix/target).parent.mkdir(parents=True,exist_ok=True)
                    path.rename(prefix/target); removed.add(relative)
                    relocations.append({"from":relative,"to":target,"sha256":sha(prefix/target)})
            for path in sorted((prefix/root).rglob("*"),reverse=True):
                if path.is_dir(): path.rmdir()
            (prefix/root).rmdir()
        roots = [root.removeprefix(RESOURCE) for root in selection["omitted_collection_roots"]]
        changes = []
        for path in sorted((prefix/(RESOURCE+"selections")).glob("*.xml")):
            data, refs = trim_catalogue(path.read_bytes(),roots, {"gmt/GMT_dem1"} if followup else ())
            if refs:
                original = sha(path); path.write_bytes(data)
                changes.append({"path":str(path.relative_to(prefix)),"before_sha256":original,"after_sha256":sha(path),"removed_references":refs})
        if followup:
            require(len(changes) == 7 and sum(len(row["removed_references"]) for row in changes) == 7,
                    "expected exact seven GMT catalogue references")
        notices = {} if followup else {"default-icons-LICENSE.TXT":"images/themes/default/LICENSE.TXT",
                   "QGIS-Vera-COPYRIGHT.TXT":"tests/testdata/font/QGIS-Vera/COPYRIGHT.TXT",
                   "QGIS-Vera-README.txt":"tests/testdata/font/QGIS-Vera/QGIS-Vera-README.txt"}
        with tarfile.open(args.source_archive) as archive:
            for target, member in notices.items():
                matches = [m for m in archive.getmembers() if m.isfile() and m.name.endswith("/"+member)]
                require(len(matches) == 1,"notice member ambiguity")
                (prefix/(NOTICE_ROOT+target)).write_bytes(archive.extractfile(matches[0]).read())
        readme = (f"Private proposed QGIS resource profile. Exactly {len(selection['exclusions']):,} optional SVG palettes are omitted.\n"
                  "The old source/stage remain custody records, not approved distribution bundles.\n"
                  "ColorBrewer: This product includes color specifications and designs developed by Cynthia Brewer (http://colorbrewer.org/).\n"
                  "Its exact acknowledgement, naming and notice terms remain in resources/cpt-city-qgis-min/cb/COPYING.xml.\n"
                  "Other inherited resource/support/icon/font obligations remain; these additions are not legal clearance.\n"
                  "Omitted collection metadata/notices are retained here outside the active palette archive.\n"
                  "Saved projects can retain serialized symbol/shader colors, but omitted named ramps cannot be selected or reloaded.\n"
                  "Reclassification from such a ramp requires an explicit user choice; full saved-project compatibility is not claimed.\n")
        readme_path = prefix/(NOTICE_ROOT+"README.txt")
        original_readme = sha(readme_path) if followup else None
        readme_path.write_text(readme)
        if followup:
            report["notice_readme_change"] = {"path":NOTICE_ROOT+"README.txt", "before_sha256":original_readme, "after_sha256":sha(readme_path)}
        report["packaged_reference_audit"] = audit_packaged_references(prefix, selection)
        after = inventory(prefix); before_by = {r["path"]:r for r in rows}; after_by = {r["path"]:r for r in after}
        changed = {e["path"] for e in changes}
        if followup: changed.add(NOTICE_ROOT+"README.txt")
        additions = set(after_by)-set(before_by)
        require(set(before_by)-set(after_by) == removed,"unexpected removed stage files")
        require({p for p in set(before_by)&set(after_by) if before_by[p] != after_by[p]} == changed,"unrelated staged bytes changed")
        require(all(p.startswith(NOTICE_ROOT) for p in additions),"unexpected stage addition")
        modes = {}
        for p in sorted(set(before_by)&set(after_by)):
            require(stat.S_IMODE((args.baseline/p).lstat().st_mode) == stat.S_IMODE((prefix/p).lstat().st_mode),"unrelated stage mode changed")
        excluded_hashes = {r["sha256"] for g in selection["groups"].values() for r in g["files"]}
        alternate_copies = [r for r in after if r.get("sha256") in excluded_hashes]
        expected_alias = GMT_ALIAS
        require(alternate_copies == ([] if followup else [expected_alias]), "unexpected alternate excluded-palette copy")
        require(not set(selection["exclusions"]) & set(after_by), "cumulative omitted palette remains")
        alias_notice = file_ref(prefix/(RESOURCE+"gmt/COPYING.xml"))
        report["alternate_copy_blockers"] = [] if followup else [{"finding":"F06-QGIS-SRC-02", "retained":expected_alias,
            "excluded_path":RESOURCE+"td/DEM_print.svg", "retained_scope_notice":alias_notice,
            "interpretation":"Byte-identical palette remains under separate GMT GPLv2 notice; exact named td path is absent. Differing provenance/notice scope remains unresolved; no extra deletion or clearance inferred."}]
        require(all(after_by[r["path"]] == r for r in selection["colorbrewer"]),"ColorBrewer altered")
        verify_inventory(args.baseline,rows)
        require(inventory(tooling) == json.loads((output/"tooling.json").read_text()),"tooling changed")
        save(output/"after-manifest.json",{"prefix":str(prefix),"source_commit":"1a4cda5f2620e7374e5926fc955a7d2d06493e15","files":after})
        report.update(result_exit_code=0, selection=file_ref(output/"selection.json"), output_manifest=file_ref(output/"after-manifest.json"),
                      prefix=str(prefix), palette_counts={k:v["count"] for k,v in selection["groups"].items()},
                      retained_colorbrewer=265, before_entries=len(rows), after_entries=len(after),
                      removed_palette_files=len(selection["exclusions"]), newly_removed_palette_files=1 if followup else len(selection["exclusions"]), relocated_metadata=relocations, catalogue_changes=changes,
                      added_files=[after_by[p] for p in sorted(additions)], unchanged_files=len(set(before_by)&set(after_by))-len(changed),
                      baseline_unchanged=True, retained_modes_unchanged=True, alternate_exact_palette_copies=alternate_copies,
                      compile_steps=0, tooling=file_ref(output/"tooling.json"))
    except BaseException as error: report["error"]={"type":type(error).__name__,"message":str(error)}
    report["executed_recipe"]["files_after"] = {name:file_ref(HERE/name) for name in producer}
    if report["executed_recipe"]["files_after"] != producer:
        report["result_exit_code"] = 1; report["producer_integrity_error"] = "executed recipe changed"
    report["seconds"] = round(time.monotonic()-started,3)
    save(output/"result.json",report)
    print(json.dumps({"output":str(output),"result_exit_code":report["result_exit_code"],"error":report.get("error")}))
    return report["result_exit_code"]


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,required=True);parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--parent-selection",type=Path,help="Pinned selection-03 selection.json; explicitly selects the authorized one-file GMT follow-up")
    parser.add_argument("--rights",type=Path,default=PLATFORM/"plan/verification/candidate-selection/frontend-qgis-rights.json")
    parser.add_argument("--source-archive",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    raise SystemExit(run(parser.parse_args()))
