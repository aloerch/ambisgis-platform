#!/usr/bin/env python3
"""Restore owned GeoNode/client sources, rebuild their wheels and install offline.

Dependencies use retained wheels; this is not a full dependency source rebuild.
For network-denial evidence run this command in an independently denied namespace.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

from inputs import OWNED_WHEELS, SOURCES, dump, extract, native_environment, patch_project, run, sha256, verify_manifest, verify_owned_tree


_ACTIVE_RECEIPT = None

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict-verifier', action='store_true', help='Apply the guarded opt-in GeoNode verifier source repair before rebuilding')
    parser.add_argument('--strict-roles', action='store_true', help='Layer guarded read-only role authority on the strict verifier before rebuilding')
    parser.add_argument('--custody', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--native-prefix', required=True, type=Path)
    args = parser.parse_args()
    if args.strict_roles and not args.strict_verifier:
        parser.error('--strict-roles requires --strict-verifier')
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('The recorded compatibility profile requires Python 3.12')
    if args.work.exists():
        raise ValueError('Restore requires a fresh work directory; previous source and wheels are never reused')
    args.work.mkdir(parents=True, exist_ok=False)
    global _ACTIVE_RECEIPT
    _ACTIVE_RECEIPT = args.work / 'build-receipt.json'
    manifest = json.loads((args.custody / 'manifest.json').read_text())
    verify_manifest(args.custody, manifest)
    receipt = json.loads((args.custody / 'source-inputs.json').read_text())
    log = args.work / 'build.log'
    env = native_environment(args.native_prefix)
    env['PIP_NO_INDEX'] = '1'
    env['PIP_FIND_LINKS'] = str(args.custody / 'wheels')
    if {x['name'] for x in receipt['sources']} != set(SOURCES) or len(receipt['sources']) != len(SOURCES):
        raise ValueError('Unexpected source receipt set')
    native_version = subprocess.check_output([str(args.native_prefix / 'bin/gdal-config'), '--version'], text=True).strip()
    if native_version != '3.10.3':
        raise ValueError('Compatibility profile requires retained native GDAL 3.10.3')
    source_paths = {}
    for item in receipt['sources']:
        expected = SOURCES[item['name']]
        if item['commit'] != expected['commit'] or item['repository_id'] != expected['repository_id']:
            raise ValueError('Unexpected owned source identity')
        expected_archive = 'owned-sources/' + item['name'] + '-' + expected['commit'] + '.tar'
        if item['archive'] != expected_archive:
            raise ValueError('Unexpected source archive path')
        dest = args.work / 'sources' / item['name']
        if not dest.exists():
            extract(args.custody / item['archive'], dest)
        source_paths[item['name']] = str(dest)
    project = args.work / 'sources/geonode/pyproject.toml'
    if sha256(project) == receipt['compatibility_patch']['baseline_sha256']:
        patched, _ = patch_project(project.read_text())
        project.write_text(patched)
    if sha256(project) != receipt['compatibility_patch']['patched_sha256']:
        raise ValueError('Unexpected local source changes in compatibility pyproject')
    for item in receipt['sources']:
        verify_owned_tree(args.custody / item['archive'], Path(source_paths[item['name']]),
                          receipt['compatibility_patch']['patched_sha256'] if item['name'] == 'geonode' else None)
    source_repair = None
    role_source_repair = None
    if args.strict_verifier:
        import verifier_repair
        geonode_source = Path(source_paths['geonode'])
        source_repair = verifier_repair.apply(geonode_source)
        allowed_changes = verifier_repair.expected_files()
        source_repair['recipe_inputs'] = [
            {'path': str(Path(verifier_repair.__file__)), 'sha256': sha256(Path(verifier_repair.__file__))},
            {'path': str(Path(__file__).with_name('verifier_tests.py')), 'sha256': sha256(Path(__file__).with_name('verifier_tests.py'))},
        ]
        source_repair['expected_files'] = dict(allowed_changes)
        for item in receipt['sources']:
            verify_owned_tree(args.custody / item['archive'], Path(source_paths[item['name']]),
                              receipt['compatibility_patch']['patched_sha256'] if item['name'] == 'geonode' else None,
                              allowed_changes=allowed_changes if item['name'] == 'geonode' else None)
        source_repair['post_patch_tree_verification'] = 'passed'
        if args.strict_roles:
            import roles_repair
            role_source_repair = roles_repair.apply(geonode_source)
            allowed_changes.update(roles_repair.expected_files())
            role_source_repair['recipe_inputs'] = [
                {'path': str(Path(roles_repair.__file__)), 'sha256': sha256(Path(roles_repair.__file__))},
                {'path': str(Path(__file__).with_name('roles_tests.py')), 'sha256': sha256(Path(__file__).with_name('roles_tests.py'))},
            ]
            role_source_repair['expected_files'] = dict(allowed_changes)
            for item in receipt['sources']:
                verify_owned_tree(args.custody / item['archive'], Path(source_paths[item['name']]),
                                  receipt['compatibility_patch']['patched_sha256'] if item['name'] == 'geonode' else None,
                                  allowed_changes=allowed_changes if item['name'] == 'geonode' else None)
            role_source_repair['post_patch_tree_verification'] = 'passed'
    venv = args.work / 'venv'
    if not (venv / 'bin/python').exists():
        run([sys.executable, '-m', 'venv', '--without-pip', venv], log=log, env=env)
    run([sys.executable, '-m', 'pip', '--python', venv / 'bin/python', 'install', '--no-index', '--find-links', args.custody / 'wheels', '-r', args.custody / 'bootstrap-requirements.txt'], log=log, env=env)
    py = venv / 'bin/python'
    output = args.work / 'owned-wheels'
    output.mkdir(exist_ok=True)
    for name in SOURCES:
        run([py, '-m', 'pip', 'wheel', '--no-index', '--no-deps', '--no-build-isolation', '--wheel-dir', output, args.work / 'sources' / name], log=log, env=env)
    inventory = json.loads((args.custody / 'python-components.json').read_text())
    lock = args.work / 'requirements.lock'
    lines = []
    for component in inventory['components']:
        normalized = component['name'].lower().replace('_', '-')
        if normalized in {'geonode', 'django-geonode-mapstore-client'}:
            continue
        lines.append(component['name'] + '==' + component['version'] + ' --hash=sha256:' + component['sha256'])
    lock.write_text('\n'.join(sorted(lines)) + '\n')
    run([py, '-m', 'pip', 'install', '--no-index', '--no-deps', '--require-hashes', '--find-links', args.custody / 'wheels', '-r', lock], log=log, env=env)
    if {p.name for p in output.iterdir()} != set(OWNED_WHEELS.values()):
        raise ValueError('Unexpected owned wheel output set')
    for filename in OWNED_WHEELS.values():
        wheel = output / filename
        run([py, '-m', 'pip', 'install', '--no-index', '--no-deps', '--force-reinstall', wheel], log=log, env=env)
    run([py, '-m', 'pip', 'check'], log=log, env=env)
    run([py, '-c', 'from osgeo import gdal; import geonode, geonode_mapstore_client; print(gdal.VersionInfo()); print(geonode.__file__); print(geonode_mapstore_client.__file__)'], log=log, env=env)
    installed = json.loads(subprocess.check_output([str(py), '-m', 'pip', 'list', '--format=json'], env=env, text=True))
    source_hashes = {name: {str(p.relative_to(Path(path))): sha256(p) for p in sorted(Path(path).rglob('*.py'))} for name, path in source_paths.items()}
    dump(args.work / 'build-receipt.json', {
        'status': 'passed', 'profile': 'geonode-identity-headless', 'python': str(py), 'sources': receipt['sources'],
        'source_paths': source_paths, 'source_python_hashes': source_hashes,
        'compatibility_patch': receipt['compatibility_patch'], 'source_repair': source_repair, 'role_source_repair': role_source_repair, 'installed': installed,
        'native_prefix': str(args.native_prefix),
        'native_libraries': [{'path': str(p), 'sha256': sha256(p.resolve())} for p in [args.native_prefix / 'lib/libgdal.so', args.native_prefix / 'lib/libpq.so'] if p.exists()], 'native_gdal_version': native_version,
        'manifest_sha256': sha256(args.custody / 'manifest.json'), 'requirements_lock_sha256': sha256(lock),
        'owned_wheels': [{'path': str(p), 'sha256': sha256(p)} for p in sorted(output.glob('*.whl'))],
        'pip_check': 'passed', 'imports': 'passed',
        'network_policy': 'pip --no-index; external network denial must be recorded separately',
        'scope': 'Owned GeoNode/client wheel rebuild and dependency-wheel restore; not complete dependency or toolchain source rebuild.',
        'frontend_scope': 'Owned Python packages include inherited static assets; frontend source build, asset closure, browser and accessibility acceptance remain deferred.',
        'owned_install_provenance': {name: {**SOURCES[name], 'installed_wheel': str(output / filename), 'sha256': sha256(output / filename)} for name, filename in OWNED_WHEELS.items()},
    })
    print(json.dumps({'python': str(py), 'receipt': str(args.work / 'build-receipt.json')}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if _ACTIVE_RECEIPT is not None:
            dump(_ACTIVE_RECEIPT, {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)})
        raise
