"""Ordinary local developer runtime adapter. First-party GPL-3.0-or-later.

No engine is invoked by the planners or validators. Only main() executes the
selected ordinary command after input/configuration verification. This adapter
does not implement or authorize vulnerability probes, restore, or checkpoint.
"""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys

from installer import bundle, config
from installer.state import InstallError, atomic_write, checked_path, digest, private_directory, read_json

ROLES = (*bundle.SERVICES, 'catalog-init', 'geoserver-init')
PATH_NAMES = ('home', 'config', 'data', 'run', 'storage', 'networks', 'hooks', 'tmp')


def global_arguments(root):
    paths = {name: root / 'runtime' / name for name in PATH_NAMES}
    return [item for flag, name in (('--root', 'storage'), ('--runroot', 'run'),
            ('--network-config-dir', 'networks'), ('--hooks-dir', 'hooks'), ('--tmpdir', 'tmp'))
            for item in (flag, str(paths[name]))] + ['--events-backend', 'file']


def compose_prefix(root, selected_root, product):
    return ['--in-pod', 'false', '--podman-path', str(selected_root / 'runtime/bin/podman'),
            '--podman-args=' + shlex.join(global_arguments(root)),
            '--env-file', str(root / 'runtime/config/compose.env'), '--no-ansi', '--parallel', '4',
            '-p', config.project_name(product), '-f', str(root / 'compose.json')]


def compose_arguments(arguments, root, selected_root, product):
    prefix = compose_prefix(root, selected_root, product)
    if arguments[:len(prefix)] != prefix:
        raise InstallError('Only the product-generated Compose invocation is supported.')
    tail = arguments[len(prefix):]
    if tail in [['--profile', 'bootstrap', 'run', '-T', '--rm', '--no-deps',
                 '--name', config.project_name(product) + '-' + role, role]
                for role in ('catalog-init', 'geoserver-init')]:
        return arguments
    if tail[:5] == ['up', '-d', '--no-build', '--pull', 'never'] and tail[5:] in [
            ['database'], list(bundle.SERVICES)]:
        return arguments
    # Ordinary lifecycle controls cannot remove images or persistent volumes.
    if tail and tail[0] in ('stop', 'start', 'restart') and tail[1:] and all(x in ROLES for x in tail[1:]):
        if len(set(tail[1:])) == len(tail[1:]): return arguments
    if tail == ['down']: return arguments
    raise InstallError('Unsupported Compose lifecycle command; no producer was executed.')


class NetworkArgumentPlanner:
    """An inert provider argv dependency, never a network permission oracle."""
    async def output(self, arguments, command, tail):
        if arguments or command != 'network' or len(tail) != 2 or tail[0] != 'exists':
            raise InstallError('Unexpected side effect during provider argument planning.')
        return b''


def provider_plan(root, selected_root, product):
    # Import only after complete runtime closure verification. Parse a verified
    # product-generated file, not arbitrary operator Compose/YAML/extensions.
    import podman_compose as provider
    compose = provider.PodmanCompose()
    compose.commands = provider.podman_compose.commands.copy()
    compose._parse_args(compose_prefix(root, selected_root, product) +
                        ['--profile', 'bootstrap', 'up', '-d', '--no-build', '--pull', 'never'])
    compose._parse_compose_file()
    if compose.pods or set(compose.services) != set(ROLES):
        raise InstallError('Provider profile differs from the supported independent containers.')
    compose.podman = NetworkArgumentPlanner()
    return provider, compose


def expected_container(arguments, operation, root, selected_root, product):
    provider, compose = provider_plan(root, selected_root, product)
    if not arguments or not arguments[0].startswith('--name='):
        raise InstallError('Container name is required.')
    actual_name = arguments[0].removeprefix('--name=')
    for role in ROLES:
        cnt = copy.deepcopy(compose.container_by_name[config.project_name(product) + '-' + role])
        if operation == 'create':
            if role.endswith('-init') or cnt['name'] != actual_name: continue
        else:
            if not role.endswith('-init') or cnt['name'] != actual_name: continue
            cnt['tty'] = False
            cnt.pop('restart', None)
        expected = asyncio.run(provider.container_to_args(compose, cnt, detached=False, no_deps=True))
        if operation == 'run': expected[1:1] = ['--rm', '-i']
        if arguments == expected: return
    raise InstallError('Container arguments differ from the exact product configuration.')


