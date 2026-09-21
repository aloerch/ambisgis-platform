import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location('configured_auth_fixture', Path(__file__).with_name('configured_auth_fixture.py'))
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class ConfiguredAuthFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source' / 'geoserver'
        for relative in fixture.SOURCE_PATHS:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('// retained definition\n')
        self.output = self.root / 'fixture'
        self.secret = 'disposable-' + 'x' * 32

    def tearDown(self):
        self.temporary.cleanup()

    def generate(self, **kw):
        return fixture.prepare(self.source, self.output, 'http://127.0.0.1:43210',
                               'synthetic-client', self.secret, **kw)

    def test_policy_identities_credentials_and_manifest(self):
        manifest = self.generate()
        self.assertNotIn(self.secret, json.dumps(manifest))
        self.assertFalse(manifest['stateless_bearer_authentication'])
        self.assertIsNone(ET.parse(self.output / 'security/filter/fixture-oauth/config.xml').getroot()
                          .find('statelessBearerAuthentication'))
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        security = ET.parse(self.output / 'security/config.xml').getroot()
        self.assertEqual(len(security.find('authProviderNames')), 0)
        chains = security.find('filterChain').findall('filters')
        self.assertEqual([x.attrib['name'] for x in chains], ['rest', 'default'])
        self.assertTrue(all([x.text for x in c.findall('filter')] == ['fixture-oauth', 'anonymous'] for c in chains))
        users = ET.parse(self.output / 'security/usergroup/fixture/users.xml').getroot()
        identities = [e for e in users.iter() if e.tag.endswith('}user')]
        self.assertEqual({e.attrib['name'] for e in identities}, set(fixture.IDENTITIES))
        self.assertTrue(all(e.attrib['password'].startswith('plain:') and len(e.attrib['password']) > 50 for e in identities))
        self.assertFalse(any(e.attrib['name'] in ('root', 'admin') for e in identities))
        rules = [ET.fromstring(body) for body in manifest['geofence_rule_bodies']]
        self.assertIsNone(rules[0].find('roleName'))
        self.assertEqual(rules[1].findtext('roleName'), 'ROLE_FIXTURE_READER')
        self.assertEqual(rules[2].findtext('layer'), 'private_points')
        self.assertEqual(rules[2].findtext('priority'), '30')
        self.assertEqual(rules[2].findtext('layerDetails/cqlFilterRead'), 'EXCLUDE')
        self.assertEqual(rules[2].findtext('layerDetails/cqlFilterWrite'), 'EXCLUDE')
        self.assertEqual(rules[2].findtext('layerDetails/catalogMode'), 'MIXED')
        self.assertEqual(len(manifest['source_definitions']), len(fixture.SOURCE_PATHS))

    def test_explicit_stateless_option_is_serialized_and_recorded(self):
        manifest = self.generate(stateless_bearer_authentication=True)
        self.assertTrue(manifest['stateless_bearer_authentication'])
        oauth = ET.parse(self.output / 'security/filter/fixture-oauth/config.xml').getroot()
        self.assertEqual(oauth.findtext('statelessBearerAuthentication'), 'true')
        with self.assertRaisesRegex(ValueError, 'explicit boolean'):
            fixture.prepare(self.source, self.root / 'invalid-option', 'http://127.0.0.1:43210',
                            'synthetic-client', self.secret, stateless_bearer_authentication='false')

    def test_new_output_and_source_requirements(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.generate()
        self.output.rmdir()
        (self.source / fixture.SOURCE_PATHS[0]).unlink()
        with self.assertRaisesRegex(ValueError, 'missing regular'):
            self.generate()
        self.assertFalse(self.output.exists())

    def test_remote_or_credential_urls_are_rejected(self):
        for url in ('http://localhost:1234', 'https://127.0.0.1:1234', 'http://127.0.0.2:1234',
                    'http://127.0.0.1:1234/path', 'http://user@127.0.0.1:1234', 'http://127.0.0.1:1234?secret=value'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                fixture.prepare(self.source, self.output, url, 'client', self.secret)
        self.assertFalse(self.output.exists())

    def test_shape_binary_structure_and_feature_payload(self):
        self.generate()
        shp = (self.output / 'data/private_points.shp').read_bytes()
        shx = (self.output / 'data/private_points.shx').read_bytes()
        dbf = (self.output / 'data/private_points.dbf').read_bytes()
        self.assertEqual(struct.unpack('>i', shp[:4]), (9994,))
        self.assertEqual(struct.unpack('>i', shp[24:28])[0] * 2, len(shp))
        self.assertEqual(struct.unpack('>2i', shx[100:108]), (50, 10))
        self.assertEqual(struct.unpack('<idd', shp[108:]), (1, 1., 2.))
        count, head, length = struct.unpack('<IHH', dbf[4:12])
        self.assertEqual((count, head, length), (1, 65, 33))
        self.assertEqual(dbf[head + 1:head + length].rstrip(), b'PRIVATE_WITNESS')
        self.assertEqual(dbf[32:43].rstrip(b'\0'), b'label')
        for name in ('public_points', 'private_points'):
            resource = ET.parse(self.output / f'workspaces/fixture/{name}/{name}/featuretype.xml').getroot()
            self.assertEqual(resource.findtext('store/id'), 'fixture-store-' + name)

    def test_runtime_secrets_are_removed_with_marked_fixture_only(self):
        self.generate()
        redacted = fixture.scrub_secrets(self.output)
        self.assertIn('security/filter/fixture-oauth/config.xml', redacted)
        self.assertIn('security/masterpw/fixture/passwd', redacted)
        for p in (self.output / 'security').rglob('*'):
            if p.is_file():
                self.assertNotIn(self.secret.encode(), p.read_bytes())
        (self.output / fixture.MARKER).unlink()
        with self.assertRaises(ValueError):
            fixture.scrub_secrets(self.output)

    def test_scrub_refuses_symlink_to_external_secret(self):
        self.generate()
        external = self.root / 'outside.xml'
        external.write_text('<x><clientSecret>preserve</clientSecret></x>')
        (self.output / 'security/escape.xml').symlink_to(external)
        with self.assertRaises(ValueError):
            fixture.scrub_secrets(self.output)
        self.assertIn('preserve', external.read_text())


if __name__ == '__main__':
    unittest.main()
