"""Loopback product entry point; catalog remains the sole policy authority."""
import http.client
import json
from urllib.parse import urlencode, urlsplit

from .common import SAMPLE, inputs, request, response, serve

WFS = {'service': 'WFS', 'version': '1.0.0', 'request': 'GetFeature', 'typename': SAMPLE, 'outputformat': 'application/json'}
WMS = {'service': 'WMS', 'version': '1.1.1', 'request': 'GetMap', 'layers': SAMPLE, 'styles': '',
       'srs': 'EPSG:4326', 'bbox': '0,0,4,4', 'width': '512', 'height': '512', 'format': 'image/png', 'transparent': 'FALSE'}
AUTH_PATHS = {'/account/login/', '/account/logout/', '/o/authorize/', '/o/token/', '/o/revoke_token/'}


def policy(product, secrets, name, authorization):
    try:
        status, _, _ = request(product['catalog_origin'], 'GET', '/internal/policy/read', headers={
            'X-AmbisGIS-Policy-Key': secrets['policy_key'], 'X-AmbisGIS-Resource': name,
            'Authorization': authorization}, limit=1024)
        return status == 204
    except (OSError, ValueError, http.client.HTTPException):
        return False


def data_response(product, secrets, path, query, authorization):
    from ambisgis_policy.gateway import resource as feature_resource
    from ambisgis_render.boundary import resource as map_resource
    name = feature_resource(path, query, 'GET') if path == '/wfs' else map_resource('GET', path, query)
    if name != SAMPLE or not policy(product, secrets, name, authorization):
        return 403, 'text/plain', b''
    status, content_type, body = request(product['engine_origin'], 'GET',
                                         '/geoserver/' + ('wfs' if path == '/wfs' else 'wms') + '?' + query,
                                         headers={'Authorization': authorization})
    expected = 'application/json' if path == '/wfs' else 'image/png'
    if status != 200 or content_type.split(';')[0] != expected:
        return 503, 'text/plain', b''
    return status, content_type, body


def useful_readiness(product, secrets):
    checks = {'catalog': False, 'database': False, 'map': False, 'query': False}
    try:
        status, _, body = request(product['catalog_origin'], 'GET', '/internal/health',
                                  headers={'X-AmbisGIS-Policy-Key': secrets['policy_key']}, limit=32768)
        native = json.loads(body)
        if status == 200 and native.get('install_id') == product['install_id']:
            checks['catalog'] = native.get('catalog') is True
            checks['database'] = native.get('database') is True
        authorization = 'Bearer ' + secrets['health_token']
        status, _, body = data_response(product, secrets, '/wfs', urlencode(WFS), authorization)
        if status == 200:
            value = json.loads(body)
            checks['query'] = value.get('type') == 'FeatureCollection' and len(value.get('features', [])) == 2
        status, _, body = data_response(product, secrets, '/map', urlencode(WMS), authorization)
        if status == 200:
            # Exact nonblank/pixel semantics are additionally checked in the
            # installation acceptance journey, independently of this health API.
            checks['map'] = len(body) > 256 and body[:8] == b'\x89PNG\r\n\x1a\n' and body[16:24] == b'\x00\x00\x02\x00\x00\x00\x02\x00'
    except (OSError, ValueError, TypeError, KeyError, http.client.HTTPException):
        pass
    return {'install_id': product['install_id'], 'ready': all(checks.values()), 'checks': checks}


def catalog_proxy(product, env, start):
    path, method = env['PATH_INFO'], env['REQUEST_METHOD']
    query = env.get('QUERY_STRING', '')
    if len(query) > 4096 or method not in ('GET', 'POST', 'PATCH'):
        return response(start, 400)
    size = int(env.get('CONTENT_LENGTH') or '0')
    if not 0 <= size <= 65536:
        return response(start, 413)
    payload = env['wsgi.input'].read(size) if size else None
    # Only these explicitly supported fields cross the gateway. Internal
    # identity/policy/forwarded headers from callers are never propagated.
    headers = {'Host': urlsplit(product['public_origin']).netloc}
    for source, target in (('HTTP_AUTHORIZATION', 'Authorization'), ('HTTP_COOKIE', 'Cookie'),
                           ('CONTENT_TYPE', 'Content-Type'), ('HTTP_ORIGIN', 'Origin'), ('HTTP_REFERER', 'Referer')):
        if env.get(source): headers[target] = env[source]
    connection = http.client.HTTPConnection('catalog', 8000, timeout=8)
    try:
        connection.request(method, path + ('?' + query if query else ''), body=payload, headers=headers)
        result = connection.getresponse(); body = result.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024:
            return response(start, 503)
        outgoing = [('Content-Type', result.getheader('Content-Type', 'application/octet-stream')),
                    ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')]
        for key, value in result.getheaders():
            if key.lower() == 'set-cookie': outgoing.append(('Set-Cookie', value))
            if key.lower() == 'location':
                parsed = urlsplit(value)
                if ('\\' in value or any(ord(c) < 32 for c in value) or value.startswith('//')
                        or parsed.netloc and not parsed.scheme
                        or parsed.scheme and (parsed.scheme + '://' + parsed.netloc) != product['public_origin']):
                    return response(start, 503)
                outgoing.append(('Location', value))
        start(str(result.status) + ' ' + http.client.responses.get(result.status, 'Response'), outgoing)
        return [body]
    finally:
        connection.close()


def application():
    product, secrets = inputs()
    def handle(env, start):
        path, method = env.get('PATH_INFO'), env.get('REQUEST_METHOD')
        try:
            if path == '/health/live' and method == 'GET' and not env.get('QUERY_STRING'):
                return response(start, 200, {'install_id': product['install_id'], 'live': True})
            if path == '/health/ready' and method == 'GET' and not env.get('QUERY_STRING'):
                value = useful_readiness(product, secrets)
                return response(start, 200 if value['ready'] else 503, value)
            if path in ('/wfs', '/map') and method == 'GET':
                status, content_type, body = data_response(product, secrets, path, env.get('QUERY_STRING', ''), env.get('HTTP_AUTHORIZATION', ''))
                return response(start, status, body, content_type=content_type)
            if path in AUTH_PATHS or path == '/api/v1/installation/sample':
                return catalog_proxy(product, env, start)
            if path == '/' and method == 'GET':
                page = b'<!doctype html><html lang="en"><meta charset="utf-8"><title>AmbisGIS development</title><main><h1>AmbisGIS development installation</h1><p>Persistent local catalog and protected synthetic map/query services.</p><p><a href="/health/ready">Check useful service readiness</a></p><p>This developer foundation does not yet provide the complete portal, publishing jobs or managed branch editing.</p></main></html>'
                return response(start, 200, page, content_type='text/html; charset=utf-8')
            return response(start, 404)
        except (OSError, ValueError, TypeError, http.client.HTTPException):
            return response(start, 503, {'error': 'Required service unavailable.'})
    return handle


def main():
    serve(application())
