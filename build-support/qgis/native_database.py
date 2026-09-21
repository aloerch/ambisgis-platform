#!/usr/bin/env python3
"""Own a fresh native-test database and supervise the frozen QGIS test runner."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'java'))
import configured_auth_database
import loopback_exec
import native_tests


def fixture_sql(source, selection):
    """Take unchanged, hash-verified fixture statements, not the full pg suite."""
    record = selection['database_fixture']
    path = Path(source) / record['source']
    if native_tests.sha(path) != selection['source_sha256'][record['source']]:
        raise ValueError('native PostgreSQL fixture source mismatch')
    text = path.read_text()
    start, end = record['start_marker'], record['end_marker']
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('native PostgreSQL fixture marker ambiguity')
    fragment = text.split(start, 1)[1].split(end, 1)[0]
    # Verify that this exact source excerpt supplies only the intended tables.
    if fragment.count('CREATE TABLE ') != 2 or 'CREATE EXTENSION' in fragment:
        raise ValueError('native fixture selection changed')
    return start + fragment


def prepare(database, source, service_file):
    selection = native_tests.load_selection(source)
    sql = fixture_sql(source, selection)
    password = secrets.token_urlsafe(48)
    database.secret_values.append(password)
    database.sql('native-create-role', "CREATE ROLE qgis_test_group NOLOGIN;\n"
                 "CREATE ROLE qgis_native_reader LOGIN PASSWORD '" + password + "';\n")
    database.sql('native-create-database', 'CREATE DATABASE qgis_native;\n')
    database.sql('native-postgis', "CREATE EXTENSION postgis VERSION '3.5.7';\n", 'qgis_native')
    database.sql('native-fixture', sql, 'qgis_native')
    database.sql('native-grants', 'GRANT USAGE ON SCHEMA qgis_test TO qgis_native_reader;\n'
                 'GRANT SELECT ON ALL TABLES IN SCHEMA qgis_test TO qgis_native_reader;\n'
                 'GRANT USAGE ON ALL SEQUENCES IN SCHEMA qgis_test TO qgis_native_reader;\n', 'qgis_native')
    hba = database.data / 'pg_hba.conf'
    text = hba.read_text()
    reject = 'host all all 0.0.0.0/0 reject\n'
    if text.count(reject) != 1:
        raise ValueError('native owned database HBA does not match helper contract')
    hba.write_text(text.replace(reject,
        'host qgis_native qgis_native_reader 127.0.0.1/32 scram-sha-256\n' + reject))
    database.sql('native-reload', 'SELECT pg_reload_conf();\n')
    service_file = Path(service_file)
    with service_file.open('x') as stream:
        stream.write('[qgis_test]\nhost=127.0.0.1\nport=' + str(database.port) +
                     '\ndbname=qgis_native\nuser=qgis_native_reader\npassword=' + password +
                     '\nsslmode=disable\nconnect_timeout=5\n')
    service_file.chmod(0o600)
    database.configured_files.append(service_file)
    return {'sql_source': selection['database_fixture']['source'],
            'sql_source_sha256': selection['source_sha256'][selection['database_fixture']['source']],
            'sql_excerpt_sha256': hashlib.sha256(sql.encode()).hexdigest(),
            'database': 'qgis_native', 'runtime_role': 'qgis_native_reader',
            'runtime_permissions': 'SELECT tables, USAGE schema and sequences; default-value test advances fixture sequence',
            'full_donor_bootstrap_executed': False}


def run(config, output):
    output = Path(output).absolute()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    result = {'result_exit_code': 1,
              'database_control_limitation': 'Fresh PostgreSQL runs outside the retained loopback supervisor because native backend setsid is denied; authenticated loopback TCP only, Unix listeners disabled, owned PID shutdown. QGIS native clients stay supervised.',
              'scope': 'F02-04 selected native tests; no full provider suite or release acceptance'}
    database = None
    recipes = [Path(__file__).resolve(), Path(native_tests.__file__).resolve(), native_tests.SELECTION,
               Path(loopback_exec.__file__).resolve(), Path(configured_auth_database.__file__).resolve()]
    result['recipe_sha256'] = {str(path): native_tests.sha(path) for path in recipes}
    try:
        native_tests.load_selection(config['qgis_source'])
        database = configured_auth_database.start(config['database_prefix'], config['database_evidence'], output / 'database')
        database.receipt['scope'] = 'fresh QGIS native fixture cluster; helper-created fixture_geofence is unused'
        service = output / 'pg_service.conf'
        result['fixture'] = prepare(database, config['qgis_source'], service)
        child_config = dict(config, pg_service_file=str(service))
        invocation = output / 'invocation.json'
        native_tests.save(invocation, child_config)
        network = output / 'network-loopback.json'
        command = [sys.executable, str(Path(loopback_exec.__file__).resolve()), '--evidence', str(network),
                   '--timeout', '2400', '--', sys.executable, str(Path(native_tests.__file__).resolve()),
                   '--config', str(invocation), '--output', str(output / 'native')]
        with (output / 'supervisor.log').open('x') as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=2450)
        result['command'] = command
        result['process_exit_code'] = completed.returncode
        result['network'] = loopback_exec.verify_receipt(network, completed.returncode)
        result['native'] = json.loads((output / 'native/native-result.json').read_text())
        result['result_exit_code'] = 0 if completed.returncode == 0 and result['native']['result_exit_code'] == 0 else 1
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        if database is not None:
            try:
                if database.receipt.get('started'):
                    # Invalidates all login secrets before stopping this fresh cluster.
                    database.sql('native-invalidate-roles', "DO $$ DECLARE role_name text; BEGIN "
                                 "FOR role_name IN SELECT rolname FROM pg_roles WHERE rolcanlogin LOOP "
                                 "EXECUTE format('ALTER ROLE %I NOLOGIN PASSWORD NULL', role_name); "
                                 "END LOOP; END $$;\n")
                    result['credentials_invalidated'] = True
            except Exception as error:
                result['result_exit_code'] = 1
                result['credential_cleanup_error'] = type(error).__name__
            try:
                database.stop()
                result['database'] = database.receipt
                if not database.receipt.get('stopped') or database.receipt.get('result_exit_code') != 0:
                    result['result_exit_code'] = 1
            except Exception as error:
                result['result_exit_code'] = 1
                result['database_cleanup_error'] = type(error).__name__
    if any(native_tests.sha(path) != result['recipe_sha256'][str(path)] for path in recipes):
        result['result_exit_code'] = 1
        result['recipe_integrity_error'] = 'native runner or dependency changed during execution'
    native_tests.save(output / 'result.json', result)
    print(json.dumps({'result_exit_code': result['result_exit_code'], 'output': str(output), 'error': result.get('error')}))
    return result['result_exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.exit(run(json.loads(args.config.read_text()), args.output))
