#!/usr/bin/env python3
"""Replay a pinned Maven model or dependency goal from retained files.

The default effective stage recomputes the selected effective model. The
optional dependencies stage runs only the selected reactor's pinned go-offline
goal. Both use a fresh Maven repository and the existing socket-denial wrapper;
neither compiles Java, runs a lifecycle build, or proves runtime acceptance.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

from resolution_inventory import verify_custody, read_file, walk_files
from resolution import (command, execute, maven_inventory, sha, validate_effective, write_json)
import toolchain


def replay(work, custody, tool_custody, tools, output, stage='effective'):
    if stage not in ('effective', 'dependencies'):
        raise ValueError('replay permits only effective or dependencies stages')
    # Reserve a fresh result directory before preparation. Existing output is
    # never reused; failures in verification or mirror creation get receipts too.
    output.mkdir(parents=True, exist_ok=False)
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'stage': stage, 'status': 'preparing', 'phase': 'preflight',
              'goal_timeout_seconds': 3600, 'transitive_closure_complete': False,
              'java_build_run': False, 'acceptance_build_ready': False,
              'result_exit_code': 1, 'exit_code': None}
    write_json(output / 'started.json', report)
    before = None
    try:
        manifest = json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
        installed = toolchain.verify_extracted(tool_custody, manifest, tools)
        report['toolchain'] = installed
        java = tools / next(a['root'] for a in manifest['archives']
                            if a['role'] == 'distribution' and a['path'].startswith('OpenJDK'))
        maven = tools / next(a['root'] for a in manifest['archives']
                             if a['role'] == 'distribution' and a['path'].startswith('apache-maven'))
        before = json.loads((work / 'preparation.json').read_text())['maven_files']
        if maven_inventory(work / 'source') != before or (work / 'source/.mvn').exists():
            raise ValueError('prepared Maven source/configuration changed')
        if (work / 'empty-global-settings.xml').read_bytes() != b'<settings/>\n':
            raise ValueError('empty global settings changed')
        repository = output / 'retained-repository'
        repository.mkdir()
        rows = []
        # This path is read-only and has no network acquisition function. Stop
        # concurrent acquisition before taking this complete, verified snapshot.
        inventory = verify_custody(custody)
        if not inventory['verification']['valid']:
            raise ValueError('retained Maven custody failed verification')
        records = {(r['repository'], r['maven_path']): r for r in inventory['artifacts']}
        selection_root = custody / 'selections'
        traversal_errors = []
        selection_files = walk_files(selection_root, traversal_errors)
        if traversal_errors:
            raise ValueError('unsafe selection tree: ' + json.dumps(traversal_errors, sort_keys=True))
        for path in selection_files:
            if path.suffix != '.json':
                raise ValueError('unexpected non-JSON selection file: ' + str(path))
            selected = json.loads(read_file(path))
            record = records[(selected['repository'], selected['maven_path'])]
            if path.relative_to(selection_root).as_posix() != record['maven_path'] + '.json':
                raise ValueError('selection path does not match artifact identity')
            target = repository / record['maven_path']
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream, (custody / record['blob_path']).open('rb') as source:
                shutil.copyfileobj(source, stream)
            if sha(target) != record['sha256']:
                raise ValueError('file mirror copy changed')
            rows.append(record)
        write_json(output / 'retained-inputs.json', rows)
        report['retained_files'] = len(rows)
        report['input_manifest_sha256'] = sha(output / 'retained-inputs.json')
        settings = output / 'settings.xml'
        with settings.open('x') as stream:
            stream.write('<settings><mirrors><mirror><id>ambisgis-custody</id>'
                         '<mirrorOf>*</mirrorOf><url>' + repository.as_uri() +
                         '</url></mirror></mirrors></settings>\n')
        local = output / 'fresh-m2'
        local.mkdir()
        report['fresh_local_repository'] = str(local)
        run_id = ('network-denied-model-' if stage == 'effective'
                  else 'network-denied-dependencies-') + output.name
        model = work / 'logs' / (run_id + '-effective.xml') if stage == 'effective' else None
        if model is not None and (model.exists() or model.is_symlink()):
            raise ValueError('model output already exists')
        cmd, env = command(work, java, maven, stage, local, settings, run_id)
        offline_runner = Path(__file__).resolve().parents[1] / 'postgis/offline_exec.py'
        guarded = [sys.executable, str(offline_runner), '--evidence',
                   str(output / 'network-denial.json'), '--', *cmd]
        report.update(command=guarded, environment=env, phase='execution', status='running')
        with (output / 'maven.log').open('x') as stream:
            result = execute(guarded, work / 'source', env, stream, 3600)
        report['exit_code'] = result
        if result == 0:
            report['phase'] = 'validation'
        if result == 0 and stage == 'effective':
            graph = validate_effective(model)
            write_json(output / 'effective-graph.json', graph)
            report['effective_projects'] = graph['project_count']
            report['effective_xml_sha256'] = sha(model)
        report['result_exit_code'] = result
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
        report['result_exit_code'] = 1
    finally:
        # A failed source read or log hash must not hide the primary failure or
        # prevent the immutable final receipt from being written.
        report['source_maven_files_unchanged'] = None
        report['log_sha256'] = None
        try:
            if before is not None:
                report['source_maven_files_unchanged'] = maven_inventory(work / 'source') == before
                if not report['source_maven_files_unchanged']:
                    report['result_exit_code'] = 1
            log = output / 'maven.log'
            if log.exists():
                report['log_sha256'] = sha(log)
        except BaseException as error:
            report['finalization_error'] = {'type': type(error).__name__, 'message': str(error)}
            report['result_exit_code'] = 1
        report['status'] = 'succeeded' if report['result_exit_code'] == 0 else 'failed'
        write_json(output / 'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'custody', 'toolchain-custody', 'tools', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--stage', choices=('effective', 'dependencies'), default='effective',
                        help='pinned acquisition goal to replay; default: effective')
    args = parser.parse_args()
    report = replay(args.work.resolve(), args.custody.resolve(),
                    args.toolchain_custody.resolve(), args.tools.resolve(), args.output.absolute(), args.stage)
    print(json.dumps(report, indent=2))
    raise SystemExit(report['result_exit_code'])


if __name__ == '__main__':
    main()
