"""Bounded real ImageMosaic/PostGIS index witness in the existing exact-WAR backend.

The caller owns services, containment, disposable database and token invalidation.
Call cleanup after both server phases stop, including when exercise/probe fails.
"""
import hashlib
import io
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

SCHEMA = 'remediation_mosaic'
LAYER = 'remediation_mosaic'
COLORS = {'west.tif': (40, 80, 160), 'east.tif': (180, 60, 20)}


def require(value, message):
    if not value: raise ValueError(message)


def sha(value): return hashlib.sha256(value).hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')


def secrets(config, token=''):
    return [token, config['database']['password'], config['runtime_database']['password'],
            config.get('client_secret', ''), *config.get('passwords', {}).values()]


def guarded_paths(config, output):
    output = Path(output).resolve()
    require(output == Path(config['output']).resolve(), 'mosaic output must be the active task output')
    db = config['database']
    require(db['host'] == '127.0.0.1' and db['name'] == 'fixture_geonode' and db['user'] == 'fixture_gn_owner'
            and type(db['port']) is int and 0 < db['port'] < 65536, 'mosaic requires the disposable owned fixture database')
    base = urlsplit(config['geoserver_url'])
    require(base.scheme == 'http' and base.hostname == '127.0.0.1' and base.port and not base.username
            and not base.query and not base.fragment, 'mosaic HTTP origin must be explicit loopback')
    data = output / 'geoserver-data'
    require(data.is_dir() and not data.is_symlink(), 'existing exact-WAR data directory required')
    return output / 'remediation-mosaic', data / 'data/fixture' / LAYER


def connect(config):
    import psycopg2
    db = config['database']
    return psycopg2.connect(host=db['host'], port=db['port'], dbname=db['name'],
                           user=db['user'], password=db['password'], connect_timeout=10,
                           application_name='ambisgis_remediation_mosaic')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ValueError('unexpected mosaic HTTP redirect')


def request(config, token, output, label, route, *, method='GET', body=None,
            content_type='application/xml', statuses=(200,)):
    url = config['geoserver_url'] + route
    headers = {'Authorization': 'Bearer ' + token, 'Accept': '*/*',
               'Cache-Control': 'no-cache', 'X-AmbisGIS-Fixture-Case': 'mosaic-' + label}
    if body is not None: headers['Content-Type'] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try: response = opener.open(req, timeout=60)
    except urllib.error.HTTPError as error: response = error
    with response:
        data = response.read(4 * 1024 * 1024 + 1)
        require(len(data) <= 4 * 1024 * 1024, 'oversized mosaic response')
        require('Set-Cookie' not in response.headers, 'mosaic request unexpectedly created a session')
        record = {'method': method, 'url': url, 'status': response.status, 'bytes': len(data),
                  'body_sha256': sha(data), 'content_type': response.headers.get('Content-Type', ''),
                  'request_body_sha256': sha(body) if body is not None else None,
                  'resolved_url': response.geturl(), 'client_cache': False}
    require(not any(v and v.encode() in data for v in secrets(config, token)), 'mosaic response contains fixture credential')
    save(output / (label + '-http.json'), record)
    (output / (label + '.body')).write_bytes(data)
    require(record['status'] in statuses, 'mosaic HTTP request failed: ' + label + ' status=' + str(record['status']))
    return data


def create_tiles(directory):
    """Two independent known-color GeoTIFF inputs, covering [0,4] x [0,4]."""
    from PIL import Image, TiffImagePlugin
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    rows = []
    for name, xmin in [('west.tif', 0), ('east.tif', 2)]:
        tags = TiffImagePlugin.ImageFileDirectory_v2()
        tags[33550] = (0.125, 0.125, 0.0)
        tags[33922] = (0.0, 0.0, 0.0, float(xmin), 4.0, 0.0)
        tags[34735] = (1, 1, 0, 4, 1024, 0, 1, 2, 1025, 0, 1, 1,
                       2048, 0, 1, 4326, 2054, 0, 1, 9102)
        tags.tagtype[33550] = 12; tags.tagtype[33922] = 12; tags.tagtype[34735] = 3
        path = directory / name
        Image.new('RGB', (16, 32), COLORS[name]).save(path, format='TIFF', compression='raw', tiffinfo=tags)
        with Image.open(path) as image:
            require(image.size == (16, 32) and image.getpixel((8, 16)) == COLORS[name]
                    and tuple(image.tag_v2[34735]) == tags[34735], 'generated GeoTIFF does not match fixture')
        rows.append({'name': name, 'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size,
                     'extent': [xmin, 0, xmin + 2, 4], 'rgb': list(COLORS[name]), 'crs': 'EPSG:4326'})
    return rows


