#!/usr/bin/env python3
"""Deliver only the two exact owner-authorized FND-07 source successors.

Default is read-only. --apply creates absent review/canonical refs; exact refs
are no-ops and every other value is a collision. No ref updates, settings
mutations, defaults, releases, workflow execution or source regeneration.
Each invocation creates a new fsynced journal; retries always reconcile live
state. Independent remote recovery remains a separate acceptance operation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
PLATFORM = Path(__file__).resolve().parents[2]
AUTH_SHA = '40d4bac51de35df99aa81f7c16db45f54644145272ce0a5f424aca208f38c402'
PROPOSAL = PLATFORM / 'plan/verification/canonical-and-publication-repairs/next-source-publication.json'
PROPOSAL_SHA = '1510cba3c5d96fa4be7f464352541277b41fc53629445fcb10ffcd4904cb7bdb'
BASE = '5213f31cd51aed5230d7bd550cc03662bcfb566f'
RUN = 'build-worktrees/canonical-and-publication-repairs/run-002'
LOCAL = {
    'geotools': ('geotools-v2/source', 'geotools-v2/receipt.json',
                '5fe6003847a95da95a280a958b1e27fdbf0ecd43a219251e257827c46534a2f8'),
    'qgis': ('qgis/attempt-003/source.git', 'qgis/attempt-003/result.json',
             'f9828bf21e349a596c3ed16c58287c4f26dce1a271aab5f4cf15ab336f20d4eb'),
}


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, PLATFORM / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


P = module('successor_promotion_guards', 'plan/tools/promote_source_refs.py')
require = P.require


def rows():
    """The prior proposal remains historical, hash-bound and unmodified."""
    return P.bound_json(PROPOSAL, PROPOSAL_SHA)['repositories']


def approved(row):
    require(row in rows(), 'Unapproved source successor row')


def local_check(row, workspace):
    approved(row)
    root = P.custody.confined(workspace, RUN)
    relative, receipt_relative, digest = LOCAL[row['root_id']]
    source = P.custody.confined(root, relative)
    receipt = P.custody.verified_file(root, receipt_relative, digest)
    if row['root_id'] == 'geotools':
        tool = module('successor_geotools', 'build-support/source_publication/geotools_notice.py')
        result = tool.verify(workspace,
            PLATFORM / 'plan/verification/canonical-and-publication-repairs/authorization.json',
            receipt.parent, digest)
        P.custody.git(source, 'fsck', '--full', '--strict')
    else:
        tool = module('successor_qgis', 'build-support/source_publication/qgis_snapshot.py')
        report = tool.trusted_receipt(receipt, digest)
        provenance = json.loads(Path(report['provenance']['path']).read_text())
        expected = json.loads(Path(report['expected_tree']['path']).read_text())
        forbidden = set(json.loads(Path(report['forbidden_objects']['path']).read_text()))
        original_source = P.custody.confined(workspace, 'build-worktrees/source-baseline-restore/run-001/repos/qgis')
        selection_path = P.custody.confined(workspace, 'build-worktrees/java-gmt-remediation/qgis/selection-01/selection.json')
        selection, omitted = tool.load_selection(selection_path)
        require(tool.git(original_source, 'rev-parse', tool.BASE + '^{tree}').decode().strip() == tool.BASE_TREE,
                'Original QGIS source identity changed')
        original = tool.tree_entries(original_source, tool.BASE)
        require(forbidden == {original[p]['oid'] for p in omitted}, 'Forbidden object map changed')
        require(expected[tool.PROVENANCE]['oid'] == tool.blob_id(tool.encoded(provenance)),
                'Source provenance changed')
        result = {'comparison': tool.verify_complete_delta(original, expected, provenance, omitted, original_source)}
        for key in ('source', 'restore'):
            item = report[key]
            require(item['commit'] == row['proposed_commit'] and item['tree'] == row['proposed_tree'],
                    'QGIS successor identity changed')
            result[key] = tool.verify_repository(Path(item['path']), item['commit'], item['tree'], expected, forbidden)
        sys.path.insert(0, str(PLATFORM / 'build-support/qgis'))
        try:
            from publication_selection import publication_variant_stage
            resources = report['resources']; restored = report['restore']
            actual = publication_variant_stage(Path(restored['path']), restored['commit'], restored['tree'],
                expected, provenance, selection_path, selection_path.parent / 'after-manifest.json',
                Path(resources['output']), Path(resources['replay_output']), verify_only=True)
        finally:
            sys.path.pop(0)
        for key in ('inventory_sha256', 'catalogue_notice_only_changes', 'relocated_original_metadata',
                    'selected_entries', 'unchanged_entries', 'catalogue_effective_xml_equal'):
            require(actual[key] == resources[key], 'QGIS resource comparison changed: ' + key)
        result['resources'] = {key: actual[key] for key in
            ('inventory_sha256', 'selected_entries', 'unchanged_entries', 'catalogue_effective_xml_equal')}
    require(P.custody.git(source, 'rev-parse', row['proposed_commit'] + '^{tree}').decode().strip() ==
            row['proposed_tree'], 'Source tree identity changed')
    transport_configuration(source)
    return {'path': str(source), 'commit': row['proposed_commit'], 'tree': row['proposed_tree'],
            'receipt_sha256': digest, 'verified': result}


def transport_configuration(repo):
    allowed = {'core.repositoryformatversion': {'0'}, 'core.filemode': {'true', 'false'},
               'core.bare': {'true', 'false'}, 'core.logallrefupdates': {'true'}}
    for line in P.custody.git(repo, 'config', '--local', '--list').decode().splitlines():
        key, separator, value = line.partition('=')
        require(separator and key in allowed and value in allowed[key], 'Unexpected transport config: ' + key)


def creation_arguments(commit, ref, destination):
    # Same server-side absent-value lease used by the reviewed baseline publisher.
    # Despite the Git option name, no existing ref can be updated or overwritten,
    # including a concurrently created ancestor that a normal push would advance.
    require(re.fullmatch('[0-9a-f]{40}', commit) and
            ref in {r['destinations'][0]['ref'] for r in rows()}, 'Invalid creation-only source target')
    return ['push', '--porcelain', '--force-with-lease=' + ref + ':', destination, commit + ':' + ref]


class GitHub(P.CanonicalGitHub):
    def authorize(self, path):
        require(P.custody.sha(path) == AUTH_SHA, 'Standing owner delegation bytes changed')
        viewer = self.api('user')
        require(viewer['login'] == P.OWNER and viewer['id'] == P.OWNER_ID, 'Authenticated owner mismatch')
        info = self.api('repos/aloerch/ambisgis-platform')
        require(info['id'] == 1376927351 and info['full_name'] == 'aloerch/ambisgis-platform' and
                info['owner']['login'] == P.OWNER and info['owner']['id'] == P.OWNER_ID and info['private'] is False,
                'Platform repository identity mismatch')
        return {'login': P.OWNER, 'id': P.OWNER_ID, 'delegation_sha256': AUTH_SHA,
                'provenance': 'Owner-supplied Codex task; no fabricated GitHub owner comment'}

    def transport(self, repo, *args):
        transport_configuration(repo)
        env = P.custody.git_environment(); env['GIT_ALLOW_PROTOCOL'] = 'https'
        return self.command(['git', '--no-replace-objects', '-c', 'core.hooksPath=/dev/null',
            '-c', 'core.fsmonitor=false', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0',
            '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential',
            '-c', 'push.followTags=false', '-c', 'push.recurseSubmodules=no', '-C', str(repo), *args],
            env=env, timeout=300)

    def snapshot(self, row, repo):
        approved(row)
        # Reuse reviewed identity, default, Actions, hook and default-commit
        # automation visibility. The old baseline ref is not a mutation target.
        mapped = {**row, 'donor_default_preserved': {
            'name': row['default_to_preserve']['name'], 'sha': row['default_to_preserve']['commit']}}
        state = P.GitHub.snapshot(self, mapped, repo)
        refs = {}
        for line in self.transport(repo, 'ls-remote', '--refs', 'https://github.com/' + row['repository'] + '.git').splitlines():
            oid, ref = line.split('\t')
            require(re.fullmatch('[0-9a-f]{40}', oid) and ref.startswith('refs/') and ref not in refs,
                    'Malformed/duplicate remote ref')
            refs[ref] = oid
        state['refs'] = refs
        if any(refs.get(item['ref']) == row['proposed_commit'] for item in row['destinations']):
            endpoint = 'repos/' + row['repository']
            commit = self.api(endpoint + '/git/commits/' + row['proposed_commit'])
            require(commit['sha'] == row['proposed_commit'] and commit['tree']['sha'] == row['proposed_tree'],
                    'Remote successor commit/tree mismatch')
            expected_parents = ['aac73e9b89821331e77f67f1dd0921e541a78cfc'] if row['root_id'] == 'geotools' else []
            require([p['sha'] for p in commit['parents']] == expected_parents, 'Remote successor ancestry changed')
            for page in self.api(endpoint + '/commits/' + row['proposed_commit'] + '/check-runs?per_page=100', pages=True):
                require(isinstance(page.get('check_runs'), list), 'Successor checks inaccessible')
                state['checks'] += [{'status': c['status'], 'app': {'slug': (c.get('app') or {}).get('slug')}}
                                    for c in page['check_runs']]
            for page in self.api(endpoint + '/commits/' + row['proposed_commit'] + '/status?per_page=100', pages=True):
                require(isinstance(page.get('statuses'), list), 'Successor statuses inaccessible')
                state['statuses'] += [{'state': s['state'], 'creator': {'login': (s.get('creator') or {}).get('login')}}
                                      for s in page['statuses']]
        return state

    def create(self, row, repo, ref):
        approved(row)
        require(ref in {x['ref'] for x in row['destinations']}, 'Unapproved successor ref')
        if ref == row['destinations'][0]['ref']:
            return self.transport(repo, *creation_arguments(row['proposed_commit'], ref,
                                  'https://github.com/' + row['repository'] + '.git'))
        return self.api('repos/' + row['repository'] + '/git/refs', method='POST',
                        payload={'ref': ref, 'sha': row['proposed_commit']})


def clear(row, state):
    require(state['repository'] == row['repository'] and state['repository_id'] == row['repository_id'],
            'Source repository identity changed')
    default = row['default_to_preserve']
    require(state['default'] == {'name': default['name'], 'sha': default['commit']} and
            state['refs'].get('refs/heads/' + default['name']) == default['commit'], 'Default branch changed')
    require(state['actions']['enabled'] is False and all(state['actions'].get(k) == v
            for k, v in row['actions_to_preserve'].items()), 'Actions containment changed')
    for item in row['destinations']:
        require(state['refs'].get(item['ref']) in (None, row['proposed_commit']), 'Source destination collision')
    P.automation_clear(state)


def preserved(row, before, after):
    clear(row, after)
    require(before['actions'] == after['actions'], 'Actions settings drift')
    require(all(after['refs'].get(ref) == oid for ref, oid in before['refs'].items()), 'Existing ref changed/disappeared')
    allowed = {x['ref'] for x in row['destinations']}
    require(set(after['refs']) - set(before['refs']) <= allowed, 'Unexpected ref created')
    old_runs = {r['id'] for r in before['runs']}
    require(not [r for r in after['runs'] if r['id'] not in old_runs and
                 r['head_sha'] == row['proposed_commit'] and 'refs/heads/' + r['head_branch'] in allowed],
            'Unexpected successor workflow run')


def publish(selected, authorization, workspace, github, receipt, *, apply=False, local_check=local_check):
    writes = 0
    try:
        require(selected == rows(), 'Only exact two-source proposal is allowed')
        receipt.emit('authorization', verified=github.authorize(authorization))
        receipt.emit('public_companion', verified=github.companion())
        local, baseline = {}, {}
        # Preflight both roots before any remote mutation.
        for row in selected:
            key = row['root_id']; local[key] = local_check(row, workspace)
            baseline[key] = github.snapshot(row, Path(local[key]['path']))
            clear(row, baseline[key])
            receipt.emit('before', root_id=key, local=local[key], remote=baseline[key])
        for row in selected:
            key = row['root_id']; repo = Path(local[key]['path'])
            for item in row['destinations']:
                ref = item['ref']
                if apply:
                    receipt.emit('public_companion', root_id=key, verified=github.companion())
                receipt.emit('authorization', root_id=key, verified=github.authorize(authorization))
                state = github.snapshot(row, repo); preserved(row, baseline[key], state)
                status = 'already-exact' if ref in state['refs'] else 'ready'
                if apply and status == 'ready':
                    receipt.emit('attempt', root_id=key, ref=ref, commit=row['proposed_commit'],
                                 operation='create_only_review' if ref == row['destinations'][0]['ref'] else 'create_only_canonical')
                    writes += 1
                    try:
                        response = github.create(row, repo, ref)
                        receipt.emit('response', root_id=key, ref=ref, response=response)
                    except (ValueError, OSError) as error:
                        receipt.emit('uncertain', root_id=key, ref=ref, error=str(error))
                    # No automatic retry: reconcile even after an ambiguous response.
                    state = github.snapshot(row, repo); preserved(row, baseline[key], state)
                    require(state['refs'].get(ref) == row['proposed_commit'], 'Creation unverified; reconcile before retry')
                    status = 'created-or-reconciled'
                receipt.emit('result', root_id=key, ref=ref, status=status, remote=state)
                # Every observed/created ref becomes a preservation obligation for
                # the next operation; the first snapshot alone is insufficient.
                baseline[key] = state
        for row in selected:
            key = row['root_id']
            final = github.snapshot(row, Path(local[key]['path']))
            preserved(row, baseline[key], final)
            if apply:
                require(all(final['refs'].get(x['ref']) == row['proposed_commit'] for x in row['destinations']),
                        'Final complete successor delivery changed')
            receipt.emit('final', root_id=key, remote=final)
        receipt.emit('summary', status='passed', apply=apply, source_mutation_attempts=writes, settings_mutation_attempts=0)
        return True
    except (ValueError, OSError, KeyError, TypeError) as error:
        receipt.emit('summary', status='held', error=str(error), apply=apply,
                     source_mutation_attempts=writes, settings_mutation_attempts=0)
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-root', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    context = P.runtime_context()
    P.custody.git(PLATFORM, 'merge-base', '--is-ancestor', BASE, 'HEAD')
    require(not args.apply or not context['working_changes'], 'Commit/review helper before apply')
    journal = P.Receipt(args.receipt)
    try:
        journal.emit('start', context=context, implementation_sha256=P.custody.sha(Path(__file__)),
                     delegation_sha256=AUTH_SHA, proposal_sha256=PROPOSAL_SHA, apply=args.apply)
        return 0 if publish(rows(), args.authorization, args.workspace_root.resolve(), GitHub(), journal,
                            apply=args.apply) else 2
    finally:
        journal.close()


if __name__ == '__main__':
    raise SystemExit(main())
