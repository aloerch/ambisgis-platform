#!/usr/bin/env python3
"""Account for independent source and exact JSON definitions in a selected classpath/WAR."""
import argparse,hashlib,io,json,zipfile
from pathlib import Path
sha=lambda data:hashlib.sha256(data).hexdigest()

def inspect_data(build,entries):
    build=Path(build);r=json.loads((build/'result.json').read_text());replacement=r['replacements'][0]
    source_path=Path(replacement['source_manifest_path']);source_manifest=json.loads(source_path.read_text())
    errors=[]
    if sha(source_path.read_bytes())!=replacement['source_manifest_sha256']:errors.append('source manifest hash differs')
    for source in source_manifest:
        path=build/'retained-source'/source['path']
        if not path.is_file() or sha(path.read_bytes())!=source['sha256']:errors.append('source differs: '+source['path'])
    expected={x['path']:x['sha256'] for x in json.loads(Path(replacement['artifact_members_path']).read_text()) if x['path'].endswith('.class')}
    origins={};variants=[];old_fingerprints=[]
    old_root=build.parents[2]/'java-gmt-remediation/source'
    known_old=set()
    for original,expected_hash in [(old_root/'baseline-libs/json-lib-2.4.2-geoserver.jar','c1de06da06183458cd8e4975e3b07e1d1d82a9f6e0a4438ed3d5dd8040983d2d'),(old_root/'build-01/artifacts/json-lib-2.4.1-ambisgis-source-1.jar','92c744bdb2ed2a6ff255af473f271bf3954e00ab037ed5649a39056eeab2fbf2')]:
        if not original.is_file() or sha(original.read_bytes())!=expected_hash:raise ValueError('Missing/changed historical fingerprint source: '+str(original))
        with zipfile.ZipFile(original) as archive: known_old.update(sha(archive.read(n)) for n in archive.namelist() if n.endswith('.class'))
    libraries=[];nested_archives=[]
    def scan(name,data,depth=0):
        if depth>8:raise ValueError('Nested archive depth exceeds inspection bound')
        with zipfile.ZipFile(io.BytesIO(data)) as jar:
            for member in jar.namelist():
                if member.endswith('.class'):
                    member_hash=sha(jar.read(member))
                    if member_hash in known_old:old_fingerprints.append(name+'!'+member)
                    if 'net/sf/json/' in member:
                        class_key=member[member.index('net/sf/json/'):]
                        origins.setdefault(class_key,[]).append({'jar':name,'member':member,'sha256':member_hash})
                elif member.lower().endswith(('.jar','.zip')):
                    nested=jar.read(member)
                    if zipfile.is_zipfile(io.BytesIO(nested)):
                        nested_archives.append(name+'!'+member);scan(name+'!'+member,nested,depth+1)
                elif member=='META-INF/ambisgis-variant.json':
                    identity=json.loads(jar.read(member))
                    if identity.get('variant_id')==replacement['variant_id']:
                        variants.append({'jar':name,'sha256':sha(data),'identity':identity})
    for name,data in entries:
        libraries.append({'path':name,'sha256':sha(data)});scan(name,data)
    if len(variants)!=1 or variants[0]['sha256']!=replacement['replacement_sha256']:errors.append('exact independent adapter artifact missing/duplicated/changed')
    if set(origins)!=set(expected):errors.append('JSON runtime definition set differs from new compilation')
    for member,witnesses in origins.items():
        if len(witnesses)!=1 or witnesses[0]['sha256']!=expected.get(member):errors.append('duplicate/foreign JSON definition: '+member)
    if old_fingerprints:errors.append('old json-lib class bytes remain (including renamed entries)')
    return {'schema_version':1,'passed':not errors,'errors':errors,'variant_id':replacement['variant_id'],'source_manifest_sha256':replacement['source_manifest_sha256'],'source_files_verified':len(source_manifest),'source_accounting':'Entire original json-lib production layer excluded; seven attributed files, alternate JDK15 copies and all uncredited helpers including JSONUtils are outside new compilation. Exact newly authored source manifest retained. Binary absence is not represented as proof against arbitrary transformed copying.','definitions':origins,'variant_artifacts':variants,'old_class_fingerprint_count':len(known_old),'old_class_matches':old_fingerprints,'libraries':libraries,'nested_archives_inspected':nested_archives}

def inspect_jars(build,jars):return inspect_data(build,[(str(p),Path(p).read_bytes()) for p in jars])
def inspect_war(build,war):
    with zipfile.ZipFile(war) as z:return inspect_data(build,[(n,z.read(n)) for n in z.namelist() if n.startswith('WEB-INF/lib/') and n.endswith('.jar')])
def inspect_artifacts(build,jar_entries,class_origins=None,libraries=None):
    """Aggregate integration: derive component custody from the frozen selected mapping."""
    build=Path(build);result=json.loads((build/'result.json').read_text())
    mappings=result.get('local_variant_inputs',{}).get('replacements',[])
    selected=[x for x in mappings if x.get('maven_path')=='net/sf/json-lib/json-lib/2.4.2-geoserver/json-lib-2.4.2-geoserver.jar']
    if len(selected)!=1:raise ValueError('One frozen JSON replacement mapping required')
    mapping=selected[0];candidates=[]
    for source in mapping.get('source_evidence',[]):
        path=Path(source['path'])
        if not path.is_file() or sha(path.read_bytes())!=source['sha256']:raise ValueError('Changed JSON source evidence')
        if path.name=='result.json':
            receipt=json.loads(path.read_text())
            if any(x.get('replacement_sha256')==mapping.get('sha256') and x.get('variant_id')==mapping.get('variant_id') for x in receipt.get('replacements',[])):candidates.append(path.parent)
    if len(candidates)!=1:raise ValueError('Exact component result binding missing')
    report=inspect_war(candidates[0],build/'work/source/geoserver/src/web/app/target/geoserver.war')
    if not report['passed']:raise ValueError('Independent JSON runtime guard failed: '+str(report['errors']))
    return report
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--war',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=inspect_war(a.build,a.war);result['war']={'path':str(a.war),'sha256':sha(a.war.read_bytes())};a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'errors':result['errors']}));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
