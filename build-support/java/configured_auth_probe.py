#!/usr/bin/env python3
"""Real configured GeoServer HTTP authorization checks on an exact retained WAR.

The identity endpoint is synthetic. The servlet, filter, catalog, GeoFence and
role services come from the packaged application. No response is manufactured
on the application side. Every attempt has separate, fail-closed evidence.
"""
import argparse
import base64
import concurrent.futures
import hashlib
import http.client
import http.server
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


class Identity:
    def __init__(self):
        self.client = 'fixture-client'
        self.secret = secrets.token_hex(24)
        self.basic = 'Basic ' + base64.b64encode((self.client + ':' + self.secret).encode()).decode()
        self.marker = 'identity-private-' + secrets.token_hex(16)
        self.tokens = {}
        self.extra_sensitive = []
        self.calls = []
        self.violations = []
        self.lock = threading.Lock()
        identity = self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *args): pass
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                values = urllib.parse.parse_qs(body.decode(), keep_blank_values=True)
                token = values.get('token', [None])[0]
                with identity.lock:
                    mode = identity.tokens.get(token, 'invalid')
                    valid = (self.path == '/verify_token' and self.headers.get('Authorization') == identity.basic
                             and set(values) == {'token'} and len(values['token']) == 1)
                    identity.calls.append(mode)
                    if not valid: identity.violations.append('unexpected-protocol')
                response = {'client_id': identity.client, 'issued_to': 'fixture-reader', 'expires_in': 60000}
                status = 200
                if not valid or mode in ('invalid', 'expired'): status, response = 403, {'error': identity.marker}
                elif mode == 'unauthorized': status, response = 401, {'error': identity.marker}
                elif mode == 'failure': status, response = 503, {'error': identity.marker}
                elif mode == 'disconnect': self.close_connection = True; return
                elif mode == 'outsider': response['issued_to'] = 'fixture-outsider'
                elif mode == 'disabled': response['issued_to'] = 'fixture-disabled'
                elif mode == 'root': response['issued_to'] = 'root'
                elif mode == 'unknown': response['issued_to'] = 'fixture-unprovisioned'
                elif mode == 'admin': response['issued_to'] = 'fixture-admin'
                elif mode == 'missing-principal': response.pop('issued_to')
                elif mode == 'empty-principal': response['issued_to'] = ''
                elif mode == 'blank-principal': response['issued_to'] = '   '
                elif mode == 'non-string-principal': response['issued_to'] = 42
                elif mode == 'missing-client': response.pop('client_id')
                elif mode == 'misleading-roles':
                    response.update(issued_to='fixture-outsider', authorities=['ROLE_ADMINISTRATOR', 'ROLE_FIXTURE_READER'], roles=['ROLE_ADMINISTRATOR'], private_data=identity.marker)
                elif mode == 'reader-misleading-roles': response.update(authorities=['ROLE_ADMINISTRATOR'], private_data=identity.marker)
                if mode == 'malformed': data = ('[broken-' + identity.marker).encode()
                else: data = json.dumps(response).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def token(self, mode):
        value = secrets.token_hex(24)
        with self.lock: self.tokens[value] = mode
        return value

    def sensitive(self):
        with self.lock: return [self.secret, self.basic, self.basic[6:], self.marker, *self.tokens, *self.extra_sensitive]

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)
        if self.thread.is_alive(): raise RuntimeError('identity endpoint did not stop')


