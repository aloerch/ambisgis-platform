"""Verify the complete staged owned QGIS input before and after renderer tests."""
import json
from pathlib import Path, PurePosixPath
import os

from runtime_common import sha


def verify_stage(config):
    manifest = Path(config['resource_manifest'])
    if sha(manifest) != config['resource_manifest_sha256']:
        raise ValueError('QGIS stage manifest changed')
    value = json.loads(manifest.read_text())
    root = Path(config['qgis_prefix']).resolve()
    if Path(value['prefix']).resolve() != root:
        raise ValueError('QGIS stage prefix differs')
    successor = config.get('successor', {})
    if (value.get('source_commit') != successor.get('commit') or
            value.get('source_tree') != successor.get('tree') or not successor):
        raise ValueError('QGIS stage source identity differs')
    expected = set()
    for row in value['files']:
        name = row['path']; path = PurePosixPath(name)
        if (path.is_absolute() or str(path) != name or '..' in path.parts or
                name in expected or not name):
            raise ValueError('invalid QGIS stage member')
        expected.add(name); target = root / name
        if not target.resolve().is_relative_to(root):
            raise ValueError('QGIS stage link escapes prefix')
        if 'link' in row:
            if set(row) != {'path', 'link'} or not target.is_symlink() or os.readlink(target) != row['link']:
                raise ValueError('QGIS stage link changed: ' + name)
        elif (set(row) != {'path', 'sha256', 'bytes'} or target.is_symlink() or not target.is_file()
              or any(parent.is_symlink() for parent in target.parents)
              or target.stat().st_size != row['bytes'] or sha(target) != row['sha256']):
            raise ValueError('QGIS stage bytes changed: ' + name)
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if expected != actual:
        raise ValueError('QGIS stage member set changed')
    server = (root / 'lib/libqgis_server.so').resolve()
    return {'manifest_sha256': sha(manifest), 'files_verified': len(expected),
            'source_commit': value['source_commit'], 'source_tree': value['source_tree'],
            'native_server_path': str(server), 'native_server_sha256': sha(server)}
