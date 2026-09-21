#!/usr/bin/env python3
"""Rebuild retained Marlin sources for an explicit headless Temurin-17 profile."""
import argparse, hashlib, json, os, pathlib, subprocess, sys, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'build-support/java'))
import source_closure as sc
import toolchain
SHA='60fc2008c33f01281ce75dbbfe04c1771ddb9544746ed32c3dbef551ee60270a'
IDENTITY='ambisgis-marlin-0.9.4.8-headless-temurin17-2'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(root):return [{'path':str(p.relative_to(root)),'sha256':digest(p)} for p in sorted(root.rglob('*')) if p.is_file()]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();o=a.output.resolve();o.mkdir(parents=True,exist_ok=False)
 result={'identity':IDENTITY,'status':'failed','stages':[],'original_correspondence':False,'excluded_profile':'OpenGL acceleration and unused TestArrayCacheInt benchmark helper; original predecessor bytecode/header mismatch preserved','source_revision':'5b1cbb57c39082cc444807daec401dd033754af7','source_sha256':SHA}
 try:
  result['recipe']={'path':str(pathlib.Path(__file__).resolve()),'sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
  result['toolchain']=toolchain.verify_extracted(a.workspace/'source-archives/java-resolution/toolchain',json.loads((ROOT/'build-support/java/toolchain-inputs.json').read_text()),a.workspace/'build-worktrees/java-resolution/toolchain')
  blob=a.workspace/'source-archives/java-source-closure/blobs/sha256'/SHA
  if digest(blob)!=SHA:raise ValueError('source checksum')
  members=sc.archive_members(blob.read_bytes());src=o/'source';src.mkdir()
  for n,b in members.items():
   rel=pathlib.Path(*pathlib.PurePosixPath(n).parts[1:]);t=src/rel;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(b)
  tooling=o/'executed-tooling';tooling.mkdir();(tooling/pathlib.Path(__file__).name).write_bytes(pathlib.Path(__file__).read_bytes());(tooling/'RenderingWitness.java').write_bytes(pathlib.Path(__file__).with_name('RenderingWitness.java').read_bytes())
  result['original_source_manifest']=manifest(src)
  engine=src/'src/main/java/sun/java2d/marlin/DMarlinRenderingEngine.java';s=engine.read_text();needle='    public DMarlinRenderingEngine() {\n        super();'
  if s.count(needle)!=1:raise ValueError('constructor guard mismatch')
  s=s.replace('package sun.java2d.marlin;', '// AmbisGIS modification 2026-09-21: enforce headless/no-OpenGL profile; original copyright and Classpath exception retained.\npackage sun.java2d.marlin;')
  s=s.replace(needle,needle+'\n        if (!java.awt.GraphicsEnvironment.isHeadless() || Boolean.getBoolean("sun.java2d.opengl")) {\n            throw new IllegalStateException("'+IDENTITY+' requires headless=true and opengl=false");\n        }');engine.write_text(s)
  version=src/'src/main/java/sun/java2d/marlin/Version.java';s=version.read_text();s=s.replace('marlin-0.9.4.8-Unsafe-OpenJDK',IDENTITY);s=s.replace('package sun.java2d.marlin;', '// AmbisGIS modification 2026-09-21: label the owned headless variant; original copyright and Classpath exception retained.\npackage sun.java2d.marlin;');version.write_text(s)
  result['selected_source_manifest']=manifest(src)
  java=a.workspace/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1/bin'
  result['compiler']={'path':str(java/'javac'),'sha256':digest(java/'javac')}
  def run(stage,cmd,expected=0):
   receipt=o/(stage+'-network.json');log=o/(stage+'.log');env={'PATH':str(java)+':/usr/bin:/bin','HOME':str(o/'home'),'TMPDIR':str(o/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
   for d in ['home','tmp']:(o/d).mkdir(exist_ok=True)
   with log.open('xb') as f:r=subprocess.run([sys.executable,str(ROOT/'build-support/postgis/offline_exec.py'),'--evidence',str(receipt),'--',*map(str,cmd)],cwd=o,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=240)
   n=json.loads(receipt.read_text());probes={x['family']:x for x in n.get('probes',[]) if x.get('operation')=='socket(SOCK_STREAM)'}
   ok=n.get('status')=='completed' and n.get('command_exit_code')==r.returncode and all(probes.get(f,{}).get('passed') and probes[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
   result['stages'].append(dict(name=stage,command=list(map(str,cmd)),exit_code=r.returncode,log_sha256=digest(log),network_verified=ok))
   if not ok or (r.returncode!=expected if expected is not None else r.returncode==0):raise ValueError(stage+' failed')
  classes=o/'classes';classes.mkdir();benchmark=src/'src/main/java/sun/java2d/marlin/TestArrayCacheInt.java'
  result['excluded_benchmark']={'path':str(benchmark.relative_to(src)),'sha256':digest(benchmark),'reason':'Only unselected JMH benchmark consumer; zero production references; TODO header does not establish file-specific Classpath exception.'}
  javas=[f for f in sorted((src/'src/main/java').rglob('*.java')) if f!=benchmark]
  # Match the publisher source compilation, including helper tests compiled there.
  run('compile',[java/'javac','-proc:none','-encoding','UTF-8','--patch-module','java.desktop='+str(src/'src/main/java'),'-d',classes,*javas])
  if list(classes.rglob('TestArrayCacheInt*.class')):raise ValueError('excluded benchmark implicitly recompiled')
  jar=o/(IDENTITY+'.jar')
  with zipfile.ZipFile(jar,'x',compression=zipfile.ZIP_DEFLATED) as z:
   def add(n,b):i=zipfile.ZipInfo(n,date_time=(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,b)
   add('META-INF/MANIFEST.MF',('Manifest-Version: 1.0\nImplementation-Title: '+IDENTITY+'\nImplementation-Version: '+IDENTITY+'\nAmbisGIS-Source-Revision: '+result['source_revision']+'\n\n').encode())
   for f in sorted((classes/'sun/java2d').rglob('*.class')):add(str(f.relative_to(classes)),f.read_bytes())
   for f in sorted(src.glob('*')):
    if f.is_file() and 'license' in f.name.lower():add('META-INF/'+f.name,f.read_bytes())
  result['output']={'path':str(jar),'sha256':digest(jar),'classes':manifest(classes)}
  flags=['--patch-module','java.desktop='+str(jar),'-Djava.awt.headless=true','-Dsun.java2d.opengl=false','-Dsun.java2d.renderer=sun.java2d.marlin.DMarlinRenderingEngine']
  result['required_jvm_flags']=flags
  witness=tooling/'RenderingWitness.java';run('witness-compile',[java/'javac','--add-exports','java.desktop/sun.java2d.pipe=ALL-UNNAMED','-d',o/'witness',witness])
  testflags=['--add-exports','java.desktop/sun.java2d.pipe=ALL-UNNAMED','--add-exports','java.desktop/sun.java2d.marlin=ALL-UNNAMED']
  run('render',[java/'java',*flags,*testflags,'-cp',o/'witness','RenderingWitness',jar,result['output']['sha256']])
  run('reject-opengl',[java/'java',*flags,'-Dsun.java2d.opengl=true',*testflags,'-cp',o/'witness','RenderingWitness',jar,result['output']['sha256']],expected=None)
  run('reject-unpatched',[java/'java','-Djava.awt.headless=true',*testflags,'-cp',o/'witness','RenderingWitness',jar,result['output']['sha256']],expected=None)
  if manifest(src)!=result['selected_source_manifest']:raise ValueError('source changed during build')
  result['status']='passed'
 except Exception as e:result['error']=str(e)
 (o/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(o)}));return result['status']!='passed'
if __name__=='__main__':raise SystemExit(main())
