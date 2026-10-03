#!/usr/bin/env python3
"""Build exact owned Java successors from retained inputs; never reapply old patches.

This is a producer for FND-08, not a replacement for historical FND-02 receipts.
It cannot fetch packages, select mutable source refs, deploy or publish artifacts.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from resolution import command, execute, sha, write_json
from compatibility import materialize, test_reports, verify_network_receipt
import toolchain
import variant_inputs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = {
    'geotools': {'commit':'3363c3d4ae8adfe3ed2024c27f92ec63855093be',
                 'tree':'ebb65f687763ce40445eb02f6ce710dc1eaa1e00','repository_id':1376927869},
    'geoserver': {'commit':'fd2fe1dfcc78fa974bdb81673872879336312077',
                  'tree':'c12018e88493a351c60c370f2a43894701acf995','repository_id':1376927947},
    'geowebcache': {'commit':'b4e9a30c8e2be00b9aa87fb17324efa8e489ac22',
                    'tree':'8df655d13b9955776fe1532dfb27fac64612a772','repository_id':1376927892},
}
RECOVERY_SHA = 'eb0a50b8d6cafb2380ae66e1d09e708df84c808d61fd7965afcbc7a1f3de4789'
JAVA_INVENTORY = '3d6eff1f26df893465f314aa4e7ba219a48b92977fbf2233cea17730a47f1a2c'
VENDORS = ('geofence-132a1d16901b7039f974c8c30d7e7df042d8af4c',
           'mapfish-print-v2-da1f37cfc0d7a235cb2c0ec5677010495d9f664b')


def git_environment():
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_NO_REPLACE_OBJECTS='1',
               GIT_TERMINAL_PROMPT='0',GIT_ALLOW_PROTOCOL='file',GIT_OPTIONAL_LOCKS='0')
    return env


def git(repo,*args):
    return subprocess.check_output(['git','--no-replace-objects','-c','core.hooksPath=/dev/null',
                                     '-C',str(repo),*args],env=git_environment())


def inventory(root):
    result={}
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink():
            raise ValueError('Source symlink forbidden: '+str(p))
        if p.is_file():
            result[p.relative_to(root).as_posix()]=sha(p)
    return result


def inventory_digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def export_owned(repo, selection, destination):
    """Export every exact Git blob and mode, including export-ignore attributes."""
    commit=selection['commit']
    if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Source selection must be a full immutable commit')
    tree=git(repo,'rev-parse',commit+'^{tree}').decode().strip()
    if tree!=selection['tree']:
        raise ValueError('Owned source tree identity mismatch')
    entries=[]
    for record in git(repo,'ls-tree','-r','-z',commit).split(b'\0'):
        if not record: continue
        info,name=record.split(b'\t',1)
        mode,kind,oid=info.decode().split()
        name=name.decode();relative=PurePosixPath(name)
        if (kind!='blob' or mode not in ('100644','100755') or relative.is_absolute()
                or '..' in relative.parts or '\\' in name or '\n' in name):
            raise ValueError('Unsupported or unsafe selected Git entry: '+name)
        entries.append((name,mode,oid))
    destination.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryFile() as requests:
        requests.write(''.join(oid+'\n' for _,_,oid in entries).encode());requests.seek(0)
        process=subprocess.Popen(['git','--no-replace-objects','-C',str(repo),'cat-file','--batch'],
                                  stdin=requests,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  env=git_environment())
        try:
            for name,mode,oid in entries:
                header=process.stdout.readline().decode().split()
                if len(header)!=3 or header[:2]!=[oid,'blob']:
                    raise ValueError('Selected blob is unavailable: '+name)
                size=int(header[2]);data=process.stdout.read(size)
                if len(data)!=size or process.stdout.read(1)!=b'\n':
                    raise ValueError('Truncated Git blob')
                if hashlib.sha1(b'blob '+str(size).encode()+b'\0'+data).hexdigest()!=oid:
                    raise ValueError('Git blob identity mismatch')
                path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data);path.chmod(0o755 if mode=='100755' else 0o644)
            error=process.stderr.read()
            if process.wait()!=0: raise ValueError(error.decode(errors='replace'))
        finally:
            if process.poll() is None: process.kill();process.wait()
            process.stdout.close();process.stderr.close()
    return {**selection,'repository':str(repo),'files':len(entries),'tree_verified':True,
            'export_method':'exact blob bytes and executable modes; no attributes/patches/ref resolution'}


def prepare_sources(recovered, repos, destination):
    recipes=recovered/'recipes.json'
    if sha(recipes)!=RECOVERY_SHA:
        raise ValueError('Recovered source recipe identity mismatch')
    prior=recovered/'derived/java-source'
    old=inventory(prior)
    if len(old)!=39622 or inventory_digest(old)!=JAVA_INVENTORY:
        raise ValueError('Recovered Java source inventory mismatch')
    destination.mkdir(parents=True,exist_ok=False)
    evidence={}
    for name,selection in SOURCES.items():
        evidence[name]=export_owned(repos[name],selection,destination/name)
    for name in VENDORS:
        shutil.copytree(prior/name,destination/name)
    shutil.copyfile(prior/'pom.xml',destination/'pom.xml')
    copied={p:d for p,d in old.items() if p=='pom.xml' or p.split('/')[0] in VENDORS}
    actual=inventory(destination)
    if any(actual.get(p)!=d for p,d in copied.items()):
        raise ValueError('Recovered vendor/reactor copy changed')
    if any('target' in Path(p).parts for p in actual):
        raise ValueError('Selected source unexpectedly contains build output directory')
    return {'owned_roots':evidence,'class_b_files':len(copied),
            'class_b_inventory_sha256':inventory_digest(copied),
            'recovery_recipe_sha256':RECOVERY_SHA,'historical_inventory_sha256':JAVA_INVENTORY},actual


def artifact_origins(source):
    built=[{'path':p.relative_to(source).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
           for p in sorted(source.rglob('*')) if p.is_file() and p.parent.name=='target' and p.suffix in ('.jar','.war')]
    by_name={}
    for row in built: by_name.setdefault(Path(row['path']).name,set()).add(row['sha256'])
    wars=[p for p in source.rglob('*.war') if p.parent.name=='target']
    if len(wars)!=1: raise ValueError('Expected one owned aggregate WAR')
    matches=[]
    with zipfile.ZipFile(wars[0]) as z:
        for name in sorted(z.namelist()):
            filename=Path(name).name
            if name.startswith('WEB-INF/lib/') and filename.startswith(('gt-','gs-','gwc-','geowebcache-')) and filename.endswith('.jar'):
                digest=hashlib.sha256(z.read(name)).hexdigest()
                if digest not in by_name.get(filename,set()):
                    raise ValueError('Aggregate embeds a core jar not produced from selected source: '+filename)
                matches.append({'entry':name,'sha256':digest})
    for prefix in ('gt-','gs-','gwc-'):
        if not any(Path(r['entry']).name.startswith(prefix) for r in matches):
            raise ValueError('Missing owned aggregate family: '+prefix)
    return {'built':built,'war':str(wars[0]),'war_sha256':sha(wars[0]),'owned_embedded_jars':matches}


def build(args):
    output=args.output.absolute();output.mkdir(parents=True,exist_ok=False)
    report={'task':'FND-08','purpose':'new owned source producer','started_at':datetime.now(timezone.utc).isoformat(),
            'source_successor':SOURCES,'historical_receipts_modified':False,'full_fnd08_acceptance':False,
            'result_exit_code':1,'runner_sha256':sha(Path(__file__))}
    start=time.monotonic();write_json(output/'started.json',report)
    tooling=output/'tooling'
    for p in HERE.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.json','.patch','.java') and '__pycache__' not in p.parts:
            target=tooling/'build-support/java'/p.relative_to(HERE)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    target=tooling/'build-support/postgis/offline_exec.py';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'build-support/postgis/offline_exec.py',target)
    write_json(output/'tooling-manifest.json',inventory(tooling))
    report['tooling_manifest_sha256']=sha(output/'tooling-manifest.json')
    source=output/'work/source'
    try:
        (output/'work').mkdir();(output/'work/logs').mkdir();(output/'work/user').mkdir()
        (output/'work/empty-global-settings.xml').write_text('<settings/>\n')
        report['preparation'],originals=prepare_sources(args.recovered,{'geotools':args.geotools_repo,
            'geoserver':args.recovered/'repos/geoserver','geowebcache':args.recovered/'repos/geowebcache'},source)
        write_json(output/'source-inputs.json',originals)
        report['source_inputs_sha256']=sha(output/'source-inputs.json')
        tools=json.loads((HERE/'toolchain-inputs.json').read_text())
        report['toolchain']=toolchain.verify_extracted(args.toolchain_custody,tools,args.tools)
        report['toolchain_gaps']=tools['remaining_gaps']
        java=args.tools/'jdk-17.0.20.1+1';maven=args.tools/'apache-maven-3.9.16'
        rows=materialize(args.custody,output/'retained-repository',no_oracle=True)
        rows,report['variant_inputs']=variant_inputs.apply(output/'retained-repository',rows,HERE/'json-nojpeg2000-variant-inputs.json')
        write_json(output/'retained-inputs.json',rows);report['retained_inputs_sha256']=sha(output/'retained-inputs.json')
        settings=output/'settings.xml'
        settings.write_text('<settings><mirrors><mirror><id>ambisgis-custody</id><mirrorOf>*</mirrorOf><url>'+
                            (output/'retained-repository').as_uri()+'</url></mirror></mirrors></settings>\n')
        local=output/'fresh-m2';local.mkdir()
        cmd,env=command(output/'work',java,maven,'dependencies',local,settings,output.name,role_service=True)
        cmd=cmd[:cmd.index('-pl')]+['-pl','org.geoserver.web:gs-web-app','-am','package',
            '-Dspotless.check.skip=true','-DskipTests=true','-Dmaven.test.failure.ignore=false',
            '-Dallow.test.failure.ignore=false','-Dproject.build.outputTimestamp=2026-10-02T00:00:00Z']
        # Both source and Maven state are fresh. No user/global Maven settings or cache is consulted.
        env['SOURCE_DATE_EPOCH']='1790899200'
        offline=ROOT/'build-support/postgis/offline_exec.py'
        wrapped=[sys.executable,str(offline),'--evidence',str(output/'network-denial.json'),'--',*cmd]
        report.update(command=wrapped,environment=env)
        with (output/'maven.log').open('x') as log:
            report['build_exit_code']=execute(wrapped,source,env,log,args.timeout)
        report['network']=verify_network_receipt(output/'network-denial.json',report['build_exit_code'])
        report['source_files_unchanged']=all((source/p).is_file() and sha(source/p)==digest for p,digest in originals.items())
        if report['build_exit_code'] or not report['source_files_unchanged']:
            raise ValueError('Owned aggregate build failed or changed original source')
        report['artifacts']=artifact_origins(source)
        report['native_execution']=native_tests(output,java,maven,args.timeout)
        report['native_tests']=test_reports(source)
        report['native_tests_pending']=False
        report['source_files_unchanged']=all((source/p).is_file() and sha(source/p)==digest for p,digest in originals.items())
        if not report['source_files_unchanged']:
            raise ValueError('Native tests changed selected original source')
        report['result_exit_code']=0
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)}
    finally:
        report['duration_seconds']=time.monotonic()-start
        write_json(output/'result.json',report)
    print(json.dumps({k:report.get(k) for k in ('result_exit_code','duration_seconds','error','build_exit_code')}),flush=True)
    return report['result_exit_code']


def native_tests(output,java,maven,timeout):
    """Execute inherited referencing cases from these newly compiled sources."""
    selector='%regex[org/geotools/referencing/.*Test.class],!%regex[.*OnlineTest.class],!%regex[.*StressTest.class]'
    cmd,env=command(output/'work',java,maven,'dependencies',output/'fresh-m2',output/'settings.xml',output.name,role_service=True)
    cmd=cmd[:cmd.index('-pl')]+['-pl','org.geotools:gt-referencing','-am','test',
        '-Dspotless.check.skip=true','-Dmaven.test.failure.ignore=false','-Dallow.test.failure.ignore=false',
        '-Dtest='+selector,'-Dsurefire.failIfNoSpecifiedTests=false']
    offline=output/'tooling/build-support/postgis/offline_exec.py'
    wrapped=[sys.executable,str(offline),'--evidence',str(output/'native-network-denial.json'),'--',*cmd]
    with (output/'native-tests.log').open('x') as log:
        status=execute(wrapped,output/'work/source',env,log,timeout)
    network=verify_network_receipt(output/'native-network-denial.json',status)
    native=test_reports(output/'work/source')
    if status or native['failures'] or native['errors'] or native['passed']<=0:
        raise ValueError('New-source native referencing tests failed or did not execute')
    return {'command':wrapped,'selector':selector,'network':network,'counts':{k:native[k] for k in ('tests','passed','failures','errors','skipped')},
            'limits':'Referencing cases only; Online/Stress and reported skips are not product acceptance.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('recovered','geotools-repo','custody','toolchain-custody','tools','output'):
        p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--timeout',type=int,default=7200)
    return build(p.parse_args())


if __name__=='__main__':
    raise SystemExit(main())