def index_evidence(config, tiles):
    from psycopg2 import sql
    with connect(config) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_user,current_database(),postgis_lib_version()')
            user, database, version = cursor.fetchone()
            require((user, database, version) == ('fixture_gn_owner', 'fixture_geonode', '3.5.7'),
                    'unexpected owned database/profile identity')
            cursor.execute('SELECT f_table_name,f_geometry_column,srid,type FROM geometry_columns WHERE f_table_schema=%s AND f_table_name<>%s', (SCHEMA,'vector_points'))
            tables = cursor.fetchall()
            # The native upload validator opens the ZIP in a uniquely named
            # temporary directory and creates its own PostGIS index there. It
            # removes that directory, but leaves its database table. Account for
            # that source-defined side effect explicitly; never select an
            # arbitrary table as the actual published mosaic index.
            target = [row for row in tables if row[0] == LAYER]
            scratch = [row for row in tables if re.fullmatch(r'CoverageStoreFileValidator[0-9]+', row[0])]
            require(len(target) == 1 and len(scratch) == 1 and len(tables) == 2
                    and all(row[1:] == ('the_geom', 4326, 'POLYGON') for row in tables),
                    'native published/validator PostGIS index identities differ: '+repr(tables))
            evidence = []
            for table, geometry, _, _ in target + scratch:
                cursor.execute(sql.SQL('SELECT location,ST_SRID({g}),ST_XMin({g}),ST_YMin({g}),ST_XMax({g}),ST_YMax({g}),ST_Area({g}) FROM {s}.{t} ORDER BY location').format(
                    g=sql.Identifier(geometry), s=sql.Identifier(SCHEMA), t=sql.Identifier(table)))
                rows = cursor.fetchall()
                require(len(rows) == 2, 'native mosaic index must contain exactly two input granules')
                observed = {}
                for location, srid, xmin, ymin, xmax, ymax, area in rows:
                    relative = Path(location)
                    require(not relative.is_absolute() and len(relative.parts) == 1 and relative.name in COLORS,
                            'native mosaic index must use exact relative input granule names')
                    path = tiles / relative
                    require(path.resolve().parent == tiles.resolve() and path.is_file(),
                            'mosaic index points outside known input granules')
                    extent = [float(xmin), float(ymin), float(xmax), float(ymax)]
                    expected = [0, 0, 2, 4] if path.name == 'west.tif' else [2, 0, 4, 4]
                    require(srid == 4326 and abs(area - 8) < 1e-9 and all(abs(a-b) < 1e-9 for a,b in zip(extent, expected)),
                            'native PostGIS granule geometry differs from independent input extent')
                    observed[path.name] = {'extent': extent, 'srid': srid, 'area': float(area), 'sha256': sha(path.read_bytes())}
                require(set(observed) == set(COLORS), 'duplicate or missing native index granule')
                cursor.execute('SELECT indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=%s', (SCHEMA, table))
                indexes = [row[0] for row in cursor.fetchall()]
                require(any('USING gist' in value for value in indexes), 'native PostGIS spatial index missing')
                evidence.append({'table':table, 'geometry_column':geometry, 'granules':observed, 'spatial_index':True})
    require(not list(tiles.glob('*.shp')), 'ImageMosaic silently selected a shapefile index')
    return {'database': database, 'user': user, 'postgis_version': version, 'schema': SCHEMA,
            'published_index': evidence[0], 'native_upload_validator_index': evidence[1],
            'validator_index_disposition': 'temporary files removed by native validator; owned schema dropped at final cleanup',
            'index_writer': 'actual selected GeoTools ImageMosaic/PostGIS provider; helper creates schema only'}


