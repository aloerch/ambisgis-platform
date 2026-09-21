#!/usr/bin/env python3
"""Retain exact supporting RPM inputs, inspect scriptlets, extract without installation.

Run on the host. Network exists only in fetch; extract is entirely retained-input.
RPMs are supporting toolchain inputs, never a source of QGIS product artifacts.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

NS = {'c': 'http://linux.duke.edu/metadata/common', 'r': 'http://linux.duke.edu/metadata/rpm'}


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def package_records(primary, arches=('x86_64', 'noarch')):
    """Read retained primary metadata; selection is an explicit caller decision."""
    p = subprocess.Popen(['zstd', '-dc', str(primary)], stdout=subprocess.PIPE)
    records = {}
    try:
        for _, node in ET.iterparse(p.stdout, events=('end',)):
            if node.tag != '{%s}package' % NS['c']: continue
            name = node.findtext('c:name', namespaces=NS)
            arch = node.findtext('c:arch', namespaces=NS)
            if arch in arches:
                ver = node.find('c:version', NS).attrib
                chk = node.find('c:checksum', NS)
                records[name] = {'name': name, 'arch': arch, 'epoch': ver['epoch'],
                    'version': ver['ver'], 'release': ver['rel'],
                    'location': node.find('c:location', NS).attrib['href'],
                    'publisher_digest_algorithm': chk.attrib['type'], 'publisher_digest': chk.text,
                    'source_rpm': node.findtext('c:format/r:sourcerpm', namespaces=NS),
                    'license': node.findtext('c:format/r:license', namespaces=NS)}
            node.clear()
    finally:
        p.stdout.close()
    if p.wait() != 0: raise ValueError('Cannot decompress publisher metadata')
    return records


def safe_relative(value):
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Unsafe payload path: ' + value)
    return Path(*p.parts)


def cpio_entries(data):
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        if header[:6] not in (b'070701', b'070702'): raise ValueError('Unsupported cpio format')
        vals = [int(header[6+i*8:14+i*8], 16) for i in range(13)]
        inode, mode, _, _, nlink, _, size, _, _, _, _, namesize, checksum = vals
        offset += 110
        if namesize < 1 or offset + namesize > len(data): raise ValueError('Invalid cpio name')
        rawname = data[offset:offset+namesize]
        if rawname[-1:] != b'\0': raise ValueError('Invalid cpio name terminator')
        name = rawname[:-1].decode('utf-8')
        offset = (offset + namesize + 3) & ~3
        if offset + size > len(data): raise ValueError('Truncated cpio payload')
        payload = data[offset:offset+size]
        offset = (offset + size + 3) & ~3
        if header[:6] == b'070702' and sum(payload) & 0xffffffff != checksum:
            raise ValueError('Invalid cpio checksum')
        if name == 'TRAILER!!!': return
        if name in ('.', './'): continue
        yield safe_relative(name), mode, payload, inode, nlink
    raise ValueError('Missing cpio trailer')


def extract_cpio(data, prefix):
    """No devices, traversal, special permissions or writes through symlink ancestors."""
    prefix = Path(prefix).resolve()
    entries = list(cpio_entries(data))
    hard_data = {inode: content for _, mode, content, inode, nlink in entries
                 if stat.S_ISREG(mode) and nlink > 1 and content}
    for rel, mode, content, inode, nlink in entries:
        dest = prefix / rel
        for ancestor in dest.parents:
            if ancestor == prefix: break
            if ancestor.is_symlink(): raise ValueError('Symlink ancestor: ' + str(ancestor))
        if stat.S_ISDIR(mode):
            if dest.is_symlink(): raise ValueError('Directory collides with symlink')
            dest.mkdir(parents=True, exist_ok=True)
        elif stat.S_ISREG(mode):
            if nlink > 1 and not content: content = hard_data.get(inode, b'')
            if dest.is_symlink(): raise ValueError('File collides with symlink')
            if dest.exists():
                if not dest.is_file() or dest.read_bytes() != content:
                    raise ValueError('Nonidentical payload collision: ' + str(rel))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            dest.chmod(mode & 0o777)
        elif stat.S_ISLNK(mode):
            target = content.decode('utf-8')
            if PurePosixPath(target).is_absolute():
                alternatives = {'/etc/alternatives/pylupdate5': '/usr/bin/pylupdate5-3.13',
                                '/etc/alternatives/pyrcc5': '/usr/bin/pyrcc5-3.13',
                                '/etc/alternatives/pyuic5': '/usr/bin/pyuic5-3.13',
                                '/etc/alternatives/pyqt5-sip': '/usr/share/pyqt5-sip-3.13',
                                '/etc/alternatives/pyproj': '/usr/bin/pyproj-3.13'}
                if target in alternatives: target = alternatives[target]
                if not target.startswith('/usr/'):
                    raise ValueError('External absolute symlink: ' + target)
                target = os.path.relpath(prefix / target.lstrip('/'), dest.parent)
            # Lexically enforce target containment, without following existing links.
            resolved = Path(os.path.abspath(dest.parent / target))
            if not resolved.is_relative_to(prefix): raise ValueError('Escaping symlink')
            if dest.is_symlink():
                if os.readlink(dest) != target: raise ValueError('Nonidentical symlink collision')
                continue
            if dest.exists(): raise ValueError('Symlink collides with file')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(target)
        else:
            raise ValueError('Unsupported cpio file type')


def checked_package(entry, source=False):
    if 'qgis' in entry['name'].lower(): raise ValueError('Binary QGIS inputs forbidden')
    if entry['arch'] not in (('src', 'nosrc') if source else ('x86_64', 'noarch')): raise ValueError('Unexpected architecture')
    safe_relative(entry['location'])
    if entry['publisher_digest_algorithm'] not in ('sha256', 'sha512'):
        raise ValueError('Weak or unknown publisher digest')


def fetch_one(entry, root, base, source=False):
    checked_package(entry, source=source)
    dest = root / ('source-rpms' if source else 'rpms') / Path(entry['location']).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink(): raise ValueError('Retained RPM path must not be a symlink')
    if not dest.exists():
        tmp = dest.with_suffix(dest.suffix + '.partial')
        if tmp.exists() or tmp.is_symlink(): tmp.rename(tmp.with_name(tmp.name + '.' + str(time.time_ns())))
        with urllib.request.urlopen(base.rstrip('/') + '/' + entry['location'], timeout=90) as src, tmp.open('wb') as dst:
            while b := src.read(1024*1024): dst.write(b)
        if digest(tmp, entry['publisher_digest_algorithm']) != entry['publisher_digest']:
            raise ValueError('Publisher checksum mismatch: ' + dest.name)
        tmp.rename(dest)
    if digest(dest, entry['publisher_digest_algorithm']) != entry['publisher_digest']:
        raise ValueError('Retained checksum mismatch: ' + dest.name)
    signature = subprocess.run(['rpmkeys', '--checksig', str(dest)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env={**os.environ, 'LC_ALL': 'C'})
    if signature.returncode != 0 or 'digests signatures OK' not in signature.stdout:
        raise ValueError('RPM signature verification failed: ' + dest.name)
    return {'name': entry['name'], 'file': str(dest), 'sha256': digest(dest), 'size': dest.stat().st_size, 'signature_verification': signature.stdout.strip()}


def fetch(manifest, root, source=False):
    entries = manifest['source_packages' if source else 'packages']
    base = manifest['source_repository_url' if source else 'repository_url']
    results = []; failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_one, e, root, base, source): e for e in entries}
        for future in concurrent.futures.as_completed(futures):
            entry = futures[future]
            try: results.append(future.result()); print('retained', entry['name'], flush=True)
            except Exception as e: failures.append({'name': entry['name'], 'error': str(e)}); print('FAILED', entry['name'], str(e), flush=True)
    receipt = {'kind': 'sources' if source else 'binaries', 'packages': sorted(results, key=lambda e:e['name']), 'failures': failures}
    out = root / ('acquisition-' + str(time.time_ns()) + '.json')
    out.write_text(json.dumps(receipt, indent=2)+'\n')
    if failures: raise SystemExit(1)


def extract(manifest, root, prefix):
    if prefix.exists(): raise ValueError('Extraction prefix must be fresh')
    prefix.mkdir(parents=True)
    inspection = root / 'rpm-inspection'; inspection.mkdir(exist_ok=True)
    for entry in manifest['packages']:
        checked_package(entry)
        rpm = root / 'rpms' / Path(entry['location']).name
        if digest(rpm, entry['publisher_digest_algorithm']) != entry['publisher_digest']:
            raise ValueError('Retained checksum mismatch: ' + rpm.name)
        scripts = subprocess.check_output(['rpm', '-qp', '--scripts', str(rpm)], stderr=subprocess.STDOUT)
        (inspection / (rpm.name + '.scripts.txt')).write_bytes(scripts)
        query = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME}\n%{EPOCHNUM}\n%{VERSION}\n%{RELEASE}\n%{ARCH}\n%{SOURCERPM}\n%{LICENSE}\n', str(rpm)], stderr=subprocess.DEVNULL).decode().splitlines()
        if query[:5] != [entry['name'], entry['epoch'], entry['version'], entry['release'], entry['arch']]:
            raise ValueError('RPM identity differs from manifest')
        (inspection / (rpm.name + '.identity.txt')).write_text('\n'.join(query)+'\n')
        payload = subprocess.check_output(['rpm2cpio', str(rpm)])
        extract_cpio(payload, prefix)
        print('extracted', entry['name'], flush=True)
    (prefix/'support-inputs.json').write_text(json.dumps(manifest, indent=2)+'\n')
    inventory = []
    for path in sorted(prefix.rglob('*')):
        if path.is_symlink():
            inventory.append({'path': str(path.relative_to(prefix)), 'link': os.readlink(path)})
        elif path.is_file():
            inventory.append({'path': str(path.relative_to(prefix)), 'sha256': digest(path), 'size': path.stat().st_size, 'mode': oct(path.stat().st_mode & 0o777)})
    (prefix.parent/(prefix.name+'-inventory.json')).write_text(json.dumps({'prefix':str(prefix),'files':inventory},indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch','fetch-sources','extract'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--retained', type=Path, required=True)
    parser.add_argument('--prefix', type=Path)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text())
    if manifest['repository_url'] != 'https://download.opensuse.org/tumbleweed/repo/oss':
        raise ValueError('Unreviewed publisher repository')
    if args.action in ('fetch','fetch-sources'):
        if args.action == 'fetch-sources' and manifest['source_repository_url'] != 'https://download.opensuse.org/source/tumbleweed/repo/oss':
            raise ValueError('Unreviewed source repository')
        fetch(manifest,args.retained,source=args.action == 'fetch-sources')
    else:
        if args.prefix is None: parser.error('--prefix is required for extract')
        extract(manifest,args.retained,args.prefix)

if __name__=='__main__': main()
