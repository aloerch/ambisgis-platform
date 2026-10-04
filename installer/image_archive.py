"""Bounded OCI image-layout verification before any container-runtime invocation.

This guard does not make an affected runtime safe. Runtime fixes and sandbox
acceptance remain independent requirements. No layer is extracted or executed.
"""
import gzip
import hashlib
import json
from pathlib import PurePosixPath
import re
import tarfile
import zlib

from .state import InstallError

MANIFEST = 'application/vnd.oci.image.manifest.v1+json'
CONFIG = 'application/vnd.oci.image.config.v1+json'
INDEX = 'application/vnd.oci.image.index.v1+json'
LAYER = 'application/vnd.oci.image.layer.v1.tar'
JSON_LIMIT = 8 * 1024 * 1024
ARCHIVE_LIMIT = 64 * 1024 ** 3
EXPANDED_LIMIT = 64 * 1024 ** 3


def metadata(value, depth=0):
    """Reject checkpoint/restore annotation families at archive and inspect boundaries."""
    if depth > 32: raise InstallError('Image metadata nesting exceeded its bound.')
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str): raise InstallError('Image metadata keys must be text.')
            if 'checkpoint' in key.lower() or 'restore' in key.lower():
                raise InstallError('Checkpoint/restore image metadata is forbidden in the developer profile.')
            metadata(item, depth + 1)
    elif isinstance(value, list):
        for item in value: metadata(item, depth + 1)


