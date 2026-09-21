#!/usr/bin/env python3
"""Retain an acquired npm v3 graph; hash every archive; make replay local-only.

Only registry.npmjs.org, the two reviewed helper archives and one exact observed
transitive Git input are allowed. No lifecycle scripts execute in this step.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import os
import shutil
import tarfile
import urllib.request
from build import sha, require, save, verify_sri, CLIENT, MAPSTORE, validate_lock

NOMNOM = '559dfcd9436b3beeeccdc0a4f28f0e3f988379ca'

def retain(root, out):
    require(not out.exists(), 'Fresh retained-input directory required')
    out.mkdir(); (out/'vendor/registry').mkdir(parents=True)
    front = root/'acquire-01/client/geonode_mapstore_client/client'
    lock = json.loads((front/'package-lock.json').read_text())
    shutil.copyfile(front/'package-lock.json', out/'acquisition-lock.json')
    for name in ('project','patcher'):
        shutil.copyfile(front/'vendor'/(name+'.tar.gz'),out/'vendor'/(name+'.tar.gz'))
    giturl='https://codeload.github.com/gerhobbelt/nomnom/tar.gz/'+NOMNOM
    gitpath=out/'vendor/nomnom.tar.gz'
    with urllib.request.urlopen(giturl, timeout=120) as r,gitpath.open('xb') as f:
        shutil.copyfileobj(r,f)
    jobs={}; inputs=[]
    for name,row in lock['packages'].items():
        resolved=row.get('resolved','')
        if not resolved or row.get('link'): continue
        if resolved.startswith('file:vendor/'):
            verify_sri(out/resolved[5:],row['integrity']);continue
        if resolved.startswith('git+'):
            require(name=='node_modules/@gerhobbelt/nomnom' and resolved=='git+ssh://git@github.com/gerhobbelt/nomnom.git#'+NOMNOM, 'Unreviewed Git input: '+name)
            row['resolved']='file:vendor/nomnom.tar.gz'
            row['integrity']='sha512-'+base64.b64encode(hashlib.sha512(gitpath.read_bytes()).digest()).decode()
            inputs.append({'package':name,'original':resolved,'acquired':giturl,'sha256':sha(gitpath),'status':'retained exact Git source, not donor branch'})
            continue
        require(resolved.startswith('https://registry.npmjs.org/'), 'Unreviewed archive origin: '+resolved)
        integrity=row['integrity']; key=hashlib.sha256(integrity.encode()).hexdigest()+'.tgz'
        jobs[key]=(resolved,integrity)
        row['resolved']='file:vendor/registry/'+key
    def fetch(job):
        key,(url,integrity)=job; dest=out/'vendor/registry'/key
        algorithm,encoded=integrity.split(' ',1)[0].split('-',1); digest=base64.b64decode(encoded).hex()
        cache=root/'acquire-01/npm-cache/_cacache/content-v2'/algorithm/digest[:2]/digest[2:4]/digest[4:]
        if cache.exists(): shutil.copyfile(cache,dest)
        else:
            with urllib.request.urlopen(url, timeout=120) as r,dest.open('xb') as f:shutil.copyfileobj(r,f)
        verify_sri(dest,integrity)
        with tarfile.open(dest) as t:
            members=t.getmembers(); manifests=[m for m in members if m.isfile() and len(Path(m.name).parts) == 2 and m.name.endswith('/package.json')]
            d=json.load(t.extractfile(manifests[0])) if manifests else {}
            notices=[{'path':m.name,'sha256':hashlib.sha256(t.extractfile(m).read()).hexdigest()} for m in members if m.isfile() and any(word in Path(m.name).name.lower() for word in ('license','licence','notice','copying'))]
            binaries=[m.name for m in members if m.isfile() and m.name.endswith(('.node','.wasm','.dll','.so','.exe'))]
        return {'archive':str(dest.relative_to(out)),'url':url,'integrity':integrity,'sha256':sha(dest),'bytes':dest.stat().st_size,
                'name':d.get('name'),'version':d.get('version'),'license_declaration':d.get('license',d.get('licenses')),
                'notice_files':notices,'binary_files':binaries,'lifecycle':{k:v for k,v in d.get('scripts',{}).items() if k in ('preinstall','install','postinstall','prepare')},
                'engines':d.get('engines'), 'status':'registry package retained; source/binary declaration is not independent source rebuild or license clearance'}
    with ThreadPoolExecutor(max_workers=8) as pool: rows=list(pool.map(fetch,jobs.items()))
    save(out/'registry-inventory.json',rows);save(out/'git-inputs.json',inputs)
    save(out/'package-lock.json',lock);validate_lock(lock,out/'vendor')
    source_root=Path('/home/revelberry/Projects/AmbisGIS/source-archives')
    for source,dest in [(source_root/'ambisgis-mapstore-client-673a854c4b3b.bundle',out/'client.bundle'),(source_root/'ambisgis-mapstore-0eedc8b7184d.bundle',out/'mapstore.bundle'),(root/'inputs/node-v24.18.1-linux-x64.tar.xz',out/'node.tar.xz')]:
        os.link(source,dest)
    save(out/'manifest.json',{'client_commit':CLIENT,'mapstore_commit':MAPSTORE,
        'files':[{'path':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()],
        'registry_archives':len(rows),'lifecycle_policy':'install ignored; only selected explicit source hook may execute offline'})
    print(json.dumps({'inputs':str(out),'registry_archives':len(rows),'lock_entries':len(lock['packages'])}))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();retain(a.root.resolve(),a.output.resolve())
