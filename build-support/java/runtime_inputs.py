#!/usr/bin/env python3
"""Hash-checked retained servlet runtime staging; never resolves dependencies online."""
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import zipfile

from compatibility import verify_network_receipt
from resolution import execute, sha, write_json

MANIFEST = Path(__file__).with_name('runtime-inputs.json')
LAUNCHER = Path(__file__).with_name('runtime-fixtures') / 'ConfiguredGeoServerRuntime.java'


def checked_path(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative:
        raise ValueError('unsafe runtime input path')
    target = Path(root) / path
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('runtime input is not a retained regular file')
    return target


def verify(custody, manifest=None):
    manifest = json.loads(MANIFEST.read_text()) if manifest is None else manifest
    for row in manifest['artifacts']:
        for kind in ('binary', 'source', 'pom'):
            item = row[kind]
            blob = checked_path(custody, item['blob'])
            record = checked_path(custody, item['record'])
            if sha(blob) != item['sha256'] or blob.stat().st_size != item['size']:
                raise ValueError('retained servlet runtime input changed: ' + item['maven_path'])
            if sha(record) != item['record_sha256']:
                raise ValueError('servlet runtime acquisition record changed')
            acquired = json.loads(record.read_text())
            if acquired.get('sha256') != item['sha256'] or acquired.get('maven_path') != item['maven_path']:
                raise ValueError('servlet runtime acquisition identity differs')
            if kind != 'pom':
                with zipfile.ZipFile(blob) as archive:
                    for name, digest in item['notice_entries'].items():
                        import hashlib
                        if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                            raise ValueError('retained servlet runtime notice differs')
    return manifest


def stage(custody, output):
    """Create an exclusive new runtime directory from existing immutable custody."""
    custody, output = Path(custody), Path(output)
    manifest = verify(custody)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'lib').mkdir()
    rows = []
    for row in manifest['artifacts']:
        item = row['binary']
        target = output / 'lib' / PurePosixPath(item['maven_path']).name
        shutil.copyfile(checked_path(custody, item['blob']), target)
        if sha(target) != item['sha256']:
            raise ValueError('servlet runtime copy changed')
        rows.append({'name': target.name, 'sha256': item['sha256'], 'size': item['size']})
    report = {'schema_version': 1, 'network_acquisition': False,
              'manifest_path': str(MANIFEST.resolve()), 'manifest_sha256': sha(MANIFEST),
              'custody': str(custody.resolve()), 'libraries': rows}
    write_json(output / 'staged.json', report)
    report['classpath'] = classpath(output)
    return report


def classpath(staged):
    staged = Path(staged)
    report = json.loads((staged / 'staged.json').read_text())
    if report['manifest_sha256'] != sha(MANIFEST):
        raise ValueError('servlet runtime manifest changed')
    expected = {PurePosixPath(row['binary']['maven_path']).name: row['binary']['sha256']
                for row in json.loads(MANIFEST.read_text())['artifacts']}
    actual = {row['name']: row['sha256'] for row in report['libraries']}
    if expected != actual or len(actual) != len(report['libraries']):
        raise ValueError('servlet runtime staged inventory differs')
    if {p.name for p in (staged / 'lib').iterdir()} != set(expected):
        raise ValueError('unexpected servlet runtime classpath member')
    files = []
    for name, digest in expected.items():
        path = checked_path(staged / 'lib', name)
        if sha(path) != digest:
            raise ValueError('staged servlet runtime library changed')
        files.append(str(path.resolve()))
    return os.pathsep.join(files)


def compile_launcher(java_home, staged, output):
    """Compile the project-owned launcher under the existing socket-denial runner."""
    java_home, staged, output = Path(java_home), Path(staged), Path(output)
    cp = classpath(staged)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(LAUNCHER, output / LAUNCHER.name)
    (output / 'classes').mkdir()
    offline = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
    report = {'result_exit_code': 1, 'launcher_source_sha256': sha(LAUNCHER),
              'runtime_manifest_sha256': sha(MANIFEST), 'application_started': False}
    write_json(output / 'started.json', report)
    try:
        command = [sys.executable, str(offline), '--evidence', str(output / 'network-denial.json'),
                   '--', str(java_home / 'bin/javac'), '--release', '17', '-cp', cp,
                   '-d', str(output / 'classes'), str(output / LAUNCHER.name)]
        report['command'] = command
        with (output / 'compile.log').open('x') as stream:
            report['exit_code'] = execute(command, output,
                {'PATH': str(java_home / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'}, stream, 90)
        report['network_denial_verified'] = verify_network_receipt(
            output / 'network-denial.json', report['exit_code'])
        if report['exit_code']:
            raise ValueError('servlet launcher compilation failed')
        report['classes'] = {p.relative_to(output / 'classes').as_posix(): sha(p)
                             for p in (output / 'classes').rglob('*.class')}
        if not report['classes']:
            raise ValueError('servlet launcher produced no classes')
        report['classpath'] = str((output / 'classes').resolve()) + os.pathsep + cp
        report['result_exit_code'] = 0
        return report
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        write_json(output / 'result.json', report)


def launcher_command(java_home, staged, compiled, war, data, runtime, port=0, java_profile=None):
    """Recheck compiler evidence and every launcher/runtime byte before execution."""
    compiled = Path(compiled)
    report = json.loads((compiled / 'result.json').read_text())
    if report.get('result_exit_code') != 0 or report.get('exit_code') != 0:
        raise ValueError('require successful servlet launcher compiler receipt')
    if report.get('launcher_source_sha256') != sha(LAUNCHER):
        raise ValueError('servlet launcher source changed after compile')
    if report.get('runtime_manifest_sha256') != sha(MANIFEST):
        raise ValueError('servlet runtime manifest changed after compile')
    verify_network_receipt(compiled / 'network-denial.json', 0)
    expected = report['classes']
    actual = {p.relative_to(compiled / 'classes').as_posix(): sha(p)
              for p in (compiled / 'classes').rglob('*') if p.is_file()}
    if not expected or actual != expected:
        raise ValueError('compiled servlet launcher classes changed')
    for path in expected:
        checked_path(compiled / 'classes', path)
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError('invalid servlet fixture port')
    cp = str((compiled / 'classes').resolve()) + os.pathsep + classpath(staged)
    import runtime_profile
    options = runtime_profile.flags(java_profile, war)
    return [str(Path(java_home) / 'bin/java'), *options, '-Djava.awt.headless=true', '-cp', cp,
            'ConfiguredGeoServerRuntime', str(Path(war).absolute()), str(Path(data).absolute()),
            str(Path(runtime).absolute()), str(port)]
