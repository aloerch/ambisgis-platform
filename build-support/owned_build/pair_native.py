#!/usr/bin/env python3
"""Two actual fresh native builds around a nonvacuous synthetic donor change."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from common import sha
from fixture import prepare,drift

HERE=Path(__file__).resolve().parent
PLATFORM=HERE.parents[1]


def write(path,data):path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')


def build_id(path):
    if path.read_bytes()[:4]!=b'\x7fELF':return None
    text=subprocess.check_output(['/usr/bin/readelf','-n',str(path)],text=True)
    matches=re.findall(r'Build ID: ([0-9a-f]+)',text)
    return bytes.fromhex(matches[0]) if len(matches)==1 else None


def archive_metadata(data):
    """Return diagnostic-only bytes with exact SysV ar mtime fields blanked."""
    if not data.startswith(b'!<arch>\n'):return None
    result=bytearray(data);dates=[];offset=8
    while offset<len(data):
        header=data[offset:offset+60]
        if len(header)!=60 or header[58:]!=b'`\n':raise ValueError('Invalid static archive header')
        size=int(header[48:58]);stamp=header[16:28]
        if stamp.strip() and not stamp.strip().isdigit():raise ValueError('Invalid static archive date')
        dates.append({'offset':offset+16,'member':header[:16].decode('ascii'),'value':stamp.decode('ascii')})
        result[offset+16:offset+28]=b' '*12;offset+=60+size+(size%2)
    if offset!=len(data):raise ValueError('Static archive size mismatch')
    return bytes(result),dates


def diagnose(a,b,first,second):
    """Keep originals; attribute exact path and ELF-note differences in memory."""
    x,y=a.read_bytes(),b.read_bytes()
    if x==y:return {'kind':'byte-identical'}
    pa,pb=str(first).encode(),str(second).encode()
    counts=[x.count(pa),y.count(pb)]
    dx,dy=x.replace(pa,b'<JOB-ROOT>'),y.replace(pb,b'<JOB-ROOT>')
    if dx==dy and all(counts):return {'kind':'recorded-job-paths-only','path_occurrences':counts}
    ax,ay=archive_metadata(x),archive_metadata(y)
    if ax and ay and ax[0].replace(pa,b'<JOB-ROOT>')==ay[0].replace(pb,b'<JOB-ROOT>'):
        return {'kind':'static-archive-dates-and-recorded-job-paths','path_occurrences':counts,
                'archive_dates_before':ax[1],'archive_dates_after':ay[1]}
    ia,ib=build_id(a),build_id(b)
    if ia and ib and x.count(ia)==1 and y.count(ib)==1:
        if dx.replace(ia,b'<ELF-BUILD-ID>')==dy.replace(ib,b'<ELF-BUILD-ID>'):
            return {'kind':'recorded-job-paths-and-elf-build-id','path_occurrences':counts,
                    'build_ids':[ia.hex(),ib.hex()],'note_offsets':[x.index(ia),y.index(ib)]}
    return {'kind':'unexplained-content'}


def main(args):
    root=args.output.absolute();root.mkdir(parents=True,exist_ok=False)
    report={'task':'T-OWN-02','component':'owned-postgresql-postgis','started_at':datetime.now(timezone.utc).isoformat(),
            'result_exit_code':1,'artifact_rewriting':False,'full_fnd08_acceptance':False}
    write(root/'started.json',report)
    fixture=root/'synthetic-donor';prepare(fixture)
    results=[]
    try:
        for number in (1,2):
            if number==2:drift(fixture)
            out=root/f'build-{number}'
            network=root/f'build-{number}-network.json'
            command=[sys.executable,str(PLATFORM/'build-support/postgis/offline_exec.py'),'--evidence',str(network),'--',
                     sys.executable,str(HERE/'native.py'),'--repos',str(args.repos),'--custody',str(args.custody),
                     '--support',str(args.support),'--output',str(out),'--jobs',str(args.jobs)]
            write(root/f'build-{number}-invocation.json',{'at':datetime.now(timezone.utc).isoformat(),'command':command})
            with (root/f'build-{number}.log').open('x') as log:
                subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
            result=json.loads((out/'result.json').read_text());proof=json.loads(network.read_text())
            if result['result_exit_code'] or proof.get('status')!='completed' or proof.get('command_exit_code')!=0:
                raise ValueError('Build or network-denial evidence failed')
            results.append(result)
        inputs={k:[r[k] for r in results] for k in ('source_inputs_sha256','support_inputs_sha256','tooling_manifest_sha256')}
        if any(a!=b for a,b in inputs.values()):raise ValueError('Paired selected input identities changed')
        inventories=[json.loads((root/f'build-{n}/output-manifest.json').read_text()) for n in (1,2)]
        if set(inventories[0])!=set(inventories[1]):raise ValueError('Installed membership differs')
        outputs=[]
        for name in sorted(inventories[0]):
            before,after=[r[name] for r in inventories]
            a,b=[root/f'build-{n}/prefix'/name for n in (1,2)]
            if 'symlink' in before or 'symlink' in after:
                diagnosis={'kind':'byte-identical' if before==after else 'unexplained-link'}
            else:
                if sha(a)!=before['sha256'] or sha(b)!=after['sha256']:raise ValueError('Installed output changed')
                diagnosis=diagnose(a,b,root/'build-1',root/'build-2')
            outputs.append({'path':name,'before':before,'after':after,**diagnosis})
        report.update(selected_inputs=inputs,outputs=outputs,fixture=json.loads((fixture/'drift.json').read_text()),
                      byte_identical=sum(r['kind']=='byte-identical' for r in outputs),artifact_count=len(outputs),
                      unexplained=sum(r['kind'].startswith('unexplained') for r in outputs),
                      comparison_scope='Raw artifact hashes retained. In-memory diagnostic substitutions only attribute exact job-root bytes and ELF build-id notes; they do not establish raw byte identity.')
        if report['unexplained']:raise ValueError('Unexplained native output changes')
        report['result_exit_code']=0
    except BaseException as error:
        report['error']={'type':type(error).__name__,'message':str(error)}
        raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();write(root/'result.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repos','custody','support','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--jobs',type=int,default=4);a=p.parse_args()
    if not 1<=a.jobs<=4:p.error('jobs must be 1..4')
    main(a)
