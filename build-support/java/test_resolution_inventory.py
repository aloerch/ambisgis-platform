"""Offline regression checks for custody integrity and honest source coverage."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import resolution_inventory as inventory


def jar(entries=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in (entries or {"example.class": b"bytecode"}).items():
            archive.writestr(path, data)
    return stream.getvalue()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.custody = self.root / "custody"
        (self.custody / "records").mkdir(parents=True)
        (self.custody / "blobs" / "sha256").mkdir(parents=True)
        self.base = "org/example/tool/1.2/tool-1.2"

    def retain(self, path, data, repository="central", **changes):
        digest = hashlib.sha256(data).hexdigest()
        blob = self.custody / "blobs" / "sha256" / digest
        if not blob.exists():
            blob.write_bytes(data)
        record = {"schema_version": 1, "repository": repository, "maven_path": path,
                  "sha256": digest, "size": len(data), "status": 200,
                  "original_url": inventory.REPOSITORIES[repository] + "/" + path,
                  "final_url": inventory.REPOSITORIES[repository] + "/" + path,
                  "classification": inventory.classification(path),
                  "acquired_at": "2026-09-19T00:00:00+00:00",
                  "license_status": "unreviewed"}
        record.update(changes)
        record_file = self.custody / "records" / repository / (path + ".json")
        record_file.parent.mkdir(parents=True, exist_ok=True)
        record_file.write_text(json.dumps(record))
        return SimpleNamespace(record=record, path=blob, record_file=record_file)

    def complete_gav(self, classifier="", repository="central"):
        binary = self.retain(self.base + classifier + ".jar", jar(), repository)
        self.retain(self.base + "-sources.jar", jar({"Example.java": b"class Example {}"}), repository)
        self.retain(self.base + ".pom", b'<project xmlns="http://maven.apache.org/POM/4.0.0"><licenses><license><name>Example license</name><url>https://example.org/license</url></license></licenses></project>', repository)
        return binary

    def test_complete_coverage_remains_candidate_and_not_build_ready(self):
        self.complete_gav()
        report, _ = inventory.make_report(self.custody)
        self.assertTrue(report["verification"]["valid"])
        self.assertEqual(report["verification"]["verified_record_count"], 3)
        self.assertTrue(report["source_coverage_complete"])
        self.assertFalse(report["build_ready"])
        self.assertFalse(report["license_approval"])
        self.assertFalse(report["source_binary_correspondence_established"])
        self.assertEqual(report["pom_licenses"][0]["declarations"][0]["name"], "Example license")
        self.assertFalse(report["pom_licenses"][0]["inherited_licenses_resolved"])

    def test_hash_and_size_tampering_fail_integrity(self):
        first = self.retain(self.base + ".jar", jar())
        second = self.retain("org/example/other/2/other-2.pom", b"<project/>", size=99)
        first.path.write_bytes(b"changed")
        result = inventory.verify_custody(self.custody)
        self.assertFalse(result["verification"]["valid"])
        self.assertEqual(result["verification"]["record_count"], 2)
        self.assertEqual(result["verification"]["verified_record_count"], 0)
        self.assertEqual(len(result["verification"]["errors"]), 3)
        self.assertTrue(second.path.exists())

    def test_every_record_is_checked_after_one_invalid_record(self):
        self.retain(self.base + ".jar", jar(), status=500)
        self.retain(self.base + ".pom", b"<project/>")
        result = inventory.verify_custody(self.custody)
        self.assertEqual(result["verification"]["record_count"], 2)
        self.assertEqual(result["verification"]["verified_record_count"], 1)
        self.assertFalse(result["verification"]["valid"])

    def test_duplicate_record_keys_are_rejected(self):
        artifact = self.retain(self.base + ".jar", jar())
        original = artifact.record_file.read_text()
        artifact.record_file.write_text('{"size": 1,' + original[1:])
        report = inventory.verify_custody(self.custody)
        self.assertFalse(report["verification"]["valid"])
        self.assertIn("duplicate", report["verification"]["errors"][0]["error"])

    def test_release_group_names_are_not_moving_version_aliases(self):
        self.retain("org/apache/maven/release/maven-release/3.0.1/maven-release-3.0.1.pom", b"<project/>")
        report = inventory.verify_custody(self.custody)
        self.assertTrue(report["verification"]["valid"])
        for version in ("LATEST", "RELEASE", "1.2-SNAPSHOT"):
            with self.assertRaises(inventory.InventoryError):
                inventory.validate_maven_path("org/example/tool/" + version + "/tool.pom")

    def test_record_path_identity_is_checked(self):
        artifact = self.retain(self.base + ".jar", jar())
        artifact.record_file.rename(artifact.record_file.with_name("wrong.json"))
        result = inventory.verify_custody(self.custody)
        self.assertFalse(result["verification"]["valid"])
        self.assertIn("filesystem path", result["verification"]["errors"][0]["error"])

    def test_snapshot_paths_and_snapshot_repository_urls_rejected(self):
        self.retain("org/example/a/1-SNAPSHOT/a-1-SNAPSHOT.jar", jar())
        self.retain(self.base + ".pom", b"<project/>", final_url="https://repo.osgeo.org/repository/snapshot/tool.pom")
        result = inventory.verify_custody(self.custody)
        self.assertFalse(result["verification"]["valid"])
        self.assertEqual(result["verification"]["verified_record_count"], 0)

    def test_symlink_record_blob_and_directory_are_not_followed(self):
        artifact = self.retain(self.base + ".jar", jar())
        replacement = self.root / "outside"
        replacement.write_bytes(artifact.path.read_bytes())
        artifact.path.unlink()
        artifact.path.symlink_to(replacement)
        (self.custody / "records" / "linked").symlink_to(self.root, target_is_directory=True)
        (self.custody / "records" / "linked.json").symlink_to(replacement)
        result = inventory.verify_custody(self.custody)
        self.assertFalse(result["verification"]["valid"])
        self.assertGreaterEqual(len(result["verification"]["errors"]), 3)

    def test_metadata_and_sidecars_are_preserved_without_becoming_binaries(self):
        self.retain("org/example/tool/maven-metadata.xml", b"<metadata/>")
        self.retain(self.base + ".pom.sha1", b"abc123")
        self.retain(self.base + ".jar.sha256", b"abc123")
        report, _ = inventory.make_report(self.custody)
        self.assertEqual(len(report["artifacts"]), 3)
        self.assertEqual(report["source_coverage"], [])
        self.assertEqual(report["artifacts"][2]["classification"], "mutable-discovery-metadata")

    def test_test_and_native_classifiers_use_base_version_sources(self):
        for classifier in ("-tests", "-linux-x86_64", "-natives-linux"):
            self.complete_gav(classifier)
        report, _ = inventory.make_report(self.custody)
        self.assertEqual(len(report["source_coverage"]), 3)
        for item in report["source_coverage"]:
            self.assertEqual(item["sources_path"], self.base + "-sources.jar")
            self.assertEqual(item["version"], "1.2")
            self.assertIn("classifier contents", item["coverage_scope"])
        for classifier in ("-sources", "-test-sources", "-javadoc", "-test-javadoc"):
            self.assertIsNone(inventory.jar_coordinate(self.base + classifier + ".jar"))

    def test_same_gav_other_repository_is_not_silent_source_correspondence(self):
        self.retain(self.base + ".jar", jar(), "osgeo")
        self.retain(self.base + "-sources.jar", jar(), "central")
        self.retain(self.base + ".pom", b"<project/>", "central")
        report, _ = inventory.make_report(self.custody)
        self.assertEqual(len(report["missing_sources"]), 2)
        self.assertFalse(report["source_coverage_complete"])

    def test_acquisition_is_explicit_origin_preserving_and_deduplicated(self):
        for classifier in ("", "-tests", "-linux-x86_64"):
            self.retain(self.base + classifier + ".jar", jar(), "osgeo")
        records = inventory.verify_custody(self.custody)["artifacts"]
        calls = []
        def fetch(path, repository):
            calls.append((path, repository))
            if path.endswith(".pom"):
                return self.retain(path, b"<project/>", repository)
            raise RuntimeError("fixture confirmed missing source")
        outcomes = inventory.acquire_sources(self.custody, records, fetch)
        self.assertEqual(calls, [(self.base + ".pom", "osgeo"), (self.base + "-sources.jar", "osgeo")])
        self.assertEqual([x["status"] for x in outcomes], ["retained", "gap"])
        report, _ = inventory.make_report(self.custody, outcomes)
        self.assertEqual(len(report["missing_sources"]), 3)
        self.assertEqual(report["acquisition"][1]["error_type"], "RuntimeError")

    def test_notice_bytes_are_retained_by_hash_without_path_extraction(self):
        data = b"original notice\x00\xff"
        self.retain(self.base + ".jar", jar({"../../NOTICE.txt": data,
            "META-INF/LICENSE-third-party": b"License", "LICENSED.class": b"not a notice"}))
        report, content = inventory.make_report(self.custody)
        output = self.root / "report.json"
        inventory.write_report(output, report, content)
        entries = report["notices"][0]["entries"]
        self.assertEqual(len(entries), 2)
        selected = next(x for x in entries if x["entry"] == "../../NOTICE.txt")
        self.assertEqual((self.root / selected["retained_path"]).read_bytes(), data)
        self.assertEqual(selected["sha256"], hashlib.sha256(data).hexdigest())
        self.assertFalse((self.root / "NOTICE.txt").exists())
        self.assertFalse(report["license_approval"])

    def test_notice_size_bound_is_explicit_and_not_silent(self):
        self.retain(self.base + "-sources.jar", jar({"NOTICE": b"long notice"}))
        with patch.object(inventory, "_MAX_NOTICE", 2):
            report, content = inventory.make_report(self.custody)
        self.assertEqual(content, {})
        self.assertIn("size bound", report["notices"][0]["inspection_errors"][0])

    def test_invalid_source_zip_and_pom_are_explicit_gaps(self):
        self.retain(self.base + ".jar", jar())
        self.retain(self.base + "-sources.jar", b"not zip")
        self.retain(self.base + ".pom", b"<broken")
        report, _ = inventory.make_report(self.custody)
        self.assertTrue(report["verification"]["valid"])
        self.assertFalse(report["source_coverage_complete"])
        self.assertEqual(len(report["missing_sources"]), 2)
        self.assertIn("error", report["pom_licenses"][0])

    def test_pom_entities_and_non_project_xml_are_not_interpreted(self):
        for data in (b'<!DOCTYPE project [<!ENTITY x "value">]><project/>', b"<html/>"):
            parsed = inventory.pom_licenses(data)
            self.assertIn("error", parsed)
            self.assertEqual(parsed["declarations"], [])

    def test_reports_never_overwrite_existing_output_or_notice_directory(self):
        self.complete_gav()
        report, contents = inventory.make_report(self.custody)
        output = self.root / "report.json"
        output.write_text("preserve")
        with self.assertRaises(inventory.InventoryError):
            inventory.write_report(output, report, contents)
        self.assertEqual(output.read_text(), "preserve")
        output.unlink()
        (self.root / "report.notices").mkdir()
        with self.assertRaises(inventory.InventoryError):
            inventory.write_report(output, report, contents)

    def test_default_cli_does_not_fetch_or_modify_custody(self):
        self.retain(self.base + ".jar", jar())
        before = {p.relative_to(self.custody): p.read_bytes() for p in self.custody.rglob("*") if p.is_file()}
        with patch.object(inventory, "acquire_sources", side_effect=AssertionError("network forbidden")), contextlib.redirect_stdout(io.StringIO()):
            code = inventory.main(["--custody", str(self.custody), "--output", str(self.root / "report.json")])
        after = {p.relative_to(self.custody): p.read_bytes() for p in self.custody.rglob("*") if p.is_file()}
        self.assertEqual(code, 2)
        self.assertEqual(before, after)

    def test_corrupt_custody_does_not_acquire_sources(self):
        self.retain(self.base + ".jar", jar(), size=999)
        with patch.object(inventory, "acquire_sources", side_effect=AssertionError("network forbidden")), contextlib.redirect_stdout(io.StringIO()):
            code = inventory.main(["--custody", str(self.custody), "--output", str(self.root / "report.json"), "--acquire-sources"])
        self.assertEqual(code, 1)

    def schema_capsule(self):
        import schema_resources
        path = "org/geotools/schemas/xlink-1.0/1.0.0-3/xlink-1.0-1.0.0-3.jar"
        data = jar({"net/opengis/schemas/xlink/1.0.0/xlinks.xsd":
                    b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>'})
        validation = schema_resources.validate_schema_archive(path, data)
        artifact = self.retain(path, data, "osgeo", source_resource_validation=validation)
        self.retain(path[:-4] + ".pom", b'<project><groupId>org.geotools.schemas</groupId><artifactId>xlink-1.0</artifactId><version>1.0.0-3</version></project>', "osgeo")
        return path, data, artifact

    def test_validated_schema_capsule_is_own_source_with_explicit_notice_gaps(self):
        path, data, artifact = self.schema_capsule()
        report, _ = inventory.make_report(self.custody)
        self.assertTrue(report["verification"]["valid"])
        self.assertTrue(report["source_coverage_complete"])
        self.assertEqual(report["source_coverage"][0]["sources_path"], path)
        self.assertEqual(report["source_coverage"][0]["sources"]["status"], "retained-source-resource-candidate")
        self.assertEqual(len(report["license_notice_gaps"]), 2)
        self.assertFalse(report["build_ready"])
        self.assertFalse(report["source_binary_correspondence_established"])
        calls = []
        def fetch(requested, repository):
            calls.append((requested, repository))
            return artifact
        inventory.acquire_sources(self.custody, report["artifacts"], fetch)
        self.assertEqual(calls, [(path[:-4] + ".pom", "osgeo")])

    def test_partial_schema_capsule_cannot_count_as_complete_sources(self):
        import schema_resources
        path = "org/geotools/schemas/cgiutilities-1.0/1.0.0-4/cgiutilities-1.0-1.0.0-4.jar"
        data = jar({"org/geosciml/www/cgiutilities/1.0/xsd/cgiUtilities.xsd":
                    b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>'})
        with self.assertRaises(ValueError):
            schema_resources.validate_schema_archive(path, data)
        self.retain(path, data, "osgeo", source_resource_validation={})
        self.retain(path[:-4] + ".pom", b"<project/>", "osgeo")
        report, _ = inventory.make_report(self.custody)
        self.assertFalse(report["verification"]["valid"])
        self.assertFalse(report["source_coverage_complete"])
        self.assertEqual(report["source_coverage"], [])

    def test_schema_validation_manifest_must_match_actual_capsule(self):
        path, data, artifact = self.schema_capsule()
        record = json.loads(artifact.record_file.read_text())
        record["source_resource_validation"]["resource_count"] += 1
        artifact.record_file.write_text(json.dumps(record))
        report, _ = inventory.make_report(self.custody)
        self.assertFalse(report["verification"]["valid"])
        self.assertEqual(report["source_coverage"], [])
        self.assertIn("validation differs", report["verification"]["errors"][0]["error"])

    def test_malformed_or_executable_schema_capsules_never_count_as_sources(self):
        path, original, artifact = self.schema_capsule()
        valid_manifest = artifact.record["source_resource_validation"]
        for data in (b"not an archive", jar({"net/opengis/schemas/xlink/1.0.0/xlinks.xsd":
                b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>',
                "Hidden.class": b"unexpected executable"})):
            self.retain(path, data, "osgeo", source_resource_validation=valid_manifest)
            report, _ = inventory.make_report(self.custody)
            self.assertFalse(report["verification"]["valid"])
            self.assertFalse(report["source_coverage_complete"])
            self.assertEqual(report["source_coverage"], [])

    def test_schema_checksum_requires_same_origin_archive_and_validated_bytes(self):
        path, data, artifact = self.schema_capsule()
        checksum = hashlib.sha1(data).hexdigest()
        details = {"schema_version": 1, "source_archive_path": path,
                   "source_archive_sha256": hashlib.sha256(data).hexdigest(),
                   "checksum_algorithm": "sha1", "checksum": checksum}
        sidecar = self.retain(path + ".sha1", checksum.encode(), "osgeo", source_resource_validation=details)
        self.assertTrue(inventory.verify_custody(self.custody)["verification"]["valid"])
        self.retain(path + ".sha1", b"0" * 40, "osgeo", source_resource_validation=details)
        self.assertFalse(inventory.verify_custody(self.custody)["verification"]["valid"])
        sidecar.record_file.unlink()
        self.retain(path + ".sha1", checksum.encode(), "central", source_resource_validation=details)
        report = inventory.verify_custody(self.custody)
        self.assertFalse(report["verification"]["valid"])
        self.assertIn("same-origin", report["verification"]["errors"][0]["error"])

    def test_schema_checksum_grammar_matches_proxy_replay_policy(self):
        path, data, artifact = self.schema_capsule()
        checksum = hashlib.sha1(data).hexdigest()
        details = {"schema_version": 1, "source_archive_path": path,
                   "source_archive_sha256": hashlib.sha256(data).hexdigest(),
                   "checksum_algorithm": "sha1", "checksum": checksum}
        filename = path.rsplit("/", 1)[-1]
        for body in (checksum, checksum.upper(), checksum + " *" + filename):
            self.retain(path + ".sha1", body.encode(), "osgeo", source_resource_validation=details)
            self.assertTrue(inventory.verify_custody(self.custody)["verification"]["valid"])
        for body in (checksum + " other.jar", checksum + " " + filename + " extra"):
            self.retain(path + ".sha1", body.encode(), "osgeo", source_resource_validation=details)
            report = inventory.verify_custody(self.custody)
            self.assertFalse(report["verification"]["valid"])
            self.assertIn("checksum bytes disagree", report["verification"]["errors"][0]["error"])

    def test_forged_resource_verified_flag_cannot_skip_source_acquisition(self):
        self.retain(self.base + ".jar", jar(), source_resource_verified=True,
                    source_resource_validation={"notices": []})
        report, _ = inventory.make_report(self.custody)
        self.assertFalse(report["verification"]["valid"])
        self.assertEqual(report["source_coverage"], [])
        self.assertIn("derived", report["verification"]["errors"][0]["error"])

    def test_schema_capsule_cannot_skip_recorded_content_validation(self):
        path, data, artifact = self.schema_capsule()
        record = json.loads(artifact.record_file.read_text())
        del record["source_resource_validation"]
        artifact.record_file.write_text(json.dumps(record))
        self.assertFalse(inventory.verify_custody(self.custody)["verification"]["valid"])

    def test_unknown_jar_coordinate_is_a_gap(self):
        self.retain("org/example/tool/1.2/different.jar", jar())
        report, _ = inventory.make_report(self.custody)
        self.assertFalse(report["source_coverage_complete"])
        self.assertIn("filename", report["missing_sources"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