def probe(config, bearer_admin_token, output, phase='restart'):
    from PIL import Image
    record_dir, tiles = guarded_paths(config, output)
    require(phase in ('initial', 'restart'), 'unsupported mosaic phase')
    report = {'result_exit_code': 1, 'phase': phase}
    try:
        report['postgis_index'] = index_evidence(config, tiles)
        vector_params = {'SERVICE':'WFS','VERSION':'1.0.0','REQUEST':'GetFeature',
                         'typeName':'fixture:remediation_vector','OUTPUTFORMAT':'application/json'}
        vector_data = request(config,bearer_admin_token,record_dir,phase+'-vector-wfs','wfs?'+urlencode(vector_params))
        collection = json.loads(vector_data)
        require(collection.get('type') == 'FeatureCollection' and len(collection.get('features',[])) == 2,
                'PostGIS WFS did not return two features')
        observed = []
        for feature in collection['features']:
            require(feature.get('geometry',{}).get('type') == 'Point', 'PostGIS WFS geometry type mismatch')
            observed.append((feature.get('properties',{}).get('label'), tuple(feature['geometry']['coordinates'])))
        require(sorted(observed) == [('east',(3,2)),('west',(1,2))], 'PostGIS WFS known values or geometry changed')
        report['postgis_vector'] = {'feature_count':2,'features':[{'label':label,'coordinates':list(xy)} for label,xy in sorted(observed)],
                                    'response_sha256':sha(vector_data),'store':'remediation_vector','native_table':SCHEMA+'.vector_points'}
        params = {'SERVICE': 'WMS', 'VERSION': '1.1.1', 'REQUEST': 'GetMap',
                  'LAYERS': 'fixture:' + LAYER, 'STYLES': 'remediation_mosaic_style',
                  'SRS': 'EPSG:4326', 'BBOX': '-1,-1,5,5', 'WIDTH': 384, 'HEIGHT': 384,
                  'FORMAT': 'image/png', 'TRANSPARENT': 'true', 'TILED': 'false'}
        data = request(config, bearer_admin_token, record_dir, phase+'-wms', 'wms?'+urlencode(params))
        require(data.startswith(b'\x89PNG\r\n\x1a\n'), 'mosaic WMS did not return PNG')
        with Image.open(io.BytesIO(data)) as source:
            require(source.size == (384,384), 'mosaic WMS dimensions changed')
            image = source.convert('RGBA'); samples = []
            for name, xy in [('west.tif',(128,192)), ('east.tif',(256,192))]:
                color = image.getpixel(xy)
                # Interior pixels avoid resampling boundaries. Tolerance two only
                # accommodates codec/renderer rounding; no golden image replacement.
                require(color[3] == 255 and max(abs(a-b) for a,b in zip(color[:3],COLORS[name])) <= 2,
                        'mosaic WMS known raster color absent/misplaced: ' + name)
                samples.append({'granule': name, 'pixel': list(xy), 'rgba': list(color), 'rgb_tolerance': 2})
            for xy in [(32,192),(352,192),(192,32),(192,352)]:
                require(image.getpixel(xy)[3] == 0, 'mosaic WMS outside coverage must be transparent')
        (record_dir/(phase+'-wms.png')).write_bytes(data)
        report.update(result_exit_code=0, png_sha256=sha(data), samples=samples,
                      transparent_outside_extent=True, cache='direct WMS, no client/tile cache',
                      world_extent=[0,0,4,4], srs='EPSG:4326')
    except Exception as error:
        message = str(error)
        for value in secrets(config, bearer_admin_token):
            if value: message = message.replace(value, '[REDACTED_FIXTURE_VALUE]')
        report['error'] = {'type':type(error).__name__, 'message':message}
        raise
    finally: save(record_dir/(phase+'-result.json'),report)
    return report


