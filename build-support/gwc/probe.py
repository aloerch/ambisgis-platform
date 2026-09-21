"""Finite WMTS observations; cache headers alone and identical PNG bytes never suffice."""
import hashlib
import io
import json
import math
from pathlib import Path
import time
from urllib.parse import urlencode, urlsplit
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

NS = {'w':'http://www.opengis.net/wmts/1.0', 'o':'http://www.opengis.net/ows/1.1', 'x':'http://www.w3.org/1999/xlink'}


def require(value, message):
    if not value: raise ValueError(message)


def sha(data): return hashlib.sha256(data).hexdigest()


def save(path, value):
    with Path(path).open('x') as stream: json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')


def security_hashes(data):
    paths = list((data / 'security').rglob('*')) + list((data / 'geofence').rglob('*'))
    return {str(p.relative_to(data)): sha(p.read_bytes()) for p in sorted(paths) if p.is_file()}


def configure_cache(data, cache):
    require(not cache.exists() and not cache.is_symlink(), 'cache must be exclusively fresh')
    require(cache.parent.resolve() == data.parent.resolve(), 'cache must belong to this attempt')
    cache.mkdir(mode=0o700)
    # GeoFence's order-99 placeholder configurer sees this before the later GWC
    # configurer; mirror the owned GeoFence integration fixture's explicit prefix.
    properties=data/'geofence/geofence-server.properties'
    properties.write_text(properties.read_text()+'gwc.context.suffix=gwc\n')
    fields = dict(version='1.1.0', directWMSIntegrationEnabled='false', requireTiledParameter='true',
        WMSCEnabled='true', TMSEnabled='true', WMTSEnabled='true', securityEnabled='true',
        cacheLayersByDefault='true', cacheNonDefaultStyles='false', metaTilingX='1', metaTilingY='1',
        metaTilingThreads='0', gutter='0')
    root = ET.Element('GeoServerGWCConfig')
    for key,value in fields.items(): ET.SubElement(root,key).text=value
    for key, value in [('defaultCachingGridSetIds','EPSG:4326'),('defaultCoverageCacheFormats','image/png'),
                       ('defaultVectorCacheFormats','image/png'),('defaultOtherCacheFormats','image/png')]:
        ET.SubElement(ET.SubElement(root,key),'string').text=value
    ET.indent(root)
    (data / 'gwc-gs.xml').write_bytes(ET.tostring(root))
    # Same independent Point(1,2)/28px red-circle oracle for the protected fixture.
    path = data / 'workspaces/fixture/private_points/private_points/layer.xml'
    tree = ET.parse(path)
    ET.SubElement(ET.SubElement(tree.getroot(),'defaultStyle'),'id').text='fixture-witness-style'
    tree.write(path,encoding='unicode')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError('unexpected HTTP redirect')


def request(url, output, label, secrets, token=None, method='GET', body=None):
    parsed=urlsplit(url)
    require(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port and not parsed.username,
            'HTTP fixture origin must be explicit loopback')
    headers={'Accept':'application/xml' if '/gwc/rest/' in url else '*/*', 'X-AmbisGIS-Fixture-Case':label}
    if token: headers['Authorization']='Bearer '+token
    if body is not None: headers['Content-Type']='application/xml'
    req=urllib.request.Request(url,data=body,headers=headers,method=method)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    start=time.monotonic()
    try: response=opener.open(req,timeout=45)
    except urllib.error.HTTPError as error: response=error
    with response:
        data=response.read(8*1024*1024+1)
        require(len(data)<=8*1024*1024,'oversized fixture response')
        response_headers=dict((k.lower(),v) for k,v in response.headers.items())
        metadata={'url':url,'method':method,'identity':'bearer' if token else 'anonymous',
            'status':response.status,'headers':response_headers,'body_sha256':sha(data),'bytes':len(data),
            'request_body_sha256':sha(body) if body is not None else None,'elapsed_seconds':time.monotonic()-start,'observed_at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'client_cache':False,'resolved_url':response.geturl()}
    raw=json.dumps(metadata).encode()+data
    require(not any(value and value.encode() in raw for value in secrets),'response contains a fixture credential')
    require('set-cookie' not in response_headers,'unexpected session cookie on stateless tile path')
    save(output/(label+'.json'),metadata)
    (output/(label+'.body')).write_bytes(data)
    return metadata,data


def cache_manifest(root):
    root=Path(root)
    require(root.is_dir() and not root.is_symlink(),'cache is not a regular task directory')
    rows={}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'cache path escape')
        if p.is_file() and p.suffix=='.png':
            st=p.stat()
            rows[str(p.relative_to(root))]={'sha256':sha(p.read_bytes()),'bytes':st.st_size,
                'mtime_ns':st.st_mtime_ns,'inode':st.st_ino}
    require(len(rows)<=2 and sum(row['bytes'] for row in rows.values())<=2*1024*1024,'bounded tile cache exceeded')
    return rows