class Matrix:
    def __init__(self, port, identity, stateless=False):
        self.port, self.identity = port, identity
        self.stateless = stateless
        self.rows = []
        self.leaks = []

    def request(self, name, path, token=None, method='GET', body=None, headers=None, expected=(200,), contains=None, excludes=('PRIVATE_WITNESS',), connection=None):
        h = dict(headers or {})
        h['X-AmbisGIS-Fixture-Case'] = name
        if token is not None: h['Authorization'] = 'Bearer ' + token
        owned = connection is None
        c = connection or http.client.HTTPConnection('127.0.0.1', self.port, timeout=35)
        before = len(self.identity.calls)
        try:
            c.request(method, '/geoserver' + path, body=body, headers=h)
            response = c.getresponse(); data = response.read()
            text = data.decode('utf-8', errors='replace')
            raw_headers = response.getheaders()
            response_headers = {key.lower():value for key,value in raw_headers}
            cookies = [value for key,value in raw_headers if key.lower() == 'set-cookie']
            if cookies: response_headers['set-cookie'] = '; '.join(cookies)
            leaks = sum(value in (text + str(raw_headers)) for value in self.identity.sensitive())
            if leaks: self.leaks.append({'case': name, 'count': leaks})
            ok = response.status in expected and not leaks and not (self.stateless and cookies)
            if contains in ('PUBLIC_WITNESS','PRIVATE_WITNESS'):
                from configured_auth_evidence import validate_geojson
                ok = ok and validate_geojson(text,contains)
            elif contains is not None: ok = ok and contains in text
            for value in excludes: ok = ok and value not in text
            ok = ok and (not any(value for key,value in raw_headers if key.lower() == 'location') or (response.status == 201 and method == 'POST')) and '<form' not in text.lower()
            self.rows.append({'case': name, 'method': method, 'path': path, 'expected_status': list(expected), 'status': response.status,
                              'body_sha256': hashlib.sha256(data).hexdigest(), 'body_size': len(data),
                              'content_type': response_headers.get('content-type'), 'content_assertion': contains, 'set_cookie_header_count': len(cookies),
                              'verification_calls': len(self.identity.calls) - before, 'passed': bool(ok)})
            return response.status, text, response_headers
        finally:
            if owned: c.close()

    def require_last(self):
        if not self.rows[-1]['passed']: raise RuntimeError('HTTP positive/setup control failed: ' + self.rows[-1]['case'])


def wfs(layer, route='/wfs'):
    return route + '?' + urllib.parse.urlencode({'service': 'WFS', 'version': '1.0.0', 'request': 'GetFeature',
                                                'typeName': 'fixture:' + layer, 'outputFormat': 'application/json'})


