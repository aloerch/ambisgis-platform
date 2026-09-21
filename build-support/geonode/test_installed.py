"""Tamper controls on installed owned artifacts; not GIS acceptance tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from installed import digest, verify


class InstalledTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.python = self.root / 'venv/bin/python'
        self.python.parent.mkdir(parents=True)
        self.site = self.root / 'site'
        self.site.mkdir()
        self.wheel = self.root / 'owned.whl'
        with zipfile.ZipFile(self.wheel, 'w') as archive:
            for package in ('geonode', 'geonode_mapstore_client'):
                folder = self.site / package
                folder.mkdir()
                (folder / '__init__.py').write_text('# source-owned\n')
                archive.writestr(package + '/__init__.py', '# source-owned\n')
        (self.root / 'build-receipt.json').write_text(json.dumps({'python': str(self.python), 'pip_check': 'passed', 'imports': 'passed', 'owned_wheels': [{'path': str(self.wheel), 'sha256': digest(self.wheel)}]}))
        self.subprocess = patch('installed.subprocess.check_output', return_value=str(self.site) + '\n')
        self.subprocess.start()
        self.addCleanup(self.subprocess.stop)

    def test_verified_unchanged_installed_bytes(self):
        self.assertEqual(verify(self.python)['verified_owned_files'], 2)

    def test_changed_installed_module_fails(self):
        (self.site / 'geonode/__init__.py').write_text('# modified\n')
        with self.assertRaisesRegex(ValueError, 'differs'): verify(self.python)

    def test_extra_native_shadow_module_fails(self):
        (self.site / 'geonode/__init__.so').write_bytes(b'unrecorded import executable')
        with self.assertRaisesRegex(ValueError, 'unrecorded'): verify(self.python)

    def test_symlink_directory_fails(self):
        (self.site / 'geonode/extra').symlink_to(self.site / 'geonode_mapstore_client', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): verify(self.python)


if __name__ == '__main__': unittest.main()
