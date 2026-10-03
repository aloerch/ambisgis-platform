from pathlib import Path
import hashlib
import importlib.util
import json
import shutil

W = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-corpus-worktree')
R = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-corpus-runtime')
F = R / 'round-005'
V = W / 'plan/fixtures/synthetic-corpus/verification'
V.mkdir()

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(path.read_text())

def retain(source, relative):
    destination = V / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return {'path': relative, 'sha256': sha(destination), 'bytes': destination.stat().st_size}

producer = W / 'plan/tools/synthetic_corpus.py'
assert sha(producer) == sha(F / 'executed-synthetic-corpus.py')
spec = importlib.util.spec_from_file_location('synthetic_corpus', producer)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
selected_config = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd08-qgis-runtime/runtime-002-config.json')
assert sha(selected_config) == '5990ce8512cc548d9900241ee06e8e6df4f9a8865d3b65a6ffef7cdb5a10f3e7'
wrong = read(F / 'wrong-owned-source-config.json')
assert wrong['successor']['commit'] == '0' * 40
wrong['successor']['commit'] = read(selected_config)['successor']['commit']
assert wrong == read(selected_config)
evidence = {'schema_version': 1, 'task': 'FND-06',
    'base_commit': '6d18637e39818e60bcc947d3a7c252e84ab48fe0',
    'scope': 'Synthetic corpus generation, native fixture inspection and package checks only; not product/API/policy acceptance.',
    'selected_round': 'round-005', 'producer_sha256': sha(producer),
    'synthetic': True, 'rights': 'First-party GPL-3.0-or-later under existing project policy; no third-party runtime/font bytes included.',
    'source_files': {}, 'runs': {}, 'failed_attempts': [], 'custody_files': []}
for relative in ('plan/tools/synthetic_corpus.py', 'plan/tests/test_synthetic_corpus.py',
                 'plan/fixtures/synthetic-corpus/author_project.py',
                 'plan/fixtures/synthetic-corpus/templates/rich-style.qgs',
                 'plan/fixtures/synthetic-corpus/expected-small.json',
                 'plan/docs/fnd-06-synthetic-corpus.md'):
    evidence['source_files'][relative] = sha(W / relative)
assert sha(W / 'plan/fixtures/synthetic-corpus/small/manifest.json') == sha(F / 'small/manifest.json')
evidence['small_manifest_sha256'] = sha(F / 'small/manifest.json')
for name in ('final-checks.py', 'exercise-scales.py', 'scale-results.json', 'package-tests.log', 'package-schemas.log'):
    evidence['custody_files'].append(retain(F / name, name))
for count in (100000, 1000000):
    for suffix in ('command', 'network'):
        name = f'scale-{count}-{suffix}.json'
        evidence['custody_files'].append(retain(F / name, name))
    manifest_path = F / f'scale-{count}/manifest.json'
    evidence['custody_files'].append(retain(manifest_path, f'large-manifests/{count}.json'))
    assert read(manifest_path)['generator_sha256'] == sha(producer)
    assert read(manifest_path)['files'] == read(R / f'scale-{count}/manifest.json')['files']
