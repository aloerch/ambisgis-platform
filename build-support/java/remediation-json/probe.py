#!/usr/bin/env python3
"""Focused baseline/adapter contracts, native writer selection, and exact-WAR mode."""
import argparse,hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace-root',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--war',type=Path);p.add_argument('--war-sha256');a=p.parse_args()
 root=a.workspace_root.resolve();build=a.build.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 result={'schema_version':1,'status':'failed','recipe_sha256':sha(Path(__file__)),'commands':[],'scope':'Selected adapter contracts; aggregate HTTP acceptance remains separate'}
 try:
  build_result=json.loads((build/'result.json').read_text());entry=build_result['replacements'][0];artifact=Path(entry['replacement_path'])
  if sha(artifact)!=entry['replacement_sha256']:raise ValueError('Changed adapter artifact')
  for folder in ['classes','home','tmp']:(out/folder).mkdir()
  baseline=root/'build-worktrees/java-gmt-remediation/source/baseline-libs';originals=sorted(baseline.glob('*.jar'));assert len(originals)==369
  selected=[artifact if x.name=='json-lib-2.4.2-geoserver.jar' else x for x in originals]
  if a.war:
   if not a.war_sha256 or sha(a.war)!=a.war_sha256:raise ValueError('WAR hash required and must match')
   (out/'war-libs').mkdir();selected=[]
   with zipfile.ZipFile(a.war) as archive:
    for name in archive.namelist():
     if name.startswith('WEB-INF/lib/') and name.endswith('.jar'):
      target=out/'war-libs'/Path(name).name;target.write_bytes(archive.read(name));selected.append(target)
   result['war']={'path':str(a.war),'sha256':a.war_sha256}
  import inventory
  inspection=inventory.inspect_jars(build,selected)
  (out/'selected-runtime.json').write_text(json.dumps(inspection,indent=2)+'\n')
  if not inspection['passed']:raise ValueError('Runtime definitions differ')
  result['selected_runtime_sha256']=sha(out/'selected-runtime.json')
  result['runtime_inputs']=[{'path':str(x),'sha256':sha(x)} for x in selected]
  old_control=inventory.inspect_jars(build,originals)
  result['old_runtime_negative_control']={'passed':not old_control['passed'] and bool(old_control['old_class_matches']),'errors':old_control['errors'],'old_matches':len(old_control['old_class_matches'])}
  if not result['old_runtime_negative_control']['passed']:raise ValueError('Old runtime negative control was not detected')
  jdk=root/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1';env={'PATH':str(jdk/'bin')+':/usr/bin:/bin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
  def require_success(name,exit_code):
   if exit_code:raise ValueError(name+' failed')
  def invoke(name,command,required=True):
   cmd=[sys.executable,str(HERE.parent.parent/'postgis/offline_exec.py'),'--evidence',str(out/(name+'-network.json')),'--',*map(str,command)]
   with (out/(name+'.log')).open('xb') as log:proc=subprocess.run(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
   n=json.loads((out/(name+'-network.json')).read_text());ps={x['family']:x for x in n.get('probes',[]) if x['operation']=='socket(SOCK_STREAM)'}
   okay=n.get('status')=='completed' and n.get('command_exit_code')==proc.returncode and all(ps.get(f,{}).get('passed') and ps[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
   result['commands'].append({'name':name,'command':cmd,'exit_code':proc.returncode,'network_verified':bool(okay),'log_sha256':sha(out/(name+'.log'))})
   if not okay:raise ValueError(name+' network proof failed')
   if required:require_success(name,proc.returncode)
   return proc.returncode
  cp=lambda xs:':'.join(map(str,xs))
  junit=root/'build-worktrees/geonode-role-propagation/aggregate-repaired-02/fresh-m2/junit/junit/4.13.2/junit-4.13.2.jar'
  donor=root/'build-worktrees/java-gmt-remediation/source/build-01/source/json/src/test/java/net/sf/json/util'
  native=[donor/'TestJSONBuilder.java',donor/'TestJSONStringer.java']
  wfs_native=root/'build-worktrees/java-gmt-remediation/aggregate-02/work/source/geoserver/src/wfs/src/test/java/org/geoserver/wfs/json/GeoJSONBuilderTest.java'
  result['native_source_terms']=[{'path':str(x),'sha256':sha(x),'scope':'Unmodified 4 non-function methods each; file explicitly Apache-2.0 and Andres Almiray attribution, no JSON.org attribution'} for x in native]
  fixture=HERE.parent/'remediation-source/SourceContracts.java';sources=[fixture,HERE/'JsonContracts.java',HERE/'NativeSelection.java',HERE/'LoadedOrigins.java',HERE/'LegacyObservations.java',wfs_native,*native]
  result['test_sources']=[{'path':str(x),'sha256':sha(x)} for x in sources]
  invoke('fixture-compile',[jdk/'bin/javac','--release','17','-proc:none','-encoding','UTF-8','-cp',cp([*originals,junit]),'-d',out/'classes',*sources])
  production_classes=set()
  for jar in selected:
   with zipfile.ZipFile(jar) as archive:production_classes.update(name for name in archive.namelist() if name.endswith('.class'))
  fixture_classes=sorted(str(x.relative_to(out/'classes')) for x in (out/'classes').rglob('*.class'))
  if any(name in production_classes for name in fixture_classes):raise ValueError('Fixture class shadows selected production definition')
  result['fixture_class_non_shadowing']={'passed':True,'compiled_fixture_classes':fixture_classes,'selected_production_classes':len(production_classes)}
  for label,jars in [('baseline',originals),('variant',selected)]:
   invoke('retained213-'+label,[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'classes',*jars]),'SourceContracts','json'])
   invoke('changed-common-'+label,[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'classes',*jars]),'JsonContracts'])
   invoke('legacy-observations-'+label,[jdk/'bin/java','-cp',cp([out/'classes',*jars]),'LegacyObservations'])
   hamcrest=root/'build-worktrees/geonode-role-propagation/aggregate-repaired-02/fresh-m2/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'
   invoke('native-geoserver-wfs-'+label,[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'classes',*jars,junit,hamcrest]),'org.junit.runner.JUnitCore','org.geoserver.wfs.json.GeoJSONBuilderTest'])
   invoke('native-selected-'+label,[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'classes',*jars,junit]),'NativeSelection'])
  invoke('loaded-origin-variant',[jdk/'bin/java','-cp',cp([out/'classes',*selected]),'LoadedOrigins',inspection['variant_artifacts'][0]['jar']])
  invoke('changed-safety-variant',[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'classes',*selected]),'JsonContracts','safety'])
  markers=lambda text:[line for line in text.splitlines() if line.startswith(('builder-depth:','json-contracts='))]
  result['retained_213_output_equal']=markers((out/'retained213-baseline.log').read_text())==markers((out/'retained213-variant.log').read_text())
  if not result['retained_213_output_equal']:raise ValueError('Retained contract/depth output changed')
  bad_build=root/'build-worktrees/json-jpeg2000-remediation/json/build-03'
  bad_record=json.loads((bad_build/'result.json').read_text())['replacements'][0];bad_artifact=Path(bad_record['replacement_path'])
  if sha(bad_artifact)!=bad_record['replacement_sha256']:raise ValueError('Changed retained regression control artifact')
  bad_jars=[bad_artifact if x.name=='json-lib-2.4.2-geoserver.jar' else x for x in originals]
  exit_code=invoke('negative-native-regression',[jdk/'bin/java','-Djava.awt.headless=true','-cp',cp([out/'classes',*bad_jars,junit,hamcrest]),'org.junit.runner.JUnitCore','org.geoserver.wfs.json.GeoJSONBuilderTest'],required=False)
  detected=False
  try:require_success('negative-native-regression',exit_code)
  except ValueError:detected=True
  result['native_failure_negative_control']={'passed':detected and exit_code==1,'artifact_sha256':bad_record['replacement_sha256'],'exit_code':exit_code,'expected_failure':'The two preserved UUID native regressions must make require_success fail; this command is a deliberate negative control.'}
  if not result['native_failure_negative_control']['passed']:raise ValueError('Native failure negative control failed')
  result['known_historical_native_failures']={'fresh_reexecution':False,'cases':['testElement_Collection2_exclusions_ignoreDefault','testElement_Bean_exclusions_ignoreDefault'],'reason':'BeanUtils class introspection suppression; safe behavior independently asserted in changed-common'}
  for entry in result['runtime_inputs']+result['test_sources']:
   if sha(Path(entry['path']))!=entry['sha256']:raise ValueError('Runtime/test input changed during probe')
  if a.war and sha(a.war)!=a.war_sha256:raise ValueError('WAR changed during probe')
  if sha(Path(__file__))!=result['recipe_sha256']:raise ValueError('Probe recipe changed during execution')
  result['retained_runtime_and_test_inputs_unchanged']=True
  result['status']='passed-selected-profile-contracts'
 except Exception as e:result['error']=str(e)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(out),'error':result.get('error')}));return 0 if result['status']=='passed-selected-profile-contracts' else 1
if __name__=='__main__':raise SystemExit(main())
