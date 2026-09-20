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
        self.assertEqual(toolchain.verify_extracted(self.root, self.manifest, destination)["files"], 1)
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
        self.assertEqual(toolchain.verify_extracted(self.root, self.manifest, destination)["directories"], 2)

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


    def test_extracted_same_size_change_is_rejected(self):
        destination = self.base / "tools"
        toolchain.extract(self.root, self.manifest, destination)
        (destination / "tool/bin/tool").write_bytes(b"evil binary")
        with self.assertRaisesRegex(toolchain.CustodyError, "changed extracted file"):
            toolchain.verify_extracted(self.root, self.manifest, destination)

    def test_extracted_missing_and_extra_files_are_rejected(self):
        destination = self.base / "tools"
        toolchain.extract(self.root, self.manifest, destination)
        (destination / "tool/bin/tool").unlink()
        with self.assertRaisesRegex(toolchain.CustodyError, "missing="):
            toolchain.verify_extracted(self.root, self.manifest, destination)
        (destination / "tool/bin/tool").write_bytes(b"test binary")
        (destination / "tool/injected.jar").write_bytes(b"extra")
        with self.assertRaisesRegex(toolchain.CustodyError, "extra="):
            toolchain.verify_extracted(self.root, self.manifest, destination)

    def test_wrong_distribution_root_is_rejected(self):
        destination = self.base / "tools"
        toolchain.extract(self.root, self.manifest, destination)
        (destination / "tool").rename(destination / "other")
        with self.assertRaisesRegex(toolchain.CustodyError, "extracted tree differs"):
            toolchain.verify_extracted(self.root, self.manifest, destination)

    def test_file_replaced_by_external_symlink_is_rejected(self):
        destination = self.base / "tools"
        toolchain.extract(self.root, self.manifest, destination)
        (self.base / "external").write_bytes(b"test binary")
        (destination / "tool/bin/tool").unlink()
        (destination / "tool/bin/tool").symlink_to(self.base / "external")
        with self.assertRaisesRegex(toolchain.CustodyError, "changed extracted file"):
            toolchain.verify_extracted(self.root, self.manifest, destination)

    def test_internal_symlink_and_hardlink_bytes_are_checked(self):
        archive = self.root / "tool.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            member = tarfile.TarInfo("tool/bin/tool")
            member.size = 11
            stream.addfile(member, io.BytesIO(b"test binary"))
            symlink = tarfile.TarInfo("tool/link")
            symlink.type = tarfile.SYMTYPE
            symlink.linkname = "bin/tool"
            stream.addfile(symlink)
            hardlink = tarfile.TarInfo("tool/hardlink")
            hardlink.type = tarfile.LNKTYPE
            hardlink.linkname = "tool/bin/tool"
            stream.addfile(hardlink)
        (self.root / "tool.sha256").write_text(toolchain.digest(archive))
        for row in self.manifest["files"]:
            path = self.root / row["path"]
            row.update(bytes=path.stat().st_size, sha256=toolchain.digest(path))
        destination = self.base / "tools"
        toolchain.extract(self.root, self.manifest, destination)
        result = toolchain.verify_extracted(self.root, self.manifest, destination)
        self.assertEqual((result["files"], result["symlinks"]), (2, 1))
        (destination / "tool/link").unlink()
        (destination / "tool/link").symlink_to("hardlink")
        with self.assertRaisesRegex(toolchain.CustodyError, "changed extracted symlink"):
            toolchain.verify_extracted(self.root, self.manifest, destination)

    def test_archive_declared_escape_symlink_is_rejected(self):
        self.write_archive("tool/link", b"", link="../../outside")
        destination = self.base / "tools"
        (destination / "tool").mkdir(parents=True)
        (self.base / "outside").write_bytes(b"outside")
        (destination / "tool/link").symlink_to("../../outside")
        with self.assertRaisesRegex(toolchain.CustodyError, "unsafe/broken extracted symlink"):
            toolchain.verify_extracted(self.root, self.manifest, destination)

    def test_destination_symlink_is_rejected(self):
        destination = self.base / "tools"
        toolchain.extract(self.root, self.manifest, destination)
        alias = self.base / "alias"
        alias.symlink_to(destination)
        with self.assertRaisesRegex(toolchain.CustodyError, "existing real directory"):
            toolchain.verify_extracted(self.root, self.manifest, alias)



if __name__ == "__main__":
    unittest.main()
