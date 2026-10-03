from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess

R = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-corpus-runtime/round-005')
W = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-corpus-worktree')
T = W / 'plan/tools/synthetic_corpus.py'
C = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd08-qgis-runtime/runtime-002-config.json')
environment = json.loads((R / 'environment.json').read_text())
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def run(name, corpus, config, expected, error=None):
    report = R / (name + '.json')
    argv = ['/usr/bin/python3', str(W / 'build-support/postgis/offline_exec.py'),
            '--evidence', str(R / (name + '-network.json')), '--', '/usr/bin/python3.13',
            str(T), 'verify-native', str(corpus), '--report', str(report),
            '--runtime-config', str(config)]
    receipt = {'argv': argv, 'environment': environment, 'tool_sha256': sha(T),
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    result = subprocess.run(argv, env=environment, capture_output=True, text=True)
    (R / (name + '.log')).write_text(result.stdout + result.stderr)
    receipt.update(exit_code=result.returncode,
                   finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (R / (name + '-command.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    assert result.returncode == expected, result.stderr
    if expected:
        assert not report.exists()
        if error:
            assert error in result.stderr
    print(name, 'expected exit', expected, 'observed', result.returncode, flush=True)

wrong = json.loads(C.read_text())
wrong['successor']['commit'] = '0' * 40
bad = R / 'wrong-owned-source-config.json'
bad.write_text(json.dumps(wrong, indent=2) + '\n')
run('wrong-owned-source-001', R / 'small', bad, 1, 'wrong selected owned QGIS source')
run('native-small', R / 'small', C, 0)
for name, relative, replacement in (
        ('truncated-ndjson', 'addresses.ndjson', b''),
        ('changed-feet', 'native/epsg2230.csv', None)):
    target = R / name
    shutil.copytree(R / 'small', target)
    path = target / relative
    if replacement is None:
        replacement = path.read_bytes().replace(b'6300000 1800000', b'6300001 1800000')
    path.write_bytes(replacement)
    manifest_path = target / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files'][relative] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    run('reject-' + name, target, C, 1)
for count in (100000, 1000000):
    run(f'native-scale-{count}', R / f'scale-{count}', C, 0)
