"""Fixed gateway DNS wire check, sent as exact hash-bound Python -c source.

No caller input, hostname, resolver override, retry or external fallback.
Importing this file only defines pure parsers and the explicit check entrypoint.
"""
import hashlib
import ipaddress
import json
import os
import socket
import stat
import struct
import sys

QUESTION = b'\x08database\x00\x00\x01\x00\x01'


def private_ipv4(value):
    address = ipaddress.IPv4Address(value)
    if (str(address) != value or not address.is_private or address.is_loopback
            or address.is_link_local or address.is_unspecified or address.is_multicast
            or address.is_reserved):
        raise ValueError('unsupported private IPv4 address')
    return address


def resolver_config(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 4096:
        raise ValueError('resolver configuration bound')
    rows = []
    for line in raw.decode('ascii').splitlines():
        fields = line.split('#', 1)[0].split(';', 1)[0].split()
        if not fields:
            continue
        if fields[0] == 'nameserver':
            if len(fields) != 2:
                raise ValueError('resolver configuration shape')
            private_ipv4(fields[1])
            rows.append(fields[1])
        elif fields[0] not in ('search', 'domain', 'options'):
            raise ValueError('unrecognized resolver directive')
        # Search/options have no effect: this program sends an absolute wire
        # question to the parsed numeric address without getaddrinfo/NSS.
    if len(rows) != 1:
        raise ValueError('one unambiguous resolver required')
    return rows[0]


def query(transaction):
    if type(transaction) is not int or not 0 <= transaction <= 65535:
        raise ValueError('transaction identifier')
    return struct.pack('!6H', transaction, 0x0100, 1, 0, 0, 0) + QUESTION


def name(packet, offset):
    labels, seen, end, total = [], set(), None, 0
    while True:
        if offset in seen or offset >= len(packet) or len(seen) >= 64:
            raise ValueError('invalid DNS name reference')
        seen.add(offset)
        length = packet[offset]
        if length & 0xc0 == 0xc0:
            if offset + 1 >= len(packet):
                raise ValueError('truncated DNS pointer')
            target = ((length & 0x3f) << 8) | packet[offset + 1]
            if target < 12 or target >= offset:
                raise ValueError('DNS pointer must refer backward')
            if end is None:
                end = offset + 2
            offset = target
            continue
        if length & 0xc0 or offset + 1 + length > len(packet):
            raise ValueError('invalid DNS label')
        offset += 1
        if not length:
            return b'.'.join(labels).lower(), offset if end is None else end
        label = packet[offset:offset + length]
        if any(c < 33 or c > 126 for c in label):
            raise ValueError('non-ASCII DNS label')
        total += length + 1
        if total > 254:
            raise ValueError('DNS name bound')
        labels.append(label)
        offset += length


def answer(packet, transaction):
    if type(packet) is not bytes or not 12 <= len(packet) <= 512:
        raise ValueError('DNS datagram bound')
    ident, flags, questions, answers, authority, additional = struct.unpack('!6H', packet[:12])
    # Exactly one A response to our one A/IN question. No EDNS, aliases,
    # truncation, error response or additional resolver transport is supported.
    if (ident != transaction or flags & ~0x8580 or flags & 0x8100 != 0x8100
            or (questions, answers, authority, additional) != (1, 1, 0, 0)):
        raise ValueError('DNS response header differs')
    question, position = name(packet, 12)
    if question != b'database' or packet[position:position + 4] != b'\x00\x01\x00\x01':
        raise ValueError('DNS question differs')
    owner, position = name(packet, position + 4)
    if owner != b'database' or position + 10 > len(packet):
        raise ValueError('DNS answer owner differs')
    kind, klass, ttl, size = struct.unpack('!HHIH', packet[position:position + 10])
    position += 10
    if (kind, klass, size) != (1, 1, 4) or position + size != len(packet):
        raise ValueError('DNS A answer shape differs')
    result = str(ipaddress.IPv4Address(packet[position:]))
    private_ipv4(result)
    return result


def read_resolver():
    # Podman supplies this fixed mount. Its host source, mount identity and
    # exact content hash are independently checked by the lifecycle driver.
    fd = os.open('/etc/resolv.conf', os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise ValueError('unsafe resolver file')
        return stream.read(4097)


def run():
    if sys.argv != ['-c'] or sys.stdin.buffer.read(1):
        raise ValueError('DNS check does not accept arguments or stdin')
    raw = read_resolver()
    resolver = resolver_config(raw)
    transaction = int.from_bytes(os.urandom(2), 'big')
    request = query(transaction)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(3)
        if connection.sendto(request, (resolver, 53)) != len(request):
            raise ValueError('DNS query incomplete')
        response, peer = connection.recvfrom(513)
    if peer != (resolver, 53):
        raise ValueError('DNS response source differs')
    value = answer(response, transaction)
    return {'schema_version': 1, 'status': 'verified', 'resolver': resolver,
            'resolver_config_sha256': hashlib.sha256(raw).hexdigest(),
            'question': 'database.', 'type': 'A', 'class': 'IN',
            'query_hex': request.hex(), 'response_hex': response.hex(),
            'peer': [peer[0], peer[1]], 'answer': value}


def main():
    try:
        result = run()
    except TimeoutError:
        result = {'status': 'failed', 'classification': 'dns_timeout'}
    except (ValueError, OSError):
        result = {'status': 'failed', 'classification': 'dns_check_failed'}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
