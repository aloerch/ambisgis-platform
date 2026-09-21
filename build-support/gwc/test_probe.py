"""Independent F02-05 probe failure tests; no servers, network, or repo mutations."""
import copy
import json
from unittest.mock import patch, Mock
import importlib.util
import io
import math
from urllib.parse import urlencode
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

MODULE = Path(__file__).with_name('probe.py')
spec = importlib.util.spec_from_file_location('f02_gwc_probe_review', MODULE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
BASE = 'http://127.0.0.1:32456/geoserver/'
TILE = {'tile_size': [256, 256], 'expected_center_px': [128, 128]}

def png(kind='circle'):
    im = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    if kind == 'circle':
        draw.ellipse((115, 115, 141, 141), fill=(230, 0, 0, 255))
    elif kind == 'square':
        draw.rectangle((116, 116, 139, 139), fill=(230, 0, 0, 255))
    elif kind == 'misplaced':
        draw.ellipse((35, 35, 61, 61), fill=(230, 0, 0, 255))
    elif kind == 'blue':
        draw.ellipse((115, 115, 141, 141), fill=(0, 0, 230, 255))
    elif kind == 'opaque':
        draw.rectangle((0, 0, 255, 255), fill=(255, 255, 255, 255))
        draw.ellipse((115, 115, 141, 141), fill=(230, 0, 0, 255))
    elif kind == 'small':
        im = Image.new('RGBA', (1, 1))
    out = io.BytesIO(); im.save(out, format='PNG'); return out.getvalue()

def capabilities():
    scale = (5.625 / 256) * (2 * math.pi * 6378137 / 360) / .00028
    previous=''.join(f'<TileMatrix><o:Identifier>EPSG:4326:{z}</o:Identifier><ScaleDenominator>{scale*(2**(5-z))}</ScaleDenominator><TopLeftCorner>90 -180</TopLeftCorner><TileWidth>256</TileWidth><TileHeight>256</TileHeight><MatrixWidth>{2**(z+1)}</MatrixWidth><MatrixHeight>{2**z}</MatrixHeight></TileMatrix>' for z in range(5))
    return f'''<Capabilities xmlns="{probe.NS['w']}" xmlns:o="{probe.NS['o']}" xmlns:x="{probe.NS['x']}" version="1.0.0">
    <o:OperationsMetadata><o:Operation name="GetTile"><o:DCP><o:HTTP><o:Get x:href="{BASE}gwc/service/wmts?"/></o:HTTP></o:DCP></o:Operation></o:OperationsMetadata>
    <Contents><Layer><o:Identifier>fixture:public_points</o:Identifier><Style isDefault="true"><o:Identifier>witness</o:Identifier></Style><Format>image/png</Format><TileMatrixSetLink><TileMatrixSet>EPSG:4326</TileMatrixSet></TileMatrixSetLink></Layer>
    <TileMatrixSet><o:Identifier>EPSG:4326</o:Identifier><o:SupportedCRS>urn:ogc:def:crs:EPSG::4326</o:SupportedCRS>{previous}<TileMatrix><o:Identifier>EPSG:4326:5</o:Identifier><ScaleDenominator>{scale}</ScaleDenominator><TopLeftCorner>90 -180</TopLeftCorner><TileWidth>256</TileWidth><TileHeight>256</TileHeight><MatrixWidth>64</MatrixWidth><MatrixHeight>32</MatrixHeight></TileMatrix></TileMatrixSet></Contents></Capabilities>'''.encode()


def cache_meta(layer='fixture:public_points', row=15, col=32):
    params = dict(SERVICE='WMTS', VERSION='1.0.0', REQUEST='GetTile', LAYER=layer, STYLE='witness', FORMAT='image/png', TILEMATRIXSET='EPSG:4326', TILEMATRIX='EPSG:4326:5', TILEROW=row, TILECOL=col)
    return {'body_sha256': probe.sha(png()), 'url': BASE + 'gwc/service/wmts?' + urlencode(params)}

def cache_entries(layer='fixture:public_points', x=32, y=16, body=None):
    return {layer.replace(':','_') + f'/EPSG_4326_05/4_2/{x}_{y}.png': {'sha256': probe.sha(png() if body is None else body), 'mtime_ns': 1, 'inode': 1}}

def exception(code, locator, text):
    root = ET.Element('{'+probe.NS['o']+'}ExceptionReport', version='1.1.0')
    error = ET.SubElement(root, '{'+probe.NS['o']+'}Exception', exceptionCode=code, locator=locator)
    ET.SubElement(error, '{'+probe.NS['o']+'}ExceptionText').text = text
    return ET.tostring(root)


def selected_tile(layer='fixture:public_points'):
    xml = capabilities().replace(b'fixture:public_points', layer.encode())
    return probe.select_tile(xml, BASE, layer)

def transition(before, after, metadata, expected):
    from urllib.parse import parse_qs, urlsplit
    layer = parse_qs(urlsplit(metadata['url']).query)['LAYER'][0]
    return probe.cache_transition(before, after, metadata, expected, selected_tile(layer))

def tile_image(tile):
    image = Image.new('RGBA', (256,256), (0,0,0,0)); cx,cy=tile['expected_center_px']
    for y in range(256):
        for x in range(256):
            if math.hypot(x+.5-cx,y+.5-cy) <= 13:
                image.putpixel((x,y), (230,0,0,255))
    out=io.BytesIO(); image.save(out,format='PNG'); return out.getvalue()

def tile_metadata():
    tile=selected_tile()
    return {'status':200,'headers':{'content-type':'image/png','geowebcache-cache-result':'HIT','geowebcache-gridset':'EPSG:4326','geowebcache-crs':'EPSG:4326','geowebcache-tile-index':'[32,16,5]','geowebcache-tile-bounds':json.dumps(tile['bounds_xy'])}}

class FakeResponse:
    def __init__(self, data=b'response', headers=None):
        self.data=data; self.headers={} if headers is None else headers; self.status=200
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,limit): return self.data[:limit]
    def geturl(self): return BASE+'gwc/service/wmts'


