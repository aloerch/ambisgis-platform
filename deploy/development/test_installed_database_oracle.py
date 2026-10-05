"""Inert installed-oracle contracts, not PostgreSQL/container acceptance."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import installed_database_oracle as oracle
import concurrent_installation as concurrent
import test_concurrent_installation as concurrency_fixture


def data():
    product = {'install_id': '10000000-0000-4000-8000-000000000001', 'owner': 'publisher', 'viewer': 'viewer'}
    users = [{'id': i, 'username': name, 'password': 'private-native-password-hash', 'is_active': True,
              'is_staff': False, 'is_superuser': False, 'date_joined': '2026-01-01'}
             for i, name in ((-1, 'AnonymousUser'), (1, 'publisher'), (2, 'viewer'), (3, 'installation-health'))]
    resource_uuid = str(oracle.uuid.uuid5(oracle.uuid.UUID(product['install_id']), 'diagnostic-private-points'))
    catalog = {'principals': users, 'resources': [{'id': 4, 'uuid': resource_uuid, 'alternate': 'fixture:private_points',
               'owner_id': 1, 'title': 'private changed metadata', 'abstract': 'private abstract',
               'is_published': True, 'is_approved': True, 'resource_type': 'dataset'}],
               'applications': [{'id': 5, 'name': 'AmbisGIS development', 'user_id': 1, 'client_id': 'private-client',
                 'client_secret': 'private-oauth-secret', 'client_type': 'confidential',
                 'authorization_grant_type': 'authorization-code', 'redirect_uris': 'http://127.0.0.1:8787/oauth/callback',
                 'skip_authorization': False}],
               'migrations': [{'id': 6, 'app': 'people', 'name': 'selected_migration', 'applied': '2026-01-01'}]}
    transport = {'rules': [{'id': i, 'priority': priority, 'service': service, 'request': request,
                           'workspace': 'fixture', 'layer': 'private_points', 'grant_type': 'ALLOW'}
                          for i, priority, service, request in ((1, 10, 'WMS', 'GETMAP'), (2, 20, 'WFS', 'GETFEATURE'))],
                 'sequence': [{'last_value': 3, 'is_called': True}]}
    schemas = {db: {name: [] for name in oracle.SCHEMA_ROWS} for db in (oracle.CATALOG, oracle.TRANSPORT)}
    for db, owner, names in ((oracle.CATALOG, 50, ('people_profile', 'base_resourcebase', 'oauth2_provider_application', 'django_migrations')),
                             (oracle.TRANSPORT, 51, ('gf_rule', 'hibernate_sequence'))):
        schemas[db]['relations'] = [{'nspname': 'public', 'relname': name, 'relowner': owner} for name in names]
    roles = {'roles': [{'oid': 20 + i, 'rolname': name, 'rolcanlogin': True, 'rolsuper': False,
                       'rolinherit': False, 'rolcreatedb': False, 'rolcreaterole': False,
                       'rolreplication': False, 'rolbypassrls': False} for i, name in enumerate(oracle.ROLES)],
             'memberships': [], 'databases': [{'oid': 10, 'datname': oracle.CATALOG, 'datdba': 50},
                                             {'oid': 11, 'datname': oracle.TRANSPORT, 'datdba': 51}]}
    roles['roles'] += [{'oid': 50, 'rolname': 'ambisgis_catalog_owner'}, {'oid': 51, 'rolname': 'ambisgis_transport_owner'}]
    return product, catalog, transport, schemas, roles


def receipt():
    return {'schema_version': 1, 'status': 'passed', 'snapshot': oracle.project(*data()),
            'denials': [{'role': role, 'case': case, 'sqlstate': '42501', 'authenticated_read': True, 'rollback': True}
                       for role, cases in oracle.CASES.items() for case in cases],
            'logical_state_unchanged': True, 'nontransactional_sequence_calls': False}


def denied(role='ambisgis_catalog_app'):
    row = {'session_user': role, 'current_user': role, 'database': oracle.ROLES[role][0], 'read_count': 4, 'read_only': 'off'}
    return 0, json.dumps(row).encode() + b'\nORACLE_SQLSTATE 42501\nORACLE_ROLLED_BACK\n', b'ERROR:  42501\n'


class OracleContracts(unittest.TestCase):
    def setUp(self):
        # Any accidental native execution/connection is a test failure. Individual
        # runner tests replace run with a finite fake and assert the exact contract.
        self.addCleanup(patch.stopall)
        patch('subprocess.Popen', side_effect=AssertionError('native subprocess forbidden')).start()
        patch('socket.socket', side_effect=AssertionError('native socket forbidden')).start()

    def test_projection_counts_identity_and_private_rows(self):
        value = receipt()
        self.assertIs(oracle.validate_receipt(value, value['snapshot']['identity']), value)
        self.assertEqual(value['snapshot']['catalog']['principals']['count'], 4)
        for secret in ('private-native-password-hash', 'private-oauth-secret', 'private-client', 'private changed metadata', 'private abstract'):
            self.assertNotIn(secret, oracle.encoded(value))

    def test_duplicate_selected_principal_resource_application_and_migration_rejected(self):
        for section in oracle.CATALOG_ROWS:
            values = data()
            values[1][section].append(copy.deepcopy(values[1][section][-1]))
            with self.subTest(section=section), self.assertRaises(ValueError):
                oracle.project(*values)

    def test_wrong_owner_item_type_rule_or_role_fails_closed(self):
        for change in ('owner', 'item', 'rule', 'membership', 'superuser', 'table_owner', 'database_owner'):
            values = data()
            if change == 'owner': values[1]['resources'][0]['owner_id'] = 2
            if change == 'item': values[1]['resources'][0]['alternate'] = 'fixture:other'
            if change == 'rule': values[2]['rules'][0]['grant_type'] = 'DENY'
            if change == 'membership': values[4]['memberships'].append({'member': 20})
            if change == 'superuser': values[4]['roles'][0]['rolsuper'] = True
            if change == 'table_owner': values[3][oracle.CATALOG]['relations'][0]['relowner'] = 20
            if change == 'database_owner': values[4]['databases'][0]['datdba'] = 51
            with self.subTest(change=change), self.assertRaises(ValueError): oracle.project(*values)

    def test_row_changes_change_fingerprint_even_when_counts_and_ids_stable(self):
        before = oracle.project(*data())
        for section, field in (('principals', 'password'), ('resources', 'title'),
                               ('applications', 'client_secret'), ('migrations', 'applied')):
            values = data(); values[1][section][0][field] = 'changed'
            after = oracle.project(*values)
            self.assertEqual(before['catalog'][section]['count'], after['catalog'][section]['count'])
            self.assertNotEqual(before['catalog'][section]['sha256'], after['catalog'][section]['sha256'])

    def test_malformed_duplicate_and_oversize_output_rejected(self):
        for raw in (b'', b'not-json', b'{"a":1,"a":2}', b' ' * (oracle.LIMIT + 1)):
            with self.subTest(size=len(raw)), self.assertRaises((ValueError, TypeError)): oracle.decode(raw)

    def test_successful_authenticated_read_and_exact_denial_rollback(self):
        native = oracle.NativeOracle(data()[0], {})
        for role in oracle.ROLES:
            with patch.object(native, 'run', return_value=denied(role)) as run:
                actual = native.deny(role, 'table_create')
                self.assertTrue(actual['rollback'])
                args = run.call_args.args
                self.assertEqual(args[:2], (role, oracle.ROLES[role][0]))
                sql = args[2]
                self.assertLess(sql.index('session_user'), sql.index('SAVEPOINT'))
                self.assertLess(sql.index('SAVEPOINT'), sql.index('CREATE TABLE'))
                self.assertIn('ROLLBACK TO SAVEPOINT installed_oracle; ROLLBACK;', sql)
                self.assertNotIn('READ ONLY', sql)

    def test_wrong_error_state_syntax_connection_timeout_and_success_rejected(self):
        native = oracle.NativeOracle(data()[0], {})
        for state in ('00000', '28P01', '42601', '25006', '57014', '25P02'):
            code, out, err = denied()
            out = out.replace(b'42501', state.encode()); err = err.replace(b'42501', state.encode())
            with self.subTest(state=state), patch.object(native, 'run', return_value=(code, out, err)), self.assertRaises(ValueError):
                native.deny('ambisgis_catalog_app', 'table_create')
        with patch.object(native, 'run', side_effect=subprocess.TimeoutExpired('fixed', 10)), self.assertRaises(subprocess.TimeoutExpired):
            native.deny('ambisgis_catalog_app', 'table_create')

    def test_42501_without_valid_same_session_identity_read_and_rollback_is_not_success(self):
        native = oracle.NativeOracle(data()[0], {})
        _, output, error = denied()
        row = json.loads(output.splitlines()[0])
        changes = [('current_user', 'ambisgis_admin'), ('session_user', 'ambisgis_admin'),
                   ('database', oracle.TRANSPORT), ('read_count', 0), ('read_count', True), ('read_only', 'on')]
        for key, val in changes:
            bad = dict(row); bad[key] = val
            out = json.dumps(bad).encode() + b'\nORACLE_SQLSTATE 42501\nORACLE_ROLLED_BACK\n'
            with self.subTest(key=key, val=val), patch.object(native, 'run', return_value=(0, out, error)), self.assertRaises(ValueError):
                native.deny('ambisgis_catalog_app', 'table_create')
        for value in ((1, output, error), (0, output.replace(b'ORACLE_ROLLED_BACK', b''), error),
                      (0, output, b''), (0, output, error + b'ERROR: 42601\n')):
            with patch.object(native, 'run', return_value=value), self.assertRaises(ValueError):
                native.deny('ambisgis_catalog_app', 'table_create')

    def test_runner_actual_tcp_auth_environment_stdin_and_complete_bounds(self):
        material = {key: 'secret-' + key for _, key, _ in oracle.ROLES.values()}
        material['database_admin'] = 'secret-admin'
        native = oracle.NativeOracle(data()[0], material)
        def run(argv, **kw):
            self.assertEqual(argv[0], oracle.PSQL)
            self.assertEqual(argv[argv.index('-h') + 1], '127.0.0.1')
            self.assertEqual(argv[argv.index('-U') + 1], 'ambisgis_catalog_app')
            self.assertEqual(kw['input'], b'fixed-synthetic-input')
            self.assertEqual(kw['env']['PGPASSWORD'], material['catalog_runtime'])
            self.assertNotIn('PGHOST', kw['env']); self.assertNotIn('PGOPTIONS', kw['env'])
            self.assertNotIn(material['catalog_runtime'], ' '.join(argv))
            self.assertLessEqual(kw['timeout'], 10)
            kw['stdout'].write(b'bounded-output'); kw['stderr'].write(b'')
            return SimpleNamespace(returncode=0)
        with patch.dict(os.environ, {'PGHOST': 'foreign', 'PGOPTIONS': 'foreign'}), patch.object(oracle.subprocess, 'run', side_effect=run):
            self.assertEqual(native.run('ambisgis_catalog_app', oracle.CATALOG, 'fixed-synthetic-input'), (0, b'bounded-output', b''))
        with patch.object(oracle.subprocess, 'run') as run, self.assertRaises(ValueError):
            native.run('ambisgis_catalog_app', oracle.TRANSPORT, 'fixed-synthetic-input')
        run.assert_not_called()

    def test_runner_overflow_timeout_and_expired_deadline_do_not_pass(self):
        native = oracle.NativeOracle(data()[0], {'catalog_runtime': 'private-password'})
        def overflow(argv, **kw):
            kw['stdout'].write(b'x' * (oracle.LIMIT + 1)); return SimpleNamespace(returncode=0)
        with patch.object(oracle.subprocess, 'run', side_effect=overflow), self.assertRaises(ValueError):
            native.run('ambisgis_catalog_app', oracle.CATALOG, 'fixed')
        with patch.object(oracle.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixed', 10)), self.assertRaises(subprocess.TimeoutExpired):
            native.run('ambisgis_catalog_app', oracle.CATALOG, 'fixed')
        native.deadline = -1
        with patch.object(oracle.subprocess, 'run') as run, self.assertRaises(ValueError):
            native.run('ambisgis_catalog_app', oracle.CATALOG, 'fixed')
        run.assert_not_called()

    def test_admin_projections_are_read_only_and_never_use_product_health(self):
        native = oracle.NativeOracle(data()[0], {})
        with patch.object(native, 'run', return_value=(0, b'[]', b'')) as run:
            self.assertEqual(native.rows(oracle.CATALOG, oracle.CATALOG_ROWS['migrations']), [])
            self.assertEqual(run.call_args.args[:2], ('ambisgis_admin', oracle.CATALOG))
            self.assertTrue(run.call_args.args[2].startswith('BEGIN READ ONLY;'))
            self.assertTrue(run.call_args.args[2].endswith('ROLLBACK;'))

    def test_all_fixed_denials_and_state_recheck_on_error_or_unexpected_drift(self):
        native = oracle.NativeOracle(data()[0], {})
        snap = receipt()['snapshot']
        with patch.object(native, 'snapshot', return_value=snap) as snapshots, patch.object(native, 'deny', return_value={'passed': True}) as deny:
            self.assertTrue(native.check()['logical_state_unchanged'])
            self.assertEqual(snapshots.call_count, 2)
            self.assertEqual(deny.call_count, 19)
        with patch.object(native, 'snapshot', return_value=snap) as snapshots, patch.object(native, 'deny', side_effect=TimeoutError), self.assertRaises(TimeoutError):
            native.check()
        self.assertEqual(snapshots.call_count, 2)
        changed = copy.deepcopy(snap); changed['catalog']['resources']['sha256'] = '0' * 64
        with patch.object(native, 'snapshot', side_effect=[snap, changed]), patch.object(native, 'deny'), self.assertRaises(ValueError):
            native.check()

    def test_receipt_identity_count_boolean_extra_and_omitted_denial_poison(self):
        for name in ('identity', 'count', 'status', 'denial', 'extra', 'schema_bool', 'rolledback', 'denial_numeric', 'id_bool'):
            value = receipt(); identity = copy.deepcopy(value['snapshot']['identity'])
            if name == 'identity': value['snapshot']['identity']['owner_pk'] += 1
            if name == 'count': value['snapshot']['catalog']['principals']['count'] = True
            if name == 'status': value['status'] = 'incomplete'
            if name == 'denial': value['denials'].pop()
            if name == 'extra': value['raw_sql'] = 'private'
            if name == 'schema_bool': value['schema_version'] = True
            if name == 'rolledback': value['logical_state_unchanged'] = False
            if name == 'denial_numeric': value['denials'][0]['rollback'] = 1
            if name == 'id_bool': value['snapshot']['identity']['owner_pk'] = True
            with self.subTest(name=name), self.assertRaises(ValueError): oracle.validate_receipt(value, identity)

    def test_no_unbounded_or_nontransactional_operation_in_fixed_cases(self):
        sql = ' '.join(case for cases in oracle.CASES.values() for case in cases.values()).lower()
        for denied_text in ('nextval', 'setval', 'create database', 'grant ', 'revoke ', 'set role'):
            self.assertNotIn(denied_text, sql)
        for case in ('policy_insert', 'policy_update', 'policy_delete'):
            self.assertIn('WHERE false', oracle.CASES['ambisgis_transport_reader'][case])

    def test_native_failure_output_never_serializes_secret_exception(self):
        from types import ModuleType
        common = ModuleType('ambisgis_development.common')
        common.inputs = lambda: (data()[0], {})
        output = io.StringIO()
        with patch.dict('sys.modules', {'ambisgis_development.common': common}), patch.object(oracle.NativeOracle, 'check', side_effect=ValueError('private-password/private-path')) as check, redirect_stdout(output):
            self.assertEqual(oracle.native_main(), 1)
        check.assert_called_once()
        self.assertEqual(json.loads(output.getvalue()), {'schema_version': 1, 'status': 'failed'})


class OracleWiringTests(unittest.TestCase):
    def setUp(self):
        self.fixture = concurrency_fixture.ConcurrentInstallationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.check = self.fixture.check
        self.addCleanup(patch.stopall)
        patch('subprocess.Popen', side_effect=AssertionError('native subprocess forbidden')).start()
        patch('socket.socket', side_effect=AssertionError('native socket forbidden')).start()

    def test_default_record_and_actual_inherited_journey_wiring_unchanged(self):
        with patch.object(oracle, 'observe') as observe:
            self.fixture.exercise_native_fixture()
        observe.assert_not_called()
        self.assertNotIn('installed_database_oracle', self.check.record)
        self.assertFalse(self.check.record['installed_sql_role_acceptance'])
        self.assertEqual(len(self.check.record['http_journeys']), 2)

    def test_opt_in_observes_after_baseline_and_before_later_journey(self):
        self.check.installed_database_oracle = True
        seen = []
        def observe(check):
            seen.append(len(check.record['http_journeys']))
            self.assertIsNotNone(check.native_identity)
            return receipt()
        with patch.object(oracle, 'observe', side_effect=observe):
            self.fixture.exercise_native_fixture()
        self.assertEqual(seen, [1, 1])
        self.assertEqual(len(self.check.record['http_journeys']), 2)
        self.assertTrue(self.check.record['installed_database_oracle']['complete'])
        self.assertTrue(self.check.record['installed_sql_role_acceptance'])
        self.assertFalse(self.check.record['native_uniqueness_acceptance'])
        self.assertFalse(self.check.record['full_installation_acceptance'])
        self.assertFalse(self.check.record['installed_database_oracle']['migration_secret_file_surface_verified'])

    def test_changed_native_cardinality_stops_before_second_journey_can_repair_it(self):
        self.check.installed_database_oracle = True
        before = receipt(); after = copy.deepcopy(before)
        after['snapshot']['catalog']['migrations']['count'] += 1
        with patch.object(oracle, 'observe', side_effect=[before, after]), self.assertRaisesRegex(ValueError, 'logical state changed'):
            self.fixture.exercise_native_fixture()
        self.assertEqual(len(self.check.record['http_journeys']), 1)
        self.assertFalse(self.check.record['installed_database_oracle']['complete'])
        self.assertFalse(self.check.record['installed_sql_role_acceptance'])

    def test_timeout_fails_without_second_journey_or_database_credit(self):
        self.check.installed_database_oracle = True
        with patch.object(oracle, 'observe', side_effect=TimeoutError), self.assertRaises(TimeoutError):
            self.fixture.exercise_native_fixture()
        self.assertEqual(len(self.check.record['http_journeys']), 1)
        self.assertFalse(self.check.record['installed_database_oracle']['complete'])
        self.assertFalse(self.check.record['installed_sql_role_acceptance'])

    def test_main_oracle_failure_retains_error_and_runs_existing_finally_shutdown(self):
        from argparse import Namespace
        args = Namespace(directory=self.fixture.f.base / 'fresh-oracle', output=self.fixture.f.base / 'oracle-evidence',
                         bundle=self.fixture.f.manifest, bundle_sha256=self.fixture.f.identity,
                         installed_database_oracle=True)
        def exercise(check, *unused):
            check.database_snapshot('before')
        with patch.object(concurrent.ConcurrentCheck, 'exercise', exercise), patch.object(oracle, 'observe', side_effect=TimeoutError), \
                patch.object(concurrent.ConcurrentCheck, 'shutdown', return_value={'complete': False, 'reconciliation_required': True}) as shutdown:
            self.assertEqual(concurrent.main(args), 1)
        shutdown.assert_called_once()
        result = json.loads((args.output / 'result.json').read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_type'], 'TimeoutError')
        self.assertFalse(result['installed_database_oracle']['complete'])
        self.assertFalse(result['installed_sql_role_acceptance'])
        self.assertFalse(result['shutdown']['complete'])
        self.assertTrue(any(Path(row['path']).name == 'installed_database_oracle.py' for row in result['sources']))

    def test_observer_uses_owned_database_only_and_rejects_stopped_service(self):
        self.check.native_identity = receipt()['snapshot']['identity']
        self.check.native_identity['install_id'] = self.check.record['install_id']
        value = receipt(); value['snapshot']['identity'] = dict(self.check.native_identity)
        product = {'install_id': self.check.record['install_id']}
        rows = {role: {'process': 'running'} for role in concurrent.bundle.SERVICES}
        rows.update({role: {'process': 'absent'} for role in ('catalog-init', 'geoserver-init')})
        calls = []
        def engine(*args, **kwargs):
            calls.append((args, kwargs)); return 0, oracle.encoded(value).encode()
        self.check.rt = SimpleNamespace(config=product, processes=lambda **kw: rows, engine=engine)
        self.assertEqual(oracle.observe(self.check), value)
        argv, kw = calls[0]
        self.assertEqual(argv[:4], ('exec', concurrent.config.project_name(product) + '-database', '/opt/ambisgis/python/bin/python3', '-c'))
        self.assertEqual(argv[4], Path(oracle.__file__).read_text())
        self.assertEqual(kw, {'timeout': 150, 'allow_failure': True})
        rows['database']['process'] = 'stopped'
        with self.assertRaises(ValueError): oracle.observe(self.check)
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
