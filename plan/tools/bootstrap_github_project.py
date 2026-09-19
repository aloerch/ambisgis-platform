#!/usr/bin/env python3
"""Provision the approved AmbisGIS Project. Read-only unless --apply is supplied.

Receipts are local operational journals, never credentials. A failed operation
is reconciled by reading the remote resource; creates are never blindly retried.
Human progress is not derived from the planning backlog's initial status.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from .bootstrap_repositories import (BootstrapError, load_json, save_receipt,
                                        validate_manifest, verify_target)
    from .export_project_seed import build_seed
    from .validate_package import validate_plan
except ImportError:
    from bootstrap_repositories import (BootstrapError, load_json, save_receipt,
                                       validate_manifest, verify_target)
    from export_project_seed import build_seed
    from validate_package import validate_plan

ROOT = Path(__file__).resolve().parent.parent
START = '<!-- ambisgis:managed:start -->'
END = '<!-- ambisgis:managed:end -->'
MARKER = re.compile(r'<!-- ambisgis:task:([A-Z]+-\d+) -->')
PROJECT_TITLE = 'AmbisGIS — Product Development'
PROJECT_MARKER = 'ambisgis-product-development-v2'
REQUIRED_MUTATIONS = {'createProjectV2', 'updateProjectV2', 'linkProjectV2ToRepository',
                      'createProjectV2Field', 'addProjectV2ItemById', 'updateProjectV2ItemFieldValue'}


class ImportConflict(BootstrapError):
    """An ambiguous identity or concurrent edit needs inspection."""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def block(body: str) -> tuple[str, str, str]:
    if not isinstance(body, str) or body.count(START) != 1 or body.count(END) != 1:
        raise ImportConflict('Issue must contain exactly one bounded managed block.')
    a, b = body.index(START), body.index(END) + len(END)
    if a >= b - len(END):
        raise ImportConflict('Managed block markers are out of order.')
    return body[:a], body[a:b], body[b:]


def reconcile_body(current: str, desired: str, previous_hash: str | None) -> str:
    before, managed, after = block(current)
    replacement = block(desired)[1]
    if managed == replacement:
        return current
    if previous_hash is None or digest(managed) != previous_hash:
        raise ImportConflict('Managed issue content changed outside the importer; preserve it for review.')
    return before + replacement + after


def desired_body(seed: dict, issues: dict[str, dict]) -> str:
    body = seed['body']
    base = 'https://github.com/aloerch/ambisgis-platform/blob/ambisgis/main/plan/'
    body = body.replace(
        'Specification: version-controlled plan/backlog.json and relevant plan/docs chapters.',
        f'Specification: [backlog.json]({base}backlog.json), '
        f'[requirements.json]({base}requirements.json), '
        f'[component specifications]({base}docs), '
        f'[source ownership]({base}docs/11-independent-product-and-source-ownership.md).')
    deps = seed['dependency_task_ids']
    # The second pass adds actual links, never guessed issue numbers.
    if deps and all(task in issues for task in deps):
        links = ', '.join(f"[{task}]({issues[task]['html_url']})" for task in deps)
        body = body.replace('Depends on: ' + ', '.join(deps), 'Depends on: ' + links, 1)
    return body


def validate_inputs(root: Path, seed_path: Path | None = None) -> tuple[dict, dict, dict]:
    validate_plan(root)
    manifest, project = load_json(root / 'repositories.json'), load_json(root / 'project.json')
    validate_manifest(manifest, 'aloerch')
    if (project.get('schema_version') != 1 or project.get('owner') != 'aloerch'
            or project.get('owner_type') != 'User' or project.get('title') != PROJECT_TITLE
            or project.get('marker') != PROJECT_MARKER or project.get('visibility') != 'PUBLIC'):
        raise ImportConflict('Project identity/visibility is outside the approved specification.')
    names = set()
    for field in project.get('fields', []):
        if field.get('name') in names or field.get('type') not in {'TEXT', 'DATE', 'SINGLE_SELECT'}:
            raise ImportConflict('Duplicate field name or unsupported custom field type.')
        names.add(field['name'])
        if field['type'] == 'SINGLE_SELECT':
            opts = field.get('options', [])
            if not opts or len(opts) != len(set(opts)) or not all(isinstance(x, str) and x for x in opts):
                raise ImportConflict('Invalid single-select field options.')
    if 'Task ID' not in names or 'Delivery' not in names:
        raise ImportConflict('Task ID and Delivery fields are required.')
    seed = build_seed(root)
    if seed_path and load_json(seed_path) != seed:
        raise ImportConflict('Seed does not match the current validated plan. Regenerate the seed.')
    field_specs = {f['name']: f for f in project['fields']}
    for issue in seed['issues']:
        if MARKER.findall(issue['body']) != [issue['task_id']]:
            raise ImportConflict('Invalid seed task marker.')
        block(issue['body'])
        for name, value in issue['initial_fields_only'].items():
            if name not in field_specs:
                raise ImportConflict(f'Undefined seed field: {name}.')
            field = field_specs[name]
            if field['type'] == 'SINGLE_SELECT' and value not in field['options']:
                raise ImportConflict(f'Undefined seed option for {name}.')
    return manifest, project, seed


class Journal:
    def __init__(self, path: Path, apply: bool):
        self.path, self.apply = path, apply
        if path.is_symlink():
            raise ImportConflict('Project receipt must not be a symlink.')
        self.data = load_json(path) if path.exists() else {
            'receipt_version': 1, 'owner': 'aloerch', 'owner_id': None,
            'owner_node_id': None, 'repositories': {}, 'project': None,
            'issues': {}, 'pending': {}, 'views': {},
        }
        if (self.data.get('receipt_version') != 1 or self.data.get('owner') != 'aloerch'
                or any(not isinstance(self.data.get(k), dict)
                       for k in ('repositories', 'issues', 'pending', 'views'))):
            raise ImportConflict('Malformed Project receipt or wrong receipt owner/version.')
        if apply and not path.parent.is_dir():
            raise ImportConflict('Project receipt directory must already exist.')

    def save(self):
        if self.apply:
            save_receipt(self.path, self.data)

    def intend(self, key: str, value: dict):
        self.data['pending'][key] = value
        self.save()

    def finish(self, key: str):
        self.data['pending'].pop(key, None)
        self.save()


@contextmanager
def import_lock(receipt: Path, apply: bool):
    """An apply uses one local writer. Dry run creates no local files."""
    if not apply:
        yield
        return
    path = receipt.with_name(receipt.name + '.lock')
    if path.is_symlink():
        raise ImportConflict('Receipt lock must not be a symlink.')
    with path.open('a', encoding='utf-8') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ImportConflict('Another importer holds this receipt lock.') from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def index_fields(project: dict | None, specs: list[dict]) -> dict[str, dict]:
    result = {}
    for field in (project or {}).get('fields', []):
        name = field['name']
        if name in result:
            raise ImportConflict(f'Duplicate live field name: {name}.')
        result[name] = field
    for spec in specs:
        existing = result.get(spec['name'])
        if existing:
            if existing.get('dataType') != spec['type']:
                raise ImportConflict(f"Field type collision: {spec['name']}.")
            if spec['type'] == 'SINGLE_SELECT':
                options = [o['name'] for o in existing.get('options', [])]
                if len(set(options)) != len(options) or not set(spec['options']) <= set(options):
                    raise ImportConflict(f"Field option collision: {spec['name']}; no options replaced.")
    return result


def verify_issue(issue: dict, spec: dict, record: dict | None = None):
    full = spec['repository']
    expected_url = f"https://github.com/{full}/issues/{issue.get('number')}"
    if (issue.get('html_url') != expected_url or not isinstance(issue.get('id'), int)
            or isinstance(issue.get('id'), bool) or not issue.get('node_id') or 'pull_request' in issue):
        raise ImportConflict(f"Wrong or incomplete issue identity for {spec['task_id']}.")
    if MARKER.findall(issue.get('body') or '') != [spec['task_id']]:
        raise ImportConflict(f"Wrong/duplicate machine marker for {spec['task_id']}.")
    block(issue['body'])
    if record and any(record.get(k) != issue[k] for k in ('id', 'node_id', 'number', 'html_url')):
        raise ImportConflict(f"Recorded issue identity changed for {spec['task_id']}.")


def record_issue(issue: dict, spec: dict, previous: dict | None = None) -> dict:
    record = dict(previous or {})
    record.update({k: issue[k] for k in ('id', 'node_id', 'number', 'html_url')})
    record.update(repository=spec['repository'], managed_sha256=digest(block(issue['body'])[1]),
                  spec_sha256=spec['spec_sha256'])
    return record


def discover(api: Any, manifest: dict, project_spec: dict, seed: dict,
             repo_receipt: dict, journal: Journal) -> dict:
    """Complete all relevant reads and conflicts before permitting any write."""
    user = api.identity()
    if user.get('login') != 'aloerch' or user.get('type') != 'User' or not user.get('node_id'):
        raise ImportConflict('Authenticated identity is not the approved personal owner aloerch.')
    data = journal.data
    if data.get('owner_id') not in (None, user['id']) or data.get('owner_node_id') not in (None, user['node_id']):
        raise ImportConflict('Recorded owner ID differs from authenticated owner.')
    if (repo_receipt.get('receipt_version') != 1 or repo_receipt.get('owner') != 'aloerch'
            or not isinstance(repo_receipt.get('managed_repositories'), dict)):
        raise ImportConflict('A valid repository bootstrap receipt is required.')
    repos = {}
    for spec in manifest['repositories']:
        full = 'aloerch/' + spec['name']
        known = repo_receipt['managed_repositories'].get(full, {})
        repo = api.repository(full)
        verify_target(repo, 'aloerch', spec)
        if known.get('id') != repo['id'] or known.get('status') != 'ready':
            raise ImportConflict(f'Missing ready repository receipt or ID mismatch: {full}.')
        if data['repositories'].get(full, {}).get('id', repo['id']) != repo['id']:
            raise ImportConflict(f'Project receipt repository ID mismatch: {full}.')
        if not repo.get('node_id') or repo.get('owner', {}).get('id') != user['id']:
            raise ImportConflict(f'Unverified repository node/owner: {full}.')
        repos[full] = repo
    capabilities = api.capabilities()
    if (not REQUIRED_MUTATIONS <= set(capabilities.get('mutations', []))
            or not {'TEXT', 'DATE', 'SINGLE_SELECT'} <= set(capabilities.get('field_types', []))
            or capabilities.get('project_items_archived_states') is not True):
        raise ImportConflict('Required Project schema or archived-item enumeration is unavailable.')
    projects = api.projects('aloerch')  # Includes closed Projects; no search-index shortcuts.
    matches = [p for p in projects if p['title'] == project_spec['title']
               or project_spec['marker'] in (p.get('shortDescription') or '')]
    saved = data['project']
    live = None
    if saved:
        live = api.project(saved['id'])
        if (live.get('owner', {}).get('login') != 'aloerch'
                or live.get('owner', {}).get('id') != user['node_id']
                or any(live.get(k) != saved.get(k) for k in ('id', 'number', 'url'))
                or live['title'] != project_spec['title'] or live.get('closed')
                or (project_spec['marker'] not in (live.get('shortDescription') or '')
                    and not saved.get('pending_configuration'))):
            raise ImportConflict('Recorded Project identity, marker or open state changed.')
        if any(p['id'] != saved['id'] for p in matches):
            raise ImportConflict('Another Project has the approved title or marker.')
    elif matches or 'project' in data['pending']:
        raise ImportConflict('Unreceipted Project/title collision or unresolved create; inspect before adoption.')
    fields = index_fields(live, project_spec['fields'])
    for view in project_spec['views']:
        matches = [v for v in (live or {}).get('views', []) if v['name'] == view['name']]
        known = data['views'].get(view['name'])
        pending = data['pending'].get('view:' + view['name'])
        if len(matches) > 1 or (matches and not known and not pending):
            raise ImportConflict('Unreceipted or duplicate view name; inspect before adoption.')
        if known and (not matches or matches[0]['id'] != known['id']):
            raise ImportConflict('Recorded view was removed or replaced; preserve manual layout changes.')
    seeds = {s['task_id']: s for s in seed['issues']}
    issues, all_issues = {}, {}
    issue_owners = {s['repository'] for s in seed['issues']}
    for full in repos:
        if repos[full].get('has_issues') is False:
            if full in issue_owners:
                raise ImportConflict(f'Issues are disabled in task-owning repository: {full}.')
            all_issues[full] = []
        else:
            all_issues[full] = api.issues(full)
        for issue in all_issues[full]:
            markers = MARKER.findall(issue.get('body') or '')
            titles = [task for task in seeds if issue.get('title', '').startswith(f'[{task}]')]
            if not markers and titles:
                raise ImportConflict(f'Task title without verified marker: {full}#{issue["number"]}.')
            for task in markers:
                if task not in seeds:
                    raise ImportConflict(f'Unknown task marker: {task}.')
                if seeds[task]['repository'] != full or task in issues or len(markers) != 1:
                    raise ImportConflict(f'Duplicate/moved task marker: {task}.')
                verify_issue(issue, seeds[task], data['issues'].get(task))
                if task not in data['issues']:
                    intent = data['pending'].get('issue:' + task)
                    if not intent or intent.get('body_sha256') != digest(issue['body']):
                        raise ImportConflict(f'Unreceipted task issue: {task}; no title-only adoption.')
                issues[task] = issue
    for task in data['issues']:
        if task not in seeds or task not in issues:
            raise ImportConflict(f'Recorded task missing or removed from plan: {task}.')
        record = data['issues'][task]
        if record.get('repository') != seeds[task]['repository']:
            raise ImportConflict(f'Recorded repository changed for {task}.')
        desired = desired_body(seeds[task], issues)
        pending_body = data['pending'].get('body:' + task, {})
        live_hash = digest(block(issues[task]['body'])[1])
        expected_hash = record.get('managed_sha256')
        if live_hash == pending_body.get('managed_sha256'):
            expected_hash = live_hash
        reconcile_body(issues[task]['body'], desired, expected_hash)
    items = {}
    for item in (live or {}).get('items', []):
        content = item.get('content') or {}
        node = content.get('id')
        if node:
            if node in items:
                raise ImportConflict('Duplicate Project item for one issue.')
            items[node] = item
    for task, issue in issues.items():
        item = items.get(issue['node_id'])
        saved_item = data['issues'].get(task, {}).get('item_id')
        if saved_item and (not item or item['id'] != saved_item):
            raise ImportConflict(f'Recorded Project item removed/replaced: {task}.')
        if item and item.get('isArchived'):
            raise ImportConflict(f'Task item is archived; preserve for inspection: {task}.')
        if item and item.get('values', {}).get('Task ID') not in (None, task):
            raise ImportConflict(f'Project Task ID disagrees with issue marker: {task}.')
    owners = sorted({s['repository'] for s in seed['issues']})
    labels = {full: api.labels(full) for full in owners}
    dependencies = {task: api.dependencies(seeds[task]['repository'], issue['number'])
                    for task, issue in issues.items()}
    return dict(user=user, repos=repos, capabilities=capabilities, project=live, fields=fields,
                issues=issues, items=items, labels=labels, dependencies=dependencies)


def plan_changes(project_spec: dict, seed: dict, snapshot: dict,
                 pending: dict[str, dict] | None = None) -> list[dict]:
    ops = []
    pending = pending or {}
    project = snapshot['project']
    if not project:
        ops.append({'action': 'create_project', 'title': project_spec['title'], 'public': True})
    elif not project.get('public') or project_spec['marker'] not in (project.get('shortDescription') or ''):
        ops.append({'action': 'configure_project', 'id': project['id']})
    linked = {r['id'] for r in (project or {}).get('repositories', [])}
    for full, repo in snapshot['repos'].items():
        if repo['node_id'] not in linked:
            ops.append({'action': 'link_repository', 'repository': full})
    for field in project_spec['fields']:
        if field['name'] not in snapshot['fields']:
            ops.append({'action': 'create_field', 'name': field['name']})
    for s in seed['issues']:
        task, issue = s['task_id'], snapshot['issues'].get(s['task_id'])
        if not issue:
            ops.append({'action': 'create_issue', 'task_id': task, 'repository': s['repository']})
        else:
            if block(issue['body'])[1] != block(desired_body(s, snapshot['issues']))[1]:
                ops.append({'action': 'update_managed_body', 'task_id': task})
        item = snapshot['items'].get(issue['node_id']) if issue else None
        if item is None:
            ops.append({'action': 'add_item', 'task_id': task,
                        'initial_fields_only': s['initial_fields_only']})
        else:
            # An interrupted add may leave an existing item with journaled
            # initialization still due. Plan the same absent-only writes as
            # apply; never propose replacing a human's current field value.
            initial = pending.get('item:' + task, {}).get('initial_fields', {})
            for name, value in initial.items():
                if name not in item.get('values', {}):
                    ops.append({'action': 'set_initial_field', 'task_id': task,
                                'field': name, 'value': value})
        existing_labels = {x['name'] for x in snapshot['labels'][s['repository']]}
        for label in s['labels']:
            operation = {'action': 'create_label', 'repository': s['repository'], 'name': label}
            if label not in existing_labels and operation not in ops:
                ops.append(operation)
        edges = {x['id'] for x in snapshot['dependencies'].get(task, [])}
        for dep in s['dependency_task_ids']:
            if dep not in snapshot['issues'] or snapshot['issues'][dep]['id'] not in edges:
                ops.append({'action': 'add_dependency', 'task_id': task, 'blocked_by': dep})
    if snapshot['capabilities'].get('create_view'):
        existing_views = {v['name'] for v in (project or {}).get('views', [])}
        for view in project_spec['views']:
            if view['name'] not in existing_views:
                ops.append({'action': 'create_view', 'name': view['name'], 'layout': view['layout']})
    return ops


def reread_created_issue(api: Any, spec: dict) -> dict | None:
    candidates = [i for i in api.issues(spec['repository'])
                  if spec['marker'] in (i.get('body') or '')
                  or i.get('title', '').startswith(f"[{spec['task_id']}]")]
    if len(candidates) > 1:
        raise ImportConflict(f"Ambiguous issue creation for {spec['task_id']}.")
    if not candidates:
        return None
    verify_issue(candidates[0], spec)
    return candidates[0]


def execute(api: Any, root: Path, repository_receipt: Path, receipt: Path,
            *, apply: bool = False, seed_path: Path | None = None) -> dict:
    api.read_only = True
    manifest, project_spec, seed = validate_inputs(root, seed_path)
    if repository_receipt.is_symlink():
        raise ImportConflict('Repository receipt must not be a symlink.')
    repo_receipt = load_json(repository_receipt)
    with import_lock(receipt, apply):
        journal = Journal(receipt, apply)
        snapshot = discover(api, manifest, project_spec, seed, repo_receipt, journal)
        operations = plan_changes(project_spec, seed, snapshot, journal.data['pending'])
        if not apply:
            return {'mode': 'dry-run', 'operations': operations,
                    'views': 'Pending capability-checked creation and owner layout verification.',
                    'mutations': 0}
        # Only after every discovery/read/schema conflict has passed.
        scopes = snapshot['user'].get('_oauth_scopes', ['project'])
        if scopes is None or 'project' not in scopes:
            raise ImportConflict('Full Project authorization is required for apply; owner must authorize locally.')
        if snapshot['project'] is not None and snapshot['project'].get('viewerCanUpdate') is not True:
            raise ImportConflict('Project write permission is unavailable; owner authorization is required.')
        api.read_only = False
        data = journal.data
        for task, issue in snapshot['issues'].items():
            intent = data['pending'].get('body:' + task, {})
            observed = digest(block(issue['body'])[1])
            if observed == intent.get('managed_sha256'):
                data['issues'][task]['managed_sha256'] = observed
                data['pending'].pop('body:' + task)
        data.update(owner_id=snapshot['user']['id'], owner_node_id=snapshot['user']['node_id'])
        data['repositories'] = {name: {'id': r['id'], 'node_id': r['node_id']}
                                for name, r in snapshot['repos'].items()}
        journal.save()
        live = snapshot['project']
        if live is None:
            # If response is lost, leave intent and require inspected ID recovery.
            appeared = [p for p in api.projects('aloerch')
                        if p['title'] == PROJECT_TITLE or PROJECT_MARKER in (p.get('shortDescription') or '')]
            if appeared:
                raise ImportConflict('Project appeared after preflight; inspect the collision.')
            journal.intend('project', {'title': project_spec['title']})
            live = api.create_project(snapshot['user']['node_id'], project_spec['title'])
            if (not live.get('id') or type(live.get('number')) is not int
                    or live['number'] <= 0
                    or live.get('url') != f"https://github.com/users/aloerch/projects/{live['number']}"
                    or live.get('owner', {}).get('id') != snapshot['user']['node_id']
                    or live.get('owner', {}).get('login') != 'aloerch'
                    or live.get('title') != PROJECT_TITLE):
                raise ImportConflict('Unverified Project creation identity; inspect pending receipt.')
            data['project'] = {k: live[k] for k in ('id', 'number', 'url')}
            data['project']['pending_configuration'] = True
            journal.finish('project')
        pid = data['project']['id']
        if not live.get('public') or PROJECT_MARKER not in (live.get('shortDescription') or ''):
            api.update_project(pid, True, PROJECT_MARKER)
            live = api.project(pid)
            if not live.get('public') or PROJECT_MARKER not in (live.get('shortDescription') or ''):
                raise ImportConflict('Public Project visibility/marker readback failed.')
        data['project'].pop('pending_configuration', None)
        journal.save()
        linked = {r['id'] for r in live.get('repositories', [])}
        for full, repo in snapshot['repos'].items():
            if repo['node_id'] not in linked:
                api.link_repository(pid, repo['node_id'])
                journal.save()
        fields = index_fields(live, project_spec['fields'])
        for spec in project_spec['fields']:
            if spec['name'] not in fields:
                try:
                    api.create_field(pid, spec)
                except Exception:
                    # A response can be lost after creation; never retry blindly.
                    recovered = index_fields(api.project(pid), project_spec['fields'])
                    if spec['name'] not in recovered:
                        raise
                fields = index_fields(api.project(pid), project_spec['fields'])
                if spec['name'] not in fields:
                    raise ImportConflict('Created field missing from readback.')
                journal.save()
        data['fields'] = {name: {'id': f['id'], 'options': f.get('options', [])}
                          for name, f in fields.items() if name in {s['name'] for s in project_spec['fields']}}
        journal.save()
        for full, labels in snapshot['labels'].items():
            existing = {x['name'] for x in labels}
            wanted = {label for s in seed['issues'] if s['repository'] == full for label in s['labels']}
            for label in sorted(wanted - existing):
                try:
                    api.create_label(full, label)
                except Exception:
                    if label not in {x['name'] for x in api.labels(full)}:
                        raise
        issues = snapshot['issues']
        for spec in seed['issues']:
            task = spec['task_id']
            issue = issues.get(task)
            if issue is None:
                # Detect a race after full preflight before issuing any create.
                if reread_created_issue(api, spec):
                    raise ImportConflict(f'Issue appeared after preflight: {task}.')
                journal.intend('issue:' + task, {'body_sha256': digest(spec['body'])})
                try:
                    issue = api.create_issue(spec['repository'], spec['title'], spec['body'], spec['labels'])
                except Exception:
                    issue = reread_created_issue(api, spec)
                    if issue is None or digest(issue['body']) != data['pending']['issue:' + task]['body_sha256']:
                        raise
                verify_issue(issue, spec)
                if digest(issue['body']) != digest(spec['body']):
                    raise ImportConflict('Created issue body differs from submitted content.')
                issues[task] = issue
            if task not in data['issues']:
                data['issues'][task] = record_issue(issue, spec)
                journal.finish('issue:' + task)
        # All URLs are now real, so reconcile linked dependencies in managed blocks.
        for spec in seed['issues']:
            task = spec['task_id']
            record = data['issues'][task]
            current = api.issue(spec['repository'], record['number'])
            verify_issue(current, spec, record)
            desired = desired_body(spec, issues)
            updated = reconcile_body(current['body'], desired, record['managed_sha256'])
            if updated != current['body']:
                # Optimistic fresh read; GitHub does not promise atomic body CAS.
                fresh = api.issue(spec['repository'], record['number'])
                verify_issue(fresh, spec, record)
                updated = reconcile_body(fresh['body'], desired, record['managed_sha256'])
                journal.intend('body:' + task, {'managed_sha256': digest(block(updated)[1])})
                try:
                    api.update_issue_body(spec['repository'], record['number'], updated)
                except Exception:
                    readback = api.issue(spec['repository'], record['number'])
                    if readback['body'] != updated:
                        raise
                current = api.issue(spec['repository'], record['number'])
                verify_issue(current, spec, record)
                if current['body'] != updated:
                    raise ImportConflict('Issue changed during managed update; review remote text.')
                data['issues'][task] = record_issue(current, spec, record)
                journal.finish('body:' + task)
            # Item recovery initializes only absent fields from a persisted intent.
            if record.get('item_id'):
                items = [api.item(record['item_id'])]
            else:
                items = [i for i in api.items(pid) if (i.get('content') or {}).get('id') == record['node_id']]
            if len(items) > 1:
                raise ImportConflict('Duplicate issue Project items.')
            key = 'item:' + task
            if not items:
                journal.intend(key, {'initial_fields': spec['initial_fields_only']})
                try:
                    added = api.add_item(pid, record['node_id'])
                    items = [api.item(added['id'])]
                except Exception:
                    items = [i for i in api.items(pid)
                             if (i.get('content') or {}).get('id') == record['node_id']]
                    if len(items) != 1:
                        raise
                if not items:
                    items = [i for i in api.items(pid)
                             if (i.get('content') or {}).get('id') == record['node_id']]
            if len(items) != 1:
                raise ImportConflict('Project item readback failed.')
            item = items[0]
            record = data['issues'][task]
            record['item_id'] = item['id']
            journal.save()
            pending = data['pending'].get(key)
            if pending and item.get('isArchived'):
                raise ImportConflict('Item was archived during initialization; preserve it for inspection.')
            if pending:
                for name, value in list(pending['initial_fields'].items()):
                    # Re-read each time: previous attempts or humans may have progressed it.
                    fresh = api.item(item['id'])
                    if fresh.get('isArchived') or (fresh.get('content') or {}).get('id') != record['node_id']:
                        raise ImportConflict('Item identity/archive state changed during initialization.')
                    if name not in fresh.get('values', {}):
                        api.set_field(pid, item['id'], fields[name], value)
                        readback = api.item(item['id'])
                        if readback.get('values', {}).get(name) != value:
                            raise ImportConflict(f'Initial field write was not verified: {task}/{name}.')
                    pending['initial_fields'].pop(name)
                    journal.save()
                journal.finish(key)
        for spec in seed['issues']:
            issue = data['issues'][spec['task_id']]
            existing = {i['id'] for i in api.dependencies(spec['repository'], issue['number'])}
            for dep in spec['dependency_task_ids']:
                dep_id = data['issues'][dep]['id']
                if dep_id not in existing:
                    try:
                        api.add_dependency(spec['repository'], issue['number'], dep_id)
                    except Exception:
                        if dep_id not in {i['id'] for i in api.dependencies(spec['repository'], issue['number'])}:
                            raise
                    journal.save()
        # Views only use documented operations; grouping/sorting/date selection remain UI gates.
        live = api.project(pid)
        if snapshot['capabilities'].get('create_view'):
            for spec in project_spec['views']:
                matches = [v for v in live.get('views', []) if v['name'] == spec['name']]
                key = 'view:' + spec['name']
                known = data['views'].get(spec['name'])
                if len(matches) > 1 or (matches and not known and key not in data['pending']):
                    raise ImportConflict('Unreceipted or duplicate view name; inspect before adoption.')
                if not matches:
                    journal.intend(key, {'name': spec['name'], 'layout': spec['layout']})
                    try:
                        api.create_view(pid, {**spec, 'visibleFieldIds': [f['id'] for f in fields.values() if f['name'] != 'Status']})
                    except Exception:
                        matches = [v for v in api.project(pid).get('views', []) if v['name'] == spec['name']]
                        if len(matches) != 1:
                            raise
                    matches = [v for v in api.project(pid).get('views', []) if v['name'] == spec['name']]
                if len(matches) != 1 or matches[0]['layout'] != spec['layout'] + '_LAYOUT':
                    raise ImportConflict('View layout readback failed.')
                data['views'][spec['name']] = {'id': matches[0]['id']}
                journal.finish(key)
                live = api.project(pid)
        report = verify_completion(api, project_spec, seed, data)
        data['last_verification'] = report
        journal.save()
        return {'mode': 'apply', 'project': data['project'], **report}


def verify_completion(api: Any, project_spec: dict, seed: dict, data: dict) -> dict:
    live = api.project(data['project']['id'])
    failures = []
    if (not live.get('public') or live.get('closed')
            or live.get('title') != PROJECT_TITLE
            or live.get('owner', {}).get('id') != data['owner_node_id']
            or live.get('owner', {}).get('login') != data['owner']
            or any(live.get(k) != data['project'].get(k) for k in ('id', 'number', 'url'))
            or PROJECT_MARKER not in (live.get('shortDescription') or '')):
        failures.append('Project public visibility/marker')
    fields = index_fields(live, project_spec['fields'])
    if not {f['name'] for f in project_spec['fields']} <= fields.keys():
        failures.append('Missing custom fields')
    if not {r['node_id'] for r in data['repositories'].values()} <= {r['id'] for r in live['repositories']}:
        failures.append('Missing linked repositories')
    edges = 0
    for spec in seed['issues']:
        record = data['issues'][spec['task_id']]
        issue = api.issue(spec['repository'], record['number'])
        verify_issue(issue, spec, record)
        if digest(block(issue['body'])[1]) != record['managed_sha256']:
            failures.append('Concurrent managed body edit: ' + spec['task_id'])
        matches = [i for i in live['items'] if (i.get('content') or {}).get('id') == record['node_id']]
        if len(matches) != 1 or matches[0].get('isArchived') or matches[0]['values'].get('Task ID') != spec['task_id']:
            failures.append('Missing item/Task ID: ' + spec['task_id'])
        elif not spec['initial_fields_only'].keys() <= matches[0]['values'].keys():
            failures.append('Missing initial fields: ' + spec['task_id'])
        deps = {i['id'] for i in api.dependencies(spec['repository'], record['number'])}
        for dep in spec['dependency_task_ids']:
            edges += 1
            if data['issues'][dep]['id'] not in deps:
                failures.append(f'Missing native dependency: {spec["task_id"]} -> {dep}')
    if failures:
        raise ImportConflict('Readback incomplete: ' + '; '.join(failures))
    return {'verified_issues': len(seed['issues']), 'verified_dependency_edges': edges,
            'views_pending': [f"{v['name']}: verify grouping, sorting, filters, visible fields and roadmap dates in the UI"
                              for v in project_spec['views']],
            'gov_01': 'Live provisioning verified; human review remains required.',
            'gov_02': 'Incomplete: view configuration and evidence transitions require verification.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--repository-receipt', type=Path, default=Path('.bootstrap-receipt.json'))
    parser.add_argument('--receipt', type=Path, default=Path('.project-receipt.json'))
    parser.add_argument('--seed', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        try:
            from .github_project_api import GitHubProjectAPI
        except ImportError:
            from github_project_api import GitHubProjectAPI
        result = execute(GitHubProjectAPI(), args.root, args.repository_receipt,
                         args.receipt, apply=args.apply, seed_path=args.seed)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (BootstrapError, OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f'STOPPED: {exc}', file=sys.stderr)
        print('No automatic retries of creates, resource deletion or permission escalation. Inspect the local receipt.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