def select_tile(xml, base, layer):
    root=ET.fromstring(xml)
    require(root.tag=='{'+NS['w']+'}Capabilities','not WMTS capabilities')
    layers=root.findall('w:Contents/w:Layer',NS)
    selected=[v for v in layers if v.findtext('o:Identifier',namespaces=NS)==layer]
    require(len(selected)==1,'intended layer absent/duplicated in capabilities')
    selected=selected[0]
    require('image/png' in [v.text for v in selected.findall('w:Format',NS)],'PNG not advertised')
    grid='EPSG:4326'
    require(grid in [v.text for v in selected.findall('w:TileMatrixSetLink/w:TileMatrixSet',NS)],'selected grid not advertised')
    grids=[v for v in root.findall('w:Contents/w:TileMatrixSet',NS) if v.findtext('o:Identifier',namespaces=NS)==grid]
    require(len(grids)==1,'matrix set missing/duplicated')
    crs=grids[0].findtext('o:SupportedCRS',namespaces=NS)
    require(crs=='urn:ogc:def:crs:EPSG::4326','unsupported CRS axis convention')
    # EPSG:4326 is north/east in WMTS advertised CRS; convert to x/y explicitly.
    matrices=[v for v in grids[0].findall('w:TileMatrix',NS) if int(v.findtext('w:MatrixWidth',namespaces=NS))==64]
    require(len(matrices)==1,'no unique bounded matrix')
    matrix=matrices[0]
    get=lambda tag: matrix.findtext('w:'+tag,namespaces=NS)
    height,width=int(get('TileHeight')),int(get('TileWidth'))
    require((width,height)==(256,256),'unexpected advertised tile dimensions')
    top,left=map(float,get('TopLeftCorner').split())
    scale=float(get('ScaleDenominator'))
    resolution=scale*0.00028/(2*math.pi*6378137/360)
    sx,sy=width*resolution,height*resolution
    require(4<sx<8 and math.isclose(left,-180) and math.isclose(top,90),'unexpected matrix bounds')
    column,row=math.floor((1-left)/sx),math.floor((top-2)/sy)
    require(0<=column<int(get('MatrixWidth')) and 0<=row<int(get('MatrixHeight')),'point outside matrix')
    xmin,ymax=left+column*sx,top-row*sy
    styles=selected.findall('w:Style',NS)
    defaults=[v.findtext('o:Identifier',namespaces=NS) for v in styles if v.get('isDefault')=='true']
    require(len(defaults)==1,'default style not advertised')
    endpoints=root.findall("o:OperationsMetadata/o:Operation[@name='GetTile']/o:DCP/o:HTTP/o:Get",NS)
    endpoint=next((e.get('{'+NS['x']+'}href') for e in endpoints if e.get('{'+NS['x']+'}href','').startswith(base)),None)
    require(endpoint is not None,'no same-origin advertised GetTile endpoint')
    require(endpoint.rstrip('?')==base+'gwc/service/wmts','unexpected advertised WMTS endpoint')
    params={'SERVICE':'WMTS','VERSION':'1.0.0','REQUEST':'GetTile','LAYER':layer,'STYLE':defaults[0],
        'FORMAT':'image/png','TILEMATRIXSET':grid,'TILEMATRIX':get('Identifier') or matrix.findtext('o:Identifier',namespaces=NS),
        'TILEROW':row,'TILECOL':column}
    return {'endpoint':endpoint.rstrip('?'),'parameters':params,'crs':crs,'axis_order':'latitude longitude',
        'top_left_advertised':[top,left],'scale_denominator':scale,'resolution_degrees':resolution,
        'bounds_xy':[xmin,ymax-sy,xmin+sx,ymax],'expected_center_px':[(1-xmin)/resolution,(ymax-2)/resolution],
        'tile_size':[width,height],'matrix_index':grids[0].findall('w:TileMatrix',NS).index(matrix),'matrix_size':[int(get('MatrixWidth')),int(get('MatrixHeight'))]}


