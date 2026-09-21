#!/usr/bin/env python3
"""Explicit online acquisition; retains owned sources, artifacts and source notices.

Run on the host with Python 3.12. This never starts services or changes a database.
An output wheel is an installation aid, not proof of its own source rebuild.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from email.parser import BytesParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib
import urllib.parse
import urllib.request
import zipfile

from inputs import BOOTSTRAP, OWNED_WHEELS, RESOLUTION_CONSTRAINTS, SOURCES, dump, extract, native_environment, patch_project, run, sha256, verify_manifest, verify_owned_tree

_ACTIVE_RECEIPT = None


def fetch(url: str, path: Path, digest: str | None = None) -> dict:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'pypi.org', 'files.pythonhosted.org', 'www.python.org'}:
        raise ValueError('Unapproved acquisition URL')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urllib.request.urlopen(url, timeout=180) as src, path.open('wb') as out:
            shutil.copyfileobj(src, out)
    actual = sha256(path)
    if digest and actual != digest:
        raise ValueError('Acquisition digest mismatch for ' + path.name)
    return {'filename': path.name, 'url': url, 'sha256': actual, 'size': path.stat().st_size}


def retain_pypi_source(root: Path, name: str, version: str) -> dict:
    key = name.lower().replace('_', '-') + '-' + version
    metadata_path = root / 'pypi-metadata' / (key + '.json')
    fetch('https://pypi.org/pypi/' + urllib.parse.quote(name) + '/' + urllib.parse.quote(version) + '/json', metadata_path)
    metadata = json.loads(metadata_path.read_text())
    sources = []
    for item in metadata['urls']:
        if item['packagetype'] == 'sdist':
            sources.append(fetch(item['url'], root / 'dependency-sources' / item['filename'], item['digests']['sha256']))
    return {'name': name, 'version': version, 'sources': sources,
            'source_status': 'retained' if sources else 'no-sdist-published',
            'license_declared': metadata['info'].get('license'),
            'license_expression': metadata['info'].get('license_expression')}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-custody', type=Path, help='Verified immutable prior downloads to seed a new acquisition; never modified')
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--custody', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--native-prefix', type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('The recorded compatibility profile requires Python 3.12')
    if args.custody.exists() or args.work.exists():
        raise ValueError('Acquisition requires fresh custody and work directories; retained inputs are never overwritten')
    args.custody.mkdir(parents=True, exist_ok=False)
    args.work.mkdir(parents=True, exist_ok=False)
    global _ACTIVE_RECEIPT
    _ACTIVE_RECEIPT = args.work / 'acquisition-receipt.json'
    reused_manifest = None
    if args.reuse_custody:
        prior = json.loads((args.reuse_custody / 'manifest.json').read_text())
        verify_manifest(args.reuse_custody, prior)
        reused_manifest = sha256(args.reuse_custody / 'manifest.json')
        for directory in ['downloads', 'dependency-sources', 'pypi-metadata', 'toolchain-sources']:
            shutil.copytree(args.reuse_custody / directory, args.custody / directory)
    log = args.custody / 'acquisition.log'
    source_receipt = []
    for name, source in SOURCES.items():
        repo = args.base / source['repository']
        origin = subprocess.check_output(['git', '-C', str(repo), 'remote', 'get-url', 'origin'], text=True).strip()
        if origin != 'https://github.com/aloerch/' + source['repository'] + '.git':
            raise ValueError('Owned source remote mismatch: ' + name)
        actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', source['commit'] + '^{commit}'], text=True).strip()
        if actual != source['commit']:
            raise ValueError('Owned source commit mismatch')
        archive = args.custody / 'owned-sources' / (name + '-' + actual + '.tar')
        archive.parent.mkdir(parents=True, exist_ok=True)
        run(['git', '-C', repo, 'archive', '--format=tar', '--output=' + str(archive), actual], log=log)
        dest = args.work / 'sources' / name
        extract(archive, dest)
        verify_owned_tree(archive, dest)
        source_receipt.append(dict(source, name=name, archive=str(archive.relative_to(args.custody)), sha256=sha256(archive)))
    pyproject = args.work / 'sources/geonode/pyproject.toml'
    baseline = subprocess.check_output(['git', '-C', str(args.base / SOURCES['geonode']['repository']), 'show', SOURCES['geonode']['commit'] + ':pyproject.toml'], text=True)
    patched, changes = patch_project(baseline)
    if pyproject.read_text() not in (baseline, patched):
        raise ValueError('Candidate source pyproject has an unexpected local change')
    pyproject.write_text(patched)
    patch_receipt = {'changes': changes, 'baseline_sha256': __import__('hashlib').sha256(baseline.encode()).hexdigest(), 'patched_sha256': sha256(pyproject)}
    dump(args.custody / 'source-inputs.json', {'sources': source_receipt, 'compatibility_patch': patch_receipt, 'resolution_constraints': RESOLUTION_CONSTRAINTS, 'reused_manifest_sha256': reused_manifest})
    deps = tomllib.loads(patched)['project']['dependencies']
    deps = [x for x in deps if not x.startswith('django-geonode-mapstore-client==')]
    requirements = args.custody / 'candidate-requirements.txt'
    requirements.write_text('\n'.join(deps + RESOLUTION_CONSTRAINTS) + '\n')
    bootstrap = args.custody / 'bootstrap-requirements.txt'
    bootstrap.write_text('\n'.join(BOOTSTRAP) + '\n')
    incoming = args.custody / 'downloads'
    incoming.mkdir(exist_ok=True)
    env = native_environment(args.native_prefix)
    # Retained CPython headers are used to compile extensions against the installed
    # host interpreter. This is not a claim to rebuild that host interpreter.
    version = '.'.join(map(str, sys.version_info[:3]))
    python_archive = args.custody / 'toolchain-sources' / ('Python-' + version + '.tgz')
    fetch('https://www.python.org/ftp/python/' + version + '/Python-' + version + '.tgz', python_archive)
    python_root = args.work / 'python-headers'
    if not python_root.exists():
        extract(python_archive, python_root)
    headers = python_root / ('Python-' + version)
    if not (headers / 'pyconfig.h').exists():
        run([headers / 'configure', '--with-ensurepip=no', '--enable-shared'], log=log, env=env, cwd=headers)
    env = native_environment(args.native_prefix, headers)
    build_env = args.work / 'build-env'
    if not (build_env / 'bin/python').exists():
        run([sys.executable, '-m', 'venv', '--without-pip', build_env], log=log)
    run([sys.executable, '-m', 'pip', 'download', '--index-url', 'https://pypi.org/simple', '--dest', incoming, '-r', bootstrap], log=log, env=env)
    run([sys.executable, '-m', 'pip', '--python', build_env / 'bin/python', 'install', '--no-index', '--find-links', incoming, '-r', bootstrap], log=log, env=env)
    py = build_env / 'bin/python'
    run([py, '-m', 'pip', 'download', '--index-url', 'https://pypi.org/simple', '--prefer-binary', '--no-build-isolation', '--dest', incoming, '-r', requirements], log=log, env=env)
    wheels = args.custody / 'wheels'
    wheels.mkdir(exist_ok=True)
    run([py, '-m', 'pip', 'wheel', '--no-index', '--find-links', incoming, '--no-build-isolation', '--wheel-dir', wheels, '-r', requirements, '-r', bootstrap], log=log, env=env)
    for item in source_receipt:
        verify_owned_tree(args.custody / item['archive'], args.work / 'sources' / item['name'],
                          patch_receipt['patched_sha256'] if item['name'] == 'geonode' else None)
    for name in SOURCES:
        run([py, '-m', 'pip', 'wheel', '--no-index', '--no-deps', '--no-build-isolation', '--wheel-dir', wheels, args.work / 'sources' / name], log=log, env=env)
    components = []
    notices = args.custody / 'notices'
    notices.mkdir(exist_ok=True)
    for wheel in sorted(wheels.glob('*.whl')):
        with zipfile.ZipFile(wheel) as zf:
            metadata_name = next(x for x in zf.namelist() if x.endswith('.dist-info/METADATA'))
            meta = BytesParser().parsebytes(zf.read(metadata_name))
            name, version = meta['Name'], meta['Version']
            files = []
            for member in zf.namelist():
                if not member.endswith('/') and (member == metadata_name or any(word in Path(member).name.lower() for word in ['license', 'copying', 'notice', 'copyright'])):
                    target = notices / (wheel.stem + '__' + member.replace('/', '__'))
                    target.write_bytes(zf.read(member)); files.append(str(target.relative_to(args.custody)))
            owned_name = next((key for key, filename in OWNED_WHEELS.items() if filename == wheel.name), None)
            provenance = ({'kind': 'owned-source-built-wheel', **SOURCES[owned_name]} if owned_name else
                          {'kind': 'retained-third-party-artifact', 'source_rebuild_claimed': False})
            components.append({'name': name, 'version': version, 'wheel': wheel.name, 'sha256': sha256(wheel), 'notices': files,
                               'provenance': provenance,
                               'frontend_scope': 'Inherited static assets packaged from owned source; no frontend rebuild or acceptance' if owned_name else None})
    external = [x for x in components if x['name'].lower().replace('_','-') not in {'geonode', 'django-geonode-mapstore-client'}]
    def retain(component):
        return retain_pypi_source(args.custody, component['name'], component['version'])
    with ThreadPoolExecutor(max_workers=6) as pool:
        source_status = list(pool.map(retain, external))
    dump(args.custody / 'python-components.json', {'components': components, 'corresponding_source_inventory': source_status,
         'limitations': ['Third-party wheels retained; full third-party source rebuild not demonstrated.',
                        'Host Python 3.12 interpreter provenance is a host prerequisite, not a rebuilt toolchain.',
                        'License declarations and notices are retained evidence, not legal approval.']})
    files = [{'path': str(p.relative_to(args.custody)), 'sha256': sha256(p), 'size': p.stat().st_size}
             for p in sorted(args.custody.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    dump(args.custody / 'manifest.json', {'schema': 1, 'profile': 'geonode-identity-headless', 'files': files})
    dump(_ACTIVE_RECEIPT, {'status': 'passed', 'manifest_sha256': sha256(args.custody / 'manifest.json')})
    print(json.dumps({'custody': str(args.custody), 'wheels': len(components), 'source_gaps': [x['name'] for x in source_status if not x['sources']]}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if _ACTIVE_RECEIPT is not None:
            dump(_ACTIVE_RECEIPT, {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)})
        raise
