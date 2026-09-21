#!/usr/bin/env python3
"""Fresh owned PostgreSQL/PostGIS TCP fixture for the real configured application.

The retained loopback supervisor rejects PostgreSQL backend setsid(). The caller
must retain that observed failure before electing to run this database outside
that supervisor. The application and identity HTTP clients stay supervised.
This helper does not change any sandbox, host service or retained engine binary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import time


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def verify_prefix(prefix, historical):
    """Reuse geofence_fixture's retained artifact identity contract, fail closed."""
    prefix, historical = Path(prefix).resolve(), Path(historical).resolve()
    reference = json.loads(historical.read_text())
    required = {prefix / 'bin' / n for n in ('postgres', 'initdb', 'pg_ctl', 'psql', 'pg_config')}
    verified = []
    for item in reference['runtime']['artifacts']:
        ident = item['identity']
        relative = ident['path'].split('/prefix/', 1)
        if len(relative) != 2:
            continue
        path = prefix / relative[1]
        if not path.resolve().is_relative_to(prefix) or not path.is_file() or sha(path) != ident['sha256']:
            raise ValueError('retained database artifact mismatch: ' + str(path))
        verified.append({'path': str(path), 'sha256': ident['sha256']})
        required.discard(path)
    if required:
        raise ValueError('retained snapshot omits required PostgreSQL tools')
    return {'historical_snapshot': str(historical), 'historical_sha256': sha(historical),
            'verified_artifacts': verified, 'verification_contract': 'geofence_fixture.py retained runtime artifacts',
            'verification_reference_sha256': sha(Path(__file__).with_name('geofence_fixture.py'))}


