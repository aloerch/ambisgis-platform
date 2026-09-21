#!/usr/bin/env python3
"""Bind repaired aggregate sources, packaged entries and selected class origins."""
import argparse
from collections import defaultdict
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath
import zipfile

from combined_logging_probe import packaged_classpath
from resolution import PROFILES, sha, write_json

PATCHED_CLASSES = {
    'org/geoserver/security/oauth2/services/GeoNodeTokenServices.class': {
        'jar': 'gs-sec-oauth2-geonode-2.28.5.jar',
        'module': 'geoserver/src/community/security/oauth2-geonode',
        'present': ['Received GeoNode token validation response', 'Converted GeoNode token validation response',
                    'Token validation response has no valid principal', 'isBlank'],
        'absent': ['Original map = ', 'Transformed = ']},
    'org/geoserver/security/oauth2/GeoServerOAuthRemoteTokenServices.class': {
        'jar': 'gs-sec-oauth2-core-2.28.5.jar',
        'module': 'geoserver/src/community/security/oauth2/oauth2-core',
        'present': ['Token validation denied', 'Token validation endpoint returned an error'],
        'absent': ['check_token returned error: ']},
}
CONFIGURED_CLASSES = {
    'org/geoserver/security/auth/GuavaAuthenticationCacheImpl.class': {
        'jar': 'gs-main-2.28.5.jar', 'module': 'geoserver/src/main',
        'present': ['AuthenticationCache has no entry for ', 'AuthenticationCache adding new entry for '],
        'absent': ['AuthenticationCache has no entry for \x01, \x01',
                   'AuthenticationCache adding new entry for \x01, \x01']},
    'org/geoserver/security/oauth2/GeoServerOAuthAuthenticationFilter.class': {
        'jar': 'gs-sec-oauth2-core-2.28.5.jar',
        'module': 'geoserver/src/community/security/oauth2/oauth2-core',
        'present': ['Attempting OAuth principal authentication', 'OAuth token validation endpoint rejected credentials',
                    'OAuth provider denied authentication', 'OAuth provider could not be reached'],
        'absent': ['Authenticated OAuth request for principal {0}',
                   'Could not Authorize OAuth2 Resource due to the following exception:',
                   'Error while trying to authenticate to OAuth2 Provider with the following Exception cause:']},
}
STATELESS_CLASSES = {
    'org/geoserver/security/oauth2/GeoServerOAuthAuthenticationFilter$StatelessBearerSecurityContext.class': {
        'jar': 'gs-sec-oauth2-core-2.28.5.jar',
        'module': 'geoserver/src/community/security/oauth2/oauth2-core',
        'present': ['Lorg/springframework/security/core/Transient;',
                    'org/springframework/security/core/context/SecurityContextImpl'],
        'absent': []},
    'org/geoserver/security/oauth2/GeoServerOAuth2FilterConfig.class': {
        'jar': 'gs-sec-oauth2-core-2.28.5.jar',
        'module': 'geoserver/src/community/security/oauth2/oauth2-core',
        'present': ['statelessBearerAuthentication', 'isStatelessBearerAuthentication', 'setStatelessBearerAuthentication'],
        'absent': []},
}
REQUIRED = {'gs-importer-core-2.28.5.jar', 'gs-importer-rest-2.28.5.jar',
            'gs-geofence-server-2.28.5.jar', 'geofence-persistence-3.8.3.jar',
            'gt-jdbc-postgis-34.5.jar', 'gs-printing-2.28.5.jar', 'print-lib-2.4.1.jar',
            'gs-sec-oauth2-geonode-2.28.5.jar', 'gs-sec-oauth2-core-2.28.5.jar'}


def entries(archive):
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError('duplicate archive entry')
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name:
            raise ValueError('unsafe aggregate archive entry')
        if not name.endswith('/'):
            data = archive.read(name)
            yield name, data


def check_repaired_class(data, spec):
    for marker in spec['present']:
        if marker.encode() not in data:
            raise ValueError('expected OAuth repair bytecode marker missing')
    for marker in spec['absent']:
        if marker.encode() in data:
            raise ValueError('inherited OAuth sensitive diagnostic remains in packaged bytecode')


