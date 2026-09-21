#!/usr/bin/env python3
"""Generate/compile matching GDAL Python bindings from the retained native source."""
import argparse
import json
import shutil
from pathlib import Path
import sys
from common import PLATFORM, HERE, environment, inventory, require, run, save, sha, verify_inventory, verify_selected
sys.path.insert(0,str(PLATFORM/'build-support/postgis'))
from acquisition import extract_input


METADATA = {'PKG-INFO','SOURCES.txt','dependency_links.txt','entry_points.txt',
            'not-zip-safe','requires.txt','top_level.txt'}


def check_source(before, after):
    originals={row['path']:row for row in before}
    actual={row['path']:row for row in after}
    require(all(actual.get(name)==row for name,row in originals.items()),
            'GDAL binding source changed')
    added=set(actual)-set(originals)
    permitted={'swig/python/gdal-utils/GDAL.egg-info/'+name for name in METADATA}
    require(added==permitted, 'Unexpected GDAL source additions')
    return [actual[name] for name in sorted(added)]


def build(custody,native,spatial,support,output):
    require(not output.exists(),'Fresh bindings output required')
    authority=verify_selected(native,spatial,support)
    item=next(x for x in json.loads((PLATFORM/'build-support/postgis/inputs.json').read_text())['inputs'] if x['name']=='gdal')
    original=json.loads((spatial.parent/'output-manifest.json').read_text());verify_inventory(spatial,original['files'])
    output.mkdir(parents=True)
    try:
        recipe=output/'recipe';recipe.mkdir()
        for source_path in (Path(__file__),HERE/'common.py',HERE/'profile-inputs.json',HERE/'source-inputs.json',HERE/'support-inputs.json',PLATFORM/'build-support/postgis/acquisition.py',PLATFORM/'build-support/postgis/offline_exec.py',spatial.parent/'configure-command.json'):
            shutil.copyfile(source_path,recipe/source_path.name)
        env=environment(output,native,support,spatial)
        swig=support/'usr/bin/swig'
        candidates=list((support/'usr/share').glob('swig*/swig.swg'))+list((support/'usr/share/swig').glob('*/swig.swg'))
        require(len(candidates)==1,'Expected exact retained SWIG support library')
        env['SWIG_LIB']=str(candidates[0].parent)
        require(swig.is_file(),'Missing retained SWIG')
        source=extract_input(custody,output/'sources',item);builddir=output/'build'
        source_before=inventory(source);save(output/'source-manifest.json',source_before)
        prior=json.loads((spatial.parent/'configure-command.json').read_text())['argv']
        flags=prior[prior.index('-G')+2:]
        flags=[f for f in flags if not f.startswith(('-DBUILD_PYTHON_BINDINGS=','-DCMAKE_INSTALL_PREFIX='))]
        flags += ['-DBUILD_PYTHON_BINDINGS=ON',f'-DCMAKE_INSTALL_PREFIX={output}/unused-stage',
                  '-DPython_EXECUTABLE=/usr/bin/python3.13',f'-DSWIG_EXECUTABLE={swig}',
                  f'-DSWIG_DIR={candidates[0].parent}']
        save(output/'recipe.json',{'selected_profile':authority,'source':item,'spatial_manifest_sha256':sha(spatial.parent/'output-manifest.json'),
             'executed_recipe':inventory(recipe),'recipe_sha256':sha(Path(__file__)),'swig_sha256':sha(swig),'swig_library':str(candidates[0].parent),
             'python':'/usr/bin/python3.13','scope':'generate wrappers and compile against the selected GDAL; no alternate native GDAL compilation'})
        run(['cmake','-S',source,'-B',builddir,'-G','Ninja',*flags],output,env,output,'configure')
        run(['cmake','--build',builddir,'--parallel','2','--target','python_generated_files'],output,env,output,'generate')
        source_py=builddir/'swig/python';dest=output/'python'
        run(['/usr/bin/python3.13','setup.py','build_py','--build-lib',dest],source_py,env,output,'python-stage')
        run(['/usr/bin/python3.13','setup.py','build_ext',f'--gdal-config={spatial}/bin/gdal-config',
             f'--include-dirs={spatial}/include',f'--library-dirs={spatial}/lib',
             '--parallel=2','--build-lib',dest],source_py,env,output,'compile')
        env['PYTHONPATH']=str(dest)+':'+env['PYTHONPATH']
        code='from osgeo import gdal,ogr,osr,gdal_array; import json,numpy; assert gdal.VersionInfo()=="3100300"; assert gdal.GetDriverByName("GTiff"); assert ogr.GetDriverByName("GPKG"); print(json.dumps({"gdal":gdal.__file__,"version":gdal.VersionInfo(),"numpy":numpy.__file__}))'
        run(['/usr/bin/python3.13','-c',code],output,env,output,'import-probe')
        verify_selected(native,spatial,support)
        save(output/'generated-source-metadata.json',check_source(source_before,inventory(source)))
        save(output/'output-manifest.json',{'prefix':str(dest),'files':inventory(dest)})
        save(output/'success.json',{'state':'bindings-built','manifest_sha256':sha(output/'output-manifest.json')})
    except Exception as e:
        save(output/'failure.json',{'type':type(e).__name__,'message':str(e)})
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('custody','native','spatial','support','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();build(a.custody.resolve(),a.native.resolve(),a.spatial.resolve(),a.support.resolve(),a.output.resolve())
