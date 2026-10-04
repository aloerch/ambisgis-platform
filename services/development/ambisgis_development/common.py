"""Fixed container interfaces, scoped secret files and bounded internal HTTP."""
import http.client
import json
import os
from pathlib import Path
import re
import stat
import uuid
from urllib.parse import urlsplit

CONFIG = Path('/run/ambisgis/product.json')
SECRETS = Path('/run/ambisgis/secrets.json')
DATA = Path('/var/lib/ambisgis')
SAMPLE = 'fixture:private_points'


def read(path):
    path = Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('unsafe service input path')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077
                or metadata.st_uid != os.getuid() or metadata.st_size > 65536):
            raise ValueError('service configuration must be bounded and owner-only')
        raw = stream.read(65537)
    if len(raw) > 65536: raise ValueError('service configuration exceeded its bound')
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('duplicate service configuration key')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(value, dict): raise ValueError('service configuration must be an object')
    return value


def inputs():
    value, secrets = read(CONFIG), read(SECRETS)
    if value.get('schema_version') != 1 or value.get('profile') != 'developer-loopback':
        raise ValueError('unsupported service configuration')
    if (value.get('database_host') != 'database' or value.get('database_port') != 5432
            or value.get('catalog_origin') != 'http://catalog:8000' or value.get('engine_origin') != 'http://geoserver:8080'
            or value.get('catalog_database') != 'ambisgis_catalog' or value.get('managed_database') != 'ambisgis_data'):
        raise ValueError('unexpected private service selection')
    if str(uuid.UUID(value.get('install_id', ''))) != value.get('install_id'):
        raise ValueError('missing installation identity')
    public = urlsplit(value.get('public_origin', ''))
    if public.scheme != 'http' or public.hostname != '127.0.0.1' or not public.port or public.path or public.query or public.fragment or public.username or public.password:
        raise ValueError('developer profile must be loopback bound')
    if any(not isinstance(s, str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}', s) for s in secrets.values()):
        raise ValueError('invalid scoped secret input')
    return value, secrets


def save(path, value):
    path = Path(path)
    data = json.dumps(value, sort_keys=True, indent=2).encode() + b'\n'
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(data); output.flush(); os.fsync(output.fileno())


def response(start, status, value=None, *, content_type='application/json'):
    body = b'' if value is None else value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    start(str(status) + ' ' + http.client.responses.get(status, 'Response'),
          [('Content-Type', content_type), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
           ('X-Content-Type-Options', 'nosniff')])
    return [body]


def request(origin, method, path, *, headers=None, body=None, limit=4 * 1024 * 1024, timeout=4):
    address = urlsplit(origin)
    if origin not in ('http://catalog:8000', 'http://geoserver:8080'):
        raise ValueError('only generated internal service origins are permitted')
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=timeout)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        result = connection.getresponse()
        payload = result.read(limit + 1)
        if len(payload) > limit or result.getheader('Location'):
            raise ValueError('bounded internal response required')
        return result.status, result.getheader('Content-Type', ''), payload
    finally:
        connection.close()


def serve(application, port=8000):
    # Waitress is a separately retained, reviewed dependency supplied by the
    # image assembler. Never import/install it during bundle discovery/init.
    import logging
    import signal
    from waitress import create_server, wasyncore
    from waitress.task import ThreadedTaskDispatcher

    stopping = False
    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    channels, previous = {}, {}
    dispatcher = ThreadedTaskDispatcher()
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, request_stop)
        logging.basicConfig()
        dispatcher.set_thread_count(4)
        server = create_server(application, map=channels, _dispatcher=dispatcher,
            host='0.0.0.0', port=port, threads=4, connection_limit=64,
            backlog=64, channel_timeout=20, cleanup_interval=5, max_request_header_size=16384,
            max_request_body_size=65536, expose_tracebacks=False, ident='AmbisGIS',
            clear_untrusted_proxy_headers=True, trusted_proxy=None, channel_request_lookahead=0)
        server.print_listen('Serving on http://{}:{}')
        while channels and not stopping:
            wasyncore.loop(timeout=0.25, count=1, map=channels,
                           use_poll=server.adj.asyncore_use_poll)
    finally:
        try:
            try:
                dispatcher.shutdown(timeout=5)
                # Waitress returns True even when its bounded wait expires.
                with dispatcher.lock:
                    if dispatcher.threads:
                        raise RuntimeError('service worker shutdown incomplete')
            finally:
                wasyncore.close_all(channels)
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