def retained_repair_manifest(build, result, name):
    """Read the exact recipe executed by this build, even after later fixture edits."""
    if '/' in name or '\\' in name or name not in (
            'oauth-redaction.json', 'oauth-principal.json', 'configured-auth-repairs.json',
            'configured-auth-stateless.json'):
        raise ValueError('unknown retained repair manifest')
    path = build / 'tooling/java' / name
    expected = result['tooling_manifest'].get('java/' + name)
    if not expected or path.is_symlink() or sha(path) != expected:
        raise ValueError('retained executed repair manifest changed')
    return path


def inspect(build, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {'purpose': 'repaired-aggregate-source-and-packaged-class-identities',
              'result_exit_code': 1, 'runtime_executed': False, 'full_source_closure': False,
              'runner_sha256': sha(Path(__file__))}
    try:
        tooling = output / 'tooling'
        tooling.mkdir()
        tool_names = ('aggregate_evidence.py', 'combined_logging_probe.py', 'compatibility.py',
                      'resolution.py', 'resolution_inventory.py', 'native_reports.py', 'toolchain.py',
                      'oauth-redaction.json', 'oauth-principal.json', 'configured-auth-repairs.json',
                      'configured-auth-stateless.json')
        report['tooling_manifest'] = {}
        for name in tool_names:
            shutil.copyfile(Path(__file__).with_name(name), tooling / name)
            report['tooling_manifest'][name] = sha(tooling / name)
        if report['tooling_manifest']['aggregate_evidence.py'] != report['runner_sha256']:
            raise ValueError('aggregate evidence runner changed during snapshot')
        result = json.loads((build / 'result.json').read_text())
        source = build / 'work/source'
        preparation = json.loads((build / 'work/preparation.json').read_text())
        if preparation['profiles'] != PROFILES:
            raise ValueError('aggregate selected profiles differ from retained recipe')
        if '-P' + ','.join(PROFILES) not in result['command']:
            raise ValueError('aggregate command omitted selected profiles')
        report['profiles'] = PROFILES
        report['packaging_tests_skipped'] = result.get('test_execution_skipped') is True
        repaired = result['aggregate_oauth_repair']
        if (repaired.get('authentication_decision_changed') is not True
                or repaired.get('injected_sources') != []
                or repaired.get('test_sources_unchanged') is not True):
            raise ValueError('require principal-repaired, main-source-only aggregate')
        inventory = packaged_classpath(build, output)
        if not REQUIRED.issubset({row['name'] for row in inventory['libraries']}):
            raise ValueError('aggregate selected module missing')
        report['classpath'] = inventory
        manifests = ['oauth-redaction.json', 'oauth-principal.json']
        if [row['manifest'] for row in repaired['repairs']] != manifests:
            raise ValueError('unexpected aggregate OAuth repair order')
        source_manifest = build / 'source-inputs.json'
        if sha(source_manifest) != result['source_manifest_sha256']:
            raise ValueError('aggregate source input manifest changed')
        source_inputs = json.loads(source_manifest.read_text())
        expected_outputs = {}
        for index, row in enumerate(repaired['repairs']):
            manifest_path = retained_repair_manifest(build, result, row['manifest'])
            if sha(manifest_path) != row['manifest_sha256'] or row.get('application_order') != index + 1:
                raise ValueError('repair evidence differs from reviewed manifest')
            for repair in json.loads(manifest_path.read_text()):
                if '/src/main/java/' in repair['path']:
                    expected_outputs[repair['path']] = repair['after_sha256']
        if repaired['source_outputs'] != expected_outputs:
            raise ValueError('repaired source output identities differ from reviewed repairs')
        for name, digest in repaired['source_outputs'].items():
            if source_inputs.get(name) != digest or sha(source / name) != digest:
                raise ValueError('repaired aggregate source differs from recorded compiler input')
        report['oauth_repair'] = repaired
        configured = result.get('configured_auth_diagnostics')
        stateless = result.get('configured_auth_stateless')
        final_source_outputs = dict(expected_outputs)
        expected_classes = dict(PATCHED_CLASSES)
        report['configured_diagnostics_applied'] = configured is not None
        if configured is not None:
            configured_manifest = retained_repair_manifest(build, result, 'configured-auth-repairs.json')
            if (configured.get('manifest_sha256') != sha(configured_manifest)
                    or configured.get('injected_sources') != [] or configured.get('repair_applied') is not True
                    or configured.get('required_preceding_repairs') != manifests):
                raise ValueError('configured aggregate repair manifest changed or test sources injected')
            configured_rows = json.loads(configured_manifest.read_text())['sources']
            identities = lambda rows: [{key: row[key] for key in ('path', 'before_sha256', 'after_sha256')} for row in rows]
            if identities(configured.get('repairs', [])) != identities(configured_rows):
                raise ValueError('configured aggregate diagnostic repairs missing or reordered')
            final_source_outputs.update({row['path']: row['after_sha256'] for row in configured_rows})
            expected_classes.update(CONFIGURED_CLASSES)
            report['configured_auth_diagnostics'] = configured
        report['stateless_bearer_source_support_applied'] = stateless is not None
        if stateless is not None:
            stateless_manifest = retained_repair_manifest(build, result, 'configured-auth-stateless.json')
            if (configured is None or stateless.get('repair_applied') is not True
                    or stateless.get('manifest_sha256') != sha(stateless_manifest)
                    or stateless.get('injected_sources') != []
                    or stateless.get('required_preceding_repairs') != [*manifests, 'configured-auth-repairs.json']):
                raise ValueError('stateless aggregate repair manifest changed, preceding repairs missing or tests injected')
            stateless_rows = json.loads(stateless_manifest.read_text())['sources']
            if identities(stateless.get('repairs', [])) != identities(stateless_rows):
                raise ValueError('stateless aggregate source repairs missing or reordered')
            for row in stateless_rows:
                if row['path'] in final_source_outputs and final_source_outputs[row['path']] != row['before_sha256']:
                    raise ValueError('stateless aggregate source repair does not follow preceding repair output')
                final_source_outputs[row['path']] = row['after_sha256']
            expected_classes.update(STATELESS_CLASSES)
            filter_class = 'org/geoserver/security/oauth2/GeoServerOAuthAuthenticationFilter.class'
            expected_classes[filter_class] = {**expected_classes[filter_class],
                'present': [*expected_classes[filter_class]['present'], 'isStatelessBearerAuthentication']}
            report['configured_auth_stateless'] = stateless
        for name, digest in final_source_outputs.items():
            if source_inputs.get(name) != digest or sha(source / name) != digest:
                raise ValueError('final repaired source differs from recorded compiler input')
        report['final_repaired_source_outputs'] = final_source_outputs
        names = manifests + (['configured-auth-repairs.json'] if configured else []) + (['configured-auth-stateless.json'] if stateless else [])
        report['executed_repair_manifests'] = {name: {'path': str(retained_repair_manifest(build, result, name)),
            'sha256': result['tooling_manifest']['java/' + name]} for name in names}
        report['build_repairs'] = {'xmlcodegen': result['repair'], 'lifecycle': result['aggregate_lifecycle_repair']}
        report['repair_application_order'] = ['xmlcodegen-emf', 'aggregate-lifecycle', 'oauth-redaction', 'oauth-principal']
        if configured is not None:
            report['repair_application_order'].append('configured-auth-diagnostics')
        if stateless is not None:
            report['repair_application_order'].append('configured-auth-stateless')
        retained = json.loads((build / 'retained-inputs.json').read_text())
        library_origins = {}
        for library in inventory['libraries']:
            digest = library['sha256']
            built = [{'kind': 'source-built', 'path': row['path']} for row in result['built_jars']
                     if Path(row['path']).name == library['name'] and row['sha256'] == digest]
            inputs = [{'kind': 'retained-input', 'repository': row['repository'], 'maven_path': row['maven_path']}
                      for row in retained if Path(row['maven_path']).name == library['name'] and row['sha256'] == digest]
            if not built and not inputs:
                raise ValueError('aggregate library has no retained or source-built origin')
            library_origins[library['name']] = {'sha256': digest, 'origins': built + inputs}
        war_entries, class_origins, jar_entries = [], defaultdict(list), {}
        with zipfile.ZipFile(inventory['war_path']) as archive:
            for name, data in entries(archive):
                war_entries.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
        patched = {}
        for jar in inventory['libraries']:
            member_rows = []
            with zipfile.ZipFile(output / 'lib' / jar['name']) as archive:
                for name, data in entries(archive):
                    digest = hashlib.sha256(data).hexdigest()
                    member_rows.append({'path': name, 'sha256': digest, 'size': len(data)})
                    if not name.endswith('.class'):
                        continue
                    if any(witness in name for witness in ('AmbisgisGeoNodeHttpTest', 'AmbisgisGeoNodeDiagnosticsTest',
                                                          'AmbisgisConfiguredDiagnosticsTest', 'AmbisgisStatelessOAuthFilterTest')):
                        raise ValueError('OAuth test witness leaked into aggregate application')
                    class_origins[name].append({'jar': jar['name'], 'sha256': digest})
                    if name in expected_classes:
                        spec = expected_classes[name]
                        if jar['name'] != spec['jar'] or name in patched:
                            raise ValueError('duplicate or unexpected OAuth class origin')
                        compiled = source / spec['module'] / 'target/classes' / name
                        if sha(compiled) != digest:
                            raise ValueError('packaged OAuth class differs from the source-build compiler output')
                        check_repaired_class(data, spec)
                        patched[name] = {'jar': jar['name'], 'class_sha256': digest,
                                         'compiled_path': str(compiled), 'repair_markers_verified': True}
            jar_entries[jar['name']] = member_rows
        if set(patched) != set(expected_classes):
            raise ValueError('repaired OAuth class missing')
        duplicates = {name: rows for name, rows in class_origins.items() if len(rows) > 1}
        if any(name.startswith('org/geoserver/security/') for name in duplicates):
            raise ValueError('duplicate GeoServer security class')
        logging = inventory['logging_resources']
        providers = logging['META-INF/services/org.slf4j.spi.SLF4JServiceProvider']
        if providers != ['log4j-slf4j2-impl-2.25.3.jar'] or logging['org/slf4j/impl/StaticLoggerBinder.class']:
            raise ValueError('unexpected aggregate logging provider selection')
        report['patched_classes'] = patched
        report['duplicate_classes'] = {'names': len(duplicates),
            'identical_byte_names': sum(len({row['sha256'] for row in rows}) == 1 for rows in duplicates.values()),
            'security_names': 0, 'all_duplicates_resolved': False,
            'scope': 'all duplicates retained; no duplicate GeoServer security class or competing SLF4J provider'}
        files = {'war-entries.json': war_entries, 'jar-entries.json': jar_entries,
                 'library-origins.json': library_origins,
                 'class-origins.json': dict(class_origins), 'duplicate-classes.json': duplicates}
        report['manifests'] = {}
        for name, data in files.items():
            write_json(output / name, data)
            report['manifests'][name] = {'sha256': sha(output / name), 'size': (output / name).stat().st_size}
        report['counts'] = {'war_files': len(war_entries), 'libraries': len(inventory['libraries']),
                            'jar_files': sum(len(rows) for rows in jar_entries.values()),
                            'distinct_class_paths': len(class_origins),
                            'class_entries': sum(len(rows) for rows in class_origins.values())}
        if sha(Path(inventory['war_path'])) != inventory['war_sha256']:
            raise ValueError('aggregate WAR changed during evidence inspection')
        for name, digest in report['tooling_manifest'].items():
            if sha(tooling / name) != digest or sha(Path(__file__).with_name(name)) != digest:
                raise ValueError('aggregate evidence tooling changed during inspection')
        report['retained_tooling_unchanged'] = True
        report['result_exit_code'] = 0
    except Exception as error:
        report['result_exit_code'] = 1
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    write_json(output / 'result.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.build.resolve(), args.output.absolute())
    print(json.dumps(result, indent=2))
    raise SystemExit(result['result_exit_code'])
