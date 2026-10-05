"""Opt-in fixed installed-database evidence for a fresh concurrency invocation.

The host entry is observe(check); the same reviewed file is sent as fixed Python
code to that invocation's owned database container. There is no SQL, database,
role, installation-adoption or connection-target command-line input.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid

LIMIT = 1024 * 1024
PSQL = '/opt/ambisgis/postgres/bin/psql'
CATALOG = 'ambisgis_catalog'
TRANSPORT = 'ambisgis_transport'
ROLES = {
    'ambisgis_catalog_app': (CATALOG, 'catalog_runtime', 'public.people_profile'),
    'ambisgis_render_reader': (CATALOG, 'render_reader', 'pg_catalog.pg_class'),
    'ambisgis_transport_reader': (TRANSPORT, 'transport_reader', 'public.gf_rule'),
}

# Each case is transactional. The zero-row DML still requires the native table
# privilege, but cannot invoke a row default/sequence even under a bad grant.
# No SET ROLE, GRANT, REVOKE, CREATE DATABASE, nextval or setval is executed.
CASES = {
    'ambisgis_catalog_app': {
        'schema_create': 'CREATE SCHEMA ambisgis_installed_oracle_denied',
        'table_create': 'CREATE TABLE public.ambisgis_installed_oracle_denied(id integer)',
        'temporary_table': 'CREATE TEMPORARY TABLE ambisgis_installed_oracle_denied(id integer)',
        'migration_ddl': 'ALTER TABLE public.django_migrations ADD COLUMN ambisgis_installed_oracle_denied integer',
        'owner_change': 'ALTER TABLE public.base_resourcebase OWNER TO ambisgis_catalog_app',
    },
    'ambisgis_render_reader': {
        'schema_create': 'CREATE SCHEMA ambisgis_installed_oracle_denied',
        'table_create': 'CREATE TABLE public.ambisgis_installed_oracle_denied(id integer)',
        'temporary_table': 'CREATE TEMPORARY TABLE ambisgis_installed_oracle_denied(id integer)',
        'catalog_read': 'SELECT id FROM public.people_profile LIMIT 1',
        'catalog_delete': 'DELETE FROM public.base_resourcebase WHERE false',
        'migration_ddl': 'ALTER TABLE public.django_migrations ADD COLUMN ambisgis_installed_oracle_denied integer',
    },
    'ambisgis_transport_reader': {
        'schema_create': 'CREATE SCHEMA ambisgis_installed_oracle_denied',
        'table_create': 'CREATE TABLE public.ambisgis_installed_oracle_denied(id integer)',
        'temporary_table': 'CREATE TEMPORARY TABLE ambisgis_installed_oracle_denied(id integer)',
        'migration_ddl': 'ALTER TABLE public.gf_rule ADD COLUMN ambisgis_installed_oracle_denied integer',
        'owner_change': 'ALTER TABLE public.gf_rule OWNER TO ambisgis_transport_reader',
        'policy_insert': 'INSERT INTO public.gf_rule(id,priority,grant_type) SELECT id,priority,grant_type FROM public.gf_rule WHERE false',
        'policy_update': 'UPDATE public.gf_rule SET priority=priority WHERE false',
        'policy_delete': 'DELETE FROM public.gf_rule WHERE false',
    },
}

# Fixed identifiers trace to the selected owned models/recorder; see the
# accompanying source references. No arbitrary SQL/table selector is accepted.
CATALOG_ROWS = {
    'principals': 'SELECT id,username,password,is_active,is_staff,is_superuser,date_joined FROM public.people_profile ORDER BY id',
    'resources': 'SELECT id,uuid,alternate,owner_id,title,abstract,is_published,is_approved,resource_type FROM public.base_resourcebase ORDER BY id',
    'applications': 'SELECT id,client_id,client_secret,user_id,name,client_type,authorization_grant_type,redirect_uris,skip_authorization FROM public.oauth2_provider_application ORDER BY id',
    'migrations': 'SELECT id,app,name,applied FROM public.django_migrations ORDER BY app,name,id',
}
TRANSPORT_ROWS = {
    'rules': 'SELECT * FROM public.gf_rule ORDER BY id',
    'sequence': 'SELECT last_value,is_called FROM public.hibernate_sequence',
}
SCHEMA_ROWS = {
    'relations': "SELECT c.oid,n.nspname,c.relname,c.relkind,c.relowner,c.relacl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' ORDER BY c.oid",
    'columns': "SELECT a.attrelid,a.attnum,a.attname,a.atttypid,a.atttypmod,a.attnotnull,a.attisdropped,a.attidentity,a.attgenerated,a.attacl,pg_get_expr(d.adbin,d.adrelid) AS expression FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attnum>0 AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' ORDER BY a.attrelid,a.attnum",
    'constraints': "SELECT c.oid,c.conrelid,c.conname,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' ORDER BY c.oid",
    'namespaces': "SELECT oid,nspname,nspowner,nspacl FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema' ORDER BY oid",
    'default_acl': 'SELECT oid,defaclrole,defaclnamespace,defaclobjtype,defaclacl FROM pg_default_acl ORDER BY oid',
}
ROLE_ROWS = "SELECT oid,rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls FROM pg_roles WHERE rolname LIKE 'ambisgis_%' ORDER BY oid"
MEMBER_ROWS = 'SELECT roleid,member,grantor,admin_option FROM pg_auth_members ORDER BY roleid,member,grantor'
DATABASE_ROWS = 'SELECT oid,datname,datdba,datacl FROM pg_database ORDER BY oid'


def require(condition):
    if not condition:
        raise ValueError('Installed database oracle contract failed.')


def pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result)
        result[key] = value
    return result


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def fingerprint(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def decode(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= LIMIT)
    return json.loads(raw, object_pairs_hook=pairs)


def summary(rows):
    require(type(rows) is list and len(rows) <= 10000 and all(type(row) is dict for row in rows))
    return {'count': len(rows), 'sha256': fingerprint(rows)}


def project(product, catalog, transport, schemas, roles, *, _stage=None):
    """Keep raw rows, including native password/client hashes, in memory only."""
    require(set(catalog) == set(CATALOG_ROWS) and set(transport) == set(TRANSPORT_ROWS))
    if _stage is not None: _stage('principals')
    users = catalog['principals']
    selected = {}
    for key, name in (('owner', product['owner']), ('viewer', product['viewer']),
                      ('health', 'installation-health'), ('anonymous', 'AnonymousUser')):
        rows = [row for row in users if row['username'] == name]
        require(len(rows) == 1 and type(rows[0]['id']) is int)
        selected[key] = rows[0]
    require(len({row['id'] for row in selected.values()}) == 4)
    require(all(row['is_active'] is True and row['is_staff'] is False and row['is_superuser'] is False
                for key, row in selected.items() if key != 'anonymous'))
    if _stage is not None: _stage('resource')
    expected_uuid = str(uuid.uuid5(uuid.UUID(product['install_id']), 'diagnostic-private-points'))
    resources = [row for row in catalog['resources'] if row['uuid'] == expected_uuid or row['alternate'] == 'fixture:private_points']
    require(len(resources) == 1)
    item = resources[0]
    require(item['uuid'] == expected_uuid and item['alternate'] == 'fixture:private_points'
            and item['owner_id'] == selected['owner']['id'] and type(item['id']) is int
            and item['is_published'] is True and item['is_approved'] is True and item['resource_type'] == 'dataset')
    if _stage is not None: _stage('application')
    applications = [row for row in catalog['applications'] if row['name'] == 'AmbisGIS development']
    require(len(applications) == 1 and applications[0]['user_id'] == selected['owner']['id']
            and applications[0]['client_type'] == 'confidential'
            and applications[0]['authorization_grant_type'] == 'authorization-code'
            and applications[0]['skip_authorization'] is False)
    if _stage is not None: _stage('migrations')
    migrations = catalog['migrations']
    require(migrations and len({(row['app'], row['name']) for row in migrations}) == len(migrations)
            and len({row['id'] for row in migrations}) == len(migrations)
            and all(type(row['id']) is int and row['applied'] and row['app'] and row['name'] for row in migrations))
    if _stage is not None: _stage('transport')
    rules = transport['rules']
    require(len(rules) == 2 and len({row['id'] for row in rules}) == 2)
    require(sorted((row['priority'], row['service'], row['request'], row['workspace'], row['layer'], row['grant_type'])
                   for row in rules) == [(10, 'WMS', 'GETMAP', 'fixture', 'private_points', 'ALLOW'),
                                         (20, 'WFS', 'GETFEATURE', 'fixture', 'private_points', 'ALLOW')])
    require(len(transport['sequence']) == 1)
    if _stage is not None: _stage('roles')
    role_by_name = {row['rolname']: row for row in roles['roles']}
    owners = {CATALOG: 'ambisgis_catalog_owner', TRANSPORT: 'ambisgis_transport_owner'}
    require(all(name in role_by_name for name in (*ROLES, *owners.values())))
    if _stage is not None: _stage('ownership')
    for db, owner in owners.items():
        db_rows = [row for row in roles['databases'] if row['datname'] == db]
        require(len(db_rows) == 1 and db_rows[0]['datdba'] == role_by_name[owner]['oid'])
        names = ('people_profile', 'base_resourcebase', 'oauth2_provider_application', 'django_migrations') if db == CATALOG else ('gf_rule', 'hibernate_sequence')
        for name in names:
            rows = [row for row in schemas[db]['relations'] if row['nspname'] == 'public' and row['relname'] == name]
            require(len(rows) == 1 and rows[0]['relowner'] == role_by_name[owner]['oid'])
    if _stage is not None: _stage('roles')
    for name in ROLES:
        row = role_by_name[name]
        require(row['rolcanlogin'] is True and all(row[key] is False for key in
                ('rolsuper', 'rolinherit', 'rolcreaterole', 'rolcreatedb', 'rolreplication', 'rolbypassrls')))
        require(not any(member['member'] == row['oid'] for member in roles['memberships']))
        require(not any(item['relowner'] == row['oid'] for entries in schemas.values() for item in entries['relations'])
                and not any(item['nspowner'] == row['oid'] for entries in schemas.values() for item in entries['namespaces']))
    result = {'identity': {'install_id': product['install_id'], 'resource_uuid': expected_uuid,
                          'resource_pk': item['id'], 'owner_pk': selected['owner']['id'],
                          'viewer_pk': selected['viewer']['id']},
              'catalog': {name: summary(rows) for name, rows in catalog.items()},
              'transport': {name: summary(rows) for name, rows in transport.items()},
              'schemas': {db: {name: summary(rows) for name, rows in entries.items()} for db, entries in schemas.items()},
              'roles': {name: summary(rows) for name, rows in roles.items()}}
    # Canonical JSON only; no SQL, password, role credential, metadata or row data
    # crosses the native process boundary.
    return result


# Failure vocabulary is fixed by this source, never exception messages, query
# text, row values, paths or stderr. Unknown native errors remain unclassified.
SQLSTATES = frozenset(('00000', '42501', '42703', '42P01', '42601', '28P01',
                      '3D000', '57014', '25006', '25P02', '23505', '42P07'))
STAGES = frozenset(('input', 'native_check', 'state_compare', 'host_preflight',
                    'host_exec', 'host_native_receipt', 'host_success_receipt',
                    'host_identity_recheck')) | frozenset(
    phase + '.' + group + '.' + name
    for phase in ('snapshot_before', 'snapshot_after')
    for group, names in (('catalog', CATALOG_ROWS), ('transport', TRANSPORT_ROWS),
                         ('catalog_schema', SCHEMA_ROWS), ('transport_schema', SCHEMA_ROWS),
                         ('roles', ('roles', 'memberships', 'databases')),
                         ('project', ('contract', 'principals', 'resource', 'application', 'migrations', 'transport', 'roles', 'ownership')))
    for name in names) | frozenset('denial.' + role + '.' + case
                                for role, cases in CASES.items() for case in cases)


RETURN_CODES = frozenset(('0', '1', '125', '126', '127', 'signal', 'OTHER', 'not_observed'))


def return_code_class(value):
    if type(value) is not int:
        return 'OTHER'
    if value in (0, 1, 125, 126, 127):
        return str(value)
    return 'signal' if -64 <= value < 0 else 'OTHER'


def failure_fact(error, stage, sqlstate='not_observed', rollback='not_observed', return_code='not_observed'):
    kinds = {ValueError: 'ValueError', TypeError: 'TypeError', KeyError: 'KeyError',
             RuntimeError: 'RuntimeError', OSError: 'OSError', ImportError: 'ImportError',
             ModuleNotFoundError: 'ModuleNotFoundError', json.JSONDecodeError: 'JSONDecodeError',
             subprocess.TimeoutExpired: 'TimeoutExpired', TimeoutError: 'TimeoutError'}
    return {'stage': stage if type(stage) is str and stage in STAGES else 'OTHER',
            'exception_class': kinds.get(type(error), 'OTHER'),
            'sqlstate': sqlstate if type(sqlstate) is str and sqlstate in SQLSTATES | {'not_observed', 'OTHER'} else 'OTHER',
            'rollback': rollback if type(rollback) is str and rollback in ('not_observed', 'marker_observed') else 'not_observed',
            'return_code': return_code if type(return_code) is str and return_code in RETURN_CODES else 'OTHER'}


def validate_failure(value):
    require(type(value) is dict and set(value) == {'schema_version', 'status', 'failures'}
            and type(value['schema_version']) is int and value['schema_version'] == 1
            and value['status'] == 'failed' and type(value['failures']) is list
            and 1 <= len(value['failures']) <= 2)
    classes = {'ValueError', 'TypeError', 'KeyError', 'RuntimeError', 'OSError', 'ImportError',
               'ModuleNotFoundError', 'JSONDecodeError', 'TimeoutExpired', 'TimeoutError', 'OTHER'}
    for row in value['failures']:
        require(type(row) is dict and set(row) == {'stage', 'exception_class', 'sqlstate', 'rollback', 'return_code'})
        require(type(row['stage']) is str and row['stage'] in STAGES | {'OTHER'}
                and type(row['exception_class']) is str and row['exception_class'] in classes
                and type(row['sqlstate']) is str and row['sqlstate'] in SQLSTATES | {'not_observed', 'OTHER'}
                and type(row['rollback']) is str and row['rollback'] in ('not_observed', 'marker_observed')
                and type(row['return_code']) is str and row['return_code'] in RETURN_CODES)
    return value


class NativeOracle:
    def __init__(self, product, material):
        self.product, self.material = product, material
        self.deadline = time.monotonic() + 120
        self.phase, self.stage = 'snapshot_before', 'native_check'
        self.sqlstate, self.rollback = 'not_observed', 'not_observed'
        self.return_code = 'not_observed'
        self.failures = []

    def at(self, stage):
        require(stage in STAGES)
        self.stage = stage
        self.sqlstate, self.rollback = 'not_observed', 'not_observed'
        self.return_code = 'not_observed'

    def failed(self, error):
        return failure_fact(error, self.stage, self.sqlstate, self.rollback, self.return_code)

    def outcome(self, code, output, error):
        self.return_code = return_code_class(code)
        match = re.fullmatch(rb'(?:ERROR|FATAL):\s+([0-9A-Z]{5})\s*', error)
        if code == 0 and error == b'':
            self.sqlstate = '00000'
        elif match:
            value = match.group(1).decode('ascii')
            self.sqlstate = value if value in SQLSTATES else 'OTHER'
        else:
            self.sqlstate = 'OTHER'
        # This is only an observed fixed marker, never an inferred rollback after
        # timeout/disconnection or a claim that all database storage is unchanged.
        if code == 0 and output.splitlines()[-1:] == [b'ORACLE_ROLLED_BACK']:
            self.rollback = 'marker_observed'

    def run(self, role, database, statement):
        # All callers below select literals from this file; there is no protocol
        # accepting statements, roles, targets or credentials from a caller.
        if role == 'ambisgis_admin':
            target, key = '/var/lib/ambisgis/socket', 'database_admin'
        else:
            expected_db, key, _ = ROLES[role]
            require(database == expected_db)
            target = '127.0.0.1'
        env = {'PGPASSWORD': self.material[key], 'PGCONNECT_TIMEOUT': '4',
               'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
        if 'LD_LIBRARY_PATH' in os.environ:
            env['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
        remaining = min(10, self.deadline - time.monotonic())
        require(remaining > 0)
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            result = subprocess.run([PSQL, '-X', '-qAt', '-w', '-v', 'ON_ERROR_STOP=1',
                                     '-h', target, '-p', '5432', '-U', role, '-d', database],
                                    input=statement.encode(), env=env,
                                    stdout=stdout, stderr=stderr, timeout=remaining, check=False)
            self.return_code = return_code_class(result.returncode)
            stdout.seek(0); output = stdout.read(LIMIT + 1)
            stderr.seek(0); error = stderr.read(LIMIT + 1)
        require(len(output) + len(error) <= LIMIT and type(result.returncode) is int)
        return result.returncode, output, error

    def rows(self, database, select):
        statement = ('\\set VERBOSITY sqlstate\nBEGIN READ ONLY; SET LOCAL statement_timeout=4000; SET LOCAL lock_timeout=1500; '
                     "SELECT COALESCE(json_agg(t),'[]'::json) FROM (" + select + ') t; ROLLBACK;')
        code, output, error = self.run('ambisgis_admin', database, statement)
        self.outcome(code, output, error)
        require(code == 0 and error == b'')
        result = decode(output)
        summary(result)
        return result

    def snapshot(self):
        def rows(group, database, statements):
            result = {}
            for name, query in statements.items():
                self.at(self.phase + '.' + group + '.' + name)
                result[name] = self.rows(database, query)
            return result
        catalog = rows('catalog', CATALOG, CATALOG_ROWS)
        transport = rows('transport', TRANSPORT, TRANSPORT_ROWS)
        schemas = {CATALOG: rows('catalog_schema', CATALOG, SCHEMA_ROWS),
                   TRANSPORT: rows('transport_schema', TRANSPORT, SCHEMA_ROWS)}
        roles = rows('roles', CATALOG, {'roles': ROLE_ROWS, 'memberships': MEMBER_ROWS,
                                       'databases': DATABASE_ROWS})
        self.at(self.phase + '.project.contract')
        return project(self.product, catalog, transport, schemas, roles,
                       _stage=lambda name: self.at(self.phase + '.project.' + name))

    def deny(self, role, case):
        self.at('denial.' + role + '.' + case)
        database, _, relation = ROLES[role]
        # ON_ERROR_STOP is disabled only around the one named operation, so even
        # an unexpected success is rolled back. An aborted transaction is first
        # rolled back to the savepoint, then the outer transaction is rolled back.
        sql = "\\set VERBOSITY sqlstate\nBEGIN; SET LOCAL statement_timeout=4000; SET LOCAL lock_timeout=1500;\n"
        sql += ("SELECT json_build_object('session_user',session_user,'current_user',current_user,"
                "'database',current_database(),'read_count',count(*),'read_only',current_setting('transaction_read_only')) FROM " + relation + ';\n')
        sql += 'SAVEPOINT installed_oracle;\n\\set ON_ERROR_STOP off\n' + CASES[role][case] + ';\n'
        sql += ('\\echo ORACLE_SQLSTATE :SQLSTATE\n\\set ON_ERROR_STOP on\n'
                "ROLLBACK TO SAVEPOINT installed_oracle; ROLLBACK; SELECT 'ORACLE_ROLLED_BACK';\n")
        code, output, error = self.run(role, database, sql)
        self.outcome(code, output, error)
        lines = output.splitlines()
        require(code == 0 and len(lines) == 3 and lines[1:] == [b'ORACLE_SQLSTATE 42501', b'ORACLE_ROLLED_BACK'])
        identity = decode(lines[0])
        require(set(identity) == {'session_user', 'current_user', 'database', 'read_count', 'read_only'}
                and identity['session_user'] == identity['current_user'] == role
                and identity['database'] == database and identity['read_only'] == 'off'
                and type(identity['read_count']) is int and identity['read_count'] > 0)
        require(re.fullmatch(rb'ERROR:\s+42501\s*', error) is not None)
        return {'role': role, 'case': case, 'sqlstate': '42501', 'authenticated_read': True, 'rollback': True}

    def check(self):
        before = self.snapshot()
        denials = []
        try:
            for role, cases in CASES.items():
                for case in cases:
                    denials.append(self.deny(role, case))
        except BaseException as error:
            self.failures.append(self.failed(error))
            raise
        finally:
            # This is a logical projection, not equality of WAL/statistics or all
            # database bytes. A failed/timeout/aborted observation cannot pass.
            self.phase = 'snapshot_after'
            try:
                after = self.snapshot()
                self.at('state_compare')
                require(before == after)
            except BaseException as error:
                self.failures.append(self.failed(error))
                raise
        return {'schema_version': 1, 'status': 'passed', 'snapshot': before, 'denials': denials,
                'logical_state_unchanged': True, 'nontransactional_sequence_calls': False}


def native_main():
    native = None
    try:
        from ambisgis_development.common import inputs
        product, material = inputs()
        native = NativeOracle(product, material)
        result = native.check()
        print(encoded(result), flush=True)
        return 0
    except BaseException as error:
        facts = native.failures if native is not None else []
        if not facts:
            facts = [native.failed(error) if native is not None else failure_fact(error, 'input')]
        # No raw exception fields or native output enter this finite receipt.
        print(encoded(validate_failure({'schema_version': 1, 'status': 'failed', 'failures': facts})), flush=True)
        return 1


def validate_receipt(value, identity):
    require(type(value) is dict and set(value) == {'schema_version', 'status', 'snapshot', 'denials',
                                                  'logical_state_unchanged', 'nontransactional_sequence_calls'})
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['status'] == 'passed'
            and value['logical_state_unchanged'] is True and value['nontransactional_sequence_calls'] is False)
    require(value['denials'] == [{'role': role, 'case': case, 'sqlstate': '42501', 'authenticated_read': True, 'rollback': True}
                               for role, cases in CASES.items() for case in cases])
    require(all(row['authenticated_read'] is True and row['rollback'] is True for row in value['denials']))
    snapshot = value['snapshot']
    require(set(snapshot) == {'identity', 'catalog', 'transport', 'schemas', 'roles'} and snapshot['identity'] == identity)
    require(set(identity) == {'install_id', 'resource_uuid', 'resource_pk', 'owner_pk', 'viewer_pk'}
            and all(type(snapshot['identity'][key]) is int for key in ('resource_pk', 'owner_pk', 'viewer_pk')))
    expected = {'catalog': set(CATALOG_ROWS), 'transport': set(TRANSPORT_ROWS),
                'roles': {'roles', 'memberships', 'databases'}}
    for kind, names in expected.items():
        require(set(snapshot[kind]) == names)
    require(set(snapshot['schemas']) == {CATALOG, TRANSPORT})
    for rows in snapshot['schemas'].values():
        require(set(rows) == set(SCHEMA_ROWS))
    groups = [snapshot[k] for k in expected] + list(snapshot['schemas'].values())
    for group in groups:
        for row in group.values():
            require(type(row) is dict and set(row) == {'count', 'sha256'}
                    and type(row['count']) is int and 0 <= row['count'] <= 10000
                    and isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']))
    require(snapshot['catalog']['migrations']['count'] > 0 and snapshot['transport']['rules']['count'] == 2
            and snapshot['transport']['sequence']['count'] == 1)
    return value


def observe(check):
    """Only the existing fresh invocation calls this; no existing-install CLI."""
    from installer import config
    stage, engine_return_code = 'host_preflight', 'not_observed'
    evidence = check.record.setdefault('installed_database_oracle', {'status': 'running', 'complete': False})
    try:
        check.assert_root()
        check.capture_identity()
        require(check.rt.config['install_id'] == check.record['install_id'])
        require(check.native_identity['install_id'] == check.record['install_id'])
        observed = check.rt.processes(include_initializers=True)
        require(all(observed[role]['process'] == 'running' for role in ('database', 'catalog', 'geoserver', 'gateway'))
                and all(observed[role]['process'] != 'running' for role in ('catalog-init', 'geoserver-init')))
        program = Path(__file__).read_text()
        stage = 'host_exec'
        code, output = check.rt.engine('exec', config.project_name(check.rt.config) + '-database',
                                      '/opt/ambisgis/python/bin/python3', '-c', program,
                                      timeout=150, allow_failure=True)
        engine_return_code = return_code_class(code)
        evidence['engine_return_code'] = engine_return_code
        stage = 'host_native_receipt'
        require(type(code) is int and type(output) is bytes and len(output) <= 65536)
        if code != 0:
            value = validate_failure(decode(output))
            evidence['failures'] = value['failures']
            raise ValueError('Installed database oracle failed.')
        stage = 'host_success_receipt'
        value = validate_receipt(decode(output), check.native_identity)
        require(check.safe(encoded(value)))
        stage = 'host_identity_recheck'
        check.capture_identity()
        return value
    except BaseException as error:
        if 'failures' not in evidence:
            evidence['failures'] = [failure_fact(error, stage, return_code=engine_return_code)]
        raise


if __name__ == '__main__':
    raise SystemExit(native_main())
