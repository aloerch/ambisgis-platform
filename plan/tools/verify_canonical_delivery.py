#!/usr/bin/env python3
"""Verify nine canonical source trees in fresh independent depth-one stores.

Full ancestry/diff evidence is reused, explicitly, from the hash-bound PR70 receipt
for the identical commits. Depth-one fetches prove current complete source trees;
they are not a new full-history recovery. Never writes to a remote.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path

PLATFORM = Path(__file__).resolve().parents[2]
PROPOSAL_SHA256 = '519dd189533c6d077648f0b9bbf1f98e052e28d4d614414b6c04f141deb0d28d'
HISTORY_SHA256 = 'ea237c635a6990d739ffe1cb9fe191e2f506c947f33400f286b3586822389e90'
REF = 'refs/heads/ambisgis/main'
_spec = importlib.util.spec_from_file_location('canonical_delivery_git', Path(__file__).with_name('verify_source_delivery.py'))
previous = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(previous)
git, text, require = previous.git, previous.text, previous.require


def bound_json(path, expected):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, 'Receipt/proposal hash mismatch')
    return json.loads(raw)


def verify_tip(repo, row, history):
    require(not repo.is_symlink(), 'Symlink repository')
    require(not (repo / 'objects').is_symlink(), 'Symlink object store')
    require(not (repo / 'objects/info/alternates').exists() and
            not (repo / 'objects/info/http-alternates').exists(), 'Shared object store')
    require(not (repo / 'info/grafts').exists(), 'Grafted history')
    require(not list((repo / 'objects').rglob('*.promisor')), 'Promisor object store')
    for path in (repo / 'objects').rglob('*'):
        require(not path.is_symlink(), 'Symlink object')
        if path.is_file():
            require(path.stat().st_nlink == 1, 'Hardlinked object')
    require(text(repo, 'for-each-ref', '--format=%(refname)') == REF, 'Unexpected refs')
    require((repo / 'shallow').read_text().strip() == row['proposed_commit'], 'Unexpected shallow boundary')
    require(text(repo, 'rev-parse', REF + '^{commit}') == row['proposed_commit'], 'Canonical commit mismatch')
    require(text(repo, 'rev-parse', REF + '^{tree}') == row['proposed_tree'], 'Canonical tree mismatch')
    require(history['status'] == 'verified' and history['commit'] == row['proposed_commit'] and
            history['tree'] == row['proposed_tree'] and history['repository_id'] == row['repository_id'] and
            history['repository'] == row['repository'] and history['root_id'] == row['root_id'] and
            history['fsck_exit_code'] == 0, 'Historical recovery identity mismatch')
    entries = git(repo, 'ls-tree', '-rz', REF).stdout
    links = []
    for line in entries.split(b'\0'):
        if line.startswith(b'160000 '):
            header, path = line.split(b'\t', 1)
            links.append({'path': path.decode(), 'commit': header.decode().split()[2]})
    require(links == history['gitlinks'], 'Gitlink mismatch')
    for notice in history['notices']:
        require(previous.tree_entry(repo, REF, notice['path']) == notice['entry'], 'Original notice changed')
    check = git(repo, 'fsck', '--full', '--no-reflogs')
    return {'commit': row['proposed_commit'], 'tree': row['proposed_tree'],
            'source_entries': len(entries.split(b'\0')) - 1,
            'tree_inventory_sha256': hashlib.sha256(entries).hexdigest(),
            'notice_paths_verified': len(history['notices']), 'gitlinks': links,
            'fsck_exit_code': check.returncode, 'fsck_stdout': check.stdout.decode(),
            'fsck_stderr': check.stderr.decode(),
            'history_evidence_reused': {'receipt_sha256': HISTORY_SHA256,
                                      'history_commits': history['history_commits'],
                                      'changed_paths': history['changed_paths']}}


def verify_mapping(repo, row, child):
    require(child['status'] == 'verified', 'MapStore child not verified')
    key_lines = text(repo, 'config', '--blob', REF + ':.gitmodules', '--get-regexp', r'^submodule\..*\.url$').splitlines()
    require(len(key_lines) == 1, 'Unexpected submodule declarations')
    key, donor = key_lines[0].split(' ', 1)
    require(donor == 'https://github.com/geosolutions-it/MapStore2.git', 'Unexpected donor declaration')
    path = text(repo, 'config', '--blob', REF + ':.gitmodules', '--get', key[:-3] + 'path')
    require(path == 'geonode_mapstore_client/client/MapStore2', 'Unexpected submodule path')
    require(row['gitlinks'] == [{'path': path, 'commit': child['commit']}], 'Wrong child gitlink')
    owned = 'https://github.com/aloerch/ambisgis-mapstore.git'
    argv = ['-c', 'url.' + owned + '.insteadOf=' + donor, 'ls-remote', '--exit-code', '--refs', donor, REF]
    observed = text(repo, *argv)
    require(observed == child['commit'] + '\t' + REF, 'Owned URL mapping did not resolve canonical child')
    return {'from': donor, 'to': owned, 'scope': 'process-only; .gitmodules unchanged',
            'path': path, 'argv': ['git', *argv], 'readback': observed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    proposal = bound_json(PLATFORM / 'plan/verification/source-ref-promotion/canonical-proposal.json', PROPOSAL_SHA256)
    history = bound_json(PLATFORM / 'plan/verification/source-ref-promotion/remote-delivery.json', HISTORY_SHA256)
    histories = {r['root_id']: r for r in history['repositories']}
    rows = [r for r in proposal['repositories'] if r['eligible_for_requested_separate_authorization']]
    require(len(rows) == 9 and not {'qgis', 'geotools'} & {r['root_id'] for r in rows}, 'Wrong eligible membership')
    root = args.workspace_root.resolve() / 'build-worktrees/canonical-and-publication-repairs'
    output = args.output.absolute()
    require(output.resolve().is_relative_to(root) and output != root and
            output.parent.resolve() == output.parent and not output.exists(), 'Fresh task-local output required')
    output.mkdir(parents=True, exist_ok=False)
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    result = {'schema_version': 1, 'started_at': datetime.now(timezone.utc).isoformat(),
              'canonical_proposal_sha256': PROPOSAL_SHA256, 'prior_full_history_receipt_sha256': HISTORY_SHA256,
              'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'mode': 'independent-complete-tip-trees-depth-one; prior-full-history-evidence-reused', 'repositories': []}
    for row in sorted(rows, key=lambda r: r['root_id'] == 'mapstore-client'):
        entry = {k: row[k] for k in ('root_id', 'repository', 'repository_id')}
        result['repositories'].append(entry)
        try:
            repo = output / row['root_id']; repo.mkdir()
            git(repo, 'init', '--bare', '--template=')
            url = 'https://github.com/' + row['repository'] + '.git'
            require(text(repo, 'ls-remote', '--exit-code', '--refs', url, REF) ==
                    row['proposed_commit'] + '\t' + REF, 'Canonical ref absent/different')
            argv = ['fetch', '--depth=1', '--no-tags', '--no-recurse-submodules', url, REF + ':' + REF]
            fetch = git(repo, *argv)
            (output / (row['root_id'] + '-fetch.txt')).write_bytes(fetch.stdout + fetch.stderr)
            entry['fetch_argv'] = ['git', *argv]
            entry.update(verify_tip(repo, row, histories[row['root_id']]))
            if row['root_id'] == 'mapstore-client':
                child = next(r for r in result['repositories'] if r['root_id'] == 'mapstore')
                entry['required_owned_url_mapping'] = verify_mapping(repo, entry, child)
            entry['status'] = 'verified'
        except Exception as exc:
            entry.update(status='failed', error=str(exc))
        finally:
            entry['observed_at'] = datetime.now(timezone.utc).isoformat()
            temp = output / 'delivery.json.tmp'
            temp.write_text(json.dumps(result, indent=2) + '\n'); os.replace(temp, output / 'delivery.json')
            print(entry['root_id'], entry['status'], flush=True)
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    result['passed'] = len(result['repositories']) == 9 and all(r['status'] == 'verified' for r in result['repositories'])
    (output / 'delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
