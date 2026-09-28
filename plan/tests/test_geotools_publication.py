"""Guard checks and real Git ancestry comparisons for the bounded notice repair.

Synthetic POMs test refusal and insertion mechanics; the separately retained
actual-source run covers the immutable product bytes and offline Maven parser.
"""
import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[2]/'build-support/source_publication/geotools_notice.py'
spec = importlib.util.spec_from_file_location('geotools_publication_tests', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
POM = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
       b'<!-- Original copyright and license remain here. -->\n'
       b'<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>'
       b'<version>2</version></project>\n')


class NoticeGuardTests(unittest.TestCase):
    def test_unknown_path_refused(self):
        with self.assertRaisesRegex(ValueError, 'two-file'):
            m.repair_pom('pom.xml', POM, '2026-09-28')

    def test_wrong_real_preimage_refused(self):
        for name in m.ROWS:
            with self.subTest(path=name), self.assertRaisesRegex(ValueError, 'input hash'):
                m.repair_pom(name, POM, '2026-09-28')

    def test_comment_preserves_xml_configuration_and_every_original_byte(self):
        name = next(iter(m.ROWS))
        row = dict(m.ROWS[name], sha256=m.digest(POM))
        with patch.dict(m.ROWS, {name: row}):
            after, notice = m.repair_pom(name, POM, '2026-09-28')
            self.assertEqual(after.replace(notice, b'', 1), POM)
            self.assertEqual(m.xml_configuration(after), m.xml_configuration(POM))
            self.assertIn(b'Functional change recorded 2026-09-20', notice)
            self.assertIn(b'materialized 2026-09-22', notice)
            self.assertIn(b'notice added 2026-09-28 (UTC)', notice)
            with self.assertRaisesRegex(ValueError, 'input hash'):
                m.repair_pom(name, after, '2026-09-28')

    def test_backdated_and_malformed_dates_refused(self):
        name = next(iter(m.ROWS))
        with patch.dict(m.ROWS, {name: dict(m.ROWS[name], sha256=m.digest(POM))}):
            for bad in ('2026-09-22', '2026-09-27', '2026-9-28', '2026-02-30', 'today'):
                with self.subTest(date=bad), self.assertRaises(ValueError):
                    m.repair_pom(name, POM, bad)

    def test_xml_injection_layout_and_original_header_refused(self):
        for data, notice in [(POM, b'<!--\nwrong -- delimiter\n-->\n'),
                            (POM.replace(b'\n', b'\r\n'), b'<!--\nnotice\n-->\n'),
                            (POM.replace(b'-->\n', b'--> \n'), b'<!--\nnotice\n-->\n')]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                m.insert_notice(data, notice)
        with self.assertRaises(ValueError):
            m.xml_configuration(b'<!DOCTYPE project [<!ENTITY x "bad">]><project/>')

    def test_configuration_detects_element_attribute_and_text_changes(self):
        baseline = m.xml_configuration(POM)
        for changed in (POM.replace(b'<version>2', b'<version>3'),
                        POM.replace(b'<version>', b'<version enabled="false">'),
                        POM.replace(b'<version>2</version>', b'')):
            self.assertNotEqual(baseline, m.xml_configuration(changed))

    def test_authorization_rejects_wrong_owner_body_identity_and_date(self):
        body = 'Synthetic owner-decision fixture; actual execution pins the real body.'
        doc = {'body_sha256': m.digest(body.encode()), 'comment': {
            'id': 5863464446, 'html_url': m.AUTH_URL,
            'user': {'login':'aloerch', 'id':15285626},
            'created_at':'2026-09-28T04:35:51Z', 'updated_at':'2026-09-28T04:35:51Z', 'body':body}}
        with patch.object(m, 'AUTH_BODY', m.digest(body.encode())):
            self.assertEqual(m.authorize(doc)['author'], 'aloerch')
            for key, value in [('id',0), ('html_url','https://example.invalid/'), ('user',{'login':'aloerch','id':0}),
                               ('body',body+'changed'), ('updated_at','2026-09-28T04:35:52Z')]:
                bad = copy.deepcopy(doc)
                bad['comment'][key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    m.authorize(bad)


class RealSourceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ambisgis-geotools-notices-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)/'repo'
        self.repo.mkdir()
        m.C.git(self.repo, 'init', '--template=', '--initial-branch=main')
        for name in m.ROWS:
            target = self.repo/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(POM.replace(b'<version>2',b'<version>1'))
        (self.repo/'LICENSE').write_text('Synthetic unchanged original notice.\n')
        self.base = self.commit('base')
        self.before = {p:POM for p in m.ROWS}
        for name in m.ROWS:
            (self.repo/name).write_bytes(POM)
        self.old = self.commit('old unnotified product')
        self.old_entries = m.C.tree_entries(self.repo, self.old)
        self.patchers = [patch.object(m, 'BASE', self.base), patch.object(m, 'OLD', self.old),
                        patch.dict(m.ROWS, {p:dict(row, sha256=m.digest(POM)) for p,row in m.ROWS.items()})]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        m.C.git(self.repo, 'checkout', '--detach', self.base)
        for name in m.ROWS:
            (self.repo/name).write_bytes(m.repair_pom(name, POM, '2026-09-28')[0])
        self.corrected = self.commit('corrected sibling')

    def commit(self, message):
        m.C.git(self.repo, 'add', '--all')
        m.C.git(self.repo, '-c', 'user.name=GeoTools notice test',
                '-c', 'user.email=notice-test@example.invalid', 'commit', '-m', message)
        return m.C.git(self.repo, 'rev-parse', 'HEAD').decode().strip()

    def compare(self, commit=None):
        return m.complete_comparison(self.repo, self.old_entries, commit or self.corrected,
                                    self.before, '2026-09-28')

    def test_real_sibling_retains_all_source_and_excludes_old_ancestor(self):
        result = self.compare()
        self.assertEqual(result['changed_paths'], sorted(m.ROWS))
        self.assertFalse(result['old_product_is_ancestor'])
        self.assertEqual(result['unchanged_entries'], 1)
        # Old source is still retained, with unchanged bytes.
        self.assertEqual(m.C.git(self.repo, 'show', self.old+':'+next(iter(m.ROWS))), POM)

    def test_extra_and_missing_payloads_fail_complete_membership(self):
        (self.repo/'unexpected.txt').write_text('unexpected source')
        extra = self.commit('extra payload')
        with self.assertRaisesRegex(ValueError, 'membership'):
            self.compare(extra)
        m.C.git(self.repo, 'reset', '--hard', self.corrected)
        (self.repo/'LICENSE').unlink()
        missing = self.commit('missing original notice')
        with self.assertRaisesRegex(ValueError, 'membership'):
            self.compare(missing)

    def test_unrelated_source_and_mode_changes_are_rejected(self):
        (self.repo/'LICENSE').write_text('changed attribution')
        with self.assertRaisesRegex(ValueError, 'Unexpected source change'):
            self.compare(self.commit('altered notice'))
        m.C.git(self.repo, 'reset', '--hard', self.corrected)
        m.C.git(self.repo, 'update-index', '--chmod=+x', next(iter(m.ROWS)))
        m.C.git(self.repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                'commit', '-m', 'changed mode')
        with self.assertRaisesRegex(ValueError, 'Unexpected source change'):
            self.compare(m.C.git(self.repo, 'rev-parse', 'HEAD').decode().strip())

    def test_notice_or_behavior_tampering_is_rejected(self):
        name = next(iter(m.ROWS))
        (self.repo/name).write_bytes((self.repo/name).read_bytes().replace(b'<version>2', b'<version>9'))
        with self.assertRaisesRegex(ValueError, 'Notice output'):
            self.compare(self.commit('behavior tampered'))

    def test_child_of_unnotified_old_product_is_rejected(self):
        m.C.git(self.repo, 'checkout', '--detach', self.old)
        for name in m.ROWS:
            (self.repo/name).write_bytes(m.repair_pom(name, POM, '2026-09-28')[0])
        child = self.commit('notices with wrong ancestor')
        with self.assertRaisesRegex(ValueError, 'directly parent'):
            self.compare(child)


