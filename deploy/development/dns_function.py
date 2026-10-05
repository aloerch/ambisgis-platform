"""Ordinary fixed-service DNS evidence; no NSS/hosts-file success substitute."""
from contextlib import contextmanager
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import struct

from installer import config
from installer.state import checked_path, no_duplicate_keys, read_json

PROGRAM = Path(__file__).with_name('dns_wire_probe.py')
spec = importlib.util.spec_from_file_location('fixed_dns_wire', PROGRAM)
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)


def identifier(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('native identity differs')
    return value


def one(raw):
    if not isinstance(raw, bytes) or len(raw) > 4 * 1024 * 1024:
        raise ValueError('native inspect bound')
    rows = json.loads(raw, object_pairs_hook=no_duplicate_keys)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError('one native identity required')
    return rows[0]


def expected(product, selection, network, database, gateway, resolver):
    """Pure selected-field oracle, independent of returned DNS answer bytes."""
    project = config.project_name(product)
    name = project + '_internal'
    if (network['name'] != name or network['driver'] != 'bridge'
            or network['internal'] is not True or network['ipv6_enabled'] is not False
            or network['dns_enabled'] is not True
            or network['labels'].get('org.ambisgis.install-id') != product['install_id']
            or network.get('routes') or network.get('network_dns_servers') or network.get('options')
            or network.get('ipam_options', {}) not in ({}, {'driver': 'host-local'})
            or not isinstance(network['subnets'], list) or len(network['subnets']) != 1):
        raise ValueError('owned single IPv4 DNS network required')
    subnet = network['subnets'][0]
    prefix = ipaddress.IPv4Network(subnet['subnet'], strict=True)
    router = wire.private_ipv4(subnet['gateway'])
    if (not prefix.is_private or prefix.is_loopback or prefix.is_link_local
            or subnet.get('lease_range') or router not in prefix
            or router in (prefix.network_address, prefix.broadcast_address)):
        raise ValueError('owned resolver subnet differs')
    value = {'install_id': product['install_id'], 'network_id': identifier(network['id']),
             'network_name': name, 'subnet': str(prefix), 'resolver': str(router)}
    for role, row in (('database', database), ('gateway', gateway)):
        labels = row['Config']['Labels']
        image = row['Image']
        if not image.startswith('sha256:'):
            image = 'sha256:' + image
        networks = row['NetworkSettings']['Networks']
        if (row['Name'].removeprefix('/') != project + '-' + role
                or labels.get('org.ambisgis.install-id') != product['install_id']
                or labels.get('org.ambisgis.role') != role
                or image != selection['images'][role]['image_id']
                or row['State']['Running'] is not True or set(networks) != {name}):
            raise ValueError('owned running container identity differs')
        link = networks[name]
        address = wire.private_ipv4(link['IPAddress'])
        if (address not in prefix or address in (prefix.network_address, prefix.broadcast_address, router)
                or type(link['IPPrefixLen']) is not int or link['IPPrefixLen'] != prefix.prefixlen
                or link.get('NetworkID') != network['id']
                or link.get('Gateway') != str(router)
                or link.get('GlobalIPv6Address') or link.get('IPv6Gateway')
                or link.get('SecondaryIPAddresses') or link.get('SecondaryIPv6Addresses')):
            raise ValueError('container address differs from owned subnet')
        if role == 'database':
            aliases = link.get('Aliases')
            if (not isinstance(aliases, list) or any(type(alias) is not str for alias in aliases)
                    or 'database' not in aliases):
                raise ValueError('database service alias missing')
        value[role + '_id'] = identifier(row['Id'])
        value[role + '_image'] = image
        value[role + '_ip'] = str(address)
    if value['database_ip'] == value['gateway_ip']:
        raise ValueError('container addresses must differ')
    if any(gateway['HostConfig'].get(key) not in (None, []) for key in ('Dns', 'DnsOptions', 'DnsSearch')):
        raise ValueError('gateway DNS override differs')
    if wire.resolver_config(resolver) != str(router):
        raise ValueError('resolver is not the owned network gateway')
    value['resolver_config_sha256'] = hashlib.sha256(resolver).hexdigest()
    return value


def root_mapping(raw):
    """Map namespace root to the different namespace opening this proc file."""
    if type(raw) is not bytes or not 0 < len(raw) <= 4096:
        raise ValueError('bounded root mapping required')
    lines = raw.splitlines()
    if not 0 < len(lines) <= 32:
        raise ValueError('bounded root mapping required')
    rows = []
    for line in lines:
        if re.fullmatch(rb'[ \t]*[0-9]+[ \t]+[0-9]+[ \t]+[0-9]+[ \t]*', line) is None:
            raise ValueError('invalid root mapping')
        inside, outside, size = map(int, line.split())
        if (size <= 0 or inside + size > 2**32 - 1 or outside + size > 2**32 - 1
                or any(inside < i + n and i < inside + size or outside < o + n and o < outside + size
                       for i, o, n in rows)):
            raise ValueError('ambiguous root mapping')
        rows.append([inside, outside, size])
    roots = [outside for inside, outside, size in rows if inside == 0]
    if len(roots) != 1:
        raise ValueError('namespace root mapping missing')
    return roots[0], rows


def proc_bytes(directory, name):
    # Callers use only stat/uid_map/gid_map, relative to one retained proc FD.
    if name not in ('stat', 'uid_map', 'gid_map'):
        raise ValueError('unexpected process field')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('nonregular process field')
        raw = stream.read(4097)
    if not 0 < len(raw) <= 4096:
        raise ValueError('bounded process field required')
    return raw


def process_start(raw, pid):
    try:
        first, tail = raw.split(b' (', 1)
        fields = tail.rsplit(b') ', 1)[1].split()
        if (int(first) != pid or len(fields) < 20 or fields[0] not in (b'R', b'S', b'D', b'T', b't', b'W', b'K', b'P', b'I')
                or re.fullmatch(rb'[0-9]+', fields[19]) is None or int(fields[19]) <= 0):
            raise ValueError()
        return int(fields[19])
    except (IndexError, ValueError):
        raise ValueError('live gateway process identity unavailable') from None


def namespace_identity(info):
    return [info.st_dev, info.st_ino]


@contextmanager
def gateway_process(gateway):
    pid = gateway['State']['Pid']
    if gateway['State']['Running'] is not True or type(pid) is not int or not 1 < pid < 2**31:
        raise ValueError('live gateway process required')
    directory = os.open('/proc/' + str(pid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        def sample():
            start = process_start(proc_bytes(directory, 'stat'), pid)
            target = namespace_identity(os.stat('ns/user', dir_fd=directory))
            observer = namespace_identity(os.stat('/proc/self/ns/user'))
            # Same-namespace maps describe the parent, unlike caller-relative stat.
            # https://man7.org/linux/man-pages/man7/user_namespaces.7.html
            if target == observer:
                raise ValueError('different observer user namespace required')
            uid, uid_map = root_mapping(proc_bytes(directory, 'uid_map'))
            gid, gid_map = root_mapping(proc_bytes(directory, 'gid_map'))
            if (process_start(proc_bytes(directory, 'stat'), pid) != start
                    or namespace_identity(os.stat('ns/user', dir_fd=directory)) != target
                    or namespace_identity(os.stat('/proc/self/ns/user')) != observer):
                raise ValueError('gateway process changed')
            return {'pid': pid, 'start_ticks': start, 'user_namespace': target,
                    'observer_user_namespace': observer, 'root_uid': uid, 'root_gid': gid,
                    'uid_map': uid_map, 'gid_map': gid_map}
        before = sample()
        yield before
        if sample() != before:
            raise ValueError('gateway process or root mapping changed')
    finally:
        os.close(directory)


def file_identity(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def resolver_bytes(rt, gateway):
    path = checked_path(gateway['ResolvConfPath'])
    if not any(path.is_relative_to(rt.paths[key]) for key in ('run', 'storage')):
        raise ValueError('resolver file escaped owned storage')
    # container_security has already checked this contained OCIConfigPath.
    oci = read_json(gateway['OCIConfigPath'])
    mounts = [row for row in oci['mounts'] if row.get('destination') == '/etc/resolv.conf']
    if len(mounts) != 1 or mounts[0].get('type') != 'bind' or mounts[0].get('source') != str(path):
        raise ValueError('resolver mount differs from inspected source')
    with gateway_process(gateway) as owner:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner['root_uid']
                    or info.st_gid != owner['root_gid'] or info.st_mode & 0o022):
                raise ValueError('unsafe owned resolver source')
            identity = file_identity(info)
            raw = stream.read(4097)
            if (file_identity(os.fstat(stream.fileno())) != identity
                    or file_identity(os.stat(path, follow_symlinks=False)) != identity):
                raise ValueError('owned resolver source changed')
        wire.resolver_config(raw)
    return raw, dict(owner, resolver_file=identity)


def snapshot(rt):
    # Reuse full bundle/archive/image/source, container security/mount/namespace
    # and native-network guards. Re-inspected rows also bind selected identities.
    for role in ('gateway', 'database'):
        rt.image(role)
    processes = rt.processes()
    if any(processes[role]['process'] != 'running' for role in ('gateway', 'database')) or rt.network() is None:
        raise ValueError('owned DNS services must be running')
    project = config.project_name(rt.config)
    rows = {}
    for role in ('gateway', 'database'):
        code, raw = rt.engine('container', 'inspect', project + '-' + role)
        if code:
            raise ValueError('container inspect failed')
        rows[role] = one(raw)
        rt.container_security(rows[role], role)
    code, raw = rt.engine('network', 'inspect', project + '_internal')
    if code:
        raise ValueError('network inspect failed')
    resolver, process = resolver_bytes(rt, rows['gateway'])
    network = one(raw)
    identity = expected(rt.config, rt.selection, network, rows['database'], rows['gateway'], resolver)
    # Bracket the process/file read with a fresh exact owned-container check.
    code, raw = rt.engine('container', 'inspect', project + '-gateway')
    if code:
        raise ValueError('gateway reinspection failed')
    after = one(raw)
    rt.container_security(after, 'gateway')
    if (expected(rt.config, rt.selection, network, rows['database'], after, resolver) != identity
            or any(after['State'][key] != rows['gateway']['State'][key] for key in ('Pid', 'StartedAt'))
            or any(after[key] != rows['gateway'][key] for key in ('OCIConfigPath', 'ResolvConfPath'))):
        raise ValueError('gateway identity changed during resolver observation')
    identity['gateway_process'] = process
    return identity


def verified_response(raw, identity):
    if not isinstance(raw, bytes) or len(raw) > 4096:
        raise ValueError('bounded DNS receipt required')
    value = json.loads(raw, object_pairs_hook=no_duplicate_keys)
    fields = {'schema_version', 'status', 'resolver', 'resolver_config_sha256', 'question', 'type',
              'class', 'query_hex', 'response_hex', 'peer', 'answer'}
    if (not isinstance(value, dict) or set(value) != fields or type(value['schema_version']) is not int
            or value['schema_version'] != 1 or value['status'] != 'verified'
            or value['question'] != 'database.' or value['type'] != 'A' or value['class'] != 'IN'
            or type(value['peer']) is not list or len(value['peer']) != 2 or type(value['peer'][1]) is not int
            or value['resolver'] != identity['resolver'] or value['peer'] != [identity['resolver'], 53]
            or value['resolver_config_sha256'] != identity['resolver_config_sha256']
            or value['answer'] != identity['database_ip']):
        raise ValueError('DNS receipt identity differs')
    for field in ('query_hex', 'response_hex'):
        if not isinstance(value[field], str) or re.fullmatch('[0-9a-f]+', value[field]) is None:
            raise ValueError('canonical packet evidence required')
    request, response = bytes.fromhex(value['query_hex']), bytes.fromhex(value['response_hex'])
    if len(request) != 26:
        raise ValueError('fixed DNS query length differs')
    transaction = struct.unpack('!H', request[:2])[0]
    if request != wire.query(transaction) or wire.answer(response, transaction) != identity['database_ip']:
        raise ValueError('packet evidence differs from owned database identity')
    return value


def observe(rt):
    program = PROGRAM.read_text()
    program_sha = hashlib.sha256(program.encode()).hexdigest()
    pinned = read_json(rt.bundle_root / 'runtime/configuration/ordinary-command.json')
    if pinned.get('dns_wire_sha256') != program_sha:
        raise ValueError('fixed DNS program differs from reviewed bundle')
    before = snapshot(rt)
    code, raw = rt.engine('exec', config.project_name(rt.config) + '-gateway',
                         '/opt/ambisgis/python/bin/python3', '-c', program, timeout=15)
    if code:
        raise ValueError('fixed DNS client failed')
    result = verified_response(raw, before)
    if snapshot(rt) != before:
        raise ValueError('owned DNS identities changed during observation')
    return {'status': 'verified', 'scope': 'one database. A/IN UDP exchange from owned gateway',
            'identity': before, 'program_sha256': program_sha, 'wire': result,
            'host_files_or_NSS_used_for_answer': False, 'full_installation_acceptance': False}
