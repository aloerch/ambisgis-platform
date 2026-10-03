"""Controlled loader for exact generated synthetic bytes, separate from reader."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time

import psycopg2


def connect(database):
    return psycopg2.connect(**{('dbname' if k == 'name' else k): v for k, v in database.items()})


def load(config):
    output = Path(config['output'])
    manifest = json.loads((output / 'corpus-manifest.json').read_text())
    source = output / 'addresses.ndjson'
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['files']['addresses.ndjson']['sha256']:
        raise ValueError('generated corpus identity differs')
    revision = config['layer']['data_revision']
    start = time.monotonic_ns()
    count = 0
    def escaped(value):
        if value is None: return '\\N'
        return str(value).replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')
    with (output / 'load.tsv').open('x') as target, source.open() as stream:
        for line in stream:
            feature = json.loads(line, parse_float=Decimal)
            props, geom = feature['properties'], feature['geometry']
            if geom['type'] != 'Point' or len(geom['coordinates']) != 2 or feature['id'] != props['fid']:
                raise ValueError('unsupported generated geometry/identity')
            fields = [revision] + [props[x] for x in ('fid', 'object_id', 'name', 'district', 'population', 'elevation', 'observed_at')]
            fields.append('SRID=4326;POINT(' + ' '.join(map(str, geom['coordinates'])) + ')')
            target.write('\t'.join(map(escaped, fields)) + '\n')
            count += 1
    if count != manifest['addresses']: raise ValueError('generated corpus count differs')
    with connect(config['database']) as database, database.cursor() as cursor:
        cursor.execute('CREATE SCHEMA spike; REVOKE ALL ON SCHEMA spike FROM PUBLIC')
        cursor.execute('''CREATE TABLE spike.addresses (
            data_revision uuid NOT NULL, fid uuid NOT NULL, object_id integer NOT NULL CHECK(object_id > 0),
            name varchar(256), district varchar(32) NOT NULL, population integer NOT NULL,
            elevation numeric(12,3), observed_at timestamptz NOT NULL,
            geom geometry(Point,4326) NOT NULL CHECK(NOT ST_IsEmpty(geom)),
            PRIMARY KEY(data_revision,object_id), UNIQUE(data_revision,fid))''')
        with (output / 'load.tsv').open() as stream:
            cursor.copy_expert('COPY spike.addresses FROM STDIN', stream)
        cursor.execute('CREATE INDEX ON spike.addresses USING gist(geom)')
        cursor.execute('CREATE INDEX ON spike.addresses(data_revision,district COLLATE "C",object_id)')
        cursor.execute('CREATE INDEX ON spike.addresses(data_revision,name COLLATE "C",object_id)')
        cursor.execute('ANALYZE spike.addresses')
        cursor.execute('GRANT USAGE ON SCHEMA spike TO fixture_query; GRANT SELECT ON spike.addresses TO fixture_query')
        cursor.execute('SELECT count(*),min(object_id),max(object_id),count(DISTINCT fid) FROM spike.addresses')
        actual = cursor.fetchone()
        if actual != (count, 1, count, count): raise ValueError('loaded row identities differ')
    # Use actual native catalog resource UUIDs in the runtime mapping; no title collision adoption.
    import os
    os.environ.update(AMBISGIS_GEONODE_CONFIG=str(output / 'private.json'), AMBISGIS_GEONODE_RUNTIME='1', DJANGO_SETTINGS_MODULE='fixture_settings')
    import django
    django.setup()
    from geonode.base.models import ResourceBase
    resources = [{'resource': key, 'catalog_uuid': str(ResourceBase.objects.get(alternate=name).uuid),
                  'layer_id': config['layer']['layer_id'], 'data_revision': revision} for key, name in config['resources'].items()]
    report = {'addresses': count, 'distinct_uuid': actual[3], 'input_sha256': manifest['files']['addresses.ndjson']['sha256'],
              'load_elapsed_ms': (time.monotonic_ns() - start) / 1e6, 'resources': resources,
              'numeric_load': 'Decimal parsed from original JSON text, COPY into numeric(12,3)',
              'reader_denials': {}}
    # Read role must be unable to mutate snapshot or read catalog authority tables.
    for name, sql in [('insert', 'INSERT INTO spike.addresses SELECT * FROM spike.addresses LIMIT 1'),
                      ('update', 'UPDATE spike.addresses SET population=999 WHERE object_id=1'),
                      ('delete', 'DELETE FROM spike.addresses WHERE object_id=1'),
                      ('catalog', 'SELECT * FROM oauth2_provider_accesstoken LIMIT 1')]:
        connection = connect(config['query_database'])
        try:
            with connection.cursor() as cursor: cursor.execute(sql)
        except psycopg2.Error as error:
            report['reader_denials'][name] = error.pgcode
        else:
            raise RuntimeError('query reader exceeded read boundary')
        finally:
            connection.rollback(); connection.close()
    (output / 'fixture.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
