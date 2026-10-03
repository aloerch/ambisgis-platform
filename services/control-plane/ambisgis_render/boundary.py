"""Finite WMS profile and immutable asset bindings; no permission database."""
import hashlib
import http.client
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

FIELDS = {'service': 'WMS', 'version': '1.1.1', 'request': 'GetMap',
          'styles': '', 'srs': 'EPSG:4326', 'bbox': '0,0,4,4',
          'width': '512', 'height': '512', 'format': 'image/png', 'transparent': 'FALSE'}


def resource(method, path, query, *, route='/map'):
    if method != 'GET' or path != route or not query or len(query) > 2048:
        return None
    if re.search(r'%(?![0-9A-Fa-f]{2})', query): return None
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True,
                          encoding='utf-8', errors='strict', max_num_fields=12)
    except (ValueError, UnicodeError): return None
    fields = {}
    for key, value in pairs:
        key = key.lower()
        if key in fields: return None
        fields[key] = value
    if set(fields) != set(FIELDS) | {'layers'}: return None
    if any(fields[key] != value for key, value in FIELDS.items()): return None
    name = fields['layers']
    return name if re.fullmatch(r'fixture:[a-z][a-z_]{0,63}', name) else None


def decision(origin, key, name, authorization):
    address = urlsplit(origin)
    if (address.scheme != 'http' or address.hostname != '127.0.0.1' or not address.port
            or address.path or address.query or address.fragment or address.username):
        raise ValueError('explicit loopback catalog origin required')
    connection = http.client.HTTPConnection('127.0.0.1', address.port, timeout=1.5)
    try:
        connection.request('GET', '/internal/policy/read', headers={
            'X-AmbisGIS-Policy-Key': key, 'X-AmbisGIS-Resource': name,
            'Authorization': authorization or ''})
        response = connection.getresponse()
        return response.status == 204 and response.getheader('Location') is None
    except (OSError, http.client.HTTPException, ValueError): return False
    finally: connection.close()


class Bindings:
    """Server provisioner supplies this fixed map; uploads/callers cannot select it.

    Every request checks the approved project/data/style bytes. This prototype
    accepts only fresh task-owned immutable copies; no shared writable data source.
    """
    def __init__(self, path, expected_sha256):
        path = Path(path)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_sha256: raise ValueError('binding receipt differs')
        self.entries = json.loads(data)
        if not self.entries or len(self.entries) > 16: raise ValueError('invalid renderer bindings')
        for name, row in self.entries.items():
            if not re.fullmatch(r'fixture:[a-z][a-z_]{0,63}', name): raise ValueError('invalid catalog binding')
            if row['renderer'] not in ('geoserver', 'qgis-server'): raise ValueError('invalid renderer')
            if not row['assets'] or len(row['assets']) > 128: raise ValueError('invalid assets')
            for asset in row['assets']:
                p = Path(asset['path'])
                if not p.is_absolute() or not re.fullmatch(r'[0-9a-f]{64}', asset['sha256']):
                    raise ValueError('invalid asset binding')

    def valid(self, name):
        try:
            row = self.entries[name]
            for asset in row['assets']:
                path = Path(asset['path'])
                if (path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file()
                        or path.stat().st_size > 32 * 1024 * 1024
                        or hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']): return False
            return True
        except (KeyError, OSError): return False


def gateway(origin, key, bindings, targets):
    endpoints = {name: urlsplit(value) for name, value in targets.items()}
    if set(endpoints) != {'geoserver', 'qgis-server'}: raise ValueError('renderer endpoints required')
    for endpoint in endpoints.values():
        if endpoint.scheme != 'http' or endpoint.hostname != '127.0.0.1' or not endpoint.port or endpoint.username:
            raise ValueError('renderer endpoint must be fixed loopback')
    def application(env, start):
        name = resource(env.get('REQUEST_METHOD'), env.get('PATH_INFO'), env.get('QUERY_STRING', ''))
        body, status = b'', '403 Forbidden'
        if name and bindings.valid(name) and decision(origin, key, name, env.get('HTTP_AUTHORIZATION', '')):
            endpoint = endpoints[bindings.entries[name]['renderer']]
            connection = http.client.HTTPConnection('127.0.0.1', endpoint.port, timeout=10)
            try:
                connection.request('GET', endpoint.path + '?' + env['QUERY_STRING'],
                                   headers={'Authorization': env.get('HTTP_AUTHORIZATION', '')})
                response = connection.getresponse(); candidate = response.read(4 * 1024 * 1024 + 1)
                if response.status == 200 and response.getheader('Content-Type', '').split(';')[0] == 'image/png' and len(candidate) <= 4 * 1024 * 1024:
                    body, status = candidate, '200 OK'
            except (OSError, http.client.HTTPException): status = '503 Service Unavailable'
            finally: connection.close()
        start(status, [('Content-Type', 'image/png' if body else 'text/plain'),
                       ('Cache-Control', 'no-store'), ('Content-Length', str(len(body)))])
        return [body]
    return application
