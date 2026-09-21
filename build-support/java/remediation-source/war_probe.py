#!/usr/bin/env python3
"""Run parser, serialization, AspectJ proxy/advice and legacy weaving from exact WAR.

No global or adjacent application library is on a test classpath. This focused
classpath probe complements, and never replaces, deployment/HTTP/persistence tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['workspace-root','war','component-build','output']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--war-sha256',required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 result={'schema_version':1,'status':'failed','scope':'Exact-WAR extracted-library focused component probe; actual deployed HTTP and database acceptance separate','commands':[],'assertions':[],'fixture_sources':[{'path':str(x),'sha256':sha(x.read_bytes())} for x in [HERE/'SourceContracts.java',*sorted((HERE/'weaving').glob('*.java'))]]}
 try:
  data=a.war.read_bytes()
  if sha(data)!=a.war_sha256:raise ValueError('WAR hash differs')
  result['war']={'path':str(a.war.resolve()),'sha256':sha(data)}
  build=json.loads((a.component_build/'result.json').read_text())
  if build['status']!='built-focused-probes-pending':raise ValueError('Component build failed')
  expected={Path(r['original_maven_path']).name:r for r in build['replacements']}
  for d in ['lib','classes','home','tmp']:(out/d).mkdir()
  with zipfile.ZipFile(a.war) as z:
   names=z.namelist()
   if len(names)!=len(set(names)):raise ValueError('Duplicate WAR archive members')
   selected=[n for n in names if n.startswith('WEB-INF/lib/') and n.endswith('.jar')]
   for n in selected:
    target=out/'lib'/Path(n).name
    if target.exists():raise ValueError('Duplicate library basename')
    target.write_bytes(z.read(n))
  libs=sorted((out/'lib').glob('*.jar'));result['libraries']=[{'path':x.name,'sha256':sha(x.read_bytes())} for x in libs]
  for name,r in expected.items():
   artifact=out/'lib'/name
   if sha(artifact.read_bytes())!=r['replacement_sha256']:raise ValueError('WAR replacement differs: '+name)
   if sha(Path(r['source_manifest_path']).read_bytes())!=r['source_manifest_sha256']:raise ValueError('Component source manifest changed')
  # All selected target class definitions must have exactly one origin.
  owned={}
  for path in libs:
   with zipfile.ZipFile(path) as z:
    for n in z.namelist():
     if n.endswith('.class') and (n.startswith('org/aspectj/') or n.startswith('org/xmlpull/v1/') or n.startswith('net/sf/json/')):
      if n in owned:raise ValueError('Duplicate target class '+n)
      owned[n]=path.name
  result['target_class_origins']=owned
  jdk=a.workspace_root/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1'
  import sys as _sys
  _sys.path.insert(0,str(HERE.parent))
  import toolchain
  result['toolchain']=toolchain.verify_extracted(a.workspace_root/'source-archives/java-resolution/toolchain',json.loads((HERE.parent/'toolchain-inputs.json').read_text()),jdk.parent)
  env={'PATH':str(jdk/'bin')+':/usr/bin:/bin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
  def invoke(name,cmd):
   command=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(out/(name+'-network.json')),'--',*map(str,cmd)]
   with (out/(name+'.log')).open('xb') as log:r=subprocess.run(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
   n=json.loads((out/(name+'-network.json')).read_text());probes={x['family']:x for x in n.get('probes',[]) if x['operation']=='socket(SOCK_STREAM)'}
   valid=n.get('status')=='completed' and n.get('command_exit_code')==r.returncode and all(probes.get(f,{}).get('passed') is True and probes[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
   result['commands'].append({'name':name,'command':command,'exit_code':r.returncode,'network_verified':valid,'log_sha256':sha((out/(name+'.log')).read_bytes())})
   if not valid or r.returncode:raise ValueError(name+' failed')
  cp=':'.join(map(str,libs));fixture_cp=str(out/'classes')+':'+cp
  invoke('compile',[jdk/'bin/javac','--release','7','-proc:none','-encoding','UTF-8','-cp',cp,'-d',out/'classes',HERE/'SourceContracts.java'])
  for name in ['json','xml','proxy']:
   invoke(name,[jdk/'bin/java','-Djava.awt.headless=true','-cp',fixture_cp,'SourceContracts',name]);result['assertions'].append({'name':name,'passed':True})
  ecj=a.workspace_root/'build-worktrees/java-gmt-remediation/source/recovery/ac0ba5876eaf7ebb47749a0d1be179c51f194b9dd0b875d1c09e1b530f5a2db5'
  if sha(ecj.read_bytes())!=ecj.name:raise ValueError('ECJ fixture compiler differs')
  invoke('legacy-fixture-compile',[jdk/'bin/java','-jar',ecj,'-source','1.5','-target','1.5','-proc:none','-cp',cp,'-d',out/'classes',*sorted((HERE/'weaving').glob('*.java'))])
  meta=out/'classes/META-INF';meta.mkdir();(meta/'aop.xml').write_text('<aspectj><aspects><aspect name="remediation.weaving.WitnessAspect"/></aspects><weaver options="-showWeaveInfo"><include within="remediation.weaving..*"/></weaver></aspectj>\n')
  invoke('legacy-weaving',[jdk/'bin/java','--add-opens=java.base/java.lang=ALL-UNNAMED','-javaagent:'+str(out/'lib/aspectjweaver-1.5.4.jar'),'-cp',fixture_cp,'remediation.weaving.Main'])
  result['assertions'].append({'name':'real-legacy-bytecode-weaving','passed':True,'limitation':'Java5 target fixture; baseline and variant both fail Java7 target stackmap verification, preserved in source/probe-01.'})
  if sha(a.war.read_bytes())!=a.war_sha256:raise ValueError('WAR changed during probe')
  for lib in result['libraries']:
   if sha((out/'lib'/lib['path']).read_bytes())!=lib['sha256']:raise ValueError('Extracted library changed')
  result['status']='passed'
 except Exception as exc:result['error']=str(exc)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(out),'error':result.get('error')}));return 0 if result['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
