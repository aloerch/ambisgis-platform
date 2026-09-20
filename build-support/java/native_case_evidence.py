#!/usr/bin/env python3
"""Compare exact historical XML/MapFish native case failures with fresh outcomes.

Report verification is separate from runtime isolation, source closure and product
acceptance. Historical duplicate setup/teardown error records remain visible.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from native_reports import parse_report
from resolution import sha, write_json
import http_fixtures

MODULES = {
    'xml': 'geotools/modules/library/xml',
    'mapfish': 'mapfish-print-v2-da1f37cfc0d7a235cb2c0ec5677010495d9f664b',
}
PREFIXES = {'xml': 'org.geotools.xml.', 'mapfish': 'org.mapfish.'}
SCHEMA_CLASS = 'org.geotools.xml.resolver.SchemaCacheTest'
SCHEMA_METHODS = ('delete', 'resolve', 'testIsSuitableDirectoryToContainCache',
                  'downloadWithHttpClient', 'circularRedirectMultithreadedHttpClient')
MAPFISH_FAILURES = {
    'org.mapfish.print.config.LocalHostMatcherTest': ('testAllIpV4',),
    'org.mapfish.print.config.layout.LegendsBlockTest': ('testBrokenUrl',),
    'org.mapfish.print.map.readers.WMTSServiceInfoTest': ('testReadCapabilities1_0_0',),
    'org.mapfish.print.map.readers.WMTSMapReaderTest': ('testGetTileUriUsingCapabilities', 'testGetTileUriNoCapabilities'),
    'org.mapfish.print.map.readers.WMSMapReaderTest': (
        'testGetTileUri_Version1_1_1', 'testGetTileUri_VersionDefault', 'testGetTileUri_Version1_3_0',
        'testGetTileUri_Version1_3_0_NonEPSG4326', 'testGetTileUri_VersionCustomParams_1_3_0',
        'testMergeableParamsWithArrayCustomParams'),
    'org.mapfish.print.PDFUtilsTest': (
        'testGetImageDirectWMSError', 'testGetImageDirectHTTPError', 'testPlaceholder',
        'testRenderString_Scale', 'testRenderString_ScaleForMultipleMaps', 'testClearMapProvidersPrivateKeys'),
}


def report_cases(source, target):
    if target not in MODULES:
        raise ValueError('unsupported native case target')
    source = Path(source).absolute()
    directory = source / MODULES[target] / 'target/surefire-reports'
    paths = sorted(directory.glob('TEST-*.xml'))
    if not paths:
        raise ValueError('selected module has no native Surefire reports')
    reports, cases, names = [], [], set()
    for path in paths:
        relative = path.relative_to(source).as_posix()
        path = http_fixtures._checked_file(source, relative)
        data = path.read_bytes()
        if len(data) > 64 * 1024 * 1024:
            raise ValueError('native report exceeds bounded parser size')
        suite, _validated_counts = parse_report(data, relative)
        name = suite.get('name')
        if suite.tag != 'testsuite' or not name or not name.startswith(PREFIXES[target]):
            raise ValueError('unexpected selected native report suite')
        if path.name != 'TEST-' + name + '.xml' or name in names:
            raise ValueError('native suite identity does not match unique report path')
        names.add(name)
        declared = {}
        for key in ('tests', 'failures', 'errors', 'skipped'):
            value = suite.get(key)
            if value is None or not re.fullmatch(r'[0-9]+', value):
                raise ValueError('native report count is missing or malformed')
            declared[key] = int(value)
        observed = Counter()
        suite_cases = []
        for index, case in enumerate(suite.findall('testcase')):
            classname, method = case.get('classname'), case.get('name')
            if not classname or method is None:
                raise ValueError('native testcase identity is missing')
            if any(child.tag not in ('failure', 'error', 'skipped', 'system-out', 'system-err') for child in case):
                raise ValueError('unsupported native testcase outcome, including retries/flakes')
            markers = [child for child in case if child.tag in ('failure', 'error', 'skipped')]
            if len(markers) > 1:
                raise ValueError('native testcase has contradictory outcomes')
            outcome = markers[0].tag if markers else 'passed'
            if not method and outcome != 'error':
                raise ValueError('empty testcase name is only valid for class-rule errors')
            observed[outcome] += 1
            row = {'classname': classname, 'name': method, 'outcome': outcome,
                   'report': relative, 'record_index': index}
            if markers:
                detail = markers[0]
                row['detail'] = {'type': detail.get('type'), 'message': detail.get('message'),
                                 'text_sha256': hashlib.sha256((detail.text or '').encode()).hexdigest()}
            suite_cases.append(row)
        actual = {'tests': len(suite_cases), 'failures': observed['failure'],
                  'errors': observed['error'], 'skipped': observed['skipped']}
        if actual != declared:
            raise ValueError('native suite counters disagree with testcase outcomes: ' + name)
        reports.append({'path': relative, 'sha256': hashlib.sha256(data).hexdigest(),
                        'name': name, **actual})
        cases.extend(suite_cases)
    counts = Counter((case['classname'], case['name']) for case in cases)
    totals = {key: sum(report[key] for report in reports) for key in ('tests', 'failures', 'errors', 'skipped')}
    totals['passed'] = totals['tests'] - totals['failures'] - totals['errors'] - totals['skipped']
    return {'source': str(source), 'reports': reports, 'cases': cases, 'totals': totals,
            'unique_identities': len(counts),
            'duplicate_records': [{'classname': key[0], 'name': key[1], 'records': count}
                                  for key, count in sorted(counts.items()) if count > 1]}


def _groups(evidence):
    groups = defaultdict(list)
    for case in evidence['cases']:
        groups[(case['classname'], case['name'])].append(case)
    return groups


def compare_cases(historical, current, target):
    """Return failed evidence rather than silently dropping missing/error cases."""
    if target not in MODULES:
        raise ValueError('unsupported native case target')
    before, after = _groups(historical), _groups(current)
    expected = ({(name, method) for name, methods in MAPFISH_FAILURES.items() for method in methods}
                if target == 'mapfish' else {(SCHEMA_CLASS, '')})
    failures = {key for key, rows in before.items() if any(row['outcome'] in ('failure', 'error') for row in rows)}
    problems = []
    if failures != expected:
        problems.append({'kind': 'historical-failure-identities-differ',
                         'missing': sorted(expected - failures), 'unexpected': sorted(failures - expected)})
    mappings = []
    for identity, rows in sorted(before.items()):
        required = ([(SCHEMA_CLASS, method) for method in SCHEMA_METHODS]
                    if target == 'xml' and identity == (SCHEMA_CLASS, '') else [identity])
        destinations = []
        old_outcomes = {row['outcome'] for row in rows}
        for key in required:
            found = after.get(key, [])
            outcomes = [case['outcome'] for case in found]
            destinations.append({'classname': key[0], 'name': key[1], 'records': found})
            if not found:
                problems.append({'kind': 'missing-case', 'identity': key})
            elif old_outcomes != {'skipped'} and outcomes != ['passed']:
                problems.append({'kind': 'expected-single-passing-case', 'identity': key, 'outcomes': outcomes})
        mappings.append({'classname': identity[0], 'name': identity[1], 'historical_records': rows,
                         'hidden_class_rule_methods': len(required) if identity[1] == '' else 0,
                         'current_cases': destinations})
    for key, rows in sorted(after.items()):
        outcomes = [row['outcome'] for row in rows]
        if any(outcome in ('failure', 'error') for outcome in outcomes):
            problems.append({'kind': 'current-failure-or-error', 'identity': key, 'outcomes': outcomes})
        if any(outcome == 'skipped' for outcome in outcomes) and not (
                key in before and all(row['outcome'] == 'skipped' for row in before[key])):
            problems.append({'kind': 'new-skip', 'identity': key})
        if len(rows) != 1:
            problems.append({'kind': 'duplicate-current-case', 'identity': key, 'records': len(rows)})
    return {'schema_version': 1, 'target': target, 'purpose': 'native-case-outcome-comparison',
            'acceptance_build': False, 'verified': not problems, 'problems': problems,
            'historical': historical, 'current': current, 'case_mappings': mappings,
            'historical_failed_unique_identities': len(failures),
            'historical_failed_records': sum(row['outcome'] in ('failure', 'error') for row in historical['cases'])}


def compare(historical_source, current_source, target):
    historical = report_cases(historical_source, target)
    current = report_cases(current_source, target)
    result = compare_cases(historical, current, target)
    if target == 'xml':
        fixture = http_fixtures._manifest()['targets']['xml']
        old = http_fixtures._checked_file(Path(historical_source), fixture['path'])
        new = http_fixtures._checked_file(Path(current_source), fixture['path'])
        if sha(old) != fixture['before_sha256'] or sha(new) != fixture['after_sha256']:
            raise ValueError('SchemaCache source changed; hidden test mapping cannot be verified')
        result['hidden_class_rule_source'] = {'path': fixture['path'], 'historical_sha256': sha(old),
                                            'current_sha256': sha(new), 'methods': SCHEMA_METHODS}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=MODULES, required=True)
    parser.add_argument('--historical-source', type=Path, required=True)
    parser.add_argument('--current-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; preserve earlier evidence')
    try:
        result = compare(args.historical_source, args.current_source, args.target)
    except Exception as error:
        result = {'schema_version': 1, 'target': args.target, 'verified': False,
                  'error': {'type': type(error).__name__, 'message': str(error)}}
    write_json(args.output, result)
    print(json.dumps({'verified': result['verified'], 'output': str(args.output)}, indent=2))
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
