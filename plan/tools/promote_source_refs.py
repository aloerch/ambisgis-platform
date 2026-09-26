#!/usr/bin/env python3
"""Promote only PR #69's exact FND-07 review refs; default is read-only.

Application requires the unchanged separate owner decision and hashed publication
findings. Each invocation writes a NEW fsynced JSONL receipt. Resume by a new
invocation: actual remote state, never the prior receipt, determines operations.
Repository Actions may be disabled for a publication-held row; its source is not
uploaded. No canonical refs, defaults, workflow files or releases are changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-root', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--publication-evidence', type=Path, required=True)
    parser.add_argument('--publication-sha256', required=True)
    parser.add_argument('--receipt', type=Path, required=True, help='New JSONL receipt; existing evidence is never replaced')
    parser.add_argument('--only', nargs='+', help='Bounded subset of approved root IDs')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    receipt = None
    try:
        receipt = Receipt(args.receipt)
        receipt.emit('started', schema_version=1, apply=args.apply, plan_sha256=PLAN_SHA256,
                     recovery_sha256=RECOVERY_SHA256, publication_sha256=args.publication_sha256,
                     context=runtime_context())
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
