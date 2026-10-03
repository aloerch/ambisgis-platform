"""Exact canonical-ref authority, race, and resume guards; no remote mutations."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'tools/promote_source_refs.py'
spec = importlib.util.spec_from_file_location('source_canonical_tests', MODULE)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class MemoryReceipt:
    def __init__(self):
        self.events = []

    def emit(self, event, **fields):
        self.events.append({'event': event, **deepcopy(fields)})


class FakeCanonical:
    def __init__(self, rows, receipt):
        self.receipt = receipt
        self.states = {r['root_id']: {
            'repository': r['repository'], 'repository_id': r['repository_id'],
            'default': {'name': r['default_to_preserve']['name'], 'sha': r['default_to_preserve']['commit']},
            'review': {'ref': p.TARGET_REF, 'commit': r['proposed_commit'], 'tree': r['proposed_tree']},
            'ref_state': 'absent', 'commit': None, 'tree': None, 'actions': {'enabled': False},
            'runs': [], 'hooks': [], 'checks': [], 'statuses': []} for r in rows}
        self.mutations = []
        self.authorizations = 0
        self.companions = 0
        self.reads = []
        self.race = None
        self.timeout = False
        self.failed = False
        self.interrupt = False
        self.read_failure = False
        self.companion_failure = False
        self.auth_failure_after = None
        self.on_snapshot = None
        self.after_create = None

    def authorize(self, auth):
        self.authorizations += 1
        if self.auth_failure_after and self.authorizations >= self.auth_failure_after:
            raise ValueError('Owner authorization revoked')
        return {'comment_id': p.CANONICAL_COMMENT_ID}

    def companion(self):
        self.companions += 1
        if self.companion_failure:
            raise ValueError('Public companion unavailable')
        return {'verified': True}

    def snapshot(self, row, repo):
        self.reads.append(row['root_id'])
        if self.read_failure and row['root_id'] in self.mutations:
            raise ValueError('Readback unavailable')
        if self.on_snapshot:
            self.on_snapshot(row, self)
        return deepcopy(self.states[row['root_id']])

    def submodule(self, repo, row, child):
        assert self.states['mapstore']['ref_state'] == 'exact'
        return {'gitlink': child['proposed_commit'], 'process_only': True}

    def create_canonical(self, row):
        assert self.receipt.events[-1]['event'] == 'attempt'
        assert self.receipt.events[-1]['method'] == 'POST'
        key = row['root_id']
        self.mutations.append(key)
        if self.race:
            state, sha = self.race
            self.states[key].update(ref_state=state, commit=sha,
                                    tree=row['proposed_tree'] if state == 'exact' else None)
            raise ValueError('HTTP 422: Reference already exists')
        if self.failed:
            raise ValueError('HTTP 403: permission denied')
        self.states[key].update(ref_state='exact', commit=row['proposed_commit'], tree=row['proposed_tree'])
        if self.after_create:
            self.after_create(row, self)
        if self.interrupt:
            raise KeyboardInterrupt('Interrupted after server commit')
        if self.timeout:
            raise p.CommandFailure('Response timeout after server commit')
        return {'ref': p.CANONICAL_REF, 'object': {'sha': row['proposed_commit']}}


class CanonicalCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='canonical-tests-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve()
        self.rows = p.canonical_rows()
        self.findings = {r['root_id']: {'disposition': 'publishable'} for r in self.rows}
        self.roots = {r['root_id']: {'relative_path': 'repos/' + r['root_id']} for r in self.rows}
        for root in self.roots.values():
            (self.path / root['relative_path']).mkdir(parents=True)
        self.receipt = MemoryReceipt()
        self.client = FakeCanonical(self.rows, self.receipt)

    def execute(self, *, apply=True, only=('postgresql',)):
        return p.promote_canonical(self.rows, {}, self.findings, self.path, self.roots,
                                   self.client, self.receipt, apply=apply, only=only,
                                   local_check=lambda *args: {'synthetic_verified': True})

    def auth(self):
        body = 'Synthetic separately posted canonical owner authorization.'
        return {'schema_version': 1, 'canonical_proposal_sha256': p.CANONICAL_SHA256,
                'body_sha256': p.digest_bytes(body.encode()),
                'comment': {'id': p.CANONICAL_COMMENT_ID, 'html_url': p.CANONICAL_COMMENT_URL,
                            'issue_url': 'https://api.github.com/repos/aloerch/ambisgis-platform/issues/6',
                            'user': {'login': p.OWNER, 'id': p.OWNER_ID},
                            'created_at': p.CANONICAL_COMMENT_DATE, 'updated_at': p.CANONICAL_COMMENT_DATE,
                            'body': body}}


class CanonicalStateTests(CanonicalCase):
    def test_default_readonly_and_exact_replay_never_write_settings(self):
        result, writes = self.execute(apply=False)
        self.assertEqual(result, {'postgresql': 'ready'})
        self.assertEqual(writes, {'settings': 0, 'source_refs': 0})
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'created-or-reconciled')
        self.assertEqual(writes, {'settings': 0, 'source_refs': 1})
        self.client.mutations.clear()
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'already-exact')
        self.assertEqual(writes, {'settings': 0, 'source_refs': 0})
        self.assertEqual(self.client.mutations, [])

    def test_collision_never_advances_existing_canonical(self):
        self.client.states['postgresql'].update(ref_state='conflicting', commit='a' * 40)
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.assertEqual(writes['source_refs'], 0)
        self.assertEqual(self.client.states['postgresql']['commit'], 'a' * 40)

    def test_mutated_row_id_commit_tree_destination_and_held_rows_refused(self):
        for key, value in [('repository_id', -1), ('proposed_commit', 'a' * 40),
                           ('proposed_tree', 'a' * 40), ('target_ref', p.TARGET_REF)]:
            with self.subTest(key=key):
                rows = deepcopy(self.rows)
                self.rows[0][key] = value
                with self.assertRaisesRegex(ValueError, 'Unapproved canonical'):
                    self.execute()
                self.rows = rows
        for root in ('geotools', 'qgis', 'unrelated'):
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, 'Unknown or held'):
                self.execute(only=(root,))
        self.assertEqual(self.client.mutations, [])

    def test_actions_enabled_or_unreadable_holds_without_disabling(self):
        for policy in ({'enabled': True}, {}, {'enabled': None}):
            with self.subTest(policy=policy):
                self.client.states['postgresql']['actions'] = policy
                result, writes = self.execute()
                self.assertEqual(result['postgresql'], 'held')
                self.assertEqual(writes, {'settings': 0, 'source_refs': 0})
                self.assertEqual(self.client.mutations, [])

    def test_default_review_and_repository_changes_hold(self):
        original = deepcopy(self.client.states['postgresql'])
        changes = [('repository_id', -1), ('default', {'name': 'main', 'sha': 'a' * 40}),
                   ('review', {'ref': p.TARGET_REF, 'commit': 'a' * 40, 'tree': 'b' * 40})]
        for key, value in changes:
            with self.subTest(key=key):
                self.client.states['postgresql'] = {**deepcopy(original), key: value}
                result, writes = self.execute()
                self.assertEqual(result['postgresql'], 'held')
                self.assertEqual(writes['source_refs'], 0)

    def test_second_snapshot_detects_race_before_post(self):
        def race(row, client):
            if len(client.reads) == 2:
                client.states[row['root_id']]['actions']['enabled'] = True
        self.client.on_snapshot = race
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.assertEqual(writes['source_refs'], 0)
        self.assertEqual(self.client.mutations, [])

    def test_conflicting_race_readback_is_held_and_never_retried(self):
        self.client.race = ('conflicting', 'a' * 40)
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.assertEqual(writes['source_refs'], 1)
        self.assertEqual(self.client.mutations, ['postgresql'])
        self.assertTrue(any(e['event'] == 'reconciled' for e in self.receipt.events))
        self.assertEqual(self.client.states['postgresql']['commit'], 'a' * 40)

    def test_exact_concurrent_create_reconciles_without_second_post(self):
        self.client.race = ('exact', self.rows[0]['proposed_commit'])
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'created-or-reconciled')
        self.assertEqual(self.client.mutations, ['postgresql'])

    def test_timeout_success_reconciles_and_failed_post_stays_held(self):
        self.client.timeout = True
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'created-or-reconciled')
        self.assertEqual(self.client.mutations, ['postgresql'])
        self.client.failed = True
        result, writes = self.execute(only=('postgis',))
        self.assertEqual(result['postgis'], 'held')
        self.assertEqual(self.client.mutations.count('postgis'), 1)

    def test_interruption_preserves_journal_then_resume_observes_success(self):
        self.client.interrupt = True
        with self.assertRaises(KeyboardInterrupt):
            self.execute()
        self.assertEqual(self.receipt.events[-1]['event'], 'attempt')
        self.client.interrupt = False
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'already-exact')
        self.assertEqual(writes, {'settings': 0, 'source_refs': 0})
        self.assertEqual(self.client.mutations, ['postgresql'])

    def test_unavailable_readback_is_failed_receipt_and_replay_resolves(self):
        self.client.read_failure = True
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.assertEqual(self.receipt.events[-2]['error'], 'Readback unavailable')
        self.client.read_failure = False
        result, writes = self.execute()
        self.assertEqual(result['postgresql'], 'already-exact')
        self.assertEqual(writes['source_refs'], 0)

    def test_companion_failure_and_owner_revocation_prevent_creation(self):
        self.client.companion_failure = True
        result, _ = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.client.companion_failure = False
        self.client.auth_failure_after = self.client.authorizations + 2
        result, _ = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.assertEqual(self.client.mutations, [])

    def test_independent_rows_continue_and_mapstore_precedes_client(self):
        self.client.states['postgresql']['actions']['enabled'] = True
        result, writes = self.execute(only=None)
        self.assertEqual(result['postgresql'], 'held')
        self.assertEqual(writes, {'settings': 0, 'source_refs': 8})
        self.assertLess(self.client.mutations.index('mapstore'), self.client.mutations.index('mapstore-client'))
        self.assertNotIn('qgis', self.client.reads)
        self.assertNotIn('geotools', self.client.reads)
        self.client.states['postgresql']['actions']['enabled'] = False
        result, writes = self.execute(only=None)
        self.assertEqual(writes, {'settings': 0, 'source_refs': 1})
        self.assertEqual(result['mapstore-client'], 'already-exact')

    def test_client_alone_is_held_until_child_canonical_is_verified(self):
        result, writes = self.execute(only=('mapstore-client',))
        self.assertEqual(result['mapstore-client'], 'held')
        self.assertEqual(self.client.mutations, [])

    def test_policy_drift_after_create_is_unsuccessful_and_not_rolled_back(self):
        self.client.after_create = lambda row, client: client.states[row['root_id']]['actions'].update(enabled=True)
        result, _ = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.assertEqual(self.client.states['postgresql']['ref_state'], 'exact')
        self.assertEqual(self.client.mutations, ['postgresql'])

    def test_new_workflow_run_is_failed_evidence(self):
        def run(row, client):
            client.states[row['root_id']]['runs'] = [{'id': 11, 'status': 'completed',
                'head_sha': row['proposed_commit'], 'head_branch': 'ambisgis/main'}]
        self.client.after_create = run
        result, _ = self.execute()
        self.assertEqual(result['postgresql'], 'held')
        self.assertIn('Unexpected canonical-triggered', self.receipt.events[-2]['error'])


class CanonicalBindingTests(CanonicalCase):
    def test_immutable_proposal_bytes_are_not_original_plan_digest(self):
        path = self.path / 'wrong-plan.json'
        path.write_bytes(p.CANONICAL_PLAN.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            p.canonical_rows(path)
        self.assertNotEqual(p.CANONICAL_SHA256, p.PLAN_SHA256)
        self.assertEqual({r['root_id'] for r in self.rows}, p.CANONICAL_ROOTS)

    def test_previous_review_comment_cannot_authorize_canonical_operation(self):
        auth = self.auth()
        with patch.object(p, 'CANONICAL_COMMENT_SHA256', auth['body_sha256']):
            p.canonical_authorization_identity(auth)
            for key, value in [('id', p.COMMENT_ID), ('updated_at', 'changed'),
                               ('body', 'changed'), ('issue_url', 'https://example.com/')]:
                with self.subTest(key=key):
                    changed = deepcopy(auth)
                    changed['comment'][key] = value
                    with self.assertRaises(ValueError):
                        p.canonical_authorization_identity(changed)
            auth['canonical_proposal_sha256'] = p.PLAN_SHA256
            with self.assertRaisesRegex(ValueError, 'immutable canonical proposal'):
                p.canonical_authorization_identity(auth)

    def test_live_authorization_and_live_immutable_plan_rechecked(self):
        auth = self.auth()
        client = p.CanonicalGitHub()
        platform = {'id': 1376927351, 'full_name': 'aloerch/ambisgis-platform',
                    'owner': {'id': p.OWNER_ID}, 'private': False}
        responses = [{'login': p.OWNER, 'id': p.OWNER_ID}, platform, auth['comment']]
        with patch.object(p, 'CANONICAL_COMMENT_SHA256', auth['body_sha256']), \
                patch.object(client, 'api', side_effect=responses), \
                patch.object(client, 'public_bytes', return_value=p.CANONICAL_PLAN.read_bytes()) as read:
            result = client.authorize(auth)
            self.assertEqual(result['comment_id'], p.CANONICAL_COMMENT_ID)
            self.assertIn(p.CANONICAL_HEAD, read.call_args.args[0])
        with patch.object(p, 'CANONICAL_COMMENT_SHA256', auth['body_sha256']), \
                patch.object(client, 'api', side_effect=responses), \
                patch.object(client, 'public_bytes', return_value=b'changed'):
            with self.assertRaisesRegex(ValueError, 'immutable canonical proposal changed'):
                client.authorize(auth)

    def test_create_endpoint_is_only_post_and_exact_ref_sha(self):
        client = p.CanonicalGitHub()
        row = self.rows[0]
        with patch.object(client, 'api') as api, patch.object(client, 'push') as push, \
                patch.object(client, 'disable_actions') as settings:
            client.create_canonical(row)
            api.assert_called_once_with('repos/' + row['repository'] + '/git/refs', method='POST',
                                        payload={'ref': p.CANONICAL_REF, 'sha': row['proposed_commit']})
            push.assert_not_called()
            settings.assert_not_called()
            row = deepcopy(row)
            row['proposed_commit'] = 'a' * 40
            with self.assertRaisesRegex(ValueError, 'Unapproved canonical'):
                client.create_canonical(row)
            self.assertEqual(api.call_count, 1)

    def test_public_companion_uses_all_exact_previously_published_bytes(self):
        client = p.CanonicalGitHub()
        manifest = p.bound_json(p.COMPANION, p.COMPANION_SHA256)
        data = {r['public_url']: (p.PLATFORM / r['path']).read_bytes() for r in manifest['files']}
        with patch.object(client, 'public_bytes', side_effect=data.__getitem__):
            result = client.companion()
        self.assertEqual(len(result['files']), 20)
        data[manifest['files'][0]['public_url']] += b'changed'
        with patch.object(client, 'public_bytes', side_effect=data.__getitem__), \
                self.assertRaisesRegex(ValueError, 'Public companion missing or changed'):
            client.companion()

    def test_canonical_snapshot_checks_review_default_and_remote_tree(self):
        client = p.CanonicalGitHub()
        row = self.rows[0]
        base = deepcopy(self.client.states[row['root_id']])
        base.update(ref_state='exact', commit=row['proposed_commit'], tree=row['proposed_tree'])
        raw = (row['proposed_commit'] + '\t' + p.TARGET_REF + '\n' +
               row['default_to_preserve']['commit'] + '\trefs/heads/' + row['default_to_preserve']['name'] + '\n')
        with patch.object(p.GitHub, 'snapshot', side_effect=lambda *args: deepcopy(base)), \
                patch.object(client, 'transport', return_value=raw):
            self.assertEqual(client.snapshot(row, self.path)['ref_state'], 'absent')
        with patch.object(p.GitHub, 'snapshot', side_effect=lambda *args: deepcopy(base)), \
                patch.object(client, 'transport', return_value=raw + row['proposed_commit'] + '\t' + p.CANONICAL_REF + '\n'), \
                patch.object(client, 'api', return_value={'sha': row['proposed_commit'], 'tree': {'sha': 'a' * 40}}):
            with self.assertRaisesRegex(ValueError, 'commit/tree mismatch'):
                client.snapshot(row, self.path)

    def test_process_only_owned_submodule_mapping_keeps_declaration_unchanged(self):
        client = p.CanonicalGitHub()
        rows = {r['root_id']: r for r in self.rows}
        row, child = rows['mapstore-client'], rows['mapstore']
        path = 'geonode_mapstore_client/client/MapStore2'
        donor = 'https://github.com/geosolutions-it/MapStore2.git'
        owned = 'https://github.com/aloerch/ambisgis-mapstore.git'
        answers = [('160000 commit ' + child['proposed_commit'] + '\t' + path).encode(),
                   ('submodule.MapStore2.url ' + donor).encode(), path.encode()]
        with patch.object(p.custody, 'git', side_effect=answers), \
                patch.object(client, 'transport', return_value=child['proposed_commit'] + '\t' + p.CANONICAL_REF) as remote:
            result = client.submodule(self.path, row, child)
            self.assertEqual(result['from'], donor)
            remote.assert_called_once_with(self.path, '-c', 'url.' + owned + '.insteadOf=' + donor,
                                           'ls-remote', '--exit-code', '--refs', donor, p.CANONICAL_REF)
        answers[0] = ('160000 commit ' + 'a' * 40 + '\t' + path).encode()
        with patch.object(p.custody, 'git', side_effect=answers), \
                self.assertRaisesRegex(ValueError, 'gitlink mismatch'):
            client.submodule(self.path, row, child)


if __name__ == '__main__':
    unittest.main()