def exercise(invocation, config, bearer_admin_token, output):
    record_dir, tiles = guarded_paths(config, output)
    require(not record_dir.exists() and not tiles.exists(), 'mosaic fixture must be exclusively fresh')
    record_dir.mkdir(mode=0o700)
    db = config['database']
    marker = {'database':db['name'], 'host':db['host'], 'port':db['port'], 'schema':SCHEMA,
              'schema_created':False, 'tiles':str(tiles)}
    save(record_dir/'owner.json',marker)
    report = {'result_exit_code':1, 'exact_war_sha256':invocation['runtime']['war_sha256'], 'scope':'non-Oracle native ImageMosaic/PostGIS index and direct WMS'}
    try:
        with connect(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT to_regnamespace(%s)',(SCHEMA,))
                require(cursor.fetchone()[0] is None, 'refuse to adopt existing mosaic schema')
                cursor.execute('CREATE SCHEMA remediation_mosaic AUTHORIZATION fixture_gn_owner')
                cursor.execute('CREATE TABLE remediation_mosaic.vector_points(id integer PRIMARY KEY,label text NOT NULL,geom geometry(Point,4326) NOT NULL)')
                cursor.execute("INSERT INTO remediation_mosaic.vector_points VALUES (1,'west',ST_SetSRID(ST_MakePoint(1,2),4326)),(2,'east',ST_SetSRID(ST_MakePoint(3,2),4326))")
        marker['schema_created'] = True
        (record_dir/'owner.json').write_text(json.dumps(marker,indent=2,sort_keys=True)+'\n')
        # PostGIS datastore registration goes through the actual server REST
        # path. Neither credential-bearing request XML nor connection GET is retained.
        store = ET.Element('dataStore')
        ET.SubElement(store,'name').text='remediation_vector'
        ET.SubElement(store,'enabled').text='true'
        params = ET.SubElement(store,'connectionParameters')
        vector_fields = {'dbtype':'postgis','host':db['host'],'port':str(db['port']),
                         'database':db['name'],'schema':SCHEMA,'user':db['user'],'passwd':db['password'],
                         'namespace':'urn:ambisgis:configured-auth-fixture','Expose primary keys':'true'}
        for key,value in vector_fields.items():ET.SubElement(params,'entry',key=key).text=value
        request(config,bearer_admin_token,record_dir,'create-vector-store','rest/workspaces/fixture/datastores',
                method='POST',body=ET.tostring(store),statuses=(200,201))
        feature = b'<featureType><name>remediation_vector</name><nativeName>vector_points</nativeName><srs>EPSG:4326</srs><projectionPolicy>FORCE_DECLARED</projectionPolicy><enabled>true</enabled></featureType>'
        request(config,bearer_admin_token,record_dir,'publish-vector','rest/workspaces/fixture/datastores/remediation_vector/featuretypes',
                method='POST',body=feature,statuses=(200,201))
        inputs = record_dir/'inputs'
        report['inputs'] = create_tiles(inputs)
        fields = {'SPI':'org.geotools.data.postgis.PostgisNGDataStoreFactory', 'host':db['host'],
                  'port':str(db['port']), 'user':db['user'], 'passwd':db['password'],
                  'database':db['name'], 'schema':SCHEMA}
        properties = ''.join(key+'='+value+'\n' for key,value in fields.items())
        (inputs/'indexer.properties').write_text('Schema=*the_geom:Polygon,location:String\nAbsolutePath=false\nCaching=false\n')
        report['selected_spi'] = fields['SPI']
        report['native_indexer_sha256'] = sha((inputs/'indexer.properties').read_bytes())
        sld = b'''<?xml version="1.0"?><StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld"><NamedLayer><Name>remediation_mosaic_style</Name><UserStyle><Title>Synthetic RGB raster</Title><FeatureTypeStyle><Rule><RasterSymbolizer><Opacity>1</Opacity><ChannelSelection><RedChannel><SourceChannelName>1</SourceChannelName></RedChannel><GreenChannel><SourceChannelName>2</SourceChannelName></GreenChannel><BlueChannel><SourceChannelName>3</SourceChannelName></BlueChannel></ChannelSelection></RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>'''
        request(config,bearer_admin_token,record_dir,'create-style','rest/styles?name=remediation_mosaic_style',method='POST',body=sld,content_type='application/vnd.ogc.sld+xml',statuses=(200,201))
        # Use the supported inline upload API. External file URLs are denied
        # by the existing server URL policy; no exception is added for this test.
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_STORED) as archive:
            for path in sorted(inputs.iterdir()):archive.writestr(path.name,path.read_bytes())
            archive.writestr('datastore.properties',properties)
        request(config,bearer_admin_token,record_dir,'publish','rest/workspaces/fixture/coveragestores/'+LAYER+'/file.imagemosaic?configure=all&coverageName='+LAYER,
                method='PUT',body=payload.getvalue(),content_type='application/zip',statuses=(201,))
        require((tiles/'datastore.properties').is_file(), 'native upload did not stage its own mosaic properties')
        (tiles/'datastore.properties').chmod(0o600)
        for row in report['inputs']:
            require(sha((tiles/row['name']).read_bytes()) == row['sha256'], 'native uploaded TIFF differs from known input')
        layer = b'<layer><enabled>true</enabled><defaultStyle><name>remediation_mosaic_style</name></defaultStyle></layer>'
        request(config,bearer_admin_token,record_dir,'set-style','rest/layers/fixture:'+LAYER,method='PUT',body=layer,statuses=(200,))
        report['initial'] = probe(config,bearer_admin_token,output,phase='initial')
        report['result_exit_code'] = 0
    except Exception as error:
        message=str(error)
        for value in secrets(config,bearer_admin_token):
            if value: message=message.replace(value,'[REDACTED_FIXTURE_VALUE]')
        report['error']={'type':type(error).__name__,'message':message}
        raise
    finally: save(record_dir/'exercise-result.json',report)
    return report


