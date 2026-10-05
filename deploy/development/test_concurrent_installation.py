"""Inert command-concurrency guards; no CLI, engine or HTTP is executed."""
from argparse import Namespace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import concurrent_installation as concurrent
import test_lifecycle_check as lifecycle_fixture
from installer import config
from installer.state import InstallError, atomic_write


class ConcurrentInstallationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = lifecycle_fixture.LifecycleBoundaryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.fixture
        self.output = self.f.base / 'concurrency-evidence'
        self.output.mkdir(mode=0o700)
        self.check = concurrent.ConcurrentCheck(self.f.root, self.output)
        self.check.prepare(self.f.manifest, self.f.identity)
        self.created = config.initialize(self.f.root, self.check.bundle_path, self.f.identity)
        self.check.capture_identity()
        self.children = []
        self.calls = []

    def busy(self, command='init', error=None):
        return (1, b'', json.dumps({'command': command, 'ok': False,
                'error': error or concurrent.BUSY}).encode())

    def success(self, command='init', created=True):
        value = dict(self.created, created=created)
        if command == 'up':
            value = {'command': 'up', 'install_id': self.created['install_id'],
                     'ready': True, 'readiness': {'ready': True, 'checks':
                     dict.fromkeys(('catalog', 'database', 'map', 'query'), True)},
                     'network': {'name': config.project_name(config.load(self.f.root)) + '_internal',
                                 'internal': True, 'ipv6_enabled': False, 'driver': 'bridge', 'verified': True},
                     'services': {role: {'process': 'running', 'engine_health': 'healthy'}
                                  for role in concurrent.bundle.SERVICES}}
        return 0, json.dumps(value).encode(), b''

    def factory(self, replies, *, stuck=False, fail_second=False, early=False):
        test = self
        class Child:
            def __init__(self, reply):
                self.pid = 800000 + len(test.children)
                self.reply = reply; self.returncode = None; self.polls = 0
                self.streams = []
                for payload in reply[1:]:
                    reader, writer = os.pipe()
                    os.write(writer, payload); os.close(writer)
                    self.streams.append(os.fdopen(reader, 'rb', buffering=0))
                self.stdout, self.stderr = self.streams
            def poll(self):
                self.polls += 1
                overlap_poll = self.pid == 800000 and self.polls <= 2
                if early or (len(test.children) == 2 and not stuck and not overlap_poll):
                    self.returncode = self.reply[0]
                return self.returncode
            def wait(self, timeout=None):
                if self.returncode is None:
                    raise subprocess.TimeoutExpired('inert child', timeout)
                return self.returncode
        def create(argv, **kwargs):
            test.calls.append((argv, kwargs))
            if fail_second and test.children:
                raise OSError('inert second launch failure')
            child = Child(replies[len(test.children)])
            test.children.append(child)
            return child
        return create

    def run_pair(self, replies, **kwargs):
        with (patch.object(concurrent.subprocess, 'Popen', self.factory(replies, **kwargs)),
              patch.object(concurrent, 'group_members', return_value=[]),
              patch.object(concurrent.os, 'killpg') as signals):
            def killed(pid, sig):
                next(x for x in self.children if x.pid == pid).returncode = -int(sig)
            signals.side_effect = killed
            return self.check.pair('init')

    def test_two_calls_start_before_wait_and_only_selected_argv_environment(self):
        result = self.run_pair([self.success(), self.busy()])
        self.assertEqual([x['outcome'] for x in result['children']], ['created', 'busy'])
        self.assertTrue(result['launch_overlap_observed'])
        self.assertTrue(result['lock_contention_observed'])
        self.assertEqual(len(self.calls), 2)
        for argv, kwargs in self.calls:
            self.assertEqual(argv, [str(self.check.launcher), 'init', '--directory', str(self.f.root),
                                    '--bundle', str(self.check.bundle_path), '--bundle-sha256', self.f.identity])
            self.assertTrue(kwargs['start_new_session'])
            self.assertNotIn('DBUS_SESSION_BUS_ADDRESS', kwargs['env'])
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)

    def test_two_successes_require_one_created_and_same_identity(self):
        result = self.run_pair([self.success(), self.success(created=False)])
        self.assertFalse(result['lock_contention_observed'])
        self.assertTrue(result['launch_overlap_observed'])

    def test_unmarked_directory_error_is_failure_not_allowed_contention(self):
        with self.assertRaises(ValueError):
            self.run_pair([self.success(), self.busy(error='Installation directory is not empty and has no product configuration.')])
        self.assertEqual(self.check.record['pairs'][0]['children'][1]['outcome'], 'rejected')

    def test_arbitrary_command_rejected_before_any_child(self):
        with patch.object(concurrent.subprocess, 'Popen') as spawn:
            with self.assertRaises(ValueError): self.check.pair('exec')
            spawn.assert_not_called()

    def test_both_busy_and_two_creators_fail(self):
        for replies in ([self.busy(), self.busy()], [self.success(), self.success()]):
            self.children.clear(); self.calls.clear()
            with self.subTest(replies=replies), self.assertRaises(ValueError):
                self.run_pair(replies)

    def test_wrong_returned_identity_or_extra_json_key_fails_without_echo(self):
        for change in ({'install_id': '00000000-0000-0000-0000-000000000000'},
                       {'untrusted': 'do-not-record'}):
            self.children.clear()
            row = json.loads(self.success()[1]); row.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_pair([(0, json.dumps(row).encode(), b''), self.busy()])
        self.assertNotIn('do-not-record', json.dumps(self.check.record))

    def test_config_or_credentials_reset_is_detected(self):
        for name in ('product.json', 'secrets/product.json'):
            original = (self.f.root / name).read_bytes()
            value = json.loads(original)
            if name == 'product.json': value['listen']['port'] += 1
            else: value['owner_password'] = 'x' * 48
            atomic_write(self.f.root / name, value, replace=True)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.check.capture_identity()
            atomic_write(self.f.root / name, original, replace=True)

    def test_secret_or_duplicate_json_diagnostic_is_withheld(self):
        secret = config.secret_material(self.f.root)['owner_password'].encode()
        for output in (secret, b'{"command":"init","command":"init"}'):
            self.children.clear()
            with self.subTest(output=output[:4]), self.assertRaises(ValueError):
                self.run_pair([(0, output, b''), self.busy()])
        self.check.save()
        self.assertNotIn(secret, (self.output / 'result.json').read_bytes())

    def test_no_overlap_fails_instead_of_replaying(self):
        with self.assertRaises(ValueError):
            self.run_pair([self.success(), self.busy()], early=True)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.check.record['pairs'][0]['launch_overlap_observed'])

    def test_output_limit_is_enforced_while_reading(self):
        with patch.object(concurrent, 'OUTPUT_LIMIT', 32), self.assertRaises(ValueError):
            self.run_pair([self.success(), self.busy()])
        self.assertTrue(self.check.record['pairs'][0]['child_cleanup']['complete'])

    def test_timeout_terminates_only_launched_sessions(self):
        with patch.object(concurrent, 'PAIR_TIMEOUT', 0.02), self.assertRaises(TimeoutError):
            self.run_pair([self.success(), self.busy()], stuck=True)
        self.assertTrue(self.check.record['pairs'][0]['child_cleanup']['complete'])
        self.assertEqual(len(self.children), 2)

    def test_second_spawn_failure_cleans_first_child(self):
        with self.assertRaises(OSError):
            self.run_pair([self.success(), self.busy()], stuck=True, fail_second=True)
        self.assertEqual(len(self.children), 1)
        self.assertTrue(self.check.record['pairs'][0]['child_cleanup']['complete'])

    def test_unreaped_or_leftover_child_group_is_not_success(self):
        with (patch.object(concurrent.subprocess, 'Popen', self.factory([self.success(), self.busy()])),
              patch.object(concurrent, 'group_members', return_value=[999999])):
            with self.assertRaises(ValueError): self.check.pair('init')
        self.assertFalse(self.check.record['pairs'][0]['child_cleanup']['complete'])

    def test_marker_drift_prevents_launch_and_engine_cleanup(self):
        self.check.up_attempted = True
        (self.output / 'installation-marker.json').write_text('{}')
        with patch.object(concurrent.subprocess, 'Popen') as spawn:
            with self.assertRaises(ValueError): self.check.pair('init')
            spawn.assert_not_called()
        with patch.object(concurrent.runtime, 'Runtime') as factory:
            with self.assertRaises(ValueError): self.check.shutdown()
            factory.assert_not_called()

    def test_up_requires_ready_peer_and_preserves_identity(self):
        with (patch.object(concurrent.subprocess, 'Popen',
                           self.factory([self.success('up'), self.busy('up')])),
              patch.object(concurrent, 'group_members', return_value=[])):
            result = self.check.pair('up')
        self.assertEqual([x['outcome'] for x in result['children']], ['ready', 'busy'])
        self.assertEqual(self.check.record['identity'], self.check.capture_identity())

    def test_owned_shutdown_is_reused_and_uncertainty_propagates(self):
        self.check.up_attempted = True
        with (patch.object(concurrent.runtime, 'Runtime') as factory,
              patch.object(concurrent.lifecycle.Check, 'stop_owned',
                           return_value={'attempted': True, 'running_services': 0,
                                         'persistent_data_preserved': True}) as stop):
            result = self.check.shutdown()
            self.assertEqual(result['running_services'], 0)
            factory.assert_called_once_with(self.f.root)
            stop.assert_called_once_with(self.check)
        with (patch.object(concurrent.runtime, 'Runtime', side_effect=InstallError('uncertain')),
              self.assertRaises(InstallError)):
            self.check.shutdown()

    def test_nonready_or_numeric_truth_is_rejected(self):
        for change in ('not_ready', 'numeric_check', 'numeric_network'):
            self.children.clear()
            row = json.loads(self.success('up')[1])
            if change == 'not_ready': row['ready'] = False
            elif change == 'numeric_check': row['readiness']['checks']['map'] = 1
            else: row['network']['internal'] = 1
            with (self.subTest(change=change),
                  patch.object(concurrent.subprocess, 'Popen',
                      self.factory([(0, json.dumps(row).encode(), b''), self.busy('up')])),
                  patch.object(concurrent, 'group_members', return_value=[]),
                  self.assertRaises(ValueError)):
                self.check.pair('up')

    def test_inspection_failure_does_not_claim_group_cleanup(self):
        with (patch.object(concurrent.subprocess, 'Popen', self.factory([self.success(), self.busy()])),
              patch.object(concurrent, 'group_members', side_effect=PermissionError('inert uncertainty')),
              self.assertRaises(ValueError)):
            self.check.pair('init')
        self.assertFalse(self.check.record['pairs'][0]['child_cleanup']['complete'])

    def test_unreaped_children_prevent_engine_cleanup(self):
        self.check.up_attempted = True
        self.check.record['pairs'] = [{'child_cleanup': {'complete': False}}]
        with patch.object(concurrent.runtime, 'Runtime') as factory:
            with self.assertRaises(ValueError): self.check.shutdown()
            factory.assert_not_called()

    def test_interrupt_during_pair_still_reaps_created_children(self):
        with (patch.object(concurrent.subprocess, 'Popen',
                           self.factory([self.success(), self.busy()], stuck=True)),
              patch.object(concurrent.os, 'read', side_effect=KeyboardInterrupt),
              patch.object(concurrent, 'group_members', return_value=[]),
              patch.object(concurrent.os, 'killpg') as signals):
            def killed(pid, sig):
                next(x for x in self.children if x.pid == pid).returncode = -int(sig)
            signals.side_effect = killed
            with self.assertRaises(KeyboardInterrupt): self.check.pair('init')
        self.assertTrue(self.check.record['pairs'][0]['child_cleanup']['complete'])

    def test_malformed_eof_is_rejected_and_both_pipes_closed(self):
        with self.assertRaises(ValueError):
            self.run_pair([(0, b'', b''), self.busy()])
        self.assertTrue(all(stream.closed for child in self.children for stream in child.streams))

    def test_main_failure_still_attempts_owned_cleanup(self):
        args = Namespace(directory=self.f.base / 'fresh', output=self.f.base / 'fresh-output',
                         bundle=self.f.manifest, bundle_sha256=self.f.identity)
        with (patch.object(concurrent.ConcurrentCheck, 'exercise', side_effect=KeyboardInterrupt),
              patch.object(concurrent.ConcurrentCheck, 'shutdown', return_value={'complete': True}) as stop):
            self.assertEqual(concurrent.main(args), 1)
            stop.assert_called_once()
        result = json.loads((args.output / 'result.json').read_text())
        self.assertEqual(result['error_type'], 'KeyboardInterrupt')
        self.assertEqual(result['status'], 'failed')

    def test_existing_or_nested_directories_rejected_before_relocation(self):
        for directory, output in ((self.f.root, self.f.base / 'new'),
                                  (self.f.base / 'new', self.f.base / 'new' / 'output')):
            args = Namespace(directory=directory, output=output, bundle=self.f.manifest,
                             bundle_sha256=self.f.identity)
            with patch.object(concurrent.lifecycle, 'relocate') as relocate:
                with self.assertRaises((ValueError, FileExistsError)): concurrent.main(args)
                relocate.assert_not_called()

    def test_main_records_cleanup_failure_even_after_success(self):
        args = Namespace(directory=self.f.base / 'fresh', output=self.f.base / 'fresh-output',
                         bundle=self.f.manifest, bundle_sha256=self.f.identity)
        with (patch.object(concurrent.ConcurrentCheck, 'exercise'),
              patch.object(concurrent.ConcurrentCheck, 'shutdown', side_effect=InstallError('secret message'))):
            self.assertEqual(concurrent.main(args), 1)
        result = json.loads((args.output / 'result.json').read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['shutdown']['complete'])
        self.assertNotIn('secret message', json.dumps(result))
        self.assertFalse(result['native_uniqueness_acceptance'])
        self.assertFalse(result['full_installation_acceptance'])


    def test_repeated_init_requires_existing_success_and_rejects_creator(self):
        for replies,passes in [([self.success(created=False),self.busy()],True),
                               ([self.success(created=False),self.success(created=False)],True),
                               ([self.success(),self.busy()],False),
                               ([self.busy(),self.busy()],False)]:
            self.children.clear();self.calls.clear()
            with (self.subTest(passes=passes),
                  patch.object(concurrent.subprocess,'Popen',self.factory(replies)),
                  patch.object(concurrent,'group_members',return_value=[])):
                if passes:
                    self.assertTrue(self.check.pair('init',reinitialize=True)['reinitialize'])
                else:
                    with self.assertRaises(ValueError):self.check.pair('init',reinitialize=True)

    def test_reinitialize_flag_is_finite_and_rejects_up_before_launch(self):
        with patch.object(concurrent.subprocess,'Popen')as spawn:
            for command,flag in [('up',True),('init',1),('init','yes')]:
                with self.subTest(command=command,flag=flag),self.assertRaises(ValueError):
                    self.check.pair(command,reinitialize=flag)
            spawn.assert_not_called()

    def exercise_native_fixture(self, *, drift=None, lost_title=False, token_failure=False):
        from types import SimpleNamespace
        events=[];state={'identity':{'resource_uuid':'fixture','resource_pk':3,'owner_pk':1,'viewer_pk':2},'policy':'fixed-policy'}
        class Journey:
            def __init__(self,directory):
                events.append(('construct',));self.cleanup_result={'complete':True};self.permission_cleanup={'complete':True};self.browsers=[];self.rows=[];self.permission_events=[]
            def login(self, principal):
                events.append(('login',principal));return None,SimpleNamespace(access_token='inert-token')
            def request(self, path, **kwargs):
                events.append(('metadata', 'edited-title'))
                test_title='missing-title' if lost_title else 'edited-title'
                return 200,json.dumps({'title':test_title}).encode()
            def cleanup_tokens(self):
                events.append(('metadata-token-cleanup',));return {'complete':True}
            def run(self):
                events.append(('run',))
                if token_failure and len([e for e in events if e[0]=='run'])==2:
                    self.cleanup_result={'complete':False}
                    raise RuntimeError('Synthetic token cleanup incomplete')
                return {'retained_metadata_title':'edited-title','native_item_permission_roundtrip':{
                    'identity':dict(state['identity']),'restoration':{'native':{'after_sha256':state['policy']}}}}
        def pair(command,**kwargs):
            events.append(('pair',command,kwargs.get('reinitialize',False)))
            if kwargs.get('reinitialize'):
                if drift=='identity':state['identity']['viewer_pk']=99
                if drift=='policy':state['policy']='changed-policy'
            return {'child_cleanup':{'complete':True}}
        rows={role:{'process':'running'}for role in concurrent.bundle.SERVICES}
        rows.update({'catalog-init':{'process':'absent'},'geoserver-init':{'process':'absent'}})
        rt=SimpleNamespace(processes=lambda **kw:rows,network=lambda:{'verified':True})
        with (patch.object(self.check,'prepare'),patch.object(self.check,'pair',side_effect=pair),
              patch.object(concurrent.runtime,'Runtime',return_value=rt),
              patch.object(concurrent.lifecycle.journey_module,'Journey',Journey)):
            try:self.check.exercise(self.f.manifest,self.f.identity)
            finally:self.native_events=events
        return events

    def test_inherited_journey_wiring_and_read_before_edit_after_pairs(self):
        events=self.exercise_native_fixture()
        self.assertEqual([e for e in events if e[0]=='pair'],[('pair','init',False),('pair','up',False),('pair','init',True),('pair','up',False)])
        reads=[i for i,e in enumerate(events)if e[0]=='run'];self.assertEqual(len(reads),2)
        self.assertLess(events.index(('metadata','edited-title')),reads[1])
        self.assertEqual(len(self.check.record['http_journeys']),2)
        self.assertEqual(len(self.check.record['token_cleanup']),3)
        self.assertIn(('login','owner'),events)
        self.assertIn(('metadata-token-cleanup',),events)
        self.assertEqual(len(self.check.record['permission_cleanup']),2)
        self.assertEqual(len(self.check.record['stages']),2)
        self.assertTrue(self.check.record['native_identity_and_policy_preserved'])
        self.assertFalse(self.check.record['native_uniqueness_acceptance'])
        self.assertFalse(self.check.record['installed_sql_role_acceptance'])
        self.assertFalse(self.check.record['full_installation_acceptance'])

    def test_native_identity_and_policy_drift_block_preservation_credit(self):
        for drift in ('identity','policy'):
            self.check.native_identity=None;self.check.native_policy_sha256=None
            with self.subTest(drift=drift),self.assertRaisesRegex(ValueError,'native principals'):
                self.exercise_native_fixture(drift=drift)
            self.assertFalse(self.check.record['native_identity_and_policy_preserved'])

    def test_missing_old_metadata_prevents_second_journey_write(self):
        with self.assertRaisesRegex(ValueError,'previous metadata edit'):
            self.exercise_native_fixture(lost_title=True)
        self.assertEqual(len([e for e in self.native_events if e[0]=='run']),1)
        self.assertFalse(self.check.record['native_identity_and_policy_preserved'])

    def test_journey_cleanup_failure_retained_without_success_credit(self):
        with self.assertRaisesRegex(RuntimeError,'token cleanup'):
            self.exercise_native_fixture(token_failure=True)
        self.assertFalse(self.check.record['token_cleanup'][-1]['complete'])
        self.assertFalse(self.check.record['native_identity_and_policy_preserved'])

    def test_main_incomplete_cannot_be_reported_passed(self):
        args=Namespace(directory=self.f.base/'fresh-incomplete',output=self.f.base/'out-incomplete',bundle=self.f.manifest,bundle_sha256=self.f.identity)
        def incomplete(check,*unused):check.record['incomplete_checks'].append({'classification':'synthetic_unavailable'})
        with (patch.object(concurrent.ConcurrentCheck,'exercise',incomplete),
              patch.object(concurrent.ConcurrentCheck,'shutdown',return_value={'complete':True})):
            self.assertEqual(concurrent.main(args),1)
        value=json.loads((args.output/'result.json').read_text());self.assertEqual(value['status'],'incomplete')
        self.assertFalse(value['full_installation_acceptance'])

    def test_main_explicit_incomplete_shutdown_cannot_be_reported_passed(self):
        args=Namespace(directory=self.f.base/'fresh-stop',output=self.f.base/'out-stop',bundle=self.f.manifest,bundle_sha256=self.f.identity)
        with (patch.object(concurrent.ConcurrentCheck,'exercise'),
              patch.object(concurrent.ConcurrentCheck,'shutdown',return_value={'complete':False,'reconciliation_required':True})):
            self.assertEqual(concurrent.main(args),1)
        self.assertEqual(json.loads((args.output/'result.json').read_text())['status'],'failed')


if __name__ == '__main__':
    unittest.main()
