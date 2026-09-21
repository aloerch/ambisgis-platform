"""Verify owned installed Python modules against the recorded built wheels."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(python):
    python = Path(python).absolute()
    receipt_path = python.parent.parent.parent / 'build-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('pip_check') != 'passed' or receipt.get('imports') != 'passed':
        raise ValueError('isolated backend build has not passed dependency/import checks')
    if Path(receipt['python']).absolute() != python:
        raise ValueError('Python path differs from owned build receipt')
    site = Path(subprocess.check_output([str(python), '-I', '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'], text=True).strip())
    modules, wheels = {}, []
    for item in receipt['owned_wheels']:
        wheel = Path(item['path'])
        if digest(wheel) != item['sha256']: raise ValueError('owned wheel changed')
        wheels.append({'name': wheel.name, 'sha256': item['sha256']})
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.endswith('/') or '.dist-info/' in name: continue
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts or any(part.endswith('.data') for part in relative.parts):
                    raise ValueError('unsupported owned wheel installation layout')
                installed = site / relative
                if installed.is_symlink() or not installed.is_file(): raise ValueError('owned wheel file is absent or a symlink')
                actual = digest(installed)
                expected = hashlib.sha256(archive.read(name)).hexdigest()
                if actual != expected: raise ValueError('installed owned file differs from built wheel: ' + name)
                modules[name] = actual
    for package in ('geonode', 'geonode_mapstore_client'):
        if package + '/__init__.py' not in modules: raise ValueError('required owned backend package absent')
        for path in (site / package).rglob('*'):
            if path.is_symlink(): raise ValueError('symlink in owned package tree')
            if not path.is_file(): continue
            if '__pycache__' in path.parts and path.suffix == '.pyc': continue
            if str(path.relative_to(site)) not in modules: raise ValueError('unrecorded owned package file installed')
    return {'build_receipt': str(receipt_path), 'build_receipt_sha256': digest(receipt_path),
            'python': str(python), 'site_packages': str(site), 'owned_wheels': wheels,
            'verified_owned_files': len(modules), 'files': modules,
            'scope': 'Owned installed wheel files; dependency binaries/toolchain remain separately inventoried.'}
