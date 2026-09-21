"""Guards for the bounded IFC source stage; no fabricated build acceptance."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import webifc_sources as subject


class SourceGuards(unittest.TestCase):
    def archive(self, rows):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as archive:
            for name, kind, data in rows:
                info = tarfile.TarInfo(name)
                info.type = kind
                if kind == tarfile.REGTYPE:
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
                else:
                    info.linkname = "/outside"
                    archive.addfile(info)
        return output.getvalue()

    def test_regular_archive(self):
        self.assertEqual(subject.archive_files(self.archive([("root/a", tarfile.REGTYPE, b"source")])), {"a": b"source"})

    def test_archive_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsafe"):
            subject.archive_files(self.archive([("root/../escape", tarfile.REGTYPE, b"bad")]))

    def test_archive_links_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "special"):
                subject.archive_files(self.archive([("root/link", kind, b"")]))

    def test_duplicate_members_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            subject.archive_files(self.archive([("root/a", tarfile.REGTYPE, b"one"), ("root/a", tarfile.REGTYPE, b"two")]))

    def test_cmake_comments_not_selected(self):
        lines = [f'FetchContent_Declare(dep{i} GIT_REPOSITORY "https://github.com/a/b" GIT_TAG "{i:040x}")' for i in range(8)]
        text = "\n".join(lines + ["# " + lines[0]])
        self.assertEqual(len(subject.cmake_pins(text)), 8)
        with self.assertRaisesRegex(ValueError, "eight distinct"):
            subject.cmake_pins("\n".join(lines + [lines[0]]))

    def test_dependency_revision_tamper(self):
        rows = [{"name": f"dep{i}", "repository": "https://github.com/a/b", "revision": f"{i:040x}"} for i in range(8)]
        cmake = "\n".join(f'FetchContent_Declare({r["name"]} GIT_REPOSITORY "{r["repository"]}" GIT_TAG "{r["revision"]}")' for r in rows)
        subject.verify_pins(cmake, rows)
        rows[0]["revision"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "lock mismatch"):
            subject.verify_pins(cmake, rows)

    def test_frontend_tamper_and_extra_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api.js").write_bytes(b"exact")
            subject.verify_package_assets(root, {"api.js": b"exact"})
            with self.assertRaisesRegex(ValueError, "bytes changed"):
                subject.verify_package_assets(root, {"api.js": b"other"})
            (root / "extra").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "membership"):
                subject.verify_package_assets(root, {"api.js": b"exact"})

    def test_wasm_binding_tamper(self):
        names = [f"binding_{i}" for i in range(35)]
        cpp = "\n".join(f'emscripten::function("{name}", &{name});' for name in names)
        data = b"\0asm\1\0\0\0" + b"".join(n.encode() + b"\0" for n in names)
        wasm = {f"file{i}.wasm": data for i in range(3)}
        self.assertEqual(subject.verify_wasm_bindings(cpp, wasm), names)
        wasm["file1.wasm"] = data.replace(b"binding_34", b"missing_34")
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            subject.verify_wasm_bindings(cpp, wasm)

    def test_publisher_blob_and_membership(self):
        data = b"source"
        blob = hashlib.sha1(b"blob 6\0" + data).hexdigest()
        tree = {"truncated": False, "tree": [{"type": "blob", "path": "a", "sha": blob}]}
        subject.verify_tree({"a": data}, tree)
        with self.assertRaisesRegex(ValueError, "blob mismatch"):
            subject.verify_tree({"a": b"changed"}, tree)
        with self.assertRaisesRegex(ValueError, "membership"):
            subject.verify_tree({"a": data, "extra": b"x"}, tree)

    def test_truncated_tree_and_gitlink_rejected(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            subject.verify_tree({}, {"truncated": True})
        with self.assertRaisesRegex(ValueError, "gitlink"):
            subject.verify_tree({}, {"truncated": False, "tree": [{"type": "commit"}]})

    def test_changed_retained_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = root / "a"
            p.write_bytes(b"source")
            row = subject.file_record(p, root)
            subject.verified_file(root, row)
            p.write_bytes(b"tamper")
            with self.assertRaisesRegex(ValueError, "changed"):
                subject.verified_file(root, row)

    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = root / "a"
            p.write_bytes(b"source")
            row = subject.file_record(p, root)
            (root / "link").symlink_to(p)
            row["path"] = "link"
            with self.assertRaisesRegex(ValueError, "symlink"):
                subject.verified_file(root, row)

    def test_existing_stage_is_untouched_on_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "sentinel"
            sentinel.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "fresh stage"):
                subject.prepare(root / "absent", root, root / "absent")
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            self.assertEqual(list(root.iterdir()), [sentinel])


if __name__ == "__main__":
    unittest.main()
