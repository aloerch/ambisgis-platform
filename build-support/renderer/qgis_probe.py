"""Launch a selected owned PyQGIS script with fresh isolated runtime settings."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'qgis'))
from runtime import build_environment, validate_config
from renderer_artifacts import verify_stage
sys.path.insert(0, str(HERE.parent / 'java'))
from loopback_exec import verify_receipt


def run(config_path, output, script, plugin_root):
    config = json.loads(Path(config_path).read_text()); validate_config(config)
    output = Path(output).absolute(); output.mkdir(parents=True, mode=0o700)
    before = verify_stage(config)
    snapshot = output / 'tooling'
    shutil.copytree(plugin_root, snapshot / 'plugin', ignore=shutil.ignore_patterns('.git', '__pycache__'))
    shutil.copytree(HERE.parent / 'qgis', snapshot / 'qgis', ignore=shutil.ignore_patterns('__pycache__'))
    for relative in ('java/loopback_exec.py', 'postgis/offline_exec.py', 'renderer/qgis_probe.py'):
        target = snapshot / relative; target.parent.mkdir(exist_ok=True)
        shutil.copyfile(HERE.parent / relative, target)
    source_hashes = {str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in snapshot.rglob('*') if p.is_file()}
    selected_script = snapshot / 'plugin' / Path(script).resolve().relative_to(Path(plugin_root).resolve())
    env = build_environment(config, output)
    env['PYTHONFAULTHANDLER'] = '1'
    env['PYTHONPATH'] = str(snapshot / 'plugin') + ':' + str(snapshot / 'qgis') + ':' + ':'.join(config['python_paths'])
    config['output'] = str(output)
    (output / 'runtime-config.json').write_text(json.dumps(config, indent=2) + '\n')
    command = [config['python'], str(selected_script), str(output / 'runtime-config.json')]
    supervisor = [sys.executable, str(snapshot / 'java/loopback_exec.py'), '--evidence',
                  str(output / 'network-loopback.json'), '--timeout', '180', '--', *command]
    with (output / 'execution.log').open('x') as log:
        process = subprocess.Popen(supervisor, env=env, stdout=log, stderr=subprocess.STDOUT)
        try: code = process.wait(timeout=220)
        except subprocess.TimeoutExpired:
            process.terminate()
            try: process.wait(timeout=45)
            except subprocess.TimeoutExpired: raise RuntimeError('QGIS supervisor cleanup unresponsive')
            raise RuntimeError('QGIS supervisor deadline exceeded')
    network_error = None
    try: network = verify_receipt(output / 'network-loopback.json', code)
    except (RuntimeError, OSError, ValueError) as error:
        network = {}; network_error = str(error)
    after = verify_stage(config)
    unchanged = all(hashlib.sha256((snapshot / name).read_bytes()).hexdigest() == value for name,value in source_hashes.items())
    passed = code == 0 and unchanged and before == after and network_error is None
    report = {'command': supervisor, 'exit_code': code, 'result_exit_code': 0 if passed else 1, 'script': str(script),
              'script_sha256': hashlib.sha256(Path(script).read_bytes()).hexdigest(),
              'runtime_config_sha256': hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
              'source_sha256': source_hashes,
              'network_verified': network.get('status') == 'completed', 'network_error': network_error, 'stage': before,
              'stage_unchanged': before == after, 'tooling_unchanged': unchanged}
    (output / 'execution.json').write_text(json.dumps(report, indent=2) + '\n')
    return report['result_exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('config', 'output', 'script', 'plugin-root'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.output, args.script, args.plugin_root))
