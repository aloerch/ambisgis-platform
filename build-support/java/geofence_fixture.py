"""Disposable, owned PostgreSQL/PostGIS fixture for selected GeoFence tests."""
import argparse
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote
from resolution import sha, write_json


def start(prefix, historical, output, source):
    reference = json.loads(historical.read_text())
    artifacts = reference['runtime']['artifacts']
    required = {prefix / 'bin' / name for name in ('postgres', 'initdb', 'pg_ctl', 'psql', 'pg_config')}
    verified = []
    for item in artifacts:
        ident = item['identity']
        relative = ident['path'].split('/prefix/', 1)
        if len(relative) != 2:
            continue
        path = prefix / relative[1]
        if sha(path) != ident['sha256']:
            raise ValueError('retained database artifact changed: ' + str(path))
        verified.append({'path': str(path), 'sha256': ident['sha256']})
        required.discard(path)
    if required:
        raise ValueError('historical snapshot omitted required PostgreSQL tools')
    helper = Path(__file__).resolve().parents[1] / 'postgis/validate_database.py'
    spec = importlib.util.spec_from_file_location('geofence_owned_db_helper', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    probe = module.Probe(argparse.Namespace(prefix=prefix, work_root=output / 'database',
                                            phase='geofence', upgrade_state=None, timeout=60))
    try:
        probe.preflight()
        probe.start()
        probe.sql('fixture-role', 'CREATE ROLE geofence_test LOGIN;\n')
        probe.sql('fixture-database', 'CREATE DATABASE geofence_test OWNER geofence_test;\n')
        probe.sql('fixture-postgis', "CREATE EXTENSION postgis VERSION '3.5.7';\n", 'geofence_test')
        version = probe.sql('fixture-version', 'SELECT postgis_lib_version();\n', 'geofence_test').strip()
        if version != '3.5.7':
            raise ValueError('PostGIS version mismatch')
        gf = source / 'geofence-132a1d16901b7039f974c8c30d7e7df042d8af4c/src/services/core'
        java = gf / 'persistence/src/test/java/org/ambisgis/probe/UnixSocketFactory.java'
        java.parent.mkdir(parents=True)
        java.write_bytes(Path(__file__).with_name('fixtures').joinpath('UnixSocketFactory.java').read_bytes())
        properties = gf / 'persistence-pg-test/src/test/resources/geofence-datasource-ovr.properties'
        before = sha(properties)
        original = properties.read_text()
        old = 'jdbc:postgresql://localhost:5432/geofence_test'
        if original.count(old) != 1:
            raise ValueError('unexpected original PostgreSQL test fixture')
        url = ('jdbc:postgresql://localhost/geofence_test?sslmode=disable&gssEncMode=disable'
               '&socketFactory=org.ambisgis.probe.UnixSocketFactory&socketFactoryArg=' +
               quote(str(probe.socket_dir / '.s.PGSQL.5432'), safe=''))
        properties.write_text(original.replace(old, url))
        receipt = {'historical_snapshot': str(historical), 'historical_sha256': sha(historical),
                   'verified_artifacts': verified, 'helper_sha256': sha(helper),
                   'transport': 'JDK17 AF_UNIX SocketFactory; no TCP fallback; parent timeout only',
                   'adapter_sha256': sha(java), 'properties_before_sha256': before,
                   'properties_after_sha256': sha(properties), 'database_report': str(probe.log_dir / 'report.json'),
                   'database_version': version, 'server_identity': probe.report['server_identity']}
        write_json(output / 'postgres-fixture.json', receipt)
        return probe, receipt
    except BaseException:
        probe.stop()
        raise
