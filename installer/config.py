"""One installation configuration; Compose and scoped secrets are derived views."""
import hashlib
import os
from pathlib import Path
import re
import secrets
import uuid

from . import bundle
from .state import InstallError, atomic_write, canonical, checked_path, digest, locked, private_directory, read_json

PROFILE = 'developer-loopback'
SECRET_NAMES = ('database_admin', 'catalog_migrator', 'catalog_runtime', 'render_reader',
                'transport_migrator', 'transport_reader',
                'django_key', 'policy_key', 'oauth_client', 'oauth_secret',
                'engine_admin', 'owner_password', 'viewer_password', 'health_token')
DATA_NAMES = ('postgres', 'catalog', 'geoserver', 'blobs')


def validate(value, root):
    bundle.exact_keys(value, ('schema_version', 'install_id', 'profile', 'listen', 'storage', 'bundle', 'owner', 'viewer'))
    if value['schema_version'] != 1 or value['profile'] != PROFILE:
        raise InstallError('Only version 1 developer-loopback installations are supported.')
    try:
        if str(uuid.UUID(value['install_id'])) != value['install_id']:
            raise ValueError()
    except (ValueError, TypeError, AttributeError) as error:
        raise InstallError('Installation identity must be a canonical UUID.') from error
    bundle.exact_keys(value['listen'], ('host', 'port'))
    if value['listen']['host'] != '127.0.0.1' or type(value['listen']['port']) is not int or not 1024 <= value['listen']['port'] <= 65535:
        raise InstallError('Developer access requires 127.0.0.1 and an unprivileged TCP port.')
    if value['storage'] != str(root / 'data'):
        raise InstallError('This profile keeps persistent storage inside its installation directory.')
    bundle.exact_keys(value['bundle'], ('path', 'sha256'))
    checked_path(value['bundle']['path'])
    bundle.sha256(value['bundle']['sha256'])
    for name in ('owner', 'viewer'):
        if not isinstance(value[name], str) or not re.fullmatch(r'[a-z][a-z0-9_-]{2,31}', value[name]):
            raise InstallError('Enrollment names must be 3–32 lowercase letters, digits, underscores or hyphens.')
    if value['owner'] == value['viewer']:
        raise InstallError('The two enrolled principals must be distinct.')
    return value


def load(root):
    root = private_directory(root)
    value = validate(read_json(root / 'product.json', private=True), root)
    storage_directories(root)
    return value


def storage_directories(root, *, create=False):
    """Validate every persistent bind source before rendering or engine calls."""
    private_directory(root / 'data', create=create)
    for name in DATA_NAMES:
        private_directory(root / 'data' / name, create=create)


def secret_material(root):
    value = read_json(root / 'secrets' / 'product.json', private=True)
    bundle.exact_keys(value, SECRET_NAMES)
    if any(not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}', item) for item in value.values()):
        raise InstallError('Generated secret material is invalid; it will not be silently replaced.')
    if len(set(value.values())) != len(value):
        raise InstallError('Service credentials must be distinct.')
    return value


def project_name(config):
    return 'ambisgis-' + config['install_id'].replace('-', '')


def service_configuration(config):
    # Every runtime address is generated here, not inherited from GeoNode defaults.
    return {
        'schema_version': 1, 'install_id': config['install_id'], 'profile': PROFILE,
        'public_origin': 'http://127.0.0.1:' + str(config['listen']['port']),
        'database_host': 'database', 'database_port': 5432,
        'catalog_origin': 'http://catalog:8000', 'engine_origin': 'http://geoserver:8080',
        'owner': config['owner'], 'viewer': config['viewer'],
        'catalog_database': 'ambisgis_catalog', 'managed_database': 'ambisgis_data',
    }


