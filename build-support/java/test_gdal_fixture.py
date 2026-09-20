"""Check retained native archive handling before exposing binaries to Java tests."""
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import gdal_fixture
from resolution import sha


class GdalFixtureTests(unittest.TestCase):
    def inputs(self, root):
        prefix = root / 'prefix'
        (prefix / 'bin').mkdir(parents=True)
        (prefix / 'bin/gdal_translate').write_bytes(b'fixture executable')
        os.link(prefix / 'bin/gdal_translate', prefix / 'bin/gdaladdo')
        (prefix / 'bin/gdalwarp').write_bytes(b'separate fixture executable')
        archive = root / 'prefix.tar.gz'
        with tarfile.open(archive, 'w:gz') as tf:
            tf.add(prefix, arcname='prefix')
        output = root / 'output'
        output.mkdir()
        return prefix, archive, output, {'output_archive': {'sha256': sha(archive)}}

    def test_verified_hardlinks_preserve_all_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix, archive, output, expected = self.inputs(Path(tmp))
            with patch('gdal_fixture.json.loads', return_value=expected):
                report = gdal_fixture.prepare(prefix, archive, output)
            self.assertEqual(len(report['verified_files']), 3)
            self.assertEqual(len(report['staged_binaries']), 3)
            self.assertEqual((output / 'native-bin/gdaladdo').read_bytes(), b'fixture executable')

    def test_changed_installed_binary_refused_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix, archive, output, expected = self.inputs(Path(tmp))
            (prefix / 'bin/gdalwarp').write_bytes(b'changed')
            with patch('gdal_fixture.json.loads', return_value=expected), self.assertRaisesRegex(ValueError, 'differs'):
                gdal_fixture.prepare(prefix, archive, output)
            self.assertFalse((output / 'native-bin').exists())

    def test_changed_archive_refused_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix, archive, output, expected = self.inputs(Path(tmp))
            with archive.open('ab') as stream:
                stream.write(b'changed')
            with patch('gdal_fixture.json.loads', return_value=expected), self.assertRaisesRegex(ValueError, 'does not match'):
                gdal_fixture.prepare(prefix, archive, output)
            self.assertFalse((output / 'native-bin').exists())


if __name__ == '__main__':
    unittest.main()
