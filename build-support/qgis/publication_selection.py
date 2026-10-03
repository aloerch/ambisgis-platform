"""Exact source-publication variant adapter; accepted selection recipe stays unchanged."""
import json
from pathlib import Path
import stat
import xml.etree.ElementTree as ET

from resource_selection import (PLATFORM, SOURCE_RESOURCE, RESOURCE, NOTICE_ROOT,
                                require, sha, inventory, verify_inventory, audit_packaged_references)

def publication_variant_stage(repo, commit, tree, expected, provenance, selection_path,
                              accepted_manifest, output, replay_output, verify_only=False):
    """Materialize only this reviewed source variant's palette/notice stage.

    The old two recipe modes are unchanged. This adapter consumes a complete,
    independently restored snapshot; absence is valid only for its exact 1,130
    bound source omissions. A complete stage can be verified idempotently; any
    extra/missing/changed path fails. No old source archive is consulted.
    """
    if verify_only:
        require(output.is_dir() and not output.is_symlink()
                and replay_output.is_dir() and not replay_output.is_symlink(),
                'read-only verification requires both existing resource stages')
    import hashlib
    import importlib.util
    publication_path = PLATFORM / "build-support/source_publication/qgis_snapshot.py"
    spec = importlib.util.spec_from_file_location("qgis_publication_adapter", publication_path)
    publication = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publication)
    require(publication.git(repo, "rev-parse", commit+"^{tree}").decode().strip() == tree,
            "variant snapshot tree mismatch")
    actual = publication.tree_entries(repo, commit)
    require(actual == expected, "variant complete source mismatch")
    require(provenance["original_commit"] == publication.BASE
            and provenance["original_tree"] == publication.BASE_TREE
            and provenance["selection_sha256"] == publication.SELECTION_SHA,
            "wrong variant source binding")
    require(sha(accepted_manifest) == publication.STAGE_SHA, "wrong accepted resource manifest")
    selection, excluded = publication.load_selection(selection_path)
    require(set(excluded).isdisjoint(actual), "excluded source payload reintroduced")
    mapping = provenance["retained_file_mapping"]
    require({r["path"]: {"mode":r["mode"], "oid":r["snapshot_oid"]} for r in mapping}
            == {p:r for p,r in actual.items() if p not in (publication.PROVENANCE, publication.NOTICE)},
            "variant provenance/inventory disagreement")
    reader = publication.Blobs(repo)
    payloads = {}; catalogue_notices = {}; relocated = []
    roots = [r.removeprefix("share/qgis/") for r in selection["omitted_collection_roots"]]
    changes = {r["path"]:r for r in provenance["catalogue_changes"]}
    require(len(changes) == 19, "variant catalogue change count")
    try:
        for path,row in sorted(actual.items()):
            if not path.startswith(SOURCE_RESOURCE):
                continue
            require(row["mode"] == "100644", "unexpected resource mode")
            data = reader.read(row["oid"])
            target = "share/qgis/" + path
            if any(path.startswith(root+"/") for root in roots):
                require(Path(path).suffix in (".xml", ".txt"), "unexpected omitted collection content")
                target = NOTICE_ROOT + "omitted-metadata/" + path.removeprefix(SOURCE_RESOURCE)
                relocated.append({"source":path, "target":target, "sha256":publication.digest(data)})
            if path in changes:
                change = changes[path]
                require(publication.digest(data) == change["after_sha256"], "variant catalogue identity")
                comment = change["notice"].encode()
                require(data.count(comment) == 1, "missing or duplicated modification notice")
                old_stage = data.replace(comment, b"", 1)
                require(ET.tostring(ET.fromstring(data)) == ET.tostring(ET.fromstring(old_stage)),
                        "catalogue notice changes effective XML")
                catalogue_notices[target] = {"notice":change["notice"],
                                             "accepted_sha256":publication.digest(old_stage),
                                             "variant_sha256":publication.digest(data)}
            payloads[target] = data
        require(len(relocated) == 84 and len(catalogue_notices) == 19, "variant metadata scope")
        notices = {"default-icons-LICENSE.TXT":"images/themes/default/LICENSE.TXT",
                   "QGIS-Vera-COPYRIGHT.TXT":"tests/testdata/font/QGIS-Vera/COPYRIGHT.TXT",
                   "QGIS-Vera-README.txt":"tests/testdata/font/QGIS-Vera/QGIS-Vera-README.txt"}
        for target,source in notices.items():
            payloads[NOTICE_ROOT+target] = reader.read(actual[source]["oid"])
        payloads[NOTICE_ROOT+"README.txt"] = (
            "Private proposed QGIS resource profile. Exactly 1,130 optional SVG palettes are omitted.\n"
            "The old source/stage remain custody records, not approved distribution bundles.\n"
            "ColorBrewer: This product includes color specifications and designs developed by Cynthia Brewer (http://colorbrewer.org/).\n"
            "Its exact acknowledgement, naming and notice terms remain in resources/cpt-city-qgis-min/cb/COPYING.xml.\n"
            "Other inherited resource/support/icon/font obligations remain; these additions are not legal clearance.\n"
            "Omitted collection metadata/notices are retained here outside the active palette archive.\n"
            "Saved projects can retain serialized symbol/shader colors, but omitted named ramps cannot be selected or reloaded.\n"
            "Reclassification from such a ramp requires an explicit user choice; full saved-project compatibility is not claimed.\n"
        ).encode()
        accepted = {r["path"]:r for r in json.loads(Path(accepted_manifest).read_text())["files"]
                    if r["path"].startswith((RESOURCE, NOTICE_ROOT))}
        require(set(payloads) == set(accepted), "complete selected resource path mismatch")
        for path,data in payloads.items():
            expected_sha = catalogue_notices[path]["accepted_sha256"] if path in catalogue_notices else publication.digest(data)
            require(accepted[path]["sha256"] == expected_sha, "retained resource bytes changed: "+path)
            if path not in catalogue_notices:
                require(accepted[path]["bytes"] == len(data), "retained resource length changed")
        for row in selection["colorbrewer"]:
            require(publication.digest(payloads[row["path"]]) == row["sha256"], "ColorBrewer changed")
        # Preserve the new source notice alongside inherited packaging notices.
        payloads[NOTICE_ROOT+"SOURCE-PUBLICATION.md"] = reader.read(actual[publication.NOTICE]["oid"])
    finally:
        reader.close()
    expected_stage = [{"path":p,"bytes":len(data),"sha256":publication.digest(data)}
                      for p,data in sorted(payloads.items())]
    def materialize_or_verify(target):
        if target.exists():
            require(target.is_dir() and not target.is_symlink(), "unexpected resource output")
            verify_inventory(target, expected_stage)
            require(all(stat.S_IMODE((target/p).stat().st_mode) == 0o644 for p in payloads),
                    "resource stage modes changed")
            return "already-exact"
        target.mkdir(parents=True)
        for p,data in payloads.items():
            destination = target/p
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            destination.chmod(0o644)
        verify_inventory(target, expected_stage)
        return "created"
    initial = materialize_or_verify(output)
    replay = materialize_or_verify(output)
    second = materialize_or_verify(replay_output)
    require(inventory(output) == inventory(replay_output), "independent resource replay differs")
    audit = audit_packaged_references(output, selection)
    audit['scope'] = ('This palette/notice projection contains no containers; source .qrc checked separately. '
                      'Native resource enumeration is reused historical evidence, not reexecuted.')
    return {"scope":"Palette archive and corresponding notices; other source/build inputs independently unchanged.",
            "source_commit":commit,"source_tree":tree,"accepted_stage_sha256":publication.STAGE_SHA,
            "selection_sha256":publication.SELECTION_SHA,"output":str(output),"replay_output":str(replay_output),
            "initial":initial,"unchanged_reapply":replay,"second_fresh_stage":second,
            "selected_entries":len(expected_stage),"accepted_projection_entries":len(accepted),
            "unchanged_entries":len(accepted)-len(catalogue_notices),
            "catalogue_notice_only_changes":catalogue_notices,"catalogue_effective_xml_equal":True,
            "added_notice":NOTICE_ROOT+"SOURCE-PUBLICATION.md","relocated_original_metadata":relocated,
            "retained_colorbrewer":265,"exact_omissions":1130,"packaged_reference_audit":audit,
            "inventory_sha256":publication.digest(publication.encoded(expected_stage)),
            "idempotent_replay_mutations":0,"original_source_archive_reads":0,
            "restored_source_resources_only":True}
