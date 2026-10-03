"""Verify the local, reviewed installation bundle before executing any producer."""
import os
from pathlib import Path
import pwd
import re
import stat

from .state import InstallError, checked_path, digest, read_json

HEX = re.compile(r'[a-f0-9]{64}')
SERVICES = ('database', 'catalog', 'geoserver', 'gateway')
ENVIRONMENT = {'PATH', 'LD_LIBRARY_PATH', 'PYTHONPATH'}


def exact_keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise InstallError('Configuration has missing or unsupported fields.')


def sha256(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise InstallError('A complete SHA256 identity is required.')
    return value


def relative(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
        raise InstallError('Bundle members must use contained relative paths.')
    return checked_path(root / name)


def member(root, record, *, executable=False, verify=True):
    exact_keys(record, ('path', 'sha256'))
    path = relative(root, record['path'])
    sha256(record['sha256'])
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o022:
        raise InstallError('Bundle input must be a regular file without group/public write access.')
    if executable and not os.access(path, os.X_OK):
        raise InstallError('The retained runtime executable is not executable.')
    if verify and digest(path) != record['sha256']:
        raise InstallError('Bundle member integrity mismatch. Restore the exact reviewed input.')
    return path


def verify_manifest(root, reference):
    manifest = read_json(member(root, reference))
    exact_keys(manifest, ('schema_version', 'files'), ('symlinks',))
    if manifest['schema_version'] != 1 or not isinstance(manifest['files'], list) or not manifest['files']:
        raise InstallError('The runtime closure manifest is missing.')
    names = set()
    for record in manifest['files']:
        if record.get('path') in names:
            raise InstallError('Duplicate runtime closure member.')
        names.add(record.get('path'))
        member(root, record)
    for record in manifest.get('symlinks', []):
        exact_keys(record, ('path', 'target'))
        name, target = record['path'], record['target']
        if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts or name in names:
            raise InstallError('Invalid or duplicate runtime symlink member.')
        link = checked_path((root / name).parent) / Path(name).name
        if not link.is_symlink() or os.readlink(link) != target or Path(target).is_absolute():
            raise InstallError('Runtime symlink identity mismatch.')
        resolved = link.resolve(strict=True)
        if not resolved.is_relative_to(root) or str(resolved.relative_to(root)) not in names:
            raise InstallError('Runtime symlinks must resolve to a verified bundle file.')
        names.add(name)
    return names


def host_prerequisites(value):
    exact_keys(value, ('schema_version', 'host_tools', 'requirements'))
    if value['schema_version'] != 1 or not isinstance(value['host_tools'], list) or not value['host_tools']:
        raise InstallError('Missing explicit host prerequisite inventory.')
    for record in value['host_tools']:
        exact_keys(record, ('path', 'sha256', 'uid', 'gid', 'mode', 'capability_hex'))
        host = checked_path(record['path'])
        metadata = host.stat()
        try:
            capabilities = os.getxattr(host, 'security.capability').hex()
        except OSError as error:
            if error.errno not in (61, 95):
                raise
            capabilities = ''
        if (not stat.S_ISREG(metadata.st_mode) or digest(host) != sha256(record['sha256'])
                or metadata.st_uid != record['uid'] or metadata.st_gid != record['gid']
                or stat.S_IMODE(metadata.st_mode) != record['mode'] or capabilities != record['capability_hex']):
            raise InstallError('Host helper bytes, ownership, mode or capabilities changed; requalify the runtime.')
    requirements = value['requirements']
    exact_keys(requirements, ('kernel_release', 'minimum_subordinate_ids', 'cgroup_controllers', 'fuse_required'))
    if requirements['kernel_release'] != os.uname().release:
        raise InstallError('This bundle has not qualified the running host kernel.')
    minimum = requirements['minimum_subordinate_ids']
    if type(minimum) is not int or minimum < 65536:
        raise InstallError('Rootless runtime requires an explicit subordinate-ID range.')
    username = pwd.getpwuid(os.getuid()).pw_name
    for file in ('/etc/subuid', '/etc/subgid'):
        identity = os.getuid() if file == '/etc/subuid' else os.getgid()
        records = []
        for line in Path(file).read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            fields = line.split(':')
            if len(fields) == 3 and fields[0] in (username, str(os.getuid())):
                start, count = int(fields[1]), int(fields[2])
                if start > 0 and count >= minimum and not start <= identity < start + count:
                    records.append((start, count))
        if not records:
            raise InstallError('The current user needs an approved subordinate UID and GID range.')
    controllers = requirements['cgroup_controllers']
    if not isinstance(controllers, list) or not {'cpu', 'memory', 'pids'} <= set(controllers):
        raise InstallError('Explicit cgroup-v2 resource-controller requirements are missing.')
    available = set(Path('/sys/fs/cgroup/cgroup.controllers').read_text().split())
    if not set(controllers) <= available:
        raise InstallError('Required cgroup-v2 controllers are unavailable.')
    if type(requirements['fuse_required']) is not bool:
        raise InstallError('FUSE prerequisite must be explicit.')
    if requirements['fuse_required']:
        fuse = Path('/dev/fuse')
        if not fuse.exists() or not stat.S_ISCHR(fuse.stat().st_mode) or not os.access(fuse, os.R_OK | os.W_OK):
            raise InstallError('The selected rootless storage backend requires accessible /dev/fuse.')


def load(path, expected_sha256, *, verify_images=True, image_receipts=None):
    path = checked_path(path)
    if digest(path) != sha256(expected_sha256):
        raise InstallError('Bundle manifest identity mismatch.')
    value = read_json(path)
    exact_keys(value, ('schema_version', 'kind', 'target', 'product_revision', 'source_manifest', 'runtime', 'images'))
    if value['schema_version'] != 1 or value['kind'] != 'ambisgis.development-bundle':
        raise InstallError('Unsupported installation bundle version or kind.')
    if value['target'] != {'os': 'linux', 'architecture': 'x86_64'} or os.uname().sysname != 'Linux' or os.uname().machine != 'x86_64':
        raise InstallError('This developer bundle requires Linux x86_64.')
    if not isinstance(value['product_revision'], str) or not re.fullmatch(r'[a-f0-9]{40}', value['product_revision']):
        raise InstallError('The bundle must bind its exact owned product revision.')
    root = path.parent
    member(root, value['source_manifest'])
    runtime = value['runtime']
    exact_keys(runtime, ('podman', 'compose', 'environment', 'files_manifest', 'prerequisites'))
    names = verify_manifest(root, runtime['files_manifest'])
    for tool in ('podman', 'compose'):
        member(root, runtime[tool], executable=True)
        if runtime[tool]['path'] not in names:
            raise InstallError('Runtime executable is absent from the closure manifest.')
    if not isinstance(runtime['environment'], dict) or set(runtime['environment']) - ENVIRONMENT:
        raise InstallError('Runtime environment contains unsupported overrides.')
    for name, entries in runtime['environment'].items():
        if not isinstance(entries, list) or not entries:
            raise InstallError('Runtime paths must be nonempty lists of bundle directories.')
        for entry in entries:
            if ':' in entry or not relative(root, entry).is_dir():
                raise InstallError('Runtime paths must be contained bundle directories.')
    host_prerequisites(read_json(member(root, runtime['prerequisites'])))
    images = value['images']
    exact_keys(images, SERVICES, ('qgis',))
    for role, image in images.items():
        exact_keys(image, ('archive', 'archive_sha256', 'reference', 'image_id', 'source_manifest_sha256'))
        member(root, {'path': image['archive'], 'sha256': image['archive_sha256']}, verify=verify_images)
        if not isinstance(image['reference'], str) or not re.fullmatch(r'localhost/ambisgis/[a-z][a-z0-9-]*:[a-z0-9][a-z0-9._-]{0,100}', image['reference']) or image['reference'].endswith(':latest'):
            raise InstallError('Images require explicit local product references.')
        if not isinstance(image['image_id'], str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image['image_id']):
            raise InstallError('Images require exact local image identities.')
        if image['source_manifest_sha256'] != value['source_manifest']['sha256']:
            raise InstallError('Image and bundle source selections differ.')
        if verify_images:
            from .image_archive import verify
            receipt = verify(relative(root, image['archive']), image, value['product_revision'])
            if image_receipts is not None: image_receipts[role] = receipt
    return value
