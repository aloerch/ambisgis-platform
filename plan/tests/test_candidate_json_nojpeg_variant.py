"""Prevent scope, historical evidence and approval drift in the authorized successor."""
import hashlib
import json
from pathlib import Path
import unittest

PLAN = Path(__file__).resolve().parents[1]
CHANGED = {'F02-JAVA-json-lib', 'F02-JAVA-jai-imageio11'}

class JsonNoJpegVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = PLAN / 'candidates/fnd-02-candidate-parent-3.json'
        cls.parent = json.loads(cls.path.read_text())
        cls.current = json.loads((PLAN / 'candidates/fnd-02-candidate.json').read_text())

    def test_parent_authority_and_unaffected_findings_are_preserved(self):
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),
                         '8083a10deee529363e15925941c28e5a1e1f3030716f0cac7154c39466efbb90')
        self.assertEqual(self.current['roots'], self.parent['roots'])
        self.assertEqual(self.current['schema_version'], 1)
        self.assertEqual(self.current['candidate_revision'], 4)
        old = {f['id']: f for f in self.parent['findings']}
        new = {f['id']: f for f in self.current['findings']}
        self.assertEqual(set(old), set(new))
        self.assertEqual(len(new), 58)
        self.assertEqual({key for key in old if old[key] != new[key]}, CHANGED)
        for key in CHANGED:
            self.assertEqual(new[key]['original_vs_variant']['parent_finding'], old[key])
            self.assertFalse(new[key]['blocks']['candidate_adoption'])
            self.assertTrue(new[key]['blocks']['distribution'])
        self.assertEqual(new['F02-JAVA-json-lib']['closure']['condition'],
                         old['F02-JAVA-json-lib']['closure']['condition'])
        self.assertIn('OR verified removal', new['F02-JAVA-jai-imageio11']['closure']['condition'])

    def test_unchanged_profiles_and_selected_inputs_are_not_reopened(self):
        old = {c['id']: c for c in self.parent['combinations']}
        new = {c['id']: c for c in self.current['combinations']}
        self.assertEqual(set(old), set(new))
        for key in ['database', 'jupyter', 'qgis']:
            self.assertEqual(old[key], new[key])
        prior = {p['id']: p for p in self.parent['profiles']}
        current = {p['id']: p for p in self.current['profiles']}
        for key in ['database-native', 'notebook-python', 'qgis-desktop-server', 'qgis-native-support']:
            self.assertEqual(prior[key], current[key])
        oldmap = json.loads((PLAN.parent / 'build-support/java/java-gmt-variant-inputs.json').read_text())
        newmap = json.loads((PLAN.parent / 'build-support/java/json-nojpeg2000-variant-inputs.json').read_text())
        oldrepl = {r['maven_path']: r for r in oldmap['replacements']}
        newrepl = {r['maven_path']: r for r in newmap['replacements']}
        self.assertEqual(set(oldrepl), set(newrepl))
        changed = {k for k in oldrepl if oldrepl[k] != newrepl[k]}
        self.assertEqual(changed, {'net/sf/json-lib/json-lib/2.4.2-geoserver/json-lib-2.4.2-geoserver.jar',
                                   'javax/media/jai_imageio/1.1/jai_imageio-1.1.jar'})

    def test_new_war_consumers_require_new_receipts_and_no_fictional_approval(self):
        for combo in self.current['combinations']:
            if combo['id'] in ['java-native', 'identity', 'frontend-browser', 'embedded-gwc']:
                self.assertIn('json-nojpeg-war', combo['artifact_ids'])
                self.assertNotIn('java-gmt-war', combo['artifact_ids'])
                self.assertTrue(any(r.startswith('json-nojpeg-') for r in combo['evidence_ids']))
        self.assertEqual(self.current['maintenance_binding']['rule'], self.parent['maintenance_binding']['rule'])
        self.assertIn('pending', self.current['maintenance_binding']['acceptance'])
        self.assertFalse(any(f['blocks']['candidate_adoption'] for f in self.current['findings']))

if __name__ == '__main__':
    unittest.main()
