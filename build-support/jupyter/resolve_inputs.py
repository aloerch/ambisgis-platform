#!/usr/bin/env python3
"""One-time experimental acquisition; all execution logs and selected inputs retained."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import urllib.request

# Resolution is an explicit acquisition action, never part of a replay build.
# It writes a new proposal; commit/review exact output locks before reuse.
C = S = NODE = None


def fetch(url, path, expected=None):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix+'.part')
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(path)
    digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
    if expected and digest != expected:
        raise ValueError('hash mismatch: '+str(path))
    return digest

def run(args, cwd=S, env=None, name='command'):
    path=S/(name+'.log')
    with path.open('x') as out:
        result=subprocess.run([str(a) for a in args],cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT)
    print(name, result.returncode, flush=True)
    if result.returncode: raise RuntimeError(str(path))

def main():
    global C, S, NODE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--custody', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True,
                        help='Prepared owned source exports and retained Node directory')
    parser.add_argument('--resolver-python', type=Path, required=True,
                        help='Verified isolated pip environment; no global installation')
    a = parser.parse_args()
    C, S = a.custody.resolve(), a.stage.resolve()
    NODE = S/'node-v24.21.0-linux-x64/bin'
    if (C/'python-inputs.json').exists():
        parser.error('Refusing to re-resolve an existing locked custody store; choose a new proposal directory')
    lab=tomllib.loads((S/'jupyterlab/pyproject.toml').read_text())
    hub=(S/'jupyterhub/requirements.txt').read_text()
    tests=['pytest','pytest-asyncio>=1.1','pytest-jupyter[server]','pytest-tornasync','pytest-timeout','pytest-console-scripts','pytest-check-links','pytest-xdist','requests-mock','mock','beautifulsoup4[html5lib]','cryptography','virtualenv','websocket-client','requests-cache','pytest-cov']
    build=['pip==26.2.1','setuptools>=77','setuptools-scm','wheel','build','hatchling>=1.21.1','hatch-jupyter-builder>=0.3.2','jupyter-builder==1.2.3']
    (S/'hub.in').write_text(hub+'\n'+'\n'.join(tests)+'\n')
    (S/'user.in').write_text(hub+'\n'+'\n'.join(lab['project']['dependencies']+tests)+'\n')
    (S/'build.in').write_text('\n'.join(build)+'\n')
    reports={}
    pip=str(a.resolver_python)
    for name in ['hub','user','build']:
        report=S/(name+'-resolve.json')
        if not report.exists():
            run([pip,'-m','pip','--isolated','install','--dry-run','--ignore-installed','--only-binary=:all:','--index-url','https://pypi.org/simple','--report',report,'-r',S/(name+'.in')],name=name+'-resolve')
        reports[name]=json.loads(report.read_text())
    entries={}
    for role,report in reports.items():
        locks=[]
        for item in report['install']:
            meta=item['metadata']; name=meta['name']; ver=meta['version']; download=item['download_info']; sha=download['archive_info']['hashes']['sha256']; url=download['url']; filename=url.rsplit('/',1)[1]
            assert name.lower().replace('_','-') not in {'jupyterhub','jupyterlab'}, name
            locks.append(f'{name}=={ver} --hash=sha256:{sha}')
            entries.setdefault((name,ver),{'name':name,'version':ver,'wheel':filename,'url':url,'sha256':sha,'roles':[],'license':meta.get('license_expression') or meta.get('license'),'project_urls':meta.get('project_url',[])})['roles'].append(role)
        (C/(role+'-requirements.txt')).write_text('\n'.join(sorted(locks))+'\n')
    def retain(item):
        fetch(item['url'],C/'wheels'/item['wheel'],item['sha256'])
        url=f'https://pypi.org/pypi/{item["name"]}/{item["version"]}/json'
        meta_path=C/'pypi-metadata'/(item['name']+'-'+item['version']+'.json')
        fetch(url,meta_path)
        meta=json.loads(meta_path.read_text())
        sdists=[x for x in meta['urls'] if x['packagetype']=='sdist']
        item['source']=[]
        for s in sdists:
            sha=fetch(s['url'],C/'python-sources'/s['filename'],s['digests']['sha256'])
            item['source'].append({'url':s['url'],'path':'python-sources/'+s['filename'],'sha256':sha})
        return item
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        result=list(pool.map(retain,entries.values()))
    (C/'python-inputs.json').write_text(json.dumps(result,indent=2)+'\n')
    print('retained Python distributions',len(result),'missing sdists',[x['name'] for x in result if not x['source']],flush=True)
    env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['TOKEN','PROXY','SECRET','PIP_','PYTHONPATH'])}
    env.update(PATH=str(NODE)+':/usr/bin:/bin',HOME=str(S/'home'),npm_config_cache=str(C/'npm-cache'),npm_config_audit='false',npm_config_fund='false',npm_config_ignore_scripts='true',npm_config_update_notifier='false')
    (S/'home').mkdir(exist_ok=True)
    boot=S/'bootstrap-env'
    if not boot.exists():run([sys.executable,'-m','venv',boot],name='bootstrap-venv')
    py=boot/'bin/python'
    run([py,'-m','pip','--isolated','install','--no-index','--find-links',C/'wheels','--require-hashes','-r',C/'build-requirements.txt'],name='bootstrap-install')
    env['PATH']=str(boot/'bin')+':'+env['PATH']
    for name,path in [('hub',S/'jupyterhub'),('hub-jsx',S/'jupyterhub/jsx')]:
        run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=path,env=env,name=name+'-npm-acquire')
    proxy=S/'proxy';proxy.mkdir(exist_ok=True)
    (proxy/'package.json').write_text(json.dumps({'name':'ambisgis-proxy-fixture','private':True,'dependencies':{'configurable-http-proxy':'5.3.0'}})+'\n')
    run(['npm','install','--ignore-scripts','--no-audit','--no-fund'],cwd=proxy,env=env,name='proxy-acquire')
    (C/'proxy-package.json').write_bytes((proxy/'package.json').read_bytes());(C/'proxy-package-lock.json').write_bytes((proxy/'package-lock.json').read_bytes())
    env.update(YARN_CACHE_FOLDER=str(C/'yarn-cache'),YARN_ENABLE_GLOBAL_CACHE='false',YARN_ENABLE_SCRIPTS='false',YARN_ENABLE_TELEMETRY='false')
    run(['jlpm','install','--immutable','--mode=skip-build'],cwd=S/'jupyterlab',env=env,name='lab-yarn-acquire')

if __name__=='__main__':main()
