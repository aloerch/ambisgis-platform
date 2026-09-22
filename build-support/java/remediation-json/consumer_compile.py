#!/usr/bin/env python3
"""Compile actual selected JSON consumers, including reactor tests, against the new API.

This bounded source/API check uses retained parent dependencies and compiled helper
classes. It does not replace a fresh Maven aggregate or execute native tests.
"""
import argparse, hashlib, json, os, subprocess, sys, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def record(p):return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--workspace-root',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();root=a.workspace_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 result={'schema_version':1,'status':'failed','recipe':record(Path(__file__)),'scope':'Actual selected source compilation only, not test execution or aggregate acceptance','commands':[]}
 try:
  component=json.loads((a.build/'result.json').read_text())['replacements'][0];artifact=Path(component['replacement_path'])
  if sha(artifact)!=component['replacement_sha256']:raise ValueError('Changed component artifact')
  parent=root/'build-worktrees/java-gmt-remediation/aggregate-02';src=parent/'work/source'
  scope=root/'build-worktrees/json-jpeg2000-remediation/json/scope-01.json';j=json.loads(scope.read_text())
  result['parent_scope']=record(scope);result['component']=record(a.build/'result.json')
  sources=[]
  for entry in j['source_references']:
   source=src/entry['path']
   if source.suffix!='.java':continue
   for kind in ['main','test']:
    delim='/src/'+kind+'/java/'
    if delim not in str(source):continue
    prefix,relative=str(source).split(delim,1);compiled=Path(prefix)/'target'/('classes' if kind=='main' else 'test-classes')/relative.replace('.java','.class')
    if not compiled.is_file():continue
    if sha(source)!=entry['sha256']:raise ValueError('Selected source changed: '+str(source))
    target=out/'retained-source'/entry['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
    sources.append((kind,target));break
  if sum(k=='main' for k,_ in sources)!=25 or sum(k=='test' for k,_ in sources)!=69:raise ValueError('Selected source count changed')
  result['source_counts']={k:sum(t==k for t,_ in sources) for k in ['main','test']}
  result['sources']=[{'kind':k,**record(s)} for k,s in sources]
  current=root/'build-worktrees/json-jpeg2000-remediation/aggregate-02/work/source/geoserver/src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/ImportJSONReader.java'
  importer=src/'geoserver/src/extension/importer/rest/src/main/java/org/geoserver/importer/rest/converters/ImportJSONReader.java'
  if sha(importer)!=sha(current):raise ValueError('Failed aggregate importer source differs from consumer probe')
  result['failed_aggregate_importer_source']=record(current)
  baseline=sorted((root/'build-worktrees/java-gmt-remediation/source/baseline-libs').glob('*.jar'))
  old=[x for x in baseline if x.name=='json-lib-2.4.2-geoserver.jar'];assert len(old)==1 and len(baseline)==369
  jars=[x for x in baseline if x not in old];digests={sha(x) for x in jars};excluded=[]
  for jar in sorted((parent/'fresh-m2').rglob('*.jar')):
   digest=sha(jar)
   if digest in digests:continue
   with zipfile.ZipFile(jar) as z:
    if any(n.startswith('net/sf/json/') and n.endswith('.class') for n in z.namelist()):excluded.append(record(jar));continue
   jars.append(jar);digests.add(digest)
  # The selected GeoTools parent declares Hamcrest 3.0; older Maven-plugin
  # dependencies in the retained repository must not win this test classpath.
  hamcrest=parent/'fresh-m2/org/hamcrest/hamcrest/3.0/hamcrest-3.0.jar'
  if not hamcrest.is_file():raise ValueError('Missing selected native Hamcrest')
  jars=[hamcrest,*[x for x in jars if x!=hamcrest]]
  dirs=sorted((parent/'work/source').rglob('target/test-classes'))
  for folder in dirs:
   if (folder/'net/sf/json').exists():raise ValueError('Old implementation in test helpers')
  result['classpath_jars']=[record(x) for x in jars];result['excluded_json_implementation_jars']=excluded
  helper_manifest=[]
  for folder in dirs:
   for member in sorted(folder.rglob('*.class')):helper_manifest.append(record(member))
  (out/'helper-class-manifest.json').write_text(json.dumps(helper_manifest,indent=2)+'\n');result['helper_class_manifest']=record(out/'helper-class-manifest.json')
  jdk=root/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1'
  for name in ['home','tmp']:(out/name).mkdir()
  env={'PATH':str(jdk/'bin')+':/usr/bin:/bin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
  def compile(label,first,negative=False):
   target=out/(label+'-classes');target.mkdir();args=['--release','17','-proc:none','-implicit:none','-encoding','UTF-8','-cp',':'.join(map(str,[first,*jars,*dirs])),'-d',str(target),*map(str,[s for _,s in sources])]
   argfile=out/(label+'-arguments.txt');argfile.write_text('\n'.join(json.dumps(s) for s in args)+'\n')
   cmd=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(out/(label+'-network.json')),'--',str(jdk/'bin/javac'),'@'+str(argfile)]
   with (out/(label+'.log')).open('xb') as log:proc=subprocess.run(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
   n=json.loads((out/(label+'-network.json')).read_text());ps={x['family']:x for x in n.get('probes',[]) if x['operation']=='socket(SOCK_STREAM)'}
   verified=n.get('status')=='completed' and n.get('command_exit_code')==proc.returncode and all(ps.get(f,{}).get('passed') and ps[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
   result['commands'].append({'name':label,'command':cmd,'exit_code':proc.returncode,'network_verified':bool(verified),'arguments':record(argfile),'log':record(out/(label+'.log'))})
   if not verified:raise ValueError('Network evidence failed')
   if negative:
    text=(out/(label+'.log')).read_text();passed=proc.returncode==1 and 'ImportJSONReader.java:479' in text and 'cannot be converted to Map<String,Object>' in text
    result['previous_adapter_negative_control']={'passed':passed,'artifact':record(first)}
    if not passed:raise ValueError('Prior generics regression not detected')
   elif proc.returncode:raise ValueError(label+' compile failed')
  compile('baseline',old[0]);compile('variant',artifact)
  previous=json.loads((root/'build-worktrees/json-jpeg2000-remediation/json/build-06/result.json').read_text())['replacements'][0]
  prior=Path(previous['replacement_path'])
  if sha(prior)!=previous['replacement_sha256']:raise ValueError('Changed prior regression artifact')
  compile('prior-generics-negative',prior,negative=True)
  for entry in result['classpath_jars']+helper_manifest:
   if sha(Path(entry['path']))!=entry['sha256']:raise ValueError('Retained compile input changed')
  result['status']='passed-selected-consumer-compilation'
 except Exception as e:result['error']=str(e)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(out),'error':result.get('error')}));return 0 if result['status']=='passed-selected-consumer-compilation' else 1
if __name__=='__main__':raise SystemExit(main())
