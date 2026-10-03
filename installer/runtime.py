"""Explicit local runtime invocation and installation-scoped lifecycle."""
import http.client
import ipaddress
import json
import os
from pathlib import Path
import shlex
import subprocess
import stat
import tempfile
import time

from . import bundle, config
from .state import InstallError, atomic_write, checked_path, locked, private_directory, read_json


class Runtime:
    def __init__(self, root, *, verify_images=True):
        self.root = private_directory(root)
        self.config = config.load(root)
        self.image_receipts = {}
        self.selection = bundle.load(self.config['bundle']['path'], self.config['bundle']['sha256'],
                                     verify_images=verify_images, image_receipts=self.image_receipts)
        self.bundle_root = Path(self.config['bundle']['path']).parent
        self.paths = {}
        private_directory(self.root / 'runtime', create=True)
        for name in ('home', 'config', 'data', 'run', 'storage', 'networks', 'hooks', 'tmp'):
            self.paths[name] = private_directory(self.root / 'runtime' / name, create=True)
        self.environment = self.clean_environment()
        runtime = self.selection['runtime']
        self.podman = str(bundle.member(self.bundle_root, runtime['podman'], executable=True))
        self.provider = str(bundle.member(self.bundle_root, runtime['compose'], executable=True))
        self.global_args = ['--root', str(self.paths['storage']), '--runroot', str(self.paths['run']),
                            '--network-config-dir', str(self.paths['networks']), '--hooks-dir', str(self.paths['hooks']),
                            '--tmpdir', str(self.paths['tmp']), '--events-backend', 'file']

    def clean_environment(self):
        # Set child environment directly, never change the caller's HOME or
        # accept inherited daemon/socket/provider/config/preload variables.
        value = {'HOME': str(self.paths['home']), 'XDG_CONFIG_HOME': str(self.paths['config']),
                 'XDG_DATA_HOME': str(self.paths['data']), 'XDG_RUNTIME_DIR': str(self.paths['run']),
                 'TMPDIR': str(self.paths['tmp']), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                 'PYTHONNOUSERSITE': '1', 'PYTHONSAFEPATH': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
        for key, paths in self.selection['runtime']['environment'].items():
            value[key] = os.pathsep.join(str(bundle.relative(self.bundle_root, path)) for path in paths)
        return value

    def run(self, arguments, *, timeout=60, allow_failure=False):
        # Output remains private and is never included in exceptions. Native
        # diagnostics may contain connection details; status emits selected fields.
        with tempfile.TemporaryFile(dir=self.paths['tmp']) as capture:
            try:
                result = subprocess.run(arguments, env=self.environment, cwd=self.root,
                                        stdin=subprocess.DEVNULL, stdout=capture, stderr=subprocess.STDOUT,
                                        timeout=timeout, check=False)
            except subprocess.TimeoutExpired as error:
                raise InstallError('Runtime operation timed out. Use status and doctor; persistent data was preserved.') from error
            capture.seek(0)
            output = capture.read(4 * 1024 * 1024 + 1)
        if len(output) > 4 * 1024 * 1024:
            raise InstallError('Runtime diagnostic output exceeded its bound.')
        if result.returncode and not allow_failure:
            raise InstallError('Local runtime operation failed (exit ' + str(result.returncode) + '); use doctor.')
        return result.returncode, output

    def engine(self, *arguments, **kwargs):
        return self.run([self.podman, *self.global_args, *map(str, arguments)], **kwargs)

    def compose(self, *arguments, **kwargs):
        empty = self.paths['config'] / 'compose.env'
        if not empty.exists():
            atomic_write(empty, b'')
        return self.run([self.provider, '--podman-path', self.podman,
                         '--podman-args=' + shlex.join(self.global_args), '--env-file', str(empty),
                         '--no-ansi', '--parallel', '4', '-p', config.project_name(self.config),
                         '-f', str(self.root / 'compose.json'), *arguments], **kwargs)

    def image(self, role, *, load=False):
        record = self.selection['images'][role]
        code, _ = self.engine('image', 'exists', record['reference'], allow_failure=True)
        if code not in (0, 1):
            raise InstallError('The image store could not be inspected; no mutation was attempted.')
        if code == 1:
            if not load:
                raise InstallError('A required owned image is not loaded.')
            self.engine('load', '--input', bundle.relative(self.bundle_root, record['archive']), timeout=600)
        _, output = self.engine('image', 'inspect', record['reference'])
        try:
            rows = json.loads(output)
            if len(rows) != 1:
                raise ValueError()
            value = rows[0]
            from .image_archive import metadata
            metadata(value)
            identity = value['Id']
            if not identity.startswith('sha256:'):
                identity = 'sha256:' + identity
            labels = value.get('Labels') or value.get('Config', {}).get('Labels', {})
            if (identity != record['image_id']
                    or value.get('Digest') != self.image_receipts[role]['manifest_digest']
                    or labels.get('org.ambisgis.source-manifest-sha256') != record['source_manifest_sha256']
                    or labels.get('org.opencontainers.image.revision') != self.selection['product_revision']):
                raise ValueError()
        except InstallError:
            raise
        except (KeyError, ValueError, TypeError, AttributeError) as error:
            raise InstallError('Local image identity/source labels or manifest differ from the reviewed bundle; no container was started.') from error
        return identity

    def processes(self, *, include_initializers=False):
        results = {}
        name = config.project_name(self.config)
        roles = (*bundle.SERVICES, 'catalog-init', 'geoserver-init') if include_initializers else bundle.SERVICES
        for role in roles:
            code, _ = self.engine('container', 'exists', name + '-' + role, allow_failure=True)
            if code not in (0, 1):
                raise InstallError('Container state is unavailable; no mutation was attempted.')
            if code == 1:
                results[role] = {'process': 'absent', 'engine_health': 'unavailable'}
                continue
            _, output = self.engine('container', 'inspect', name + '-' + role)
            try:
                rows = json.loads(output)
                if len(rows) != 1:
                    raise ValueError()
                row = rows[0]
                labels = row['Config']['Labels']
                if labels.get('org.ambisgis.install-id') != self.config['install_id'] or labels.get('org.ambisgis.role') != role:
                    raise ValueError()
                image = row['Image']
                if not image.startswith('sha256:'):
                    image = 'sha256:' + image
                if image != self.selection['images'][role.removesuffix('-init')]['image_id']:
                    raise ValueError()
                ports = row.get('HostConfig', {}).get('PortBindings') or {}
                expected = {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(self.config['listen']['port'])}]} if role == 'gateway' else {}
                if ports != expected:
                    raise ValueError()
                self.container_security(row, role)
                state = row['State']
                results[role] = {'process': 'running' if state.get('Running') else 'stopped',
                                 'engine_health': (state.get('Health') or {}).get('Status', 'unavailable')}
            except (KeyError, ValueError, TypeError, AttributeError) as error:
                raise InstallError('Container ownership, image, ports, security, mounts or namespaces differ from this installation.') from error
        return results

    def container_security(self, row, role):
        """Reject drift before any Compose mutation, including stopped containers.

        Podman 6 computes CapDrop relative to configured defaults. Its effective
        and bounding lists are the meaningful empty-capability check. Actual
        rootless/SELinux/OCI namespace behavior still has native acceptance tests.
        """
        expected = config.compose(self.config, self.selection, self.root)['services'][role]
        # This Podman version does not expose a HostConfig.Sysctls field. Bind
        # the actual OCI file named by its inspected OCIConfigPath instead.
        try:
            path = checked_path(row['OCIConfigPath'])
            if not any(path.is_relative_to(self.paths[name]) for name in ('storage', 'run')):
                raise ValueError('OCI configuration escaped installation storage')
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise ValueError('unsafe OCI configuration file')
            oci = read_json(path)
            if oci['linux']['sysctl'] != expected['sysctls']:
                raise ValueError('container IPv4-only sysctl drift')
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise InstallError('Container OCI configuration or IPv4-only sysctls differ from this installation.') from error
        host, process = row['HostConfig'], row['Config']
        def environment(items):
            if not isinstance(items, list) or any(not isinstance(value, str) or '=' not in value for value in items):
                raise ValueError('invalid container environment')
            values = dict(value.split('=', 1) for value in items)
            if len(values) != len(items): raise ValueError('duplicate container environment')
            return values
        wanted_environment = environment(self.image_receipts[role.removesuffix('-init')]['environment'])
        actual_environment = environment(process.get('Env'))
        # Podman's two informational additions cannot override pinned image
        # variables or introduce startup/loader/provider configuration.
        for key, value in (('container', 'podman'), ('HOSTNAME', process.get('Hostname'))):
            if key not in wanted_environment and actual_environment.get(key) == value:
                actual_environment.pop(key, None)
        if actual_environment != wanted_environment:
            raise ValueError('container environment drift')
        if (host.get('ReadonlyRootfs') is not True or host.get('Privileged') is not False
                or host.get('PublishAllPorts') is not False or host.get('CapAdd') not in ([], None)
                or 'EffectiveCaps' not in row or row['EffectiveCaps'] not in ([], None)
                or 'BoundingCaps' not in row or row['BoundingCaps'] not in ([], None)
                or host.get('SecurityOpt') != ['no-new-privileges']
                or process.get('User') != expected['user'] or process.get('Entrypoint') != expected['entrypoint']
                or process.get('Cmd') != expected['command']):
            raise ValueError('container security or command drift')
        if (host.get('UsernsMode') != 'private' or host.get('PidMode') != 'private'
                or host.get('UTSMode') != 'private' or host.get('IpcMode') not in ('private', 'shareable')
                or host.get('CgroupMode') != 'private' or host.get('Devices') not in ([], None)
                or host.get('GroupAdd') not in ([], None)):
            raise ValueError('container namespace or device drift')
        networks = row['NetworkSettings']['Networks']
        if set(networks) != {config.project_name(self.config) + '_internal'}:
            raise ValueError('container network membership drift')
        tmpfs = host.get('Tmpfs')
        if not isinstance(tmpfs, dict) or set(tmpfs) != {'/tmp'} or not isinstance(tmpfs['/tmp'], str):
            raise ValueError('container tmpfs membership drift')
        options = set(tmpfs['/tmp'].split(','))
        if (not {'rw', 'nosuid', 'nodev'} <= options or len(options & {'size=256m', 'size=268435456'}) != 1
                or options - {'rw', 'nosuid', 'nodev', 'noexec', 'size=256m', 'size=268435456', 'mode=1777', 'tmpcopyup'}):
            raise ValueError('container tmpfs permissions or limits drift')
        wanted = {mount['target']: mount for mount in expected['volumes']}
        mounts = row['Mounts']
        if not isinstance(mounts, list) or len(mounts) != len(wanted):
            raise ValueError('container mount membership drift')
        seen = set()
        for mount in mounts:
            target = mount['Destination']
            if target in seen or target not in wanted:
                raise ValueError('container mount target drift')
            seen.add(target); selected = wanted[target]
            if (mount.get('Type') != 'bind' or mount.get('Source') != selected['source']
                    or mount.get('RW') is not (not selected.get('read_only', False))
                    or mount.get('Propagation') not in ('private', 'rprivate')
                    or mount.get('Mode') not in ('', selected['bind']['selinux'])
                    or mount.get('SubPath') or set(mount.get('Options', [])) - {'rbind', 'bind', 'nosuid', 'nodev', 'noexec'}):
                raise ValueError('container mount access or source drift')

    def network(self):
        name = config.project_name(self.config) + '_internal'
        code, _ = self.engine('network', 'exists', name, allow_failure=True)
        if code == 1: return None
        if code != 0: raise InstallError('Installation network state is unavailable; no mutation was attempted.')
        _, output = self.engine('network', 'inspect', name)
        try:
            rows = json.loads(output)
            if not isinstance(rows, list) or len(rows) != 1: raise ValueError()
            value = rows[0]
            if (value['name'] != name or value['driver'] != 'bridge' or value['internal'] is not True
                    or value['ipv6_enabled'] is not False or value['dns_enabled'] is not True
                    or value['labels'].get('org.ambisgis.install-id') != self.config['install_id']
                    or value.get('routes') or value.get('network_dns_servers') or value.get('options')
                    or value.get('ipam_options', {}) not in ({}, {'driver': 'host-local'})):
                raise ValueError()
            subnets = value['subnets']
            if not isinstance(subnets, list) or not subnets: raise ValueError()
            for subnet in subnets:
                network = ipaddress.IPv4Network(subnet['subnet'], strict=True)
                if not network.is_private or network.is_loopback or network.is_link_local: raise ValueError()
                if subnet.get('gateway') and ipaddress.IPv4Address(subnet['gateway']) not in network: raise ValueError()
                if subnet.get('lease_range'): raise ValueError()
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise InstallError('Installation network ownership, driver, routing or IPv4-only configuration differs.') from error
        return {'name': name, 'internal': True, 'ipv6_enabled': False, 'driver': 'bridge', 'verified': True}

    def readiness(self):
        connection = http.client.HTTPConnection('127.0.0.1', self.config['listen']['port'], timeout=14)
        try:
            connection.request('GET', '/health/ready')
            response = connection.getresponse()
            body = response.read(32769)
            if len(body) > 32768 or response.getheader('Location'):
                raise ValueError()
            value = json.loads(body)
            if value.get('install_id') != self.config['install_id'] or type(value.get('ready')) is not bool:
                raise ValueError()
            if response.status not in (200, 503) or (response.status == 200) != value['ready']:
                raise ValueError()
            # Never return arbitrary service-supplied details/exception text.
            checks = value.get('checks', {})
            if not isinstance(checks, dict) or set(checks) != {'catalog', 'database', 'map', 'query'} or any(type(v) is not bool for v in checks.values()):
                raise ValueError()
            if value['ready'] != all(checks.values()):
                raise ValueError()
            return {'ready': value['ready'], 'checks': checks}
        except (OSError, http.client.HTTPException, ValueError, TypeError):
            return {'ready': False, 'reason': 'Useful service readiness is unavailable.'}
        finally:
            connection.close()

    def status(self):
        return {'command': 'status', 'install_id': self.config['install_id'],
                'services': self.processes(), 'network': self.network(), 'readiness': self.readiness()}


