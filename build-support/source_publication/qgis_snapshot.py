#!/usr/bin/env python3
"""Prepare/verify the exact LOCAL FND-07 QGIS source-publication snapshot.

No remote mutation, source fetching, old-history rewriting or distribution occurs.
The original accepted manifest and custody records remain authoritative.
"""
import argparse
import bz2
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1]
BASE = '1a4cda5f2620e7374e5926fc955a7d2d06493e15'
BASE_TREE = 'c8542e82e3c3810950f32ce8d58a16bfed12e6c8'
SELECTION_SHA = 'a1b259c8e422d52f63aba093d49af915301c6b4b7c11bb134d0a600d31f6e43c'
STAGE_SHA = 'a2152edc50a7fdb34401e148c1eec238dfdf5dad6600faf73e92a063a4c47baa'
AUTH_SHA = '87d79df2d4458d9570c269ff9d20310c4117f7d82c2dc23d4588ca505900da1f'
REF = 'refs/heads/ambisgis/review/fnd-07-publication-snapshot-v1'
RESOURCE = 'resources/cpt-city-qgis-min/'
PROVENANCE = 'AMBISGIS-SOURCE-PROVENANCE.json'
NOTICE = 'AMBISGIS-PUBLICATION.md'
GIT_ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_TERMINAL_PROMPT': '0',
           'GIT_ATTR_NOSYSTEM': '1', 'GIT_CONFIG_COUNT': '0'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def blob_id(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value))


def file_ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def safe_path(value):
    path = PurePosixPath(value)
    require(value and not path.is_absolute() and '..' not in path.parts and str(path) == value,
            'unsafe source path')
    require('.git' not in (p.lower() for p in path.parts) and '\x00' not in value,
            'Git administrative source path')
    return path


def quoted_git_path(path):
    raw = path.encode('utf-8')
    return b'"' + b''.join(bytes([c]) if 32 <= c < 127 and c not in (34, 92)
                            else ('\\%03o' % c).encode() for c in raw) + b'"'


