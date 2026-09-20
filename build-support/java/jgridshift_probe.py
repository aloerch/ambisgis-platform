#!/usr/bin/env python3
"""Compile retained JGridShift 1.3 core and compare public API under socket denial.

This is an isolated source/API probe, without donor Maven lifecycle execution.
It does not prove binary equivalence, grid-correction accuracy, tests or release
acceptance. The selected historical upstream tree contains no core test sources.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import source_closure as sc
import toolchain

GAV='it.geosolutions.jgridshift:jgridshift-core:1.3'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--supplement',type=Path,required=True)
    p.add_argument('--frozen-maven',type=Path,required=True)
    p.add_argument('--toolchain-custody',type=Path,required=True)
    p.add_argument('--tools',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();output=args.output.absolute();output.mkdir(parents=True,exist_ok=False)
    result={'scope':'JGridShift recovered source compilation/public API probe','source_binary_correspondence_established':False,'product_acceptance':False,'native_tests':'not run; retained historical core tree has no test source files','stages':[]}
    try:
        manifest=sc.read_json(Path(__file__).with_name('source-closure-inputs.json'))
        source=manifest['artifacts'][GAV]['sources'][0]
        archive=sc.archive_members(sc.checked_blob(args.supplement.absolute(),source))
        tools_manifest=sc.read_json(Path(__file__).with_name('toolchain-inputs.json'))
        result['toolchain']=toolchain.verify_extracted(args.toolchain_custody,tools_manifest,args.tools)
        java=args.tools/next(x['root'] for x in tools_manifest['archives'] if x['role']=='distribution' and x['path'].startswith('OpenJDK'))
        paths=[]
        for name,data in archive.items():
            if '/core/src/main/java/' not in name or not name.endswith('.java'):continue
            target=output/'source'/name.split('/core/src/main/java/',1)[1];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);paths.append(target)
        if len(paths)!=4:raise ValueError('expected exact four core source files')
        result['source_archive']=source
        result['source_files']=[{'path':str(x.relative_to(output)),'sha256':sc.digest(x.read_bytes())} for x in sorted(paths)]
        result['core_test_sources']=[n for n in archive if '/core/src/test/' in n]
        triage=sc.read_json(Path(__file__).resolve().parents[2]/'plan/verification/java-resolution-source-gap-triage.json')
        binary_sha=next(x['binary_sha256'] for x in triage['gaps'] if x['gav']==GAV)
        binary=sc.read_file(args.frozen_maven.absolute()/'blobs/sha256'/binary_sha)
        if sc.digest(binary)!=binary_sha:raise ValueError('binary checksum differs')
        original=output/'original.jar';original.write_bytes(binary)
        (output/'classes').mkdir();(output/'home').mkdir();(output/'tmp').mkdir()
        runner=Path(__file__).resolve().parents[1]/'postgis/offline_exec.py'
        env={'PATH':str(java/'bin')+':/usr/bin:/bin','HOME':str(output/'home'),'TMPDIR':str(output/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
        def invoke(stage,cmd):
            argv=[sys.executable,str(runner),'--evidence',str(output/(stage+'-network.json')),'--',*map(str,cmd)]
            with (output/(stage+'.log')).open('xb') as log:
                run=subprocess.run(argv,cwd=output,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            result['stages'].append({'stage':stage,'command':argv,'exit_code':run.returncode,'log_sha256':sc.digest((output/(stage+'.log')).read_bytes())})
            network=sc.read_json(output/(stage+'-network.json'))
            probes={x['family']:x for x in network.get('probes',[]) if x.get('operation')=='socket(SOCK_STREAM)'}
            valid=(network.get('status')=='completed' and network.get('command_exit_code')==run.returncode
                   and all(probes.get(f,{}).get('passed') is True and probes[f].get('errno')==1
                           for f in ('AF_INET','AF_INET6')))
            result['stages'][-1]['network_receipt_verified']=valid
            if not valid:raise ValueError(stage+' network denial receipt invalid')
            if run.returncode:raise ValueError(stage+' failed')
        invoke('compile',[java/'bin/javac','-proc:none','-source','7','-target','7','-d',output/'classes',*sorted(paths)])
        names=['au.com.objectix.jgridshift.'+x.stem for x in sorted(paths)]
        invoke('original-api',[java/'bin/javap','-public','-classpath',original,*names])
        invoke('compiled-api',[java/'bin/javap','-public','-classpath',output/'classes',*names])
        after=[{'path':str(x.relative_to(output)),'sha256':sc.digest(x.read_bytes())} for x in sorted(paths)]
        result['source_files_unchanged']=after==result['source_files']
        if not result['source_files_unchanged']:raise ValueError('probe changed source bytes')
        result['public_api_equal']=(output/'original-api.log').read_bytes()==(output/'compiled-api.log').read_bytes()
        result['compiled_classes']=[{'path':str(x.relative_to(output)),'sha256':sc.digest(x.read_bytes())} for x in sorted((output/'classes').rglob('*.class'))]
        result['status']='passed' if result['public_api_equal'] else 'public-api-mismatch'
        code=0 if result['public_api_equal'] else 2
    except Exception as exc:
        result.update(status='failed',error=str(exc));code=1
    with (output/'result.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'output':str(output)}));return code

if __name__=='__main__':raise SystemExit(main())
