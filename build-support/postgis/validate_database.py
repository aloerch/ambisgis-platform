#!/usr/bin/env python3
"""Owned PostgreSQL/PostGIS probe with retained logs and disposable own clusters.

prepare-upgrade: run while 3.5.6 is installed, retain fixture and stop cluster.
finish-upgrade: after installing 3.5.7 in the SAME prefix, actually update the
retained database, assert old data survived, and smoke-test a fresh database.
smoke: fresh installation checks; explicitly reports the missing upgrade test.
No cluster is deleted and no existing database service is contacted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid

POSTGRES_VERSION = '15.19'
OLD_POSTGIS = '3.5.6'
TARGET_POSTGIS = '3.5.7'
EXTENSIONS = ('postgis', 'postgis_raster', 'postgis_topology')
TRACKED_ENV = ('PATH', 'LD_LIBRARY_PATH', 'PROJ_DATA', 'PROJ_LIB', 'PROJ_NETWORK',
               'PROJ_USER_WRITABLE_DIRECTORY', 'GDAL_DATA', 'HOME', 'PGHOST', 'PGPORT', 'PGUSER', 'PGDATABASE', 'LC_ALL')


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def contained(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    require(resolved.is_relative_to(root.resolve()) and resolved != root.resolve(),
            f'Path must be inside {root}: {path}')
    return resolved


def extension_libraries(directory: Path) -> list[Path]:
    paths = [directory/name for name in
             ('postgis-3.so', 'postgis_raster-3.so', 'postgis_topology-3.so')]
    for path in paths:
        require(path.is_file(), f'Required candidate extension library is missing: {path}')
    return paths


def require_owned_linkage(linked: str, prefix: Path) -> None:
    require('not found' not in linked, 'Unresolved shared library')
    for line in linked.splitlines():
        fields = line.split()
        if not fields:
            continue
        name = Path(fields[0]).name
        if re.match(r'lib(?:geos(?:_c)?|proj|gdal|json-c|protobuf-c|xml2|sqlite3|z|png(?:16)?|jpeg|tiff|curl)[.-]', name):
            # Absolute DT_NEEDED entries have no `name =>` prefix in ldd.
            match = re.search(r'=>\s+(/\S+)|^\s*(/\S+)\s+\(', line)
            require(match is not None, f'Cannot establish owned dependency path: {line}')
            contained(Path(match[1] or match[2]), prefix)


def require_postgis_versions(actual: dict, version: str) -> None:
    # These native APIs return the version plus optional build revision, unlike
    # postgis_lib_version(). Archive builds report revision 0; source identity
    # is established independently by retained archive/commit and binary hashes.
    require(actual['postgis'] == version, f'Wrong PostGIS runtime: {actual}')
    for key in ('raster', 'scripts'):
        require(re.fullmatch(re.escape(version) + r'(?: [0-9A-Za-z._+-]+)?', actual[key]) is not None,
                f'Runtime/SQL PostGIS version mismatch: {actual}')


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def validate_state(state_path: Path, root: Path, prefix: Path) -> dict:
    state_path = contained(state_path, root)
    state = json.loads(state_path.read_text())
    require(state.get('kind') == 'ambisgis-postgis-upgrade-fixture-v1', 'Unknown state format')
    require(state.get('status') == 'prepared-and-stopped', 'Fixture is not prepared and stopped')
    require(state.get('uid') == os.getuid(), 'Fixture belongs to another OS user')
    require(state.get('prefix') == str(prefix.resolve()), 'Fixture prefix differs')
    require(state.get('from_version') == OLD_POSTGIS and state.get('to_version') == TARGET_POSTGIS,
            'Fixture version pair differs from this candidate slice')
    run_dir = contained(Path(state['run_dir']), root)
    require(run_dir == state_path.parent, 'Fixture state was moved')
    data_dir = contained(Path(state['data_dir']), run_dir)
    require((data_dir / '.ambisgis-probe-owner').read_text().strip() == state['nonce'],
            'Cluster ownership marker differs')
    require(not (data_dir / 'postmaster.pid').exists(), 'Fixture cluster is already running or has a stale PID')
    return state


class Probe:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.prefix = Path(args.prefix).resolve()
        self.root = Path(args.work_root).resolve()
        require(self.prefix.is_dir(), 'Installation prefix must exist')
        self.root.mkdir(parents=True, exist_ok=True)
        self.state = None
        if args.phase == 'finish-upgrade':
            require(bool(args.upgrade_state), '--upgrade-state is required for finish-upgrade')
            self.state = validate_state(Path(args.upgrade_state), self.root, self.prefix)
            self.run_dir = Path(self.state['run_dir'])
            self.data_dir = Path(self.state['data_dir'])
            self.nonce = self.state['nonce']
        else:
            require(not args.upgrade_state, '--upgrade-state is only valid for finish-upgrade')
            self.run_dir = Path(tempfile.mkdtemp(prefix='database-', dir=self.root))
            self.run_dir.chmod(0o700)
            self.data_dir = self.run_dir / 'data'
            self.nonce = uuid.uuid4().hex
        self.log_dir = Path(tempfile.mkdtemp(prefix=args.phase + '-', dir=self.run_dir))
        recipe = Path(__file__).read_bytes()
        self.recipe_sha256 = hashlib.sha256(recipe).hexdigest()
        (self.log_dir/'validate_database.py').write_bytes(recipe)
        self.smoke_sql = Path(__file__).with_name('smoke.sql').read_bytes()
        (self.log_dir/'smoke.sql').write_bytes(self.smoke_sql)
        # UNIX sockaddr paths have a short platform limit: avoid long build roots.
        self.socket_dir = Path(tempfile.mkdtemp(prefix='ambisgis-pg-', dir='/tmp'))
        self.socket_dir.chmod(0o700)
        self.env = {'HOME': str(self.run_dir/'home')}
        (self.run_dir/'home').mkdir(exist_ok=True)
        (self.run_dir/'proj-user').mkdir(exist_ok=True)
        self.env.update(PATH=f'{self.prefix / "bin"}:' + os.defpath,
                        LD_LIBRARY_PATH=f'{self.prefix / "lib"}:{self.prefix / "lib64"}',
                        PROJ_DATA=str(self.prefix / 'share/proj'),
                        PROJ_LIB=str(self.prefix / 'share/proj'), PROJ_NETWORK='OFF',
                        PROJ_USER_WRITABLE_DIRECTORY=str(self.run_dir/'proj-user'),
                        GDAL_DATA=str(self.prefix / 'share/gdal'), PGHOST=str(self.socket_dir),
                        PGPORT='5432', PGUSER='ambisgis_probe', PGDATABASE='postgres', LC_ALL='C')
        self.started = False
        self.report = dict(kind='ambisgis-postgis-database-probe-v1', phase=args.phase,
                           recipe_sha256=self.recipe_sha256,
                           started_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                           prefix=str(self.prefix), run_dir=str(self.run_dir),
                           data_dir=str(self.data_dir), socket_dir=str(self.socket_dir),
                           cwd=str(self.run_dir), environment={k: self.env[k] for k in TRACKED_ENV},
                           commands=[], checks={}, status='running', failures=[], skips=[],
                           limits=['Experimental database slice only; no managed branch, authorization, '
                                   'production TLS, backup/restore, or whole-product independence claim.',
                                   'CRS fixture uses EPSG 4326 to 3857; datum and vertical grid transformations remain untested.'])
        self.save()

    def save(self) -> None:
        write_json(self.log_dir / 'report.json', self.report)

    def run(self, name: str, argv: list[str], *, input_text: str | None = None,
            allowed: tuple[int, ...] = (0,)) -> str:
        sequence = len(self.report['commands']) + 1
        log = self.log_dir / f'{sequence:03d}-{name}.log'
        sql = None
        if input_text is not None:
            sql = self.log_dir / f'{sequence:03d}-{name}.sql'
            sql.write_text(input_text)
        entry = dict(name=name, argv=[str(x) for x in argv], cwd=str(self.run_dir),
                     input_sql=str(sql) if sql else None, log=str(log), started_at=time.time())
        self.report['commands'].append(entry)
        self.save()
        started = time.monotonic()
        try:
            with log.open('w') as output:
                completed = subprocess.run(argv, cwd=self.run_dir, env=self.env, input=input_text,
                                           text=True, stdout=output, stderr=subprocess.STDOUT,
                                           timeout=self.args.timeout, check=False)
            entry.update(exit_status=completed.returncode, duration_seconds=time.monotonic() - started,
                         log_sha256=digest(log))
            require(completed.returncode in allowed,
                    f'{name} exited {completed.returncode}; see {log}')
            return log.read_text()
        except BaseException as exc:
            entry.setdefault('exit_status', None)
            entry.update(error=str(exc), duration_seconds=time.monotonic() - started)
            raise
        finally:
            self.save()

    def sql(self, name: str, query: str, database: str = 'postgres') -> str:
        return self.run(name, [str(self.prefix / 'bin/psql'), '-X', '--no-password',
                        '-v', 'ON_ERROR_STOP=1', '-A', '-t', '-d', database], input_text=query)

    def preflight(self) -> None:
        binaries = {}
        for name in ('pg_config', 'postgres', 'initdb', 'pg_ctl', 'psql'):
            path = contained(self.prefix / 'bin' / name, self.prefix)
            require(path.is_file(), f'Missing owned binary: {path}')
            binaries[name] = {'path': str(path), 'sha256': digest(path)}
        self.report['binaries'] = binaries
        pg_config = str(self.prefix / 'bin/pg_config')
        version = self.run('pg-config-version', [pg_config, '--version']).strip()
        require(version == f'PostgreSQL {POSTGRES_VERSION}', f'Unexpected pg_config: {version}')
        paths = {}
        for flag in ('--bindir', '--pkglibdir', '--sharedir'):
            value = self.run(f'pg-config-{flag[2:]}', [pg_config, flag]).strip()
            paths[flag] = str(contained(Path(value), self.prefix))
        require(Path(paths['--bindir']) == self.prefix / 'bin', 'Unexpected PostgreSQL bindir')
        self.report['pg_config_paths'] = paths
        self.report['pg_config'] = self.run('pg-config-all', [pg_config])
        resources = {}
        for path in (self.prefix / 'share/proj/proj.db', self.log_dir/'smoke.sql'):
            require(path.is_file(), f'Required resource absent: {path}')
            resources[str(path)] = digest(path)
        self.report['resources_sha256'] = resources
        libraries = {}
        for path in extension_libraries(Path(paths['--pkglibdir'])):
            libraries[str(path)] = digest(path)
            linked = self.run(f'ldd-{path.name}', ['/usr/bin/ldd', str(path)])
            require_owned_linkage(linked, self.prefix)
        self.report['extension_libraries_sha256'] = libraries
        if self.state:
            require(self.state['postgres_sha256'] == binaries['postgres']['sha256'],
                    'PostgreSQL binary changed between extension upgrade phases')
            require(self.state['extension_libraries_sha256'] != libraries,
                    'Old and new PostGIS shared libraries are identical; target install not demonstrated')
        self.save()

    def start(self) -> None:
        if not self.state:
            self.run('initdb', [str(self.prefix / 'bin/initdb'), '-D', str(self.data_dir),
                               '-U', 'ambisgis_probe', '--encoding=UTF8', '--no-locale',
                               '--auth-local=trust', '--auth-host=reject'])
            (self.data_dir / '.ambisgis-probe-owner').write_text(self.nonce + '\n')
        require((self.data_dir / '.ambisgis-probe-owner').read_text().strip() == self.nonce,
                'Refusing to start unowned cluster')
        require(not (self.data_dir / 'postmaster.pid').exists(), 'Refusing existing PID file')
        self.started = True  # start timeout may still leave our own postmaster running.
        self.run('start', [str(self.prefix / 'bin/pg_ctl'), '-D', str(self.data_dir), '-w', '-t', '60',
                         '-l', str(self.log_dir / 'postgres.log'), '-o',
                         f"-c listen_addresses='' -c unix_socket_directories='{self.socket_dir}' "
                         "-c unix_socket_permissions=0700 -c port=5432", 'start'])
        observation = self.sql('server-identity', "SELECT json_build_object('version',current_setting('server_version'),"
                               "'version_num',current_setting('server_version_num'),"
                               "'data_directory',current_setting('data_directory'),"
                               "'listen_addresses',current_setting('listen_addresses'));\n")
        identity = json.loads(observation.strip())
        require(identity['version_num'] == '150019', f'Unexpected running PostgreSQL: {identity}')
        require(Path(identity['data_directory']).resolve() == self.data_dir.resolve(), 'Wrong running cluster')
        require(identity['listen_addresses'] == '', 'Unexpected TCP listener')
        self.report['server_identity'] = identity

    def stop(self) -> None:
        if not self.started:
            return
        require((self.data_dir / '.ambisgis-probe-owner').read_text().strip() == self.nonce,
                'Refusing to stop unowned cluster')
        self.run('stop', [str(self.prefix / 'bin/pg_ctl'), '-D', str(self.data_dir), '-w', '-t', '60',
                         '-m', 'fast', 'stop'])
        require(not (self.data_dir / 'postmaster.pid').exists(), 'Cluster PID persists after stop')
        self.started = False
        self.report['cluster_stopped'] = True
        self.save()

    def extensions(self, database: str, version: str) -> None:
        self.sql('create-' + database, f'CREATE DATABASE {database};\n')
        for extension in EXTENSIONS:
            self.sql('install-' + extension, f"CREATE EXTENSION {extension} VERSION '{version}';\n", database)

    def versions(self, database: str, version: str, *, runtime: bool = True) -> dict:
        query = "SELECT json_object_agg(extname, extversion) FROM pg_extension WHERE extname IN ('postgis','postgis_raster','postgis_topology');\n"
        versions = json.loads(self.sql('extension-versions-' + database, query, database).strip())
        require(versions == {name: version for name in EXTENSIONS}, f'Extension version mismatch: {versions}')
        if runtime:
            query = """SELECT json_build_object('postgis',postgis_lib_version(), 'raster',postgis_raster_lib_version(),
              'scripts',postgis_scripts_installed(), 'geos',postgis_geos_version(), 'proj',postgis_proj_version(),
              'gdal',postgis_gdal_version(), 'json_c',postgis_libjson_version(),
              'protobuf_c',postgis_libprotobuf_version(), 'full',postgis_full_version());\n"""
            actual = json.loads(self.sql('runtime-versions-' + database, query, database).strip())
            require_postgis_versions(actual, version)
            require('NETWORK_ENABLED=OFF' in actual['proj'], 'PROJ networking must be disabled')
            require('USER_WRITABLE_DIRECTORY=' + str(self.run_dir/'proj-user') in actual['proj'],
                    'PROJ writable resources escaped the disposable run')
            require('DATABASE_PATH=' + str(self.prefix / 'share/proj/proj.db') in actual['proj'],
                    'Runtime PROJ database is not the retained prefix resource')
            for component in ('geos', 'proj', 'gdal', 'json_c', 'protobuf_c'):
                require(bool(actual[component]), f'Missing {component} runtime version')
                expected = getattr(self.args, 'expected_' + component)
                if expected:
                    require(re.search(r'(?<![\d.])' + re.escape(expected) + r'(?![\d.])', actual[component]) is not None,
                            f'{component} runtime mismatch: expected {expected}, observed {actual[component]}')
            versions['runtime'] = actual
        self.report['checks'][database + '-versions-' + version] = versions
        return versions

    def smoke(self, database: str) -> None:
        output = self.sql('smoke-' + database, self.smoke_sql.decode(), database)
        tests = re.findall(r'^AMBISGIS_ASSERT\|(.+)$', output, re.MULTILINE)
        count = re.findall(r'^AMBISGIS_COUNT\|(\d+)$', output, re.MULTILINE)
        require(count == [str(len(tests))] and len(tests) == 13, f'Smoke assertion count mismatch: {tests}')
        self.report['checks'][database + '-smoke'] = dict(passed=len(tests), failed=0, skipped=0, assertions=tests)

    def prepare(self) -> None:
        self.extensions('upgrade_probe', OLD_POSTGIS)
        self.versions('upgrade_probe', OLD_POSTGIS)
        self.smoke('upgrade_probe')
        self.sql('upgrade-fixture', """CREATE SCHEMA ambisgis_upgrade;
