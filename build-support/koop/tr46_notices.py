#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify and stage the exact tr46 notice supplement; never install or fetch."""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile

INPUT_MANIFEST_SHA256 = '760dba33ab7b05ecf622c5a5be93b20d7e31734e2ade76fb601530229fd82e1a'
BUNDLE = Path(__file__).resolve().parent / 'notices/tr46-0.0.3'
NOTICE_FILES = ('MIT-LICENSE.txt', 'UNICODE-LICENSE.txt', 'NOTICE.txt')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_hash(kind, data):
    return hashlib.sha1(kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def checked_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path or ancestor')
    return path


def new_output(path):
    path = checked_path(path)
    require(not path.exists(), 'output must be new; existing data is never overwritten')
    require(path.parent.is_dir(), 'output parent must already exist')
    return path


def regular(path):
    path = checked_path(path)
    require(path.exists() and stat.S_ISREG(path.stat().st_mode), 'input is not a regular file')
    return path


def inventory(root, expected):
    root = checked_path(root)
    require(root.is_dir(), 'missing input directory')
    files, directories = set(), set()
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):
            directories.add(relative)
        else:
            require(stat.S_ISREG(mode), 'symlink or special file in inventory')
            files.add(relative)
    expected_directories = {parent.as_posix() for name in expected
                            for parent in PurePosixPath(name).parents if str(parent) != '.'}
    require(files == set(expected) and directories == expected_directories, 'inventory membership differs')


def load_bundle(root):
    root = checked_path(root)
    manifest_path = regular(root / 'input-manifest.json')
    require(manifest_path.stat().st_size < 100000, 'input manifest size')
    raw = manifest_path.read_bytes()
    require(sha(raw) == INPUT_MANIFEST_SHA256, 'unreviewed input manifest')
    manifest = json.loads(raw)
    inventory(root, set(manifest['files']) | {'input-manifest.json'})
    files = {'input-manifest.json': raw}
    for relative, record in manifest['files'].items():
        path = regular(root / relative)
        require(path.stat().st_size == record['bytes'], 'input size differs: ' + relative)
        data = path.read_bytes()
        require(sha(data) == record['sha256'], 'input hash differs: ' + relative)
        files[relative] = data
    return manifest, files


def tree_entries(value, expected):
    require(not value.get('truncated'), 'incomplete source tree')
    entries, folders, identities = {}, {'': []}, {'': expected}
    for row in value['tree']:
        name = row['path']; path = PurePosixPath(name)
        require(name and not path.is_absolute() and '..' not in path.parts
                and '\\' not in name and name not in entries, 'invalid source tree path')
        require(row['type'] in ('blob', 'tree'), 'unsupported source tree entry')
        require(row['mode'] == ('040000' if row['type'] == 'tree' else '100644'), 'unexpected source mode')
        entries[name] = (row['mode'], row['type'], row['sha'])
        parent = '' if str(path.parent) == '.' else str(path.parent)
        folders.setdefault(parent, []).append(row)
        if row['type'] == 'tree':
            folders.setdefault(name, [])
            identities[name] = row['sha']
    for folder, rows in folders.items():
        body = b''
        for row in sorted(rows, key=lambda x: (PurePosixPath(x['path']).name +
                                               ('/' if x['type'] == 'tree' else '')).encode()):
            mode = '40000' if row['type'] == 'tree' else row['mode']
            body += (mode + ' ' + PurePosixPath(row['path']).name).encode() + b'\0' + bytes.fromhex(row['sha'])
        require(git_hash('tree', body) == identities.get(folder), 'source tree content differs')
    return entries


def read_archive(raw):
    """Parse bounded regular members in memory; no archive paths are extracted."""
    files = {}; size = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            require(member.isfile() and not path.is_absolute() and '..' not in path.parts
                    and '\\' not in member.name and member.name.startswith('package/'), 'unsafe archive member')
            require(member.name not in files, 'duplicate archive member')
            size += member.size
            require(0 <= member.size <= 300000 and size <= 300000 and len(files) < 5, 'archive member limits')
            files[member.name] = archive.extractfile(member).read()
    return files