def denial_metadata():
    return {'status':400,'headers':{'content-type':'text/html;charset=utf-8'}}

def denial(message='400: Cannot access private_points with the current privileges',extra=''):
    return ('<html><head><title>GWC Error</title></head><body><h4>'+message+'</h4>'+extra+'</body></html>').encode()

class ProbeReviewTests(unittest.TestCase):
    def rejects(self, fn, *args, **kwargs):
        with self.assertRaises((ValueError, ET.ParseError)):
            fn(*args, **kwargs)

    def test_positive_png_control(self):
        self.assertTrue(probe.image_witness(png(), TILE)['red_pixels'] > 450)

    def test_blank_png_rejected(self): self.rejects(probe.image_witness, png('blank'), TILE)
    def test_wrong_size_rejected(self): self.rejects(probe.image_witness, png('small'), TILE)
    def test_blue_geometry_rejected(self): self.rejects(probe.image_witness, png('blue'), TILE)
    def test_misplaced_geometry_rejected(self): self.rejects(probe.image_witness, png('misplaced'), TILE)
    def test_opaque_background_rejected(self): self.rejects(probe.image_witness, png('opaque'), TILE)
    def test_wrong_square_geometry_rejected(self): self.rejects(probe.image_witness, png('square'), TILE)
    def test_xml_image_rejected(self): self.rejects(probe.image_witness, b'<ExceptionReport/>', TILE)

    def test_positive_capabilities_geometry_control(self):
        tile = probe.select_tile(capabilities(), BASE, 'fixture:public_points')
        self.assertEqual(tile['matrix_index'], 5)
        self.assertEqual(tile['parameters']['TILEROW'], 15)
        self.assertEqual(tile['parameters']['TILECOL'], 32)
        self.assertEqual(tile['parameters']['TILEMATRIX'], 'EPSG:4326:5')
        self.assertEqual(tile['bounds_xy'], [0.0, 0.0, 5.625, 5.625])
        self.assertAlmostEqual(tile['expected_center_px'][0], 45.51111111111111)
        self.assertAlmostEqual(tile['expected_center_px'][1], 164.9777777777778)

    def test_wrong_capabilities_document_rejected(self): self.rejects(probe.select_tile, b'<ExceptionReport/>', BASE, 'fixture:public_points')
    def test_unknown_layer_rejected(self): self.rejects(probe.select_tile, capabilities(), BASE, 'fixture:absent')
    def test_wrong_axis_order_rejected(self): self.rejects(probe.select_tile, capabilities().replace(b'90 -180', b'-180 90'), BASE, 'fixture:public_points')
    def test_nonloopback_advertised_endpoint_rejected(self): self.rejects(probe.select_tile, capabilities().replace(BASE.encode(), b'http://remote.example/geoserver/'), BASE, 'fixture:public_points')
    def test_wrong_crs_rejected(self): self.rejects(probe.select_tile, capabilities().replace(b'urn:ogc:def:crs:EPSG::4326', b'urn:ogc:def:crs:EPSG::3857'), BASE, 'fixture:public_points')

    def test_cache_symlink_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'real').mkdir(); (root/'cache').symlink_to(root/'real', target_is_directory=True)
            self.rejects(probe.cache_manifest, root/'cache')
    def test_cache_symlink_file_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'cache').mkdir(); (root/'outside.png').write_bytes(png()); (root/'cache'/'tile.png').symlink_to(root/'outside.png')
            self.rejects(probe.cache_manifest, root/'cache')
    def test_cache_symlink_directory_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'cache').mkdir(); (root/'outside').mkdir(); (root/'cache'/'outside').symlink_to(root/'outside', target_is_directory=True)
            self.rejects(probe.cache_manifest, root/'cache')
    def test_cache_bounded_entry_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in range(3): (root/f'{n}.png').write_bytes(png())
            self.rejects(probe.cache_manifest, root)
    def test_fake_hit_without_disk_evidence_rejected(self): self.rejects(transition, {}, {}, cache_meta(), 'HIT')
    def test_fake_hit_wrong_disk_content_rejected(self):
        entries = cache_entries(body=png('blank'))
        self.rejects(transition, entries, entries, cache_meta(), 'HIT')
    def test_fake_hit_mutated_entry_rejected(self):
        before = cache_entries()
        after = copy.deepcopy(before); after[next(iter(after))]['mtime_ns'] = 2
        self.rejects(transition, before, after, cache_meta(), 'HIT')
    def test_fake_hit_wrong_layer_evidence_rejected(self):
        entries = cache_entries()
        metadata = cache_meta(layer='fixture:private_points')
        self.rejects(transition, entries, entries, metadata, 'HIT')
    def test_fake_miss_without_entry_rejected(self): self.rejects(transition, {}, {}, cache_meta(), 'MISS')

    def test_http200_exception_rejected(self): self.rejects(probe.protocol_error, {'status': 200}, b'<ExceptionReport><Exception>not found</Exception></ExceptionReport>')
    def test_image_error_rejected(self): self.rejects(probe.protocol_error, {'status': 400}, png())
    def test_empty_protocol_report_rejected(self): self.rejects(probe.protocol_error, {'status': 400}, b'<ExceptionReport/>')
    def test_unrelated_namespace_error_rejected(self): self.rejects(probe.protocol_error, {'status': 403}, b'<ExceptionReport xmlns="urn:unrelated">access denied</ExceptionReport>', authorization=True)
    def test_upstream_access_problem_not_authorization_proof(self): self.rejects(probe.protocol_error, {'status': 500}, b'<ExceptionReport xmlns="http://www.opengis.net/ows/1.1"><Exception exceptionCode="NoApplicableCode"><ExceptionText>Failure accessing datasource</ExceptionText></Exception></ExceptionReport>', authorization=True)
    def test_external_request_rejected_before_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.rejects(probe.request, 'http://example.test:80/geoserver/', Path(tmp), 'external', [])


    def test_positive_cold_then_warm_disk_control(self):
        after = cache_entries()
        transition({}, after, cache_meta(), 'MISS')
        transition(after, after, cache_meta(), 'HIT')
    def test_fake_hit_same_layer_wrong_coordinates_rejected(self):
        entries = cache_entries(x=31)
        self.rejects(transition, entries, entries, cache_meta(), 'HIT')
    def test_fake_miss_same_layer_wrong_coordinates_rejected(self):
        self.rejects(transition, {}, cache_entries(x=31), cache_meta(), 'MISS')
    def test_positive_native_invalid_layer_protocol_control(self):
        result = probe.protocol_error({'status':400}, exception('InvalidParameterValue','LAYER','LAYER fixture:no_such_tile_layer is not known.'))
        self.assertEqual(result['status'],400)
    def test_wrong_exception_locator_rejected(self):
        self.rejects(probe.protocol_error, {'status':400}, exception('InvalidParameterValue','TILEROW','LAYER fixture:no_such_tile_layer is not known.'))
    def test_wrong_invalid_layer_identity_rejected(self):
        self.rejects(probe.protocol_error, {'status':400}, exception('InvalidParameterValue','LAYER','LAYER fixture:unrelated is not known.'))
    def test_generic_service_missing_not_auth_denial(self):
        self.rejects(probe.protocol_error, {'status':400,'headers':{'content-type':'text/xml'}}, exception('NoApplicableCode','request','Service or request not found'), authorization=True)
    def test_same_layer_datasource_error_not_auth_denial(self):
        self.rejects(probe.protocol_error, {'status':400,'headers':{'content-type':'text/xml'}}, exception('NoApplicableCode','','Failure accessing datasource for fixture:private_points'), authorization=True)


    def test_expected_path_derived_from_actual_matrix_order_and_row_flip(self):
        self.assertEqual(probe.expected_cache_path(selected_tile()), 'fixture_public_points/EPSG_4326_05/4_2/32_16.png')
    def test_request_tile_parameters_cannot_disagree(self):
        self.rejects(probe.cache_transition, cache_entries(),cache_entries(),cache_meta(col=31),'HIT',selected_tile())
    def test_positive_native_response_identity_control(self):
        tile=selected_tile()
        probe.tile_response(tile_metadata(),tile_image(tile),tile,'HIT')
    def test_wrong_native_response_grid_rejected(self):
        meta=tile_metadata();meta['headers']['geowebcache-gridset']='EPSG:3857'
        self.rejects(probe.tile_response,meta,tile_image(selected_tile()),selected_tile(),'HIT')
    def test_wrong_native_response_index_rejected(self):
        meta=tile_metadata();meta['headers']['geowebcache-tile-index']='[32,15,5]'
        self.rejects(probe.tile_response,meta,tile_image(selected_tile()),selected_tile(),'HIT')
    def test_wrong_native_response_bounds_rejected(self):
        meta=tile_metadata();meta['headers']['geowebcache-tile-bounds']='[1,0,6.625,5.625]'
        self.rejects(probe.tile_response,meta,tile_image(selected_tile()),selected_tile(),'HIT')
    def test_wrong_native_cache_result_rejected(self):
        meta=tile_metadata();meta['headers']['geowebcache-cache-result']='WMS'
        self.rejects(probe.tile_response,meta,tile_image(selected_tile()),selected_tile(),'HIT')
    def test_positive_source_defined_anonymous_denial(self):
        result=probe.protocol_error(denial_metadata(),denial('400: Cannot access private_points as anonymous'),authorization=True)
        self.assertEqual(result['status'],400)
    def test_positive_source_defined_outsider_denial(self):
        result=probe.protocol_error(denial_metadata(),denial('400: Cannot access private_points with the current privileges'),authorization=True)
        self.assertEqual(result['status'],400)
    def test_wrong_protected_layer_denial_rejected(self):
        self.rejects(probe.protocol_error,denial_metadata(),denial('400: Cannot access other_layer with the current privileges'),authorization=True)
    def test_set_cookie_rejected_without_writing_receipt(self):
        opener=Mock();opener.open.return_value=FakeResponse(headers={'Set-Cookie':'session=synthetic'})
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe.urllib.request,'build_opener',return_value=opener):
            self.rejects(probe.request,BASE+'gwc/service/wmts',Path(tmp),'cookie',[])
            self.assertEqual(list(Path(tmp).iterdir()),[])
    def test_secret_reflection_rejected_without_writing_receipt(self):
        opener=Mock();opener.open.return_value=FakeResponse(b'fixture-sensitive-sentinel')
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe.urllib.request,'build_opener',return_value=opener):
            self.rejects(probe.request,BASE+'gwc/service/wmts',Path(tmp),'secret',['fixture-sensitive-sentinel'])
            self.assertEqual(list(Path(tmp).iterdir()),[])
    def test_http_redirect_rejected_before_following(self):
        req=probe.urllib.request.Request(BASE+'gwc/service/wmts')
        self.rejects(probe.NoRedirect().http_error_302,req,None,302,'Found',{'location':'http://example.test/redirect'})
    def test_oversized_response_rejected_without_writing_receipt(self):
        opener=Mock();opener.open.return_value=FakeResponse(b'x'*(8*1024*1024+1))
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe.urllib.request,'build_opener',return_value=opener):
            self.rejects(probe.request,BASE+'gwc/service/wmts',Path(tmp),'oversize',[])
            self.assertEqual(list(Path(tmp).iterdir()),[])


    def test_native_denial_success_status_rejected(self):
        meta=denial_metadata();meta['status']=200
        self.rejects(probe.protocol_error,meta,denial(),authorization=True)
    def test_native_denial_wrong_title_rejected(self):
        self.rejects(probe.protocol_error,denial_metadata(),denial().replace(b'GWC Error',b'Login'),authorization=True)
    def test_native_denial_with_login_form_rejected(self):
        self.rejects(probe.protocol_error,denial_metadata(),denial(extra='<form action="/login"/>'),authorization=True)
    def test_native_denial_for_missing_service_rejected(self):
        self.rejects(probe.protocol_error,denial_metadata(),denial('400: Service or request not found'),authorization=True)
    def test_native_denial_for_datasource_failure_rejected(self):
        self.rejects(probe.protocol_error,denial_metadata(),denial('400: Failure accessing private_points datasource'),authorization=True)
    def test_native_denial_empty_body_rejected(self):
        self.rejects(probe.protocol_error,denial_metadata(),b'',authorization=True)
    def test_native_denial_duplicate_messages_rejected(self):
        self.rejects(probe.protocol_error,denial_metadata(),denial(extra='<h4>400: Cannot access private_points as anonymous</h4>'),authorization=True)
    def test_positive_blank_native_default_style_control(self):
        tile=selected_tile();tile['parameters']['STYLE']=''
        meta=cache_meta();meta['url']=meta['url'].replace('STYLE=witness','STYLE=')
        probe.cache_transition(cache_entries(),cache_entries(),meta,'HIT',tile)

if __name__ == '__main__': unittest.main(verbosity=2)
