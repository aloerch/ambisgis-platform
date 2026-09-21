"""Scope and evidence regressions for the separately proposed F02-06 variant."""
import hashlib
import json
from pathlib import Path
import unittest

PLAN=Path(__file__).resolve().parents[1]
TARGETS={'F06-FE-WEBIFC','F06-FE-RECIPE',*(f'F06-QGIS-SRC-{n:02d}' for n in range(1,5))}

class CandidateVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline_path=PLAN/'candidates/fnd-02-candidate-baseline-1.json'
        cls.baseline=json.loads(cls.baseline_path.read_text())
        cls.variant=json.loads((PLAN/'candidates/fnd-02-candidate.json').read_text())

    def test_original_manifest_is_preserved_byte_for_byte(self):
        self.assertEqual(hashlib.sha256(self.baseline_path.read_bytes()).hexdigest(),
            '18d80d6e7520e3a16db023bbff87cd2dc20a33ba921bd4f26e49a67d71a0aace')

    def test_variant_has_distinct_identity_and_unchanged_schema(self):
        self.assertNotEqual(self.variant['candidate_id'],self.baseline['candidate_id'])
        self.assertEqual(self.variant['schema_version'],self.baseline['schema_version'])
        self.assertEqual(self.variant['roots'],self.baseline['roots'])
        records={r['id']:r for r in self.variant['records']}
        baseline=records['baseline-candidate-manifest']
        self.assertEqual(baseline['sha256'],hashlib.sha256(self.baseline_path.read_bytes()).hexdigest())
        self.assertTrue(any(b.get('equals_record_sha256')=='baseline-candidate-manifest'
                            for b in self.variant['bindings']))

    def test_only_authorized_findings_change(self):
        old={f['id']:f for f in self.baseline['findings']}
        new={f['id']:f for f in self.variant['findings']}
        self.assertEqual(set(old),set(new))
        self.assertEqual({k for k in old if old[k]!=new[k]},TARGETS)
        self.assertTrue(all(new[k]['blocks']['candidate_adoption'] for k in old
                            if k.startswith('F02-JAVA-') and old[k]['blocks']['candidate_adoption']))

    def test_unchanged_java_database_notebook_profiles_are_reused(self):
        old={p['id']:p for p in self.baseline['profiles']}
        new={p['id']:p for p in self.variant['profiles']}
        for key in set(old)-{'frontend-build','qgis-desktop-server'}:
            self.assertEqual(old[key],new[key],key)
        old_records={r['id']:r for r in self.baseline['records']}
        new_records={r['id']:r for r in self.variant['records']}
        for key in ('geoserver-war','geonode-wheel','mapstore-client-wheel',
                    'database-prefix-archive','jupyterhub-wheel','jupyterlab-wheel'):
            self.assertEqual(old_records[key],new_records[key],key)

    def test_changed_combinations_have_new_artifacts_and_evidence(self):
        old={c['id']:c for c in self.baseline['combinations']}
        new={c['id']:c for c in self.variant['combinations']}
        self.assertEqual(set(old),set(new))
        for key in set(old)-{'frontend-browser','qgis'}:
            self.assertEqual(old[key],new[key],key)
        for key in ('frontend-browser','qgis'):
            self.assertNotEqual(old[key]['artifact_ids'],new[key]['artifact_ids'])
            self.assertNotEqual(old[key]['evidence_ids'],new[key]['evidence_ids'])

if __name__=='__main__':unittest.main()
