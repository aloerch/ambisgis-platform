"""Offline regressions for custody corruption and unsafe recovery inputs."""
import copy
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import toolchain


class ToolchainCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "custody"
        self.root.mkdir()
        self.write_archive("tool/bin/tool", b"test binary")

    def write_archive(self, name, payload, link=None):
        path = self.root / "tool.tar.gz"
        with tarfile.open(path, "w:gz") as stream:
            item = tarfile.TarInfo(name)
            if link is None:
                item.size = len(payload)
                item.mode = 0o755
                stream.addfile(item, io.BytesIO(payload))
            else:
                item.type = tarfile.SYMTYPE
                item.linkname = link
                stream.addfile(item)
        (self.root / "tool.sha256").write_text(toolchain.digest(path))
        rows = []
        for source in sorted(self.root.iterdir()):
            rows.append({"path": source.name, "bytes": source.stat().st_size,
                         "sha256": toolchain.digest(source)})
        self.manifest = {"schema_version": 1, "files": rows, "archives": [
            {"path": "tool.tar.gz", "root": "tool", "role": "distribution",
             "publisher_checksum": "tool.sha256", "algorithm": "sha256"}]}

    def test_verify_and_safe_reextract(self):
        result = toolchain.verify(self.root, self.manifest)
        self.assertTrue(result["verified"])
        self.assertFalse(result["toolchain_rebuild_closure_complete"])
        destination = self.base / "fresh"
        toolchain.extract(self.root, self.manifest, destination)
        self.assertEqual((destination / "tool/bin/tool").read_bytes(), b"test binary")
        with self.assertRaisesRegex(toolchain.CustodyError, "already exist"):
            toolchain.extract(self.root, self.manifest, destination)

    def test_repeated_directory_entries_are_safe(self):
        archive = self.root / "tool.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            for _ in range(2):
                directory = tarfile.TarInfo("tool/lib")
                directory.type = tarfile.DIRTYPE
                stream.addfile(directory)
        (self.root / "tool.sha256").write_text(toolchain.digest(archive))
        for row in self.manifest["files"]:
            path = self.root / row["path"]
            row.update(bytes=path.stat().st_size, sha256=toolchain.digest(path))
        destination = self.base / "repeated-directory"
        toolchain.extract(self.root, self.manifest, destination)
        self.assertTrue((destination / "tool/lib").is_dir())

    def test_corrupted_archive_refused_before_extraction(self):
        (self.root / "tool.tar.gz").write_bytes(b"corrupt")
        destination = self.base / "fresh"
        with self.assertRaisesRegex(toolchain.CustodyError, "changed retained"):
            toolchain.extract(self.root, self.manifest, destination)
        self.assertFalse(destination.exists())

    def test_missing_input_reported(self):
        (self.root / "tool.tar.gz").unlink()
        with self.assertRaisesRegex(toolchain.CustodyError, "missing/nonregular"):
            toolchain.verify(self.root, self.manifest)

    def test_extra_input_refused(self):
        (self.root / "unrecorded.jar").write_bytes(b"input")
        with self.assertRaisesRegex(toolchain.CustodyError, "unrecorded"):
            toolchain.verify(self.root, self.manifest)

    def test_symlink_substitution_refused(self):
        original = self.root / "tool.tar.gz"
        moved = self.base / "outside"
        original.rename(moved)
        original.symlink_to(moved)
        with self.assertRaisesRegex(toolchain.CustodyError, "missing/nonregular"):
            toolchain.verify(self.root, self.manifest)

    def test_path_and_duplicate_manifest_entries_refused(self):
        for path in ("../outside", "/outside", "folder/name", "..", "a\\b"):
            manifest = copy.deepcopy(self.manifest)
            manifest["files"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(toolchain.CustodyError):
                toolchain.entries(manifest)
        manifest = copy.deepcopy(self.manifest)
        manifest["files"].append(manifest["files"][0])
        with self.assertRaisesRegex(toolchain.CustodyError, "duplicate"):
            toolchain.entries(manifest)

    def test_archive_paths_must_be_locked(self):
        self.manifest["archives"][0]["path"] = "../outside"
        with self.assertRaisesRegex(toolchain.CustodyError, "absent from retained"):
            toolchain.entries(self.manifest)

    def test_publisher_checksum_independently_checked(self):
        checksum = self.root / "tool.sha256"
        checksum.write_text("0" * 64)
        row = next(r for r in self.manifest["files"] if r["path"] == checksum.name)
        row["sha256"] = toolchain.digest(checksum)
        with self.assertRaisesRegex(toolchain.CustodyError, "publisher checksum mismatch"):
            toolchain.verify(self.root, self.manifest)

    def test_fixed_https_urls_required(self):
        for url in ("http://github.com/a", "https://github.com/a/latest/b", "https://other.invalid/a", "https://token@github.com/a", "https://github.com/a?token=x"):
            manifest = copy.deepcopy(self.manifest)
            manifest["files"][0]["acquire_url"] = url
            with self.subTest(url=url), self.assertRaises(toolchain.CustodyError):
                toolchain.entries(manifest)

    def test_changed_file_stops_acquisition_before_network(self):
        (self.root / "tool.tar.gz").write_bytes(b"corrupt")
        with patch.object(toolchain, "urlopen") as request:
            with self.assertRaisesRegex(toolchain.CustodyError, "changed retained"):
                toolchain.acquire(self.root, self.manifest)
            request.assert_not_called()

    def test_tar_traversal_and_external_link_refused(self):
        self.write_archive("tool/../../outside", b"escape")
        with self.assertRaises(toolchain.CustodyError):
            toolchain.extract(self.root, self.manifest, self.base / "traversal")
        self.assertFalse((self.base / "outside").exists())
        self.write_archive("tool/link", b"", link="../../outside")
        with self.assertRaises(tarfile.FilterError):
            toolchain.extract(self.root, self.manifest, self.base / "link")
        self.assertFalse((self.base / "outside").exists())


if __name__ == "__main__":
    unittest.main()
