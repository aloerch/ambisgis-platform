#!/usr/bin/env python3
"""Fresh real public-map browser/backend smoke; never reuses an attempt directory."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'geonode'), str(HERE.parent / 'java')]
from run import Capture, configure_database, digest, fresh_port, private_values, save
TASK = Path('/home/revelberry/Projects/AmbisGIS')
ROLE = TASK / 'build-worktrees/geonode-role-propagation'
WAR_SHA = 'a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52'


def tree_manifest(root):
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink(): raise ValueError('artifact tree contains a symlink')
        if path.is_file(): files[str(path.relative_to(root))] = digest(path)
    return files


def verify_manifest(root, path):
    document = json.loads(Path(path).read_text())
    rows = document.get('files') if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError('compiled output manifest must contain a nonempty files list')
    expected = {row['path']: row['sha256'] for row in rows}
    if len(expected) != len(rows):
        raise ValueError('compiled output manifest contains duplicate paths')
    if not isinstance(expected, dict) or not expected:
        raise ValueError('manifest must be a nonempty relative-path to SHA256 object')
    if tree_manifest(root) != expected:
        raise ValueError('frontend tree differs from complete compiled output manifest')
    if 'dist/js/gn-map.js' not in expected:
        raise ValueError('manifest does not identify the compiled integrated map entry')
    return expected


def wait_file(path, process, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists(): return json.loads(path.read_text())
        if process.poll() is not None: raise RuntimeError('backend exited before ' + path.name)
        time.sleep(.2)
    raise RuntimeError('timed out waiting for ' + path.name)


def run(args):
    import combined_logging_probe
    import configured_auth_database
    import installed
    import loopback_exec
    import runtime_inputs
    import toolchain
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    result = {'result_exit_code':1, 'scope':'FND-02 owned frontend public-map candidate, not browser SSO/policy/publishing acceptance', 'cleanup':{}}
    database = supervisor = None
    values = []
    config_path = output / 'private.json'
    try:
        frontend = verify_manifest(args.frontend.resolve(), args.frontend_manifest)
        save(output / 'frontend-input-manifest.json', frontend)
        result['frontend_manifest_sha256'] = digest(output / 'frontend-input-manifest.json')
        result['browser_retention_sha256'] = digest(args.browser_inputs / 'retention.json')
        browser_retention = json.loads((args.browser_inputs / 'retention.json').read_text())
        for item in browser_retention['sources']:
            if digest(item['archive']) != item['archive_sha256']: raise ValueError('retained browser archive changed')
            actual = tree_manifest(args.browser_inputs / item['name'])
            if actual != item['files']: raise ValueError('retained browser package changed')
        origin_before = installed.verify(args.python)
        save(output / 'installed-origin-before.json', origin_before)
        prefix = TASK / 'build-worktrees/postgis-slice/run-003/prefix'
        database = configured_auth_database.start(prefix, TASK / 'build-worktrees/postgis-slice/run-003-evidence-final.json', output / 'database')
        owner_db, runtime_db = configure_database(database, output)
        port = fresh_port()
        config = {'output':str(output), 'database':owner_db, 'runtime_database':runtime_db,
            'site_url':'http://127.0.0.1:' + str(port) + '/',
            'geoserver_url':'http://127.0.0.1:' + str(fresh_port()) + '/geoserver/',
            'secret_key':secrets.token_urlsafe(48), 'api_key':secrets.token_urlsafe(36),
            'client_id':'fixture-geoserver-' + secrets.token_hex(12), 'client_secret':secrets.token_urlsafe(36),
            'second_client_id':'fixture-second-app-' + secrets.token_hex(12), 'second_client_secret':secrets.token_urlsafe(36),
            'redirect_uri':'http://127.0.0.1:' + str(port) + '/fixture-callback',
            'passwords':{name:secrets.token_urlsafe(32) for name in ('fixture-reader','fixture-outsider','fixture-disabled','fixture-admin','fixture-unmapped')},
            'oidc_rsa_private_key_file':str(output / 'oidc-key.pem'), 'strict_verifier':True, 'strict_roles':True,
            'role_service_username':'fixture-role-service', 'role_service_api_key':secrets.token_urlsafe(36),
            'frontend':str(args.frontend.resolve())}
        values = private_values(config)
        subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',config['oidc_rsa_private_key_file']],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        Path(config['oidc_rsa_private_key_file']).chmod(0o600)
        save(config_path,config,private=True)
        env = {'PATH':str(args.python.parent) + ':' + str(prefix / 'bin') + ':/usr/bin:/bin',
            'HOME':str(output), 'LANG':'C.UTF-8', 'LC_ALL':'C.UTF-8',
            'LD_LIBRARY_PATH':str(prefix / 'lib') + ':' + str(prefix / 'lib64'),
            'PROJ_DATA':str(prefix / 'share/proj'),'PROJ_NETWORK':'OFF','GDAL_DATA':str(prefix / 'share/gdal'),
            'GDAL_LIBRARY_PATH':str(prefix / 'lib/libgdal.so'),'GEOS_LIBRARY_PATH':str(prefix / 'lib/libgeos_c.so'),
            'PYTHONPATH':str(HERE.parent / 'geonode'), 'PYTHONNOUSERSITE':'1', 'PYTHONPYCACHEPREFIX':str(output / 'python-cache')}
        tools = TASK / 'build-worktrees/java-resolution/toolchain'
        java_home = tools / 'jdk-17.0.20.1+1'
        result['java_toolchain'] = toolchain.verify_extracted(TASK / 'source-archives/java-resolution/toolchain',
            json.loads((HERE.parent / 'java/toolchain-inputs.json').read_text()),tools)
        build = ROLE / 'aggregate-repaired-02'
        inventory = combined_logging_probe.packaged_classpath(build,output)
        if inventory['war_sha256'] != WAR_SHA: raise ValueError('retained #61 WAR digest mismatch')
        save(output / 'application-inventory.json',inventory)
        result['servlet_inputs'] = runtime_inputs.stage(TASK / 'source-archives/java-http-auth/maven',output / 'servlet')
        result['launcher'] = runtime_inputs.compile_launcher(java_home,output / 'servlet',output / 'launcher')
        invocation = {'config':str(config_path),'python':str(args.python),'environment':env,'runtime':{
            'source':str(build / 'work/source'),'java_home':str(java_home),'servlet':str(output / 'servlet'),
            'launcher':str(output / 'launcher'),'war':inventory['war_path'],'war_sha256':WAR_SHA,
            'database_properties':str(database.properties_path)}}
        snapshot = output / 'tooling'
        for component in ('frontend','geonode','java','postgis'):
            for source in (HERE.parent / component).rglob('*'):
                if source.is_file() and source.suffix in ('.py','.json','.java','.cjs') and '__pycache__' not in source.parts:
                    target = snapshot / component / source.relative_to(HERE.parent / component)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,target)
        tooling = tree_manifest(snapshot)
        save(output / 'tooling.json',tooling)
        invocation['environment']['PYTHONPATH'] = str(snapshot / 'geonode')
        save(output / 'invocation.json',invocation)
        command = [sys.executable,'-B',str(snapshot / 'java/loopback_exec.py'),'--evidence',str(output / 'network-loopback.json'),
            '--timeout','900','--',sys.executable,'-B',str(snapshot / 'frontend/smoke_backend.py'),'child',str(output / 'invocation.json')]
        with (output / 'supervisor.log').open('x') as log:
            supervisor = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            ready = wait_file(output / 'ready-initial.json',supervisor,500)
            for phase in ('initial','restart'):
                if phase == 'restart':
                    (output / 'restart.request').write_text('restart task-owned services using unchanged artifacts\n')
                    restarted = wait_file(output / 'ready-restart.json',supervisor,220)
                    if restarted != {'same_frontend':True,'same_war':True}: raise RuntimeError('restart artifact identity mismatch')
                browser_dir = output / ('browser-' + phase)
                browser_dir.mkdir()
                browser_config = {'origin':ready['origin'],'geoserverOrigin':ready['geoserver_origin'],'route':ready['route'],
                    'mapId':ready['map_id'],'phase':phase,'output':str(browser_dir),'manifest':str(output / 'served-frontend-manifest.json'),
                    'playwright':str(args.browser_inputs / 'playwright-core'),'chromium':str(args.browser_inputs / 'chromium/chrome')}
                save(browser_dir / 'invocation.json',browser_config)
                with (browser_dir / 'console.log').open('x') as browser_log:
                    browser_process = subprocess.Popen([str(args.node),str(snapshot / 'frontend/browser.cjs'),str(browser_dir / 'invocation.json')],
                        stdout=browser_log,stderr=subprocess.STDOUT)
                    try: code = browser_process.wait(timeout=200)
                    except subprocess.TimeoutExpired:
                        browser_process.terminate()
                        try: browser_process.wait(timeout=15)
                        except subprocess.TimeoutExpired: browser_process.kill(); browser_process.wait(timeout=10)
                        raise RuntimeError('browser exceeded deadline; attempt fails')
                result['browser-' + phase] = json.loads((browser_dir / 'result.json').read_text())
                if code or result['browser-' + phase]['result_exit_code']: raise RuntimeError('browser ' + phase + ' failed')
            (output / 'stop.request').write_text('browser evidence complete\n')
            code = supervisor.wait(timeout=100)
        result['network'] = loopback_exec.verify_receipt(output / 'network-loopback.json',code)
        result['backend'] = json.loads((output / 'backend-result.json').read_text())
        origin_after = installed.verify(args.python)
        save(output / 'installed-origin-after.json',origin_after)
        if origin_before != origin_after: raise RuntimeError('installed owned backend changed')
        if tree_manifest(snapshot) != tooling: raise RuntimeError('executed tooling changed')
        if verify_manifest(args.frontend,args.frontend_manifest) != frontend: raise RuntimeError('compiled input changed')
        if code or result['backend']['result_exit_code']: raise RuntimeError('backend or network proof failed')
        result['result_exit_code'] = 0
    except Exception as error:
        message = str(error)
        for value in values:
            if value: message = message.replace(value,'[REDACTED]')
        result['error'] = {'type':type(error).__name__,'message':message}
    finally:
        if supervisor is not None and supervisor.poll() is None:
            (output / 'stop.request').write_text('stop on parent completion or failure\n')
            try: supervisor.wait(timeout=100)
            except subprocess.TimeoutExpired:
                supervisor.terminate()
                try: supervisor.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    result['cleanup']['supervisor_unresponsive'] = True
                    result['result_exit_code'] = 1
        if supervisor is not None:
            result['cleanup']['supervisor_exit_code'] = supervisor.poll()
            if supervisor.poll() != 0: result['result_exit_code'] = 1
        if database is not None:
            try:
                database.stop(); result['database'] = database.receipt
                if not database.receipt.get('stopped') or database.receipt.get('result_exit_code'): result['result_exit_code'] = 1
            except Exception as error: result['cleanup']['database_error'] = type(error).__name__; result['result_exit_code'] = 1
        for name in ('private.json','oidc-key.pem'):
            try:
                path = output / name
                if path.exists(): path.write_text('SCRUBBED DISPOSABLE FIXTURE SECRET\n')
            except Exception as error: result['cleanup']['secret_scrub_error'] = type(error).__name__; result['result_exit_code'] = 1
        result['database_supervisor_exception'] = 'Existing #61 PostgreSQL-only SCRAM loopback exception retained because native backend setsid is denied.'
        result['browser_containment'] = 'Browser runs separately with Chromium sandbox intact and exact task-origin application request allowlist; not ptrace/host network proof.'
        save(output / 'result.json',result)
    print(json.dumps({'output':str(output),'result_exit_code':result['result_exit_code'],'error':result.get('error')}))
    return result['result_exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend',required=True,type=Path)
    parser.add_argument('--frontend-manifest',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--python',type=Path,default=ROLE / 'run-003/venv/bin/python')
    parser.add_argument('--browser-inputs',type=Path,default=TASK / 'build-worktrees/frontend-completion/browser-inputs')
    parser.add_argument('--node',type=Path,default=TASK / 'build-worktrees/frontend-completion/inputs/node/node-v24.18.1-linux-x64/bin/node')
    raise SystemExit(run(parser.parse_args()))
