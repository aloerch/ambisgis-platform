#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic, wholly synthetic GIS fixtures; no product capability claim.

Generation uses only the Python standard library. ``verify-native`` deliberately
requires the selected owned QGIS/GDAL runtime; it never installs dependencies.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import traceback
import uuid
import xml.etree.ElementTree as ET

VERSION = 1
DEFAULT_SEED = 2409
MAX_ADDRESSES = 1_000_000
OWNED_QGIS_COMMIT = '86af40542b219b0da6df1a43914413443330c0c0'
FONT_SHA256 = '08a82cf71e13669f725bccdfeff7ed8dc0e43ffdeac22633074399098112d3e3'
FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'synthetic-corpus'
NAMES = ('Alpha', None, '', 'München', '東京', "O'Neil", 'line\nbreak',
         'naïve', 'zero', None, '', 'Ωmega')
DISTRICTS = ('north', 'south', 'east', 'west')
ELEVATIONS = (-1.125, 0.0, 123.456, 2.25)
TIMES = ('2026-01-01T00:00:00Z', '2026-01-01T01:00:00+01:00',
         '2025-12-31T16:00:00-08:00')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stable_id(kind, index, seed=DEFAULT_SEED):
    """Identity includes fixture generation, dataset, seed and zero-based index."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL,
                         f'https://example.invalid/ambisgis/synthetic/v1/{seed}/{kind}/{index}'))


def validate_parameters(seed, count):
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    if type(count) is not int or not 12 <= count <= MAX_ADDRESSES:
        raise ValueError('addresses must be between 12 and 1000000')


def iter_addresses(seed=DEFAULT_SEED, count=12):
    """Stream GeoJSON Features. The first twelve rows are a fixed semantic cycle.

    ObjectIDs are stable positive signed-32-bit values. Large native IDs live in
    a separate fixture and must not silently enter the bounded C1 profile.
    """
    validate_parameters(seed, count)
    offset = seed % 100 / 1_000_000
    for index in range(count):
        fid = stable_id('addresses', index, seed)
        yield {'type': 'Feature', 'id': fid,
               'properties': {'fid': fid, 'object_id': index + 1,
                              'name': NAMES[index % 12],
                              'district': DISTRICTS[index % 4],
                              'population': (index % 12) * 10,
                              'elevation': ELEVATIONS[index % 4],
                              'observed_at': TIMES[index % 3]},
               'geometry': {'type': 'Point', 'coordinates': [
                   round(-117 + (index % 1000) / 10000 + offset, 6),
                   round(32 + (index // 1000) / 10000 + offset, 6)]}}


def feature(kind, index, geometry, properties, seed):
    return {'type': 'Feature', 'id': stable_id(kind, index, seed),
            'properties': {'fid': stable_id(kind, index, seed), **properties},
            'geometry': geometry}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def write_features(path, features, ndjson=None):
    """One pass, bounded memory even for the million-row fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    other = ndjson.open('xb') if ndjson else None
    try:
        with path.open('xb') as stream:
            stream.write(b'{"type":"FeatureCollection","features":[\n')
            for index, row in enumerate(features):
                raw = encoded(row)
                if index:
                    stream.write(b',\n')
                stream.write(raw.rstrip(b'\n'))
                if other:
                    other.write(raw)
            stream.write(b'\n]}\n')
    finally:
        if other:
            other.close()


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(columns)
        writer.writerows(rows)


def raster_payloads(name, bases=(0, 100, 200), x=-117.0):
    """Native GDAL VRT with explicit local little-endian UInt16 raw bands.

    This is an inspectable multiband raster, not a claim that the publication
    analyzer accepts VRT uploads. Every reference stays in this generated root.
    """
    payloads = {}
    vrt = ET.Element('VRTDataset', rasterXSize='4', rasterYSize='3')
    ET.SubElement(vrt, 'SRS').text = 'EPSG:4326'
    ET.SubElement(vrt, 'GeoTransform').text = f'{x},0.01,0,32.03,0,-0.01'
    for band, base in enumerate(bases, 1):
        filename = f'{name}-band-{band}.raw'
        values = [base + i for i in range(1, 12)] + [65535]
        payloads[filename] = struct.pack('<12H', *values)
        node = ET.SubElement(vrt, 'VRTRasterBand', dataType='UInt16',
                             band=str(band), subClass='VRTRawRasterBand')
        ET.SubElement(node, 'NoDataValue').text = '65535'
        ET.SubElement(node, 'SourceFilename', relativeToVRT='1').text = filename
        for key, value in (('ImageOffset', '0'), ('PixelOffset', '2'),
                           ('LineOffset', '8'), ('ByteOrder', 'LSB')):
            ET.SubElement(node, key).text = value
    ET.indent(vrt)
    payloads[f'{name}.vrt'] = ET.tostring(vrt, encoding='utf-8', xml_declaration=True)
    return payloads


