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
import zipfile
from native_reports import parse_report

from resolution import prepare, command, execute, maven_inventory, sha, write_json
from resolution_inventory import verify_custody, read_file, walk_files, checked_path
import toolchain

TARGETS = {
    'referencing': 'org.geotools:gt-referencing',
    'xml': 'org.geotools:gt-xml',
    'mapfish': 'org.mapfish.print:print-lib',
    'geofence': 'org.geoserver.geofence:geofence-persistence-pg-test',
    'importer': 'org.geoserver.importer:gs-importer-core',
    'oauth': 'org.geoserver.community:gs-sec-oauth2-geonode',
    'role-service': 'org.geoserver.extension:gs-authkey',
    'webapp': 'org.geoserver.web:gs-web-app',
}

TEST_PACKAGES = {'referencing': 'org/geotools/referencing/', 'xml': 'org/geotools/xml/',
                 'mapfish': 'org/mapfish/', 'geofence': 'org/geoserver/geofence/',
                 'importer': 'org/geoserver/importer/', 'oauth': 'org/geoserver/security/', 'webapp': 'org/geoserver/web/', 'role-service': 'org/geoserver/security/'}

TARGET_MODULES = {'referencing': 'geotools/modules/library/referencing/',
                  'xml': 'geotools/modules/library/xml/',
                  'mapfish': 'mapfish-print-v2-da1f37cfc0d7a235cb2c0ec5677010495d9f664b/',
                  'geofence': 'geofence-132a1d16901b7039f974c8c30d7e7df042d8af4c/src/services/core/persistence-pg-test/',
                  'importer': 'geoserver/src/extension/importer/core/',
                  'oauth': 'geoserver/src/community/security/oauth2-geonode/',
                  'webapp': 'geoserver/src/web/app/',
                  'role-service': 'geoserver/src/extension/authkey/'}


