#!/usr/bin/env python3
"""Build the explicit NO-JPEG2000 Java-only JAI ImageIO source profile.
Native codecLib and inactive javax.media.jai operation adapters are excluded at
source/SPI boundary. ImageN and imageio-ext are untouched. All JJ2000 sources and dependent JPEG2000 providers are excluded. Original
sources, notices, failed and JPEG2000-positive evidence remain in custody.
"""
import argparse,hashlib,json,os,pathlib,re,subprocess,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'build-support/java'))
import source_closure as sc
import toolchain
SHA='f7dac9b2350337503a7fb56636b927700247c6111f3a254ac223f510e1bffb68'
IDENTITY='ambisgis-jai-imageio-1.1-nojpeg2000-temurin17-1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(root):return [{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in sorted(root.rglob('*')) if p.is_file()]
def replace_guarded(p,old,new,count=1):
 b=p.read_text(encoding='iso-8859-1')
 if b.count(old)!=count:raise ValueError('patch mismatch '+str(p)+': '+str(b.count(old)))
 p.write_text(b.replace(old,new),encoding='iso-8859-1')
def remove_braced(text,needle,count):
 if text.count(needle)!=count:raise ValueError('native branch count mismatch')
 for _ in range(count):
  start=text.index(needle);pos=text.index('{',start);depth=1;end=pos+1
  while depth:
   if text[end]=='{':depth+=1
   if text[end]=='}':depth-=1
   end+=1
  text=text[:start]+'/* AmbisGIS: native codecLib unavailable in the Java-only profile. */'+text[end:]
 return text

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();o=a.output.resolve();o.mkdir(parents=True,exist_ok=False)
 result={'identity':IDENTITY,'status':'failed','source_revision':'c3c86a17fecc8a2d9b83bd0e6f686542c55d294b','source_sha256':SHA,'stages':[],'original_binary_equivalence':False,'rights':'Selected com.sun Java sources retain Sun BSD with nuclear disclaimer; JJ2000 and dependent JPEG2000 sources excluded, their original terms unchanged in custody; distribution review remains separate','profile_exclusions':['NO-JPEG2000: all jj2000 and com.sun.media.imageio[impl].plugins.jpeg2000 source, classes and SPIs','codecLib JNI adapters and their native-only ImageIO providers','inactive javax.media.jai ImageRead/ImageWrite bridge (selected WAR uses org.eclipse.imagen; retained ImageN/imageio-ext unaffected)']}
 try:
  result['recipe']={'path':str(pathlib.Path(__file__).resolve()),'sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
  result['toolchain']=toolchain.verify_extracted(a.workspace/'source-archives/java-resolution/toolchain',json.loads((ROOT/'build-support/java/toolchain-inputs.json').read_text()),a.workspace/'build-worktrees/java-resolution/toolchain')
  archive=a.workspace/'source-archives/java-gmt-remediation/imaging'/SHA
  if sha(archive)!=SHA:raise ValueError('source integrity')
  members=sc.archive_members(archive.read_bytes());source=o/'source';source.mkdir();excluded=[]
  for n,b in members.items():
   rel=pathlib.Path(*pathlib.PurePosixPath(n).parts[1:])
   if n.endswith(('.so','.dll','.jar')):excluded.append({'path':str(rel),'sha256':hashlib.sha256(b).hexdigest(),'reason':'closed native codecLib binary; retained original archive, never executed/extracted'});continue
   t=source/rel;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(b)
  result['original_source_manifest']=manifest(source);result['excluded_archive_binaries']=excluded
  src=source/'src/share/classes';selected=o/'selected-source';selected.mkdir();omitted=[]
  for f in sorted(src.rglob('*')):
   if not f.is_file():continue
   rel=f.relative_to(src);reason=None
   if str(rel).startswith('com/sun/media/jai/'):reason='inactive javax.media.jai bridge'
   if f.suffix=='.java' and ('CodecLib' in f.name or f.name.startswith('CLib') or f.name=='MediaLibAccessor.java'):reason='native-only adapter or metadata'
   if str(rel).startswith(('jj2000/','com/sun/media/imageio/plugins/jpeg2000/','com/sun/media/imageioimpl/plugins/jpeg2000/')):reason='owner-authorized NO-JPEG2000 source/profile exclusion'
   if reason:omitted.append({'path':str(rel),'sha256':sha(f),'reason':reason});continue
   t=selected/rel;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(f.read_bytes())
  result['omitted_sources']=omitted
  common=selected/'com/sun/media/imageioimpl/common/PackageUtil.java'
  replace_guarded(common,'import com.sun.medialib.codec.jiio.Util;','// AmbisGIS Java-only profile has no proprietary codecLib dependency.')
  replace_guarded(common,'isCodecLibAvailable = Util.isCodecLibAvailable();','isCodecLibAvailable = false; // AmbisGIS: Java-only source build.')
  for name,n in [('TIFFImageReader.java',2),('TIFFImageWriter.java',3)]:
   f=selected/'com/sun/media/imageioimpl/plugins/tiff'/name;s=f.read_text(encoding='iso-8859-1');s=remove_braced(s,'if(PackageUtil.isCodecLibAvailable())',n);f.write_text(s,encoding='iso-8859-1')
  replace_guarded(selected/'com/sun/media/imageioimpl/common/ImageUtil.java','import com.sun.medialib.codec.jiio.Util;','// AmbisGIS: unused proprietary codecLib import removed.')
  result['selected_source_manifest']=manifest(selected)
  java=a.workspace/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1/bin';result['compiler']={'path':str(java/'javac'),'sha256':sha(java/'javac')}
  def run(stage,cmd,expected=0):
   for d in ['home','tmp']:(o/d).mkdir(exist_ok=True)
   receipt=o/(stage+'-network.json');log=o/(stage+'.log');env={'PATH':str(java)+':/usr/bin:/bin','HOME':str(o/'home'),'TMPDIR':str(o/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
   with log.open('xb') as f:r=subprocess.run([sys.executable,str(ROOT/'build-support/postgis/offline_exec.py'),'--evidence',str(receipt),'--',*map(str,cmd)],cwd=o,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
   n=json.loads(receipt.read_text());probes={x['family']:x for x in n.get('probes',[]) if x.get('operation')=='socket(SOCK_STREAM)'};ok=n.get('status')=='completed' and n.get('command_exit_code')==r.returncode and all(probes.get(f,{}).get('passed') and probes[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
   result['stages'].append(dict(name=stage,command=list(map(str,cmd)),exit_code=r.returncode,log_sha256=sha(log),network_verified=ok))
   if not ok or r.returncode!=expected:raise ValueError(stage+' failed')
  classes=o/'classes';classes.mkdir();javas=sorted(selected.rglob('*.java'));result['selected_java_sources']=len(javas)
  run('compile',[java/'javac','-proc:none','-source','8','-target','8','-encoding','ISO-8859-1','-d',classes,*javas])
  jar=o/(IDENTITY+'.jar')
  with zipfile.ZipFile(jar,'x',compression=zipfile.ZIP_DEFLATED) as z:
   def add(n,b):i=zipfile.ZipInfo(n,date_time=(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,b)
   add('META-INF/MANIFEST.MF',('Manifest-Version: 1.0\nImplementation-Title: '+IDENTITY+'\nImplementation-Version: '+IDENTITY+'\nImplementation-Vendor: AmbisGIS local candidate\nSpecification-Title: Java Advanced Imaging Image I/O Tools\nAmbisGIS-Source-Revision: '+result['source_revision']+'\n\n').encode())
   for f in sorted(classes.rglob('*.class')):add(str(f.relative_to(classes)),f.read_bytes())
   for f in sorted(selected.rglob('*')):
    if f.is_file() and f.suffix=='.properties':add(str(f.relative_to(selected)),f.read_bytes())
   # Exact publisher SPI registrations, retaining copyright header, with only
   # absent source-profile providers omitted. No arbitrary provider reordering.
   for f in sorted((source/'src/share/services').glob('*')):
    if f.name=='javax.media.jai.OperationRegistrySpi':continue
    s=f.read_text(encoding='iso-8859-1');s='\n'.join(x for x in s.splitlines() if not (x.startswith('com.') and ('CLib' in x or 'CodecLib' in x or '.jpeg2000.' in x)))+'\n';add('META-INF/services/'+f.name,s.encode('iso-8859-1'))
   for n in ['LICENSE.txt','COPYRIGHT.txt']:add('META-INF/'+n,(source/n).read_bytes())
   add('META-INF/AMBISGIS-VARIANT.json',(json.dumps({'identity':IDENTITY,'source_sha256':SHA,'source_revision':result['source_revision'],'excluded_profile':result['profile_exclusions'],'rights':result['rights']},indent=2)+'\n').encode())
  result['output']={'path':str(jar),'sha256':sha(jar),'class_count':len(list(classes.rglob('*.class')))}
  binary=sc.archive_members(jar.read_bytes());selected_java={str(f.relative_to(selected)):f.read_bytes() for f in javas};result['source_class_coverage']=sc.coverage(binary,selected_java)
  if result['source_class_coverage']['unmapped']:raise ValueError('unmapped output class')
  for n,b in binary.items():
   if n.endswith('.class') or n.startswith('META-INF/services/'):
    if any(v in b.lower() or v in n.lower().encode() for v in [b'jj2000',b'jpeg2000',b'com/sun/medialib/codec']):raise ValueError('forbidden codec reference '+n)
  if manifest(selected)!=result['selected_source_manifest']:raise ValueError('sources changed')
  result['status']='built-technical-tests-pending'
 except Exception as e:result['error']=str(e)
 (o/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(o)}));return result['status']=='failed'
if __name__=='__main__':raise SystemExit(main())
