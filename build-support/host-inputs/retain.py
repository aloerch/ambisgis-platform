#!/usr/bin/env python3
"""Recover exact host RPMs and source-build inputs without installing anything.

Network access is acquisition only. RPM signatures, publisher hashes, exact
identities and the observed installed header digest are verified. Removed SRPMs
can be replaced in custody by the complete public OBS source directory selected
by the verified binary's DISTURL. This does not claim a compiler bootstrap build.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def digest(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def checked_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
        raise ValueError('Unapproved acquisition URL')
    if parsed.hostname != 'download.opensuse.org' or parsed.query or parsed.fragment:
        raise ValueError('Unapproved RPM publisher')
    if not re.fullmatch(r'/(?:history/[0-9]{8}/)?(?:source/)?tumbleweed/repo/oss/(?:x86_64|noarch|src)/[A-Za-z0-9+_.-]+\.rpm', parsed.path):
        raise ValueError('Unapproved RPM path')
    return url


def fetch(url, dest, expected_size, expected_digest, algorithm):
    if dest.is_symlink() or any(parent.is_symlink() for parent in dest.parents):
        raise ValueError('Symlink at retained destination')
    if dest.exists():
        if dest.stat().st_size != expected_size or digest(dest, algorithm) != expected_digest:
            raise ValueError('Retained bytes changed: ' + str(dest))
        return {'url': url, 'network': False, 'sha256': digest(dest), 'bytes': expected_size}
    partial = dest.with_name(dest.name + '.partial-' + str(time.time_ns()))
    with urllib.request.urlopen(url, timeout=90) as response, partial.open('xb') as output:
        total = 0
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > expected_size:
                raise ValueError('Download exceeds pinned size')
            output.write(block)
        output.flush(); os.fsync(output.fileno())
        final_url = response.url
    if total != expected_size or digest(partial, algorithm) != expected_digest:
        raise ValueError('Downloaded digest/size mismatch')
    # link is creation-only; concurrent acquisition cannot overwrite a winner.
    os.link(partial, dest)
    partial.unlink()
    return {'url': url, 'final_url': final_url, 'network': True,
            'sha256': digest(dest), 'bytes': total}


def verify_rpm(path, entry, source=False):
    if digest(path, entry['publisher_digest_algorithm']) != entry['publisher_digest']:
        raise ValueError('RPM publisher digest mismatch')
    signature = subprocess.run(['rpmkeys', '--checksig', str(path)], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               env={**os.environ, 'LC_ALL': 'C'})
    if signature.returncode or 'digests signatures OK' not in signature.stdout:
        raise ValueError('RPM signature verification failed')
    fields = ['NAME', 'EPOCHNUM', 'VERSION', 'RELEASE', 'ARCH', 'SOURCEPACKAGE', 'SHA256HEADER', 'DISTURL']
    values = subprocess.check_output(['rpm', '-qp', '--qf', '\t'.join('%{'+k+'}' for k in fields), str(path)],
                                     text=True, stderr=subprocess.PIPE).split('\t')
    expected = [entry[k] for k in ('name', 'epoch', 'version', 'release')]
    if values[:4] != expected or (values[5] == '1') != source:
        raise ValueError('RPM identity mismatch')
    if not source:
        if values[4] != entry['arch'] or values[6] != entry['installed_header_sha256']:
            raise ValueError('RPM differs from observed installed header')
        if values[7] != entry['source_build_disturl']:
            raise ValueError('RPM source-build identity mismatch')
    return {'signature': signature.stdout.strip(), 'header_sha256': values[6], 'disturl': values[7]}


def binary(entry, retained):
    name = Path(entry['location']).name
    dest = retained / 'rpms' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    attempts = []
    for url in entry['retrieval_urls']:
        checked_url(url)
        try:
            receipt = fetch(url, dest, entry['bytes'], entry['publisher_digest'], entry['publisher_digest_algorithm'])
            return {'name': entry['name'], 'file': str(dest), **receipt,
                    'verification': verify_rpm(dest, entry), 'attempts': attempts}
        except urllib.error.HTTPError as error:
            attempts.append({'url': url, 'status': error.code})
            if error.code not in (404, 410):
                raise
    raise ValueError('Exact binary unavailable: ' + repr(attempts))


def obs_identity(disturl):
    match = re.fullmatch(r'obs://build\.opensuse\.org/(openSUSE:Factory)/standard/([0-9a-f]{32})-([A-Za-z0-9+_.:-]+)', disturl)
    if not match:
        raise ValueError('Unreviewed source-build origin')
    return match.groups()


def source_listing(data, revision):
    root = ET.fromstring(data)
    if root.tag != 'directory' or root.attrib.get('srcmd5') != revision:
        raise ValueError('OBS source directory differs from signed build identity')
    result = []
    for node in root:
        if node.tag != 'entry':
            raise ValueError('Unexpanded OBS source/link entry')
        row = dict(node.attrib)
        if not re.fullmatch(r'[A-Za-z0-9+_.-]+', row['name']) or row['name'] in ('.', '..', '_link'):
            raise ValueError('Unsafe or unresolved OBS source entry')
        if not re.fullmatch(r'[0-9a-f]{32}', row['md5']) or not 0 <= int(row['size']) <= 1024**3:
            raise ValueError('Invalid OBS source metadata')
        result.append(row)
    if not result or len({r['name'] for r in result}) != len(result):
        raise ValueError('Empty or duplicate OBS source entries')
    # OBS srcmd5 is the MD5 of this sorted md5sum-style source listing. Bind
    # the entries as well as the XML attribute to the signed RPM's DISTURL.
    listing = ''.join(row['md5'] + '  ' + row['name'] + '\n'
                      for row in sorted(result, key=lambda row: row['name'])).encode()
    if hashlib.md5(listing).hexdigest() != revision:
        raise ValueError('OBS source entry set does not match signed source digest')
    return result


def source(entry, sources, retained):
    candidates = [e for e in sources if Path(e['location']).name == entry['source_rpm']]
    if candidates:
        src = candidates[0]; path = retained / 'source-rpms' / entry['source_rpm']
        if path.exists():
            return {'source_rpm': entry['source_rpm'], 'kind': 'retained-source-rpm',
                    'sha256': digest(path), 'verification': verify_rpm(path, src, source=True)}
    # The exact signed binary must already have been retained and verified.
    verified = verify_rpm(retained / 'rpms' / Path(entry['location']).name, entry)
    project, revision, package = obs_identity(verified['disturl'])
    # OBS multibuild flavors share the source package and exact source digest.
    # The response still must match the signed binary's full source revision.
    source_package, _, flavor = package.partition(':')
    url = 'https://api.opensuse.org/public/source/' + urllib.parse.quote(project, safe='') + '/' + urllib.parse.quote(source_package, safe='')
    listing_url = url + '?rev=' + revision
    dest = retained / 'obs-source' / (package.replace(':', '_') + '-' + revision)
    dest.mkdir(parents=True, exist_ok=True)
    listing = dest / 'directory.xml'
    if listing.exists():
        data = listing.read_bytes()
    else:
        with urllib.request.urlopen(listing_url, timeout=90) as response:
            data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError('Source listing too large')
        source_listing(data, revision)
        with listing.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    rows = source_listing(data, revision)
    receipts = []
    for row in rows:
        file_url = url + '/' + urllib.parse.quote(row['name'], safe='') + '?rev=' + revision
        receipt = fetch(file_url, dest / row['name'], int(row['size']), row['md5'], 'md5')
        receipts.append({'name': row['name'], 'publisher_md5': row['md5'], **receipt})
    return {'source_rpm': entry['source_rpm'], 'kind': 'exact-obs-build-sources',
            'source_rpm_not_retained': True, 'disturl': verified['disturl'],
            'source_package': source_package, 'multibuild_flavor': flavor or None,
            'listing_url': listing_url, 'listing_sha256': hashlib.sha256(data).hexdigest(),
            'files': receipts, 'scope': 'Original source archives/specs/patches; no source-to-binary rebuild claimed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['binaries', 'sources'])
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if args.action == 'binaries':
        entries = manifest['packages']
        operation = lambda e: binary(e, args.retained)
    else:
        entries = list({e['source_rpm']: e for e in manifest['packages']}.values())
        operation = lambda e: source(e, manifest['source_packages'], args.retained)
    results, failures = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(operation, e): e for e in entries}
        for future in concurrent.futures.as_completed(futures):
            entry = futures[future]
            try:
                results.append(future.result()); print('retained', entry['name'], flush=True)
            except Exception as error:
                failures.append({'name': entry['name'], 'source_rpm': entry['source_rpm'], 'error': str(error)})
                print('FAILED', entry['name'], str(error), flush=True)
    with args.output.open('x') as stream:
        json.dump({'action': args.action, 'manifest_sha256': digest(args.manifest),
                   'results': results, 'failures': failures}, stream, indent=2); stream.write('\n')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
