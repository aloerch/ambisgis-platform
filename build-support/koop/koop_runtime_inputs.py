"""No-execution identity guards for the selected contract and generated corpus."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

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


def node_binding(archive_path, extracted):
    """Verify actual runtime files/modes/links against the retained tool archive."""
    extracted = Path(extracted).resolve()
    rows, expected = [], set()
    with tarfile.open(archive_path) as archive:
        for member in archive:
            relative = Path(member.name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('unsafe Node archive path')
            path = extracted / relative
            if member.isdir(): continue
            if not path.resolve().is_relative_to(extracted): raise ValueError('Node runtime path escapes custody')
            if member.issym():
                if not path.is_symlink() or str(path.readlink()) != member.linkname:
                    raise ValueError('Node runtime link differs')
                rows.append({'path': member.name, 'link': member.linkname})
            elif member.isfile():
                if not path.is_file() or path.is_symlink() or path.stat().st_size != member.size:
                    raise ValueError('Node runtime file identity differs')
                expected_sha = hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest()
                if digest(path) != expected_sha or path.stat().st_mode & 0o777 != member.mode & 0o777:
                    raise ValueError('Node runtime bytes/mode differ')
                rows.append({'path': member.name, 'sha256': expected_sha, 'bytes': member.size, 'mode': member.mode & 0o777})
            else:
                raise ValueError('unsupported Node archive member')
            expected.add(member.name)
    actual = {p.relative_to(extracted).as_posix() for p in extracted.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != expected: raise ValueError('Node runtime file set differs')
    return rows
