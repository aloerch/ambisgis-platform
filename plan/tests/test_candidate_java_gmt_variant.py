"""Preserve historical acceptance boundaries while selecting the authorized successor."""
import hashlib,json,unittest
from pathlib import Path
PLAN=Path(__file__).resolve().parents[1]
TARGETS={'F02-JAVA-aspectj154','F02-JAVA-xmlpull1131','F02-JAVA-jai-imageio11','F02-JAVA-json-lib','F02-JAVA-marlin0948','F02-JAVA-ojdbc17-source-placeholder','F06-QGIS-SRC-02'}
class JavaGmtVariantTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=PLAN/'candidates/fnd-02-candidate-parent-2.json';cls.parent=json.loads(cls.path.read_text());cls.new=json.loads((PLAN/'candidates/fnd-02-candidate.json').read_text())
 def test_parent_and_source_authority_preserved(self):
  self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),'3c59d99834b53f8778143db70f754272bce9920ca05071586d4f3629cdd625a0')
  self.assertEqual(self.new['roots'],self.parent['roots']);self.assertEqual(self.new['schema_version'],1);self.assertEqual(self.new['candidate_revision'],3)
 def test_only_seven_authorized_findings_change(self):
  old={f['id']:f for f in self.parent['findings']};new={f['id']:f for f in self.new['findings']}
  self.assertEqual(set(new),set(old));self.assertEqual({k for k in old if old[k]!=new[k]},TARGETS)
  for k in TARGETS:self.assertEqual(new[k]['original_vs_variant']['parent_finding'],old[k])
 def test_unresolved_rights_still_block_adoption(self):
  new={f['id']:f for f in self.new['findings']}
  for k in ['F02-JAVA-jai-imageio11','F02-JAVA-json-lib']:
   self.assertTrue(new[k]['blocks']['candidate_adoption']);self.assertTrue(new[k]['blocks']['distribution']);self.assertEqual(new[k]['classification'],'selection-blocker')
 def test_database_notebook_combinations_and_frontend_bytes_unchanged(self):
  old={c['id']:c for c in self.parent['combinations']};new={c['id']:c for c in self.new['combinations']}
  self.assertEqual(set(old),set(new))
  for k in ['database','jupyter']:self.assertEqual(old[k],new[k])
  oldr={r['id']:r for r in self.parent['records']};newr={r['id']:r for r in self.new['records']}
  for k in ['frontend-replay-output','geoserver-war','geonode-wheel','mapstore-client-wheel','database-prefix-archive','jupyterhub-wheel','jupyterlab-wheel']:self.assertEqual(oldr[k],newr[k])
 def test_changed_consumers_select_new_war_and_resource_stage(self):
  c={x['id']:x for x in self.new['combinations']}
  for k in ['java-native','identity','frontend-browser','embedded-gwc']:
   self.assertIn('java-gmt-war',c[k]['artifact_ids']);self.assertNotIn('geoserver-war',c[k]['artifact_ids'])
  self.assertIn('java-gmt-qgis-output',c['qgis']['artifact_ids']);self.assertNotIn('qgis-selection-output',c['qgis']['artifact_ids'])
 def test_eight_pass_conditions_and_four_criteria_preserved(self):
  import subprocess
  original=subprocess.check_output(['git','show','6b2e2fd7edc91746748d916d34af01f0a681e342:plan/docs/fnd-02-completion.md'],cwd=PLAN,text=True)
  current=(PLAN/'docs/fnd-02-completion.md').read_text()
  rows=lambda s:{line.split('|')[1].strip():line.split('|')[5].strip() for line in s.splitlines() if line.startswith('| F02-')}
  criteria=lambda s:[line for line in s.splitlines() if line.startswith('- [ ]')]
  self.assertEqual(rows(current),rows(original));self.assertEqual(len(rows(current)),8);self.assertEqual(criteria(current),criteria(original));self.assertEqual(len(criteria(current)),4)
if __name__=='__main__':unittest.main()