def compose(config, selection, root):
    name = project_name(config)
    services = {}
    # The entrypoint takes a role, reads mounted JSON, and never receives secrets
    # on the command line or in container environment/inspection output.
    for role in (*bundle.SERVICES, 'catalog-init', 'geoserver-init'):
        image_role = role.removesuffix('-init')
        mounts = [
            {'type': 'bind', 'source': str(root / 'generated' / 'service.json'), 'target': '/run/ambisgis/product.json', 'read_only': True},
            {'type': 'bind', 'source': str(root / 'generated' / (role + '-secrets.json')), 'target': '/run/ambisgis/secrets.json', 'read_only': True},
        ]
        if image_role in ('database', 'catalog', 'geoserver'):
            data = 'postgres' if role == 'database' else image_role
            mounts.append({'type': 'bind', 'source': str(root / 'data' / data), 'target': '/var/lib/ambisgis'})
        if image_role in ('catalog', 'geoserver'):
            mounts.append({'type': 'bind', 'source': str(root / 'data' / 'blobs'), 'target': '/var/lib/ambisgis-blobs', 'read_only': image_role == 'geoserver'})
        service = {
            'image': selection['images'][image_role]['image_id'], 'pull_policy': 'never',
            'container_name': name + '-' + role,
            'labels': {'org.ambisgis.install-id': config['install_id'], 'org.ambisgis.role': role},
            'entrypoint': ['/opt/ambisgis/bin/service'], 'command': [role],
            'user': str(os.getuid()) + ':' + str(os.getgid()), 'userns_mode': 'keep-id',
            'read_only': True, 'cap_drop': ['ALL'],
            'security_opt': ['no-new-privileges:true'],
            'sysctls': {'net.ipv6.conf.all.disable_ipv6': '1', 'net.ipv6.conf.default.disable_ipv6': '1'},
            'tmpfs': ['/tmp:rw,nosuid,nodev,size=256m'],
            'volumes': mounts, 'networks': ['internal'],
            'stop_grace_period': '45s', 'restart': 'unless-stopped',
            'healthcheck': {'test': ['CMD', '/opt/ambisgis/bin/health', role], 'interval': '15s', 'timeout': '15s', 'retries': 3, 'start_period': '60s'},
        }
        if role == 'gateway':
            service['ports'] = [str(config['listen']['host']) + ':' + str(config['listen']['port']) + ':8000']
        if role.endswith('-init'):
            service['profiles'] = ['bootstrap']
            service['restart'] = 'no'
            service.pop('healthcheck')
        services[role] = service
    return {'name': name, 'services': services, 'networks': {'internal': {'internal': True, 'enable_ipv6': False, 'labels': {'org.ambisgis.install-id': config['install_id']}}}}


def render(root, config, selection):
    root = private_directory(root)
    storage_directories(root)
    generated = private_directory(root / 'generated', create=True)
    material = secret_material(root)
    scopes = {
        'database': ('database_admin', 'catalog_migrator', 'catalog_runtime', 'render_reader', 'transport_migrator', 'transport_reader'),
        'catalog-init': ('catalog_migrator', 'django_key', 'policy_key', 'oauth_client', 'oauth_secret', 'owner_password', 'viewer_password', 'health_token'),
        'catalog': ('catalog_runtime', 'django_key', 'policy_key', 'oauth_client', 'oauth_secret'),
        'geoserver-init': ('transport_migrator', 'engine_admin', 'policy_key'),
        'geoserver': ('transport_reader', 'engine_admin', 'policy_key'),
        'gateway': ('policy_key', 'health_token'),
    }
    for role, keys in scopes.items():
        atomic_write(generated / (role + '-secrets.json'), {key: material[key] for key in keys}, replace=True)
    atomic_write(generated / 'service.json', service_configuration(config), replace=True)
    atomic_write(root / 'compose.json', compose(config, selection, root), replace=True)


def initialize(directory, bundle_path, bundle_sha256, *, port=None, owner=None, viewer=None):
    root = checked_path(directory)
    selection = bundle.load(bundle_path, bundle_sha256)
    # Never adopt preexisting application/user data by directory title. An
    # interrupted first init without its final configuration fails closed.
    if root.exists() and not (root / 'product.json').exists() and any(root.iterdir()):
        raise InstallError('Installation directory is not empty and has no product configuration.')
    candidate = validate({'schema_version': 1, 'install_id': str(uuid.uuid4()), 'profile': PROFILE,
                          'listen': {'host': '127.0.0.1', 'port': port if port is not None else 8787},
                          'storage': str(root / 'data'),
                          'bundle': {'path': str(checked_path(bundle_path)), 'sha256': bundle_sha256},
                          'owner': owner if owner is not None else 'publisher',
                          'viewer': viewer if viewer is not None else 'viewer'}, root)
    private_directory(root, create=True)
    with locked(root):
        if (root / 'product.json').exists():
            config = load(root)
            if config['bundle'] != {'path': str(checked_path(bundle_path)), 'sha256': bundle_sha256}:
                raise InstallError('An existing installation cannot silently change its bundle.')
            for requested, actual in ((port, config['listen']['port']), (owner, config['owner']), (viewer, config['viewer'])):
                if requested is not None and requested != actual:
                    raise InstallError('Reinitialization conflicts with existing configuration; state was preserved.')
            secret_material(root)
            created = False
        else:
            config = candidate
            private_directory(root / 'secrets', create=True)
            atomic_write(root / 'secrets' / 'product.json', {name: secrets.token_urlsafe(48) for name in SECRET_NAMES})
            storage_directories(root, create=True)
            atomic_write(root / 'product.json', config)
            created = True
        render(root, config, selection)
    return {'command': 'init', 'created': created, 'install_id': config['install_id'],
            'profile': PROFILE, 'url': service_configuration(config)['public_origin'],
            'credentials_file': str(root / 'secrets' / 'product.json')}