def exercise(matrix, fixture, restart=False):
    identity = matrix.identity
    admin = identity.token('admin')
    reader = identity.token('reader')
    if not restart:
        for i, body in enumerate(fixture['geofence_rule_bodies']):
            matrix.request('provision-geofence-' + str(i), '/rest/geofence/rules', admin, 'POST', body,
                           {'Content-Type': 'application/xml'}, expected=(200,201), excludes=())
            matrix.require_last()
    matrix.request('anonymous-public', wfs('public_points'), contains='PUBLIC_WITNESS'); matrix.require_last()
    matrix.request('reader-private', wfs('private_points'), reader, contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
    matrix.request('anonymous-private', wfs('private_points'), expected=(401,403,404))
    matrix.request('outsider-private', wfs('private_points'), identity.token('outsider'), expected=(401,403,404))
    matrix.request('admin-workspaces-json', '/rest/workspaces.json', admin, contains='fixture', excludes=()); matrix.require_last()
    if restart: return
    _,imports,_ = matrix.request('importer-initialization','/rest/imports',admin,headers={'Accept':'application/json'},contains='"imports"',excludes=())
    try: matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and json.loads(imports).get('imports') == []
    except (ValueError,AttributeError): matrix.rows[-1]['passed'] = False
    _,printing,_ = matrix.request('printing-info','/pdf/info.json',admin,headers={'Accept':'application/json'},contains='"scales"',excludes=())
    try:
        info=json.loads(printing)
        matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and all(isinstance(info.get(key),list) and info[key] for key in ('scales','layouts','dpis'))
    except (ValueError,AttributeError): matrix.rows[-1]['passed'] = False
    for mode in ('invalid','expired','unauthorized','failure','disconnect','missing-principal','empty-principal','blank-principal','non-string-principal','missing-client','malformed','misleading-roles','disabled','root','unknown'):
        matrix.request('fresh-' + mode, wfs('private_points'), identity.token(mode), expected=(401,403,404))
        matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and matrix.rows[-1]['verification_calls'] > 0
    matrix.request('empty-bearer', wfs('private_points'), '', expected=(401,403,404))
    matrix.request('reader-misleading-roles-private', wfs('private_points'), identity.token('reader-misleading-roles'), contains='PRIVATE_WITNESS', excludes=())
    # Real route/method controls on the same resource, including workspace routes.
    for route in ('/ows','/fixture/ows','/fixture/wfs'):
        matrix.request('reader-route-' + route, wfs('private_points', route), identity.token('reader'), contains='PRIVATE_WITNESS', excludes=())
        matrix.request('outsider-route-' + route, wfs('private_points', route), identity.token('outsider'), expected=(401,403,404))
    body = urllib.parse.urlsplit(wfs('private_points')).query
    for mode in ('reader','outsider'):
        matrix.request(mode + '-wfs-post', '/wfs', identity.token(mode), 'POST', body, {'Content-Type':'application/x-www-form-urlencoded'},
                       expected=(200,) if mode == 'reader' else (401,403,404), contains='PRIVATE_WITNESS' if mode == 'reader' else None,
                       excludes=() if mode == 'reader' else ('PRIVATE_WITNESS',))
    # Every denied create has an admin read proving absence, followed by same-route positive control.
    for suffix in ('', '.xml', '.json'):
        name = 'denied_fixture_' + (suffix[1:] or 'plain')
        body = json.dumps({'workspace':{'name':name}}) if suffix == '.json' else '<workspace><name>'+name+'</name></workspace>'
        content_type = 'application/json' if suffix == '.json' else 'application/xml'
        for mode in (None,'empty','reader','outsider','misleading-roles','reader-misleading-roles','invalid','expired'):
            matrix.request('denied-create-'+str(mode)+suffix, '/rest/workspaces'+suffix, None if mode is None else ('' if mode == 'empty' else identity.token(mode)), 'POST',body,{'Content-Type':content_type},expected=(401,403,404))
            matrix.request('unchanged-'+str(mode)+suffix, '/rest/workspaces/'+name+'.json', admin, expected=(404,), contains=name, excludes=())
        matrix.request('admin-create'+suffix, '/rest/workspaces'+suffix, admin, 'POST',body,{'Content-Type':content_type},expected=(200,201),excludes=());matrix.require_last()
        matrix.request('admin-read-created'+suffix, '/rest/workspaces/'+name+'.json',admin,contains=name,excludes=());matrix.require_last()
        for mode in ('reader','outsider'):
            matrix.request('denied-delete-'+mode+suffix,'/rest/workspaces/'+name+suffix,identity.token(mode),'DELETE',expected=(401,403,404))
            matrix.request('unchanged-after-delete-'+mode+suffix,'/rest/workspaces/'+name+'.json',admin,contains=name,excludes=())
        matrix.request('admin-delete'+suffix,'/rest/workspaces/'+name+suffix,admin,'DELETE',expected=(200,),excludes=());matrix.require_last()
    # A persistent HTTP/1.1 connection cycles identities; the bounded servlet pool is reused.
    connection = http.client.HTTPConnection('127.0.0.1', matrix.port, timeout=35)
    try:
        for n in range(32):
            mode = (None,'reader','outsider','admin')[n % 4]
            allowed = mode in ('reader','admin')
            matrix.request('sequential-'+str(n),wfs('private_points'), None if mode is None else identity.token(mode),
                           expected=(200,) if allowed else (401,403,404),contains='PRIVATE_WITNESS' if allowed else None,
                           excludes=() if allowed else ('PRIVATE_WITNESS',),connection=connection)
    finally: connection.close()
    def parallel_case(n):
        mode = (None,'reader','outsider','admin')[n % 4]
        allowed = mode in ('reader','admin')
        matrix.request('parallel-'+str(n),wfs('private_points'),None if mode is None else identity.token(mode),
                       expected=(200,) if allowed else (401,403,404),contains='PRIVATE_WITNESS' if allowed else None,
                       excludes=() if allowed else ('PRIVATE_WITNESS',))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(parallel_case,range(32)))
    # Cache is explicitly nonzero. Revocation changes the synthetic verifier only.
    token = identity.token('reader')
    matrix.request('cache-prime',wfs('private_points'),token,contains='PRIVATE_WITNESS',excludes=());matrix.require_last()
    identity.tokens[token] = 'expired'
    immediate = matrix.request('cache-after-revocation',wfs('private_points'),token,expected=(200,401,403,404),excludes=())
    from configured_auth_evidence import validate_geojson
    matrix.rows[-1]['observed_cached_allow'] = immediate[0] == 200 and validate_geojson(immediate[1],'PRIVATE_WITNESS')
    matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and (validate_geojson(immediate[1],'PRIVATE_WITNESS') if immediate[0] == 200 else ('PRIVATE_WITNESS' not in immediate[1]))
    if fixture.get('stateless_bearer_authentication'):
        matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and matrix.rows[-1]['observed_cached_allow'] and matrix.rows[-1]['verification_calls'] == 0
    time.sleep(fixture.get('cache_seconds',2) + 1.5)
    matrix.request('cache-after-expiry',wfs('private_points'),token,expected=(401,403,404))
    matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and matrix.rows[-1]['verification_calls'] > 0
    # Incidental sessions must not carry reader identity without fresh credentials.
    _,_,headers = matrix.request('session-reader',wfs('private_points'),identity.token('reader'),contains='PRIVATE_WITNESS',excludes=())
    cookie = headers.get('set-cookie','').split(';')[0]
    cookie_header_observed = matrix.rows[-1]['set_cookie_header_count'] > 0
    if cookie:
        matrix.request('session-without-bearer',wfs('private_points'),headers={'Cookie':cookie},expected=(401,403,404))
        matrix.request('session-outsider',wfs('private_points'),identity.token('outsider'),headers={'Cookie':cookie},expected=(401,403,404))
    matrix.rows.append({'case':'session-policy','passed':not cookie_header_observed if fixture.get('stateless_bearer_authentication') else True,'incidental_session_cookie_observed':cookie_header_observed,'stateless_bearer_authentication':fixture.get('stateless_bearer_authentication',False),
                        'logout_scope':'Stateless service mode must create no session; browser login/logout is outside this fixture.' if fixture.get('stateless_bearer_authentication') else 'Legacy OAuth created authenticated sessions; service fixture cookie denial checks remain required.'})


