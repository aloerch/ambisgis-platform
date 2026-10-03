"""Verify completed private spike evidence and produce a public hash inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def read(path):
    return json.loads(Path(path).read_text())


def reference(path):
    path = Path(path).resolve()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def summarize(run, installation, head):
    result, tests = read(run / 'result.json'), read(run / 'tests.json')
    if result['result_exit_code'] or not tests['passed'] or not all(x['passed'] for x in tests['cases']):
        raise ValueError('actual runtime failed')
    if not result['origins_unchanged'] or not result['database']['stopped'] or not result['cleanup']['private_configuration_scrubbed']:
        raise ValueError('origin or cleanup evidence failed')
    cleanup = result['child']['cleanup']
    if not cleanup['credentials_invalidated'] or any(not cleanup[name]['stopped'] or cleanup[name]['security_failures'] for name in ('catalog', 'native', 'koop')):
        raise ValueError('service cleanup/diagnostics failed')
    # The fixture-outsider owns group_points and is authorized independently of
    # the reader's group. Require actual credential binding rejection, not403.
    changed = read(run / 'responses/native-cursor-changed-principal.json')
    status = next(x['status'] for x in tests['cases'] if x['case'] == 'native-cursor-changed-principal-bounded')
    if status != 400 or changed['error']['code'] != 'INVALID_CURSOR':
        raise ValueError('otherwise authorized credential cursor binding was not demonstrated')
    if read(run / 'node-toolchain-before.json') != read(run / 'node-toolchain-after.json'):
        raise ValueError('actual Node runtime changed')
    audit = [json.loads(x) for x in (run / 'native-audit.jsonl').read_text().splitlines()]
    queries = [x for x in audit if x['event'] == 'sql_query']
    projections = [read(p) for p in sorted(run.glob('projection-*.json'))]
    if any(x['raw_overflow'] for x in projections): raise ValueError('unexpected codec response overflow')
    if any(x['changed'] and not (x['metadata'] or x['empty_extent']) for x in projections):
        raise ValueError('unreviewed feature encoder projection')
    stats = read(run / 'koop-stats.json')
    if stats['cacheInsert'] != 0: raise ValueError('data cache stored a response')
    references = []
    for name in ('result.json', 'child-result.json', 'tests.json', 'fixture.json', 'invocation.json', 'tooling.json',
                 'contract-bindings.json', 'corpus-manifest.json', 'layer.json', 'network.json', 'network.probes.json',
                 'koop-installed-before.json', 'node-toolchain-before.json', 'node-toolchain-after.json',
                 'catalog-origin-before.json', 'catalog-origin-after.json', 'native-audit.jsonl', 'koop-stats.json',
                 'codec-diagnostics.json', 'codec-diagnostics-command.json', 'issuance.json', 'outer-invocation-observed.json'):
        references.append(reference(run / name))
    for pattern in ('raw-*.json', 'projection-*.json', 'responses/*.json', '*-command.json', '*-runtime.log'):
        for path in sorted(run.glob(pattern)):
            if not any(row['path'] == str(path.resolve()) for row in references): references.append(reference(path))
    for name in ('result.json', 'installed.json', 'network.json', 'install-command.json', 'manifest-projection.json'):
        references.append(reference(installation / name))
    histories = []
    for name in ('runtime-001', 'runtime-002', 'runtime-003', 'runtime-004'):
        path = run.parent / name / 'result.json'
        historical = read(path)
        histories.append({'attempt': name, 'result_exit_code': historical['result_exit_code'], 'receipt': reference(path),
                          'error': historical.get('child', {}).get('error'),
                          'actual_assertions': historical.get('child', {}).get('tests', {}).get('assertions')})
    return {'schema_version': 1, 'task': 'FND-06', 'scope': 'Private bounded Koop reuse spike; not production C1/client acceptance or distribution approval.',
            'implementation_head': head, 'runtime': str(run), 'assertions': tests['assertions'],
            'evidence_generator': reference(__file__),
            'source_commit': read(installation / 'result.json')['source_commit'],
            'input_manifest_sha256': read(installation / 'result.json')['input_manifest_sha256'],
            'contract_commit': read(run / 'invocation.json')['contract_commit'], 'corpus': result['corpus'],
            'addresses': result['child']['fixture']['addresses'], 'final_counters': {
                'sql_statements': len(queries), 'catalog_checks': sum(x['event'] == 'catalog_check' for x in audit),
                'raw_koop_responses': len(projections), 'changed_responses': sum(x['changed'] for x in projections),
                'changed_metadata': sum(x['changed'] and x['metadata'] for x in projections),
                'changed_empty_extent': sum(x['changed'] and x['empty_extent'] for x in projections),
                'koop': stats},
            'counter_scope_note': 'tests.json stores some counters before the final outage probes; final_counters here are recomputed from completed immutable files.',
            'sql_elapsed_ms': {'min': min(x['elapsed_ms'] for x in queries), 'median': statistics.median(x['elapsed_ms'] for x in queries), 'max': max(x['elapsed_ms'] for x in queries)},
            'maximum_rows_fetched_per_statement': max(x['rows_fetched'] for x in queries),
            'node_archive_entries_verified': len(read(run / 'node-toolchain-before.json')),
            'installed_registry_files_verified': read(installation / 'result.json')['installed_files'],
            'source_files_verified': read(installation / 'result.json')['source_files_verified'],
            'prior_attempts': histories, 'references': references, 'limits': tests['limitations']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = summarize(args.run.resolve(), args.installation.resolve(), args.head)
    with args.output.open('x') as stream: stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')
