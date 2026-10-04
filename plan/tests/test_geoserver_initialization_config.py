"""Actual owned configuration generation with synthetic files; no Java/service.

The native XML alias/default/REST pattern is bound to retained source in the
component evidence. These checks are not a native deserialization/startup test.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/development'))
from ambisgis_development import geoserver

# Exact selected RESTAccessRuleDAO.PATTERN; unchanged engine source rejects PATCH.
REST_PATTERN = r'\S+;(GET|POST|PUT|DELETE|HEAD|OPTIONS)(,(GET|POST|PUT|DELETE|HEAD|OPTIONS))*=\S+(, ?\S+)*'
IMAGE_PROCESSING = {'allowInterpolation': 'false', 'recycling': 'false',
                    'tilePriority': '5', 'tileThreads': '7', 'memoryCapacity': '0.5',
                    'memoryThreshold': '0.75', 'imageIOCache': 'false', 'pngEncoderType': 'PNGJ'}


class GeoServerConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = self.root / 'engine'; self.engine.mkdir()
        (self.engine / 'lib').mkdir()
        self.data = self.root / 'data'; self.data.mkdir()
        (self.data / 'assets').mkdir()
        for name, content in [('private_points.properties', geoserver.POINTS), ('diagnostic.sld', geoserver.STYLE)]:
            (self.data / 'assets' / name).write_bytes(content)
        war = self.engine / 'application.war'; war.write_bytes(b'synthetic-not-a-WAR')
        profile = {'schema_version': 1, 'profile': 'NO-ORACLE-NO-JPEG2000-headless-Temurin17',
                   'war_sha256': hashlib.sha256(war.read_bytes()).hexdigest()}
        for key, name in [('renderer','marlin-0.9.4.8.jar'),('imageio','jai_imageio-1.1.jar'),('json','json-lib-2.4.2-geoserver.jar')]:
            value = ('synthetic-' + key).encode(); (self.engine / 'lib' / name).write_bytes(value)
            profile[key + '_member'] = 'WEB-INF/lib/' + name
            profile[key + '_sha256'] = hashlib.sha256(value).hexdigest()
        (self.engine / 'runtime-profile.json').write_text(json.dumps(profile))
        self.secrets = {key: 'synthetic-secret-' + key for key in ('engine_admin','policy_key','transport_migrator','transport_reader')}
        self.product = {'install_id': '11111111-1111-4111-8111-111111111111'}
    def generate(self, initialize=True):
        runtime = self.root / ('init' if initialize else 'serve')
        with patch.object(geoserver,'ENGINE',self.engine),patch.object(geoserver,'DATA',self.data),patch.object(geoserver,'RUNTIME',runtime),patch.object(geoserver.subprocess,'run',side_effect=AssertionError('no child')):
            geoserver.configuration(self.product,self.secrets,initialize)
        return runtime / 'data'
    def test_global_has_native_aliased_image_processing_defaults(self):
        root = ET.parse(self.generate() / 'global.xml').getroot()
        self.assertEqual(root.tag,'global')
        jai = root.findall('jai'); self.assertEqual(len(jai),1)
        self.assertEqual({e.tag:e.text for e in jai[0]},IMAGE_PROCESSING)
        self.assertEqual(len(jai[0]),len(IMAGE_PROCESSING))
        self.assertIsNone(root.find('imageProcessing'))
    def test_native_rest_rule_is_accepted_and_remains_admin_only(self):
        rule=(self.generate() / 'security/rest.properties').read_text().strip()
        self.assertIsNotNone(re.fullmatch(REST_PATTERN,rule))
        target, authority=rule.split('=');path,methods=target.split(';')
        self.assertEqual(path,'/**');self.assertEqual(authority,'ROLE_ADMINISTRATOR')
        self.assertEqual(set(methods.split(',')),{'GET','HEAD','OPTIONS','POST','PUT','DELETE'})
    def test_native_rest_pattern_rejects_original_and_unsupported_methods(self):
        for methods in ('GET,HEAD,OPTIONS,POST,PUT,PATCH,DELETE','PATCH','GET,TRACE','GET,,POST'):
            with self.subTest(methods=methods):self.assertIsNone(re.fullmatch(REST_PATTERN,'/**;'+methods+'=ROLE_ADMINISTRATOR'))
    def test_serving_and_init_share_fixed_image_and_rest_settings(self):
        init=self.generate();serve=self.generate(False)
        for name in ('global.xml','security/rest.properties'):
            self.assertEqual((init/name).read_bytes(),(serve/name).read_bytes())
            for secret in self.secrets.values():self.assertNotIn(secret,(init/name).read_text())
        self.assertIn('hibernate.hbm2ddl.auto]=update',(init/'geofence/geofence-datasource-ovr.properties').read_text())
        self.assertIn('hibernate.hbm2ddl.auto]=validate',(serve/'geofence/geofence-datasource-ovr.properties').read_text())


if __name__ == '__main__': unittest.main()
