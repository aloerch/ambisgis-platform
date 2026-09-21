import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import common

import build
import python_gdal
from common import inventory, verify_inventory

class BuildGuards(unittest.TestCase):
    def test_prefix_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'library').write_bytes(b'owned')
            rows=inventory(root);verify_inventory(root,rows)
            (root/'library').write_bytes(b'host')
            with self.assertRaisesRegex(ValueError,'changed'):verify_inventory(root,rows)

    def test_symlink_retargeting(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'library').write_bytes(b'owned');(root/'link').symlink_to('library')
            rows=inventory(root);(root/'link').unlink();(root/'link').symlink_to('/usr/lib/host')
            with self.assertRaisesRegex(ValueError,'changed'):verify_inventory(root,rows)

    def test_omitted_output_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'library').write_bytes(b'owned');rows=inventory(root)
            (root/'library').unlink()
            with self.assertRaisesRegex(ValueError,'changed'):verify_inventory(root,rows)

    def test_publisher_mode_guard(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'tool';p.write_bytes(b'tool');p.chmod(0o755)
            rows=inventory(root);rows[0]['size']=rows[0].pop('bytes');rows[0]['mode']='0o755'
            verify_inventory(root,rows);p.chmod(0o644)
            with self.assertRaisesRegex(ValueError,'mode'):verify_inventory(root,rows)

    def cache(self):
        rows={k:('BOOL',v) for k,v in build.REQUIRED.items()}
        rows.update({k:('PATH',v) for k,v in {'CMAKE_INSTALL_PREFIX':'/private/stage',
           'Python_EXECUTABLE':'/usr/bin/python3.13','SHA':build.COMMIT,'GDAL_DIR':'/private/spatial/cmake',
           'GEOS_DIR':'/private/native/cmake','PROJ_DIR':'/private/spatial/cmake',
           'PostgreSQL_LIBRARY_RELEASE':'/private/native/lib/libpq.so','Qt5_DIR':'/private/support/qt',
           'FCGI_INCLUDE_DIR':'/private/support/include/fastcgi','FCGI_LIBRARY':'/private/support/lib/libfcgi.so',
           'LIBXML2_LIBRARY':'/private/xml/lib/libxml2.so','LIBXML2_INCLUDE_DIR':'/private/xml/include/libxml2',
           'pkgcfg_lib_PC_SPATIALITE_xml2':'/private/xml/lib/libxml2.so',
           'ZSTD_INCLUDE_DIR':'/private/support/include','ZSTD_LIBRARY':'/private/support/lib/libzstd.so',
           'SQLite3_LIBRARY':'/private/spatial/lib/libsqlite3.so',
           'QWT_INCLUDE_DIR':'/private/support/include/qwt','QWT_LIBRARY':'/private/support/lib/libqwt.so',
           'pkgcfg_lib_PC_SPATIALITE_spatialite':'/private/support/lib/libspatialite.so',
           'pkgcfg_lib_PC_SPATIALITE_sqlite3':'/private/spatial/lib/libsqlite3.so',
           'pkgcfg_lib_PC_SPATIALITE_z':'/private/native/lib/libz.so'}.items()})
        return rows

    def check(self,rows):
        build.check_config(rows,Path('/private/native'),Path('/private/spatial'),Path('/private/support'),Path('/private/xml'))

    def test_required_features(self):
        self.check(self.cache())
        for key in ('WITH_DESKTOP','WITH_SERVER','WITH_PYTHON','WITH_BINDINGS','WITH_POSTGRESQL','ENABLE_TESTS'):
            with self.subTest(key=key):
                rows=self.cache();rows[key]=('BOOL','OFF')
                with self.assertRaisesRegex(ValueError,'profile'):self.check(rows)

    def test_qt6_and_global_bindings_rejected(self):
        for key in ('BUILD_WITH_QT6','BINDINGS_GLOBAL_INSTALL','SIP_GLOBAL_INSTALL','WITH_VCPKG'):
            with self.subTest(key=key):
                rows=self.cache();rows[key]=('BOOL','ON')
                with self.assertRaisesRegex(ValueError,'profile'):self.check(rows)

    def test_host_spatial_fallback_rejected(self):
        for key in ('GDAL_DIR','GEOS_DIR','PROJ_DIR','PostgreSQL_LIBRARY_RELEASE','Qt5_DIR','FCGI_LIBRARY','QWT_INCLUDE_DIR','ZSTD_LIBRARY','SQLite3_LIBRARY','LIBXML2_LIBRARY','pkgcfg_lib_PC_SPATIALITE_sqlite3','pkgcfg_lib_PC_SPATIALITE_z'):
            with self.subTest(key=key):
                rows=self.cache();rows[key]=('PATH','/usr/lib/unrecorded')
                with self.assertRaisesRegex(ValueError,'origin'):self.check(rows)

    def test_binding_source_changes_and_unexpected_additions_fail(self):
        original=[{'path':'gcore/gdal.cpp','bytes':5,'sha256':'original'}]
        metadata=[{'path':'swig/python/gdal-utils/GDAL.egg-info/'+n,'bytes':1,'sha256':'generated'}
                  for n in python_gdal.METADATA]
        self.assertEqual(len(python_gdal.check_source(original,original+metadata)),7)
        for after in (metadata,original,original+metadata+[{'path':'unexpected'}],
                      [dict(original[0],sha256='changed')]+metadata):
            with self.subTest(after=after),self.assertRaises(ValueError):
                python_gdal.check_source(original,after)

    def test_xml_producer_and_inventory_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);prefix=root/'prefix';prefix.mkdir();library=prefix/'libxml2.so'
            library.write_bytes(b'owned XML ABI')
            manifest=root/'output-manifest.json'
            manifest.write_text(json.dumps({'prefix':str(prefix),'files':inventory(prefix)}))
            success=root/'success.json'
            success.write_text(json.dumps({'state':'xml-profile-built','manifest_sha256':common.sha(manifest)}))
            profile={'references':{key:{'path':str(path),'sha256':common.sha(path)}
                     for key,path in [('xml_manifest',manifest),('xml_success',success)]}}
            (root/'profile-inputs.json').write_text(json.dumps(profile))
            with mock.patch.object(common,'HERE',root):
                common.verify_xml(prefix)
                with self.assertRaisesRegex(ValueError,'Wrong selected XML'):
                    common.verify_xml(root/'unselected')
                library.write_bytes(b'host replacement')
                with self.assertRaisesRegex(ValueError,'Retained prefix changed'):
                    common.verify_xml(prefix)
                library.write_bytes(b'owned XML ABI');(root/'failure.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'did not succeed'):
                    common.verify_xml(prefix)

    def test_prior_output_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'success.json').write_text('preserved')
            with self.assertRaisesRegex(ValueError,'Fresh output'):
                build.build(root,root,root,root,root,4)
            self.assertEqual((root/'success.json').read_text(),'preserved')
            self.assertEqual(list(root.iterdir()),[root/'success.json'])

if __name__=='__main__':unittest.main()
