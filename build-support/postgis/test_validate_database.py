"""Safety checks for disposable probe and upgrade receipt validation.

These are tooling tests, separate from actual PostgreSQL/PostGIS SQL assertions.
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('validate_database', Path(__file__).with_name('validate_database.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class UpgradeStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.prefix = self.root / 'prefix'
        self.prefix.mkdir()
        self.run = self.root / 'run'
        self.data = self.run / 'data'
        self.data.mkdir(parents=True)
        (self.data / '.ambisgis-probe-owner').write_text('own-marker\n')
        self.state = dict(kind='ambisgis-postgis-upgrade-fixture-v1', status='prepared-and-stopped',
                          uid=os.getuid(), prefix=str(self.prefix), run_dir=str(self.run),
                          data_dir=str(self.data), nonce='own-marker',
                          from_version='3.5.6', to_version='3.5.7')
        self.path = self.run / 'upgrade-state.json'

    def validate(self):
        self.path.write_text(json.dumps(self.state))
        return probe.validate_state(self.path, self.root, self.prefix)

    def test_owned_stopped_earlier_fixture_accepted(self):
        self.assertEqual(self.validate()['from_version'], '3.5.6')

    def test_same_version_fixture_rejected(self):
        self.state['from_version'] = '3.5.7'
        with self.assertRaisesRegex(RuntimeError, 'version pair'):
            self.validate()

    def test_marker_mismatch_rejected(self):
        self.state['nonce'] = 'some-other-cluster'
        with self.assertRaisesRegex(RuntimeError, 'ownership marker'):
            self.validate()

    def test_existing_postmaster_rejected(self):
        (self.data / 'postmaster.pid').write_text('12345\n')
        with self.assertRaisesRegex(RuntimeError, 'already running'):
            self.validate()

    def test_different_installation_rejected(self):
        self.state['prefix'] = str(self.root / 'other')
        with self.assertRaisesRegex(RuntimeError, 'prefix differs'):
            self.validate()

    def test_foreign_os_user_rejected(self):
        self.state['uid'] += 1
        with self.assertRaisesRegex(RuntimeError, 'another OS user'):
            self.validate()

    def test_moved_state_rejected(self):
        self.state['run_dir'] = str(self.root / 'different-run')
        with self.assertRaisesRegex(RuntimeError, 'state was moved'):
            self.validate()

    def test_data_directory_escape_rejected(self):
        self.state['data_dir'] = str(self.root / 'elsewhere')
        with self.assertRaisesRegex(RuntimeError, 'Path must be inside'):
            self.validate()

    def test_symlink_escape_rejected(self):
        link = self.run / 'escape'
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'Path must be inside'):
            probe.contained(link, self.run)


class LibraryNameTests(unittest.TestCase):
    def test_postgis35_requires_actual_raster_and_topology_module_names(self):
        from validate_database import extension_libraries
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('postgis-3.so', 'postgis_raster-3.so', 'postgis_topology-3.so'):
                (root/name).touch()
            self.assertEqual(len(extension_libraries(root)), 3)
            (root/'postgis_raster-3.so').unlink()
            (root/'rtpostgis-3.so').touch()
            with self.assertRaisesRegex(RuntimeError, 'postgis_raster'):
                extension_libraries(root)


class RuntimeVersionTests(unittest.TestCase):
    def test_native_revision_suffix_is_recorded_without_accepting_wrong_version(self):
        from validate_database import require_postgis_versions
        actual = {'postgis': '3.5.6', 'raster': '3.5.6 0', 'scripts': '3.5.6 0'}
        require_postgis_versions(actual, '3.5.6')
        for wrong in ('3.5.60 0', '3.5.6dev 0', '3.5.7 0'):
            with self.assertRaises(RuntimeError):
                require_postgis_versions(dict(actual, raster=wrong), '3.5.6')


class LibraryResolutionTests(unittest.TestCase):
    def test_absolute_and_arrow_dependencies_must_be_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefix = root / 'prefix'
            (prefix / 'lib').mkdir(parents=True)
            library = prefix / 'lib/libsqlite3.so'
            library.touch()
            for line in (f' {library} (0x1234)', f' libsqlite3.so => {library} (0x1234)'):
                probe.require_owned_linkage(line, prefix)
            for line in (' /usr/lib/libsqlite3.so (0x1234)',
                         ' libsqlite3.so => /usr/lib/libsqlite3.so (0x1234)',
                         ' libsqlite3.so => not found', ' libproj.so => unknown'):
                with self.subTest(line=line), self.assertRaises(RuntimeError):
                    probe.require_owned_linkage(line, prefix)

    def test_dependency_symlink_to_host_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefix = root / 'prefix'
            prefix.mkdir()
            outside = root / 'libsqlite3.so'
            outside.touch()
            library = prefix / 'libsqlite3.so'
            library.symlink_to(outside)
            with self.assertRaises(RuntimeError):
                probe.require_owned_linkage(f' {library} (0x1234)', prefix)


if __name__ == '__main__':
    unittest.main()