def cleanup(config, output):
    """After GeoServer stops: scrub local driver credentials, drop our own schema."""
    record_dir, tiles = guarded_paths(config, output)
    if not record_dir.exists(): return {'not_started':True}
    marker = json.loads((record_dir/'owner.json').read_text())
    db=config['database']
    require(all(marker[k] == db[k] for k in ('host','port')) and marker['database'] == db['name']
            and marker['schema'] == SCHEMA and marker['tiles'] == str(tiles), 'mosaic cleanup ownership mismatch')
    report={'result_exit_code':1,'files_scrubbed':[],'schema_dropped':False}
    try:
        if tiles.exists():
            for path in tiles.rglob('*'):
                require(not path.is_symlink(),'refuse symlink in mosaic credential cleanup')
                if path.is_file() and path.suffix in ('.zip','.imagemosaic'):
                    # Native successful unzip removes its temporary archive;
                    # preserve any unsuccessful archive only after credential scrubbing.
                    data=path.read_bytes()
                    if any(value and value.encode() in data for value in secrets(config)):
                        path.write_bytes(b'SCRUBBED DISPOSABLE FIXTURE CREDENTIAL ARCHIVE\n')
                        report['files_scrubbed'].append(str(path.relative_to(Path(output))))
                if path.is_file() and path.suffix in ('.properties','.xml'):
                    text=path.read_text();redacted=text
                    for value in secrets(config):
                        if value:redacted=redacted.replace(value,'REDACTED-DISPOSABLE-CREDENTIAL')
                    if redacted != text:
                        path.write_text(redacted);report['files_scrubbed'].append(str(path.relative_to(Path(output))))
        vector_directory = Path(output)/'geoserver-data/workspaces/fixture/remediation_vector'
        if vector_directory.exists():
            require(not vector_directory.is_symlink(), 'refuse symlink in vector credential cleanup')
            for path in vector_directory.rglob('*.xml'):
                require(not path.is_symlink(),'refuse symlink in vector credential cleanup')
                tree=ET.parse(path);changed=False
                for element in tree.getroot().iter():
                    if element.tag == 'entry' and element.get('key') in ('passwd','password'):
                        element.text='REDACTED-DISPOSABLE-CREDENTIAL';changed=True
                if changed:
                    tree.write(path,encoding='unicode');report['files_scrubbed'].append(str(path.relative_to(Path(output))))
        if marker['schema_created']:
            with connect(config) as connection:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=%s',(SCHEMA,))
                    require(cursor.fetchone() == ('fixture_gn_owner',),'mosaic schema owner changed before cleanup')
                    cursor.execute('DROP SCHEMA remediation_mosaic CASCADE')
            report['schema_dropped']=True
        report['result_exit_code']=0
    finally:save(record_dir/'cleanup-result.json',report)
    return report
