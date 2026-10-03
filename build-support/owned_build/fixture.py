"""Nonvacuous synthetic donor fixture; mutates only a marked fresh local repository."""
import hashlib
import json
from pathlib import Path
import subprocess
from common import git

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path,value):
    Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")

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
