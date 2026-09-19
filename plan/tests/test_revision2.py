from __future__ import annotations
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from tools.export_project_seed import build_seed, main
from tools.bootstrap_repositories import EXPECTED, validate_manifest

ROOT = Path(__file__).resolve().parent.parent

class OwnershipAndProjectTests(unittest.TestCase):
    def test_manifest_owns_core_sources(self):
        manifest=json.loads((ROOT/'repositories.json').read_text())
        validate_manifest(manifest,'aloerch')
        self.assertEqual(len(manifest['repositories']),15)
        forks={r['upstream'] for r in manifest['repositories'] if r['kind']=='fork'}
        self.assertEqual(len(forks),11)
        self.assertTrue({'postgres/postgres','postgis/postgis','qgis/QGIS','jupyterhub/jupyterhub','jupyterlab/jupyterlab','geotools/geotools','GeoWebCache/geowebcache'} <= forks)
        self.assertEqual({r['name'] for r in manifest['repositories']},set(EXPECTED))

    def test_project_matches_repo_allowlist(self):
        m=json.loads((ROOT/'repositories.json').read_text())
        p=json.loads((ROOT/'project.json').read_text())
        self.assertEqual(p['owner'],m['owner'])
        self.assertEqual(set(p['repositories']),{r['name'] for r in m['repositories']})
        self.assertEqual(p['visibility'],'PUBLIC')
        self.assertEqual(len(p['views']),5)
        self.assertTrue(p['provisioning']['never_reset_live_progress'])

    def test_seed_deterministic_and_unique(self):
        s=build_seed()
        self.assertEqual(s,build_seed())
        self.assertEqual(s['issue_count'],66)
        self.assertEqual(len({i['marker'] for i in s['issues']}),66)
        self.assertEqual(len({i['task_id'] for i in s['issues']}),66)
        self.assertTrue(all(i['repository'].startswith('aloerch/ambisgis-') for i in s['issues']))

    def test_seed_fields_are_valid(self):
        p=json.loads((ROOT/'project.json').read_text())
        by={f['name']:f for f in p['fields']}
        for i in build_seed()['issues']:
            for name,value in i['initial_fields_only'].items():
                self.assertIn(name,by)
                if by[name]['type']=='SINGLE_SELECT':self.assertIn(value,by[name]['options'])

    def test_seed_preserves_all_dependencies_and_acceptance(self):
        tasks=json.loads((ROOT/'backlog.json').read_text())['tasks']
        by={i['task_id']:i for i in build_seed()['issues']}
        for t in tasks:
            self.assertEqual(by[t['id']]['dependency_task_ids'],t['dependencies'])
            for a in t['acceptance']:self.assertIn(a,by[t['id']]['body'])
            self.assertIn('<!-- ambisgis:managed:end -->',by[t['id']]['body'])

    def test_export_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'seed.json';path.write_text('keep')
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main(['--out',str(path)]),1)
            self.assertEqual(path.read_text(),'keep')

    def test_export_new_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'seed.json'
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(['--out',str(path)]),0)
            self.assertEqual(json.loads(path.read_text())['issue_count'],66)

    def test_lock_is_honestly_unresolved_and_owned(self):
        lock=json.loads((ROOT/'release-lock.template.json').read_text())
        self.assertFalse(lock['resolved'])
        self.assertFalse(lock['policy']['automatic_upstream_sync'])
        self.assertEqual(len(lock['owned_roots']),15)
        self.assertTrue(all(r['selected_product_commit'] is None for r in lock['owned_roots']))
        self.assertIsNone(lock['independent_patch_evidence'])

    def test_release_depends_on_independence_and_governance(self):
        tasks={t['id']:t for t in json.loads((ROOT/'backlog.json').read_text())['tasks']}
        visited=set()
        def visit(id):
            if id in visited:return
            visited.add(id)
            for dep in tasks[id]['dependencies']:visit(dep)
        visit('REL-02')
        self.assertTrue({'FND-07','FND-08','GOV-01','GOV-02','OWN-01','OWN-02','SEC-04'} <= visited)

if __name__=='__main__':unittest.main()
