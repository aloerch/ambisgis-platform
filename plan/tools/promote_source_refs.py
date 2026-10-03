#!/usr/bin/env python3
"""Promote exact authorized FND-07 review or canonical refs; default is read-only.

Application requires the unchanged separate owner decision and hashed publication
findings. Each invocation writes a NEW fsynced JSONL receipt. Resume by a new
invocation: actual remote state, never the prior receipt, determines operations.
Repository Actions may be disabled for a publication-held row; its source is not
uploaded. Explicit --canonical selects the separately authorized nine-row operation,
which only creates absent refs and never changes settings. Defaults, workflow
files and releases are never changed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

sys.dont_write_bytecode = True
PLATFORM = Path(__file__).resolve().parents[2]
PLAN = PLATFORM / 'plan/verification/source-baseline-restore/promotion-plan.json'
PLAN_SHA256 = 'a9477bbdcab4f85fad69cbf77ed04ed76de92efd63d3d663054bda34e4b573a6'
RECOVERY_SHA256 = '11bd0ba5f1662606b2d8ac604d469c2d3d02c1d73b0a1540d648856cdc2343f0'
RECOVERY_PATH = 'build-worktrees/source-baseline-restore/run-002'
OWNER = 'aloerch'
OWNER_ID = 15285626
COMMENT_ID = 5850316210
COMMENT_URL = 'https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5850316210'
COMMENT_DATE = '2026-09-26T22:07:35Z'
COMMENT_SHA256 = '14cbf5562a767905ca4a48174be5d64416c6a1f1046ad62d058e78f1338dd818'
TARGET_REF = 'refs/heads/ambisgis/review/fnd-07-baseline-v4'
BASE_MERGE = '4d0602542d3120024ec5974501624c96e5de48d4'
_spec = importlib.util.spec_from_file_location('promotion_custody', PLATFORM / 'build-support/source_restore/common.py')
custody = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(custody)
require = custody.require


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def bound_json(path, expected):
    data = Path(path).read_bytes()
    require(digest_bytes(data) == expected, 'Evidence hash mismatch: ' + str(path))
    return json.loads(data)


def authorization_identity(record):
    require(record.get('schema_version') == 1 and record.get('plan_sha256') == PLAN_SHA256,
            'Authorization is not bound to approved plan')
    comment = record['comment']
    require(comment['id'] == COMMENT_ID and comment['html_url'] == COMMENT_URL and
            comment['user']['login'] == OWNER and comment['user']['id'] == OWNER_ID and
            comment['created_at'] == COMMENT_DATE and comment['updated_at'] == COMMENT_DATE,
            'Wrong separate owner decision identity/date')
    require(record['body_sha256'] == COMMENT_SHA256 and
            digest_bytes(comment['body'].encode()) == COMMENT_SHA256,
            'Owner decision body changed')
    return comment


def validate_inputs(plan_path, authorization_path, publication_path, publication_sha, workspace):
    plan = bound_json(plan_path, PLAN_SHA256)
    auth = json.loads(Path(authorization_path).read_text())
    authorization_identity(auth)
    publication = bound_json(publication_path, publication_sha)
    require(publication.get('schema_version') == 1 and publication.get('plan_sha256') == PLAN_SHA256,
            'Publication findings do not bind approved plan')
    rows = plan['repositories']
    require(len(rows) == 11 and len({r['root_id'] for r in rows}) == 11, 'Wrong source repository set')
    findings = {r['root_id']: r for r in publication['repositories']}
    require(len(findings) == len(publication['repositories']) and findings.keys() == {r['root_id'] for r in rows},
            'Publication findings must cover exact source repository set')
    run = custody.confined(workspace, RECOVERY_PATH)
    recovery = bound_json(custody.confined(run, 'recovery.json'), RECOVERY_SHA256)
    roots = {r['id']: r for r in recovery['roots']}
    require(roots.keys() == findings.keys() and len(roots) == len(recovery['roots']), 'Recovery membership mismatch')
    for row in rows:
        require(row['target_ref'] == TARGET_REF and row['expected_old_sha'] is None and
                row['repository'] == OWNER + '/ambisgis-' + row['root_id'], 'Unsupported promotion boundary')
        finding = findings[row['root_id']]
        for key in ('repository', 'repository_id', 'proposed_commit', 'proposed_tree'):
            require(finding[key] == row[key], 'Publication identity mismatch: ' + row['root_id'])
        require(finding['disposition'] in ('publishable', 'held') and
                isinstance(finding.get('basis'), str) and finding['basis'].strip() and
                isinstance(finding.get('evidence'), list) and finding['evidence'] and
                all(isinstance(x, str) and x.strip() for x in finding['evidence']),
                'Publication finding needs disposition, precise basis and evidence')
        root = roots[row['root_id']]
        require(root['repository'] == row['repository'] and root['repository_id'] == row['repository_id'] and
                root['commit'] == row['proposed_commit'] and root['tree'] == row['proposed_tree'] and
                root['relative_path'] == 'repos/' + row['root_id'], 'Recovery identity mismatch')
    return rows, auth, findings, run, roots


class Receipt:
    """Exclusive creation and flush/fsync before any potentially effective write."""
    def __init__(self, path):
        path = Path(path)
        require(not path.is_symlink(), 'Receipt symlink forbidden')
        self.stream = path.open('x', encoding='utf-8')
        # Persist the directory entry as well as every subsequent event.
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def emit(self, event, **fields):
        value = {'at': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
        self.stream.write(json.dumps(value, sort_keys=True) + '\n')
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()


class CommandFailure(ValueError):
    pass


class GitHub:
    def command(self, argv, *, cwd=None, env=None, timeout=90, input=None):
        try:
            result = subprocess.run(argv, cwd=cwd, env=env, input=input, text=True,
                                    capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise CommandFailure('Command timeout; outcome may require remote reconciliation') from exc
        # No headers, tokens, API hook config, or credential helper output are logged.
        require(result.returncode == 0, 'Command failed (exit ' + str(result.returncode) + '): ' +
                result.stderr[-2000:])
        return result.stdout

    def api(self, endpoint, *, method='GET', payload=None, pages=False):
        command = ['gh', 'api', '--method', method, endpoint]
        if pages:
            command += ['--paginate', '--slurp']
        if payload is not None:
            command += ['--input', '-']
        output = self.command(command, input=None if payload is None else json.dumps(payload))
        return json.loads(output) if output.strip() else None

    def authorize(self, auth):
        expected = authorization_identity(auth)
        viewer = self.api('user')
        require(viewer['login'] == OWNER and viewer['id'] == OWNER_ID, 'Authenticated owner mismatch')
        live = self.api('repos/aloerch/ambisgis-platform/issues/comments/' + str(COMMENT_ID))
        authorization_identity({'schema_version': 1, 'plan_sha256': PLAN_SHA256,
                                'comment': live, 'body_sha256': COMMENT_SHA256})
        require(live['body'] == expected['body'], 'Live owner authorization changed')
        return {'login': viewer['login'], 'id': viewer['id'], 'comment_id': live['id'],
                'comment_url': live['html_url'], 'body_sha256': COMMENT_SHA256,
                'updated_at': live['updated_at']}

    def transport(self, repo, *args):
        # Recovered repos have no remotes/includes/filters; use only this bounded URL
        # and the existing gh credential helper, without changing any Git config.
        transport_configuration(repo)
        env = custody.git_environment()
        env['GIT_ALLOW_PROTOCOL'] = 'https'
        return self.command(['git', '--no-replace-objects', '-c', 'core.hooksPath=/dev/null',
                             '-c', 'core.fsmonitor=false', '-c', 'maintenance.auto=false',
                             '-c', 'gc.auto=0', '-c', 'credential.helper=',
                             '-c', 'credential.helper=!gh auth git-credential',
                             '-c', 'push.followTags=false', '-c', 'push.recurseSubmodules=no',
                             '-C', str(repo), *args],
                            env=env, timeout=300)

    def snapshot(self, row, repo):
        full = row['repository']
        info = self.api('repos/' + full)
        require(info['id'] == row['repository_id'] and info['full_name'] == full and
                info['owner']['login'] == OWNER and info['owner']['id'] == OWNER_ID and
                info['private'] is False and info.get('visibility', 'public') == 'public',
                'Repository identity/visibility mismatch: ' + full)
        require(info['default_branch'] == row['donor_default_preserved']['name'],
                'Default branch name changed: ' + full)
        default_ref = 'refs/heads/' + info['default_branch']
        raw = self.transport(repo, 'ls-remote', '--refs', 'https://github.com/' + full + '.git',
                             TARGET_REF, default_ref)
        refs = {}
        for line in raw.splitlines():
            oid, ref = line.split('\t')
            require(ref in (TARGET_REF, default_ref) and ref not in refs, 'Unexpected remote ref response')
            refs[ref] = oid
        require(default_ref in refs, 'Default ref inaccessible')
        actual = refs.get(TARGET_REF)
        state = 'absent' if actual is None else ('exact' if actual == row['proposed_commit'] else 'conflicting')
        tree = None
        if state == 'exact':
            commit = self.api('repos/' + full + '/git/commits/' + actual)
            tree = commit['tree']['sha']
            require(commit['sha'] == actual and tree == row['proposed_tree'], 'Remote commit/tree mismatch')
        policy = self.api('repos/' + full + '/actions/permissions')
        require(type(policy.get('enabled')) is bool, 'Actions enabled state inaccessible')
        runs = []
        for page in self.api('repos/' + full + '/actions/runs?per_page=100', pages=True):
            require(isinstance(page.get('workflow_runs'), list), 'Workflow run visibility inaccessible')
            runs += [{k: run.get(k) for k in ('id', 'status', 'conclusion', 'head_sha', 'head_branch', 'event', 'created_at')}
                     for run in page['workflow_runs']]
        hooks = []
        for page in self.api('repos/' + full + '/hooks?per_page=100', pages=True):
            require(isinstance(page, list), 'Repository hook visibility inaccessible')
            hooks += [{k: hook.get(k) for k in ('id', 'name', 'active', 'events')} for hook in page]
        require(all(type(hook.get('active')) is bool and isinstance(hook.get('events'), list) for hook in hooks),
                'Incomplete repository hook response')
        checks, statuses = [], []
        for oid in sorted({refs[default_ref]} | ({actual} if state == 'exact' else set())):
            for page in self.api('repos/' + full + '/commits/' + oid + '/check-runs?per_page=100', pages=True):
                require(isinstance(page.get('check_runs'), list), 'Check-run visibility inaccessible')
                for check in page['check_runs']:
                    checks.append({'commit': oid, **{k: check.get(k) for k in ('id', 'name', 'status', 'conclusion')},
                                   'app': {k: (check.get('app') or {}).get(k) for k in ('id', 'slug')}})
            for page in self.api('repos/' + full + '/commits/' + oid + '/status?per_page=100', pages=True):
                require(isinstance(page.get('statuses'), list), 'Commit-status visibility inaccessible')
                for status in page['statuses']:
                    statuses.append({'commit': oid, **{k: status.get(k) for k in ('id', 'state', 'context')},
                                     'creator': {k: (status.get('creator') or {}).get(k) for k in ('id', 'login')}})
        return {'repository': full, 'repository_id': info['id'], 'public': True,
                'default': {'name': info['default_branch'], 'sha': refs[default_ref]},
                'historical_default_moved': refs[default_ref] != row['donor_default_preserved']['sha'],
                'ref_state': state, 'commit': actual, 'tree': tree, 'actions': policy,
                'runs': runs, 'hooks': hooks, 'checks': checks, 'statuses': statuses,
                'automation_scope': 'Visible hooks, all Actions runs, and checks/statuses on current default/review commits; no assertion about unexposed third-party app subscriptions.'}

    def disable_actions(self, row):
        return self.api('repos/' + row['repository'] + '/actions/permissions',
                        method='PUT', payload={'enabled': False})

    def push(self, row, repo):
        return self.transport(repo, *push_arguments(row, 'https://github.com/' + row['repository'] + '.git'))


def push_arguments(row, destination):
    require(row['target_ref'] == TARGET_REF, 'Unauthorized destination ref')
    # Empty expected value means that *any* concurrently created ref rejects the
    # push, including an ancestor that an ordinary push would fast-forward.
    return ['push', '--porcelain', '--force-with-lease=' + TARGET_REF + ':',
            destination, row['proposed_commit'] + ':' + TARGET_REF]


def transport_configuration(repo):
    # A URL rewrite, push refspec/recurse setting, injected helper or proxy could
    # turn a syntactically bounded command into a different external operation.
    # These independent recovery repos need only Git's four initialization keys.
    allowed = {'core.repositoryformatversion': {'0'}, 'core.filemode': {'true', 'false'},
               'core.bare': {'false'}, 'core.logallrefupdates': {'true'}}
    config = custody.git(repo, 'config', '--local', '--list').decode()
    for line in config.splitlines():
        key, separator, value = line.partition('=')
        require(separator and key in allowed and value in allowed[key],
                'Unexpected local Git transport configuration: ' + key)


def verify_local(repo, row, root, run):
    custody.independent(repo)
    transport_configuration(repo)
    require(custody.git(repo, 'rev-parse', 'HEAD').decode().strip() == row['proposed_commit'], 'Local commit changed')
    require(custody.git(repo, 'rev-parse', 'HEAD^{tree}').decode().strip() == row['proposed_tree'], 'Local tree changed')
    require(not custody.git(repo, 'status', '--porcelain', '--untracked-files=all').strip(), 'Local source is dirty')
    custody.git(repo, 'merge-base', '--is-ancestor', row['accepted_base_commit'], row['proposed_commit'])
    for record in root.get('retained_product_bundles', []):
        bundle = custody.verified_file(run, record['path'], record['sha256'], record['bytes'])
        require(custody.bundle_header(bundle)['prerequisites'] == record['prerequisites'], 'Bundle prerequisites changed')
        custody.git(repo, 'bundle', 'verify', str(bundle))
    return {'path': str(repo), 'commit': row['proposed_commit'], 'tree': row['proposed_tree'],
            'clean': True, 'recovery_receipt_sha256': RECOVERY_SHA256}


def automation_clear(state):
    require(not [run for run in state['runs'] if run['status'] != 'completed'], 'Unresolved pending/running Actions executions')
    require(not [hook for hook in state['hooks'] if hook['active'] and
                 (set(hook['events']) & {'push', 'create', '*'})], 'Active external push/create hook requires review')
    require(not [check for check in state.get('checks', []) if check['status'] != 'completed'],
            'Unresolved check executions')
    require(not [check for check in state.get('checks', []) if check['app']['slug'] != 'github-actions'],
            'Observed external check app requires containment review')
    require(not [status for status in state.get('statuses', []) if status['state'] == 'pending'],
            'Unresolved commit status execution')
    require(not [status for status in state.get('statuses', []) if status['creator']['login'] != 'github-actions[bot]'],
            'Observed external commit status integration requires containment review')


def unchanged_identity(before, after):
    require(before['repository_id'] == after['repository_id'] and
            before['default']['name'] == after['default']['name'], 'Repository/default identity changed')


def promote(rows, auth, findings, run, roots, github, receipt, *, apply=False, only=None, local_check=verify_local):
    selected = set(only) if only else {row['root_id'] for row in rows}
    require(selected <= {row['root_id'] for row in rows}, 'Unknown --only root')
    receipt.emit('authorization', verified=github.authorize(auth))
    results = {}
    writes = {'settings': 0, 'source_refs': 0}
    # The child is published before the client gitlink parent.
    for row in sorted(rows, key=lambda value: value['root_id'] == 'mapstore-client'):
        key = row['root_id']
        if key not in selected:
            continue
        try:
            repo = custody.confined(run, roots[key]['relative_path'])
            local = local_check(repo, row, roots[key], run)
            before = github.snapshot(row, repo)
            receipt.emit('before', root_id=key, local=local, remote=before, publication=findings[key])
            require(before['ref_state'] != 'conflicting', 'Conflicting existing review ref; no overwrite authorized')
            automation_clear(before)
            state = before
            if apply and before['actions']['enabled']:
                github.authorize(auth)
                state = github.snapshot(row, repo)
                unchanged_identity(before, state)
                require(state['ref_state'] != 'conflicting', 'Concurrent conflicting ref before Actions change')
                automation_clear(state)
                if state['actions']['enabled']:
                    receipt.emit('attempt', root_id=key, operation='disable_actions',
                                 method='PUT', endpoint='repos/' + row['repository'] + '/actions/permissions',
                                 payload={'enabled': False}, before=state)
                    writes['settings'] += 1
                    try:
                        response = github.disable_actions(row)
                        receipt.emit('response', root_id=key, operation='disable_actions', response=response)
                    except (ValueError, OSError) as exc:
                        receipt.emit('uncertain', root_id=key, operation='disable_actions', error=str(exc))
                    # Reconcile every write once before taking any other action; do
                    # not blindly retry even if a request timed out.
                    state = github.snapshot(row, repo)
                    receipt.emit('reconciled', root_id=key, operation='disable_actions', remote=state)
                    unchanged_identity(before, state)
                    require(state['actions']['enabled'] is False, 'Actions disablement not verified; owner UI action required')
                    automation_clear(state)
            finding = findings[key]
            require(finding['disposition'] == 'publishable', 'Publication hold: ' + finding['basis'])
            if key == 'mapstore-client':
                child = next(value for value in rows if value['root_id'] == 'mapstore')
                require(findings['mapstore']['disposition'] == 'publishable', 'Dependent MapStore source publication held')
                child_repo = custody.confined(run, roots['mapstore']['relative_path'])
                child_state = github.snapshot(child, child_repo)
                require(child_state['ref_state'] == 'exact' and child_state['actions']['enabled'] is False,
                        'Dependent owned MapStore review ref is not verified published/contained')
                automation_clear(child_state)
            if not apply:
                status = 'already-exact' if state['ref_state'] == 'exact' else 'ready'
                receipt.emit('result', root_id=key, status=status, remote=state,
                             proposed_settings_writes=int(state['actions']['enabled']),
                             proposed_source_writes=int(state['ref_state'] == 'absent'))
                results[key] = status
                continue
            github.authorize(auth)
            local_check(repo, row, roots[key], run)
            state = github.snapshot(row, repo)
            unchanged_identity(before, state)
            require(state['actions']['enabled'] is False, 'Actions not disabled immediately before promotion')
            require(state['ref_state'] != 'conflicting', 'Concurrent conflicting review ref; creation refused')
            automation_clear(state)
            status = 'already-exact'
            if state['ref_state'] == 'absent':
                command = push_arguments(row, 'https://github.com/' + row['repository'] + '.git')
                receipt.emit('attempt', root_id=key, operation='create_ref', git_arguments=command, before=state)
                writes['source_refs'] += 1
                try:
                    response = github.push(row, repo)
                    receipt.emit('response', root_id=key, operation='create_ref', response=response)
                except (ValueError, OSError) as exc:
                    receipt.emit('uncertain', root_id=key, operation='create_ref', error=str(exc))
                state = github.snapshot(row, repo)
                receipt.emit('reconciled', root_id=key, operation='create_ref', remote=state)
                status = 'created-or-reconciled'
            unchanged_identity(before, state)
            require(state['ref_state'] == 'exact', 'Review ref creation not verified; reconcile before a later explicit retry')
            require(state['actions']['enabled'] is False, 'Actions containment changed after promotion')
            automation_clear(state)
            original_runs = {item['id'] for item in before['runs']}
            require(not [item for item in state['runs'] if item['id'] not in original_runs and
                         item['head_sha'] == row['proposed_commit'] and item['head_branch'] == TARGET_REF.removeprefix('refs/heads/')],
                    'Unexpected promotion-triggered workflow run')
            receipt.emit('result', root_id=key, status=status, remote=state,
                         default_moved_during_operation=before['default'] != state['default'])
            results[key] = status
        except (ValueError, OSError, KeyError, TypeError) as exc:
            results[key] = 'held'
            receipt.emit('result', root_id=key, status='held', error=str(exc))
    receipt.emit('summary', results=results, attempted_mutations=writes, apply=apply)
    return results, writes


def runtime_context():
    origin = subprocess.run(['git', '-C', str(PLATFORM), 'remote', 'get-url', 'origin'],
                            capture_output=True, text=True, check=True).stdout.strip()
    require(origin in ('https://github.com/aloerch/ambisgis-platform.git',
                       'git@github.com:aloerch/ambisgis-platform.git'), 'Platform origin mismatch')
    custody.git(PLATFORM, 'merge-base', '--is-ancestor', BASE_MERGE, 'HEAD')
    return {'platform': str(PLATFORM), 'cwd': str(Path.cwd()), 'origin': origin,
            'branch': custody.git(PLATFORM, 'branch', '--show-current').decode().strip(),
            'head': custody.git(PLATFORM, 'rev-parse', 'HEAD').decode().strip(),
            'working_changes': custody.git(PLATFORM, 'status', '--porcelain').decode(),
            'implementation_sha256': custody.sha(Path(__file__))}



CANONICAL_PLAN = PLATFORM / 'plan/verification/source-ref-promotion/canonical-proposal.json'
CANONICAL_SHA256 = '519dd189533c6d077648f0b9bbf1f98e052e28d4d614414b6c04f141deb0d28d'
CANONICAL_HEAD = '7d5ceb06f7a1814d4a95b7e4b05a2b46d8728720'
CANONICAL_BASE = '0df95126d9fecd9df3cf1fd0cd88ab565a680989'
CANONICAL_REF = 'refs/heads/ambisgis/main'
CANONICAL_COMMENT_ID = 5863464446
CANONICAL_COMMENT_URL = 'https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863464446'
CANONICAL_COMMENT_DATE = '2026-09-28T04:35:51Z'
CANONICAL_COMMENT_SHA256 = '87d79df2d4458d9570c269ff9d20310c4117f7d82c2dc23d4588ca505900da1f'
CANONICAL_ROOTS = frozenset(('postgresql', 'postgis', 'jupyterhub', 'jupyterlab',
                            'geowebcache', 'geoserver', 'geonode', 'mapstore', 'mapstore-client'))
PUBLICATION_SHA256 = '0133d14729dac54a7680418b4f54977f0a6d607992cbe3bd5cfdcbb794aecf84'
COMPANION = PLATFORM / 'plan/verification/source-ref-promotion/public-companion-readback.json'
COMPANION_SHA256 = '3641e9223746b5ebda6451cce5153b74c7d2990b88aa7842aa9438a6e4d5616e'
DELIVERY = PLATFORM / 'plan/verification/source-ref-promotion/remote-delivery.json'
DELIVERY_SHA256 = 'ea237c635a6990d739ffe1cb9fe191e2f506c947f33400f286b3586822389e90'


def canonical_authorization_identity(record):
    require(record.get('schema_version') == 1 and
            record.get('canonical_proposal_sha256') == CANONICAL_SHA256,
            'Authorization is not bound to immutable canonical proposal')
    comment = record['comment']
    require(comment['id'] == CANONICAL_COMMENT_ID and comment['html_url'] == CANONICAL_COMMENT_URL and
            comment['issue_url'] == 'https://api.github.com/repos/aloerch/ambisgis-platform/issues/6' and
            comment['user']['login'] == OWNER and comment['user']['id'] == OWNER_ID and
            comment['created_at'] == CANONICAL_COMMENT_DATE and comment['updated_at'] == CANONICAL_COMMENT_DATE,
            'Wrong canonical owner decision identity/date')
    require(record['body_sha256'] == CANONICAL_COMMENT_SHA256 and
            digest_bytes(comment['body'].encode()) == CANONICAL_COMMENT_SHA256,
            'Canonical owner decision body changed')
    return comment


def canonical_rows(plan_path=CANONICAL_PLAN):
    proposal = bound_json(plan_path, CANONICAL_SHA256)
    require(proposal['plan_sha256'] == PLAN_SHA256, 'Canonical original plan mismatch')
    original = {r['root_id']: r for r in bound_json(PLAN, PLAN_SHA256)['repositories']}
    eligible = [r for r in proposal['repositories'] if r['eligible_for_requested_separate_authorization']]
    require(len(eligible) == 9 and {r['root_id'] for r in eligible} == CANONICAL_ROOTS,
            'Wrong canonical repository set; held roots are excluded')
    result = []
    for row in eligible:
        require(row['target_ref'] == CANONICAL_REF and row['expected_old_commit'] is None and
                row['review_ref'] == TARGET_REF and row['hold'] is None and
                row['actions_to_preserve'] == {'enabled': False}, 'Invalid canonical boundary')
        source = original[row['root_id']]
        require(all(row[key] == source[key] for key in
                    ('repository', 'repository_id', 'proposed_commit', 'proposed_tree')),
                'Canonical identity differs from original approved source')
        result.append({**source, **row})
    return result


def validate_canonical_inputs(authorization_path, publication_path, publication_sha, workspace):
    require(publication_sha == PUBLICATION_SHA256, 'Canonical publication findings changed')
    rows = canonical_rows()
    auth = json.loads(Path(authorization_path).read_text())
    canonical_authorization_identity(auth)
    publication = bound_json(publication_path, PUBLICATION_SHA256)
    require(publication['plan_sha256'] == PLAN_SHA256, 'Canonical publication plan mismatch')
    findings = {r['root_id']: r for r in publication['repositories']}
    run = custody.confined(workspace, RECOVERY_PATH)
    recovery = bound_json(custody.confined(run, 'recovery.json'), RECOVERY_SHA256)
    roots = {r['id']: r for r in recovery['roots']}
    delivery = bound_json(DELIVERY, DELIVERY_SHA256)
    delivered = {r['root_id']: r for r in delivery['repositories']}
    bound_json(COMPANION, COMPANION_SHA256)
    for row in rows:
        key = row['root_id']
        finding, root, prior = findings[key], roots[key], delivered[key]
        require(all(finding[k] == row[k] for k in
                    ('repository', 'repository_id', 'proposed_commit', 'proposed_tree')) and
                finding['disposition'] == 'publishable', 'Canonical publication identity/hold mismatch')
        require(root['repository'] == row['repository'] and root['repository_id'] == row['repository_id'] and
                root['commit'] == row['proposed_commit'] and root['tree'] == row['proposed_tree'] and
                root['relative_path'] == 'repos/' + key, 'Canonical recovery identity mismatch')
        require(prior['status'] == 'verified' and prior['commit'] == row['proposed_commit'] and
                prior['tree'] == row['proposed_tree'], 'Prior full-history delivery evidence mismatch')
    return rows, auth, findings, run, roots


class CanonicalGitHub(GitHub):
    @staticmethod
    def public_bytes(url):
        # Anonymous HTTPS only: public availability cannot be inferred from an
        # authenticated contents API. Do not use mutable branch URLs.
        require(url.startswith('https://raw.githubusercontent.com/aloerch/ambisgis-platform/'),
                'Unexpected public companion host/repository')
        with urlopen(url, timeout=60) as response:
            require(response.status == 200 and response.url == url, 'Public readback redirected or failed')
            return response.read()

    def authorize(self, auth):
        expected = canonical_authorization_identity(auth)
        viewer = self.api('user')
        require(viewer['login'] == OWNER and viewer['id'] == OWNER_ID, 'Authenticated owner mismatch')
        platform = self.api('repos/aloerch/ambisgis-platform')
        require(platform['id'] == 1376927351 and platform['full_name'] == 'aloerch/ambisgis-platform' and
                platform['owner']['id'] == OWNER_ID and platform['private'] is False,
                'Platform repository identity mismatch')
        live = self.api('repos/aloerch/ambisgis-platform/issues/comments/' + str(CANONICAL_COMMENT_ID))
        canonical_authorization_identity({'schema_version': 1, 'canonical_proposal_sha256': CANONICAL_SHA256,
                                          'comment': live, 'body_sha256': CANONICAL_COMMENT_SHA256})
        require(live['body'] == expected['body'], 'Live canonical owner authorization changed')
        url = ('https://raw.githubusercontent.com/aloerch/ambisgis-platform/' + CANONICAL_HEAD +
               '/plan/verification/source-ref-promotion/canonical-proposal.json')
        require(digest_bytes(self.public_bytes(url)) == CANONICAL_SHA256, 'Live immutable canonical proposal changed')
        return {'login': OWNER, 'id': OWNER_ID, 'comment_id': live['id'],
                'comment_url': live['html_url'], 'body_sha256': CANONICAL_COMMENT_SHA256,
                'created_at': live['created_at'], 'updated_at': live['updated_at'],
                'canonical_proposal_sha256': CANONICAL_SHA256, 'proposal_url': url}

    def companion(self):
        manifest = bound_json(COMPANION, COMPANION_SHA256)
        def verify(record):
            data = self.public_bytes(record['public_url'])
            require(len(data) == record['bytes'] and digest_bytes(data) == record['sha256'],
                    'Public companion missing or changed: ' + record['path'])
            return {'path': record['path'], 'sha256': record['sha256'], 'bytes': len(data)}
        with ThreadPoolExecutor(max_workers=5) as pool:
            files = list(pool.map(verify, manifest['files']))
        return {'manifest_sha256': COMPANION_SHA256, 'files': files, 'anonymous_byte_readback': True}

    def snapshot(self, row, repo):
        state = super().snapshot(row, repo)
        require(state['ref_state'] == 'exact', 'Approved review ref is not exact')
        state['review'] = {'ref': TARGET_REF, 'commit': state['commit'], 'tree': state['tree']}
        default = row['default_to_preserve']
        require(state['default'] == {'name': default['name'], 'sha': default['commit']},
                'Default ref/name differs from canonical proposal')
        raw = self.transport(repo, 'ls-remote', '--refs', 'https://github.com/' + row['repository'] + '.git',
                             CANONICAL_REF, TARGET_REF, 'refs/heads/' + default['name'])
        refs = {}
        for line in raw.splitlines():
            oid, ref = line.split('\t')
            require(ref in (CANONICAL_REF, TARGET_REF, 'refs/heads/' + default['name']) and ref not in refs,
                    'Unexpected canonical remote ref response')
            refs[ref] = oid
        require(refs.get(TARGET_REF) == row['proposed_commit'] and
                refs.get('refs/heads/' + default['name']) == default['commit'],
                'Concurrent review/default ref change')
        actual = refs.get(CANONICAL_REF)
        state.update(ref_state='absent' if actual is None else
                     ('exact' if actual == row['proposed_commit'] else 'conflicting'), commit=actual, tree=None)
        if state['ref_state'] == 'exact':
            commit = self.api('repos/' + row['repository'] + '/git/commits/' + actual)
            require(commit['sha'] == actual and commit['tree']['sha'] == row['proposed_tree'],
                    'Canonical remote commit/tree mismatch')
            state['tree'] = commit['tree']['sha']
        return state

    def create_canonical(self, row):
        # GitHub's create-reference endpoint refuses an existing ref; there is
        # deliberately no update-ref API, force option, Git push or settings call.
        expected = {r['root_id']: r for r in canonical_rows()}
        require(row == expected.get(row['root_id']), 'Unapproved canonical mutation row')
        return self.api('repos/' + row['repository'] + '/git/refs', method='POST',
                        payload={'ref': CANONICAL_REF, 'sha': row['proposed_commit']})

    def submodule(self, repo, row, child):
        path = 'geonode_mapstore_client/client/MapStore2'
        entry = custody.git(repo, 'ls-tree', row['proposed_commit'], '--', path).decode().strip()
        require(entry == '160000 commit ' + child['proposed_commit'] + '\t' + path,
                'Client approved MapStore gitlink mismatch')
        donor = 'https://github.com/geosolutions-it/MapStore2.git'
        owned = 'https://github.com/aloerch/ambisgis-mapstore.git'
        declarations = custody.git(repo, 'config', '--blob', row['proposed_commit'] + ':.gitmodules',
                                   '--get-regexp', r'^submodule\..*\.url$').decode().splitlines()
        require(len(declarations) == 1, 'Unexpected submodule declarations')
        key, declared_url = declarations[0].split(' ', 1)
        require(declared_url == donor and custody.git(repo, 'config', '--blob', row['proposed_commit'] +
                ':.gitmodules', '--get', key[:-3] + 'path').decode().strip() == path,
                'Unreviewed submodule declaration')
        args = ['-c', 'url.' + owned + '.insteadOf=' + donor,
                'ls-remote', '--exit-code', '--refs', donor, CANONICAL_REF]
        readback = self.transport(repo, *args).strip()
        require(readback == child['proposed_commit'] + '\t' + CANONICAL_REF,
                'Owned submodule process-only URL override readback mismatch')
        return {'from': donor, 'to': owned, 'path': path, 'gitlink': child['proposed_commit'],
                'arguments': args, 'readback': readback, 'scope': 'process-only; .gitmodules unchanged'}


def canonical_clear(row, state):
    require(state['repository_id'] == row['repository_id'] and state['repository'] == row['repository'],
            'Canonical repository identity changed')
    require(state['default'] == {'name': row['default_to_preserve']['name'],
                                'sha': row['default_to_preserve']['commit']}, 'Canonical default changed')
    require(state['review'] == {'ref': TARGET_REF, 'commit': row['proposed_commit'],
                               'tree': row['proposed_tree']}, 'Canonical review ref/tree changed')
    require(state['actions']['enabled'] is False, 'Actions must already be disabled; no settings change authorized')
    require(state['ref_state'] != 'conflicting', 'Canonical collision; no overwrite or fast-forward authorized')
    automation_clear(state)


def promote_canonical(rows, auth, findings, run, roots, github, receipt, *, apply=False, only=None,
                      local_check=verify_local):
    approved = {r['root_id']: r for r in canonical_rows()}
    require(len(rows) == 9 and {r['root_id'] for r in rows} == CANONICAL_ROOTS and
            all(row == approved[row['root_id']] for row in rows), 'Unapproved canonical row identity/set')
    selected = set(only) if only else CANONICAL_ROOTS
    require(selected <= CANONICAL_ROOTS, 'Unknown or held --only canonical root')
    receipt.emit('authorization', verified=github.authorize(auth))
    results, writes = {}, {'settings': 0, 'source_refs': 0}
    for row in sorted(rows, key=lambda value: value['root_id'] == 'mapstore-client'):
        key = row['root_id']
        if key not in selected:
            continue
        try:
            repo = custody.confined(run, roots[key]['relative_path'])
            local = local_check(repo, row, roots[key], run)
            require(findings[key]['disposition'] == 'publishable', 'Canonical publication hold')
            before = github.snapshot(row, repo)
            receipt.emit('before', root_id=key, local=local, remote=before,
                         reused_full_history_delivery_sha256=DELIVERY_SHA256)
            canonical_clear(row, before)
            # Recheck all public notices immediately before every possible create.
            receipt.emit('public_companion', root_id=key, verified=github.companion())
            receipt.emit('authorization', root_id=key, verified=github.authorize(auth))
            if key == 'mapstore-client':
                child = approved['mapstore']
                child_state = github.snapshot(child, custody.confined(run, roots['mapstore']['relative_path']))
                canonical_clear(child, child_state)
                require(child_state['ref_state'] == 'exact', 'Owned MapStore canonical ref not delivered')
                receipt.emit('submodule', root_id=key, verified=github.submodule(repo, row, child), remote=child_state)
            state = github.snapshot(row, repo)
            canonical_clear(row, state)
            require(state['actions'] == before['actions'], 'Actions policy changed during canonical operation')
            status = 'already-exact' if state['ref_state'] == 'exact' else 'ready'
            if apply and state['ref_state'] == 'absent':
                receipt.emit('attempt', root_id=key, operation='create_canonical_ref',
                             method='POST', endpoint='repos/' + row['repository'] + '/git/refs',
                             payload={'ref': CANONICAL_REF, 'sha': row['proposed_commit']}, before=state)
                writes['source_refs'] += 1
                try:
                    response = github.create_canonical(row)
                    receipt.emit('response', root_id=key, operation='create_canonical_ref', response=response)
                except (ValueError, OSError) as exc:
                    receipt.emit('uncertain', root_id=key, operation='create_canonical_ref', error=str(exc))
                # Never retry here. A failed readback remains held; a new invocation
                # must observe actual remote state before another explicit attempt.
                state = github.snapshot(row, repo)
                receipt.emit('reconciled', root_id=key, operation='create_canonical_ref', remote=state)
                canonical_clear(row, state)
                require(state['ref_state'] == 'exact', 'Canonical delivery unverified; reconcile before any retry')
                require(state['actions'] == before['actions'], 'Actions policy changed after canonical creation')
                original_runs = {item['id'] for item in before['runs']}
                require(not [item for item in state['runs'] if item['id'] not in original_runs and
                             item['head_sha'] == row['proposed_commit'] and
                             item['head_branch'] == CANONICAL_REF.removeprefix('refs/heads/')],
                        'Unexpected canonical-triggered workflow run')
                status = 'created-or-reconciled'
            receipt.emit('result', root_id=key, status=status, remote=state,
                         proposed_settings_writes=0, proposed_source_writes=int(state['ref_state'] == 'absent'))
            results[key] = status
        except (ValueError, OSError, KeyError, TypeError) as exc:
            results[key] = 'held'
            receipt.emit('result', root_id=key, status='held', error=str(exc))
    receipt.emit('summary', results=results, attempted_mutations=writes, apply=apply, mode='canonical')
    return results, writes

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-root', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--publication-evidence', type=Path, required=True)
    parser.add_argument('--publication-sha256', required=True)
    parser.add_argument('--receipt', type=Path, required=True, help='New JSONL receipt; existing evidence is never replaced')
    parser.add_argument('--only', nargs='+', help='Bounded subset of approved root IDs')
    parser.add_argument('--canonical', action='store_true', help='Separate nine-row owner authorization; creates only absent canonical refs, never settings')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    receipt = None
    try:
        receipt = Receipt(args.receipt)
        receipt.emit('started', schema_version=1, apply=args.apply, plan_sha256=PLAN_SHA256,
                     recovery_sha256=RECOVERY_SHA256, publication_sha256=args.publication_sha256,
                     context=runtime_context())
        if args.canonical:
            custody.git(PLATFORM, 'merge-base', '--is-ancestor', CANONICAL_BASE, 'HEAD')
            receipt.emit('canonical_scope', canonical_proposal_sha256=CANONICAL_SHA256,
                         excluded_roots=['geotools', 'qgis'], target_ref=CANONICAL_REF)
            rows, auth, findings, run, roots = validate_canonical_inputs(
                args.authorization, args.publication_evidence, args.publication_sha256, args.workspace_root)
            results, writes = promote_canonical(rows, auth, findings, run, roots, CanonicalGitHub(), receipt,
                                                apply=args.apply, only=args.only)
        else:
            rows, auth, findings, run, roots = validate_inputs(PLAN, args.authorization, args.publication_evidence,
                                                              args.publication_sha256, args.workspace_root)
            results, writes = promote(rows, auth, findings, run, roots, GitHub(), receipt, apply=args.apply, only=args.only)
        print(json.dumps({'results': results, 'attempted_mutations': writes, 'receipt': str(args.receipt)}, indent=2))
        return 2 if 'held' in results.values() else 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        if receipt:
            receipt.emit('failed', error=str(exc))
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if receipt:
            receipt.close()


if __name__ == '__main__':
    raise SystemExit(main())
