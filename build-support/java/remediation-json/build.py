#!/usr/bin/env python3
"""Build the independently authored selected-profile JSON compatibility artifact."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=a.workspace_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    result={'schema_version':1,'status':'failed','recipe_sha256':sha(Path(__file__)),'commands':[],'replacements':[]}
    try:
        inputs=json.loads((HERE/'inputs.json').read_text());result['inputs_sha256']=sha(HERE/'inputs.json')
        for entry in inputs['inputs'].values():
            if sha(root/entry['path'])!=entry['sha256']:raise ValueError('Input differs: '+entry['path'])
        jdk=root/inputs['jdk']
        sys.path.insert(0,str(HERE.parent));import toolchain
        result['toolchain']=toolchain.verify_extracted(root/inputs['toolchain_custody'],json.loads((HERE.parent/'toolchain-inputs.json').read_text()),jdk.parent)
        for folder in ['classes','home','tmp','artifacts','retained-source','notices']: (out/folder).mkdir()
        sources=[];manifest=[]
        for source in sorted((HERE/'src').rglob('*.java')):
            relative=source.relative_to(HERE/'src');target=out/'retained-source'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes());sources.append(target)
            manifest.append({'path':str(relative),'sha256':sha(target),'bytes':target.stat().st_size,'provenance':'Independently authored AmbisGIS adapter; Apache-2.0; no json-lib production source incorporated'})
        (out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');manifest_hash=sha(out/'source-manifest.json')
        (out/'sources.txt').write_text('\n'.join(map(str,sources))+'\n')
        env={'PATH':str(jdk/'bin')+':/usr/bin:/bin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
        command=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(out/'compile-network.json'),'--',str(jdk/'bin/javac'),'--release','17','-proc:none','-encoding','UTF-8','-cp',str(root/inputs['inputs']['jackson-core-binary']['path']),'-d',str(out/'classes'),'@'+str(out/'sources.txt')]
        with (out/'compile.log').open('xb') as log: proc=subprocess.run(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        receipt=json.loads((out/'compile-network.json').read_text());probes={x['family']:x for x in receipt.get('probes',[]) if x['operation']=='socket(SOCK_STREAM)'}
        valid=receipt.get('status')=='completed' and receipt.get('command_exit_code')==proc.returncode and all(probes.get(f,{}).get('passed') and probes[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
        result['commands'].append({'command':command,'exit_code':proc.returncode,'network_verified':bool(valid),'log_sha256':sha(out/'compile.log')})
        if proc.returncode or not valid:raise ValueError('Compile or network evidence failed')
        variant='json-compat-1-ambisgis-jackson-2.21.0'
        identity={'variant_id':variant,'new_source_output':True,'not_upstream_release':True,'original_maven_path':'net/sf/json-lib/json-lib/2.4.2-geoserver/json-lib-2.4.2-geoserver.jar','original_sha256':'c1de06da06183458cd8e4975e3b07e1d1d82a9f6e0a4438ed3d5dd8040983d2d','source_manifest_sha256':manifest_hash,'scope':'Selected GeoServer profile compatibility, not full json-lib API/data-binding compatibility','replacement_source_files':len(manifest)}
        items={str(x.relative_to(out/'classes')):x.read_bytes() for x in (out/'classes').rglob('*.class')}
        items['META-INF/ambisgis-variant.json']=(json.dumps(identity,indent=2)+'\n').encode()
        items['META-INF/NOTICE-AMBISGIS-JSON.txt']=(HERE/'NOTICE.txt').read_bytes()
        for entry in inputs['inputs'].values():
            if entry.get('role')=='packaged-notice':items[entry['member']]=(root/entry['path']).read_bytes()
        with zipfile.ZipFile(root/inputs['inputs']['jackson-core-source']['path']) as archive:
            items['META-INF/LICENSE']=archive.read('META-INF/LICENSE')
        items['META-INF/MANIFEST.MF']=('Manifest-Version: 1.0\r\nImplementation-Vendor: AmbisGIS development candidate\r\nImplementation-Version: '+variant+'\r\n\r\n').encode()
        artifact=out/'artifacts'/(variant+'.jar')
        with zipfile.ZipFile(artifact,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in sorted(items.items()):
                zi=zipfile.ZipInfo(name,(1980,1,1,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o100644<<16;archive.writestr(zi,data)
        members=[{'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in sorted(items.items())]
        (out/'json-compat-members.json').write_text(json.dumps(members,indent=2)+'\n')
        result['replacements']=[{**identity,'replacement_path':str(artifact),'replacement_sha256':sha(artifact),'source_manifest_path':str(out/'source-manifest.json'),'artifact_members_path':str(out/'json-compat-members.json')}]
        result['status']='built-focused-probes-pending'
    except Exception as e: result['error']=str(e)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(out),'error':result.get('error')}));return 0 if result['status']=='built-focused-probes-pending' else 1
if __name__=='__main__':raise SystemExit(main())
