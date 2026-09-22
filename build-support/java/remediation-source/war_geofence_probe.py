#!/usr/bin/env python3
"""Rerun actual GeoFence DAO tests and transactions on exact-WAR production jars."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import geofence_fixture
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
GF='geofence-132a1d16901b7039f974c8c30d7e7df042d8af4c/src/services/core'

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['workspace-root','war','native-build','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--war-sha256',required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);db=None
 r={'schema_version':1,'status':'failed','scope':'Fresh PostgreSQL GeoFence tests with exact-WAR production jars and retained JUnit/Hamcrest test-only dependencies','commands':[],'recipe_sha256':sha(Path(__file__))}
 try:
  if sha(a.war)!=a.war_sha256:raise ValueError('WAR differs')
  r['war']={'path':str(a.war),'sha256':a.war_sha256}
  native=json.loads((a.native_build/'result.json').read_text());r['native_build_sha256']=sha(a.native_build/'result.json')
  if native['result_exit_code']!=0 or not native['network_denial_verified']:raise ValueError('Native inputs failed')
  gf=a.native_build/'work/source'/GF;test_source=gf/'persistence-pg-test/target/test-classes'
  shutil.copytree(test_source,out/'test-classes');(out/'lib').mkdir();(out/'home').mkdir();(out/'tmp').mkdir()
  with zipfile.ZipFile(a.war) as z:
   for n in z.namelist():
    if n.startswith('WEB-INF/lib/') and n.endswith('.jar'):(out/'lib'/Path(n).name).write_bytes(z.read(n))
  libs=sorted((out/'lib').glob('*.jar'));production_classes=set()
  for lib in libs:
   with zipfile.ZipFile(lib) as z:production_classes.update(n for n in z.namelist() if n.endswith('.class'))
  for f in (out/'test-classes').rglob('*.class'):
   if str(f.relative_to(out/'test-classes')) in production_classes:raise ValueError('Test class shadows production class')
  # Recover the exact unmodified fixture property file, then let the established
  # helper rewrite only the fresh AF_UNIX connection for a fresh owned cluster.
  prop=out/'fixture-source'/GF/'persistence-pg-test/src/test/resources/geofence-datasource-ovr.properties';prop.parent.mkdir(parents=True)
  original=(gf/'persistence-pg-test/src/test/resources/geofence-datasource-ovr.properties').read_text()
  original=re.sub(r'jdbc:postgresql://localhost/geofence_test\?[^\r\n]+','jdbc:postgresql://localhost:5432/geofence_test',original)
  prop.write_text(original)
  if sha(prop)!='bb83786e244520be34397b8a89d5b7e48eddbcb4010072259119b263ca479c56':raise ValueError('Original fixture recovery differs')
  db,r['postgres_fixture']=geofence_fixture.start(a.workspace_root/'build-worktrees/postgis-slice/run-003/prefix',a.workspace_root/'build-worktrees/postgis-slice/run-003-evidence-final.json',out,out/'fixture-source')
  shutil.copyfile(prop,out/'test-classes/geofence-datasource-ovr.properties')
  tests=sorted({ET.parse(x).getroot().attrib['name'] for x in (gf/'persistence-pg-test/target/surefire-reports').glob('TEST*.xml')})
  extras=[a.native_build/'fresh-m2/junit/junit/4.13/junit-4.13.jar',a.native_build/'fresh-m2/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar']
  # Only explicitly retained test frameworks supplement the exact production jars.
  rows={x['maven_path']:x for x in json.loads((a.native_build/'retained-inputs.json').read_text())}
  for extra in extras:
   rel=str(extra.relative_to(a.native_build/'fresh-m2'))
   if sha(extra)!=rows[rel]['sha256']:raise ValueError('Test dependency differs')
   with zipfile.ZipFile(extra) as z:
    if any(n in production_classes for n in z.namelist() if n.endswith('.class')):raise ValueError('Test jar shadows WAR classes')
  r['classpath']=[{'path':str(x),'sha256':sha(x)} for x in [*libs,*extras]]
  r['test_class_inputs']=[{'path':str(x.relative_to(out)),'sha256':sha(x)} for x in sorted((out/'test-classes').rglob('*')) if x.is_file()]
  r['fixture_java']={'path':str(HERE/'GeofenceWarTests.java'),'sha256':sha(HERE/'GeofenceWarTests.java')}
  jdk=a.workspace_root/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1';cp=':'.join(map(str,[out/'test-classes',*libs,*extras]));env={'PATH':str(jdk/'bin')+':/usr/bin:/bin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
  def invoke(name,cmd):
   full=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(out/(name+'-network.json')),'--',*map(str,cmd)]
   with (out/(name+'.log')).open('xb') as log:q=subprocess.run(full,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
   n=json.loads((out/(name+'-network.json')).read_text());probes={v['family']:v for v in n.get('probes',[]) if v['operation']=='socket(SOCK_STREAM)'}
   ok=n.get('status')=='completed' and n.get('command_exit_code')==q.returncode and all(probes.get(f,{}).get('passed') and probes[f]['errno']==1 for f in ['AF_INET','AF_INET6'])
   r['commands'].append({'name':name,'command':full,'exit_code':q.returncode,'network_verified':ok,'log_sha256':sha(out/(name+'.log'))})
   if not ok or q.returncode:raise ValueError(name+' failed')
  invoke('compile',[jdk/'bin/javac','-proc:none','-cp',cp,'-d',out/'fixture-classes',HERE/'GeofenceWarTests.java'])
  invoke('postgres-tests',[jdk/'bin/java','-Djava.awt.headless=true','-cp',str(out/'fixture-classes')+':'+cp,'GeofenceWarTests',out/'lib',*tests])
  if sha(a.war)!=a.war_sha256:raise ValueError('WAR changed')
  for item in r['classpath']:
   if sha(Path(item['path']))!=item['sha256']:raise ValueError('Classpath input changed')
  r.update(status='passed',native_classes=tests)
 except Exception as e:r['error']=str(e)
 finally:
  if db is not None:
   try:db.stop();r['postgres_cluster_stopped']=True
   except Exception as e:r.update(status='failed',cleanup_error=str(e))
  (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({'status':r['status'],'error':r.get('error'),'output':str(out)}));return 0 if r['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
