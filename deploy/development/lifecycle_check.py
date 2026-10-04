#!/usr/bin/env python3
"""Actual ordinary developer-installation lifecycle; preserves all persistent data.

This does not run the held container vulnerability probe or qualify a release.
Only the exact reviewed bundle and this invocation's fresh installation are used.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from installer import bundle, config, runtime
from installer.state import checked_path, digest
from installer.diagnostics import from_cli

spec = importlib.util.spec_from_file_location('ordinary_installation_journey', ROOT / 'deploy/development/journey_probe.py')
journey_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = journey_module
spec.loader.exec_module(journey_module)
dns_spec = importlib.util.spec_from_file_location('ordinary_dns_observation', ROOT / 'deploy/development/dns_observation.py')
dns_module = importlib.util.module_from_spec(dns_spec)
sys.modules[dns_spec.name] = dns_module
dns_spec.loader.exec_module(dns_module)


DNS_UNAVAILABLE = frozenset({'observation_permission', 'observation_unavailable', 'namespace_binding_unavailable'})


def utc():
    return datetime.now(timezone.utc).isoformat()


def relocate(source, expected, destination):
    """Copy exactly the reviewed closure and archive inputs, then verify again."""
    source = checked_path(source)
    value = bundle.load(source, expected)
    destination = checked_path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    closure = json.loads(bundle.member(source.parent, value['runtime']['files_manifest']).read_bytes())
    for name in closure['roots']:
        original = bundle.relative(source.parent, name)
        target = destination / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copytree(original, target, symlinks=True)
    paths = {source.name, value['source_manifest']['path'], value['runtime']['files_manifest']['path'],
             value['runtime']['prerequisites']['path'], *(image['archive'] for image in value['images'].values())}
    for name in sorted(paths):
        original = bundle.relative(source.parent, name)
        target = destination / name
        if target.exists():
            if not target.is_file() or digest(target) != digest(original):
                raise ValueError('overlapping relocated bundle member differs')
            continue
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        target.chmod(original.stat().st_mode & 0o777)
    relocated = destination / source.name
    bundle.load(relocated, expected)
    launcher = destination / 'bin/ambisgis'
    names, _ = bundle.verify_manifest(destination, value['runtime']['files_manifest'])
    if 'bin/ambisgis' not in names or not os.access(launcher, os.X_OK):
        raise ValueError('the actual CLI launcher must be in the verified closure')
    return relocated, launcher


class Check:
    def __init__(self, directory, output):
        self.directory = directory
        self.output = output
        self.record = {'schema_version': 1, 'task': 'PLT-01', 'status': 'running', 'started': utc(),
                       'full_installation_acceptance': False, 'targeted_probe_executed': False,
                       'scope': 'Actual ordinary CLI, bundle relocation, persistent identity/metadata, service fault/recovery, read-only native DNS observations and shutdown only',
                       'stages': [], 'token_cleanup': [], 'persistent_data_deleted': False}
        self.secrets = []
        self.browsers = []
        self.launcher = None
        self.bundle_path = None
        self.bundle_sha256 = None
        self.initial_config = None
        self.initial_secrets = None
        self.rt = None
        self.native_identity = None
        self.native_policy_sha256 = None
        self.dns_expectation = None
        self.dns_running = None
        self.record['incomplete_checks'] = []

    def safe(self, text):
        return not any(value in text for value in self.secrets) and not any(
            browser.secrets.matches(text) for browser in self.browsers)

    def save(self):
        text = json.dumps(self.record, indent=2, sort_keys=True) + '\n'
        if not self.safe(text):
            raise RuntimeError('sensitive evidence was withheld')
        (self.output / 'result.json').write_text(text)
        (self.output / 'result.json').chmod(0o600)

    def stage(self, name, facts):
        self.record['stages'].append({'name': name, 'at': utc(), 'facts': facts})
        self.save()
        print(json.dumps({'stage': name, 'completed': True}), flush=True)

    def cli(self, command, *, expected=0):
        args = [str(self.launcher), command, '--directory', str(self.directory)]
        if command == 'init':
            args += ['--bundle', str(self.bundle_path), '--bundle-sha256', self.bundle_sha256]
        # Host bootstrap trust is recorded by the bundle. Selected subprocesses
        # receive no caller loader/Python/provider configuration.
        env = {'HOME': str(self.output), 'PATH': str(self.launcher.parent), 'LANG': 'C.UTF-8',
               'LC_ALL': 'C.UTF-8', 'PYTHONNOUSERSITE': '1', 'PYTHONSAFEPATH': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
        done = subprocess.run(args, cwd=self.output, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200)
        combined = done.stdout + done.stderr
        if len(combined) > 4 * 1024 * 1024 or not self.safe(combined.decode('utf-8', errors='replace')):
            raise RuntimeError('bounded CLI diagnostics failed safe evidence checks')
        if done.returncode != expected:
            self.record['cli_failure'] = {'command': command, 'returncode': done.returncode,
                                         'stdout_bytes': len(done.stdout), 'stderr_bytes': len(done.stderr)}
            failure = from_cli(done.stderr, command)
            if failure is not None:
                self.record['cli_failure']['startup_failure'] = failure
            raise RuntimeError('ordinary CLI stage failed')
        value = json.loads(done.stdout)
        if value.get('command') != command:
            raise ValueError('CLI result identity differs')
        return value

    def preserve_identity(self):
        if ((self.directory / 'product.json').read_bytes() != self.initial_config
                or (self.directory / 'secrets/product.json').read_bytes() != self.initial_secrets):
            raise ValueError('installation identity or credential material changed')

    def wait_ready(self, ready=True, timeout=180):
        deadline = time.monotonic() + timeout
        while True:
            value = self.rt.status()
            running = all(row['process'] == 'running' for row in value['services'].values())
            if value['readiness']['ready'] is ready and (running or not ready):
                return value
            if time.monotonic() >= deadline:
                raise TimeoutError('bounded useful-readiness wait failed')
            time.sleep(1)

    def metadata(self, title):
        exercise = journey_module.Journey(self.directory)
        try:
            _, tokens = exercise.login('owner')
            code, raw = exercise.request('/api/v1/installation/sample', token=tokens.access_token)
            if code != 200 or json.loads(raw).get('title') != title:
                raise ValueError('previous metadata edit did not survive lifecycle operation')
        finally:
            cleanup = exercise.cleanup_tokens()
            self.record['token_cleanup'].append(cleanup)
            self.browsers += [browser for _, browser in exercise.browsers]
            if not cleanup['complete']:
                raise RuntimeError('lifecycle token cleanup incomplete')

    def prepare_dns_observation(self):
        if self.rt.selection['runtime'].get('dns_profile') != 'native-direct-v1':
            self.record['dns_profile_observation'] = 'not selected by this bundle'
            return
        manifest = json.loads(bundle.member(self.rt.bundle_root,
            self.rt.selection['runtime']['files_manifest']).read_bytes())
        self.dns_expectation = dns_module.from_verified(self.directory, self.rt.config,
            self.rt.bundle_root, manifest, os.getuid())

    def observe_dns(self, name):
        if self.dns_expectation is None:
            return
        value = dns_module.observe_running(self.dns_expectation)
        self.record.setdefault('dns_observations', []).append({'at': utc(), 'stage': name, 'result': value})
        unavailable = value['status'] == 'unsupported' and value['classification'] in DNS_UNAVAILABLE
        if value.get('identity_verified') is True and (value['status'] == 'verified' or unavailable):
            self.dns_running = value
        if unavailable:
            self.record['incomplete_checks'].append({'stage': name, 'classification': value['classification']})
        self.save()
        if value['status'] != 'verified' and not unavailable:
            raise RuntimeError('native DNS identity observation failed')
        self.stage(name, {'observation_status': value['status'],
                         'classification': value['classification'],
                         'identity_verified': value.get('identity_verified') is True,
                         'namespace_binding_verified': value.get('namespace_binding_verified') is True})

    def observe_dns_stopped(self, timeout=15):
        if self.dns_expectation is None:
            return None
        if self.dns_running is None:
            return {'status': 'unobserved', 'classification': 'no_prior_identity',
                    'cleanup_verified': False, 'daemon_cleanup_verified': False}
        deadline = time.monotonic() + timeout
        observations = []
        while True:
            value = dns_module.observe_stopped(self.dns_expectation, self.dns_running)
            observations.append({'at': utc(), 'result': value})
            # Only native asynchronous process/file removal is pollable. An
            # identity mismatch, PID reuse or unavailable read is not retried.
            if (value['classification'] not in dns_module.TRANSIENT_CLEANUP
                    or time.monotonic() >= deadline):
                break
            time.sleep(0.25)
        self.record.setdefault('dns_cleanup', []).append(observations)
        unavailable = value['status'] == 'unsupported' and value['classification'] in DNS_UNAVAILABLE
        if unavailable:
            self.record['incomplete_checks'].append({'stage': 'DNS shutdown',
                                                     'classification': value['classification']})
        self.save()
        if (value['status'] != 'verified' and not unavailable) or (
                value['status'] == 'verified' and value.get('cleanup_verified') is not True):
            raise RuntimeError('native DNS cleanup observation failed')
        return value

    def stop_owned(self):
        if self.rt is None:
            return {'attempted': False, 'reason': 'no runtime invocation was reached'}
        observed = self.rt.processes(include_initializers=True)
        names = [config.project_name(self.rt.config) + '-' + role for role, row in observed.items()
                 if row['process'] == 'running']
        if names:
            self.rt.engine('stop', '--time', '45', *names, timeout=300)
        after = self.rt.processes(include_initializers=True)
        if any(row['process'] == 'running' for row in after.values()):
            raise RuntimeError('owned installation services did not stop')
        result = {'attempted': True, 'running_services': 0, 'persistent_data_preserved': True}
        dns = self.observe_dns_stopped()
        if dns is not None: result['dns'] = dns
        return result

    def protected_journey(self, name, expected_title=None):
        # Persistence assertions MUST precede a journey that can edit metadata.
        if expected_title is not None:
            self.metadata(expected_title)
            self.preserve_identity()
        journey = journey_module.Journey(self.directory)
        try:
            result = journey.run()
        finally:
            self.record['token_cleanup'].append(journey.cleanup_result)
            self.record.setdefault('permission_cleanup', []).append(journey.permission_cleanup)
            self.browsers += [browser for _, browser in journey.browsers]
        identity = result['native_item_permission_roundtrip']['identity']
        policy = result['native_item_permission_roundtrip']['restoration']['native']['after_sha256']
        if self.native_identity is None:
            self.native_identity, self.native_policy_sha256 = identity, policy
        elif self.native_identity != identity or self.native_policy_sha256 != policy:
            raise ValueError('native principals/resource/permissions changed across lifecycle')
        if expected_title is not None and result['retained_metadata_title'] != expected_title:
            raise ValueError('repeated journey changed retained metadata expectation')
        self.preserve_identity()
        row = {'stage': name, 'result': result, 'requests': journey.rows, 'permission_events': journey.permission_events}
        self.record.setdefault('http_journeys', []).append(row)
        if 'http_journey' not in self.record: self.record['http_journey'] = row
        self.stage(name, {'completed': True, 'native_identity_and_permissions_preserved': True})
        return result['retained_metadata_title']

    def exercise(self, args):
        self.bundle_path, self.launcher = relocate(args.bundle, args.bundle_sha256, self.output / 'relocated-bundle')
        self.bundle_sha256 = args.bundle_sha256
        self.stage('verified relocated bundle', {'bundle_sha256': self.bundle_sha256,
                   'original': str(args.bundle), 'relocated': str(self.bundle_path)})
        first = self.cli('init')
        if first.get('created') is not True:
            raise ValueError('first initialization must create a new installation')
        self.initial_config = (self.directory / 'product.json').read_bytes()
        self.initial_secrets = (self.directory / 'secrets/product.json').read_bytes()
        self.secrets = list(config.secret_material(self.directory).values())
        self.record['install_id'] = first['install_id']
        self.rt = runtime.Runtime(self.directory)
        self.prepare_dns_observation()
        self.stage('fresh init', {'created': True, 'install_id': first['install_id']})
        value = self.cli('up')
        if value.get('ready') is not True:
            raise ValueError('fresh up did not become useful')
        self.preserve_identity()
        for command in ('status', 'doctor'):
            if self.cli(command)['readiness']['ready'] is not True:
                raise ValueError('running CLI readiness failed')
        self.stage('fresh up status doctor', {'useful_readiness': True})
        self.observe_dns('native DNS after initial CLI exit')
        title = self.protected_journey('protected map query metadata journey')
        self.stop_owned()
        self.preserve_identity()
        self.stage('stopped persistent installation', {'identity_and_credentials_unchanged': True})
        name = config.project_name(self.rt.config)
        self.rt.engine('start', name + '-database', timeout=90)
        deadline = time.monotonic() + 90
        while True:
            code, _ = self.rt.engine('exec', name + '-database', '/opt/ambisgis/bin/health', 'database', allow_failure=True)
            if code == 0:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('database restart readiness failed')
            time.sleep(1)
        self.rt.engine('start', *[name + '-' + role for role in ('catalog', 'geoserver', 'gateway')], timeout=180)
        self.wait_ready()
        self.metadata(title)
        self.preserve_identity()
        self.stage('restart preserves metadata and credentials', {'verified': True})
        self.observe_dns('native DNS after restart')
        self.protected_journey('full protected journey after restart', title)
        repeated = self.cli('init')
        if repeated.get('created') is not False or repeated['install_id'] != first['install_id']:
            raise ValueError('reinitialization changed installation identity')
        self.preserve_identity()
        if self.cli('up').get('ready') is not True:
            raise ValueError('repeated up failed')
        self.metadata(title)
        self.preserve_identity()
        self.stage('reinitialization preserves metadata and credentials', {'verified': True})
        self.observe_dns('native DNS after repeated CLI exit')
        self.protected_journey('full protected journey after reinitialization', title)
        self.rt.engine('stop', '--time', '45', name + '-geoserver', timeout=90)
        down = self.wait_ready(False, timeout=30)
        if down['readiness'].get('checks', {}).get('map') is not False:
            raise ValueError('renderer fault was not reflected in map readiness')
        diagnostic = self.cli('doctor', expected=1)
        if diagnostic['readiness']['ready'] is not False:
            raise ValueError('doctor concealed a stopped dependency')
        live_probe = journey_module.Journey(self.directory)
        live_code, live_body = live_probe.request('/health/live')
        if (down['services']['gateway']['process'] != 'running' or live_code != 200
                or json.loads(live_body).get('install_id') != self.record['install_id']
                or json.loads(live_body).get('live') is not True):
            raise ValueError('gateway liveness was not preserved during renderer fault')
        self.stage('stopped renderer produces useful failure', {'readiness': down['readiness'], 'doctor_exit': 1,
                   'gateway_process': 'running', 'gateway_live_status': live_code, 'live_request': live_probe.rows})
        self.rt.engine('start', name + '-geoserver', timeout=90)
        self.wait_ready()
        self.metadata(title)
        self.preserve_identity()
        self.stage('dependency recovery preserves state', {'verified': True})
        self.observe_dns('native DNS after dependency recovery')
        self.protected_journey('full protected journey after dependency recovery', title)


def main(args):
    os.umask(0o077)
    directory, output = checked_path(args.directory), checked_path(args.output)
    if directory.exists() or output.exists() or directory.is_relative_to(output) or output.is_relative_to(directory):
        raise ValueError('fresh distinct installation and evidence paths are required')
    output.mkdir(mode=0o700, parents=True)
    check = Check(directory, output)
    check.record['source'] = {str(p.relative_to(ROOT)): digest(p) for p in
        (Path(__file__).resolve(), ROOT / 'deploy/development/journey_probe.py', journey_module.POLICY_PROGRAM,
         ROOT / 'build-support/geonode/protocol_probe.py', ROOT / 'deploy/development/dns_observation.py')}
    passed = False
    try:
        check.exercise(args)
        passed = True
    except Exception as error:
        check.record['error_type'] = type(error).__name__
    finally:
        try:
            check.record['shutdown'] = check.stop_owned()
        except Exception as error:
            check.record['shutdown'] = {'complete': False, 'error_type': type(error).__name__}
            passed = False
        status = 'passed' if passed else 'failed'
        if passed and check.record['incomplete_checks']:
            status, passed = 'incomplete', False
        check.record.update(status=status, finished=utc())
        check.save()
    print(json.dumps({'status': check.record['status'], 'receipt': str(output / 'result.json')}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(main(parser.parse_args()))
