#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unpack audited RPM payloads as inert files; links and scripts remain data.

This is an inspection store, not a runnable filesystem or installed package set.
Each package has its own directory. Never run scriptlets, create device nodes,
set capabilities, preserve privileged modes, or materialize package symlinks.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess

from custody import checked_path
from selection import IDENTITY, sha

_helper_path = Path(__file__).resolve().parents[1] / 'qgis/acquisition.py'
_spec = importlib.util.spec_from_file_location('reviewed_cpio_parser', _helper_path)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)


def materialize(data, package, destination):
    """Require exact signed membership, file types, byte sizes and digests."""
    if package['payload']['filedigestalgo'] != 8:
        raise ValueError('Unsupported signed file digest algorithm')
    headers = {row['path'].lstrip('/'): row for row in package['files']}
    entries = list(_helper.cpio_entries(data))
    names = [str(row[0]) for row in entries]
    expected = {name for name, row in headers.items() if not row['fileflags'] & 64}
    if len(set(names)) != len(names) or set(names) != expected:
        raise ValueError('Payload/signed membership differs: ' + repr({
            'missing': sorted(expected - set(names)), 'unexpected': sorted(set(names) - expected)}))
    hard_data = {}
    for rel, mode, content, inode, nlink in entries:
        if stat.S_ISREG(mode) and nlink > 1 and content:
            if inode in hard_data and content != hard_data[inode]:
                raise ValueError('Ambiguous payload hardlink group')
            hard_data[inode] = content
    records = []
    for rel, mode, content, inode, nlink in entries:
        signed = headers[str(rel)]
        if mode != signed['filemodes']:
            raise ValueError('Payload/signed file mode differs: ' + str(rel))
        if stat.S_ISDIR(mode):
            records.append({'path': str(rel), 'kind': 'directory', 'materialized': False})
            continue
        if stat.S_ISLNK(mode):
            target = content.decode('utf-8')
            if target != signed['filelinktos'] or len(content) != signed['filesizes']:
                raise ValueError('Payload/signed symlink differs: ' + str(rel))
            records.append({'path': str(rel), 'kind': 'symlink', 'target': target, 'materialized': False})
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Special payload file unsupported')
        if nlink > 1 and not content:
            content = hard_data.get(inode, b'')
        digest = hashlib.sha256(content).hexdigest()
        if len(content) != signed['filesizes'] or digest != signed['filedigests']:
            raise ValueError('Payload/signed file size or digest differs: ' + str(rel))
        path = checked_path(destination / rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as output:
            output.write(content)
        # Inert inspection store. Assembly must explicitly opt into each final
        # runtime executable mode from the separately recorded signed header.
        path.chmod(0o600)
        records.append({'path': str(rel), 'kind': 'file', 'sha256': digest,
                        'bytes': len(content), 'signed_mode': oct(mode), 'materialized_mode': '0600'})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--audit-sha256', required=True)
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if sha(args.audit) != args.audit_sha256:
        raise ValueError('Static audit receipt differs')
    audit = json.loads(args.audit.read_text())
    if audit['failures'] or not audit['packages']:
        raise ValueError('Static audit incomplete')
    destination = checked_path(args.output)
    destination.mkdir()
    results, failures = [], []
    for package in audit['packages']:
        identity = package['identity']
        name = identity['name'] + '-' + identity['version'] + '-' + identity['release'] + '.' + identity['arch']
        try:
            archive = checked_path(args.retained / 'rpms' / (name + '.rpm'))
            if sha(archive) != package['archive_sha256']:
                raise ValueError('Retained archive changed since signature/header audit')
            package_dir = checked_path(destination / name)
            package_dir.mkdir()
            process = subprocess.run(['rpm2cpio', str(archive)], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, timeout=120)
            if process.returncode:
                raise ValueError('Existing host rpm2cpio failed')
            records = materialize(process.stdout, package, package_dir)
            row = {'identity': identity, 'directory': str(package_dir),
                   'archive_sha256': package['archive_sha256'], 'files': records}
            results.append(row)
        except Exception as error:
            failures.append({'identity': identity, 'error': str(error)})
    receipt = {'schema_version': 1, 'static_audit_sha256': sha(args.audit),
               'tool_sha256': sha(Path(__file__)), 'cpio_parser_sha256': sha(_helper_path),
               'packages': results, 'failures': failures,
               'package_code_executed': False, 'symlinks_materialized': False,
               'host_modified': False, 'scope': 'Inert payload inspection; not runtime assembly'}
    (destination / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'packages': len(results), 'failures': len(failures), 'receipt_sha256': sha(destination / 'receipt.json')}))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
