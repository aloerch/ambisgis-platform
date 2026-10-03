#!/usr/bin/env python3
"""Inventory actual successor inputs and retained source candidates, without fetches.

Source presence is not source/binary correspondence or a toolchain bootstrap.
The complete Maven selections and source tree inventories remain separately bound.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

from resolution import sha, write_json
from resolution_inventory import jar_coordinate, verify_custody
from source_closure import checked_blob

HERE=Path(__file__).resolve().parent


def reference(path):
    return {'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size}


def inspect(build,custody,output):
    result=json.loads((build/'result.json').read_text())
    if result['result_exit_code']:raise ValueError('Successful actual build required')
    rows=json.loads((build/'retained-inputs.json').read_text())
    if sha(build/'retained-inputs.json')!=result['retained_inputs_sha256']:
        raise ValueError('Selected Maven inventory changed')
    verified=verify_custody(custody)
    if not verified['verification']['valid']:raise ValueError('Custody verification failed')
    records={(r['repository'],r['maven_path']):r for r in verified['artifacts']}
    selected={r['maven_path']:r for r in rows}
    supplement=json.loads((HERE/'source-closure-inputs.json').read_text())
    variants={r['maven_path']:r for r in result['variant_inputs']['replacements']}
    consumed=[]
    for path in sorted((build/'fresh-m2').rglob('*.jar')):
        name=path.relative_to(build/'fresh-m2').as_posix()
        row=selected[name]
        if path.is_symlink() or sha(path)!=row['sha256']:
            raise ValueError('Actual Maven binary differs from recorded input: '+name)
        coordinate=jar_coordinate(name)
        if coordinate is None:continue
        item={'maven_path':name,'sha256':row['sha256'],'gav':coordinate['gav'],
              'recorded_origin':row['repository'],'source_candidates':[]}
        if name in variants:
            v=variants[name]
            for r in v['source_evidence']:
                if sha(Path(r['path']))!=r['sha256']:raise ValueError('Variant source evidence changed')
            item.update(source_disposition='controlled-source-variant',source_candidates=v['source_evidence'],variant_id=v['variant_id'])
        elif row.get('source_resource_verified'):
            item.update(source_disposition='retained-schema-resource',source_candidates=[{'maven_path':name,'sha256':row['sha256']}])
        else:
            source=records.get((row['repository'],coordinate['sources_path']))
            if source:
                item.update(source_disposition='retained-coordinate-source-candidate',
                            source_candidates=[{**reference(custody/source['blob_path']),
                                                'maven_path':source['maven_path'],
                                                'record':reference(custody/source['record_path'])}])
            else:
                candidate=supplement['artifacts'].get(coordinate['gav'],{})
                for r in candidate.get('sources',[]):
                    checked_blob(Path(supplement['custody_root']),r)
                    item['source_candidates'].append({**r,'custody_root':supplement['custody_root']})
                item['source_disposition']='retained-supplement-source-candidate' if item['source_candidates'] else 'no-separate-source-candidate'
                item['prior_source_limit']=candidate.get('remaining')
                item['retained_investigation_receipts']=[reference(Path(supplement['custody_root'])/p)
                    for p in candidate.get('investigation',[]) if (Path(supplement['custody_root'])/p).is_file()]
                if not item['source_candidates']:
                    with zipfile.ZipFile(path) as z:
                        classes=[n for n in z.namelist() if n.endswith('.class')]
                        sources=[n for n in z.namelist() if n.endswith('.java')]
                        item['embedded_java_sources']=sources;item['class_entries']=len(classes)
                        item['class_paths']=classes
                        if not classes:item['source_disposition']='resource-or-metadata-only'
                        elif sources:item['source_disposition']='embedded-source-candidate'
        consumed.append(item)
    # Identify every WAR library, including owned vendor builds and non-core JARs.
    by_hash={r['sha256']:{'kind':'retained-maven-input','maven_path':r['maven_path']} for r in rows}
    by_hash.update({r['sha256']:{'kind':'new-source-build','source_output':r['path']} for r in result['artifacts']['built']})
    libraries=[]
    war=Path(result['artifacts']['war'])
    if sha(war)!=result['artifacts']['war_sha256']:raise ValueError('Built WAR changed')
    with zipfile.ZipFile(war) as z:
        for name in sorted(z.namelist()):
            if not name.startswith('WEB-INF/lib/') or not name.endswith('.jar'):continue
            digest=hashlib.sha256(z.read(name)).hexdigest()
            if digest not in by_hash:raise ValueError('WAR library has no selected origin: '+name)
            libraries.append({'entry':name,'sha256':digest,**by_hash[digest]})
    for item in consumed:
        item['shipped_in_war']=[r['entry'] for r in libraries if r['sha256']==item['sha256']]
        item['observed_scope']='shipped-in-aggregate' if item['shipped_in_war'] else 'build-or-test-resolution-only'
    sources=json.loads((build/'source-inputs.json').read_text())
    if sha(build/'source-inputs.json')!=result['source_inputs_sha256']:raise ValueError('Source inventory changed')
    resources={p:d for p,d in sources.items() if Path(p).suffix.lower() in
               ('.ttf','.otf','.woff','.woff2','.sld','.css','.svg','.png','.jpg','.jpeg','.tif','.tiff','.sql','.properties','.prj','.wkt','.xsd')}
    report={'task':'FND-08','scope':'actual Java successor build inputs',
        'build_result':reference(build/'result.json'),'selected_maven_inputs':reference(build/'retained-inputs.json'),
        'complete_source_inventory':reference(build/'source-inputs.json'),
        'toolchain_manifest':reference(build/'tooling/build-support/java/toolchain-inputs.json'),
        'source_supplement_manifest':reference(HERE/'source-closure-inputs.json'),
        'selected_maven_file_count':len(rows),'actual_maven_jar_count':len(consumed),
        'source_dispositions':dict(sorted(Counter(r['source_disposition'] for r in consumed).items())),
        'actual_maven_jars':consumed,'war_libraries':libraries,
        'source_resource_subset':resources,'source_resource_count':len(resources),
        'limits':['Source candidate presence does not prove structural coverage or source/binary correspondence.',
                  'Complete selected source file inventory includes styles/fonts/CRS/schema and other resources; the displayed subset is only a convenience.',
                  'Host executables/shared libraries are tracked by the aggregate FND-08 host inventory.',
                  'Independent toolchain source bootstrap remains a later qualification obligation.'],
        'full_fnd08_acceptance':False}
    write_json(output,report)
    print(json.dumps({k:report[k] for k in ('actual_maven_jar_count','source_dispositions','source_resource_count')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('build','custody','output'):p.add_argument('--'+arg,type=Path,required=True)
    a=p.parse_args();inspect(a.build,a.custody,a.output)
