#!/usr/bin/env python3
"""Execute a new frontend replay from a retained immutable tooling snapshot.

The old build-01 identity is never inferred or rewritten. This wrapper executes
its frozen copy, checks it after the command, and preserves failed attempts.
Native/browser checks remain separate receipts against the produced artifacts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PLATFORM = Path(__file__).resolve().parents[2]
COMPONENTS = ('frontend', 'postgis', 'geonode', 'java')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    result = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlink in frozen tooling: ' + str(path))
        if path.is_file():
            result.append({'path':str(path.relative_to(root)), 'sha256':sha(path), 'bytes':path.stat().st_size})
    return result


def save(path, document):
    with path.open('x') as stream:
        json.dump(document,stream,indent=2,sort_keys=True)
        stream.write('\n')


def freeze(platform, destination):
    destination.mkdir(parents=True,exist_ok=False)
    for component in COMPONENTS:
        source = platform / 'build-support' / component
        for path in sorted(source.rglob('*')):
            if '__pycache__' in path.parts:
                continue
            if path.is_symlink():
                raise ValueError('symlink in source tooling: ' + str(path))
            if path.is_file():
                target = destination / path.relative_to(platform)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
    return inventory(destination)


def verify_frozen(root, expected):
    if inventory(root) != expected:
        raise ValueError('frozen executed tooling changed; replay fails')


def run(inputs, output):
    output.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    result = {'state':'failed','scope':'new frontend replay only; native/browser acceptance separate'}
    try:
        snapshot = output/'frozen-platform'
        frozen = freeze(PLATFORM,snapshot)
        save(output/'tooling-manifest.json',frozen)
        command = [sys.executable,'-B',str(snapshot/'build-support/frontend/build.py'),
                   '--inputs',str(inputs),'--output',str(output/'build')]
        save(output/'invocation.json',{'argv':command,'cwd':str(snapshot),
             'executed_tooling_manifest_sha256':sha(output/'tooling-manifest.json'),
             'retained_inputs_manifest_sha256':sha(inputs/'manifest.json'),
             'source_platform':str(PLATFORM),
             'authorization':'2026-09-21 owner remediation prompt, course B; not retrospective PR #65 approval'})
        verify_frozen(snapshot,frozen)
        with (output/'console.log').open('xb') as log:
            proc = subprocess.run(command,cwd=snapshot,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
                                  stdout=log,stderr=subprocess.STDOUT)
        result['command_exit_code'] = proc.returncode
        verify_frozen(snapshot,frozen)
        if proc.returncode:
            raise RuntimeError('frozen build failed; see preserved build/failure.json and console.log')
        success = json.loads((output/'build/success.json').read_text())
        if success.get('state') != 'build-passed' or success['output_manifest_sha256'] != sha(output/'build/output-manifest.json'):
            raise ValueError('build success/output binding failed')
        result.update(state='replay-build-passed',output_manifest_sha256=success['output_manifest_sha256'],
                      executed_tooling_manifest_sha256=sha(output/'tooling-manifest.json'))
    except Exception as error:
        result['error'] = {'type':type(error).__name__,'message':str(error)}
    finally:
        result['elapsed_seconds'] = round(time.monotonic()-started,3)
        save(output/'replay-result.json',result)
    return 0 if result['state'] == 'replay-build-passed' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sys.exit(run(args.inputs.resolve(),args.output.resolve()))