def engine_arguments(arguments, root, selected_root, product, selection):
    """Return canonical argv, rejecting unsupported flags without dropping any."""
    # The pinned podman-compose 1.6.0 Podman.output(['--version'], '', [])
    # includes its empty command slot. Canonicalize only this version probe;
    # empty arguments in all other operations remain subject to exact guards.
    if arguments in (['--version'], ['--version', '']): return ['--version']
    globals_ = global_arguments(root)
    if arguments[:len(globals_)] == globals_:
        tail = arguments[len(globals_):]
    elif arguments and arguments[1:1 + len(globals_)] == globals_:
        # podman-compose 1.6.0 places its global options after the command.
        tail = [arguments[0], *arguments[1 + len(globals_):]]
    else:
        raise InstallError('Runtime storage/global arguments differ from the installation.')
    if not tail: raise InstallError('Missing ordinary engine command.')
    project = config.project_name(product)
    names = {project + '-' + role for role in ROLES}
    images = {row['reference'] for row in selection['images'].values()} | {
              row['image_id'] for row in selection['images'].values()}
    command, args = tail[0], tail[1:]
    allowed = False
    if command == 'image':
        allowed = len(args) == 2 and args[0] in ('exists', 'inspect') and args[1] in images
    elif command == 'load':
        allowed = len(args) == 2 and args[0] == '--input' and args[1] in {
            str(selected_root / row['archive']) for row in selection['images'].values()}
    elif command == 'container':
        allowed = len(args) == 2 and args[0] in ('exists', 'inspect') and args[1] in names
    elif command in ('start', 'stop', 'restart', 'rm'):
        remaining = args
        if command in ('stop', 'restart') and remaining[:2] in (['--time', '45'], ['-t', '45']): remaining = remaining[2:]
        allowed = bool(remaining) and len(set(remaining)) == len(remaining) and all(x in names for x in remaining)
    elif command == 'exec':
        allowed = args == [project + '-database', '/opt/ambisgis/bin/health', 'database']
        if len(args) == 4 and args[:3] == [project + '-database', '/opt/ambisgis/python/bin/python3', '-c']:
            pinned = read_json(selected_root / 'runtime/configuration/ordinary-command.json')
            allowed = hashlib.sha256(args[3].encode()).hexdigest() == pinned.get('installed_database_oracle_sha256')
        if len(args) == 4 and args[:3] == [project + '-gateway', '/opt/ambisgis/python/bin/python3', '-c']:
            pinned = read_json(selected_root / 'runtime/configuration/ordinary-command.json')
            allowed = hashlib.sha256(args[3].encode()).hexdigest() == pinned.get('dns_wire_sha256')
        if len(args) == 5:
            for role, key in (('gateway', 'internal_client_sha256'), ('catalog', 'catalog_permission_sha256')):
                if args[:4] == ['-i', project + '-' + role, '/opt/ambisgis/python/bin/python3', '-c']:
                    pinned = read_json(selected_root / 'runtime/configuration/ordinary-command.json')
                    allowed = hashlib.sha256(args[4].encode()).hexdigest() == pinned.get(key)
    elif command == 'ps':
        allowed = args == ['--filter', 'label=io.podman.compose.project=' + project, '-a', '--format', 'json']
    elif command == 'network':
        network = project + '_internal'
        allowed = args in [[op, network] for op in ('exists', 'inspect', 'rm')]
        allowed |= args == ['ls', '--noheading', '--filter', 'label=io.podman.compose.project=' + project,
                            '--format', '{{.Name}}']
        allowed |= args == ['create', '--label', 'io.podman.compose.project=' + project,
                            '--label', 'com.docker.compose.project=' + project, '--label',
                            'org.ambisgis.install-id=' + product['install_id'], '--internal', network]
    elif command in ('create', 'run'):
        expected_container(args, command, root, selected_root, product)
        allowed = True
    if not allowed:
        raise InstallError('Unsupported or unscoped ordinary engine operation; no producer was executed.')
    return globals_ + tail


