"""FND-07 refusal/reconciliation tests; remote writes are mocked or local bare Git."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'tools/promote_source_refs.py'
spec = importlib.util.spec_from_file_location('source_promotion_tests', MODULE)
promotion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promotion)


class MemoryReceipt:
    def __init__(self):
        self.events = []

    def emit(self, event, **fields):
        self.events.append({'event': event, **deepcopy(fields)})


class FakeGitHub:
    def __init__(self, rows, receipt):
        self.receipt = receipt
        self.states = {r['root_id']: {
            'repository': r['repository'], 'repository_id': r['repository_id'],
            'default': deepcopy(r['donor_default_preserved']), 'ref_state': 'absent',
            'commit': None, 'tree': None, 'actions': {'enabled': True, 'allowed_actions': 'all'},
            'runs': [], 'hooks': []} for r in rows}
        self.mutations = []
        self.authorization_failure = False
        self.settings_failure = False
        self.settings_timeout = False
        self.push_timeout = False
        self.push_failure = False
        self.read_failure_after_push = False
        self.conflict_race = False
        self.unexpected_run = False
        self.snapshot_calls = []

    def authorize(self, auth):
        if self.authorization_failure:
            raise ValueError('Authenticated owner mismatch')
        return {'login': promotion.OWNER, 'comment_id': promotion.COMMENT_ID}

    def snapshot(self, row, repo):
        key = row['root_id']
        self.snapshot_calls.append(key)
        if self.read_failure_after_push and any(action == 'push' for _, action in self.mutations):
            raise ValueError('Remote readback inaccessible')
        return deepcopy(self.states[key])

    def disable_actions(self, row):
        key = row['root_id']
        assert self.receipt.events[-1]['event'] == 'attempt'
        assert self.receipt.events[-1]['operation'] == 'disable_actions'
        self.mutations.append((key, 'disable'))
        if self.settings_failure:
            raise ValueError('Permission denied')
        self.states[key]['actions']['enabled'] = False
        if self.settings_timeout:
            raise promotion.CommandFailure('timeout after successful Actions write')
        return None

    def push(self, row, repo):
        key = row['root_id']
        assert self.receipt.events[-1]['event'] == 'attempt'
        assert self.receipt.events[-1]['operation'] == 'create_ref'
        self.mutations.append((key, 'push'))
        if self.conflict_race:
            self.states[key].update(ref_state='conflicting', commit='c' * 40)
            raise ValueError('Creation-only lease rejected concurrent ref')
        if self.push_failure:
            raise ValueError('Transport failure before remote write')
        self.states[key].update(ref_state='exact', commit=row['proposed_commit'], tree=row['proposed_tree'])
        if self.unexpected_run:
            self.states[key]['runs'] = [{'id': 1, 'status': 'completed', 'head_sha': row['proposed_commit'],
                                       'head_branch': promotion.TARGET_REF.removeprefix('refs/heads/')}]
        if self.push_timeout:
            raise promotion.CommandFailure('timeout after successful ref creation')
        return 'synthetic bounded creation response'


class PromotionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ambisgis-promotion-test-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve()
        self.plan = json.loads(promotion.PLAN.read_text())
        self.rows = deepcopy(self.plan['repositories'])
        self.findings = {r['root_id']: {k: r[k] for k in
                         ('root_id', 'repository', 'repository_id', 'proposed_commit', 'proposed_tree')}
                         for r in self.rows}
        for finding in self.findings.values():
            finding.update(disposition='publishable', basis='Synthetic test publication finding', evidence=['test-fixture'])
        self.roots = {r['root_id']: {'id': r['root_id'], 'repository': r['repository'],
                      'repository_id': r['repository_id'], 'commit': r['proposed_commit'],
                      'tree': r['proposed_tree'], 'relative_path': 'repos/' + r['root_id']}
                      for r in self.rows}
        (self.path / 'repos').mkdir()
        for key in self.roots:
            (self.path / 'repos' / key).mkdir()
        self.receipt = MemoryReceipt()
        self.github = FakeGitHub(self.rows, self.receipt)

    def execute(self, *, apply=True, only=('postgresql',), check=None):
        return promotion.promote(self.rows, {}, self.findings, self.path, self.roots,
                                 self.github, self.receipt, apply=apply, only=only,
                                 local_check=check or (lambda *args: {'verified': True}))

    def make_auth(self):
        body = 'Synthetic owner authorization fixture.'
        return {'schema_version': 1, 'plan_sha256': promotion.PLAN_SHA256,
                'body_sha256': promotion.digest_bytes(body.encode()),
                'comment': {'id': promotion.COMMENT_ID, 'html_url': promotion.COMMENT_URL,
                            'user': {'login': promotion.OWNER, 'id': promotion.OWNER_ID},
                            'created_at': promotion.COMMENT_DATE, 'updated_at': promotion.COMMENT_DATE, 'body': body}}


class PromotionStateTests(PromotionCase):
    def test_default_preflight_proposes_bounded_writes_without_mutations(self):
        results, writes = self.execute(apply=False)
        self.assertEqual(results, {'postgresql': 'ready'})
        self.assertEqual(writes, {'settings': 0, 'source_refs': 0})
        self.assertEqual(self.github.mutations, [])
        result = next(e for e in self.receipt.events if e['event'] == 'result')
        self.assertEqual(result['proposed_settings_writes'], 1)
        self.assertEqual(result['proposed_source_writes'], 1)

    def test_apply_creates_once_then_unchanged_replay_is_zero_writes(self):
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'created-or-reconciled')
        self.assertEqual(writes, {'settings': 1, 'source_refs': 1})
        self.assertEqual(self.github.mutations, [('postgresql', 'disable'), ('postgresql', 'push')])
        self.github.mutations.clear()
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'already-exact')
        self.assertEqual(writes, {'settings': 0, 'source_refs': 0})
        self.assertEqual(self.github.mutations, [])

    def test_existing_conflict_never_changes_ref_or_settings(self):
        self.github.states['postgresql']['ref_state'] = 'conflicting'
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'held')
        self.assertEqual(self.github.mutations, [])

    def test_owner_mismatch_prevents_all_mutations(self):
        self.github.authorization_failure = True
        with self.assertRaisesRegex(ValueError, 'owner mismatch'):
            self.execute()
        self.assertEqual(self.github.mutations, [])

    def test_changed_local_tree_prevents_containment_and_push(self):
        def changed(*args):
            raise ValueError('Local tree changed')
        results, writes = self.execute(check=changed)
        self.assertEqual(results['postgresql'], 'held')
        self.assertEqual(self.github.mutations, [])
        self.assertIn('Local tree changed', self.receipt.events[-2]['error'])

    def test_actions_failure_retains_before_attempt_error_and_readback_without_push(self):
        self.github.settings_failure = True
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'held')
        self.assertEqual(self.github.mutations, [('postgresql', 'disable')])
        self.assertTrue(any(e['event'] == 'before' for e in self.receipt.events))
        self.assertTrue(any(e['event'] == 'uncertain' and 'Permission denied' in e['error'] for e in self.receipt.events))
        self.assertTrue(any(e['event'] == 'reconciled' for e in self.receipt.events))

    def test_settings_timeout_reconciles_success_without_retry(self):
        self.github.settings_timeout = True
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'created-or-reconciled')
        self.assertEqual(self.github.mutations.count(('postgresql', 'disable')), 1)

    def test_push_timeout_reconciles_success_without_retry(self):
        self.github.push_timeout = True
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'created-or-reconciled')
        self.assertEqual(self.github.mutations.count(('postgresql', 'push')), 1)
        self.assertTrue(any(e['event'] == 'uncertain' and e['operation'] == 'create_ref' for e in self.receipt.events))

    def test_push_failure_is_held_and_never_blindly_retried(self):
        self.github.push_failure = True
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'held')
        self.assertEqual(self.github.mutations.count(('postgresql', 'push')), 1)
        self.assertEqual(self.github.states['postgresql']['ref_state'], 'absent')

    def test_remote_readback_failure_preserved_then_fresh_run_reconciles(self):
        self.github.read_failure_after_push = True
        results, _ = self.execute()
        self.assertEqual(results['postgresql'], 'held')
        self.assertEqual(self.github.states['postgresql']['ref_state'], 'exact')
        self.assertIn('readback inaccessible', self.receipt.events[-2]['error'])
        self.github.read_failure_after_push = False
        self.github.mutations.clear()
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'already-exact')
        self.assertEqual(writes, {'settings': 0, 'source_refs': 0})

    def test_publication_hold_disables_authorized_actions_but_never_uploads(self):
        self.findings['postgresql'].update(disposition='held', basis='Concrete unresolved test asset')
        results, writes = self.execute()
        self.assertEqual(results['postgresql'], 'held')
        self.assertEqual(self.github.mutations, [('postgresql', 'disable')])
        self.assertIn('Concrete unresolved test asset', self.receipt.events[-2]['error'])
        self.assertFalse(self.github.states['postgresql']['actions']['enabled'])

    def test_child_publication_hold_blocks_parent_but_allows_independent_rows(self):
        self.findings['mapstore']['disposition'] = 'held'
        results, _ = self.execute(only=('postgresql', 'mapstore', 'mapstore-client'))
        self.assertEqual(results['postgresql'], 'created-or-reconciled')
        self.assertEqual(results['mapstore'], 'held')
        self.assertEqual(results['mapstore-client'], 'held')
        self.assertNotIn(('mapstore-client', 'push'), self.github.mutations)

    def test_child_push_precedes_client_parent_and_partial_replay_is_safe(self):
        results, _ = self.execute(only=('mapstore-client', 'mapstore'))
        pushes = [key for key, action in self.github.mutations if action == 'push']
        self.assertEqual(pushes, ['mapstore', 'mapstore-client'])
        self.assertEqual(results['mapstore-client'], 'created-or-reconciled')
        self.github.mutations.clear()
        results, writes = self.execute(only=('postgresql', 'mapstore', 'mapstore-client'))
        self.assertEqual(writes, {'settings': 1, 'source_refs': 1})
        self.assertEqual(results['mapstore'], 'already-exact')
        self.assertEqual(results['mapstore-client'], 'already-exact')

    def test_unresolved_executions_and_push_hooks_stop_all_mutations(self):
        for kind, value in (
            ('runs', [{'id': 7, 'status': 'in_progress'}]),
            ('hooks', [{'id': 9, 'active': True, 'events': ['push']}]),
            ('hooks', [{'id': 9, 'active': True, 'events': ['create']}]),
            ('hooks', [{'id': 9, 'active': True, 'events': ['*']}]),
        ):
            with self.subTest(kind=kind, value=value):
                self.github.states['postgresql'][kind] = value
                results, _ = self.execute()
                self.assertEqual(results['postgresql'], 'held')
                self.assertEqual(self.github.mutations, [])
                self.github.states['postgresql'][kind] = []

    def test_concurrent_conflict_and_unexpected_workflow_preserve_evidence(self):
        self.github.conflict_race = True
        results, _ = self.execute()
        self.assertEqual(results['postgresql'], 'held')
        self.assertEqual(self.github.states['postgresql']['commit'], 'c' * 40)
        self.assertEqual(self.github.mutations.count(('postgresql', 'push')), 1)
        self.github.conflict_race = False
        self.github.unexpected_run = True
        results, _ = self.execute(only=('postgis',))
        self.assertEqual(results['postgis'], 'held')
        self.assertEqual(self.github.states['postgis']['ref_state'], 'exact')
        self.assertIn('Unexpected promotion-triggered', self.receipt.events[-2]['error'])

    def test_observed_checks_and_status_automation_require_containment(self):
        for kind, value in (
            ('checks', [{'status': 'queued', 'app': {'slug': 'github-actions'}}]),
            ('checks', [{'status': 'completed', 'app': {'slug': 'external-ci'}}]),
            ('statuses', [{'state': 'pending', 'creator': {'login': 'github-actions[bot]'}}]),
            ('statuses', [{'state': 'success', 'creator': {'login': 'external-bot'}}]),
        ):
            with self.subTest(kind=kind, value=value):
                self.github.states['postgresql'][kind] = value
                results, _ = self.execute()
                self.assertEqual(results['postgresql'], 'held')
                self.assertEqual(self.github.mutations, [])
                self.github.states['postgresql'][kind] = []

    def test_unknown_subset_cannot_expand_allowlist(self):
        with self.assertRaisesRegex(ValueError, 'Unknown --only'):
            self.execute(only=('unrelated',))
        self.assertEqual(self.github.mutations, [])


class IdentityAndEvidenceTests(PromotionCase):
    def inputs_fixture(self, *, change=None):
        auth = self.make_auth()
        authorization = self.path / 'authorization.json'
        publication = self.path / 'publication.json'
        authorization.write_text(json.dumps(auth))
        findings = {'schema_version': 1, 'plan_sha256': promotion.PLAN_SHA256,
                    'repositories': list(deepcopy(self.findings).values())}
        if change:
            change(findings)
        publication.write_text(json.dumps(findings))
        run = self.path / 'fixture-run'
        run.mkdir(exist_ok=True)
        recovery = run / 'recovery.json'
        recovery.write_text(json.dumps({'roots': list(self.roots.values())}))
        return auth, authorization, publication, recovery

    def test_bound_inputs_accept_only_exact_publication_and_recovery_identities(self):
        auth, authorization, publication, recovery = self.inputs_fixture()
        with patch.object(promotion, 'COMMENT_SHA256', auth['body_sha256']), \
                patch.object(promotion, 'RECOVERY_PATH', 'fixture-run'), \
                patch.object(promotion, 'RECOVERY_SHA256', promotion.custody.sha(recovery)):
            rows, _, findings, _, roots = promotion.validate_inputs(
                promotion.PLAN, authorization, publication, promotion.custody.sha(publication), self.path)
        self.assertEqual(len(rows), 11)
        self.assertEqual(findings.keys(), roots.keys())

    def test_publication_commit_mismatch_missing_row_and_blank_basis_are_refused(self):
        mutations = [lambda value: value['repositories'][0].update(proposed_commit='0' * 40),
                     lambda value: value['repositories'].pop(),
                     lambda value: value['repositories'][0].update(basis=''),
                     lambda value: value['repositories'].append(deepcopy(value['repositories'][0]))]
        for mutation in mutations:
            auth, authorization, publication, recovery = self.inputs_fixture(change=mutation)
            with self.subTest(mutation=mutation), patch.object(promotion, 'COMMENT_SHA256', auth['body_sha256']), \
                    patch.object(promotion, 'RECOVERY_PATH', 'fixture-run'), \
                    patch.object(promotion, 'RECOVERY_SHA256', promotion.custody.sha(recovery)):
                with self.assertRaises(ValueError):
                    promotion.validate_inputs(promotion.PLAN, authorization, publication,
                                              promotion.custody.sha(publication), self.path)

    def test_publication_and_recovery_bytes_cannot_change_after_hash_binding(self):
        auth, authorization, publication, recovery = self.inputs_fixture()
        pub_sha = promotion.custody.sha(publication)
        receipt_sha = promotion.custody.sha(recovery)
        with patch.object(promotion, 'COMMENT_SHA256', auth['body_sha256']), \
                patch.object(promotion, 'RECOVERY_PATH', 'fixture-run'), \
                patch.object(promotion, 'RECOVERY_SHA256', receipt_sha):
            publication.write_text(publication.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                promotion.validate_inputs(promotion.PLAN, authorization, publication, pub_sha, self.path)
            pub_sha = promotion.custody.sha(publication)
            recovery.write_text(recovery.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                promotion.validate_inputs(promotion.PLAN, authorization, publication, pub_sha, self.path)

    def test_immutable_plan_tampering_is_rejected_before_network(self):
        changed = self.path / 'plan.json'
        changed.write_text(promotion.PLAN.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            promotion.bound_json(changed, promotion.PLAN_SHA256)

    def test_authorization_requires_fixed_identity_body_and_unchanged_timestamp(self):
        auth = self.make_auth()
        with patch.object(promotion, 'COMMENT_SHA256', auth['body_sha256']):
            promotion.authorization_identity(auth)
            for key in ('body', 'updated_at', 'id', 'html_url'):
                value = deepcopy(auth)
                value['comment'][key] = 'tampered'
                with self.subTest(key=key), self.assertRaises(ValueError):
                    promotion.authorization_identity(value)
            for key in ('login', 'id'):
                value = deepcopy(auth)
                value['comment']['user'][key] = 'wrong-owner'
                with self.subTest(key=key), self.assertRaises(ValueError):
                    promotion.authorization_identity(value)

    def test_live_comment_rechecked_not_replaced_by_local_decision(self):
        auth = self.make_auth()
        changed = deepcopy(auth['comment'])
        changed['body'] += ' revocation'
        client = promotion.GitHub()
        with patch.object(promotion, 'COMMENT_SHA256', auth['body_sha256']), patch.object(client, 'api', side_effect=[
                {'login': promotion.OWNER, 'id': promotion.OWNER_ID}, changed]):
            with self.assertRaisesRegex(ValueError, 'body changed'):
                client.authorize(auth)

    def test_receipt_is_exclusive_and_events_survive_close(self):
        destination = self.path / 'run.jsonl'
        receipt = promotion.Receipt(destination)
        receipt.emit('attempt', operation='synthetic')
        receipt.close()
        with self.assertRaises(FileExistsError):
            promotion.Receipt(destination)
        self.assertEqual(json.loads(destination.read_text())['operation'], 'synthetic')
        link = self.path / 'link'
        link.symlink_to(destination)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            promotion.Receipt(link)

    def test_api_repository_id_and_public_visibility_fail_closed(self):
        client = promotion.GitHub()
        row = self.rows[0]
        info = {'id': row['repository_id'], 'full_name': row['repository'],
                'owner': {'login': promotion.OWNER, 'id': promotion.OWNER_ID},
                'private': False, 'default_branch': row['donor_default_preserved']['name']}
        for mutation in ({'id': -1}, {'private': True}, {'full_name': 'aloerch/unrelated'}, {'default_branch': 'unexpected'}):
            with self.subTest(mutation=mutation), patch.object(client, 'api', return_value={**info, **mutation}), \
                    patch.object(client, 'transport') as transport:
                with self.assertRaises(ValueError):
                    client.snapshot(row, self.path)
                transport.assert_not_called()

    def test_api_unreadable_actions_and_hooks_are_not_empty_success(self):
        client = promotion.GitHub()
        row = self.rows[0]
        info = {'id': row['repository_id'], 'full_name': row['repository'],
                'owner': {'login': promotion.OWNER, 'id': promotion.OWNER_ID}, 'private': False,
                'default_branch': row['donor_default_preserved']['name']}
        refs = row['donor_default_preserved']['sha'] + '\trefs/heads/' + info['default_branch'] + '\n'
        for responses in ([info, {}], [info, {'enabled': False}, [{'workflow_runs': []}], ValueError('hook permission denied')]):
            with self.subTest(responses=responses), patch.object(client, 'api', side_effect=responses), \
                    patch.object(client, 'transport', return_value=refs):
                with self.assertRaises(ValueError):
                    client.snapshot(row, self.path)

    def test_transport_and_setting_operation_have_exact_bounded_arguments(self):
        row = self.rows[0]
        client = promotion.GitHub()
        with patch.object(client, 'api', return_value=None) as api:
            client.disable_actions(row)
            api.assert_called_once_with('repos/' + row['repository'] + '/actions/permissions',
                                        method='PUT', payload={'enabled': False})
        arguments = promotion.push_arguments(row, 'https://github.com/' + row['repository'] + '.git')
        self.assertEqual(arguments, ['push', '--porcelain', '--force-with-lease=' + promotion.TARGET_REF + ':',
                         'https://github.com/' + row['repository'] + '.git',
                         row['proposed_commit'] + ':' + promotion.TARGET_REF])
        self.assertFalse(set(arguments) & {'--all', '--tags', '--mirror', '--force'})


class LocalGitRaceTests(PromotionCase):
    def producer(self):
        repo = self.path / 'producer'
        repo.mkdir()
        promotion.custody.git(repo, 'init', '--template=', '--initial-branch=main')
        (repo / 'LICENSE').write_text('Synthetic source copyright and license notice\n')
        (repo / 'source.txt').write_text('base\n')
        base = self.commit(repo)
        (repo / 'source.txt').write_text('approved new implementation\n')
        selected = self.commit(repo)
        row = deepcopy(self.rows[0])
        row.update(accepted_base_commit=base, proposed_commit=selected,
                   proposed_tree=promotion.custody.git(repo, 'rev-parse', 'HEAD^{tree}').decode().strip())
        bare = self.path / 'remote.git'
        bare.mkdir()
        promotion.custody.git(bare, 'init', '--bare', '--template=')
        return repo, bare, row, base

    def commit(self, repo):
        promotion.custody.git(repo, 'add', '--all')
        promotion.custody.git(repo, '-c', 'user.name=Synthetic test', '-c', 'user.email=test@example.invalid',
                              'commit', '-m', 'Synthetic test commit')
        return promotion.custody.git(repo, 'rev-parse', 'HEAD').decode().strip()

    def test_actual_empty_lease_creates_exact_ref_and_rejects_concurrent_ancestor(self):
        repo, bare, row, base = self.producer()
        # Simulate a ref appearing after preflight at the ancestor. A normal push
        # would fast-forward it; the expected-absent lease must reject it.
        promotion.custody.git(repo, 'push', str(bare), base + ':' + promotion.TARGET_REF)
        result = subprocess.run(['git', '-C', str(repo), *promotion.push_arguments(row, str(bare))],
                                env=promotion.custody.git_environment(), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stale info', result.stdout)
        self.assertEqual(promotion.custody.git(bare, 'rev-parse', promotion.TARGET_REF).decode().strip(), base)
        other = self.path / 'empty.git'
        other.mkdir()
        promotion.custody.git(other, 'init', '--bare', '--template=')
        promotion.custody.git(repo, *promotion.push_arguments(row, str(other)))
        self.assertEqual(promotion.custody.git(other, 'rev-parse', promotion.TARGET_REF).decode().strip(), row['proposed_commit'])
        self.assertEqual(promotion.custody.git(other, 'for-each-ref', '--format=%(refname)').decode().splitlines(),
                         [promotion.TARGET_REF])

    def test_local_verification_detects_modified_tree_and_changed_commit(self):
        repo, _, row, base = self.producer()
        promotion.verify_local(repo, row, {}, self.path)
        wrong = {**row, 'proposed_tree': '0' * 40}
        with self.assertRaisesRegex(ValueError, 'Local tree changed'):
            promotion.verify_local(repo, wrong, {}, self.path)
        (repo / 'source.txt').write_text('unapproved working change\n')
        with self.assertRaisesRegex(ValueError, 'dirty'):
            promotion.verify_local(repo, row, {}, self.path)
        self.commit(repo)
        with self.assertRaisesRegex(ValueError, 'Local commit changed'):
            promotion.verify_local(repo, row, {}, self.path)

    def test_transport_rejects_local_url_rewrite_and_recursive_push_configuration(self):
        repo, _, row, _ = self.producer()
        for key, value in (('url.https://example.invalid/.pushInsteadOf', 'https://github.com/'),
                           ('push.recurseSubmodules', 'on-demand'),
                           ('credential.helper', '!malicious helper'),
                           ('http.proxy', 'https://example.invalid/')):
            with self.subTest(key=key):
                promotion.custody.git(repo, 'config', '--local', key, value)
                with self.assertRaisesRegex(ValueError, 'Unexpected local Git transport'):
                    promotion.verify_local(repo, row, {}, self.path)
                client = promotion.GitHub()
                with patch.object(client, 'command') as command:
                    with self.assertRaisesRegex(ValueError, 'Unexpected local Git transport'):
                        client.transport(repo, 'push')
                    command.assert_not_called()
                promotion.custody.git(repo, 'config', '--local', '--unset', key)

    def test_local_verification_checks_actual_delta_prerequisites(self):
        repo, _, row, base = self.producer()
        bundle = self.path / 'delta.bundle'
        promotion.custody.git(repo, 'bundle', 'create', str(bundle), 'HEAD', '^' + base)
        record = {'path': 'delta.bundle', 'sha256': promotion.custody.sha(bundle),
                  'bytes': bundle.stat().st_size, 'prerequisites': [base]}
        promotion.verify_local(repo, row, {'retained_product_bundles': [record]}, self.path)
        record['prerequisites'] = ['0' * 40]
        with self.assertRaisesRegex(ValueError, 'prerequisites changed'):
            promotion.verify_local(repo, row, {'retained_product_bundles': [record]}, self.path)


if __name__ == '__main__':
    unittest.main()
