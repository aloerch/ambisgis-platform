#!/usr/bin/env python3
"""Finite F02-04 runtime controller. Every attempt gets a new retained directory.

PostgreSQL alone retains the documented existing supervision exception. QGIS
fixture generation, real desktop and native server run inside loopback_exec.
This is trusted-fixture egress containment, not hostile-code isolation.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
from xml.sax.saxutils import escape

from runtime_common import POINTS, inventory, require, save, sha

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'java'))
TASK = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/qgis-candidate')


def private_write(path, value):
    descriptor = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream: stream.write(value)


def redact(value, sensitive):
    value = str(value)
    for secret in sensitive:
        if secret: value = value.replace(secret,'[REDACTED_FIXTURE_VALUE]')
    return value


def validate_config(config):
    for key in ('python','qgis_prefix','spatial_prefix','database_prefix','database_evidence',
                'support_prefix','qt_plugins','font_file','gdal_library'):
        require(key in config and Path(config[key]).is_absolute() and Path(config[key]).exists(), 'missing absolute retained input: '+key)
    for key in ('library_paths','python_paths'):
        require(isinstance(config.get(key),list) and config[key], 'explicit input paths required: '+key)
        require(all(Path(p).is_absolute() and Path(p).is_dir() for p in config[key]), 'input path missing: '+key)
    prefix = Path(config['qgis_prefix']).resolve()
    for key, default in (('desktop',prefix/'bin/qgis'),('server',prefix/'bin/qgis_mapserver')):
        config[key] = str(Path(config.get(key,default)).resolve())
        require(Path(config[key]).is_file() and Path(config[key]).is_relative_to(prefix), 'owned staged executable missing: '+key)
    require(Path(config['gdal_library']).resolve().is_relative_to(Path(config['spatial_prefix']).resolve()) or
            Path(config['gdal_library']).resolve().is_relative_to(Path(config['database_prefix']).resolve()), 'GDAL must come from retained native prefix')
    return config


def build_environment(config, output):
    """No inherited HOME, Python, Qt, proxy, GDAL or application configuration."""
    output = Path(output)
    for name in ('home','config','cache','data','tmp','auth','runtime-dir','empty-plugins','fonts','font-cache'):
        (output/name).mkdir(mode=0o700,exist_ok=True)
    font = output/'fonts'/Path(config['font_file']).name
    if not font.exists(): shutil.copyfile(config['font_file'],font)
    (output/'fonts.conf').write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>'+escape(str(output/'fonts'))+'</dir><cachedir>'+escape(str(output/'font-cache'))+'</cachedir></fontconfig>\n')
    prefix = Path(config['qgis_prefix']); native = Path(config['database_prefix'])
    env = {'PATH':str(Path(config['python']).parent)+':'+str(prefix/'bin')+':'+str(native/'bin')+':/usr/bin:/bin',
           'HOME':str(output/'home'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
           'XDG_CONFIG_HOME':str(output/'config'),'XDG_CACHE_HOME':str(output/'cache'),
           'XDG_DATA_HOME':str(output/'data'),'XDG_RUNTIME_DIR':str(output/'runtime-dir'),'TMPDIR':str(output/'tmp'),
           'LD_LIBRARY_PATH':':'.join(config['library_paths']),
           'PYTHONPATH':str(HERE)+':'+':'.join(config['python_paths']),
           'PYTHONNOUSERSITE':'1','PYTHONPYCACHEPREFIX':str(output/'cache/python'),
           'QT_PLUGIN_PATH':config['qt_plugins'],'QT_QPA_PLATFORM':'offscreen',
           'QT_QPA_FONTDIR':str(output/'fonts'),'FONTCONFIG_FILE':str(output/'fonts.conf'),
           'QGIS_PREFIX_PATH':config['qgis_prefix'],'QGIS_PLUGINPATH':config.get('provider_path',str(prefix/'lib/qgis/plugins')),
           'QGIS_AUTH_DB_DIR_PATH':str(output/'auth'),'QGIS_SERVER_PARALLEL_RENDERING':'0','QGIS_SERVER_MAX_THREADS':'1',
           'QGIS_SERVER_LOG_LEVEL':'1','QGIS_SERVER_LOG_STDERR':'1',
           'PROJ_DATA':config.get('proj_data',str(native/'share/proj')),'PROJ_NETWORK':'OFF',
           'GDAL_DATA':config.get('gdal_data',str(Path(config['spatial_prefix'])/'share/gdal')),
           'PGSERVICEFILE':str(output/'pg_service.conf'),'PGPASSFILE':str(output/'pgpass'),
           'AMBISGIS_QGIS_RUNTIME_CONFIG':str(output/'runtime-config.json')}
    return env


def configure_database(database, output):
    password = secrets.token_urlsafe(40); database.secret_values.append(password)
    database.sql('qgis-reader',"CREATE ROLE fixture_qgis_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '"+password+"';\nALTER ROLE fixture_qgis_reader SET default_transaction_read_only=on;\n")
    database.sql('qgis-database','CREATE DATABASE fixture_qgis;\nREVOKE ALL ON DATABASE fixture_qgis FROM PUBLIC;\nGRANT CONNECT ON DATABASE fixture_qgis TO fixture_qgis_reader;\n')
    rows = ','.join("(%d,'%s',ST_SetSRID(ST_MakePoint(%s,%s),4326))" % row for row in POINTS)
    database.sql('qgis-data',"CREATE EXTENSION postgis VERSION '3.5.7';\nREVOKE CREATE ON SCHEMA public FROM PUBLIC;\nCREATE TABLE public.points(id integer PRIMARY KEY,label text NOT NULL,geom geometry(Point,4326) NOT NULL);\nINSERT INTO public.points VALUES "+rows+";\nGRANT USAGE ON SCHEMA public TO fixture_qgis_reader;\nGRANT SELECT ON public.points TO fixture_qgis_reader;\n",'fixture_qgis')
    hba = database.data/'pg_hba.conf'
    hba.write_text('host fixture_qgis fixture_qgis_reader 127.0.0.1/32 scram-sha-256\n'+hba.read_text())
    database.sql('qgis-reload','SELECT pg_reload_conf();\n')
    private_write(output/'pg_service.conf','[qgis_fixture]\nhost=127.0.0.1\nport='+str(database.port)+'\ndbname=fixture_qgis\nuser=fixture_qgis_reader\nsslmode=disable\nconnect_timeout=5\n')
    private_write(output/'pgpass','127.0.0.1:'+str(database.port)+':fixture_qgis:fixture_qgis_reader:'+password+'\n')
    env = {**database.env,'PGSERVICEFILE':str(output/'pg_service.conf'),'PGPASSFILE':str(output/'pgpass'),'PGSERVICE':'qgis_fixture'}
    args = [str(database.prefix/'bin/psql'),'-X','--no-password','-A','-t','-v','ON_ERROR_STOP=1']
    read = subprocess.run(args,input="SELECT json_build_object('user',current_user,'read_only',current_setting('default_transaction_read_only'),'count',(SELECT count(*) FROM public.points),'select',has_table_privilege(current_user,'public.points','SELECT'),'insert',has_table_privilege(current_user,'public.points','INSERT'),'update',has_table_privilege(current_user,'public.points','UPDATE'),'delete',has_table_privilege(current_user,'public.points','DELETE'));\n",env=env,text=True,capture_output=True,timeout=20)
    require(read.returncode == 0,'restricted database credential failed')
    identity = json.loads(read.stdout)
    require(identity == {'user':'fixture_qgis_reader','read_only':'on','count':3,'select':True,'insert':False,'update':False,'delete':False},'runtime database privileges are not restricted')
    denied = subprocess.run(args,input="SET default_transaction_read_only=off; INSERT INTO public.points VALUES(99,'forbidden',ST_SetSRID(ST_MakePoint(0,0),4326));\n",env=env,text=True,capture_output=True,timeout=20)
    require(denied.returncode != 0 and 'permission denied for table points' in denied.stderr,'runtime INSERT permission denial not demonstrated')
    save(output/'database-privileges.json',{'identity':identity,'write_denied_even_without_readonly_default':True})
    return password


def run(config_path, output):
    import configured_auth_database
    import loopback_exec
    output = output.resolve()
    require(output.is_relative_to(TASK) and output != TASK,'runtime output must be a fresh child of qgis-candidate')
    output.mkdir(parents=True,exist_ok=False,mode=0o700); output.chmod(0o700)
    database = None; values = []; snapshot = None; supervisor = None; before = None; roots = None
    report = {'result_exit_code':1,'cleanup':{},'scope':'F02-04 Linux synthetic vector/raster/CRS/PostGIS desktop/server smoke',
              'database_supervisor_exception':'Existing #59 limitation: owned disposable PostgreSQL alone runs outside unchanged supervisor because backend setsid is denied.'}
    try:
        config = validate_config(json.loads(config_path.read_text()))
        config.update(output=str(output),config_path=str(output/'runtime-config.json'),pgpass=str(output/'pgpass'))
        environment = build_environment(config,output)
        roots = {key:Path(config[key]).resolve() for key in ('qgis_prefix','spatial_prefix','database_prefix')}
        before = {key:inventory(path) for key,path in roots.items()}
        save(output/'artifact-integrity-before.json',before)
        tooling = output/'tooling'
        for component,names in {'qgis':[p.name for p in HERE.glob('*.py')],
            'java':['loopback_exec.py','configured_auth_database.py','geofence_fixture.py'],
            'postgis':['offline_exec.py']}.items():
            for name in names:
                target = tooling/component/name; target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(HERE.parent/component/name,target)
        snapshot = inventory(tooling); save(output/'tooling.json',snapshot)
        environment['PYTHONPATH'] = str(tooling/'qgis')+':'+':'.join(config['python_paths'])
        save(output/'runtime-config.json',config); save(output/'environment.json',environment)
        database = configured_auth_database.start(config['database_prefix'],config['database_evidence'],output/'database')
        values = database.secret_values
        configure_database(database,output)
        command = [sys.executable,str(tooling/'java/loopback_exec.py'),'--evidence',str(output/'network-loopback.json'),'--timeout','600','--',config['python'],str(tooling/'qgis/runtime_child.py'),str(output/'runtime-config.json')]
        with (output/'supervisor.log').open('x') as log:
            supervisor = subprocess.Popen(command,env=environment,stdout=log,stderr=subprocess.STDOUT)
            try: code = supervisor.wait(timeout=650)
            except subprocess.TimeoutExpired:
                supervisor.terminate()
                try: supervisor.wait(timeout=45)
                except subprocess.TimeoutExpired: raise RuntimeError('runtime supervisor cleanup unresponsive')
                raise RuntimeError('runtime supervisor deadline exceeded')
        report['network'] = loopback_exec.verify_receipt(output/'network-loopback.json',code)
        report['child'] = json.loads((output/'child-result.json').read_text())
        after = {key:inventory(path) for key,path in roots.items()}
        save(output/'artifact-integrity-after.json',after)
        require(before == after,'staged/native artifact integrity changed during runtime')
        report['artifact_integrity_unchanged'] = True
        require(snapshot == inventory(tooling),'executed tooling changed')
        report['tooling_integrity_unchanged'] = True
        require(code == 0 and report['child']['result_exit_code'] == 0,'runtime witness failed')
        report['result_exit_code'] = 0
    except BaseException as error:
        report['error'] = {'type':type(error).__name__,'message':redact(error,values)}
    finally:
        if supervisor is not None and supervisor.poll() is None:
            try:
                supervisor.terminate(); supervisor.wait(timeout=45)
                report['cleanup']['supervisor_stopped_after_failure'] = True
            except BaseException as error:
                report['cleanup']['supervisor_error'] = type(error).__name__
                report['result_exit_code'] = 1
        if before is not None and not report.get('artifact_integrity_unchanged'):
            try:
                after = {key:inventory(path) for key,path in roots.items()}
                report['artifact_integrity_unchanged'] = before == after
                if not (output/'artifact-integrity-after.json').exists(): save(output/'artifact-integrity-after.json',after)
                require(before == after,'artifact integrity changed')
            except BaseException as error:
                report['integrity_error'] = type(error).__name__; report['result_exit_code'] = 1
        if snapshot is not None:
            report['tooling_integrity_unchanged'] = snapshot == inventory(output/'tooling')
            if not report['tooling_integrity_unchanged']: report['result_exit_code'] = 1
        if database is not None:
            try:
                if database.process is not None and database.process.poll() is None:
                    database.sql('qgis-invalidate',"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename='fixture_qgis_reader' AND pid<>pg_backend_pid();\nDO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='fixture_qgis_reader') THEN ALTER ROLE fixture_qgis_reader NOLOGIN PASSWORD NULL; END IF; END $$;\nALTER ROLE fixture_geofence NOLOGIN PASSWORD NULL;\nALTER ROLE fixture_owner NOLOGIN PASSWORD NULL;\n")
                    report['cleanup']['database_credentials_invalidated'] = True
            except BaseException as error:
                report['cleanup']['credential_error'] = redact(error,values); report['result_exit_code'] = 1
            finally:
                try:
                    database.stop(); report['database'] = database.receipt
                    require(database.receipt.get('stopped') and not database.receipt.get('result_exit_code'),'database cleanup failed')
                except BaseException as error:
                    report['cleanup']['database_error'] = redact(error,values); report['result_exit_code'] = 1
        report['cleanup']['private_files_scrubbed'] = True
        for name in ('pgpass','pg_service.conf'):
            try:
                if (output/name).exists(): (output/name).write_text('SCRUBBED DISPOSABLE FIXTURE CREDENTIAL\n')
            except BaseException as error:
                report['cleanup']['private_files_scrubbed'] = False; report['result_exit_code'] = 1
        # Final scan covers projects, receipts and diagnostics, excluding binary DB
        # pages. Detection sanitizes retained text and fails the overall receipt.
        hits = []
        for path in output.rglob('*'):
            if not path.is_file() or 'data' in path.relative_to(output).parts and 'database' in path.relative_to(output).parts: continue
            if path.suffix not in ('.json','.log','.qgs','.ini','.conf','.properties','.txt') and path.name != 'pgpass': continue
            try:
                text = path.read_text(); safe = redact(text,values)
                if safe != text: path.write_text(safe); hits.append(str(path.relative_to(output)))
            except UnicodeDecodeError: continue
            except BaseException as error:
                report['cleanup']['scan_error'] = type(error).__name__; report['result_exit_code'] = 1
        report['cleanup']['diagnostic_secret_hits'] = hits
        if hits: report['result_exit_code'] = 1
        save(output/'result.json',report)
    print(json.dumps({'output':str(output),'result_exit_code':report['result_exit_code'],'error':report.get('error')}))
    return report['result_exit_code']


if __name__ == '__main__':
    def interrupted(signum,frame): raise KeyboardInterrupt('runtime interrupted; cleaning task-owned services')
    signal.signal(signal.SIGTERM,interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); raise SystemExit(run(args.config,args.output))