def image_witness(data, tile):
    from PIL import Image
    require(data.startswith(b'\x89PNG\r\n\x1a\n'),'not PNG')
    image=Image.open(io.BytesIO(data)); image.load()
    require(image.format=='PNG' and list(image.size)==tile['tile_size'],'wrong decoded image dimensions/type')
    image=image.convert('RGBA'); cx,cy=tile['expected_center_px']
    red=[]; opaque=[]
    for y in range(image.height):
        for x in range(image.width):
            r,g,b,a=image.getpixel((x,y))
            if a>200: opaque.append((x,y))
            if r>180 and g<50 and b<50 and a>200: red.append((x,y))
    require(450<=len(red)<=650,'expected independently specified 28px red circle missing')
    require(all(math.hypot(x+.5-cx,y+.5-cy)<=14.5 for x,y in red),'red feature misplaced or not circular')
    for y in range(image.height):
        for x in range(image.width):
            if math.hypot(x+.5-cx,y+.5-cy)<11:
                r,g,b,a=image.getpixel((x,y))
                require(r>180 and g<50 and b<50 and a>200,'circle interior missing')
    require(all(abs(x-cx)<=17 and abs(y-cy)<=17 for x,y in opaque),'unexpected opaque geometry/background')
    centroid=[sum(p[axis] for p in red)/len(red) for axis in (0,1)]
    require(abs(centroid[0]-cx)<2 and abs(centroid[1]-cy)<2,'red centroid differs from Point(1,2) projection')
    return {'size':list(image.size),'red_pixels':len(red),'opaque_pixels':len(opaque),
        'red_centroid':centroid,'expected_center':tile['expected_center_px'],'rgba_sha256':sha(image.tobytes())}


def tile_response(metadata,data,tile,expected):
    require(metadata['status']==200 and metadata['headers'].get('content-type','').split(';')[0]=='image/png','tile HTTP/type failure')
    require(metadata['headers'].get('geowebcache-cache-result')==expected,'unexpected native cache result')
    params=tile['parameters']
    require(metadata['headers'].get('geowebcache-gridset')==params['TILEMATRIXSET'] and metadata['headers'].get('geowebcache-crs')=='EPSG:4326','cache grid identity differs')
    index=json.loads(metadata['headers'].get('geowebcache-tile-index','null'))
    require(index==[params['TILECOL'],tile['matrix_size'][1]-params['TILEROW']-1,tile['matrix_index']],'native cache tile index differs')
    bounds=[float(v) for v in metadata['headers'].get('geowebcache-tile-bounds','').strip('[]').split(',')]
    require(len(bounds)==4 and all(math.isclose(a,b,abs_tol=1e-8) for a,b in zip(bounds,tile['bounds_xy'])),'native tile bounds differ')
    return image_witness(data,tile)


