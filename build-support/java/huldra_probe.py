#!/usr/bin/env python3
"""Compile recovered Huldra 0.7.1 source and run its original 19 JUnit tests.

This is an isolated third-party repair-source probe, not product acceptance.
All executable inputs are already retained; no acquisition or Maven runs here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tarfile

from resolution import execute, sha, write_json
import toolchain

SOURCE_SHA = '3985701f0a8ef56a0d5408f2bfac9890e01efeb70751e946b9c34a3d1647a497'
REVISION = 'efb66d8bfe782a66a78cb8c4b7ddd2be7212a9f9'
JARS = {
    'junit-4.12.jar': '59721f0805e223d84b90677887d9ff567dc534d7c502ca903c0c2b17f05c116a',
    'hamcrest-core-1.3.jar': '66fdef91e9739348df7a096aa384a5685f4e875584cce89386a7a47251c4d8e9',
}


def verify_denial(evidence, exit_code):
    if evidence.get('status') != 'completed' or evidence.get('command_exit_code') != exit_code:
        raise ValueError('network wrapper did not complete with the recorded exit')
    probes = {p.get('family'): p for p in evidence.get('probes', []) if p.get('operation') == 'socket(SOCK_STREAM)'}
    for family in ('AF_INET', 'AF_INET6'):
        if not probes.get(family, {}).get('passed') or probes[family].get('errno') != 1:
            raise ValueError('missing successful network-denial probe: ' + family)


def probe(source, maven_custody, tool_custody, tools, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {'source_commit': REVISION, 'source_sha256': SOURCE_SHA,
              'acceptance_build': False, 'host_toolchain_closure': False,
              'purpose': 'third-party-repair-source-compilation-and-native-tests',
              'commands': [], 'exit_code': 1}
    try:
        if source.is_symlink() or sha(source) != SOURCE_SHA:
            raise ValueError('recovered source archive hash mismatch')
        manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
        report['toolchain'] = toolchain.verify_extracted(tool_custody, manifest, tools)
        java = tools / 'jdk-17.0.20.1+1'
        src = output / 'source'
        src.mkdir()
        # Read only the exact retained source/test/license members; never extract arbitrary paths.
        members = ['src/main/java/org/huldra/math/BigInt.java',
                   'src/test/java/org/huldra/math/BasicTest.java', 'LICENSE', 'pom.xml']
        inputs = []
        with tarfile.open(source) as archive:
            for name in members:
                member = archive.getmember('Huldra-' + REVISION + '/' + name)
                if not member.isfile():
                    raise ValueError('expected regular source member')
                content = archive.extractfile(member).read()
                target = src / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(content)
                inputs.append({'path': name, 'sha256': sha(target), 'size': len(content)})
        report['source_members'] = inputs
        lib = output / 'lib'
        lib.mkdir()
        for name, digest in JARS.items():
            original = maven_custody / 'blobs/sha256' / digest
            if original.is_symlink() or sha(original) != digest:
                raise ValueError('retained test input hash mismatch: ' + name)
            with (lib / name).open('xb') as stream:
                stream.write(original.read_bytes())
            if sha(lib / name) != digest:
                raise ValueError('test input changed during copy')
        report['test_inputs'] = JARS
        classes = output / 'classes'
        classes.mkdir()
        test_cp = os.pathsep.join(str(lib / name) for name in JARS)
        commands = [
            ('compile', [str(java / 'bin/javac'), '-source', '7', '-target', '7',
                         '-encoding', 'UTF-8', '-g', '-cp', test_cp, '-d', str(classes),
                         str(src / members[0]), str(src / members[1])]),
            ('native-tests', [str(java / 'bin/java'), '-cp', str(classes) + os.pathsep + test_cp,
                              'org.junit.runner.JUnitCore', 'org.huldra.math.BasicTest']),
        ]
        guard = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
        for name, command in commands:
            denial = output / (name + '-network-denial.json')
            guarded = [sys.executable, str(guard), '--evidence', str(denial), '--', *command]
            log = output / (name + '.log')
            with log.open('x') as stream:
                result = execute(guarded, output, env, stream, timeout=300)
            report['commands'].append({'name': name, 'command': guarded, 'exit_code': result,
                                       'log_sha256': sha(log), 'network_denial_sha256': sha(denial)})
            verify_denial(json.loads(denial.read_text()), result)
            if result:
                raise RuntimeError(name + ' failed with exit ' + str(result))
        text = (output / 'native-tests.log').read_text()
        if not re.search(r'^OK \(19 tests\)$', text, re.MULTILINE):
            raise ValueError('expected all 19 original native tests to execute and pass')
        report['native_tests'] = {'tests': 19, 'failures': 0, 'errors': 0, 'skipped': 0,
                                  'randomized_tests_use_original_unseeded_random': True}
        report['classes'] = [{'path': str(p.relative_to(classes)), 'sha256': sha(p)}
                             for p in sorted(classes.rglob('*.class'))]
        report['original_source_unchanged'] = all(sha(src / row['path']) == row['sha256'] for row in inputs)
        if not report['original_source_unchanged']:
            raise ValueError('original source was modified during probe')
        report['exit_code'] = 0
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        write_json(output / 'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'maven-custody', 'toolchain-custody', 'tools', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.source.absolute(), args.maven_custody.absolute(),
                   args.toolchain_custody.absolute(), args.tools.absolute(), args.output.absolute())
    print(json.dumps(result, indent=2))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
