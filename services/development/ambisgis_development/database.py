"""Persistent owned PostgreSQL/PostGIS process and least-privilege bootstrap."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .common import DATA, inputs, read, save
from .startup_diagnostics import ChildFailure, StartupFailure

PREFIX = Path('/opt/ambisgis/postgres')
ROLES = {'ambisgis_catalog_owner': 'catalog_migrator', 'ambisgis_catalog_app': 'catalog_runtime',
         'ambisgis_render_reader': 'render_reader', 'ambisgis_transport_owner': 'transport_migrator',
         'ambisgis_transport_reader': 'transport_reader'}
SERVING_ROLES = ('ambisgis_catalog_app', 'ambisgis_render_reader', 'ambisgis_transport_reader')
DATABASE_OWNERS = {'ambisgis_catalog': 'ambisgis_catalog_owner', 'ambisgis_transport': 'ambisgis_transport_owner'}


def call(arguments, *, env=None, timeout=60, data=None):
    value = subprocess.run([str(x) for x in arguments], input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, env=env, timeout=timeout)
    if value.returncode:
        raise ChildFailure(value.returncode)
    return value.stdout.decode().strip()


def sql(statement, secret, *, database='postgres'):
    environment = dict(os.environ, PGPASSWORD=secret, PGCONNECT_TIMEOUT='4')
    return call([PREFIX / 'bin/psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
                 '-h', DATA / 'socket', '-U', 'ambisgis_admin', '-d', database],
                env=environment, data=statement.encode())


def validate_roles(password):
    # NOINHERIT alone does not prevent SET ROLE, including predefined powerful
    # roles. Refuse existing grants/ownership; never silently revoke operator data.
    for role in ROLES:
        invalid = sql("SELECT count(*) FROM pg_roles WHERE rolname='" + role + "' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit OR NOT rolcanlogin);", password)
        membership = sql("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='" + role + "');", password)
        if invalid != '0' or membership != '0':
            raise ValueError('existing database role has unsafe privileges or memberships')
        if role in SERVING_ROLES:
            owned = sql("SELECT count(*) FROM pg_shdepend WHERE refclassid='pg_authid'::regclass AND refobjid=(SELECT oid FROM pg_roles WHERE rolname='" + role + "') AND deptype='o';", password)
            if owned != '0':
                raise ValueError('serving database role owns objects')


def privilege_audit(database):
    """Finite serving policy, including PUBLIC/column grants and grant options.

    The catalog application gets ordinary table DML and sequence usage; the
    transport reader gets table/sequence SELECT. Sequence SELECT exposes schema
    metadata and values, without nextval/setval. Neither may create objects, delegate grants,
    execute application routines, or acquire privileges on the other's data.
    Owned PostGIS extension SELECT/EXECUTE defaults remain usable.
    """
    owner = DATABASE_OWNERS[database]
    reader = 'ambisgis_catalog_app' if database == 'ambisgis_catalog' else 'ambisgis_transport_reader'
    table_privileges = "('SELECT','INSERT','UPDATE','DELETE')" if database == 'ambisgis_catalog' else "('SELECT')"
    sequence_privileges = "('USAGE','SELECT')" if database == 'ambisgis_catalog' else "('SELECT')"
    names = ','.join("'" + name + "'" for name in SERVING_ROLES)
    return f"""WITH serving AS (SELECT oid,rolname FROM pg_roles WHERE rolname IN ({names})),
      objects AS (SELECT c.*,n.nspname,EXISTS(SELECT 1 FROM pg_depend d JOIN pg_extension e ON e.oid=d.refobjid
        WHERE d.classid='pg_class'::regclass AND d.objid=c.oid AND d.refclassid='pg_extension'::regclass
        AND d.deptype='e' AND e.extname='postgis') AS extension_member
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'),
      problems AS (
        SELECT 'database:'||r.rolname AS problem FROM serving r WHERE has_database_privilege(r.oid,current_database(),'CREATE,TEMPORARY,CONNECT WITH GRANT OPTION')
        UNION ALL SELECT 'schema:'||r.rolname||':'||n.nspname FROM serving r CROSS JOIN pg_namespace n
          WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema'
          AND has_schema_privilege(r.oid,n.oid,'CREATE,USAGE WITH GRANT OPTION')
        UNION ALL SELECT 'table:'||r.rolname||':'||c.relname||':'||p.priv FROM serving r CROSS JOIN objects c
          CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p(priv)
          WHERE c.relkind IN ('r','p','v','m','f') AND (
            has_table_privilege(r.oid,c.oid,p.priv||' WITH GRANT OPTION')
            OR (p.priv IN ('SELECT','INSERT','UPDATE','REFERENCES')
                AND has_any_column_privilege(r.oid,c.oid,p.priv||' WITH GRANT OPTION'))
            OR ((has_table_privilege(r.oid,c.oid,p.priv)
                 OR (p.priv IN ('SELECT','INSERT','UPDATE','REFERENCES') AND has_any_column_privilege(r.oid,c.oid,p.priv)))
              AND NOT ((r.rolname='{reader}' AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname='{owner}')
                         AND c.nspname='public' AND p.priv IN {table_privileges})
                       OR (c.extension_member AND p.priv='SELECT'))))
        UNION ALL SELECT 'sequence:'||r.rolname||':'||c.relname||':'||p.priv FROM serving r CROSS JOIN objects c
          CROSS JOIN unnest(ARRAY['USAGE','SELECT','UPDATE']) p(priv)
          WHERE c.relkind='S' AND (has_sequence_privilege(r.oid,c.oid,p.priv||' WITH GRANT OPTION')
            OR (has_sequence_privilege(r.oid,c.oid,p.priv) AND NOT (
                r.rolname='{reader}'
                AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname='{owner}')
                AND c.nspname='public' AND p.priv IN {sequence_privileges})))
        UNION ALL SELECT 'function:'||r.rolname||':'||n.nspname||'.'||p.proname FROM serving r CROSS JOIN pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE has_function_privilege(r.oid,p.oid,'EXECUTE') AND (
            p.prosecdef OR has_function_privilege(r.oid,p.oid,'EXECUTE WITH GRANT OPTION')
            OR EXISTS(SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee=r.oid)
            OR (n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND NOT EXISTS(
              SELECT 1 FROM pg_depend d JOIN pg_extension e ON e.oid=d.refobjid
              WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.refclassid='pg_extension'::regclass
              AND d.deptype='e' AND e.extname='postgis'))
            OR (n.nspname='pg_catalog' AND p.proname IN ('lo_import','lo_export',
                'pg_read_file','pg_read_binary_file','pg_ls_dir','pg_ls_logdir','pg_ls_waldir',
                'pg_ls_archive_statusdir','pg_ls_tmpdir')))
        UNION ALL SELECT 'default_acl:'||r.rolname||':'||a.privilege_type FROM serving r CROSS JOIN pg_default_acl d
          CROSS JOIN LATERAL aclexplode(d.defaclacl) a
          WHERE a.grantee IN (0,r.oid) AND (a.is_grantable OR NOT (
            a.grantee=r.oid AND r.rolname='{reader}'
            AND d.defaclrole=(SELECT oid FROM pg_roles WHERE rolname='{owner}')
            AND d.defaclnamespace=(SELECT oid FROM pg_namespace WHERE nspname='public')
            AND ((d.defaclobjtype='r' AND a.privilege_type IN {table_privileges})
              OR (d.defaclobjtype='S' AND a.privilege_type IN {sequence_privileges}))))
      ) SELECT count(*) FROM problems;"""


def validate_existing_privileges(password):
    validate_roles(password)
    for name, expected_owner in DATABASE_OWNERS.items():
        owner = sql("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='" + name + "';", password)
        if not owner:
            continue
        if owner != expected_owner:
            raise ValueError('installation database has a conflicting owner')
        if sql(privilege_audit(name), password, database=name) != '0':
            raise ValueError('serving database role has unexpected effective object privileges')


def bootstrap(config, secrets):
    password = secrets['database_admin']
    # Installation/catalog roles only. DB-01 owns all managed branch schemas.
    # Check already existing roles before any role/database/schema mutation.
    validate_existing_privileges(password)
    for role, key in ROLES.items():
        exists = sql("SELECT count(*) FROM pg_roles WHERE rolname='" + role + "';", password)
        if exists == '0':
            sql('CREATE ROLE ' + role + " LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '" + secrets[key] + "';", password)
    validate_roles(password)
    exists = sql("SELECT count(*) FROM pg_database WHERE datname='ambisgis_catalog';", password)
    if exists == '0':
        sql('CREATE DATABASE ambisgis_catalog OWNER ambisgis_catalog_owner;', password)
    owner = sql("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='ambisgis_catalog';", password)
    if owner != 'ambisgis_catalog_owner':
        raise ValueError('catalog database has a conflicting owner')
    sql("""CREATE EXTENSION IF NOT EXISTS postgis;
        REVOKE ALL ON DATABASE ambisgis_catalog FROM PUBLIC;
        GRANT CONNECT ON DATABASE ambisgis_catalog TO ambisgis_catalog_owner, ambisgis_catalog_app, ambisgis_render_reader;
        REVOKE CREATE ON SCHEMA public FROM PUBLIC;
        GRANT USAGE, CREATE ON SCHEMA public TO ambisgis_catalog_owner;
        GRANT USAGE ON SCHEMA public TO ambisgis_catalog_app;
        ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_catalog_owner IN SCHEMA public
          GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ambisgis_catalog_app;
        ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_catalog_owner IN SCHEMA public
          GRANT USAGE, SELECT ON SEQUENCES TO ambisgis_catalog_app;
        """, password, database='ambisgis_catalog')
    actual = sql("SELECT extversion FROM pg_extension WHERE extname='postgis';", password, database='ambisgis_catalog')
    if actual != '3.5.7':
        raise ValueError('unexpected owned PostGIS extension version')
    exists = sql("SELECT count(*) FROM pg_database WHERE datname='ambisgis_transport';", password)
    if exists == '0':
        sql('CREATE DATABASE ambisgis_transport OWNER ambisgis_transport_owner;', password)
    if sql("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='ambisgis_transport';", password) != 'ambisgis_transport_owner':
        raise ValueError('transport database has a conflicting owner')
    sql("""CREATE EXTENSION IF NOT EXISTS postgis;
        REVOKE ALL ON DATABASE ambisgis_transport FROM PUBLIC;
        GRANT CONNECT ON DATABASE ambisgis_transport TO ambisgis_transport_owner, ambisgis_transport_reader;
        REVOKE CREATE ON SCHEMA public FROM PUBLIC;
        GRANT USAGE, CREATE ON SCHEMA public TO ambisgis_transport_owner;
        GRANT USAGE ON SCHEMA public TO ambisgis_transport_reader;
        ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public
          GRANT SELECT ON TABLES TO ambisgis_transport_reader;
        ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public
          GRANT SELECT ON SEQUENCES TO ambisgis_transport_reader;
        DO $transport_sequences$
        DECLARE target record;
        BEGIN
          FOR target IN SELECT n.nspname,c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind='S' AND n.nspname='public'
              AND c.relowner='ambisgis_transport_owner'::regrole
          LOOP
            EXECUTE format('GRANT SELECT ON SEQUENCE %I.%I TO ambisgis_transport_reader',
                           target.nspname,target.relname);
          END LOOP;
        END; $transport_sequences$;
        """, password, database='ambisgis_transport')
    validate_existing_privileges(password)


def main():
    stage = 'input'
    try:
        config, secrets = inputs()
        stage = 'identity'
        marker = DATA / 'installation.json'
        identity = {'schema_version': 1, 'install_id': config['install_id'], 'purpose': 'developer-database'}
        if marker.exists():
            if read(marker) != identity:
                raise ValueError('database directory belongs to a different installation')
        else:
            if any(DATA.iterdir()):
                raise ValueError('will not adopt an unmarked database directory')
            save(marker, identity)
        stage = 'storage'
        pgdata, socket = DATA / 'pgdata', DATA / 'socket'
        if pgdata.is_symlink() or socket.is_symlink():
            raise ValueError('database storage cannot redirect outside its volume')
        socket.mkdir(mode=0o700, exist_ok=True)
        if not (pgdata / 'PG_VERSION').exists():
            stage = 'password'
            pwfile = Path('/tmp/initial-database-password')
            descriptor = os.open(pwfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            primary = None
            try:
                with os.fdopen(descriptor, 'w') as output:
                    output.write(secrets['database_admin'])
                stage = 'initdb'
                call([PREFIX / 'bin/initdb', '-D', pgdata, '--username=ambisgis_admin', '--auth-local=scram-sha-256',
                      '--auth-host=scram-sha-256', '--encoding=UTF8', '--locale=C.UTF-8', '--pwfile=' + str(pwfile)])
            except Exception as error:
                primary = StartupFailure(stage, error)
                raise primary from None
            finally:
                try:
                    pwfile.unlink()
                except Exception as error:
                    raise StartupFailure('password_cleanup', primary if primary is not None else error,
                                         cleanup_failed=True) from None
        stage = 'storage'
        # Only the catalog roles are reachable over the private container network.
        # The superuser stays on the database container's owner-only Unix socket.
        hba = ('local all ambisgis_admin scram-sha-256\n'
               'host ambisgis_catalog ambisgis_catalog_owner,ambisgis_catalog_app,ambisgis_render_reader 0.0.0.0/0 scram-sha-256\n'
               'host ambisgis_transport ambisgis_transport_owner,ambisgis_transport_reader 0.0.0.0/0 scram-sha-256\n'
               'host all all 0.0.0.0/0 reject\n'
               'host all all ::/0 reject\n')
        target = pgdata / 'pg_hba.conf'
        if target.is_symlink():
            raise ValueError('database authentication configuration cannot be a symlink')
        target.write_text(hba)
        target.chmod(0o600)
        stage = 'server'
        process = subprocess.Popen([str(PREFIX / 'bin/postgres'), '-D', str(pgdata), '-p', '5432',
                                    '-c', 'listen_addresses=*', '-c', 'unix_socket_directories=' + str(socket),
                                    '-c', 'log_statement=none', '-c', 'log_min_error_statement=panic'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def stop(signum, frame):
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
        try:
            stage = 'readiness'
            deadline = time.monotonic() + 60
            while True:
                try:
                    if sql('SELECT 1;', secrets['database_admin']) == '1':
                        break
                except (RuntimeError, subprocess.TimeoutExpired):
                    pass
                returncode = process.poll()
                if returncode is not None:
                    raise ChildFailure(returncode)
                if time.monotonic() >= deadline:
                    raise TimeoutError('database did not become available')
                time.sleep(0.5)
            stage = 'bootstrap'
            bootstrap(config, secrets)
            print(json.dumps({'event': 'database_ready', 'install_id': config['install_id']}), flush=True)
            stage = 'server'
            raise SystemExit(process.wait())
        finally:
            stop(None, None)
            process.wait(timeout=40)
    except Exception as error:
        raise StartupFailure(stage, error) from None


def health():
    _, secrets = inputs()
    validate_existing_privileges(secrets['database_admin'])
    return sql("SELECT ST_SRID(ST_SetSRID(ST_MakePoint(1,2),4326)) = 4326 AND ST_DWithin(ST_MakePoint(1,2),ST_MakePoint(1,2),0);",
               secrets['database_admin'], database='ambisgis_catalog') == 't'