def git(repo, *args, data=None):
    return subprocess.run(['git', '--no-optional-locks', '-c', 'protocol.allow=never',
                           '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args],
                          input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=GIT_ENV, check=True).stdout


def init_repo(path):
    require(not path.exists(), 'fresh isolated repository required')
    subprocess.run(['git', 'init', '--bare', '--template=', '--initial-branch=unused', str(path)],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=GIT_ENV)


def tree_entries(repo, commit):
    rows = {}
    for line in git(repo, 'ls-tree', '-rz', commit).split(b'\0'):
        if not line:
            continue
        meta, raw_path = line.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        path = raw_path.decode('utf-8')
        safe_path(path)
        require(path not in rows and kind == 'blob' and mode in ('100644', '100755', '120000'),
                'unexpected duplicate, gitlink or source mode')
        rows[path] = {'mode': mode, 'oid': oid}
    return rows


class Blobs:
    def __init__(self, repo):
        self.proc = subprocess.Popen(['git', '--no-optional-locks', '-C', str(repo),
                                      'cat-file', '--batch'], env=GIT_ENV,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

    def read(self, oid):
        self.proc.stdin.write((oid + '\n').encode())
        self.proc.stdin.flush()
        fields = self.proc.stdout.readline().split()
        require(len(fields) == 3 and fields[0].decode() == oid and fields[1] == b'blob',
                'missing or incorrect source blob')
        data = self.proc.stdout.read(int(fields[2]))
        require(len(data) == int(fields[2]) and self.proc.stdout.read(1) == b'\n'
                and blob_id(data) == oid, 'source blob integrity failure')
        return data

    def close(self):
        self.proc.stdin.close()
        result = self.proc.wait()
        self.proc.stdout.close()
        self.proc.stderr.close()
        require(result == 0, 'source object reader failed')


def authorization(path):
    record = json.loads(Path(path).read_text())
    comment = record['comment']
    require(comment['id'] == 5863464446 and comment['user']['login'] == 'aloerch'
            and comment['user']['id'] == 15285626
            and comment['created_at'] == '2026-09-28T04:35:51Z'
            and digest(comment['body'].encode()) == record['body_sha256'] == AUTH_SHA,
            'wrong owner decision identity/body')
    return {'url': comment['html_url'], 'author': 'aloerch', 'author_id': 15285626,
            'created_at': comment['created_at'], 'body_sha256': AUTH_SHA}


def load_selection(path):
    require(sha(path) == SELECTION_SHA, 'wrong exact palette selection identity')
    selection = json.loads(Path(path).read_text())
    excluded = {r['path'].removeprefix('share/qgis/'): r
                for group in selection['groups'].values() for r in group['files']}
    require(len(excluded) == len(selection['exclusions']) == 1130,
            'wrong palette exclusion membership')
    require(set(excluded) == {p.removeprefix('share/qgis/') for p in selection['exclusions']},
            'selection maps disagree')
    require({k: v['count'] for k, v in selection['groups'].items()}
            == {'SRC-01': 256, 'SRC-02': 139, 'SRC-03': 690, 'SRC-04': 45},
            'wrong exclusion group counts')
    require(RESOURCE + 'gmt/GMT_dem1.svg' in excluded and len(selection['colorbrewer']) == 265,
            'missing alias or ColorBrewer members')
    for path in excluded:
        safe_path(path)
        require(path.startswith(RESOURCE) and path.endswith('.svg'), 'invalid omission scope')
    return selection, excluded


def catalogue_change(data, roots, date):
    # Import the existing deterministic selection semantics, not a new selector.
    sys.path.insert(0, str(PLATFORM / 'build-support/qgis'))
    from resource_selection import trim_catalogue
    trimmed, refs = trim_catalogue(data, roots, {'gmt/GMT_dem1'})
    if not refs:
        return data, [], b''
    comment = ('<!-- AmbisGIS modification ' + date + ': removed references to the exact '
               '1130 optional palettes excluded from this source-publication snapshot; '
               'see /AMBISGIS-SOURCE-PROVENANCE.json. Original attribution is retained. -->\n').encode()
    pos = trimmed.index(b'\n') + 1
    return trimmed[:pos] + comment + trimmed[pos:], refs, comment


def embedded_audit(data, label, forbidden_sha, record, depth=0):
    """Check exact omitted payload aliases in retained blobs and archive members.

    This is a bounded payload check, not blanket licensing clearance. Oversize or
    unknown compressed archives fail rather than being silently skipped.
    """
    require(digest(data) not in forbidden_sha, 'forbidden palette payload: ' + label)
    require(depth <= 8, 'nested archive depth exceeded: ' + label)
    def check(member, payload):
        record['archive_members'] += 1
        record['expanded_bytes'] += len(payload)
        require(record['archive_members'] < 100000 and record['expanded_bytes'] < 4 * 1024**3,
                'archive expansion requires explicit review')
        embedded_audit(payload, label + '!' + member, forbidden_sha, record, depth + 1)
    if data.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')):
        record['containers'].append(label)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if not member.is_dir():
                    require(member.file_size < 256 * 1024**2, 'oversize zip member')
                    check(member.filename, archive.read(member))
    elif len(data) > 262 and data[257:262] == b'ustar':
        record['containers'].append(label)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
            for member in archive:
                if member.isfile():
                    require(member.size < 256 * 1024**2, 'oversize tar member')
                    check(member.name, archive.extractfile(member).read())
    else:
        opener = (gzip.GzipFile if data.startswith(b'\x1f\x8b') else
                  lzma.LZMAFile if data.startswith(b'\xfd7zXZ') else
                  bz2.BZ2File if data.startswith(b'BZh') else None)
        if opener:
            record['containers'].append(label)
            compressed = opener(fileobj=io.BytesIO(data)) if opener is gzip.GzipFile else opener(io.BytesIO(data))
            with compressed as stream:
                payload = stream.read(256 * 1024**2 + 1)
            require(len(payload) <= 256 * 1024**2, 'oversize compressed member')
            check('decompressed', payload)
        require(not data.startswith((b'RCC', b'qres')), 'compiled Qt resource needs explicit member audit')


def isolation(repo):
    require(not repo.is_symlink(), 'symlinked repository')
    for path in [repo, *repo.rglob('*')]:
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), 'symlinked repository/object file')
        if stat.S_ISREG(mode):
            require(path.stat().st_nlink == 1, 'hardlinked repository/object file')
    require(not (repo / 'objects/info/alternates').exists()
            and not (repo / 'objects/info/http-alternates').exists()
            and not (repo / 'shallow').exists() and not (repo / 'info/grafts').exists(),
            'shared, shallow or replaced object store')
    require(not list((repo / 'objects/pack').glob('*.promisor')), 'promisor object store')
    require(not (repo / 'hooks').exists() or not any((repo / 'hooks').iterdir()), 'unexpected hooks')
    config = git(repo, 'config', '--local', '--list').decode().splitlines()
    require(all(line in ('core.repositoryformatversion=0', 'core.filemode=true', 'core.bare=true')
                for line in config), 'unexpected repository config/filter/remote')


