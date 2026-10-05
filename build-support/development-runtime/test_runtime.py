"""Pure adapter tests: no engine, provider subprocess, mapping helper or bus."""
import ast
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import ambisgis_runtime as adapter
from installer import config
from installer.state import InstallError


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'installation'; self.root.mkdir(mode=0o700)
        self.bundle = self.base / 'bundle'; self.bundle.mkdir(mode=0o700)
        self.product = {'install_id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', 'listen': {'host': '127.0.0.1', 'port': 8787}}
        self.selection = {'images': {role: {'image_id': 'sha256:' + str(i) * 64,
            'reference': 'localhost/ambisgis/' + role + ':pinned', 'archive': role + '.oci.tar'}
            for i, role in enumerate(adapter.bundle.SERVICES, 1)}}
        self.name = config.project_name(self.product)
        self.globals = adapter.global_arguments(self.root)
        (self.root / 'runtime').mkdir(mode=0o700)
        for name in adapter.PATH_NAMES: (self.root / 'runtime' / name).mkdir(mode=0o700)
        (self.root / 'runtime/config/compose.env').write_bytes(b''); (self.root / 'runtime/config/compose.env').chmod(0o600)
        (self.root / 'compose.json').write_text(json.dumps(config.compose(self.product, self.selection, self.root)))
        self.env = patch.dict(os.environ, {'PATH': '', 'HOME': str(self.base)}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)

    def engine(self, tail):
        return adapter.engine_arguments(self.globals + tail, self.root, self.bundle, self.product, self.selection)

    def test_direct_wrapper_rejects_path_profile_before_derived_configuration(self):
        product = {'bundle': {'path': str(self.bundle / 'bundle.json'), 'sha256': '0' * 64}}
        selection = {'runtime': {'path_profile': 'owned-health-timer-ascii-v1'}}
        with patch.object(adapter.config, 'load', return_value=product), \
             patch.object(adapter.bundle, 'load', return_value=selection), \
             patch.object(adapter.bundle, 'validate_runtime_paths', create=True,
                          side_effect=InstallError('Unsupported ASCII installation path')) as validate, \
             patch.object(adapter.config, 'compose', return_value={}) as compose, \
             patch.object(adapter, 'read_json', return_value={}) as read:
            with self.assertRaisesRegex(InstallError, 'ASCII'):
                adapter.context(self.bundle, self.root)
            validate.assert_called_once_with(selection, self.root, bundle_root=self.bundle)
            compose.assert_not_called()
            read.assert_not_called()

    def test_global_positions_are_preserved_canonically(self):
        tail = ['image', 'exists', self.selection['images']['database']['image_id']]
        self.assertEqual(self.engine(tail), self.globals + tail)
        self.assertEqual(adapter.engine_arguments([tail[0], *self.globals, *tail[1:]], self.root,
            self.bundle, self.product, self.selection), self.globals + tail)
        with self.assertRaises(InstallError): self.engine(['--remote', *tail])
        with self.assertRaises(InstallError): adapter.engine_arguments(tail, self.root, self.bundle, self.product, self.selection)

    def test_real_provider_version_output_empty_command_is_narrowly_canonicalized(self):
        provider_root = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/plt01-runtime/inert-002/runtime/lib/python3.13/site-packages')
        file = provider_root / 'podman_compose.py'
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),
                         '14320ec9102f4aa9602426f2f4e549ca5c6536beb1ccc9de2931ad84e450b919')
        for directory in (provider_root, provider_root.parents[2] / 'lib64/python3.13/site-packages'):
            sys.path.insert(0, str(directory)); self.addCleanup(sys.path.remove, str(directory))
        import podman_compose as provider
        executable = str(self.bundle / 'runtime/bin/podman')
        self.assertEqual(Path(provider.__file__).resolve(), file.resolve())
        process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(b'podman version synthetic\n', b'')))
        # Exercise the exact producer.output implementation, intercepting the
        # subprocess boundary before any child or engine can be created.
        with patch.object(provider.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)) as launch:
            result = asyncio.run(provider.Podman(SimpleNamespace(), executable).output(['--version'], '', []))
        launch.assert_awaited_once()
        self.assertEqual(launch.call_args.args, (executable, '--version', ''))
        self.assertEqual(result, b'podman version synthetic\n')
        self.assertEqual(adapter.engine_arguments(list(launch.call_args.args[1:]), self.root, self.bundle,
                         self.product, self.selection), ['--version'])
        self.assertEqual(adapter.engine_arguments(['--version'], self.root, self.bundle,
                         self.product, self.selection), ['--version'])
        for arguments in (['--version', '', ''], ['--version', '--remote'],
                          self.globals + ['image', '', 'inspect', self.selection['images']['database']['image_id']]):
            with self.assertRaises(InstallError):
                adapter.engine_arguments(arguments, self.root, self.bundle, self.product, self.selection)

    def test_lifecycle_is_named_and_cannot_remove_data_or_pull(self):
        for tail in [['start', self.name + '-database'], ['stop', '--time', '45', self.name + '-catalog'],
                     ['restart', self.name + '-gateway'], ['rm', self.name + '-catalog-init']]:
            self.assertEqual(self.engine(tail), self.globals + tail)
        for tail in [['stop', '--all'], ['rm', '--volumes', self.name + '-database'], ['volume', 'rm', 'anything'],
                     ['pull', 'foreign'], ['build', '.'], ['container', 'restore', self.name + '-database'],
                     ['start', 'unrelated'], ['exec', self.name + '-database', 'sh']]:
            with self.subTest(tail=tail), self.assertRaises(InstallError): self.engine(tail)

    def test_network_is_exact_internal_owned_and_ipv4(self):
        tail = ['network', 'create', '--label', 'io.podman.compose.project=' + self.name,
                '--label', 'com.docker.compose.project=' + self.name, '--label',
                'org.ambisgis.install-id=' + self.product['install_id'], '--internal', self.name + '_internal']
        self.engine(tail)
        for index, replacement in [(tail.index('--internal'), '--ipv6'), (-1, 'unrelated')]:
            bad = tail.copy(); bad[index] = replacement
            with self.assertRaises(InstallError): self.engine(bad)

    def test_compose_exact_no_pod_no_tty_and_no_build(self):
        prefix = adapter.compose_prefix(self.root, self.bundle, self.product)
        for tail in [['up', '-d', '--no-build', '--pull', 'never', 'database'],
                     ['--profile', 'bootstrap', 'run', '-T', '--rm', '--no-deps',
                      '--name', self.name + '-catalog-init', 'catalog-init'], ['down']]:
            self.assertEqual(adapter.compose_arguments(prefix + tail, self.root, self.bundle, self.product), prefix + tail)
        for tail in [['down', '-v'], ['up', '-d', 'database'], ['--profile', 'bootstrap', 'run', '--rm', '--no-deps', 'catalog-init']]:
            with self.assertRaises(InstallError): adapter.compose_arguments(prefix + tail, self.root, self.bundle, self.product)
        with self.assertRaises(InstallError): adapter.compose_arguments(prefix[2:] + ['down'], self.root, self.bundle, self.product)

    def test_configs_have_real_source_fields_and_no_security_disable(self):
        rows = adapter.configuration_bytes(self.root, self.bundle)
        containers = tomllib.loads(rows['containers.conf'].decode())
        storage = tomllib.loads(rows['storage.conf'].decode())
        self.assertEqual(storage['storage']['driver'], 'vfs')
        self.assertEqual(set(storage['storage']), {'driver', 'graphroot', 'runroot'})
        self.assertEqual(storage['storage']['graphroot'], str(self.root / 'runtime/storage'))
        self.assertEqual(containers['engine']['runtime'], 'runc')
        self.assertEqual(containers['containers']['seccomp_profile'], str(self.bundle / 'runtime/configuration/seccomp.json'))
        self.assertEqual(containers['containers']['log_driver'], 'k8s-file')
        self.assertNotIn('label', containers['containers'])
        self.assertNotIn('firewall_driver', containers['network'])
        self.assertNotIn('default_mounts_file', containers['engine'])
        self.assertEqual(json.loads(rows['policy.json'])['default'], [{'type': 'reject'}])

    def test_configs_are_idempotent_and_reject_drift_and_links(self):
        adapter.prepare_configs(self.root, self.bundle)
        before = {p.name: p.read_bytes() for p in (self.root / 'runtime/config').iterdir() if p.is_file()}
        adapter.prepare_configs(self.root, self.bundle)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / 'runtime/config').iterdir() if p.is_file()})
        path = self.root / 'runtime/config/mounts.conf'; path.write_bytes(b'/host:/container')
        with self.assertRaises(InstallError): adapter.prepare_configs(self.root, self.bundle)
        path.unlink(); outside = self.base / 'keep'; outside.write_bytes(b'preserved'); path.symlink_to(outside)
        with self.assertRaises(InstallError): adapter.prepare_configs(self.root, self.bundle)
        self.assertEqual(outside.read_bytes(), b'preserved')

    def test_hooks_and_plugins_cannot_gain_unlisted_code(self):
        adapter.prepare_configs(self.root, self.bundle)
        for relative in ['hooks/evil.json', 'config/empty-cdi/evil.json', 'config/empty-plugins/helper']:
            path = self.root / 'runtime' / relative; path.write_bytes(b'inert')
            with self.assertRaises(InstallError): adapter.prepare_configs(self.root, self.bundle)
            path.unlink()

    def test_child_environment_does_not_inherit_host_overrides(self):
        with patch.dict(os.environ, {'CONTAINER_HOST': 'unix:/other', 'CONTAINERS_CONF_OVERRIDE': '/other',
            'LD_PRELOAD': '/other', 'PYTHONPATH': '/other', 'HOME': '/other', 'PODMAN_COMPOSE_PROVIDER': '/other'}):
            env = adapter.child_environment(self.root, self.bundle, bus=False)
        self.assertNotIn('CONTAINER_HOST', env); self.assertNotIn('CONTAINERS_CONF_OVERRIDE', env)
        self.assertNotIn('LD_PRELOAD', env); self.assertNotIn('PODMAN_COMPOSE_PROVIDER', env)
        self.assertEqual(env['HOME'], str(self.root / 'runtime/home'))

    def test_internal_diagnostic_program_is_exact_not_arbitrary_exec(self):
        source = ROOT / 'deploy/development/journey_probe.py'
        for node in ast.parse(source.read_text()).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'INTERNAL_CLIENT' for t in node.targets):
                program = ast.literal_eval(node.value)
        target = self.bundle / 'runtime/configuration'; target.mkdir(parents=True)
        permission = (ROOT / 'deploy/development/catalog_permission_probe.py').read_text()
        (target / 'ordinary-command.json').write_text(json.dumps({'internal_client_sha256': hashlib.sha256(program.encode()).hexdigest(),
                     'catalog_permission_sha256': hashlib.sha256(permission.encode()).hexdigest()}))
        tail = ['exec', '-i', self.name + '-gateway', '/opt/ambisgis/python/bin/python3', '-c', program]
        self.engine(tail)
        tail[-1] += '\nprint(1)'
        with self.assertRaises(InstallError): self.engine(tail)
        authorized = ['exec','-i',self.name+'-catalog','/opt/ambisgis/python/bin/python3','-c',permission]
        self.engine(authorized)
        for bad in [authorized+['arbitrary-argument'], authorized[:-1]+[permission+'\nprint(1)'],
                    authorized[:-1]+[program], ['exec','-i',self.name+'-gateway',*authorized[3:]],
                    ['exec','-i',self.name+'-catalog-init',*authorized[3:]]]:
            with self.assertRaises(InstallError):self.engine(bad)

    def test_native_timer_has_exact_unit_program_store_and_interval(self):
        cid = 'c' * 64
        original = ['--root', str(self.root / 'runtime/storage'), '--runroot', str(self.root / 'runtime/run'),
            '--log-level', 'warning', '--cgroup-manager', 'systemd', '--tmpdir', str(self.root / 'runtime/tmp'),
            '--network-config-dir', str(self.root / 'runtime/networks'), '--volumepath', str(self.root / 'runtime/storage/volumes'),
            '--transient-store=false', '--hooks-dir', str(self.root / 'runtime/hooks'), '--runtime', 'runc',
            '--storage-driver', 'vfs', '--events-backend', 'file', 'healthcheck', 'run', '--ignore-result', cid]
        args = ['--property', 'LogLevelMax=notice', '--user', '--setenv=PATH=' + str(self.bundle / 'runtime/bin') + ':' +
            str(self.bundle / 'runtime/helpers'), '--unit', cid + '-abc123', '--on-unit-inactive=15s',
            '--timer-property=AccuracySec=1s', '--property=StartLimitIntervalSec=0', str(self.bundle / 'runtime/engine/podman'), *original]
        fixed = adapter.systemd_arguments(args, self.root, self.bundle)
        self.assertEqual(adapter.timer_installation(args), self.root)
        self.assertIn('--property=WorkingDirectory=' + str(self.root), fixed)
        self.assertIn(str(self.bundle / 'runtime/bin/healthcheck-timer'), fixed)
        self.assertEqual(adapter.timer_engine_arguments(original, self.root), self.globals + ['healthcheck', 'run', '--ignore-result', cid])
        for position, value in [(5, 'arbitrary-unit'), (6, '--on-unit-inactive=0'), (9, '/bin/sh'),
                                (11, '/foreign-storage'), (-1, 'd' * 64)]:
            changed = args.copy(); changed[position] = value
            with self.assertRaises(InstallError): adapter.systemd_arguments(changed, self.root, self.bundle)
        for bad in [args + ['--root', str(self.root / 'runtime/storage')], ['--root', '/other/store'], ['--root']]:
            with self.assertRaises(InstallError): adapter.timer_installation(bad)

    def test_dns_wire_program_is_gateway_only_no_stdin_or_extra_arguments(self):
        program = (ROOT / 'deploy/development/dns_wire_probe.py').read_text()
        target = self.bundle / 'runtime/configuration'; target.mkdir(parents=True)
        binding = target / 'ordinary-command.json'
        binding.write_text(json.dumps({'dns_wire_sha256': hashlib.sha256(program.encode()).hexdigest()}))
        tail = ['exec', self.name + '-gateway', '/opt/ambisgis/python/bin/python3', '-c', program]
        self.assertEqual(self.engine(tail), self.globals + tail)
        for bad in [tail + ['8.8.8.8'], tail + ['other.example'], ['exec', '-i', *tail[1:]],
                    ['exec', self.name + '-catalog', *tail[2:]], ['exec', self.name + '-gateway', '/bin/sh'],
                    tail[:-1] + [program + '\nprint(1)'], tail[:-1] + ['print(1)']]:
            with self.subTest(prefix=bad[:4]), self.assertRaises(InstallError): self.engine(bad)
        binding.write_text('{}')
        with self.assertRaises(InstallError): self.engine(tail)


    def oracle_command(self):
        program = (ROOT / 'deploy/development/installed_database_oracle.py').read_text()
        target = self.bundle / 'runtime/configuration'; target.mkdir(parents=True)
        binding = target / 'ordinary-command.json'
        binding.write_text(json.dumps({'installed_database_oracle_sha256': hashlib.sha256(program.encode()).hexdigest()}))
        return binding, ['exec', self.name + '-database', '/opt/ambisgis/python/bin/python3', '-c', program]

    def test_installed_oracle_exact_current_program_is_authorized(self):
        _, tail = self.oracle_command()
        self.assertEqual(self.engine(tail), self.globals + tail)
        self.assertEqual(self.engine(['exec', self.name + '-database', '/opt/ambisgis/bin/health', 'database']),
                         self.globals + ['exec', self.name + '-database', '/opt/ambisgis/bin/health', 'database'])

    def test_installed_oracle_missing_stale_and_malformed_pins_are_denied(self):
        binding, tail = self.oracle_command()
        for value in ({}, {'installed_database_oracle_sha256': '0' * 64},
                      {'installed_database_oracle_sha256': True}, {'installed_database_oracle_sha256': None},
                      {'installed_database_oracle_sha256': ['wrong']}, {'installed_database_oracle_sha256': 1}):
            binding.write_text(json.dumps(value))
            with self.subTest(value=value), self.assertRaises(InstallError): self.engine(tail)
        binding.unlink()
        with self.assertRaises((InstallError, OSError)): self.engine(tail)

    def test_installed_oracle_rejects_other_roles_stdin_flags_interpreter_and_extra_args(self):
        _, tail = self.oracle_command()
        variants = [tail + ['extra'], ['exec', '-i', *tail[1:]], ['exec', '--user', '0', *tail[1:]],
                    ['exec', tail[1], '/bin/sh', '-c', tail[-1]], tail[:-2] + ['-m', tail[-1]]]
        variants += [['exec', self.name + '-' + role, *tail[2:]] for role in
                     ('gateway', 'catalog', 'geoserver', 'database-init', 'catalog-init', 'geoserver-init')]
        variants += [['exec', 'foreign-database', *tail[2:]]]
        for bad in variants:
            with self.subTest(prefix=bad[:4]), self.assertRaises(InstallError): self.engine(bad)

    def test_installed_oracle_rejects_changed_program_and_cross_registered_programs(self):
        binding, tail = self.oracle_command()
        foreign = (ROOT / 'deploy/development/dns_wire_probe.py').read_text()
        value = json.loads(binding.read_text()); value['dns_wire_sha256'] = hashlib.sha256(foreign.encode()).hexdigest()
        binding.write_text(json.dumps(value))
        for program in (tail[-1] + '\n', tail[-1] + '\nprint(1)', tail[-1][:-1], 'print(1)', '', foreign):
            with self.subTest(size=len(program)), self.assertRaises(InstallError): self.engine(tail[:-1] + [program])

    def test_real_retained_provider_arguments_match_all_six_roles_without_execution(self):
        provider_root = os.environ.get('AMBISGIS_TEST_PROVIDER')
        # The test runner supplies the exact already-reviewed retained provider;
        # no installation, engine or provider subprocess is used.
        if not provider_root:
            provider_root = '/home/revelberry/Projects/AmbisGIS/build-worktrees/plt01-runtime/inert-002/runtime/lib/python3.13/site-packages'
        file = Path(provider_root) / 'podman_compose.py'
        if hashlib.sha256(file.read_bytes()).hexdigest() != '14320ec9102f4aa9602426f2f4e549ca5c6536beb1ccc9de2931ad84e450b919':
            raise AssertionError('retained provider identity changed')
        sys.path.insert(0, provider_root); self.addCleanup(sys.path.remove, provider_root)
        yaml_root = str(Path(provider_root).parents[2] / 'lib64/python3.13/site-packages')
        sys.path.insert(0, yaml_root); self.addCleanup(sys.path.remove, yaml_root)
        with patch('subprocess.Popen', side_effect=AssertionError('subprocess forbidden')):
            provider, compose = adapter.provider_plan(self.root, self.bundle, self.product)
            for role in adapter.ROLES:
                cnt = copy.deepcopy(compose.container_by_name[self.name + '-' + role])
                operation = 'run' if role.endswith('-init') else 'create'
                if operation == 'run':
                    args = compose._parse_args(adapter.compose_prefix(self.root, self.bundle, self.product) +
                        ['--profile', 'bootstrap', 'run', '-T', '--rm', '--no-deps', '--name', self.name + '-' + role, role])
                    provider.compose_run_update_container_from_args(compose, cnt, args)
                    self.assertEqual(cnt['name'], self.name + '-' + role)
                arguments = asyncio.run(provider.container_to_args(compose, cnt, detached=False, no_deps=True))
                if operation == 'run': arguments[1:1] = ['--rm', '-i']
                self.engine([operation, *arguments])
                if operation == 'run':
                    with self.assertRaises(InstallError): self.engine([operation, '--name=' + compose.format_name(role, 'tmp321'), *arguments[1:]])
                for extra in ['--privileged', '--pull=always', '--annotation=unreviewed=true']:
                    with self.assertRaises(InstallError): self.engine([operation, arguments[0], extra, *arguments[1:]])
                with self.assertRaises(InstallError): self.engine([operation, *arguments[:-2], 'sha256:' + 'f' * 64, role])


if __name__ == '__main__': unittest.main()
