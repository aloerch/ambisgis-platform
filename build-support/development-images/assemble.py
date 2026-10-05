#!/usr/bin/env python3
"""Inert, deterministic OCI assembly from an explicitly reviewed local selection.

No package manager, shell, container engine, source build or package code runs.
The selection and all referenced inventories must be reviewed before use.
"""
import argparse
import base64
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from installer import image_archive
from installer.state import checked_path, no_duplicate_keys

MAX_FILE = 8 * 1024**3
MAX_TOTAL = 32 * 1024**3
MAX_ENTRIES = 250000
ROLES = ('database', 'catalog', 'geoserver', 'gateway')
ENV = [
    'PATH=/opt/ambisgis/python/bin:/opt/ambisgis/postgres/bin:/usr/bin:/bin',
    'LD_LIBRARY_PATH=/opt/ambisgis/postgres/lib:/opt/ambisgis/support/lib:/usr/lib64:/lib64',
    'PYTHONPATH=/opt/ambisgis/modules:/opt/ambisgis/python-site',
    'PYTHONNOUSERSITE=1', 'PYTHONSAFEPATH=1', 'PYTHONDONTWRITEBYTECODE=1',
    'GDAL_DATA=/opt/ambisgis/support/share/gdal',
    'PROJ_DATA=/opt/ambisgis/support/share/proj', 'PROJ_NETWORK=OFF',
    'HOME=/tmp', 'TMPDIR=/tmp', 'LANG=C.UTF-8', 'TZ=UTC',
]


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): result.update(block)
    return result.hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or any(ord(c) < 32 for c in value) or value.startswith('/')
            or str(PurePosixPath(value)) != value or '..' in PurePosixPath(value).parts
            or any(p.startswith('.wh.') for p in PurePosixPath(value).parts)):
        raise ValueError('unsafe image member path')
    return value


def regular(path):
    path = checked_path(Path(path))
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_size > MAX_FILE:
        raise ValueError('bounded regular input required')
    return path


def reference(value):
    if set(value) != {'path', 'sha256'} or not re.fullmatch('[a-f0-9]{64}', value['sha256']):
        raise ValueError('exact file reference required')
    path = regular(value['path'])
    if digest(path) != value['sha256']: raise ValueError('input digest differs: ' + str(path))
    return path


def document(path):
    path = regular(path)
    if path.stat().st_size > 128 * 1024**2: raise ValueError('inventory exceeds bound')
    return json.loads(path.read_bytes(), object_pairs_hook=no_duplicate_keys)


def mode(value):
    if type(value) is not int or value < 0 or value & ~0o777 or value & 0o022:
        raise ValueError('unsafe source mode; special or shared-writable bits are excluded')
    return value


def link_target(name, target):
    if (not isinstance(target, str) or not target or '\\' in target
            or any(ord(c) < 32 for c in target)):
        raise ValueError('unsafe symbolic link')
    parts = [] if target.startswith('/') else name.split('/')[:-1]
    for part in target.split('/'):
        if part in ('', '.'): continue
        if part == '..':
            if not parts: raise ValueError('symbolic link escapes image root')
            parts.pop()
        else: parts.append(part)
    if not parts: raise ValueError('symbolic link targets image root')
    return '/'.join(parts)


@dataclass
class Entry:
    name: str
    kind: str
    mode: int
    component: str
    source: str
    size: int = 0
    sha256: str = ''
    target: str = ''
    path: Path | None = None
    member: str | None = None
    data: bytes | None = None
    source_mode: int | None = None

    def inventory(self):
        value = {k: getattr(self, k) for k in ('kind', 'mode', 'component', 'source')}
        if self.kind == 'file': value.update(bytes=self.size, sha256=self.sha256)
        if self.kind == 'symlink': value['target'] = self.target
        if self.source_mode is not None:
            value['source_mode'] = self.source_mode
            value['mode_projection'] = 'root-owned image: directories/executable files 0755; ordinary files 0644'
        return value


