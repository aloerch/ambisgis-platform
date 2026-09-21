"""Retained inputs and guarded source changes for the GeoNode identity probe.

This is a local compatibility profile, not a product dependency approval.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

SOURCES = {
    "geonode": {
        "repository": "ambisgis-geonode", "repository_id": 1376927978,
        "commit": "a1db97e81dfc26c16bb4ee1a5d2b408877af66c9",
    },
    "mapstore-client": {
        "repository": "ambisgis-mapstore-client", "repository_id": 1376928013,
        "commit": "7ca4822125b67999c97cb4aa1faa84b8a28eee9b",
    },
}
OWNED_WHEELS = {
    'geonode': 'geonode-5.1.0.post1-py3-none-any.whl',
    'mapstore-client': 'django_geonode_mapstore_client-5.1.0-py3-none-any.whl',
}
# The older binary-only 0.14.0 selection imports symbols removed by Django 5.
# 0.14.7 remains inside the candidate's declared <0.15.0 range.
RESOLUTION_CONSTRAINTS = ['django-tastypie==0.14.7']
BOOTSTRAP = ["pip==26.2.1", "setuptools==82.0.1", "wheel==0.45.1", "numpy==1.26.4", "packaging==26.3"]
PATCHES = [
    ('"GDAL==3.8.4"', '"GDAL==3.10.3"',
     "Match the retained source-built GDAL 3.10.3 native library; candidate compatibility change, not approved product pin."),
    ('    "pylibmc==1.6.3",\n', '',
     "Headless profile uses Django local-memory caches; memcached and its native binding are omitted."),
    ('    "uWSGI==2.0.30",\n', '',
     "Headless loopback WSGI probe uses the Python WSGI server; the production process server is outside this slice."),
]


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def run(argv, *, log: Path, env=None, cwd=None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a') as stream:
        stream.write(json.dumps([str(x) for x in argv]) + '\n')
        stream.flush()
        subprocess.run([str(x) for x in argv], cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)


def patch_project(text: str) -> tuple[str, list[dict]]:
    changes = []
    for before, after, reason in PATCHES:
        if text.count(before) != 1:
            raise ValueError('Guarded candidate dependency patch does not match exactly once: ' + before.strip())
        text = text.replace(before, after, 1)
        changes.append({'before': before.strip(), 'after': after.strip(), 'reason': reason})
    return text, changes


def extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as tf:
        tf.extractall(dest, filter='data')


def native_environment(prefix: Path, headers: Path | None = None) -> dict:
    env = os.environ.copy()
    # A build must not inherit alternate package indexes or remote pip links.
    for key in list(env):
        if key.startswith('PIP_'):
            env.pop(key)
    for key in ['PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONUSERBASE']:
        env.pop(key, None)
    env['PYTHONNOUSERSITE'] = '1'
    env.update(PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_NO_CACHE_DIR='1')
    env['PATH'] = str(prefix / 'bin') + os.pathsep + env.get('PATH', '')
    env['LD_LIBRARY_PATH'] = str(prefix / 'lib')
    env['GDAL_CONFIG'] = str(prefix / 'bin/gdal-config')
    env['GDAL_DATA'] = str(prefix / 'share/gdal')
    env['PROJ_DATA'] = str(prefix / 'share/proj')
    env['CFLAGS'] = '-I' + str(prefix / 'include')
    env['LDFLAGS'] = '-L' + str(prefix / 'lib') + ' -Wl,-rpath,' + str(prefix / 'lib')
    if headers:
        env['CFLAGS'] += ' -I' + str(headers / 'Include') + ' -I' + str(headers)
        env['CXXFLAGS'] = env['CFLAGS']
        env['CPPFLAGS'] = env['CFLAGS']
    return env


def verify_manifest(root: Path, manifest: dict) -> None:
    expected = set()
    for item in manifest['files']:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts or str(relative) in expected:
            raise ValueError('Invalid or duplicate retained inventory path')
        expected.add(str(relative))
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256(path) != item['sha256']:
            raise ValueError('Retained input digest mismatch: ' + item['path'])
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in retained input root')
        if path.is_file() and path != root / 'manifest.json':
            actual.add(str(path.relative_to(root)))
    if actual != expected:
        raise ValueError('Retained inventory file set does not match manifest')


def verify_owned_tree(archive: Path, dest: Path, patched_project_hash: str | None = None, *, allowed_changes: dict[str, str] | None = None) -> None:
    """Reject missing, extra, linked or changed source before executing build code."""
    expected_names = set()
    allowed_changes = allowed_changes or {}
    for relative in allowed_changes:
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or str(path) != relative:
            raise ValueError('Invalid approved source repair path')
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            if member.issym() or member.islnk():
                raise ValueError('Unexpected link in candidate owned-source archive')
            if not member.isfile():
                continue
            expected_names.add(member.name)
            path = dest / member.name
            if path.is_symlink() or not path.is_file():
                raise ValueError('Missing or linked retained source file: ' + member.name)
            expected = hashlib.sha256(tf.extractfile(member).read()).hexdigest()
            if member.name == 'pyproject.toml' and patched_project_hash is not None:
                expected = patched_project_hash
            if member.name in allowed_changes:
                expected = allowed_changes[member.name]
            if sha256(path) != expected:
                raise ValueError('Owned source changed outside guarded patch: ' + member.name)
    for relative, expected in allowed_changes.items():
        path = dest / relative
        if path.is_symlink() or not path.is_file() or sha256(path) != expected:
            raise ValueError('Approved source repair digest mismatch: ' + relative)
    expected_names.update(allowed_changes)
    actual_names = set()
    for path in dest.rglob('*'):
        if path.is_symlink():
            raise ValueError('Unexpected symlink in owned source tree')
        if path.is_file():
            actual_names.add(str(path.relative_to(dest)))
    if actual_names != expected_names:
        raise ValueError('Owned source file set differs from retained archive')
