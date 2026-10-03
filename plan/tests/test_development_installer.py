"""Installer state/negative guards; these are not container or GIS acceptance."""
import hashlib
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
from ambisgis_development import common, gateway, geoserver
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
        self.put('closure.json', {'schema_version': 1, 'files': [self.ref('bin/podman'), self.ref('bin/compose')]})
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

    def test_loaded_checkpoint_annotation_rejected(self):
        self.init(); selected = runtime.Runtime(self.root)
        row = {'Id': self.document['images']['database']['image_id'], 'Annotations': {
            'io.podman.annotations.checkpoint.runtime.name': 'untrusted-runtime'}}
        with patch.object(selected, 'engine', side_effect=[(0, b''), (0, json.dumps([row]).encode())]):
            with self.assertRaisesRegex(InstallError, 'Checkpoint/restore'): selected.image('database')


if __name__ == '__main__':
    unittest.main()
