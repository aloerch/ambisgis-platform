#!/usr/bin/env python3
"""Real protected HTTP journey for an already running developer installation.

Uses the two installation principals and only its unmanaged diagnostic resource.
This is one acceptance slice, not an installer/network/restore qualification.
Tokens and passwords stay in memory; output contains selected hashes and facts.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import selectors
import struct
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from installer import config, runtime
from installer.state import checked_path, digest, no_duplicate_keys, private_directory

CLIENT = ROOT / 'build-support/geonode/protocol_probe.py'
POLICY_PROGRAM = ROOT / 'deploy/development/catalog_permission_probe.py'
spec = importlib.util.spec_from_file_location('installed_identity_protocol', CLIENT)
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)

FEATURE_QUERY = urlencode({'service': 'WFS', 'version': '1.0.0', 'request': 'GetFeature',
                          'typename': 'fixture:private_points', 'outputformat': 'application/json'})
MAP_QUERY = urlencode({'service': 'WMS', 'version': '1.1.1', 'request': 'GetMap',
                      'layers': 'fixture:private_points', 'styles': '', 'srs': 'EPSG:4326',
                      'bbox': '0,0,4,4', 'width': '512', 'height': '512', 'format': 'image/png', 'transparent': 'FALSE'})
EMPTY_TRANSACTION = b'<wfs:Transaction service="WFS" version="1.0.0" xmlns:wfs="http://www.opengis.net/wfs"/>'
INTERNAL_CLIENT = """import base64,http.client,json,sys
from urllib.parse import urlencode
raw=sys.stdin.read(16385)
if len(raw)>16384:raise ValueError('bounded request required')
v=json.loads(raw)
if set(v)!={'method','path','headers','body'}:raise ValueError('fixed request fields required')
if v['method'] not in ('GET','POST','PUT','DELETE') or not v['path'].startswith('/geoserver/') or len(v['path'])>4096:raise ValueError('fixed engine path required')
body=base64.b64decode(v['body'],validate=True)
empty=b'<wfs:Transaction service="WFS" version="1.0.0" xmlns:wfs="http://www.opengis.net/wfs"/>'
if body not in (b'',empty) or body and v['method']!='POST':raise ValueError('only empty no-feature transaction body supported')
if not isinstance(v['headers'],list) or len(v['headers'])>16:raise ValueError('bounded header list required')
for key,value in v['headers']:
 if key.lower() not in ('authorization','x-ambisgis-policy-key','x-ambisgis-resource','content-type') or len(value)>1024:raise ValueError('unsupported diagnostic header')
# Project stdin onto the declared finite acceptance matrix before connecting.
# No path normalization, arbitrary REST resource or administrative write exists.
queries={'wfs':urlencode({'service':'WFS','version':'1.0.0','request':'GetFeature','typename':'fixture:private_points','outputformat':'application/json'}),
 'wms':urlencode({'service':'WMS','version':'1.1.1','request':'GetMap','layers':'fixture:private_points','styles':'','srs':'EPSG:4326','bbox':'0,0,4,4','width':'512','height':'512','format':'image/png','transparent':'FALSE'})}
allowed={('GET','/geoserver/rest/workspaces',b''),('GET','/geoserver/web/',b''),('POST','/geoserver/wfs',empty)}
for name,query in queries.items():
 path='/geoserver/'+name+'?'+query
 for method in ('GET','POST','PUT','DELETE'):allowed.add((method,path,b''))
 invalid=[query+'&request=GetFeature',query+'&REQUEST=GetFeature',query+'&%72equest=GetFeature',query+'&unexpected=value',
  query.replace('service=','broken&service=',1),query.replace('service=','service=%ZZ',1),
  query.replace('version=','version=unsupported',1),query.replace('fixture%3Aprivate_points','fixture%3Aother_points'),
  query.replace('request=GetFeature','request=Transaction').replace('request=GetMap','request=GetCapabilities')]
 if name=='wms':invalid += [query.replace('width=512','width=0'),query.replace('bbox=0%2C0%2C4%2C4','bbox=0%2C0%2C9%2C9')]
 for query in invalid:allowed.add(('GET','/geoserver/'+name+'?'+query,b''))
