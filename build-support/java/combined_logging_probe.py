#!/usr/bin/env python3
"""Inspect and exercise the complete packaged candidate classpath, without deployment."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import zipfile

from compatibility import verify_network_receipt
from resolution import execute, sha, write_json
import toolchain

REQUIRED = ('gs-main-2.28.5.jar', 'gs-sec-oauth2-geonode-2.28.5.jar',
            'gs-geofence-server-2.28.5.jar', 'gs-printing-2.28.5.jar',
            'print-lib-2.4.1.jar', 'gs-importer-core-2.28.5.jar')
WATCHED = ('org/slf4j/LoggerFactory.class', 'org/slf4j/impl/StaticLoggerBinder.class',
           'META-INF/services/org.slf4j.spi.SLF4JServiceProvider',
           'org/apache/logging/log4j/LogManager.class',
           'org/apache/logging/log4j/core/LoggerContext.class',
           'org/apache/commons/logging/LogFactory.class', 'org/apache/log4j/Logger.class')


def inspect_war(war, known_artifacts, destination):
    """Extract only verified library bytes; inherited application/data files stay inert."""
    destination.mkdir()
    rows, watched = [], {key: [] for key in WATCHED}
    with zipfile.ZipFile(war) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate WAR entries')
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('unsafe WAR entry')
            if name.startswith('WEB-INF/classes/') and not name.endswith('/'):
                raise ValueError('WAR classes/resources outside the bounded library classpath')
            if not (name.startswith('WEB-INF/lib/') and name.endswith('.jar')):
                continue
            if len(path.parts) != 3:
                raise ValueError('nested library path')
            data = archive.read(name)
            digest = hashlib.sha256(data).hexdigest()
            if digest not in known_artifacts.get(path.name, set()):
                raise ValueError('WAR library is absent from verified input/output inventory: ' + path.name)
            target = destination / path.name
            with target.open('xb') as stream:
                stream.write(data)
            with zipfile.ZipFile(io.BytesIO(data)) as jar:
                members = jar.namelist()
                if len(members) != len(set(members)):
                    raise ValueError('duplicate JAR entries: ' + path.name)
                for key in WATCHED:
                    if key in members:
                        watched[key].append(path.name)
            rows.append({'name': path.name, 'sha256': digest, 'size': len(data)})
    missing = sorted(set(REQUIRED) - {row['name'] for row in rows})
    if missing:
        raise ValueError('selected capabilities missing from WAR: ' + ', '.join(missing))
    return {'libraries': sorted(rows, key=lambda row: row['name']), 'logging_resources': watched}


def packaged_classpath(build, output):
    result_path = build / 'result.json'
    result = json.loads(result_path.read_text())
    if (result.get('result_exit_code') != 0 or result.get('target') != 'webapp'
            or result.get('stage') != 'package' or result.get('network_denial_verified') is not True
            or result.get('changed_original_source_files') != []):
        raise ValueError('require successful, network-denied selected webapp package receipt')
    verify_network_receipt(build / 'network-denial.json', result['exit_code'])
    known_artifacts = {}
    for row in result['built_jars']:
        relative = PurePosixPath(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unsafe built artifact path')
        actual = build / 'work/source' / relative
        if actual.is_symlink() or sha(actual) != row['sha256']:
            raise ValueError('built artifact changed')
        known_artifacts.setdefault(relative.name, set()).add(row['sha256'])
    retained_path = build / 'retained-inputs.json'
    if sha(retained_path) != result['input_manifest_sha256']:
        raise ValueError('retained input inventory changed')
    for row in json.loads(retained_path.read_text()):
        known_artifacts.setdefault(PurePosixPath(row['maven_path']).name, set()).add(row['sha256'])
    war = build / 'work/source/geoserver/src/web/app/target/geoserver.war'
    if war.is_symlink():
        raise ValueError('WAR must be a regular file')
    war_digest = sha(war)
    inventory = inspect_war(war, known_artifacts, output / 'lib')
    if sha(war) != war_digest:
        raise ValueError('WAR changed during inspection')
    inventory.update(war_path=str(war), war_sha256=war_digest,
                     build_receipt_path=str(result_path), build_receipt_sha256=sha(result_path))
    return inventory


def run(build, tool_custody, tools, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {'purpose': 'complete-candidate-war-logging-probe', 'acceptance_build': False,
              'application_started': False, 'native_component_logger_fields_exercised': False, 'service_requests_exercised': False,
              'explicit_witness_config': {'jul_manager': 'org.apache.logging.log4j.jul.LogManager',
                  'geotools_factory': 'org.geotools.util.logging.Log4J2LoggerFactory'},
              'result_exit_code': 1, 'runner_sha256': sha(Path(__file__))}
    write_json(output / 'started.json', report)
    try:
        tooling = output / 'tooling'
        for file in Path(__file__).resolve().parent.rglob('*'):
            if file.is_file() and file.suffix in ('.py', '.json', '.java', '.patch') and '__pycache__' not in file.parts:
                destination = tooling / 'java' / file.relative_to(Path(__file__).resolve().parent)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, destination)
        offline = tooling / 'postgis/offline_exec.py'
        offline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py', offline)
        report['tooling_manifest'] = {p.relative_to(tooling).as_posix(): sha(p)
                                      for p in sorted(tooling.rglob('*')) if p.is_file()}
        manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
        report['toolchain'] = toolchain.verify_extracted(tool_custody, manifest, tools)
        java = tools / next(row['root'] for row in manifest['archives']
                            if row['role'] == 'distribution' and row['path'].startswith('OpenJDK'))
        report['classpath'] = packaged_classpath(build, output)
        write_json(output / 'classpath.json', report['classpath'])
        source = Path(__file__).with_name('combined_logging-fixtures') / 'CombinedLoggingWitness.java'
        shutil.copyfile(source, output / source.name)
        report['witness_sha256'] = sha(output / source.name)
        cp = ':'.join(str(output / 'lib' / row['name']) for row in report['classpath']['libraries'])
        env = {'PATH': str(java / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'}
        def guarded(command, label):
            command = [sys.executable, str(offline), '--evidence', str(output / (label + '-network.json')), '--', *command]
            with (output / (label + '.log')).open('x') as stream:
                code = execute(command, output, env, stream, 90)
            return {'command': command, 'exit_code': code,
                    'network_denial': verify_network_receipt(output / (label + '-network.json'), code),
                    'log_sha256': sha(output / (label + '.log'))}
        report['compile'] = guarded([str(java / 'bin/javac'), '--release', '17', '-cp', cp,
                                     str(output / source.name)], 'compile')
        if report['compile']['exit_code']:
            raise ValueError('logging witness did not compile on packaged candidate')
        report['runtime'] = guarded([str(java / 'bin/java'), '-Djava.awt.headless=true',
                                     '-Djava.util.logging.manager=org.apache.logging.log4j.jul.LogManager', '-cp',
                                     str(output) + ':' + cp, 'CombinedLoggingWitness'], 'runtime')
        log = (output / 'runtime.log').read_text()
        markers = ['AMBISGIS_NATIVE_' + name for name in
                   ('GEOSERVER', 'GEOFENCE', 'PRINTING', 'OAUTH', 'PRINTING_COMMONS')]
        markers += ['AMBISGIS_JUL_BRIDGE', 'AMBISGIS_LOG4J1_API_BRIDGE']
        report['emissions'] = {marker: sum(marker == line or line.endswith(' ' + marker)
                              for line in log.splitlines()) for marker in markers}
        report['result_exit_code'] = 0 if report['runtime']['exit_code'] == 0 and all(
            count == 1 for count in report['emissions'].values()) else 1
        report['native_component_logger_fields_exercised'] = report['result_exit_code'] == 0
        for relative, digest in report['tooling_manifest'].items():
            if sha(tooling / relative) != digest:
                raise ValueError('retained logging-probe tooling changed')
        report['retained_tooling_unchanged'] = True
    except Exception as error:
        report['result_exit_code'] = 1
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    write_json(output / 'result.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'toolchain-custody', 'tools', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = run(args.build.resolve(), args.toolchain_custody.resolve(), args.tools.resolve(), args.output.absolute())
    print(json.dumps(result, indent=2))
    raise SystemExit(result['result_exit_code'])
