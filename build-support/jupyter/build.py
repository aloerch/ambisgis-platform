#!/usr/bin/env python3
"""Build exact owned Hub/Lab sources in a new run using verified retained inputs.

Run under ../postgis/offline_exec.py for enforced build network denial. Runtime
probes must run separately because they require loopback TCP/WebSockets.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(custody, manifest):
    indexed = {}
    for item in manifest['files']:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts or item['path'] in indexed:
            raise ValueError('unsafe or duplicate manifest path: '+item['path'])
        indexed[item['path']] = item
        path = custody / item['path']
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(custody.resolve()):
            raise ValueError('unsafe or missing retained input: '+str(path))
        if path.stat().st_size != item['size'] or digest(path) != item['sha256']:
            raise ValueError('retained input mismatch: '+str(path))


    for root in manifest['roots']:
        if root['path'] not in indexed or root['sha256'] != indexed[root['path']]['sha256']:
            raise ValueError('root is not a verified manifest input: '+root['path'])
    for required in ['build-requirements.txt','hub-requirements.txt','user-requirements.txt','proxy-package.json','proxy-package-lock.json']:
        if required not in indexed:
            raise ValueError('required lock is not verified: '+required)


def copy_verified(custody, destination, manifest, prefix):
    """Only manifest-listed files enter a consumed dependency directory."""
    destination.mkdir(parents=True, exist_ok=False)
    for item in manifest['files']:
        path = Path(item['path'])
        if path.parts[0] != prefix:
            continue
        target = destination.joinpath(*path.parts[1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(custody/path, target)
        if digest(target) != item['sha256']:
            raise ValueError('input changed while copying: '+str(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--custody', type=Path, required=True)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, default=Path(__file__).with_name('inputs.json'))
    args = ap.parse_args()
    c, r = args.custody.resolve(), args.run.absolute()
    manifest = json.loads(args.manifest.read_text())
    verify(c, manifest)
    r.mkdir(parents=True, exist_ok=False)
    (r/'logs').mkdir(); (r/'home').mkdir(); (r/'tmp').mkdir(); (r/'sources').mkdir(); (r/'wheels').mkdir()
    (r/'recipe.py').write_bytes(Path(__file__).read_bytes())
    (r/'inputs.json').write_bytes(args.manifest.read_bytes())
    evidence = {'started': datetime.now(timezone.utc).isoformat(), 'status':'running', 'commands':[], 'inputs_sha256':digest(args.manifest), 'recipe_sha256':digest(Path(__file__)), 'host_python':{'version':sys.version, 'executable':sys.executable,'sha256':digest(Path(sys.executable).resolve())}}
    env = {'PATH':'/usr/bin:/bin','HOME':str(r/'home'),'TMPDIR':str(r/'tmp'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONNOUSERSITE':'1','PIP_CONFIG_FILE':os.devnull,'PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1','npm_config_cache':str(r/'npm-cache'),'npm_config_offline':'true','npm_config_audit':'false','npm_config_fund':'false','npm_config_ignore_scripts':'true','npm_config_update_notifier':'false','YARN_CACHE_FOLDER':str(r/'yarn-cache'),'YARN_ENABLE_GLOBAL_CACHE':'false','YARN_ENABLE_SCRIPTS':'false','YARN_ENABLE_TELEMETRY':'false','YARN_ENABLE_NETWORK':'false','NODE_OPTIONS':'--max-old-space-size=6144'}
    def save():
        (r/'build-report.json').write_text(json.dumps(evidence,indent=2)+'\n')
    def run(name, cmd, cwd=r, extra=None):
        log = r/'logs'/(name+'.log')
        record = {'name':name,'argv':[str(x) for x in cmd],'cwd':str(cwd),'started':datetime.now(timezone.utc).isoformat(),'log':str(log.relative_to(r))}
        evidence['commands'].append(record); save()
        with log.open('x') as out:
            result = subprocess.run(record['argv'], cwd=cwd, env=env| (extra or {}), stdout=out,stderr=subprocess.STDOUT)
        record.update(exit_code=result.returncode,log_sha256=digest(log),finished=datetime.now(timezone.utc).isoformat()); save()
        print(name, result.returncode, flush=True)
        if result.returncode: raise RuntimeError('command failed; see '+str(log))
    try:
        for item in manifest['roots']:
            if item['class']=='owned-source' or item['class']=='retained-binary':
                with tarfile.open(c/item['path']) as archive:
                    archive.extractall(r/'sources',filter='data')
        pam_recipe=Path(__file__).with_name('build_pam.py')
        shutil.copyfile(pam_recipe,r/'build_pam.py')
        evidence['pam_recipe_sha256']=digest(pam_recipe)
        run('pam-library',[sys.executable,r/'build_pam.py','--archive',c/'Linux-PAM-1.7.2.tar.xz','--run',r/'pam'])
        evidence['native_library_dir']='pam/prefix/lib'
        evidence['pam_report_sha256']=digest(r/'pam/report.json')
        env['LD_LIBRARY_PATH']=str(r/'pam/prefix/lib')
        node = r/'sources/node-v24.21.0-linux-x64/bin'
        env['PATH']=str(node)+':'+env['PATH']
        # Private caches prevent a previous machine cache from supplying inputs.
        for prefix in ['npm-cache','yarn-cache','wheels']:
            copy_verified(c,r/('dependency-wheels' if prefix=='wheels' else prefix),manifest,prefix)
        for name in ['build','hub','user']:
            target = r/(name+'-env')
            run(name+'-venv',[sys.executable,'-m','venv',target])
            run(name+'-deps',[target/'bin/python','-m','pip','--isolated','install','--no-index','--find-links',r/'dependency-wheels','--require-hashes','-r',c/(name+'-requirements.txt')])
        env['PATH']=str(r/'build-env/bin')+':'+env['PATH']
        hub,lab = r/'sources/jupyterhub',r/'sources/jupyterlab'
        for name,path in [('hub',hub),('hub-jsx',hub/'jsx')]:
            run(name+'-npm',['npm','ci','--offline','--ignore-scripts','--no-audit','--no-fund'],path)
        run('hub-components',['npm','run','postinstall'],hub)
        run('hub-css',['npm','run','css'],hub)
        run('hub-jsx',['npm','run','build'],hub/'jsx')
        required_hub=['share/jupyterhub/static/css/style.min.css','share/jupyterhub/static/css/style.min.css.map','share/jupyterhub/static/js/admin-react.js']
        for f in required_hub:
            if not (hub/f).is_file() or (hub/f).stat().st_size==0:raise RuntimeError('missing built asset '+f)
        # Prevent setup.py from repeating npm acquisition after explicit build.
        os.utime(hub/'node_modules'); os.utime(hub/'share/jupyterhub/static/components')
        # setuptools-scm cannot enumerate tracked data from a Git archive.
        # Preserve the exact owned migration/schema/template data explicitly.
        hub_data=['jupyterhub/alembic.ini','jupyterhub/alembic/README',
                  'jupyterhub/alembic/script.py.mako',
                  'jupyterhub/event-schemas/server-actions/v1.yaml',
                  'jupyterhub/singleuser/templates/page.html']
        with (hub/'MANIFEST.in').open('a') as package_manifest:
            package_manifest.write('\n# AmbisGIS archive packaging: owned tracked runtime data\n')
            package_manifest.writelines('include '+path+'\n' for path in hub_data)
        evidence['hub_archive_packaging']={'manifest_sha256':digest(hub/'MANIFEST.in'),'included_owned_data':hub_data}
        run('hub-wheel',[r/'build-env/bin/python','-m','build','--wheel','--no-isolation','--outdir',r/'wheels'],hub)
        hubwheel=next((r/'wheels').glob('jupyterhub-*.whl'))
        with zipfile.ZipFile(hubwheel) as wheel:
            for path in hub_data:
                if wheel.read(path)!=(hub/path).read_bytes():
                    raise RuntimeError('owned Hub runtime data missing or changed: '+path)
        run('lab-yarn',['jlpm','install','--immutable','--immutable-cache','--mode=skip-build'],lab)
        # Verify every owned @jupyterlab workspace resolves to this extracted tree.
        packages=[]
        for path in sorted((lab/'packages').glob('*/package.json')):
            name=json.loads(path.read_text())['name']
            link=lab/'node_modules'/name
            if not link.resolve().is_relative_to(lab) or link.resolve()!=path.parent.resolve():
                raise RuntimeError('workspace escaped owned source: '+name)
            packages.append({'name':name,'source':str(path.parent.relative_to(lab))})
        evidence['owned_lab_workspaces']=packages;save()
        run('lab-utils',['npm','run','build:utils'],lab)
        run('lab-packages',['npm','run','build:packages'],lab)
        run('lab-nbconvert-css',['npm','run','build:nbconvert:css'],lab)
        run('lab-frontend',['npm','run','build:prod'],lab/'dev_mode')
        for name in ['static','schemas','themes']:
            shutil.copytree(lab/'dev_mode'/name,lab/'jupyterlab'/name,dirs_exist_ok=True)
        required_lab=['static/package.json','static/index.html','schemas/@jupyterlab/shortcuts-extension/shortcuts.json','themes/@jupyterlab/theme-light-extension/index.css']
        for f in required_lab:
            if not (lab/'jupyterlab'/f).is_file():raise RuntimeError('missing built Lab asset '+f)
        # Package the owned Python + freshly compiled frontend through the normal
        # sdist-shaped wheel path, whose buildapi explicitly skips npm when
        # dev_mode is absent. No registry JupyterLab core package replaces the
        # owned workspaces; third-party frontend dependencies remain retained.
        package = r/'lab-package'
        def ignored(directory,names):
            return {n for n in names if n in {'node_modules','dev_mode','packages','buildutils','galata','.yarn','examples','tests','testutils','.git'} or n.endswith('.js.map')}
        shutil.copytree(lab,package,ignore=ignored)
        run('lab-wheel',[r/'build-env/bin/python','-m','build','--wheel','--no-isolation','--outdir',r/'wheels'],package)
        hubwheel=next((r/'wheels').glob('jupyterhub-*.whl'));labwheel=next((r/'wheels').glob('jupyterlab-*.whl'))
        for name,wheels in [('hub',[hubwheel]),('user',[hubwheel,labwheel])]:
            run(name+'-owned-install',[r/(name+'-env/bin/python'),'-m','pip','--isolated','install','--no-index','--no-deps',*wheels])
            run(name+'-pip-check',[r/(name+'-env/bin/python'),'-m','pip','check'])
        proxy = r/'proxy';proxy.mkdir()
        for src,dst in [('proxy-package.json','package.json'),('proxy-package-lock.json','package-lock.json')]:
            shutil.copyfile(c/src,proxy/dst)
        run('proxy-install',['npm','ci','--offline','--ignore-scripts','--no-audit','--no-fund'],proxy)
        evidence['wheels']=[{'path':str(p.relative_to(r)),'sha256':digest(p),'size':p.stat().st_size} for p in sorted((r/'wheels').glob('*.whl'))]
        evidence['assets']=[{'package':pkg,'path':f,'sha256':digest(base/f)} for pkg,base,files in [('jupyterhub',hub,required_hub),('jupyterlab',lab/'jupyterlab',required_lab)] for f in files]
        evidence['status']='passed'
    except Exception as exc:
        evidence.update(status='failed',error=str(exc));raise
    finally:
        evidence['finished']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__': main()
