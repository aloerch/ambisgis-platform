#!/usr/bin/env python3
"""Fresh owned QGIS desktop/server/bindings configure, compile and private stage.

Use retained exact source and supporting development inputs. Every build command
runs under the existing non-Internet-socket runner. This is not hostile-code
isolation, a distribution installer or acceptance of runtime/native tests.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from common import COMMIT, HERE, PLATFORM, environment, inventory, require, run, save, sha, tools_record, verify_inventory, verify_historical, verify_selected, verify_xml
sys.path.insert(0,str(PLATFORM/'build-support/postgis'))
from acquisition import extract_input

REQUIRED = {'WITH_DESKTOP':'ON','WITH_GUI':'ON','WITH_CORE':'ON','WITH_SERVER':'ON',
    'WITH_PYTHON':'ON','WITH_BINDINGS':'ON','WITH_ANALYSIS':'ON','WITH_POSTGRESQL':'ON',
    'WITH_SPATIALITE':'ON','WITH_AUTH':'ON','WITH_OAUTH2_PLUGIN':'ON','WITH_GSL':'ON',
    'WITH_SERVER_PLUGINS':'ON','WITH_QGIS_PROCESS':'ON','WITH_QTPRINTER':'ON',
    'ENABLE_TESTS':'ON','ENABLE_PGTEST':'ON','BUILD_WITH_QT6':'OFF','WITH_VCPKG':'OFF',
    'BINDINGS_GLOBAL_INSTALL':'OFF','SIP_GLOBAL_INSTALL':'OFF','USE_CCACHE':'OFF',
    'WITH_3D':'OFF','WITH_GRASS7':'OFF','WITH_GRASS8':'OFF',
    'WITH_QTWEBKIT':'OFF','WITH_QTWEBENGINE':'OFF','WITH_PDAL':'OFF','WITH_DRACO':'OFF',
    'WITH_EPT':'ON','WITH_COPC':'ON','WITH_INTERNAL_LAZPERF':'ON','WITH_ORACLE':'OFF','WITH_HANA':'OFF',
    'WITH_QUICK':'OFF','WITH_QTGAMEPAD':'OFF','WITH_CRASH_HANDLER':'OFF','USE_OPENCL':'OFF',
    'WITH_QTSERIALPORT':'ON','WITH_QSCIAPI':'OFF','WITH_PY_COMPILE':'OFF',
    'WITH_INTERNAL_SPATIALINDEX':'ON','WITH_INTERNAL_POLY2TRI':'ON',
    'WITH_INTERNAL_MDAL':'ON','WITH_INTERNAL_O2':'ON','WITH_INTERNAL_NLOHMANN_JSON':'ON',
    'WITH_SERVER_LANDINGPAGE_WEBAPP':'OFF','ENABLE_LOCAL_BUILD_SHORTCUTS':'OFF'}
TARGETS=['src/all','python/all','images/all','resources/all','i18n/all','doc/all','version','qgis_bench']
TEST_TARGETS=['test_core_coordinatetransform','test_core_project','test_core_ogrprovider',
    'test_core_gdalprovider','test_provider_postgresprovider','test_server_serverquerystringparameter']


GENERATED_SOURCE = 'python/plugins/grassprovider/description/algorithms.json'
GENERATOR_IDENTITIES = {
    'python/plugins/grassprovider/description_to_json.py': 'cabd076a4604962e01e48725adc5ffebee0416c090602c8de8e02ffb61b1fa88',
    'python/plugins/grassprovider/parsed_description.py': '0ab8694202882791135fd26204e107603b19ca92839bb8aaa65fd9a06a6e2ce0',
    'python/plugins/grassprovider/__init__.py': 'ce575c1d315b8eedf2dce5b54e9bbd6e306ef6343cd752d687f65a9a70338f47',
    'python/plugins/grassprovider/CMakeLists.txt': 'a6f203d79cccf418e5409ac8f32a343f0adc1ee0d9f200a022ef60eb6b13e55f',
}


def verify_source_delta(source, before):
    """Preserve every donor byte; permit only its pinned configure generator output."""
    expected = {row['path']: row for row in before}
    require(len(expected) == len(before) and GENERATED_SOURCE not in expected,
            'Invalid original source inventory')
    actual = {row['path']: row for row in inventory(source)}
    require(all(actual.get(path) == row for path, row in expected.items()),
            'Original source file changed or disappeared')
    require(set(actual) - set(expected) == {GENERATED_SOURCE},
            'Unexpected generated source files')
    for path, digest in GENERATOR_IDENTITIES.items():
        require(path in expected and expected[path].get('sha256') == digest,
                'Unreviewed inherited generator identity: ' + path)
    generated = actual[GENERATED_SOURCE]
    require('sha256' in generated and not (source / GENERATED_SOURCE).is_symlink(),
            'Generated metadata must be a regular file')
    data = json.loads((source / GENERATED_SOURCE).read_text())
    require(isinstance(data, list) and len(data) == 307
            and all(isinstance(row, dict) and isinstance(row.get('name'), str) for row in data),
            'Unexpected GRASS metadata structure')
    return {'original_files_verified': len(before), 'added': [generated],
            'generator_identities': GENERATOR_IDENTITIES, 'record_count': len(data)}


def reproduce_generated_source(source, before, prefix, env, output):
    result = verify_source_delta(source, before)
    reproduced = output / 'regenerated-grass-algorithms.json'
    run(['/usr/bin/python3.13', '-B', '-m', 'grassprovider.description_to_json',
         source / 'python/plugins/grassprovider/description', reproduced],
        source / 'python/plugins', env, output, 'generated-source-reproduce')
    generated = source / GENERATED_SOURCE
    require(sha(reproduced) == sha(generated), 'Independent generated metadata differs')
    installed = prefix / 'share/qgis/python/plugins/grassprovider/description/algorithms.json'
    require(installed.is_file() and not installed.is_symlink()
            and sha(installed) == sha(generated), 'Staged generated metadata differs')
    require(verify_source_delta(source, before) == result,
            'Source changed during independent metadata reproduction')
    result['reproduced_sha256'] = sha(reproduced)
    result['installed_sha256'] = sha(installed)
    save(output / 'generated-source-manifest.json', result)
    return result


def cache_entries(path):
    result={}
    for line in path.read_text().splitlines():
        if line.startswith(('#','//')) or '=' not in line or ':' not in line.split('=',1)[0]:continue
        left,value=line.split('=',1);key,kind=left.split(':',1);result[key]=(kind,value)
    return result


def check_config(cache, native, spatial, support, xml):
    for key,value in REQUIRED.items():
        require(key in cache and cache[key][1].upper() in ({'ON','TRUE','1'} if value=='ON' else {'OFF','FALSE','0'}), 'Required profile mismatch: '+key)
    require(cache['CMAKE_INSTALL_PREFIX'][1] not in ('/usr','/usr/local'), 'Private stage required')
    require(cache['Python_EXECUTABLE'][1]=='/usr/bin/python3.13','Wrong Python executable')
    require(cache['SHA'][1]==COMMIT,'Missing owned source version')
    # Explicit discovery pins prevent a matching label from accepting host QGIS's spatial ABI.
    for key,root in [('GDAL_DIR',spatial),('GEOS_DIR',native),('PROJ_DIR',spatial),
                     ('PostgreSQL_LIBRARY_RELEASE',native),('Qt5_DIR',support),
                     ('FCGI_INCLUDE_DIR',support),('FCGI_LIBRARY',support),('QWT_INCLUDE_DIR',support),
                     ('QWT_LIBRARY',support),('LIBXML2_LIBRARY',xml),('LIBXML2_INCLUDE_DIR',xml),
                     ('pkgcfg_lib_PC_SPATIALITE_xml2',xml),('ZSTD_LIBRARY',support),('ZSTD_INCLUDE_DIR',support),('SQLite3_LIBRARY',spatial),
                     ('pkgcfg_lib_PC_SPATIALITE_spatialite',support),
                     ('pkgcfg_lib_PC_SPATIALITE_sqlite3',spatial),('pkgcfg_lib_PC_SPATIALITE_z',native)]:
        require(key in cache and Path(cache[key][1]).resolve().is_relative_to(root.resolve()),'Unexpected dependency origin: '+key)


def build(output,native,spatial,support,support_inventory,jobs,xml=None):
    require(1<=jobs<=6,'Parallelism must be 1..6')
    require(not output.exists(),'Fresh output directory required')
    authority=verify_selected(native,spatial,support,support_inventory)
    xml_authority=verify_xml(xml)
    historical=authority["historical_authority"]
    spec=json.loads((HERE/'source-inputs.json').read_text())
    require(spec['repository']=='aloerch/ambisgis-qgis' and spec['repository_id']==1376927721 and spec['commit']==COMMIT,'Wrong owned source authority')
    archive=Path(spec['archive']['path'])
    require(archive.is_file() and not archive.is_symlink() and archive.stat().st_size==spec['archive']['bytes'] and sha(archive)==spec['archive']['sha256'],'Owned archive changed')
    # Prefix snapshots are generated by the corresponding acquisition/native recipe,
    # then hash-bound into this immutable attempt before any inherited build executes.
    support_rows=json.loads(support_inventory.read_text())
    if isinstance(support_rows,dict): support_rows=support_rows['files']
    verify_inventory(support,support_rows)
    spatial_manifest=spatial.parent/'output-manifest.json'
    spatial_doc=json.loads(spatial_manifest.read_text());verify_inventory(spatial,spatial_doc['files'])
    output.mkdir(parents=True)
    try:
        env=environment(output,native,support,spatial,xml)
        recipe=output/'recipe';recipe.mkdir()
        for p in (HERE/'build.py',HERE/'common.py',HERE/'source-inputs.json',HERE/'profile-inputs.json',HERE/'support-inputs.json',PLATFORM/'build-support/postgis/offline_exec.py',PLATFORM/'build-support/postgis/acquisition.py'):
            shutil.copyfile(p,recipe/p.name)
        save(output/'receipt.json',{'state':'started','commit':COMMIT,'specification_sha256':sha(HERE/'source-inputs.json'),
             'support_inventory_sha256':sha(support_inventory),'spatial_manifest_sha256':sha(spatial_manifest),
             'support_prefix':str(support),'spatial_prefix':str(spatial),'native_prefix':str(native),
             'selected_profile':authority,'xml_profile':xml_authority,'historical_authority':historical,'base_inventory':inventory(native),'recipe':inventory(recipe),'tools':tools_record(env),'jobs':jobs})
        item={'artifact':archive.name,'archive_root':spec['archive']['root'],'bytes':spec['archive']['bytes'],'sha256':spec['archive']['sha256']}
        source=extract_input(archive.parent,output/'sources',item)
        before=inventory(source);save(output/'source-manifest.json',before)
        prefix=output/'prefix';builddir=output/'build';usr=support/'usr'
        flags=[f'-D{k}={v}' for k,v in REQUIRED.items()]
        flags += [f'-DSHA={COMMIT}','-DCMAKE_BUILD_TYPE=Release',f'-DCMAKE_C_FLAGS=-isystem {usr}/include',
            f'-DCMAKE_CXX_FLAGS=-isystem {usr}/include','-DCMAKE_C_FLAGS_RELEASE=-O1 -DNDEBUG',
            '-DCMAKE_CXX_FLAGS_RELEASE=-O1 -DNDEBUG','-DCMAKE_C_COMPILER=/usr/bin/gcc-15','-DCMAKE_CXX_COMPILER=/usr/bin/g++-15',
            '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF','-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF',
            '-DPython_EXECUTABLE=/usr/bin/python3.13',f'-DCMAKE_PREFIX_PATH={xml};{spatial};{native};{usr}',
            f'-DSIP_BUILD_EXECUTABLE={usr}/bin/sip-build-3.13',
            f'-DFCGI_INCLUDE_DIR={usr}/include/fastcgi',f'-DFCGI_LIBRARY={usr}/lib64/libfcgi.so',
            f'-DZSTD_INCLUDE_DIR={usr}/include',f'-DZSTD_LIBRARY={usr}/lib64/libzstd.so',
            f'-DQWT_INCLUDE_DIR={usr}/include/qt5/qwt6',f'-DQWT_LIBRARY={usr}/lib64/libqwt-qt5.so',
            f'-Dpkgcfg_lib_PC_SPATIALITE_z={native}/lib/libz.so',
            f'-DLIBXML2_LIBRARY={xml}/lib/libxml2.so',f'-DLIBXML2_INCLUDE_DIR={xml}/include/libxml2',
            f'-Dpkgcfg_lib_PC_SPATIALITE_xml2={xml}/lib/libxml2.so',f'-DQt5_DIR={usr}/lib64/cmake/Qt5',f'-DGDAL_DIR={spatial}/lib/cmake/gdal',
            f'-DGEOS_DIR={native}/lib/cmake/GEOS',f'-DPROJ_DIR={spatial}/lib/cmake/proj',
            f'-DPostgreSQL_LIBRARY_RELEASE={native}/lib/libpq.so',f'-DPostgreSQL_INCLUDE_DIR={native}/include',
            f'-DPostgreSQL_TYPE_INCLUDE_DIR={native}/include/postgresql/server',f'-DSQLite3_INCLUDE_DIR={spatial}/include',
            f'-DSQLite3_LIBRARY={spatial}/lib/libsqlite3.so',f'-DQT_PLUGINS_DIR={usr}/lib64/qt5/plugins',
            f'-DCMAKE_INSTALL_PREFIX={prefix}',f'-DCMAKE_INSTALL_RPATH={prefix}/lib;{xml}/lib;{spatial}/lib;{native}/lib;{usr}/lib64',
            f'-DCMAKE_EXE_LINKER_FLAGS=-Wl,-rpath-link,{xml}/lib,-rpath-link,{spatial}/lib','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON']
        run(['cmake','-S',source,'-B',builddir,'-G','Ninja',*flags],output,env,output,'configure')
        cache=cache_entries(builddir/'CMakeCache.txt');check_config(cache,native,spatial,support,xml)
        save(output/'configuration.json',{'flags':flags,'cache':cache,'source':str(source),'build':str(builddir),'prefix':str(prefix)})
        target_text=subprocess.check_output(['ninja','-C',str(builddir),'-t','targets','all'],text=True,env=env)
        (output/'targets.txt').write_text(target_text)
        for t in TARGETS+TEST_TARGETS:require(t+':' in target_text,'Expected actual native target absent: '+t)
        # Tests remain configured and selected executable targets are built below;
        # only generated production subdirectory targets are requested here.
        run(['cmake','--build',builddir,'--parallel',jobs,'--target',*TARGETS],output,env,output,'compile')
        run(['cmake','--install',builddir],output,env,output,'stage')
        require(not any(x in (output/'stage.log').read_text() for x in ('CRSs synchronization not possible','CRSs could not be updated')),
                'Inherited crssync reported a failure despite installer exit status')
        stage_env=env.copy();stage_env['QGIS_PREFIX_PATH']=str(prefix)
        stage_env['PYTHONPATH']=str(prefix/'share/qgis/python')+':'+env['PYTHONPATH']
        stage_env['LD_LIBRARY_PATH']=str(prefix/'lib')+':'+env['LD_LIBRARY_PATH']
        check='from qgis.core import QgsApplication,QgsCoordinateReferenceSystem; a=QgsApplication([],False); QgsApplication.setPrefixPath('+repr(str(prefix))+',True); a.initQgis(); result=QgsCoordinateReferenceSystem.syncDatabase(); print(\"staged_crs_sync\",result,QgsApplication.srsDatabaseFilePath()); assert result>=0; a.exitQgis()'
        run(['/usr/bin/python3.13','-c',check],output,stage_env,output,'staged-crs-sync')
        run(['cmake','--build',builddir,'--parallel',jobs,'--target',*TEST_TARGETS],output,env,output,'native-test-compile')
        for p in ('bin/qgis','bin/qgis_mapserv.fcgi','bin/qgis_mapserver','lib/libqgis_core.so','lib/libqgis_gui.so','lib/libqgis_server.so',
                  'share/qgis/python/qgis/_core.so','share/qgis/python/qgis/_gui.so','share/qgis/python/qgis/_server.so'):
            require((prefix/p).is_file(),'Missing staged artifact '+p)
        run(['ldd',prefix/'bin/qgis'],output,env,output,'desktop-linkage')
        run(['ldd',prefix/'bin/qgis_mapserver'],output,env,output,'server-linkage')
        for n in ('desktop-linkage','server-linkage'): require('not found' not in (output/(n+'.log')).read_text(),'Missing staged library')
        reproduce_generated_source(source,before,prefix,env,output)
        verify_xml(xml)
        verify_inventory(support,support_rows)
        verify_inventory(spatial,spatial_doc['files'])
        verify_inventory(native,json.loads((output/'receipt.json').read_text())['base_inventory'])
        save(output/'output-manifest.json',{'prefix':str(prefix),'files':inventory(prefix),'source_commit':COMMIT,
             'generated_version_sha256':sha(builddir/'qgsversion.h'),'configuration_sha256':sha(output/'configuration.json')})
        save(output/'success.json',{'state':'compiled-staged','manifest_sha256':sha(output/'output-manifest.json'),
            'acceptance':'Runtime and native assertions remain separate gates; build alone is partial F02-04'})
    except Exception as e:
        save(output/'failure.json',{'type':type(e).__name__,'message':str(e)})
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('output','native','spatial','support','support-inventory','xml'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--jobs',type=int,default=4);a=p.parse_args()
    build(a.output.resolve(),a.native.resolve(),a.spatial.resolve(),a.support.resolve(),a.support_inventory.resolve(),a.jobs,a.xml.resolve())
