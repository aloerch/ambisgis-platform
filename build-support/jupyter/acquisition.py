#!/usr/bin/env python3
"""Verify a retained input store; optional fetch restores only recorded URL inputs.

Large caches are custody artifacts, not implicit downloads. Missing cache entries
fail verification and must be restored from the retained store/backup; this tool
never runs a resolver or executes package installation hooks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request
from build import digest, verify


def restore(custody, manifest, owned_root=None):
    custody=custody.resolve()
    # Validate destinations before any directory creation or download.
    for item in manifest['files']:
        relative=Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unsafe manifest path')
        path=custody/relative
        if not path.parent.resolve().is_relative_to(custody):
            raise ValueError('restore destination escapes custody')
        if any(parent.is_symlink() for parent in [path,*path.parents] if parent!=custody and parent.is_relative_to(custody)):
            raise ValueError('symlink in restore destination')
    origins = {x['path']:x for x in manifest['roots']}
    # Recovery metadata is itself pinned by the checked-in manifest.
    index={x['path']:x for x in manifest['files']}
    for metadata in ['python-inputs.json','toolchain-source-inputs.json','pam-inputs.json']:
        path=custody/metadata
        if not path.is_file() or digest(path)!=index[metadata]['sha256']:
            raise ValueError('restore verified metadata from backup first: '+metadata)
        for item in json.loads(path.read_text()):
            if 'wheel' in item:
                origins['wheels/'+item['wheel']]={'url':item['url']}
                for source in item['source']:origins[source['path']]=source
            else:origins[item['path']]=item
    restored=[]
    for item in manifest['files']:
        rel=Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('unsafe manifest path')
        path=custody/rel
        if path.exists():continue
        source=origins.get(item['path'])
        if not source:continue
        path.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.restore-',delete=False) as tmp:
            temporary=Path(tmp.name)
            try:
                if source.get('class')=='owned-source':
                    if owned_root is None:raise ValueError('--owned-root needed for Git archive restoration')
                    repo=owned_root/('ambisgis-'+source['name'])
                    expected='https://github.com/aloerch/ambisgis-'+source['name']+'.git'
                    origin=subprocess.check_output(['git','-C',str(repo),'remote','get-url','origin'],text=True).strip()
                    if origin!=expected:raise ValueError('owned remote mismatch')
                    subprocess.run(['git','-C',str(repo),'archive','--format=tar','--prefix='+source['name']+'/',source['commit']],stdout=tmp,check=True)
                else:
                    url=source['url']
                    if not url.startswith('https://'):raise ValueError('expected HTTPS origin')
                    with urllib.request.urlopen(url,timeout=60) as response:
                        while chunk:=response.read(1024*1024):tmp.write(chunk)
                tmp.flush()
                if digest(temporary)!=item['sha256'] or temporary.stat().st_size!=item['size']:
                    raise ValueError('restored input did not match pin: '+str(rel))
                temporary.rename(path);restored.append(str(rel))
            finally:
                temporary.unlink(missing_ok=True)
    return restored


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--custody',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,default=Path(__file__).with_name('inputs.json'))
    ap.add_argument('--fetch',action='store_true')
    ap.add_argument('--owned-root',type=Path)
    a=ap.parse_args();manifest=json.loads(a.manifest.read_text())
    restored=restore(a.custody,manifest,a.owned_root) if a.fetch else []
    verify(a.custody,manifest)
    print(json.dumps({'status':'verified','files':len(manifest['files']),'bytes':sum(x['size'] for x in manifest['files']),'manifest_sha256':digest(a.manifest),'restored':restored}))


if __name__=='__main__':main()
