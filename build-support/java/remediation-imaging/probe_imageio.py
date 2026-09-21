#!/usr/bin/env python3
"""Inventory real providers and probe retained WAR libraries with selected codec mapping."""
import argparse,hashlib,json,os,pathlib,subprocess,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'build-support/java'))
import source_closure as sc
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=pathlib.Path);p.add_argument('--war',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--replacement',type=pathlib.Path);p.add_argument('--expected-war-sha256');p.add_argument('--mapfish',action='store_true');a=p.parse_args();o=a.output.resolve();o.mkdir(parents=True,exist_ok=False);result={'status':'failed','war':{'path':str(a.war),'sha256':sha(a.war)},'replacement':None,'stages':[]}
 try:
  if a.expected_war_sha256 and result['war']['sha256']!=a.expected_war_sha256:raise ValueError('WAR expected hash mismatch')
  libs=o/'libs';libs.mkdir();members=[]
  with zipfile.ZipFile(a.war) as z:
   for n in sorted(z.namelist()):
    if n.startswith('WEB-INF/lib/') and n.endswith('.jar'):
     b=z.read(n)
     if a.replacement and n=='WEB-INF/lib/jai_imageio-1.1.jar':result['excluded_original']={'path':n,'sha256':hashlib.sha256(b).hexdigest()};continue
     t=libs/pathlib.Path(n).name;t.write_bytes(b);members.append({'path':n,'sha256':sha(t)})
  if a.replacement:
   t=libs/a.replacement.name;t.write_bytes(a.replacement.read_bytes());result['replacement']={'path':str(a.replacement),'sha256':sha(t)}
  result['library_manifest']=members
  renderer=None
  for library in sorted(libs.glob('*.jar')):
   with zipfile.ZipFile(library) as archive:
    if 'sun/java2d/marlin/DMarlinRenderingEngine.class' in archive.namelist():
     mf=archive.read('META-INF/MANIFEST.MF').decode('utf-8')
     if 'Implementation-Title: ambisgis-marlin-0.9.4.8-headless-temurin17-' in mf:
      if renderer is not None:raise ValueError('duplicate renderer variant')
      renderer=library
  result['renderer']=None if renderer is None else {'path':str(renderer),'sha256':sha(renderer)}
  flags=['-Djava.awt.headless=true','-Dsun.java2d.opengl=false']
  if renderer:flags+=['--patch-module','java.desktop='+str(renderer),'-Dsun.java2d.renderer=sun.java2d.marlin.DMarlinRenderingEngine','--add-exports','java.desktop/sun.java2d.pipe=ALL-UNNAMED','--add-exports','java.desktop/sun.java2d.marlin=ALL-UNNAMED','-Dambisgis.witness.renderer='+str(renderer),'-Dambisgis.witness.renderer.sha256='+sha(renderer)]
  java=a.workspace/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1/bin';cp=':'.join(map(str,sorted(libs.glob('*.jar'))))
  def run(stage,cmd,allow_failure=False):
   for d in ['home','tmp']:(o/d).mkdir(exist_ok=True)
   receipt=o/(stage+'-network.json');log=o/(stage+'.log');env={'PATH':str(java)+':/usr/bin:/bin','HOME':str(o/'home'),'TMPDIR':str(o/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
   with log.open('xb') as f:r=subprocess.run([sys.executable,str(ROOT/'build-support/postgis/offline_exec.py'),'--evidence',str(receipt),'--',*map(str,cmd)],cwd=o,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=240)
   n=json.loads(receipt.read_text());probes={x['family']:x for x in n.get('probes',[]) if x.get('operation')=='socket(SOCK_STREAM)'};ok=n.get('status')=='completed' and n.get('command_exit_code')==r.returncode and all(probes.get(f,{}).get('passed') and probes[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
   result['stages'].append(dict(name=stage,command=list(map(str,cmd)),exit_code=r.returncode,log_sha256=sha(log),network_verified=ok))
   if not ok or (r.returncode and not allow_failure):raise ValueError(stage+' failed')
   return r.returncode
  fixtures=[pathlib.Path(__file__).with_name('ImageIOWitness.java'),pathlib.Path(__file__).with_name('RenderingWitness.java')]
  if renderer:
   archive=a.workspace/'source-archives/java-source-closure/blobs/sha256/60fc2008c33f01281ce75dbbfe04c1771ddb9544746ed32c3dbef551ee60270a'
   if sha(archive)!=archive.name:raise ValueError('native renderer fixture source archive changed')
   sources=sc.archive_members(archive.read_bytes());entries=[(n,b) for n,b in sources.items() if n.endswith('/src/main/java/JoinMiterRedundantLineSegmentsTest.java')]
   if len(entries)!=1:raise ValueError('native renderer fixture path ambiguous')
   fixture=o/'JoinMiterRedundantLineSegmentsTest.java';fixture.write_bytes(entries[0][1]);fixtures.extend([fixture,pathlib.Path(__file__).with_name('NativeRenderingWitness.java')])
   result['native_renderer_source']={'archive':str(archive),'archive_sha256':sha(archive),'member':entries[0][0],'sha256':sha(fixture)}
  if a.mapfish:fixtures.append(pathlib.Path(__file__).with_name('MapFishImagingWitness.java'))
  run('compile',[java/'javac','-proc:none','--add-exports','java.desktop/sun.java2d.pipe=ALL-UNNAMED','-cp',cp,'-d',o/'classes',*fixtures])
  run('providers-roundtrip',[java/'java',*flags,'-cp',str(o/'classes')+':'+cp,'ImageIOWitness',o/'fixtures'])
  native_code=0
  if renderer:native_code=run('native-renderer',[java/'java',*flags,'-cp',str(o/'classes')+':'+cp,'NativeRenderingWitness'],allow_failure=True)
  if a.mapfish:run('mapfish',[java/'java',*flags,'-cp',str(o/'classes')+':'+cp,'MapFishImagingWitness',o/'print-fixtures'])
  if sha(a.war)!=result['war']['sha256']:raise ValueError('WAR changed during probes')
  result['fixture_sources']=[{'path':str(f),'sha256':sha(f)} for f in fixtures]
  result['tooling']={'path':str(pathlib.Path(__file__).resolve()),'sha256':sha(pathlib.Path(__file__))}
  result['print_fixtures']=[{'path':str(f.relative_to(o)),'sha256':sha(f)} for f in sorted((o/'print-fixtures').glob('*'))] if a.mapfish else []
  result['native_renderer_failures_preserved']=bool(native_code)
  result['status']='partial-native-renderer-failure' if native_code else 'passed';result['fixtures']=[{'path':str(f.relative_to(o)),'sha256':sha(f)} for f in sorted((o/'fixtures').glob('*'))]
 except Exception as e:result['error']=str(e)
 (o/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(o)}));return result['status']!='passed'
if __name__=='__main__':raise SystemExit(main())