def protocol_error(metadata,data,authorization=False):
    require(metadata['status'] in ((400,401,403) if authorization else (400,)), 'unexpected protocol error status')
    require(not data.startswith(b'\x89PNG'),'error returned image')
    root=ET.fromstring(data)
    if authorization:
        # The selected GeoServer security exception passes through the native
        # GWC dispatcher -> ResponseUtils.writeErrorPage (HTTP400 HTML), not OWS.
        require(metadata['status']==400 and metadata['headers'].get('content-type','').split(';')[0]=='text/html','unexpected native authorization response')
        require(root.tag=='html' and root.findtext('head/title')=='GWC Error','not native GWC error page')
        messages=[v.text for v in root.findall('body/h4')]
        allowed={'400: Cannot access private_points as anonymous',
                 '400: Cannot access private_points with the current privileges'}
        require(len(messages)==1 and messages[0] in allowed,'not the exact protected-layer security denial')
        require(not root.findall('.//form'),'login form is not authorization evidence')
        return {'status':400,'exception':messages[0],'format':'native GWC HTML error'}
    require(root.tag=='{'+NS['o']+'}ExceptionReport','not genuine OWS 1.1 protocol exception')
    errors=root.findall('o:Exception',NS)
    require(len(errors)==1,'empty or ambiguous protocol exception')
    error=errors[0]
    text=error.findtext('o:ExceptionText',namespaces=NS)
    require(bool(text and text.strip()),'empty exception text')
    require(error.get('exceptionCode')=='InvalidParameterValue' and error.get('locator')=='LAYER'
        and text=='LAYER fixture:no_such_tile_layer is not known.','wrong invalid-layer exception')
    return {'status':metadata['status'],'exception':text,'code':error.get('exceptionCode'),'locator':error.get('locator')}


