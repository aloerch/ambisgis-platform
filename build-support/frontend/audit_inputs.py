#!/usr/bin/env python3
"""Supplement retained archive/license/hook evidence without altering raw inventory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
from build import require, save, sha, verify_inputs

def inspect(archive):
    with tarfile.open(archive) as t:
        for member in t.getmembers():
            rel = PurePosixPath(member.name)
            require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe archive member')
        candidates=[m for m in t.getmembers() if m.isfile() and len(PurePosixPath(m.name).parts)==2 and m.name.endswith('/package.json')]
        require(len(candidates)==1,'Ambiguous root package metadata: '+str(archive))
        d=json.load(t.extractfile(candidates[0]))
        notices=[{'path':m.name,'sha256':hashlib.sha256(t.extractfile(m).read()).hexdigest()} for m in t.getmembers() if m.isfile() and any(w in Path(m.name).name.lower() for w in ('license','licence','notice','copying'))]
        return {'name':d.get('name'),'version':d.get('version'),'license_declaration':d.get('license',d.get('licenses')),
                'lifecycle':{k:v for k,v in d.get('scripts',{}).items() if k in ('preinstall','install','postinstall','prepare')},
                'engines':d.get('engines'), 'notices':notices,'sha256':sha(archive)}

def audit(inputs, output):
    manifest = json.loads((inputs/'manifest.json').read_text())
    verify_inputs(inputs, manifest)
    retained = {row['path'] for row in manifest['files']}
    rows=json.loads((inputs/'registry-inventory.json').read_text())
    for row in rows:
        rel = PurePosixPath(row['archive'])
        require(not rel.is_absolute() and '..' not in rel.parts and str(rel) == row['archive'] and row['archive'] in retained, 'Unmanifested inventory archive')
        require(sha(inputs/row['archive']) == row['sha256'], 'Retained inventory archive changed')
        metadata=inspect(inputs/row['archive'])
        row.update({k:v for k,v in metadata.items() if k!='notices'})
        row['notice_files']=metadata['notices']
    helpers=[{'archive':'vendor/'+n+'.tar.gz',**inspect(inputs/'vendor'/(n+'.tar.gz'))} for n in ('project','patcher','nomnom')]
    save(output,{'registry':rows,'helpers':helpers,'inventory_sha256':sha(inputs/'registry-inventory.json'),
                 'license_review':'Declarations and retained notices are evidence, not legal clearance. Unspecified metadata needs actual retained-file review.',
                 'binary_status':'Registry precompiled JS/WASM/native files are retained; broader source rebuild/repair closure remains FND-08.'})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();audit(a.inputs,a.output)