def configuration_bytes(root, selected_root):
    """All names/options correspond to retained Podman/vendor source fields."""
    def quote(value): return json.dumps(str(value))
    runtime = selected_root / 'runtime'
    paths = {name: root / 'runtime' / name for name in PATH_NAMES}
    config_root = paths['config']
    # JSON strings/arrays have the needed escaping for these TOML values.
    containers = '\n'.join([
        '[containers]', 'http_proxy = false', 'log_driver = "k8s-file"',
        'seccomp_profile = ' + quote(runtime / 'configuration/seccomp.json'),
        '[engine]', 'runtime = "runc"', 'cgroup_manager = "systemd"', 'events_logger = "file"',
        'pull_policy = "never"', 'remote = false', 'env = []', 'conmon_env_vars = []',
        'volume_path = ' + quote(paths['storage'] / 'volumes'),
        'conmon_path = [' + quote(runtime / 'helpers/conmon') + ']',
        'helper_binaries_dir = [' + quote(runtime / 'helpers') + ']',
        'hooks_dir = [' + quote(paths['hooks']) + ']',
        'cdi_spec_dirs = [' + quote(config_root / 'empty-cdi') + ']',
        'compose_providers = [' + quote(runtime / 'bin/compose') + ']',
        'init_path = ' + quote(runtime / 'helpers/catatonit'),
        '[engine.runtimes]', 'runc = [' + quote(runtime / 'helpers/runc') + ']',
        '[network]', 'network_backend = "netavark"', 'default_rootless_network_cmd = "pasta"',
        'network_config_dir = ' + quote(paths['networks']),
        'netavark_plugin_dirs = [' + quote(config_root / 'empty-plugins') + ']',
        'default_host_ips = ["127.0.0.1"]', '',
    ]).encode()
    storage = ('[storage]\ndriver = "vfs"\ngraphroot = ' + quote(paths['storage']) +
               '\nrunroot = ' + quote(paths['run']) + '\n').encode()
    # No registry search or remote transport policy is allowed. The guarded
    # exact local OCI archives and immutable containers-storage are explicit.
    policy = {'default': [{'type': 'reject'}], 'transports': {
        'oci-archive': {'': [{'type': 'insecureAcceptAnything'}]},
        'containers-storage': {'': [{'type': 'insecureAcceptAnything'}]}}}
    return {'containers.conf': containers, 'storage.conf': storage,
            'registries.conf': b'unqualified-search-registries = []\nshort-name-mode = "enforcing"\n',
            'policy.json': (json.dumps(policy, sort_keys=True) + '\n').encode(),
            'mounts.conf': b'', 'compose.env': b''}


def prepare_configs(root, selected_root):
    paths = {name: private_directory(root / 'runtime' / name) for name in PATH_NAMES}
    for name in ('empty-cdi', 'empty-plugins'):
        path = private_directory(paths['config'] / name, create=True)
        if any(path.iterdir()): raise InstallError('Runtime plugin/device directories must remain empty.')
    if any(paths['hooks'].iterdir()): raise InstallError('Installation hooks directory must remain empty.')
    for name, data in configuration_bytes(root, selected_root).items():
        path = checked_path(paths['config'] / name)
        if path.exists():
            if path.stat().st_uid != os.getuid() or stat.S_IMODE(path.stat().st_mode) != 0o600 or path.read_bytes() != data:
                raise InstallError('Runtime configuration differs; no producer was executed.')
        else:
            try: atomic_write(path, data)
            except FileExistsError:
                if path.read_bytes() != data: raise InstallError('Concurrent runtime configuration conflict.')
    return paths


def systemd_user_environment():
    """Select the caller's existing manager independently of private engine XDG."""
    uid = os.getuid()
    user_runtime = checked_path(Path('/run/user') / str(uid))
    info = user_runtime.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise InstallError('An existing private systemd user runtime directory is required.')
    bus = checked_path(user_runtime / 'bus')
    info = bus.stat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != uid:
        raise InstallError('The existing systemd user bus is unavailable.')
    manager = checked_path(user_runtime / 'systemd')
    info = manager.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_mode & 0o022:
        raise InstallError('The existing systemd user manager directory is unsafe.')
    private = checked_path(manager / 'private')
    info = private.stat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077:
        raise InstallError('The existing private systemd user manager socket is unavailable.')
    return {'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(bus),
            'AMBISGIS_SYSTEMD_USER_SOCKET': str(private)}