def child(config):
    from configured_auth_fixture import prepare, scrub_secrets
    import runtime_inputs
    from configured_auth_evidence import finalize_report
    out = Path(config['output'])
    identity = Identity()
    report = {'result_exit_code':1,'scenario_results':[], 'identity_is_synthetic':True, 'cleanup':{}}
    logs = []; leak_counts = []; process = None; thread = None; capture_errors = []
    fixture_dir = out/'data'
    try:
        fixture = prepare(Path(config['source']),fixture_dir,'http://127.0.0.1:'+str(identity.server.server_port),identity.client,identity.secret,stateless_bearer_authentication=config.get('stateless',False))
        properties=Path(config['database_properties']).read_text()
        identity.extra_sensitive.extend(line.split('=',1)[1] for line in properties.splitlines() if line.startswith('geofenceDataSource.password='))
        (fixture_dir/'geofence/geofence-datasource-ovr.properties').write_text(properties)
        fixture['database_properties_sha256']=digest(fixture_dir/'geofence/geofence-datasource-ovr.properties')
        for record in fixture['files']:
            if record['path']=='geofence/geofence-datasource-ovr.properties': record['sha256']=fixture['database_properties_sha256']
        save(out/'fixture.json',fixture)
        for round_name in ('configured','restart'):
            runtime = out/round_name
            command = runtime_inputs.launcher_command(Path(config['java']).parent.parent,Path(config['servlet']),Path(config['launcher']),Path(config['war']),fixture_dir,runtime)
            process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace', env={'PATH':str(Path(config['java']).parent)+':/usr/bin:/bin','LANG':'C.UTF-8'})
            def capture(proc, destination, label=round_name):
                try:
                    with destination.open('x') as f:
                        for line in proc.stdout:
                            sensitive = identity.sensitive()
                            hits = sum(value in line for value in sensitive)
                            if hits: leak_counts.append({'stream':label,'count':hits})
                            for value in sensitive: line = line.replace(value,'[REDACTED_FIXTURE_VALUE]')
                            f.write(line); f.flush()
                except Exception as error:
                    capture_errors.append({'type':type(error).__name__,'message':'runtime diagnostic capture failed'})
            thread = threading.Thread(target=capture,args=(process,out/(round_name+'-runtime.log')),daemon=True);thread.start()
            deadline=time.monotonic()+150
            ready=runtime/'ready.json'
            while not ready.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.25)
            if not ready.exists():raise RuntimeError('WAR did not reach ready state: '+round_name)
            information=json.loads(ready.read_text());report[round_name]=information
            active=information.get('security_configuration',{})
            if config.get('stateless') and active.get('stateless_bearer_authentication') is not True:
                raise RuntimeError('actual loaded OAuth configuration is not stateless')
            if active.get('role_source')!='UserGroupService' or active.get('user_group_service')!='fixture':
                raise RuntimeError('actual loaded role service differs from fixture')
            matrix=Matrix(information['port'],identity,stateless=config.get('stateless',False))
            try:exercise(matrix,fixture,restart=round_name=='restart')
            finally:
                report['scenario_results'].extend(dict(row,round=round_name) for row in matrix.rows)
                report.setdefault('response_leaks',[]).extend(matrix.leaks)
            process.terminate(); process.wait(timeout=40);thread.join(10)
            report['cleanup'][round_name]={'process_stopped':process.poll() is not None,'log_reader_stopped':not thread.is_alive()}
            process=None
        report['worker_reuse']={}
        request_rows=[json.loads(line) for line in (out/'configured/requests.jsonl').read_text().splitlines()]
        by_thread={}
        for row in request_rows:
            if row['case'].startswith('sequential-'):
                by_thread.setdefault(row['thread'],[]).append(row)
        report['worker_reuse']={'requests':sum(len(rows) for rows in by_thread.values()),'threads':by_thread,
            'mixed_authorization_on_reused_worker':any(any(row['status']==200 for row in rows) and any(row['status'] in (401,403,404) for row in rows) for rows in by_thread.values())}
        if report['worker_reuse']['requests']!=32 or not report['worker_reuse']['mixed_authorization_on_reused_worker']:raise RuntimeError('missing real mixed-identity worker reuse evidence')
        report['logger_capture_controls']={name+'-'+kind:(out/(name+'-runtime.log')).read_text().count('AMBISGIS_CONFIGURED_'+kind+'_LOG_CAPTURE_CONTROL') for name in ('configured','restart') for kind in ('OAUTH','CACHE')}
        report['protocol']={'per_row_verification_calls_scope':'Global counter deltas; sequential rows are isolated, concurrent row windows overlap and are not per-request attribution.','verify_calls':len(identity.calls),'violations':identity.violations,'mode_counts':{x:identity.calls.count(x) for x in sorted(set(identity.calls))}}
        report['diagnostic_leaks']=leak_counts
        report['result_exit_code']=int(bool(leak_counts or identity.violations or report.get('response_leaks') or any(not r['passed'] for r in report['scenario_results']) or any(count != 1 for count in report['logger_capture_controls'].values()) or any(not v for row in report['cleanup'].values() if isinstance(row,dict) for v in row.values())))
    except Exception as error:
        report['error']={'type':type(error).__name__,'message':str(error)}
        report['diagnostic_leaks']=leak_counts
    finally:
        def finalize_step(name, operation):
            try:
                operation()
            except Exception as error:
                report['result_exit_code']=1
                report.setdefault('finalization_errors',[]).append({'step':name,'type':type(error).__name__,'message':str(error)})
        def stop_process():
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=35)
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait(timeout=10);report['cleanup']['forced_kill']=True
                report['cleanup']['last_process_stopped']=process.poll() is not None
            if thread is not None:
                thread.join(10)
                report['cleanup']['last_reader_stopped']=not thread.is_alive()
        finalize_step('stop-application',stop_process)
        def stop_identity():
            identity.close();report['cleanup']['identity_stopped']=True
        finalize_step('stop-identity',stop_identity)
        def scrub():
            if fixture_dir.exists(): scrub_secrets(fixture_dir)
            if config.get('database_properties'):
                private=Path(config['database_properties']);raw=private.read_text()
                for value in identity.sensitive(): raw=raw.replace(value,'[REDACTED_FIXTURE_VALUE]')
                private.write_text(raw)
            for path in out.rglob('*'):
                if path.is_file() and path.suffix not in ('.jar','.war','.class'):
                    raw=path.read_bytes();changed=False
                    for value in identity.sensitive():
                        if value.encode() in raw:
                            raw=raw.replace(value.encode(),b'[REDACTED_FIXTURE_VALUE]');changed=True
                    if changed:
                        path.write_bytes(raw)
                        report.setdefault('residual_secret_files_redacted',[]).append(str(path.relative_to(out)))
                        report['result_exit_code']=1
        finalize_step('scrub-fixture',scrub)
        def verify_war():
            report['war_sha256_after']=digest(config['war'])
            if report['war_sha256_after']!=config['war_sha256']:raise ValueError('WAR changed during runtime')
        finalize_step('verify-war',verify_war)
        report['capture_errors']=capture_errors
        report = finalize_report(report,out/'http-result.json',identity.sensitive())
    return report['result_exit_code']


