"""Synthetic wire/identity fixtures only; no engine, socket or live process."""
from contextlib import nullcontext
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import dns_function as dns
from installer import config

wire = dns.wire
RESOLVER = b'# synthetic managed resolver\nnameserver 10.87.0.1\nsearch dns.podman\n'
# Independent literal response: ID1234, authoritative success, one question/A.
RESPONSE = bytes.fromhex('1234850000010001000000000864617461626173650000010001'
                         'c00c000100010000001e00040a570002')


def identities():
    product = {'install_id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'}
    project = config.project_name(product)
    selection = {'images': {role: {'image_id': 'sha256:' + str(i) * 64}
                           for i, role in enumerate(('database', 'gateway'), 1)}}
    network = {'name': project + '_internal', 'id': '3' * 64, 'driver': 'bridge',
               'internal': True, 'ipv6_enabled': False, 'dns_enabled': True,
               'labels': {'org.ambisgis.install-id': product['install_id']},
               'subnets': [{'subnet': '10.87.0.0/24', 'gateway': '10.87.0.1'}]}
    rows = []
    for index, role in enumerate(('database', 'gateway'), 2):
        rows.append({'Id': str(index + 2) * 64, 'Name': project + '-' + role,
                     'Image': selection['images'][role]['image_id'],
                     'Config': {'Labels': {'org.ambisgis.install-id': product['install_id'], 'org.ambisgis.role': role}},
                     'State': {'Running': True, 'Pid': 4321, 'StartedAt': 'synthetic-start'},
                     'OCIConfigPath': '/synthetic/config.json', 'ResolvConfPath': '/synthetic/resolv.conf', 'HostConfig': {'Dns': [], 'DnsOptions': [], 'DnsSearch': []},
                     'NetworkSettings': {'Networks': {network['name']: {'IPAddress': '10.87.0.' + str(index),
                         'IPPrefixLen': 24, 'Gateway': '10.87.0.1', 'NetworkID': network['id'], 'Aliases': [role]}}}})
    return product, selection, network, *rows


def receipt():
    return {'schema_version': 1, 'status': 'verified', 'resolver': '10.87.0.1',
            'resolver_config_sha256': hashlib.sha256(RESOLVER).hexdigest(),
            'question': 'database.', 'type': 'A', 'class': 'IN', 'peer': ['10.87.0.1', 53],
            'query_hex': '1234010000010000000000000864617461626173650000010001',
            'response_hex': RESPONSE.hex(), 'answer': '10.87.0.2'}