def child_environment(root, selected_root, *, bus=True):
    runtime = selected_root / 'runtime'; config_root = root / 'runtime/config'
    result = {'HOME': str(root / 'runtime/home'), 'XDG_CONFIG_HOME': str(config_root),
              'XDG_DATA_HOME': str(root / 'runtime/data'), 'XDG_RUNTIME_DIR': str(root / 'runtime/run'),
              'TMPDIR': str(root / 'runtime/tmp'), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
              'PATH': str(runtime / 'bin') + ':' + str(runtime / 'helpers'),
              'LD_LIBRARY_PATH': str(runtime / 'lib64'), 'PYTHONHOME': str(runtime),
              'PYTHONPATH': ':'.join(str(runtime / path) for path in
                  ('modules', 'lib/python3.13/site-packages', 'lib64/python3.13/site-packages')),
              'PYTHONNOUSERSITE': '1', 'PYTHONSAFEPATH': '1', 'PYTHONDONTWRITEBYTECODE': '1',
              'CONTAINERS_CONF': str(config_root / 'containers.conf'),
              'CONTAINERS_STORAGE_CONF': str(config_root / 'storage.conf'),
              'CONTAINERS_REGISTRIES_CONF': str(config_root / 'registries.conf'),
              'CONTAINERS_POLICY_JSON': str(config_root / 'policy.json')}
    if bus:
        result.update(systemd_user_environment())
        # Owned finite native health timers; never inherit an operator selector.
        result['AMBISGIS_HEALTH_TIMER_PROFILE'] = 'development-v1'
    return result


def timer_engine_arguments(arguments, root):
    """The retained GlobalPodmanArgs representation for a native health timer."""
    expected = ['--root', str(root / 'runtime/storage'), '--runroot', str(root / 'runtime/run'),
                '--log-level', 'warning', '--cgroup-manager', 'systemd',
                '--tmpdir', str(root / 'runtime/tmp'), '--network-config-dir', str(root / 'runtime/networks'),
                '--volumepath', str(root / 'runtime/storage/volumes'), '--transient-store=false',
                '--hooks-dir', str(root / 'runtime/hooks'), '--runtime', 'runc',
                '--storage-driver', 'vfs', '--events-backend', 'file',
                'healthcheck', 'run', '--ignore-result']
    if arguments[:-1] != expected or not re.fullmatch(r'[a-f0-9]{64}', arguments[-1]):
        raise InstallError('Native health timer command differs from this installation.')
    return global_arguments(root) + ['healthcheck', 'run', '--ignore-result', arguments[-1]]


def systemd_arguments(arguments, root, selected_root):
    prefix = ['--property', 'LogLevelMax=notice', '--user',
              '--setenv=PATH=' + str(selected_root / 'runtime/bin') + ':' + str(selected_root / 'runtime/helpers'),
              '--unit']
    if arguments[:len(prefix)] != prefix or len(arguments) < len(prefix) + 7:
        raise InstallError('Only native container health timers are supported.')
    name = arguments[len(prefix)]
    fixed = ['--on-unit-inactive=15s', '--timer-property=AccuracySec=1s',
             '--property=StartLimitIntervalSec=0', str(selected_root / 'runtime/engine/podman')]
    if arguments[len(prefix) + 1:len(prefix) + 5] != fixed:
        raise InstallError('Native health timer settings differ.')
    original = arguments[len(prefix) + 5:]
    timer_engine_arguments(original, root)
    if not re.fullmatch(re.escape(original[-1]) + r'-[a-f0-9]+', name):
        raise InstallError('Health timer identity differs from its container.')
    # The native engine forwards only PATH. A fixed bootstrap instead restores
    # the exact loader/config environment when the existing user manager runs
    # this transient healthcheck. No new scheduler or installed unit is added.
    return [*prefix, name, *fixed[:3], '--property=WorkingDirectory=' + str(root),
            str(selected_root / 'runtime/bin/healthcheck-timer'), *original]