def verify_repository(repo, commit, tree, expected, forbidden):
    isolation(repo)
    require(git(repo, 'rev-parse', commit + '^{tree}').decode().strip() == tree,
            'wrong snapshot tree')
    require(git(repo, 'rev-list', '--parents', '--all').decode().splitlines() == [commit],
            'unexpected commit ancestry or extra commits')
    refs = git(repo, 'for-each-ref', '--format=%(refname) %(objectname)').decode().splitlines()
    require(refs == [REF + ' ' + commit], 'unexpected source refs')
    require(tree_entries(repo, commit) == expected, 'complete source inventory mismatch')
    reachable = {line.split()[0] for line in git(repo, 'rev-list', '--objects', '--all').decode().splitlines()}
    stored_rows = [line.split() for line in git(repo, 'cat-file', '--batch-all-objects',
                                            '--batch-check=%(objectname) %(objecttype)').decode().splitlines()]
    stored = {row[0] for row in stored_rows}
    require(stored == reachable and not (stored & set(forbidden)),
            'forbidden or unreachable stored object')
    git(repo, 'fsck', '--full', '--strict', '--no-reflogs')
    return {'commit': commit, 'tree': tree, 'refs': refs, 'source_entries': len(expected),
            'objects': len(stored), 'object_types': dict(Counter(row[1] for row in stored_rows)),
            'parent_count': 0, 'stored_equals_reachable': True, 'forbidden_objects': [],
            'fsck': 'passed', 'alternates_replacements_promisors_hooks_filters': 'absent'}


