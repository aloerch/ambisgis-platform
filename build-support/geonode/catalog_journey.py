"""Fresh real two-user WFS journey through gateway and mandatory engine policy."""
import concurrent.futures
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from protocol_probe import OAuthBrowser, SecretRegistry
from journey import LiveEvidence
from configured_auth_probe import Matrix
import configured_auth_fixture
import runtime_inputs

HERE = Path(__file__).resolve().parent


def exercise(invocation, config, private):
    from run import Capture, digest, save, stop
    output = Path(config['output'])
    runtime = invocation['runtime']
    origin = config['site_url'].rstrip('/')
    registry = SecretRegistry()
    registry.add(*private)
    browsers, processes, captures = [], {}, []
    identity = LiveEvidence(output / 'geonode-runtime.log', registry, browsers, private)
    report = {'result_exit_code':1, 'authority':'GeoNode ResourceBase / guardian / native access tokens',
        'identity_is_synthetic':False, 'fixture_data':'Synthetic two-user catalog and geometry only',
        'requests':[], 'mutations':[], 'cleanup':{}, 'positive_decision_cache':False}
    data = output / 'geoserver-data'
    keyfile = output / 'policy-key.txt'
    keyfile.write_text(config['policy_key']); keyfile.chmod(0o600)

    def start(name, command, ready, environment=None):
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors='replace', env=environment or invocation['environment'])
        capture = Capture(process, output / (name + '.log'), identity.sensitive)
        processes[name] = (process, capture); captures.append(capture)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline and process.poll() is None:
            if capture.path.exists() and ready(capture.path): return
            time.sleep(.2)
        raise RuntimeError('service failed to become ready: ' + name)

    def stopped(name):
        process, capture = processes.pop(name)
        stop(process, capture)
        report['cleanup'][name] = {'stopped':process.poll() is not None, 'secret_hits':capture.security_failures}

    def mutation(action):
        command = [invocation['python'], str(HERE / 'catalog_fixture.py'), '--config', invocation['config'], action]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors='replace', env=invocation['environment'])
        capture = Capture(process, output / ('catalog-%02d.log' % len(report['mutations'])), identity.sensitive)
        captures.append(capture)
        code = process.wait(timeout=90); capture.finish()
        acknowledgments = []
        for line in capture.path.read_text().splitlines():
            try: record = json.loads(line)
            except ValueError: continue
            if record.get('event') == 'catalog_committed': acknowledgments.append(record)
        if code or capture.security_failures or len(acknowledgments) != 1:
            raise RuntimeError('catalog mutation failed: ' + action)
        report['mutations'].append(acknowledgments[0]); return acknowledgments[0]

    def engine(label, protected):
        target = output / label
        command = runtime_inputs.launcher_command(Path(runtime['java_home']), Path(runtime['servlet']),
            Path(runtime['launcher']), Path(runtime['war']), data, target,
            port=urlsplit(config['geoserver_url']).port, java_profile=runtime.get('java_profile'))
        if protected:
            command[1:1] = ['-Dambisgis.catalog.origin=' + origin, '-Dambisgis.catalog.keyFile=' + str(keyfile)]
        start(label, command, lambda _: (target / 'ready.json').exists(),
              {'PATH':str(Path(runtime['java_home']) / 'bin') + ':/usr/bin:/bin', 'LANG':'C.UTF-8'})
        report[label] = json.loads((target / 'ready.json').read_text())

    def request(case, route, layer='public_points', principal=None, allowed=True, path=None, method='GET', headers=None):
        port = config['gateway_port'] if route == 'gateway' else urlsplit(config['geoserver_url']).port
        if path is None:
            path = '/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=fixture:' + layer + '&outputFormat=application/json'
        if route == 'engine': path = '/geoserver' + path
        supplied = dict(headers or {})
        if principal is not None: supplied['Authorization'] = 'Bearer ' + tokens[principal]
        supplied['X-AmbisGIS-Fixture-Case'] = case + '-' + route
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
        started = time.monotonic_ns()
        try:
            connection.request(method, path, headers=supplied)
            response = connection.getresponse(); body = response.read()
            status = response.status
            response_bytes = body + repr(response.getheaders()).encode()
            secret_free = all(not value or value.encode() not in response_bytes for value in identity.sensitive())
            if allowed:
                payload = json.loads(body)
                label = configured_auth_fixture.LAYERS[layer]
                passed = status == 200 and payload.get('type') == 'FeatureCollection' and len(payload.get('features', [])) == 1
                passed = passed and label in body.decode() and payload['features'][0]['geometry']['coordinates'] == [1,2]
            else:
                passed = status in (401,403,404,503) and all(value.encode() not in body for value in configured_auth_fixture.LAYERS.values())
            passed = passed and secret_free and response.getheader('Cache-Control') == 'no-store' and response.getheader('Set-Cookie') is None
            report['requests'].append({'case':case, 'route':route, 'principal':principal, 'expected_allow':allowed,
                'status':status, 'bytes':len(body), 'body_sha256':hashlib.sha256(body).hexdigest(),
                'start_monotonic_ns':started, 'end_monotonic_ns':time.monotonic_ns(), 'passed':passed})
            if not passed: raise RuntimeError('catalog HTTP assertion failed: ' + case + '/' + route)
        finally: connection.close()

    def both(case, **kwargs):
        for route in ('gateway','engine'): request(case, route, **kwargs)

    def start_catalog(label):
        start(label, [invocation['python'], str(HERE / 'manage_fixture.py'), '--config', invocation['config'], 'serve'],
              lambda path: '"event": "listening"' in path.read_text())

    try:
        if digest(runtime['war']) != runtime['war_sha256']: raise RuntimeError('WAR changed')
        start_catalog('geonode-runtime')
        tokens = {}
        for name in ('reader','outsider','admin'):
            browser = OAuthBrowser(origin, config['client_id'], config['redirect_uri'], config['client_secret'])
            browsers.append(browser)
            grant = browser.authorize('fixture-' + name, config['passwords']['fixture-' + name])
            issued = browser.exchange(grant)
            if issued.scope != 'read': raise RuntimeError('unexpected native grant scope')
            tokens[name] = issued.access_token
            registry.add(issued.access_token, issued.refresh_token, grant.code, grant.verifier, grant.state)
        report['issuance'] = {'principals':['fixture-reader','fixture-outsider'], 'flow':'Native HTTP login/CSRF/consent/authorization_code/PKCE S256', 'admin':'disposable provisioning and negative raw-admin witness only'}
        mutation('initialize')
        configured_auth_fixture.LAYERS['group_points'] = 'GROUP_WITNESS'
        configured_auth_fixture.prepare(Path(runtime['source']), data, origin, config['client_id'], config['client_secret'], stateless_bearer_authentication=True)
        oauth = data / 'security/filter/fixture-oauth/config.xml'
        xml = ET.parse(oauth); xml.getroot().find('checkTokenEndpointUrl').text = origin + '/api/o/v4/tokeninfo'; xml.write(oauth)
        properties = Path(runtime['database_properties']).read_text()
        registry.add(*(line.split('=',1)[1] for line in properties.splitlines() if line.startswith('geofenceDataSource.password=')))
        (data / 'geofence/geofence-datasource-ovr.properties').write_text(properties)
        engine('engine-provision', False)
        matrix = Matrix(urlsplit(config['geoserver_url']).port, identity, stateless=True)
        matrix.request('transport-rule', '/rest/geofence/rules', tokens['admin'], 'POST',
            '<Rule><priority>1</priority><workspace>fixture</workspace><access>ALLOW</access></Rule>',
            {'Content-Type':'application/xml'}, expected=(200,201), excludes=()); matrix.require_last()
        matrix.request('baseline-raw-admin-is-accessible', '/rest/workspaces.json', tokens['admin'], contains='fixture', excludes=()); matrix.require_last()
        report['baseline_without_boundary'] = {'raw_admin_accessible':True,
            'criterion':'No raw admin access', 'acceptance_would_fail':True,
            'scope':'private provisioning process, before gateway is started'}
        # This static transport rule has no principal/object sharing assignments.
        # The controlled provisioning process ends before the product boundary starts.
        stopped('engine-provision')
        security = data / 'security/config.xml'
        tree = ET.parse(security)
        for chain in tree.getroot().find('filterChain'):
            for item in list(chain):
                if item.tag == 'filter' and item.text == 'fixture-oauth': chain.remove(item)
        tree.write(security)
        (data / 'security/role/fixture/roles.xml').write_text('<roleRegistry xmlns="http://www.geoserver.org/security/roles" version="1.0"><roleList/><userList/><groupList/></roleRegistry>')
        engine('engine-protected', True)
        fixed = {str(p.relative_to(data)):digest(p) for p in data.rglob('*') if p.is_file() and ('security' in p.parts or p.name == 'geofence-server.properties')}
        start('gateway', [invocation['python'], str(HERE / 'catalog_fixture.py'), '--config', invocation['config'], 'gateway'],
            lambda path: '"event": "listening"' in path.read_text())
        for name in (None,'reader','outsider'):
            both('public-' + str(name), principal=name)
        both('private-owner', layer='private_points', principal='reader')
        both('private-anonymous', layer='private_points', allowed=False)
        both('private-outsider', layer='private_points', principal='outsider', allowed=False)
        both('group-member', layer='group_points', principal='reader')
        both('group-owner', layer='group_points', principal='outsider')
        both('group-anonymous', layer='group_points', allowed=False)
        for action, case, layer, principal, allowed in (
                ('group-remove','group-revoked','group_points','reader',False),
                ('group-add','group-restored','group_points','reader',True),
                ('private-share','private-shared','private_points','outsider',True),
                ('private-revoke','private-revoked','private_points','outsider',False),
                ('public-revoke','public-revoked','public_points',None,False),
                ('public-restore','public-restored','public_points',None,True),
                ('disable-reader','disabled-owner','private_points','reader',False),
                ('enable-reader','enabled-owner','private_points','reader',True)):
            ack = mutation(action)
            both(case, layer=layer, principal=principal, allowed=allowed)
            if any(row['start_monotonic_ns'] < ack['ack_monotonic_ns'] for row in report['requests'][-2:]): raise RuntimeError('revocation timing invalid')
        for principal in (None,'reader','outsider','admin'):
            for path in ('/rest/workspaces.json','/web/','/gwc/rest/layers','/ows','/fixture/wfs','/j_spring_oauth2_geonode_login'):
                both('raw-route-' + str(principal) + '-' + path.replace('/','_'), principal=principal, path=path, allowed=False)
        query = '/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=fixture:private_points&outputFormat=application/json'
        for suffix in ('&typeName=fixture:public_points','&TYPENAME=fixture:public_points','&authkey=unused','&viewparams=x','&srsName=EPSG:4326'):
            both('unsupported-query-' + suffix.split('=')[0][1:], path=query + suffix, principal='reader', allowed=False)
        both('transaction-denied', path='/wfs', method='POST', principal='admin', allowed=False)
        mutation('group-remove')
        def concurrent_read(index):
            route = 'engine' if index % 2 else 'gateway'
            principal = 'reader' if index % 4 < 2 else 'outsider'
            request('concurrent-' + str(index), route, layer='group_points', principal=principal, allowed=principal=='outsider')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(concurrent_read,range(32)))
        stopped('geonode-runtime')
        both('catalog-outage-private', layer='private_points', principal='reader', allowed=False)
        both('catalog-outage-public', allowed=False)
        start_catalog('geonode-restart')
        both('catalog-restart-revocation', layer='group_points', principal='reader', allowed=False)
        both('catalog-restart-public')
        stopped('engine-protected')
        engine('engine-restart', True)
        both('engine-restart-revocation', layer='group_points', principal='reader', allowed=False)
        both('engine-restart-public')
        mutation('revoke-reader-tokens')
        both('token-revoked-immediately', layer='private_points', principal='reader', allowed=False)
        both('invalid-token-public-fails-closed', headers={'Authorization':'Bearer invalid-credential-1234567890'}, allowed=False)
        if fixed != {str(p.relative_to(data)):digest(p) for p in data.rglob('*') if p.is_file() and ('security' in p.parts or p.name == 'geofence-server.properties')}:
            raise RuntimeError('inherited policy configuration changed')
        report['engine_policy_configuration_unchanged'] = True
        report['result_exit_code'] = 0
    except Exception as error:
        report['error'] = {'type':type(error).__name__, 'message':str(error)}
    finally:
        for name in list(processes):
            try: stopped(name)
            except Exception as error: report['cleanup'][name] = type(error).__name__; report['result_exit_code'] = 1
        keyfile.write_text('SCRUBBED DISPOSABLE SERVICE CREDENTIAL\n')
        report['diagnostic_secret_hits'] = sum(c.security_failures for c in captures)
        report['war_unchanged'] = digest(runtime['war']) == runtime['war_sha256']
        if report['diagnostic_secret_hits'] or not report['war_unchanged']: report['result_exit_code'] = 1
        configured_auth_fixture.scrub_secrets(data) if data.exists() else None
        save(output / 'catalog-result.json', report)
    return report
