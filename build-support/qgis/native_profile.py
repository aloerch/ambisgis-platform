#!/usr/bin/env python3
"""Build a separate retained GDAL profile for QGIS; never alter the database prefix."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from common import HERE, PLATFORM, environment, inventory, require, run, save, sha, tools_record, verify_historical
sys.path.insert(0,str(PLATFORM/'build-support/postgis'))
from acquisition import extract_input


def build(custody, native, output, jobs):
    require(1 <= jobs <= 6, 'Parallelism must be 1..6')
    require(not output.exists(), 'Fresh output required')
    require(native.is_dir() and not native.is_symlink(), 'Expected existing owned native prefix')
    historical=verify_historical(native)
    manifest=PLATFORM/'build-support/postgis/inputs.json'
    inputs=json.loads(manifest.read_text())['inputs']
    item=next(x for x in inputs if x['name']=='gdal')
    output.mkdir(parents=True)
    try:
        env=environment(output,native)
        save(output/'recipe.json',{'native_manifest_sha256':sha(manifest),'recipe_sha256':sha(Path(__file__)),
             'common_sha256':sha(HERE/'common.py'),'reason':'Native QGIS OGR/provider tests require CSV and GeoPackage; GEOS integration enables OGR geometry checks. Database prefix preserved.',
             'historical_authority':historical,'base_prefix':str(native),'base_inventory':inventory(native),'tools':tools_record(env)})
        prefix=output/'prefix'; builddir=output/'build'
        sqlite=extract_input(custody,output/'sources',next(x for x in inputs if x['name']=='sqlite'))
        sqlite_build=output/'sqlite-build'; sqlite_build.mkdir()
        run([sqlite/'configure',f'--prefix={prefix}','--enable-shared','--enable-rtree','--disable-readline','--soname=legacy',
             'CFLAGS=-O1 -DSQLITE_ENABLE_COLUMN_METADATA=1'],sqlite_build,env,output,'sqlite-configure')
        run(['make','-j'+str(jobs)],sqlite_build,env,output,'sqlite-compile')
        run(['make','install'],sqlite_build,env,output,'sqlite-stage')
        run([prefix/'bin/sqlite3',':memory:',
             'CREATE VIRTUAL TABLE bounds USING rtree(id,minx,maxx,miny,maxy); INSERT INTO bounds VALUES(1,0,2,0,2); SELECT count(*) FROM bounds WHERE minx<=1 AND maxx>=1;'],
            output,env,output,'sqlite-rtree')
        require((output/'sqlite-rtree.log').read_text().strip()=='1','SQLite RTree functional probe failed')
        env=environment(output,native,spatial=prefix)
        proj=extract_input(custody,output/'sources',next(x for x in inputs if x['name']=='proj'))
        proj_build=output/'proj-build'
        run(['cmake','-S',proj,'-B',proj_build,'-G','Ninja',
             '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_LIBDIR=lib','-DCMAKE_CXX_FLAGS_RELEASE=-O1 -DNDEBUG',
             '-DCMAKE_C_COMPILER=/usr/bin/gcc-15','-DCMAKE_CXX_COMPILER=/usr/bin/g++-15',
             f'-DCMAKE_PREFIX_PATH={prefix};{native}',f'-DCMAKE_INSTALL_PREFIX={prefix}',
             '-DCMAKE_INSTALL_LIBDIR=lib',f'-DCMAKE_INSTALL_RPATH={prefix}/lib;{native}/lib',
             '-DBUILD_SHARED_LIBS=ON','-DBUILD_TESTING=OFF','-DENABLE_CURL=ON',
             '-DENABLE_TIFF=ON','-DBUILD_PROJSYNC=OFF',
             f'-DSQLite3_INCLUDE_DIR={prefix}/include',f'-DSQLite3_LIBRARY={prefix}/lib/libsqlite3.so'],
            output,env,output,'proj-configure')
        run(['cmake','--build',proj_build,'--parallel',str(jobs)],output,env,output,'proj-compile')
        run(['cmake','--install',proj_build],output,env,output,'proj-stage')
        env['PROJ_DATA']=str(prefix/'share/proj')
        run([prefix/'bin/projinfo','-s','EPSG:4326','-t','EPSG:3857','--summary'],output,env,output,'proj-preflight')
        run(['readelf','-d',prefix/'lib/libproj.so'],output,env,output,'proj-needed')
        needed=(output/'proj-needed.log').read_text()
        require('libsqlite3.so.0' in needed and str(native/'lib/libsqlite3.so') not in needed,
                'PROJ must use selected SONAME SQLite, not absolute old SQLite')
        source=extract_input(custody,output/'sources',item)
        flags=['-DBUILD_SHARED_LIBS=ON','-DBUILD_TESTING=OFF',
               '-DGDAL_USE_EXTERNAL_LIBS=OFF','-DGDAL_USE_ZLIB=ON','-DGDAL_USE_TIFF=ON',
               '-DGDAL_USE_PNG=ON','-DGDAL_USE_JPEG=ON','-DGDAL_USE_GEOTIFF_INTERNAL=ON',
               '-DGDAL_BUILD_OPTIONAL_DRIVERS=OFF','-DOGR_BUILD_OPTIONAL_DRIVERS=OFF',
               '-DGDAL_ENABLE_DRIVER_GTIFF=ON','-DGDAL_ENABLE_DRIVER_PNG=ON',
               '-DGDAL_ENABLE_DRIVER_JPEG=ON','-DGDAL_ENABLE_DRIVER_RAW=ON',
               '-DGDAL_ENABLE_DRIVER_AAIGRID=ON','-DGDAL_ENABLE_DRIVER_DTED=ON',
               '-DOGR_ENABLE_DRIVER_SHAPE=ON','-DOGR_ENABLE_DRIVER_CSV=ON',
               '-DOGR_ENABLE_DRIVER_GPKG=ON','-DOGR_ENABLE_DRIVER_SQLITE=ON',
               '-DGDAL_USE_SQLITE3=ON','-DGDAL_USE_GEOS=ON',
               '-DBUILD_PYTHON_BINDINGS=OFF','-DBUILD_JAVA_BINDINGS=OFF',
               '-DBUILD_CSHARP_BINDINGS=OFF','-DGDAL_USE_CURL=OFF',
               '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF','-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF',
               '-DCMAKE_C_COMPILER=/usr/bin/gcc-15','-DCMAKE_CXX_COMPILER=/usr/bin/g++-15',
               '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_LIBDIR=lib','-DCMAKE_CXX_FLAGS_RELEASE=-O1 -DNDEBUG',
               '-DCMAKE_C_FLAGS_RELEASE=-O1 -DNDEBUG',f'-DCMAKE_EXE_LINKER_FLAGS=-Wl,-rpath-link,{prefix}/lib',f'-DCMAKE_PREFIX_PATH={prefix};{native}',
               f'-DCMAKE_INSTALL_RPATH={prefix}/lib;{native}/lib',f'-DCMAKE_INSTALL_PREFIX={prefix}',f'-DPROJ_DIR={prefix}/lib/cmake/proj']
        run(['cmake','-S',source,'-B',builddir,'-G','Ninja',*flags],output,env,output,'configure')
        run(['cmake','--build',builddir,'--parallel',str(jobs)],output,env,output,'compile')
        run(['cmake','--install',builddir],output,env,output,'stage')
        e=environment(output,native,spatial=prefix)
        run([prefix/'bin/ogrinfo','--formats'],output,e,output,'ogr-formats')
        run([prefix/'bin/gdalinfo','--formats'],output,e,output,'gdal-formats')
        formats=(output/'ogr-formats.log').read_text()
        for n in ('GPKG','SQLite','CSV','GeoJSON','ESRI Shapefile'):
            require(n in formats, 'Missing required native fixture driver '+n)
        require('GTiff' in (output/'gdal-formats.log').read_text(),'Missing GeoTIFF')
        from common import verify_inventory
        verify_inventory(native,json.loads((output/'recipe.json').read_text())['base_inventory'])
        save(output/'output-manifest.json',{'prefix':str(prefix),'files':inventory(prefix)})
        save(output/'success.json',{'state':'native-profile-built','manifest_sha256':sha(output/'output-manifest.json'),
             'test_scope':'driver preflight only; actual QGIS provider/native tests run separately',
             'python_bindings':'separate retained-source build required for selected PyQGIS native tests'})
    except Exception as e:
        save(output/'failure.json',{'type':type(e).__name__,'message':str(e)})
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--custody',type=Path,required=True); p.add_argument('--native',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--jobs',type=int,default=4)
    a=p.parse_args();build(a.custody.resolve(),a.native.resolve(),a.output.resolve(),a.jobs)