class InertOnly(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'):
            guard = patch(target, side_effect=AssertionError('native/network producer forbidden'))
            guard.start(); self.addCleanup(guard.stop)


class WireTests(InertOnly):
    def test_literal_fixture_and_exact_query(self):
        self.assertEqual(wire.query(0x1234).hex(), receipt()['query_hex'])
        self.assertEqual(wire.answer(RESPONSE, 0x1234), '10.87.0.2')
        uncompressed = RESPONSE[:26] + b'\x08database\x00' + RESPONSE[28:]
        self.assertEqual(wire.answer(uncompressed, 0x1234), '10.87.0.2')

    def test_every_truncation_and_extra_bytes_fail(self):
        for end in range(len(RESPONSE)):
            with self.subTest(end=end), self.assertRaises(ValueError): wire.answer(RESPONSE[:end], 0x1234)
        for raw in (RESPONSE + b'\0', b'\0' * 513):
            with self.assertRaises(ValueError): wire.answer(raw, 0x1234)

    def test_header_errors_and_ambiguous_records_fail(self):
        for offset, value in [(0, 0x1235), (2, 0x0100), (2, 0x8700), (2, 0x8503),
                              (2, 0x8d00), (2, 0x8540), (4, 0), (4, 2), (6, 0), (6, 2), (8, 1), (10, 1)]:
            raw = bytearray(RESPONSE); raw[offset:offset + 2] = struct.pack('!H', value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError): wire.answer(bytes(raw), 0x1234)

    def test_wrong_question_answer_type_owner_and_class_fail(self):
        for offset, data in [(13, b'x'), (22, b'\x00\x1c'), (24, b'\x00\x03'),
                             (28, b'\x00\x05'), (30, b'\x00\x03'), (36, b'\x00\x03'), (38, b'\x7f\0\0\1')]:
            raw = bytearray(RESPONSE); raw[offset:offset + len(data)] = data
            with self.subTest(offset=offset), self.assertRaises(ValueError): wire.answer(bytes(raw), 0x1234)

    def test_compression_forward_self_header_and_loops_reject(self):
        for pointer in (b'\xc0\x1a', b'\xc0\x1c', b'\xc0\x00', b'\xff\xff'):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                wire.answer(RESPONSE[:26] + pointer + RESPONSE[28:], 0x1234)
        for raw in (b'\0' * 12 + b'\x40bad', b'\0' * 12 + b'\x01\xff\0',
                    b'\0' * 12 + b'\x01x\xc0\x0c'):
            with self.assertRaises(ValueError): wire.name(raw, 12)

    def test_resolver_requires_one_private_ipv4_without_fallback(self):
        self.assertEqual(wire.resolver_config(RESOLVER), '10.87.0.1')
        for raw in (b'', b'nameserver 8.8.8.8\n', b'nameserver 127.0.0.1\n', b'nameserver ::1\n',
                    b'nameserver 0.0.0.0\n', b'nameserver 169.254.1.1\n', b'nameserver 224.0.0.1\n',
                    b'nameserver 10.87.0.1 10.87.0.2\n', RESOLVER + RESOLVER, b'bad directive\n',
                    b'nameserver 010.87.0.1\n', b'#' * 4097, b'\xff'):
            with self.subTest(raw=raw[:35]), self.assertRaises(ValueError): wire.resolver_config(raw)

    def socket_run(self, response=RESPONSE, peer=('10.87.0.1', 53), stdin=b'', argv=None, failure=None):
        connection = Mock(); connection.__enter__ = Mock(return_value=connection); connection.__exit__ = Mock(return_value=False)
        connection.sendto.return_value = 26
        if failure: connection.recvfrom.side_effect = failure
        else: connection.recvfrom.return_value = (response, peer)
        with patch.object(wire, 'read_resolver', return_value=RESOLVER), \
                patch.object(wire.sys, 'argv', ['-c'] if argv is None else argv), \
                patch.object(wire.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(stdin))), \
                patch.object(wire.os, 'urandom', return_value=b'\x12\x34'), \
                patch.object(wire.socket, 'socket', return_value=connection) as create:
            try: result = wire.run()
            finally: self.last_create, self.last_connection = create, connection
        return result

    def test_exact_udp_exchange_uses_no_hosts_or_name_resolver(self):
        self.assertEqual(self.socket_run(), receipt())
        self.last_create.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_connection.settimeout.assert_called_once_with(3)
        self.last_connection.sendto.assert_called_once_with(bytes.fromhex(receipt()['query_hex']), ('10.87.0.1', 53))
        self.last_connection.recvfrom.assert_called_once_with(513)

    def test_input_and_arguments_rejected_before_socket(self):
        for kwargs in ({'stdin': b'x'}, {'argv': ['-c', '8.8.8.8']}, {'argv': ['-c', 'other.example']}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.socket_run(**kwargs)
            self.last_create.assert_not_called()

    def test_wrong_peer_timeout_and_invalid_response_never_retry(self):
        for kwargs, error in [({'peer': ('10.87.0.9', 53)}, ValueError),
                              ({'peer': ('10.87.0.1', 54)}, ValueError),
                              ({'failure': TimeoutError('synthetic')}, TimeoutError),
                              ({'response': RESPONSE + b'x'}, ValueError)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(error): self.socket_run(**kwargs)
            self.last_connection.sendto.assert_called_once()
            self.last_connection.recvfrom.assert_called_once()

    def test_error_output_is_fixed_and_does_not_disclose_exception(self):
        for error, code in ((TimeoutError('private-token'), 'dns_timeout'),
                            (OSError('private-token'), 'dns_check_failed'), (ValueError('private-token'), 'dns_check_failed')):
            output = io.StringIO()
            with patch.object(wire, 'run', side_effect=error), patch.object(wire.sys, 'stdout', output):
                self.assertEqual(wire.main(), 1)
            self.assertEqual(json.loads(output.getvalue()), {'status': 'failed', 'classification': code})


class IdentityTests(InertOnly):
    def test_native_expected_address_is_independent_of_dns_answer(self):
        value = dns.expected(*identities(), RESOLVER)
        self.assertEqual(value['database_ip'], '10.87.0.2')
        self.assertEqual(value['resolver'], '10.87.0.1')
        self.assertEqual(dns.verified_response(json.dumps(receipt()).encode(), value), receipt())

    def test_network_and_container_drift_fail(self):
        changes = [(2, ('internal',), False), (2, ('ipv6_enabled',), True), (2, ('dns_enabled',), False),
                   (2, ('driver',), 'other'), (2, ('id',), 'not-id'), (2, ('network_dns_servers',), ['8.8.8.8']),
                   (2, ('labels', 'org.ambisgis.install-id'), 'other'),
                   (3, ('State', 'Running'), False), (3, ('Config', 'Labels', 'org.ambisgis.role'), 'gateway'),
                   (3, ('Image',), 'sha256:' + '0' * 64), (4, ('Id',), 'not-id'),
                   (4, ('Name',), 'unrelated'), (4, ('HostConfig', 'Dns'), ['8.8.8.8']),
                   (4, ('HostConfig', 'DnsOptions'), ['rotate']), (4, ('HostConfig', 'DnsSearch'), ['other'])]
        for index, path, replacement in changes:
            data = list(identities()); row = data[index]
            for key in path[:-1]: row = row[key]
            row[path[-1]] = replacement
            with self.subTest(path=path), self.assertRaises(ValueError): dns.expected(*data, RESOLVER)

    def test_addresses_aliases_subnets_and_resolver_must_correspond(self):
        for key, value in [('IPAddress', '10.88.0.2'), ('IPAddress', '10.87.0.1'), ('IPAddress', '10.87.0.255'),
                           ('IPPrefixLen', 16), ('IPPrefixLen', True), ('NetworkID', 'f' * 64),
                           ('Gateway', '10.87.0.9'), ('Aliases', ['other']), ('Aliases', 'other-database'),
                           ('GlobalIPv6Address', '::1'), ('SecondaryIPAddresses', ['10.87.0.7'])]:
            data = identities(); link = next(iter(data[3]['NetworkSettings']['Networks'].values())); link[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): dns.expected(*data, RESOLVER)
        data = identities(); data[2]['subnets'] *= 2
        with self.assertRaises(ValueError): dns.expected(*data, RESOLVER)
        with self.assertRaises(ValueError): dns.expected(*identities(), b'nameserver 10.87.0.9\n')

    def test_receipt_cannot_substitute_expected_answer_or_wire(self):
        identity = dns.expected(*identities(), RESOLVER)
        for key, value in [('answer', '10.87.0.9'), ('resolver', '10.87.0.9'), ('peer', ['10.87.0.9', 53]),
                           ('peer', ['10.87.0.1', 53.0]),
                           ('question', 'other.'), ('type', 'AAAA'), ('class', 'CH'), ('status', 'failed'),
                           ('schema_version', True), ('resolver_config_sha256', '0' * 64),
                           ('query_hex', receipt()['query_hex'] + '00'), ('response_hex', RESPONSE.hex()[:-2] + '09'),
                           ('response_hex', RESPONSE.hex().upper()), ('extra', 'private')]:
            row = receipt(); row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): dns.verified_response(json.dumps(row).encode(), identity)
        for raw in (b'x' * 4097, b'[]', b'{"answer":"x","answer":"y"}'):
            with self.assertRaises(ValueError): dns.verified_response(raw, identity)

    def test_native_json_must_be_one_unambiguous_object(self):
        for value in (b'[]', b'[{},{}]', b'[1]', b'[{"Id":"a","Id":"b"}]', b'x' * (4 * 1024 * 1024 + 1)):
            with self.assertRaises(ValueError): dns.one(value)

    def test_owned_resolver_path_mount_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); storage = base / 'storage'; storage.mkdir()
            resolver = storage / 'resolv.conf'; resolver.write_bytes(RESOLVER); resolver.chmod(0o600)
            oci = storage / 'config.json'; mount = {'destination': '/etc/resolv.conf', 'type': 'bind', 'source': str(resolver)}
            oci.write_text(json.dumps({'mounts': [mount]}))
            rt = SimpleNamespace(paths={'storage': storage, 'run': base / 'run'})
            row = {'ResolvConfPath': str(resolver), 'OCIConfigPath': str(oci)}
            owner = {'root_uid': os.getuid(), 'root_gid': os.getgid()}
            guard = patch.object(dns, 'gateway_process', side_effect=lambda row: nullcontext(owner))
            guard.start(); self.addCleanup(guard.stop)
            self.assertEqual(dns.resolver_bytes(rt, row)[0], RESOLVER)
            resolver.chmod(0o666)
            with self.assertRaises(ValueError): dns.resolver_bytes(rt, row)
            resolver.chmod(0o600); resolver.unlink(); target = base / 'outside'; target.write_bytes(RESOLVER); resolver.symlink_to(target)
            with self.assertRaises(ValueError): dns.resolver_bytes(rt, row)
            resolver.unlink(); resolver.write_bytes(RESOLVER); resolver.chmod(0o600)
            for mounts in ([], [mount, mount], [dict(mount, source=str(target))]):
                oci.write_text(json.dumps({'mounts': mounts}))
                with self.assertRaises(ValueError): dns.resolver_bytes(rt, row)
            row['ResolvConfPath'] = str(target)
            with self.assertRaises(ValueError): dns.resolver_bytes(rt, row)

    def test_snapshot_reuses_full_runtime_guards_and_fresh_native_rows(self):
        product, selection, network, database, gateway = identities()
        rt = Mock(config=product, selection=selection)
        rt.processes.return_value = {role: {'process': 'running'} for role in ('database', 'gateway')}
        rt.engine.side_effect = [(0, json.dumps([row]).encode()) for row in (gateway, database, network, gateway)]
        with patch.object(dns, 'resolver_bytes', return_value=(RESOLVER, {'pid': 4321})):
            wanted = dns.expected(product, selection, network, database, gateway, RESOLVER)
            self.assertEqual(dns.snapshot(rt), dict(wanted, gateway_process={'pid': 4321}))
        self.assertEqual(rt.image.call_count, 2); rt.processes.assert_called_once(); rt.network.assert_called_once()
        self.assertEqual(rt.container_security.call_count, 3)

    def test_observe_checks_program_and_before_after_identity_before_success(self):
        identity = dns.expected(*identities(), RESOLVER)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); path = base / 'runtime/configuration'; path.mkdir(parents=True)
            record = path / 'ordinary-command.json'
            record.write_text(json.dumps({'dns_wire_sha256': hashlib.sha256(dns.PROGRAM.read_bytes()).hexdigest()}))
            rt = Mock(bundle_root=base, config=identities()[0]); rt.engine.return_value = (0, json.dumps(receipt()).encode())
            with patch.object(dns, 'snapshot', return_value=identity) as snapshot:
                self.assertEqual(dns.observe(rt)['status'], 'verified')
                self.assertEqual(snapshot.call_count, 2)
            args = rt.engine.call_args.args
            self.assertEqual(args[:4], ('exec', config.project_name(rt.config) + '-gateway', '/opt/ambisgis/python/bin/python3', '-c'))
            self.assertEqual(args[4], dns.PROGRAM.read_text()); self.assertEqual(rt.engine.call_args.kwargs, {'timeout': 15})
            with patch.object(dns, 'snapshot', side_effect=[identity, dict(identity, gateway_id='f' * 64)]):
                with self.assertRaises(ValueError): dns.observe(rt)
            rt.engine.reset_mock(); record.write_text('{"dns_wire_sha256":"wrong"}')
            with patch.object(dns, 'snapshot') as snapshot:
                with self.assertRaises(ValueError): dns.observe(rt)
                snapshot.assert_not_called(); rt.engine.assert_not_called()