CREATE TABLE ambisgis_upgrade.geometry_fixture (id integer PRIMARY KEY, geom geometry(Point,4326));
INSERT INTO ambisgis_upgrade.geometry_fixture VALUES (1,ST_SetSRID(ST_Point(12,34),4326));
CREATE INDEX upgrade_geometry_gix ON ambisgis_upgrade.geometry_fixture USING gist(geom);
CREATE TABLE ambisgis_upgrade.raster_fixture AS SELECT ST_AddBand(
  ST_MakeEmptyRaster(2,2,0,2,1,-1,0,0,4326),'8BUI'::text,7,0) rast;
SELECT topology.CreateTopology('ambisgis_upgrade_topology',4326);
SELECT topology.ST_AddIsoNode('ambisgis_upgrade_topology',NULL,ST_SetSRID(ST_Point(12,34),4326));
""", 'upgrade_probe')
        witness = self.witness()
        self.stop()
        state = dict(kind='ambisgis-postgis-upgrade-fixture-v1', status='prepared-and-stopped', uid=os.getuid(),
                     prefix=str(self.prefix), run_dir=str(self.run_dir), data_dir=str(self.data_dir), nonce=self.nonce,
                     from_version=OLD_POSTGIS, to_version=TARGET_POSTGIS, witness=witness,
                     postgres_sha256=self.report['binaries']['postgres']['sha256'],
                     extension_libraries_sha256=self.report['extension_libraries_sha256'])
        write_json(self.run_dir / 'upgrade-state.json', state)
        self.report['upgrade_state'] = str(self.run_dir / 'upgrade-state.json')
        self.report['upgrade'] = dict(status='prepared; target installation and finish-upgrade still required')

    def witness(self) -> dict:
        output = self.sql('upgrade-data-witness', """SELECT json_build_object(
'geometry', (SELECT json_agg(json_build_array(id,encode(ST_AsEWKB(geom),'hex')) ORDER BY id)
 FROM ambisgis_upgrade.geometry_fixture),
'raster', (SELECT json_agg(encode(ST_AsBinary(rast),'hex')) FROM ambisgis_upgrade.raster_fixture),
'topology', (SELECT json_agg(json_build_array(node_id,containing_face,encode(ST_AsEWKB(geom),'hex')) ORDER BY node_id)
 FROM ambisgis_upgrade_topology.node));\n""", 'upgrade_probe')
        return json.loads(output.strip())

    def finish(self) -> None:
        self.versions('upgrade_probe', OLD_POSTGIS, runtime=False)
        require(self.witness() == self.state['witness'], 'Fixture data changed before update')
        for extension in EXTENSIONS:
            self.sql('update-' + extension,
                     f"ALTER EXTENSION {extension} UPDATE TO '{TARGET_POSTGIS}';\n", 'upgrade_probe')
        self.versions('upgrade_probe', TARGET_POSTGIS)
        require(self.witness() == self.state['witness'], 'Data changed during actual extension update')
        self.smoke('upgrade_probe')
        self.report['upgrade'] = dict(status='passed', from_version=OLD_POSTGIS, to_version=TARGET_POSTGIS,
                                     geometry_raster_topology_preserved=True, source_state=str(self.args.upgrade_state))
        self.extensions('fresh_probe', TARGET_POSTGIS)
        self.versions('fresh_probe', TARGET_POSTGIS)
        self.smoke('fresh_probe')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare-upgrade', 'finish-upgrade', 'smoke'))
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--upgrade-state')
    parser.add_argument('--timeout', type=int, default=300)
    for component in ('geos', 'proj', 'gdal', 'json-c', 'protobuf-c'):
        parser.add_argument('--expected-' + component)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    probe = None
    try:
        probe = Probe(args)
        print(f'Probe report: {probe.log_dir / "report.json"}', flush=True)
        probe.preflight()
        probe.start()
        if args.phase == 'prepare-upgrade':
            probe.prepare()
        elif args.phase == 'finish-upgrade':
            probe.finish()
        else:
            probe.extensions('fresh_probe', TARGET_POSTGIS)
            probe.versions('fresh_probe', TARGET_POSTGIS)
            probe.smoke('fresh_probe')
            probe.report['skips'].append('Earlier extension fixture not supplied: actual upgrade not tested')
            probe.report['upgrade'] = {'status': 'gap; actual retained earlier-version fixture required'}
        probe.report['status'] = 'passed'
    except (Exception, KeyboardInterrupt) as exc:
        if probe:
            probe.report['status'] = 'failed'
            probe.report['failures'].append(str(exc))
        print(f'Validation failed: {exc}', file=sys.stderr)
    finally:
        if probe:
            try:
                probe.stop()
            except (Exception, KeyboardInterrupt) as exc:
                probe.report['status'] = 'failed'
                probe.report['failures'].append(f'Cluster shutdown failed: {exc}')
            probe.report['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            probe.save()
            # Only our empty socket directory, never PGDATA or any user's files.
            try:
                probe.socket_dir.rmdir()
            except OSError:
                pass
    return 0 if probe and probe.report['status'] == 'passed' else 1


if __name__ == '__main__':
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt('Probe interrupted; stopping own cluster')
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
