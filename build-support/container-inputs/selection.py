#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Select a conservative required RPM closure from one retained OS snapshot.

No installation, package execution, server lookup or version update occurs.
Required providers are selected by exact snapshot identity. Installed identities
only disambiguate providers and evaluate host-conditional dependencies; they do
not substitute unrecorded installed bytes for retained packages. This is not a
transaction solver: conflicts/obsoletes and installation scripts must receive a
separate disposition before assembly or execution.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

NS = {'c': 'http://linux.duke.edu/metadata/common',
      'r': 'http://linux.duke.edu/metadata/rpm'}
IDENTITY = ('name', 'epoch', 'version', 'release', 'arch')
OPERATORS = {'EQ', 'GE', 'GT', 'LE', 'LT'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def key(record):
    return tuple(record[name] for name in IDENTITY)


def evr(atom):
    value = str(atom.get('epoch', '0')) + ':' + str(atom.get('ver', ''))
    if atom.get('rel'):
        value += '-' + atom['rel']
    return value


def rpm_overlap(provide, requirement):
    import rpm
    flags = {'EQ': rpm.RPMSENSE_EQUAL, 'GT': rpm.RPMSENSE_GREATER,
             'GE': rpm.RPMSENSE_GREATER | rpm.RPMSENSE_EQUAL,
             'LT': rpm.RPMSENSE_LESS, 'LE': rpm.RPMSENSE_LESS | rpm.RPMSENSE_EQUAL}
    supplied = rpm.ds((provide['name'], flags['EQ'] if provide.get('ver') else 0,
                       evr(provide) if provide.get('ver') else ''), 'provides')
    needed = rpm.ds((requirement['name'], flags[requirement['flags']], evr(requirement)), 'requires')
    return bool(supplied.Compare(needed))


def satisfies(provide, requirement, compare):
    if provide['name'] != requirement['name']:
        return False
    flags = requirement.get('flags')
    if not flags:
        return True
    if flags not in OPERATORS:
        raise ValueError('Unsupported dependency operator: ' + str(flags))
    # Provides in this retained selection must be exact capabilities. Range
    # provides are not silently treated as equality.
    if provide.get('flags') not in (None, 'EQ'):
        raise ValueError('Unsupported range provider: ' + str(provide))
    return compare(provide, requirement)


def parse_atom(text):
    # Capability names may contain balanced parentheses, e.g. kmod(foo.ko).
    match = re.fullmatch(r'([^\s]+)(?:\s+(=|>=|<=|>|<)\s+([^\s]+))?', text)
    if not match or match[1].count('(') != match[1].count(')'):
        raise ValueError('Unsupported dependency atom: ' + text)
    name, operator, version = match.groups()
    atom = {'name': name}
    if operator:
        atom['flags'] = {'=': 'EQ', '>=': 'GE', '<=': 'LE', '>': 'GT', '<': 'LT'}[operator]
        epoch, separator, rest = version.partition(':')
        if not separator:
            epoch, rest = '0', version
        if not epoch.isdigit():
            raise ValueError('Invalid dependency epoch')
        ver, separator, release = rest.rpartition('-')
        atom.update(epoch=epoch, ver=ver if separator else rest)
        if separator:
            atom['rel'] = release
    return atom


def rich_dependency(text):
    """Support two atoms only; unknown Boolean syntax is an explicit failure."""
    if not text.startswith('(') or not text.endswith(')'):
        raise ValueError('Invalid rich dependency')
    inner = text[1:-1]
    matches = list(re.finditer(r'\s+(if|or)\s+', inner))
    if len(matches) != 1:
        raise ValueError('Unsupported rich dependency: ' + text)
    split = matches[0]
    left = parse_atom(inner[:split.start()])
    right_text = inner[split.end():]
    right = parse_condition(right_text) if split[1] == 'if' else parse_atom(right_text)
    return split[1], left, right


def parse_condition(text):
    # One observed conjunctive condition is supported explicitly. Do not
    # approximate arbitrary rich expressions or silently omit unknown syntax.
    if text.startswith('(') and text.endswith(')'):
        parts = text[1:-1].split(' and ')
        if len(parts) != 2 or any(part.startswith('(') for part in parts):
            raise ValueError('Unsupported compound condition: ' + text)
        return {'all_of': [parse_atom(part) for part in parts]}
    return parse_atom(text)


def parse_records(stream):
    records = []
    for _, node in ET.iterparse(stream, events=['end']):
        if node.tag != '{%s}package' % NS['c']:
            continue
        arch = node.findtext('c:arch', namespaces=NS)
        if arch in ('x86_64', 'noarch'):
            version = node.find('c:version', NS).attrib
            checksum = node.find('c:checksum', NS)
            location = node.find('c:location', NS).attrib['href']
            if not re.fullmatch(r'(x86_64|noarch)/[A-Za-z0-9+_.~-]+\.rpm', location):
                raise ValueError('Unsafe publisher package path')
            record = {'name': node.findtext('c:name', namespaces=NS), 'arch': arch,
                      'epoch': version['epoch'], 'version': version['ver'], 'release': version['rel'],
                      'location': location, 'publisher_digest_algorithm': checksum.attrib['type'],
                      'publisher_digest': checksum.text,
                      'source_rpm': node.findtext('c:format/r:sourcerpm', namespaces=NS),
                      'license': node.findtext('c:format/r:license', namespaces=NS),
                      'bytes': int(node.find('c:size', NS).attrib['package'])}
            for group in ('provides', 'requires', 'conflicts', 'obsoletes', 'recommends', 'suggests'):
                record[group] = [dict(entry.attrib) for entry in node.findall('c:format/r:' + group + '/r:entry', NS)]
            record['files'] = [entry.text for entry in node.findall('c:format/c:file', NS)]
            records.append(record)
        node.clear()
    return records


class Selector:
    def __init__(self, records, compare, installed_providers):
        self.records = {}
        self.providers = defaultdict(list)
        self.compare = compare
        self.installed_providers = installed_providers
        self.host_queries = {}
        self.selected = {}
        self.edges = []
        self.conditionals = []
        self.unresolved = []
        for record in records:
            identity = key(record)
            if identity in self.records:
                if record != self.records[identity]:
                    raise ValueError('Conflicting exact snapshot identity')
                continue
            self.records[identity] = record
            capabilities = record['provides'] + [{'name': path} for path in record['files']]
            for capability in capabilities:
                self.providers[capability['name']].append((identity, capability))

    def installed(self, requirement):
        name = requirement['name']
        if name not in self.host_queries:
            self.host_queries[name] = self.installed_providers(name)
        return [record for record in self.host_queries[name]
                if any(satisfies(capability, requirement, self.compare) for capability in record['provides'])]

    def candidates(self, requirement):
        return sorted({identity for identity, capability in self.providers[requirement['name']]
                       if satisfies(capability, requirement, self.compare)})

    def choose(self, requirement):
        candidates = self.candidates(requirement)
        if not candidates:
            raise ValueError('No exact snapshot provider for ' + str(requirement))
        selected = [identity for identity in candidates if identity in self.selected]
        if len(selected) == 1:
            return selected[0], 'already-selected exact provider'
        # A requirement explicitly naming a package should not pick an unrelated
        # compatibility provider just because it happens to be installed.
        named = [identity for identity in candidates if identity[0] == requirement['name']]
        if len(named) == 1:
            return named[0], 'unique exact named package'
        installed_keys = {key(record) for record in self.installed(requirement)}
        installed = [identity for identity in candidates if identity in installed_keys]
        if len(installed) == 1:
            return installed[0], 'unique installed identity present in pinned snapshot'
        if len(candidates) == 1:
            return candidates[0], 'unique exact snapshot capability provider'
        raise ValueError('Ambiguous provider requires explicit selection: ' + str(requirement))

    def add_requirement(self, parent, requirement, original=None):
        identity, basis = self.choose(requirement)
        if identity not in self.selected:
            self.selected[identity] = self.records[identity]
        edge = {'from': list(parent) if parent else None, 'requirement': requirement,
                'provider': list(identity), 'selection_basis': basis}
        if original:
            edge['rich_requirement'] = original
        if edge not in self.edges:
            self.edges.append(edge)

    def condition(self, expression):
        if 'all_of' in expression:
            values = [self.condition(part) for part in expression['all_of']]
            return (all(value[0] for value in values),
                    sorted({identity for _, selected, _ in values for identity in selected}),
                    sorted({identity for _, _, host in values for identity in host}))
        selected = [identity for identity in self.candidates(expression) if identity in self.selected]
        host = [key(record) for record in self.installed(expression)]
        return bool(selected or host), selected, host

    def select(self, roots):
        for name in roots:
            self.add_requirement(None, {'name': name})
        processed = set()
        conditional_edges = []
        while True:
            for identity in sorted(set(self.selected) - processed):
                processed.add(identity)
                for requirement in self.records[identity]['requires']:
                    try:
                        name = requirement['name']
                        if name.startswith('('):
                            operation, left, right = rich_dependency(name)
                            if operation == 'if':
                                conditional_edges.append((identity, name, left, right))
                            else:
                                available = [atom for atom in (left, right) if self.candidates(atom)]
                                if not available:
                                    raise ValueError('Neither rich OR alternative has a snapshot provider')
                                # Prefer a selected or installed viable alternative;
                                # otherwise the original declared first alternative.
                                choice = next((atom for atom in available if any(k in self.selected for k in self.candidates(atom))),
                                              next((atom for atom in available if self.installed(atom)), available[0]))
                                self.add_requirement(identity, choice, name)
                        else:
                            self.add_requirement(identity, requirement)
                    except ValueError as error:
                        self.unresolved.append({'from': list(identity), 'requirement': requirement, 'error': str(error)})
            changed = False
            conditions = []
            for identity, original, required, condition in conditional_edges:
                active, selected, host = self.condition(condition)
                conditions.append({'from': list(identity), 'requirement': original, 'active': active,
                                   'selected_condition_providers': [list(k) for k in selected],
                                   'installed_condition_providers': [list(identity) for identity in host]})
                if active:
                    before = len(self.selected)
                    try:
                        self.add_requirement(identity, required, original)
                    except ValueError as error:
                        failure = {'from': list(identity), 'requirement': {'name': original}, 'error': str(error)}
                        if failure not in self.unresolved:
                            self.unresolved.append(failure)
                    changed |= len(self.selected) != before
            self.conditionals = conditions
            if not changed and set(self.selected) == processed:
                break
        return sorted(self.selected.values(), key=key)


def host_provider_reader(transaction):
    def read(name):
        result = []
        matches = list(transaction.dbMatch('provides', name))
        if name.startswith('/'):
            matches += list(transaction.dbMatch('basenames', name))
        seen = set()
        for header in matches:
            record = {field: str(header[field] or '0') for field in IDENTITY}
            if key(record) in seen:
                continue
            seen.add(key(record))
            capabilities = []
            for capability, flags, version in zip(header['providename'], header['provideflags'], header['provideversion']):
                if capability != name:
                    continue
                atom = {'name': capability}
                if version:
                    atom = parse_atom(capability + ' = ' + version)
                    sense = flags & 14
                    if sense != 8:
                        raise ValueError('Unsupported installed range provider')
                capabilities.append(atom)
            if name.startswith('/') and name in header['filenames']:
                capabilities.append({'name': name})
            record['provides'] = capabilities
            result.append(record)
        return result
    return read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogs', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--root', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import rpm
    catalogs = json.loads(args.catalogs.read_text())
    matches = [entry for entry in catalogs if entry['kind'] == 'binary' and entry['repository_url'] == args.repository]
    if len(matches) != 1 or not re.fullmatch(r'https://download\.opensuse\.org/history/[0-9]{8}/tumbleweed/repo/oss', args.repository):
        raise ValueError('Exactly one fixed retained snapshot is required')
    catalog = matches[0]
    metadata = Path(catalog['file'])
    if sha(metadata) != catalog['sha256']:
        raise ValueError('Retained metadata changed')
    with subprocess.Popen(['zstd', '-dc', str(metadata)], stdout=subprocess.PIPE) as process:
        try:
            records = parse_records(process.stdout)
        finally:
            process.stdout.close()
        if process.wait():
            raise ValueError('Retained metadata decompression failed')
    selector = Selector(records, rpm_overlap, host_provider_reader(rpm.TransactionSet()))
    packages = selector.select(args.root)
    for package in packages:
        package['retrieval_urls'] = [args.repository + '/' + package['location']]
    result = {'schema_version': 1, 'classification': 'Exact retained-snapshot required-provider selection; not install/assembly approval',
              'catalog': catalog, 'catalogs_sha256': sha(args.catalogs), 'explicit_roots': args.root,
              'packages': packages, 'dependency_edges': selector.edges,
              'conditional_requirements': selector.conditionals,
              'host_provider_observations': selector.host_queries, 'unresolved': selector.unresolved,
              'limits': ['No package installed or package script executed.',
                         'Conflicts/obsoletes, scripts, extracted configuration and required selected paths need review before assembly.',
                         'Host conditional dependencies are recorded; no kernel/security configuration is changed.',
                         'Optional recommendations/suggestions remain visible but are not automatically selected.',
                         'Existing host identities are selection evidence, not a substitute for retained runtime bytes.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'packages': len(packages), 'edges': len(selector.edges), 'conditions': len(selector.conditionals),
                      'unresolved': len(selector.unresolved), 'output': str(args.output)}))
    return 1 if selector.unresolved else 0


if __name__ == '__main__':
    raise SystemExit(main())
