"""Meaningful failure guards for the local-only QGIS source-publication boundary."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('qgis_snapshot', ROOT / 'build-support/source_publication/qgis_snapshot.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class PublicationGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def repository(self, name='source.git', payload=b'retained source\n'):
        repo = self.root / name
        q.init_repo(repo)
        oid = q.git(repo, 'hash-object', '-w', '--stdin', data=payload).decode().strip()
        tree = q.git(repo, 'mktree', data=('100644 blob ' + oid + '\tfile.txt\n').encode()).decode().strip()
        commit = q.git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                       'commit-tree', tree, data=b'local fixture\n').decode().strip()
        q.git(repo, 'update-ref', q.REF, commit)
        return repo, commit, tree, {'file.txt': {'mode': '100644', 'oid': oid}}

    def test_exact_root_and_independent_bundle_restore(self):
        repo, commit, tree, expected = self.repository()
        result = q.verify_repository(repo, commit, tree, expected, set())
        self.assertEqual(result['parent_count'], 0)
        bundle = self.root / 'snapshot.bundle'
        q.git(repo, 'bundle', 'create', str(bundle), q.REF)
        restored = self.root / 'restored.git'
        actual = q.restore_bundle(bundle, restored, commit, tree, expected, set())
        self.assertEqual(actual['objects'], result['objects'])
        self.assertNotEqual((repo / 'objects').stat().st_ino, (restored / 'objects').stat().st_ino)

    def test_restore_never_starts_automatic_maintenance(self):
        repo, commit, tree, expected = self.repository()
        bundle = self.root / 'snapshot.bundle'
        q.git(repo, 'bundle', 'create', str(bundle), q.REF)
        trace = self.root / 'restore-trace.jsonl'
        with patch.dict(q.GIT_ENV, {'GIT_TRACE2_EVENT': str(trace)}):
            actual = q.restore_bundle(bundle, self.root / 'restored.git',
                                      commit, tree, expected, set())
        self.assertEqual((actual['commit'], actual['tree']), (commit, tree))
        self.assertTrue(actual['stored_equals_reachable'])
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        self.assertTrue(any(event.get('event') == 'cmd_name' and
                            event.get('name') == 'fetch' for event in events),
                        'trace must observe the actual restore fetch')
        maintenance = [event for event in events
                       if event.get('event') == 'child_start' and
                       any(argument in ('maintenance', 'gc', 'git-maintenance', 'git-gc')
                           for argument in event.get('argv', []))]
        self.assertEqual(maintenance, [],
                         'verified restore must not launch automatic maintenance')

    def test_wrong_commit_tree_and_complete_source_inventory(self):
        repo, commit, tree, expected = self.repository()
        with self.assertRaises(ValueError):
            q.verify_repository(repo, commit, '0' * 40, expected, set())
        with self.assertRaises(ValueError):
            q.verify_repository(repo, commit, tree, {}, set())
        changed = copy.deepcopy(expected)
        changed['file.txt']['mode'] = '100755'
        with self.assertRaises(ValueError):
            q.verify_repository(repo, commit, tree, changed, set())

    def test_parent_ancestry_is_rejected(self):
        repo, commit, tree, expected = self.repository()
        child = q.git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                      'commit-tree', tree, '-p', commit, data=b'invalid child\n').decode().strip()
        q.git(repo, 'update-ref', q.REF, child)
        with self.assertRaisesRegex(ValueError, 'ancestry'):
            q.verify_repository(repo, child, tree, expected, set())

    def test_additional_backup_refs_are_rejected(self):
        repo, commit, tree, expected = self.repository()
        q.git(repo, 'update-ref', 'refs/heads/backup', commit)
        with self.assertRaisesRegex(ValueError, 'refs'):
            q.verify_repository(repo, commit, tree, expected, set())

    def test_forbidden_reachable_and_unreachable_blobs_are_rejected(self):
        repo, commit, tree, expected = self.repository()
        with self.assertRaisesRegex(ValueError, 'forbidden'):
            q.verify_repository(repo, commit, tree, expected, {expected['file.txt']['oid']})
        q.git(repo, 'hash-object', '-w', '--stdin', data=b'forbidden stale object')
        with self.assertRaisesRegex(ValueError, 'unreachable'):
            q.verify_repository(repo, commit, tree, expected, set())

    def test_shared_alternate_promisor_and_hooks_are_rejected(self):
        for name in ('objects/info/alternates', 'objects/info/http-alternates', 'shallow', 'info/grafts',
                     'objects/pack/missing.promisor', 'hooks/post-checkout'):
            with self.subTest(path=name):
                repo, commit, tree, expected = self.repository(name.replace('/', '-') + '.git')
                p = repo / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('unreviewed\n')
                with self.assertRaises(ValueError):
                    q.verify_repository(repo, commit, tree, expected, set())

    def test_missing_payload_never_passes_fsck_or_tree_check(self):
        repo, commit, tree, expected = self.repository()
        oid = expected['file.txt']['oid']
        (repo / 'objects' / oid[:2] / oid[2:]).unlink()
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            q.verify_repository(repo, commit, tree, expected, set())

    def test_wrong_selection_identity_refused_before_loading(self):
        p = self.root / 'selection.json'
        p.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'selection identity'):
            q.load_selection(p)

    def test_wrong_owner_authorization_refused(self):
        p = self.root / 'authorization.json'
        value = {'body_sha256': q.AUTH_SHA, 'comment': {'id': 5863464446,
                 'user': {'login': 'aloerch', 'id': 15285626},
                 'created_at': '2026-09-28T04:35:51Z', 'body': 'changed local approval'}}
        p.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'owner decision'):
            q.authorization(p)

    def test_exact_catalogue_change_preserves_other_scopes_and_xml(self):
        original = b'<selection><collect dir="es"/><collect dir="esdb"/><gradient dir="gmt" file="GMT_dem1"/><gradient dir="gmt" file="other"/></selection>'
        changed, removed, notice = q.catalogue_change(original, ['es'], '2026-09-28')
        self.assertEqual(len(removed), 2)
        self.assertIn(b'dir="esdb"', changed)
        self.assertIn(b'file="other"', changed)
        self.assertIn(b'AmbisGIS modification 2026-09-28', notice)
        self.assertEqual(changed.count(notice), 1)

    def test_embedded_alias_and_compressed_alias_rejected(self):
        forbidden = b'<svg>restricted fixture</svg>'
        digest = q.digest(forbidden)
        for payload in (forbidden, gzip.compress(forbidden)):
            with self.subTest(length=len(payload)), self.assertRaisesRegex(ValueError, 'forbidden'):
                q.embedded_audit(payload, 'fixture', {digest}, {'archive_members':0,'expanded_bytes':0,'containers':[]})
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('renamed-palette.dat', forbidden)
        with self.assertRaisesRegex(ValueError, 'forbidden'):
            q.embedded_audit(stream.getvalue(), 'renamed.zip', {digest}, {'archive_members':0,'expanded_bytes':0,'containers':[]})

    def test_safe_paths_reject_administrative_and_escape_members(self):
        for path in ('../file', '/file', '.git/config', 'a/.GIT/config', 'a//file'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                q.safe_path(path)

    def test_existing_output_and_bundle_with_wrong_ref_rejected(self):
        repo, commit, tree, expected = self.repository()
        with self.assertRaises(ValueError):
            q.init_repo(repo)
        bundle = self.root / 'invalid.bundle'
        bundle.write_bytes(b'# v2 git bundle\n' + commit.encode() + b' refs/heads/other\n\n')
        with self.assertRaisesRegex(ValueError, 'bundle refs'):
            q.restore_bundle(bundle, self.root/'restored.git', commit, tree, expected, set())


    def test_binary_qt_magic_refused(self):
        for magic in (b'qres', b'RCC'):
            with self.subTest(magic=magic), self.assertRaisesRegex(ValueError, 'compiled Qt'):
                q.embedded_audit(magic+b'opaque', 'fixture', set(),
                                 {'archive_members':0,'expanded_bytes':0,'containers':[]})

    def test_symlinked_and_hardlinked_object_stores_refused(self):
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind):
                repo, commit, tree, expected = self.repository(kind+'.git')
                oid = expected['file.txt']['oid']
                obj = repo/'objects'/oid[:2]/oid[2:]
                other = self.root/(kind+'-other')
                if kind == 'symlink':
                    obj.rename(other)
                    obj.symlink_to(other)
                else:
                    os.link(obj, other)
                with self.assertRaisesRegex(ValueError, kind):
                    q.verify_repository(repo, commit, tree, expected, set())

    def test_unicode_fast_import_path_encoding(self):
        repo = self.root/'unicode.git'
        q.init_repo(repo)
        path = 'fixtures/polys_non_ascii_ñññ.gfs'
        payload = b'correct Unicode-path fixture\n'
        commands = (b'commit '+q.REF.encode()+b'\ncommitter Fixture <fixture@example.invalid> 1790568000 +0000\n'
                    b'data 8\nfixture\n\nM 100644 inline '+q.quoted_git_path(path)+b'\ndata '+
                    str(len(payload)).encode()+b'\n'+payload+b'\n\ndone\n')
        q.git(repo, 'fast-import', '--quiet', data=commands)
        commit = q.git(repo, 'rev-parse', q.REF).decode().strip()
        self.assertEqual(q.tree_entries(repo, commit), {path:{'mode':'100644','oid':q.blob_id(payload)}})

    def test_mutated_or_failed_receipt_refused(self):
        p = self.root/'result.json'
        p.write_text('{"status":"passed"}\n')
        before = q.sha(p)
        p.write_text('{"status":"passed", "mutated":true}\n')
        with self.assertRaisesRegex(ValueError, 'receipt identity'):
            q.trusted_receipt(p, before)
        p.write_text('{"status":"failed"}\n')
        with self.assertRaisesRegex(ValueError, 'failed receipt'):
            q.trusted_receipt(p, q.sha(p))

    def test_hash_bound_receipt_payload_tamper_refused(self):
        payload = self.root/'payload.json'; payload.write_text('{}')
        ref = q.file_ref(payload)
        record = {'status':'passed','old_source':{'commit':q.BASE,'tree':q.BASE_TREE},
                  'authorization':{'body_sha256':q.AUTH_SHA},
                  **{key:ref for key in ('bundle','provenance','expected_tree','forbidden_objects')}}
        receipt = self.root/'result.json'; q.save(receipt, record)
        receipt_sha = q.sha(receipt)
        self.assertEqual(q.trusted_receipt(receipt, receipt_sha), record)
        payload.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'payload identity'):
            q.trusted_receipt(receipt, receipt_sha)

    def test_final_integrity_failure_controls_exit_and_receipt(self):
        from types import SimpleNamespace
        receipt = self.root/'claimed-success.json'
        receipt.write_text('{"status":"passed"}')
        output = self.root/'verification.json'
        args = SimpleNamespace(receipt=receipt, receipt_sha256='0'*64,
                               workspace_root=self.root, output=output)
        self.assertEqual(q.verify_existing(args), 1)
        self.assertEqual(json.loads(output.read_text())['status'], 'failed')

    def test_complete_delta_rejects_extra_omission_or_compiler_change(self):
        repo = self.root/'comparison.git'; q.init_repo(repo)
        original = {}; expected = {}; mapping = []; changes = []
        for index in range(19):
            path = q.RESOURCE+'selections/test-'+str(index)+'.xml'
            before = b'<selection><collect dir="es"/><collect dir="cb"/></selection>'
            oid = q.git(repo,'hash-object','-w','--stdin',data=before).decode().strip()
            after, removed, notice = q.catalogue_change(before,['es'],'2026-09-28')
            original[path]={'mode':'100644','oid':oid}
            expected[path]={'mode':'100644','oid':q.blob_id(after)}
            mapping.append({'path':path,'mode':'100644','original_oid':oid,'snapshot_oid':q.blob_id(after)})
            changes.append({'path':path,'removed_references':removed,'notice':notice.decode(),
                            'before_sha256':q.digest(before),'after_sha256':q.digest(after)})
        original['src/main.cpp']={'mode':'100644','oid':q.blob_id(b'unchanged')}
        expected['src/main.cpp']=original['src/main.cpp'].copy()
        mapping.append({'path':'src/main.cpp','mode':'100644','original_oid':original['src/main.cpp']['oid'],
                        'snapshot_oid':expected['src/main.cpp']['oid']})
        original['excluded.svg']={'mode':'100644','oid':q.blob_id(b'omitted')}
        for path in (q.PROVENANCE,q.NOTICE):expected[path]={'mode':'100644','oid':q.blob_id(path.encode())}
        provenance={'created_utc':'2026-09-28T00:00:00+00:00','retained_file_mapping':mapping,
                    'omitted_files':[{'path':'excluded.svg'}],'catalogue_changes':changes}
        self.assertEqual(q.verify_complete_delta(original,expected,provenance,{'excluded.svg':{}},repo)
                         ['unchanged_retained_files'],1)
        bad=copy.deepcopy(expected);del bad['src/main.cpp']
        with self.assertRaisesRegex(ValueError,'omissions'):
            q.verify_complete_delta(original,bad,provenance,{'excluded.svg':{}},repo)
        bad=copy.deepcopy(expected);bad['src/main.cpp']['oid']=q.blob_id(b'changed compiler source')
        changed_prov=copy.deepcopy(provenance)
        changed_prov['retained_file_mapping'][-1]['snapshot_oid']=bad['src/main.cpp']['oid']
        with self.assertRaisesRegex(ValueError,'compiler'):
            q.verify_complete_delta(original,bad,changed_prov,{'excluded.svg':{}},repo)


    def test_readonly_resource_verify_does_not_recreate_missing_stage(self):
        sys.path.insert(0, str(ROOT/'build-support/qgis'))
        import publication_selection
        output=self.root/'missing-stage'; replay=self.root/'also-missing'
        with self.assertRaisesRegex(ValueError, 'both existing resource stages'):
            publication_selection.publication_variant_stage(None,None,None,None,None,None,None,
                                                          output,replay,verify_only=True)
        self.assertFalse(output.exists())
        self.assertFalse(replay.exists())


if __name__ == '__main__':
    unittest.main()
