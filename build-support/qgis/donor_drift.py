#!/usr/bin/env python3
"""Local synthetic donor drift fixture; never opens or edits a real donor repo."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

MARKER = {'task':'FND-08', 'fixture':'synthetic donor default/API drift', 'synthetic_only':True}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def git(root, *args):
    env = {'PATH':'/usr/bin:/bin', 'HOME':str(root/'empty-home'),
           'GIT_CONFIG_NOSYSTEM':'1', 'GIT_CONFIG_GLOBAL':'/dev/null',
           'GIT_AUTHOR_NAME':'AmbisGIS synthetic fixture', 'GIT_AUTHOR_EMAIL':'fixture@example.invalid',
           'GIT_COMMITTER_NAME':'AmbisGIS synthetic fixture', 'GIT_COMMITTER_EMAIL':'fixture@example.invalid',
           'GIT_AUTHOR_DATE':'2026-10-02T00:00:00Z', 'GIT_COMMITTER_DATE':'2026-10-02T00:00:00Z'}
    return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-C',str(root/'donor'),*args],
                                   env=env, stderr=subprocess.PIPE).decode().strip()


def validate(root):
    if root.is_symlink() or json.loads((root/'JOB_OWNERSHIP.json').read_text()) != MARKER:
        raise ValueError('not the exact job-owned synthetic donor fixture')
    if (root/'donor').is_symlink() or (root/'donor/.git').is_symlink():
        raise ValueError('fixture repository redirected')
    if git(root,'remote'):
        raise ValueError('synthetic fixture unexpectedly has a remote')
    if git(root,'rev-parse','--show-toplevel') != str(root/'donor'):
        raise ValueError('synthetic fixture escaped its own root')


def snapshot(root):
    validate(root)
    api_path = root/'api.json'
    api = json.loads(api_path.read_text())
    ref = git(root,'symbolic-ref','HEAD')
    commit = git(root,'rev-parse','HEAD')
    # Deliberately floating positive control: resolve current fake API default
    # rather than the independently pinned product source commit.
    floating_commit = git(root,'rev-parse','refs/heads/'+api['default_branch'])
    sentinel = git(root,'show',floating_commit+':sentinel-source.txt').encode()
    return {'ref':ref, 'commit':commit, 'tree':git(root,'rev-parse','HEAD^{tree}'),
            'api_sha256':digest(api_path.read_bytes()),
            'floating':{'commit':floating_commit, 'source_sha256':digest(sentinel),
                        'api_schema':api['schema'], 'default_branch':api['default_branch']}}


def prepare(root):
    if root.exists() or root.is_symlink():
        raise ValueError('fresh synthetic fixture directory required')
    root.mkdir(parents=True)
    (root/'empty-home').mkdir()
    (root/'donor').mkdir()
    write(root/'JOB_OWNERSHIP.json',MARKER)
    git(root,'init','--initial-branch=donor-before')
    (root/'donor/sentinel-source.txt').write_text('synthetic donor source before drift\n')
    git(root,'add','sentinel-source.txt')
    git(root,'commit','--no-gpg-sign','-m','Synthetic donor before drift')
    write(root/'api.json',{'schema':1,'default_branch':'donor-before','revision_field':'sha'})
    before = snapshot(root)
    write(root/'before.json',before)
    return before


def mutate(root):
    before = json.loads((root/'before.json').read_text())
    if snapshot(root) != before or (root/'after.json').exists():
        raise ValueError('fixture changed or drift already applied')
    git(root,'checkout','-b','donor-after')
    (root/'donor/sentinel-source.txt').write_text('synthetic donor incompatible source after drift\n')
    git(root,'add','sentinel-source.txt')
    git(root,'commit','--no-gpg-sign','-m','Synthetic donor incompatible default/API')
    # Preserve exact old fake API and deliberately change its schema/default.
    (root/'api.json').rename(root/'api-before.json')
    write(root/'api.json',{'schema':2,'default_branch':'donor-after','revision_field':'object_oid'})
    after = snapshot(root)
    if not all(before[k] != after[k] for k in ('ref','commit','tree','api_sha256','floating')):
        raise ValueError('synthetic drift positive control did not change')
    write(root/'after.json',after)
    report = {'fixture_before':before,'fixture_after':after,
              'floating_positive_control':{'before':before['floating'],'after':after['floating'],'changed':True},
              'scope':'synthetic local fixture only; actual two-build product comparison recorded separately'}
    write(root/'drift.json',report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','mutate','inspect'))
    parser.add_argument('--root',type=Path,required=True)
    args = parser.parse_args()
    action = {'prepare':prepare,'mutate':mutate,'inspect':snapshot}[args.action]
    print(json.dumps(action(args.root.absolute()),sort_keys=True))