if (v['method'],v['path'],body) not in allowed:raise ValueError('unlisted acceptance method/path/body')
c=http.client.HTTPConnection('geoserver',8080,timeout=10)
try:
 c.putrequest(v['method'],v['path'])
 for key,value in v['headers']:c.putheader(key,value)
 if body:c.putheader('Content-Length',str(len(body)))
 c.endheaders(body);r=c.getresponse();body=r.read(4194305)
 if len(body)>4194304:raise ValueError('bounded response exceeded')
 print(json.dumps({'status':r.status,'headers':r.getheaders(),'body':base64.b64encode(body).decode()}))
finally:c.close()
"""


class PermissionSession:
    """Finite private native-policy session; token material never enters it."""
    def __init__(self, journey):
        self.journey = journey; self.process = None; self.buffer = b''; self.events = []
        self.cleanup = None; self.diagnostics = None

    def event(self, timeout=20):
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as poll:
            poll.register(self.process.stdout, selectors.EVENT_READ)
            while b'\n' not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not poll.select(remaining): raise TimeoutError('native policy response timed out')
                value = os.read(self.process.stdout.fileno(), 4097)
                if not value: raise ValueError('native policy response ended')
                self.buffer += value
                if len(self.buffer) > 8192: raise ValueError('native policy response bound exceeded')
        raw, self.buffer = self.buffer.split(b'\n', 1)
        if len(raw) > 4096: raise ValueError('native policy event bound exceeded')
        result = json.loads(raw, object_pairs_hook=no_duplicate_keys)
        if not isinstance(result, dict): raise ValueError('native policy event must be an object')
        self.events.append(result)
        return result

    def __enter__(self):
        rt = self.journey.runtime
        self.diagnostics = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen([rt.podman, *rt.global_args, 'exec', '-i',
                config.project_name(self.journey.product) + '-catalog', '/opt/ambisgis/python/bin/python3', '-c',
                POLICY_PROGRAM.read_text()], env=rt.environment, cwd=rt.root,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.diagnostics)
            row = self.event()
            expected = str(uuid.uuid5(uuid.UUID(self.journey.product['install_id']), 'diagnostic-private-points'))
            if (row.get('event') != 'ready' or row.get('identity', {}).get('install_id') != self.journey.product['install_id']
                    or row['identity'].get('resource_uuid') != expected):
                raise ValueError('native policy session identity differs')
            self.initial = row
            return self
        except BaseException:
            self.close()
            raise

    def change(self, grant):
        action = 'grant' if grant else 'revoke'
        self.process.stdin.write((json.dumps({'action': action})+'\n').encode()); self.process.stdin.flush()
        row = self.event()
        if row.get('event') != action or row.get('granted') is not grant:
            raise ValueError('native permission transition failed')
        return row

    def close(self):
        complete = False
        try:
            if self.process is not None:
                try:
                    self.process.stdin.write(b'{"action":"finish"}\n'); self.process.stdin.flush()
                except (BrokenPipeError, OSError, ValueError): pass
                finally:
                    if self.process.stdin: self.process.stdin.close()
                # Failed action events may precede the native finally receipt.
                for _ in range(3):
                    row = self.event()
                    if row.get('event') == 'cleanup':
                        self.cleanup = row
                        complete = (row.get('complete') is True and
                            row.get('before_sha256') == row.get('after_sha256') ==
                            getattr(self, 'initial', {}).get('policy_sha256'))
                        break
                code = self.process.wait(timeout=20)
                if code: complete = False
                if self.diagnostics.tell() > 65536: complete = False
        except Exception as error:
            self.cleanup = {'complete': False, 'error_type': type(error).__name__}
        finally:
            if self.process is not None and self.process.poll() is None:
                # EOF was already sent so native finally can restore. A process
                # that still does not exit is never reported as clean/successful.
                try:
                    try: self.process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        self.process.terminate()
                        try: self.process.wait(timeout=5)
                        except subprocess.TimeoutExpired: self.process.kill(); self.process.wait(timeout=5)
                except Exception as error:
                    self.cleanup = {'complete': False, 'error_type': type(error).__name__}
                complete = False
            if self.process is not None:
                self.process.stdout.close()
            if self.diagnostics is not None: self.diagnostics.close()
            self.journey.permission_cleanup = {'complete': complete, 'native': self.cleanup}
            self.journey.permission_events = self.events
        if not complete: raise RuntimeError('Native item-policy restoration is incomplete.')

    def __exit__(self, *_): self.close()


class TrackedOAuthBrowser(protocol.OAuthBrowser):
    """Keep only this helper's newly issued token families for finally cleanup."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created_tokens = []
        self.token_sets = []
        self.issuance_accounted_for = True

    def exchange(self, authorization, verifier=None):
        # A lost issuance response may leave an unknown grant. Never report
        # successful cleanup merely because no token string reached the client.
        self.issuance_accounted_for = False
        return super().exchange(authorization, verifier)

    def refresh(self, refresh_token):
        self.issuance_accounted_for = False
        return super().refresh(refresh_token)

    def _tokens(self, response):
        if response.status in (400, 401):
            self.issuance_accounted_for = True  # Explicit grant/client rejection.
        elif response.status == 200:
            try:
                value = json.loads(response.body, object_pairs_hook=no_duplicate_keys)
                accounted_for = True
                for key in ('access_token', 'refresh_token'):
                    token = value.get(key)
                    if key == 'refresh_token' and token is None:
                        continue
                    if not isinstance(token, str) or not token or len(token) > 512:
                        accounted_for = False
                        continue
                    # Keep each known token even if another field is malformed.
                    self.created_tokens.append((key, token))
                    self.secrets.add(token)
                self.issuance_accounted_for = accounted_for
            except (ValueError, TypeError, AttributeError):
                self.issuance_accounted_for = False
        token_set = super()._tokens(response)
        self.token_sets.append(token_set)
        return token_set


