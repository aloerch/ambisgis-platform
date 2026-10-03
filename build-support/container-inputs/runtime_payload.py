#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Select an inert runtime filesystem from already audited signed RPM payloads.

This performs no package/script/runtime execution, host installation or chmod
to executable. Patched Podman/rootlessport and owned configuration are separate
reviewed assembly inputs. The affected original Podman binary is never selected.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import stat

BASE_PAYLOAD_SHA = '6d685c53f28d75e66923f4e3c1c652398f76c41a48863caa10d3dbcf87591650'
PROGRAMS = {
    'usr/bin/conmon': 'conmon', 'usr/bin/runc': 'runc',
    'usr/bin/fuse-overlayfs': 'fuse-overlayfs', 'usr/bin/catatonit': 'catatonit',
    'usr/bin/pasta': 'pasta', 'usr/bin/passt': 'passt',
    'usr/libexec/podman/netavark': 'netavark',
    'usr/libexec/podman/aardvark-dns': 'aardvark-dns',
    'usr/bin/python3.13': 'python3.13',
}
PYTHON_PACKAGES = {'python313-base', 'python313-PyYAML', 'python313-click',
                   'python313-podman-compose', 'python313-python-dotenv'}
HOST_PATH_HOOK = 'usr/lib64/python3.13/site-packages/zzzz-import-failed-hooks.pth'
HOST_PATH_HOOK_SHA = '12fa5a475447ba4a6b5c78efbfaee7188b622c57e0947d7da17896ddb11a1b98'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(path, *, fresh=False):
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('Parent traversal is unsupported')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('Source/output ancestor cannot be a symlink')
    if fresh and path.exists():
        raise ValueError('Creation-only output already exists')
    return path


def relative(value):
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or '..' in path.parts or str(path) != value:
        raise ValueError('Noncanonical package member')
    return value


def read_receipt(path, expected):
    path = checked(path)
    if sha(path) != expected:
        raise ValueError('Payload receipt digest mismatch')
    value = json.loads(path.read_text())
    if value['failures'] or value['package_code_executed'] or value['symlinks_materialized'] or value['host_modified']:
        raise ValueError('Requires successfully audited inert payloads')
    return value


def catalog(receipts):
    result = {}
    for receipt in receipts:
        for package in receipt['packages']:
            for row in package['files']:
                name = relative(row['path'])
                identity = {k: row[k] for k in ('kind', 'sha256', 'target', 'signed_mode') if k in row}
                if name in result:
                    if result[name]['identity'] != identity:
                        raise ValueError('Conflicting signed member: ' + name)
                    continue
                result[name] = {'identity': identity, 'row': row,
                                'source': str(checked(Path(package['directory']) / name)),
                                'package': package['identity'], 'archive_sha256': package['archive_sha256']}
    return result


def resolve(entries, name):
    """Resolve signed links lexically without trusting host filesystem links."""
    seen, chain = set(), []
    while True:
        relative(name)
        if name in seen:
            raise ValueError('Signed link cycle')
        seen.add(name)
        if name not in entries:
            raise ValueError('Signed link target is absent: ' + name)
        item = entries[name]
        if item['row']['kind'] == 'file':
            return item, chain
        if item['row']['kind'] != 'symlink':
            raise ValueError('Selected runtime path is not a regular file')
        target = item['row']['target']
        if not isinstance(target, str) or not target or '\x00' in target:
            raise ValueError('Invalid signed link target')
        chain.append({'path': name, 'target': target, 'package': item['package'],
                      'archive_sha256': item['archive_sha256']})
        name = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(name), target))
        # usrmerge aliases are signed entries, not an implicit host translation.
        first, _, tail = name.partition('/')
        if first in ('lib', 'lib64', 'bin', 'sbin') and first in entries:
            alias = entries[first]
            if alias['row']['kind'] != 'symlink' or alias['row']['target'] != 'usr/' + first:
                raise ValueError('Unsupported usrmerge alias')
            chain.append({'path': first, 'target': alias['row']['target'], 'package': alias['package'],
                          'archive_sha256': alias['archive_sha256']})
            name = posixpath.join(alias['row']['target'], tail)