def tree(component):
    root = checked_path(Path(component['root']))
    if not root.is_dir(): raise ValueError('source tree is missing')
    inventory = document(reference(component['inventory']))
    if set(inventory) != {'schema_version', 'entries'} or inventory['schema_version'] != 1:
        raise ValueError('unsupported exact tree inventory')
    expected = inventory['entries']
    actual = {}
    def visit(directory, prefix=''):
        for child in sorted(os.scandir(directory), key=lambda c: c.name):
            name = relative(prefix + child.name)
            metadata = child.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                actual[name] = {'kind': 'symlink', 'target': os.readlink(child.path)}
            elif stat.S_ISDIR(metadata.st_mode):
                actual[name] = {'kind': 'directory', 'mode': stat.S_IMODE(metadata.st_mode)}
                visit(child.path, name + '/')
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_size > MAX_FILE: raise ValueError('source file exceeds bound')
                actual[name] = {'kind': 'file', 'mode': stat.S_IMODE(metadata.st_mode),
                                'bytes': metadata.st_size, 'sha256': digest(child.path)}
            else: raise ValueError('source tree contains a special file')
            if len(actual) > MAX_ENTRIES: raise ValueError('source membership exceeds bound')
    visit(root)
    if actual != expected: raise ValueError('source tree differs from complete inventory: ' + component['id'])
    destination = component['destination']
    if destination: relative(destination)
    result = []
    for name, item in actual.items():
        mapped = relative((destination + '/' if destination else '') + name)
        kind = item['kind']; original = None if kind == 'symlink' else mode(item['mode'])
        permissions = 0o777 if kind == 'symlink' else 0o755 if kind == 'directory' or original & 0o111 else 0o644
        result.append(Entry(mapped, kind, permissions, component['id'], name,
                            size=item.get('bytes', 0), sha256=item.get('sha256', ''),
                            target=item.get('target', ''), path=root / name, source_mode=original))
    return result


