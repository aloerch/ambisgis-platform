#!/usr/bin/env python3
"""Inventory retained package archives and preserve original license/notice files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile


def sha(data): return hashlib.sha256(data).hexdigest()


def scan(custody, output):
    notices = custody/'notices';notices.mkdir(exist_ok=True)
    packages=[];notice_records=[];python_native={}
    def record(archive, members, ecosystem, roles):
        meta={}; original=[]; native=[]
        for name, data in members:
            base=Path(name).name.lower()
            if name.endswith('/package.json') and name.count('/')<=3:
                try:
                    candidate=json.loads(data)
                    if candidate.get('name') and (not meta or len(name)<len(meta.get('_path','x'*1000))):meta=candidate|{'_path':name}
                except (ValueError,UnicodeDecodeError):pass
            if re.match(r'^(licen[cs]e|copying|notice|copyright|authors)([.\-_]|$)',base):
                digest=sha(data);dest=notices/digest
                if not dest.exists():dest.write_bytes(data)
                original.append({'member':name,'sha256':digest,'retained':'notices/'+digest})
            if name.endswith(('.node','.so','.dll','.dylib','.wasm','.exe')) or '.so.' in Path(name).name:native.append(name)
        path=str(archive.relative_to(custody))
        notice_records.append({'archive':path,'notices':original})
        if ecosystem=='python':
            python_native[archive.name]=native
        else:
            packages.append({'name':meta.get('name'),'version':meta.get('version'),'ecosystem':ecosystem,'archive':path,'sha256':sha(archive.read_bytes()),'license':meta.get('license'),'repository':meta.get('repository'),'scripts':meta.get('scripts',{}),'native_members':native,'roles':roles,'custody':'retained registry distribution; source completeness not certified'})
    for archive in sorted((custody/'wheels').glob('*.whl')):
        with zipfile.ZipFile(archive) as z:
            record(archive,((n,z.read(n)) for n in z.namelist() if not n.endswith('/')), 'python',['build/runtime/test per python-inputs.json'])
    for archive in sorted((custody/'yarn-cache').glob('*.zip')):
        with zipfile.ZipFile(archive) as z:
            record(archive,((n,z.read(n)) for n in z.namelist() if not n.endswith('/')), 'yarn',['Lab frontend build/runtime/test graph'])
    for archive in sorted((custody/'npm-cache/_cacache/content-v2').rglob('*')):
        if not archive.is_file() or archive.open('rb').read(2)!=b'\x1f\x8b':continue
        try:
            with tarfile.open(archive,'r:gz') as t:
                record(archive,((m.name,t.extractfile(m).read()) for m in t if m.isfile()),'npm',['Hub frontend/proxy build/runtime/test graph'])
        except tarfile.ReadError:continue
    roots=json.loads((custody/'initial-inputs.json').read_text())
    for extra in ['toolchain-source-inputs.json','pam-inputs.json']:
        if (custody/extra).exists():roots+=json.loads((custody/extra).read_text())
    for root in roots:
        archive=custody/root['path']
        with tarfile.open(archive) as t:
            record(archive,((m.name,t.extractfile(m).read()) for m in t if m.isfile() and re.match(r'^(licen[cs]e|copying|notice|copyright|authors)([.\-_]|$)',Path(m.name).name.lower())), 'python', ['owned source' if root['class']=='owned-source' else 'Node toolchain'])
    python_inputs=json.loads((custody/'python-inputs.json').read_text())
    for item in python_inputs:
        item.update(native_members=python_native.get(item['wheel'],[]),custody='retained binary wheel plus matching third-party source distribution; not locally source-built')
    result={'python':python_inputs,'javascript':packages,'notices':notice_records,'limits':['npm/Yarn distributions can include compiled JavaScript/native bindings; full corresponding-source completeness and third-party rebuild/repair are not certified','Node source is retained but its binary is not locally source-built','Python executable/stdlib, libc, loader, libstdc++, PAM and shell/toolchain remain host inputs; no whole-product closure']}
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'python':len(result['python']),'javascript':len(packages),'notice_records':sum(len(x['notices']) for x in notice_records),'unique_notices':len(list(notices.iterdir())),'native_javascript_distributions':sum(bool(p['native_members']) for p in packages),'native_python_distributions':sum(bool(p['native_members']) for p in python_inputs)}))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--custody',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();scan(a.custody,a.output)
