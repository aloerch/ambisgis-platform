#!/usr/bin/env python3
"""Two actual fresh owned UI compilations around an isolated donor drift."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

from common import sha
from fixture import prepare,drift

HERE=Path(__file__).resolve().parent;PLATFORM=HERE.parents[1]


def write(path,data):path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')


def main(args):
    root=args.output.absolute();root.mkdir(parents=True,exist_ok=False)
    report={'task':'T-OWN-02','component':'owned-frontend','started_at':datetime.now(timezone.utc).isoformat(),
            'result_exit_code':1,'normalization_applied':False,'full_fnd08_acceptance':False}
    write(root/'started.json',report);fixture=root/'synthetic-donor';prepare(fixture);results=[]
    try:
        for n in (1,2):
            if n==2:drift(fixture)
            out=root/f'build-{n}';network=root/f'build-{n}-network.json'
            cmd=[sys.executable,str(PLATFORM/'build-support/postgis/offline_exec.py'),'--evidence',str(network),'--',
                 sys.executable,str(HERE/'frontend.py'),'--repos',str(args.repos),'--inputs',str(args.inputs),'--output',str(out)]
            write(root/f'build-{n}-invocation.json',{'at':datetime.now(timezone.utc).isoformat(),'command':cmd})
            with (root/f'build-{n}.log').open('x') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
            r=json.loads((out/'result.json').read_text());proof=json.loads(network.read_text())
            if r['result_exit_code'] or proof.get('status')!='completed' or proof.get('command_exit_code')!=0:
                raise ValueError('Build/network evidence failed')
            results.append(r)
        inputs={k:[r[k] for r in results] for k in ('source_inputs_sha256','dependency_manifest_sha256','tooling_manifest_sha256')}
        if any(a!=b for a,b in inputs.values()):raise ValueError('Selected frontend input identity changed')
        inventories=[]
        for n in (1,2):
            rows=json.loads((root/f'build-{n}/output-manifest.json').read_text())
            for row in rows:
                p=root/f'build-{n}/client/geonode_mapstore_client/static/mapstore'/row['path']
                if sha(p)!=row['sha256']:raise ValueError('Produced UI artifact changed')
            inventories.append({row['path']:row for row in rows})
        a,b=inventories
        outputs=[{'path':name,'before':a.get(name),'after':b.get(name),'byte_identical':a.get(name)==b.get(name)}
                 for name in sorted(a.keys()|b.keys())]
        report.update(inputs=inputs,outputs=outputs,artifact_count=len(outputs),
                      byte_identical=sum(r['byte_identical'] for r in outputs),fixture=json.loads((fixture/'drift.json').read_text()))
        if not all(row['byte_identical'] for row in outputs):raise ValueError('UI output differences require explicit diagnosis')
        report['result_exit_code']=0
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)};raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();write(root/'result.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repos','inputs','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