def selection(entries):
    plan = {name: 'runtime/bin/' + destination for name, destination in PROGRAMS.items()}
    for name, item in entries.items():
        path = PurePosixPath(name)
        if item['row']['kind'] not in ('file', 'symlink'):
            continue
        # Retain the conservative complete top-level shared-library set. Every
        # runtime ELF's actual needed/rpath closure is checked before execution.
        if path.parent == PurePosixPath('usr/lib64') and ('.so' in path.name or path.name.startswith('ld-')):
            plan[name] = 'runtime/lib64/' + path.name
        if item['package']['name'] in PYTHON_PACKAGES:
            if name.startswith(('usr/lib64/python3.13/', 'usr/lib/python3.13/')):
                if '__pycache__' in path.parts or path.suffix == '.pyc':
                    continue
                if path.suffix == '.pth':
                    if name == HOST_PATH_HOOK and item['row'].get('sha256') == HOST_PATH_HOOK_SHA:
                        # openSUSE's optional missing-module hint points at the
                        # host /usr prefix. Retain its bytes outside import roots.
                        plan[name] = 'runtime/notices/disabled-host-startup/' + path.name
                        continue
                    raise ValueError('Python startup hook requires explicit review')
                plan[name] = 'runtime/' + name.removeprefix('usr/')
    plan['usr/share/containers/seccomp.json'] = 'runtime/configuration/seccomp.json'
    owners = set()
    for name in plan:
        item, chain = resolve(entries, name)
        owners.add(item['package']['name'])
        owners.update(link['package']['name'] for link in chain)
    for name, item in entries.items():
        if item['package']['name'] in owners and item['row']['kind'] in ('file', 'symlink'):
            if name.startswith(('usr/share/licenses/', 'usr/share/doc/packages/')):
                plan[name] = 'runtime/notices/' + name.removeprefix('usr/share/')
    if len(set(plan.values())) != len(plan):
        raise ValueError('Selected output collision')
    return plan


def materialize(receipts, output):
    output = checked(output, fresh=True)
    entries = catalog(receipts)
    plan = selection(entries)
    # Resolve and validate all selected source bytes before creating any output.
    sources = {}
    for name in sorted(plan):
        item, chain = resolve(entries, name)
        source = checked(item['source'])
        metadata = source.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o777 != 0o600:
            raise ValueError('Selected input is not the inert regular payload')
        if sha(source) != item['row']['sha256']:
            raise ValueError('Selected inert payload changed: ' + name)
        sources[name] = (item, chain)
    output.mkdir(parents=True, mode=0o700)
    records = []
    for name, destination in sorted(plan.items()):
        item, chain = sources[name]
        target = checked(output / relative(destination), fresh=True)
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        data = checked(item['source']).read_bytes()
        if hashlib.sha256(data).hexdigest() != item['row']['sha256']:
            raise ValueError('Payload changed during assembly')
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        records.append({'path': destination, 'sha256': sha(target), 'bytes': len(data),
                        'mode': '0600', 'package_member': name, 'resolved_source': item['source'],
                        'package': item['package'], 'archive_sha256': item['archive_sha256'],
                        'signed_link_chain': chain})
    for directory in sorted((x for x in output.rglob('*') if x.is_dir()), reverse=True):
        directory.chmod(0o700)
    result = {'schema_version': 1, 'files': records, 'regular_files': len(records),
              'bytes': sum(x['bytes'] for x in records), 'original_podman_selected': False,
              'runtime_executed': False, 'executable_modes_applied': False,
              'startup_adjustment': {'member': HOST_PATH_HOOK, 'sha256': HOST_PATH_HOOK_SHA,
                                     'action': 'Retain outside import roots; absolute host missing-module-hint directory is not activated'},
              'scope': 'Inert static payload only; patched engine, wrappers, host prerequisites, ELF closure and actual sandbox acceptance remain required.'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--additional-payload', type=Path)
    parser.add_argument('--additional-sha256')
    parser.add_argument('--additional-package', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if bool(args.additional_payload) != bool(args.additional_sha256):
        raise ValueError('Additional retained payload requires its reviewed exact hash')
    if bool(args.additional_payload) != bool(args.additional_package):
        raise ValueError('Additional payload requires an explicit package selection')
    receipts = [read_receipt(args.payload, BASE_PAYLOAD_SHA)]
    inputs = [{'path': str(checked(args.payload)), 'sha256': BASE_PAYLOAD_SHA, 'packages': 'all original runtime inputs'}]
    if args.additional_payload:
        extra = read_receipt(args.additional_payload, args.additional_sha256)
        selected = [p for p in extra['packages'] if p['identity']['name'] in args.additional_package]
        if {p['identity']['name'] for p in selected} != set(args.additional_package) or len(selected) != len(set(args.additional_package)):
            raise ValueError('Additional package selection is missing or ambiguous')
        receipts.append({'packages': selected})
        inputs.append({'path': str(checked(args.additional_payload)), 'sha256': args.additional_sha256,
                       'packages': args.additional_package})
    result = materialize(receipts, args.output)
    result['inputs'] = inputs
    result['recipe_sha256'] = sha(Path(__file__))
    (args.output / 'runtime-payload.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))


if __name__ == '__main__':
    main()
