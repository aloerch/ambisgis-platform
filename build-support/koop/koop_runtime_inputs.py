"""No-execution identity guards for the selected contract and generated corpus."""
import hashlib
import json
from pathlib import Path
import subprocess

CONTRACT = 'a31a285b5e659a08bc6c18c393cfe5a8581bf293'


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''): value.update(data)
    return value.hexdigest()


def verify_blob(path, expected):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('selected contract input missing/nonregular')
    contents = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(contents)).encode() + b'\0' + contents).hexdigest()
    if blob != expected: raise ValueError('shared contract file differs from reviewed checkpoint')
    return {'git_blob': blob, 'sha256': digest(path)}


def contract_bindings(root):
    root = Path(root)
    listing = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', CONTRACT, '--',
        'plan/tools/native_contracts.py', 'plan/examples/layer.json', 'plan/contracts'], text=True)
    bindings = []
    expected = set()
    for line in listing.splitlines():
        metadata, relative = line.split('\t')
        mode, kind, blob = metadata.split()
        if mode != '100644' or kind != 'blob': raise ValueError('unexpected selected contract mode')
        record = verify_blob(root / relative, blob)
        bindings.append({'path': relative, **record})
        if relative.startswith('plan/contracts/'): expected.add(relative)
    actual = {p.relative_to(root).as_posix() for p in (root / 'plan/contracts').rglob('*') if p.is_file()}
    if expected != actual or len(bindings) < 3: raise ValueError('selected contract file set differs')
    return bindings


def corpus_binding(root, manifest_sha256):
    root = Path(root)
    manifest_path, payload = root / 'manifest.json', root / 'addresses.ndjson'
    if any(not p.is_file() or p.is_symlink() for p in (manifest_path, payload)):
        raise ValueError('selected corpus input missing/nonregular')
    if digest(manifest_path) != manifest_sha256: raise ValueError('selected corpus manifest identity differs')
    manifest = json.loads(manifest_path.read_text())
    row = manifest['files']['addresses.ndjson']
    if payload.stat().st_size != row['bytes'] or digest(payload) != row['sha256']:
        raise ValueError('selected corpus payload identity differs')
    return manifest
