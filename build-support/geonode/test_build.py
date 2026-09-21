"""Safety checks for retained inputs and the explicit compatibility patch."""
import json
from pathlib import Path
import tempfile
import tarfile
import unittest

from inputs import PATCHES, patch_project, sha256, verify_manifest, verify_owned_tree


class InputsTests(unittest.TestCase):
    def test_patch_rejects_drift_in_baseline(self):
        source = '\n'.join(before for before, _, _ in PATCHES)
        changed, receipt = patch_project(source)
        self.assertIn('"GDAL==3.10.3"', changed)
        self.assertEqual(len(receipt), 3)
        for altered in [source.replace('3.8.4', '3.8.5'), source + PATCHES[0][0], changed]:
            with self.assertRaises(ValueError):
                patch_project(altered)

    def test_tampered_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'source.tar'
            archive.write_bytes(b'retained source')
            manifest = {'files': [{'path': 'source.tar', 'sha256': sha256(archive)}]}
            verify_manifest(root, manifest)
            archive.write_bytes(b'changed source')
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)

    def test_unrecorded_build_script_edit_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dest = root / 'source'
            dest.mkdir()
            source = dest / 'setup.py'
            source.write_text('original build code')
            archive = root / 'source.tar'
            with tarfile.open(archive, 'w') as tf:
                tf.add(source, arcname='setup.py')
            verify_owned_tree(archive, dest)
            source.write_text('modified build code')
            with self.assertRaises(ValueError):
                verify_owned_tree(archive, dest)

    def test_extra_artifact_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'retained.whl'
            file.write_bytes(b'wheel')
            manifest = {'files': [{'path': file.name, 'sha256': sha256(file)}]}
            extra = root / 'injected.whl'
            extra.write_bytes(b'extra')
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)
            extra.unlink()
            extra.symlink_to(file)
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)

    def test_extra_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dest = root / 'source'
            dest.mkdir()
            source = dest / 'setup.py'
            source.write_text('original')
            archive = root / 'source.tar'
            with tarfile.open(archive, 'w') as tf:
                tf.add(source, arcname='setup.py')
            (dest / 'sitecustomize.py').write_text('unexpected code')
            with self.assertRaises(ValueError):
                verify_owned_tree(archive, dest)

    def test_repair_allowlist_requires_exact_new_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dest = root / 'source'
            dest.mkdir()
            original = dest / 'core.py'
            original.write_text('baseline')
            archive = root / 'source.tar'
            with tarfile.open(archive, 'w') as tf:
                tf.add(original, arcname='core.py')
            added = dest / 'repair.py'
            added.write_text('approved repair')
            allowed = {'repair.py': sha256(added)}
            verify_owned_tree(archive, dest, allowed_changes=allowed)
            added.write_text('changed repair')
            with self.assertRaises(ValueError):
                verify_owned_tree(archive, dest, allowed_changes=allowed)

    def test_manifest_cannot_escape_retained_root(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ['../outside', '/tmp/outside']:
                with self.assertRaises(ValueError):
                    verify_manifest(Path(directory), {'files': [{'path': name, 'sha256': '0' * 64}]})


if __name__ == '__main__':
    unittest.main()
