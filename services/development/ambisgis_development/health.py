"""Read-only native health probes for the selected fixed container role."""
import http.client
import json
import sys

from .common import inputs


def probe(role):
    product, secrets = inputs()
    if role == 'database':
        from .database import health
        return health()
    if role not in {'catalog', 'geoserver', 'gateway'}:
        return False
    port = 8080 if role == 'geoserver' else 8000
    path = {'catalog': '/internal/health', 'geoserver': '/health/live', 'gateway': '/health/ready'}[role]
    headers = {'X-AmbisGIS-Policy-Key': secrets['policy_key']}
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=14)
    try:
        connection.request('GET', path, headers=headers)
        reply = connection.getresponse()
        data = reply.read(32769)
        if reply.status != 200 or reply.getheader('Location') or len(data) > 32768:
            return False
        value = json.loads(data)
        if value.get('install_id') != product['install_id']:
            return False
        if role == 'catalog':
            return value.get('catalog') is True and value.get('database') is True
        if role == 'geoserver':
            # This is explicitly process/application health. Gateway readiness
            # additionally performs a real authorized map and feature query.
            return value.get('application') is True
        return value.get('ready') is True and value.get('checks') == dict.fromkeys(('catalog', 'database', 'map', 'query'), True)
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        ready = len(sys.argv) == 2 and probe(sys.argv[1])
    except Exception:
        ready = False
    raise SystemExit(0 if ready else 1)
