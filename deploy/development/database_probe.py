#!/usr/bin/env python3
"""Supplementary real owned-PostgreSQL privilege checks; not installer acceptance.

Run under build-support/postgis/offline_exec.py. This creates and stops only its
new marked synthetic cluster, with a private Unix socket and no TCP listener.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/development'))
from ambisgis_development import database


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''): value.update(part)
    return value.hexdigest()


def retained_inventory(prefix, manifest):
    inventory = json.loads(manifest.read_text())
    actual = {str(path.relative_to(prefix)) for path in prefix.rglob('*') if path.is_file() or path.is_symlink()}
    if actual != set(inventory): raise ValueError('retained prefix membership changed')
    for name, item in inventory.items():
        path = prefix / name
        if 'symlink' in item:
            if not path.is_symlink() or os.readlink(path) != item['symlink']: raise ValueError('retained link changed')
        elif path.is_symlink() or sha(path) != item['sha256']:
            raise ValueError('retained prefix bytes changed')
    return {'manifest_sha256': sha(manifest), 'members_verified': len(inventory)}


def run(arguments, *, data=None, fail=False):
    result = subprocess.run([str(x) for x in arguments], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if (result.returncode != 0) != fail:
        raise RuntimeError('native command had unexpected exit status: ' + result.stderr.decode(errors='replace')[:1000])
    return result.stdout.decode().strip()


def main(args):
    output = args.output.absolute(); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    record = {'scope': 'supplementary synthetic Unix-only SQL privilege checks; not container installation acceptance',
              'started': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'cases': [],
              'source': {str(path.relative_to(ROOT)): sha(path) for path in (Path(__file__).resolve(), Path(database.__file__))}}
    snapshots = output / 'source'; snapshots.mkdir(mode=0o700)
    for path in (Path(__file__).resolve(), Path(database.__file__)):
        (snapshots / path.name).write_bytes(path.read_bytes())
    (output / 'SYNTHETIC_CLUSTER.json').write_text(json.dumps({'owner': 'PLT-01 database_probe.py', 'output': str(output)}) + '\n')
    prefix = args.build / 'prefix'
    retained = json.loads((args.build / 'result.json').read_text())
    if (retained['result_exit_code'] != 0 or retained['owned_sources']['postgresql']['commit'] != '2ff1375b5dd8bf09d8cb0e795974528180fd75ca'
            or retained['owned_sources']['postgis']['commit'] != '9816f82458db774e62906cfb2c4f01f8b262c862'
            or sha(args.build / 'output-manifest.json') != retained['output_manifest_sha256']):
        raise ValueError('owned native build binding differs')
    record['owned_build'] = {'result_sha256': sha(args.build / 'result.json'), 'sources': retained['owned_sources'],
                             **retained_inventory(prefix, args.build / 'output-manifest.json')}
    support = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/postgis-slice/run-003/prefix')
    record['support'] = retained_inventory(support, args.build / 'support-inputs.json')
    os.environ.clear()
    os.environ.update(PATH=str(prefix / 'bin') + ':/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8',
                      LD_LIBRARY_PATH=str(prefix / 'lib') + ':' + str(support / 'lib'), PROJ_NETWORK='OFF',
                      PROJ_DATA=str(support / 'share/proj'), HOME=str(output), TMPDIR=str(output))
    pgdata = output / 'pgdata'; started = False
    material = {key: secrets.token_urlsafe(48) for key in ('database_admin', *database.ROLES.values())}
    try:
        with tempfile.TemporaryDirectory(prefix='ag-plt-db-', dir='/tmp') as local:
            local = Path(local); (local / 'socket').mkdir(mode=0o700)
            database.PREFIX, database.DATA = prefix, local
            database.inputs = lambda: ({}, material)  # Fixture configuration only; all policy SQL remains real.
            run([prefix / 'bin/initdb', '-D', pgdata, '-U', 'ambisgis_admin', '--auth-local=trust', '--auth-host=reject', '--locale=C.UTF-8'])
            run([prefix / 'bin/pg_ctl', '-D', pgdata, '-l', output / 'database.log', '-o',
                 "-c listen_addresses='' -c unix_socket_directories=" + str(local / 'socket'), '-w', 'start'])
            started = True
            record['server_version'] = database.sql('SHOW server_version;', material['database_admin'])
            record['listen_addresses'] = database.sql('SHOW listen_addresses;', material['database_admin'])
            if record['listen_addresses']: raise AssertionError('TCP listener unexpectedly enabled')
            try:
                database.bootstrap({}, material)
            except ValueError:
                record['initial_privilege_diagnostics'] = {
                    db: database.sql(database.privilege_audit(db).replace('SELECT count(*) FROM problems',
                                      'SELECT json_agg(problems) FROM problems'), material['database_admin'], database=db)
                    for db in database.DATABASE_OWNERS}
                raise
            database.bootstrap({}, material)
            if not database.health(): raise AssertionError('native database health failed')
            record['cases'].append({'name': 'fresh_and_repeated_real_bootstrap', 'passed': True})

            def admin(statement, db='ambisgis_catalog'):
                return database.sql(statement, material['database_admin'], database=db)

            def as_role(role, statement, db='ambisgis_catalog', fail=False):
                return run([prefix / 'bin/psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-h', local / 'socket',
                            '-U', role, '-d', db], data=statement.encode(), fail=fail)

            admin('SET ROLE ambisgis_catalog_owner; CREATE TABLE protected_rows(id serial PRIMARY KEY, value text); INSERT INTO protected_rows(value) VALUES (\'original\'); RESET ROLE;')
            admin('SET ROLE ambisgis_transport_owner; CREATE TABLE protected_rules(id serial PRIMARY KEY, value text); INSERT INTO protected_rules(value) VALUES (\'original\'); RESET ROLE;', 'ambisgis_transport')
            database.validate_existing_privileges(material['database_admin'])
            as_role('ambisgis_catalog_app', "INSERT INTO protected_rows(value) VALUES ('allowed'); UPDATE protected_rows SET value='updated' WHERE id=2; DELETE FROM protected_rows WHERE id=2;")
            if as_role('ambisgis_transport_reader', 'SELECT count(*) FROM protected_rules;', 'ambisgis_transport') != '1': raise AssertionError('SELECT failed')
            # Same query used by the retained Hibernate PostgreSQL dialect.
            # SELECT visibility must not confer sequence advancement or DDL.
            admin('SET ROLE ambisgis_transport_owner; CREATE SEQUENCE hibernate_sequence; '
                  'CREATE SEQUENCE "quoted sequence"; CREATE SCHEMA private_fixture; '
                  'CREATE SEQUENCE private_fixture.hidden_sequence; RESET ROLE; '
                  'CREATE SEQUENCE foreign_owner_sequence;', 'ambisgis_transport')
            def visible_sequences():
                rows = as_role('ambisgis_transport_reader', 'select * from information_schema.sequences;', 'ambisgis_transport')
                return {(row.split('|')[1], row.split('|')[2]) for row in rows.splitlines()}
            expected_sequences = {('public', name) for name in ('protected_rules_id_seq', 'hibernate_sequence', 'quoted sequence')}
            if visible_sequences() != expected_sequences: raise AssertionError('Hibernate sequence metadata is not exactly visible')
            database.validate_existing_privileges(material['database_admin'])
            record['cases'].append({'name': 'future_owner_public_sequence_select_visible', 'passed': True})
            # Model an existing installation whose sequences predate the new
            # default ACL. Only exact owner/public objects may gain SELECT.
            admin('REVOKE SELECT ON SEQUENCE hibernate_sequence,"quoted sequence" FROM ambisgis_transport_reader;', 'ambisgis_transport')
            if visible_sequences() != {('public', 'protected_rules_id_seq')}: raise AssertionError('fixture revoke did not hide metadata')
            database.bootstrap({}, material)
            database.bootstrap({}, material)
            if visible_sequences() != expected_sequences: raise AssertionError('existing owned sequence metadata not restored')
            if admin("SELECT count(*) FROM pg_class c WHERE c.relkind='S' AND c.relname IN ('foreign_owner_sequence','hidden_sequence') AND has_sequence_privilege('ambisgis_transport_reader',c.oid,'SELECT,USAGE,UPDATE');", 'ambisgis_transport') != '0':
                raise AssertionError('backfill reached another owner or schema')
            record['cases'].append({'name': 'existing_exact_owner_public_backfill_repeat_safe', 'passed': True})

            sequence_before = admin('SELECT last_value,is_called FROM hibernate_sequence;', 'ambisgis_transport')
            for name, role, statement, db in [
                ('application_ddl_denied', 'ambisgis_catalog_app', 'CREATE TABLE forbidden(id int);', 'ambisgis_catalog'),
                ('application_set_owner_denied', 'ambisgis_catalog_app', 'SET ROLE ambisgis_catalog_owner;', 'ambisgis_catalog'),
                ('transport_insert_denied', 'ambisgis_transport_reader', "INSERT INTO protected_rules(value) VALUES ('forbidden');", 'ambisgis_transport'),
                ('transport_sequence_denied', 'ambisgis_transport_reader', "SELECT nextval('protected_rules_id_seq');", 'ambisgis_transport'),
                ('transport_setval_denied', 'ambisgis_transport_reader', "SELECT setval('hibernate_sequence',42);", 'ambisgis_transport'),
                ('transport_nextval_denied', 'ambisgis_transport_reader', "SELECT nextval('hibernate_sequence');", 'ambisgis_transport'),
                ('transport_sequence_ddl_denied', 'ambisgis_transport_reader', 'ALTER SEQUENCE hibernate_sequence RESTART WITH 42;', 'ambisgis_transport'),
                ('transport_create_sequence_denied', 'ambisgis_transport_reader', 'CREATE SEQUENCE forbidden_sequence;', 'ambisgis_transport'),
                ('transport_set_owner_denied', 'ambisgis_transport_reader', 'SET ROLE ambisgis_transport_owner;', 'ambisgis_transport'),
            ]:
                as_role(role, statement, db, fail=True); record['cases'].append({'name': name, 'passed': True})
            if admin('SELECT last_value,is_called FROM hibernate_sequence;', 'ambisgis_transport') != sequence_before:
                raise AssertionError('denied reader operations changed sequence state')
            # PostgreSQL may warn instead of failing GRANT without grant option;
            # assert no delegated privilege, rather than relying on its exit code.
            as_role('ambisgis_transport_reader', 'GRANT SELECT ON SEQUENCE hibernate_sequence TO ambisgis_render_reader;', 'ambisgis_transport')
            if admin("SELECT has_sequence_privilege('ambisgis_render_reader','hibernate_sequence','SELECT,USAGE,UPDATE');", 'ambisgis_transport') != 'f':
                raise AssertionError('reader delegated sequence privilege')
            record['cases'].append({'name': 'transport_sequence_state_and_delegation_unchanged', 'passed': True})

            def state():
                parts = [admin("SELECT row_to_json(t) FROM (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls FROM pg_roles ORDER BY oid) t;"),
                         admin('SELECT row_to_json(t) FROM (SELECT * FROM pg_auth_members ORDER BY roleid,member) t;'),
                         admin('SELECT row_to_json(t) FROM (SELECT oid,datname,datdba,datacl FROM pg_database ORDER BY oid) t;')]
                for db in database.DATABASE_OWNERS:
                    for table, fields, order in [('pg_class','oid,relname,relnamespace,relowner,relacl','oid'),
                                                  ('pg_namespace','oid,nspname,nspowner,nspacl','oid'),
                                                  ('pg_proc','oid,proname,proowner,proacl,prosecdef,prosrc','oid'),
                                                  ('pg_attribute','attrelid,attnum,attacl','attrelid,attnum'),
                                                  ('pg_default_acl','*','oid')]:
                        parts.append(admin(f'SELECT row_to_json(t) FROM (SELECT {fields} FROM {table} ORDER BY {order}) t;', db))
                    parts.append(admin('TABLE ' + ('protected_rows' if db == 'ambisgis_catalog' else 'protected_rules') + ';', db))
                    if db == 'ambisgis_transport': parts.append(admin('SELECT last_value,is_called FROM hibernate_sequence;', db))
                return hashlib.sha256('\n'.join(parts).encode()).hexdigest()

            cases = [
                ('owner_membership', 'GRANT ambisgis_catalog_owner TO ambisgis_catalog_app;', 'REVOKE ambisgis_catalog_owner FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('predefined_role_membership', 'GRANT pg_write_server_files TO ambisgis_catalog_app;', 'REVOKE pg_write_server_files FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('serving_object_owner_revoked_acl', 'ALTER TABLE protected_rows OWNER TO ambisgis_catalog_app; REVOKE ALL ON protected_rows FROM ambisgis_catalog_app;', 'ALTER TABLE protected_rows OWNER TO ambisgis_catalog_owner; GRANT SELECT,INSERT,UPDATE,DELETE ON protected_rows TO ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('schema_create', 'GRANT CREATE ON SCHEMA public TO ambisgis_catalog_app;', 'REVOKE CREATE ON SCHEMA public FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('database_create', 'GRANT CREATE ON DATABASE ambisgis_catalog TO ambisgis_catalog_app;', 'REVOKE CREATE ON DATABASE ambisgis_catalog FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('table_truncate', 'GRANT TRUNCATE ON protected_rows TO ambisgis_catalog_app;', 'REVOKE TRUNCATE ON protected_rows FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('table_grant_option', 'GRANT SELECT ON protected_rows TO ambisgis_catalog_app WITH GRANT OPTION;', 'REVOKE GRANT OPTION FOR SELECT ON protected_rows FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('column_grant_option', 'GRANT SELECT(value) ON protected_rows TO ambisgis_catalog_app WITH GRANT OPTION;', 'REVOKE SELECT(value) ON protected_rows FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('unauthorized_column_read', 'GRANT SELECT(value) ON protected_rows TO ambisgis_render_reader;', 'REVOKE SELECT(value) ON protected_rows FROM ambisgis_render_reader;', 'ambisgis_catalog'),
                ('application_sequence_update', 'GRANT UPDATE ON protected_rows_id_seq TO ambisgis_catalog_app;', 'REVOKE UPDATE ON protected_rows_id_seq FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('transport_direct_write', 'GRANT UPDATE ON protected_rules TO ambisgis_transport_reader;', 'REVOKE UPDATE ON protected_rules FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('transport_column_write', 'GRANT UPDATE(value) ON protected_rules TO ambisgis_transport_reader;', 'REVOKE UPDATE(value) ON protected_rules FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('transport_public_write', 'GRANT DELETE ON protected_rules TO PUBLIC;', 'REVOKE DELETE ON protected_rules FROM PUBLIC;', 'ambisgis_transport'),
                ('transport_sequence_usage', 'GRANT USAGE ON protected_rules_id_seq TO ambisgis_transport_reader;', 'REVOKE USAGE ON protected_rules_id_seq FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('transport_sequence_update', 'GRANT UPDATE ON hibernate_sequence TO ambisgis_transport_reader;', 'REVOKE UPDATE ON hibernate_sequence FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('transport_sequence_grant_option', 'GRANT SELECT ON hibernate_sequence TO ambisgis_transport_reader WITH GRANT OPTION;', 'REVOKE GRANT OPTION FOR SELECT ON hibernate_sequence FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('transport_sequence_public_select', 'GRANT SELECT ON hibernate_sequence TO PUBLIC;', 'REVOKE SELECT ON hibernate_sequence FROM PUBLIC;', 'ambisgis_transport'),
                ('transport_sequence_cross_owner_select', 'GRANT SELECT ON foreign_owner_sequence TO ambisgis_transport_reader;', 'REVOKE SELECT ON foreign_owner_sequence FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('transport_sequence_cross_schema_select', 'GRANT SELECT ON private_fixture.hidden_sequence TO ambisgis_transport_reader;', 'REVOKE SELECT ON private_fixture.hidden_sequence FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('protected_function_execute', 'CREATE FUNCTION protected_function() RETURNS int LANGUAGE sql SECURITY DEFINER AS $$SELECT 1$$; REVOKE ALL ON FUNCTION protected_function() FROM PUBLIC; GRANT EXECUTE ON FUNCTION protected_function() TO ambisgis_catalog_app;', 'DROP FUNCTION protected_function();', 'ambisgis_catalog'),
                ('public_protected_function_execute', 'CREATE FUNCTION protected_function() RETURNS int LANGUAGE sql SECURITY DEFINER AS $$SELECT 1$$;', 'DROP FUNCTION protected_function();', 'ambisgis_catalog'),
                ('system_function_execute', 'GRANT EXECUTE ON FUNCTION pg_catalog.pg_read_file(text) TO ambisgis_catalog_app;', 'REVOKE EXECUTE ON FUNCTION pg_catalog.pg_read_file(text) FROM ambisgis_catalog_app;', 'ambisgis_catalog'),
                ('future_table_write', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public GRANT UPDATE ON TABLES TO ambisgis_transport_reader;', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public REVOKE UPDATE ON TABLES FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('future_sequence_usage', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public GRANT USAGE ON SEQUENCES TO ambisgis_transport_reader;', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public REVOKE USAGE ON SEQUENCES FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('future_sequence_update', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public GRANT UPDATE ON SEQUENCES TO ambisgis_transport_reader;', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public REVOKE UPDATE ON SEQUENCES FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('future_sequence_grant_option', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public GRANT SELECT ON SEQUENCES TO ambisgis_transport_reader WITH GRANT OPTION;', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public REVOKE GRANT OPTION FOR SELECT ON SEQUENCES FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('future_sequence_cross_schema', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA private_fixture GRANT SELECT ON SEQUENCES TO ambisgis_transport_reader;', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA private_fixture REVOKE SELECT ON SEQUENCES FROM ambisgis_transport_reader;', 'ambisgis_transport'),
                ('future_sequence_cross_owner', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_admin IN SCHEMA public GRANT SELECT ON SEQUENCES TO ambisgis_transport_reader;', 'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_admin IN SCHEMA public REVOKE SELECT ON SEQUENCES FROM ambisgis_transport_reader;', 'ambisgis_transport'),
            ]
            original_sql = database.sql
            for name, poison, repair, db in cases:
                admin(poison, db); before = state(); statements = []
                def observed_sql(statement, *a, **kw):
                    statements.append(statement.lstrip().split(None, 1)[0])
                    return original_sql(statement, *a, **kw)
                database.sql = observed_sql
                try:
                    try: database.bootstrap({}, material)
                    except ValueError: pass
                    else: raise AssertionError('unsafe existing state accepted: ' + name)
                    try: database.health()
                    except ValueError: pass
                    else: raise AssertionError('unsafe health accepted: ' + name)
                finally: database.sql = original_sql
                if any(word not in ('SELECT','WITH') for word in statements): raise AssertionError('mutation before rejection')
                after = state()
                if after != before: raise AssertionError('rejection changed database state')
                record['cases'].append({'name': name, 'passed': True, 'state_before_sha256': before,
                                        'state_after_sha256': after, 'queries_read_only': True,
                                        'fresh_health_rejected': True})
                admin(repair, db); database.validate_existing_privileges(material['database_admin'])
            record['status'] = 'passed'
    except Exception as error:
        record.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        cleanup_error = None
        if started or (pgdata / 'postmaster.pid').exists():
            try:
                run([prefix / 'bin/pg_ctl', '-D', pgdata, '-m', 'fast', '-w', 'stop'])
                record['cluster_stopped'] = True
            except RuntimeError as error:
                cleanup_error = error
                record.update(cluster_stopped=False, status='failed', cleanup_error=str(error))
        record['finished'] = datetime.now(timezone.utc).isoformat()
        (output / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        if cleanup_error: raise cleanup_error


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
