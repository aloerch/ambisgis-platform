#!/usr/bin/env python3
"""Bounded Maven model/input acquisition; never compile, install or deploy.

All source and Maven repositories are task-local. Success here is resolution
only: source correspondence, native inputs and runtime tests are separate gates.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import signal
from pathlib import Path
import re
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET

NS = {'m': 'http://maven.apache.org/POM/4.0.0'}
PROFILES = ['importer', 'oauth2-geonode', 'geofence-server',
            'geofence-server-postgres', 'printing', 'postgis']
TARGETS = 'org.geoserver.web:gs-web-app,org.geoserver.geofence:geofence-persistence-pg-test'
HELP = 'org.apache.maven.plugins:maven-help-plugin:3.5.1:effective-pom'
DEPENDENCIES = 'org.apache.maven.plugins:maven-dependency-plugin:3.11.0:go-offline'
ROOTS = ['geotools', 'geowebcache/geowebcache',
         'geofence-132a1d16901b7039f974c8c30d7e7df042d8af4c/src',
         'mapfish-print-v2-da1f37cfc0d7a235cb2c0ec5677010495d9f664b',
         'geoserver/src']
EXTERNAL = ['dependency-research/geofence-3.8.3.tar.gz',
            'dependency-research/mapfish-2.4.1.tar.gz']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')


def pom_inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('pom.xml'))}


def maven_inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and (p.name == 'pom.xml' or '.mvn' in p.parts)}


def prepare(custody, output):
    from acquisition import verify
    manifest = json.loads(Path(__file__).with_name('inputs.json').read_text())
    verify(custody, manifest)
    # Existing source or resolver state is never silently reused or overwritten.
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    selected = []
    for item in manifest['files']:
        if ((item['origin'].get('kind') == 'owned-git-archive'
             and 'geonode' not in item['path']) or item['path'] in EXTERNAL):
            archive = custody / item['path']
            with tarfile.open(archive) as tf:
                tf.extractall(source, filter='data')
            selected.append(item)
    modules = ''.join('<module>' + r + '</module>' for r in ROOTS)
    (source / 'pom.xml').write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0">'
        '<modelVersion>4.0.0</modelVersion><groupId>org.ambisgis.audit</groupId>'
        '<artifactId>java-resolution</artifactId><version>1</version>'
        '<packaging>pom</packaging><modules>' + modules + '</modules></project>\n')
    (output / 'logs').mkdir()
    (output / 'empty-global-settings.xml').write_text('<settings/>\n')
    (output / 'user').mkdir()
    write_json(output / 'preparation.json', {
        'schema_version': 1, 'purpose': 'experimental-resolution-only',
        'source_archives': selected, 'roots': ROOTS, 'profiles': PROFILES, 'targets': TARGETS,
        'properties': {'gt.version': '34.5', 'gt-version': '34.5', 'mf.version': '2.4.1'},
        'source_adoption_approved': False, 'build_acceptance': False,
        'poms': pom_inventory(source), 'maven_files': maven_inventory(source)})
    return output


def command(work, java, maven, stage, local_repository, settings, log_id):
    if stage not in ('effective', 'dependencies'):
        raise ValueError('only explicitly pinned resolution goals are allowed')
    goal = HELP if stage == 'effective' else DEPENDENCIES
    cmd = [str(maven / 'bin/mvn'), '--batch-mode', '--no-transfer-progress',
           '-gs', str(work / 'empty-global-settings.xml'), '-s', str(settings),
           '-Dmaven.repo.local=' + str(local_repository),
           '-Dstyle.color=never', '-Dgt.version=34.5', '-Dgt-version=34.5',
           '-Dmf.version=2.4.1', '-Dspotless.apply.skip=true',
           '-Dpom.fmt.skip=true', '-P' + ','.join(PROFILES),
           '-pl', TARGETS, '-am', goal]
    if stage == 'effective':
        cmd += ['-Doutput=' + str(work / 'logs' / (log_id + '-effective.xml'))]
    else:
        cmd += ['--fail-at-end', '-DexcludeReactor=true']
    # No inherited MAVEN_OPTS, credentials, agents, mavenrc or user/global settings.
    env = {'PATH': str(java / 'bin') + ':/usr/bin:/bin', 'JAVA_HOME': str(java),
           'MAVEN_SKIP_RC': 'true', 'MAVEN_BASEDIR': str(work / 'source'), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
           'MAVEN_OPTS': '-Xmx2g -XX:ActiveProcessorCount=4 -Djava.awt.headless=true '
                         '-Duser.home=' + str(work / 'user')}
    return cmd, env


def execute(cmd, cwd, env, output, timeout, termination_grace=10):
    if termination_grace < 0:
        raise ValueError('termination grace must be nonnegative')
    process = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=output,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + termination_grace
        while True:
            # Reap the leader promptly, but its exit does not prove that the
            # offline wrapper's Maven/JVM descendants have left the group.
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(min(0.05, remaining))
        process.wait()
        raise


def validate_effective(path):
    report = effective_report(path)
    present = {p['gav'] for p in report['projects']}
    for target in TARGETS.split(','):
        if not any(gav.rsplit(':', 1)[0] == target for gav in present):
            raise ValueError('effective model omitted required target: ' + target)
    if 'org.mapfish.print:print-lib:2.4.1' not in present:
        raise ValueError('effective model omitted fixed printing candidate')
    return report


def run(work, custody, java, maven, toolchain_custody, stage, offline, run_id):
    from maven_proxy import MavenCustodyProxy
    import toolchain
    if not re.fullmatch('[a-z0-9][a-z0-9-]*', run_id):
        raise ValueError('run ID must be a simple unique filename')
    before = json.loads((work / 'preparation.json').read_text())['maven_files']
    if maven_inventory(work / 'source') != before or (work / 'source/.mvn').exists():
        raise ValueError('prepared Maven source/configuration changed')
    if (work / 'empty-global-settings.xml').read_bytes() != b'<settings/>\n':
        raise ValueError('empty global settings changed')
    tools_manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
    if java.parent != maven.parent:
        raise ValueError('JDK and Maven must share the verified toolchain extraction root')
    expected = {a['root'] for a in tools_manifest['archives'] if a['role'] == 'distribution'}
    if {java.name, maven.name} != expected:
        raise ValueError('tool paths do not match retained distributions')
    tools_receipt = toolchain.verify_extracted(toolchain_custody, tools_manifest, java.parent)
    logs = work / 'logs'
    receipt_path = logs / (run_id + '.json')
    for suffix in ('.json', '-started.json', '.log', '-settings.xml', '-effective.xml'):
        path = logs / (run_id + suffix)
        if path.exists() or path.is_symlink():
            raise ValueError('run output already exists: ' + str(path))
    local_repository = work / ('m2-' + run_id)
    local_repository.mkdir()
    started = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    receipt = {'schema_version': 1, 'started_at': started,
               'stage': stage, 'offline_proxy': offline,
               'fresh_local_repository': str(local_repository),
               'toolchain_verification': tools_receipt,
               'exit_code': None, 'result_exit_code': 1,
               'java_build_run': False, 'acceptance_build_ready': False}
    write_json(logs / (run_id + '-started.json'), receipt)
    try:
        with MavenCustodyProxy(custody, offline=offline) as proxy:
            settings = logs / (run_id + '-settings.xml')
            with settings.open('x') as stream:
                stream.write('<settings><mirrors><mirror><id>ambisgis-custody</id>'
                             '<mirrorOf>*</mirrorOf><url>' + proxy.base_url +
                             'all/</url></mirror></mirrors></settings>\n')
            cmd, env = command(work, java, maven, stage, local_repository, settings, run_id)
            receipt.update(command=cmd, environment=env)
            with (logs / (run_id + '.log')).open('x') as output:
                receipt['exit_code'] = execute(cmd, work / 'source', env, output, 3600)
        if receipt['exit_code'] == 0 and stage == 'effective':
            report = validate_effective(logs / (run_id + '-effective.xml'))
            receipt['effective_projects'] = report['project_count']
        receipt['result_exit_code'] = receipt['exit_code']
    except BaseException as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
        receipt['result_exit_code'] = 1
    finally:
        receipt['duration_seconds'] = round(time.monotonic() - start, 3)
        receipt['source_maven_files_unchanged'] = maven_inventory(work / 'source') == before
        log = logs / (run_id + '.log')
        receipt['log_sha256'] = sha(log) if log.exists() else None
        if not receipt['source_maven_files_unchanged']:
            receipt['result_exit_code'] = 1
        write_json(receipt_path, receipt)
    return receipt


def effective_report(path):
    root = ET.parse(path).getroot()
    projects = [root] if root.tag.endswith('}project') else list(root)
    result = []
    for p in projects:
        coord = ':'.join(p.findtext('m:' + k, '', NS) for k in ['groupId', 'artifactId', 'version'])
        deps = []
        for d in p.findall('m:dependencies/m:dependency', NS):
            deps.append({k: d.findtext('m:' + k, '', NS) for k in
                         ['groupId', 'artifactId', 'version', 'type', 'scope', 'classifier']})
        plugins = []
        for d in p.findall('m:build/m:plugins/m:plugin', NS):
            plugins.append({k: d.findtext('m:' + k, '', NS) for k in
                            ['groupId', 'artifactId', 'version']})
        result.append({'gav': coord, 'dependencies': deps, 'plugins': plugins})
    return {'project_count': len(result), 'projects': result,
            'effective_xml_sha256': sha(path), 'transitive_closure_complete': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['prepare', 'effective', 'dependencies', 'report'])
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--audit-custody', type=Path)
    p.add_argument('--custody', type=Path)
    p.add_argument('--java', type=Path)
    p.add_argument('--maven', type=Path)
    p.add_argument('--toolchain-custody', type=Path)
    p.add_argument('--offline', action='store_true')
    p.add_argument('--run-id')
    p.add_argument('--effective-xml', type=Path)
    args = p.parse_args()
    if args.stage == 'prepare':
        if not args.audit_custody:
            p.error('prepare requires --audit-custody')
        print(prepare(args.audit_custody.resolve(), args.work.absolute()))
    elif args.stage == 'report':
        if not args.effective_xml:
            p.error('report requires --effective-xml')
        print(json.dumps(effective_report(args.effective_xml), indent=2))
    else:
        if not all([args.custody, args.java, args.maven, args.run_id, args.toolchain_custody]):
            p.error('resolution requires --custody --java --maven --toolchain-custody --run-id')
        report = run(args.work.resolve(), args.custody.absolute(), args.java.resolve(),
                     args.maven.resolve(), args.toolchain_custody.resolve(), args.stage, args.offline, args.run_id)
        print(json.dumps(report, indent=2))
        raise SystemExit(report['result_exit_code'])


if __name__ == '__main__':
    main()