def materialize(custody, destination, no_oracle=False):
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
        if no_oracle:
            from no_oracle import excluded_input
            if excluded_input(record['maven_path']):
                continue
        target = destination / record['maven_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output, (custody / record['blob_path']).open('rb') as source:
            shutil.copyfileobj(source, output)
        if sha(target) != record['sha256']:
            raise ValueError('retained input changed while copying')
        rows.append(record)
    return rows




TEST_AGENT_PATH = 'net/bytebuddy/byte-buddy-agent/1.15.11/byte-buddy-agent-1.15.11.jar'
TEST_AGENT_SHA256 = '316d2c0795c2a4d4c4756f2e6f9349837c7430ac34e0477ead874d05f5cc19e5'


def startup_test_agent(retained, rows):
    """Use the original Mockito instrumentation at startup; forbid dynamic attach."""
    selected = [r for r in rows if r['maven_path'] == TEST_AGENT_PATH]
    if len(selected) != 1 or selected[0]['sha256'] != TEST_AGENT_SHA256:
        raise ValueError('expected retained Mockito instrumentation agent is missing')
    path = retained / TEST_AGENT_PATH
    checked_path(path)
    if sha(path) != TEST_AGENT_SHA256:
        raise ValueError('retained Mockito instrumentation agent changed')
    with zipfile.ZipFile(path) as archive:
        manifest = archive.read('META-INF/MANIFEST.MF').decode('utf-8')
    if 'Premain-Class: net.bytebuddy.agent.Installer' not in manifest:
        raise ValueError('retained instrumentation agent has no expected startup entry')
    return {'path': TEST_AGENT_PATH, 'sha256': TEST_AGENT_SHA256,
            'java_option': '-javaagent:' + str(path),
            'purpose': 'original inline Mockito instrumentation without Unix-socket self-attachment',
            'native_assertions_changed': False}


def prime_runtime_repository(rows, retained, local, output):
    """Stage verified retained providers before Maven -o; never fetch or replace."""
    staged = []
    for row in rows:
        relative = Path(row['maven_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unsafe retained runtime artifact path')
        source, destination = retained / relative, local / relative
        checked_path(source)
        if source.is_symlink() or sha(source) != row['sha256']:
            raise ValueError('retained runtime input changed before staging')
        if source.name.endswith(('.sha1', '.sha256', '.sha512', '.md5', '.asc')):
            # Maven normalizes cached checksum text. Publisher sidecars remain
            # retained evidence and are not runtime resolution artifacts.
            continue
        copied = not destination.exists()
        if copied:
            current = local
            checked_path(current, directory=True)
            for part in relative.parts[:-1]:
                current = current / part
                if current.is_symlink():
                    raise ValueError('runtime repository parent is a symlink')
                if not current.exists():
                    current.mkdir()
                checked_path(current, directory=True)
            with destination.open('xb') as stream, source.open('rb') as incoming:
                shutil.copyfileobj(incoming, stream)
        checked_path(destination)
        if destination.is_symlink() or sha(destination) != row['sha256']:
            raise ValueError('runtime repository conflicts with retained artifact: ' + row['maven_path'])
        # Enhanced Local Repository Manager tracks availability per repository.
        # Record the actual controlled file-mirror origin for these copied bytes.
        origins = destination.parent / '_remote.repositories'
        if origins.is_symlink():
            raise ValueError('runtime repository origin file is a symlink')
        line = destination.name + '>ambisgis-custody='
        previous = origins.read_text() if origins.exists() else ''
        if line not in previous.splitlines():
            with origins.open('a') as stream:
                if previous and not previous.endswith('\n'): stream.write('\n')
                stream.write(line + '\n')
        staged.append({'maven_path': row['maven_path'], 'sha256': row['sha256'], 'copied': copied})
    write_json(output / 'runtime-staged-inputs.json', staged)
    return {'files': len(staged), 'copied': sum(row['copied'] for row in staged),
            'manifest_sha256': sha(output / 'runtime-staged-inputs.json'), 'network_acquisition': False}


def test_reports(root):
    reports, skipped_cases = [], []
    for path in sorted(root.rglob('TEST-*.xml')):
        if path.parent.name not in ('surefire-reports', 'failsafe-reports'):
            continue
        suite, counts = parse_report(path.read_bytes(), str(path))
        reports.append({'path': path.relative_to(root).as_posix(), 'sha256': sha(path),
                        'name': suite.get('name'), **counts})
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


def verify_execution_network(report, output):
    if report.get('runtime_network') == 'controlled-loopback':
        import loopback_exec
        expected = report['tooling_manifest']['java/loopback_exec.py']
        if sha(Path(loopback_exec.__file__)) != expected:
            raise ValueError('loopback verifier differs from retained executed tooling')
        report['runtime_network_verified'] = loopback_exec.verify_receipt(output / 'network-loopback.json', report['exit_code'])
        if report['runtime_network_verified'].get('runner_sha256') != expected:
            raise ValueError('loopback receipt runner differs from retained tooling')
        if report.get('build_exit_code') != 0 or not report.get('build_network_denial_verified'):
            raise ValueError('runtime success requires the preceding network-denied build')
    else:
        report['network_denial'] = verify_network_receipt(output / 'network-denial.json', report['exit_code'])
        report['network_denial_verified'] = True


def validate_execution(report, output, target, tests):
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
        if target == 'role-service':
            inherited = [row for row in selected
                         if row['name'] == 'org.geoserver.security.GeoServerRestRoleServiceTest']
            if len(inherited) != 1 or inherited[0]['tests'] != 2 or inherited[0]['skipped']:
                raise ValueError('selected inherited role-service cases missing, repeated or skipped')
        for key in ('configured_auth_diagnostics', 'configured_auth_stateless', 'role_service_repair'):
            fixture = report.get(key, {})
            expected = fixture.get('native_test_count', 0)
            if not expected:
                continue
            injected_suites = []
            for source in fixture['injected_sources']:
                module, java_class = source['path'].split('/src/test/java/')
                if not java_class.endswith('.java'):
                    raise ValueError('configured native fixture is not a Java test source')
                name = java_class[:-5].replace('/', '.')
                matches = [row for row in native['suites'] if row['name'] == name
                           and row['path'].startswith(module + '/target/')]
                if len(matches) != 1 or matches[0]['skipped']:
                    raise ValueError('configured native regression suite missing, repeated or skipped')
                injected_suites.extend(matches)
            count = sum(row['tests'] for row in injected_suites)
            if count != expected:
                raise ValueError('configured native regression case count does not match its retained manifest')
            fixture['native_executed_tests'] = count


def prepare_webapp_oauth(source, principal=False):
    """Apply only the reviewed main-source rows; packaging never injects tests."""
    import oauth_fixture
    source = Path(source)
    for name, digest in oauth_fixture.SOURCES.items():
        if sha(source / name) != digest:
            raise ValueError('aggregate OAuth repair requires exact inspected owned sources')
    diagnostic = oauth_fixture.repair_rows('oauth-redaction.json')
    principal_rows = oauth_fixture.repair_rows('oauth-principal.json') if principal else []
    inspected = set(oauth_fixture.SOURCES)
    if (len(diagnostic) != len(inspected)
            or {row['path'] for row in diagnostic} != inspected):
        raise ValueError('aggregate diagnostic repair must contain exactly the inspected main sources')
    principal_source = oauth_fixture.MODULE + '/src/main/java/org/geoserver/security/oauth2/services/GeoNodeTokenServices.java'
    principal_test = oauth_fixture.MODULE + '/src/test/java/org/geoserver/security/oauth2/OAuth2RestTemplateTest.java'
    if principal and (len(principal_rows) != 2
                      or {row['path'] for row in principal_rows} != {principal_source, principal_test}):
        raise ValueError('aggregate principal repair has unexpected source/test scope')
    selected_principal = [row for row in principal_rows if row['path'] in inspected]
    test_inventory = {p.relative_to(source).as_posix(): sha(p)
                      for p in sorted(source.glob('geoserver/src/community/security/**/src/test/**/*'))
                      if p.is_file()}
    repairs = []
    for manifest, rows in [('oauth-redaction.json', diagnostic),
                           ('oauth-principal.json', selected_principal)]:
        if rows:
            repairs.append({'manifest': manifest, 'manifest_sha256': sha(Path(oauth_fixture.__file__).with_name(manifest)),
                            'application_order': len(repairs) + 1,
                            'sources': oauth_fixture.apply_repairs(source, rows)})
    after = {p.relative_to(source).as_posix(): sha(p)
             for p in sorted(source.glob('geoserver/src/community/security/**/src/test/**/*'))
             if p.is_file()}
    if after != test_inventory:
        raise ValueError('aggregate OAuth packaging must not change test sources')
    return {'purpose': 'guarded-main-source-only-aggregate-oauth-repair',
            'repairs': repairs, 'source_outputs': {name: sha(source / name) for name in sorted(inspected)},
            'test_sources_unchanged': True, 'test_source_files': len(test_inventory),
            'injected_sources': [], 'authentication_decision_changed': principal,
            'human_security_review_required': True, 'acceptance_build': False}


def probe(audit_custody, custody, tool_custody, tools, output, target, stage, timeout=1200, tests='all', repair='none', postgres_prefix=None, postgres_evidence=None, gdal_prefix=None, gdal_archive=None, runtime_http=False, oauth_redaction=False, oauth_principal=False, configured_auth_diagnostics=False, configured_auth_diagnostic_tests=False, configured_auth_stateless=False, configured_auth_stateless_tests=False, role_service=False, role_service_repair=False, role_service_tests=False, no_oracle=False, variant_inputs=None):
    if target not in TARGETS or stage not in ('test', 'package') or tests not in ('all', 'target', 'schema-resolver', 'compile-only'):
        raise ValueError('unsupported bounded target or lifecycle')
    if repair not in ('none', 'xmlcodegen-emf') or (tests == 'schema-resolver' and target != 'xml'):
        raise ValueError('unsupported bounded repair or schema test target')
    if (postgres_prefix is None) != (postgres_evidence is None) or (postgres_prefix and target != 'geofence'):
        raise ValueError('PostgreSQL fixture requires both paths and GeoFence target')
    if (gdal_prefix is None) != (gdal_archive is None) or (gdal_prefix and target != 'importer'):
        raise ValueError('GDAL fixture requires both paths and importer target')
    if oauth_principal and not oauth_redaction:
        raise ValueError('OAuth principal repair requires the diagnostic repair')
    aggregate_oauth = target == 'webapp' and stage == 'package' and tests == 'compile-only' and not runtime_http
    if oauth_redaction and not ((target == 'oauth' and runtime_http) or aggregate_oauth):
        raise ValueError('OAuth repair requires its controlled HTTP probe or network-denied aggregate packaging')
    if configured_auth_diagnostics or configured_auth_diagnostic_tests:
        if not (oauth_redaction and oauth_principal):
            raise ValueError('configured diagnostic checks require the existing OAuth diagnostic/principal repairs')
        native_oauth = target == 'oauth' and runtime_http and tests in ('all', 'target')
        if not (native_oauth or (aggregate_oauth and configured_auth_diagnostics and not configured_auth_diagnostic_tests)):
            raise ValueError('configured diagnostics require tested OAuth HTTP mode or source-only aggregate packaging')
    if configured_auth_stateless or configured_auth_stateless_tests:
        if not (configured_auth_diagnostics and oauth_redaction and oauth_principal):
            raise ValueError('stateless bearer checks require configured diagnostics and the existing OAuth repairs')
        native_oauth = target == 'oauth' and runtime_http and tests in ('all', 'target')
        if not (native_oauth or (aggregate_oauth and configured_auth_stateless and not configured_auth_stateless_tests)):
            raise ValueError('stateless bearer checks require tested OAuth HTTP mode or source-only aggregate packaging')
    if runtime_http and (target not in ('xml', 'mapfish', 'oauth', 'role-service') or tests == 'compile-only' or timeout < 30):
        raise ValueError('controlled HTTP runtime requires a tested XML/MapFish/OAuth/role-service target and timeout >=30')
    role_service = role_service or target == 'role-service'
    if role_service and target not in ('role-service', 'webapp'):
        raise ValueError('role service profile requires its native target or aggregate packaging')
    if role_service and target == 'webapp' and not (
            aggregate_oauth and repair == 'xmlcodegen-emf' and oauth_redaction
            and oauth_principal and configured_auth_diagnostics and configured_auth_stateless):
        raise ValueError('role-service aggregate must preserve all reviewed build and OAuth repairs')
    if role_service_repair or role_service_tests:
        native_role = target == 'role-service' and runtime_http and tests == 'target'
        if not role_service or not (native_role or (aggregate_oauth and role_service_repair and not role_service_tests)):
            raise ValueError('role service repairs require its selected native HTTP tests or source-only aggregate packaging')
    if variant_inputs is not None and not no_oracle:
        raise ValueError('coordinated Java variant requires explicit NO-ORACLE selection')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 1, 'runner_sha256': sha(Path(__file__)), 'started_at': datetime.now(timezone.utc).isoformat(),
              'target': target, 'stage': stage, 'test_selection': tests, 'role_service_profile': role_service, 'purpose': 'exploratory-compatibility-probe',
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
        work = prepare(audit_custody, output / 'work', role_service=True) if role_service else prepare(audit_custody, output / 'work')
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
        if target == 'webapp':
            import combined_logging_patch
            report['aggregate_lifecycle_repair'] = combined_logging_patch.prepare(work / 'source')
            if oauth_redaction:
                report['aggregate_oauth_repair'] = prepare_webapp_oauth(work / 'source', principal=oauth_principal)
        if runtime_http:
            if target in ('xml', 'mapfish'):
                import http_fixtures
                report['http_fixture'] = http_fixtures.prepare(work / 'source', output, target)
            elif target == 'oauth':
                import oauth_fixture
                report['oauth_fixture'] = oauth_fixture.prepare(work / 'source', redact=oauth_redaction, principal=oauth_principal)
            report['runtime_network'] = 'controlled-loopback'
        if configured_auth_diagnostics or configured_auth_diagnostic_tests:
            import configured_auth_repairs
            report['configured_auth_diagnostics'] = configured_auth_repairs.prepare(
                work / 'source', repair=configured_auth_diagnostics, tests=configured_auth_diagnostic_tests)
        if configured_auth_stateless or configured_auth_stateless_tests:
            import configured_auth_stateless as stateless_repairs
            report['configured_auth_stateless'] = stateless_repairs.prepare(
                work / 'source', repair=configured_auth_stateless, tests=configured_auth_stateless_tests)
        if role_service_repair or role_service_tests:
            import role_service_repair as role_repairs
            report['role_service_repair'] = role_repairs.prepare(
                work / 'source', repair=role_service_repair, tests=role_service_tests)
        if no_oracle:
            import no_oracle as no_oracle_profile
            report['no_oracle_profile'] = no_oracle_profile.prepare(work / 'source')
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
        rows = materialize(custody, output / 'retained-repository', no_oracle=True) if no_oracle else materialize(custody, output / 'retained-repository')
        if variant_inputs is not None:
            import variant_inputs as local_variants
            rows, report['local_variant_inputs'] = local_variants.apply(output / 'retained-repository', rows, variant_inputs)
            shutil.copyfile(variant_inputs, output / 'variant-inputs.json')
        write_json(output / 'retained-inputs.json', rows)
        report['input_manifest_sha256'] = sha(output / 'retained-inputs.json')
        report['retained_files'] = len(rows)
        settings = output / 'settings.xml'
        settings.write_text('<settings><mirrors><mirror><id>ambisgis-custody</id>'
                            '<mirrorOf>*</mirrorOf><url>' + (output / 'retained-repository').as_uri() +
                            '</url></mirror></mirrors></settings>\n')
        local = output / 'fresh-m2'
        local.mkdir()
        cmd, env = command(work, java, maven, 'dependencies', local, settings, output.name, role_service=role_service)
        if gdal_prefix is not None:
            import gdal_fixture
            report['gdal_fixture'] = gdal_fixture.prepare(gdal_prefix, gdal_archive, output)
            env.update(report['gdal_fixture']['environment'])
            env['PATH'] = str(output / 'native-bin') + ':' + env['PATH']
        cmd = cmd[:cmd.index('-pl')] + ['-pl', TARGETS[target], '-am', stage,
            '-Dspotless.check.skip=true', '-Dmaven.test.failure.ignore=false',
            '-Dallow.test.failure.ignore=false']
        if tests == 'target':
            selector = '%regex[' + TEST_PACKAGES[target] + '.*Test.class],!%regex[.*OnlineTest.class],!%regex[.*StressTest.class]'
            if target == 'role-service':
                selector = 'org.geoserver.security.GeoServerRestRoleServiceTest,org.geoserver.security.AmbisGISRestRoleServiceTest'
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
        offline = tooling / 'postgis/offline_exec.py'
        if runtime_http:
            # First compile/package every prerequisite with all Internet sockets
            # denied. Runtime then uses the same retained inputs and Maven -o.
            build_cmd = [sys.executable, str(offline), '--evidence', str(output / 'network-denial-build.json'),
                         '--', *cmd, '-DskipTests=true']
            report.update(build_command=build_cmd, build_environment=dict(env), java_build_run=True)
            with (output / 'build.log').open('x') as stream:
                report['build_exit_code'] = execute(build_cmd, work / 'source', env, stream, timeout)
            report['build_log_sha256'] = sha(output / 'build.log')
            report['build_network_denial'] = verify_network_receipt(output / 'network-denial-build.json', report['build_exit_code'])
            report['build_network_denial_verified'] = True
            if report['build_exit_code']:
                raise ValueError('network-denied compilation failed; HTTP runtime was not started')
            report['runtime_repository_staging'] = prime_runtime_repository(rows, output / 'retained-repository', local, output)
            report['startup_test_agent'] = startup_test_agent(output / 'retained-repository', rows)
            properties = [report['startup_test_agent']['java_option'], *report.get('http_fixture', {}).get('java_properties', [])]
            if properties:
                if any(any(c.isspace() or c in '\"\'' for c in value) for value in properties):
                    raise ValueError('HTTP fixture JVM property paths must not contain whitespace or quotes')
                env['JAVA_TOOL_OPTIONS'] = ' '.join(properties)
            loopback = tooling / 'java/loopback_exec.py'
            guarded = [sys.executable, str(loopback), '--evidence', str(output / 'network-loopback.json'),
                       '--timeout', str(timeout - 15), '--', *cmd, '--offline']
        else:
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
        report['result_exit_code'] = 1
    finally:
        report['duration_seconds'] = round(time.monotonic() - start, 3)
        source = output / 'work/source'
        try:
            for relative, digest in report['tooling_manifest'].items():
                if sha(tooling / relative) != digest:
                    raise ValueError('retained executed tooling changed: ' + relative)
            report['retained_tooling_unchanged'] = True
            after = maven_inventory(source)
            report['source_maven_files_unchanged'] = all(after.get(k) == v for k, v in before.items()) if before is not None else None
            report['generated_maven_files'] = {k: v for k, v in after.items() if before is not None and k not in before}
            if any('target' not in Path(k).parts or '.mvn' in Path(k).parts for k in report['generated_maven_files']):
                raise ValueError('unexpected new Maven configuration outside generated targets')
            if before is not None and report['source_maven_files_unchanged'] is not True:
                raise ValueError('Maven source/configuration changed during execution')
            log = output / 'maven.log'
            report['log_sha256'] = sha(log) if log.exists() else None
            if report['exit_code'] is not None:
                verify_execution_network(report, output)
            report['native_tests'] = test_reports(source) if source.exists() else None
            report['built_jars'] = [{'path': p.relative_to(source).as_posix(), 'sha256': sha(p), 'size': p.stat().st_size}
                                    for p in sorted(source.rglob('*.jar')) if p.parent.name == 'target']
            if runtime_http and target in ('xml', 'mapfish') and report.get('exit_code') is not None:
                report['http_fixture_finalization'] = http_fixtures.finalize(output, target)
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
    parser.add_argument('--gdal-prefix', type=Path)
    parser.add_argument('--gdal-archive', type=Path)
    parser.add_argument('--postgres-prefix', type=Path)
    parser.add_argument('--postgres-evidence', type=Path)
    parser.add_argument('--repair', choices=('none', 'xmlcodegen-emf'), default='none')
    parser.add_argument('--tests', choices=('all', 'target', 'schema-resolver', 'compile-only'), default='all')
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--oauth-redaction', action='store_true', help='apply the guarded OAuth diagnostic-only repair')
    parser.add_argument('--oauth-principal', action='store_true', help='apply guarded nonblank principal validation; requires diagnostic repair and security review')
    parser.add_argument('--configured-auth-diagnostics', action='store_true', help='apply guarded cache/filter diagnostic repairs after the existing OAuth repairs')
    parser.add_argument('--configured-auth-diagnostic-tests', action='store_true', help='inject native configured diagnostic regressions in controlled OAuth HTTP mode only')
    parser.add_argument('--configured-auth-stateless', action='store_true', help='apply guarded opt-in stateless bearer source support after configured diagnostic repairs')
    parser.add_argument('--configured-auth-stateless-tests', action='store_true', help='inject native stateless bearer regressions in controlled OAuth HTTP mode only')
    parser.add_argument('--no-oracle', action='store_true', help='explicit source/dependency profile; Oracle remains unsupported')
    parser.add_argument('--variant-inputs', type=Path, help='hash-locked locally source-built replacements; requires --no-oracle')
    parser.add_argument('--role-service', action='store_true', help='add the owned authkey module while preserving existing aggregate profiles')
    parser.add_argument('--role-service-repair', action='store_true', help='apply guarded GeoNode REST role-service repairs')
    parser.add_argument('--role-service-tests', action='store_true', help='inject selected role-service regressions in controlled HTTP mode only')
    parser.add_argument('--runtime-http', action='store_true', help='compile with sockets denied, then run real tests under verified loopback control')
    args = parser.parse_args()
    result = probe(args.audit_custody.resolve(), args.custody.resolve(), args.toolchain_custody.resolve(),
                   args.tools.resolve(), args.output.absolute(), args.target, args.stage, args.timeout, args.tests, args.repair, args.postgres_prefix, args.postgres_evidence, args.gdal_prefix, args.gdal_archive, args.runtime_http, args.oauth_redaction, args.oauth_principal, args.configured_auth_diagnostics, args.configured_auth_diagnostic_tests, args.configured_auth_stateless, args.configured_auth_stateless_tests, args.role_service, args.role_service_repair, args.role_service_tests, args.no_oracle, args.variant_inputs)
    print(json.dumps(result, indent=2))
    return result['result_exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