def import_snapshot(repo, source, original, omitted, selection, decision, timestamp, identity):
    roots = [p.removeprefix('share/qgis/' + RESOURCE) for p in selection['omitted_collection_roots']]
    expected = {}; mapping = []; changes = []; omitted_rows = []
    forbidden = {original[p]['oid'] for p in omitted}
    require(not any(v['oid'] in forbidden for p, v in original.items() if p not in omitted),
            'excluded alias outside exact omission map')
    forbidden_sha = {row['sha256'] for row in omitted.values()}
    audit = {'containers': [], 'archive_members': 0, 'expanded_bytes': 0, 'qrc_files': [],
             'retained_blobs_checked': 0, 'forbidden_payload_aliases': []}
    log = (repo.parent / 'fast-import.log').open('xb')
    importer = subprocess.Popen(['git', '-C', str(repo), 'fast-import', '--quiet', '--date-format=raw'],
                                env=GIT_ENV, stdin=subprocess.PIPE, stdout=log, stderr=log)
    stream = importer.stdin
    epoch = int(datetime.fromisoformat(timestamp).timestamp())
    message = ('Prepare parentless QGIS source publication snapshot\n\n'
               'Derived from ' + BASE + '; 1130 disputed optional palettes omitted.\n'
               'Original histories remain in controlled custody; no rights waiver.\n').encode()
    stream.write(('commit ' + REF + '\nauthor ' + identity + ' ' + str(epoch) + ' +0000\n'
                  'committer ' + identity + ' ' + str(epoch) + ' +0000\n').encode())
    stream.write(b'data ' + str(len(message)).encode() + b'\n' + message + b'\n')
    def emit(path, mode, data):
        safe_path(path)
        stream.write(('M ' + mode + ' inline ').encode() + quoted_git_path(path) + b'\n')
        stream.write(b'data ' + str(len(data)).encode() + b'\n' + data + b'\n')
        expected[path] = {'mode': mode, 'oid': blob_id(data)}
    reader = Blobs(source)
    try:
        for path, row in sorted(original.items()):
            data = reader.read(row['oid'])
            source_sha = digest(data)
            if path in omitted:
                require(source_sha == omitted[path]['sha256'] and len(data) == omitted[path]['bytes'],
                        'omitted source differs from accepted selection')
                omitted_rows.append({'path': path, **row, 'sha256': source_sha, 'bytes': len(data)})
                continue
            new = data
            if path.startswith(RESOURCE + 'selections/') and path.endswith('.xml'):
                new, removed, comment = catalogue_change(data, roots, timestamp[:10])
                if removed:
                    changes.append({'path': path, 'before_oid': row['oid'], 'after_oid': blob_id(new),
                                    'before_sha256': source_sha, 'after_sha256': digest(new),
                                    'removed_references': removed, 'notice': comment.decode()})
            embedded_audit(new, path, forbidden_sha, audit)
            audit['retained_blobs_checked'] += 1
            if path.endswith('.qrc'):
                qrc = ET.fromstring(new)
                require(not any('cpt-city' in (el.text or '') for el in qrc.iter('file')),
                        'cpt-city embedded in Qt resource')
                audit['qrc_files'].append({'path': path, 'sha256': digest(new)})
            emit(path, row['mode'], new)
            mapping.append({'path': path, 'original_oid': row['oid'], 'snapshot_oid': blob_id(new),
                            'mode': row['mode'], 'original_sha256': source_sha,
                            'snapshot_sha256': digest(new)})
        require(len(changes) == 19 and sum(len(r['removed_references']) for r in changes) == 107,
                'wrong catalogue delta')
        require(sum(p.startswith(RESOURCE + 'cb/') and p.endswith('.svg') for p in expected) == 265,
                'ColorBrewer source changed')
        provenance = {'schema_version': 1, 'variant': 'fnd-07-qgis-publication-snapshot-v1',
                      'original_commit': BASE, 'original_tree': BASE_TREE,
                      'accepted_candidate_manifest_sha256': '0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99',
                      'selection_sha256': SELECTION_SHA, 'owner_decision': decision,
                      'created_utc': timestamp, 'retained_file_mapping': mapping,
                      'omitted_files': omitted_rows, 'catalogue_changes': changes,
                      'new_files': [PROVENANCE, NOTICE],
                      'history': 'No original parent. Original complete history retained separately in controlled custody; not a distributable predecessor.',
                      'hosting_limitation': 'Existing fork branches/tags and GitHub fork-network reachability are not purged or certified clean.',
                      'source_changes': 'Exact optional-palette omissions, catalogue references and modification notices only. Executable code and compiler inputs unchanged.'}
        notice = ('# QGIS-derived AmbisGIS source-publication snapshot\n\n'
                  'Prepared ' + timestamp + '. This is a local source variant awaiting owner review; '
                  'it is not a release or a blanket licensing clearance.\n\n'
                  'Original source: ' + BASE + ', tree ' + BASE_TREE + '. '
                  'The per-file original/new object mapping and 1130 exact omissions are in '
                  + PROVENANCE + '. The 19 modified catalogue files carry dated notices. '
                  'All other retained source files, copyright and license texts are unchanged. '
                  'Original author attribution remains in the source headers, doc/AUTHORS and notices. '
                  'The new root metadata identifies preparation of this snapshot, not authorship of inherited QGIS.\n\n'
                  'Original complete history and omitted source remain in established controlled custody '
                  'under their actual rights constraints. They are not ancestors of this root or contents '
                  'of its local publication bundle. This boundary does not purge or certify existing public '
                  'fork branches, tags or the GitHub fork network. No visibility or existing history changes '
                  'are authorized.\n\n'
                  'This product includes color specifications and designs developed by Cynthia Brewer '
                  '(http://colorbrewer.org/). All 265 ColorBrewer palettes and their original '
                  'resources/cpt-city-qgis-min/cb/COPYING.xml remain; acknowledgment and naming conditions apply. '
                  'The remaining GMT collection and its original COPYING.xml remain. '
                  'Original icon, font, embedded dependency and other source obligations remain.\n\n'
                  'Packaging uses the explicit variant adapter in the accompanying AmbisGIS platform source. '
                  'It keeps original metadata/notices outside the active palette chooser and never restores '
                  'the omitted payloads. FND-02 remains accepted; this does not claim a new binary build, '
                  'FND-07 final acceptance or FND-08 completion.\n').encode()
        emit(PROVENANCE, '100644', encoded(provenance))
        emit(NOTICE, '100644', notice)
        stream.write(b'\ndone\n'); stream.close()
        require(importer.wait() == 0, 'snapshot import failed')
    except BaseException:
        if importer.poll() is None:
            importer.kill(); importer.wait()
        raise
    finally:
        reader.close(); log.close()
    return expected, provenance, audit, forbidden


