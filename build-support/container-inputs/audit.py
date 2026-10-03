#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect retained signed RPMs without installing or executing their contents."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time

from custody import checked_path, verify_rpm
from selection import IDENTITY, sha

FINGERPRINT = 'AD485664E901B867051AB15F35A2F86E29B700A4'
SENSE = {'LT': 2, 'GT': 4, 'EQ': 8, 'LE': 10, 'GE': 12, None: 0}
DEPENDENCIES = ('requires', 'provides', 'conflicts', 'obsoletes', 'recommends', 'suggests')
SCRIPT_TAG = re.compile(r'^(?:PREIN|POSTIN|PREUN|POSTUN|PRETRANS|POSTTRANS|PREUNTRANS|POSTUNTRANS|VERIFYSCRIPT|TRIGGER|FILETRIGGER|TRANSFILETRIGGER)')


def run(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=90,
                            env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise ValueError('Inspection command failed: ' + repr(argv) + ': ' + result.stderr)
    return result.stdout


def metadata_dependency(row):
    version = row.get('ver', '')
    if row.get('rel'):
        version += '-' + row['rel']
    if row.get('epoch') not in (None, '', '0'):
        version = row['epoch'] + ':' + version
    return row['name'], SENSE[row.get('flags')], version


def normalized_evr(value):
    return value[2:] if value.startswith('0:') else value


def compare_dependencies(metadata, observed, allow_extra=False):
    expected = {metadata_dependency(row) for row in metadata}
    actual = {(row['name'], row['flags'] & 14, normalized_evr(row['evr']))
              for row in observed if not row['name'].startswith('rpmlib(')}
    if expected - actual or (actual - expected and not allow_extra):
        raise ValueError('Publisher/signed dependency mismatch: ' + repr({
            'only_metadata': sorted(expected - actual), 'only_header': sorted(actual - expected)}))
    return actual - expected


def safe_filename(name):
    path = PurePosixPath(name)
    # systemd unit names use literal backslash-xHH escapes on Linux. Do not
    # interpret/unescape them; other backslashes remain unsupported.
    if (not name.startswith('/') or name.startswith('//') or '\\' in re.sub(r'\\x[0-9a-fA-F]{2}', '', name)
            or '\x00' in name or '..' in path.parts or str(path) != name):
        raise ValueError('Unsafe signed package filename')
    return name


def package_inventory(entry, archive, providers):
    import rpm
    verified = verify_rpm(archive, entry)
    with archive.open('rb') as stream:
        header = rpm.TransactionSet().hdrFromFdno(stream.fileno())
    if str(header['license']) != entry['license']:
        raise ValueError('Publisher/signed license expression differs')
    dependencies = {}
    additional_requirements = []
    for kind in DEPENDENCIES:
        rows = [{'name': d.N(), 'flags': d.Flags(), 'evr': d.EVR(), 'text': d.DNEVR()}
                for d in rpm.ds(header, kind)]
        extras = compare_dependencies(entry[kind], rows, allow_extra=(kind == 'requires'))
        # Publisher primary metadata can prune redundant/self-provided requires.
        # Do not assume redundancy: every extra signed requirement needs an
        # exact, selected archive provider with native RPM comparison semantics.
        for name, flags, evr in sorted(extras):
            requirement = next(iter(rpm.ds((name, flags, evr), 'requires')))
            if requirement.IsRich():
                raise ValueError('Additional rich requirement needs explicit closure analysis')
            matches = sorted({identity for identity, capability in providers.get(name, [])
                              if capability.Compare(requirement)})
            if not matches:
                raise ValueError('Signed requirement absent from selected archives: ' + name)
            additional_requirements.append({'requirement': requirement.DNEVR(),
                                            'selected_provider_identities': matches})
        dependencies[kind] = rows
    rpmlib = []
    for requirement in rpm.ds(header, 'requires'):
        if requirement.N().startswith('rpmlib('):
            matches = [p.DNEVR() for p in rpm.ds.Rpmlib() if p.Compare(requirement)]
            if not matches:
                raise ValueError('Existing inspection librpm cannot satisfy package-format requirement')
            rpmlib.append({'requirement': requirement.DNEVR(), 'actual_librpm_providers': matches})
    names = list(header['filenames'])
    for name in names:
        safe_filename(name)
    if len(set(names)) != len(names) or not set(entry['files']).issubset(names):
        raise ValueError('Duplicate or publisher/signed filename mismatch')
    columns = ('filemodes', 'fileflags', 'filesizes', 'filedigests', 'filelinktos',
               'fileusername', 'filegroupname', 'filecaps', 'filedevices', 'fileinodes')
    values = {}
    for column in columns:
        items = list(header[column] or [])
        if not items and column == 'filecaps':
            items = [''] * len(names)
        if len(items) != len(names):
            raise ValueError('Signed file column has inconsistent length: ' + column)
        values[column] = items
    files = [{ 'path': name, **{column: values[column][index] for column in columns}}
             for index, name in enumerate(names)]
    scripts = {rpm.tagnames[tag]: header[tag] for tag in header.keys()
               if SCRIPT_TAG.match(rpm.tagnames.get(tag, ''))}
    return {'identity': {field: entry[field] for field in IDENTITY},
            'archive_sha256': sha(archive), 'signed_verification': verified,
            'license_expression': str(header['license']),
            'payload': {field: header[field] for field in
                        ('payloadformat', 'payloadcompressor', 'payloadflags', 'filedigestalgo')},
            'dependencies': dependencies, 'rpm_format_requirements': rpmlib,
            'additional_signed_requirements': additional_requirements,
            'scripts_and_triggers': scripts, 'files': files,
            'privileged_files': [row['path'] for row in files
                                 if row['filecaps'] or row['filemodes'] & (stat.S_ISUID | stat.S_ISGID)],
            'special_files': [row['path'] for row in files
                              if stat.S_IFMT(row['filemodes']) not in
                              (stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK)],
            'notice_candidates': [name for name in names if name.startswith('/usr/share/licenses/')],
            'scripts_executed': False, 'payload_extracted': False}


def keyring(key, output):
    # This is a job-owned verification database, never the host RPM database or
    # a login/signing credential store. Only the independently identified public
    # publisher key is admitted. Retain both the original key and exact outputs.
    home = output / 'gpg-home'
    home.mkdir(mode=0o700)
    listing = run(['gpg', '--homedir', str(home), '--batch', '--with-colons', '--show-keys', str(key)])
    rows = [line.split(':') for line in listing.splitlines()]
    pubs = [row for row in rows if row[0] == 'pub']
    fingerprints = [row[9] for row in rows if row[0] == 'fpr']
    if (len(pubs) != 1 or fingerprints != [FINGERPRINT] or pubs[0][1] in ('r', 'e', 'd')
            or (pubs[0][6] and int(pubs[0][6]) <= time.time())):
        raise ValueError('Publisher verification key differs, expired or revoked')
    (output / 'key-listing.txt').write_text(listing)
    db = output / 'rpm-keyring'
    db.mkdir(mode=0o700)
    run(['rpmkeys', '--dbpath', str(db), '--import', str(key)])
    installed = run(['rpmkeys', '--dbpath', str(db), '--list'])
    if len(installed.strip().splitlines()) != 1 or '29b700a4-' not in installed:
        raise ValueError('Isolated verification keyring membership differs')
    (output / 'rpm-key-listing.txt').write_text(installed)
    return db, {'path': str(key), 'sha256': sha(key), 'fingerprint': FINGERPRINT,
                'identity_url': 'https://build.opensuse.org/projects/openSUSE:Factory/signing_keys',
                'gpg_listing_sha256': sha(output / 'key-listing.txt'),
                'rpm_listing_sha256': sha(output / 'rpm-key-listing.txt')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--publisher-key', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    output = checked_path(args.output)
    output.mkdir()
    entries = json.loads(args.selection.read_text())
    if entries['unresolved']:
        raise ValueError('Incomplete selection')
    db, key = keyring(checked_path(args.publisher_key), output)
    import rpm
    providers = {}
    for entry in entries['packages']:
        archive = checked_path(args.retained / 'rpms' / Path(entry['location']).name)
        verify_rpm(archive, entry)
        with archive.open('rb') as stream:
            header = rpm.TransactionSet().hdrFromFdno(stream.fileno())
        identity = tuple(entry[field] for field in IDENTITY)
        for capability in rpm.ds(header, 'provides'):
            providers.setdefault(capability.N(), []).append((identity, capability))
        for name in header['filenames']:
            capability = next(iter(rpm.ds((name, 0, ''), 'provides')))
            providers.setdefault(name, []).append((identity, capability))
    results, failures = [], []
    for entry in entries['packages']:
        try:
            archive = checked_path(args.retained / 'rpms' / Path(entry['location']).name)
            signature = run(['rpmkeys', '--dbpath', str(db), '--checksig', '--verbose', str(archive)])
            signers = re.findall(r'Signature, key ID ([0-9a-f]+): OK', signature)
            if not signers or set(signers) != {'29b700a4'} or any(v in signature for v in ('NOTTRUSTED', 'NOKEY', 'BAD')):
                raise ValueError('Isolated publisher signature verification failed')
            result = package_inventory(entry, archive, providers)
            result['isolated_signature_verification'] = signature
            results.append(result)
        except Exception as error:
            failures.append({'name': entry['name'], 'error': str(error)})
    receipt = {'schema_version': 1, 'selection_sha256': sha(args.selection), 'inspection_source_sha256': sha(Path(__file__)),
               'publisher_key': key, 'packages': results, 'failures': failures,
               'host_database_changed': False, 'package_scripts_executed': False,
               'scope': 'Static signed-header, key and requirement audit; no execution, filesystem assembly or distribution acceptance'}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'packages': len(results), 'failures': len(failures), 'receipt_sha256': sha(output / 'receipt.json')}))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
