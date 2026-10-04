"""Inert lifecycle-helper boundary checks, not installation/GIS acceptance."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import lifecycle_check as lifecycle
sys.path.insert(0, str(lifecycle.ROOT / 'plan/tests'))
import test_development_installer as installer_fixture
from installer.state import InstallError


class LifecycleBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = installer_fixture.InstallerStateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        f = self.fixture
        (f.inputs / 'bin/ambisgis').write_bytes(b'inert CLI fixture; must never execute\n')
        (f.inputs / 'bin/ambisgis').chmod(0o700)
        closure = json.loads((f.inputs / 'closure.json').read_bytes())
        closure['files'].append(f.ref('bin/ambisgis'))
        f.put('closure.json', closure)
        f.document['runtime']['files_manifest'] = f.ref('closure.json')
        f.seal()

    def test_relocation_preserves_verified_inputs_and_excludes_unselected_neighbor(self):
        f = self.fixture
        (f.inputs / 'unselected-executable').write_bytes(b'must not enter bundle')
        before = {str(p.relative_to(f.inputs)): p.read_bytes() for p in f.inputs.rglob('*') if p.is_file()}
        manifest, launcher = lifecycle.relocate(f.manifest, f.identity, f.base / 'relocated')
        self.assertEqual(launcher.read_bytes(), (f.inputs / 'bin/ambisgis').read_bytes())
        self.assertEqual(manifest.read_bytes(), f.manifest.read_bytes())
        self.assertFalse((manifest.parent / 'unselected-executable').exists())
        after = {str(p.relative_to(f.inputs)): p.read_bytes() for p in f.inputs.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(lifecycle.bundle.load(manifest, f.identity), f.document)

    def test_unlisted_runtime_code_rejected_before_any_destination_is_created(self):
        f = self.fixture
        (f.inputs / 'bin/unreviewed').write_bytes(b'not selected')
        with self.assertRaises(InstallError):
            lifecycle.relocate(f.manifest, f.identity, f.base / 'relocated')
        self.assertFalse((f.base / 'relocated').exists())

    def test_existing_destination_keeps_sentinel_and_is_never_replaced(self):
        f = self.fixture
        destination = f.base / 'relocated'; destination.mkdir()
        (destination / 'keep').write_bytes(b'preserved')
        with self.assertRaises(FileExistsError):
            lifecycle.relocate(f.manifest, f.identity, destination)
        self.assertEqual(list(destination.iterdir()), [destination / 'keep'])
        self.assertEqual((destination / 'keep').read_bytes(), b'preserved')

    def test_existing_installation_is_rejected_without_creating_evidence(self):
        from argparse import Namespace
        f = self.fixture; f.root.mkdir(); (f.root / 'data').write_bytes(b'preserved')
        with self.assertRaises(ValueError):
            lifecycle.main(Namespace(directory=f.root, output=f.base / 'evidence', bundle=f.manifest, bundle_sha256=f.identity))
        self.assertFalse((f.base / 'evidence').exists())
        self.assertEqual((f.root / 'data').read_bytes(), b'preserved')

    def test_receipt_secret_scan_prevents_write(self):
        f = self.fixture; output = f.base / 'evidence'; output.mkdir()
        check = lifecycle.Check(f.root, output)
        check.secrets = ['synthetic-secret-only-for-test']
        check.record['unsafe'] = 'synthetic-secret-only-for-test'
        with self.assertRaises(RuntimeError):
            check.save()
        self.assertFalse((output / 'result.json').exists())


class ProtectedRepetitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.check=lifecycle.Check(root/'installation',root/'evidence')
        self.calls=[];self.check.metadata=lambda title:self.calls.append(('metadata',title))
        self.check.preserve_identity=lambda:self.calls.append(('preserve',))
        self.check.stage=lambda *args:self.calls.append(('stage',args[0]))
        self.identity={'resource_uuid':'same-resource','viewer_pk':2,'owner_pk':1}
        test=self
        class Journey:
            def __init__(self,path):
                test.calls.append(('construct',));self.cleanup_result={'complete':True}
                self.permission_cleanup={'complete':True};self.browsers=[];self.rows=[];self.permission_events=[]
            def run(self):
                test.calls.append(('run',))
                return {'retained_metadata_title':'old-title','native_item_permission_roundtrip':{
                    'identity':dict(test.identity),'restoration':{'native':{'after_sha256':'unchanged'}}}}
        self.patcher=patch.object(lifecycle.journey_module,'Journey',Journey);self.patcher.start();self.addCleanup(self.patcher.stop)

    def test_persistence_is_checked_before_repeated_journey_can_write(self):
        self.check.protected_journey('after restart','old-title')
        self.assertEqual(self.calls[:4],[('metadata','old-title'),('preserve',),('construct',),('run',)])
        self.assertEqual(self.check.record['http_journeys'][0]['stage'],'after restart')
        self.assertEqual(self.check.record['permission_cleanup'],[{'complete':True}])

    def test_lost_metadata_prevents_journey_rewrite(self):
        def fail(title):raise ValueError('old metadata missing')
        self.check.metadata=fail
        with self.assertRaisesRegex(ValueError,'old metadata'):self.check.protected_journey('after recovery','old-title')
        self.assertNotIn(('construct',),self.calls)

    def test_native_identity_drift_blocks_success(self):
        self.check.protected_journey('initial')
        self.identity['viewer_pk']=99
        with self.assertRaisesRegex(ValueError,'native principals'):self.check.protected_journey('after reinit','old-title')
        self.assertEqual(len(self.check.record['http_journeys']),1)


class DNSObservationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.check = lifecycle.Check(root / 'installation', root)
        self.check.dns_expectation = object()
        self.check.stage = lambda *args: None
        self.running = {'status': 'verified', 'classification': 'running',
                        'identity_verified': True, 'namespace_binding_verified': True}
        self.gone = {'status': 'verified', 'classification': 'gone',
                     'cleanup_verified': True, 'daemon_cleanup_verified': True}

    def test_verified_running_identity_is_retained_for_cleanup(self):
        with patch.object(lifecycle.dns_module, 'observe_running', return_value=self.running) as observe:
            self.check.observe_dns('after CLI exit')
        observe.assert_called_once_with(self.check.dns_expectation)
        self.assertIs(self.check.dns_running, self.running)
        self.assertEqual(self.check.record['incomplete_checks'], [])

    def test_unsupported_binding_is_retained_and_never_becomes_a_pass(self):
        value = dict(self.running, status='unsupported', namespace_binding_verified=False,
                     classification='namespace_binding_unavailable')
        with patch.object(lifecycle.dns_module, 'observe_running', return_value=value):
            self.check.observe_dns('after CLI exit')
        self.assertIs(self.check.dns_running, value)
        self.assertEqual(self.check.record['incomplete_checks'], [
            {'stage': 'after CLI exit', 'classification': 'namespace_binding_unavailable'}])
        self.assertEqual(self.check.record['dns_observations'][0]['result']['status'], 'unsupported')

    def test_identity_mismatch_is_recorded_and_stops_the_journey(self):
        value = {'status': 'failed', 'classification': 'executable_mismatch', 'identity_verified': False}
        with patch.object(lifecycle.dns_module, 'observe_running', return_value=value):
            with self.assertRaisesRegex(RuntimeError, 'identity observation'):
                self.check.observe_dns('after CLI exit')
        self.assertIsNone(self.check.dns_running)
        self.assertEqual(self.check.record['dns_observations'][0]['result'], value)

    def test_native_async_cleanup_is_bounded_and_records_every_observation(self):
        self.check.dns_running = self.running
        live = {'status': 'failed', 'classification': 'live_retained', 'cleanup_verified': False}
        with patch.object(lifecycle.dns_module, 'observe_stopped', side_effect=[live, self.gone]) as observe, \
                patch.object(lifecycle.time, 'sleep') as sleep:
            self.assertEqual(self.check.observe_dns_stopped(), self.gone)
        self.assertEqual(observe.call_count, 2); sleep.assert_called_once_with(0.25)
        self.assertEqual(len(self.check.record['dns_cleanup'][0]), 2)

    def test_persistent_live_process_does_not_get_cleanup_credit(self):
        self.check.dns_running = self.running
        live = {'status': 'failed', 'classification': 'live_retained', 'cleanup_verified': False}
        with patch.object(lifecycle.dns_module, 'observe_stopped', return_value=live) as observe, \
                patch.object(lifecycle.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'cleanup observation'):
                self.check.observe_dns_stopped(timeout=0)
        observe.assert_called_once(); sleep.assert_not_called()

    def test_pid_reuse_is_not_polled_or_overlooked(self):
        self.check.dns_running = self.running
        reused = {'status': 'failed', 'classification': 'pid_reused', 'cleanup_verified': False}
        with patch.object(lifecycle.dns_module, 'observe_stopped', return_value=reused) as observe, \
                patch.object(lifecycle.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'cleanup observation'):
                self.check.observe_dns_stopped()
        observe.assert_called_once(); sleep.assert_not_called()

    def test_unsupported_status_cannot_mask_known_cleanup_failures(self):
        self.check.dns_running = self.running
        for code in ('pid_reused', 'pidfile_changed', 'live_retained', 'pidfile_retained', 'config_retained'):
            with self.subTest(code=code):
                value = {'status': 'unsupported', 'classification': code, 'cleanup_verified': False}
                with patch.object(lifecycle.dns_module, 'observe_stopped', return_value=value):
                    with self.assertRaisesRegex(RuntimeError, 'cleanup observation'):
                        self.check.observe_dns_stopped(timeout=0)
        self.assertEqual(self.check.record['incomplete_checks'], [])

    def test_unsupported_status_cannot_mask_running_identity_mismatch(self):
        value = {'status': 'unsupported', 'classification': 'executable_mismatch', 'identity_verified': True}
        with patch.object(lifecycle.dns_module, 'observe_running', return_value=value):
            with self.assertRaisesRegex(RuntimeError, 'identity observation'):
                self.check.observe_dns('after CLI exit')
        self.assertIsNone(self.check.dns_running)
        self.assertEqual(self.check.record['incomplete_checks'], [])

    def test_absence_without_previous_identity_is_unobserved(self):
        with patch.object(lifecycle.dns_module, 'observe_stopped') as observe:
            value = self.check.observe_dns_stopped()
        observe.assert_not_called()
        self.assertEqual(value['status'], 'unobserved')
        self.assertFalse(value['cleanup_verified'])
        self.assertFalse(value['daemon_cleanup_verified'])

    def test_incomplete_observation_makes_completed_journey_exit_nonzero(self):
        from argparse import Namespace
        root = Path(self.temp.name); output = root / 'evidence'
        def exercise(check, args):
            check.record['incomplete_checks'].append({'stage': 'DNS', 'classification': 'namespace_binding_unavailable'})
        with patch.object(lifecycle.Check, 'exercise', exercise), \
                patch.object(lifecycle.Check, 'stop_owned', return_value={'running_services': 0}):
            code = lifecycle.main(Namespace(directory=root / 'new-installation', output=output,
                bundle=root / 'unused-bundle.json', bundle_sha256='0' * 64))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((output / 'result.json').read_text())['status'], 'incomplete')


if __name__ == '__main__':
    unittest.main()