def restore_bundle(bundle, output, commit, tree, expected, forbidden):
    init_repo(output)
    header = Path(bundle).open('rb')
    try:
        require(header.readline() == b'# v2 git bundle\n', 'unexpected bundle version')
        refs = []
        while True:
            line = header.readline()
            require(line, 'truncated bundle header')
            if line == b'\n':
                break
            require(not line.startswith(b'-'), 'bundle has predecessor prerequisite')
            refs.append(line.decode().strip())
        require(refs == [commit + ' ' + REF], 'unexpected bundle refs')
    finally:
        header.close()
    git(output, 'bundle', 'verify', str(bundle))
    git(output, '-c', 'protocol.file.allow=always', 'fetch', '--no-tags', '--no-write-fetch-head',
        str(bundle), REF + ':' + REF)
    return verify_repository(output, commit, tree, expected, forbidden)


def prepare(args):
    output = args.output.resolve()
    require(not output.exists(), 'fresh output required; failures are preserved')
    decision = authorization(args.authorization)
    workspace = args.workspace_root.resolve()
    source = workspace / 'build-worktrees/source-baseline-restore/run-001/repos/qgis'
    selection_path = workspace / 'build-worktrees/java-gmt-remediation/qgis/selection-01/selection.json'
    stage_manifest = selection_path.parent / 'after-manifest.json'
    selection, omitted = load_selection(selection_path)
    require(sha(stage_manifest) == STAGE_SHA, 'wrong accepted selected-stage identity')
    require(git(source, 'rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE,
            'accepted source identity mismatch')
    original = tree_entries(source, BASE)
    require(len(original) == 33579 and set(omitted) <= set(original), 'incomplete accepted source')
    require('\n' not in args.author_name + args.author_email and '<' not in args.author_name
            and '>' not in args.author_email and '@' in args.author_email, 'invalid honest author metadata')
    output.mkdir(parents=True, mode=0o700)
    before = {str(p): sha(p) for p in (Path(__file__), PLATFORM / 'build-support/qgis/resource_selection.py',
                                               PLATFORM / 'build-support/qgis/publication_selection.py')}
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    report = {'status': 'failed', 'started_utc': timestamp, 'authorization': decision,
              'old_source': {'commit': BASE, 'tree': BASE_TREE}, 'remote_writes': 0,
              'original_histories_unchanged': True, 'tooling_before': before}
    try:
        repo = output / 'source.git'; init_repo(repo)
        expected, provenance, audit, forbidden = import_snapshot(
            repo, source, original, omitted, selection, decision, timestamp,
            args.author_name + ' <' + args.author_email + '>')
        commit = git(repo, 'rev-parse', REF).decode().strip()
        tree = git(repo, 'rev-parse', commit + '^{tree}').decode().strip()
        report['source'] = verify_repository(repo, commit, tree, expected, forbidden)
        report['source']['path'] = str(repo)
        save(output / 'expected-tree.json', expected)
        save(output / 'source-provenance.json', provenance)
        save(output / 'embedded-audit.json', audit)
        save(output / 'forbidden-object-ids.json', sorted(forbidden))
        bundle = output / 'qgis-publication-snapshot.bundle'
        git(repo, 'bundle', 'create', str(bundle), REF)
        report['bundle'] = file_ref(bundle)
        restored = output / 'restored.git'
        report['restore'] = restore_bundle(bundle, restored, commit, tree, expected, forbidden)
        report['restore']['path'] = str(restored)
        sys.path.insert(0, str(PLATFORM / 'build-support/qgis'))
        from publication_selection import publication_variant_stage
        report['resources'] = publication_variant_stage(
            restored, commit, tree, expected, provenance, selection_path, stage_manifest,
            output / 'resources', output / 'resources-replay')
        changed = {r['path'] for r in provenance['catalogue_changes']}
        require({p for p in set(original) & set(expected) if original[p] != expected[p]} == changed,
                'unrelated retained source changed')
        require(set(original) - set(expected) == set(omitted)
                and set(expected) - set(original) == {PROVENANCE, NOTICE}, 'unexpected complete-source delta')
        report['comparison'] = {'original_files': len(original), 'retained_files': len(provenance['retained_file_mapping']),
                                'omissions': 1130, 'catalogues_changed': 19, 'catalogue_references_removed': 107,
                                'new_provenance_notice_files': [PROVENANCE, NOTICE],
                                'all_other_source_paths_modes_blobs_identical': True,
                                'compiler_executable_provider_python_cmake_inputs_unchanged': True,
                                'source_recompiled': False, 'native_runtime_reexecuted': False,
                                'embedded_audit': file_ref(output / 'embedded-audit.json')}
        report['provenance'] = file_ref(output / 'source-provenance.json')
        report['expected_tree'] = file_ref(output / 'expected-tree.json')
        report['forbidden_objects'] = file_ref(output / 'forbidden-object-ids.json')
        require(before == {p: sha(p) for p in before}, 'executed tooling changed')
        require(sha(selection_path) == SELECTION_SHA and sha(stage_manifest) == STAGE_SHA,
                'accepted inputs changed during execution')
        report['status'] = 'passed'
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    report['finished_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    save(output / 'result.json', report)
    print(json.dumps({'status': report['status'], 'result': str(output / 'result.json'),
                      'source': report.get('source'), 'error': report.get('error')}))
    return 0 if report['status'] == 'passed' else 1



def trusted_receipt(path, expected_sha):
    require(len(expected_sha) == 64 and sha(path) == expected_sha, 'receipt identity mismatch')
    report = json.loads(Path(path).read_text())
    require(report.get('status') == 'passed', 'failed receipt cannot authorize verification')
    require(report['old_source'] == {'commit': BASE, 'tree': BASE_TREE}
            and report['authorization']['body_sha256'] == AUTH_SHA, 'receipt source/authority mismatch')
    for key in ('bundle', 'provenance', 'expected_tree', 'forbidden_objects'):
        ref = report[key]
        require(Path(ref['path']).is_relative_to(Path(path).resolve().parent), 'receipt path escapes run')
        require(file_ref(ref['path']) == ref, 'receipt payload identity mismatch: ' + key)
    return report


def verify_complete_delta(original, expected, provenance, omitted, source):
    require(set(original) - set(expected) == set(omitted)
            and set(expected) - set(original) == {PROVENANCE, NOTICE}, 'incorrect complete-source omissions/additions')
    mapping = provenance['retained_file_mapping']
    require(len(mapping) == len(original) - len(omitted)
            and len({r['path'] for r in mapping}) == len(mapping), 'incomplete/duplicate provenance mapping')
    require({r['path'] for r in provenance['omitted_files']} == set(omitted), 'omission provenance mismatch')
    for row in mapping:
        path = row['path']
        require(original[path] == {'mode': row['mode'], 'oid': row['original_oid']}
                and expected[path] == {'mode': row['mode'], 'oid': row['snapshot_oid']}, 'file provenance mismatch')
    changes = provenance['catalogue_changes']
    require(len(changes) == 19 and len({r['path'] for r in changes}) == 19,
            'incorrect catalogue delta count')
    changed = {p for p in set(original) & set(expected) if original[p] != expected[p]}
    require(changed == {r['path'] for r in changes}, 'unrelated source/compiler input changed')
    roots = ['es', 'jjg/ccolo', 'jjg/neo10', 'jm', 'td']
    reader = Blobs(source)
    try:
        for change in changes:
            path = change['path']
            require(path.startswith(RESOURCE + 'selections/') and path.endswith('.xml'), 'catalogue scope escape')
            data = reader.read(original[path]['oid'])
            transformed, removed, notice = catalogue_change(data, roots, provenance['created_utc'][:10])
            require(blob_id(transformed) == expected[path]['oid']
                    and removed == change['removed_references'] and notice.decode() == change['notice']
                    and digest(data) == change['before_sha256']
                    and digest(transformed) == change['after_sha256'], 'recomputed catalogue delta mismatch')
    finally:
        reader.close()
    return {'complete_source_comparison': 'passed', 'omissions': len(omitted),
            'unchanged_retained_files': len(mapping) - len(changes), 'changed_catalogues': len(changes),
            'all_executable_compiler_provider_build_inputs_unchanged': True}


def verify_existing(args):
    require(not args.output.exists(), 'fresh verification receipt required')
    producer = {str(p): sha(p) for p in (Path(__file__), PLATFORM / 'build-support/qgis/resource_selection.py',
                                               PLATFORM / 'build-support/qgis/publication_selection.py')}
    result = {'status': 'failed', 'tooling_before': producer, 'receipt': str(args.receipt), 'receipt_sha256': args.receipt_sha256,
              'started_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    try:
        report = trusted_receipt(args.receipt.resolve(), args.receipt_sha256)
        provenance = json.loads(Path(report['provenance']['path']).read_text())
        expected = json.loads(Path(report['expected_tree']['path']).read_text())
        forbidden = set(json.loads(Path(report['forbidden_objects']['path']).read_text()))
        workspace = args.workspace_root.resolve()
        source = workspace / 'build-worktrees/source-baseline-restore/run-001/repos/qgis'
        selection_path = workspace / 'build-worktrees/java-gmt-remediation/qgis/selection-01/selection.json'
        selection, omitted = load_selection(selection_path)
        require(git(source, 'rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE,
                'original accepted source mismatch')
        original = tree_entries(source, BASE)
        require(forbidden == {original[p]['oid'] for p in omitted}, 'forbidden object receipt mismatch')
        require(expected[PROVENANCE]['oid'] == blob_id(encoded(provenance)), 'source provenance bytes mismatch')
        result['source_comparison'] = verify_complete_delta(original, expected, provenance, omitted, source)
        for key in ('source', 'restore'):
            row = report[key]
            result[key] = verify_repository(Path(row['path']), row['commit'], row['tree'], expected, forbidden)
        require(report['source']['commit'] == report['restore']['commit']
                and report['source']['tree'] == report['restore']['tree'], 'restored identity mismatch')
        sys.path.insert(0, str(PLATFORM / 'build-support/qgis'))
        from publication_selection import publication_variant_stage
        row = report['restore']; resources = report['resources']
        result['resources'] = publication_variant_stage(
            Path(row['path']), row['commit'], row['tree'], expected, provenance,
            selection_path, selection_path.parent / 'after-manifest.json',
            Path(resources['output']), Path(resources['replay_output']), verify_only=True)
        for key in ('inventory_sha256', 'catalogue_notice_only_changes', 'relocated_original_metadata',
                    'selected_entries', 'unchanged_entries', 'catalogue_effective_xml_equal'):
            require(result['resources'][key] == resources[key], 'resource receipt content mismatch: ' + key)
        # A process exit alone is not acceptance; every final identity/publication check above must pass.
        result['tooling_after'] = {p: sha(p) for p in producer}
        require(result['tooling_after'] == producer, 'verification tooling changed')
        result['status'] = 'passed'
    except BaseException as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    result['finished_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    save(args.output, result)
    print(json.dumps({'status': result['status'], 'output': str(args.output), 'error': result.get('error')}))
    return 0 if result['status'] == 'passed' else 1

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('prepare', help='Prepare local exact snapshot and independent bundle restoration')
    create.add_argument('--workspace-root', type=Path, required=True)
    create.add_argument('--authorization', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    create.add_argument('--author-name', required=True)
    create.add_argument('--author-email', required=True)
    verify = sub.add_parser('verify', help='Read-only verify a trusted receipt against immutable inputs and actual stores/resources')
    verify.add_argument('--workspace-root', type=Path, required=True)
    verify.add_argument('--receipt', type=Path, required=True)
    verify.add_argument('--receipt-sha256', required=True)
    verify.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    return prepare(args) if args.command == 'prepare' else verify_existing(args)


if __name__ == '__main__':
    raise SystemExit(main())
