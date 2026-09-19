"""Adversarial importer tests against a stateful, in-memory GitHub boundary.

All IDs and URLs below are synthetic test fixtures. These tests establish local
provisioning behavior only; they are not evidence of any live GitHub action.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.bootstrap_repositories import BootstrapError
from tools import bootstrap_github_project as importer

ROOT = Path(__file__).resolve().parent.parent


class SimulatedInterruption(BaseException):
    """Process death which ordinary network recovery must not swallow."""


class FakeAPI:
    """Return detached reads, reject dry-run writes, and inject lost replies."""

    def __init__(self, manifest):
        self.read_only = True
        self.user = {'login': 'aloerch', 'type': 'User', 'id': 901, 'node_id': 'TEST_USER'}
        self.repos = {}
        self.issue_store = {}
        self.label_store = {}
        for n, spec in enumerate(manifest['repositories'], 100):
            full = 'aloerch/' + spec['name']
            repo = {'id': n, 'node_id': 'TEST_REPO_' + str(n), 'full_name': full,
                    'owner': copy.deepcopy(self.user), 'private': False, 'fork': spec['kind'] == 'fork',
                    'archived': False, 'disabled': False, 'default_branch': 'main'}
            if spec['upstream']:
                repo['parent'] = {'full_name': spec['upstream']}
            self.repos[full] = repo
            self.issue_store[full] = []
            self.label_store[full] = []
        self.project_store = {}
        self.edge_store = {}
        self.calls = []
        self.writes = []
        self.next_id = 1000
        self.fail_before = {}
        self.fail_after = {}
        self.read_failures = {}
        self.support_views = False
        self.ignore_field_names = set()

    def _id(self, prefix):
        self.next_id += 1
        return prefix + str(self.next_id)

    def _read(self, operation, value):
        self.calls.append(('read', operation))
        failure = self.read_failures.pop(operation, None)
        if failure:
            raise failure
        return copy.deepcopy(value)

    def _begin(self, operation):
        if self.read_only:
            raise AssertionError('Mutation attempted while read_only: ' + operation)
        self.calls.append(('write', operation))
        self.writes.append(operation)
        failure = self.fail_before.pop(operation, None)
        if failure:
            raise failure

    def _end(self, operation, value=None):
        failure = self.fail_after.pop(operation, None)
        if failure:
            raise failure
        return copy.deepcopy(value)

    def identity(self):
        return self._read('identity', self.user)

    def repository(self, full):
        return self._read('repository', self.repos[full])

    def capabilities(self):
        return self._read('capabilities', {'create_view': self.support_views,
            'mutations': ['createProjectV2', 'updateProjectV2', 'linkProjectV2ToRepository',
                          'createProjectV2Field', 'addProjectV2ItemById', 'updateProjectV2ItemFieldValue'],
            'field_types': ['TEXT', 'DATE', 'SINGLE_SELECT'],
            'project_items_archived_states': True})

    def projects(self, owner):
        assert owner == 'aloerch'
        return self._read('projects', list(self.project_store.values()))

    def project(self, project_id):
        return self._read('project', self.project_store[project_id])

    def items(self, project_id):
        return self._read('items', self.project_store[project_id]['items'])

    def item(self, item_id):
        return self._read('item', next(i for p in self.project_store.values() for i in p['items'] if i['id'] == item_id))

    def issues(self, full):
        return self._read('issues', self.issue_store[full])

    def issue(self, full, number):
        return self._read('issue', next(i for i in self.issue_store[full] if i['number'] == number))

    def labels(self, full):
        return self._read('labels', self.label_store[full])

    def dependencies(self, full, number):
        return self._read('dependencies', [{'id': i} for i in self.edge_store.get((full, number), [])])

    def create_project(self, owner_id, title):
        self._begin('create_project')
        assert owner_id == self.user['node_id']
        result = {'id': self._id('TEST_PROJECT_'), 'number': 42,
                  'url': 'https://github.com/users/aloerch/projects/42', 'title': title,
                  'owner': {'login': 'aloerch', 'id': owner_id}, 'public': False, 'closed': False,
                  'shortDescription': '', 'fields': [], 'items': [], 'repositories': [], 'views': [], 'viewerCanUpdate': True}
        self.project_store[result['id']] = result
        return self._end('create_project', result)

    def update_project(self, project_id, public, description):
        self._begin('update_project')
        self.project_store[project_id].update(public=public, shortDescription=description)
        return self._end('update_project')

    def link_repository(self, project_id, repo_id):
        self._begin('link_repository')
        self.project_store[project_id]['repositories'].append({'id': repo_id})
        return self._end('link_repository')

    def create_field(self, project_id, spec):
        self._begin('create_field')
        field = {'id': self._id('TEST_FIELD_'), 'name': spec['name'], 'dataType': spec['type']}
        if spec['type'] == 'SINGLE_SELECT':
            field['options'] = [{'id': self._id('TEST_OPTION_'), 'name': name} for name in spec['options']]
        self.project_store[project_id]['fields'].append(field)
        return self._end('create_field', field)

    def create_label(self, full, label):
        self._begin('create_label')
        self.label_store[full].append({'name': label})
        return self._end('create_label')

    def create_issue(self, full, title, body, labels):
        self._begin('create_issue')
        issue = self.insert_issue(full, title, body, labels)
        return self._end('create_issue', issue)

    def insert_issue(self, full, title, body, labels=()):
        number = len(self.issue_store[full]) + 1
        node_id = self._id('TEST_ISSUE_')
        result = {'id': self.next_id, 'node_id': node_id, 'number': number, 'title': title,
                  'html_url': f'https://github.com/{full}/issues/{number}', 'body': body,
                  'state': 'open', 'assignees': [], 'labels': [{'name': x} for x in labels]}
        self.issue_store[full].append(result)
        return result

    def update_issue_body(self, full, number, body):
        self._begin('update_issue_body')
        next(i for i in self.issue_store[full] if i['number'] == number)['body'] = body
        return self._end('update_issue_body')

    def add_item(self, project_id, issue_id):
        self._begin('add_item')
        item = {'id': self._id('TEST_ITEM_'), 'content': {'id': issue_id}, 'values': {}, 'isArchived': False}
        self.project_store[project_id]['items'].append(item)
        return self._end('add_item', item)

    def set_field(self, project_id, item_id, field, value):
        self._begin('set_field')
        item = next(i for i in self.project_store[project_id]['items'] if i['id'] == item_id)
        if field['name'] not in self.ignore_field_names:
            item['values'][field['name']] = value
        return self._end('set_field')

    def add_dependency(self, full, number, issue_id):
        self._begin('add_dependency')
        self.edge_store.setdefault((full, number), []).append(issue_id)
        return self._end('add_dependency')

    def create_view(self, project_id, spec):
        self._begin('create_view')
        view = {'id': self._id('TEST_VIEW_'), 'name': spec['name'], 'layout': spec['layout'] + '_LAYOUT'}
        self.project_store[project_id]['views'].append(view)
        return self._end('create_view', view)


class ProjectImporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'plan'
        self.root.mkdir()
        for name in ('repositories.json', 'project.json', 'backlog.json', 'requirements.json',
                     'SOURCES.md', 'README.md', 'AGENTS.md', 'CODEX_START_PROMPT.md', 'DECISIONS.md', 'STATUS.md'):
            shutil.copyfile(ROOT / name, self.root / name)
        (self.root / 'docs').mkdir()
        self.manifest, self.project_spec, self.seed = importer.validate_inputs(self.root)
        self.api = FakeAPI(self.manifest)
        self.repo_receipt = self.base / 'repository-receipt.json'
        self.receipt = self.base / 'project-receipt.json'
        self.repo_data = {'receipt_version': 1, 'owner': 'aloerch', 'managed_repositories': {
            full: {'id': repo['id'], 'status': 'ready'} for full, repo in self.api.repos.items()}}
        self.repo_receipt.write_text(json.dumps(self.repo_data))

    def run_import(self, apply=False):
        self.api.read_only = True
        return importer.execute(self.api, self.root, self.repo_receipt, self.receipt, apply=apply)

    def seed_complete(self):
        """Create a complete synthetic existing state without invoking importer writes."""
        api = self.api
        api.read_only = False
        project = api.create_project(api.user['node_id'], self.project_spec['title'])
        pid = project['id']
        api.update_project(pid, True, importer.PROJECT_MARKER)
        for repo in api.repos.values():
            api.link_repository(pid, repo['node_id'])
        fields = {spec['name']: api.create_field(pid, spec) for spec in self.project_spec['fields']}
        issues = {}
        for spec in self.seed['issues']:
            issues[spec['task_id']] = api.insert_issue(spec['repository'], spec['title'], spec['body'], spec['labels'])
            for label in spec['labels']:
                if label not in {x['name'] for x in api.label_store[spec['repository']]}:
                    api.label_store[spec['repository']].append({'name': label})
        data = {'receipt_version': 1, 'owner': 'aloerch', 'owner_id': api.user['id'],
                'owner_node_id': api.user['node_id'],
                'repositories': {full: {'id': repo['id'], 'node_id': repo['node_id']} for full, repo in api.repos.items()},
                'project': {key: project[key] for key in ('id', 'number', 'url')},
                'issues': {}, 'pending': {}, 'views': {}}
        for spec in self.seed['issues']:
            issue = issues[spec['task_id']]
            issue['body'] = importer.desired_body(spec, issues)
            item = api.add_item(pid, issue['node_id'])
            for name, value in spec['initial_fields_only'].items():
                api.set_field(pid, item['id'], fields[name], value)
            record = importer.record_issue(issue, spec)
            record['item_id'] = item['id']
            data['issues'][spec['task_id']] = record
            api.edge_store[(spec['repository'], issue['number'])] = [issues[d]['id'] for d in spec['dependency_task_ids']]
        self.receipt.write_text(json.dumps(data))
        api.read_only = True
        api.writes.clear()
        api.calls.clear()
        self.data, self.issues, self.pid = data, issues, pid
        return api.project_store[pid]

    def assert_preflight_rejects(self):
        with self.assertRaises(BootstrapError):
            self.run_import(apply=True)
        self.assertEqual(self.api.writes, [])

    def test_dry_run_full_plan_does_not_mutate_or_write_receipt(self):
        before = set(self.base.iterdir())
        report = self.run_import()
        self.assertEqual(report['mode'], 'dry-run')
        self.assertEqual(report['mutations'], 0)
        self.assertEqual(len([x for x in report['operations'] if x['action'] == 'create_issue']), 66)
        self.assertEqual(len([x for x in report['operations'] if x['action'] == 'link_repository']), 15)
        self.assertEqual(self.api.writes, [])
        self.assertEqual(set(self.base.iterdir()), before)

    def test_full_apply_then_unchanged_rerun_has_no_remote_mutations(self):
        report = self.run_import(apply=True)
        self.assertEqual(report['verified_issues'], 66)
        expected_edges = sum(len(i['dependency_task_ids']) for i in self.seed['issues'])
        self.assertEqual(report['verified_dependency_edges'], expected_edges)
        self.assertEqual(self.api.writes.count('create_project'), 1)
        self.assertEqual(self.api.writes.count('create_issue'), 66)
        self.assertEqual(self.api.writes.count('add_item'), 66)
        self.assertEqual(len(json.loads(self.receipt.read_text())['issues']), 66)
        self.api.writes.clear()
        rerun = self.run_import(apply=True)
        self.assertEqual(rerun['verified_issues'], 66)
        self.assertEqual(self.api.writes, [])

    def test_human_discussion_assignment_closed_state_and_live_progress_preserved(self):
        project = self.seed_complete()
        issue = self.issues['FND-01']
        issue.update(body='Owner preface\n' + issue['body'] + '\nActual human evidence',
                     state='closed', assignees=[{'login': 'reviewer'}])
        item = next(i for i in project['items'] if i['content']['id'] == issue['node_id'])
        item['values'].update({'Delivery': 'In review', 'Priority': 'Low', 'Start date': '2026-09-19',
                               'Target date': '2026-10-01', 'Evidence': 'human evidence'})
        before_issue, before_item = copy.deepcopy(issue), copy.deepcopy(item)
        self.run_import(apply=True)
        self.assertEqual(issue, before_issue)
        self.assertEqual(item, before_item)
        self.assertEqual(self.api.writes, [])

    def test_checked_acceptance_conflicts_without_erasing_human_progress(self):
        self.seed_complete()
        issue = self.issues['FND-01']
        issue['body'] = issue['body'].replace('- [ ] ', '- [x] ', 1)
        before = issue['body']
        self.assert_preflight_rejects()
        self.assertEqual(issue['body'], before)
        self.assertEqual(self.api.writes, [])

    def test_spec_update_only_changes_managed_content_preserving_human_evidence(self):
        self.seed_complete()
        issue = self.issues['FND-01']
        issue['body'] = 'Owner preface\n' + issue['body'] + '\nHuman evidence stays here.'
        backlog_path = self.root / 'backlog.json'
        backlog = json.loads(backlog_path.read_text())
        task = next(t for t in backlog['tasks'] if t['id'] == 'FND-01')
        task['deliverables'].append('Additional reviewed specification detail')
        backlog_path.write_text(json.dumps(backlog))
        self.run_import(apply=True)
        self.assertIn('Additional reviewed specification detail', issue['body'])
        self.assertTrue(issue['body'].startswith('Owner preface\n'))
        self.assertTrue(issue['body'].endswith('\nHuman evidence stays here.'))
        self.assertEqual(self.api.writes, ['update_issue_body'])

    def test_unexpected_edit_inside_managed_block_fails_before_writes(self):
        self.seed_complete()
        issue = self.issues['FND-01']
        issue['body'] = issue['body'].replace('### Deliverables', '### Human changed requirements')
        self.assert_preflight_rejects()

    def test_wrong_authenticated_owner_is_rejected_before_writes(self):
        self.api.user['login'] = 'unrelated-owner'
        self.assert_preflight_rejects()

    def test_repository_receipt_id_mismatch_is_rejected_before_writes(self):
        self.repo_data['managed_repositories']['aloerch/ambisgis-platform']['id'] += 1
        self.repo_receipt.write_text(json.dumps(self.repo_data))
        self.assert_preflight_rejects()

    def test_repository_not_ready_is_rejected_before_writes(self):
        self.repo_data['managed_repositories']['aloerch/ambisgis-platform']['status'] = 'created_pending_readiness'
        self.repo_receipt.write_text(json.dumps(self.repo_data))
        self.assert_preflight_rejects()

    def test_missing_permission_is_not_project_absence(self):
        self.api.read_failures['projects'] = BootstrapError('403 missing project permission')
        self.assert_preflight_rejects()
        self.assertFalse(self.receipt.exists())

    def test_open_and_closed_unreceipted_project_collisions_stop(self):
        for closed in (False, True):
            with self.subTest(closed=closed):
                self.api.project_store = {'COLLISION': {'id': 'COLLISION', 'title': importer.PROJECT_TITLE,
                                                      'shortDescription': '', 'closed': closed}}
                self.assert_preflight_rejects()

    def test_marker_collision_with_different_title_stops(self):
        self.api.project_store['COLLISION'] = {'id': 'COLLISION', 'title': 'Renamed project',
                                             'shortDescription': importer.PROJECT_MARKER, 'closed': True}
        self.assert_preflight_rejects()

    def test_second_matching_project_conflicts_with_recorded_project(self):
        self.seed_complete()
        self.api.project_store['OTHER'] = {'id': 'OTHER', 'title': importer.PROJECT_TITLE, 'shortDescription': ''}
        self.assert_preflight_rejects()

    def test_task_title_without_marker_is_not_adopted(self):
        spec = self.seed['issues'][0]
        self.api.insert_issue(spec['repository'], spec['title'], 'Human issue with similar title')
        self.assert_preflight_rejects()

    def test_duplicate_markers_across_issues_are_rejected(self):
        self.seed_complete()
        spec = self.seed['issues'][0]
        self.api.insert_issue(spec['repository'], 'Another issue', spec['body'])
        self.assert_preflight_rejects()

    def test_duplicate_markers_inside_body_are_rejected(self):
        self.seed_complete()
        self.issues['FND-01']['body'] += '\n<!-- ambisgis:task:FND-01 -->'
        self.assert_preflight_rejects()

    def test_marker_in_wrong_repository_is_rejected(self):
        spec = self.seed['issues'][0]
        wrong = next(full for full in self.api.repos if full != spec['repository'])
        self.api.insert_issue(wrong, spec['title'], spec['body'])
        self.assert_preflight_rejects()

    def test_recorded_issue_wrong_url_rejected(self):
        self.seed_complete()
        self.issues['FND-01']['html_url'] = 'https://github.com/aloerch/weaveatlas/issues/1'
        self.assert_preflight_rejects()

    def test_field_type_mismatch_stops_before_writes(self):
        project = self.seed_complete()
        next(f for f in project['fields'] if f['name'] == 'Delivery')['dataType'] = 'TEXT'
        self.assert_preflight_rejects()

    def test_field_missing_option_stops_before_writes(self):
        project = self.seed_complete()
        field = next(f for f in project['fields'] if f['name'] == 'Delivery')
        field['options'] = [o for o in field['options'] if o['name'] != 'In review']
        self.assert_preflight_rejects()

    def test_duplicate_project_items_stop_before_writes(self):
        project = self.seed_complete()
        item = copy.deepcopy(project['items'][0])
        item['id'] = 'OTHER_ITEM'
        project['items'].append(item)
        self.assert_preflight_rejects()

    def test_lost_mutation_responses_recover_without_duplicate_creates(self):
        for operation in ('create_issue', 'create_field', 'add_item', 'add_dependency', 'create_label', 'update_issue_body'):
            self.api.fail_after[operation] = RuntimeError('Response lost after server commit')
        report = self.run_import(apply=True)
        self.assertEqual(report['verified_issues'], 66)
        self.assertEqual(self.api.writes.count('create_issue'), 66)
        self.assertEqual(self.api.writes.count('add_item'), 66)
        self.assertEqual(self.api.writes.count('create_field'), len(self.project_spec['fields']))
        self.assertEqual(self.api.writes.count('add_dependency'), sum(len(s['dependency_task_ids']) for s in self.seed['issues']))

    def test_lost_project_response_stops_and_records_intent_without_duplicate(self):
        self.api.fail_after['create_project'] = RuntimeError('Response lost after project creation')
        with self.assertRaises(RuntimeError):
            self.run_import(apply=True)
        data = json.loads(self.receipt.read_text())
        self.assertIn('project', data['pending'])
        self.assertEqual(len(self.api.project_store), 1)
        self.api.writes.clear()
        self.assert_preflight_rejects()
        self.assertEqual(len(self.api.project_store), 1)

    def test_interrupted_issue_create_resumes_from_persisted_intent(self):
        self.api.fail_after['create_issue'] = SimulatedInterruption()
        with self.assertRaises(SimulatedInterruption):
            self.run_import(apply=True)
        self.assertEqual(sum(map(len, self.api.issue_store.values())), 1)
        report = self.run_import(apply=True)
        self.assertEqual(report['verified_issues'], 66)
        self.assertEqual(self.api.writes.count('create_issue'), 66)

    def test_interrupted_initialization_dry_run_lists_remaining_field_writes(self):
        self.api.fail_before['set_field'] = SimulatedInterruption()
        with self.assertRaises(SimulatedInterruption):
            self.run_import(apply=True)
        spec = self.seed['issues'][0]
        receipt_before = self.receipt.read_bytes()
        self.api.writes.clear()

        report = self.run_import()

        operations = [op for op in report['operations']
                      if op['action'] == 'set_initial_field' and op['task_id'] == spec['task_id']]
        self.assertEqual({op['field']: op['value'] for op in operations}, spec['initial_fields_only'])
        self.assertFalse(any(op['action'] == 'add_item' and op['task_id'] == spec['task_id']
                             for op in report['operations']))
        self.assertEqual(self.api.writes, [])
        self.assertEqual(self.receipt.read_bytes(), receipt_before)

    def test_resume_dry_run_omits_existing_human_field_values(self):
        self.api.fail_before['set_field'] = SimulatedInterruption()
        with self.assertRaises(SimulatedInterruption):
            self.run_import(apply=True)
        spec = self.seed['issues'][0]
        item = next(iter(self.api.project_store.values()))['items'][0]
        human_values = {'Delivery': 'In progress', 'Priority': 'Low'}
        item['values'].update(human_values)
        receipt_before = self.receipt.read_bytes()
        self.api.writes.clear()

        report = self.run_import()

        operations = [op for op in report['operations']
                      if op['action'] == 'set_initial_field' and op['task_id'] == spec['task_id']]
        self.assertEqual({op['field']: op['value'] for op in operations},
                         {name: value for name, value in spec['initial_fields_only'].items()
                          if name not in human_values})
        self.assertEqual(item['values'], human_values)
        self.assertEqual(self.api.writes, [])
        self.assertEqual(self.receipt.read_bytes(), receipt_before)
        self.run_import(apply=True)
        for name, value in human_values.items():
            self.assertEqual(item['values'][name], value)

    def test_interrupted_initialization_preserves_human_values_on_resume(self):
        self.api.fail_before['set_field'] = SimulatedInterruption()
        with self.assertRaises(SimulatedInterruption):
            self.run_import(apply=True)
        project = next(iter(self.api.project_store.values()))
        item = project['items'][0]
        item['values']['Delivery'] = 'In progress'
        item['values']['Priority'] = 'Low'
        report = self.run_import(apply=True)
        self.assertEqual(report['verified_issues'], 66)
        self.assertEqual(item['values']['Delivery'], 'In progress')
        self.assertEqual(item['values']['Priority'], 'Low')
        self.assertEqual(json.loads(self.receipt.read_text())['pending'], {})

    def test_interrupted_body_update_is_reconciled_using_pending_hash(self):
        self.api.fail_after['update_issue_body'] = SimulatedInterruption()
        with self.assertRaises(SimulatedInterruption):
            self.run_import(apply=True)
        report = self.run_import(apply=True)
        self.assertEqual(report['verified_issues'], 66)
        self.assertEqual(json.loads(self.receipt.read_text())['pending'], {})

    def test_nonexistent_initial_field_readback_prevents_completion(self):
        self.api.ignore_field_names.add('Delivery')
        with self.assertRaises(BootstrapError):
            self.run_import(apply=True)

    def test_final_verification_rejects_missing_dependency(self):
        self.seed_complete()
        dependent = next(s for s in self.seed['issues'] if s['dependency_task_ids'])
        number = self.issues[dependent['task_id']]['number']
        self.api.edge_store[(dependent['repository'], number)] = []
        with self.assertRaises(BootstrapError):
            importer.verify_completion(self.api, self.project_spec, self.seed, self.data)

    def test_final_verification_rejects_missing_repository_link(self):
        project = self.seed_complete()
        project['repositories'].pop()
        with self.assertRaises(BootstrapError):
            importer.verify_completion(self.api, self.project_spec, self.seed, self.data)

    def test_final_verification_rejects_project_closed_during_import(self):
        project = self.seed_complete()
        project['closed'] = True
        with self.assertRaises(BootstrapError):
            importer.verify_completion(self.api, self.project_spec, self.seed, self.data)

    def test_final_verification_rejects_managed_body_changed_during_import(self):
        self.seed_complete()
        issue = self.issues['FND-01']
        issue['body'] = issue['body'].replace('### Deliverables', '### Changed by concurrent actor')
        with self.assertRaises(BootstrapError):
            importer.verify_completion(self.api, self.project_spec, self.seed, self.data)


    def test_existing_project_requires_write_permission_before_any_mutation(self):
        project = self.seed_complete()
        project['viewerCanUpdate'] = False
        self.assert_preflight_rejects()

    def test_project_receipt_numeric_number_cannot_substitute_node_id(self):
        self.seed_complete()
        self.api.project_store[self.pid]['number'] += 1
        self.assert_preflight_rejects()

    def test_project_owner_node_mismatch_stops_before_mutation(self):
        project = self.seed_complete()
        project['owner']['id'] = 'TEST_UNRELATED_OWNER'
        self.assert_preflight_rejects()

    def test_duplicate_custom_field_names_stop_before_mutation(self):
        project = self.seed_complete()
        duplicate = copy.deepcopy(project['fields'][0])
        duplicate['id'] = 'TEST_DUPLICATE_FIELD'
        project['fields'].append(duplicate)
        self.assert_preflight_rejects()

    def test_unreceipted_view_collision_stops_before_any_mutation(self):
        project = self.seed_complete()
        self.api.support_views = True
        name = self.project_spec['views'][0]['name']
        project['views'].append({'id': 'TEST_HUMAN_VIEW', 'name': name, 'layout': 'TABLE_LAYOUT'})
        project['public'] = False  # A mutation is otherwise needed, but must not happen.
        self.assert_preflight_rejects()
        self.assertFalse(project['public'])

    def test_lost_view_create_reply_recovers_and_rerun_does_not_duplicate(self):
        self.api.support_views = True
        self.api.fail_after['create_view'] = RuntimeError('View reply lost after server commit')
        result = self.run_import(apply=True)
        self.assertEqual(result['verified_issues'], 66)
        expected = len(self.project_spec['views'])
        self.assertEqual(self.api.writes.count('create_view'), expected)
        self.api.writes.clear()
        self.run_import(apply=True)
        self.assertEqual(self.api.writes, [])
        self.assertEqual(len(next(iter(self.api.project_store.values()))['views']), expected)

    def test_interrupted_view_create_resumes_from_intent(self):
        self.api.support_views = True
        self.api.fail_after['create_view'] = SimulatedInterruption()
        with self.assertRaises(SimulatedInterruption):
            self.run_import(apply=True)
        self.run_import(apply=True)
        self.assertEqual(self.api.writes.count('create_view'), len(self.project_spec['views']))
        self.assertEqual(json.loads(self.receipt.read_text())['pending'], {})

    def test_lost_initial_field_response_resumes_without_progress_reset(self):
        self.api.fail_after['set_field'] = RuntimeError('Response lost after field changed')
        with self.assertRaises(RuntimeError):
            self.run_import(apply=True)
        project = next(iter(self.api.project_store.values()))
        project['items'][0]['values']['Delivery'] = 'Verified'
        self.run_import(apply=True)
        self.assertEqual(project['items'][0]['values']['Delivery'], 'Verified')
        self.assertEqual(self.api.writes.count('add_item'), 66)

    def test_invalid_external_seed_rejected_without_mutation(self):
        seed_path = self.base / 'stale-seed.json'
        seed = copy.deepcopy(self.seed)
        seed['issues'][0]['title'] = 'Changed seed'
        seed_path.write_text(json.dumps(seed))
        with self.assertRaises(BootstrapError):
            importer.execute(self.api, self.root, self.repo_receipt, self.receipt,
                             apply=True, seed_path=seed_path)
        self.assertEqual(self.api.writes, [])
        self.assertFalse(self.receipt.exists())

    def test_project_receipt_symlink_is_rejected(self):
        target = self.base / 'other-receipt.json'
        target.write_text('{}')
        self.receipt.symlink_to(target)
        self.assert_preflight_rejects()
        self.assertEqual(target.read_text(), '{}')

    def test_final_verification_rejects_archived_task_item(self):
        project = self.seed_complete()
        project['items'][0]['isArchived'] = True
        with self.assertRaises(BootstrapError):
            importer.verify_completion(self.api, self.project_spec, self.seed, self.data)

    def test_missing_schema_capability_stops_before_any_write(self):
        self.api.capabilities = lambda: {'mutations': [], 'field_types': []}
        self.assert_preflight_rejects()

    def test_read_only_project_scope_cannot_apply(self):
        self.api.user['_oauth_scopes'] = ['read:project']
        self.assert_preflight_rejects()

    def test_disabled_task_issues_stop_before_writes(self):
        self.api.repos['aloerch/ambisgis-platform']['has_issues'] = False
        self.assert_preflight_rejects()

    def test_project_created_between_preflight_and_apply_is_not_duplicated(self):
        original = self.api.projects
        calls = []
        def racing(owner):
            calls.append(owner)
            if len(calls) == 2:
                return [{'id': 'RACING_PROJECT', 'title': importer.PROJECT_TITLE}]
            return original(owner)
        self.api.projects = racing
        with self.assertRaises(BootstrapError):
            self.run_import(apply=True)
        self.assertEqual(self.api.writes, [])

    def test_wrong_created_project_owner_prevents_followup_mutations(self):
        original = self.api.create_project
        def wrong(owner, title):
            result = original(owner, title)
            result['owner']['login'] = 'someone-else'
            return result
        self.api.create_project = wrong
        with self.assertRaises(BootstrapError):
            self.run_import(apply=True)
        self.assertEqual(self.api.writes, ['create_project'])

    def test_issue_bodies_link_to_owned_version_controlled_specs(self):
        project = self.seed_complete()
        body = self.api.issue_store['aloerch/ambisgis-platform'][0]['body']
        self.assertIn('https://github.com/aloerch/ambisgis-platform/blob/ambisgis/main/plan/backlog.json', body)
        self.assertIn('[source ownership]', body)


if __name__ == '__main__':
    unittest.main()
