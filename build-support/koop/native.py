"""Disposable FND06 read provider. Shared native_contracts owns validation.

Only immutable synthetic snapshots are readable. Catalog authorization is called
before validation/cursor/data for every request. No branch write path exists.
"""
from datetime import datetime, timezone
from contextlib import closing
from decimal import Decimal
import hashlib
import hmac
import http.client
import json
import re
import time

from native_contracts import ContractError, CursorCodec, validate_query

POLICY_CONTEXT = 'live-catalog-object-check-v1'
FIELDS = ('fid', 'object_id', 'name', 'district', 'population', 'elevation', 'observed_at')
TYPES = dict(zip(FIELDS, ('uuid', 'int32', 'string', 'string', 'int32', 'decimal', 'timestamp')))
OPS = {'eq': '=', 'ne': '<>', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}


def column(name):
    if name not in FIELDS:
        raise ContractError('INVALID_REQUEST')
    return '"' + name + '"' + (' COLLATE "C"' if TYPES[name] == 'string' else '')


def parameter(literal):
    if literal['type'] == 'decimal':
        return Decimal(literal['value'])
    return literal['value']


def predicate(node, values):
    if node['op'] in ('and', 'or'):
        return '(' + (' ' + node['op'].upper() + ' ').join(predicate(x, values) for x in node['args']) + ')'
    expression = column(node['field'])
    if node['op'] in ('is_null', 'is_not_null'):
        return expression + (' IS NULL' if node['op'] == 'is_null' else ' IS NOT NULL')
    values.append(parameter(node['value']))
    return expression + ' ' + OPS[node['op']] + ' %s'


def keyset(order, position, values):
    alternatives = []
    for index, entry in enumerate(order):
        if position[index] is None:
            continue  # NULLS LAST: nothing follows NULL except a later tie key.
        terms = []
        for previous, value in zip(order[:index], position[:index]):
            expression = column(previous['field'])
            if value is None:
                terms.append(expression + ' IS NULL')
            else:
                terms.append(expression + ' IS NOT DISTINCT FROM %s')
                values.append(parameter(value))
        expression = column(entry['field'])
        operator = '>' if entry['direction'] == 'asc' else '<'
        terms.append('(' + expression + ' ' + operator + ' %s OR ' + expression + ' IS NULL)')
        values.append(parameter(position[index]))
        alternatives.append('(' + ' AND '.join(terms) + ')')
    return '(' + ' OR '.join(alternatives) + ')' if alternatives else 'FALSE'


