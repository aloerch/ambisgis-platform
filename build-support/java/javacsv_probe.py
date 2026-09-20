#!/usr/bin/env python3
"""Compile recovered JavaCSV sources and run their historical JUnit tests offline.

This is a compatibility probe with retained JDK/JUnit inputs, not an acceptance
build or a reproduction of the original Java 5 toolchain's byte output.
"""
import argparse
import errno
import os
import json
from pathlib import Path
import re
import sys

from javacsv_recovery import ARTIFACT_SHA256, SELECTED, digest
from resolution import execute
import toolchain

JUNIT = 'junit/junit/4.13.2/junit-4.13.2.jar'
HAMCREST = 'org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'
JAR_HASHES = {
    JUNIT: '8e495b634469d64fb8acfa3495a065cbacc8a0fff55ce1e31007be4c16dc57d3',
    HAMCREST: '66fdef91e9739348df7a096aa384a5685f4e875584cce89386a7a47251c4d8e9',
}
RUNNER = '''import org.junit.runner.JUnitCore;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;
public class NativeTestRunner {
  public static void main(String[] args) throws Exception {
    java.net.URI actual = com.csvreader.CsvReader.class.getProtectionDomain().getCodeSource().getLocation().toURI();
    if (!new java.io.File(actual).getCanonicalFile().equals(new java.io.File(args[0]).getCanonicalFile()))
      throw new IllegalStateException("Unexpected JavaCSV class origin: " + actual);
    System.out.println("AMBISGIS_LIBRARY_ORIGIN " + actual);
    Result r = JUnitCore.runClasses(AllTests.class);
    for (Failure f : r.getFailures()) System.out.println(f.getTrace());
    System.out.println("AMBISGIS_JUNIT_RESULT run=" + r.getRunCount()
      + " failures=" + r.getFailureCount() + " ignored=" + r.getIgnoreCount());
    if (!r.wasSuccessful()) System.exit(1);
  }
}
'''


def native_result(text):
    matches = re.findall(r'AMBISGIS_JUNIT_RESULT run=(\d+) failures=(\d+) ignored=(\d+)', text)
    if len(matches) != 1:
        raise ValueError('Native runner did not return exactly one result')
    run, failures, ignored = map(int, matches[0])
    return {'run': run, 'failures': failures, 'ignored': ignored,
            'complete_success': run == 105 and failures == 0 and ignored == 0}


def retained_jar(root, maven_path):
    record = json.loads((root / 'records/central' / (maven_path + '.json')).read_text())
    expected = JAR_HASHES[maven_path]
    path = root / 'blobs/sha256' / expected
    if (record['sha256'] != expected or path.is_symlink()
            or path.stat().st_size != record['size'] or digest(path.read_bytes()) != expected):
        raise ValueError('Retained test dependency identity/hash differs')
    return path, record


def clean_environment():
    # Never inherit JVM agents/options, class paths, shell hooks or credentials.
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}


def verify_sources(root):
    if root.is_symlink():
        raise ValueError('Source root must be a real directory')
    for name, (_, expected) in SELECTED.items():
        path = root / name
        if path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError('Recovered historical source changed: ' + name)


def verify_denial(evidence, command, exit_code):
    if (evidence.get('status') != 'completed'
            or evidence.get('command_exit_code') != exit_code
            or evidence.get('command') != command):
        raise ValueError('Network wrapper did not complete the recorded command/exit')
    probes = [p for p in evidence.get('probes', []) if p.get('operation') == 'socket(SOCK_STREAM)']
    for family in ('AF_INET', 'AF_INET6'):
        matches = [p for p in probes if p.get('family') == family]
        if (len(matches) != 1 or matches[0].get('passed') is not True
                or matches[0].get('errno') != errno.EPERM):
            raise ValueError('Missing successful Internet socket denial: ' + family)
    if evidence.get('kernel_state', {}).get('no_new_privs') != 1:
        raise ValueError('Network wrapper did not retain no_new_privs')


