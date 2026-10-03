#!/usr/bin/env python3
"""Compile exact canonical client/MapStore sources with retained npm inputs."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from common import export_owned,git,inventory,sha

HERE=Path(__file__).resolve().parent;PLATFORM=HERE.parents[1]
SOURCES={
    'mapstore-client':{'commit':'a0d3f434cea69dadc93d35e13bc969b844aceea1',
                       'tree':'8055ca37333ee3037f63624f2e1d6ee548d416f1','repository_id':1376928013,
                       'gitlinks':{'geonode_mapstore_client/client/MapStore2':'88064efbf20ef0aaffebe357f7a99a1ab4fb23b8'}},
    'mapstore':{'commit':'88064efbf20ef0aaffebe357f7a99a1ab4fb23b8',
                'tree':'11b6eb8616b90c72570c4f3aad82212b52f1cdbe','repository_id':1376928043},
}


def write(path,data):path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')


def require_only_generated_changes(changes):
    allowed_files={'geonode_mapstore_client/client/version.txt',
                   'geonode_mapstore_client/static/mapstore/version.txt'}
    allowed_directories=('geonode_mapstore_client/client/dist/',
                         'geonode_mapstore_client/static/mapstore/dist/',
                         'geonode_mapstore_client/static/mapstore/ms-translations/')
    for component,rows in changes.items():
        for path in rows:
            if component!='mapstore-client' or not (path in allowed_files or path.startswith(allowed_directories)):
                raise ValueError('Frontend build modified original source outside generated outputs: '+component+'/'+path)


def main(args):
    spec=importlib.util.spec_from_file_location('retained_frontend_builder',PLATFORM/'build-support/frontend/build.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    helper.verify_reviewed_inputs(args.inputs)
    retained=json.loads((args.inputs/'manifest.json').read_text());helper.verify_inputs(args.inputs,retained)
    root=args.output.absolute();root.mkdir(parents=True,exist_ok=False)
    report={'task':'FND-08','started_at':datetime.now(timezone.utc).isoformat(),'result_exit_code':1,
            'source_selection':SOURCES,'full_fnd08_acceptance':False,
            'dependency_manifest_sha256':sha(args.inputs/'manifest.json'),
            'historical_source_bundles':'retained unchanged but not used to select or export successor source'}
    write(root/'started.json',report)
    try:
        if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
        client=root/'client';front=client/'geonode_mapstore_client/client'
        paths={'mapstore-client':client,'mapstore':front/'MapStore2'};sources={};preparation={}
        for name,path in paths.items():
            preparation[name]=export_owned(args.repos/name,SOURCES[name],path)
            sources[name]=inventory(path)
            # Exact exported blobs remain untouched. Git metadata exists solely
            # for inherited native version plugins; read-tree never checks out.
            git(path,'init','--quiet');git(path,'fetch','--quiet','--no-tags','--depth=1',str(args.repos/name),SOURCES[name]['commit'])
            git(path,'update-ref','--no-deref','HEAD',SOURCES[name]['commit']);git(path,'read-tree',SOURCES[name]['commit'])
        write(root/'source-inputs.json',sources);report['source_inputs_sha256']=sha(root/'source-inputs.json');report['preparation']=preparation
        if json.loads((front/'package.json').read_text())['devDependencies']['@mapstore/project']!='file:vendor/project.tar.gz':
            raise ValueError('Owned client lost selected local project archive')
        if json.loads((front/'MapStore2/package.json').read_text())['dependencies']['@mapstore/patcher']!='file:../vendor/patcher.tar.gz':
            raise ValueError('Owned MapStore lost selected local patcher archive')
        tooling=root/'tooling';tooling.mkdir()
        for source in (Path(__file__),HERE/'common.py',PLATFORM/'build-support/frontend/build.py',
                       PLATFORM/'build-support/frontend/inputs.json',PLATFORM/'build-support/frontend/dependency-lock.json',
                       PLATFORM/'build-support/postgis/offline_exec.py'):
            name='historical-build.py' if source.name=='build.py' else source.name;shutil.copyfile(source,tooling/name)
        write(root/'tooling-manifest.json',inventory(tooling));report['tooling_manifest_sha256']=sha(root/'tooling-manifest.json')
        home=root/'home';home.mkdir();tool=root/'toolchain';tool.mkdir()
        with tarfile.open(args.inputs/'node.tar.xz') as archive:archive.extractall(tool,filter='data')
        bindir=tool/'node-v24.18.1-linux-x64/bin'
        env={'PATH':str(bindir)+':/usr/bin:/bin','HOME':str(home),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
             'NODE_OPTIONS':'--max-old-space-size=8192','npm_config_cache':str(root/'npm-cache'),'npm_config_offline':'true',
             'npm_config_audit':'false','npm_config_fund':'false','npm_config_update_notifier':'false','CI':'true',
             'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_NO_REPLACE_OBJECTS':'1','GIT_ALLOW_PROTOCOL':'file',
             'SOURCE_DATE_EPOCH':'1790899200'}
        if subprocess.check_output([bindir/'node','--version'],env=env,text=True).strip()!='v24.18.1':raise ValueError('Node identity mismatch')
        shutil.copytree(args.inputs/'vendor',front/'vendor')
        shutil.copyfile(args.inputs/'package-lock.json',front/'package-lock.json')
        helper.validate_lock(json.loads((front/'package-lock.json').read_text()),front/'vendor')
        static=client/'geonode_mapstore_client/static/mapstore'
        for p in (front/'dist',static/'dist',static/'ms-translations'):
            if p.exists():shutil.rmtree(p)
        def run(command,name):helper.run(command,front,env,root,name,True)
        run(['npm','ci','--offline','--ignore-scripts','--no-audit','--no-fund'],'install')
        write(root/'lifecycle-inventory.json',helper.lifecycle_inventory(front))
        run(['node','MapStore2/utility/build/postInstall.js'],'mapstore-postinstall')
        run(['npm','run','compile'],'compile')
        for name in ('gn-map.js','gn-catalogue.js','gn-components.js','gn-dashboard.js','gn-document.js','gn-geostory.js'):
            if not (static/'dist/js'/name).is_file():raise ValueError('Missing actual native UI entry '+name)
        outputs=helper.inventory(static);write(root/'output-manifest.json',outputs);report['output_manifest_sha256']=sha(root/'output-manifest.json')
        report['source_changes']={name:{p:{'before':digest,'after':sha(paths[name]/p) if (paths[name]/p).is_file() else None}
            for p,digest in rows.items() if not (paths[name]/p).is_file() or sha(paths[name]/p)!=digest} for name,rows in sources.items()}
        require_only_generated_changes(report['source_changes'])
        helper.verify_inputs(args.inputs,retained);report['result_exit_code']=0
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)};raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();write(root/'result.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repos','inputs','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
