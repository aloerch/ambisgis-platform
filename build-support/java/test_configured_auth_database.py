import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('configured_auth_database', Path(__file__).with_name('configured_auth_database.py'))
dbmod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dbmod)


class ConfiguredDatabaseSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.prefix = self.root / 'prefix'
        (self.prefix / 'bin').mkdir(parents=True)
        self.artifacts = []
        for name in ('postgres', 'initdb', 'pg_ctl', 'psql', 'pg_config'):
            path = self.prefix / 'bin' / name
            path.write_bytes(('retained-' + name).encode())
            self.artifacts.append({'identity': {'path': '/recorded/prefix/bin/' + name, 'sha256': dbmod.sha(path)}})
        self.historical = self.root / 'historical.json'
        self.write_history()

    def tearDown(self):
        self.temporary.cleanup()

    def write_history(self):
        self.historical.write_text(json.dumps({'runtime': {'artifacts': self.artifacts}}))

    def test_changed_owned_binary_fails_before_output_creation(self):
        (self.prefix / 'bin/postgres').write_bytes(b'changed')
        output = self.root / 'new-database'
        with self.assertRaisesRegex(ValueError, 'artifact mismatch'):
            dbmod.Database(self.prefix, self.historical, output)
        self.assertFalse(output.exists())

    def test_incomplete_custody_snapshot_fails(self):
        self.artifacts.pop()
        self.write_history()
        with self.assertRaisesRegex(ValueError, 'omits required'):
            dbmod.verify_prefix(self.prefix, self.historical)

    def test_snapshot_and_symlink_cannot_escape_owned_prefix(self):
        outside = self.root / 'outside'
        outside.write_bytes(b'not-owned')
        self.artifacts.append({'identity': {'path': '/recorded/prefix/../outside', 'sha256': dbmod.sha(outside)}})
        self.write_history()
        with self.assertRaisesRegex(ValueError, 'artifact mismatch'):
            dbmod.verify_prefix(self.prefix, self.historical)
        self.artifacts.pop()
        path = self.prefix / 'bin/postgres'
        path.unlink()
        path.symlink_to(outside)
        self.artifacts[0]['identity']['sha256'] = dbmod.sha(outside)
        self.write_history()
        with self.assertRaisesRegex(ValueError, 'artifact mismatch'):
            dbmod.verify_prefix(self.prefix, self.historical)

    def test_configuration_requires_owned_marker_and_scrubs_disposable_secret(self):
        database = dbmod.Database(self.prefix, self.historical, self.root / 'database')
        database.port = 54321
        fixture = self.root / 'fixture'
        (fixture / 'geofence').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'unmarked'):
            database.configure(fixture)
        (fixture / '.ambisgis-configured-auth-fixture').write_bytes(b'')
        record = database.configure(fixture)
        properties = fixture / 'geofence/geofence-datasource-ovr.properties'
        self.assertEqual(properties.stat().st_mode & 0o777, 0o600)
        self.assertIn('jdbc:postgresql://127.0.0.1:54321/fixture_geofence', properties.read_text())
        self.assertIn(database.password, properties.read_text())
        self.assertNotIn(database.password, json.dumps(record))
        self.assertNotIn(database.password, json.dumps(database.receipt))
        database.stop()
        self.assertNotIn(database.password, properties.read_text())
        self.assertTrue(database.receipt['stopped'])

    def test_existing_database_output_is_never_reused(self):
        output = self.root / 'existing'
        output.mkdir()
        witness = output / 'user-work'
        witness.write_text('preserve')
        with self.assertRaises(FileExistsError):
            dbmod.Database(self.prefix, self.historical, output)
        self.assertEqual(witness.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