class RootMappingTests(InertOnly):
    def test_exact_caller_relative_root_mapping(self):
        raw = b'1000 1000 1\n0 100000 1000\n1001 101001 64536\n'
        self.assertEqual(dns.root_mapping(raw), (100000, [[1000, 1000, 1], [0, 100000, 1000], [1001, 101001, 64536]]))
        self.assertEqual(dns.root_mapping(b'0 0 4294967295\n')[0], 0)
        self.assertEqual(dns.root_mapping(b'0 765432 1\n')[0], 765432)

    def test_missing_malformed_overlapping_and_oversized_maps_reject(self):
        bad = [b'', '0 0 1', b'0 0 1 extra', b'0 0 1\n\n', b'0 -1 1', b'+0 0 1', b'0 0 0',
               b'0 4294967295 1', b'0 0 4294967296', b'4294967294 0 2', b'1 10 1',
               b'0 100 2\n1 300 1', b'0 100 2\n2 101 1', b'0 100 1\n0 200 1',
               b'0 100 1\n1 100 1', b'0 0 1' + b' ' * 4096, b'0 0 1\n' * 33, b'0 0 \xff']
        for raw in bad:
            with self.subTest(raw=repr(raw)[:40]), self.assertRaises(ValueError): dns.root_mapping(raw)

    def test_process_stat_rejects_wrong_reused_dead_or_malformed_identity(self):
        raw = process_stat()
        self.assertEqual(dns.process_start(raw, 4321), 4567)
        for value in (raw.replace(b'4321 ', b'4322 ', 1), raw.replace(b') S ', b') Z '),
                      raw.replace(b') S ', b') X '), process_stat(ticks=0), b'4321 (bad) S 1', b'invalid'):
            with self.subTest(value=value[:35]), self.assertRaises(ValueError): dns.process_start(value, 4321)

    def test_proc_reader_is_bounded_regular_and_fixed_relative_only(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            directory_fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
            self.addCleanup(os.close, directory_fd)
            (base / 'uid_map').write_bytes(b'0 100000 1\n')
            self.assertEqual(dns.proc_bytes(directory_fd, 'uid_map'), b'0 100000 1\n')
            (base / 'uid_map').write_bytes(b'x' * 4097)
            with self.assertRaises(ValueError): dns.proc_bytes(directory_fd, 'uid_map')
            (base / 'uid_map').unlink(); (base / 'uid_map').symlink_to(base / 'missing')
            with self.assertRaises(OSError): dns.proc_bytes(directory_fd, 'uid_map')
            with self.assertRaises(ValueError): dns.proc_bytes(directory_fd, '../stat')


def process_stat(ticks=4567):
    return b'4321 (synthetic ) process) S ' + b'0 ' * 18 + str(ticks).encode() + b' 0\n'


def namespace_stat(inode):
    return SimpleNamespace(st_dev=5, st_ino=inode)


class GatewayProcessTests(InertOnly):
    def run_capture(self, *, proc=None, namespaces=None, gateway=None, during=None):
        row = gateway or {'State': {'Running': True, 'Pid': 4321}}
        def fixed_read(fd, name):
            self.assertEqual(fd, 123)
            return {'stat': process_stat(), 'uid_map': b'0 100000 1000\n1000 1000 1\n',
                    'gid_map': b'0 200000 1000\n1000 1000 1\n'}[name]
        def fixed_namespace(path, **kwargs):
            if path == 'ns/user':
                self.assertEqual(kwargs, {'dir_fd': 123}); return namespace_stat(20)
            self.assertEqual(path, '/proc/self/ns/user'); self.assertEqual(kwargs, {}); return namespace_stat(10)
        with patch.object(dns.os, 'open', return_value=123) as opened, \
                patch.object(dns.os, 'close') as closed, \
                patch.object(dns, 'proc_bytes', side_effect=proc or fixed_read), \
                patch.object(dns.os, 'stat', side_effect=namespaces or fixed_namespace):
            try:
                with dns.gateway_process(row) as proof:
                    if during: during(proof)
                    result = dict(proof)
                return result
            finally:
                if opened.called:
                    opened.assert_called_once_with('/proc/4321', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    closed.assert_called_once_with(123)

    def test_exact_root_maps_and_different_namespace_are_bound(self):
        value = self.run_capture()
        self.assertEqual((value['pid'], value['start_ticks'], value['root_uid'], value['root_gid']), (4321, 4567, 100000, 200000))
        self.assertNotEqual(value['user_namespace'], value['observer_user_namespace'])

    def test_same_namespace_or_unavailable_identity_rejects(self):
        with self.assertRaises(ValueError): self.run_capture(namespaces=lambda *a, **k: namespace_stat(10))
        with self.assertRaises(PermissionError): self.run_capture(proc=Mock(side_effect=PermissionError('private')))
        for pid in (True, 0, 1, -1, 2**31, '4321'):
            with self.subTest(pid=pid), self.assertRaises(ValueError): self.run_capture(gateway={'State': {'Running': True, 'Pid': pid}})
        with self.assertRaises(ValueError): self.run_capture(gateway={'State': {'Running': False, 'Pid': 4321}})

    def test_process_namespace_and_mapping_changes_reject_and_close(self):
        for field in ('stat', 'uid_map', 'gid_map'):
            counts = {}
            def changed(fd, name):
                counts[name] = counts.get(name, 0) + 1
                value = {'stat': process_stat(), 'uid_map': b'0 100000 1', 'gid_map': b'0 200000 1'}[name]
                if name == field and counts[name] > (2 if name == 'stat' else 1):
                    return process_stat(9999) if name == 'stat' else b'0 99999 1'
                return value
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_capture(proc=changed)
        calls = {'target': 0, 'observer': 0}
        def changed_namespace(path, **kwargs):
            key = 'target' if path == 'ns/user' else 'observer'; calls[key] += 1
            return namespace_stat(20 if key == 'target' and calls[key] == 1 else 30 if key == 'target' else 10)
        with self.assertRaises(ValueError): self.run_capture(namespaces=changed_namespace)
        with self.assertRaises(RuntimeError): self.run_capture(during=Mock(side_effect=RuntimeError('private')))


class MappedResolverTests(InertOnly):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        base = Path(temporary.name); storage = base / 'storage'; storage.mkdir()
        resolver = storage / 'resolv.conf'; resolver.write_bytes(RESOLVER); resolver.chmod(0o600)
        oci = storage / 'config.json'
        oci.write_text(json.dumps({'mounts': [{'destination': '/etc/resolv.conf', 'type': 'bind', 'source': str(resolver)}]}))
        return SimpleNamespace(paths={'storage': storage, 'run': base / 'run'}), {'ResolvConfPath': str(resolver), 'OCIConfigPath': str(oci)}, resolver

    def mapped_stat(self, real, uid=100000, gid=200000, **changes):
        fields = {name: getattr(real, name) for name in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}
        fields.update(st_uid=uid, st_gid=gid); fields.update(changes)
        return SimpleNamespace(**fields)

    def test_mapped_root_resolver_accepted_without_observer_uid_substitution(self):
        rt, row, resolver = self.fixture(); real = resolver.stat()
        mapped = self.mapped_stat(real)
        owner = {'root_uid': 100000, 'root_gid': 200000, 'pid': 4321, 'start_ticks': 4567}
        original_stat = dns.os.stat
        def selected_stat(path, *args, **kwargs):
            if Path(path) == resolver: return mapped
            return original_stat(path, *args, **kwargs)
        # create=True permits the same actual behavior witness against old source.
        with patch.object(dns, 'gateway_process', create=True, side_effect=lambda row: nullcontext(owner)), \
                patch.object(dns.os, 'fstat', return_value=mapped), \
                patch.object(dns.os, 'stat', side_effect=selected_stat), \
                patch.object(dns.os, 'getuid', return_value=1000):
            result = dns.resolver_bytes(rt, row)
        self.assertEqual(result[0], RESOLVER)
        self.assertEqual(result[1]['root_uid'], 100000)
        self.assertEqual(result[1]['root_gid'], 200000)

    def test_wrong_mapped_uid_gid_and_resolver_inode_drift_reject(self):
        rt, row, resolver = self.fixture(); real = resolver.stat()
        owner = {'root_uid': 100000, 'root_gid': 200000}
        for changes in ({'uid': 100001}, {'gid': 200001}, {'st_mode': real.st_mode | 0o002}):
            with self.subTest(changes=changes), patch.object(dns, 'gateway_process', side_effect=lambda row: nullcontext(owner)), \
                    patch.object(dns.os, 'fstat', return_value=self.mapped_stat(real, **changes)), self.assertRaises(ValueError):
                dns.resolver_bytes(rt, row)
        original_fstat = dns.os.fstat
        for key, value in (('st_ino', real.st_ino + 1), ('st_size', real.st_size + 1), ('st_mtime_ns', real.st_mtime_ns + 1)):
            calls = []
            def changed_fstat(fd):
                actual = original_fstat(fd)
                if actual.st_ino != real.st_ino: return actual
                calls.append(fd)
                return self.mapped_stat(real, **({key: value} if len(calls) > 1 else {}))
            with self.subTest(key=key), patch.object(dns, 'gateway_process', side_effect=lambda row: nullcontext(owner)), \
                    patch.object(dns.os, 'fstat', side_effect=changed_fstat), self.assertRaises(ValueError):
                dns.resolver_bytes(rt, row)
            self.assertEqual(len(calls), 2)

    def test_safe_modes_and_exact_path_inode_are_preserved(self):
        rt, row, resolver = self.fixture()
        owner = {'root_uid': os.getuid(), 'root_gid': os.getgid()}
        for mode in (0o400, 0o600, 0o644):
            resolver.chmod(mode)
            with patch.object(dns, 'gateway_process', side_effect=lambda row: nullcontext(owner)):
                self.assertEqual(dns.resolver_bytes(rt, row)[0], RESOLVER)
        real = resolver.stat(); original_stat = dns.os.stat
        def changed_path(path, *args, **kwargs):
            actual = original_stat(path, *args, **kwargs)
            if Path(path) == resolver and kwargs.get('follow_symlinks') is False:
                return self.mapped_stat(real, uid=real.st_uid, gid=real.st_gid, st_ino=real.st_ino + 1)
            return actual
        with patch.object(dns, 'gateway_process', side_effect=lambda row: nullcontext(owner)), \
                patch.object(dns.os, 'stat', side_effect=changed_path), self.assertRaises(ValueError):
            dns.resolver_bytes(rt, row)

    def test_snapshot_rejects_fresh_container_pid_start_or_path_drift(self):
        for field, replacement in (('Pid', 9999), ('StartedAt', 'changed'), ('ResolvConfPath', '/changed'), ('OCIConfigPath', '/changed')):
            product, selection, network, database, gateway = identities()
            after = json.loads(json.dumps(gateway))
            if field in ('Pid', 'StartedAt'): after['State'][field] = replacement
            else: after[field] = replacement
            rt = Mock(config=product, selection=selection)
            rt.processes.return_value = {role: {'process': 'running'} for role in ('database', 'gateway')}
            rt.engine.side_effect = [(0, json.dumps([row]).encode()) for row in (gateway, database, network, after)]
            with self.subTest(field=field), patch.object(dns, 'resolver_bytes', return_value=(RESOLVER, {'pid': 4321})), self.assertRaises(ValueError):
                dns.snapshot(rt)


if __name__ == '__main__':
    unittest.main()
