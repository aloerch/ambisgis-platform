#!/usr/bin/env python3
"""Inventory selected installed build tools and their RPM dependency providers.

Read-only: this neither installs packages nor consults a package server. Exact
publisher matches are selected from already retained, hash-pinned metadata.
This conservative provider closure is not a claim of a source-rebuilt toolchain.
Run with the host Python RPM bindings. Unresolved requirements remain explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

NS = {'c': 'http://linux.duke.edu/metadata/common', 'r': 'http://linux.duke.edu/metadata/rpm'}


def parse_packages(stream, arches):
    """Preserve multiple versions/architectures; a name is not an identity."""
    records = []
    for _, node in ET.iterparse(stream, events=('end',)):
        if node.tag != '{%s}package' % NS['c']:
            continue
        if node.findtext('c:arch', namespaces=NS) in arches:
            version = node.find('c:version', NS).attrib
            checksum = node.find('c:checksum', NS)
            records.append({'name': node.findtext('c:name', namespaces=NS),
                'arch': node.findtext('c:arch', namespaces=NS),
                'epoch': version['epoch'], 'version': version['ver'], 'release': version['rel'],
                'location': node.find('c:location', NS).attrib['href'],
                'publisher_digest_algorithm': checksum.attrib['type'], 'publisher_digest': checksum.text,
                'source_rpm': node.findtext('c:format/r:sourcerpm', namespaces=NS),
                'license': node.findtext('c:format/r:license', namespaces=NS),
                'bytes': int(node.find('c:size', NS).attrib['package'])})
        node.clear()
    return records


def package_records(path, arches):
    with subprocess.Popen(['zstd', '-dc', str(path)], stdout=subprocess.PIPE) as process:
        try:
            records = parse_packages(process.stdout, arches)
        finally:
            process.stdout.close()
        if process.wait() != 0:
            raise ValueError('Cannot decompress retained publisher metadata')
    return records


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(header):
    return {name: str(header[name] or '0') for name in
            ('name', 'epoch', 'version', 'release', 'arch')}


def key(row):
    return tuple(row[name] for name in ('name', 'epoch', 'version', 'release', 'arch'))


def exact_record(installed, records):
    matches = [row for row in records if key(row) == key(installed)]
    if not matches:
        raise ValueError('No exact publisher identity for ' + repr(key(installed)))
    signatures = {(row['publisher_digest_algorithm'], row['publisher_digest'],
                   row['source_rpm']) for row in matches}
    if len(signatures) != 1:
        raise ValueError('Conflicting publisher records for ' + repr(key(installed)))
    result = dict(matches[0])
    result['retrieval_urls'] = sorted({row['repository_url'].rstrip('/') + '/' + row['location']
                                       for row in matches})
    return result


def simple_rich(expression):
    """Parse two explicit atoms only; version semantics stay with librpm."""
    atom = r'([A-Za-z0-9+_./-]+)(?:\s*(=|>=|<=|>|<)\s*([A-Za-z0-9+_.:~-]+))?'
    match = re.fullmatch(r'\(' + atom + r' (if|or) ' + atom + r'\)', expression)
    if not match:
        raise ValueError('Unsupported rich dependency: ' + expression)
    name, operator, version, connective, name2, operator2, version2 = match.groups()
    return connective, (name, operator, version), (name2, operator2, version2)


def checked_metadata(entry):
    path = Path(entry['file'])
    if digest(path) != entry['sha256']:
        raise ValueError('Retained publisher metadata digest mismatch')
    return path


def selected_paths(observation):
    paths = set()
    for row in observation['toolchain_files']:
        path = Path(row['resolved'])
        if not path.is_absolute() or digest(path) != row['sha256']:
            raise ValueError('Observed tool changed: ' + str(path))
        paths.add(str(path))
        # Only paths already observed by ldd. No ldd invocation on new binaries.
        linkage = row.get('linkage', {})
        output = linkage.get('stdout', '') + linkage.get('stderr', '')
        if 'not found' in output:
            raise ValueError('Unresolved observed linkage: ' + str(path))
        if linkage.get('exit_code') != 0:
            with path.open('rb') as stream:
                script = stream.read(2) == b'#!'
            if not (linkage.get('exit_code') == 1 and script and
                    output.strip() == 'not a dynamic executable'):
                raise ValueError('Failed linkage observation: ' + str(path))
        for line in linkage.get('stdout', '').splitlines():
            match = re.search(r'(?:=>\s+)?(/\S+)\s+\(0x[0-9a-fA-F]+\)', line)
            if match:
                paths.add(str(Path(match.group(1)).resolve(strict=True)))
    return sorted(paths)


def closure(paths, package_names):
    import rpm  # Only needed for the actual host observation.
    ts = rpm.TransactionSet()
    selected, pending, unresolved, edges, bootstrap = {}, [], [], [], set()
    match_cache = {}

    def matching(requirement):
        name = requirement.N()
        cache_key = (name, requirement.Flags(), requirement.EVR())
        if cache_key in match_cache:
            return dict(match_cache[cache_key])
        candidates = list(ts.dbMatch('providename', name))
        if name.startswith('/'):
            candidates += list(ts.dbMatch('basenames', name))
        matches = {}
        for candidate in candidates:
            if identity(candidate)['arch'] not in ('x86_64', 'noarch'):
                continue
            file_match = name.startswith('/') and not requirement.EVR()
            if file_match or any(provide.Compare(requirement) for provide in rpm.ds(candidate, 'provides')):
                matches[key(identity(candidate))] = candidate
        match_cache[cache_key] = matches
        return dict(matches)

    def dependency(atom):
        name, operator, version = atom
        flags = {None: 0, '=': rpm.RPMSENSE_EQUAL, '>': rpm.RPMSENSE_GREATER,
                 '<': rpm.RPMSENSE_LESS, '>=': rpm.RPMSENSE_GREATER | rpm.RPMSENSE_EQUAL,
                 '<=': rpm.RPMSENSE_LESS | rpm.RPMSENSE_EQUAL}[operator]
        return next(iter(rpm.ds((name, flags, version or ''), 'requires')))

    def add(header, reason):
        row = identity(header)
        if row['arch'] not in ('x86_64', 'noarch'):
            return False
        k = key(row)
        if k not in selected:
            selected[k] = {**row, 'source_rpm': str(header['sourcerpm']),
                           'source_build_disturl': str(header['disturl']),
                           'installed_header_sha256': str(header['sha256header']), 'reasons': []}
            pending.append(header)
        if reason not in selected[k]['reasons']:
            selected[k]['reasons'].append(reason)
        return True

    for path in paths:
        owners = list(ts.dbMatch('basenames', path))
        if not any([add(header, {'file': path}) for header in owners]):
            unresolved.append({'file': path, 'error': 'No selected-architecture RPM owner'})
    for name in package_names:
        owners = list(ts.dbMatch('name', name))
        if not any([add(header, {'explicit_build_support': name}) for header in owners]):
            unresolved.append({'package': name, 'error': 'Not installed'})

    while pending:
        header = pending.pop()
        owner = identity(header)
        for requirement in rpm.ds(header, 'requires'):
            name = requirement.N()
            if name.startswith('rpmlib('):
                bootstrap.add(requirement.DNEVR())
                continue
            if requirement.IsRich():
                try:
                    connective, left, right = simple_rich(name)
                except ValueError as error:
                    unresolved.append({'owner': owner, 'requirement': requirement.DNEVR(),
                                       'error': str(error)})
                    continue
                condition = matching(dependency(right))
                if connective == 'if' and not condition:
                    edges.append({'owner': owner, 'requirement': requirement.DNEVR(),
                                  'condition_installed': False})
                    continue
                matches = matching(dependency(left))
                if connective == 'or':
                    matches.update(condition)
                else:
                    for candidate in condition.values():
                        add(candidate, {'condition_of': owner['name'], 'requirement': requirement.DNEVR()})
            else:
                matches = matching(requirement)
            if not matches:
                unresolved.append({'owner': owner, 'requirement': requirement.DNEVR(),
                                   'error': 'No installed matching provider'})
            for candidate in matches.values():
                add(candidate, {'required_by': owner['name'], 'requirement': requirement.DNEVR()})
                edges.append({'owner': owner, 'requirement': requirement.DNEVR(),
                              'provider': identity(candidate)})
    return sorted(selected.values(), key=key), edges, unresolved, sorted(bootstrap)


def inventory(args):
    observation = json.loads(args.observation.read_text())
    pinned = json.loads(args.support_manifest.read_text())
    catalogs = [{'kind': 'binary', 'repository_url': pinned['repository_url'], **pinned['metadata']},
                {'kind': 'source', 'repository_url': pinned['source_repository_url'], **pinned['source_metadata']}]
    if args.catalogs:
        catalogs += json.loads(args.catalogs.read_text())
    binary, sources = [], []
    for catalog in catalogs:
        arches = ('x86_64', 'noarch') if catalog['kind'] == 'binary' else ('src', 'nosrc')
        records = package_records(checked_metadata(catalog), arches)
        for row in records:
            row['repository_url'] = catalog['repository_url']
            (binary if catalog['kind'] == 'binary' else sources).append(row)
    paths = selected_paths(observation)
    generated_resources = []
    if args.runtime_observation:
        runtime = json.loads(args.runtime_observation.read_text())
        for row in runtime['files']:
            path = Path(row['resolved'])
            if not path.is_absolute() or digest(path) != row['sha256']:
                raise ValueError('Observed runtime file changed: ' + str(path))
            if str(path) in ('/etc/ld.so.cache', '/usr/share/mime/mime.cache', '/usr/lib64/gconv/gconv-modules.cache'):
                generated_resources.append({**row,
                    'disposition': 'Observed generated host cache; retain generator/source packages separately. Clean-prefix regeneration remains unperformed.'})
            else:
                paths.append(str(path))
        paths = sorted(set(paths))
    selected, edges, unresolved, bootstrap = closure(paths, args.package)
    packages, source_packages = [], {}
    for installed in selected:
        try:
            entry = exact_record(installed, binary)
            if entry['source_rpm'] != installed['source_rpm']:
                raise ValueError('Installed and publisher source-RPM association differ')
            entry['installed_header_sha256'] = installed['installed_header_sha256']
            entry['source_build_disturl'] = installed['source_build_disturl']
            packages.append(entry)
            source = [row for row in sources
                      if Path(row['location']).name == entry['source_rpm']]
            if not source:
                raise ValueError('No exact source RPM for ' + entry['source_rpm'])
            source_packages[entry['source_rpm']] = exact_record(source[0], source)
        except ValueError as error:
            unresolved.append({'installed': installed, 'error': str(error)})
    result = {
        'schema_version': 1,
        'classification': 'Selected host tool/library and conservative installed RPM provider custody; not source-built toolchain acceptance',
        'observation_sha256': digest(args.observation),
        'runtime_observation_sha256': digest(args.runtime_observation) if args.runtime_observation else None,
        'generated_host_resources': generated_resources,
        'support_manifest_sha256': digest(args.support_manifest),
        'repository_url': pinned['repository_url'],
        'source_repository_url': pinned['source_repository_url'],
        'metadata': pinned['metadata'], 'source_metadata': pinned['source_metadata'],
        'metadata_catalogs': catalogs,
        'selection_paths': paths, 'explicit_packages': args.package,
        'selected_file_observations': [{'path': path, 'sha256': digest(path),
                                        'bytes': Path(path).stat().st_size} for path in paths],
        'linkage_exceptions': [{'path': row['resolved'], 'reason': 'Verified shebang script; observed ldd says not a dynamic executable. Interpreter/provider dependencies are retained separately.'}
                              for row in observation['toolchain_files'] if row['linkage']['exit_code'] != 0],
        'installed_packages': selected, 'dependency_edges': edges,
        'rpm_bootstrap_capabilities': bootstrap,
        'packages': sorted(packages, key=key),
        'source_packages': sorted(source_packages.values(), key=key),
        'unresolved': unresolved,
        'limits': ['Includes required installed providers, not optional recommends/suggests.',
                   'No base container image selected; host OS/kernel and remaining resources are separately inventoried.',
                   'No source-to-binary compiler/bootstrap reproduction or clean product install is claimed.'],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({'packages': len(packages), 'sources': len(source_packages),
                      'unresolved': len(unresolved), 'output': str(args.output)}))
    return 1 if unresolved else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation', type=Path, required=True)
    parser.add_argument('--support-manifest', type=Path, required=True)
    parser.add_argument('--catalogs', type=Path)
    parser.add_argument('--runtime-observation', type=Path)
    parser.add_argument('--package', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    return inventory(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