def unicode_notice(raw):
    class Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
    html = raw.decode('utf8')
    marker = '<h3>1. Unicode Data Files and Software</h3>'
    require(html.count(marker) == 1, 'missing complete Unicode notice section')
    section = html.split(marker, 1)[1].split('<h3>2.', 1)[0]
    require(section.count('<pre>') == 1 and section.count('</pre>') == 1, 'incomplete Unicode notice')
    parser = Text(); parser.feed(section)
    return ('1. Unicode Data Files and Software\n\n' + ''.join(parser.parts).strip() + '\n').encode('utf8')


def reconstruct_mapping(raw):
    """Independent local conversion; never invoke the floating upstream fetch."""
    rows = []
    for line in raw.decode('utf8').split('\n'):
        cells = [cell.strip() for cell in line.split('#')[0].split(';')]
        if len(cells) == 1:
            continue
        require(2 <= len(cells) <= 4, 'invalid Unicode row')
        bounds = cells[0].split('..')
        require(1 <= len(bounds) <= 2, 'invalid code-point range')
        cells[0] = [int(bounds[0], 16), int(bounds[-1], 16)]
        require(0 <= cells[0][0] <= cells[0][1] <= 0x10ffff, 'invalid code-point bounds')
        if len(cells) >= 3:
            cells[2] = [int(value, 16) for value in cells[2].split(' ')] if cells[2] else []
        rows.append(cells)
    return json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode(), len(rows)


def verify(archive_path, bundle=BUNDLE):
    manifest, files = load_bundle(bundle)
    archive_path = regular(archive_path)
    require(archive_path.stat().st_size == manifest['archive']['bytes'], 'wrong archive size')
    raw = archive_path.read_bytes()
    require(sha(raw) == manifest['archive']['sha256'], 'wrong archive hash')
    archive = read_archive(raw)
    require(set(archive) == set(manifest['archive']['members']), 'archive membership differs')
    old_commit = json.loads(files['provenance/selected-commit.json'])
    new_commit = json.loads(files['provenance/license-commit.json'])
    require(old_commit['sha'] == manifest['selected_source']['commit'] and
            new_commit['sha'] == manifest['notice_source']['commit'], 'source commit differs')
    for commit, selected in ((old_commit, 'selected_source'), (new_commit, 'notice_source')):
        require(commit['commit']['tree']['sha'] == manifest[selected]['tree'], 'source root tree differs')
    require([p['sha'] for p in new_commit['parents']] == [old_commit['sha']], 'not a direct successor')
    require([(f['filename'], f['status']) for f in new_commit['files']] == [('LICENSE.md', 'added')], 'non-notice source change')
    old = tree_entries(json.loads(files['provenance/selected-tree.json']), manifest['selected_source']['tree'])
    new = tree_entries(json.loads(files['provenance/license-tree.json']), manifest['notice_source']['tree'])
    require(set(new) - set(old) == {'LICENSE.md'} and all(new.get(name) == row for name, row in old.items()), 'historical source not equivalent')
    require(git_hash('blob', files['MIT-LICENSE.txt']) == manifest['notice_source']['license_blob'] == new['LICENSE.md'][2], 'MIT notice differs')
    require(git_hash('blob', files['sources/index.js']) == old['index.js'][2], 'source implementation differs')
    require(git_hash('blob', files['sources/generateMappingTable.js']) == old['scripts/generateMappingTable.js'][2], 'historical generator differs')
    unicode_blob = json.loads(files['provenance/icu56-license-blob.json'])
    require(base64.b64decode(unicode_blob['content'], validate=False) == files['provenance/icu56-license.html'], 'Unicode notice blob content differs')
    require(git_hash('blob', files['provenance/icu56-license.html']) == unicode_blob['sha'] == manifest['unicode_notice_source']['blob'], 'Unicode notice source differs')
    require(unicode_notice(files['provenance/icu56-license.html']) == files['UNICODE-LICENSE.txt'], 'Unicode notice section differs')
    members = {}
    for name, data in archive.items():
        expected = manifest['archive']['members'][name]
        require(len(data) == expected['bytes'] and sha(data) == expected['sha256'], 'archive member content differs')
        blob = git_hash('blob', data)
        require(blob == expected['git_blob'], 'archive member Git hash differs')
        if expected['equal_to_both_historical_source_trees']:
            require(old[name.removeprefix('package/')][2] == blob, 'archive member/source differs')
        members[name] = {'bytes': len(data), 'sha256': sha(data),
                         'source_tree_match': expected['equal_to_both_historical_source_trees']}
    generated, rows = reconstruct_mapping(files['sources/IdnaMappingTable-8.0.0.txt'])
    require(rows == manifest['unicode_source']['rows'] and generated == archive['package/lib/mappingTable.json'], 'generated table differs')
    # Recheck live inputs after inspection, including the original archive.
    require(archive_path.read_bytes() == raw, 'archive changed during verification')
    require(load_bundle(bundle)[1] == files, 'bundle changed during verification')
    result = {'status': 'verified', 'archive_sha256': sha(raw),
              'input_manifest_sha256': INPUT_MANIFEST_SHA256, 'helper_sha256': sha(Path(__file__).read_bytes()),
              'members': members, 'unchanged_source_entries': len(old),
              'mapping_rows': rows, 'mapping_sha256': sha(generated), 'mapping_byte_equal': True,
              'complete_notices_verified': list(NOTICE_FILES), 'inputs_unchanged': True,
              'scope': 'Exact notice/source supplement only; no product adoption or distribution approval.'}
    return result, files, generated, raw


