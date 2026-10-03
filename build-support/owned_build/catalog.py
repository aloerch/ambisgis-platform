#!/usr/bin/env python3
"""Build canonical owned catalog wheels and the selected first-party policy source."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import zipfile

from common import export_owned,git,inventory,sha

HERE=Path(__file__).resolve().parent;PLATFORM=HERE.parents[1]
PLATFORM_COMMIT='0876999d7535d792d0024586981c762b2f9bf513'
SOURCES={
    'geonode':{'commit':'2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4',
               'tree':'f8fda01733dae258e319df14f42677cf3bd83e20','repository_id':1376927978},
    'mapstore-client':{'commit':'a0d3f434cea69dadc93d35e13bc969b844aceea1',
                       'tree':'8055ca37333ee3037f63624f2e1d6ee548d416f1','repository_id':1376928013,
                       'gitlinks':{'geonode_mapstore_client/client/MapStore2':'88064efbf20ef0aaffebe357f7a99a1ab4fb23b8'}},
}


def write(path,data):path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')


def main(args):
    if sys.version_info[:2]!=(3,12):raise ValueError('Selected catalog interpreter requires Python 3.12')
    root=args.output.absolute();root.mkdir(parents=True,exist_ok=False)
    report={'task':'FND-08','started_at':datetime.now(timezone.utc).isoformat(),'result_exit_code':1,
            'source_selection':SOURCES,'platform_source':PLATFORM_COMMIT,'full_fnd08_acceptance':False}
    write(root/'started.json',report)
    spec=importlib.util.spec_from_file_location('retained_catalog_inputs',PLATFORM/'build-support/geonode/inputs.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    try:
        manifest=json.loads((args.custody/'manifest.json').read_text());helper.verify_manifest(args.custody,manifest)
        report['dependency_manifest_sha256']=sha(args.custody/'manifest.json')
        sources={name:root/'sources'/name for name in SOURCES}
        report['preparation']={name:export_owned(args.repos/name,SOURCES[name],path) for name,path in sources.items()}
        source_inputs={name:inventory(path) for name,path in sources.items()}
        write(root/'source-inputs.json',source_inputs);report['source_inputs_sha256']=sha(root/'source-inputs.json')
        tooling=root/'tooling';tooling.mkdir()
        for source in (Path(__file__),HERE/'common.py',PLATFORM/'build-support/geonode/inputs.py',PLATFORM/'build-support/postgis/offline_exec.py'):
            shutil.copyfile(source,tooling/source.name)
        write(root/'tooling-manifest.json',inventory(tooling));report['tooling_manifest_sha256']=sha(root/'tooling-manifest.json')
        home=root/'home';home.mkdir();cache=root/'pip-cache';cache.mkdir()
        support=args.support
        support_inputs={p.relative_to(support).as_posix():({'symlink':os.readlink(p)} if p.is_symlink() else {'sha256':sha(p)})
                        for p in sorted(support.rglob('*')) if p.is_file() or p.is_symlink()}
        write(root/'support-inputs.json',support_inputs);report['support_inputs_sha256']=sha(root/'support-inputs.json')
        env={'PATH':f'{support}/bin:/usr/bin:/bin','HOME':str(home),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
             'PYTHONNOUSERSITE':'1','PIP_CONFIG_FILE':'/dev/null','PIP_DISABLE_PIP_VERSION_CHECK':'1',
             'PIP_NO_INDEX':'1','PIP_NO_CACHE_DIR':'1','PIP_CACHE_DIR':str(cache),'PIP_FIND_LINKS':str(args.custody/'wheels'),
             'LD_LIBRARY_PATH':str(support/'lib'),'GDAL_CONFIG':str(support/'bin/gdal-config'),
             'GDAL_DATA':str(support/'share/gdal'),'PROJ_DATA':str(support/'share/proj'),'PROJ_NETWORK':'OFF',
             'SOURCE_DATE_EPOCH':'1790899200'}
        log=root/'build.log'
        def run(argv):helper.run(argv,log=log,env=env,cwd=root)
        venv=root/'venv';py=venv/'bin/python'
        run([sys.executable,'-m','venv','--without-pip',venv])
        run([sys.executable,'-m','pip','--python',py,'install','--no-index','--find-links',args.custody/'wheels',
             '-r',args.custody/'bootstrap-requirements.txt'])
        artifacts=root/'artifacts';artifacts.mkdir()
        for path in sources.values():
            run([py,'-m','pip','wheel','--no-index','--no-deps','--no-build-isolation','--wheel-dir',artifacts,path])
        inventory_doc=json.loads((args.custody/'python-components.json').read_text())
        lines=[c['name']+'=='+c['version']+' --hash=sha256:'+c['sha256'] for c in inventory_doc['components']
               if c['name'].lower().replace('_','-') not in {'geonode','django-geonode-mapstore-client'}]
        lock=root/'requirements.lock';lock.write_text('\n'.join(sorted(lines))+'\n')
        run([py,'-m','pip','install','--no-index','--no-deps','--require-hashes','--find-links',args.custody/'wheels','-r',lock])
        wheels=list(artifacts.glob('*.whl'))
        if {p.name for p in wheels}!=set(helper.OWNED_WHEELS.values()):raise ValueError('Unexpected owned wheel membership')
        for wheel in wheels:run([py,'-m','pip','install','--no-index','--no-deps',wheel])
        run([py,'-m','pip','check'])
        run([py,'-c','from osgeo import gdal; import geonode, geonode_mapstore_client; assert gdal.VersionInfo()=="3100300"; print(geonode.__file__); print(geonode_mapstore_client.__file__)'])
        # The first-party authority is pure Python; compile exact selected source
        # into a deterministic source/bytecode capsule, not a fabricated wheel.
        policy=root/'policy/ambisgis_policy';policy.mkdir(parents=True)
        prefix='services/control-plane/ambisgis_policy/'
        rows=git(PLATFORM,'ls-tree','-r','--name-only',PLATFORM_COMMIT,'--',prefix).decode().splitlines()
        policy_inputs={}
        for path in rows:
            target=policy/Path(path).name;target.write_bytes(git(PLATFORM,'show',PLATFORM_COMMIT+':'+path));policy_inputs[path]=sha(target)
            if target.suffix=='.py':
                py_compile.compile(str(target),cfile=str(target)+'.pyc',dfile='ambisgis_policy/'+target.name,
                                   doraise=True,invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        with zipfile.ZipFile(artifacts/'ambisgis-policy-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(policy.iterdir()):
                entry=zipfile.ZipInfo('ambisgis_policy/'+path.name,date_time=(2026,10,2,0,0,0));entry.external_attr=0o100644<<16
                archive.writestr(entry,path.read_bytes())
        env['PYTHONPATH']=str(policy.parent)
        run([py,'-c','import ambisgis_policy.catalog, ambisgis_policy.gateway; print("owned policy import passed")'])
        report['policy_source_files']=policy_inputs
        report['source_unchanged']=all(sha(sources[name]/path)==digest for name,rows in source_inputs.items() for path,digest in rows.items())
        if not report['source_unchanged']:raise ValueError('Wheel build modified selected original source')
        write(root/'output-manifest.json',inventory(artifacts));report['output_manifest_sha256']=sha(root/'output-manifest.json')
        report['result_exit_code']=0;report['pip_check']='passed';report['native_imports']='passed'
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)}
        raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();write(root/'result.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repos','custody','support','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