def parse(raw):
    if len(raw) > JSON_LIMIT: raise InstallError('OCI JSON metadata exceeded its bound.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise InstallError('Duplicate OCI JSON metadata key.')
            result[key] = value
        return result
    def constant(_): raise InstallError('Nonfinite OCI JSON metadata is forbidden.')
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise InstallError('Invalid OCI JSON metadata.') from error
    metadata(value)
    return value


def keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise InstallError('OCI metadata has missing or unsupported fields.')


def annotations(value):
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
        raise InstallError('OCI annotations must be a text mapping.')
    metadata(value)


def verify(path, record, revision):
    """Verify one Linux amd64 OCI image, descriptor closure and config image ID."""
    if path.stat().st_size > ARCHIVE_LIMIT: raise InstallError('OCI archive exceeded its size bound.')
    try:
        return _verify(path, record, revision)
    except InstallError:
        raise
    except (tarfile.TarError, OSError, EOFError, ValueError, TypeError, KeyError, RecursionError, zlib.error) as error:
        raise InstallError('OCI image archive integrity or format verification failed.') from error


def _verify(path, record, revision):
    with tarfile.open(path, 'r:') as archive:
        members = {}
        for item in archive:
            name = item.name
            if (name in members or len(members) >= 1024 or not name or '\\' in name
                    or name.startswith('/') or str(PurePosixPath(name)) != name
                    or '..' in PurePosixPath(name).parts or item.pax_headers or item.sparse is not None
                    or not (item.isfile() or item.isdir())):
                raise InstallError('Unsafe, duplicate or unsupported OCI tar member.')
            if item.isdir():
                if name not in {'blobs', 'blobs/sha256'}: raise InstallError('Unexpected OCI directory.')
            elif name not in {'oci-layout', 'index.json'} and not re.fullmatch(r'blobs/sha256/[a-f0-9]{64}', name):
                raise InstallError('Unexpected OCI archive member.')
            if item.size < 0 or item.size > ARCHIVE_LIMIT: raise InstallError('Invalid OCI member size.')
            members[name] = item
        # Python and the selected OCI reader stop at tar EOF. Do not silently
        # accept an appended second archive or other hidden trailing payload.
        with path.open('rb') as stream:
            stream.seek(archive.offset)
            tail = stream.read(10241)
            if len(tail) > 10240 or len(tail) < 1024 or any(tail):
                raise InstallError('OCI tar must end with bounded zero padding only.')
        consumed = set()
        def raw(name, limit=JSON_LIMIT):
            item = members.get(name)
            if item is None or not item.isfile() or item.size > limit: raise InstallError('Missing or oversized OCI metadata member.')
            consumed.add(name)
            with archive.extractfile(item) as stream: result = stream.read(limit + 1)
            if len(result) != item.size: raise InstallError('OCI member length differs.')
            return result
        layout = parse(raw('oci-layout'))
        if layout != {'imageLayoutVersion': '1.0.0'}: raise InstallError('Unsupported OCI layout version.')
        index = parse(raw('index.json'))
        keys(index, ('schemaVersion', 'manifests'), ('mediaType', 'annotations'))
        if type(index['schemaVersion']) is not int or index['schemaVersion'] != 2 or index.get('mediaType', INDEX) != INDEX:
            raise InstallError('Unsupported OCI index.')
        if 'annotations' in index: annotations(index['annotations'])
        if not isinstance(index['manifests'], list) or len(index['manifests']) != 1:
            raise InstallError('Exactly one selected OCI image is required.')
        def descriptor(row, types, *, platform=False):
            keys(row, ('mediaType', 'digest', 'size'), ('annotations', 'platform') if platform else ('annotations',))
            if (row['mediaType'] not in types or not isinstance(row['digest'], str)
                    or not re.fullmatch(r'sha256:[a-f0-9]{64}', row['digest'])
                    or type(row['size']) is not int or not 0 <= row['size'] <= ARCHIVE_LIMIT):
                raise InstallError('Invalid OCI descriptor identity or type.')
            if 'annotations' in row: annotations(row['annotations'])
            if 'platform' in row and row['platform'] != {'architecture': 'amd64', 'os': 'linux'}:
                raise InstallError('OCI descriptor platform differs from the developer profile.')
            name = 'blobs/sha256/' + row['digest'][7:]
            item = members.get(name)
            if item is None or not item.isfile() or item.size != row['size']:
                raise InstallError('OCI descriptor references missing or changed bytes.')
            return name
        selected = index['manifests'][0]
        name = descriptor(selected, {MANIFEST}, platform=True)
        if selected.get('annotations', {}).get('org.opencontainers.image.ref.name') != record['reference']:
            raise InstallError('OCI selected reference differs from the reviewed local image tag.')
        manifest_raw = raw(name)
        if hashlib.sha256(manifest_raw).hexdigest() != selected['digest'][7:]: raise InstallError('OCI manifest digest differs.')
        manifest = parse(manifest_raw)
        keys(manifest, ('schemaVersion', 'mediaType', 'config', 'layers'), ('annotations',))
        if type(manifest['schemaVersion']) is not int or manifest['schemaVersion'] != 2 or manifest['mediaType'] != MANIFEST:
            raise InstallError('Unsupported OCI image manifest.')
        if 'annotations' in manifest: annotations(manifest['annotations'])
        config_name = descriptor(manifest['config'], {CONFIG})
        config_raw = raw(config_name)
        image_id = 'sha256:' + hashlib.sha256(config_raw).hexdigest()
        if manifest['config']['digest'] != image_id or record['image_id'] != image_id:
            raise InstallError('OCI configuration digest differs from the reviewed image ID.')
        image = parse(config_raw)
        keys(image, ('architecture', 'os', 'config', 'rootfs'), ('created', 'author', 'os.version', 'os.features', 'variant', 'history'))
        if image['architecture'] != 'amd64' or image['os'] != 'linux' or image.get('variant'):
            raise InstallError('OCI image platform differs.')
        if not isinstance(image['config'], dict): raise InstallError('OCI image runtime config must be an object.')
        environment = image['config'].get('Env', [])
        if (not isinstance(environment, list) or any(not isinstance(item, str) or '=' not in item or '\x00' in item for item in environment)
                or len({item.split('=', 1)[0] for item in environment}) != len(environment)):
            raise InstallError('OCI image environment must contain unique explicit assignments.')
        labels = image['config'].get('Labels', {})
        annotations(labels)
        if (labels.get('org.ambisgis.source-manifest-sha256') != record['source_manifest_sha256']
                or labels.get('org.opencontainers.image.revision') != revision):
            raise InstallError('OCI image source labels differ from the reviewed bundle.')
        keys(image['rootfs'], ('type', 'diff_ids'))
        layers, diff_ids = manifest['layers'], image['rootfs']['diff_ids']
        if (image['rootfs']['type'] != 'layers' or not isinstance(layers, list) or not 1 <= len(layers) <= 64
                or not isinstance(diff_ids, list) or len(diff_ids) != len(layers)):
            raise InstallError('Invalid OCI layer closure.')
        expanded_total = 0
        for row, diff_id in zip(layers, diff_ids):
            name = descriptor(row, {LAYER, LAYER + '+gzip'})
            if not isinstance(diff_id, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', diff_id):
                raise InstallError('Invalid OCI uncompressed layer identity.')
            digest = hashlib.sha256()
            with archive.extractfile(members[name]) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
            if digest.hexdigest() != row['digest'][7:]: raise InstallError('OCI layer digest differs.')
            expanded_digest = hashlib.sha256()
            with archive.extractfile(members[name]) as source:
                stream = gzip.GzipFile(fileobj=source) if row['mediaType'].endswith('+gzip') else source
                try:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        expanded_total += len(block)
                        if expanded_total > EXPANDED_LIMIT: raise InstallError('OCI expanded layers exceeded their size bound.')
                        expanded_digest.update(block)
                finally:
                    if stream is not source: stream.close()
            if 'sha256:' + expanded_digest.hexdigest() != diff_id: raise InstallError('OCI root filesystem digest differs.')
            consumed.add(name)
        if {name for name, item in members.items() if item.isfile()} != consumed:
            raise InstallError('OCI archive contains unreferenced hidden members.')
        return {'image_id': image_id, 'manifest_digest': selected['digest'], 'layers': len(layers),
                'expanded_bytes': expanded_total, 'checkpoint_restore_metadata_absent': True,
                'environment': environment}
