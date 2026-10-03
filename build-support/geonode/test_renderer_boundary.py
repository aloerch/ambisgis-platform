"""Parser/integrity negatives are unit evidence, separate from real GIS runtime."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlencode

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/control-plane'))
from ambisgis_render.boundary import Bindings, FIELDS, resource


class MapBoundary(unittest.TestCase):
    def query(self,**changes):return urlencode(dict(FIELDS,layers='fixture:private_points',**changes))
    def test_supported_single_map(self):
        self.assertEqual(resource('GET','/map',self.query()),'fixture:private_points')
    def test_duplicate_extra_and_target_injection(self):
        for suffix in ('&LAYERS=fixture:public_points','&%6cayers=fixture:public_points',
                       '&MAP=/etc/passwd','&SLD=http://127.0.0.1/x','&SLD_BODY=payload',
                       '&FEATURE_COUNT=5','&layers=x','&foo','&'):
            with self.subTest(suffix=suffix):self.assertIsNone(resource('GET','/map',self.query()+suffix))
    def test_excluded_requests_and_formats(self):
        for key,value in [('request','GetFeatureInfo'),('request','GetCapabilities'),('format','text/html'),
                          ('width','2000000000'),('height','-1'),('srs','EPSG:3857'),('styles','else'),
                          ('layers','fixture:public_points,fixture:private_points'),('bbox','nan,0,4,4')]:
            fields=dict(FIELDS,layers='fixture:private_points');fields[key]=value
            with self.subTest(key=key,value=value):self.assertIsNone(resource('GET','/map',urlencode(fields)))
    def test_routes_verbs_malformed_encoding(self):
        for method,path in [('POST','/map'),('GET','/rest'),('GET','//map'),('GET','/map/')]:
            self.assertIsNone(resource(method,path,self.query()))
        self.assertIsNone(resource('GET','/map',self.query()+'%zz'))
    def test_approved_asset_binding_rejects_mutation_and_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);asset=root/'map.qgs';asset.write_text('approved')
            bindings={'fixture:private_points':{'renderer':'qgis-server','assets':[{
                'path':str(asset),'sha256':hashlib.sha256(asset.read_bytes()).hexdigest()}]}}
            path=root/'bindings.json';path.write_text(json.dumps(bindings))
            digest=hashlib.sha256(path.read_bytes()).hexdigest();bound=Bindings(path,digest)
            self.assertTrue(bound.valid('fixture:private_points'))
            self.assertFalse(bound.valid('fixture:public_points'))
            asset.write_text('mutated');self.assertFalse(bound.valid('fixture:private_points'))
            copy=root/'other';copy.write_text('approved');asset.unlink();asset.symlink_to(copy)
            self.assertFalse(bound.valid('fixture:private_points'))
            with self.assertRaises(ValueError):Bindings(path,'0'*64)


if __name__=='__main__':unittest.main()
