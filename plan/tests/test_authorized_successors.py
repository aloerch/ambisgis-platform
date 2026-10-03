"""Creation-only successor delivery guards; real local Git race coverage."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'tools/publish_authorized_successors.py'
spec = importlib.util.spec_from_file_location('authorized_successors_tests', MODULE)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class Journal:
    def __init__(self):
        self.events = []

    def emit(self, event, **fields):
        self.events.append({'event': event, **deepcopy(fields)})


class Remote:
    def __init__(self, rows, journal):
        self.rows, self.journal = rows, journal
        self.states = {r['root_id']: {
            'repository': r['repository'], 'repository_id': r['repository_id'],
            'default': {'name': r['default_to_preserve']['name'],
                        'sha': r['default_to_preserve']['commit']},
            'actions': deepcopy(r['actions_to_preserve']),
            'refs': {'refs/heads/' + r['default_to_preserve']['name']: r['default_to_preserve']['commit']},
            'runs': [], 'hooks': [], 'checks': [], 'statuses': [],
        } for r in rows}
        self.writes = []
        self.timeout = False
        self.race = False
        self.changed_default = False
        self.changed_actions = False
        self.new_run = False

    def authorize(self, path):
        return {'login': 'aloerch', 'id': 15285626}

    def companion(self):
        return {'verified': True}

    def snapshot(self, row, repo):
        return deepcopy(self.states[row['root_id']])

    def create(self, row, repo, ref):
        assert self.journal.events[-1]['event'] == 'attempt'
        self.writes.append((row['root_id'], ref))
        state = self.states[row['root_id']]
        if self.race:
            state['refs'][ref] = 'f' * 40
            raise ValueError('concurrent collision')
        state['refs'][ref] = row['proposed_commit']
        if self.changed_default:
            state['refs']['refs/heads/' + state['default']['name']] = 'e' * 40
        if self.changed_actions:
            state['actions']['sha_pinning_required'] = True
        if self.new_run:
            state['runs'].append({'id': 99, 'status': 'completed', 'head_sha': row['proposed_commit'],
                                  'head_branch': ref.removeprefix('refs/heads/')})
        if self.timeout:
            raise ValueError('ambiguous response after create')
        return 'created'


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.rows = delivery.rows()
        self.journal = Journal()
        self.remote = Remote(self.rows, self.journal)

    def run_delivery(self, apply=True):
        return delivery.publish(self.rows, Path('/unused'), Path('/unused'), self.remote,
                                self.journal, apply=apply,
                                local_check=lambda row, workspace: {'path': '/unused', 'verified': True})

    def test_read_only_preflight_and_idempotent_apply(self):
        self.assertTrue(self.run_delivery(False))
        self.assertEqual(self.remote.writes, [])
        self.assertTrue(self.run_delivery())
        self.assertEqual(len(self.remote.writes), 4)
        self.assertTrue(self.run_delivery())
        self.assertEqual(len(self.remote.writes), 4)

    def test_collision_in_second_root_prevents_all_writes(self):
        row = self.rows[1]
        self.remote.states[row['root_id']]['refs'][row['destinations'][1]['ref']] = 'f' * 40
        self.assertFalse(self.run_delivery())
        self.assertEqual(self.remote.writes, [])

    def test_enabled_actions_wrong_identity_and_default_fail_closed(self):
        for mutation in ('actions', 'repository_id', 'default'):
            with self.subTest(mutation=mutation):
                self.setUp()
                state = self.remote.states[self.rows[0]['root_id']]
                if mutation == 'actions': state['actions']['enabled'] = True
                elif mutation == 'repository_id': state['repository_id'] = 1
                else: state['default']['sha'] = 'e' * 40
                self.assertFalse(self.run_delivery())
                self.assertEqual(self.remote.writes, [])

    def test_external_automation_and_pending_runs_prevent_writes(self):
        for kind in ('hooks', 'runs', 'checks', 'statuses'):
            with self.subTest(kind=kind):
                self.setUp()
                self.remote.states[self.rows[0]['root_id']][kind] = {
                    'hooks': [{'active': True, 'events': ['push']}],
                    'runs': [{'status': 'queued'}],
                    'checks': [{'status': 'completed', 'app': {'slug': 'outside-app'}}],
                    'statuses': [{'state': 'success', 'creator': {'login': 'outside-app'}}],
                }[kind]
                self.assertFalse(self.run_delivery())
                self.assertEqual(self.remote.writes, [])

    def test_ambiguous_success_reconciles_without_retry(self):
        self.remote.timeout = True
        self.assertTrue(self.run_delivery())
        self.assertEqual(len(self.remote.writes), 4)
        self.assertEqual(sum(x['event'] == 'uncertain' for x in self.journal.events), 4)

    def test_race_settings_drift_or_triggered_run_stops_after_first_attempt(self):
        for attribute in ('race', 'changed_default', 'changed_actions', 'new_run'):
            with self.subTest(attribute=attribute):
                self.setUp()
                setattr(self.remote, attribute, True)
                self.assertFalse(self.run_delivery())
                self.assertEqual(len(self.remote.writes), 1)

    def test_local_integrity_failure_prevents_any_write(self):
        with patch.object(delivery, 'rows', return_value=self.rows):
            def bad(*args): raise ValueError('source identity changed')
            self.assertFalse(delivery.publish(self.rows, Path('/unused'), Path('/unused'),
                             self.remote, self.journal, apply=True, local_check=bad))
        self.assertEqual(self.remote.writes, [])

    def test_new_review_ref_deleted_or_moved_between_steps_is_held(self):
        for replacement in (None, 'f' * 40):
            with self.subTest(replacement=replacement):
                self.setUp()
                original_snapshot = self.remote.snapshot
                reads_after_first_write = 0
                def drift(row, repo):
                    nonlocal reads_after_first_write
                    if len(self.remote.writes) == 1:
                        reads_after_first_write += 1
                        if reads_after_first_write == 2:
                            refs = self.remote.states[row['root_id']]['refs']
                            ref = row['destinations'][0]['ref']
                            if replacement is None: del refs[ref]
                            else: refs[ref] = replacement
                    return original_snapshot(row, repo)
                self.remote.snapshot = drift
                self.assertFalse(self.run_delivery())
                self.assertEqual(len(self.remote.writes), 1)

    def test_final_readback_detects_earlier_root_drift(self):
        original_snapshot = self.remote.snapshot
        def drift(row, repo):
            if len(self.remote.writes) == 4 and row['root_id'] == self.rows[0]['root_id']:
                del self.remote.states[row['root_id']]['refs'][row['destinations'][0]['ref']]
            return original_snapshot(row, repo)
        self.remote.snapshot = drift
        self.assertFalse(self.run_delivery())
        self.assertEqual(len(self.remote.writes), 4)

    def test_unapproved_row_is_rejected(self):
        self.rows[0]['proposed_commit'] = 'e' * 40
        self.assertFalse(self.run_delivery())
        self.assertEqual(self.remote.writes, [])

    def test_authority_hash_and_principal_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'authority.md'; path.write_text('not owner delegation')
            with self.assertRaisesRegex(ValueError, 'delegation'):
                delivery.GitHub().authorize(path)
        with patch.object(delivery.P.custody, 'sha', return_value=delivery.AUTH_SHA), \
             patch.object(delivery.GitHub, 'api', return_value={'login': 'someone-else', 'id': 1}):
            with self.assertRaisesRegex(ValueError, 'owner'):
                delivery.GitHub().authorize(Path('/unused'))

    def test_transport_rejects_rewrite_and_allows_bare_initialization(self):
        with patch.object(delivery.P.custody, 'git', return_value=b'core.bare=true\ncore.filemode=true\ncore.repositoryformatversion=0\n'):
            delivery.transport_configuration(Path('/unused'))
        with patch.object(delivery.P.custody, 'git', return_value=b'url.https://other.invalid.insteadof=https://github.com\n'):
            with self.assertRaises(ValueError): delivery.transport_configuration(Path('/unused'))

    def test_creation_lease_rejects_existing_ancestor_on_real_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source'; remote = root / 'remote.git'
            def git(*args, cwd=None, ok=True):
                result = subprocess.run(['git', *map(str, args)], cwd=cwd, capture_output=True, text=True)
                if ok: self.assertEqual(result.returncode, 0, result.stderr)
                return result
            git('init', '--bare', remote); git('init', source)
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                'commit', '--allow-empty', '-m', 'base', cwd=source)
            base = git('rev-parse', 'HEAD', cwd=source).stdout.strip()
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                'commit', '--allow-empty', '-m', 'child', cwd=source)
            commit = git('rev-parse', 'HEAD', cwd=source).stdout.strip()
            ref = self.rows[0]['destinations'][0]['ref']
            git('push', remote, base + ':' + ref, cwd=source)
            args = delivery.creation_arguments(commit, ref, str(remote))
            result = git(*args, cwd=source, ok=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(git('rev-parse', ref, cwd=remote).stdout.strip(), base)
            absent = self.rows[1]['destinations'][0]['ref']
            git(*delivery.creation_arguments(commit, absent, str(remote)), cwd=source)
            self.assertEqual(git('rev-parse', absent, cwd=remote).stdout.strip(), commit)


if __name__ == '__main__':
    unittest.main()
