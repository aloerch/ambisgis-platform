#!/usr/bin/env python3
"""Compile recovered JavaCSV sources and run their historical JUnit tests offline.

This is a compatibility probe with retained JDK/JUnit inputs, not an acceptance
build or a reproduction of the original Java 5 toolchain's byte output.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from javacsv_recovery import ARTIFACT_SHA256, SELECTED, digest

JUNIT = 'junit/junit/4.13.2/junit-4.13.2.jar'
HAMCREST = 'org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'
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
    path = root / 'blobs/sha256' / record['sha256']
    if path.stat().st_size != record['size'] or digest(path.read_bytes()) != record['sha256']:
        raise ValueError('Retained test dependency hash differs')
    return path, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--jdk', type=Path, required=True)
    parser.add_argument('--maven-custody', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--line-separator', choices=('host', 'crlf'), default='host',
                        help='Historical tests assume CRLF; host mode retains real platform failures')
    parser.add_argument('--original-artifact', type=Path,
                        help='Run tests against verified original JAR for comparison instead of rebuilt classes')
    args = parser.parse_args()
    for name, (_, expected) in SELECTED.items():
        if digest((args.sources / name).read_bytes()) != expected:
            raise ValueError('Recovered historical source changed')
    if args.original_artifact and digest(args.original_artifact.read_bytes()) != ARTIFACT_SHA256:
        raise ValueError('Baseline artifact differs from selected JavaCSV 2.0')
    dependencies = [retained_jar(args.maven_custody, name) for name in (JUNIT, HAMCREST)]
    args.run.mkdir(parents=True, exist_ok=False)
    source = args.run / 'src'
    shutil.copytree(args.sources / 'src', source)
    classes = args.run / 'classes'
    classes.mkdir()
    (source / 'NativeTestRunner.java').write_text(RUNNER)
    classpath = ':'.join(str(path) for path, _ in dependencies)
    offline = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
    library_origin = args.original_artifact or classes
    runtime_classpath = (str(args.original_artifact) + ':' if args.original_artifact else '') + str(classes) + ':' + classpath
    java_options = ['-Dline.separator=\r\n'] if args.line_separator == 'crlf' else []
    record = {'line_separator': args.line_separator, 'tested_library': str(library_origin),
              'purpose': 'isolated compatibility probe, not GIS acceptance',
              'java_target': '--release 8; original Java 5 output is not reproduced',
              'source_recovery': json.loads((args.sources / 'recovery.json').read_text()),
              'jdk_binaries': {name: {'path': str(args.jdk / 'bin' / name),
                                    'sha256': digest((args.jdk / 'bin' / name).read_bytes())}
                               for name in ('javac', 'java')},
              'dependencies': [metadata for _, metadata in dependencies], 'commands': []}
    commands = [
        ('compile', [str(args.jdk/'bin/javac'), '--release', '8', '-encoding', 'ISO-8859-1',
                     '-cp', classpath, '-d', str(classes)] + [str(path) for path in sorted(source.rglob('*.java'))]),
        ('native-tests', [str(args.jdk/'bin/java')] + java_options + ['-cp', runtime_classpath, 'NativeTestRunner', str(library_origin)])]
    for label, command in commands:
        log = args.run / (label + '.log')
        with log.open('wb') as stream:
            result = subprocess.run([sys.executable, str(offline), '--evidence',
                str(args.run/(label+'-offline.json')), '--'] + command,
                cwd=args.run, stdout=stream, stderr=subprocess.STDOUT)
        record['commands'].append({'label': label, 'argv': command, 'exit_code': result.returncode,
                                   'log': str(log), 'log_sha256': digest(log.read_bytes())})
        if result.returncode:
            break
    record['outputs'] = [{'path': str(path.relative_to(args.run)), 'size': path.stat().st_size,
                          'sha256': digest(path.read_bytes())} for path in sorted(classes.rglob('*.class'))]
    if len(record['commands']) == 2:
        record['native_result'] = native_result((args.run/'native-tests.log').read_text())
    record['passed'] = (len(record['commands']) == 2
                        and all(x['exit_code'] == 0 for x in record['commands'])
                        and record['native_result']['complete_success'])
    (args.run/'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'passed': record['passed'], 'commands': record['commands']}, indent=2))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
