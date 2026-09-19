"""Offline regression tests for source custody, corruption and archive boundaries."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


RECIPE = Path(__file__).resolve().parents[2] / "build-support/postgis/acquisition.py"
spec = importlib.util.spec_from_file_location("postgis_acquisition", RECIPE)
acquisition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquisition)


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.custody = self.root / "custody"
        self.custody.mkdir()

    def archive(self, extras=()):
        path = self.custody / "source.tar"
        with tarfile.open(path, "w") as archive:
            for name, content in (("source/LICENSE", b"original license\n"), ("source/configure", b"#!/bin/sh\n")):
                entry = tarfile.TarInfo(name)
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            for entry, content in extras:
                archive.addfile(entry, io.BytesIO(content) if content else None)
        return {"name": "sample", "version": "1", "artifact": path.name,
                "archive_root": "source", "bytes": path.stat().st_size,
                "sha256": acquisition.sha256(path), "source_url": "https://example.invalid/source.tar",
                "license_evidence": [{"original_path": "LICENSE", "retained_path": "licenses/sample/LICENSE",
                                      "sha256": hashlib.sha256(b"original license\n").hexdigest()}]}

    def test_manifest_rejects_unsafe_names_duplicates_and_non_https(self):
        item = self.archive()
        path = self.root / "inputs.json"
        mutations = [{"artifact": "../outside"}, {"archive_root": "/outside"},
                     {"source_url": "http://example.invalid/source.tar"}, {"sha256": "a"},
                     {"bytes": 0}, {"owned_repository": "unrelated"}]
        for change in mutations:
            with self.subTest(change=change):
                path.write_text(json.dumps({"schema_version": 1, "inputs": [item | change]}))
                with self.assertRaises(ValueError):
                    acquisition.load_manifest(path)
        path.write_text(json.dumps({"schema_version": 1, "inputs": [item, item]}))
        with self.assertRaises(ValueError):
            acquisition.load_manifest(path)

    def test_verify_is_read_only_and_detects_archive_and_license_corruption(self):
        item = self.archive()
        acquisition.retain_licenses(self.custody, item)
        before = {p.relative_to(self.custody): p.read_bytes() for p in self.custody.rglob("*") if p.is_file()}
        with patch.object(acquisition.urllib.request, "build_opener", side_effect=AssertionError("unexpected network")):
            acquisition.verify_input(self.custody, item)
        after = {p.relative_to(self.custody): p.read_bytes() for p in self.custody.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        license_path = self.custody / item["license_evidence"][0]["retained_path"]
        license_path.write_bytes(b"modified license\n")
        with self.assertRaisesRegex(ValueError, "license evidence hash"):
            acquisition.verify_input(self.custody, item)
        path = self.custody / item["artifact"]
        path.write_bytes(b"bad archive")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            acquisition.verify_artifact(path, item)

    def test_existing_corrupt_archive_is_never_replaced_or_fetched(self):
        item = self.archive()
        path = self.custody / item["artifact"]
        path.write_bytes(b"preserve this evidence")
        with patch.object(acquisition.urllib.request, "build_opener", side_effect=AssertionError("unexpected network")):
            with self.assertRaises(ValueError):
                acquisition.fetch_input(self.custody, item)
        self.assertEqual(path.read_bytes(), b"preserve this evidence")

    def test_extract_keeps_internal_symlink_and_refuses_reuse(self):
        link = tarfile.TarInfo("source/test-link")
        link.type = tarfile.SYMTYPE
        link.linkname = "LICENSE"
        item = self.archive([(link, None)])
        path = acquisition.extract_input(self.custody, self.root / "extract", item)
        self.assertEqual((path / "test-link").read_bytes(), b"original license\n")
        (path / "configure").write_bytes(b"existing work")
        with self.assertRaises(FileExistsError):
            acquisition.extract_input(self.custody, self.root / "extract", item)
        self.assertEqual((path / "configure").read_bytes(), b"existing work")

    def test_extract_rejects_traversal_wrong_root_devices_duplicates_and_escaping_links(self):
        for name, kind, linkname in (("../escape", tarfile.REGTYPE, ""),
                                     ("different/LICENSE", tarfile.REGTYPE, ""),
                                     ("source/fifo", tarfile.FIFOTYPE, ""),
                                     ("source/LICENSE", tarfile.REGTYPE, ""),
                                     ("source/link", tarfile.SYMTYPE, "../../escape"),
                                     ("source/link", tarfile.SYMTYPE, "../escape"),
                                     ("source/hardlink", tarfile.LNKTYPE, "outside")):
            with self.subTest(name=name, kind=kind):
                entry = tarfile.TarInfo(name)
                entry.type = kind
                entry.linkname = linkname
                item = self.archive([(entry, None)])
                with self.assertRaises((ValueError, tarfile.FilterError)):
                    acquisition.extract_input(self.custody, self.root / "extract", item)
                self.assertFalse((self.root / "extract/source").exists())
                self.assertFalse((self.root / "escape").exists())

    def test_license_retention_rejects_escape_through_existing_directory_link(self):
        item = self.archive()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (self.custody / "licenses").symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes custody"):
            acquisition.retain_licenses(self.custody, item)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_failed_download_never_installs_partial_input(self):
        item = self.archive()
        (self.custody / item["artifact"]).unlink()
        response = io.BytesIO(b"truncated download")
        response.geturl = lambda: item["source_url"]
        class Opener:
            def open(self, *args, **kwargs):
                return response
        with patch.object(acquisition.urllib.request, "build_opener", return_value=Opener()):
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                acquisition.fetch_input(self.custody, item)
        self.assertEqual(list(self.custody.iterdir()), [])

    def test_repository_manifest_is_valid_and_has_owned_earlier_upgrade_fixture(self):
        manifest = acquisition.load_manifest(RECIPE.with_name("inputs.json"))
        inputs = {item["name"]: item for item in manifest["inputs"]}
        self.assertEqual(inputs["postgis"]["version"], "3.5.7")
        self.assertEqual(inputs["postgis-upgrade"]["version"], "3.5.6")
        self.assertNotEqual(inputs["postgis"]["commit"], inputs["postgis-upgrade"]["commit"])
        for name in ("geos", "proj", "gdal", "protobuf-c", "json-c", "cunit"):
            self.assertTrue(inputs[name]["license_evidence"])


if __name__ == "__main__":
    unittest.main()
