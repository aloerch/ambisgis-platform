"""Actual HTTP assertions over synthetic owned catalog and PostGIS, not mocks."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from functools import cmp_to_key
import hashlib
import hmac
import http.client
import json
from pathlib import Path
import subprocess
import time
import urllib.parse

from protocol_probe import OAuthBrowser
from native import ContractError, koop_data
from native_contracts import CursorCodec, validate_query, validate_schema
from runtime_fixture import connect


def exercise(config, secrets, catalog_process):
    output = Path(config['output'])
    rows = []
    responses = output / 'responses'; responses.mkdir()
    layer = config['layer']
    context = {key: layer[key] for key in ('layer_id', 'service_revision', 'data_revision')}
    c1_context = {'serviceRevision': layer['service_revision'], 'dataRevision': layer['data_revision'], 'f': 'json'}
    sample = []
    with (output / 'addresses.ndjson').open() as stream:
        for _ in range(12): sample.append(json.loads(next(stream)))
    def check(name, condition, **detail):
        rows.append({'case': name, 'passed': bool(condition), **detail})
        return bool(condition)
    def request(name, port, path, *, method='GET', body=None, headers=None):
        start = time.monotonic_ns()
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            payload = response.read(2 * 1024 * 1024 + 1)
            status = response.status
            response_headers = response.getheaders()
        finally:
            connection.close()
        for value in secrets:
            if value and value.encode() in payload: raise RuntimeError('response secret disclosure')
        target = responses / (name + '.json')
        target.write_bytes(payload)
        check(name + '-bounded', len(payload) <= 2 * 1024 * 1024,
              status=status, elapsed_ms=(time.monotonic_ns() - start) / 1e6,
              response_sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
        try: value = json.loads(payload)
        except ValueError: value = {'invalid_json': True}
        if port == config['backend_port'] and 'error' in value:
            try: validate_schema('native-error', value)
            except ContractError: check(name + '-native-error-schema', False)
            else: check(name + '-native-error-schema', True)
        return status, value
    def native(name, query, credential='', resource='public_points', **headers):
        return request(name, config['backend_port'], '/native', method='POST',
            body=json.dumps({'resource': resource, 'query': {'schema_version': 1, **context, **query}}),
            headers={'Content-Type': 'application/json', 'X-Spike-Key': config['backend_key'], 'Authorization': credential, **headers})
    def c1(name, params=None, credential='', resource='public_points', method='GET', path=None, context=True, **headers):
        params = {**(c1_context if context else {}), **(params or {})}
        encoded = urllib.parse.urlencode(params)
        endpoint = path or '/owned/rest/services/' + resource + '/FeatureServer/0/query'
        return request(name, config['koop_port'], endpoint + ('?' + encoded if method == 'GET' else ''), method=method,
                       body=encoded if method == 'POST' else None,
                       headers={'Authorization': credential, **({'Content-Type': 'application/x-www-form-urlencoded'} if method == 'POST' else {}), **headers})
    def ids(value):
        return [x['attributes']['object_id'] for x in value.get('features', [])]
    def denied(value):
        return isinstance(value, dict) and 'error' in value and not {'features', 'count', 'extent', 'fields'} & value.keys()
    def mutate(action):
        from runtime import execute, HERE
        execute([config['python'], str(HERE.parent / 'geonode/catalog_fixture.py'), '--config', str(output / 'private.json'), action],
                config['environment'], output, 'mutation-' + action, secrets)
    tokens = {}
    issuance = []
    for user in ('fixture-reader', 'fixture-outsider'):
        browser = OAuthBrowser(config['site_url'].rstrip('/'), config['client_id'], config['redirect_uri'], config['client_secret'])
        grant = browser.authorize(user, config['passwords'][user])
        token = browser.exchange(grant)
        secrets.extend(browser.secrets.sensitive_values())
        secrets.extend([token.access_token, token.refresh_token, grant.code, grant.verifier, grant.state])
        check('native-oauth-' + user, token.response.status == 200 and token.scope == 'read')
        issuance.append({'principal': user, 'requests': browser.records, 'scope': token.scope, 'flow': 'native authorization_code with PKCE S256'})
        tokens[user] = 'Bearer ' + token.access_token
    (output / 'issuance.json').write_text(json.dumps(issuance, indent=2) + '\n')
    reader, outsider = tokens['fixture-reader'], tokens['fixture-outsider']
    status, value = native('native-total', {'mode': 'count'})
    total = json.loads((output / 'fixture.json').read_text())['addresses']
    check('native-full-count', status == 200 and value == {'count': total})
    status, value = c1('c1-first', {'where': 'object_id <= 12', 'resultRecordCount': '5'})
    check('c1-page-one', ids(value) == [1, 2, 3, 4, 5] and value.get('exceededTransferLimit') is True)
    # Continue collecting diagnostics after unexpected raw codec behavior.
    for offset, expected, more in [(5, [6, 7, 8, 9, 10], True), (10, [11, 12], False), (12, [], False)]:
        _, value = c1('c1-offset-' + str(offset), {'where': 'object_id <= 12', 'resultRecordCount': '5', 'resultOffset': str(offset)})
        check('c1-offset-values-' + str(offset), ids(value) == expected and value.get('exceededTransferLimit') is more)
    _, value = c1('c1-full-small', {'where': 'object_id <= 12', 'resultRecordCount': '12'})
    expected_types = {'fid': 'esriFieldTypeGUID', 'object_id': 'esriFieldTypeOID', 'name': 'esriFieldTypeString',
                      'district': 'esriFieldTypeString', 'population': 'esriFieldTypeInteger', 'elevation': 'esriFieldTypeDouble', 'observed_at': 'esriFieldTypeDate'}
    check('query-seven-field-types', {x['name']: x['type'] for x in value.get('fields', [])} == expected_types)
    features = value.get('features', [])
    if len(features) == 12:
        for original, encoded in zip(sample, features):
            p, a = original['properties'], encoded['attributes']
            stamp = int(datetime.fromisoformat(p['observed_at'].replace('Z', '+00:00')).timestamp() * 1000)
            check('c1-scalars-' + str(p['object_id']), a.get('fid') == p['fid'] and a.get('object_id') == p['object_id']
                  and a.get('name') == p['name'] and a.get('district') == p['district'] and a.get('population') == p['population']
                  and Decimal(str(a.get('elevation'))) == Decimal(str(p['elevation'])) and a.get('observed_at') == stamp
                  and encoded.get('geometry') == {'x': original['geometry']['coordinates'][0], 'y': original['geometry']['coordinates'][1]})
    else: check('c1-twelve-scalars', False, observed_features=len(features))
    _, value = c1('c1-projection', {'where': 'object_id = 1', 'outFields': 'name'})
    check('c1-selected-field-no-hash-id', len(value.get('features', [])) == 1 and value['features'][0]['attributes'] == {'name': 'Alpha'}
          and value.get('objectIdFieldName') == 'object_id')
    cases = [("name IS NULL AND object_id <= 12", 2), ("name = '' AND object_id <= 12", 2),
             ("name = 'O''Neil' AND object_id <= 12", 1), ("name = '東京' AND object_id <= 12", 1),
             ("population >= 50 AND object_id <= 12", 7), ("(district = 'north' OR district = 'south') AND object_id <= 12", 6),
             ("elevation = 123.456 AND object_id <= 12", 3), ("name = 'missing'", 0)]
    for index, (where, expected) in enumerate(cases):
        _, value = c1('c1-count-' + str(index), {'where': where, 'returnCountOnly': 'true'})
        check('c1-count-predicate-' + str(index), value == {'count': expected})
    _, getvalue = c1('c1-unicode-get', {'where': "name = '東京' AND object_id <= 12", 'returnCountOnly': 'false'})
    _, postvalue = c1('c1-unicode-post', {'where': "name = '東京' AND object_id <= 12", 'returnCountOnly': 'false'}, method='POST')
    check('c1-get-post-unicode-false-equivalent', getvalue == postvalue and ids(getvalue) == [5])
    _, value = c1('c1-count-all', {'returnCountOnly': 'true'})
    check('c1-count-not-page', value == {'count': total})
    _, value = c1('c1-extent-small', {'where': 'object_id <= 12', 'returnExtentOnly': 'true'})
    coordinates = [x['geometry']['coordinates'] for x in sample]
    check('c1-full-filter-extent', value == {'extent': {'xmin': min(x[0] for x in coordinates), 'ymin': min(x[1] for x in coordinates),
          'xmax': max(x[0] for x in coordinates), 'ymax': max(x[1] for x in coordinates), 'spatialReference': {'wkid': 4326}}})
    _, value = c1('c1-empty-extent', {'where': "name = 'missing'", 'returnExtentOnly': 'true'})
    check('c1-empty-extent-null', value == {'extent': None})
    _, value = c1('c1-bbox', {'geometry': ','.join(map(str, [coordinates[0][0], coordinates[0][1], coordinates[2][0], coordinates[2][1]])),
                            'geometryType': 'esriGeometryEnvelope', 'where': 'object_id <= 12'})
    check('c1-inclusive-bbox', ids(value) == [1, 2, 3])
    # Native opaque keyset traverses ties, nullable strings and descending order.
    query = {'mode': 'features', 'filter': {'op': 'le', 'field': 'object_id', 'value': {'type': 'int32', 'value': 12}},
             'order_by': [{'field': 'name', 'direction': 'desc'}], 'page_size': 3}
    def compare(a, b):
        x, y = a['properties']['name'], b['properties']['name']
        if x is None or y is None:
            first = 0 if x is y else 1 if x is None else -1
        else: first = (y.encode() > x.encode()) - (y.encode() < x.encode())
        return first or a['properties']['object_id'] - b['properties']['object_id']
    expected = [x['properties']['object_id'] for x in sorted(sample, key=cmp_to_key(compare))]
    actual, cursor, first_cursor = [], None, None
    for index in range(5):
        status, value = native('native-keyset-' + str(index), {**query, **({'cursor': cursor} if cursor else {})}, reader, 'group_points')
        check('native-keyset-response-' + str(index), status == 200 and 'features' in value)
        actual.extend(ids(value)); cursor = value.get('next_cursor')
        if index == 0: first_cursor = cursor
        if not cursor: break
    check('native-keyset-no-gaps-ties-null-desc', actual == expected and len(set(actual)) == 12)
    if first_cursor:
        for name, changes, credential in [('tampered', {'cursor': first_cursor[:-1] + ('A' if first_cursor[-1] != 'A' else 'B')}, reader),
            ('changed-query', {'cursor': first_cursor, 'page_size': 4}, reader),
            ('changed-principal', {'cursor': first_cursor}, outsider),
            ('changed-projection', {'cursor': first_cursor, 'fields': ['name']}, reader),
            ('changed-revision', {'cursor': first_cursor, 'data_revision': '20000000-0000-4000-8000-000000000006'}, reader)]:
            status, value = native('native-cursor-' + name, {**query, **changes}, credential, 'group_points')
            check('native-cursor-reject-' + name, status in (400, 403) and denied(value))
        status, value = native('native-cursor-cross-resource', {**query, 'cursor': first_cursor}, reader, 'public_points')
        check('native-cursor-resource-bound', status == 400 and value.get('error', {}).get('code') == 'INVALID_CURSOR')
        key = bytes.fromhex(config['cursor_key'])
        normalized = validate_query({'schema_version': 1, **context, **query}, layer)
        principal_scope = hmac.new(key, b'credential\0group_points\0' + reader.encode(), hashlib.sha256).hexdigest()
        codec = CursorCodec(key, layer)
        position = codec.verify(first_cursor, normalized, principal_scope, 'live-catalog-object-check-v1')
        expired = codec.issue(normalized, principal_scope, 'live-catalog-object-check-v1', position, now=int(time.time()) - 301)
        status, value = native('native-cursor-expired', {**query, 'cursor': expired}, reader, 'group_points')
        check('native-cursor-expiry', status == 400 and value.get('error', {}).get('code') == 'INVALID_CURSOR')
        with connect(config['database']) as db, db.cursor() as sql:
            sql.execute('INSERT INTO spike.addresses SELECT %s,fid,object_id,%s,district,population,elevation,observed_at,geom FROM spike.addresses WHERE data_revision=%s AND object_id=1',
                        ['20000000-0000-4000-8000-000000000006', 'Concurrent new revision', layer['data_revision']])
        _, value = native('native-old-snapshot-after-new-revision', {**query, 'cursor': first_cursor}, reader, 'group_points')
        check('native-stable-snapshot', ids(value) == expected[3:6])
        mutate('group-remove')
        status, value = native('native-revoked-cursor', {**query, 'cursor': first_cursor}, reader, 'group_points')
        check('revocation-before-cursor', status == 403 and denied(value))
        mutate('group-add')
    # Positive data/metadata/count/extent authorization across actual native grants.
    for resource, credential, allowed in [('private_points', '', False), ('private_points', outsider, False),
                                           ('private_points', reader, True), ('missing', reader, False)]:
        for mode, params in [('features', {}), ('count', {'returnCountOnly': 'true'}), ('extent', {'returnExtentOnly': 'true'})]:
            status, value = c1('permission-' + resource + '-' + ('anon' if not credential else 'reader' if credential == reader else 'outsider') + '-' + mode,
                          params, credential, resource)
            valid_mode = (mode == 'features' and len(value.get('features', [])) == 100 and ids(value) == list(range(1, 101))) or (mode == 'count' and value == {'count': total}) or (mode == 'extent' and isinstance(value.get('extent'), dict) and {'xmin', 'ymin', 'xmax', 'ymax', 'spatialReference'} == set(value['extent']))
            check('permission-' + resource + '-' + mode + '-' + str(allowed), (status == 200 and valid_mode) if allowed else denied(value) and value['error'].get('code') == 400)
    _, metadata = c1('metadata-public', {'f': 'json'}, path='/owned/rest/services/public_points/FeatureServer/0', context=False)
    check('metadata-seven-fields-truthful', len(metadata.get('fields', [])) == 7 and metadata.get('supportedQueryFormats') == 'JSON'
          and metadata.get('capabilities') == 'Query' and metadata.get('supportsStatistics') is False
          and metadata.get('maxRecordCount') == 1000 and metadata.get('supportsPagination') is True
          and not any(x in metadata for x in ('editingInfo', 'templates', 'timeInfo', 'supportsQuantizationEditMode')))
    check('metadata-no-broad-advanced-query-claim', 'supportsAdvancedQueries' not in metadata
          and metadata.get('advancedQueryCapabilities', {}).get('supportsOrderBy') is True)
    field_map = {x['name']: x for x in metadata.get('fields', [])}
    types = {'fid': 'esriFieldTypeGUID', 'object_id': 'esriFieldTypeOID', 'name': 'esriFieldTypeString',
             'district': 'esriFieldTypeString', 'population': 'esriFieldTypeInteger', 'elevation': 'esriFieldTypeDouble', 'observed_at': 'esriFieldTypeDate'}
    check('metadata-types-nullability', set(field_map) == set(types) and all(field_map[k]['type'] == v for k, v in types.items())
          and all(field_map[k]['nullable'] == (k in ('name', 'elevation')) for k in types))
    _, value = c1('metadata-private', {'f': 'json'}, path='/owned/rest/services/private_points/FeatureServer/0', context=False)
    check('metadata-private-denied', denied(value))
    mutate('public-revoke')
    _, value = c1('revoke-public-count', {'returnCountOnly': 'true'})
    check('public-revoke-no-positive-cache', denied(value))
    mutate('public-restore')
    mutate('disable-reader')
    _, value = c1('disabled-reader-count', {'returnCountOnly': 'true'}, reader, 'private_points')
    check('disabled-user-no-positive-cache', denied(value))
    mutate('enable-reader')
    for index, params in enumerate([{'f': 'pbf'}, {'f': 'geojson'}, {'outStatistics': '[]'}, {'returnCountOnly': 'true', 'returnExtentOnly': 'true'},
                                  {'where': '1=1; DROP TABLE spike.addresses'}, {'where': 'population + 1 > 0'}, {'where': "name = 'x' OR 1=1"},
                                  {'resultRecordCount': '1001'}, {'resultOffset': '-1'}, {'outSR': '2230'}, {'returnGeometry': 'false'},
                                  {'returnCountOnly': 'bogus'}, {'dataRevision': '20000000-0000-4000-8000-000000000006'}]):
        _, value = c1('unsupported-query-' + str(index), params)
        check('unsupported-query-denied-' + str(index), denied(value))
    for index, path in enumerate(['/owned/rest/generateToken', '/owned/rest/info', '/owned/rest/services/public_points/MapServer',
                                 '/owned/rest/services/public_points/FeatureServer/0/queryRelatedRecords',
                                 '/owned/rest/services/public_points/FeatureServer/0/generateRenderer', '/status']):
        status, value = request('unsupported-route-' + str(index), config['koop_port'], path)
        check('unsupported-route-denied-' + str(index), status == 404 and denied(value))
    for name, raw, headers in [('oversize', 'x=' + 'a' * 32769, {}), ('bad-percent', 'where=%C3', {}),
                               ('duplicate', 'f=json&f=pbf', {}), ('compressed', 'x=x', {'Content-Encoding': 'gzip'}),
                               ('spoofed-policy', 'f=json', {'X-Ambisgis-Resource': 'fixture:public_points'}),
                               ('long-credential', 'f=json', {'Authorization': 'Bearer ' + 'a' * 600})]:
        status, value = request('http-' + name, config['koop_port'], '/owned/rest/services/public_points/FeatureServer/0/query', method='POST', body=raw,
                               headers={'Content-Type': 'application/x-www-form-urlencoded', **headers})
        check('http-reject-' + name, status in (400, 403, 413) and denied(value))
    status, value = request('backend-direct-denied', config['backend_port'], '/native', method='POST', body='{}', headers={'Content-Type': 'application/json'})
    check('backend-key-required', status == 403 and denied(value))
    for method in ('GET', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'BREW'):
        status, value = request('native-method-' + method.lower(), config['backend_port'], '/native', method=method)
        check('native-method-rejected-' + method.lower(), status == 405 and value.get('error', {}).get('code') == 'UNSUPPORTED_CAPABILITY')
    connection = http.client.HTTPConnection('127.0.0.1', config['backend_port'], timeout=5)
    try:
        connection.request('HEAD', '/native')
        response = connection.getresponse()
        check('native-head-rejected-without-body', response.status == 405 and response.read() == b'' and response.getheader('Content-Length') == '0')
    finally: connection.close()
    for name, body in [('utf16', json.dumps({'resource': 'public_points', 'query': {'schema_version': 1, **context, 'mode': 'count'}}).encode('utf-16')),
                       ('invalid-utf8', b'{"resource":"public_points","query":\xff}')]:
        status, value = request('backend-' + name, config['backend_port'], '/native', method='POST', body=body,
                               headers={'Content-Type': 'application/json', 'X-Spike-Key': config['backend_key']})
        check('backend-strict-utf8-' + name, status == 400 and value.get('error', {}).get('code') == 'INVALID_REQUEST')
    # A genuine lock conflict reaches the real read-only SQL boundary and fails boundedly.
    connection = connect(config['database'])
    try:
        with connection.cursor() as cursor: cursor.execute('LOCK spike.addresses IN ACCESS EXCLUSIVE MODE')
        begin = time.monotonic()
        status, value = native('native-lock-timeout', {'mode': 'count'}, reader, 'private_points')
        check('real-db-lock-timeout', status == 503 and denied(value) and value['error'].get('code') == 'LIMIT_EXCEEDED'
              and value['error'].get('retryable') is True and time.monotonic() - begin < 3)
    finally:
        connection.rollback(); connection.close()
    for name, property_name, value in [('long-decimal', 'elevation', '123456789.123456789123456789'), ('large-id', 'object_id', 2**53 + 1)]:
        feature = {'fid': sample[0]['id'], 'attributes': dict(sample[0]['properties']), 'geometry': sample[0]['geometry']}
        feature['attributes'][property_name] = value
        try: koop_data({'features': [feature], 'exceeded_transfer_limit': False}, layer)
        except ContractError: check('c1-native-out-of-range-' + name, True)
        else: check('c1-native-out-of-range-' + name, False)
    stats = json.loads((output / 'koop-stats.json').read_text())
    check('explicit-cache-never-stores', stats['cacheInsert'] == 0 and stats['cacheRetrieve'] > 0 and stats['authorize'] >= stats['getData'])
    audit = [json.loads(x) for x in (output / 'native-audit.jsonl').read_text().splitlines()]
    queries = [x for x in audit if x['event'] == 'sql_query']
    check('db-page-fetch-bounded', all(x['rows_fetched'] <= 1001 for x in queries) and any(x['rows_fetched'] == 6 for x in queries))
    catalog_process.terminate(); catalog_process.wait(timeout=15)
    for mode, params in [('features', {}), ('count', {'returnCountOnly': 'true'}), ('extent', {'returnExtentOnly': 'true'})]:
        status, value = native('native-catalog-outage-' + mode, {'mode': mode}, reader, 'private_points')
        check('native-policy-outage-fails-closed-' + mode, status == 503 and value.get('error', {}).get('code') == 'POLICY_UNAVAILABLE')
        _, value = c1('c1-catalog-outage-' + mode, params, reader, 'private_points')
        check('c1-policy-outage-fails-closed-' + mode, denied(value) and value['error'].get('code') == 503)
    _, value = c1('c1-metadata-outage', {'f': 'json'}, reader, path='/owned/rest/services/private_points/FeatureServer/0', context=False)
    check('c1-policy-outage-metadata', denied(value) and value['error'].get('code') == 503)
    final_audit = [json.loads(x) for x in (output / 'native-audit.jsonl').read_text().splitlines()]
    check('catalog-outage-no-sql', sum(x['event'] == 'sql_query' for x in final_audit) == len(queries))
    result = {'passed': all(x['passed'] for x in rows), 'assertions': len(rows), 'cases': rows, 'koop_stats': stats,
              'sql_statements': len(queries), 'catalog_checks': sum(x['event'] == 'catalog_check' for x in audit),
              'limitations': ['All seven SQL fields fetched internally; no projection-pushdown claim.',
                'C1 resultOffset can scan its prefix in PostgreSQL; memory transfer bounded to page+1, not constant-time deep paging.',
                'Raw EXPLAIN predicates are retained only for this explicitly synthetic private fixture.',
                'No named ArcGIS desktop client, Windows, C1 adoption, distribution or production OIDC claim.']}
    (output / 'tests.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return result
