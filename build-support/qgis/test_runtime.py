#!/usr/bin/env python3
"""Guard tests, explicitly not real QGIS acceptance evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_common import POINTS, SAMPLES, image_witness, inventory, loaded_origins, python_origins, selected_xml_origin, validate_mapped_origins
from runtime import build_environment, private_write, redact, validate_config
from runtime_child import command, server


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
    def markers(self, database=True, shift=0, local=True):
        for _,_,x,y in POINTS:
            px,py=self.xy(x,y)
            if local:
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
        self.assertEqual(10,len(result['checks']))
        omitted=[check for check in result['checks'] if check['kind']=='database']
        self.assertEqual([0,0,0],[check['matching_pixels'] for check in omitted])

    def test_combined_render_rejected_when_either_layer_omitted(self):
        for omitted in ('local','database'):
            with self.subTest(omitted=omitted),self.assertRaisesRegex(AssertionError,omitted+' omitted marker'):
                image_witness(Image().raster().markers(),(0,0,4,4),**{omitted:False})

    def test_database_only_render_has_no_local_markers(self):
        result=image_witness(Image().raster().markers(local=False),(0,0,4,4),local=False)
        omitted=[check for check in result['checks'] if check['kind']=='local']
        self.assertEqual([0,0,0],[check['matching_pixels'] for check in omitted])

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

    def test_nonzero_child_exit_retains_command_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(AssertionError,'exited unsuccessfully: 7'):
                command([sys.executable,'-c','raise SystemExit(7)'],{'output':name},'synthetic',[])
            receipt=json.loads((Path(name)/'synthetic-command.json').read_text())
            self.assertEqual(7,receipt['exit_code'])
            self.assertEqual(1,receipt['result_exit_code'])
            self.assertIn('log_sha256',receipt)

    def test_server_failure_preserves_partial_failed_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            with patch('runtime_child.server_requests',side_effect=RuntimeError('synthetic startup failure')):
                with self.assertRaisesRegex(RuntimeError,'startup failure'):
                    server({'output':name},[])
            receipt=json.loads((Path(name)/'server-result.json').read_text())
            self.assertEqual(1,receipt['result_exit_code'])
            self.assertEqual([],receipt['runs'])

    def test_python_plugin_search_is_empty_and_separate_from_native_registry(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name); font=root/'fixture.ttf'; font.write_bytes(b'fixture font')
            config={'python':sys.executable,'qgis_prefix':name,'database_prefix':name,
                    'spatial_prefix':name,'xml_prefix':str(root/'selected-xml'),'font_file':str(font),'qt_plugins':name,
                    'library_paths':[name],'python_paths':[name], 'provider_path':str(root/'native-providers')}
            env=build_environment(config,root)
            self.assertEqual(str(root/'empty-plugins'),env['QGIS_PLUGINPATH'])
            self.assertNotEqual(config['provider_path'],env['QGIS_PLUGINPATH'])
            self.assertEqual([],list((root/'empty-plugins').iterdir()))
            self.assertEqual('disable',env['GDAL_DRIVER_PATH'])
            self.assertIn('DISPLAY',env)
            self.assertEqual('',env['DISPLAY'])
            self.assertEqual('offscreen',env['QT_QPA_PLATFORM'])
            self.assertEqual(str(root/'platforms'),env['QT_QPA_PLATFORM_PLUGIN_PATH'])
            self.assertEqual(str(root/'selected-xml/lib'),env['LD_LIBRARY_PATH'].split(':')[0])

    def test_host_pyqt_module_fallback_rejected(self):
        config={'qgis_prefix':'/tmp/staged-qgis','support_prefix':'/tmp/retained-support'}
        with patch.dict(sys.modules,{'PyQt5.QtCore':SimpleNamespace(__file__='/usr/lib64/python3.13/site-packages/PyQt5/QtCore.so')}):
            with self.assertRaisesRegex(AssertionError,'unretained Python binding module'):
                python_origins(config)

    def test_original_or_host_xml_fallback_rejected(self):
        config={'xml_prefix':'/tmp/retained-xml'}
        for path in ('/usr/lib64/libxml2.so.2','/tmp/original-native/lib/libxml2.so.2'):
            with self.subTest(path=path), self.assertRaisesRegex(AssertionError,'unselected libxml2 mapping'):
                selected_xml_origin(config,[path])

    def test_multiple_xml_mappings_rejected(self):
        config={'xml_prefix':'/tmp/retained-xml'}
        with self.assertRaisesRegex(AssertionError,'multiple libxml2'):
            selected_xml_origin(config,['/tmp/retained-xml/lib/libxml2.so','/usr/lib64/libxml2.so.2'])

    def test_exact_selected_xml_mapping_accepted(self):
        config={'xml_prefix':'/tmp/retained-xml'}
        path='/tmp/retained-xml/lib/libxml2.so'
        self.assertEqual(path,selected_xml_origin(config,[path,path]))

    def mapped_fixture(self):
        config={key:'/retained/'+label for key,label in (
            ('qgis_prefix','qgis'),('spatial_prefix','spatial'),('database_prefix','native'),
            ('support_prefix','support'),('xml_prefix','xml'))}
        config['qt_plugins']='/retained/support/usr/lib64/qt5/plugins'
        paths=[
            '/retained/qgis/lib/libqgis_core.so',
            '/retained/qgis/lib/qgis/plugins/libprovider_postgres.so',
            '/retained/spatial/lib/libgdal.so', '/retained/spatial/lib/libproj.so',
            '/retained/spatial/lib/libsqlite3.so', '/retained/native/lib/libgeos.so',
            '/retained/native/lib/libgeos_c.so', '/retained/native/lib/libpq.so',
            '/retained/xml/lib/libxml2.so', '/retained/support/usr/lib64/libQt5Core.so',
            '/retained/support/usr/lib64/libQt5Gui.so',
            '/retained/support/usr/lib64/qt5/plugins/platforms/libqoffscreen.so',
            '/retained/support/usr/lib64/qt5/plugins/crypto/libqca-ossl.so']
        return config,paths

    def test_full_selected_mapping_set_accepted(self):
        config,paths=self.mapped_fixture()
        result=validate_mapped_origins(config,paths)
        self.assertEqual(['/retained/spatial/lib/libsqlite3.so'],result['libsqlite3.so'])
        self.assertEqual(2,len(result['qt_modules']))

    def test_host_qt_gui_rejected_even_with_retained_core(self):
        config,paths=self.mapped_fixture()
        paths[paths.index('/retained/support/usr/lib64/libQt5Gui.so')]='/usr/lib64/libQt5Gui.so.5'
        with self.assertRaisesRegex(AssertionError,'unretained Qt module'):
            validate_mapped_origins(config,paths)

    def test_original_gdal_proj_sqlite_fallbacks_rejected(self):
        config,original=self.mapped_fixture()
        for library in ('libgdal.so','libproj.so','libsqlite3.so'):
            paths=original.copy();paths[paths.index('/retained/spatial/lib/'+library)]='/retained/native/lib/'+library
            with self.subTest(library=library),self.assertRaisesRegex(AssertionError,'unselected runtime mapping'):
                validate_mapped_origins(config,paths)

    def test_host_offscreen_platform_fallback_rejected(self):
        config,paths=self.mapped_fixture()
        paths[paths.index(config['qt_plugins']+'/platforms/libqoffscreen.so')]='/usr/lib64/qt5/plugins/platforms/libqoffscreen.so'
        with self.assertRaisesRegex(AssertionError,'unselected runtime mapping: libqoffscreen'):
            validate_mapped_origins(config,paths)

    def test_host_qt_image_plugin_rejected(self):
        config,paths=self.mapped_fixture()
        paths.append('/usr/lib64/qt5/plugins/imageformats/libqjpeg.so')
        with self.assertRaisesRegex(AssertionError,'unretained Qt/QCA plugin'):
            validate_mapped_origins(config,paths)

    def test_host_qca_plugin_rejected(self):
        config,paths=self.mapped_fixture()
        paths.append('/usr/lib64/qca-qt5/crypto/libqca-ossl.so')
        with self.assertRaisesRegex(AssertionError,'unretained QCA'):
            validate_mapped_origins(config,paths)

    def test_empty_profile_rejected(self):
        with self.assertRaisesRegex(AssertionError,'retained input'): validate_config({})

    def test_missing_loaded_engine_is_failure(self):
        config={key:'/tmp' for key in ('qgis_prefix','spatial_prefix','database_prefix','support_prefix','xml_prefix')}
        with patch('pathlib.Path.read_text',return_value=''):
            with self.assertRaisesRegex(AssertionError,'mapping absent'): loaded_origins(config)

    def test_unretained_qgis_mapping_rejected(self):
        config={key:'/tmp/retained' for key in ('qgis_prefix','spatial_prefix','database_prefix','support_prefix','xml_prefix')}
        with patch('pathlib.Path.read_text',return_value='1-2 r-xp 0 0:0 0 /usr/lib64/libqgis_core.so.3\n'):
            with self.assertRaisesRegex(AssertionError,'unretained QGIS'): loaded_origins(config)

if __name__=='__main__': unittest.main()
