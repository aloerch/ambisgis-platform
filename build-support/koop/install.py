"""Fresh, socket-denied installation of the reviewed production-only source graph.

This invokes retained npm with every lifecycle disabled; it does not import Koop.
The six installation manifests omit devDependencies only. Original source and
manifests remain intact in custody and in the attempt's source-pristine directory.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from custody import (COMMIT, TREE, WORKSPACES, archive_files, require, save, sha,
                     source_manifest, verify_inventory)

HERE = Path(__file__).resolve().parent


def verify_reviewed(inputs, specification):
    spec = json.loads(Path(specification).read_text())
    require(spec['source_commit'] == COMMIT and spec['source_tree'] == TREE, 'reviewed source identity differs')
    require(sha(inputs / 'manifest.json') == spec['manifest_sha256'], 'reviewed manifest differs')
    require(sha(inputs / 'package-lock.json') == spec['production_lock_sha256'], 'reviewed lock differs')
    return verify_inventory(inputs)


def source_projection(files, app):
    changes = []
    for name in WORKSPACES:
        path = 'packages/' + name + '/package.json'
        original = json.loads(files[path])
        projected = {key: value for key, value in original.items() if key != 'devDependencies'}
        save(app / path, projected)
        changes.append({'path': path, 'removed_field': 'devDependencies',
                        'removed_value': original.get('devDependencies'),
                        'all_other_fields_equal': projected == {k: v for k, v in original.items() if k != 'devDependencies'}})
    return changes


def verify_installed(app, inputs, lock):
    rows = []
    expected_files = set()
    workspace_links = {}
    for name, row in lock['packages'].items():
        if not name.startswith('node_modules/') or row.get('link'):
            continue
        require(row.get('resolved') and row.get('integrity'), 'unresolved installed registry identity: ' + name)
        path = app / name
        if not path.exists():
            require(row.get('optional'), 'required installed package missing: ' + name)
            rows.append({'path': name, 'version': row['version'], 'omitted_optional': True})
            continue
        require(not path.is_symlink(), 'registry package directory is a link')
        files = archive_files(inputs / row['resolved'][5:])
        verified = 0
        for archive_name, data in files.items():
            relative = '/'.join(archive_name.split('/')[1:])
            target = path / relative
            require(target.is_file() and not target.is_symlink(), 'installed archive member missing: ' + str(target))
            require(target.read_bytes() == data, 'installed member differs from retained archive: ' + str(target))
            expected_files.add(target.relative_to(app).as_posix())
            verified += 1
        package = json.loads((path / 'package.json').read_text())
        require(package['version'] == row['version'], 'installed package version differs')
        rows.append({'path': name, 'name': package['name'], 'version': row['version'],
                     'archive_members_verified': verified, 'package_sha256': sha(path / 'package.json')})
    require(not (app / 'node_modules/farmhash').exists(), 'unselected native hashing installed')
    for name in WORKSPACES:
        source = app / 'packages' / name
        manifest = json.loads((source / 'package.json').read_text())
        link = app / 'node_modules' / manifest['name']
        require(link.is_symlink() and link.resolve() == source.resolve(), 'workspace source binding differs')
        workspace_links[link.relative_to(app).as_posix()] = source.resolve()
    installed_files = []
    installed_links = []
    for directory, directories, filenames in os.walk(app / 'node_modules', followlinks=False):
        for name in directories + filenames:
            path = Path(directory) / name
            relative = path.relative_to(app).as_posix()
            if path.is_symlink():
                target = path.resolve()
                if relative in workspace_links:
                    require(target == workspace_links[relative], 'unexpected workspace link target')
                else:
                    require(path.parent.name == '.bin' and target.is_relative_to(app)
                            and target.relative_to(app).as_posix() in expected_files,
                            'unexpected installed link: ' + relative)
                installed_links.append({'path': relative, 'target': os.readlink(path)})
            elif path.is_file():
                require(relative in expected_files or relative == 'node_modules/.package-lock.json',
                        'unexpected installed file: ' + relative)
                installed_files.append({'path': relative, 'sha256': sha(path), 'bytes': path.stat().st_size})
    require(expected_files <= {row['path'] for row in installed_files}, 'installed expected file inventory incomplete')
    return {'packages': rows, 'files': installed_files, 'links': installed_links}


def install(inputs, output, specification):
    manifest = verify_reviewed(inputs, specification)
    require(not output.exists(), 'fresh installation output required')
    output.mkdir(parents=True)
    tooling = output / 'tooling'
    tooling.mkdir()
    for source in (HERE / 'custody.py', HERE / 'install.py', Path(specification),
                   HERE.parent / 'postgis/offline_exec.py'):
        shutil.copyfile(source, tooling / source.name)
    save(output / 'started.json', {'input_manifest_sha256': sha(inputs / 'manifest.json'),
                                  'tooling': [{'path': str(path), 'sha256': sha(path)} for path in sorted(tooling.iterdir())],
                                  'package_imports': False, 'lifecycle_execution': False})
    files, source_rows = source_manifest(inputs / 'source.tar.gz', json.loads((inputs / 'source-tree.json').read_text()))
    pristine = output / 'source-pristine'
    app = output / 'app'
    app.mkdir()
    for path, data in files.items():
        destination = pristine / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(int(source_rows[path]['git_mode'], 8) & 0o777)
        if path.startswith('packages/') and path.split('/')[1] in WORKSPACES:
            target = app / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not path.endswith('/package.json') or path.count('/') != 2:
                shutil.copyfile(destination, target)
                target.chmod(destination.stat().st_mode & 0o777)
    changes = source_projection(files, app)
    save(output / 'manifest-projection.json', changes)
    shutil.copyfile(inputs / 'package.json', app / 'package.json')
    shutil.copyfile(inputs / 'package-lock.json', app / 'package-lock.json')
    shutil.copytree(inputs / 'registry', app / 'registry')
    toolchain = output / 'toolchain'
    toolchain.mkdir()
    with tarfile.open(inputs / 'node.tar.xz') as archive:
        archive.extractall(toolchain, filter='data')
    bindir = toolchain / 'node-v24.18.1-linux-x64/bin'
    home = output / 'home'
    home.mkdir()
    for name in ('user.npmrc', 'global.npmrc'):
        (output / name).write_text('')
    env = {'PATH': str(bindir) + ':/usr/bin:/bin', 'HOME': str(home), 'LANG': 'C.UTF-8',
           'LC_ALL': 'C.UTF-8', 'NODE_OPTIONS': '--max-old-space-size=1024',
           'npm_config_cache': str(output / 'npm-cache'), 'npm_config_offline': 'true',
           'npm_config_userconfig': str(output / 'user.npmrc'), 'npm_config_globalconfig': str(output / 'global.npmrc'),
           'npm_config_audit': 'false', 'npm_config_fund': 'false', 'npm_config_update_notifier': 'false',
           'OBJECTID_FEATURE_HASH': 'javascript', 'CI': 'true'}
    require(subprocess.check_output([str(bindir / 'node'), '--version'], cwd=app, env=env,
                                    text=True).strip() == 'v24.18.1', 'retained Node version differs')
    command = ['/usr/bin/python3', str(tooling / 'offline_exec.py'), '--evidence', str(output / 'network.json'),
               '--', str(bindir / 'npm'), 'ci', '--offline', '--ignore-scripts', '--omit=dev', '--omit=optional',
               '--no-audit', '--no-fund']
    with (output / 'install.log').open('xb') as log:
        result = subprocess.run(command, cwd=app, env=env, stdout=log, stderr=subprocess.STDOUT)
    save(output / 'install-command.json', {'argv': command, 'cwd': str(app), 'environment': env, 'exit_code': result.returncode})
    require(result.returncode == 0, 'offline install failed; attempt retained')
    proof = json.loads((output / 'network.json').read_text())
    require(proof['status'] == 'completed' and proof['command_exit_code'] == 0, 'network proof incomplete')
    installed = verify_installed(app, inputs, json.loads((inputs / 'package-lock.json').read_text()))
    for path, data in files.items():
        require((pristine / path).read_bytes() == data, 'pristine source changed')
        if path.startswith('packages/') and path.split('/')[1] in WORKSPACES:
            target = app / path
            if path.endswith('/package.json') and path.count('/') == 2:
                expected = {k: v for k, v in json.loads(data).items() if k != 'devDependencies'}
                require(json.loads(target.read_text()) == expected, 'installation manifest mutation')
            else:
                require(target.read_bytes() == data, 'workspace source mutation')
    verify_reviewed(inputs, specification)
    save(output / 'installed.json', installed)
    save(output / 'result.json', {'result_exit_code': 0, 'source_commit': COMMIT, 'source_tree': TREE,
                                'input_manifest_sha256': sha(inputs / 'manifest.json'),
                                'installed_registry_packages': sum(not r.get('omitted_optional') for r in installed['packages']),
                                'omitted_optional_packages': sum(bool(r.get('omitted_optional')) for r in installed['packages']),
                                'installed_files': len(installed['files']), 'installed_links': len(installed['links']),
                                'workspace_packages': len(WORKSPACES), 'source_files_verified': len(source_rows),
                                'network_receipt_sha256': sha(output / 'network.json'),
                                'source_projection_sha256': sha(output / 'manifest-projection.json'),
                                'package_code_execution': False, 'lifecycle_execution': False,
                                'scope': 'Fresh exact offline install only; runtime and compatibility tests remain separate.'})
    print(json.dumps({'output': str(output), 'result_sha256': sha(output / 'result.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--specification', type=Path, default=HERE / 'inputs.json')
    args = parser.parse_args()
    install(args.inputs.resolve(), args.output.resolve(), args.specification.resolve())