def scalar(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    if value is None or type(value) in (str, int, float, bool):
        return value
    return str(value)  # psycopg UUID


class Provider:
    def __init__(self, config, connect, audit):
        self.config, self.connect, self.audit = config, connect, audit
        self.layer = config['layer']
        self.key = bytes.fromhex(config['cursor_key'])
        self.codec = CursorCodec(self.key, self.layer)

    def authorize(self, resource, credential):
        # No caller-supplied resource URI, identity or policy revision reaches the catalog.
        if not isinstance(credential, str) or (credential and not re.fullmatch(r'Bearer [A-Za-z0-9._~-]{20,512}', credential)):
            raise ContractError('NOT_FOUND_OR_FORBIDDEN')
        name = self.config['resources'].get(resource, 'fixture:nonexistent')
        conn = http.client.HTTPConnection('127.0.0.1', self.config['catalog_port'], timeout=3)
        try:
            conn.request('GET', '/internal/policy/read', headers={
                'X-Ambisgis-Policy-Key': self.config['policy_key'],
                'X-Ambisgis-Resource': name, 'Authorization': credential})
            response = conn.getresponse()
            response.read(1)
            status = response.status
        except (OSError, ValueError, http.client.HTTPException):
            status = 503
        finally:
            conn.close()
        self.audit({'event': 'catalog_check', 'resource': resource if resource in self.config['resources'] else 'unknown',
                    'status': status, 'monotonic_ns': time.monotonic_ns()})
        if status != 204:
            raise ContractError('NOT_FOUND_OR_FORBIDDEN' if status == 403 else 'POLICY_UNAVAILABLE')

    def query(self, request, resource, credential, *, c1_offset=0, already_authorized=False):
        if not already_authorized:
            self.authorize(resource, credential)
        normalized = validate_query(request, self.layer)
        scope = hmac.new(self.key, b'credential\0' + resource.encode() + b'\0' + credential.encode(), hashlib.sha256).hexdigest()
        position = self.codec.verify(normalized['cursor'], normalized, scope, POLICY_CONTEXT) if normalized.get('cursor') else None
        values = [normalized['data_revision']]
        clauses = ['data_revision = %s']
        if 'filter' in normalized:
            clauses.append(predicate(normalized['filter'], values))
        if 'bbox' in normalized:
            values.extend(normalized['bbox']['bounds'])
            clauses.append('ST_Intersects(geom, ST_MakeEnvelope(%s,%s,%s,%s,4326))')
        mode = normalized['mode']
        if mode == 'features' and position:
            clauses.append(keyset(normalized['order_by'], position, values))
        base = ' FROM spike.addresses WHERE ' + ' AND '.join(clauses)
        if mode == 'count':
            sql = 'SELECT count(*)' + base
        elif mode == 'extent':
            sql = 'SELECT ST_XMin(e),ST_YMin(e),ST_XMax(e),ST_YMax(e) FROM (SELECT ST_Extent(geom) e' + base + ') bounds'
        else:
            sql = 'SELECT ' + ','.join('"' + x + '"' for x in FIELDS) + ', ST_X(geom),ST_Y(geom)' + base
            sql += ' ORDER BY ' + ','.join(column(x['field']) + ' ' + x['direction'].upper() + ' NULLS LAST' for x in normalized['order_by'])
            sql += ' LIMIT %s'
            values.append(normalized['page_size'] + 1)
            if c1_offset:
                if normalized.get('cursor') or type(c1_offset) is not int or not 0 <= c1_offset <= 1000000:
                    raise ContractError('INVALID_REQUEST')
                sql += ' OFFSET %s'
                values.append(c1_offset)
        start = time.monotonic_ns()
        with closing(self.connect()) as connection, connection:
            connection.set_session(readonly=True)
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '1500ms'")
                cursor.execute("SET LOCAL lock_timeout = '500ms'")
                cursor.execute(sql, values)
                rows = cursor.fetchall()
                cursor.execute('EXPLAIN (FORMAT JSON) ' + sql, values)
                plan = cursor.fetchone()[0]
        record = {'event': 'sql_query', 'mode': mode, 'rows_fetched': len(rows),
                  'elapsed_ms': (time.monotonic_ns() - start) / 1e6,
                  'statement_sha256': hashlib.sha256(sql.encode()).hexdigest(),
                  'statement_template': sql, 'explain': plan, 'c1_offset': c1_offset,
                  'parameter_count': len(values), 'read_only_transaction': True}
        self.audit(record)
        if mode == 'count':
            return {'count': rows[0][0]}
        if mode == 'extent':
            return {'extent': None if rows[0][0] is None else dict(zip(('xmin', 'ymin', 'xmax', 'ymax'), rows[0])),
                    'crs': 'EPSG:4326'}
        more = len(rows) > normalized['page_size']
        selected = rows[:normalized['page_size']]
        features = []
        for row in selected:
            attributes = dict(zip(FIELDS, map(scalar, row[:7])))
            features.append({'fid': attributes['fid'], 'attributes': {x: attributes[x] for x in normalized['fields']},
                             'geometry': {'type': 'Point', 'coordinates': list(row[7:])}})
        token = None
        if more and selected:
            attributes = dict(zip(FIELDS, map(scalar, selected[-1][:7])))
            after = [None if attributes[x['field']] is None else {'type': TYPES[x['field']], 'value': attributes[x['field']]}
                     for x in normalized['order_by']]
            token = self.codec.issue(normalized, scope, POLICY_CONTEXT, after)
        result = {'features': features, 'next_cursor': token, 'exceeded_transfer_limit': more}
        if len(json.dumps(result, allow_nan=False).encode()) > 2 * 1024 * 1024:
            raise ContractError('LIMIT_EXCEEDED')
        return result


TOKEN = re.compile(r"\s*(?:(?P<string>'(?:[^']|'')*')|(?P<number>-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?)|(?P<word>[A-Za-z_][A-Za-z_0-9]*)|(?P<symbol><=|>=|<>|!=|[=<>\(\)]))")


def where_filter(text):
    """Deliberately bounded C1 syntax → native AST, never SQL text passthrough."""
    if text.strip() == '1=1':
        return None
    tokens, offset = [], 0
    while offset < len(text):
        match = TOKEN.match(text, offset)
        if not match:
            if text[offset:].strip():
                raise ContractError('UNSUPPORTED_CAPABILITY')
            break
        tokens.append((match.lastgroup, match.group(match.lastgroup)))
        offset = match.end()
        if len(tokens) > 512:
            raise ContractError('LIMIT_EXCEEDED')
    index = 0
    def peek(value):
        return index < len(tokens) and tokens[index][1].upper() == value
    def take():
        nonlocal index
        if index >= len(tokens):
            raise ContractError('INVALID_REQUEST')
        result = tokens[index]
        index += 1
        return result
    def atom(depth):
        if depth > 8:
            raise ContractError('LIMIT_EXCEEDED')
        if peek('('):
            take(); value = expression(depth + 1)
            if take()[1] != ')':
                raise ContractError('INVALID_REQUEST')
            return value
        kind, field = take()
        if kind != 'word' or field not in FIELDS:
            raise ContractError('INVALID_REQUEST')
        if peek('IS'):
            take(); negate = peek('NOT')
            if negate: take()
            if take()[1].upper() != 'NULL':
                raise ContractError('INVALID_REQUEST')
            return {'op': 'is_not_null' if negate else 'is_null', 'field': field}
        operator = take()[1]
        mapping = {'=': 'eq', '<>': 'ne', '!=': 'ne', '<': 'lt', '<=': 'le', '>': 'gt', '>=': 'ge'}
        if operator not in mapping:
            raise ContractError('UNSUPPORTED_CAPABILITY')
        kind, value = take()
        expected = TYPES[field]
        if expected in ('uuid', 'string', 'timestamp'):
            if kind != 'string': raise ContractError('INVALID_REQUEST')
            value = value[1:-1].replace("''", "'")
        elif expected == 'int32':
            if kind != 'number' or '.' in value: raise ContractError('INVALID_REQUEST')
            value = int(value)
        elif kind != 'number':
            raise ContractError('INVALID_REQUEST')
        return {'op': mapping[operator], 'field': field, 'value': {'type': expected, 'value': value}}
    def conjunction(depth):
        nodes = [atom(depth)]
        while peek('AND'):
            take(); nodes.append(atom(depth))
        return nodes[0] if len(nodes) == 1 else {'op': 'and', 'args': nodes}
    def expression(depth):
        nodes = [conjunction(depth)]
        while peek('OR'):
            take(); nodes.append(conjunction(depth))
        return nodes[0] if len(nodes) == 1 else {'op': 'or', 'args': nodes}
    result = expression(1)
    if index != len(tokens):
        raise ContractError('UNSUPPORTED_CAPABILITY')
    return result


def c1_request(params, layer):
    allowed = {'f', 'where', 'outFields', 'orderByFields', 'resultOffset', 'resultRecordCount',
               'returnCountOnly', 'returnExtentOnly', 'returnGeometry', 'outSR', 'geometry',
               'geometryType', 'inSR', 'spatialRel', 'serviceRevision', 'dataRevision'}
    if set(params) - allowed or any(not isinstance(v, str) for v in params.values()):
        raise ContractError('UNSUPPORTED_CAPABILITY')
    if params.get('f', 'json') != 'json':
        raise ContractError('UNSUPPORTED_CAPABILITY')
    def boolean(name, default=False):
        value = params.get(name, str(default).lower()).lower()
        if value not in ('true', 'false'): raise ContractError('INVALID_REQUEST')
        return value == 'true'
    count, extent = boolean('returnCountOnly'), boolean('returnExtentOnly')
    if count and extent:
        raise ContractError('UNSUPPORTED_CAPABILITY')
    if not boolean('returnGeometry', True):
        raise ContractError('UNSUPPORTED_CAPABILITY')
    request = {'schema_version': 1, 'layer_id': layer['layer_id'],
               'service_revision': params.get('serviceRevision'), 'data_revision': params.get('dataRevision'),
               'mode': 'count' if count else 'extent' if extent else 'features',
               'output_crs': 'EPSG:' + params.get('outSR', '4326')}
    expression = where_filter(params.get('where', '1=1'))
    if expression: request['filter'] = expression
    if 'geometry' in params:
        if params.get('geometryType') != 'esriGeometryEnvelope' or params.get('inSR', '4326') != '4326' or params.get('spatialRel', 'esriSpatialRelIntersects') != 'esriSpatialRelIntersects':
            raise ContractError('UNSUPPORTED_CAPABILITY')
        try:
            bounds = [float(x) for x in params['geometry'].split(',')]
        except ValueError:
            raise ContractError('INVALID_REQUEST') from None
        request['bbox'] = {'crs': 'EPSG:4326', 'bounds': bounds}
    elif {'geometryType', 'inSR', 'spatialRel'} & params.keys():
        raise ContractError('INVALID_REQUEST')
    offset = 0
    if request['mode'] == 'features':
        if params.get('outFields', '*') != '*':
            request['fields'] = [x.strip() for x in params['outFields'].split(',')]
        if 'orderByFields' in params:
            order = []
            for part in params['orderByFields'].split(','):
                tokens = part.strip().split()
                if len(tokens) not in (1, 2): raise ContractError('INVALID_REQUEST')
                order.append({'field': tokens[0], 'direction': tokens[1].lower() if len(tokens) == 2 else 'asc'})
            request['order_by'] = order
        for name in ('resultOffset', 'resultRecordCount'):
            if not re.fullmatch(r'0|[1-9][0-9]{0,6}', params.get(name, '0')):
                raise ContractError('INVALID_REQUEST')
        request['page_size'] = int(params.get('resultRecordCount', '100'))
        offset = int(params.get('resultOffset', '0'))
        if offset > 1000000: raise ContractError('LIMIT_EXCEEDED')
    elif {'outFields', 'orderByFields', 'resultOffset', 'resultRecordCount'} & params.keys():
        raise ContractError('INVALID_REQUEST')
    return validate_query(request, layer), offset


def koop_data(result, layer):
    """Native typed results → provider GeoJSON only; Koop owns C1 encoding."""
    if 'count' in result:
        return {'type': 'FeatureCollection', 'features': [], 'count': result['count']}
    if 'extent' in result:
        extent = result['extent']
        return {'type': 'FeatureCollection', 'features': [], 'extent':
                dict(extent, spatialReference={'wkid': 4326}) if extent else None}
    features = []
    for feature in result['features']:
        properties = dict(feature['attributes'])
        oid = properties.get('object_id')
        if oid is not None and (type(oid) is not int or not 0 < oid < 2**31):
            raise ContractError('UNSUPPORTED_CAPABILITY')
        if properties.get('elevation') is not None:
            original = Decimal(properties['elevation'])
            converted = float(original)
            if Decimal(str(converted)) != original:
                raise ContractError('UNSUPPORTED_CAPABILITY')
            properties['elevation'] = converted
        features.append({'type': 'Feature', 'id': feature['fid'], 'properties': properties, 'geometry': feature['geometry']})
    # Koop provider vocabulary differs from its Esri output vocabulary. Winnow
    # specifically recognizes capitalized Date when converting to epoch ms.
    field_types = {'uuid': 'GUID', 'int32': 'Integer', 'string': 'String',
                   'decimal': 'Double', 'timestamp': 'Date'}
    fields = [{'name': f['name'], 'alias': f['name'], 'type': field_types[f['type']],
               'nullable': f['nullable'], 'editable': False,
               **({'length': f['max_length']} if f['type'] == 'string' else {})} for f in layer['fields']]
    return {'type': 'FeatureCollection', 'features': features,
            'metadata': {'name': 'Synthetic addresses', 'idField': 'object_id', 'geometryType': 'Point',
                         'fields': fields, 'maxRecordCount': 1000, 'crs': 4326,
                         'exceededTransferLimit': result['exceeded_transfer_limit']},
            'filtersApplied': {name: True for name in ('where', 'geometry', 'spatialRel', 'orderByFields',
                                                      'resultOffset', 'offset', 'resultRecordCount')}}
