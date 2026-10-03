"""Inert lifecycle-helper boundary checks, not installation/GIS acceptance."""
import json
from pathlib import Path
import sys
import unittest

import lifecycle_check as lifecycle
sys.path.insert(0, str(lifecycle.ROOT / 'plan/tests'))
import test_development_installer as installer_fixture
from installer.state import InstallError


class LifecycleBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = installer_fixture.InstallerStateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        f = self.fixture
        (f.inputs / 'bin/ambisgis').write_bytes(b'inert CLI fixture; must never execute\n')
        (f.inputs / 'bin/ambisgis').chmod(0o700)
        closure = json.loads((f.inputs / 'closure.json').read_bytes())
        closure['files'].append(f.ref('bin/ambisgis'))
        f.put('closure.json', closure)
        f.document['runtime']['files_manifest'] = f.ref('closure.json')
        f.seal()

    def test_relocation_preserves_verified_inputs_and_excludes_unselected_neighbor(self):
        f = self.fixture
        (f.inputs / 'unselected-executable').write_bytes(b'must not enter bundle')
        before = {str(p.relative_to(f.inputs)): p.read_bytes() for p in f.inputs.rglob('*') if p.is_file()}
        manifest, launcher = lifecycle.relocate(f.manifest, f.identity, f.base / 'relocated')
        self.assertEqual(launcher.read_bytes(), (f.inputs / 'bin/ambisgis').read_bytes())
        self.assertEqual(manifest.read_bytes(), f.manifest.read_bytes())
        self.assertFalse((manifest.parent / 'unselected-executable').exists())
        after = {str(p.relative_to(f.inputs)): p.read_bytes() for p in f.inputs.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(lifecycle.bundle.load(manifest, f.identity), f.document)

    def test_unlisted_runtime_code_rejected_before_any_destination_is_created(self):
        f = self.fixture
        (f.inputs / 'bin/unreviewed').write_bytes(b'not selected')
        with self.assertRaises(InstallError):
            lifecycle.relocate(f.manifest, f.identity, f.base / 'relocated')
        self.assertFalse((f.base / 'relocated').exists())

    def test_existing_destination_keeps_sentinel_and_is_never_replaced(self):
        f = self.fixture
        destination = f.base / 'relocated'; destination.mkdir()
        (destination / 'keep').write_bytes(b'preserved')
        with self.assertRaises(FileExistsError):
            lifecycle.relocate(f.manifest, f.identity, destination)
        self.assertEqual(list(destination.iterdir()), [destination / 'keep'])
        self.assertEqual((destination / 'keep').read_bytes(), b'preserved')

    def test_existing_installation_is_rejected_without_creating_evidence(self):
        from argparse import Namespace
        f = self.fixture; f.root.mkdir(); (f.root / 'data').write_bytes(b'preserved')
        with self.assertRaises(ValueError):
            lifecycle.main(Namespace(directory=f.root, output=f.base / 'evidence', bundle=f.manifest, bundle_sha256=f.identity))
        self.assertFalse((f.base / 'evidence').exists())
        self.assertEqual((f.root / 'data').read_bytes(), b'preserved')

    def test_receipt_secret_scan_prevents_write(self):
        f = self.fixture; output = f.base / 'evidence'; output.mkdir()
        check = lifecycle.Check(f.root, output)
        check.secrets = ['synthetic-secret-only-for-test']
        check.record['unsafe'] = 'synthetic-secret-only-for-test'
        with self.assertRaises(RuntimeError):
            check.save()
        self.assertFalse((output / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
