#!/usr/bin/env python3
"""Job-owned donor fixture and exact artifact comparison for real T-OWN-02 builds."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

from resolution import sha, write_json
from owned_successor import git, inventory_digest

PRODUCER_INPUTS = ('owned_successor.py', 'resolution.py', 'compatibility.py',
                  'resolution_inventory.py', 'native_reports.py', 'no_oracle.py',
                  'toolchain.py', 'variant_inputs.py', 'toolchain-inputs.json',
                  'json-nojpeg2000-variant-inputs.json')


def floating_resolver(root):
    """Positive control deliberately follows an unpinned simulated default."""
    api=json.loads((root/'api-response.json').read_text())
    payload=git(root/'repository','show','refs/heads/'+api['default_branch']+':api-contract.json')
    return {'default_branch':api['default_branch'],'payload':json.loads(payload),
            'payload_sha256':hashlib.sha256(payload).hexdigest()}


def describe(root):
    api=json.loads((root/'api-response.json').read_text())
    ref='refs/heads/'+api['default_branch']
    return {'ref':ref,'commit':git(root/'repository','rev-parse',ref).decode().strip(),
            'tree':git(root/'repository','rev-parse',ref+'^{tree}').decode().strip(),
            'api_sha256':sha(root/'api-response.json')}


def commit_fixture(root,version):
    repo=root/'repository'
    (repo/'api-contract.json').write_text(json.dumps({'synthetic':True,'api':version,'sentinel':'incompatible-'+version})+'\n')
    git(repo,'add','api-contract.json')
    git(repo,'-c','user.name=AmbisGIS synthetic donor fixture','-c','user.email=test@example.invalid',
        'commit','-qm','Synthetic donor '+version)


def prepare(root):
    root.mkdir(parents=True,exist_ok=False)
    (root/'JOB_OWNERSHIP.json').write_text(json.dumps({'task':'FND-08','synthetic_only':True})+'\n')
    subprocess.run(['git','init','--quiet','--initial-branch=donor-main',str(root/'repository')],check=True)
    commit_fixture(root,'v1')
    (root/'api-response.json').write_text(json.dumps({'default_branch':'donor-main','api':'v1'})+'\n')
    write_json(root/'before.json',{'fixture_before':describe(root),'floating_before':floating_resolver(root)})


def drift(root):
    if json.loads((root/'JOB_OWNERSHIP.json').read_text())!={'task':'FND-08','synthetic_only':True}:
        raise ValueError('Not a job-owned synthetic fixture')
    before=json.loads((root/'before.json').read_text())
    if describe(root)!=before['fixture_before']:
        raise ValueError('Donor fixture changed unexpectedly before drift')
    git(root/'repository','checkout','-qb','donor-next')
    commit_fixture(root,'v2')
    (root/'api-response.json').write_text(json.dumps({'default_branch':'donor-next','api':'v2'})+'\n')
    after=floating_resolver(root)
    if after['payload_sha256']==before['floating_before']['payload_sha256']:
        raise ValueError('Floating positive control did not observe drift')
    write_json(root/'drift.json',{**before,'fixture_after':describe(root),
        'floating_positive_control':{'before':before['floating_before'],'after':after,'changed':True},
        'real_donor_or_owned_refs_modified':False})


def zip_entries(path):
    with zipfile.ZipFile(path) as archive:
        names=[info.filename for info in archive.infolist()]
        if len(names)!=len(set(names)):
            raise ValueError('Archive contains duplicate entries')
        return {info.filename:{'sha256':hashlib.sha256(archive.read(info)).hexdigest(),
                               'bytes':info.file_size,'timestamp':list(info.date_time),
                               'compression':info.compress_type,'mode':info.external_attr}
                for info in archive.infolist()}


def timestamp_changes(name, before, after):
    """Diagnose exact changed lines; never rewrite or equate the artifact bytes."""
    a,b=before.splitlines(keepends=True),after.splitlines(keepends=True)
    if len(a)!=len(b): return None
    if name=='META-INF/MANIFEST.MF':
        pattern=rb'Build-Timestamp: [0-9]{2}-[A-Za-z]{3}-[0-9]{4} [0-9]{2}:[0-9]{2}\r?\n'
    elif name.startswith('GeoServerApplication') and name.endswith('.properties'):
        pattern=rb'(?:# )?build\.date\s*=\s*[0-9]{2}-[A-Za-z]{3}-[0-9]{4} [0-9]{2}:[0-9]{2}\r?\n'
    elif name=='org/geotools/util/factory/GeoTools.properties':
        pattern=rb'build\.timestamp=[0-9]{2}-[A-Za-z]{3}-[0-9]{4} [0-9]{2}:[0-9]{2}\r?\n'
    elif name.startswith('META-INF/maven/') and name.endswith('/pom.properties'):
        pattern=rb'#[A-Za-z]{3} [A-Za-z]{3} [0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} [A-Z]+ [0-9]{4}\r?\n'
    else: return None
    changes=[{'line':n+1,'before':x.decode('ascii'),'after':y.decode('ascii')}
             for n,(x,y) in enumerate(zip(a,b)) if x!=y and re.fullmatch(pattern,x) and re.fullmatch(pattern,y)]
    if len(changes)!=sum(x!=y for x,y in zip(a,b)) or not changes: return None
    return changes


def attribute_archive(before, after, prefix=''):
    """Recursively inspect nested artifacts; unexpected content remains explicit."""
    changes=[]
    with zipfile.ZipFile(before) as a,zipfile.ZipFile(after) as b:
        na,nb=a.namelist(),b.namelist()
        if len(na)!=len(set(na)) or len(nb)!=len(set(nb)):
            raise ValueError('Archive contains duplicate entries')
        for name in sorted(set(na)|set(nb)):
            if name not in na or name not in nb:
                changes.append({'entry':prefix+name,'kind':'unexplained-membership'});continue
            x,y=a.read(name),b.read(name)
            if x==y: continue
            row={'entry':prefix+name,'before_sha256':hashlib.sha256(x).hexdigest(),
                 'after_sha256':hashlib.sha256(y).hexdigest()}
            if name.endswith(('.jar','.war')):
                nested=attribute_archive(io.BytesIO(x),io.BytesIO(y),prefix+name+'!/')
                changes.append({**row,'kind':'nested-archive','changes':nested})
            else:
                details=timestamp_changes(name,x,y)
                changes.append({**row,'kind':'generated-timestamp' if details else 'unexplained-content',
                                'changed_lines':details})
    return changes


def unexplained(changes):
    return sum(row['kind'].startswith('unexplained') or
               (row['kind']=='nested-archive' and unexplained(row['changes'])) for row in changes)


def compare(first,second,fixture,output):
    before=json.loads((first/'result.json').read_text());after=json.loads((second/'result.json').read_text())
    if before['result_exit_code'] or after['result_exit_code']:
        raise ValueError('Two actually successful new-source builds required')
    selected=['source_successor','source_inputs_sha256','retained_inputs_sha256','runner_sha256','toolchain']
    inputs={key:{'before':before[key],'after':after[key],'equal':before[key]==after[key]} for key in selected}
    if not all(row['equal'] for row in inputs.values()):
        raise ValueError('Simulated drift changed selected build inputs')
    # The donor fixture analyzer was added between the two builds. It is not
    # imported by the producer. Bind all actually executed producer inputs.
    ma=json.loads((first/'tooling-manifest.json').read_text());mb=json.loads((second/'tooling-manifest.json').read_text())
    selected_tools=['build-support/java/'+name for name in PRODUCER_INPUTS]+['build-support/postgis/offline_exec.py']
    producer_tools={name:{'before':ma[name],'after':mb[name],'equal':ma[name]==mb[name]} for name in selected_tools}
    if not all(row['equal'] for row in producer_tools.values()):
        raise ValueError('Executed producer tooling changed between builds')
    a={row['path']:row for row in before['artifacts']['built']};b={row['path']:row for row in after['artifacts']['built']}
    if set(a)!=set(b):raise ValueError('Produced artifact membership changed')
    outputs=[]
    for name in sorted(a):
        pa,pb=first/'work/source'/name,second/'work/source'/name
        if sha(pa)!=a[name]['sha256'] or sha(pb)!=b[name]['sha256']:
            raise ValueError('Produced artifact changed after recorded build')
        ea,eb=zip_entries(pa),zip_entries(pb)
        attribution=attribute_archive(pa,pb) if a[name]['sha256']!=b[name]['sha256'] else []
        outputs.append({'path':name,'before':a[name]['sha256'],'after':b[name]['sha256'],
            'byte_identical':a[name]['sha256']==b[name]['sha256'],
            'entry_inventory_before':inventory_digest(ea),'entry_inventory_after':inventory_digest(eb),
            'content_changes':[{'entry':n,'before':ea.get(n),'after':eb.get(n)} for n in sorted(set(ea)|set(eb))
                               if ea.get(n,{}).get('sha256')!=eb.get(n,{}).get('sha256')],
            'metadata_changed_entries':sum(ea.get(n)!=eb.get(n) and ea.get(n,{}).get('sha256')==eb.get(n,{}).get('sha256') for n in set(ea)|set(eb)),
            'recursive_content_attribution':attribution,'unexplained_content_changes':unexplained(attribution)})
    write_json(output,{'task':'T-OWN-02','fixture':json.loads((fixture/'drift.json').read_text()),
        'product':{'inputs':inputs,'producer_tools':producer_tools,'outputs':outputs,'byte_identical_artifacts':sum(r['byte_identical'] for r in outputs),
                   'artifact_count':len(outputs),'changed_content_entries':sum(len(r['content_changes']) for r in outputs)},
        'unexplained_content_changes':sum(r['unexplained_content_changes'] for r in outputs),
        'network_receipts':[before['network'],after['network']],
        'normalization_applied':False,'full_fnd08_acceptance':False})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','drift','compare']);parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--first',type=Path);parser.add_argument('--second',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.fixture)
    elif args.action=='drift':drift(args.fixture)
    else:
        if not all([args.first,args.second,args.output]):parser.error('compare requires first/second/output')
        compare(args.first,args.second,args.fixture,args.output)


if __name__=='__main__':main()