def up(root, *, timeout=180):
    with locked(root):
        runtime = Runtime(root)
        # Validate existing names/ownership before a Compose invocation can act.
        existing = runtime.processes(include_initializers=True)
        network = runtime.network()
        if network is None and any(row['process'] != 'absent' for row in existing.values()):
            raise InstallError('Existing containers have lost their installation network; no mutation was attempted.')
        for role in bundle.SERVICES:
            runtime.image(role, load=True)
        database_name = config.project_name(runtime.config) + '-database'
        if existing['database']['process'] == 'running':
            runtime.engine('exec', database_name, '/opt/ambisgis/bin/health', 'database')
        config.render(runtime.root, runtime.config, runtime.selection)
        runtime.compose('up', '-d', '--no-build', '--pull', 'never', 'database', timeout=180)
        deadline = time.monotonic() + timeout
        while True:
            database = runtime.processes()['database']
            if database['process'] == 'running' and database['engine_health'] == 'healthy':
                break
            if time.monotonic() >= deadline:
                raise InstallError('Database readiness timed out; migration and serving startup were not attempted. Persistent state was preserved.')
            time.sleep(1)
        # Engine health may be from the preceding interval. Recheck the actual
        # effective SQL privilege boundary immediately before migrations.
        runtime.engine('exec', database_name, '/opt/ambisgis/bin/health', 'database')
        # A fresh one-shot container performs native migrations and first-run
        # enrollment under the DB advisory lock. Its secret view never reaches
        # the serving catalog. Repeated runs preserve existing credentials/data.
        runtime.compose('--profile', 'bootstrap', 'run', '--rm', '--no-deps',
                        'catalog-init', timeout=600)
        runtime.compose('--profile', 'bootstrap', 'run', '--rm', '--no-deps',
                        'geoserver-init', timeout=240)
        runtime.compose('up', '-d', '--no-build', '--pull', 'never', *bundle.SERVICES, timeout=180)
        deadline = time.monotonic() + timeout
        result = runtime.status()
        while not result['readiness']['ready'] and time.monotonic() < deadline:
            time.sleep(1)
            result = runtime.status()
        result['command'] = 'up'
        result['ready'] = result['readiness']['ready'] and all(row['process'] == 'running' for row in result['services'].values())
        return result


def status(root):
    with locked(root):
        return Runtime(root).status()


def doctor(root):
    with locked(root):
        runtime = Runtime(root)
        images = {role: runtime.image(role) for role in bundle.SERVICES}
        result = runtime.status()
        result.update(command='doctor', images=images, bundle_verified=True,
                      profile=config.PROFILE, full_installation_acceptance=False)
        if not result['readiness']['ready']:
            result['remediation'] = 'Check the reported dependency and owned service logs. Data and credentials are preserved; no automatic reset is performed.'
        return result