def run(args):
    import combined_logging_probe
    import loopback_exec
    import runtime_inputs
    import configured_auth_database
    import toolchain
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    database=None
    result={'result_exit_code':1,'scope':'configured inherited component enforcement, not product/security acceptance'}
    try:
        if args.stateless:
            packaged=json.loads((args.build.resolve()/'result.json').read_text())
            if not packaged.get('configured_auth_stateless',{}).get('repair_applied'):
                raise ValueError('stateless fixture requires verified source-repaired aggregate')
        tool_manifest=json.loads(Path(__file__).with_name('toolchain-inputs.json').read_text())
        expected_java=next(row['root'] for row in tool_manifest['archives'] if row['role']=='distribution' and row['path'].startswith('OpenJDK'))
        if args.java_home.resolve().name!=expected_java: raise ValueError('Java home does not match retained toolchain')
        result['toolchain']=toolchain.verify_extracted(args.toolchain_custody.resolve(),tool_manifest,args.java_home.resolve().parent)
        inventory=combined_logging_probe.packaged_classpath(args.build.resolve(),out)
        save(out/'application-inventory.json',inventory)
        runtime=runtime_inputs.stage(args.custody.resolve(),out/'servlet')
        compiled=runtime_inputs.compile_launcher(args.java_home.resolve(),out/'servlet',out/'launcher')
        # Helpers return explicit paths; retained inputs and launcher are independent of WAR classpath.
        cp=':'.join(str(p) for p in sorted((out/'servlet/lib').glob('*.jar')))+':'+str(out/'launcher/classes')
        config={'output':str(out),'source':str(args.build.resolve()/'work/source'),
                'java':str(args.java_home.resolve()/'bin/java'),'stateless':args.stateless,'classpath':cp,'servlet':str(out/'servlet'),'launcher':str(out/'launcher'),'war':inventory['war_path'],'war_sha256':inventory['war_sha256']}
        database=configured_auth_database.start(Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/postgis-slice/run-003/prefix'),Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/postgis-slice/run-003-evidence-final.json'),out/'database')
        config['database_properties']=str(database.properties_path)
        result['database_control_limitation']='Native PostgreSQL backends require setsid denied by retained supervisor (observed postgres-supervised-01); owned database runs outside supervisor with authenticated loopback-only TCP/no Unix, app and IDP remain supervised.'
        save(out/'invocation.json',config)
        tooling=out/'tooling/java';tooling.mkdir(parents=True)
        (out/'tooling/postgis').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1]/'postgis/offline_exec.py',out/'tooling/postgis/offline_exec.py')
        for p in Path(__file__).parent.rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json','.java') and '__pycache__' not in p.parts:
                target=tooling/p.relative_to(Path(__file__).parent);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        hashes={str(p.relative_to(tooling)):digest(p) for p in tooling.rglob('*') if p.is_file()}
        save(out/'tooling.json',hashes)
        command=[sys.executable,str(tooling/'loopback_exec.py'),'--evidence',str(out/'network-loopback.json'),'--timeout','600','--',sys.executable,str(tooling/Path(__file__).name),'--child',str(out/'invocation.json')]
        with (out/'supervisor.log').open('x') as log:completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=650)
        result['command']=command;result['exit_code']=completed.returncode
        result['network']=loopback_exec.verify_receipt(out/'network-loopback.json',completed.returncode)
        result['http']=json.loads((out/'http-result.json').read_text())
        if any(digest(tooling/name)!=sha for name,sha in hashes.items()):raise ValueError('executed harness changed')
        if digest(inventory['war_path'])!=inventory['war_sha256']:raise ValueError('WAR changed during test')
        result['toolchain_after']=toolchain.verify_extracted(args.toolchain_custody.resolve(),tool_manifest,args.java_home.resolve().parent)
        result['artifact_sha256']=inventory['war_sha256']
        result['runtime']=runtime;result['launcher']=compiled
        result['result_exit_code']=0 if completed.returncode==0 and result['http']['result_exit_code']==0 else 1
    except Exception as error:result['error']={'type':type(error).__name__,'message':str(error)}
    if database is not None:
        try:
            database.stop(); result['database']=database.receipt
            if not database.receipt.get('stopped') or database.receipt.get('result_exit_code') != 0: result['result_exit_code']=1
        except Exception as error:
            result['result_exit_code']=1;result['database_cleanup_error']=type(error).__name__
    save(out/'result.json',result)
    print(json.dumps({'result_exit_code':result['result_exit_code'],'error':result.get('error'),'output':str(out)}))
    return result['result_exit_code']


if __name__=='__main__':
    if sys.argv[1:2]==['--child']:raise SystemExit(child(json.loads(Path(sys.argv[2]).read_text())))
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build','custody','toolchain-custody','java-home','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--stateless',action='store_true',help='require and exercise explicit opt-in stateless source repair')
    raise SystemExit(run(parser.parse_args()))
