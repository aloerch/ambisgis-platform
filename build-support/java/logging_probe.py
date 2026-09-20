#!/usr/bin/env python3
"""Execute exact retained SLF4J provider witnesses, separate from product acceptance."""
import argparse
from pathlib import Path
import json
import sys
from resolution import execute, sha, write_json
from resolution_inventory import verify_custody, read_file
from compatibility import verify_network_receipt
import toolchain

SOURCE = '''import org.slf4j.LoggerFactory;
public class LoggingWitness {
  public static void main(String[] args) throws Exception {
    String factory = LoggerFactory.getILoggerFactory().getClass().getName();
    System.out.println("factory=" + factory);
    if (!factory.equals("org.apache.logging.slf4j.Log4jLoggerFactory"))
      throw new AssertionError("Logging provider was lost: " + factory);
    if (LoggingWitness.class.getClassLoader().getResources("org/slf4j/impl/StaticLoggerBinder.class").hasMoreElements())
      throw new AssertionError("Obsolete SLF4J 1.x binder remains on candidate classpath");
    LoggerFactory.getLogger("ambisgis.probe").atError().log("AMBISGIS_LOGGING_WITNESS");
  }
}
'''


def run(custody, tool_custody, tools, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
    report = {'purpose': 'isolated-logging-compatibility-witness', 'acceptance_build': False,
              'product_classpath_acceptance': False, 'cases': [], 'result_exit_code': 1}
    write_json(output / 'started.json', report)
    try:
        report['toolchain'] = toolchain.verify_extracted(tool_custody, manifest, tools)
        inventory = verify_custody(custody)
        if not inventory['verification']['valid']:
            raise ValueError('retained custody invalid')
        records = {(r['repository'], r['maven_path']): r for r in inventory['artifacts']}
        retained = []
        def jar(group, artifact, version):
            path = group.replace('.', '/') + '/' + artifact + '/' + version + '/' + artifact + '-' + version + '.jar'
            selected = json.loads(read_file(custody / 'selections' / (path + '.json')))
            record = records[(selected['repository'], selected['maven_path'])]
            if selected['maven_path'] != path:
                raise ValueError('selection identity mismatch')
            dest = output / Path(path).name
            if not dest.exists():
                with dest.open('xb') as target:
                    target.write(read_file(custody / record['blob_path']))
                if sha(dest) != record['sha256']:
                    raise ValueError('retained JAR changed')
                retained.append(record)
            return str(dest)
        api = jar('org.slf4j', 'slf4j-api', '2.0.17')
        variants = [('legacy-binding', '2.24.3', 'log4j-slf4j-impl', 1),
                    ('aligned-provider', '2.25.3', 'log4j-slf4j2-impl', 0)]
        java = tools / 'jdk-17.0.20.1+1'
        env = {'PATH': str(java / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'}
        offline = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
        def guarded(cmd, name):
            command = [sys.executable, str(offline), '--evidence', str(output / (name + '-network.json')), '--', *cmd]
            with (output / (name + '.log')).open('x') as stream:
                result = execute(command, output, env, stream, 60)
            network = verify_network_receipt(output / (name + '-network.json'), result)
            return {'command': command, 'exit_code': result, 'network_denial': network, 'log_sha256': sha(output / (name + '.log'))}
        (output / 'LoggingWitness.java').write_text(SOURCE)
        report['source_sha256'] = sha(output / 'LoggingWitness.java')
        report['compile'] = guarded([str(java / 'bin/javac'), '--release', '17', '-cp', api,
                                     str(output / 'LoggingWitness.java')], 'compile')
        if report['compile']['exit_code']:
            raise ValueError('witness compilation failed')
        for name, version, provider, expected in variants:
            jars = [api, jar('org.apache.logging.log4j', provider, version),
                    jar('org.apache.logging.log4j', 'log4j-api', version),
                    jar('org.apache.logging.log4j', 'log4j-core', version)]
            case = guarded([str(java / 'bin/java'), '-cp', ':'.join([str(output), *jars]), 'LoggingWitness'], name)
            case.update(name=name, expected_exit_code=expected, passed=case['exit_code'] == expected)
            log = (output / (name + '.log')).read_text()
            if expected == 0:
                case['passed'] = case['passed'] and 'AMBISGIS_LOGGING_WITNESS' in log
            else:
                case['passed'] = case['passed'] and 'NOPLoggerFactory' in log and 'No SLF4J providers were found' in log
            report['cases'].append(case)
        write_json(output / 'retained-inputs.json', retained)
        report['result_exit_code'] = 0 if all(c['passed'] for c in report['cases']) else 1
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    write_json(output / 'result.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('custody', 'toolchain-custody', 'tools', 'output'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    result = run(a.custody.resolve(), a.toolchain_custody.resolve(), a.tools.resolve(), a.output.absolute())
    print(json.dumps(result, indent=2))
    raise SystemExit(result['result_exit_code'])
