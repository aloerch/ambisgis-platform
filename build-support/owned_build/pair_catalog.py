#!/usr/bin/env python3
"""Actual fresh canonical catalog builds before and after synthetic donor drift."""
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
    report={'task':'T-OWN-02','component':'owned-catalog','started_at':datetime.now(timezone.utc).isoformat(),
            'result_exit_code':1,'normalization_applied':False,'full_fnd08_acceptance':False}
    write(root/'started.json',report);fixture=root/'synthetic-donor';prepare(fixture)
    results=[]
    try:
        for n in (1,2):
            if n==2:drift(fixture)
            out=root/f'build-{n}';network=root/f'build-{n}-network.json'
            cmd=[sys.executable,str(PLATFORM/'build-support/postgis/offline_exec.py'),'--evidence',str(network),'--',
                 args.python,str(HERE/'catalog.py'),'--repos',str(args.repos),'--custody',str(args.custody),
                 '--support',str(args.support),'--output',str(out)]
            write(root/f'build-{n}-invocation.json',{'at':datetime.now(timezone.utc).isoformat(),'command':cmd})
            with (root/f'build-{n}.log').open('x') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
            r=json.loads((out/'result.json').read_text());proof=json.loads(network.read_text())
            if r['result_exit_code'] or proof.get('status')!='completed' or proof.get('command_exit_code')!=0:
                raise ValueError('Build/network evidence failed')
            results.append(r)
        inputs={k:[r[k] for r in results] for k in ('source_inputs_sha256','dependency_manifest_sha256',
                'support_inputs_sha256','tooling_manifest_sha256','policy_source_files')}
        if any(a!=b for a,b in inputs.values()):raise ValueError('Selected catalog input identity changed')
        outputs=[json.loads((root/f'build-{n}/output-manifest.json').read_text()) for n in (1,2)]
        for n,rows in enumerate(outputs,1):
            for path,digest in rows.items():
                if sha(root/f'build-{n}/artifacts'/path)!=digest:raise ValueError('Produced catalog artifact changed')
        report.update(inputs=inputs,outputs=outputs,byte_identical=outputs[0]==outputs[1],
                      fixture=json.loads((fixture/'drift.json').read_text()))
        if not report['byte_identical']:raise ValueError('Catalog output bytes differ; diagnosis required')
        report['result_exit_code']=0
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)};raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();write(root/'result.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repos','custody','support','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--python',default='/usr/bin/python3.12');main(p.parse_args())
