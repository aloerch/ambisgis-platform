#!/usr/bin/env python3
"""Bounded embedded GeoWebCache WMTS smoke with retained strict backend and private cache."""
import argparse
from datetime import datetime, timezone
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


def run(args):
    import combined_logging_probe
    import configured_auth_database
    import installed
    import loopback_exec
    import runtime_inputs
    import toolchain
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    result = {'started_at_utc':datetime.now(timezone.utc).isoformat(), 'runner_sha256':digest(__file__), 'result_exit_code':1, 'scope':'F02-05 embedded WMTS cold/warm/restart; bounded fixture, not full policy acceptance', 'cleanup':{}}
    database = supervisor = None
    values = []
    config_path = output / 'private.json'
    try:
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
            'role_service_username':'fixture-role-service', 'role_service_api_key':secrets.token_urlsafe(36)}
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
        build = args.build.resolve() if getattr(args, 'build', None) else ROLE / 'aggregate-repaired-02'
        expected_war = getattr(args, 'war_sha256', None) or WAR_SHA
        if bool(getattr(args, 'build', None)) != bool(getattr(args, 'war_sha256', None)):
            raise ValueError('variant build and exact WAR hash must be supplied together')
        if json.loads((build / 'result.json').read_text()).get('result_exit_code') != 0:
            raise ValueError('selected aggregate build did not succeed')
        inventory = combined_logging_probe.packaged_classpath(build,output)
        if inventory['war_sha256'] != expected_war: raise ValueError('retained #61 WAR digest mismatch')
        save(output / 'application-inventory.json',inventory)
        result['servlet_inputs'] = runtime_inputs.stage(TASK / 'source-archives/java-http-auth/maven',output / 'servlet')
        result['launcher'] = runtime_inputs.compile_launcher(java_home,output / 'servlet',output / 'launcher')
        invocation = {'config':str(config_path),'python':str(args.python),'environment':env,'runtime':{
            'source':str(build / 'work/source'),'java_home':str(java_home),'servlet':str(output / 'servlet'),
            'launcher':str(output / 'launcher'),'war':inventory['war_path'],'war_sha256':expected_war,
            'database_properties':str(database.properties_path)}}
        import runtime_profile
        invocation['runtime']['java_profile'] = runtime_profile.load(getattr(args, 'java_profile', None), inventory, output)
        result['java_profile'] = invocation['runtime']['java_profile']
        snapshot = output / 'tooling'
        for component in ('gwc','frontend','geonode','java','postgis'):
            for source in (HERE.parent / component).rglob('*'):
                if source.is_file() and source.suffix in ('.py','.json','.java','.cjs') and '__pycache__' not in source.parts:
                    target = snapshot / component / source.relative_to(HERE.parent / component)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,target)
        tooling = tree_manifest(snapshot)
        if tooling['gwc/smoke.py'] != result['runner_sha256']: raise RuntimeError('outer runner snapshot mismatch')
        staged_before = {'servlet':tree_manifest(output/'servlet'),'launcher':tree_manifest(output/'launcher')}
        save(output/'staged-runtime-manifest.json',staged_before)
        save(output / 'tooling.json',tooling)
        invocation['environment']['PYTHONPATH'] = str(snapshot / 'geonode')
        save(output / 'invocation.json',invocation)
        command = [sys.executable,'-B',str(snapshot / 'java/loopback_exec.py'),'--evidence',str(output / 'network-loopback.json'),
            '--timeout','900','--',str(args.python),'-B',str(snapshot / 'gwc/backend.py'),str(output / 'invocation.json')]
        result['command'] = command
        with (output / 'supervisor.log').open('x') as log:
            supervisor = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            code = supervisor.wait(timeout=950)
        result['network'] = loopback_exec.verify_receipt(output / 'network-loopback.json',code)
        result['backend'] = json.loads((output / 'backend-result.json').read_text())
        origin_after = installed.verify(args.python)
        save(output / 'installed-origin-after.json',origin_after)
        if origin_before != origin_after: raise RuntimeError('installed owned backend changed')
        if tree_manifest(snapshot) != tooling: raise RuntimeError('executed tooling changed')
        if {'servlet':tree_manifest(output/'servlet'),'launcher':tree_manifest(output/'launcher')} != staged_before: raise RuntimeError('staged container or launcher changed')
        if digest(__file__) != result['runner_sha256']: raise RuntimeError('outer runner changed during execution')
        if digest(inventory['war_path']) != expected_war: raise RuntimeError('WAR changed during run')
        if code or result['backend']['result_exit_code']: raise RuntimeError('backend or network proof failed')
        result['result_exit_code'] = 0
    except Exception as error:
        message = str(error)
        for value in values:
            if value: message = message.replace(value,'[REDACTED]')
        result['error'] = {'type':type(error).__name__,'message':message}
    finally:
        if supervisor is not None and supervisor.poll() is None:
            supervisor.terminate()
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
                if not database.receipt.get('stopped') or database.receipt.get('result_exit_code') or database.receipt.get('postgres_exit_code') != 0: result['result_exit_code'] = 1
            except Exception as error: result['cleanup']['database_error'] = type(error).__name__; result['result_exit_code'] = 1
        for name in ('private.json','oidc-key.pem'):
            try:
                path = output / name
                if path.exists(): path.write_text('SCRUBBED DISPOSABLE FIXTURE SECRET\n')
            except Exception as error: result['cleanup']['secret_scrub_error'] = type(error).__name__; result['result_exit_code'] = 1
        result['database_supervisor_exception'] = 'Existing #61 PostgreSQL-only SCRAM loopback exception retained because native backend setsid is denied.'
        result['containment'] = 'GeoNode, GeoServer, WMTS HTTP client and decoder use unchanged trusted-fixture loopback supervision; not hostile-code or host/filesystem isolation.'
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(output / 'result.json',result)
    print(json.dumps({'output':str(output),'result_exit_code':result['result_exit_code'],'error':result.get('error')}))
    return result['result_exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path)
    parser.add_argument('--war-sha256')
    parser.add_argument('--java-profile',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--python',type=Path,default=ROLE / 'run-003/venv/bin/python')
    raise SystemExit(run(parser.parse_args()))
