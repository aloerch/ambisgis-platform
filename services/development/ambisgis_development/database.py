"""Persistent owned PostgreSQL/PostGIS process and least-privilege bootstrap."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .common import DATA, inputs, read, save

PREFIX = Path('/opt/ambisgis/postgres')


def call(arguments, *, env=None, timeout=60, data=None):
    value = subprocess.run([str(x) for x in arguments], input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, env=env, timeout=timeout)
    if value.returncode:
        raise RuntimeError('owned database command failed')
    return value.stdout.decode().strip()


def sql(statement, secret, *, database='postgres'):
    environment = dict(os.environ, PGPASSWORD=secret, PGCONNECT_TIMEOUT='4')
    return call([PREFIX / 'bin/psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
                 '-h', DATA / 'socket', '-U', 'ambisgis_admin', '-d', database],
                env=environment, data=statement.encode())


def bootstrap(config, secrets):
    password = secrets['database_admin']
    # Installation/catalog roles only. DB-01 owns all managed branch schemas.
    roles = {'ambisgis_catalog_owner': 'catalog_migrator', 'ambisgis_catalog_app': 'catalog_runtime',
             'ambisgis_render_reader': 'render_reader', 'ambisgis_transport_owner': 'transport_migrator',
             'ambisgis_transport_reader': 'transport_reader'}
    for role, key in roles.items():
        exists = sql("SELECT count(*) FROM pg_roles WHERE rolname='" + role + "';", password)
        if exists == '0':
            sql('CREATE ROLE ' + role + " LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '" + secrets[key] + "';", password)
        invalid = sql("SELECT count(*) FROM pg_roles WHERE rolname='" + role + "' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls);", password)
        if invalid != '0':
            raise ValueError('existing database role has unsafe privileges')
    exists = sql("SELECT count(*) FROM pg_database WHERE datname='ambisgis_catalog';", password)
    if exists == '0':
        sql('CREATE DATABASE ambisgis_catalog OWNER ambisgis_catalog_owner;', password)
    owner = sql("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='ambisgis_catalog';", password)
    if owner != 'ambisgis_catalog_owner':
        raise ValueError('catalog database has a conflicting owner')
    sql("""CREATE EXTENSION IF NOT EXISTS postgis;
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
        """, password, database='ambisgis_transport')


def main():
    config, secrets = inputs()
    marker = DATA / 'installation.json'
    identity = {'schema_version': 1, 'install_id': config['install_id'], 'purpose': 'developer-database'}
    if marker.exists():
        if read(marker) != identity:
            raise ValueError('database directory belongs to a different installation')
    else:
        if any(DATA.iterdir()):
            raise ValueError('will not adopt an unmarked database directory')
        save(marker, identity)
    pgdata, socket = DATA / 'pgdata', DATA / 'socket'
    if pgdata.is_symlink() or socket.is_symlink():
        raise ValueError('database storage cannot redirect outside its volume')
    socket.mkdir(mode=0o700, exist_ok=True)
    if not (pgdata / 'PG_VERSION').exists():
        pwfile = Path('/tmp/initial-database-password')
        descriptor = os.open(pwfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            output.write(secrets['database_admin'])
        try:
            call([PREFIX / 'bin/initdb', '-D', pgdata, '--username=ambisgis_admin', '--auth-local=scram-sha-256',
                  '--auth-host=scram-sha-256', '--encoding=UTF8', '--locale=C.UTF-8', '--pwfile=' + str(pwfile)])
        finally:
            pwfile.unlink()
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
    process = subprocess.Popen([str(PREFIX / 'bin/postgres'), '-D', str(pgdata), '-p', '5432',
                                '-c', 'listen_addresses=*', '-c', 'unix_socket_directories=' + str(socket),
                                '-c', 'log_statement=none', '-c', 'log_min_error_statement=panic'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def stop(signum, frame):
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                if sql('SELECT 1;', secrets['database_admin']) == '1':
                    break
            except (RuntimeError, subprocess.TimeoutExpired):
                pass
            if process.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('database did not become available')
            time.sleep(0.5)
        bootstrap(config, secrets)
        print(json.dumps({'event': 'database_ready', 'install_id': config['install_id']}), flush=True)
        raise SystemExit(process.wait())
    finally:
        stop(None, None)
        process.wait(timeout=40)


def health():
    _, secrets = inputs()
    return sql("SELECT ST_SRID(ST_SetSRID(ST_MakePoint(1,2),4326)) = 4326 AND ST_DWithin(ST_MakePoint(1,2),ST_MakePoint(1,2),0);",
               secrets['database_admin'], database='ambisgis_catalog') == 't'
