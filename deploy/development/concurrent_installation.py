#!/usr/bin/env python3
"""Finite init/up contention check for one fresh owned developer installation.

First-party GPL-3.0-or-later. Inert tests do not establish installation acceptance.
Only the reviewed bundle launcher and existing owned-container cleanup are used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import lifecycle_check as lifecycle
from installer import bundle, config, runtime
from installer.state import (atomic_write, canonical, checked_path, digest,
                             no_duplicate_keys, private_directory, read_json)

BUSY = 'Another installation command is already running.'
PAIR_TIMEOUT = 1200
OUTPUT_LIMIT = 4 * 1024 * 1024
CHILD_GRACE = 5


def utc():
    return datetime.now(timezone.utc).isoformat()


def group_members(group):
    """Observe only a session created for our CLI; never discover kill targets."""
    if type(group) is not int or group <= 1:
        raise ValueError('Invalid owned child session.')
    members = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == group:
                members.append(int(entry.name))
        except FileNotFoundError:
            continue
    return sorted(members)


def decode(data):
    def invalid_constant(value):
        raise ValueError('Nonfinite CLI JSON.')
    return json.loads(data.decode('utf-8'), object_pairs_hook=no_duplicate_keys,
                      parse_constant=invalid_constant)


class ConcurrentCheck(lifecycle.Check):
    def __init__(self, directory, output):
        super().__init__(directory, output)
        self.record.update({'schema_version': 1, 'task': 'PLT-01', 'gap': 'PLT01-GAP-05',
                       'scope': 'ordinary command concurrency and fixed native identity/policy/metadata preservation',
                       'status': 'running', 'started_at_utc': utc(), 'pairs': [],
                       'full_installation_acceptance': False,
                       'native_uniqueness_acceptance': False,
                       'installed_sql_role_acceptance': False,
                       'health_helper_cleanup_verified': False,
                       'targeted_probe_executed': False, 'persistent_data_deleted': False,
                       'native_identity_and_policy_preserved': False})
        self.root_stamp = None
        self.up_attempted = False

    def save(self):
        value = canonical(self.record)
        if not self.safe(value.decode()):
            raise ValueError('Receipt contains known secret material; withheld.')
        atomic_write(self.output / 'result.json', value, replace=True)

    def prepare(self, source, expected):
        self.bundle_sha256 = expected
        self.bundle_path, self.launcher = lifecycle.relocate(source, expected, self.output / 'relocated-bundle')
        # Keep the fresh root empty: an in-root marker would be unmarked input
        # to init. Bind its inode in the private sibling evidence directory.
        self.directory.mkdir(mode=0o700)
        metadata = private_directory(self.directory).stat()
        self.root_stamp = {'directory': str(self.directory), 'device': metadata.st_dev,
                           'inode': metadata.st_ino, 'uid': metadata.st_uid,
                           'bundle': str(self.bundle_path), 'bundle_sha256': expected}
        atomic_write(self.output / 'installation-marker.json', self.root_stamp)
        self.record['marker'] = {'path': str(self.output / 'installation-marker.json'),
                                 'sha256': digest(self.output / 'installation-marker.json')}
        self.record['bundle'] = {'path': str(self.bundle_path), 'sha256': expected}
        self.save()

    def assert_root(self):
        metadata = private_directory(self.directory).stat()
        if (self.root_stamp is None
                or read_json(self.output / 'installation-marker.json', private=True) != self.root_stamp
                or (metadata.st_dev, metadata.st_ino, metadata.st_uid) !=
                   tuple(self.root_stamp[key] for key in ('device', 'inode', 'uid'))):
            raise ValueError('Synthetic installation marker or directory identity changed.')

    def capture_identity(self):
        self.assert_root()
        current = config.load(self.directory)
        secrets = config.secret_material(self.directory)
        self.secrets = sorted(set(self.secrets) | set(secrets.values()))
        if current['bundle'] != {'path': str(self.bundle_path), 'sha256': self.bundle_sha256}:
            raise ValueError('Installation selected another bundle.')
        product_bytes = (self.directory / 'product.json').read_bytes()
        secret_bytes = (self.directory / 'secrets/product.json').read_bytes()
        if decode(product_bytes) != current or decode(secret_bytes) != secrets:
            raise ValueError('State changed during identity capture.')
        if self.initial_config is None:
            self.initial_config, self.initial_secrets = product_bytes, secret_bytes
        elif (product_bytes, secret_bytes) != (self.initial_config, self.initial_secrets):
            raise ValueError('Installation configuration or credentials changed.')
        facts = {'install_id': current['install_id'],
                 'configuration_sha256': hashlib.sha256(product_bytes).hexdigest(),
                 'credentials_file_sha256': hashlib.sha256(secret_bytes).hexdigest()}
        self.record['identity'] = facts
        self.record['install_id'] = current['install_id']
        return facts

    def result(self, command, child, row):
        code = child['process'].returncode
        stdout, stderr = bytes(child['stdout']), bytes(child['stderr'])
        row.update(returncode=code, outcome='rejected')
        if code == 1 and not stdout.strip():
            value = decode(stderr)
            if value == {'command': command, 'ok': False, 'error': BUSY}:
                row['outcome'] = 'busy'
                return
        if code != 0 or stderr.strip():
            raise ValueError('CLI failed outside the exact lock-busy contract.')
        identity = self.capture_identity()
        if not self.safe(stdout.decode('utf-8')):
            raise ValueError('CLI output contains known credentials.')
        value = decode(stdout)
        if not isinstance(value, dict):
            raise ValueError('CLI output is not an object.')
        current = config.load(self.directory)
        if command == 'init':
            expected = {'command': 'init', 'created': value.get('created'),
                        'install_id': identity['install_id'], 'profile': config.PROFILE,
                        'url': 'http://127.0.0.1:' + str(current['listen']['port']),
                        'credentials_file': str(self.directory / 'secrets/product.json')}
            if type(value.get('created')) is not bool or value != expected:
                raise ValueError('Unexpected init identity or result shape.')
            row['outcome'] = 'created' if value['created'] else 'existing'
        else:
            expected_network = {'name': config.project_name(current) + '_internal', 'internal': True,
                                'ipv6_enabled': False, 'driver': 'bridge', 'verified': True}
            if (set(value) != {'command', 'install_id', 'ready', 'readiness', 'services', 'network'}
                    or value['command'] != 'up' or value['install_id'] != identity['install_id']
                    or value['ready'] is not True
                    or value['readiness'] != {'ready': True, 'checks': dict.fromkeys(
                        ('catalog', 'database', 'map', 'query'), True)}
                    or value['network'] != expected_network
                    or value['network'].get('internal') is not True
                    or value['network'].get('ipv6_enabled') is not False
                    or value['network'].get('verified') is not True
                    or value['readiness'].get('ready') is not True
                    or any(flag is not True for flag in value['readiness']['checks'].values())
                    or not isinstance(value['services'], dict)
                    or set(value['services']) != set(bundle.SERVICES)
                    or any(not isinstance(state, dict) or set(state) != {'process', 'engine_health'}
                           or state['process'] != 'running'
                           or state['engine_health'] not in ('healthy', 'starting', 'unhealthy', 'unavailable')
                           for state in value['services'].values())):
                raise ValueError('Up did not return the exact ready installation.')
            row['outcome'] = 'ready'
        row['identity'] = identity

    def cleanup_children(self, children):
        facts = {'complete': True, 'sessions': [], 'scope': 'only launched CLI child process groups'}
        # Signal a group only while its original, unreaped Popen leader is alive.
        # Never kill by a PID discovered in /proc or adopt a leftover group.
        for child in children:
            process = child['process']
            item = {'pid': process.pid, 'term_sent': False, 'kill_sent': False}
            facts['sessions'].append(item)
            try:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM); item['term_sent'] = True
            except ProcessLookupError:
                pass
            except Exception as error:
                item['signal_error_type'] = type(error).__name__; facts['complete'] = False
        deadline = time.monotonic() + CHILD_GRACE
        while any(child['process'].poll() is None for child in children) and time.monotonic() < deadline:
            time.sleep(0.02)
        for child, item in zip(children, facts['sessions']):
            process = child['process']
            try:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL); item['kill_sent'] = True
                process.wait(timeout=CHILD_GRACE)
                item['reaped'] = True
                item['remaining_group_members'] = group_members(process.pid)
                if item['remaining_group_members']:
                    facts['complete'] = False
            except Exception as error:
                item['error_type'] = type(error).__name__; facts['complete'] = False
            finally:
                for stream in (process.stdout, process.stderr):
                    stream.close()
        return facts

    def pair(self, command, *, reinitialize=False):
        if command not in ('init', 'up') or type(reinitialize) is not bool or (reinitialize and command != 'init'):
            raise ValueError('Only the finite fresh init, existing init and up pairs are supported.')
        self.assert_root()
        if command == 'up' or reinitialize:
            self.capture_identity()
        # Revalidate the exact relocated closure immediately before each pair.
        bundle.load(self.bundle_path, self.bundle_sha256)
        arguments = [str(self.launcher), command, '--directory', str(self.directory)]
        if command == 'init':
            arguments += ['--bundle', str(self.bundle_path), '--bundle-sha256', self.bundle_sha256]
        environment = {'HOME': str(self.output), 'PATH': str(self.launcher.parent),
                       'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'PYTHONNOUSERSITE': '1',
                       'PYTHONSAFEPATH': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
        facts = {'command': command, 'reinitialize': reinitialize, 'started_at_utc': utc(), 'argv': arguments,
                 'launch_overlap_observed': False, 'lock_contention_observed': False,
                 'children': []}
        self.record['pairs'].append(facts)
        children = []
        started = time.monotonic()
        try:
            with selectors.DefaultSelector() as selector:
                for index in range(2):
                    # A completed first child proves no overlap. Do not replay.
                    if index and children[0]['process'].poll() is not None:
                        raise ValueError('The first command finished before its peer launched.')
                    if command == 'up':
                        self.up_attempted = True
                    process = subprocess.Popen(arguments, cwd=self.output, env=environment,
                                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE, start_new_session=True)
                    child = {'process': process, 'stdout': bytearray(), 'stderr': bytearray(),
                             'open_streams': 2, 'done': False}
                    children.append(child)
                    row = {'index': index, 'pid': process.pid, 'launched_at_utc': utc(),
                           'launch_elapsed_seconds': time.monotonic() - started,
                           'outcome': 'pending', 'stdout_bytes': 0, 'stderr_bytes': 0}
                    facts['children'].append(row)
                    for name in ('stdout', 'stderr'):
                        stream = getattr(process, name)
                        os.set_blocking(stream.fileno(), False)
                        selector.register(stream, selectors.EVENT_READ, (index, name))
                    if index:
                        facts['launch_overlap_observed'] = children[0]['process'].poll() is None
                        if not facts['launch_overlap_observed']:
                            raise ValueError('CLI launch overlap was not observed.')
                while not all(child['done'] for child in children):
                    if time.monotonic() - started >= PAIR_TIMEOUT:
                        raise TimeoutError('Concurrent CLI pair timed out.')
                    for key, _ in selector.select(timeout=0.05):
                        index, name = key.data; child = children[index]
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            child['open_streams'] -= 1
                            continue
                        facts['children'][index][name + '_bytes'] += len(chunk)
                        if len(child['stdout']) + len(child['stderr']) + len(chunk) > OUTPUT_LIMIT:
                            raise ValueError('CLI output exceeded the streaming bound.')
                        child[name].extend(chunk)
                    for index, child in enumerate(children):
                        code = child['process'].poll()
                        if not child['done'] and code is not None and child['open_streams'] == 0:
                            facts['children'][index]['completed_at_utc'] = utc()
                            self.result(command, child, facts['children'][index])
                            facts['lock_contention_observed'] |= facts['children'][index]['outcome'] == 'busy'
                            child['done'] = True
                outcomes = [row['outcome'] for row in facts['children']]
                facts['lock_contention_observed'] = 'busy' in outcomes
                if command == 'init':
                    if reinitialize:
                        if 'existing' not in outcomes or any(x not in ('existing', 'busy') for x in outcomes):
                            raise ValueError('Repeated init pair must preserve only the existing installation.')
                    elif outcomes.count('created') != 1 or any(x not in ('created', 'existing', 'busy') for x in outcomes):
                        raise ValueError('Init pair did not create exactly one installation.')
                elif 'ready' not in outcomes or any(x not in ('ready', 'busy') for x in outcomes):
                    raise ValueError('Up pair has no successful ready peer.')
                facts['identity_after'] = self.capture_identity()
        except BaseException as error:
            facts['error_type'] = type(error).__name__
            raise
        finally:
            facts['child_cleanup'] = self.cleanup_children(children)
            facts['completed_at_utc'] = utc()
        if not facts['child_cleanup']['complete']:
            raise ValueError('CLI child cleanup is uncertain; reconciliation required.')
        self.save()
        return facts

    def exercise(self, source, expected):
        self.prepare(source, expected)
        self.pair('init')
        self.pair('up')
        self.rt = runtime.Runtime(self.directory)
        observed = self.rt.processes(include_initializers=True)
        if (any(observed[role]['process'] != 'running' for role in bundle.SERVICES)
                or any(observed[role]['process'] == 'running' for role in ('catalog-init', 'geoserver-init'))
                or self.rt.network() is None):
            raise ValueError('Owned service state differs after concurrent up.')
        # Only selected finite process facts; native principals and SQL grants
        # are deliberately not inferred from these installation observations.
        self.record['owned_processes_after_up'] = observed
        self.capture_identity()
        title = self.protected_journey('native baseline before repeated concurrent commands')
        self.pair('init', reinitialize=True)
        self.pair('up')
        # The inherited method reads the old title before a journey can edit it,
        # and compares native principal/resource IDs and restored policy hashes.
        self.protected_journey('native state after repeated concurrent commands', title)
        self.capture_identity()
        self.record['native_identity_and_policy_preserved'] = True
        self.record['native_preservation_scope'] = 'fixed diagnostic item, owner/viewer IDs and native object policy; not full migration or database cardinality'

    def shutdown(self):
        if not self.up_attempted:
            return {'attempted': False, 'complete': True, 'reason': 'up_not_attempted',
                    'persistent_data_preserved': True}
        if any(not pair.get('child_cleanup', {}).get('complete', False) for pair in self.record['pairs']):
            raise ValueError('CLI workers may remain; concurrent engine cleanup is unsafe.')
        self.assert_root()
        self.capture_identity()
        self.rt = runtime.Runtime(self.directory)
        result = lifecycle.Check.stop_owned(self)
        self.capture_identity()
        return result


def main(args):
    directory, output = checked_path(args.directory), checked_path(args.output)
    if (directory.exists() or output.exists() or directory == output
            or directory in output.parents or output in directory.parents):
        raise ValueError('Installation and evidence must be distinct fresh, nonnested paths.')
    output.mkdir(mode=0o700, parents=True)
    check = ConcurrentCheck(directory, output)
    check.record['sources'] = [{'path': str(path), 'sha256': digest(path)} for path in (
        Path(__file__), Path(lifecycle.__file__), ROOT / 'installer/config.py',
        ROOT / 'installer/runtime.py', ROOT / 'installer/state.py', ROOT / 'installer/bundle.py',
        Path(lifecycle.journey_module.__file__), lifecycle.journey_module.POLICY_PROGRAM, lifecycle.journey_module.CLIENT)]
    passed = False
    previous = signal.getsignal(signal.SIGTERM)
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        check.exercise(args.bundle, args.bundle_sha256)
        passed = True
    except (Exception, KeyboardInterrupt) as error:
        check.record['error_type'] = type(error).__name__
    finally:
        try:
            check.record['shutdown'] = check.shutdown()
            if check.record['shutdown'].get('complete') is False:
                passed = False
        except (Exception, KeyboardInterrupt) as error:
            passed = False
            check.record['shutdown'] = {'complete': False, 'error_type': type(error).__name__,
                                        'reconciliation_required': True, 'persistent_data_preserved': True}
        status = 'passed' if passed else 'failed'
        if passed and check.record['incomplete_checks']:
            status = 'incomplete'
        check.record.update(status=status, completed_at_utc=utc())
        try:
            check.save()
        finally:
            signal.signal(signal.SIGTERM, previous)
    print(json.dumps({'status': check.record['status'], 'receipt': str(output / 'result.json')}))
    return 0 if check.record['status'] == 'passed' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(main(parser.parse_args()))
