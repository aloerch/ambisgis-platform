#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Retain selected RPM/source bytes; never install RPMs or execute their code."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from selection import IDENTITY, sha

# Reuse only the reviewed source-address and source-listing validators. No
# package import, setup script, RPM installation or RPM scriptlet is involved.
_helper_path = Path(__file__).resolve().parents[1] / 'host-inputs/retain.py'
_spec = importlib.util.spec_from_file_location('retained_host_source', _helper_path)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)


def source_listing(data, revision):
    """Reviewed validator successor: permit literal @ in Linux unit patches.

    Retains all original signed OBS revision/membership checks. A source entry
    is a single literal filename, never a path or an unresolved OBS link.
    """
    root = ET.fromstring(data)
    if root.tag != 'directory' or root.attrib.get('srcmd5') != revision:
        raise ValueError('OBS source directory differs from signed build identity')
    result = []
    for node in root:
        if node.tag != 'entry':
            raise ValueError('Unexpanded OBS source/link entry')
        row = dict(node.attrib)
        if not re.fullmatch(r'[A-Za-z0-9+_.@-]+', row['name']) or row['name'] in ('.', '..', '_link'):
            raise ValueError('Unsafe or unresolved OBS source entry')
        if not re.fullmatch(r'[0-9a-f]{32}', row['md5']) or not 0 <= int(row['size']) <= 1024**3:
            raise ValueError('Invalid OBS source metadata')
        result.append(row)
    if not result or len({row['name'] for row in result}) != len(result):
        raise ValueError('Empty or duplicate OBS source entries')
    listing = ''.join(row['md5'] + '  ' + row['name'] + '\n'
                      for row in sorted(result, key=lambda row: row['name'])).encode()
    if hashlib.md5(listing).hexdigest() != revision:
        raise ValueError('OBS source entry set does not match signed source digest')
    return result


def checked_path(path):
    path = Path(path).absolute()
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Symlink at custody destination or source')
    return path


def checked_rpm_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'download.opensuse.org'
            or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment
            or not re.fullmatch(r'/history/[0-9]{8}/tumbleweed/repo/oss/(x86_64|noarch)/[A-Za-z0-9+_.~-]+\.rpm', parsed.path)):
        raise ValueError('Unapproved exact snapshot RPM URL')


def content_digest(path, algorithm):
    if algorithm not in ('sha256', 'sha512', 'md5'):
        raise ValueError('Unsupported recorded digest')
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def copy_exact(source, destination, size, algorithm, expected):
    source, destination = checked_path(source), checked_path(destination)
    if not source.is_file() or source.stat().st_size != size or content_digest(source, algorithm) != expected:
        raise ValueError('Existing retained candidate bytes differ')
    with source.open('rb') as reader, destination.open('xb') as writer:
        shutil.copyfileobj(reader, writer)
        writer.flush()
        os.fsync(writer.fileno())
    if content_digest(destination, algorithm) != expected:
        raise ValueError('Custody copy changed')


def fetch_exact(url, destination, size, algorithm, expected):
    destination = checked_path(destination)
    if destination.exists():
        if not destination.is_file() or destination.stat().st_size != size or content_digest(destination, algorithm) != expected:
            raise ValueError('Retained bytes changed')
        return {'network': False, 'url': url, 'sha256': sha(destination), 'bytes': size}
    partial = destination.with_name(destination.name + '.partial-' + str(time.time_ns()))
    with urllib.request.urlopen(url, timeout=45) as response, partial.open('xb') as output:
        length = 0
        while block := response.read(1024 * 1024):
            length += len(block)
            if length > size:
                raise ValueError('Download exceeds exact size')
            output.write(block)
        output.flush()
        os.fsync(output.fileno())
        final_url = response.url
    if length != size or content_digest(partial, algorithm) != expected:
        raise ValueError('Downloaded bytes differ from recorded size/digest')
    os.link(partial, destination)
    partial.unlink()
    return {'network': True, 'url': url, 'final_url': final_url, 'sha256': sha(destination), 'bytes': length}


def verify_rpm(path, entry):
    path = checked_path(path)
    if path.stat().st_size != entry['bytes'] or content_digest(path, entry['publisher_digest_algorithm']) != entry['publisher_digest']:
        raise ValueError('RPM publisher size/digest mismatch')
    environment = {**os.environ, 'LC_ALL': 'C'}
    signature = subprocess.run(['rpmkeys', '--checksig', str(path)], env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=45)
    if signature.returncode or 'digests signatures OK' not in signature.stdout:
        raise ValueError('RPM signature verification failed')
    fields = ['NAME', 'EPOCHNUM', 'VERSION', 'RELEASE', 'ARCH', 'SOURCEPACKAGE', 'SHA256HEADER', 'DISTURL', 'SOURCERPM']
    query = subprocess.run(['rpm', '-qp', '--qf', '\t'.join('%{' + field + '}' for field in fields), str(path)],
                           env=environment, capture_output=True, text=True, timeout=45)
    if query.returncode:
        raise ValueError('RPM header query failed')
    values = query.stdout.split('\t')
    if len(values) != len(fields) or values[:5] != [entry[field] for field in IDENTITY] or values[5] not in ('0', '(none)'):
        raise ValueError('Signed RPM identity differs from selection')
    if values[8] != entry['source_rpm'] or not re.fullmatch('[0-9a-f]{64}', values[6]):
        raise ValueError('Signed source association/header hash invalid')
    _helper.obs_identity(values[7])
    return {'signature': signature.stdout.strip(), 'signed_header_sha256': values[6],
            'source_build_disturl': values[7], 'source_rpm': values[8],
            'installed': False, 'scope': 'Signed archive header, not an observed installed package'}


