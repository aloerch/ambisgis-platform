#!/usr/bin/env python3
"""Isolated, network-denied exploratory compilation/tests; never acceptance.

Each invocation reserves fresh source, repository and receipt directories. Inputs
are selected from verified custody; deployment and arbitrary Maven arguments are
not supported. Original source archives and earlier runs remain unchanged.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from resolution import prepare, command, execute, maven_inventory, sha, write_json
from resolution_inventory import verify_custody, read_file, walk_files
import toolchain

TARGETS = {
    'referencing': 'org.geotools:gt-referencing',
    'xml': 'org.geotools:gt-xml',
    'mapfish': 'org.mapfish.print:print-lib',
    'geofence': 'org.geoserver.geofence:geofence-persistence-pg-test',
    'importer': 'org.geoserver.importer:gs-importer-core',
    'oauth': 'org.geoserver.extension:gs-sec-oauth2-geonode',
}

TEST_PACKAGES = {'referencing': 'org/geotools/referencing/', 'xml': 'org/geotools/xml/',
                 'mapfish': 'org/mapfish/', 'geofence': 'org/geoserver/geofence/',
                 'importer': 'org/geoserver/importer/', 'oauth': 'org/geoserver/security/'}

TARGET_MODULES = {'referencing': 'geotools/modules/library/referencing/',
                  'xml': 'geotools/modules/library/xml/',
                  'mapfish': 'mapfish-print-v2-da1f37cfc0d7a235cb2c0ec5677010495d9f664b/',
                  'geofence': 'geofence-132a1d16901b7039f974c8c30d7e7df042d8af4c/src/services/core/persistence-pg-test/',
                  'importer': 'geoserver/src/extension/importer/core/',
                  'oauth': 'geoserver/src/extension/security/oauth2-geonode/'}


def materialize(custody, destination):
    inventory = verify_custody(custody)
    if not inventory['verification']['valid']:
        raise ValueError('retained Maven custody failed verification')
    records = {(r['repository'], r['maven_path']): r for r in inventory['artifacts']}
    errors = []
    selection_root = custody / 'selections'
    files = walk_files(selection_root, errors)
    if errors:
        raise ValueError('unsafe selection tree: ' + json.dumps(errors))
    destination.mkdir()
    rows = []
    for path in files:
        if path.suffix != '.json':
            raise ValueError('unexpected selection entry')
        selected = json.loads(read_file(path))
        record = records[(selected['repository'], selected['maven_path'])]
        if path.relative_to(selection_root).as_posix() != record['maven_path'] + '.json':
            raise ValueError('selection path does not match artifact identity')
        target = destination / record['maven_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output, (custody / record['blob_path']).open('rb') as source:
            shutil.copyfileobj(source, output)
        if sha(target) != record['sha256']:
            raise ValueError('retained input changed while copying')
        rows.append(record)
    return rows


def test_reports(root):
    reports, skipped_cases = [], []
    for path in sorted(root.rglob('TEST-*.xml')):
        if path.parent.name not in ('surefire-reports', 'failsafe-reports'):
            continue
        suite = ET.parse(path).getroot()
        reports.append({'path': path.relative_to(root).as_posix(), 'sha256': sha(path),
                        'name': suite.get('name'), **{key: int(suite.get(key, '0'))
                         for key in ('tests', 'failures', 'errors', 'skipped')}})
        for case in suite.findall('testcase'):
            skipped = case.find('skipped')
            if skipped is not None:
                skipped_cases.append({'suite': suite.get('name'), 'name': case.get('name'),
                                      'message': skipped.get('message', ''),
                                      'detail': (skipped.text or '').strip()})
    totals = {key: sum(r[key] for r in reports) for key in ('tests', 'failures', 'errors', 'skipped')}
    totals['passed'] = totals['tests'] - sum(totals[k] for k in ('failures', 'errors', 'skipped'))
    return {'suites': reports, 'skipped_cases': skipped_cases, **totals}


def verify_network_receipt(path, exit_code):
    network = json.loads(path.read_text())
    probes = {(p['family'], p['operation']): p for p in network['probes']}
    for family in ('AF_INET', 'AF_INET6'):
        observed = probes[(family, 'socket(SOCK_STREAM)')]
        if observed.get('errno') != 1 or observed.get('passed') is not True:
            raise ValueError('Internet socket denial not verified')
    if network.get('status') != 'completed' or network.get('command_exit_code') != exit_code:
        raise ValueError('network receipt did not match completed command')
    return {'path': str(path), 'sha256': sha(path), 'verified': True}


def validate_execution(report, output, target, tests):
    report['network_denial'] = verify_network_receipt(output / 'network-denial.json', report['exit_code'])
    report['network_denial_verified'] = True
    native = report['native_tests']
    if native['failures'] or native['errors']:
        raise ValueError('native failures must not be hidden by Maven exit zero')
    if tests != 'compile-only':
        prefix = TEST_PACKAGES[target].replace('/', '.')
        selected = [r for r in native['suites'] if r['name'].startswith(prefix)
                    and r['path'].startswith(TARGET_MODULES[target])]
        if sum(r['tests'] - r['skipped'] for r in selected) <= 0:
            raise ValueError('selected target reported no executed tests')
        report['target_executed_tests'] = sum(r['tests'] - r['skipped'] for r in selected)


def probe(audit_custody, custody, tool_custody, tools, output, target, stage, timeout=1200, tests='all', repair='none', postgres_prefix=None, postgres_evidence=None):
    if target not in TARGETS or stage not in ('test', 'package') or tests not in ('all', 'target', 'schema-resolver', 'compile-only'):
        raise ValueError('unsupported bounded target or lifecycle')
    if repair not in ('none', 'xmlcodegen-emf') or (tests == 'schema-resolver' and target != 'xml'):
        raise ValueError('unsupported bounded repair or schema test target')
    if (postgres_prefix is None) != (postgres_evidence is None) or (postgres_prefix and target != 'geofence'):
        raise ValueError('PostgreSQL fixture requires both paths and GeoFence target')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'runner_sha256': sha(Path(__file__)), 'started_at': datetime.now(timezone.utc).isoformat(),
              'target': target, 'stage': stage, 'test_selection': tests, 'purpose': 'exploratory-compatibility-probe',
              'acceptance_build': False, 'full_source_closure': False,
              'host_toolchain_closure': False, 'java_build_run': False,
              'exit_code': None, 'result_exit_code': 1, 'timeout_seconds': timeout}
    tooling = output / 'tooling'
    tooling.mkdir()
    for file in Path(__file__).resolve().parent.rglob('*'):
        if file.is_file() and file.suffix in ('.py', '.json', '.java', '.patch') and '__pycache__' not in file.parts:
            destination = tooling / 'java' / file.relative_to(Path(__file__).resolve().parent)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, destination)
    for name in ('offline_exec.py', 'validate_database.py', 'smoke.sql'):
        destination = tooling / 'postgis' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[1] / 'postgis' / name, destination)
    report['tooling_manifest'] = {p.relative_to(tooling).as_posix(): sha(p) for p in sorted(tooling.rglob('*')) if p.is_file()}
    write_json(output / 'started.json', report)
    start = time.monotonic()
    before = None
    database = None
    try:
        manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
        report['toolchain'] = toolchain.verify_extracted(tool_custody, manifest, tools)
        java = tools / next(a['root'] for a in manifest['archives']
                            if a['role'] == 'distribution' and a['path'].startswith('OpenJDK'))
        maven = tools / next(a['root'] for a in manifest['archives']
                             if a['role'] == 'distribution' and a['path'].startswith('apache-maven'))
        work = prepare(audit_custody, output / 'work')
        if repair != 'none':
            directory = Path(__file__).resolve().with_name('compatibility-patches')
            manifest = json.loads((directory / (repair + '.json')).read_text())
            patched = work / 'source' / manifest['path']
            if sha(patched) != manifest['before_sha256']:
                raise ValueError('patch input does not match exact owned source')
            applied = subprocess.run(['git', 'apply', '--verbose', str(directory / (repair + '.patch'))],
                                     cwd=work / 'source', capture_output=True, text=True)
            report['repair'] = {**manifest, 'exit_code': applied.returncode, 'output': applied.stdout + applied.stderr}
            if applied.returncode or sha(patched) != manifest['after_sha256']:
                raise ValueError('source patch output verification failed')
        if postgres_prefix is not None:
            import geofence_fixture
            database, report['postgres_fixture'] = geofence_fixture.start(
                postgres_prefix, postgres_evidence, output, work / 'source')
        before = maven_inventory(work / 'source')
        # Hash all original regular source files, not generated target outputs.
        originals = {p.relative_to(work / 'source').as_posix(): sha(p)
                     for p in sorted((work / 'source').rglob('*')) if p.is_file()}
        write_json(output / 'source-inputs.json', originals)
        report['source_manifest_sha256'] = sha(output / 'source-inputs.json')
        rows = materialize(custody, output / 'retained-repository')
        write_json(output / 'retained-inputs.json', rows)
        report['input_manifest_sha256'] = sha(output / 'retained-inputs.json')
        report['retained_files'] = len(rows)
        settings = output / 'settings.xml'
        settings.write_text('<settings><mirrors><mirror><id>ambisgis-custody</id>'
                            '<mirrorOf>*</mirrorOf><url>' + (output / 'retained-repository').as_uri() +
                            '</url></mirror></mirrors></settings>\n')
        local = output / 'fresh-m2'
        local.mkdir()
        cmd, env = command(work, java, maven, 'dependencies', local, settings, output.name)
        cmd = cmd[:cmd.index('-pl')] + ['-pl', TARGETS[target], '-am', stage,
            '-Dspotless.check.skip=true', '-Dmaven.test.failure.ignore=false',
            '-Dallow.test.failure.ignore=false']
        if tests == 'target':
            selector = '%regex[' + TEST_PACKAGES[target] + '.*Test.class],!%regex[.*OnlineTest.class],!%regex[.*StressTest.class]'
            cmd += ['-Dtest=' + selector, '-Dsurefire.failIfNoSpecifiedTests=false']
            report['test_selector'] = selector
        elif tests == 'schema-resolver':
            selector = 'org.geotools.xml.resolver.SchemaResolverTest,org.geotools.xml.SchemaFactoryResolveTest'
            cmd += ['-Dtest=' + selector, '-Dsurefire.failIfNoSpecifiedTests=false']
            report['test_selector'] = selector
        elif tests == 'compile-only':
            cmd += ['-DskipTests=true']
            report['test_execution_skipped'] = True
        if postgres_prefix is not None:
            cmd += ['-Dmaven.compiler.testRelease=17']
            report['fixture_test_release'] = 17
        offline = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
        guarded = [sys.executable, str(offline), '--evidence', str(output / 'network-denial.json'), '--', *cmd]
        report.update(command=guarded, environment=env, java_build_run=True)
        with (output / 'maven.log').open('x') as stream:
            report['exit_code'] = execute(guarded, work / 'source', env, stream, timeout)
        report['result_exit_code'] = report['exit_code']
        changed = [name for name, digest in originals.items()
                   if not (work / 'source' / name).is_file() or sha(work / 'source' / name) != digest]
        report['changed_original_source_files'] = changed
        if changed:
            report['result_exit_code'] = 1
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        report['duration_seconds'] = round(time.monotonic() - start, 3)
        source = output / 'work/source'
        try:
            after = maven_inventory(source)
            report['source_maven_files_unchanged'] = all(after.get(k) == v for k, v in before.items()) if before is not None else None
            report['generated_maven_files'] = {k: v for k, v in after.items() if before is not None and k not in before}
            if any('target' not in Path(k).parts or '.mvn' in Path(k).parts for k in report['generated_maven_files']):
                raise ValueError('unexpected new Maven configuration outside generated targets')
            if before is not None and report['source_maven_files_unchanged'] is not True:
                raise ValueError('Maven source/configuration changed during execution')
            log = output / 'maven.log'
            report['log_sha256'] = sha(log) if log.exists() else None
            report['native_tests'] = test_reports(source) if source.exists() else None
            report['built_jars'] = [{'path': p.relative_to(source).as_posix(), 'sha256': sha(p), 'size': p.stat().st_size}
                                    for p in sorted(source.rglob('*.jar')) if p.parent.name == 'target']
            if report['result_exit_code'] == 0:
                validate_execution(report, output, target, tests)
        except BaseException as error:
            report['finalization_error'] = {'type': type(error).__name__, 'message': str(error)}
            report['result_exit_code'] = 1
        if database is not None:
            try:
                database.stop()
                report['postgres_cluster_stopped'] = True
            except BaseException as error:
                report['shutdown_error'] = {'type': type(error).__name__, 'message': str(error)}
                report['result_exit_code'] = 1
        report['status'] = 'succeeded' if report['result_exit_code'] == 0 else 'failed'
        write_json(output / 'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('audit-custody', 'custody', 'toolchain-custody', 'tools', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--stage', choices=('test', 'package'), default='test')
    parser.add_argument('--postgres-prefix', type=Path)
    parser.add_argument('--postgres-evidence', type=Path)
    parser.add_argument('--repair', choices=('none', 'xmlcodegen-emf'), default='none')
    parser.add_argument('--tests', choices=('all', 'target', 'schema-resolver', 'compile-only'), default='all')
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    result = probe(args.audit_custody.resolve(), args.custody.resolve(), args.toolchain_custody.resolve(),
                   args.tools.resolve(), args.output.absolute(), args.target, args.stage, args.timeout, args.tests, args.repair, args.postgres_prefix, args.postgres_evidence)
    print(json.dumps(result, indent=2))
    return result['result_exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
