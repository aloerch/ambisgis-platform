#!/usr/bin/env python3
"""Reuse source_closure provenance parsers for targeted imaging audit evidence."""
import argparse,hashlib,io,json,pathlib,re,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'build-support/java'))
import source_closure as sc

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def file(p):return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();o=a.output;o.mkdir(parents=True,exist_ok=False)
 mapping=json.loads((ROOT/'plan/verification/java-gmt-remediation/imaging-replacements.json').read_text());root=a.workspace/'build-worktrees/java-gmt-remediation/imaging';records=[]
 for row in mapping['replacements']:
  result_path=pathlib.Path(row['source_evidence'][0]['path']);r=json.loads(result_path.read_text());original=root/'baseline-libs'/pathlib.Path(row['maven_path']).name;archive=pathlib.Path(row['source_evidence'][1]['path']);members=sc.archive_members(archive.read_bytes());binary=sc.archive_members(original.read_bytes());out=pathlib.Path(row['path']);replacement=sc.archive_members(out.read_bytes())
  if sha(original)!=row['original_sha256'] or sha(out)!=row['sha256'] or any(sha(pathlib.Path(e['path']))!=e['sha256'] for e in row['source_evidence']):raise ValueError('imaging mapping identity mismatch')
  sources={x:y for x,y in members.items() if x.endswith('.java')};cov=sc.coverage(binary,sources)
  source_root=result_path.parent/('selected-source' if 'imageio' in row['maven_path'] else 'source');selected={str(f.relative_to(source_root)):f.read_bytes() for f in source_root.rglob('*.java')};newcov=sc.coverage(replacement,selected)
  if newcov['unmapped']:raise ValueError('selected class lacks owned source')
  original_classes=set(x for x in binary if x.endswith('.class'));new_classes=set(x for x in replacement if x.endswith('.class'));omitted=sorted(original_classes-new_classes)
  references=[]
  needles=[n[:-6].encode() for n in omitted]
  for jar in sorted((root/'baseline-libs').glob('*.jar')):
   if jar==original:continue
   with zipfile.ZipFile(jar) as z:
    for name in z.namelist():
     if not name.endswith(('.class','.xml','.properties')):continue
     b=z.read(name);hits=[n.decode() for n in needles if n in b or n.replace(b'/',b'.') in b]
     if hits:references.append({'jar':jar.name,'member':name,'references':hits})
  selected_native=[n for n in replacement if n.endswith(('.so','.dll','.dylib'))]
  direct_native_refs=[n for n,b in replacement.items() if n.endswith('.class') and b'com/sun/medialib/codec/jiio/' in b]
  if selected_native or direct_native_refs:raise ValueError('closed codecLib native reintroduction')
  source_notices=sc.notices(members)
  file_headers=[]
  for name,data in sorted(sources.items()):
   m=re.search(rb'^package\s',data,re.M);header=data[:m.start()] if m else data
   file_headers.append({'path':name,'source_sha256':hashlib.sha256(data).hexdigest(),'header_sha256':hashlib.sha256(header).hexdigest(),'header_bytes':len(header),'terms_family':('JJ2000 conforming-product restriction' if b'JJ2000 Partners' in header else 'GPL-2.0-only with Classpath exception' if b'Classpath' in header else 'Sun BSD with nuclear disclaimer' if b'nuclear facility' in header else 'review exact retained header')})
  record={'original':file(original),'variant':file(out),'source_archive':file(archive),'original_source_coverage':cov,'variant_source_coverage':newcov,'source_notices':source_notices,'source_file_header_notices':file_headers,'omitted_classes':omitted,'added_classes':sorted(new_classes-original_classes),'other_war_library_references_to_omitted_classes':references,'variant_native_members':selected_native,'variant_direct_codecLib_class_references':direct_native_refs,'original_service_registrations':{n:b.decode(errors='replace') for n,b in binary.items() if n.startswith('META-INF/services/')},'variant_service_registrations':{n:b.decode(errors='replace') for n,b in replacement.items() if n.startswith('META-INF/services/')}}
  report=o/(r['identity']+'-inventory.json');report.write_text(json.dumps(record,indent=2)+'\n');records.append({'variant_id':r['identity'],'inventory':file(report),'original_source_classes':cov['mapped_class_count'],'original_classes':cov['class_count'],'variant_source_classes':newcov['mapped_class_count'],'variant_classes':newcov['class_count'],'omitted_classes':len(omitted),'other_library_reference_count':len(references),'notices':len(source_notices)})
 summary={'records':records,'scope':'Component provenance and static closure only; functional receipts and rights review separate.'};(o/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