def features(body):
    value = json.loads(body)
    if value.get('type') != 'FeatureCollection' or len(value.get('features', [])) != 2:
        raise ValueError('feature collection shape differs')
    actual = {}
    for row in value['features']:
        props = row['properties']; number = props['object_id']
        if type(number) is not int or number in actual: raise ValueError('feature ObjectID differs')
        coordinates = row['geometry'].get('coordinates')
        if not isinstance(coordinates, list) or len(coordinates) != 2 or any(type(item) not in (int, float) for item in coordinates):
            raise ValueError('feature coordinates are not two numeric values')
        actual[number] = {'id': row['id'], 'label': props['label'], 'geometry': row['geometry']}
    expected = {1: {'id': 'private_points.1', 'label': 'PRIVATE_A', 'geometry': {'type': 'Point', 'coordinates': [1, 1]}},
                2: {'id': 'private_points.2', 'label': 'PRIVATE_B', 'geometry': {'type': 'Point', 'coordinates': [2, 2]}}}
    if actual != expected: raise ValueError('native feature identities, attributes or coordinates differ')
    return {'count': 2, 'object_ids': [1, 2], 'coordinates_verified': True}


def pixels(body):
    """Bounded independent PNG oracle for the two declared point symbols."""
    if body[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('map is not PNG')
    pos, compressed, palette, header, ended = 8, bytearray(), None, None, False
    while pos < len(body):
        if len(body) - pos < 12: raise ValueError('truncated PNG chunk')
        size = int.from_bytes(body[pos:pos+4], 'big'); kind = body[pos+4:pos+8]
        data = body[pos+8:pos+8+size]; crc = body[pos+8+size:pos+12+size]
        if len(data) != size or len(crc) != 4 or zlib.crc32(kind + data) != int.from_bytes(crc, 'big'):
            raise ValueError('PNG chunk integrity differs')
        pos += size + 12
        if kind == b'IHDR':
            if header is not None or size != 13: raise ValueError('PNG header differs')
            header = struct.unpack('>IIBBBBB', data)
        elif kind == b'IDAT': compressed.extend(data)
        elif kind == b'PLTE': palette = [tuple(data[i:i+3]) for i in range(0, len(data), 3)]
        elif kind == b'tRNS': raise ValueError('opaque map profile excludes transparency-key chunks')
        elif kind == b'IEND':
            if size: raise ValueError('PNG end chunk differs')
            ended = True; break
        elif kind[:1].isupper() and kind != b'PLTE': raise ValueError('unsupported critical PNG chunk')
    if not ended or pos != len(body) or header is None: raise ValueError('PNG closure differs')
    width, height, bits, color, compression, filtering, interlace = header
    if (width, height, bits, compression, filtering, interlace) != (512, 512, 8, 0, 0, 0) or color not in (2, 3, 6):
        raise ValueError('map PNG profile differs')
    channels = {2: 3, 3: 1, 6: 4}[color]; stride = width * channels
    decompressor = zlib.decompressobj()
    decoded = decompressor.decompress(compressed, (stride + 1) * height + 1)
    if len(decoded) != (stride + 1) * height or not decompressor.eof or decompressor.unused_data:
        raise ValueError('PNG expanded size differs')
    rows = []; previous = bytearray(stride)
    for y in range(height):
        offset = y * (stride + 1); mode = decoded[offset]; row = bytearray(decoded[offset+1:offset+stride+1])
        if mode not in range(5): raise ValueError('PNG filter differs')
        for x in range(stride):
            left = row[x-channels] if x >= channels else 0
            up, diagonal = previous[x], previous[x-channels] if x >= channels else 0
            estimate = left + up - diagonal
            distances = [abs(estimate-left), abs(estimate-up), abs(estimate-diagonal)]
            predictor = (left, up, diagonal)[distances.index(min(distances))]
            row[x] = (row[x] + (0, left, up, (left+up)//2, predictor)[mode]) & 255
        rows.append(row); previous = row
    def rgb(x, y):
        row = rows[y]; offset = x * channels
        if color == 3:
            if palette is None or row[x] >= len(palette): raise ValueError('PNG palette differs')
            return palette[row[x]]
        if color == 6 and row[offset+3] != 255: raise ValueError('opaque map expected')
        return tuple(row[offset:offset+3])
    centers = [(128, 384), (256, 256)]
    for x, y in centers:
        if sum(rgb(x+dx, y+dy) == (32, 120, 180) for dx in range(-2, 3) for dy in range(-2, 3)) < 20:
            raise ValueError('declared point symbol missing at expected map coordinate')
    if rgb(0, 0) != (255, 255, 255): raise ValueError('map background differs')
    count = sum(rgb(x, y) != (255, 255, 255) for y in range(height) for x in range(width))
    if not 300 <= count <= 1200: raise ValueError('unexpected non-background coverage')
    return {'size': [512, 512], 'symbol_centers': centers, 'non_background_pixels': count}


class Journey:
    def __init__(self, installation):
        self.runtime = runtime.Runtime(installation)
        self.product = self.runtime.config
        self.secrets = config.secret_material(installation)
        self.rows = []
        self.browsers = []
        self.cleanup_result = None
        self.permission_cleanup = None
        self.permission_events = []

    def request(self, path, *, token=None, method='GET', payload=None, raw_body=None, extra=(), direct=False):
        headers = [('Authorization', 'Bearer ' + token)] if token else []
        headers += list(extra)
        data = json.dumps(payload).encode() if payload is not None else None
        if data is not None: headers.append(('Content-Type', 'application/json'))
        if raw_body is not None:
            if payload is not None or raw_body != EMPTY_TRANSACTION or method != 'POST':
                raise ValueError('only empty no-feature transaction body supported')
            data = raw_body; headers.append(('Content-Type', 'application/xml'))
        if direct:
            if payload is not None: raise ValueError('direct engine writes are excluded')
            rt = self.runtime
            result = subprocess.run([rt.podman, *rt.global_args, 'exec', '-i', config.project_name(self.product) + '-gateway',
                '/opt/ambisgis/python/bin/python3', '-c', INTERNAL_CLIENT],
                input=json.dumps({'path': path, 'method': method, 'headers': headers,
                                  'body': base64.b64encode(data or b'').decode()}).encode(),
                env=rt.environment, cwd=rt.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            if result.returncode or len(result.stdout) > 6 * 1024 * 1024: raise ValueError('direct engine probe failed')
            value = json.loads(result.stdout); body = base64.b64decode(value['body'], validate=True)
            status, received = value['status'], value['headers']
        else:
            connection = http.client.HTTPConnection('127.0.0.1', self.product['listen']['port'], timeout=15)
            try:
                connection.putrequest(method, path)
                for key, value in headers: connection.putheader(key, value)
                if data is not None: connection.putheader('Content-Length', str(len(data)))
                connection.endheaders(data); response = connection.getresponse(); body = response.read(4194305)
                status, received = response.status, response.getheaders()
            finally: connection.close()
        if len(body) > 4194304: raise ValueError('response bound exceeded')
        self.rows.append({'path': path.split('?', 1)[0], 'method': method, 'direct_engine': direct,
                          'status': status, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
        if any(name.lower() == 'location' for name, _ in received): raise ValueError('unexpected data redirect')
        return status, body

    def login(self, role):
        origin = config.service_configuration(self.product)['public_origin']
        browser = TrackedOAuthBrowser(origin, self.secrets['oauth_client'], origin + '/oauth/callback',
                                       self.secrets['oauth_secret'], scope='read write')
        self.browsers.append((role, browser))
        token = browser.exchange(browser.authorize(self.product[role], self.secrets[role + '_password']))
        if not browser.issuance_accounted_for or set(token.scope.split()) != {'read', 'write'}:
            raise ValueError('granted OAuth scope or issuance accounting differs')
        return browser, token

    def run(self):
        try:
            return self.exercise()
        finally:
            self.cleanup_result = self.cleanup_tokens()
            if not self.cleanup_result['complete']:
                raise RuntimeError('Newly created token cleanup is incomplete; journey cannot pass.')

    def cleanup_tokens(self):
        rows, incomplete, seen = [], [], set()
        for role, browser in self.browsers:
            if not browser.issuance_accounted_for:
                incomplete.append(role)
            # Revoke refresh grants first, then the associated access tokens.
            for kind, token in sorted(browser.created_tokens, key=lambda item: item[0] != 'refresh_token'):
                if (kind, token) in seen:
                    continue
                seen.add((kind, token))
                row = {'principal': role, 'kind': kind, 'revoked': False}
                try:
                    response = browser.revoke(token, hint=kind)
                    row.update(status=response.status, revoked=response.status == 200)
                except Exception as error:
                    row['error_type'] = type(error).__name__
                rows.append(row)
        return {'complete': not incomplete and all(row['revoked'] for row in rows),
                'unaccounted_issuance_principals': incomplete, 'tokens': rows}

    def contains_secret(self, text):
        return (any(secret in text for secret in self.secrets.values())
                or any(browser.secrets.matches(text) for _, browser in self.browsers))

    def metadata_oracle(self, body, title=None):
        value = json.loads(body, object_pairs_hook=no_duplicate_keys)
        expected = str(uuid.uuid5(uuid.UUID(self.product['install_id']), 'diagnostic-private-points'))
        if (str(value.get('id')) != expected or value.get('synthetic') is not True or value.get('managed') is not False
                or title is not None and value.get('title') != title):
            raise ValueError('native diagnostic metadata differs')
        return {'id': expected, 'title': value['title'], 'synthetic': True, 'managed': False}

    def protected_reads(self, token, *, allowed, title):
        facts = []
        for direct in (False, True):
            for name, query, oracle in [('wfs', FEATURE_QUERY, features), ('wms' if direct else 'map', MAP_QUERY, pixels)]:
                code, body = self.request(('/geoserver' if direct else '')+'/'+name+'?'+query, token=token, direct=direct)
                if code != (200 if allowed else 403): raise ValueError('item permission data decision differs')
                facts.append({'direct_engine': direct, 'route': name, 'status': code,
                              'oracle': oracle(body) if allowed else None})
        code, body = self.request('/api/v1/installation/sample', token=token)
        if code != (200 if allowed else 403): raise ValueError('item permission metadata decision differs')
        facts.append({'route': 'metadata', 'status': code, 'oracle': self.metadata_oracle(body,title) if allowed else None})
        return facts

    def item_permission_roundtrip(self, viewer, title):
        phases = []
        # Keep this exact access token through grant, revoke and regrant. The
        # final positive phase demonstrates it stayed valid during the denial.
        with PermissionSession(self) as policy:
            for grant in (True, False, True):
                native = policy.change(grant)
                phases.append({'granted': grant, 'native': native,
                               'access_token_sha256': hashlib.sha256(viewer.encode()).hexdigest(),
                               'reads': self.protected_reads(viewer, allowed=grant, title=title)})
        if self.permission_cleanup['native'].get('sequence_complete') is not True:
            raise ValueError('native permission sequence was incomplete')
        self.protected_reads(viewer, allowed=False, title=title)
        return {'same_valid_token': True, 'phases': phases, 'restoration': self.permission_cleanup,
                'identity': policy.initial['identity']}

    def route_negatives(self, owner, viewer):
        checks = []
        for direct in (False, True):
            prefix = '/geoserver' if direct else ''
            for name, query in [('wfs', FEATURE_QUERY), ('wms' if direct else 'map', MAP_QUERY)]:
                target = prefix+'/'+name+'?'+query
                # Actual separate wire headers, including case variation/order.
                for token, extra in [(owner, [('Authorization','Bearer '+owner)]),
                                     (owner, [('authorization','Bearer '+viewer)]),
                                     (viewer, [('Authorization','Bearer '+owner)])]:
                    code, _ = self.request(target, token=token, extra=extra, direct=direct)
                    if code != 403: raise ValueError('duplicate Authorization was not denied')
                    checks.append({'case': 'duplicate_authorization', 'direct_engine': direct, 'route': name, 'status': code})
                for authorization in ('', 'Basic invalid', 'bearer '+owner, 'Bearer malformed'):
                    code, _ = self.request(target, extra=[('Authorization',authorization)], direct=direct)
                    if code != 403: raise ValueError('malformed Authorization was not denied')
                    checks.append({'case': 'malformed_authorization', 'direct_engine': direct, 'route': name, 'status': code})
                malformed = [query+'&REQUEST=GetFeature', query+'&%72equest=GetFeature', query+'&unexpected=value',
                    query.replace('service=', 'broken&service=', 1), query.replace('service=', 'service=%ZZ', 1),
                    query.replace('version=', 'version=unsupported', 1), query.replace('fixture%3Aprivate_points','fixture%3Aother_points'),
                    query.replace('request=GetFeature','request=Transaction').replace('request=GetMap','request=GetCapabilities')]
                if name != 'wfs':
                    malformed += [query.replace('width=512','width=0'),query.replace('bbox=0%2C0%2C4%2C4','bbox=0%2C0%2C9%2C9')]
                for changed in malformed:
                    code, _ = self.request(prefix+'/'+name+'?'+changed, token=owner, direct=direct)
                    if code not in (400,403): raise ValueError('malformed or unsupported data request accepted')
                    checks.append({'case': 'malformed_query', 'direct_engine': direct, 'route': name, 'status': code})
                for method in ('POST','PUT','DELETE'):
                    code, _ = self.request(target, token=owner, method=method, direct=direct)
                    if code != (403 if direct else 404): raise ValueError('unsupported write method was not denied')
                    checks.append({'case': 'write_method', 'direct_engine': direct, 'route': name, 'method': method, 'status': code})
            for path in ('/geoserver/rest/workspaces','/geoserver/web/'):
                code, _ = self.request(path, token=owner, direct=direct)
                if code != (403 if direct else 404): raise ValueError('engine administration route exposed')
                checks.append({'case': 'admin_route', 'direct_engine': direct, 'status': code})
            code, _ = self.request(prefix+'/wfs', token=owner, method='POST', raw_body=EMPTY_TRANSACTION, direct=direct)
            if code != (403 if direct else 404): raise ValueError('empty WFS transaction was not denied')
            checks.append({'case': 'empty_transaction', 'direct_engine': direct, 'status': code})
        return checks

    def exercise(self):
        status = self.runtime.status()
        if not status['readiness']['ready'] or any(row['process'] != 'running' for row in status['services'].values()):
            raise ValueError('installation is not ready')
        owner_browser, owner_tokens = self.login('owner'); viewer_browser, viewer_tokens = self.login('viewer')
        owner, viewer = owner_tokens.access_token, viewer_tokens.access_token
        checks = []
        for direct in (False, True):
            prefix = '/geoserver' if direct else ''
            for path, query, oracle in [('wfs', FEATURE_QUERY, features), ('wms' if direct else 'map', MAP_QUERY, pixels)]:
                target = prefix + '/' + path + '?' + query
                code, body = self.request(target, token=owner, direct=direct)
                if code != 200: raise ValueError('owner data request failed')
                checks.append({'route': path, 'direct_engine': direct, 'oracle': oracle(body)})
                for token in (None, viewer):
                    code, _ = self.request(target, token=token, direct=direct)
                    if code != 403: raise ValueError('private data access was not denied')
                code, _ = self.request(target, token=viewer, direct=direct,
                    extra=[('X-AmbisGIS-Policy-Key', self.secrets['policy_key']), ('X-AmbisGIS-Resource', 'fixture:private_points')])
                if code != 403: raise ValueError('forged internal headers changed access')
                code, _ = self.request(target + '&request=GetFeature', token=owner, direct=direct)
                if code not in (400, 403): raise ValueError('duplicate query was not rejected')
        path = '/api/v1/installation/sample'
        code, body = self.request(path, token=owner)
        if code != 200: raise ValueError('owner metadata read failed')
        value = self.metadata_oracle(body)
        expected = str(uuid.uuid5(uuid.UUID(self.product['install_id']), 'diagnostic-private-points'))
        for token in (None, viewer):
            for method in ('GET', 'PATCH'):
                code, _ = self.request(path, token=token, method=method, payload={'title': 'forbidden'} if method == 'PATCH' else None)
                if code != 403: raise ValueError('private metadata operation was not denied')
        permissions = self.item_permission_roundtrip(viewer, value['title'])
        negatives = self.route_negatives(owner, viewer)
        unchanged = self.protected_reads(owner, allowed=True, title=value['title'])
        title = 'Installation acceptance retained title'
        code, body = self.request(path, token=owner, method='PATCH', payload={'title': title})
        if code != 200 or json.loads(body).get('title') != title: raise ValueError('owner metadata edit failed')
        code, body = self.request(path, token=owner)
        if code != 200 or json.loads(body).get('title') != title: raise ValueError('metadata edit did not persist')
        revoked = owner_browser.revoke(owner)
        if revoked.status != 200: raise ValueError('native revocation failed')
        for direct in (False, True):
            for path, query in [('wfs', FEATURE_QUERY), ('wms' if direct else 'map', MAP_QUERY)]:
                code, _ = self.request(('/geoserver' if direct else '') + '/' + path + '?' + query, token=owner, direct=direct)
                if code != 403: raise ValueError('revoked token retained data access')
        return {'map_query_oracles': checks, 'metadata_uuid': expected, 'retained_metadata_title': title,
                'native_item_permission_roundtrip': permissions, 'route_negatives': negatives,
                'post_negative_unchanged_oracles': unchanged,
                'revocation_denied_on_both_paths': True,
                'identity_protocol': {'owner': owner_browser.records, 'viewer': viewer_browser.records}}


def main(args):
    output = checked_path(args.output); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    private_directory(output)
    record = {'scope': 'actual protected HTTP slice; lifecycle, relocation, namespace and SELinux qualification separate',
              'full_installation_acceptance': False, 'started': datetime.now(timezone.utc).isoformat(), 'status': 'running',
              'source': {str(p.relative_to(ROOT)): digest(p) for p in (Path(__file__).resolve(), CLIENT, POLICY_PROGRAM)}}
    try:
        journey = Journey(checked_path(args.directory))
        record.update(install_id=journey.product['install_id'], bundle_sha256=journey.product['bundle']['sha256'])
        record['result'] = journey.run(); record['status'] = 'passed'
    except Exception as error:
        record.update(status='failed', error_type=type(error).__name__)
        raise RuntimeError('Protected journey failed; see selected private receipt.') from None
    finally:
        if 'journey' in locals():
            record['requests'] = journey.rows
            record['token_cleanup'] = journey.cleanup_result
            record['permission_cleanup'] = getattr(journey, 'permission_cleanup', None)
            record['permission_events'] = getattr(journey, 'permission_events', [])
        record['finished'] = datetime.now(timezone.utc).isoformat()
        text = json.dumps(record, indent=2, sort_keys=True) + '\n'
        if 'journey' in locals() and journey.contains_secret(text):
            raise RuntimeError('Receipt secret scan failed; no receipt written')
        (output / 'result.json').write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
