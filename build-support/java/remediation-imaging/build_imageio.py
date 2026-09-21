#!/usr/bin/env python3
"""Build JAI ImageIO 1.1 FCS Java-only variant from recovered complete sources.
Native codecLib and inactive javax.media.jai operation adapters are excluded at
source/SPI boundary. ImageN and imageio-ext are untouched. JJ2000 separate terms
remain a combination/license blocker, not silently classified as BSD.
"""
import argparse,hashlib,json,os,pathlib,re,subprocess,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'build-support/java'))
import source_closure as sc
import toolchain
SHA='f7dac9b2350337503a7fb56636b927700247c6111f3a254ac223f510e1bffb68'
IDENTITY='ambisgis-jai-imageio-1.1-java-temurin17-1'
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
 result={'identity':IDENTITY,'status':'failed','source_revision':'c3c86a17fecc8a2d9b83bd0e6f686542c55d294b','source_sha256':SHA,'stages':[],'original_binary_equivalence':False,'rights':'Sun BSD with nuclear disclaimer for com.sun Java; separate JJ2000 conforming-product restriction remains selection/combination blocker pending rights review','profile_exclusions':['codecLib JNI adapters and their native-only ImageIO providers','inactive javax.media.jai ImageRead/ImageWrite bridge (selected WAR uses org.eclipse.imagen; retained ImageN/imageio-ext unaffected)']}
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
   if reason:omitted.append({'path':str(rel),'sha256':sha(f),'reason':reason});continue
   t=selected/rel;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(f.read_bytes())
  result['omitted_sources']=omitted
  common=selected/'com/sun/media/imageioimpl/common/PackageUtil.java'
  replace_guarded(common,'import com.sun.medialib.codec.jiio.Util;','// AmbisGIS Java-only profile has no proprietary codecLib dependency.')
  replace_guarded(common,'isCodecLibAvailable = Util.isCodecLibAvailable();','isCodecLibAvailable = false; // AmbisGIS: Java-only source build.')
  for name,n in [('TIFFImageReader.java',2),('TIFFImageWriter.java',3)]:
   f=selected/'com/sun/media/imageioimpl/plugins/tiff'/name;s=f.read_text(encoding='iso-8859-1');s=remove_braced(s,'if(PackageUtil.isCodecLibAvailable())',n);f.write_text(s,encoding='iso-8859-1')
  for rel in ['com/sun/media/imageioimpl/common/ImageUtil.java','com/sun/media/imageioimpl/plugins/jpeg2000/J2KImageReaderSpi.java','com/sun/media/imageioimpl/plugins/jpeg2000/J2KImageWriterSpi.java']:
   replace_guarded(selected/rel,'import com.sun.medialib.codec.jiio.Util;','// AmbisGIS: unused proprietary codecLib import removed.')
  for rel in ['decoder/StdEntropyDecoder.java','encoder/EBCOTRateAllocator.java','encoder/StdEntropyCoder.java']:
   f=selected/'jj2000/j2k/entropy'/rel
   if 'private final static boolean DO_TIMING = false;' not in f.read_text(encoding='iso-8859-1'):raise ValueError('timing profile changed')
   replace_guarded(f,'System.runFinalizersOnExit(true);','// AmbisGIS Temurin17: removed obsolete finalization request in disabled timing path.')
  packed=selected/'com/sun/media/imageioimpl/plugins/jpeg2000/RenderedImageSrc.java'
  replace_guarded(packed,'        if (sm.getDataType() == DataBuffer.TYPE_USHORT ||',
   '        // AmbisGIS: packed INT RGB channels are unsigned bit fields, not signed INT samples.\n        if (sm instanceof java.awt.image.SinglePixelPackedSampleModel && sm.getSampleSize(c) < 32)\n            return false;\n\n        if (sm.getDataType() == DataBuffer.TYPE_USHORT ||')
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
    s=f.read_text(encoding='iso-8859-1');s='\n'.join(x for x in s.splitlines() if not (x.startswith('com.') and ('CLib' in x or 'CodecLib' in x)))+'\n';add('META-INF/services/'+f.name,s.encode('iso-8859-1'))
   for n in ['LICENSE.txt','COPYRIGHT.txt']:add('META-INF/'+n,(source/n).read_bytes())
   jj=(selected/'jj2000/j2k/JJ2KInfo.java').read_bytes();add('META-INF/NOTICE-JJ2000.txt',jj[:jj.index(b'package jj2000')])
   add('META-INF/AMBISGIS-VARIANT.json',(json.dumps({'identity':IDENTITY,'source_sha256':SHA,'source_revision':result['source_revision'],'excluded_profile':result['profile_exclusions'],'rights':result['rights']},indent=2)+'\n').encode())
  result['output']={'path':str(jar),'sha256':sha(jar),'class_count':len(list(classes.rglob('*.class')))}
  if manifest(selected)!=result['selected_source_manifest']:raise ValueError('sources changed')
  result['status']='built-technical-tests-pending'
 except Exception as e:result['error']=str(e)
 (o/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'output':str(o)}));return result['status']=='failed'
if __name__=='__main__':raise SystemExit(main())
