#!/usr/bin/env python3
"""Attribute actual UI output differences; retain raw names and bytes unchanged."""
import argparse
import json
from pathlib import Path
import re

from common import sha


def build_hash(rows):
    hashes={m[1] for row in rows if (m:=re.search(r'\.([0-9a-f]{16})\.chunk\.js(?:\.LICENSE\.txt)?$',row['path']))}
    if len(hashes)!=1:raise ValueError('Expected one observed native webpack build hash')
    return hashes.pop()


def logical_path(path,token):
    return re.sub(r'\.'+re.escape(token)+r'(?=\.chunk\.js(?:\.LICENSE\.txt)?$)', '.<WEBPACK-HASH>',path)


def content_difference(x,y,first,second,ha,hb):
    if x==y:return {'kind':'byte-identical-content'}
    roots=[str(first).encode(),str(second).encode()];tokens=[ha.encode(),hb.encode()]
    paths=[x.count(roots[0]),y.count(roots[1])];hashes=[x.count(tokens[0]),y.count(tokens[1])]
    a=x.replace(roots[0],b'<RECORDED-JOB-ROOT>').replace(tokens[0],b'<RECORDED-WEBPACK-HASH>')
    b=y.replace(roots[1],b'<RECORDED-JOB-ROOT>').replace(tokens[1],b'<RECORDED-WEBPACK-HASH>')
    if a==b:
        return {'kind':'recorded-build-path-or-webpack-hash-references',
                'job_path_occurrences':paths,'webpack_hash_occurrences':hashes}
    return {'kind':'unexplained-content'}


def compare(root,output):
    builds=[root/f'build-{n}' for n in (1,2)]
    results=[json.loads((p/'result.json').read_text()) for p in builds]
    if any(r['result_exit_code'] for r in results):raise ValueError('Two actually successful fresh builds required')
    for key in ('source_inputs_sha256','dependency_manifest_sha256','tooling_manifest_sha256'):
        if results[0][key]!=results[1][key]:raise ValueError('Selected producer/input identity changed')
    inventories=[json.loads((p/'output-manifest.json').read_text()) for p in builds]
    hashes=[build_hash(rows) for rows in inventories]
    maps=[{logical_path(row['path'],token):row for row in rows} for rows,token in zip(inventories,hashes)]
    if any(len(m)!=len(rows) for m,rows in zip(maps,inventories)) or maps[0].keys()!=maps[1].keys():
        raise ValueError('Logical UI membership changed or collided')
    config=builds[0]/'client/geonode_mapstore_client/client/MapStore2/build/buildConfig.js'
    if '"[name].[hash].chunk.js"' not in config.read_text():raise ValueError('Inherited webpack filename rule changed')
    entries=[]
    for name,a in sorted(maps[0].items()):
        b=maps[1][name];paths=[build/'client/geonode_mapstore_client/static/mapstore'/r['path'] for build,r in zip(builds,[a,b])]
        for p,r in zip(paths,[a,b]):
            if sha(p)!=r['sha256']:raise ValueError('Produced UI output changed after recorded build')
        diagnosis=content_difference(paths[0].read_bytes(),paths[1].read_bytes(),*builds,*hashes)
        entries.append({'logical_path':name,'before':a,'after':b,'raw_path_and_bytes_identical':a==b,**diagnosis})
    report={'task':'T-OWN-02','component':'owned-frontend','result_exit_code':0,
            'comparison_recipe_sha256':sha(Path(__file__)),'webpack_rule':{'path':str(config),'sha256':sha(config)},
            'observed_webpack_hashes':hashes,'artifact_count':len(entries),
            'same_raw_name_and_content':sum(r['raw_path_and_bytes_identical'] for r in entries),
            'identical_content_after_explicit_name_mapping':sum(r['kind']=='byte-identical-content' for r in entries),
            'unexplained':sum(r['kind'].startswith('unexplained') for r in entries),'entries':entries,
            'fixture':json.loads((root/'synthetic-donor/drift.json').read_text()),
            'build_results':[{'path':str(p/'result.json'),'sha256':sha(p/'result.json')} for p in builds],
            'artifact_rewriting':False,'raw_byte_identity_claimed':False,'full_fnd08_acceptance':False,
            'limits':['Diagnostic-only in-memory substitutions of exact observed job-root paths and generated webpack build hashes. No artifacts rewritten.',
                      'Two emitted chunks embed literal job paths; generated hash/name/runtime references consequently differ. These build-path strings remain in the actual outputs.',
                      'Earlier orchestration receipt remains failed because its original criterion required identical raw names and bytes. This report records a separate attribution audit.']}
    if report['unexplained']:report['result_exit_code']=1
    output.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    if report['unexplained']:raise ValueError('Unexplained UI output content changes; diagnostic retained')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pair',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();compare(args.pair,args.output)
