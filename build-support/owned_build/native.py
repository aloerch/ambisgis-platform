#!/usr/bin/env python3
"""Fresh exact owned PostgreSQL/PostGIS builds using retained support libraries."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from common import export_owned, inventory, inventory_digest, sha

HERE=Path(__file__).resolve().parent
PLATFORM=HERE.parents[1]
SOURCES={
    'postgresql':{'commit':'2ff1375b5dd8bf09d8cb0e795974528180fd75ca',
                  'tree':'598df31816bda464f5b904c0badbcb25bafcc4f1','repository_id':1376927644},
    'postgis':{'commit':'9816f82458db774e62906cfb2c4f01f8b262c862',
               'tree':'ee927efacdc5a00d698cab2da047ad2232d1f579','repository_id':1376927690},
}


def write(path,data):path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')


def require_unchanged_source(changes):
    if any(changes.values()):
        raise ValueError('Native build modified selected original source')


def installed_inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            if not p.resolve().is_relative_to(root.resolve()):raise ValueError('Installed symlink escapes prefix')
            result[p.relative_to(root).as_posix()]={'symlink':os.readlink(p)}
        elif p.is_file():result[p.relative_to(root).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
    return result


def main(args):
    root=args.output.absolute();root.mkdir(parents=True,exist_ok=False)
    report={'task':'FND-08','started_at':datetime.now(timezone.utc).isoformat(),
            'owned_sources':SOURCES,'result_exit_code':1,'full_fnd08_acceptance':False,
            'runner_sha256':sha(Path(__file__))}
    write(root/'started.json',report)
    tooling=root/'tooling';tooling.mkdir()
    for source in (Path(__file__),HERE/'common.py',PLATFORM/'build-support/postgis/build.py',
                   PLATFORM/'build-support/postgis/offline_exec.py',PLATFORM/'build-support/postgis/smoke.sql'):
        name='historical-build.py' if source.name=='build.py' else source.name
        shutil.copyfile(source,tooling/name)
    write(root/'tooling-manifest.json',inventory(tooling));report['tooling_manifest_sha256']=sha(root/'tooling-manifest.json')
    spec=importlib.util.spec_from_file_location('retained_native_builder',PLATFORM/'build-support/postgis/build.py')
    native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    manifest=json.loads((PLATFORM/'build-support/postgis/inputs.json').read_text())
    report['support_manifest_sha256']=sha(PLATFORM/'build-support/postgis/inputs.json')
    support=installed_inventory(args.support)
    write(root/'support-inputs.json',support);report['support_inputs_sha256']=sha(root/'support-inputs.json')
    builder=native.Builder(manifest,args.custody,root,args.jobs)
    try:
        sources={}
        for name,selection in SOURCES.items():
            sources[name]=root/'sources'/name
            export_owned(args.repos/name,selection,sources[name])
            builder.inputs[name]={'name':name,'owned_source':selection}
        source_inputs={name:inventory(path) for name,path in sources.items()}
        write(root/'source-inputs.json',source_inputs);report['source_inputs_sha256']=sha(root/'source-inputs.json')
        p=builder.prefix;s=args.support
        builder.env.update(PATH=f'{p}/bin:{s}/bin:/usr/bin:/bin',CPPFLAGS=f'-I{s}/include',
                           LDFLAGS=f'-L{s}/lib -Wl,-rpath,{p}/lib -Wl,-rpath,{s}/lib',
                           LD_LIBRARY_PATH=f'{p}/lib:{s}/lib',
                           PKG_CONFIG_LIBDIR=f'{s}/lib/pkgconfig:{s}/share/pkgconfig',
                           PROJ_DATA=str(s/'share/proj'),PROJ_LIB=str(s/'share/proj'),
                           SOURCE_DATE_EPOCH='1790899200')
        report['environment']=builder.env.copy()
        builder.component='postgresql'
        with tempfile.TemporaryDirectory(prefix='ag-own-pg-',dir='/tmp') as sockets:
            builder.env['PG_REGRESS_SOCK_DIR']=sockets
            build=root/'build/postgresql'
            builder.autotools(sources['postgresql'],build,['--without-readline','--with-libxml','--with-zlib'])
            for target in ('all','check','install'):
                builder.command(['make','-C',build/'contrib/fuzzystrmatch',f'-j{args.jobs}',target],build)
            builder.env.pop('PG_REGRESS_SOCK_DIR')
        actual=subprocess.check_output([p/'bin/pg_config','--bindir'],env=builder.env,text=True).strip()
        if actual!=str(p/'bin'):raise ValueError('PostgreSQL escaped new prefix')
        builder.component='postgis';source=sources['postgis'];build=root/'build/postgis';build.mkdir()
        builder.command(['./autogen.sh'],source)
        builder.command([source/'configure',f'--prefix={p}',f'--with-pgconfig={p}/bin/pg_config',
                         f'--with-geosconfig={s}/bin/geos-config',f'--with-gdalconfig={s}/bin/gdal-config',
                         f'--with-projdir={s}','--without-sfcgal','--without-gui','--without-address-standardizer'],build)
        config=(build/'postgis_config.h').read_text()
        for feature in ('HAVE_LIBJSON','HAVE_LIBPROTOBUF'):
            if not re.search(r'^#define '+feature+r' 1$',config,re.M):raise ValueError('Missing required PostGIS '+feature)
        for directory in ('liblwgeom/cunit','raster/test/cunit'):
            if not re.search(r'^CUNIT_LDFLAGS\s*=.*-lcunit',(build/directory/'Makefile').read_text(),re.M):
                raise ValueError('Required CUnit tests missing')
        builder.command(['make',f'-j{args.jobs}'],build)
        builder.command(['make','check-unit'],build)
        builder.command(['make','install'],build)
        builder.component='database-smoke'
        with tempfile.TemporaryDirectory(prefix='ag-own-db-',dir='/tmp') as sockets:
            data=root/'test-database';write(root/'TEST_DATABASE_OWNERSHIP.json',{'task':'FND-08','data':str(data),'disposable':True})
            builder.command([p/'bin/initdb','-D',data,'--no-locale','-E','UTF8','-A','trust'],root)
            try:
                builder.command([p/'bin/pg_ctl','-D',data,'-l',root/'database.log','-o',
                                 f"-k {sockets} -p 55486 -c listen_addresses=''",'-w','start'],root)
                base=[p/'bin/psql','-X','-v','ON_ERROR_STOP=1','-h',sockets,'-p','55486','-d','postgres']
                builder.command([*base,'-c','CREATE EXTENSION postgis; CREATE EXTENSION postgis_raster; CREATE EXTENSION postgis_topology;'],root)
                builder.command([*base,'-f',PLATFORM/'build-support/postgis/smoke.sql'],root)
                if 'AMBISGIS_COUNT|13' not in builder.last_log.read_text():raise ValueError('Real database smoke assertions incomplete')
                report['database_smoke_assertions']=13
            finally:
                if (data/'postmaster.pid').exists():
                    builder.command([p/'bin/pg_ctl','-D',data,'-m','fast','-w','stop'],root)
        outputs=installed_inventory(p);write(root/'output-manifest.json',outputs)
        report['output_manifest_sha256']=sha(root/'output-manifest.json')
        report['source_changes']={name:{path:{'before':digest,'after':sha(sources[name]/path) if (sources[name]/path).is_file() else None}
            for path,digest in entries.items() if not (sources[name]/path).is_file() or sha(sources[name]/path)!=digest}
            for name,entries in source_inputs.items()}
        require_unchanged_source(report['source_changes'])
        if installed_inventory(s)!=support:raise ValueError('Retained support prefix changed')
        report['result_exit_code']=0
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)}
        raise
    finally:
        builder.close();report['finished_at']=datetime.now(timezone.utc).isoformat();write(root/'result.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repos','custody','support','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--jobs',type=int,default=4);args=p.parse_args()
    if not 1<=args.jobs<=4:p.error('jobs must be 1..4')
    main(args)