class Database:
    def __init__(self, prefix, historical, output):
        self.prefix = Path(prefix).resolve()
        self.output = Path(output).absolute()
        self.receipt = verify_prefix(self.prefix, historical)
        if self.output.exists() or self.output.is_symlink():
            raise FileExistsError('database fixture output must be new')
        self.output.mkdir(parents=True, mode=0o700)
        self.output.chmod(0o700)
        self.data = self.output / 'data'
        self.nonce = secrets.token_hex(24)
        self.password = secrets.token_urlsafe(48)
        self.owner_password = secrets.token_urlsafe(48)
        self.process = None
        self.log_stream = None
        self.configured_files = []
        self.secret_values = [self.password, self.owner_password]
        self.env = {'PATH': str(self.prefix / 'bin') + ':' + os.defpath,
                    'HOME': str(self.output / 'home'), 'LC_ALL': 'C',
                    'LD_LIBRARY_PATH': str(self.prefix / 'lib') + ':' + str(self.prefix / 'lib64'),
                    'PROJ_DATA': str(self.prefix / 'share/proj'), 'PROJ_NETWORK': 'OFF',
                    'GDAL_DATA': str(self.prefix / 'share/gdal')}
        (self.output / 'home').mkdir(mode=0o700)
        self.receipt.update(result_exit_code=1, started=False, stopped=False, commands=[],
                            scope='disposable real GeoFence database; no native branch or full database acceptance',
                            output=str(self.output), data_directory=str(self.data),
                            recipe_sha256=sha(__file__), transport='127.0.0.1 TCP, SCRAM; Unix listeners disabled')
        self.persist()

    def persist(self):
        save(self.output / 'database-result.json', self.receipt)

    def run(self, name, arguments, *, sql=None, database='postgres', timeout=60):
        env = self.env.copy()
        if hasattr(self, 'port'):
            env.update(PGHOST='127.0.0.1', PGPORT=str(self.port), PGUSER='fixture_owner',
                       PGDATABASE=database, PGPASSWORD=self.owner_password)
        completed = subprocess.run([str(p) for p in arguments], cwd=self.output, env=env,
                                   input=sql, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=timeout)
        text = completed.stdout
        for value in self.secret_values:
            text = text.replace(value, '[REDACTED_FIXTURE_VALUE]')
        path = self.output / (name + '.log')
        if path.exists():
            raise FileExistsError('database command evidence must be fresh')
        path.write_text(text)
        self.receipt['commands'].append({'name': name, 'argv': [str(p) for p in arguments],
                                         'exit_code': completed.returncode, 'log_sha256': sha(path),
                                         'sql_sha256': hashlib.sha256(sql.encode()).hexdigest() if sql else None})
        self.persist()
        if completed.returncode:
            raise RuntimeError('database command failed: ' + name + '; retained sanitized log: ' + str(path))
        return text

    def sql(self, name, sql, database='postgres'):
        return self.run(name, [self.prefix / 'bin/psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1', '-A', '-t'],
                        sql=sql, database=database)

    def start(self):
        pwfile = self.output / 'init-password'
        pwfile.write_text(self.owner_password)
        pwfile.chmod(0o600)
        try:
            version = self.run('pg-version', [self.prefix / 'bin/pg_config', '--version']).strip()
            if version != 'PostgreSQL 15.19':
                raise ValueError('unexpected retained PostgreSQL version')
            self.run('initdb', [self.prefix / 'bin/initdb', '-D', self.data, '-U', 'fixture_owner',
                               '--encoding=UTF8', '--no-locale', '--auth-local=reject',
                               '--auth-host=scram-sha-256', '--pwfile', pwfile])
        finally:
            if pwfile.exists():
                pwfile.write_text('REDACTED-DISPOSABLE-CREDENTIAL\n')
        (self.data / '.ambisgis-configured-db-owner').write_text(self.nonce)
        (self.data / 'pg_hba.conf').write_text(
            'local all all reject\n'
            'host all fixture_owner 127.0.0.1/32 scram-sha-256\n'
            'host fixture_geofence fixture_geofence 127.0.0.1/32 scram-sha-256\n'
            'host all all 0.0.0.0/0 reject\n'
            'host all all ::0/0 reject\n')
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(('127.0.0.1', 0))
            self.port = reservation.getsockname()[1]
        command = [str(self.prefix / 'bin/postgres'), '-D', str(self.data), '-h', '127.0.0.1',
                   '-p', str(self.port), '-k', '', '-c', 'ssl=off', '-c', 'logging_collector=off',
                   '-c', 'log_statement=none', '-c', 'max_connections=20']
        self.log_stream = (self.output / 'postgres.log').open('x')
        self.process = subprocess.Popen(command, cwd=self.output, env=self.env,
                                        stdin=subprocess.DEVNULL, stdout=self.log_stream,
                                        stderr=subprocess.STDOUT)
        self.receipt.update(start_command=command, process_id=self.process.pid, port=self.port)
        self.persist()
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('owned PostgreSQL exited before readiness; see postgres.log')
            text = (self.output / 'postgres.log').read_text(errors='replace')
            if 'setsid() failed' in text:
                raise RuntimeError('retained loopback supervisor denies required PostgreSQL backend setsid(); see postgres.log')
            if 'database system is ready to accept connections' in text:
                break
            time.sleep(.15)
        else:
            raise RuntimeError('owned PostgreSQL did not become ready in 35 seconds')
        identity = json.loads(self.sql('identity', "SELECT json_build_object('version_num',current_setting('server_version_num'),'data_directory',current_setting('data_directory'),'listen_addresses',current_setting('listen_addresses'),'unix_socket_directories',current_setting('unix_socket_directories'),'server_port',inet_server_port());\n").strip())
        if (identity['version_num'] != '150019' or Path(identity['data_directory']).resolve() != self.data.resolve()
                or identity['listen_addresses'] != '127.0.0.1' or identity['unix_socket_directories'] != ''
                or identity['server_port'] != self.port):
            raise ValueError('running database identity/listener mismatch')
        self.receipt['server_identity'] = identity
        self.sql('role', "CREATE ROLE fixture_geofence LOGIN PASSWORD '" + self.password + "';\n")
        self.sql('database', 'CREATE DATABASE fixture_geofence OWNER fixture_geofence;\n')
        self.sql('postgis', "CREATE EXTENSION postgis VERSION '3.5.7';\n", 'fixture_geofence')
        version = self.sql('postgis-version', 'SELECT postgis_lib_version();\n', 'fixture_geofence').strip()
        if version != '3.5.7':
            raise ValueError('running PostGIS version mismatch')
        self.properties_path = self.output / 'datasource.properties'
        self._write_properties(self.properties_path)
        self.receipt.update(started=True, postgis_version=version, result_exit_code=0,
                            datasource_template={'path': str(self.properties_path), 'sha256': sha(self.properties_path)})
        self.persist()
        return self

    def _write_properties(self, path):
        path.write_text(
            'geofenceConfigurationManager.configuration.servicesUrl=internal:/\n'
            'geofenceEntityManagerFactory.jpaPropertyMap[hibernate.hbm2ddl.auto]=update\n'
            'geofenceVendorAdapter.databasePlatform=org.hibernate.spatial.dialect.postgis.PostgisDialect\n'
            'geofenceDataSource.driverClassName=org.postgresql.Driver\n'
            'geofenceDataSource.url=jdbc:postgresql://127.0.0.1:' + str(self.port) + '/fixture_geofence?sslmode=disable&gssEncMode=disable\n'
            'geofenceDataSource.username=fixture_geofence\n'
            'geofenceDataSource.password=' + self.password + '\n')
        path.chmod(0o600)
        self.configured_files.append(path)

    def configure(self, fixture):
        fixture = Path(fixture)
        marker = fixture / '.ambisgis-configured-auth-fixture'
        if fixture.is_symlink() or not marker.is_file() or marker.is_symlink():
            raise ValueError('refuse unmarked application fixture')
        path = fixture / 'geofence/geofence-datasource-ovr.properties'
        if path.is_symlink():
            raise ValueError('refuse linked datasource configuration')
        self._write_properties(path)
        record = {'path': str(path), 'sha256_before_secret_redaction': sha(path)}
        self.receipt.setdefault('datasource_files', []).append(record)
        self.persist()
        return record

    def stop(self):
        try:
            if self.process is not None and self.process.poll() is None:
                marker = self.data / '.ambisgis-configured-db-owner'
                if not marker.is_file() or marker.read_text() != self.nonce:
                    raise ValueError('refuse to stop unowned database')
                self.process.send_signal(signal.SIGINT)  # PostgreSQL fast shutdown, directly owned Popen PID only.
                try:
                    self.process.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    self.process.send_signal(signal.SIGQUIT)
                    self.process.wait(timeout=10)
                    self.receipt['forced_immediate_shutdown'] = True
                    self.receipt['result_exit_code'] = 1
            if self.process is not None:
                self.receipt['postgres_exit_code'] = self.process.returncode
                if (self.data / 'postmaster.pid').exists():
                    raise RuntimeError('owned database PID file persists after shutdown')
            self.receipt['stopped'] = True
        finally:
            if self.log_stream is not None:
                self.log_stream.close()
            for path in [self.output / 'postgres.log', *self.configured_files]:
                if path.is_file() and not path.is_symlink():
                    raw = path.read_text(errors='replace')
                    for value in self.secret_values:
                        raw = raw.replace(value, '[REDACTED_FIXTURE_VALUE]')
                    path.write_text(raw)
            self.persist()


def start(prefix, historical, output):
    database = Database(prefix, historical, output)
    try:
        return database.start()
    except BaseException as error:
        database.receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
        database.receipt['result_exit_code'] = 1
        database.stop()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prefix', 'historical', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    db = start(args.prefix, args.historical, args.output)
    try:
        db.sql('witness', 'SELECT ST_AsText(ST_SetSRID(ST_MakePoint(1,2),4326));\n', 'fixture_geofence')
    finally:
        db.stop()
    print(json.dumps({'result_exit_code': db.receipt['result_exit_code'], 'stopped': db.receipt['stopped'], 'output': str(db.output)}))