evidence['payloads_unchanged_from_initial_large_generation'] = True
for name, expected_exit, corpus in (
        ('native-small', 0, 'small'), ('native-scale-100000', 0, 'scale-100000'),
        ('native-scale-1000000', 0, 'scale-1000000'),
        ('wrong-owned-source-001', 1, 'small'),
        ('reject-truncated-ndjson', 1, 'truncated-ndjson'),
        ('reject-changed-feet', 1, 'changed-feet')):
    command = read(F / (name + '-command.json'))
    network = read(F / (name + '-network.json'))
    assert command['tool_sha256'] == sha(producer)
    assert command['exit_code'] == expected_exit == network['command_exit_code']
    assert all(probe['passed'] for probe in network['probes'])
    row = {'expected_exit': expected_exit, 'actual_exit': command['exit_code'],
           'corpus_manifest_sha256': sha(F / corpus / 'manifest.json'), 'files': []}
    # Revalidate actual post-run membership and every byte; do not infer this
    # from the absence of a passing report alone.
    actual_manifest = module.validate_manifest(F / corpus)
    row['post_run_complete_membership_sizes_and_hashes_verified'] = True
    row['producer_still_matches_executed_snapshot'] = True
    selected = F / 'wrong-owned-source-config.json' if name == 'wrong-owned-source-001' else selected_config
    row['actual_runtime_config_sha256'] = sha(selected)
    if name == 'wrong-owned-source-001':
        row['selected_config_unchanged_except_deliberate_zero_source_commit'] = True
    if name in ('reject-truncated-ndjson', 'reject-changed-feet'):
        expected_files = read(F / 'small/manifest.json')['files']
        relative = 'addresses.ndjson' if name == 'reject-truncated-ndjson' else 'native/epsg2230.csv'
        altered = b'' if name == 'reject-truncated-ndjson' else (F / 'small' / relative).read_bytes().replace(b'6300000 1800000', b'6300001 1800000')
        expected_files[relative] = {'bytes': len(altered), 'sha256': hashlib.sha256(altered).hexdigest()}
        assert actual_manifest['files'] == expected_files
        row['post_run_data_matches_exact_derivative_created_by_executed_script'] = True
    for suffix in ('-command.json', '-network.json', '.log'):
        row['files'].append(retain(F / (name + suffix), name + suffix))
    if expected_exit == 0:
        result = read(F / (name + '.json'))
        assert result['status'] == 'passed'
        assert result['corpus_manifest_sha256'] == row['corpus_manifest_sha256']
        row['files'].append(retain(F / (name + '.json'), name + '.json'))
    else:
        assert not (F / (name + '.json')).exists()
        row['passing_report_absent'] = True
        row['files'].append(retain(F / corpus / 'manifest.json', name + '-derivative-manifest.json'))
        if name == 'wrong-owned-source-001':
            row['files'].append(retain(F / 'wrong-owned-source-config.json', 'wrong-owned-source-config.json'))
    evidence['runs'][name] = row
for name in ('author-project-command-002.json', 'author-project-network-002.json', 'author-project-002.log'):
    evidence['custody_files'].append(retain(R / name, name))
assert read(R / 'author-project-network-002.json')['command_exit_code'] == 0
for label, path, note in (
    ('initial-authoring', R / 'author-project-network.json', 'Provider lifetime at shutdown; failed process, not accepted.'),
    ('initial-native', R / 'native-001-network.json', 'Earlier internal passing result preceded fatal shutdown and is not accepted.'),
    ('round004-truncated-negative', R / 'round-004/reject-truncated-ndjson-network.json', 'Correct rejection exposed traceback/provider lifetime crash; fixed and rerun cleanly in round005.')):
    receipt = read(path)
    assert receipt['command_exit_code'] == -11
    evidence['failed_attempts'].append({'name': label, 'raw_command_exit': -11,
        'wrapper_exit': 139, 'disposition': note,
        'receipt': retain(path, 'failed-attempts/' + label + '.json')})
evidence['package_checks'] = {
    'tests': {'command': '/home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/ci-env/bin/python -m unittest discover -s tests -v',
              'cwd': str(W / 'plan'), 'passed': 474, 'corpus_tests': 17, 'exit_code': 0,
              'note': 'The final printed failed receipt is expected output of an existing negative package test; unittest result is OK.'},
    'schemas': {'command': '/home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/ci-env/bin/python tools/validate_package.py --require-schemas',
                'cwd': str(W / 'plan'), 'schemas_examples_passed': 4, 'exit_code': 0}}
tests = (F / 'package-tests.log').read_text()
assert 'Ran 474 tests' in tests and '\nOK\n' in tests
assert 'PASS (4 schemas/examples)' in (F / 'package-schemas.log').read_text()
(V / 'evidence.json').write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
print('evidence', sha(V / 'evidence.json'))
