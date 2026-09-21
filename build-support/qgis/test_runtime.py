#!/usr/bin/env python3
"""Guard tests, explicitly not real QGIS acceptance evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_common import POINTS, SAMPLES, image_witness, inventory, loaded_origins
from runtime import private_write, redact, validate_config
from runtime_child import server


class Color:
    def __init__(self,rgb): self.rgb=rgb
    def getRgb(self): return (*self.rgb,255)

class Image:
    def __init__(self): self.pixels={}
    def width(self): return 512
    def height(self): return 512
    def isNull(self): return False
    def pixelColor(self,x,y): return Color(self.pixels.get((x,y),(255,255,255)))
    def xy(self,x,y): return round(x/4*511),round((4-y)/4*511)
    def raster(self):
        for x,y,value in SAMPLES: self.pixels[self.xy(x,y)]=(value,value,value)
        return self
    def markers(self, database=True, shift=0):
        for _,_,x,y in POINTS:
            px,py=self.xy(x,y)
            for i in range(-4,5):
                for j in range(-4,5): self.pixels[px+i+shift,py+j]=(220,20,30)
            if database:
                for i in range(-2,3):
                    for j in range(-2,3): self.pixels[px+i+shift,py+j]=(20,60,230)
        return self


class RuntimeGuards(unittest.TestCase):
    def test_blank_png_fails(self):
        with self.assertRaisesRegex(AssertionError,'raster render'): image_witness(Image(),(0,0,4,4))

    def test_missing_postgis_render_fails(self):
        with self.assertRaisesRegex(AssertionError,'database marker'): image_witness(Image().raster().markers(False),(0,0,4,4))

    def test_misplaced_vectors_fail(self):
        with self.assertRaisesRegex(AssertionError,'marker missing or misplaced'): image_witness(Image().raster().markers(shift=70),(0,0,4,4))

    def test_expected_spatial_color_layout_passes_guard(self):
        result=image_witness(Image().raster().markers(),(0,0,4,4))
        self.assertEqual(10,len(result['checks']))

    def test_explicit_single_layer_map_guard(self):
        result=image_witness(Image().raster().markers(False),(0,0,4,4),database=False)
        self.assertEqual(7,len(result['checks']))

    def test_redaction_scrubs_every_occurrence(self):
        self.assertEqual('[REDACTED_FIXTURE_VALUE] x [REDACTED_FIXTURE_VALUE]',redact('secret x secret',['secret']))

    def test_credentials_are_created_private_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'pgpass'; private_write(path,'synthetic')
            self.assertEqual(0o600,path.stat().st_mode&0o777)
            with self.assertRaises(FileExistsError): private_write(path,'replacement')

    def test_integrity_detects_content_changes(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'artifact'; path.write_text('a'); before=inventory(name)
            path.write_text('b'); self.assertNotEqual(before,inventory(name))

    def test_server_failure_preserves_partial_failed_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            with patch('runtime_child.server_requests',side_effect=RuntimeError('synthetic startup failure')):
                with self.assertRaisesRegex(RuntimeError,'startup failure'):
                    server({'output':name},[])
            receipt=json.loads((Path(name)/'server-result.json').read_text())
            self.assertEqual(1,receipt['result_exit_code'])
            self.assertEqual([],receipt['runs'])

    def test_empty_profile_rejected(self):
        with self.assertRaisesRegex(AssertionError,'retained input'): validate_config({})

    def test_missing_loaded_engine_is_failure(self):
        config={key:'/tmp' for key in ('qgis_prefix','spatial_prefix','database_prefix','support_prefix')}
        with patch('pathlib.Path.read_text',return_value=''):
            with self.assertRaisesRegex(AssertionError,'mapping absent'): loaded_origins(config)

    def test_unretained_qgis_mapping_rejected(self):
        config={key:'/tmp/retained' for key in ('qgis_prefix','spatial_prefix','database_prefix','support_prefix')}
        with patch('pathlib.Path.read_text',return_value='1-2 r-xp 0 0:0 0 /usr/lib64/libqgis_core.so.3\n'):
            with self.assertRaisesRegex(AssertionError,'unretained QGIS'): loaded_origins(config)

if __name__=='__main__': unittest.main()
