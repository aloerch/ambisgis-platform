#!/usr/bin/env python3
"""Run the frozen F02-04 selection against real owned QGIS build outputs.

Invoke this runner under loopback_exec.py. PostgreSQL is created separately by
native_database.py, using the documented PostgreSQL supervision exception.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest
import xml.etree.ElementTree as ET

SELECTION = Path(__file__).with_name('native-selection.json')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def load_selection(source, manifest=SELECTION):
    selection = json.loads(Path(manifest).read_text())
    if selection['schema'] != 1 or not selection['cpp'] or not selection['python']:
        raise ValueError('empty or unsupported native selection')
    source = Path(source).resolve()
    for relative, expected in selection['source_sha256'].items():
        path = source / relative
        if not path.resolve().is_relative_to(source) or sha(path) != expected:
            raise ValueError('native source integrity mismatch: ' + relative)
    for row in selection['cpp']:
        text = (source / row['source']).read_text()
        if not row['methods'] or len(row['methods']) != len(set(row['methods'])):
            raise ValueError('empty or duplicated C++ selection')
        for method in row['methods']:
            if not re.search(r'void\s+\w+::' + re.escape(method) + r'\s*\(', text):
                raise ValueError('C++ selector absent from owned source: ' + method)
    for row in selection['python']:
        if not row['methods'] or len(row['methods']) != len(set(row['methods'])):
            raise ValueError('empty or duplicated Python selection')
    return selection


def verify_fixture_tree(source, selection):
    record = selection['fixture_tree']
    source = Path(source).resolve()
    root = source / record['path']
    digest = hashlib.sha256()
    count = size = 0
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('native fixture contains unexpected symlink')
        if path.is_file():
            relative = str(path.relative_to(source))
            digest.update(relative.encode() + b'\0' + sha(path).encode() + b'\n')
            count += 1
            size += path.stat().st_size
    actual = {'file_count': count, 'bytes': size, 'sha256': digest.hexdigest()}
    if any(actual[key] != record[key] for key in actual):
        raise ValueError('native fixture/golden-output tree integrity mismatch')
    return actual


def native_environment(config, output):
    output = Path(output).resolve()
    build = Path(config['qgis_build']).resolve()
    source = Path(config['qgis_source']).resolve()
    spatial = Path(config['spatial_prefix']).resolve()
    database = Path(config['database_prefix']).resolve()
    dirs = {key: output / name for key, name in {
        'HOME': 'home', 'XDG_CONFIG_HOME': 'config', 'XDG_CACHE_HOME': 'cache',
        'XDG_DATA_HOME': 'data', 'XDG_RUNTIME_DIR': 'runtime', 'TMPDIR': 'tmp',
        'QGIS_CUSTOM_CONFIG_PATH': 'qgis-profile', 'QGIS_AUTH_DB_DIR_PATH': 'auth',
    }.items()}
    for path in dirs.values():
        path.mkdir(mode=0o700)
    env = {key: str(path) for key, path in dirs.items()}
    env.update(PATH=str(Path(config['python']).parent) + ':' + os.defpath,
               LC_ALL='C.UTF-8', QT_QPA_PLATFORM='offscreen', QT_HASH_SEED='1',
               PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PROJ_NETWORK='OFF',
               QGIS_PREFIX_PATH=str(build / 'output'),
               QGIS_PLUGINPATH=str(build / 'output/lib/qgis/plugins'),
               QGIS_TEST_DATA_DIR=str(source / 'tests/testdata'),
               QGIS_SERVER_DISABLE_GETPRINT='0',
               QGIS_PGTEST_DB='service=qgis_test',
               PGSERVICEFILE=str(Path(config['pg_service_file']).resolve()),
               PROJ_DATA=str(config.get('proj_data', spatial / 'share/proj')),
               GDAL_DATA=str(config.get('gdal_data', spatial / 'share/gdal')),
               QT_PLUGIN_PATH=str(config['qt_plugins']))
    env['PYTHONPATH'] = ':'.join([str(build / 'output/python'), str(source / 'tests/src/python'),
                                *config['python_paths']])
    env['LD_LIBRARY_PATH'] = ':'.join([str(build / 'output/lib'), *config['library_paths']])
    for key in ('FONTCONFIG_FILE', 'FONTCONFIG_PATH'):
        if config.get(key.lower()):
            env[key] = str(config[key.lower()])
    return env


def check_service(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError('native PostgreSQL service must be a private regular file')
    parser = configparser.ConfigParser()
    parser.read(path)
    section = parser['qgis_test']
    if section.get('host') != '127.0.0.1' or section.get('dbname') != 'qgis_native':
        raise ValueError('native service must address the separate loopback qgis_native database')
    if section.get('user') != 'qgis_native_reader':
        raise ValueError('native service must use its restricted fixture role')
    if section.get('sslmode') != 'disable' or section.get('connect_timeout') != '5':
        raise ValueError('native service transport does not match fixture policy')


def parse_qtest(path, methods):
    root = ET.parse(path).getroot()
    events = []
    found = set()
    bad = []
    for function in root.findall('TestFunction'):
        name = function.get('name')
        if name in ('initTestCase', 'cleanupTestCase'):
            for incident in function.findall('Incident'):
                if incident.get('type') != 'pass':
                    bad.append({'method': name, 'type': incident.get('type')})
            continue
        found.add(name)
        incidents = function.findall('Incident')
        if not incidents:
            bad.append({'method': name, 'type': 'no-assertion-result'})
        for incident in incidents:
            event = {'method': name, 'type': incident.get('type'),
                     'data_tag': incident.findtext('DataTag')}
            events.append(event)
            if event['type'] != 'pass':
                bad.append(event)
    if found != set(methods):
        bad.append({'type': 'selection-mismatch', 'missing': sorted(set(methods) - found),
                    'unexpected': sorted(found - set(methods))})
    return {'events': events, 'passed_cases': sum(e['type'] == 'pass' for e in events),
            'nonpassing': bad, 'result_exit_code': 0 if events and not bad else 1}


def check_python_result(result, count):
    return (count > 0 and result.get('selected_count') == count and result.get('tests_run') == count
            and result.get('successes') == count and not result.get('failures')
            and not result.get('errors') and not result.get('skips')
            and not result.get('expected_failures') and not result.get('unexpected_successes'))


def worker_preflight(config, selection):
    from qgis import _core, _gui, _analysis, _server
    from qgis.core import QgsApplication, QgsProviderRegistry, QgsVectorLayer
    from qgis.testing import start_app
    build = Path(config['qgis_build']).resolve()
    modules = {}
    for module in (_core, _gui, _analysis, _server):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(build):
            raise ValueError('QGIS binding is outside owned build: ' + module.__name__)
        modules[module.__name__] = {'path': str(path), 'sha256': sha(path)}
    for name in selection['required_python_modules']:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        modules[name] = {'path': str(path), 'sha256': sha(path)}
    from osgeo import gdal
    drivers = {}
    for name in selection['required_gdal_drivers']:
        driver = gdal.GetDriverByName(name)
        if driver is None:
            raise ValueError('required native fixture GDAL driver absent: ' + name)
        drivers[name] = driver.ShortName
    app = start_app()
    providers = QgsProviderRegistry.instance().providerList()
    if not set(selection['required_providers']).issubset(providers):
        raise ValueError('native fixture providers missing')
    import psycopg2
    with psycopg2.connect('service=qgis_test') as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_user, count(*) FROM qgis_test."someData"')
            if cursor.fetchone() != ('qgis_native', 'qgis_native_reader', 5):
                raise ValueError('native PostgreSQL fixture identity/count mismatch')
    # Force real provider and spatial-library loading before reading Linux origins.
    layer = QgsVectorLayer('service=qgis_test key=pk srid=4326 type=POINT '
                           'table="qgis_test"."someData" (geom)', 'native-preflight', 'postgres')
    if not layer.isValid() or layer.featureCount() != 5:
        raise ValueError('native PostgreSQL provider cannot open source fixture')
    maps = sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                   if '/' in line and any(s in line for s in ('libqgis_', 'libgdal.', 'libgeos', 'libproj.', 'libpq.'))})
    required = {'libqgis_': build, 'libgdal.': Path(config['spatial_prefix']).resolve(),
                'libgeos': Path(config['database_prefix']).resolve(),
                'libproj.': Path(config.get('proj_prefix', config['spatial_prefix'])).resolve(),
                'libpq.': Path(config['database_prefix']).resolve()}
    for stem, allowed in required.items():
        actual = [Path(path).resolve() for path in maps if stem in Path(path).name]
        if not actual or any(not path.is_relative_to(allowed) for path in actual):
            raise ValueError('native loaded library origin mismatch: ' + stem)
    return {'modules': modules, 'drivers': drivers, 'providers': providers,
            'mapped_spatial_libraries': [{'path': p, 'sha256': sha(p)} for p in maps],
            'qgis_prefix': QgsApplication.prefixPath(),
            'resources': {'proj_db': str(Path(os.environ['PROJ_DATA']) / 'proj.db'),
                          'proj_db_sha256': sha(Path(os.environ['PROJ_DATA']) / 'proj.db'),
                          'gdal_data': os.environ['GDAL_DATA']}, 'result_exit_code': 0}


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = 0

    def addSuccess(self, test):
        self.successes += 1
        super().addSuccess(test)


def python_worker(config, row):
    module = importlib.import_module(row['module'])
    source = Path(config['qgis_source']).resolve()
    if Path(module.__file__).resolve() != source / 'tests/src/python' / (row['module'] + '.py'):
        raise ValueError('native Python test imported from wrong source')
    cls = getattr(module, row['class'])
    suite = unittest.TestSuite()
    for method in row['methods']:
        if not callable(getattr(cls, method, None)):
            raise ValueError('selected native test method absent: ' + method)
        suite.addTest(cls(method))
    count = suite.countTestCases()
    if count != len(row['methods']) or not count:
        raise ValueError('native Python discovery count mismatch')
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    record = {'selected_count': count, 'tests_run': result.testsRun, 'successes': result.successes,
              'failures': len(result.failures), 'errors': len(result.errors),
              'skips': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
              'expected_failures': len(result.expectedFailures),
              'unexpected_successes': len(result.unexpectedSuccesses)}
    record['result_exit_code'] = 0 if check_python_result(record, count) else 1
    return record


def subprocess_evidence(command, output, env, timeout=600):
    start = time.monotonic()
    with Path(output).open('x') as log:
        try:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                       env=env, timeout=timeout)
            code = completed.returncode
        except subprocess.TimeoutExpired:
            code = 124
    return {'argv': [str(p) for p in command], 'exit_code': code,
            'duration_seconds': round(time.monotonic() - start, 3), 'log': str(output),
            'log_sha256': sha(output)}


def run(config, output):
    output = Path(output).absolute()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    receipt = {'result_exit_code': 1, 'scope': 'frozen native subset; no full-suite or product acceptance',
               'selection_sha256': sha(SELECTION), 'commands': [], 'tests': []}
    try:
        source, build = Path(config['qgis_source']).resolve(), Path(config['qgis_build']).resolve()
        selection = load_selection(source)
        receipt['selection'] = selection
        receipt['fixtures_before'] = verify_fixture_tree(source, selection)
        cache = (build / 'CMakeCache.txt').read_text()
        for key in ('ENABLE_TESTS', 'ENABLE_PGTEST'):
            if not re.search(r'^' + key + r':BOOL=(ON|TRUE|1)$', cache, re.M):
                raise ValueError('required native build flag absent: ' + key)
        if 'CMAKE_HOME_DIRECTORY:INTERNAL=' + str(source) not in cache.splitlines():
            raise ValueError('native CMake source root mismatch')
        check_service(config['pg_service_file'])
        env = native_environment(config, output)
        receipt['environment'] = env
        invocation = output / 'invocation.json'
        save(invocation, config)
        recipe = str(Path(__file__).resolve())
        preflight = output / 'preflight.json'
        command = [config['python'], recipe, '--worker', 'preflight', '--config', str(invocation), '--result', str(preflight)]
        entry = subprocess_evidence(command, output / 'preflight.log', env)
        receipt['commands'].append(entry)
        if entry['exit_code'] or not preflight.exists():
            raise ValueError('native prerequisites unavailable; see preflight.log')
        receipt['preflight'] = json.loads(preflight.read_text())
        for row in selection['cpp']:
            binary = build / 'output/bin' / row['target']
            if not binary.is_file():
                raise ValueError('native target not built: ' + row['target'])
            xml = output / (row['target'] + '.xml')
            command = [str(binary), *row['methods'], '-maxwarnings', '10000', '-o', str(xml) + ',xml', '-o', '-,txt']
            entry = subprocess_evidence(command, output / (row['target'] + '.log'), env)
            receipt['commands'].append(entry)
            result = parse_qtest(xml, row['methods']) if xml.exists() else {'result_exit_code': 1, 'error': 'missing QtTest XML'}
            result.update(name=row['target'], binary_sha256=sha(binary), process_exit_code=entry['exit_code'])
            if entry['exit_code']:
                result['result_exit_code'] = 1
            receipt['tests'].append(result)
            save(output / 'native-result.json', receipt)
        for row in selection['python']:
            path = output / (row['name'] + '.json')
            command = [config['python'], recipe, '--worker', row['name'], '--config', str(invocation), '--result', str(path)]
            entry = subprocess_evidence(command, output / (row['name'] + '.log'), env)
            receipt['commands'].append(entry)
            result = json.loads(path.read_text()) if path.exists() else {'result_exit_code': 1, 'error': 'missing unittest result'}
            result.update(name=row['name'], process_exit_code=entry['exit_code'])
            if entry['exit_code'] or not check_python_result(result, len(row['methods'])):
                result['result_exit_code'] = 1
            receipt['tests'].append(result)
            save(output / 'native-result.json', receipt)
        load_selection(source)
        receipt['fixtures_after'] = verify_fixture_tree(source, selection)
        if len(receipt['tests']) == len(selection['cpp']) + len(selection['python']) and all(t['result_exit_code'] == 0 for t in receipt['tests']):
            receipt['result_exit_code'] = 0
    except Exception as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
    save(output / 'native-result.json', receipt)
    return receipt['result_exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker')
    parser.add_argument('--result', type=Path)
    parser.add_argument('--list-targets', action='store_true')
    args = parser.parse_args()
    if args.list_targets:
        print(' '.join(row['target'] for row in json.loads(SELECTION.read_text())['cpp']))
        return 0
    config = json.loads(args.config.read_text())
    if args.worker:
        result = {'result_exit_code': 1}
        try:
            selection = load_selection(config['qgis_source'])
            result = worker_preflight(config, selection) if args.worker == 'preflight' else python_worker(config, next(row for row in selection['python'] if row['name'] == args.worker))
        except Exception as error:
            result['error'] = {'type': type(error).__name__, 'message': str(error)}
            import traceback
            traceback.print_exc()
        save(args.result, result)
        return result['result_exit_code']
    return run(config, args.output)


if __name__ == '__main__':
    sys.exit(main())