def output_files(files, generated, archive):
    output = {}
    for destination in ('software', 'documentation'):
        for name in NOTICE_FILES:
            output[f'{destination}/notices/tr46-0.0.3/{name}'] = files[name]
    for name, data in files.items():
        output['source/tr46-0.0.3/supplement/' + name] = data
    output['source/tr46-0.0.3/generated/mappingTable.json'] = generated
    output['source/tr46-0.0.3/original-npm-archive.tgz'] = archive
    output['source/tr46-0.0.3/tr46_notices.py'] = Path(__file__).read_bytes()
    return output


def verify_stage(output, archive_path, bundle=BUNDLE):
    result, files, generated, raw = verify(archive_path, bundle)
    expected = output_files(files, generated, raw)
    inventory(output, set(expected) | {'stage-manifest.json'})
    for name, data in expected.items():
        require(regular(Path(output) / name).read_bytes() == data, 'staged content differs: ' + name)
    actual_manifest = json.loads(regular(Path(output) / 'stage-manifest.json').read_bytes())
    expected_manifest = {'verification': result,
                         'files': {name: {'bytes': len(data), 'sha256': sha(data)}
                                   for name, data in sorted(expected.items())}}
    require(actual_manifest == expected_manifest, 'stage manifest differs')
    return expected_manifest


def stage(archive_path, output, bundle=BUNDLE):
    output = new_output(output)
    result, files, generated, raw = verify(archive_path, bundle)
    selected = output_files(files, generated, raw)
    output.mkdir()  # Fails on a concurrently created destination; no overwrite.
    for name, data in selected.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    manifest = {'verification': result,
                'files': {name: {'bytes': len(data), 'sha256': sha(data)}
                          for name, data in sorted(selected.items())}}
    with (output / 'stage-manifest.json').open('x') as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    verify_stage(output, archive_path, bundle)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'stage', 'verify-stage'))
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, default=BUNDLE)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action != 'verify' and args.output is None:
        parser.error('--output is required for staging or staged verification')
    try:
        if args.action == 'verify':
            result = verify(args.archive, args.bundle)[0]
        elif args.action == 'stage':
            result = stage(args.archive, args.output, args.bundle)
        else:
            result = verify_stage(args.output, args.archive, args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, OSError, tarfile.TarError) as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