def retain_binary(entry, retained, reuse):
    filename = Path(entry['location']).name
    if entry['location'] != entry['arch'] + '/' + filename or not filename.endswith('.rpm'):
        raise ValueError('Unsafe RPM location')
    destination = checked_path(retained / 'rpms' / filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copied_from = None
    if not destination.exists():
        for root in reuse:
            candidate = checked_path(root / 'rpms' / filename)
            if candidate.exists():
                copy_exact(candidate, destination, entry['bytes'], entry['publisher_digest_algorithm'], entry['publisher_digest'])
                copied_from = str(candidate)
                break
    urls = entry['retrieval_urls']
    if len(urls) != 1:
        raise ValueError('Exactly one reviewed snapshot origin required')
    checked_rpm_url(urls[0])
    receipt = fetch_exact(urls[0], destination, entry['bytes'], entry['publisher_digest_algorithm'], entry['publisher_digest'])
    verification = verify_rpm(destination, entry)
    return {'identity': {field: entry[field] for field in IDENTITY}, 'file': str(destination),
            'copied_from': copied_from, **receipt, 'verification': verification}


def retain_source(entry, retained, reuse):
    binary = retained / 'rpms' / Path(entry['location']).name
    verified = verify_rpm(binary, entry)
    project, revision, package = _helper.obs_identity(verified['source_build_disturl'])
    source_package, _, flavor = package.partition(':')
    url = ('https://api.opensuse.org/public/source/' + urllib.parse.quote(project, safe='')
           + '/' + urllib.parse.quote(source_package, safe=''))
    name = package.replace(':', '_') + '-' + revision
    destination = checked_path(retained / 'obs-source' / name)
    destination.mkdir(parents=True, exist_ok=True)
    listing = checked_path(destination / 'directory.xml')
    if not listing.exists():
        cached = next((root / 'obs-source' / name / 'directory.xml' for root in reuse
                       if (root / 'obs-source' / name / 'directory.xml').exists()), None)
        if cached:
            data = checked_path(cached).read_bytes()
        else:
            with urllib.request.urlopen(url + '?rev=' + revision, timeout=45) as response:
                data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError('Source listing too large')
        source_listing(data, revision)
        with listing.open('xb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    rows = source_listing(listing.read_bytes(), revision)
    files = []
    for row in rows:
        target = checked_path(destination / row['name'])
        copied_from = None
        if not target.exists():
            cached = next((root / 'obs-source' / name / row['name'] for root in reuse
                           if (root / 'obs-source' / name / row['name']).exists()), None)
            if cached:
                copy_exact(cached, target, int(row['size']), 'md5', row['md5'])
                copied_from = str(cached)
        receipt = fetch_exact(url + '/' + urllib.parse.quote(row['name'], safe='') + '?rev=' + revision,
                              target, int(row['size']), 'md5', row['md5'])
        files.append({'name': row['name'], 'publisher_md5': row['md5'], 'copied_from': copied_from, **receipt})
    expected_names = {'directory.xml'} | {row['name'] for row in rows}
    if {path.name for path in destination.iterdir()} != expected_names:
        raise ValueError('Unexpected retained source membership')
    return {'source_rpm': entry['source_rpm'], 'kind': 'exact-obs-build-sources',
            'disturl': verified['source_build_disturl'], 'source_package': source_package,
            'multibuild_flavor': flavor or None, 'listing_url': url + '?rev=' + revision,
            'listing_sha256': sha(listing), 'files': files,
            'source_rpm_not_retained': True,
            'scope': 'Complete exact source archives/specs/patches; no source build, installation, execution or release approval'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['binaries', 'sources'])
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--reuse', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    selection = json.loads(args.selection.read_text())
    if selection['unresolved'] or not selection['packages']:
        raise ValueError('Incomplete dependency selection')
    checked_path(args.retained).mkdir(parents=True, exist_ok=True)
    checked_path(args.output)
    if args.output.exists():
        raise ValueError('Output receipt already exists; preserve previous attempts')
    entries = selection['packages']
    associations = []
    if args.action == 'sources':
        # Same source RPM filename is not enough to group signed binaries: bind
        # every selected archive to its actual signed OBS build identity first.
        groups = {}
        for entry in entries:
            verified = verify_rpm(args.retained / 'rpms' / Path(entry['location']).name, entry)
            association = {'identity': {field: entry[field] for field in IDENTITY}, **verified}
            associations.append(association)
            groups[(entry['source_rpm'], verified['source_build_disturl'])] = entry
        entries = list(groups.values())
    operation = retain_binary if args.action == 'binaries' else retain_source
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(operation, entry, args.retained, args.reuse): entry for entry in entries}
        for future in as_completed(futures):
            entry = futures[future]
            try:
                result = future.result()
                results.append(result)
                print('retained', entry['name'], flush=True)
            except Exception as error:
                failures.append({'identity': {field: entry[field] for field in IDENTITY}, 'error': str(error)})
                print('FAILED', entry['name'], type(error).__name__, flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        json.dump({'schema_version': 1, 'action': args.action, 'selection_sha256': sha(args.selection),
                   'helper_sha256': sha(_helper_path), 'results': results, 'failures': failures,
                   'validated_binary_source_associations': associations,
                   'package_execution': False, 'host_package_database_changed': False}, output, indent=2)
        output.write('\n')
    print(json.dumps({'results': len(results), 'failures': len(failures), 'output': str(args.output)}))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
