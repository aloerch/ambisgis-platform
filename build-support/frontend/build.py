#!/usr/bin/env python3
"""Bounded owned client build: retained inputs, fresh install, denied networking.

Acquisition is separate. This command never contacts a package registry. It uses
retained owned Git bundles plus a complete lock whose archive paths are local.
The inherited legacy-peer-deps setting is preserved, not added to hide a failure.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1]
CLIENT = '7ca4822125b67999c97cb4aa1faa84b8a28eee9b'
MAPSTORE = '0f3518737f29f4049b131247ce981e94519d9ab0'
NODE = '24.18.1'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')

def inventory(root):
    return [{'path': str(p.relative_to(root)), 'bytes': p.stat().st_size,
             'sha256': sha(p)} for p in sorted(root.rglob('*')) if p.is_file()]

def verify_sri(path, integrity):
    require(isinstance(integrity, str) and integrity, 'Missing archive integrity')
    for token in integrity.split():
        algorithm, encoded = token.split('-', 1)
        require(algorithm in ('sha512', 'sha384', 'sha256', 'sha1'), 'Unsupported integrity')
        digest = hashlib.new(algorithm, Path(path).read_bytes()).digest()
        require(digest == base64.b64decode(encoded, validate=True), 'Archive integrity mismatch: ' + str(path))

def verify_inputs(root, manifest):
    require(manifest['client_commit'] == CLIENT and manifest['mapstore_commit'] == MAPSTORE,
            'Selected source tuple changed')
    require(root.is_dir() and not root.is_symlink(), 'Input root must be a real directory')
    paths = list(root.rglob('*'))
    require(not any(p.is_symlink() for p in paths), 'Symlink in retained inputs')
    actual = {str(p.relative_to(root)) for p in paths if p.is_file() and p != root/'manifest.json'}
    rows = manifest['files']
    names = [row['path'] for row in rows]
    require(len(names) == len(set(names)), 'Duplicate input record')
    required = {'client.bundle', 'mapstore.bundle', 'node.tar.xz', 'package-lock.json',
                'vendor/project.tar.gz', 'vendor/patcher.tar.gz', 'vendor/nomnom.tar.gz'}
    require(required <= set(names) and set(names) == actual, 'Incomplete or extra retained input manifest')
    for row in rows:
        rel = Path(row['path'])
        require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe input path')
        p = root / rel
        require(p.resolve().is_relative_to(root.resolve()), 'Input escapes retained root')
        require(p.is_file() and p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], 'Input changed: ' + str(rel))

def verify_reviewed_inputs(root, specification=HERE/'inputs.json', lock=HERE/'dependency-lock.json'):
    references = json.loads(specification.read_text())['references']
    manifests = [row for row in references if Path(row['path']).name == 'manifest.json']
    require(len(manifests) == 1 and sha(root/'manifest.json') == manifests[0]['sha256'], 'Retained manifest differs from reviewed input specification')
    require(sha(root/'package-lock.json') == sha(lock), 'Retained lock differs from reviewed dependency lock')

def guard_packages(front):
    p = front / 'package.json'; d = json.loads(p.read_text())
    require(d['devDependencies']['@mapstore/project'] == 'git+https://github.com/geosolutions-it/mapstore-project.git#master', 'Client source guard failed')
    d['devDependencies']['@mapstore/project'] = 'file:vendor/project.tar.gz'
    p.write_text(json.dumps(d, indent=2) + '\n')
    p = front / 'MapStore2/package.json'; d = json.loads(p.read_text())
    require(d['dependencies']['@mapstore/patcher'] == 'https://github.com/geosolutions-it/Patcher/tarball/master', 'MapStore source guard failed')
    d['dependencies']['@mapstore/patcher'] = 'file:../vendor/patcher.tar.gz'
    p.write_text(json.dumps(d, indent=2) + '\n')

def validate_lock(lock, vendor):
    require(lock['lockfileVersion'] == 3 and lock.get('packages'), 'Expected complete npm v3 lock')
    for name, row in lock['packages'].items():
        if not name or name == 'MapStore2':
            continue
        if row.get('link'):
            require(name == 'node_modules/mapstore' and row['resolved'] == 'MapStore2', 'Unexpected local link')
            continue
        resolved = row.get('resolved', '')
        require(resolved.startswith('file:vendor/'), 'Non-retained lock entry: ' + name)
        rel = Path(resolved[len('file:vendor/'):])
        require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe archive path')
        verify_sri(vendor / rel, row['integrity'])

def run(command, cwd, env, out, name, denied=False):
    cmd = list(map(str, command))
    if denied:
        cmd = [sys.executable, str(PLATFORM / 'build-support/postgis/offline_exec.py'),
               '--evidence', str(out / (name + '-network.json')), '--', *cmd]
    with (out / (name + '.log')).open('xb') as f:
        result = subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT)
    save(out / (name + '-command.json'), {'argv': cmd, 'cwd': str(cwd), 'exit_code': result.returncode})
    require(result.returncode == 0, name + ' failed; preserved log at ' + str(out))
    if denied:
        proof = json.loads((out / (name + '-network.json')).read_text())
        require(proof.get('status') == 'completed' and proof.get('command_exit_code') == 0, 'Network runner did not record command success')

def lifecycle_inventory(front):
    rows = []
    for p in sorted((front / 'node_modules').rglob('package.json')):
        try:
            d = json.loads(p.read_text())
        except (ValueError, UnicodeError):
            continue
        scripts = {k:v for k,v in d.get('scripts', {}).items() if k in ('preinstall','install','postinstall','prepare')}
        if scripts:
            rows.append({'path': str(p.relative_to(front)), 'name': d.get('name'),
                         'version': d.get('version'), 'scripts': scripts, 'package_sha256': sha(p)})
    return rows

def build(inputs, output, invocation=None):
    require(not output.exists(), 'Fresh output directory required')
    verify_reviewed_inputs(inputs)
    manifest = json.loads((inputs / 'manifest.json').read_text())
    verify_inputs(inputs, manifest)
    output.mkdir(parents=True)
    if invocation is not None:
        invocation['owns_output'] = True
    recipe = output/'recipe'; recipe.mkdir()
    for source in (HERE/'build.py', HERE/'inputs.json', HERE/'dependency-lock.json', PLATFORM/'build-support/postgis/offline_exec.py'):
        shutil.copyfile(source, recipe/source.name)
    save(output / 'receipt.json', {'state': 'started', 'inputs_sha256': sha(inputs/'manifest.json'), 'recipe': inventory(recipe)})
    # Bound inherited webpack worker fan-out without changing compilation semantics.
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4])
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(output/'home'), 'LANG': 'C.UTF-8',
           'LC_ALL': 'C.UTF-8', 'NODE_OPTIONS': '--max-old-space-size=8192',
           'npm_config_cache': str(output/'npm-cache'), 'npm_config_offline': 'true',
           'npm_config_audit': 'false', 'npm_config_fund': 'false',
           'npm_config_update_notifier': 'false', 'CI': 'true'}
    (output/'home').mkdir()
    tool = output/'toolchain'; tool.mkdir()
    with tarfile.open(inputs/'node.tar.xz') as t:
        t.extractall(tool, filter='data')
    bindir = tool/('node-v'+NODE+'-linux-x64/bin')
    env['PATH'] = str(bindir)+':/usr/bin:/bin'
    require(subprocess.check_output([str(bindir/'node'),'--version'],text=True).strip() == 'v'+NODE, 'Node version mismatch')
    client = output/'client'; front = client/'geonode_mapstore_client/client'
    for target, bundle, rev, name in [(client, inputs/'client.bundle', CLIENT, 'client'),
                                      (front/'MapStore2', inputs/'mapstore.bundle', MAPSTORE, 'mapstore')]:
        run(['git','clone','--no-checkout',bundle,target], output, env, output, name+'-recover', True)
        run(['git','checkout','--detach',rev], target, env, output, name+'-checkout', True)
    require(subprocess.check_output(['git','ls-tree',CLIENT,'geonode_mapstore_client/client/MapStore2'],cwd=client,text=True).split()[2] == MAPSTORE, 'Gitlink mismatch')
    guard_packages(front)
    shutil.copytree(inputs/'vendor', front/'vendor')
    shutil.copyfile(inputs/'package-lock.json',front/'package-lock.json')
    lock = json.loads((front/'package-lock.json').read_text()); validate_lock(lock,front/'vendor')
    # Remove inherited compiled bytes before the native compiler may run.
    static = client/'geonode_mapstore_client/static/mapstore'
    for p in (front/'dist', static/'dist', static/'ms-translations'):
        if p.exists(): shutil.rmtree(p)
    run(['npm','ci','--offline','--ignore-scripts','--no-audit','--no-fund'], front, env, output, 'install', True)
    save(output/'lifecycle-inventory.json',lifecycle_inventory(front))
    # Only reviewed source hook is needed: removes nested graticule dependency and
    # installs donor's patched Mocha locally. All other dependency hooks stay off.
    run(['node','MapStore2/utility/build/postInstall.js'], front, env, output, 'mapstore-postinstall', True)
    run(['npm','run','compile'], front, env, output, 'compile', True)
    outputs = inventory(static/'dist')
    require(outputs and any(x['path'].endswith('.js') for x in outputs) and any(x['path'].endswith('.css') for x in outputs), 'Missing compiled JS/CSS')
    save(output/'output-manifest.json', {'files': inventory(static), 'compiled_dist_files': outputs,
        'client_commit': CLIENT, 'mapstore_commit': MAPSTORE,
        'lock_sha256': sha(inputs/'package-lock.json'), 'scope': 'fresh compile; no byte-identical claim'})
    require(all((static/'dist/js'/name).is_file() for name in ('gn-map.js','gn-catalogue.js','gn-components.js','gn-dashboard.js','gn-document.js','gn-geostory.js')), 'Missing native application entry')
    verify_inputs(inputs, manifest)
    save(output/'success.json', {'state':'build-passed', 'output_manifest_sha256':sha(output/'output-manifest.json'),
        'node':subprocess.check_output(['node','--version'],env=env,text=True).strip(),
        'npm':subprocess.check_output(['npm','--version'],env=env,text=True).strip(),
        'network':'AF_INET/AF_INET6 denied for each install/hook/compiler and children',
        'limitations':'trusted-code process restriction, not hostile-code/filesystem isolation; dependency lifecycle hooks disabled except reviewed MapStore hook'})
    print(output/'success.json')

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); invocation = {}
    try:
        build(args.inputs.resolve(),args.output.resolve(),invocation)
    except Exception as e:
        if invocation.get('owns_output') and not (args.output/'failure.json').exists():
            save(args.output/'failure.json',{'state':'failed','type':type(e).__name__,'message':str(e)})
        raise
