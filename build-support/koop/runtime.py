"""Actual disposable catalog/PostGIS/Koop experiment; retained inputs only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
TASK = Path('/home/revelberry/Projects/AmbisGIS')
sys.path[:0] = [str(HERE.parent / 'geonode'), str(HERE.parent / 'java')]
from run import Capture, configure_database, digest, fresh_port, private_values, redact, save, stop


def execute(command, environment, output, name, values, timeout=240):
    process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, errors='replace')
    capture = Capture(process, output / (name + '.log'), lambda: values)
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop(process, capture)
        raise RuntimeError('bounded command timeout') from None
    capture.finish()
    receipt = {'argv': command, 'exit_code': code, 'log_sha256': digest(capture.path),
               'diagnostic_secret_hits': capture.leaks, 'source_redactions': capture.source_redactions}
    save(output / (name + '-command.json'), receipt)
    if code or capture.security_failures:
        raise RuntimeError('command failed: ' + name)
    return receipt


def child(config_path):
    config = json.loads(Path(config_path).read_text())
    output = Path(config['output'])
    env = config['environment']
    values = private_values(config) + [config['backend_key'], config['cursor_key'], config['query_database']['password']]
    report = {'result_exit_code': 1, 'cleanup': {}, 'commands': []}
    processes = []
    provision = False
    try:
        for action in ('check', 'migrate', 'provision'):
            if action == 'provision': provision = True
            cmd = [config['python'], str(HERE.parent / 'geonode/manage_fixture.py'), '--config', str(config_path), action]
            report['commands'].append(execute(cmd, env, output, action, values))
        report['commands'].append(execute([config['python'], str(HERE.parent / 'geonode/catalog_fixture.py'),
            '--config', str(config_path), 'initialize'], env, output, 'catalog-initialize', values))
        from runtime_fixture import load
        report['fixture'] = load(config)
        for name, command, environment in (
            ('catalog', [config['python'], str(HERE.parent / 'geonode/manage_fixture.py'), '--config', str(config_path), 'serve'], env),
            ('native', [config['python'], str(HERE / 'backend.py'), '--config', str(config_path)], env),
            ('koop', [config['node'], str(HERE / 'provider.js'), str(config_path)], config['node_environment'])):
            process = subprocess.Popen(command, env=environment, cwd=config['empty_config'], stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors='replace')
            capture = Capture(process, output / (name + '-runtime.log'), lambda: values)
            processes.append((name, process, capture))
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError(name + ' exited before readiness')
                if capture.path.exists() and 'listening' in capture.path.read_text(): break
                time.sleep(.1)
            else: raise RuntimeError(name + ' readiness timeout')
        from runtime_cases import exercise
        report['commands'].append(execute([config['node'], str(HERE / 'codec_diagnostics.js'), config['app'], str(output / 'codec-diagnostics.json')],
                                         config['node_environment'], output, 'codec-diagnostics', values, 30))
        report['tests'] = exercise(config, values, next(p for name, p, capture in processes if name == 'catalog'))
        if not report['tests']['passed']:
            raise RuntimeError('runtime assertions failed')
        report['result_exit_code'] = 0
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': redact(str(error), values)}
    finally:
        for name, process, capture in reversed(processes):
            try:
                stop(process, capture)
                report['cleanup'][name] = {'stopped': process.poll() is not None, 'secret_hits': capture.leaks,
                                          'security_failures': capture.security_failures}
                if capture.security_failures: report['result_exit_code'] = 1
            except Exception as error:
                report['cleanup'][name] = {'error': type(error).__name__}; report['result_exit_code'] = 1
        if provision:
            try:
                execute([config['python'], str(HERE.parent / 'geonode/manage_fixture.py'), '--config', str(config_path), 'cleanup'],
                        env, output, 'credential-cleanup', values, 90)
                report['cleanup']['credentials_invalidated'] = True
            except Exception as error:
                report['cleanup']['credentials_invalidated'] = False; report['result_exit_code'] = 1
        save(output / 'child-result.json', report)
    return report['result_exit_code']


def run(args):
    import configured_auth_database
    import installed
    import loopback_exec
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    database = None
    result = {'result_exit_code': 1, 'cleanup': {}, 'scope': 'Private bounded synthetic Koop reuse evaluation, no distribution or C1 adoption acceptance.'}
    config_path = output / 'private.json'
    values = []
    try:
        from custody import sha, verify_inventory
        from install import verify_installed
        custody = TASK / 'source-archives/fnd06-koop/candidate-002'
        verify_inventory(custody)
        installation = args.installation.resolve()
        from koop_runtime_inputs import node_binding
        node_before = node_binding(custody / 'node.tar.xz', installation / 'toolchain')
        save(output / 'node-toolchain-before.json', node_before)
        selected = json.loads((installation / 'result.json').read_text())
        if selected.get('result_exit_code') != 0 or selected['input_manifest_sha256'] != sha(custody / 'manifest.json'):
            raise ValueError('installation identity differs')
        installed_before = verify_installed(installation / 'app', custody, json.loads((custody / 'package-lock.json').read_text()))
        save(output / 'koop-installed-before.json', installed_before)
        origin = installed.verify(args.python)
        save(output / 'catalog-origin-before.json', origin)
        snapshot = output / 'tooling'
        for component in ('geonode', 'java', 'postgis', 'koop'):
            shutil.copytree(HERE.parent / component, snapshot / component,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(HERE.parents[1] / 'services/control-plane/ambisgis_policy', snapshot / 'geonode/ambisgis_policy',
                        ignore=shutil.ignore_patterns('__pycache__'))
        contract_root = args.contract.resolve()
        from koop_runtime_inputs import CONTRACT, contract_bindings, corpus_binding
        bindings = contract_bindings(contract_root)
        save(output / 'contract-bindings.json', bindings)
        (snapshot / 'plan/tools').mkdir(parents=True)
        shutil.copyfile(contract_root / 'plan/tools/native_contracts.py', snapshot / 'plan/tools/native_contracts.py')
        shutil.copytree(contract_root / 'plan/contracts', snapshot / 'plan/contracts')
        layer = json.loads((contract_root / 'plan/examples/layer.json').read_text())
        save(output / 'layer.json', layer)
        hashes = {str(p.relative_to(snapshot)): digest(p) for p in snapshot.rglob('*') if p.is_file()}
        save(output / 'tooling.json', hashes)
        source = args.corpus.resolve()
        corpus_manifest = corpus_binding(source, args.corpus_manifest_sha256)
        # Keep the exact selected corpus and source authority manifest; no regenerated rows.
        shutil.copyfile(source / 'addresses.ndjson', output / 'addresses.ndjson')
        shutil.copyfile(source / 'manifest.json', output / 'corpus-manifest.json')
        result['corpus'] = {'path': str(source), 'manifest_sha256': digest(source / 'manifest.json'),
                            'addresses_sha256': digest(output / 'addresses.ndjson')}
        database = configured_auth_database.start(TASK / 'build-worktrees/postgis-slice/run-003/prefix',
            TASK / 'build-worktrees/postgis-slice/run-003-evidence-final.json', output / 'database')
        owner, runtime = configure_database(database, output)
        query_password = secrets.token_urlsafe(36)
        database.secret_values.append(query_password)
        database.sql('query-role', "CREATE ROLE fixture_query LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '" + query_password + "'; ALTER ROLE fixture_query SET default_transaction_read_only=on; ALTER ROLE fixture_query CONNECTION LIMIT 3;")
        hba = database.data / 'pg_hba.conf'
        hba.write_text('host fixture_geonode fixture_query 127.0.0.1/32 scram-sha-256\n' + hba.read_text())
        database.sql('query-reload', 'SELECT pg_reload_conf();')
        port = fresh_port()
        empty = output / 'empty-config'; empty.mkdir()
        (empty / 'production.json').write_text('{}\n')
        config = {'output': str(output), 'python': str(args.python), 'database': owner, 'runtime_database': runtime,
                  'query_database': {**runtime, 'user': 'fixture_query', 'password': query_password},
                  'site_url': f'http://127.0.0.1:{port}/', 'catalog_port': port,
                  'geoserver_url': f'http://127.0.0.1:{fresh_port()}/geoserver/',
                  'secret_key': secrets.token_urlsafe(48), 'api_key': secrets.token_urlsafe(36),
                  'client_id': 'fixture-koop-' + secrets.token_hex(12), 'client_secret': secrets.token_urlsafe(36),
                  'second_client_id': 'fixture-second-' + secrets.token_hex(12), 'second_client_secret': secrets.token_urlsafe(36),
                  'redirect_uri': f'http://127.0.0.1:{port}/fixture-callback',
                  'passwords': {name: secrets.token_urlsafe(32) for name in ('fixture-reader', 'fixture-outsider', 'fixture-disabled', 'fixture-admin', 'fixture-unmapped')},
                  'oidc_rsa_private_key_file': str(output / 'oidc-key.pem'), 'strict_verifier': True, 'strict_roles': True,
                  'role_service_username': 'fixture-role-service', 'role_service_api_key': secrets.token_urlsafe(36),
                  'catalog_policy': True, 'policy_key': secrets.token_urlsafe(36),
                  'backend_key': secrets.token_urlsafe(36), 'cursor_key': secrets.token_hex(32),
                  'backend_port': fresh_port(), 'koop_port': fresh_port(), 'layer': layer,
                  'resources': {'public_points': 'fixture:public_points', 'private_points': 'fixture:private_points', 'group_points': 'fixture:group_points'},
                  'app': str(installation / 'app'), 'empty_config': str(empty)}
        key = subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', config['oidc_rsa_private_key_file']],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if key.returncode: raise RuntimeError('ephemeral key generation failed')
        Path(config['oidc_rsa_private_key_file']).chmod(0o600)
        prefix = TASK / 'build-worktrees/postgis-slice/run-003/prefix'
        env = {'PATH': str(args.python.parent) + ':' + str(prefix / 'bin') + ':/usr/bin:/bin',
               'HOME': str(output), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
               'LD_LIBRARY_PATH': str(prefix / 'lib') + ':' + str(prefix / 'lib64'),
               'PROJ_DATA': str(prefix / 'share/proj'), 'PROJ_NETWORK': 'OFF', 'GDAL_DATA': str(prefix / 'share/gdal'),
               'GDAL_LIBRARY_PATH': str(prefix / 'lib/libgdal.so'), 'GEOS_LIBRARY_PATH': str(prefix / 'lib/libgeos_c.so'),
               'PYTHONPATH': ':'.join(str(snapshot / x) for x in ('koop', 'plan/tools', 'geonode', 'java')),
               'PYTHONNOUSERSITE': '1', 'PYTHONPYCACHEPREFIX': str(output / 'python-cache')}
        config['environment'] = env
        config['node'] = str(installation / 'toolchain/node-v24.18.1-linux-x64/bin/node')
        config['node_environment'] = {'PATH': str(Path(config['node']).parent) + ':/usr/bin:/bin', 'HOME': str(output),
            'LANG': 'C.UTF-8', 'NODE_ENV': 'production', 'NODE_CONFIG_DIR': str(empty), 'NODE_CONFIG': '{}',
            'SUPPRESS_NO_CONFIG_WARNING': 'true', 'NODE_OPTIONS': '--max-old-space-size=256', 'OBJECTID_FEATURE_HASH': 'javascript'}
        values = private_values(config) + [config['backend_key'], config['cursor_key'], query_password]
        save(config_path, config, private=True)
        argv = [sys.executable, str(snapshot / 'java/loopback_exec.py'), '--evidence', str(output / 'network.json'), '--timeout', '900', '--',
                str(args.python), str(snapshot / 'koop/runtime.py'), '--child', str(config_path)]
        save(output / 'invocation.json', {'argv': argv, 'environment': env, 'contract_commit': CONTRACT,
            'install_result_sha256': digest(installation / 'result.json'), 'tooling_sha256': digest(output / 'tooling.json')})
        with (output / 'supervisor.log').open('x') as log:
            process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)
            try: code = process.wait(timeout=950)
            except subprocess.TimeoutExpired:
                process.terminate(); process.wait(timeout=45); raise RuntimeError('supervisor timeout') from None
        result['network'] = loopback_exec.verify_receipt(output / 'network.json', code)
        result['child'] = json.loads((output / 'child-result.json').read_text())
        after = installed.verify(args.python)
        save(output / 'catalog-origin-after.json', after)
        if after != origin: raise RuntimeError('catalog installed source changed')
        installed_after = verify_installed(installation / 'app', custody, json.loads((custody / 'package-lock.json').read_text()))
        if installed_after != installed_before: raise RuntimeError('Koop installed bytes changed')
        node_after = node_binding(custody / 'node.tar.xz', installation / 'toolchain')
        save(output / 'node-toolchain-after.json', node_after)
        if node_after != node_before: raise RuntimeError('Node runtime files changed')
        if any(digest(snapshot / p) != h for p, h in hashes.items()): raise RuntimeError('executed tooling changed')
        result['origins_unchanged'] = True
        result['result_exit_code'] = int(code != 0 or result['child']['result_exit_code'] != 0)
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': redact(str(error), values)}
    finally:
        if database:
            try:
                database.stop(); result['database'] = database.receipt
                if not database.receipt['stopped'] or database.receipt['result_exit_code']: result['result_exit_code'] = 1
            except Exception as error:
                result['cleanup']['database_error'] = type(error).__name__; result['result_exit_code'] = 1
        for name in ('private.json', 'oidc-key.pem'):
            path = output / name
            if path.exists(): path.write_text('SCRUBBED DISPOSABLE FIXTURE SECRET\n')
        result['cleanup']['private_configuration_scrubbed'] = True
        result['database_exception'] = 'Existing reviewed #59 PostgreSQL backend setsid exception; authenticated loopback-only owned disposable DB. Other services under unchanged supervisor.'
        save(output / 'result.json', result)
    print(json.dumps({'output': str(output), 'result_exit_code': result['result_exit_code'], 'error': result.get('error')}))
    return result['result_exit_code']


if __name__ == '__main__':
    if sys.argv[1:2] == ['--child']:
        raise SystemExit(child(sys.argv[2]))
    parser = argparse.ArgumentParser()
    for name in ('python', 'installation', 'contract', 'corpus', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--corpus-manifest-sha256', required=True)
    raise SystemExit(run(parser.parse_args()))
