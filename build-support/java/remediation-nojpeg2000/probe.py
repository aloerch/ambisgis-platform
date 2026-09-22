#!/usr/bin/env python3
"""Probe exact aggregate or explicitly labeled component substitutions offline."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'build-support/java'))
import toolchain
spec=importlib.util.spec_from_file_location('nojpeg_policy',HERE/'profile.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def record(path):return {'path':str(path),'sha256':sha(path),'bytes':Path(path).stat().st_size}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--war',type=Path,required=True)
    p.add_argument('--expected-war-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--component-replacement',type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    result={'status':'failed','scope':'component-substitution' if a.component_replacement else 'exact-new-WAR','stages':[],'war':record(a.war)}
    try:
        if sha(a.war)!=a.expected_war_sha256:raise ValueError('WAR identity mismatch')
        result['toolchain']=toolchain.verify_extracted(a.workspace/'source-archives/java-resolution/toolchain',json.loads((ROOT/'build-support/java/toolchain-inputs.json').read_text()),a.workspace/'build-worktrees/java-resolution/toolchain')
        java=a.workspace/'build-worktrees/java-resolution/toolchain/jdk-17.0.20.1+1/bin'
        libs=out/'libs';libs.mkdir()
        with zipfile.ZipFile(a.war) as archive:
            for name in archive.namelist():
                if name.startswith('WEB-INF/lib/') and name.endswith('.jar'):
                    data=archive.read(name)
                    if a.component_replacement and name=='WEB-INF/lib/jai_imageio-1.1.jar':data=a.component_replacement.read_bytes()
                    (libs/Path(name).name).write_bytes(data)
        servlet=a.workspace/'build-worktrees/java-gmt-remediation/aggregate-02/fresh-m2/javax/servlet/javax.servlet-api/3.1.0/javax.servlet-api-3.1.0.jar'
        result['provided_compile_only_servlet_api']=record(servlet)
        def cp():return ':'.join(str(f) for f in sorted(libs.glob('*.jar')))
        def run(label,cmd):
            for folder in ('home','tmp'):(out/folder).mkdir(exist_ok=True)
            network=out/(label+'-network.json');log=out/(label+'.log')
            env={'PATH':str(java)+':/usr/bin:/bin','HOME':str(out/'home'),'TMPDIR':str(out/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}
            with log.open('xb') as stream:
                completed=subprocess.run([sys.executable,str(ROOT/'build-support/postgis/offline_exec.py'),'--evidence',str(network),'--',*map(str,cmd)],cwd=out,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
            proof=json.loads(network.read_text());probes={x['family']:x for x in proof.get('probes',[]) if x.get('operation')=='socket(SOCK_STREAM)'}
            verified=proof.get('status')=='completed' and proof.get('command_exit_code')==completed.returncode and all(probes.get(f,{}).get('passed') and probes[f].get('errno')==1 for f in ('AF_INET','AF_INET6'))
            result['stages'].append({'name':label,'exit_code':completed.returncode,'network_verified':verified,'network':record(network),'log':record(log)})
            if completed.returncode or not verified:raise ValueError(label+' failed')
        if a.component_replacement:
            parent=a.workspace/'build-worktrees/java-gmt-remediation/aggregate-02/work/source'
            source=out/'component-source'
            for relative in ('PDFUtils.java','MapPrinter.java','servlet/MapPrinterServlet.java','config/layout/ImageBlock.java','PDFCustomBlocks.java','output/AbstractOutputFormat.java','map/renderers/PDFTileRenderer.java'):
                rel=Path(policy.MAPFISH)/'src/main/java/org/mapfish/print'/relative
                (source/rel).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(parent/rel,source/rel)
            result['source_changes']=policy.prepare(source)
            classes=out/'component-classes';classes.mkdir()
            run('compile-consumer-guards',[java/'javac','-proc:none','-cp',cp()+':'+str(servlet),'-d',classes,*sorted(source.rglob('*.java'))])
            # A labeled component experiment, never a claimed full source aggregate.
            original=libs/'print-lib-2.4.1.jar';fresh=libs/'print-lib-component-nojpeg2000.jar'
            replacements={str(f.relative_to(classes)):f.read_bytes() for f in classes.rglob('*.class')}
            with zipfile.ZipFile(original) as old,zipfile.ZipFile(fresh,'x',zipfile.ZIP_DEFLATED) as new:
                for name in old.namelist():
                    if not name.endswith('/') and name not in replacements:new.writestr(name,old.read(name))
                for name,data in sorted(replacements.items()):new.writestr(name,data)
            original.unlink()
            result['component_source_classes']=[record(f) for f in sorted(classes.rglob('*.class'))]
            # Only a classpath fixture container; not an accepted or deployed WAR.
            container=out/'component-classpath.zip'
            with zipfile.ZipFile(container,'x',zipfile.ZIP_STORED) as z:
                for library in sorted(libs.glob('*.jar')):z.write(library,'WEB-INF/lib/'+library.name)
            result['inventory']=policy.scan_war(container)
        else:
            result['inventory']=policy.scan_war(a.war)
        try:
            policy.scan_war(a.workspace/'build-worktrees/java-gmt-remediation/aggregate-02/work/source/geoserver/src/web/app/target/geoserver.war')
            raise AssertionError('old JJ2000 negative control accepted')
        except ValueError as error:
            if 'blocked definition/provider/native fallback' not in str(error):raise
            result['old_provider_negative_control']='rejected known parent JJ2000 classes/providers'
        fixtures=out/'fixtures';fixtures.mkdir()
        jp2=a.workspace/'build-worktrees/java-gmt-remediation/imaging/final-war-probe-02/fixtures/JPEG2000-selected.img'
        result['historical_positive_fixture']=record(jp2)
        data=jp2.read_bytes();(fixtures/'input.jp2').write_bytes(data);(fixtures/'disguised.png').write_bytes(data)
        position=0;codestream=None
        while position<len(data):
            size=int.from_bytes(data[position:position+4],'big');kind=data[position+4:position+8];header=8
            if size==1:size=int.from_bytes(data[position+8:position+16],'big');header=16
            if size==0:size=len(data)-position
            if size<header or position+size>len(data):raise ValueError('invalid retained JP2 box')
            if kind==b'jp2c':codestream=data[position+header:position+size]
            position+=size
        if not codestream or not codestream.startswith(bytes.fromhex('ff4fff51')):raise ValueError('missing real raw codestream')
        import struct
        # Minimal single-strip TIFF container with genuine retained raw J2K bytes.
        # Neither retained TIFF implementation supports these compression tags.
        for compression in (34712,33003,33005):
            end_ifd=8+2+10*12+4; pixel_offset=end_ifd+6
            rows=[(256,4,1,96),(257,4,1,80),(258,3,3,end_ifd),(259,3,1,compression),
                  (262,3,1,2),(273,4,1,pixel_offset),(277,3,1,3),(278,4,1,80),
                  (279,4,1,len(codestream)),(284,3,1,1)]
            tiff=b'II'+struct.pack('<HIH',42,8,10)+b''.join(struct.pack('<HHII',*row) for row in rows)+struct.pack('<IHHH',0,8,8,8)+codestream
            (fixtures/('jpeg2000-compression-'+str(compression)+'.tif')).write_bytes(tiff)
        (fixtures/'raw.j2k').write_bytes(codestream);(fixtures/'raw-disguised.tif').write_bytes(codestream)
        renderer=libs/'marlin-0.9.4.8.jar'
        if not renderer.exists():raise ValueError('selected headless renderer missing')
        flags=['-Djava.awt.headless=true','-Dsun.java2d.opengl=false','--patch-module','java.desktop='+str(renderer),'-Dsun.java2d.renderer=sun.java2d.marlin.DMarlinRenderingEngine','--add-exports','java.desktop/sun.java2d.pipe=ALL-UNNAMED','--add-exports','java.desktop/sun.java2d.marlin=ALL-UNNAMED','-Dambisgis.witness.renderer='+str(renderer),'-Dambisgis.witness.renderer.sha256='+sha(renderer)]
        witness=[HERE/'NoJpegImageIOWitness.java',HERE/'MapFishImagingWitness.java',HERE/'Jpeg2000RemovalWitness.java',HERE/'TiffJpeg2000Witness.java',ROOT/'build-support/java/remediation-imaging/RenderingWitness.java']
        run('compile-witnesses',[java/'javac','-proc:none','--add-exports','java.desktop/sun.java2d.pipe=ALL-UNNAMED','-cp',cp()+':'+str(servlet),'-d',out/'classes',*witness])
        runtime_cp=str(out/'classes')+':'+cp()+':'+str(servlet)
        run('candidate-tiff-jpeg2000',[java/'java',*flags,'-cp',runtime_cp,'TiffJpeg2000Witness',fixtures])
        if a.component_replacement:
            original_jai=out/'historical-original-jai.jar'
            with zipfile.ZipFile(a.war) as original:original_jai.write_bytes(original.read('WEB-INF/lib/jai_imageio-1.1.jar'))
            baseline_cp=str(out/'classes')+':'+str(original_jai)+':'+':'.join(str(f) for f in sorted(libs.glob('*.jar')) if f.name!='jai_imageio-1.1.jar')
            run('baseline-tiff-jpeg2000',[java/'java',*flags,'-cp',baseline_cp,'TiffJpeg2000Witness',fixtures])
        run('positive-codecs',[java/'java',*flags,'-cp',runtime_cp,'NoJpegImageIOWitness',fixtures])
        run('positive-print',[java/'java',*flags,'-cp',runtime_cp,'MapFishImagingWitness',out/'print-fixtures'])
        run('negative-jpeg2000',[java/'java',*flags,'-cp',runtime_cp,'Jpeg2000RemovalWitness',fixtures,fixtures/'PNG-automatic.img'])
        if sha(a.war)!=a.expected_war_sha256:raise ValueError('input WAR changed')
        result['library_manifest']=[record(f) for f in sorted(libs.glob('*.jar'))]
        result['fixture_sources']=[record(f) for f in witness]
        result['fixtures']=[record(f) for directory in (fixtures,out/'print-fixtures') for f in sorted(directory.glob('*')) if f.is_file()]
        result['status']='passed'
        result['scope_limits']=['Marlin inherited 46/48 and Java7 LTW limitations are preserved historical findings; not rerun here.','JPEG2000-positive cases intentionally deselected for this profile, not counted as passing.','PostGIS mosaic/live service/frontend restart are separate exact-WAR runtime acceptance.']
    except Exception as error:result['error']=str(error)
    result['recipe']=record(Path(__file__).resolve())
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'output':str(out),'error':result.get('error')}))
    return result['status']!='passed'

if __name__=='__main__':raise SystemExit(main())
