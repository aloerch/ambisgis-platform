from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess

W = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-tr46-notices-worktree')
R = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/fnd06-tr46-notices-runtime/run-002')
R.mkdir()
A = Path('/home/revelberry/Projects/AmbisGIS/source-archives/fnd06-koop/candidate-002/registry/365413f62144e1b6242d1bf5312aebee2b6a73df29813d92e374458361ab7fba.tgz')
H = W / 'build-support/koop/tr46_notices.py'
S = R / 'stage'
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

guarded = [A, A.parents[1] / 'manifest.json']
guarded += [W / 'build-support/koop' / name for name in
            ('inputs.json', 'custody.py', 'install.py', 'retain.py', 'test_custody.py')]
before = {str(path): sha(path) for path in guarded}
report = {'base_commit': 'c6af1ad061e12a90bc78026d536a3e51960a63e6',
          'helper_sha256': sha(H), 'input_manifest_sha256': sha(H.parent / 'notices/tr46-0.0.3/input-manifest.json'),
          'guarded_inputs_before': before, 'runs': []}
(R / 'executed-tr46_notices.py').write_bytes(H.read_bytes())
environment = os.environ.copy()
environment['TR46_ARCHIVE'] = str(A)
environment['PYTHONDONTWRITEBYTECODE'] = '1'

commands = [
    ('verify', ['/usr/bin/python3', str(H), 'verify', '--archive', str(A)]),
    ('stage', ['/usr/bin/python3', str(H), 'stage', '--archive', str(A), '--output', str(S)]),
    ('staged-verifier', ['/usr/bin/python3', str(S / 'source/tr46-0.0.3/tr46_notices.py'),
        'verify-stage', '--archive', str(S / 'source/tr46-0.0.3/original-npm-archive.tgz'),
        '--bundle', str(S / 'source/tr46-0.0.3/supplement'), '--output', str(S)]),
    ('guards', ['/usr/bin/python3', str(W / 'plan/verification/fnd06-tr46-notices/test_tr46_notices.py'), '-v'])]
for name, command in commands:
    argv = ['/usr/bin/python3', str(W / 'build-support/postgis/offline_exec.py'),
            '--evidence', str(R / (name + '-network.json')), '--', *command]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=W, env=environment, capture_output=True, text=True)
    (R / (name + '.stdout')).write_text(result.stdout)
    (R / (name + '.stderr')).write_text(result.stderr)
    row = {'name': name, 'argv': argv, 'cwd': str(W), 'started_at': started,
           'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'exit_code': result.returncode, 'selected_environment': {'TR46_ARCHIVE': str(A), 'PYTHONDONTWRITEBYTECODE': '1'},
           'stdout_sha256': sha(R / (name + '.stdout')), 'stderr_sha256': sha(R / (name + '.stderr')),
           'network_sha256': sha(R / (name + '-network.json'))}
    report['runs'].append(row)
    (R / 'commands.json').write_text(json.dumps(report, indent=2) + '\n')
    print(name, result.returncode, flush=True)
    assert result.returncode == 0, result.stderr
    if name in ('stage', 'staged-verifier'):
        assert json.loads(result.stdout) == json.loads((S / 'stage-manifest.json').read_text())

after = {str(path): sha(path) for path in guarded}
assert before == after and sha(H) == report['helper_sha256']
report['guarded_inputs_after'] = after
report['guarded_inputs_unchanged'] = True
report['stage_manifest_sha256'] = sha(S / 'stage-manifest.json')
report['scope'] = 'Actual supplemental notice/source staging, reconstruction and guards; no install, dependency change, product adoption or distribution approval.'
(R / 'commands.json').write_text(json.dumps(report, indent=2) + '\n')
