#!/usr/bin/env python3
"""Disposable real GeoNode runner; PostgreSQL alone uses the documented #59 exception.

Every attempt uses a new directory. Errors, leaked diagnostics, failed network
proof, integrity changes, or unsuccessful cleanup fail the receipt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'java'))
TASK = Path('/home/revelberry/Projects/AmbisGIS')
WAR_SHA256 = '8a79a2cf7647be2f28591d7f04f975dc84cb00baaaea35cb3d5f2f293ea8f39f'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def save(path, value, private=False):
    path = Path(path)
    with path.open('x', encoding='utf8') as stream:
        if private: os.chmod(path, 0o600)
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def private_values(config):
    values = [config[k] for k in ('secret_key', 'api_key', 'client_secret', 'second_client_secret')]
    values += [config.get('role_service_api_key', '')]
    values += list(config['passwords'].values())
    values += [config[k]['password'] for k in ('database', 'runtime_database')]
    return values


def redact(text, values):
    for value in sorted(set(values), key=len, reverse=True):
        if value: text = text.replace(value, '[REDACTED_FIXTURE_VALUE]')
    return text


def fresh_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def configure_database(database, output):
    """Separate catalog schema owner and runtime DML identity; no managed tables."""
    owner_pw, app_pw = secrets.token_urlsafe(36), secrets.token_urlsafe(36)
    database.secret_values += [owner_pw, app_pw]
    database.sql('geonode-roles',
        "CREATE ROLE fixture_gn_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '" + owner_pw + "';\n"
        "CREATE ROLE fixture_gn_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '" + app_pw + "';\n")
    database.sql('geonode-database', 'CREATE DATABASE fixture_geonode OWNER fixture_gn_owner;\n')
    database.sql('geonode-extensions', "CREATE EXTENSION postgis VERSION '3.5.7';\nREVOKE CREATE ON SCHEMA public FROM PUBLIC;\nGRANT USAGE, CREATE ON SCHEMA public TO fixture_gn_owner;\nGRANT USAGE ON SCHEMA public TO fixture_gn_runtime;\nALTER DEFAULT PRIVILEGES FOR ROLE fixture_gn_owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fixture_gn_runtime;\nALTER DEFAULT PRIVILEGES FOR ROLE fixture_gn_owner IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO fixture_gn_runtime;\n", 'fixture_geonode')
    hba = database.data / 'pg_hba.conf'
    original = hba.read_text()
    hba.write_text('host fixture_geonode fixture_gn_owner,fixture_gn_runtime 127.0.0.1/32 scram-sha-256\n' + original)
    database.sql('geonode-reload', 'SELECT pg_reload_conf();\n')
    return ({'host': '127.0.0.1', 'port': database.port, 'name': 'fixture_geonode', 'user': 'fixture_gn_owner', 'password': owner_pw},
            {'host': '127.0.0.1', 'port': database.port, 'name': 'fixture_geonode', 'user': 'fixture_gn_runtime', 'password': app_pw})


class Capture:
    def __init__(self, process, path, sensitive):
        self.process, self.path, self.sensitive = process, Path(path), sensitive
        self.leaks, self.errors = 0, []
        self.source_redactions = {key: 0 for key in (
            'source_diagnostic_redactions', 'source_credential_field_redactions',
            'source_private_key_redactions', 'source_opaque_value_redactions')}
        self.thread = threading.Thread(target=self.copy, daemon=True)
        self.thread.start()

    def copy(self):
        try:
            with self.path.open('x') as out:
                for line in self.process.stdout:
                    try: record = json.loads(line)
                    except (ValueError, TypeError): record = None
                    if isinstance(record, dict) and record.get('event') == 'application_log':
                        for key in self.source_redactions:
                            count = record.get(key, 0)
                            if type(count) is not int or count < 0:
                                raise ValueError('invalid source diagnostic counter')
                            self.source_redactions[key] += count
                    values = self.sensitive()
                    self.leaks += sum(bool(v) and v in line for v in values)
                    out.write(redact(line, values)); out.flush()
        except Exception as error:
            self.errors.append(type(error).__name__)

    @property
    def security_failures(self):
        return self.leaks + sum(value for key, value in self.source_redactions.items()
                                if key != 'source_opaque_value_redactions')

    def finish(self):
        self.thread.join(10)
        if self.thread.is_alive() or self.errors: raise RuntimeError('diagnostic capture failed')


def stop(process, capture):
    forced = False
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=35)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=10); forced = True
    capture.finish()
    if forced: raise RuntimeError('task-owned service required forced kill')


def child(invocation):
    config_path = Path(invocation['config'])
    config = json.loads(config_path.read_text())
    output = Path(config['output'])
    values = private_values(config)
    report = {'result_exit_code': 1, 'identity_is_synthetic': False, 'commands': [], 'cleanup': {}}
    provision_started = False
    try:
        for action in ('check', 'migrate', 'initialize', 'native-tests', 'provision'):
            if action == 'provision': provision_started = True
            cmd = [invocation['python'], str(HERE / 'manage_fixture.py'), '--config', str(config_path), action]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, errors='replace', env=invocation['environment'])
            capture = Capture(process, output / (action + '.log'), lambda: values)
            try: code = process.wait(timeout=240)
            except subprocess.TimeoutExpired:
                stop(process, capture)
                raise RuntimeError('GeoNode command timeout: ' + action)
            capture.finish()
            report['commands'].append({'action': action, 'exit_code': code, 'log_sha256': digest(capture.path), 'diagnostic_secret_hits': capture.leaks, 'source_redactions': capture.source_redactions})
            if code or capture.security_failures: raise RuntimeError('GeoNode command unsuccessful: ' + action)
        if invocation.get('integration'):
            from journey import exercise
            report['journey'] = exercise(invocation, config, values)
            if report['journey']['result_exit_code']: raise RuntimeError('real HTTP journey failed')
        report['result_exit_code'] = 0
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': redact(str(error), values)}
    finally:
        if provision_started:
            try:
                cmd = [invocation['python'], str(HERE / 'manage_fixture.py'), '--config', str(config_path), 'cleanup']
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, errors='replace', env=invocation['environment'])
                capture = Capture(process, output / 'cleanup.log', lambda: values)
                try: code = process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    stop(process, capture)
                    raise RuntimeError('GeoNode credential cleanup timed out')
                capture.finish()
                report['cleanup']['stored_credentials_invalidated'] = code == 0 and capture.security_failures == 0
                if not report['cleanup']['stored_credentials_invalidated']: report['result_exit_code'] = 1
            except Exception as error:
                report['cleanup']['error'] = type(error).__name__
                report['result_exit_code'] = 1
        save(output / 'child-result.json', report)
    return report['result_exit_code']


def run(args):
    import configured_auth_database
    import loopback_exec
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    output.chmod(0o700)
    database = None
    config_path = output / 'private.json'
    result = {'result_exit_code': 1, 'scope': 'source-owned GeoNode component integration; not unified product policy', 'cleanup': {}}
    values = []
    try:
        import installed
        origin_before = installed.verify(args.python)
        save(output / 'installed-origin-before.json', origin_before)
        result['owned_installed_files'] = origin_before['verified_owned_files']
        database = configured_auth_database.start(TASK / 'build-worktrees/postgis-slice/run-003/prefix', TASK / 'build-worktrees/postgis-slice/run-003-evidence-final.json', output / 'database')
        owner_db, runtime_db = configure_database(database, output)
        port = fresh_port()
        config = {'output': str(output), 'database': owner_db, 'runtime_database': runtime_db,
                  'site_url': 'http://127.0.0.1:' + str(port) + '/',
                  'geoserver_url': 'http://127.0.0.1:' + str(fresh_port()) + '/geoserver/',
                  'secret_key': secrets.token_urlsafe(48), 'api_key': secrets.token_urlsafe(36),
                  'client_id': 'fixture-geoserver-' + secrets.token_hex(12), 'client_secret': secrets.token_urlsafe(36),
                  'second_client_id': 'fixture-second-app-' + secrets.token_hex(12), 'second_client_secret': secrets.token_urlsafe(36),
                  'redirect_uri': 'http://127.0.0.1:' + str(port) + '/fixture-callback',
                  'passwords': {name: secrets.token_urlsafe(32) for name in ('fixture-reader', 'fixture-outsider', 'fixture-disabled', 'fixture-admin', 'fixture-unmapped')},
                  'oidc_rsa_private_key_file': str(output / 'oidc-key.pem'), 'strict_verifier': args.strict_verifier,
                  'strict_roles': args.strict_roles, 'role_service_username': 'fixture-role-service',
                  'role_service_api_key': secrets.token_urlsafe(36)}
        if args.strict_roles and (not args.strict_verifier or (args.integration and (not args.build or not args.war_sha256))):
            raise ValueError('strict roles require strict verifier, integration and explicit build/WAR digest')
        values = private_values(config)
        key = subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', config['oidc_rsa_private_key_file']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if key.returncode: raise RuntimeError('disposable RSA key generation failed')
        Path(config['oidc_rsa_private_key_file']).chmod(0o600)
        save(config_path, config, private=True)
        prefix = TASK / 'build-worktrees/postgis-slice/run-003/prefix'
        environment = {'PATH': str(args.python.parent) + ':' + str(prefix / 'bin') + ':/usr/bin:/bin',
                       'HOME': str(output), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                       'LD_LIBRARY_PATH': str(prefix / 'lib') + ':' + str(prefix / 'lib64'),
                       'PROJ_DATA': str(prefix / 'share/proj'), 'PROJ_NETWORK': 'OFF', 'GDAL_DATA': str(prefix / 'share/gdal'),
                       'GDAL_LIBRARY_PATH': str(prefix / 'lib/libgdal.so'), 'GEOS_LIBRARY_PATH': str(prefix / 'lib/libgeos_c.so'),
                       'PYTHONPATH': str(HERE), 'PYTHONNOUSERSITE': '1',
                       'PYTHONPYCACHEPREFIX': str(output / 'python-cache')}
        invocation = {'config': str(config_path), 'python': str(args.python.absolute()), 'environment': environment, 'integration': args.integration}
        if args.integration:
            import combined_logging_probe
            import runtime_inputs
            import toolchain
            build = args.build.resolve() if args.build else TASK / 'build-worktrees/geoserver-auth/aggregate-03'
            expected_war = args.war_sha256 or WAR_SHA256
            build_result = json.loads((build / 'result.json').read_text())
            if args.strict_roles:
                if build_result.get('result_exit_code') != 0:
                    raise ValueError('candidate aggregate build did not succeed')
            tools = TASK / 'build-worktrees/java-resolution/toolchain'
            java_home = tools / 'jdk-17.0.20.1+1'
            manifest = json.loads((HERE.parent / 'java/toolchain-inputs.json').read_text())
            result['toolchain'] = toolchain.verify_extracted(TASK / 'source-archives/java-resolution/toolchain', manifest, tools)
            inventory = combined_logging_probe.packaged_classpath(build, output)
            if inventory['war_sha256'] != expected_war:
                raise ValueError('retained #59 WAR digest mismatch')
            save(output / 'application-inventory.json', inventory)
            result['runtime_inputs'] = runtime_inputs.stage(TASK / 'source-archives/java-http-auth/maven', output / 'servlet')
            result['launcher'] = runtime_inputs.compile_launcher(java_home, output / 'servlet', output / 'launcher')
            invocation['runtime'] = {'source': str(build / 'work/source'), 'java_home': str(java_home),
                'servlet': str(output / 'servlet'), 'launcher': str(output / 'launcher'),
                'war': inventory['war_path'], 'war_sha256': expected_war,
                'database_properties': str(database.properties_path)}
        save(output / 'invocation.json', invocation)
        # Snapshot the exact executed harness so later edits cannot alter retained attempts.
        destination = output / 'tooling'
        for component in ('geonode', 'java', 'postgis'):
            for source in (HERE.parent / component).rglob('*'):
                if source.is_file() and source.suffix in ('.py', '.json', '.java') and '__pycache__' not in source.parts:
                    target = destination / component / source.relative_to(HERE.parent / component)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
        snapshot = {str(p.relative_to(destination)): digest(p) for p in destination.rglob('*') if p.is_file()}
        save(output / 'tooling.json', snapshot)
        invocation['environment']['PYTHONPATH'] = str(destination / 'geonode')
        # The private config is stable throughout each supervised run.
        (output / 'invocation.json').write_text(json.dumps(invocation, indent=2) + '\n')
        command = [sys.executable, str(destination / 'java/loopback_exec.py'), '--evidence', str(output / 'network-loopback.json'), '--timeout', '900', '--', sys.executable, str(destination / 'geonode/run.py'), '--child', str(output / 'invocation.json')]
        with (output / 'supervisor.log').open('x') as log:
            supervisor = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            try:
                returncode = supervisor.wait(timeout=950)
            except subprocess.TimeoutExpired:
                # SIGTERM runs the retained supervisor's process-group cleanup.
                # subprocess.run(timeout=...) would SIGKILL that cleanup owner.
                supervisor.terminate()
                try: supervisor.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    result['cleanup']['supervisor_unresponsive'] = True
                    raise RuntimeError('supervisor did not complete cleanup after termination')
                raise RuntimeError('supervised runtime exceeded parent deadline')
        result['command_exit_code'] = returncode
        result['network'] = loopback_exec.verify_receipt(output / 'network-loopback.json', returncode)
        result['child'] = json.loads((output / 'child-result.json').read_text())
        origin_after = installed.verify(args.python)
        save(output / 'installed-origin-after.json', origin_after)
        if origin_before != origin_after: raise ValueError('installed owned backend changed during execution')
        result['tooling_unchanged'] = all(digest(destination / name) == sha for name, sha in snapshot.items())
        if not result['tooling_unchanged']: raise RuntimeError('executed harness changed')
        result['result_exit_code'] = int(returncode != 0 or result['child']['result_exit_code'] != 0)
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': redact(str(error), values)}
    finally:
        if database is not None:
            try:
                database.stop(); result['database'] = database.receipt
                if not database.receipt.get('stopped') or database.receipt.get('result_exit_code'): result['result_exit_code'] = 1
            except Exception as error:
                result['result_exit_code'] = 1; result['cleanup']['database_error'] = type(error).__name__
        result['cleanup']['private_config_scrubbed'] = True
        for name in ('private.json', 'oidc-key.pem'):
            path = output / name
            try:
                if path.exists(): path.write_text('SCRUBBED DISPOSABLE FIXTURE SECRET\n')
            except Exception as error:
                result['cleanup']['private_config_scrubbed'] = False
                result['cleanup']['scrub_error'] = type(error).__name__
                result['result_exit_code'] = 1
        result['database_supervisor_exception'] = 'Existing #59 limitation: authenticated owned PostgreSQL alone runs outside unchanged supervisor because backend setsid is denied.'
        save(output / 'result.json', result)
    print(json.dumps({'output': str(output), 'result_exit_code': result['result_exit_code'], 'error': result.get('error')}))
    return result['result_exit_code']


if __name__ == '__main__':
    if sys.argv[1:2] == ['--child']:
        raise SystemExit(child(json.loads(Path(sys.argv[2]).read_text())))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--integration', action='store_true')
    parser.add_argument('--strict-verifier', action='store_true')
    parser.add_argument('--strict-roles', action='store_true')
    parser.add_argument('--build', type=Path)
    parser.add_argument('--war-sha256')
    raise SystemExit(run(parser.parse_args()))
