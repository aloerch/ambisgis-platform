import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "build-support/qgis/acquisition.py"
spec = importlib.util.spec_from_file_location("qgis_acquisition", SCRIPT)
acq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acq)


def archive(entries):
    out = bytearray()
    for inode, (name, mode, payload) in enumerate(entries + [("TRAILER!!!", 0, b"")], 1):
        name = name.encode() + b"\0"
        values = [inode, mode, 0, 0, 1, 0, len(payload), 0, 0, 0, 0, len(name), 0]
        out += b"070701" + b"".join(f"{v:08x}".encode() for v in values)
        out += name
        out += b"\0" * (-len(out) % 4)
        out += payload
        out += b"\0" * (-len(out) % 4)
    return bytes(out)


class AcquisitionGuards(unittest.TestCase):
    def test_extract_regular_file_preserves_executable_and_removes_special_bits(self):
        with tempfile.TemporaryDirectory() as tmp:
            acq.extract_cpio(archive([("usr/bin/tool", stat.S_IFREG | 0o4755, b"retained")]), tmp)
            path = Path(tmp) / "usr/bin/tool"
            self.assertEqual(path.read_bytes(), b"retained")
            self.assertEqual(path.stat().st_mode & 0o7777, 0o755)

    def test_rejects_path_traversal_and_absolute_paths(self):
        for name in ("../escape", "/usr/bin/escape", "usr/../../escape"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    acq.extract_cpio(archive([(name, stat.S_IFREG | 0o644, b"bad")]), tmp)

    def test_rejects_unknown_absolute_or_escaping_symlink(self):
        for target in (b"/etc/passwd", b"../../../outside"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    acq.extract_cpio(archive([("usr/bin/link", stat.S_IFLNK | 0o777, target)]), tmp)

    def test_retargets_only_reviewed_alternative_privately(self):
        with tempfile.TemporaryDirectory() as tmp:
            acq.extract_cpio(archive([("usr/bin/pyuic5", stat.S_IFLNK | 0o777, b"/etc/alternatives/pyuic5")]), tmp)
            self.assertEqual(os.readlink(Path(tmp)/"usr/bin/pyuic5"), "pyuic5-3.13")

    def test_rejects_write_through_symlink_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [("usr/alias",stat.S_IFLNK|0o777,b"real"),("usr/alias/data",stat.S_IFREG|0o644,b"bad")]
            with self.assertRaisesRegex(ValueError, "Symlink ancestor"):
                acq.extract_cpio(archive(entries), tmp)

    def test_nonidentical_collision_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [("usr/file",stat.S_IFREG|0o644,b"one"),("usr/file",stat.S_IFREG|0o644,b"two")]
            with self.assertRaisesRegex(ValueError, "collision"):
                acq.extract_cpio(archive(entries), tmp)

    def test_devices_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "file type"):
                acq.extract_cpio(archive([("dev/device",stat.S_IFCHR|0o666,b"")]), tmp)

    def test_truncated_archive_rejected(self):
        with self.assertRaises(ValueError): list(acq.cpio_entries(archive([])[:50]))

    def test_qgis_binary_package_rejected(self):
        with self.assertRaisesRegex(ValueError, "QGIS"):
            acq.checked_package({"name":"qgis-server"})

    def test_wrong_retained_hash_cannot_extract_or_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/"rpms").mkdir(); (root/"rpms/tool.rpm").write_bytes(b"wrong")
            entry={"name":"support","arch":"x86_64","location":"x86_64/tool.rpm","publisher_digest_algorithm":"sha256","publisher_digest":"0"*64}
            with mock.patch.object(acq.subprocess,"check_output") as run:
                with self.assertRaisesRegex(ValueError,"checksum"):
                    acq.extract({"packages":[entry]},root,root/"fresh")
                run.assert_not_called()

    def test_fresh_prefix_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"fresh"):
                acq.extract({"packages":[]},Path(tmp),Path(tmp))

    def test_existing_retained_file_requires_signature_not_only_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/"rpms").mkdir(); rpm=root/"rpms/tool.rpm"; rpm.write_bytes(b"retained")
            entry={"name":"support","arch":"x86_64","location":"x86_64/tool.rpm","publisher_digest_algorithm":"sha256","publisher_digest":acq.digest(rpm)}
            with mock.patch.object(acq.subprocess,"run", return_value=mock.Mock(returncode=0, stdout="digests OK")):
                with self.assertRaisesRegex(ValueError,"signature"):
                    acq.fetch_one(entry,root,"https://download.opensuse.org/tumbleweed/repo/oss")

    def test_existing_retained_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/"rpms").mkdir(); (root/"outside").write_bytes(b"outside")
            (root/"rpms/tool.rpm").symlink_to(root/"outside")
            entry={"name":"support","arch":"x86_64","location":"x86_64/tool.rpm","publisher_digest_algorithm":"sha256","publisher_digest":"0"*64}
            with self.assertRaisesRegex(ValueError,"symlink"):
                acq.fetch_one(entry,root,"https://download.opensuse.org/tumbleweed/repo/oss")

    def test_committed_manifest_has_exact_supported_binary_source_pairs(self):
        manifest=json.loads((SCRIPT.parent/"support-inputs.json").read_text())
        self.assertFalse(manifest["source_packages_unavailable"])
        sources={Path(e["location"]).name for e in manifest["source_packages"]}
        names=[e["name"] for e in manifest["packages"]]
        self.assertEqual(len(names),len(set(names)))
        for entry in manifest["packages"]:
            acq.checked_package(entry)
            self.assertIn(entry["source_rpm"],sources)
            self.assertTrue(entry["version"] and entry["release"])

if __name__ == "__main__": unittest.main()
