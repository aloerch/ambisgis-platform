#!/usr/bin/env python3
"""Compare installed RPM-managed files with the exact retained signed headers.

Raw observations stay private. This records all selected package files and
fails on changed observed executables/libraries or compiler/header/module inputs.
Other changed configuration, missing manuals or ghost files remain explicit;
they are not silently counted as reproduced build inputs.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

import retain


def inspect_file(path, mode, expected_digest, link, algorithm, ghost=False):
    row = {'path': str(path)}
    if not str(path).startswith(('/usr/', '/bin/', '/sbin/', '/lib/', '/lib64/')):
        return {**row, 'status': 'outside-build-file-scope'}
    if ghost:
        if path.is_symlink():
            return {**row, 'status': 'generated-link', 'link': os.readlink(path),
                    'resolved': str(path.resolve())}
        return {**row, 'status': 'ghost-not-shipped'}
    try:
        actual = path.lstat()
    except FileNotFoundError:
        return {**row, 'status': 'missing'}
    except PermissionError:
        return {**row, 'status': 'unreadable'}
    if stat.S_IFMT(actual.st_mode) != stat.S_IFMT(mode):
        return {**row, 'status': 'type-mismatch'}
    if stat.S_ISLNK(mode):
        target = os.readlink(path)
        return {**row, 'status': 'match' if target == link else 'link-mismatch',
                'link': target, 'expected_link': link}
    if stat.S_ISREG(mode):
        if not expected_digest or algorithm not in (8, 10):
            return {**row, 'status': 'missing-strong-payload-digest'}
        try:
            actual_digest = retain.digest(path, {8: 'sha256', 10: 'sha512'}[algorithm])
        except PermissionError:
            return {**row, 'status': 'unreadable', 'expected_digest': expected_digest}
        return {**row, 'status': 'match' if actual_digest == expected_digest else 'content-mismatch',
                'digest_algorithm': {8: 'sha256', 10: 'sha512'}[algorithm],
                'expected_digest': expected_digest, 'actual_digest': actual_digest,
                'sha256': retain.digest(path) if algorithm != 8 else actual_digest,
                'bytes': actual.st_size}
    return {**row, 'status': 'directory' if stat.S_ISDIR(mode) else 'special-file'}


def is_build_input(path, selected):
    if not str(path).startswith(('/usr/', '/bin/', '/sbin/', '/lib/', '/lib64/')):
        return False
    return (str(path) in selected or str(path.resolve()) in selected or
            str(path).startswith(('/usr/include/', '/usr/lib64/gcc/', '/usr/lib/gcc/',
                                 '/usr/lib64/python3.13/', '/usr/lib/python3.13/',
                                 '/usr/share/perl5/', '/usr/lib/perl5/', '/usr/lib64/perl5/',
                                 '/usr/share/cmake', '/usr/share/bison/', '/usr/share/aclocal/')))


def main():
    import rpm
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    manifest = json.loads(args.manifest.read_text())
    selected = set(manifest['selection_paths'])
    covered, observations, blocking, counts = set(), [], [], {}
    ts = rpm.TransactionSet()
    for entry in manifest['packages']:
        path = args.retained / 'rpms' / Path(entry['location']).name
        verification = retain.verify_rpm(path, entry)
        with path.open('rb') as stream:
            header = ts.hdrFromFdno(stream.fileno())
        package = {'name': entry['name'], 'rpm_sha256': retain.digest(path),
                   'verification': verification, 'files': []}
        algorithm = header['filedigestalgo']
        for name, mode, expected, link, flags in zip(header['filenames'], header['filemodes'],
                header['filedigests'], header['filelinktos'], header['fileflags'], strict=True):
            file_path = Path(name)
            row = inspect_file(file_path, mode, expected, link, algorithm, flags & rpm.RPMFILE_GHOST)
            row['build_input'] = is_build_input(file_path, selected)
            package['files'].append(row)
            counts[row['status']] = counts.get(row['status'], 0) + 1
            if row['build_input'] and row['status'] not in ('match', 'directory', 'generated-link'):
                blocking.append({'package': entry['name'], **row})
            if row['status'] == 'match':
                covered.add(name); covered.add(str(file_path.resolve()))
        observations.append(package)
    generated_links = []
    for package in observations:
        for row in package['files']:
            if row['status'] != 'generated-link':
                continue
            generated_links.append({'package': package['name'], **row})
            if row['build_input'] and row['resolved'] not in covered:
                blocking.append({'package': package['name'], **row,
                                 'error': 'Generated link target lacks signed retained payload correspondence'})
    missing = sorted(selected - covered)
    for observation in manifest['selected_file_observations']:
        if retain.digest(observation['path']) != observation['sha256']:
            blocking.append({'path': observation['path'], 'status': 'changed-since-selection'})
    result = {'manifest_sha256': retain.digest(args.manifest), 'started_at': started,
              'finished_at': datetime.now(timezone.utc).isoformat(), 'file_counts': counts,
              'selected_paths': len(selected), 'uncovered_selected_paths': missing,
              'generated_package_links': generated_links,
              'blocking_build_input_differences': blocking, 'packages': observations,
              'status': 'failed' if blocking or missing else 'selected-build-inputs-match',
              'scope': 'Current payload correspondence only; not backdated to prior build starts or an OS reinstall proof'}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('packages', 'blocking_build_input_differences')}))
    print('blocking differences', len(blocking))
    return 1 if blocking or missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
