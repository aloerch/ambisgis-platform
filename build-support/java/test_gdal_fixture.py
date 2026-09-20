"""Check retained native archive handling before exposing binaries to Java tests."""
import os
import shutil
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

    def test_binary_changed_between_verification_and_copy_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix, archive, output, expected = self.inputs(Path(tmp))
            original_copy = shutil.copy2
            def changed_copy(source, destination):
                source.write_bytes(b'changed after archive verification')
                return original_copy(source, destination)
            with patch('gdal_fixture.json.loads', return_value=expected), \
                 patch('gdal_fixture.shutil.copy2', side_effect=changed_copy), \
                 self.assertRaisesRegex(ValueError, 'staged GDAL binary changed'):
                gdal_fixture.prepare(prefix, archive, output)

    def test_changed_archive_refused_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix, archive, output, expected = self.inputs(Path(tmp))
            with archive.open('ab') as stream:
                stream.write(b'changed')
            with patch('gdal_fixture.json.loads', return_value=expected), self.assertRaisesRegex(ValueError, 'does not match'):
                gdal_fixture.prepare(prefix, archive, output)
            self.assertFalse((output / 'native-bin').exists())


    def test_extra_native_library_is_refused_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix, archive, output, expected = self.inputs(Path(tmp))
            (prefix / 'lib').mkdir()
            (prefix / 'lib/unrecorded.so').write_bytes(b'not retained')
            with patch('gdal_fixture.json.loads', return_value=expected), self.assertRaisesRegex(ValueError, 'unrecorded'):
                gdal_fixture.prepare(prefix, archive, output)
            self.assertFalse((output / 'native-bin').exists())

    def test_directory_symlink_is_refused_even_when_file_bytes_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefix, archive, output, expected = self.inputs(root)
            (prefix / 'bin').rename(root / 'elsewhere')
            (prefix / 'bin').symlink_to(root / 'elsewhere', target_is_directory=True)
            with patch('gdal_fixture.json.loads', return_value=expected), self.assertRaisesRegex(ValueError, 'directory differs'):
                gdal_fixture.prepare(prefix, archive, output)
            self.assertFalse((output / 'native-bin').exists())

    def test_relative_prefix_produces_absolute_native_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefix, archive, output, expected = self.inputs(root)
            with patch('gdal_fixture.json.loads', return_value=expected):
                report = gdal_fixture.prepare(Path(os.path.relpath(prefix)), archive, output)
            self.assertEqual(report['environment']['GDAL_DATA'], str(prefix / 'share/gdal'))
            self.assertTrue(all(Path(row['path']).is_absolute() for row in report['verified_files']))


if __name__ == '__main__':
    unittest.main()
