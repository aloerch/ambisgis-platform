"""Inventory invariants against real local bytes; no network or build fixtures."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC=importlib.util.spec_from_file_location('candidate',Path(__file__).resolve().parents[1]/'tools/validate_candidate.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.repositories=m.read_json(m.PLATFORM/'plan/repositories.json')
        owned=[x['name'] for x in self.repositories['repositories'] if x['kind']=='fork']
        (self.path/'artifact').write_bytes(b'exact candidate bytes')
        (self.path/'receipt').write_text(json.dumps({'artifact_sha256':m.sha(self.path/'artifact'),'passed':True,'source_commit':'b'*40}))
        def record(name,kind):return {'id':name,'kind':kind,'location':{'root':'workspace','path':name},'sha256':m.sha(self.path/name),'coverage':'Exact fixture bytes',**({'producing_record_ids':['receipt'],'smoke_record_ids':['receipt']} if kind=='artifact' else {})}
        self.doc={'schema_version':1,'candidate_id':'test','base_commit':'a'*40,
            'roots':[{'id':n,'repository':n,'commit':'b'*40,'version':'1.0','provenance':{'baseline_status':'proposal'},'record_ids':['receipt'],'source_binding':{'record_id':'receipt','pointer':'/source_commit'}} for n in owned],
            'records':[record('artifact','artifact'),record('receipt','evidence')],
            'profiles':[{'id':'profile','root_ids':owned,'record_ids':['artifact','receipt'],'versions':{'python':'fixture'},'limitations':['bounded test'],'unknowns':['Host compiler source bootstrap not proved']}],
            'combinations':[{'id':'combination','profile_ids':['profile'],'artifact_ids':['artifact'],'evidence_ids':['receipt'],'scope':'Fixture artifact only','bindings':[{'record_id':'receipt','pointer':'/artifact_sha256','equals_record_sha256':'artifact'},{'record_id':'receipt','pointer':'/passed','equals':True}]}],
            'findings':[{'id':'unknown-source','component':'fixture','affected':['artifact'],'classification':'selection-blocker','blocks':{'candidate_adoption':True,'independent_engineering':False,'distribution':True},'record_ids':['receipt'],'evidence':[{'record_id':'receipt','pointer':'/passed'}],'usage':'selected','established':'exact bytes retained','unknown':'source correspondence unresolved','criteria':['C2'],'gate':'F02-06','preferred':'Recover source correspondence','alternatives':['Test a compatible source-owned replacement'],'owner_action':'Authorize exact recovery/replacement course','approval_excludes':'No distribution or invented source rights','closure':'Corresponding source mapped to selected bytes'}]}
        self.mapping={'workspace':self.path,'platform':m.PLATFORM}

    def validate(self):return m.validate(self.doc,self.mapping,self.repositories)
    def fail(self):
        with self.assertRaises(Exception):self.validate()

    def test_success_with_recorded_blocker_is_not_clearance(self):
        result=self.validate()
        self.assertEqual(result['inventory']['status'],'valid')
        self.assertEqual(result['selection']['blockers'],['unknown-source'])
        self.assertFalse(result['acceptance']['owner_acceptance'])
        self.assertFalse(result['acceptance']['distribution_permission'])
        self.assertIn('Host compiler',result['selection']['profile_unknowns']['profile'][0])

    def test_changed_bytes(self):
        (self.path/'artifact').write_bytes(b'changed');self.fail()
    def test_missing_bytes(self):
        (self.path/'artifact').unlink();self.fail()
    def test_unknown_hash_is_not_empty_success(self):
        self.doc['records'][0]['sha256']=None;self.fail()
    def test_unknown_mapping(self):
        self.mapping.pop('workspace');self.fail()
    def test_duplicate_ids(self):
        self.doc['records'].append(copy.deepcopy(self.doc['records'][0]));self.fail()
    def test_duplicate_json_key(self):
        (self.path/'invalid').write_text('{"a":1,"a":2}')
        with self.assertRaises(ValueError):m.read_json(self.path/'invalid')
    def test_invalid_syntax_and_nonfinite(self):
        for value in ['{','{"value":NaN}']:
            (self.path/'invalid').write_text(value)
            with self.assertRaises(ValueError):m.read_json(self.path/'invalid')
    def test_broken_reference(self):
        self.doc['profiles'][0]['record_ids'].append('missing');self.fail()
    def test_contradictory_same_location(self):
        row=copy.deepcopy(self.doc['records'][0]);row['id']='contradiction';row['sha256']='0'*64
        self.doc['records'].append(row);self.fail()
    def test_missing_source_identity_chain(self):
        self.doc['roots'][0].pop('source_binding');self.fail()
    def test_source_commit_contradiction(self):
        self.doc['roots'][0]['commit']='c'*40;self.fail()
    def test_pass_flag_does_not_bind_artifact(self):
        self.doc['combinations'][0]['bindings'].pop(0);self.fail()
    def test_finding_evidence_must_be_resolved(self):
        self.doc['findings'][0]['evidence']=[{'record_id':'invented'}];self.fail()
    def test_finding_pointer_must_exist(self):
        self.doc['findings'][0]['evidence'][0]['pointer']='/missing';self.fail()
    def test_null_and_floating_versions(self):
        for value in [None,'latest','master','HEAD']:
            with self.subTest(value=value):
                self.doc['profiles'][0]['versions']['python']=value;self.fail()
    def test_empty_artifact_provenance(self):
        self.doc['records'][0]['producing_record_ids']=[];self.fail()
    def test_empty_obligation(self):
        self.doc['findings'][0]['closure']=None;self.fail()
    def test_contradictory_blocker_effect(self):
        self.doc['findings'][0]['blocks']['candidate_adoption']=False;self.fail()
    def test_obligation_cannot_hide_adoption_blocker(self):
        self.doc['findings'][0]['classification']='obligation';self.fail()
    def test_missing_receipt_binding(self):
        self.doc['combinations'][0]['bindings']=[];self.fail()
    def test_false_receipt_assertion(self):
        self.doc['combinations'][0]['bindings'][1]['equals']=False;self.fail()
    def test_receipt_type_not_coerced(self):
        self.doc['combinations'][0]['bindings'][1]['equals']=1;self.fail()
    def test_unselected_root(self):
        self.doc['roots'][0]['repository']='ambisgis-unknown';self.fail()
    def test_profile_coverage(self):
        self.doc['profiles'][0]['root_ids'].pop();self.fail()
    def test_unsafe_paths(self):
        for value in ['../artifact','/etc/passwd','https://example/latest','a//b','a/./b','a\\b']:
            with self.subTest(value=value):
                self.doc['records'][0]['location']['path']=value;self.fail()
    def test_unconfined_symlink(self):
        (self.path/'artifact').unlink();(self.path/'artifact').symlink_to('/etc/passwd')
        self.doc['records'][0]['link']='/etc/passwd';self.fail()
    def test_undeclared_symlink(self):
        (self.path/'target').write_bytes((self.path/'artifact').read_bytes())
        (self.path/'artifact').unlink();(self.path/'artifact').symlink_to('target');self.fail()
    def test_confined_record_symlink(self):
        (self.path/'target').write_bytes((self.path/'artifact').read_bytes())
        (self.path/'artifact').unlink();(self.path/'artifact').symlink_to('target')
        self.doc['records'][0]['link']='target';self.validate()
    def test_recipe_order(self):
        self.doc['profiles'][0]['ordered_steps']=[{'order':2,'record_ids':['artifact'],'description':'wrong order'}];self.fail()
    def test_wrong_artifact_kind(self):
        self.doc['combinations'][0]['artifact_ids']=['receipt'];self.fail()
    def test_inventory_confined_symlink_and_exact_membership(self):
        tree=self.path/'tree';tree.mkdir();(tree/'lib').write_bytes(b'shared library');(tree/'link').symlink_to('lib')
        rows=[{'path':'lib','bytes':14,'sha256':m.sha(tree/'lib')},{'path':'link','link':'lib'}]
        (self.path/'inventory').write_text(json.dumps({'files':rows}))
        self.doc['records'].append({'id':'inventory','kind':'inventory','location':{'root':'workspace','path':'inventory'},'sha256':m.sha(self.path/'inventory'),'coverage':'complete tree'})
        self.doc['inventories']=[{'id':'tree','record_id':'inventory','pointer':'/files','location':{'root':'workspace','path':'tree'},'helper':'qgis'}]
        self.assertEqual(self.validate()['inventory']['inventory_entries_checked'],2)
        (tree/'extra').write_text('unexpected');self.fail();(tree/'extra').unlink()
        (tree/'link').unlink();(tree/'link').symlink_to('/etc/passwd');self.fail()
    def test_archive_membership(self):
        with zipfile.ZipFile(self.path/'archive','w') as z:z.writestr('WEB-INF/lib/member.jar',b'jar bytes')
        self.doc['records'].append({'id':'archive','kind':'artifact','location':{'root':'workspace','path':'archive'},'sha256':m.sha(self.path/'archive'),'coverage':'exact archive','producing_record_ids':['receipt'],'smoke_record_ids':['receipt']})
        self.doc['archive_members']=[{'id':'member','archive_id':'archive','member':'WEB-INF/lib/member.jar','sha256':hashlib.sha256(b'jar bytes').hexdigest()}]
        self.validate();self.doc['archive_members'][0]['member']='absent';self.fail()
    def test_report_is_deterministic_and_preserves_unknown(self):
        result=m.render_report(self.doc)
        self.assertEqual(result,m.render_report(copy.deepcopy(self.doc)))
        self.assertIn('source correspondence unresolved',result)
        self.assertIn('No distribution',result)
    def test_cli_exit_semantics(self):
        from unittest.mock import patch
        from contextlib import redirect_stdout,redirect_stderr
        import io
        path=self.path/'candidate.json';path.write_text(json.dumps(self.doc))
        args=[str(path),'--workspace-root',str(self.path)]
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(m.main(args),0)
            self.assertEqual(m.main(args+['--eligibility']),2)
            (self.path/'artifact').unlink()
            self.assertEqual(m.main(args),1)



class StoredCandidateReportTests(unittest.TestCase):
    def test_committed_manifest_schema_and_generated_register(self):
        from jsonschema import Draft202012Validator
        document=m.read_json(m.MANIFEST)
        Draft202012Validator(m.read_json(m.SCHEMA)).validate(document)
        report=m.PLATFORM/'plan/docs/fnd-02-owner-decisions.md'
        self.assertEqual(report.read_text(),m.render_report(document)+'\n')

if __name__=='__main__':unittest.main()
