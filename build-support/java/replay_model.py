#!/usr/bin/env python3
"""Recompute the selected effective model using retained files and socket denial.

This is dependency-model replay, never a Java build or runtime acceptance test.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

from resolution_inventory import verify_custody, read_file
from resolution import (command, execute, maven_inventory, sha, validate_effective, write_json)
import toolchain


def replay(work, custody, tool_custody, tools, output):
    manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
    installed = toolchain.verify_extracted(tool_custody, manifest, tools)
    java = tools / next(a['root'] for a in manifest['archives']
                        if a['role'] == 'distribution' and a['path'].startswith('OpenJDK'))
    maven = tools / next(a['root'] for a in manifest['archives']
                         if a['role'] == 'distribution' and a['path'].startswith('apache-maven'))
    before = json.loads((work / 'preparation.json').read_text())['maven_files']
    if maven_inventory(work / 'source') != before or (work / 'source/.mvn').exists():
        raise ValueError('prepared Maven source/configuration changed')
    if (work / 'empty-global-settings.xml').read_bytes() != b'<settings/>\n':
        raise ValueError('empty global settings changed')
    output.mkdir(parents=True, exist_ok=False)
    repository = output / 'retained-repository'
    repository.mkdir()
    rows = []
    # This path is read-only and has no network acquisition function. Stop
    # concurrent acquisition before taking this complete, verified snapshot.
    inventory = verify_custody(custody)
    if not inventory['verification']['valid']:
        raise ValueError('retained Maven custody failed verification')
    records = {(r['repository'], r['maven_path']): r for r in inventory['artifacts']}
    for path in sorted((custody / 'selections').rglob('*.json')):
        selected = json.loads(read_file(path))
        record = records[(selected['repository'], selected['maven_path'])]
        if path.relative_to(custody / 'selections').as_posix() != record['maven_path'] + '.json':
            raise ValueError('selection path does not match artifact identity')
        target = repository / record['maven_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream, (custody / record['blob_path']).open('rb') as source:
            shutil.copyfileobj(source, stream)
        if sha(target) != record['sha256']:
            raise ValueError('file mirror copy changed')
        rows.append(record)
    write_json(output / 'retained-inputs.json', rows)
    settings = output / 'settings.xml'
    settings.write_text('<settings><mirrors><mirror><id>ambisgis-custody</id>'
                        '<mirrorOf>*</mirrorOf><url>' + repository.as_uri() +
                        '</url></mirror></mirrors></settings>\n')
    local = output / 'fresh-m2'
    local.mkdir()
    run_id = 'network-denied-model-' + output.name
    model = work / 'logs' / (run_id + '-effective.xml')
    if model.exists() or model.is_symlink():
        raise ValueError('model output already exists')
    cmd, env = command(work, java, maven, 'effective', local, settings, run_id)
    offline_runner = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
    guarded = [sys.executable, str(offline_runner), '--evidence',
               str(output / 'network-denial.json'), '--', *cmd]
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'toolchain': installed, 'command': guarded, 'environment': env,
              'retained_files': len(rows), 'input_manifest_sha256': sha(output / 'retained-inputs.json'),
              'java_build_run': False, 'acceptance_build_ready': False,
              'result_exit_code': 1, 'exit_code': None}
    write_json(output / 'started.json', report)
    try:
        with (output / 'maven.log').open('x') as stream:
            result = execute(guarded, work / 'source', env, stream, 600)
        report['exit_code'] = result
        if result == 0:
            graph = validate_effective(model)
            write_json(output / 'effective-graph.json', graph)
            report['effective_projects'] = graph['project_count']
            report['effective_xml_sha256'] = sha(model)
        report['result_exit_code'] = result
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
        report['result_exit_code'] = 1
    finally:
        report['source_maven_files_unchanged'] = maven_inventory(work / 'source') == before
        if not report['source_maven_files_unchanged']:
            report['result_exit_code'] = 1
        report['log_sha256'] = sha(output / 'maven.log') if (output / 'maven.log').exists() else None
        write_json(output / 'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'custody', 'toolchain-custody', 'tools', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.work.resolve(), args.custody.resolve(),
                    args.toolchain_custody.resolve(), args.tools.resolve(), args.output.absolute())
    print(json.dumps(report, indent=2))
    raise SystemExit(report['result_exit_code'])


if __name__ == '__main__':
    main()