def timer_installation(arguments):
    # Native conmon cleanup can run from its container bundle directory. Timer
    # creation therefore binds the explicit engine store path, never ambient
    # cwd or an operator environment variable. The full grammar is checked next.
    if arguments.count('--root') != 1:
        raise InstallError('Health timer requires one private store path.')
    position = arguments.index('--root')
    if position + 1 >= len(arguments): raise InstallError('Missing health timer store path.')
    store = checked_path(arguments[position + 1])
    if store.parts[-2:] != ('runtime', 'storage'):
        raise InstallError('Health timer store path is outside an installation.')
    return store.parent.parent


def context(selected_root, root=None):
    root = private_directory(checked_path(root if root is not None else Path.cwd()))
    product = config.load(root)
    selected_path = checked_path(product['bundle']['path'])
    if selected_path.parent != selected_root:
        raise InstallError('Runtime launcher and installation select different bundles.')
    selection = bundle.load(selected_path, product['bundle']['sha256'], verify_images=False)
    bundle.validate_runtime_paths(selection, root, bundle_root=selected_root)
    expected = config.compose(product, selection, root)
    if read_json(root / 'compose.json', private=True) != expected:
        raise InstallError('Derived Compose configuration differs from product configuration.')
    return root, product, selection


def main(mode, arguments, selected_root):
    """The only dispatch point that can exec; pure tests never call this."""
    if mode == 'ambisgis':
        from installer.__main__ import main as installer_main
        return installer_main(arguments)
    if mode not in ('podman', 'compose', 'newuidmap', 'newgidmap', 'systemd-run', 'healthcheck-timer'):
        raise InstallError('Unknown runtime launcher.')
    if mode in ('newuidmap', 'newgidmap'):
        # Podman passes PID plus numeric mapping triples. The privileged host
        # helpers still enforce caller ownership and /etc/subuid/subgid grants.
        if len(arguments) < 4 or (len(arguments) - 1) % 3 or not all(re.fullmatch(r'[0-9]+', x) for x in arguments):
            raise InstallError('Unsupported subordinate-ID helper arguments.')
        host = '/usr/bin/' + mode
        # The engine may change cwd before asking for a map. Helpers bind the
        # immutable bundle, not a guessed current installation directory.
        prerequisites = read_json(selected_root / 'runtime/configuration/host-prerequisites.json')
        bundle.host_prerequisites(prerequisites)
        if host not in {r['path'] for r in prerequisites['host_tools']}:
            raise InstallError('Privileged host helper lacks an exact prerequisite binding.')
        os.execve(host, [host, *arguments], {'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'})
    root, product, selection = context(selected_root, timer_installation(arguments)
        if mode in ('systemd-run', 'healthcheck-timer') else None)
    if mode == 'compose':
        checked = compose_arguments(arguments, root, selected_root, product)
    elif mode == 'systemd-run':
        checked = systemd_arguments(arguments, root, selected_root)
    elif mode == 'healthcheck-timer':
        checked = timer_engine_arguments(arguments, root)
    else:
        checked = engine_arguments(arguments, root, selected_root, product, selection)
        if 'load' in checked:
            archive = Path(checked[-1])
            image = next(row for row in selection['images'].values() if selected_root / row['archive'] == archive)
            from installer.image_archive import verify
            if digest(archive) != image['archive_sha256']: raise InstallError('Image archive integrity mismatch.')
            verify(archive, image, selection['product_revision'])
    prepare_configs(root, selected_root)
    env = child_environment(root, selected_root)
    if mode in ('podman', 'healthcheck-timer'):
        executable = str(selected_root / 'runtime/engine/podman')
        args = [executable, '--default-mounts-file', str(root / 'runtime/config/mounts.conf'), *checked]
    elif mode == 'systemd-run':
        executable = str(selected_root / 'runtime/engine/systemd-run')
        args = [executable, *checked]
    else:
        executable = str(selected_root / 'runtime/bin/python3.13')
        args = [executable, '-s', '-P', '-m', 'podman_compose', *checked]
    os.execve(executable, args, env)


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1], sys.argv[2:], Path(__file__).resolve().parents[2]))
    except (InstallError, OSError, ValueError, KeyError, TypeError):
        print('Verified ordinary runtime input/configuration failed; no fallback was attempted.', file=sys.stderr)
        raise SystemExit(125)
