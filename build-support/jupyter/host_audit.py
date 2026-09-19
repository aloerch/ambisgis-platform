#!/usr/bin/env python3
"""Record actual native link resolution; hashes do not imply host custody."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();run=a.run.resolve()
    env={'PATH':'/usr/bin:/bin','LANG':'C','LD_LIBRARY_PATH':str(run/'pam/prefix/lib')}
    candidates={Path(sys.executable).resolve(),run/'sources/node-v24.21.0-linux-x64/bin/node'}
    for base in [run/'user-env',run/'hub-env',run/'build-env',run/'pam/prefix/lib',run/'sources/jupyterlab/node_modules',run/'sources/jupyterhub/node_modules',run/'sources/jupyterhub/jsx/node_modules']:
        for p in base.rglob('*'):
            if p.is_file() and ('.so' in p.name or p.suffix=='.node'):
                with p.open('rb') as f: magic=f.read(4)
                if magic==b'\x7fELF':candidates.add(p.resolve())
    dependencies={};records=[]
    for path in sorted(candidates):
        result=subprocess.run(['ldd',str(path)],env=env,text=True,capture_output=True,timeout=30)
        raw=result.stdout+result.stderr
        records.append({'path':str(path),'sha256':digest(path),'exit_code':result.returncode,'ldd':raw})
        for target in re.findall(r'(?:=>\s+|^\s*)(/\S+)',raw,re.MULTILINE):
            dep=Path(target).resolve()
            if dep.is_file():dependencies[str(dep)]={'path':str(dep),'sha256':digest(dep),'custody':'retained/derived within run' if dep.is_relative_to(run) else 'unretained host library'}
    data={'scope':'Observed ldd resolution of selected executable/native extension files; runtime-loaded libraries and host stdlib/toolchain closure are not fully established.',
          'records':records,'dependencies':list(dependencies.values()),'missing':[x['path'] for x in records if 'not found' in x['ldd']]}
    with a.output.open('x') as out:json.dump(data,out,indent=2);out.write('\n')
    print(json.dumps({'elf_files':len(records),'libraries':len(dependencies),'unretained_host_libraries':sum(x['custody']=='unretained host library' for x in dependencies.values()),'missing':data['missing']}))
    return bool(data['missing'])


if __name__=='__main__':raise SystemExit(main())