def wheel(component):
    path = reference(component['archive']); destination = relative(component['destination'])
    entries, names, expanded = [], set(), 0
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            name = relative(item.filename.rstrip('/'))
            if name in names: raise ValueError('duplicate wheel member')
            names.add(name)
            permissions = (item.external_attr >> 16) & 0xffff
            if item.flag_bits & 1 or (stat.S_IFMT(permissions) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError('encrypted or linked wheel member is excluded')
            if permissions & 0o7000: raise ValueError('special wheel mode is excluded')
            if item.is_dir(): continue
            expanded += item.file_size
            if item.file_size > MAX_FILE or expanded > MAX_TOTAL or len(names) > MAX_ENTRIES:
                raise ValueError('wheel expansion exceeds bound')
            data = archive.read(item)
            # Purelib/platlib retain their import semantics. Scripts, headers and
            # other wheel data are retained separately, outside executable PATH.
            parts = name.split('/')
            if parts[0] in ('tests', 'test'):
                # Several retained distributions ship unrelated top-level test
                # packages. Preserve each under its distribution's data area
                # instead of reproducing pip's order-dependent overwrites.
                mapped = 'opt/ambisgis/wheel-data/' + component['id'] + '/' + name
            elif len(parts) > 2 and parts[0].endswith('.data'):
                if parts[1] in ('purelib', 'platlib'): mapped = destination + '/' + '/'.join(parts[2:])
                else: mapped = 'opt/ambisgis/wheel-data/' + component['id'] + '/' + '/'.join(parts[1:])
            else: mapped = destination + '/' + name
            entries.append(Entry(relative(mapped), 'file', 0o755 if permissions & 0o111 else 0o644,
                                 component['id'], name, len(data), hashlib.sha256(data).hexdigest(),
                                 path=path, member=item.filename, source_mode=permissions & 0o777))
        records = [x for x in names if len(x.split('/')) == 2 and x.endswith('.dist-info/RECORD')]
        if len(records) != 1: raise ValueError('one wheel RECORD required')
        rows = list(csv.reader(io.StringIO(archive.read(records[0]).decode())))
        record_names = set()
        for row in rows:
            if len(row) != 3 or row[0] in record_names: raise ValueError('invalid wheel RECORD')
            name, expected, size = row; relative(name); record_names.add(name)
            data = archive.read(name)
            if name == records[0] and not expected and not size: continue
            actual = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            if expected != 'sha256=' + actual or size != str(len(data)):
                raise ValueError('wheel RECORD content differs')
        if record_names != {x.filename for x in archive.infolist() if not x.is_dir()}:
            raise ValueError('wheel RECORD membership differs')
    return entries


def single_file(component):
    path = reference(component['file'])
    return [Entry(relative(component['destination']), 'file', mode(component['mode']),
                  component['id'], path.name, path.stat().st_size, digest(path), path=path)]


def mapped_files(component):
    """Explicit projections of retained package members and generated launchers."""
    inventory = document(reference(component['inventory']))
    if set(inventory) != {'schema_version', 'entries'} or inventory['schema_version'] != 1:
        raise ValueError('unsupported mapped inventory')
    result = []
    for name, item in inventory['entries'].items():
        relative(name)
        if item['kind'] == 'file':
            if set(item) != {'kind', 'file', 'mode', 'origin'}: raise ValueError('mapped file fields differ')
            path = reference(item['file'])
            result.append(Entry(name, 'file', mode(item['mode']), component['id'], item['origin'],
                                path.stat().st_size, item['file']['sha256'], path=path))
        elif item['kind'] == 'symlink':
            if set(item) != {'kind', 'target', 'origin'}: raise ValueError('mapped symlink fields differ')
            result.append(Entry(name, 'symlink', 0o777, component['id'], item['origin'], target=item['target']))
        else: raise ValueError('mapped entries must be files or symbolic links')
    return result


def close_entries(entries):
    values = {}
    for entry in entries:
        relative(entry.name)
        if entry.name in values:
            previous = values[entry.name]
            if entry.kind == previous.kind == 'directory' and entry.mode == previous.mode: continue
            raise ValueError('image member collision: ' + entry.name)
        values[entry.name] = entry
    for entry in list(values.values()):
        for parent in PurePosixPath(entry.name).parents:
            if str(parent) == '.': continue
            name = str(parent)
            if name in values and values[name].kind != 'directory':
                raise ValueError('image member has a nondirectory ancestor')
            if name not in values: values[name] = Entry(name, 'directory', 0o755, 'assembler', 'implicit parent')
    # Resolve through intermediate symlinks as an image reader would, never
    # through the host filesystem. No dangling references or cycles are allowed.
    def resolve(name, chain=()):
        if len(chain) > 64 or name in chain: raise ValueError('cyclic image symbolic link')
        parts = name.split('/')
        for index in range(len(parts)):
            prefix = '/'.join(parts[:index+1]); item = values.get(prefix)
            if item is None: raise ValueError('dangling image symbolic link: ' + name)
            if item.kind == 'symlink':
                suffix = '/'.join(parts[index+1:]); target = link_target(prefix, item.target)
                return resolve(target + ('/' + suffix if suffix else ''), (*chain, name))
            if index + 1 < len(parts) and item.kind != 'directory': raise ValueError('link traversal through file')
        return name
    for name, entry in values.items():
        if entry.kind == 'symlink': resolve(name)
        elif entry.mode & (0o555 if entry.kind == 'directory' else 0o444) != (0o555 if entry.kind == 'directory' else 0o444):
            raise ValueError('root-owned image member is inaccessible to keep-id users: ' + name)
    if sum(x.size for x in values.values()) > MAX_TOTAL or len(values) > MAX_ENTRIES:
        raise ValueError('image root exceeds bound')
    return dict(sorted(values.items()))


def stream(entry):
    if entry.data is not None: return io.BytesIO(entry.data)
    if entry.member is not None:
        with zipfile.ZipFile(regular(entry.path)) as archive:
            return io.BytesIO(archive.read(entry.member))
    return regular(entry.path).open('rb')


def layer(path, entries, epoch):
    with tarfile.open(path, 'w', format=tarfile.PAX_FORMAT) as archive:
        for name, entry in entries.items():
            info = tarfile.TarInfo(name); info.uid = info.gid = 0
            info.uname = info.gname = ''; info.mtime = epoch; info.mode = entry.mode
            if entry.kind == 'directory': info.type = tarfile.DIRTYPE; archive.addfile(info)
            elif entry.kind == 'symlink': info.type = tarfile.SYMTYPE; info.linkname = entry.target; archive.addfile(info)
            else:
                info.size = entry.size
                with stream(entry) as source:
                    check = hashlib.sha256()
                    # Hash exactly the bytes supplied to tar, catching source
                    # drift between initial inventory and the actual archive.
                    class Checked:
                        def read(self, size=-1):
                            data = source.read(size); check.update(data); return data
                    archive.addfile(info, Checked())
                    if source.read(1) or check.hexdigest() != entry.sha256:
                        raise ValueError('source changed during layer assembly')


def blob_descriptor(data, media_type):
    return {'mediaType': media_type, 'digest': 'sha256:' + hashlib.sha256(data).hexdigest(), 'size': len(data)}


def oci(path, layer_path, role, revision, source_hash, components, epoch):
    layer_hash = digest(layer_path)
    labels = {'org.opencontainers.image.revision': revision,
              'org.ambisgis.source-manifest-sha256': source_hash,
              'org.ambisgis.development-role': role}
    for component in components:
        revision_value = component.get('revision')
        revisions = revision_value if isinstance(revision_value, dict) else {component['id']: revision_value}
        labels.update({'org.ambisgis.component.' + name + '.revision': commit
                       for name, commit in revisions.items() if commit})
    config = encoded({'architecture': 'amd64', 'os': 'linux',
                      'config': {'Env': ENV, 'Entrypoint': ['/opt/ambisgis/bin/service'],
                                 'Cmd': [role], 'WorkingDir': '/tmp', 'Labels': labels},
                      'rootfs': {'type': 'layers', 'diff_ids': ['sha256:' + layer_hash]}})
    manifest = encoded({'schemaVersion': 2, 'mediaType': image_archive.MANIFEST,
                        'config': blob_descriptor(config, image_archive.CONFIG),
                        'layers': [{'mediaType': image_archive.LAYER, 'digest': 'sha256:' + layer_hash,
                                    'size': layer_path.stat().st_size}]})
    descriptor = blob_descriptor(manifest, image_archive.MANIFEST)
    descriptor['platform'] = {'architecture': 'amd64', 'os': 'linux'}
    image_reference = 'localhost/ambisgis/' + role + ':' + revision
    descriptor['annotations'] = {'org.opencontainers.image.ref.name': image_reference}
    index = encoded({'schemaVersion': 2, 'mediaType': image_archive.INDEX, 'manifests': [descriptor]})
    members = {'oci-layout': encoded({'imageLayoutVersion': '1.0.0'}), 'index.json': index,
               'blobs/sha256/' + hashlib.sha256(config).hexdigest(): config,
               'blobs/sha256/' + hashlib.sha256(manifest).hexdigest(): manifest,
               'blobs/sha256/' + layer_hash: layer_path}
    with tarfile.open(path, 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name, value in sorted(members.items()):
            info = tarfile.TarInfo(name); info.mode = 0o644; info.mtime = epoch
            info.size = value.stat().st_size if isinstance(value, Path) else len(value)
            with (value.open('rb') if isinstance(value, Path) else io.BytesIO(value)) as source: archive.addfile(info, source)
    record = {'path': path.name, 'sha256': digest(path), 'reference': image_reference,
              'image_id': 'sha256:' + hashlib.sha256(config).hexdigest(),
              'source_manifest_sha256': source_hash, 'manifest_digest': descriptor['digest']}
    image_archive.verify(path, record, revision)
    return record


def assemble(selection_path, output):
    selection_path = regular(selection_path); selection = document(selection_path)
    if set(selection) != {'schema_version', 'platform_revision', 'epoch', 'components', 'images'} or selection['schema_version'] != 1:
        raise ValueError('unsupported assembly selection')
    if not re.fullmatch('[a-f0-9]{40}', selection['platform_revision']): raise ValueError('exact platform revision required')
    if type(selection['epoch']) is not int or not 0 <= selection['epoch'] <= 0xffffffff: raise ValueError('bounded fixed epoch required')
    if set(selection['images']) != set(ROLES): raise ValueError('four development images required')
    output = checked_path(Path(output))
    if output.exists(): raise ValueError('assembly output must be fresh')
    components, entries = {}, {}
    for component in selection['components']:
        identifier = component['id']
        if not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}', identifier) or identifier in components:
            raise ValueError('unique bounded component identity required')
        kind = component['kind']
        expected = {'id', 'kind', 'provenance', 'revision'} | {
            'tree': {'root', 'inventory', 'destination'}, 'wheel': {'archive', 'destination'},
            'file': {'file', 'destination', 'mode'}, 'mapped': {'inventory'}}[kind]
        if set(component) != expected: raise ValueError('component fields differ')
        revisions = component['revision'] if isinstance(component['revision'], dict) else {identifier: component['revision']}
        for name, commit in revisions.items():
            if not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}', name) or (commit is not None and not re.fullmatch('[a-f0-9]{40}', commit)):
                raise ValueError('component revision must be an exact owned source commit')
        if not component['provenance']: raise ValueError('component source/rights provenance is required')
        for item in component['provenance']: reference(item)
        components[identifier] = component
        entries[identifier] = {'tree': tree, 'wheel': wheel, 'file': single_file, 'mapped': mapped_files}[kind](component)
    selected = set()
    images = {}
    for role, identifiers in selection['images'].items():
        if not identifiers or len(identifiers) != len(set(identifiers)) or any(x not in components for x in identifiers):
            raise ValueError('invalid image component selection')
        selected.update(identifiers)
        images[role] = close_entries([entry for identifier in identifiers for entry in entries[identifier]])
    if selected != set(components): raise ValueError('unreferenced component in selection')
    source = {'schema_version': 1, 'platform_revision': selection['platform_revision'],
              'selection_sha256': digest(selection_path), 'components': selection['components'],
              'images': {role: {name: entry.inventory() for name, entry in rows.items()} for role, rows in images.items()},
              'scope': 'Inert artifact assembly. Runtime, ABI relocation and installation acceptance remain unverified.'}
    source_bytes = encoded(source); source_hash = hashlib.sha256(source_bytes).hexdigest()
    output.mkdir(mode=0o700, parents=True)
    (output / 'source-manifest.json').write_bytes(source_bytes)
    result = {'schema_version': 1, 'platform_revision': selection['platform_revision'],
              'selection_sha256': digest(selection_path), 'assembler_sha256': digest(__file__),
              'source_manifest_sha256': source_hash, 'images': {}, 'runtime_executed': False,
              'full_installation_acceptance': False, 'distribution_approved': False}
    for role, rows in images.items():
        archive = output / (role + '.oci.tar'); layer_path = output / (role + '.layer.tar')
        layer(layer_path, rows, selection['epoch'])
        result['images'][role] = oci(archive, layer_path, role, selection['platform_revision'], source_hash,
                                     [components[x] for x in selection['images'][role]], selection['epoch'])
        layer_path.unlink()  # Only this fresh output's intermediate tar.
    (output / 'result.json').write_bytes(encoded(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(assemble(args.selection, args.output), sort_keys=True))
