"""Installer state/negative guards; these are not container or GIS acceptance."""
import hashlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/development'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/control-plane'))
from installer import bundle, config, runtime
from installer.state import InstallError, canonical, digest, locked
from ambisgis_development import common, database, gateway, geoserver
from installer import image_archive


def oci_input(path, reference, source, revision, alter=None, extra=None):
    """Inert OCI metadata/layer bytes for archive guards; never loaded/executed."""
    alter = alter or (lambda stage, value: None)
    content = io.BytesIO()
    with tarfile.open(fileobj=content, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        row = tarfile.TarInfo('inert-unit-input.txt'); payload = b'no executable product\n'; row.size = len(payload)
        archive.addfile(row, io.BytesIO(payload))
    layer = content.getvalue()
    blob = lambda data: 'sha256:' + hashlib.sha256(data).hexdigest()
    config_value = {'architecture': 'amd64', 'os': 'linux', 'config': {'Labels': {
        'org.ambisgis.source-manifest-sha256': source, 'org.opencontainers.image.revision': revision}},
        'rootfs': {'type': 'layers', 'diff_ids': [blob(layer)]}}
    alter('config', config_value); config_bytes = canonical(config_value)
    manifest = {'schemaVersion': 2, 'mediaType': image_archive.MANIFEST,
                'config': {'mediaType': image_archive.CONFIG, 'digest': blob(config_bytes), 'size': len(config_bytes)},
                'layers': [{'mediaType': image_archive.LAYER, 'digest': blob(layer), 'size': len(layer)}]}
    alter('manifest', manifest); manifest_bytes = canonical(manifest)
    index = {'schemaVersion': 2, 'manifests': [{'mediaType': image_archive.MANIFEST,
        'digest': blob(manifest_bytes), 'size': len(manifest_bytes),
        'annotations': {'org.opencontainers.image.ref.name': reference}, 'platform': {'architecture': 'amd64', 'os': 'linux'}}]}
    alter('index', index)
    members = {'oci-layout': canonical({'imageLayoutVersion': '1.0.0'}), 'index.json': canonical(index),
               'blobs/sha256/' + blob(config_bytes)[7:]: config_bytes,
               'blobs/sha256/' + blob(manifest_bytes)[7:]: manifest_bytes, 'blobs/sha256/' + blob(layer)[7:]: layer}
    with tarfile.open(path, 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name, payload in members.items():
            row = tarfile.TarInfo(name); row.size = len(payload); archive.addfile(row, io.BytesIO(payload))
        if extra: extra(archive)
    return blob(config_bytes)


class InstallerStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / 'installation'
        self.inputs = self.base / 'bundle'
        self.inputs.mkdir()
        (self.inputs / 'bin').mkdir()
        for tool in ('podman', 'compose'):
            # Inert bytes used only for input verification. Never executed.
            (self.inputs / 'bin' / tool).write_bytes(b'configuration test input\n')
            (self.inputs / 'bin' / tool).chmod(0o700)
        (self.inputs / 'source.json').write_bytes(b'{"test_only":true}\n')
        self.put('closure.json', {'schema_version': 1, 'roots': ['bin'], 'files': [self.ref('bin/podman'), self.ref('bin/compose')]})
        helper = self.inputs / 'bin/podman'
        self.put('prerequisites.json', {'schema_version': 1, 'host_tools': [{
            'path': str(helper), 'sha256': digest(helper), 'uid': os.getuid(), 'gid': os.getgid(),
            'mode': 0o700, 'capability_hex': ''}], 'requirements': {
                'kernel_release': os.uname().release, 'minimum_subordinate_ids': 65536,
                'cgroup_controllers': ['cpu', 'memory', 'pids'], 'fuse_required': False}})
        original_read = Path.read_text
        def observed_host(path, *args, **kwargs):
            # Explicit synthetic host observations for configuration guards;
            # real mapping/cgroup/namespace behavior belongs to runtime acceptance.
            if str(path) in ('/etc/subuid', '/etc/subgid'):
                return str(os.getuid()) + ':100000:65536\n'
            if str(path) == '/sys/fs/cgroup/cgroup.controllers':
                return 'cpu memory pids'
            return original_read(path, *args, **kwargs)
        self.host_observations = patch.object(Path, 'read_text', observed_host)
        self.host_observations.start()
        self.document = {
            'schema_version': 1, 'kind': 'ambisgis.development-bundle',
            'target': {'os': 'linux', 'architecture': 'x86_64'}, 'product_revision': '1' * 40,
            'source_manifest': self.ref('source.json'),
            'runtime': {'podman': self.ref('bin/podman'), 'compose': self.ref('bin/compose'),
                        'files_manifest': self.ref('closure.json'), 'prerequisites': self.ref('prerequisites.json'),
                        'environment': {'PATH': ['bin']}},
            'images': {},
        }
        for role in bundle.SERVICES:
            reference = 'localhost/ambisgis/' + role + ':unit-input'
            archive = 'image.tar' if role == 'database' else role + '.tar'
            image_id = oci_input(self.inputs / archive, reference, digest(self.inputs / 'source.json'), '1' * 40)
            self.document['images'][role] = {'archive': archive, 'archive_sha256': digest(self.inputs / archive),
                'reference': reference, 'image_id': image_id, 'source_manifest_sha256': digest(self.inputs / 'source.json')}
        self.manifest = self.inputs / 'bundle.json'
        self.seal()

    def tearDown(self):
        self.host_observations.stop()
        self.temporary.cleanup()

    def ref(self, name):
        return {'path': name, 'sha256': digest(self.inputs / name)}

    def put(self, name, value):
        (self.inputs / name).write_bytes(canonical(value))

    def seal(self):
        self.put('bundle.json', self.document)
        self.identity = digest(self.manifest)

    def init(self, **kwargs):
        return config.initialize(self.root, self.manifest, self.identity, **kwargs)

    def state(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_reinitialize_preserves_principals_secrets_and_data(self):
        first = self.init()
        (self.root / 'data/postgres/synthetic-row').write_text('persistent user state')
        before = self.state()
        second = self.init()
        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(first['install_id'], second['install_id'])
        self.assertEqual(before, self.state())

    def test_conflicting_reinitialize_does_not_mutate(self):
        self.init(port=18999)
        before = self.state()
        for kwargs in ({'port': 19000}, {'owner': 'another'}, {'viewer': 'another'}):
            with self.assertRaises(InstallError):
                self.init(**kwargs)
            self.assertEqual(before, self.state())

    def test_existing_unmarked_data_is_never_adopted(self):
        self.root.mkdir()
        (self.root / 'important.txt').write_text('keep')
        with self.assertRaises(InstallError):
            self.init()
        self.assertEqual(list(self.root.iterdir()), [self.root / 'important.txt'])

    def test_invalid_first_init_leaves_no_partial_installation(self):
        for kwargs in ({'port': 80}, {'owner': ''}, {'owner': 'same', 'viewer': 'same'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(InstallError):
                self.init(**kwargs)
            self.assertFalse(self.root.exists())

    def test_database_failure_prevents_migrations_and_serving(self):
        self.init()
        with patch.object(runtime, 'Runtime') as factory:
            selected = factory.return_value
            selected.root, selected.config, selected.selection = self.root, config.load(self.root), self.document
            selected.processes.return_value = {'database': {'process': 'stopped', 'engine_health': 'unhealthy'}}
            before = self.state()
            with self.assertRaisesRegex(InstallError, 'Database readiness'):
                runtime.up(self.root, timeout=0)
            self.assertEqual([tuple(call.args) for call in selected.compose.call_args_list],
                             [('up', '-d', '--no-build', '--pull', 'never', 'database')])
            self.assertEqual(before, self.state())

    def test_migration_failure_prevents_serving(self):
        self.init()
        with patch.object(runtime, 'Runtime') as factory:
            selected = factory.return_value
            selected.root, selected.config, selected.selection = self.root, config.load(self.root), self.document
            selected.processes.return_value = {'database': {'process': 'running', 'engine_health': 'healthy'}}
            selected.compose.side_effect = [None, InstallError('initialization failed')]
            with self.assertRaisesRegex(InstallError, 'initialization failed'):
                runtime.up(self.root, timeout=0)
            commands = [tuple(call.args) for call in selected.compose.call_args_list]
            self.assertEqual(commands[-1], ('--profile', 'bootstrap', 'run', '--rm', '--no-deps', 'catalog-init'))
            self.assertEqual(len(commands), 2)

    def test_fresh_sql_health_failure_prevents_repeat_up_mutations(self):
        self.init()
        with patch.object(runtime, 'Runtime') as factory:
            selected = factory.return_value
            selected.root, selected.config, selected.selection = self.root, config.load(self.root), self.document
            selected.processes.return_value = {'database': {'process': 'running', 'engine_health': 'healthy'}}
            selected.engine.side_effect = InstallError('effective privilege drift')
            before = self.state()
            with self.assertRaisesRegex(InstallError, 'privilege drift'): runtime.up(self.root, timeout=0)
            selected.compose.assert_not_called()
            self.assertEqual(selected.engine.call_args.args, ('exec', config.project_name(selected.config) + '-database', '/opt/ambisgis/bin/health', 'database'))
            self.assertEqual(before, self.state())

    def test_image_inspection_error_does_not_trigger_load(self):
        self.init()
        selected = runtime.Runtime(self.root)
        with patch.object(selected, 'engine', return_value=(125, b'private diagnostic')) as engine:
            with self.assertRaisesRegex(InstallError, 'no mutation'):
                selected.image('database', load=True)
            self.assertEqual(engine.call_count, 1)

    def test_image_label_substitution_rejected(self):
        self.init()
        selected = runtime.Runtime(self.root)
        row = {'Id': self.document['images']['database']['image_id'], 'Labels': {
            'org.ambisgis.source-manifest-sha256': '0' * 64,
            'org.opencontainers.image.revision': self.document['product_revision']}}
        with patch.object(selected, 'engine', side_effect=[(0, b''), (0, json.dumps([row]).encode())]):
            with self.assertRaisesRegex(InstallError, 'identity/source'):
                selected.image('database')

    def test_second_installation_gets_independent_credentials(self):
        self.init()
        first = config.secret_material(self.root)
        self.root = self.base / 'second'
        self.init()
        self.assertFalse(set(first.values()) & set(config.secret_material(self.root).values()))

    def test_only_gateway_is_loopback_published_and_no_socket_or_privilege(self):
        self.init()
        value = json.loads((self.root / 'compose.json').read_text())
        for role, service in value['services'].items():
            self.assertEqual(service.get('ports', []), ['127.0.0.1:8787:8000'] if role == 'gateway' else [])
            self.assertEqual(service['pull_policy'], 'never')
            self.assertNotIn('build', service)
            self.assertNotIn('privileged', service)
            self.assertEqual(service['cap_drop'], ['ALL'])
            self.assertFalse(any('sock' in entry['source'] for entry in service['volumes']))
        self.assertTrue(value['networks']['internal']['internal'])

    def test_compose_is_regenerated_from_product_authority(self):
        self.init()
        expected = (self.root / 'compose.json').read_bytes()
        (self.root / 'compose.json').write_text('{"services":{"evil":{}}}')
        self.init()
        self.assertEqual((self.root / 'compose.json').read_bytes(), expected)

    def test_catalog_secrets_never_reach_gateway_or_compose(self):
        self.init()
        secrets = config.secret_material(self.root)
        gateway = json.loads((self.root / 'generated/gateway-secrets.json').read_text())
        self.assertEqual(set(gateway), {'policy_key', 'health_token'})
        catalog = json.loads((self.root / 'generated/catalog-secrets.json').read_text())
        self.assertNotIn('catalog_migrator', catalog)
        self.assertNotIn('owner_password', catalog)
        compose = (self.root / 'compose.json').read_text()
        self.assertTrue(all(secret not in compose for secret in secrets.values()))
        for p in (self.root / 'secrets/product.json', self.root / 'generated/catalog-secrets.json'):
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_changed_runtime_bytes_are_rejected_before_state_creation(self):
        (self.inputs / 'bin/podman').write_bytes(b'changed')
        with self.assertRaises(InstallError): self.init()
        self.assertFalse(self.root.exists())

    def closure(self, value):
        self.put('closure.json', value)
        self.document['runtime']['files_manifest'] = self.ref('closure.json')
        self.seal()

    def test_unlisted_startup_module_helper_or_library_rejected_before_execution(self):
        for directory in ('python', 'python/package', 'lib', 'helpers'):
            (self.inputs / directory).mkdir(exist_ok=True)
        value = json.loads((self.inputs / 'closure.json').read_text())
        value.update(roots=['bin', 'python', 'lib', 'helpers'], directories=['python/package', 'lib', 'helpers'])
        self.closure(value)
        self.document['runtime']['environment'].update(PYTHONPATH=['python'], LD_LIBRARY_PATH=['lib'])
        self.seal(); self.init()
        for name in ('python/sitecustomize.py', 'python/startup.pth', 'python/package/__init__.py',
                     'helpers/unlisted-conmon', 'lib/libunlisted.so'):
            with self.subTest(name=name):
                added = self.inputs / name
                added.write_bytes(b'unlisted executable input; must never be loaded\n')
                before = self.state(); identity = digest(self.manifest)
                with patch.object(runtime.subprocess, 'run') as execute:
                    with self.assertRaisesRegex(InstallError, 'unmanifested'): self.init()
                    with self.assertRaisesRegex(InstallError, 'unmanifested'): runtime.Runtime(self.root)
                    execute.assert_not_called()
                self.assertEqual(before, self.state())
                self.assertEqual(identity, digest(self.manifest))
                self.assertFalse((self.root / 'runtime').exists())
                added.unlink()

    def test_closure_rejects_special_unlisted_link_and_directory(self):
        name = self.inputs / 'bin/extra'
        for kind in ('fifo', 'symlink', 'directory'):
            with self.subTest(kind=kind):
                if kind == 'fifo': os.mkfifo(name)
                elif kind == 'symlink': name.symlink_to('podman')
                else: name.mkdir()
                with self.assertRaises(InstallError): self.init()
                self.assertFalse(self.root.exists())
                name.rmdir() if kind == 'directory' else name.unlink()

    def test_declared_relative_link_and_empty_directory_are_verified(self):
        (self.inputs / 'bin/alias').symlink_to('podman')
        (self.inputs / 'bin/empty').mkdir()
        value = json.loads((self.inputs / 'closure.json').read_text())
        value.update(symlinks=[{'path': 'bin/alias', 'target': 'podman'}], directories=['bin/empty'])
        self.closure(value)
        self.init()
        (self.inputs / 'bin/alias').unlink()
        (self.inputs / 'bin/alias').symlink_to('compose')
        with self.assertRaises(InstallError): runtime.Runtime(self.root)

    def test_closure_roots_and_ancestors_cannot_be_writable(self):
        for path in (self.inputs, self.inputs / 'bin'):
            mode = path.stat().st_mode & 0o777
            path.chmod(0o777)
            try:
                with self.assertRaisesRegex(InstallError, 'directories'): self.init()
                self.assertFalse(self.root.exists())
            finally: path.chmod(mode)
        (self.inputs / 'runtime/nested').mkdir(parents=True)
        (self.inputs / 'runtime/nested/input').write_bytes(b'retained')
        value = {'schema_version': 1, 'roots': ['runtime/nested'], 'files': [self.ref('runtime/nested/input')]}
        self.closure(value)
        (self.inputs / 'runtime').chmod(0o777)
        with self.assertRaisesRegex(InstallError, 'directories'):
            bundle.verify_manifest(self.inputs, self.ref('closure.json'))

    def test_search_directory_must_be_in_complete_manifest_root(self):
        (self.inputs / 'unlisted-python').mkdir()
        self.document['runtime']['environment']['PYTHONPATH'] = ['unlisted-python']
        self.seal()
        with self.assertRaisesRegex(InstallError, 'search paths'): self.init()
        self.assertFalse(self.root.exists())

    def test_malformed_overlapping_or_aliased_closure_roots_rejected(self):
        original = json.loads((self.inputs / 'closure.json').read_text())
        for roots in ([], ['.'], ['bin', 'bin'], ['bin/'], ['bin', 'bin/nested']):
            with self.subTest(roots=roots):
                self.closure(dict(original, roots=roots))
                with self.assertRaises(InstallError): self.init()
                self.assertFalse(self.root.exists())

    def test_replaced_data_bind_directories_rejected_without_changes_or_execution(self):
        self.init()
        outside = self.base / 'outside'; outside.mkdir(mode=0o700)
        sentinel = outside / 'do-not-touch'; sentinel.write_bytes(b'external data')
        for relative in ('data', *('data/' + name for name in config.DATA_NAMES)):
            with self.subTest(path=relative):
                path = self.root / relative; saved = path.with_name(path.name + '-saved')
                path.rename(saved); path.symlink_to(outside, target_is_directory=True)
                before = self.state()
                try:
                    with patch.object(runtime.subprocess, 'run') as execute:
                        with self.assertRaises(InstallError): self.init()
                        with self.assertRaises(InstallError): runtime.up(self.root)
                        execute.assert_not_called()
                    self.assertEqual(before, self.state())
                    self.assertEqual(list(outside.iterdir()), [sentinel])
                    self.assertEqual(sentinel.read_bytes(), b'external data')
                    self.assertFalse((self.root / 'runtime').exists())
                finally:
                    path.unlink(); saved.rename(path)

    def test_unsafe_data_directory_modes_fail_without_permission_repair(self):
        self.init()
        for path in (self.root / 'data', *(self.root / 'data' / name for name in config.DATA_NAMES)):
            with self.subTest(path=path):
                path.chmod(0o750); before = self.state()
                try:
                    with self.assertRaises(InstallError): self.init()
                    with self.assertRaises(InstallError): runtime.Runtime(self.root)
                    self.assertEqual(path.stat().st_mode & 0o777, 0o750)
                    self.assertEqual(before, self.state())
                finally: path.chmod(0o700)

    def test_role_memberships_and_ownership_fail_before_bootstrap_mutations(self):
        # Query scheduling regression only; actual PostgreSQL catalog semantics
        # and SET ROLE/DML/DDL behavior still require the native acceptance run.
        for trigger in ('pg_auth_members', 'pg_shdepend', 'rolsuper'):
            for role in database.SERVING_ROLES:
                with self.subTest(trigger=trigger, role=role):
                    statements = []
                    def sql(statement, *args, **kwargs):
                        statements.append(statement)
                        return '1' if trigger in statement and "rolname='" + role + "'" in statement else '0'
                    with patch.object(database, 'sql', side_effect=sql):
                        with self.assertRaises(ValueError): database.bootstrap({}, {'database_admin': 'private-test-value'})
                    self.assertTrue(all(statement.startswith('SELECT ') for statement in statements))

    def test_changed_archive_is_rejected_before_state_creation(self):
        (self.inputs / 'image.tar').write_bytes(b'changed')
        with self.assertRaises(InstallError): self.init()
        self.assertFalse(self.root.exists())

    def test_source_binding_mismatch_is_rejected(self):
        self.document['images']['catalog']['source_manifest_sha256'] = 'f' * 64
        self.seal()
        with self.assertRaises(InstallError): self.init()

    def test_operator_environment_cannot_redirect_engine_or_provider(self):
        for key in ('CONTAINER_HOST', 'CONTAINER_CONNECTION', 'PODMAN_COMPOSE_PROVIDER', 'HOME', 'LD_PRELOAD'):
            self.document['runtime']['environment'] = {key: ['bin']}
            self.seal()
            with self.assertRaises(InstallError): self.init()

    def test_child_environment_excludes_operator_startup_and_connection_paths(self):
        self.init()
        with patch.dict(os.environ, {'CONTAINER_HOST': 'unix:///untrusted', 'CONTAINER_CONNECTION': 'untrusted',
                                    'PYTHONPATH': '/untrusted', 'PYTHONHOME': '/untrusted',
                                    'LD_PRELOAD': '/untrusted.so', 'PODMAN_COMPOSE_PROVIDER': '/untrusted'}):
            selected = runtime.Runtime(self.root)
        for name in ('CONTAINER_HOST', 'CONTAINER_CONNECTION', 'PYTHONHOME', 'LD_PRELOAD', 'PODMAN_COMPOSE_PROVIDER'):
            self.assertNotIn(name, selected.environment)
        self.assertEqual(selected.environment['PYTHONSAFEPATH'], '1')
        self.assertEqual(selected.environment['PYTHONNOUSERSITE'], '1')
        self.assertNotIn('PYTHONPATH', selected.environment)
        self.assertEqual(selected.environment['PATH'], str(self.inputs / 'bin'))
        self.assertEqual(selected.environment['HOME'], str(self.root / 'runtime/home'))

    def test_bundle_escape_and_symlink_parent_are_rejected(self):
        self.document['runtime']['podman']['path'] = '../bundle/bin/podman'
        self.seal()
        with self.assertRaises(InstallError): self.init()
        link = self.base / 'linked'
        link.symlink_to(self.inputs, target_is_directory=True)
        with self.assertRaises(InstallError): bundle.load(link / 'bundle.json', self.identity)

    def test_symlink_installation_and_secret_are_rejected(self):
        real = self.base / 'real'; real.mkdir(mode=0o700)
        self.root.symlink_to(real, target_is_directory=True)
        with self.assertRaises(InstallError): self.init()
        self.assertEqual(list(real.iterdir()), [])
        self.root.unlink(); self.init()
        secret = self.root / 'secrets/product.json'
        saved = secret.read_bytes(); secret.unlink()
        target = self.base / 'outside'; target.write_bytes(saved)
        secret.symlink_to(target)
        with self.assertRaises(InstallError): self.init()
        self.assertEqual(target.read_bytes(), saved)

    def test_public_secret_mode_fails_without_rewriting(self):
        self.init(); p = self.root / 'secrets/product.json'; p.chmod(0o644)
        before = self.state()
        with self.assertRaises(InstallError): self.init()
        self.assertEqual(before, self.state())

    def test_configuration_cannot_enable_remote_binding(self):
        self.init(); p = self.root / 'product.json'
        value = json.loads(p.read_text()); value['listen']['host'] = '0.0.0.0'; p.write_bytes(canonical(value))
        with self.assertRaises(InstallError): config.load(self.root)

    def test_duplicate_json_keys_do_not_override_validation(self):
        self.manifest.write_bytes(b'{"schema_version":1,"schema_version":2}')
        with self.assertRaises(InstallError): bundle.load(self.manifest, digest(self.manifest))

    def test_competing_lifecycle_commands_fail_closed(self):
        self.init()
        with locked(self.root):
            with self.assertRaises(InstallError): self.init()

    def test_wrong_host_capability_or_mode_is_rejected(self):
        path = self.inputs / 'prerequisites.json'
        original = json.loads(path.read_text())
        for key, value in [('capability_hex', 'f' * 40), ('mode', 0o4755), ('uid', os.getuid() + 1)]:
            candidate = json.loads(json.dumps(original))
            candidate['host_tools'][0][key] = value
            self.put('prerequisites.json', candidate)
            self.document['runtime']['prerequisites'] = self.ref('prerequisites.json')
            self.seal()
            with self.assertRaises(InstallError): self.init()

    def test_missing_controller_and_subordinate_range_fail_closed(self):
        requirements = json.loads((self.inputs / 'prerequisites.json').read_text())
        requirements['requirements']['cgroup_controllers'].append('not-a-controller')
        with self.assertRaises(InstallError): bundle.host_prerequisites(requirements)
        requirements['requirements']['cgroup_controllers'].pop()
        requirements['requirements']['minimum_subordinate_ids'] = 131072
        with self.assertRaises(InstallError): bundle.host_prerequisites(requirements)

    def test_native_service_inputs_reject_duplicate_keys_public_modes_and_symlinks(self):
        path = self.base / 'service.json'
        path.write_bytes(b'{"install_id":"first","install_id":"second"}'); path.chmod(0o600)
        with self.assertRaises(ValueError): common.read(path)
        path.write_bytes(b'{}'); path.chmod(0o644)
        with self.assertRaises(ValueError): common.read(path)
        path.chmod(0o600)
        alias = self.base / 'service-link.json'; alias.symlink_to(path)
        with self.assertRaises(ValueError): common.read(alias)
        path.write_bytes(b'[' + b' ' * 65536 + b']')
        with self.assertRaises(ValueError): common.read(path)

    def test_gateway_unsupported_queries_never_reach_policy_or_engine(self):
        from urllib.parse import urlencode
        for route, valid in [('/wfs', gateway.WFS), ('/map', gateway.WMS)]:
            queries = [urlencode(valid) + '&unknown=1', urlencode(valid) + '&SERVICE=WFS', '', 'x=%',
                       urlencode(dict(valid, typename='fixture:other')) if route == '/wfs' else urlencode(dict(valid, layers='fixture:other'))]
            for query in queries:
                with self.subTest(route=route, query=query), patch.object(gateway, 'policy') as decision, patch.object(gateway, 'request') as engine:
                    self.assertEqual(gateway.data_response({}, {}, route, query, 'Bearer invalid-value')[0], 403)
                    decision.assert_not_called(); engine.assert_not_called()

    def test_gateway_policy_outage_denies_without_engine_request(self):
        from urllib.parse import urlencode
        with patch.object(gateway, 'request', side_effect=OSError('private detail')) as backend:
            result = gateway.data_response({'catalog_origin': 'http://catalog:8000'}, {'policy_key': 'a' * 64},
                                           '/wfs', urlencode(gateway.WFS), 'Bearer ' + 'b' * 40)
            self.assertEqual(result, (403, 'text/plain', b''))
            self.assertEqual(backend.call_count, 1)

    def test_internal_redirect_and_oversized_response_rejected(self):
        for redirect, payload in [('http://elsewhere.invalid', b''), (None, b'x' * 33)]:
            with patch.object(common.http.client, 'HTTPConnection') as factory:
                reply = factory.return_value.getresponse.return_value
                reply.getheader.return_value = redirect; reply.read.return_value = payload
                with self.assertRaises(ValueError): common.request('http://catalog:8000', 'GET', '/internal/policy/read', limit=32)
                factory.return_value.close.assert_called_once()

    def test_gateway_drops_forged_internal_headers(self):
        env = {'PATH_INFO': '/o/token/', 'REQUEST_METHOD': 'POST', 'QUERY_STRING': '', 'wsgi.input': io.BytesIO(b''),
               'HTTP_X_AMBISGIS_POLICY_KEY': 'forged', 'HTTP_X_AMBISGIS_RESOURCE': 'fixture:other',
               'HTTP_X_FORWARDED_HOST': 'attacker.invalid', 'HTTP_HOST': 'attacker.invalid', 'HTTP_AUTHORIZATION': 'Bearer a',
               'CONTENT_TYPE': 'application/x-www-form-urlencoded'}
        with patch.object(gateway.http.client, 'HTTPConnection') as factory:
            reply = factory.return_value.getresponse.return_value
            reply.status = 403; reply.read.return_value = b''; reply.getheaders.return_value = []
            reply.getheader.return_value = 'text/plain'
            gateway.catalog_proxy({'public_origin': 'http://127.0.0.1:8787'}, env, lambda *_: None)
            forwarded = factory.return_value.request.call_args.kwargs['headers']
            self.assertEqual(set(forwarded), {'Host', 'Authorization', 'Content-Type'})
            self.assertEqual(forwarded['Host'], '127.0.0.1:8787')

    def test_gateway_external_or_ambiguous_redirect_is_blocked(self):
        for location in ['//attacker.invalid/', '\\\\attacker.invalid/', 'https://attacker.invalid/', 'http://127.0.0.1:8787@attacker.invalid/', '/ok\r\nInjected:yes']:
            with self.subTest(location=location), patch.object(gateway.http.client, 'HTTPConnection') as factory:
                reply = factory.return_value.getresponse.return_value
                reply.status = 302; reply.read.return_value = b''; reply.getheaders.return_value = [('Location', location)]
                reply.getheader.return_value = 'text/plain'
                statuses = []
                gateway.catalog_proxy({'public_origin': 'http://127.0.0.1:8787'},
                    {'PATH_INFO': '/o/authorize/', 'REQUEST_METHOD': 'GET', 'wsgi.input': io.BytesIO(b'')},
                    lambda status, headers: statuses.append(status))
                self.assertEqual(statuses, ['503 Service Unavailable'])

    def test_engine_migration_secrets_are_only_in_private_derived_projection(self):
        self.init()
        data, engine = self.base / 'engine-data', self.base / 'engine-inputs'
        (data / 'assets').mkdir(parents=True); (engine / 'lib').mkdir(parents=True)
        (data / 'assets/private_points.properties').write_bytes(geoserver.POINTS)
        (data / 'assets/diagnostic.sld').write_bytes(geoserver.STYLE)
        (engine / 'application.war').write_bytes(b'inert input; no Java execution')
        profile = {'schema_version': 1, 'profile': 'NO-ORACLE-NO-JPEG2000-headless-Temurin17',
                   'war_sha256': digest(engine / 'application.war')}
        for key, name in [('renderer', 'marlin-0.9.4.8.jar'), ('imageio', 'jai_imageio-1.1.jar'), ('json', 'json-lib-2.4.2-geoserver.jar')]:
            path = engine / 'lib' / name; path.write_bytes(b'inert profile input')
            profile.update({key + '_member': 'WEB-INF/lib/' + name, key + '_sha256': digest(path)})
        (engine / 'runtime-profile.json').write_bytes(canonical(profile))
        product = config.service_configuration(config.load(self.root)); secrets = config.secret_material(self.root)
        before = {p.name: p.read_bytes() for p in (data / 'assets').iterdir()}
        for initialize in [True, False]:
            runtime_dir = self.base / ('engine-init' if initialize else 'engine-serve')
            scope = json.loads((self.root / 'generated' / ('geoserver-init-secrets.json' if initialize else 'geoserver-secrets.json')).read_text())
            with patch.object(geoserver, 'DATA', data), patch.object(geoserver, 'ENGINE', engine), patch.object(geoserver, 'RUNTIME', runtime_dir):
                geoserver.configuration(product, scope, initialize)
            text = (runtime_dir / 'data/geofence/geofence-datasource-ovr.properties').read_text()
            self.assertIn('hibernate.hbm2ddl.auto]=' + ('update' if initialize else 'validate'), text)
            self.assertIn(secrets['transport_migrator' if initialize else 'transport_reader'], text)
            self.assertNotIn(secrets['transport_reader' if initialize else 'transport_migrator'], text)
            for path in runtime_dir.rglob('*'):
                if path.is_file(): self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (data / 'assets').iterdir()})

    def archive_check(self, alter=None, extra=None):
        path = self.inputs / 'image.tar'
        record = self.document['images']['database']
        record['image_id'] = oci_input(path, record['reference'], record['source_manifest_sha256'], '1' * 40, alter, extra)
        return image_archive.verify(path, record, '1' * 40)

    def test_oci_descriptor_closure_and_config_identity(self):
        result = self.archive_check()
        self.assertEqual(result['image_id'], self.document['images']['database']['image_id'])
        self.assertEqual(result['layers'], 1)
        self.assertTrue(result['checkpoint_restore_metadata_absent'])
        self.document['images']['database']['image_id'] = 'sha256:' + '0' * 64
        with self.assertRaises(InstallError): image_archive.verify(self.inputs / 'image.tar', self.document['images']['database'], '1' * 40)

    def test_checkpoint_restore_metadata_rejected_at_every_oci_level(self):
        for stage in ('index', 'manifest', 'config'):
            for key in ('io.podman.annotations.checkpoint.runtime.name', 'io.podman.annotations.checkpoint.name', 'io.podman.annotations.restore.name'):
                def alter(current, value):
                    if current == stage:
                        target = value['config'].setdefault('Labels', {}) if stage == 'config' else value.setdefault('annotations', {})
                        # Presence is dangerous even when no runtime name is supplied.
                        target[key] = ''
                with self.subTest(stage=stage, key=key), self.assertRaisesRegex(InstallError, 'Checkpoint/restore'):
                    self.archive_check(alter)

    def test_oci_external_urls_types_sizes_and_platform_rejected(self):
        modifications = [('manifest', lambda x: x['layers'][0].update(urls=['https://example.invalid/layer'])),
                         ('manifest', lambda x: x['layers'][0].update(size=True)),
                         ('manifest', lambda x: x['layers'][0].update(mediaType='application/octet-stream')),
                         ('manifest', lambda x: x['config'].update(digest='sha256:' + '0' * 64)),
                         ('config', lambda x: x['rootfs'].update(diff_ids=['sha256:' + '0' * 64])),
                         ('index', lambda x: x['manifests'][0].update(platform={'architecture': 'arm64', 'os': 'linux'})),
                         ('index', lambda x: x.update(schemaVersion=True))]
        for stage, modify in modifications:
            with self.subTest(stage=stage, modify=modify), self.assertRaises(InstallError):
                self.archive_check(lambda current, value: modify(value) if current == stage else None)

    def test_oci_tar_traversal_links_duplicates_specials_and_hidden_blobs_rejected(self):
        for name, kind in [('../outside', tarfile.REGTYPE), ('/outside', tarfile.REGTYPE),
                           ('index.json', tarfile.REGTYPE), ('blobs/sha256/' + '0' * 64, tarfile.REGTYPE),
                           ('link', tarfile.SYMTYPE), ('hardlink', tarfile.LNKTYPE), ('fifo', tarfile.FIFOTYPE)]:
            def extra(archive):
                member = tarfile.TarInfo(name); member.type = kind; member.linkname = '/outside' if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ''
                archive.addfile(member, io.BytesIO(b''))
            with self.subTest(name=name), self.assertRaises(InstallError): self.archive_check(extra=extra)

    def test_oci_json_duplicates_nonfinite_and_nesting_rejected(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'[' * 40 + b'0' + b']' * 40,
                    b'{"annotations":{"\\u0069o.podman.annotations.checkpoint.runtime.name":""}}',
                    b'{"annotations":{},"annotations":{"io.podman.annotations.checkpoint.runtime.name":""}}']:
            with self.assertRaises(InstallError): image_archive.parse(raw)

    def test_oci_trailing_payload_and_multiple_images_rejected(self):
        self.archive_check()
        path = self.inputs / 'image.tar'
        with path.open('ab') as stream: stream.write(b'hidden payload')
        with self.assertRaises(InstallError): image_archive.verify(path, self.document['images']['database'], '1' * 40)
        def alter(stage, value):
            if stage == 'index': value['manifests'].append(dict(value['manifests'][0]))
        with self.assertRaises(InstallError): self.archive_check(alter)

    def test_loaded_image_requires_immutable_manifest_as_well_as_config_digest(self):
        self.init(); selected = runtime.Runtime(self.root)
        record = self.document['images']['database']
        row = {'Id': record['image_id'], 'Digest': selected.image_receipts['database']['manifest_digest'],
               'Labels': {'org.ambisgis.source-manifest-sha256': record['source_manifest_sha256'],
                          'org.opencontainers.image.revision': self.document['product_revision']}}
        with patch.object(selected, 'engine', side_effect=[(0, b''), (0, json.dumps([row]).encode())]):
            self.assertEqual(selected.image('database'), record['image_id'])
        row['Digest'] = 'sha256:' + '0' * 64
        with patch.object(selected, 'engine', side_effect=[(0, b''), (0, json.dumps([row]).encode())]):
            with self.assertRaises(InstallError): selected.image('database')

    def test_ipv4_only_and_immutable_image_execution_are_explicit(self):
        self.init()
        value = json.loads((self.root / 'compose.json').read_text())
        self.assertIs(value['networks']['internal']['enable_ipv6'], False)
        for role, service in value['services'].items():
            self.assertEqual(service['image'], self.document['images'][role.removesuffix('-init')]['image_id'])
            self.assertEqual(service['sysctls'], {'net.ipv6.conf.all.disable_ipv6': '1', 'net.ipv6.conf.default.disable_ipv6': '1'})

    def test_shared_and_private_selinux_bind_labels_are_explicit(self):
        self.init()
        value = json.loads((self.root / 'compose.json').read_text())
        for role, service in value['services'].items():
            for mount in service['volumes']:
                label = 'Z' if mount['target'].endswith('/secrets.json') or (role == 'database' and mount['target'] == '/var/lib/ambisgis') else 'z'
                self.assertEqual(mount['bind'], {'selinux': label})
            self.assertNotIn('label=disable', service['security_opt'])

    def inspection(self, selected, role='catalog'):
        # Synthetic Podman 6 field representation, checked against retained
        # libpod inspect source. Native inspection remains a separate gate.
        service = config.compose(selected.config, selected.selection, self.root)['services'][role]
        oci = selected.paths['run'] / ('inspect-' + role) / 'config.json'
        oci.parent.mkdir(mode=0o700, exist_ok=True)
        oci.write_bytes(canonical({'linux': {'sysctl': service['sysctls']}}))
        return {'OCIConfigPath': str(oci), 'Image': selected.selection['images'][role.removesuffix('-init')]['image_id'], 'Config': {
            'Labels': service['labels'], 'User': service['user'], 'Cmd': [role],
            'Entrypoint': ['/opt/ambisgis/bin/service'], 'Hostname': 'synthetic-container',
            'Env': ['container=podman', 'HOSTNAME=synthetic-container']},
            'HostConfig': {'PortBindings': {}, 'ReadonlyRootfs': True, 'Privileged': False,
                'PublishAllPorts': False, 'CapAdd': [], 'CapDrop': ['CAP_CHOWN'],
                'SecurityOpt': ['no-new-privileges'], 'UsernsMode': 'private', 'PidMode': 'private',
                'UTSMode': 'private', 'IpcMode': 'shareable', 'CgroupMode': 'private',
                'Devices': [], 'GroupAdd': [], 'Tmpfs': {'/tmp': 'rw,nosuid,nodev,size=256m'}},
            'EffectiveCaps': [], 'BoundingCaps': [], 'State': {'Running': True, 'Health': {'Status': 'healthy'}},
            'NetworkSettings': {'Networks': {config.project_name(selected.config) + '_internal': {}}},
            'Mounts': [{'Type': 'bind', 'Source': m['source'], 'Destination': m['target'],
                        'RW': not m.get('read_only', False), 'Propagation': 'rprivate',
                        'Mode': m['bind']['selinux'], 'Options': ['rbind']}
                       for m in service['volumes']]}

    def test_inspected_security_drift_blocks_up_before_mutation(self):
        self.init(); selected = runtime.Runtime(self.root)
        original = self.inspection(selected)
        selected.container_security(original, 'catalog')
        for role in ('catalog-init', 'geoserver-init'):
            selected.container_security(self.inspection(selected, role), role)
        changes = [
            lambda x: x['HostConfig'].update(ReadonlyRootfs=False),
            lambda x: x['HostConfig'].update(Privileged=True),
            lambda x: x['HostConfig'].update(CapAdd=['CAP_SYS_ADMIN']),
            lambda x: x.update(EffectiveCaps=['CAP_NET_RAW']),
            lambda x: x.update(BoundingCaps=['CAP_SYS_ADMIN']),
            lambda x: x['HostConfig'].update(SecurityOpt=['no-new-privileges', 'label=disable']),
            lambda x: x['HostConfig'].update(SecurityOpt=[]),
            lambda x: x['HostConfig'].update(UsernsMode=''),
            lambda x: x['HostConfig'].update(PidMode='host'),
            lambda x: x['HostConfig'].update(UTSMode='host'),
            lambda x: x['HostConfig'].update(IpcMode='container:other'),
            lambda x: x['HostConfig'].update(CgroupMode='host'),
            lambda x: x['HostConfig'].update(Devices=[{'PathOnHost': '/dev/sda'}]),
            lambda x: x['HostConfig'].update(GroupAdd=['root']),
            lambda x: x['HostConfig'].update(Tmpfs={'/tmp': 'rw,nosuid,nodev,size=256m', '/escape': 'rw'}),
            lambda x: x['HostConfig'].update(Tmpfs={'/tmp': 'rw,size=256m'}),
            lambda x: x['Config'].update(User='0:0'),
            lambda x: x['Config'].update(Entrypoint=['/bin/sh']),
            lambda x: x['Config'].update(Cmd=['catalog-init']),
            lambda x: x['Config']['Env'].append('PYTHONPATH=/tmp'),
            lambda x: x['Config']['Env'].append('LD_PRELOAD=/tmp/evil.so'),
            lambda x: x['Config']['Env'].append('container=untrusted'),
            lambda x: x['NetworkSettings']['Networks'].update(other={}),
            lambda x: x['Mounts'][0].update(Source='/etc/passwd'),
            lambda x: x['Mounts'][0].update(RW=True),
            lambda x: x['Mounts'][0].update(Propagation='shared'),
            lambda x: x['Mounts'].append(dict(x['Mounts'][0])),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                row = copy.deepcopy(original); change(row)
                calls = []
                def engine(*args, **kwargs):
                    calls.append(args)
                    if args[:2] == ('container', 'exists'):
                        return (0 if args[-1].endswith('-catalog') else 1), b''
                    if args[:2] == ('container', 'inspect'): return 0, json.dumps([row]).encode()
                    raise AssertionError('unexpected engine mutation')
                before = self.state()
                with patch.object(runtime, 'Runtime', return_value=selected), patch.object(selected, 'engine', side_effect=engine), patch.object(selected, 'compose') as compose:
                    with self.assertRaises(InstallError): runtime.up(self.root, timeout=0)
                    compose.assert_not_called()
                self.assertEqual(before, self.state())
                self.assertTrue(all(args[:2] in [('container', 'exists'), ('container', 'inspect')] for args in calls))

    def test_actual_oci_sysctl_map_must_match_ipv4_profile(self):
        self.init(); selected = runtime.Runtime(self.root); row = self.inspection(selected)
        path = Path(row['OCIConfigPath']); original = path.read_bytes()
        for value in ({}, {'linux': {}}, {'linux': {'sysctl': {}}},
                      {'linux': {'sysctl': {'net.ipv6.conf.all.disable_ipv6': '0', 'net.ipv6.conf.default.disable_ipv6': '0'}}},
                      {'linux': {'sysctl': {'net.ipv6.conf.all.disable_ipv6': '1', 'net.ipv6.conf.default.disable_ipv6': '1', 'net.ipv4.ip_forward': '1'}}}):
            with self.subTest(value=value):
                path.write_bytes(canonical(value))
                with self.assertRaisesRegex(InstallError, 'sysctls'): selected.container_security(row, 'catalog')
        path.write_bytes(original)
        selected.container_security(row, 'catalog')

    def test_oci_path_rejects_escape_links_specials_and_oversized_content(self):
        self.init(); selected = runtime.Runtime(self.root); row = self.inspection(selected)
        path = Path(row['OCIConfigPath']); original = path.read_bytes()
        outside = self.base / 'outside-oci'; outside.write_bytes(original)
        changed = dict(row, OCIConfigPath=str(outside))
        with self.assertRaises(InstallError): selected.container_security(changed, 'catalog')
        for kind in ('link', 'fifo', 'oversized'):
            path.unlink()
            if kind == 'link': path.symlink_to(outside)
            elif kind == 'fifo': os.mkfifo(path)
            else: path.write_bytes(b' ' * (8 * 1024 * 1024 + 1))
            with self.subTest(kind=kind), self.assertRaises(InstallError): selected.container_security(row, 'catalog')
        redirected = selected.paths['run'] / 'redirected'
        redirected.symlink_to(path.parent, target_is_directory=True)
        with self.assertRaises(InstallError):
            selected.container_security(dict(row, OCIConfigPath=str(redirected / 'config.json')), 'catalog')
        self.assertEqual(outside.read_bytes(), original)

    def test_existing_network_security_drift_rejected_before_any_compose_change(self):
        self.init(); selected = runtime.Runtime(self.root)
        original = {'name': config.project_name(selected.config) + '_internal', 'driver': 'bridge',
                    'internal': True, 'ipv6_enabled': False, 'dns_enabled': True,
                    'labels': {'org.ambisgis.install-id': selected.config['install_id']},
                    'subnets': [{'subnet': '10.89.0.0/24', 'gateway': '10.89.0.1'}],
                    'ipam_options': {'driver': 'host-local'}}
        with patch.object(selected, 'engine', side_effect=[(0,b''), (0,json.dumps([original]).encode())]):
            self.assertTrue(selected.network()['verified'])
        modifications = [lambda v: v.update(internal=False), lambda v: v.update(ipv6_enabled=True),
                         lambda v: v.pop('ipv6_enabled'), lambda v: v.update(driver='macvlan'),
                         lambda v: v.update(labels={'org.ambisgis.install-id': 'another'}),
                         lambda v: v.update(routes=[{'destination': '0.0.0.0/0','gateway': '10.89.0.1'}]),
                         lambda v: v.update(network_dns_servers=['8.8.8.8']),
                         lambda v: v.update(options={'mode': 'unmanaged'}),
                         lambda v: v.update(subnets=[{'subnet': 'fd00::/64'}]),
                         lambda v: v.update(subnets=[{'subnet': '192.0.2.0/24','gateway': '8.8.8.8'}]),
                         lambda v: v.update(ipam_options={'driver': 'dhcp'})]
        for index, modify in enumerate(modifications):
            with self.subTest(index=index):
                value = copy.deepcopy(original); modify(value); calls = []
                def engine(*args, **kwargs):
                    calls.append(args)
                    if args[:2] == ('container','exists'): return 1,b''
                    if args[:2] == ('network','exists'): return 0,b''
                    if args[:2] == ('network','inspect'): return 0,json.dumps([value]).encode()
                    raise AssertionError('unexpected producer mutation')
                before = self.state()
                with patch.object(runtime,'Runtime',return_value=selected), patch.object(selected,'engine',side_effect=engine), patch.object(selected,'compose') as compose:
                    with self.assertRaisesRegex(InstallError,'network'): runtime.up(self.root,timeout=0)
                    compose.assert_not_called()
                self.assertEqual(before,self.state())
                self.assertTrue(all(args[:2] in [('container','exists'),('network','exists'),('network','inspect')] for args in calls))

    def test_loaded_checkpoint_annotation_rejected(self):
        self.init(); selected = runtime.Runtime(self.root)
        row = {'Id': self.document['images']['database']['image_id'], 'Annotations': {
            'io.podman.annotations.checkpoint.runtime.name': 'untrusted-runtime'}}
        with patch.object(selected, 'engine', side_effect=[(0, b''), (0, json.dumps([row]).encode())]):
            with self.assertRaisesRegex(InstallError, 'Checkpoint/restore'): selected.image('database')


if __name__ == '__main__':
    unittest.main()