def write_raster(root, name, bases=(0, 100, 200), x=-117.0):
    directory = root / 'raster'
    directory.mkdir(exist_ok=True)
    for filename, data in raster_payloads(name, bases, x).items():
        (directory / filename).write_bytes(data)


def checked_new_output(output):
    output = Path(output).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('output and ancestors must not be symlinks')
    if output.exists():
        raise ValueError('output must be a new directory; existing data is never overwritten')
    if not output.parent.is_dir():
        raise ValueError('output parent must already exist')
    return output


def generate(output, *, seed=DEFAULT_SEED, addresses=12):
    validate_parameters(seed, addresses)
    output = checked_new_output(output)
    # Validate checked-in inputs before allocating a job output.
    expectations = json.loads((FIXTURES / 'expected-small.json').read_text())
    project_template = (FIXTURES / 'templates' / 'rich-style.qgs').read_bytes()
    output.mkdir()
    write_features(output / 'addresses.geojson', iter_addresses(seed, addresses),
                   output / 'addresses.ndjson')
    roads = [feature('roads', i, {'type': 'LineString', 'coordinates': [
        [-117.001, 32.001 + i * .001], [-116.995, 32.001 + i * .001]]},
        {'name': f'Synthetic road {i + 1}', 'speed_limit': (25, 40, 60)[i]}, seed)
        for i in range(3)]
    write_features(output / 'roads.geojson', roads)
    outer = [[-117.002, 31.999], [-116.99, 31.999], [-116.99, 32.01],
             [-117.002, 32.01], [-117.002, 31.999]]
    hole = [[-116.999, 32.004], [-116.999, 32.006], [-116.997, 32.006],
            [-116.997, 32.004], [-116.999, 32.004]]
    # A hole plus an independently testable many-vertex polygon.
    ring = [[round(-116.98 + .002 * math.cos(i * math.pi / 16), 8),
             round(32.005 + .002 * math.sin(i * math.pi / 16), 8)] for i in range(32)]
    ring.append(ring[0])
    parcels = [feature('parcels', i, {'type': 'Polygon', 'coordinates': coords},
                       {'parcel_key': f'P-{i+1}', 'class': ('residential', 'park')[i]}, seed)
               for i, coords in enumerate(([outer, hole], [ring]))]
    write_features(output / 'parcels.geojson', parcels)
    write_csv(output / 'inspections.csv', ['fid', 'address_fid', 'inspection_date', 'score'],
              [[stable_id('inspections', i, seed), stable_id('addresses', i, seed),
                '2026-01-02', 0 if i == 0 else 100] for i in range(3)])
    (output / 'inspections.csvt').write_text('"String","String","Date","Integer"\n')
    attachments = output / 'attachments'
    attachments.mkdir()
    (attachments / 'inspection.txt').write_text('Synthetic inspection attachment. No real person or site.\n')
    write_json(output / 'attachment-references.json', [{
        'fid': stable_id('attachment', 0, seed), 'parent_fid': stable_id('addresses', 0, seed),
        'path': 'attachments/inspection.txt', 'media_type': 'text/plain',
        'sha256': digest(attachments / 'inspection.txt'), 'visibility': 'private',
        'note': 'Fixture expectation only; the catalog supplies actual policy.'}])
    native = output / 'native'
    native.mkdir()
    write_csv(native / 'typed-values.csv',
              ['fid', 'native_large_id', 'date_only', 'zoned_timestamp', 'decimal_value', 'empty_text'],
              [[stable_id('types', 0, seed), '9007199254740993', '2024-02-29',
                '2026-01-01T01:00:00+01:00', '1234567890.123456789', ''],
               [stable_id('types', 1, seed), '2147483648', '2026-01-01',
                '2025-12-31T16:00:00-08:00', '-0.000000001', 'Unicode Ω']])
    # WKT, not ambiguous four-coordinate RFC7946 GeoJSON, preserves M semantics.
    write_csv(native / 'dimensions.csv', ['case', 'WKT', 'srid', 'z', 'm'], [
        ['xyz', 'POINT Z (-117 32 12.5)', 4326, 12.5, ''],
        ['xym', 'POINT M (-117 32 7.25)', 4326, '', 7.25],
        ['xyzm', 'POINT ZM (-117 32 12.5 7.25)', 4326, 12.5, 7.25],
        ['empty', 'POINT EMPTY', 4326, '', '']])
    write_csv(native / 'epsg2230.csv', ['fid', 'WKT', 'srid'], [
        [stable_id('feet', 0, seed), 'POINT (6300000 1800000)', 2230]])
    write_json(native / 'null-empty-geometry.geojson', {'type': 'FeatureCollection', 'features': [
        feature('empty', 0, None, {'case': 'null'}, seed),
        feature('empty', 1, {'type': 'GeometryCollection', 'geometries': []}, {'case': 'empty'}, seed)]})
    write_raster(output, 'multiband')
    write_raster(output, 'time-20260101', (10,))
    write_raster(output, 'time-20260102', (20,), x=-116.96)
    write_csv(output / 'raster/time-mosaic.csv', ['path', 'time_start', 'time_end'], [
        ['time-20260101.vrt', '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z'],
        ['time-20260102.vrt', '2026-01-02T00:00:00Z', '2026-01-03T00:00:00Z']])
    invalid = output / 'invalid'
    invalid.mkdir()
    duplicate = list(iter_addresses(seed, 12))[:2]
    duplicate[1]['properties']['object_id'] = duplicate[0]['properties']['object_id']
    write_features(invalid / 'duplicate-object-id.geojson', duplicate)
    duplicate_uuid = list(iter_addresses(seed, 12))[:2]
    duplicate_uuid[1]['id'] = duplicate_uuid[0]['id']
    duplicate_uuid[1]['properties']['fid'] = duplicate_uuid[0]['properties']['fid']
    write_features(invalid / 'duplicate-uuid.geojson', duplicate_uuid)
    write_features(invalid / 'self-intersection.geojson', [feature('bad-polygon', 0,
        {'type': 'Polygon', 'coordinates': [[[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]]},
        {'expected_error': 'SELF_INTERSECTION'}, seed)])
    write_csv(invalid / 'orphan-inspection.csv', ['fid', 'address_fid'], [
        [stable_id('orphan', 0, seed), stable_id('addresses', addresses + 10, seed)]])
    write_json(invalid / 'typed-errors.json', [
        {'field': 'population', 'value': -1, 'expected': 'DOMAIN_VIOLATION'},
        {'field': 'population', 'value': 'ten', 'expected': 'TYPE_MISMATCH'},
        {'field': 'observed_at', 'value': '2026-02-30T00:00:00Z', 'expected': 'INVALID_TIMESTAMP'},
        {'field': 'district', 'value': 'unknown', 'expected': 'DOMAIN_VIOLATION'},
        {'field': 'object_id', 'value': 2147483648, 'expected': 'C1_ID_OUT_OF_RANGE'}])
    # These are data, never an instruction to execute SQL or access a URL.
    write_json(invalid / 'abuse-inputs.json', {
        'where': ["name = 'x' OR 1=1; DROP TABLE addresses;--", 'unknown(name) = 1'],
        'sort_fields': ['name;SELECT 1', '__not_a_field__'],
        'package_paths': ['../outside.txt', '/absolute.txt', 'a/../../outside.txt'],
        'remote_sources': ['http://127.0.0.1/', 'http://169.254.169.254/'],
        'note': 'Inert negative test strings only; do not dereference or execute.'})
    write_json(output / 'schema.json', {
        'fixture_schema_version': 1, 'crs': 'EPSG:4326',
        'addresses': {'geometry': 'Point XY', 'identity': 'fid UUID',
            'object_id': 'unique integer 1..2147483647', 'name': 'nullable text, empty distinct',
            'district': list(DISTRICTS), 'population': 'integer >=0',
            'elevation': 'decimal with 3 fractional digits', 'observed_at': 'timestamp with explicit timezone'},
        'relations': [{'child': 'inspections.address_fid', 'parent': 'addresses.fid',
                       'delete_policy_fixture': 'restrict'}],
        'authority': 'Fixture descriptors only, not a second product schema or policy authority.'})
    write_json(output / 'policy-scenarios.json', {
        'authority': 'Test setup instructions; persist grants only through the real catalog fixture API.',
        'principals': ['alice', 'bob', 'anonymous'], 'group': 'surveyors',
        'cases': [
            {'case': 'private', 'owner': 'alice', 'allowed': ['alice'], 'denied': ['bob', 'anonymous']},
            {'case': 'public', 'allowed': ['alice', 'bob', 'anonymous'], 'write_is_not_implied': True},
            {'case': 'group', 'member': 'bob', 'grant_then_revoke': True},
            {'case': 'row_filtered', 'required_filter': {'district': 'north'},
             'unsupported_secure_rendering': 'deny; no fallback to whole-layer rendering'},
            {'case': 'field_restricted', 'hidden_fields': ['population'],
             'surfaces': ['features', 'count', 'statistics', 'export', 'notebook', 'app']},
            {'case': 'revoke_during_operation', 'new_requests': 'deny', 'historical_downloads': 'not retractable'}],
        'surfaces': ['query', 'count', 'extent', 'statistics', 'map', 'legend', 'identify',
                     'raster', 'tile', 'search_facet', 'attachment', 'job_log', 'app', 'notebook_output'],
        'status': 'Scenario expectations; no runtime acceptance implied.'})
    write_json(output / 'expected-small.json', expectations)
    (output / 'rich-style.qgs').write_bytes(project_template)
    (output / 'README.txt').write_text(
        'SPDX-License-Identifier: GPL-3.0-or-later\n'
        'Wholly synthetic first-party fixture content under the existing project license policy.\n'
        'No real people, private source schemas, external data or embedded credentials.\n'
        'invalid/ contains deliberate failures. native/ preserves types beyond bounded C1.\n'
        'QGIS project needs the retained QGIS Vera Sans font; font bytes are not included.\n'
        'VRT is native inspectable raster data, not an approved publication upload format.\n'
        'Policy files describe test setup, not an alternate authorization authority.\n')
    files = {str(p.relative_to(output)): {'bytes': p.stat().st_size, 'sha256': digest(p)}
             for p in sorted(output.rglob('*')) if p.is_file()}
    manifest = {'generator_version': VERSION, 'seed': seed, 'addresses': addresses,
        'files': files, 'license': 'GPL-3.0-or-later', 'synthetic': True,
        'generator_sha256': digest(Path(__file__)),
        'rules': {'identity': 'UUIDv5 URL namespace; version/seed/dataset/index',
                  'addresses': '12-row scalar cycle; 1000-column geographic grid with seed offset',
                  'object_id': 'index+1, never derived from result ordering',
                  'raster': '4x3 UInt16 little-endian, bands 1..11+base, last cell nodata65535',
                  'expectations': 'Hand-authored first12-row oracle, not generated by a query implementation'},
        'runtime_support': 'Fixtures are test inputs, not advertised product capabilities.'}
    write_json(output / 'manifest.json', manifest)
    return manifest


def validate_manifest(root):
    """No symlinks, unsafe member paths, extra files or changed fixture bytes."""
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('symlink corpus root')
    manifest = json.loads((root / 'manifest.json').read_text())
    expected = set(manifest['files']) | {'manifest.json'}
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('symlink corpus member')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise ValueError('corpus membership differs')
    for relative, record in manifest['files'].items():
        if not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('unsafe manifest path')
        path = root / relative
        if path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise ValueError('corpus content differs: ' + relative)
    return manifest


def validate_native_profile(root):
    """Accept only this generator's trusted fixture profile before GIS parsing.

    A user-edited manifest alone cannot authorize new QGS/VRT references. This
    helper is not a general untrusted-upload validator or parser sandbox.
    """
    root = Path(root).absolute()
    manifest = validate_manifest(root)
    validate_parameters(manifest['seed'], manifest['addresses'])
    known = {'README.txt', 'addresses.geojson', 'addresses.ndjson',
        'attachment-references.json', 'attachments/inspection.txt', 'expected-small.json',
        'inspections.csv', 'inspections.csvt', 'invalid/abuse-inputs.json',
        'invalid/duplicate-object-id.geojson', 'invalid/duplicate-uuid.geojson',
        'invalid/orphan-inspection.csv', 'invalid/self-intersection.geojson',
        'invalid/typed-errors.json', 'native/dimensions.csv', 'native/epsg2230.csv',
        'native/null-empty-geometry.geojson', 'native/typed-values.csv', 'parcels.geojson',
        'policy-scenarios.json', 'raster/time-mosaic.csv', 'rich-style.qgs',
        'roads.geojson', 'schema.json'}
    for name, bases, x in [('multiband', (0, 100, 200), -117.0),
                            ('time-20260101', (10,), -117.0),
                            ('time-20260102', (20,), -116.96)]:
        for filename, data in raster_payloads(name, bases, x).items():
            relative = 'raster/' + filename
            known.add(relative)
            if (root / relative).read_bytes() != data:
                raise ValueError('unapproved native raster profile: ' + relative)
    if set(manifest['files']) != known:
        raise ValueError('unapproved native corpus membership')
    if (root / 'rich-style.qgs').read_bytes() != (FIXTURES / 'templates/rich-style.qgs').read_bytes():
        raise ValueError('unapproved native QGIS template')
    return manifest


def _inspect_native(root):
    """Release all provider/renderer objects before application shutdown."""
    from osgeo import gdal, ogr, osr
    from qgis.core import (Qgis, QgsApplication, QgsProject, QgsVectorLayer,
                           QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                           QgsPointXY, QgsMapSettings, QgsMapRendererSequentialJob,
                           QgsRectangle)
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor, QFont, QFontInfo
    gdal.UseExceptions(); ogr.UseExceptions()
    assert Qgis.QGIS_DEV_VERSION == OWNED_QGIS_COMMIT
    assert os.environ.get('PROJ_NETWORK') == 'OFF', 'PROJ_NETWORK=OFF required'
    root = Path(root).absolute()
    manifest = validate_native_profile(root)
    checks = {}
    for name, expected in [('addresses', manifest['addresses']), ('roads', 3), ('parcels', 2)]:
        source = gdal.OpenEx(str(root / f'{name}.geojson'), gdal.OF_VECTOR, allowed_drivers=['GeoJSON'])
        assert source and source.GetLayer(0).GetFeatureCount() == expected
        checks[name] = {'features': expected, 'driver': source.GetDriver().ShortName}
        if name == 'addresses':
            compared = 0
            with (root / 'addresses.ndjson').open() as stream:
                for native_row, line in zip(source.GetLayer(0), stream):
                    row = json.loads(line)
                    compared += 1
                    assert row['properties']['object_id'] == compared
                    for field in ('fid', 'object_id', 'name', 'district', 'population', 'elevation'):
                        assert native_row.GetField(field) == row['properties'][field]
                    assert json.loads(native_row.GetGeometryRef().ExportToJson()) == row['geometry']
                    if compared == 12:
                        break
            assert compared == 12, 'all first twelve address rows must be compared'
            checks[name]['first12_identity_attributes_geometry_roundtrip'] = True
    ds = gdal.Open(str(root / 'raster/multiband.vrt'))
    assert ds and (ds.RasterXSize, ds.RasterYSize, ds.RasterCount) == (4, 3, 3)
    for band, expected in [(1, 1), (2, 101), (3, 201)]:
        raw = ds.GetRasterBand(band).ReadRaster(0, 0, 4, 3, buf_type=gdal.GDT_UInt16)
        values = struct.unpack('<12H', raw)
        assert values[0] == expected and values[-1] == 65535
        assert ds.GetRasterBand(band).GetNoDataValue() == 65535
    assert ds.GetSpatialRef().GetAuthorityCode(None) == '4326'
    checks['raster'] = {'bands': 3, 'known_samples_and_nodata': True, 'geotransform': ds.GetGeoTransform()}
    for name, first in [('time-20260101', 11), ('time-20260102', 21)]:
        tile = gdal.Open(str(root / f'raster/{name}.vrt'))
        assert tile and struct.unpack('<H', tile.GetRasterBand(1).ReadRaster(0, 0, 1, 1))[0] == first
    checks['time_mosaic'] = {'tiles': 2, 'known_samples': [11, 21],
                             'scope': 'Native raster fixtures; no service time/mosaic capability implied.'}
    with (root / 'native/dimensions.csv').open() as stream:
        for row in csv.DictReader(stream):
            geom = ogr.CreateGeometryFromWkt(row['WKT'])
            assert geom is not None
            if row['case'] == 'empty':
                assert geom.IsEmpty()
            else:
                assert bool(geom.Is3D()) == bool(row['z'])
                assert bool(geom.IsMeasured()) == bool(row['m'])
                if row['z']: assert geom.GetZ() == float(row['z'])
                if row['m']: assert geom.GetM() == float(row['m'])
    checks['dimensions'] = ['XYZ', 'XYM', 'XYZM', 'EMPTY']
    empty_source = ogr.Open(str(root / 'native/null-empty-geometry.geojson'))
    empty_rows = list(empty_source.GetLayer(0))
    assert empty_rows[0].GetGeometryRef() is None
    assert empty_rows[1].GetGeometryRef() is not None and empty_rows[1].GetGeometryRef().IsEmpty()
    checks['null_and_empty_geometry'] = 'distinct after native GeoJSON read'
    feet_path = root / 'native/epsg2230.csv'
    with feet_path.open() as stream:
        feet_rows = list(csv.DictReader(stream))
    assert len(feet_rows) == 1
    feet_row = feet_rows[0]
    assert feet_row['srid'] == '2230'
    assert feet_row['fid'] == stable_id('feet', 0, manifest['seed'])
    feet_geometry = ogr.CreateGeometryFromWkt(feet_row['WKT'])
    assert feet_geometry and feet_geometry.GetGeometryType() == ogr.wkbPoint
    original = QgsPointXY(feet_geometry.GetX(), feet_geometry.GetY())
    assert (original.x(), original.y()) == (6300000, 1800000)
    crs = QgsCoordinateReferenceSystem('EPSG:' + feet_row['srid'])
    reference = osr.SpatialReference(); reference.ImportFromEPSG(int(feet_row['srid']))
    assert abs(reference.GetLinearUnits() - 1200 / 3937) < 1e-12
    transform = QgsCoordinateTransform(crs, QgsCoordinateReferenceSystem('EPSG:4326'), QgsProject.instance())
    transform.setAllowFallbackTransforms(False)
    transform.setBallparkTransformsAreAppropriate(False)
    geographic = transform.transform(original)
    operation = transform.instantiatedCoordinateOperationDetails()
    assert operation.isAvailable and operation.proj and 'ballpark' not in operation.name.lower()
    assert not transform.fallbackOperationOccurred()
    inverse = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
    inverse.setAllowFallbackTransforms(False); inverse.setBallparkTransformsAreAppropriate(False)
    returned = inverse.transform(geographic)
    assert not inverse.fallbackOperationOccurred()
    assert abs(returned.x() - original.x()) < .01 and abs(returned.y() - original.y()) < .01
    assert -118 < geographic.x() < -116 and 32 < geographic.y() < 34
    checks['epsg2230'] = {'roundtrip_tolerance_feet': .01,
                         'fixture': {'path': 'native/epsg2230.csv',
                                     'sha256': digest(feet_path), 'fid': feet_row['fid'],
                                     'srid': int(feet_row['srid']),
                                     'input_xy': [original.x(), original.y()]},
                         'linear_unit': reference.GetLinearUnitsName(),
                         'proj_network': os.environ['PROJ_NETWORK'],
                         'ballpark_allowed': False, 'fallback_allowed': False,
                         'operation': {'name': operation.name, 'pipeline': operation.proj,
                            'available': operation.isAvailable, 'accuracy_metres': operation.accuracy,
                            'grids': [{'name': grid.shortName, 'available': grid.isAvailable}
                                      for grid in operation.grids]},
                         'geographic_observed': [geographic.x(), geographic.y()],
                         'scope': 'Horizontal fixture transformation only; no universal grid/accuracy claim.'}
    bad = QgsVectorLayer(str(root / 'invalid/self-intersection.geojson'), 'invalid', 'ogr')
    assert bad.isValid() and not next(bad.getFeatures()).geometry().isGeosValid()
    checks['deliberate_invalid_geometry'] = 'native provider reads it; GEOS validity rejects it'
    project = QgsProject()
    assert project.read(str(root / 'rich-style.qgs'))
    assert len(project.mapLayers()) == 4 and all(layer.isValid() for layer in project.mapLayers().values())
    assert project.mapLayersByName('addresses')[0].labelsEnabled()
    assert len(project.mapLayersByName('addresses')[0].renderer().categories()) == 4
    actual_font = QFontInfo(QFont('QGIS Vera Sans')).family()
    assert actual_font == 'QGIS Vera Sans', actual_font
    checks['qgis_project'] = {'layers': 4, 'all_valid': True,
        'resolved_font_family': actual_font,
        'renderers': sorted(layer.renderer().type() for layer in project.mapLayers().values())}
    settings = QgsMapSettings()
    settings.setLayers([project.mapLayersByName(name)[0]
                        for name in ('addresses', 'roads', 'parcels', 'multiband')])
    settings.setDestinationCrs(project.crs())
    settings.setExtent(QgsRectangle(-117.003, 31.998, -116.975, 32.012))
    settings.setOutputSize(QSize(512, 384)); settings.setBackgroundColor(QColor('white'))
    job = QgsMapRendererSequentialJob(settings); job.start(); job.waitForFinished()
    assert not job.errors(), [error.message for error in job.errors()]
    image = job.renderedImage(); assert not image.isNull()
    colors = {image.pixelColor(x, y).rgba() for x in range(0, 512, 4) for y in range(0, 384, 4)}
    assert len(colors) > 4
    checks['qgis_project']['actual_render'] = {'width': 512, 'height': 384,
        'sampled_distinct_colors': len(colors), 'render_errors': 0,
        'scope': 'Nonempty real native rendering; no cross-engine pixel-fidelity claim.'}
    del job, settings, bad
    project.clear()
    del project
    # Native reads must not silently rewrite selected inputs or add sidecars.
    validate_manifest(root)
    result = {'status': 'passed', 'corpus_manifest_sha256': digest(root / 'manifest.json'),
              'qgis_source_commit': Qgis.QGIS_DEV_VERSION, 'qgis_version': Qgis.QGIS_VERSION,
              'gdal_version': gdal.VersionInfo(), 'checks': checks,
              'scope': 'Actual fixture parsing/geometry/raster/project checks, not GIS product acceptance.'}
    return result


def verify_native(root, report, runtime_config):
    """Inspect actual generated artifacts in an explicitly prepared GIS runtime."""
    from qgis.core import QgsApplication, QgsProject
    import qgis._core
    report = checked_new_output(report)
    validate_native_profile(root)
    config = json.loads(Path(runtime_config).read_text())
    if config['successor']['commit'] != OWNED_QGIS_COMMIT:
        raise ValueError('wrong selected owned QGIS source')
    if not Path(qgis._core.__file__).resolve().is_relative_to(Path(config['qgis_prefix']).resolve()):
        raise ValueError('QGIS bindings outside selected owned stage')
    if digest(config['resource_manifest']) != config['resource_manifest_sha256']:
        raise ValueError('selected stage manifest differs')
    if digest(config['font_file']) != FONT_SHA256:
        raise ValueError('selected source font differs')
    app = QgsApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QgsApplication([], False)
        app.initQgis()
    failure = None
    try:
        result = _inspect_native(root)
    except Exception as error:
        # Exception tracebacks retain the inspected frame's provider objects.
        # Release them while QGIS is alive, then report after clean shutdown.
        failure = f'{type(error).__name__}: {error}'
        traceback.clear_frames(error.__traceback__)
    finally:
        if owns_app:
            QgsProject.instance().clear()
            app.exitQgis()
    if failure is not None:
        raise ValueError(failure)
    # Save a passing receipt only after owned runtime shutdown succeeds.
    result['selected_runtime'] = {
        'configuration_sha256': digest(runtime_config),
        'source': config['successor'], 'qgis_prefix': config['qgis_prefix'],
        'stage_manifest_sha256': config['resource_manifest_sha256'],
        'bindings_sha256': digest(qgis._core.__file__),
        'font_file_sha256': FONT_SHA256}
    with report.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    generate_parser = sub.add_parser('generate')
    generate_parser.add_argument('--output', type=Path, required=True)
    generate_parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    generate_parser.add_argument('--addresses', type=int, default=12)
    inspect_parser = sub.add_parser('verify-native')
    inspect_parser.add_argument('corpus', type=Path)
    inspect_parser.add_argument('--report', type=Path, required=True)
    inspect_parser.add_argument('--runtime-config', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'generate':
            result = generate(args.output, seed=args.seed, addresses=args.addresses)
            print(json.dumps({'status': 'generated', 'addresses': result['addresses'],
                              'files': len(result['files']), 'manifest_sha256': digest(args.output / 'manifest.json')}))
        else:
            print(json.dumps(verify_native(args.corpus, args.report, args.runtime_config)))
    except (ValueError, OSError) as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
