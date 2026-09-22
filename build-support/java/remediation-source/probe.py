#!/usr/bin/env python3
"""Focused differential API, actual parser/proxy/weaving and donor-native probes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace-root',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 root=a.workspace_root.resolve();build=a.build.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 result={'schema_version':1,'scope':'Focused source component probes; final deployed WAR/GeoFence/PostgreSQL/HTTP acceptance separate','status':'failed','build_result_sha256':sha(build/'result.json'),'commands':[],'assertions':[]}
 try:
  r=json.loads((build/'result.json').read_text());assert r['status']=='built-focused-probes-pending'
  replacement={x['original_maven_path'].split('/')[-1]:Path(x['replacement_path']) for x in r['replacements']}
  for x in r['replacements']:
   if sha(Path(x['replacement_path']))!=x['replacement_sha256']:raise ValueError('Changed variant artifact')
  jdk=root/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1'
  baseline=root/'build-worktrees/java-gmt-remediation/source/baseline-libs'
  jars=sorted(baseline.glob('*.jar'));assert len(jars)==369
  original_cp=list(jars);variant_cp=[replacement.get(j.name,j) for j in jars]
  junit=root/'build-worktrees/geonode-role-propagation/aggregate-repaired-02/fresh-m2/junit/junit/4.13.2/junit-4.13.2.jar'
  xmlunit=root/'build-worktrees/geonode-role-propagation/aggregate-repaired-02/fresh-m2/xmlunit/xmlunit/1.6/xmlunit-1.6.jar'
  (out/'classes').mkdir();(out/'home').mkdir();(out/'tmp').mkdir()
  env={'PATH':str(jdk/'bin')+':/usr/bin:/bin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
  def invoke(name,cmd,expected=0):
   full=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(out/(name+'-network.json')),'--',*map(str,cmd)]
   with (out/(name+'.log')).open('xb') as log:q=subprocess.run(full,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
   n=json.loads((out/(name+'-network.json')).read_text());probes={x['family']:x for x in n.get('probes',[]) if x['operation']=='socket(SOCK_STREAM)'}
   ok=n.get('status')=='completed' and n.get('command_exit_code')==q.returncode and all(probes.get(f,{}).get('passed') and probes[f]['errno']==1 for f in ['AF_INET','AF_INET6'])
   result['commands'].append({'name':name,'command':full,'exit_code':q.returncode,'network_verified':ok,'log_sha256':sha(out/(name+'.log'))})
   if not ok:raise ValueError(name+' network proof failed')
   if expected is not None and q.returncode!=expected:raise ValueError(name+' failed')
   return q.returncode
  cp=lambda paths:':'.join(map(str,paths))
  invoke('fixture-compile',[jdk/'bin/javac','--release','7','-proc:none','-cp',cp(original_cp),'-d',out/'classes',HERE/'SourceContracts.java',HERE/'AspectJApi.java',*sorted((HERE/'weaving').glob('*.java'))])
  for name in ['json','xml','proxy']:
   for label,paths in [('baseline',original_cp),('variant',variant_cp)]:
    invoke(name+'-'+label,[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'classes',*paths]),'SourceContracts',name],expected=None)
   before=(out/(name+'-baseline.log')).read_text();after=(out/(name+'-variant.log')).read_text()
   # Ignore logger timestamps only; assertions and all contract output must agree.
   selected=lambda t:[line for line in t.splitlines() if line.startswith(('builder-depth:','json-contracts=','xml-contracts=','xml-provider=','aspectj-proxy-contracts='))]
   commands=result['commands'][-2:];passed=all(x['exit_code']==0 for x in commands) and selected(before)==selected(after)
   result['assertions'].append({'name':name+'-differential','passed':passed,'baseline':selected(before),'variant':selected(after)})
  for original in ['json-lib-2.4.2-geoserver.jar','xmlpull-1.1.3.1.jar','aspectjweaver-1.5.4.jar']:
   with zipfile.ZipFile(baseline/original) as z:names=[n[:-6].replace('/','.') for n in sorted(z.namelist()) if n.endswith('.class') and '$' not in n and not n.startswith('com/bea/') and 'JRockitAgent' not in n]
   for label,paths in [('baseline',original_cp),('variant',variant_cp)]:invoke(original+'-'+label+'-api',[jdk/'bin/javap','-public','-classpath',cp(paths),*names])
   identical=(out/(original+'-baseline-api.log')).read_bytes()==(out/(original+'-variant-api.log')).read_bytes()
   result['assertions'].append({'name':original+'-public-api-identical','passed':identical,'required':not original.startswith('aspectj')})
  invoke('aspectj-effective-api',[jdk/'bin/java','-cp',out/'classes','AspectJApi',baseline/'aspectjweaver-1.5.4.jar',cp([*original_cp,build/'deps/regexp.jar']),cp([*variant_cp,build/'deps/regexp.jar'])])
  result['assertions'].append({'name':'aspectj-effective-public-api','passed':True})
  # AspectJ 1.5.4 supports legacy classfiles. The failed Java7 stackmap witness is
  # retained separately in probe-01; compile a genuine Java5 target, never disable
  # the verifier or edit classfile version bytes. ECJ source/terms are retained.
  ecj=root/'build-worktrees/java-gmt-remediation/source/recovery/ac0ba5876eaf7ebb47749a0d1be179c51f194b9dd0b875d1c09e1b530f5a2db5'
  if sha(ecj)!='ac0ba5876eaf7ebb47749a0d1be179c51f194b9dd0b875d1c09e1b530f5a2db5':raise ValueError('ECJ differs')
  invoke('legacy-fixture-compile',[jdk/'bin/java','-jar',ecj,'-source','1.5','-target','1.5','-proc:none','-cp',cp(original_cp),'-d',out/'classes',*sorted((HERE/'weaving').glob('*.java'))])
  # Actual load-time class transformation of the explicitly supported legacy fixture.
  meta=out/'classes/META-INF';meta.mkdir()
  (meta/'aop.xml').write_text('<aspectj><aspects><aspect name="remediation.weaving.WitnessAspect"/></aspects><weaver options="-showWeaveInfo"><include within="remediation.weaving..*"/></weaver></aspectj>\n')
  for label,paths,agent in [('baseline',original_cp,baseline/'aspectjweaver-1.5.4.jar'),('variant',variant_cp,replacement['aspectjweaver-1.5.4.jar'])]:
   rc=invoke('weaving-'+label,[jdk/'bin/java','--add-opens=java.base/java.lang=ALL-UNNAMED','-javaagent:'+str(agent),'-cp',cp([out/'classes',*paths]),'remediation.weaving.Main'],expected=None)
   result['assertions'].append({'name':'actual-load-time-weaving-'+label,'passed':rc==0})
  # Donor native JSON tests are executed unchanged; optional XML cases use retained XMLUnit.
  tests=build/'source/json/src/test/java';native=list(tests.rglob('*.java'))
  native_cp=[replacement['json-lib-2.4.2-geoserver.jar'],*sorted((build/'deps').glob('*.jar')),xmlunit]
  sources=out/'native-sources.txt';sources.write_text('\n'.join(map(str,sorted(native)))+'\n')
  rc=invoke('json-native-compile',[jdk/'bin/javac','--release','7','-proc:none','-encoding','UTF-8','-cp',cp(native_cp),'-d',out/'native-classes','@'+str(sources)],expected=None)
  if rc==0:
   names=['net.sf.json.util.TestJSONBuilder','net.sf.json.util.TestJSONTokener','net.sf.json.util.TestJSONUtils','net.sf.json.TestJSONArray','net.sf.json.TestJSONObject','net.sf.json.TestJSONSerializer']
   for name in names:
    rc=invoke('native-'+name,[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'native-classes',build/'source/json/src/test/resources',*native_cp]),'junit.textui.TestRunner',name],expected=None)
    record={'name':'native-'+name,'passed':rc==0}
    if rc:
     baseline_native=[baseline/'json-lib-2.4.2-geoserver.jar',*sorted((build/'deps').glob('*.jar')),xmlunit]
     brc=invoke('native-baseline-'+name,[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'native-classes',build/'source/json/src/test/resources',*baseline_native]),'junit.textui.TestRunner',name],expected=None)
     failures=lambda text:[line for line in text.splitlines() if line.startswith(('1) ','2) ','Tests run:'))]
     unchanged=brc==rc and failures((out/('native-'+name+'.log')).read_text())==failures((out/('native-baseline-'+name+'.log')).read_text())
     record.update(inherited_failure_reproduced=unchanged,required=not unchanged)
    result['assertions'].append(record)
  else:result['assertions'].append({'name':'json-native-compilation','passed':False})
  # Verify no duplicate API/runtime classes across replacement jars and no BEA references.
  definitions={};bad=[]
  for file in replacement.values():
   with zipfile.ZipFile(file) as z:
    for n in z.namelist():
     if n.endswith('.class'):
      if n in definitions:bad.append('duplicate:'+n)
      definitions[n]=str(file)
      if b'com/bea/jvm' in z.read(n) or 'JRockitAgent' in n:bad.append('JRockit:'+n)
  result['assertions'].append({'name':'no-duplicate-replacement-or-BEA-definitions','passed':not bad,'errors':bad})
  result['status']='passed-with-recorded-inherited-limitations' if all(x['passed'] for x in result['assertions'] if x.get('required',True)) else 'failed'
 except Exception as exc:result['error']=str(exc)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(out),'error':result.get('error')}));return 0 if result['status']=='passed-with-recorded-inherited-limitations' else 1
if __name__=='__main__':raise SystemExit(main())