def expected_cache_path(tile):
    params=tile['parameters']; z=tile['matrix_index']
    x=params['TILECOL']; y=tile['matrix_size'][1]-params['TILEROW']-1
    half=2 << (z//2); digits=1 if half<=10 else len(str(half))
    layer=params['LAYER'].replace(':','_'); grid=params['TILEMATRIXSET'].replace(':','_')
    # Selected native DefaultFilePathGenerator, default style/no extra parameters.
    return f'{layer}/{grid}_{z:02d}/{x//half:0{digits}d}_{y//half:0{digits}d}/{x:0{2*digits}d}_{y:0{2*digits}d}.png'


def cache_transition(before,after,metadata,expected,tile):
    from urllib.parse import parse_qs
    params=parse_qs(urlsplit(metadata['url']).query,keep_blank_values=True)
    layer=params.get('LAYER',[])
    require(len(layer)==1 and layer[0] in ('fixture:public_points','fixture:private_points'),'cache request identity missing')
    require(layer[0]==tile['parameters']['LAYER'],'cache request layer differs')
    require(params=={key:[str(value)] for key,value in tile['parameters'].items()},'cache request parameters differ')
    exact=expected_cache_path(tile)
    if expected=='MISS':
        added=set(after)-set(before)
        require(len(added)==1 and all(after[k]==v for k,v in before.items()),'cold miss did not add exactly one cache entry')
        entry=next(iter(added))
        require(entry==exact and after[entry]['sha256']==metadata['body_sha256'],'persisted tile identity differs from request/response')
        return entry
    require(before and after==before,'warm request changed/lacked persistent cache entries')
    matches=[k for k,v in after.items() if k==exact and v['sha256']==metadata['body_sha256']]
    require(matches,'cache hit body absent from persistent cache')
    return matches


def exercise(base,output,credentials,secrets,phase):
    directory=output/phase;directory.mkdir()
    cache=output/'tile-cache'
    result={'requests':[],'phase':phase,'result_exit_code':1}
    try:
        if phase=='initial':
            require(cache_manifest(cache)=={},'cold cache already contains tiles')
            for name in ('public_points','private_points'):
                body=('<GeoServerLayer><enabled>true</enabled><name>fixture:'+name+'</name><mimeFormats><string>image/png</string></mimeFormats>'
                    '<gridSubsets><gridSubset><gridSetName>EPSG:4326</gridSetName></gridSubset></gridSubsets>'
                    '<metaWidthHeight><int>1</int><int>1</int></metaWidthHeight><gutter>0</gutter><autoCacheStyles>false</autoCacheStyles></GeoServerLayer>').encode()
                info,_=request(base+'gwc/rest/layers/fixture:'+name,directory,'configure-'+name,secrets,
                    credentials['admin'],'PUT',body)
                require(info['status'] in (200,201),'scoped GWC layer administration failed')
        for name in ('public_points','private_points'):
            info,data=request(base+'gwc/rest/layers/fixture:'+name,directory,'configuration-'+name,secrets,credentials['admin'])
            require(info['status']==200,'configured cache-layer readback failed')
            root=ET.fromstring(data)
            require(root.findtext('enabled')=='true' and root.findtext('name')=='fixture:'+name,'cache layer not active')
            require([int(v.text) for v in root.findall('metaWidthHeight/int')]==[1,1],'metatiling not bounded')
        for name,token in [('public_points',None),('private_points',credentials['reader'])]:
            info,xml=request(base+'gwc/service/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetCapabilities',directory,'capabilities-'+name,secrets,token)
            require(info['status']==200,'capabilities HTTP failure')
            tile=select_tile(xml,base,'fixture:'+name)
            save(directory/('selected-'+name+'.json'),tile)
            url=tile['endpoint']+'?'+urlencode(tile['parameters'])
            if name=='private_points':
                for who,denied_token in [('anonymous',None),('outsider',credentials['outsider'])]:
                    before=cache_manifest(cache)
                    meta,body=request(url,directory,'private-before-'+who,secrets,denied_token)
                    denied=protocol_error(meta,body,authorization=True)
                    require(cache_manifest(cache)==before,'denied request altered tile cache')
                    result['requests'].append({'label':'private-before-'+who,'denial':denied})
            expected='MISS' if phase=='initial' else 'HIT'
            for label,cache_result in [('first',expected),('repeat','HIT')]:
                before=cache_manifest(cache)
                meta,body=request(url,directory,name+'-'+label,secrets,token)
                witness=tile_response(meta,body,tile,cache_result)
                after=cache_manifest(cache)
                entries=cache_transition(before,after,meta,cache_result,tile)
                save(directory/(name+'-'+label+'-cache.json'),{'before':before,'after':after,'entries':entries})
                save(directory/(name+'-'+label+'-image.json'),witness)
                result['requests'].append({'label':name+'-'+label,'cache_result':cache_result,'body_sha256':meta['body_sha256'],'image':witness,'cache_entries':entries})
            if name=='private_points':
                for who,denied_token in [('anonymous',None),('outsider',credentials['outsider'])]:
                    before=cache_manifest(cache)
                    meta,body=request(url,directory,'private-cached-'+who,secrets,denied_token)
                    denied=protocol_error(meta,body,authorization=True)
                    require(cache_manifest(cache)==before,'denied cached request altered cache')
                    result['requests'].append({'label':'private-cached-'+who,'denial':denied})
            else:
                bad=dict(tile['parameters'],LAYER='fixture:no_such_tile_layer')
                before=cache_manifest(cache)
                meta,body=request(tile['endpoint']+'?'+urlencode(bad),directory,'invalid-layer',secrets)
                result['invalid']=protocol_error(meta,body)
                require(cache_manifest(cache)==before,'invalid request altered cache')
                meta,body=request(url,directory,'valid-control',secrets)
                tile_response(meta,body,tile,'HIT');cache_transition(before,cache_manifest(cache),meta,'HIT',tile)
        result['result_exit_code']=0
        return result
    finally:
        save(directory/'result.json',result)
