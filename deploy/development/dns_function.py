"""Ordinary fixed-service DNS evidence; no NSS/hosts-file success substitute."""
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


def resolver_bytes(rt, gateway):
    path = checked_path(gateway['ResolvConfPath'])
    if not any(path.is_relative_to(rt.paths[key]) for key in ('run', 'storage')):
        raise ValueError('resolver file escaped owned storage')
    # container_security has already checked this contained OCIConfigPath.
    oci = read_json(gateway['OCIConfigPath'])
    mounts = [row for row in oci['mounts'] if row.get('destination') == '/etc/resolv.conf']
    if len(mounts) != 1 or mounts[0].get('type') != 'bind' or mounts[0].get('source') != str(path):
        raise ValueError('resolver mount differs from inspected source')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o022):
            raise ValueError('unsafe owned resolver source')
        raw = stream.read(4097)
    wire.resolver_config(raw)
    return raw


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
    resolver = resolver_bytes(rt, rows['gateway'])
    return expected(rt.config, rt.selection, one(raw), rows['database'], rows['gateway'], resolver)


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
