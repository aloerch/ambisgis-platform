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
    if (not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts
            or str(Path(name)) != name or name == '.'):
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
    exact_keys(manifest, ('schema_version', 'roots', 'files'), ('symlinks', 'directories'))
    if (type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
            or not isinstance(manifest['files'], list) or not manifest['files']
            or not isinstance(manifest['roots'], list) or not manifest['roots']
            or any(not isinstance(manifest.get(key, []), list) for key in ('directories', 'symlinks'))):
        raise InstallError('The runtime closure manifest is missing.')
    def trusted_directory(path):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o022 or info.st_uid not in (0, os.getuid()):
            raise InstallError('Runtime closure directories must have trusted owners and no group/public write access.')
    roots = []
    directories = set()
    for name in manifest['roots']:
        path = relative(root, name)
        if path == root or not path.is_dir() or any(path.is_relative_to(other) or other.is_relative_to(path) for other in roots):
            raise InstallError('Runtime closure roots must be distinct contained directories.')
        roots.append(path)
        directories.add(str(path.relative_to(root)))
        # A writable parent could replace an otherwise verified subtree.
        while path.is_relative_to(root):
            trusted_directory(path)
            path = path.parent
    def contained(path):
        return any(path.is_relative_to(base) for base in roots)
    def parents(path):
        while path != root and contained(path):
            directories.add(str(path.relative_to(root)))
            path = path.parent
    names = set()
    for record in manifest['files']:
        exact_keys(record, ('path', 'sha256'))
        if not isinstance(record['path'], str) or record['path'] in names:
            raise InstallError('Duplicate runtime closure member.')
        names.add(record.get('path'))
        path = member(root, record)
        if not contained(path): raise InstallError('Runtime file is outside the complete closure roots.')
        if path.stat().st_uid not in (0, os.getuid()): raise InstallError('Runtime file has an untrusted owner.')
        parents(path.parent)
    links = set()
    for record in manifest.get('symlinks', []):
        exact_keys(record, ('path', 'target'))
        name, target = record['path'], record['target']
        if (not isinstance(name, str) or not name or str(Path(name)) != name or name == '.'
                or Path(name).is_absolute() or '..' in Path(name).parts or name in names
                or not isinstance(target, str) or not target):
            raise InstallError('Invalid or duplicate runtime symlink member.')
        link = checked_path((root / name).parent) / Path(name).name
        if not link.is_symlink() or os.readlink(link) != target or Path(target).is_absolute():
            raise InstallError('Runtime symlink identity mismatch.')
        resolved = link.resolve(strict=True)
        if not resolved.is_relative_to(root) or str(resolved.relative_to(root)) not in names:
            raise InstallError('Runtime symlinks must resolve to a verified bundle file.')
        if not contained(link) or link.lstat().st_uid not in (0, os.getuid()):
            raise InstallError('Runtime symlink is outside the closure roots or has an untrusted owner.')
        names.add(name)
        links.add(name)
        parents(link.parent)
    for name in manifest.get('directories', []):
        path = relative(root, name)
        if not contained(path) or not path.is_dir(): raise InstallError('Invalid declared runtime directory.')
        parents(path)
    actual = set()
    observed_directories = set()
    for base in roots:
        for parent, children, files in os.walk(base, followlinks=False):
            path = Path(parent)
            trusted_directory(path)
            observed_directories.add(str(path.relative_to(root)))
            for name in children + files:
                entry = path / name; info = entry.lstat(); relative_name = str(entry.relative_to(root))
                if stat.S_ISDIR(info.st_mode): continue
                if stat.S_ISLNK(info.st_mode):
                    if relative_name not in links: raise InstallError('Unmanifested runtime symlink.')
                elif not stat.S_ISREG(info.st_mode):
                    raise InstallError('Special files are forbidden in runtime closure roots.')
                actual.add(relative_name)
    if actual != names or observed_directories != directories:
        raise InstallError('Runtime closure has missing or unmanifested files, links or directories; no producer was executed.')
    return names, roots


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


def validate_runtime_paths(selected_bundle, install_root, *, bundle_root):
    """Pure, bundle-selected path capability; legacy bundles retain their rules."""
    runtime = selected_bundle['runtime']
    if 'path_profile' not in runtime:
        return
    profile = runtime['path_profile']
    if not isinstance(profile, str) or profile != 'owned-health-timer-ascii-v1':
        raise InstallError('Unsupported bundle runtime path profile.')
    paths = (bundle_root,) if install_root is None else (bundle_root, install_root)
    for path in paths:
        value = os.fspath(path) if isinstance(path, (str, os.PathLike)) else None
        if (not isinstance(value, str) or not re.fullmatch(r'/[A-Za-z0-9_./-]+', value)
                or any(part in ('', '.', '..') for part in value[1:].split('/'))):
            raise InstallError("This owned health-timer bundle requires clean absolute ASCII bundle and installation paths using only letters, digits, '/', '.', '_' and '-'. Choose supported paths before init; existing state was preserved.")


def validate_dns_profile(selected_bundle, *, bundle_root):
    """Require the selected native direct-DNS lookup boundary before execution."""
    runtime = selected_bundle['runtime']
    if 'dns_profile' not in runtime:
        return
    if not isinstance(runtime['dns_profile'], str) or runtime['dns_profile'] != 'native-direct-v1':
        raise InstallError('Unsupported bundle runtime DNS profile.')
    environment = runtime['environment']
    if (not isinstance(environment, dict)
            or environment.get('PATH') != ['runtime/bin', 'runtime/helpers']):
        raise InstallError('The native-direct-v1 DNS profile requires exactly runtime/bin and runtime/helpers in PATH.')
    root = checked_path(bundle_root)
    if ':' in str(root):
        raise InstallError('The native-direct-v1 DNS profile does not permit a colon in the selected bundle path; it would add unverified PATH locations.')
    directories = [relative(root, name) for name in ('runtime/bin', 'runtime/helpers')]
    if any(not directory.is_dir() for directory in directories):
        raise InstallError('The native-direct-v1 DNS profile requires both owned PATH directories.')
    # Retained netavark exec.go appends /usr/sbin unless PATH contains that
    # substring. Check it unconditionally as a conservative host prerequisite,
    # even if the selected bundle path itself happens to contain /usr/sbin.
    directories.append(checked_path('/usr/sbin'))
    for directory in directories:
        try:
            (directory / 'systemd-run').lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise InstallError('The native-direct-v1 DNS profile lookup could not be verified; no producer was executed.') from None
        # Native detection tests metadata existence rather than executability.
        # lstat also rejects dangling links and every other filesystem kind.
        raise InstallError('The native-direct-v1 DNS profile requires systemd-run to be absent from its owned PATH and /usr/sbin; select a qualified bundle/host without modifying host files.')


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
    exact_keys(runtime, ('podman', 'compose', 'environment', 'files_manifest', 'prerequisites'), ('path_profile', 'dns_profile'))
    validate_runtime_paths(value, None, bundle_root=root)
    validate_dns_profile(value, bundle_root=root)
    names, closure_roots = verify_manifest(root, runtime['files_manifest'])
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
            path = relative(root, entry)
            if ':' in entry or not path.is_dir() or not any(path.is_relative_to(base) for base in closure_roots):
                raise InstallError('Runtime search paths must stay inside complete verified closure roots.')
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
