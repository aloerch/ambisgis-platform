#!/usr/bin/env python3
"""Index immutable local evidence; no inventory copying or input modification.

Example:
  python3 index_evidence.py --runtime integration-repaired-04 \
    --source-commit <implementation-commit> --source-tree <implementation-tree> \
    --output evidence.json

The selected final runtime must have completed successfully. Failed prior runs
remain separately indexed as failed attempts. Test text is summarized as reported
output, not represented as an independently observed process exit status.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess

DEFAULT_ROOT = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-identity')
DEFAULT_CUSTODY = Path('/home/revelberry/Projects/AmbisGIS/source-archives/geonode-identity-v2')
WAR_SHA256 = '8a79a2cf7647be2f28591d7f04f975dc84cb00baaaea35cb3d5f2f293ea8f39f'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    value = json.loads(Path(path).read_text())
    require(isinstance(value, dict), 'receipt must be a JSON object: ' + str(path))
    return value


def identity(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'evidence must be a regular file: ' + str(path))
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
            'evidence changed while indexing: ' + str(path))
    return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': after.st_size}


def count_rows(rows):
    return {'records': len(rows), 'passed': sum(row.get('passed') is True for row in rows),
            'failed': sum(row.get('passed') is not True for row in rows)}


def native_summary(value):
    return {'tests_run': value.get('tests_run'), 'expected_count': value.get('expected_count'),
            'passed': value.get('passed'), 'strict_verifier': value.get('strict_verifier'),
            'failures': len(value.get('failures', [])), 'errors': len(value.get('errors', [])),
            'skips': len(value.get('skips', [])), 'expected_failures': len(value.get('expected_failures', [])),
            'unexpected_successes': len(value.get('unexpected_successes', [])), 'scope': value.get('scope')}


def network_summary(value):
    return {key: value.get(key) for key in ('result_exit_code', 'command_exit_code', 'mechanism',
            'network_probes', 'datagram_packets_received', 'task_process_group_stopped',
            'broker_sockets_closed', 'datagram_sentinels_closed', 'limitations')}


def journey_summary(value):
    scenarios = value.get('scenarios', [])
    rounds = Counter(row.get('round', 'unspecified') for row in scenarios)
    result = {'result_exit_code': value.get('result_exit_code'), 'identity_is_synthetic': value.get('identity_is_synthetic'),
              'geoserver_requests': count_rows(scenarios), 'geoserver_requests_by_round': dict(rounds),
              'protocol_assertions': count_rows(value.get('protocol', [])),
              'oauth_http_requests': value.get('oauth_request_count'),
              'failed_cases': [row.get('case') for row in scenarios + value.get('protocol', []) if row.get('passed') is not True],
              'war_sha256_after': value.get('war_sha256_after'),
              'restart': {'geonode_recorded': 'geonode_restart' in value, 'geoserver_recorded': 'geoserver_restart' in value},
              'error_type': value.get('error', {}).get('type')}
    for key in ('cache', 'expiry_cache', 'role_change', 'transport_faults', 'logger_capture_controls',
                'diagnostic_secret_hits', 'late_diagnostic_secret_hits', 'source_log_redactions',
                'cookie_scope', 'role_authority', 'coverage_limits', 'cleanup'):
        if key in value:
            result[key] = value[key]
    correlation = value.get('resource_request_correlation', {})
    result['resource_request_correlation'] = {key: correlation.get(key) for key in
         ('scope', 'expected_count', 'mixed_identity_worker_reuse', 'passed')}
    result['resource_request_correlation']['observed_records'] = len(correlation.get('requests', []))
    return result


def runtime_summary(value):
    child = value.get('child', {})
    result = {'result_exit_code': value.get('result_exit_code'), 'command_exit_code': value.get('command_exit_code'),
              'child_result_exit_code': child.get('result_exit_code'), 'tooling_unchanged': value.get('tooling_unchanged'),
              'network': network_summary(value.get('network', {})), 'cleanup': value.get('cleanup', {}),
              'child_cleanup': child.get('cleanup', {}), 'database_supervisor_exception': value.get('database_supervisor_exception'),
              'error_type': value.get('error', child.get('error', {})).get('type'),
              'database': {key: value.get('database', {}).get(key) for key in
                           ('started', 'stopped', 'result_exit_code', 'postgis_version', 'transport')}}
    if 'journey' in child:
        result['journey'] = journey_summary(child['journey'])
    result['commands'] = [{key: command.get(key) for key in
        ('action', 'exit_code', 'diagnostic_secret_hits', 'security_failures')} for command in child.get('commands', [])]
    return result


def validate_final(runtime, native):
    child = runtime.get('child', {})
    journey = child.get('journey', {})
    require(runtime.get('result_exit_code') == 0 and runtime.get('command_exit_code') == 0
            and child.get('result_exit_code') == 0 and journey.get('result_exit_code') == 0,
            'selected final runtime is incomplete or unsuccessful')
    require(child.get('identity_is_synthetic') is False and journey.get('identity_is_synthetic') is False,
            'selected runtime does not establish a real GeoNode identity journey')
    require(runtime.get('tooling_unchanged') is True, 'executed tooling integrity was not verified')
    require(journey.get('war_sha256_after') == WAR_SHA256, 'selected runtime WAR differs from the retained #59 artifact')
    for key in ('protocol', 'scenarios'):
        require(journey.get(key) and all(row.get('passed') is True for row in journey[key]),
                'selected runtime has absent or failed ' + key)
    require(native.get('passed') is True and native.get('strict_verifier') is True
            and isinstance(native.get('tests_run'), int) and native['tests_run'] > 0
            and native['tests_run'] == native.get('expected_count')
            and not any(native.get(key) for key in ('failures', 'errors', 'skips', 'expected_failures', 'unexpected_successes')),
            'selected native strict-verifier suite is incomplete or unsuccessful')
    network = runtime.get('network', {})
    require(network.get('result_exit_code') == 0 and network.get('command_exit_code') == 0
            and network.get('network_probes', {}).get('all_passed') is True
            and network.get('datagram_packets_received') == 0
            and all(network.get(key) is True for key in ('task_process_group_stopped', 'broker_sockets_closed', 'datagram_sentinels_closed')),
            'selected runtime network proof/cleanup is incomplete')
    database = runtime.get('database', {})
    require(database.get('result_exit_code') == 0 and database.get('started') is True and database.get('stopped') is True,
            'selected runtime database cleanup is incomplete')
    require(runtime.get('cleanup', {}).get('private_config_scrubbed') is True
            and child.get('cleanup', {}).get('stored_credentials_invalidated') is True,
            'selected runtime credential cleanup is incomplete')
    require('geonode_restart' in journey and 'geoserver_restart' in journey,
            'selected runtime has no completed service-restart evidence')
    controls = journey.get('logger_capture_controls', {})
    require(len(controls) >= 6 and all(value == 1 for value in controls.values()), 'missing positive application logger controls')
    for key in ('diagnostic_secret_hits', 'late_diagnostic_secret_hits', 'receipt_secret_hits_redacted'):
        require(journey.get(key, 0) == 0, 'selected runtime recorded a secret leak')


def verify_executed_python(final_dir, source_commit, source_tree):
    """Bind every executed GeoNode harness Python byte to frozen Git and current files."""
    repository = Path(__file__).resolve().parents[3]
    def git(*arguments):
        result = subprocess.run(['git', '-C', str(repository), *arguments],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        require(result.returncode == 0, 'cannot read the supplied implementation checkpoint')
        return result.stdout
    subtree = git('rev-parse', source_commit + ':build-support/geonode').decode().strip()
    require(source_tree is None or subtree == source_tree, 'supplied GeoNode source tree differs from implementation commit')
    committed = {name for name in git('ls-tree', '-r', '--name-only', source_commit, 'build-support/geonode').decode().splitlines()
                 if name.endswith('.py')}
    snapshot_root = final_dir / 'tooling/geonode'
    actual = {'build-support/geonode/' + path.relative_to(snapshot_root).as_posix(): path
              for path in snapshot_root.rglob('*.py')}
    require(committed and set(actual) == committed, 'executed GeoNode Python file set differs from frozen commit')
    declared = load(final_dir / 'tooling.json')
    checked = []
    for relative in sorted(committed):
        committed_bytes = git('show', source_commit + ':' + relative)
        committed_hash = hashlib.sha256(committed_bytes).hexdigest()
        snapshot = identity(actual[relative])
        current = identity(repository / relative)
        manifest_key = 'geonode/' + relative.removeprefix('build-support/geonode/')
        require(snapshot['sha256'] == current['sha256'] == committed_hash == declared.get(manifest_key),
                'executed/current/committed GeoNode Python bytes differ: ' + relative)
        checked.append({'path': relative, 'sha256': committed_hash, 'bytes': snapshot['bytes']})
    return {'passed': True, 'commit': source_commit, 'subtree': subtree, 'subtree_path': 'build-support/geonode',
            'verified_python_files': checked,
            'scope': 'Every snapshotted GeoNode harness .py matches retained tooling manifest, frozen Git commit and current source. Documentation-only changes are outside this comparison.'}


def text_summary(path):
    text = Path(path).read_text(errors='replace')
    runs = re.findall(r'^Ran (\d+) tests? in ([\d.]+)s\s*$', text, re.MULTILINE)
    if not runs:
        return {'scope': 'retained command output; inspect linked file for actual result'}
    outcomes = re.findall(r'^(OK(?:\s+\([^\n]*\))?|FAILED(?:\s+\([^\n]*\))?)\s*$', text, re.MULTILINE)
    return {'reported_tests': int(runs[-1][0]), 'reported_duration_seconds': float(runs[-1][1]),
            'reported_outcome': outcomes[-1] if outcomes else None,
            'scope': 'Parsed retained unittest output; process exit status is not inferred.'}


def generate(args):
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', args.runtime) is not None, 'runtime must be a directory basename')
    root, custody = args.retained_root.absolute(), args.custody.absolute()
    final_dir = root / args.runtime
    require(root.is_dir() and not root.is_symlink() and final_dir.is_dir() and not final_dir.is_symlink(),
            'retained runtime directory is missing or symlinked')
    runtime = load(final_dir / 'result.json')
    native = load(final_dir / 'native-tests.json')
    validate_final(runtime, native)
    require(load(final_dir / 'child-result.json') == runtime['child'], 'parent and child runtime receipts disagree')
    require(load(final_dir / 'journey-result.json') == runtime['child']['journey'], 'parent and journey receipts disagree')
    for option in ('source_commit', 'source_tree'):
        value = getattr(args, option)
        require(value is None or re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value), 'invalid ' + option + ' hash')
    require(args.source_commit is not None, 'source commit is required to bind executed tooling')
    source_verification = verify_executed_python(final_dir, args.source_commit, args.source_tree)
    index = {'schema_version': 1, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
             'scope': 'Bounded FND-02 GeoNode identity engineering evidence; no product/release acceptance.',
             'retained_root': str(root), 'selected_final_runtime': args.runtime,
             'implementation': {'commit': args.source_commit, 'tree': args.source_tree,
                                'hash_scope': 'Frozen implementation commit and build-support/geonode subtree; not a self-referential evidence commit.'},
             'executed_source_verification': source_verification,
             'generator': identity(__file__), 'final': runtime_summary(runtime), 'native_tests': native_summary(native),
             'files': [], 'prior_attempts': [], 'test_outputs': [], 'missing_optional': []}
    seen = set()

    def add(path, category, required=True, expected_sha256=None):
        path = Path(path).absolute()
        if not path.exists():
            if required:
                raise ValueError('required evidence missing: ' + str(path))
            index['missing_optional'].append(str(path))
            return None
        require(not any(part.startswith('private') or part == 'oidc-key.pem' for part in path.parts),
                'private credential files cannot be indexed')
        record = identity(path)
        if expected_sha256 is not None:
            require(record['sha256'] == expected_sha256, 'artifact hash differs from its receipt: ' + str(path))
        if str(path) not in seen:
            index['files'].append(dict(category=category, **record))
            seen.add(str(path))
        return record

    for name in ('result.json', 'child-result.json', 'journey-result.json', 'native-tests.json',
                 'network-loopback.json', 'network-loopback.probes.json', 'tooling.json',
                 'application-inventory.json', 'installed-origin-before.json', 'installed-origin-after.json', 'runtime-role.json'):
        add(final_dir / name, 'final-runtime')
    for pattern in ('*.log', 'module-origins-*.json', 'migrations-*.json', 'static-initialization.json', 'geoserver-fixture.json'):
        for path in sorted(final_dir.glob(pattern)):
            add(path, 'final-runtime-detail')
    for label in ('initial', 'restart'):
        for name in ('ready.json', 'requests.jsonl'):
            add(final_dir / ('geoserver-' + label) / name, 'final-resource-runtime')
    add(final_dir / 'database/database-result.json', 'final-database')

    attempts = {root / name for name in ('startup-01', 'startup-02', 'startup-03', 'integration-baseline-01', 'integration-repaired-01')}
    attempts.update(root.glob('integration-repaired-*'))
    for directory in sorted(attempts):
        if directory == final_dir:
            continue
        path = directory / 'result.json'
        if not path.exists():
            index['missing_optional'].append(str(path))
            continue
        record = add(path, 'prior-attempt')
        value = load(path)
        if directory.name in ('startup-01', 'startup-02', 'integration-baseline-01', 'integration-repaired-01'):
            require(type(value.get('result_exit_code')) is int and value['result_exit_code'] != 0, 'retained known failed attempt does not record a nonzero outcome')
        index['prior_attempts'].append({'name': directory.name, 'result': record, 'summary': runtime_summary(value)})
        for name in ('child-result.json', 'journey-result.json', 'native-tests.json', 'network-loopback.json', 'tooling.json'):
            if (directory / name).exists():
                add(directory / name, 'prior-attempt-detail')

    build = load(root / 'run-004/build-receipt.json')
    require(build.get('status') == 'passed', 'selected repaired build did not pass')
    source_repair = build.get('source_repair', {})
    require(source_repair.get('applied') is True and source_repair.get('default') is False
            and source_repair.get('post_patch_tree_verification') == 'passed', 'guarded source repair was not verified')
    index['build'] = {'name': 'run-004', 'status': build['status'], 'profile': build.get('profile'),
                      'python': build.get('python'), 'native_gdal_version': build.get('native_gdal_version'),
                      'owned_sources': build.get('sources'), 'source_repair': source_repair,
                      'compatibility_patch': build.get('compatibility_patch'), 'frontend_scope': build.get('frontend_scope'),
                      'network_policy': build.get('network_policy'),
                      'network_evidence_limit': 'Run004 build receipt alone is not network-denial proof; the separately indexed run005 replay retains namespace and outbound-denial proof. Runtime uses run004.'}
    for name in ('build-receipt.json', 'build.log', 'requirements.lock'):
        add(root / 'run-004' / name, 'source-build')
    for wheel in build.get('owned_wheels', []):
        add(wheel['path'], 'source-built-wheel', expected_sha256=wheel['sha256'])
    replay_dir = root / 'run-005'
    if (replay_dir / 'build-receipt.json').exists():
        replay = load(replay_dir / 'build-receipt.json')
        index['retained_input_build_replay'] = {
            'name': 'run-005', 'status': replay.get('status'),
            'manifest_sha256': replay.get('manifest_sha256'),
            'same_manifest_as_runtime_build': replay.get('manifest_sha256') == build.get('manifest_sha256'),
            'same_repaired_source_outputs': replay.get('source_repair', {}).get('expected_files') == source_repair.get('expected_files'),
            'scope': 'Separate fresh build/install replay from retained inputs; final HTTP runtime uses run-004.',
            'network_policy': replay.get('network_policy')}
        for name in ('build-receipt.json', 'build.log', 'requirements.lock'):
            add(replay_dir / name, 'retained-input-build-replay')
        for wheel in replay.get('owned_wheels', []):
            add(wheel['path'], 'replay-source-built-wheel', expected_sha256=wheel['sha256'])
    index['offline_replay_attempts'] = []
    for directory in sorted(root.glob('offline-replay-005*')):
        if not directory.is_dir():
            continue
        attempt = {'name': directory.name, 'completed': (directory / 'result.json').exists()}
        for name in ('invocation.json', 'network-proof.json', 'replay.py', 'replay.log', 'result.json'):
            if (directory / name).exists():
                add(directory / name, 'offline-build-network-proof')
        if attempt['completed']:
            result = load(directory / 'result.json')
            proof = load(directory / 'network-proof.json')
            proof_identity = identity(directory / 'network-proof.json')
            require(proof_identity['sha256'] == result.get('network_proof_sha256'), 'offline replay network proof hash mismatch')
            attempt.update({key: result.get(key) for key in ('passed', 'subprocess_exit_code', 'recipe_and_input_bytes_unchanged', 'build_receipt_sha256')})
            attempt['network'] = {key: proof.get(key) for key in ('passed', 'different_from_host', 'interfaces', 'ipv4_routes',
                                      'ipv6_routes_all_kernel_reject', 'outbound_probes', 'scope')}
            if result.get('passed') is True:
                require(result.get('subprocess_exit_code') == 0 and result.get('recipe_and_input_bytes_unchanged') is True
                        and proof.get('passed') is True and proof.get('different_from_host') is True,
                        'successful replay has inconsistent network/input proof')
                require(identity(replay_dir / 'build-receipt.json')['sha256'] == result.get('build_receipt_sha256'),
                        'offline replay build receipt hash mismatch')
        index['offline_replay_attempts'].append(attempt)
    for path in sorted(root.glob('*network*.json')):
        add(path, 'separate-build-network-proof')
    add(custody / 'manifest.json', 'source-custody', expected_sha256=build['manifest_sha256'])
    for source in build.get('sources', []):
        add(custody / source['archive'], 'owned-source-archive', expected_sha256=source['sha256'])
    for relative in ('acquisition/acquisition-receipt.json', 'acquisition-v2/acquisition-receipt.json'):
        add(root / relative, 'acquisition', required=False)
    manifest = load(custody / 'manifest.json')
    index['source_custody'] = {'profile': manifest.get('profile'), 'retained_file_records': len(manifest.get('files', [])),
                              'scope': 'Indexed manifest, not a declaration that all Python/native dependencies were rebuilt from source.'}

    synthetic_path = root / 'synthetic-regression-01/result.json'
    synthetic = load(synthetic_path)
    require(synthetic.get('result_exit_code') == 0 and synthetic.get('http', {}).get('result_exit_code') == 0,
            'preserved configured-WAR synthetic regression did not pass')
    rows = synthetic['http'].get('scenario_results', [])
    requests = [row for row in rows if 'method' in row]
    index['synthetic_regression'] = {'identity_is_synthetic': True, 'result_exit_code': synthetic['result_exit_code'],
        'scenario_records': count_rows(rows), 'actual_http_requests': count_rows(requests),
        'requests_by_round': dict(Counter(row.get('round', 'unspecified') for row in requests)),
        'war_sha256': synthetic.get('artifact_sha256'), 'network': network_summary(synthetic.get('network', {})),
        'scope': 'Separate preserved #59 configured-WAR regression; not real GeoNode issuance evidence.'}
    for name in ('result.json', 'http-result.json', 'network-loopback.json', 'network-loopback.probes.json', 'tooling.json'):
        add(root / 'synthetic-regression-01' / name, 'synthetic-regression')

    validation = root / 'validation-final-01'
    if validation.is_dir():
        for path in sorted(validation.rglob('*')):
            if path.is_file():
                record = add(path, 'final-validation')
                if path.suffix in ('.txt', '.log'):
                    index['test_outputs'].append({'file': record, 'summary': text_summary(path)})
    else:
        index['missing_optional'].append(str(validation))
    for name in ('harness-final-01.txt', 'java-tooling-final-01.txt'):
        path = root / name
        if path.exists():
            index['test_outputs'].append({'file': add(path, 'retained-test-output'), 'summary': text_summary(path)})
    index['files'].sort(key=lambda item: (item['category'], item['path']))
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--retained-root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--custody', type=Path, default=DEFAULT_CUSTODY)
    parser.add_argument('--source-commit')
    parser.add_argument('--source-tree')
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), 'output already exists; choose a new evidence path')
    index = generate(args)
    with args.output.open('x') as stream:
        json.dump(index, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'output': str(args.output.absolute()), 'files': len(index['files']),
                      'runtime': args.runtime, 'result_exit_code': index['final']['result_exit_code']}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print('Evidence index refused: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