class ReceiptIntegrityTests(unittest.TestCase):
    """Synthetic receipt prefix tests; the exact-source run exercises full recovery."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ambisgis-notice-receipt-')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.before = {name:POM for name in m.ROWS}
        self.authority = {'synthetic': 'input boundary only'}
        row_patch = patch.dict(m.ROWS, {p:dict(row, sha256=m.digest(POM)) for p,row in m.ROWS.items()})
        row_patch.start()
        self.addCleanup(row_patch.stop)
        input_patch = patch.object(m, 'inputs', return_value=(self.output/'old', self.before, None, self.authority))
        input_patch.start()
        self.addCleanup(input_patch.stop)
        models = self.output/'maven-models'
        models.mkdir()
        (models/'PomModel.java').write_text(m.MODEL_JAVA)
        model_rows = []
        for index, name in enumerate(m.ROWS):
            for kind, data in [('before', POM), ('after', m.repair_pom(name, POM, '2026-09-28')[0])]:
                (models/(str(index)+'-'+kind+'.xml')).write_bytes(data)
                (models/(str(index)+'-'+kind+'-model.xml')).write_bytes(b'Synthetic equal model fixture')
            model_sha = m.digest(b'Synthetic equal model fixture')
            model_rows.append({'path': name, 'before_model_sha256':model_sha, 'after_model_sha256':model_sha, 'equal':True})
        for i in range(1,6):
            (models/('command-'+str(i)+'.json')).write_text('{"exit_code":0}')
        patch_bytes = m.notice_patch(self.before, '2026-09-28')
        (self.output/'geotools-notices.patch').write_bytes(patch_bytes)
        self.receipt = {
            'status':'verified', 'authorization':self.authority,
            'accepted_candidate':{'path':'plan/candidates/fnd-02-candidate.json','sha256':m.CANDIDATE,'unchanged':True},
            'repository_id':1376927869, 'base_commit':m.BASE, 'base_tree':m.BASE_TREE,
            'old_product_commit':m.OLD, 'old_product_tree':m.OLD_TREE,
            'publication_authorized':False, 'remote_writes':0,
            'kind':'accepted-functional-composition-publication-sidecar',
            'repository':'aloerch/ambisgis-geotools', 'task':'FND-07',
            'proposal':m.publication_proposal(), 'recovery':m.recovery_result(),
            'implementation_sha256':m.C.sha(MODULE), 'original_source_preserved':True,
            'source':str(self.output/'source'), 'recovered':str(self.output/'recovered'),
            'bundle_chain':[{'path':str(self.output/m.PREDECESSOR),'sha256':m.PREDECESSOR_SHA,'prerequisites':[]},
                            {'path':str(self.output/'geotools-notices.bundle'),'prerequisites':[m.BASE],'ref':m.REF}],
            'maven_configuration':{'models':model_rows, 'command_count':5},
            'notice_added_utc_date':'2026-09-28',
            'patch':{'path':str(self.output/'geotools-notices.patch'),'sha256':m.digest(patch_bytes)}}

    def test_external_receipt_digest_required_and_mutation_refused(self):
        (self.output/'receipt.json').write_text(json.dumps(self.receipt))
        frozen = m.C.sha(self.output/'receipt.json')
        with self.assertRaisesRegex(ValueError, 'Trusted receipt'):
            m.verify(self.output, None, self.output, None)
        self.receipt['remote_writes'] = 1
        (self.output/'receipt.json').write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(ValueError, 'digest changed'):
            m.verify(self.output, None, self.output, frozen)

    def test_recomputed_hash_cannot_hide_wrong_patch(self):
        bad = m.notice_patch(self.before, '2026-09-28') + b'Unexpected extra patch content\n'
        (self.output/'geotools-notices.patch').write_bytes(bad)
        self.receipt['patch']['sha256'] = m.digest(bad)
        with self.assertRaisesRegex(ValueError, 'exact two-file notice'):
            m._verify_contents(self.output, None, self.output, self.receipt)

    def test_recovery_and_publication_scope_tampering_refused(self):
        for category, key, value in [('recovery','verified',False), ('recovery','fsck','failed'),
                                      ('proposal','creation_only',False), ('proposal','expected_old_commit',m.OLD),
                                      ('proposal','preserve_actions_enabled',True)]:
            bad = copy.deepcopy(self.receipt)
            bad[category][key] = value
            with self.subTest(category=category,key=key), self.assertRaisesRegex(ValueError, 'scope changed'):
                m._verify_contents(self.output, None, self.output, bad)

    def test_final_integrity_failure_never_emits_success_receipt(self):
        (self.output/'geotools-notices.patch').write_bytes(b'wrong patch')
        self.receipt.pop('status')
        with self.assertRaisesRegex(ValueError, 'exact two-file notice'):
            m.finish_receipt(self.output, None, self.output, self.receipt)
        self.assertFalse((self.output/'receipt.json').exists())
        failed = json.loads((self.output/'failed.json').read_text())
        self.assertEqual(failed['status'], 'failed')
        self.assertFalse(failed['integrity_verified'])


if __name__ == '__main__':
    unittest.main()
