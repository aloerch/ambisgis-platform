#!/usr/bin/env python3
"""Build distinct, complete-source variants from content-pinned retained inputs.

Run on the host. Every compiler, API inspection and probe runs under the existing
network-denial wrapper. No Maven lifecycle, download, cache mutation or publishing.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

HERE = Path(__file__).resolve().parent
JAVA_SUPPORT = HERE.parent
sys.path.insert(0, str(JAVA_SUPPORT))
import toolchain


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(root, entry):
    p = root / entry['path']
    data = p.read_bytes()
    if digest(data) != entry['sha256']:
        raise ValueError('Input differs: ' + str(p))
    return data


def extract(data, target, tar=False):
    members = []
    if tar:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for item in archive.getmembers():
                if item.isfile():
                    members.append(('/'.join(Path(item.name).parts[1:]), archive.extractfile(item).read()))
                elif not item.isdir():
                    raise ValueError('Non-regular archive member: ' + item.name)
    else:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [(n, archive.read(n)) for n in archive.namelist() if not n.endswith('/')]
    for name, content in members:
        path = target / name
        if not path.resolve().is_relative_to(target.resolve()):
            raise ValueError('Unsafe archive member')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def jar(path, classes, resources, identity, selector=lambda n: True, agent=False):
    items = {str(p.relative_to(classes)): p.read_bytes() for p in classes.rglob('*.class') if selector(str(p.relative_to(classes)))}
    items.update(resources)
    items['META-INF/ambisgis-variant.json'] = (json.dumps(identity, sort_keys=True, indent=2)+'\n').encode()
    manifest = 'Manifest-Version: 1.0\r\nImplementation-Vendor: AmbisGIS development candidate\r\nImplementation-Version: '+identity['variant_id']+'\r\n'
    if agent:
        manifest += 'Premain-Class: org.aspectj.weaver.loadtime.Agent\r\nCan-Redefine-Classes: true\r\n'
    items['META-INF/MANIFEST.MF'] = (manifest+'\r\n').encode()
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(items.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    return [{'path': name, 'sha256': digest(data), 'bytes': len(data)} for name, data in sorted(items.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace_root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest_path = HERE / 'inputs.json'
    manifest = json.loads(manifest_path.read_text())
    result = {'schema_version': 1, 'scope': 'Focused complete-source variant build and probes; final WAR acceptance separate', 'status': 'failed', 'recipe_sha256': digest(Path(__file__).read_bytes()), 'inputs_sha256': digest(manifest_path.read_bytes()), 'commands': [], 'replacements': []}
    try:
        inputs = {name: checked(root, item) for name, item in manifest['inputs'].items()}
        jdk = root / manifest['jdk']
        result['toolchain'] = toolchain.verify_extracted(root / manifest['toolchain_custody'], json.loads((JAVA_SUPPORT/'toolchain-inputs.json').read_text()), jdk.parent)
        for d in ['home', 'tmp', 'deps', 'artifacts']:
            (out/d).mkdir()
        deps = {}
        for key, entry in manifest['inputs'].items():
            if entry.get('role') == 'compile-dependency':
                deps[key] = out/'deps'/(key+'.jar')
                deps[key].write_bytes(inputs[key])
        env = {'PATH': str(jdk/'bin')+':/usr/bin:/bin', 'HOME': str(out/'home'), 'TMPDIR': str(out/'tmp'), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
        def invoke(name, command, allow_failure=False):
            argv = [sys.executable, str(JAVA_SUPPORT.parent/'postgis/offline_exec.py'), '--evidence', str(out/(name+'-network.json')), '--', *map(str, command)]
            with (out/(name+'.log')).open('xb') as log:
                proc = subprocess.run(argv, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
            receipt = json.loads((out/(name+'-network.json')).read_text())
            probes = {r['family']:r for r in receipt.get('probes',[]) if r['operation']=='socket(SOCK_STREAM)'}
            valid = receipt.get('status')=='completed' and receipt.get('command_exit_code')==proc.returncode and all(probes.get(f,{}).get('passed') is True and probes[f].get('errno')==1 for f in ['AF_INET','AF_INET6'])
            result['commands'].append({'name': name, 'command': argv, 'exit_code': proc.returncode, 'network_verified': valid, 'log_sha256': digest((out/(name+'.log')).read_bytes())})
            if not valid or (proc.returncode and not allow_failure):
                raise ValueError(name+' failed; retained log and network receipt')
            return proc.returncode
        def compile_sources(name, paths, cp, encoding='UTF-8'):
            classes = out/(name+'-classes')
            classes.mkdir()
            sources = out/(name+'-sources.txt')
            sources.write_text('\n'.join(str(p) for p in sorted(paths))+'\n')
            command = [jdk/'bin/javac', '-proc:none', '-encoding', encoding, '--release', '7', '-d', classes]
            if cp: command.extend(['-cp', ':'.join(map(str,cp))])
            invoke(name+'-compile', command+['@'+str(sources)])
            return classes
        # Full release sources, including bundled BCEL sources; no binary class copying.
        aj = out/'source/aspectj'
        extract(inputs['aspectj-source'], aj, tar=True)
        extract((aj/'lib/bcel/bcel-src.zip').read_bytes(), aj/'embedded-bcel')
        version = aj/'bridge/src/org/aspectj/bridge/Version.java'
        old = 'public static final String text = "DEVELOPMENT";'
        text = version.read_text()
        if text.count(old)!=1: raise ValueError('AspectJ version patch drift')
        version.write_text(text.replace(old, 'public static final String text = "1.5.4-ambisgis-source-1";'))
        sources = []
        for module in ['runtime','aspectj5rt','asm','bridge','util','weaver','loadtime','weaver5','loadtime5']:
            for folder in ['src','java5-src']:
                sources.extend(p for p in (aj/module/folder).rglob('*.java') if p.name!='JRockitAgent.java')
        sources.extend((aj/'embedded-bcel').rglob('*.java'))
        ajclasses = compile_sources('aspectj', sources, [deps['regexp'], deps['commons-logging']], 'ISO-8859-1')
        # Source counterpart API is carried by its publisher's complete source archive.
        xp = out/'source/xmlpull'
        with zipfile.ZipFile(io.BytesIO(inputs['xpp3-source'])) as archive:
            for name in ['XmlPullParser','XmlPullParserException','XmlPullParserFactory','XmlSerializer']:
                target = xp/'org/xmlpull/v1'/(name+'.java')
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.read('org/xmlpull/v1/'+name+'.java'))
        xpclasses = compile_sources('xmlpull', list(xp.rglob('*.java')), [])
        js = out/'source/json'
        extract(inputs['json-source'], js, tar=True)
        jsclasses = compile_sources('json', list((js/'src/main/java').rglob('*.java')), list(deps.values()))
        source_manifest = []
        for p in sorted((out/'source').rglob('*')):
            if p.is_file():source_manifest.append({'path':str(p.relative_to(out)), 'sha256':digest(p.read_bytes()), 'bytes':p.stat().st_size})
        (out/'source-manifest.json').write_text(json.dumps(source_manifest,indent=2)+'\n')
        source_hash = digest((out/'source-manifest.json').read_bytes())
        ajresources = {str(p.relative_to(aj/module/folder)):p.read_bytes() for module in ['runtime','aspectj5rt','asm','bridge','util','weaver','loadtime','weaver5','loadtime5'] for folder in ['src','java5-src'] for p in (aj/module/folder).rglob('*') if p.is_file() and p.suffix in ['.properties','.dtd']}
        ajresources['META-INF/NOTICE-AspectJ.html']=(aj/'docs/dist/LICENSE-AspectJ.html').read_bytes()
        ajresources['META-INF/LICENSE-BCEL.txt']=(aj/'embedded-bcel/org/aspectj/apache/bcel/Constants.java').read_bytes().split(b'package ',1)[0]
        ajresources['META-INF/LICENSE-EPL-1.0.html']=inputs['epl-license']
        isrt = lambda n:any(n.startswith(s) for s in ['org/aspectj/lang/','org/aspectj/runtime/','org/aspectj/internal/lang/'])
        targets = [('aspectjrt',ajclasses,ajresources,isrt,False),('aspectjweaver',ajclasses,ajresources,lambda n:not isrt(n),True),('xmlpull',xpclasses,{'META-INF/LICENSE-XMLPULL.txt':inputs['xmlpull-license']},lambda n:True,False),('json-lib',jsclasses,{'META-INF/LICENSE.txt':(js/'LICENSE.txt').read_bytes(),'META-INF/NOTICE-JSON-DERIVATION.txt':(HERE/'json-notice.txt').read_bytes()},lambda n:True,False)]
        for key, classes, resources, selector, agent in targets:
            original=manifest['originals'][key]
            identity={'variant_id':manifest['variants'][key], 'original_maven_path':original['maven_path'], 'original_sha256':original['sha256'], 'source_manifest_sha256':source_hash, 'new_source_output':True, 'not_upstream_release':True}
            artifact=out/'artifacts'/(identity['variant_id']+'.jar')
            members=jar(artifact,classes,resources,identity,selector,agent)
            (out/(key+'-members.json')).write_text(json.dumps(members,indent=2)+'\n')
            result['replacements'].append({**identity,'replacement_path':str(artifact),'replacement_sha256':digest(artifact.read_bytes()),'source_manifest_path':str(out/'source-manifest.json'),'artifact_members_path':str(out/(key+'-members.json'))})
        result['status']='built-focused-probes-pending'
        result['source_manifest_sha256']=source_hash
    except Exception as exc:
        result['error']=str(exc)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'output':str(out),'error':result.get('error')}))
    return 0 if result['status']=='built-focused-probes-pending' else 1

if __name__=='__main__':raise SystemExit(main())