def probe(sources, jdk, maven_custody, toolchain_custody, run,
          line_separator='host', original_artifact=None, timeout=300):
    if not 0 < timeout <= 300 or line_separator not in ('host', 'crlf'):
        raise ValueError('Invalid timeout or line-separator profile')
    run.mkdir(parents=True, exist_ok=False)
    record = {'purpose': 'isolated compatibility probe, not GIS acceptance',
              'java_target': '--release 8; original Java 5 output is not reproduced',
              'line_separator': line_separator, 'timeout_seconds_per_command': timeout,
              'environment': clean_environment(), 'commands': [], 'passed': False}
    classes = run / 'classes'
    local_source = run / 'source'
    try:
        manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
        jdk_roots = [a['root'] for a in manifest['archives']
                     if a['role'] == 'distribution' and a['root'].startswith('jdk-')]
        if jdk.is_symlink() or jdk_roots != [jdk.name]:
            raise ValueError('JDK path does not identify the retained distribution')
        record['toolchain'] = toolchain.verify_extracted(toolchain_custody, manifest, jdk.parent)
        verify_sources(sources)
        if original_artifact and (original_artifact.is_symlink()
                or digest(original_artifact.read_bytes()) != ARTIFACT_SHA256):
            raise ValueError('Baseline artifact differs from selected JavaCSV 2.0')
        dependencies = [retained_jar(maven_custody, name) for name in (JUNIT, HAMCREST)]
        # Copy only the pinned selected source/build inputs.
        for name in SELECTED:
            target = local_source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((sources / name).read_bytes())
        verify_sources(local_source)
        (local_source / 'src/NativeTestRunner.java').write_text(RUNNER)
        classes.mkdir()
        classpath = os.pathsep.join(str(path) for path, _ in dependencies)
        offline = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
        library_origin = original_artifact or classes
        runtime_classpath = ((str(original_artifact) + os.pathsep if original_artifact else '')
                             + str(classes) + os.pathsep + classpath)
        java_options = ['-Dline.separator=\r\n'] if line_separator == 'crlf' else []
        record.update(tested_library=str(library_origin),
                      source_recovery=json.loads((sources / 'recovery.json').read_text()),
                      dependencies=[metadata for _, metadata in dependencies])
        commands = [
            ('compile', [str(jdk/'bin/javac'), '--release', '8', '-encoding', 'ISO-8859-1',
                         '-cp', classpath, '-d', str(classes)]
                        + [str(local_source/name) for name in SELECTED if name.endswith('.java')]
                        + [str(local_source/'src/NativeTestRunner.java')]),
            ('native-tests', [str(jdk/'bin/java')] + java_options
                             + ['-cp', runtime_classpath, 'NativeTestRunner', str(library_origin)])]
        for label, command in commands:
            log = run / (label + '.log')
            denial = run / (label + '-offline.json')
            guarded = [sys.executable, str(offline), '--evidence', str(denial), '--'] + command
            step = {'label': label, 'argv': command, 'guarded_argv': guarded,
                    'log': str(log), 'denial_receipt': str(denial)}
            record['commands'].append(step)
            try:
                with log.open('xb') as stream:
                    code = execute(guarded, run, clean_environment(), stream,
                                   timeout=timeout, termination_grace=2)
                step['exit_code'] = code
                evidence = json.loads(denial.read_text())
                verify_denial(evidence, command, code)
                step['denial_verified'] = True
                verify_sources(sources)
                verify_sources(local_source)
                step['original_sources_unchanged'] = True
            finally:
                if log.is_file():
                    step['log_sha256'] = digest(log.read_bytes())
                if denial.is_file():
                    step['denial_sha256'] = digest(denial.read_bytes())
            if code:
                break
        if len(record['commands']) == 2:
            record['native_result'] = native_result((run/'native-tests.log').read_text())
        record['passed'] = (len(record['commands']) == 2
                            and all(x['exit_code'] == 0 for x in record['commands'])
                            and record['native_result']['complete_success'])
        record['original_sources_unchanged'] = True
    except Exception as error:
        record['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        if local_source.is_dir():
            try:
                verify_sources(sources)
                verify_sources(local_source)
                record['original_sources_unchanged'] = True
            except Exception as error:
                record['original_sources_unchanged'] = False
                record['source_integrity_error'] = {'type': type(error).__name__, 'message': str(error)}
                record['passed'] = False
        record['outputs'] = [{'path': str(path.relative_to(run)), 'size': path.stat().st_size,
                              'sha256': digest(path.read_bytes())}
                             for path in sorted(classes.rglob('*.class'))]
        (run/'result.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('sources', 'jdk', 'maven-custody', 'toolchain-custody', 'run'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--line-separator', choices=('host', 'crlf'), default='host',
                        help='Historical tests assume CRLF; host mode retains real platform failures')
    parser.add_argument('--original-artifact', type=Path,
                        help='Run tests against verified original JAR instead of rebuilt classes')
    parser.add_argument('--timeout', type=int, default=300, help='Per-command seconds, at most 300')
    args = parser.parse_args()
    result = probe(args.sources.absolute(), args.jdk.absolute(), args.maven_custody.absolute(),
                   args.toolchain_custody.absolute(), args.run.absolute(), args.line_separator,
                   args.original_artifact.absolute() if args.original_artifact else None, args.timeout)
    print(json.dumps({'passed': result['passed'], 'commands': result['commands'],
                      'error': result.get('error')}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
