#!/usr/bin/env python3
"""Embedded WMTS fixture using the unchanged #61 backend and strict guards.

Services, HTTP clients and image decoding run under the existing loopback supervisor.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit
import urllib.request
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'geonode'), str(HERE.parent / 'java')]
from run import Capture, digest, save, stop, private_values
sys.path.insert(0, str(HERE.parent / 'frontend'))
from smoke_backend import add_wms_style
from probe import configure_cache, exercise, request, security_hashes, cache_manifest


def run_child(invocation):
    import runtime_inputs
    from configured_auth_fixture import prepare, scrub_secrets
    from role_fixture import configure
    from protocol_probe import OAuthBrowser
    config = json.loads(Path(invocation['config']).read_text())
    output, runtime = Path(config['output']), invocation['runtime']
    private = private_values(config)
    processes, captures, provisioned = {}, [], False
    result = {'result_exit_code': 1, 'commands': [], 'cleanup': {}, 'restarts': 0}

    def command(action):
        nonlocal provisioned
        if action == 'provision': provisioned = True
        process = subprocess.Popen([invocation['python'], str(HERE.parent / 'geonode/manage_fixture.py'), '--config', invocation['config'], action],
            env=invocation['environment'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        capture = Capture(process, output / (action + '.log'), lambda: private)
        captures.append(capture)
        try: code = process.wait(timeout=240)
        except subprocess.TimeoutExpired:
            stop(process, capture)
            raise RuntimeError('fixture command timeout: ' + action)
        capture.finish()
        result['commands'].append({'action': action, 'exit_code': code, 'log_sha256': digest(capture.path)})
        if code or capture.security_failures: raise RuntimeError('fixture command failed: ' + action)

    def stop_service(name, label):
        pair=processes.pop(name)
        process,capture=pair
        was_running=process.poll() is None
        stop(process,capture)
        result.setdefault('service_stops',[]).append({'name':name,'phase':label,'pid':process.pid,'was_running':was_running,'exit_code':process.returncode,'log_sha256':digest(capture.path)})
        if not was_running or process.returncode not in (0,-15,143): raise RuntimeError('unexpected service exit: '+name)

    def fixture_hashes():
        return {str(p.relative_to(data)):digest(p) for p in sorted(data.rglob('*')) if p.is_file() and
            (p.name in ('gwc-gs.xml','wmts.xml','wms.xml','global.xml') or any(v in p.parts for v in ('gwc-layers','data','styles','workspaces')))}

    def start(name, label):
        if name == 'geonode':
            cmd = [invocation['python'], str(HERE.parent / 'geonode/manage_fixture.py'), '--config', invocation['config'], 'serve']
            env = invocation['environment']
        else:
            cmd = runtime_inputs.launcher_command(Path(runtime['java_home']), Path(runtime['servlet']), Path(runtime['launcher']),
                Path(runtime['war']), output / 'geoserver-data', output / ('geoserver-' + label), port=urlsplit(config['geoserver_url']).port)
            cmd[1:1] = ['-Dambisgis.fixture.gwc=true','-Dgwc.context.suffix=gwc','-Dsun.net.client.defaultReadTimeout=1500', '-Dsun.net.client.defaultConnectTimeout=1500', '-DGEOWEBCACHE_CACHE_DIR=' + str(output / 'tile-cache')]
            if digest(runtime['war']) != runtime['war_sha256']: raise RuntimeError('WAR changed before launch')
            env = {'PATH': str(Path(runtime['java_home']) / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'}
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        capture = Capture(process, output / (name + '-' + label + '.log'), lambda: private)
        processes[name] = process, capture
        captures.append(capture)
        deadline = time.monotonic() + 150
        while process.poll() is None and time.monotonic() < deadline:
            if name == 'geonode' and capture.path.exists() and '"event": "listening"' in capture.path.read_text(): return
            ready = output / ('geoserver-' + label) / 'ready.json'
            if name == 'geoserver' and ready.exists():
                active = json.loads(ready.read_text())['security_configuration']
                if not (active.get('stateless_bearer_authentication') is True and active.get('strict_geonode_roles') is True
                        and active.get('role_cache_ms') == 1000 and active.get('user_group_service') == 'fixture'):
                    raise RuntimeError('loaded strict backend guard mismatch')
                gwc=json.loads((ready.parent/'gwc-runtime.json').read_text())
                if not (gwc['security_enabled'] is True and gwc['metatile_threads']==0 and Path(gwc['cache_directory']).resolve()==(output/'tile-cache').resolve()): raise RuntimeError('loaded GWC settings mismatch')
                result[name + '-' + label] = {'ready_sha256': digest(ready), 'strict_roles': True, 'stateless': True}
                return
            time.sleep(.2)
        raise RuntimeError(name + ' failed to reach readiness')

    try:
        for action in ('check', 'migrate', 'initialize', 'provision'): command(action)
        start('geonode', 'initial')
        auth = OAuthBrowser(config['site_url'].rstrip('/'), config['client_id'], config['redirect_uri'], config['client_secret'])
        grant = auth.authorize('fixture-admin', config['passwords']['fixture-admin'])
        tokens = auth.exchange(grant)
        private.extend(auth.secrets.sensitive_values())
        private.extend([tokens.access_token, tokens.refresh_token, grant.code, grant.verifier, grant.state])
        data = output / 'geoserver-data'
        fixture = prepare(Path(runtime['source']), data, config['site_url'].rstrip('/'), config['client_id'], config['client_secret'],
                          cache_seconds=2, stateless_bearer_authentication=True)
        oauth_file = data / 'security/filter/fixture-oauth/config.xml'
        tree = ET.parse(oauth_file)
        for tag, route in (('checkTokenEndpointUrl','/api/o/v4/tokeninfo'), ('accessTokenUri','/o/token/'),
                           ('userAuthorizationUri','/o/authorize/'), ('logoutUri','/account/logout/')):
            tree.getroot().find(tag).text = config['site_url'].rstrip('/') + route
        tree.getroot().find('redirectUri').text = config['redirect_uri']
        tree.write(oauth_file, encoding='unicode')
        properties = Path(runtime['database_properties']).read_text()
        private.extend(line.split('=',1)[1] for line in properties.splitlines() if line.startswith('geofenceDataSource.password='))
        (data / 'geofence/geofence-datasource-ovr.properties').write_text(properties)
        configure(data, fixture, config)
        add_wms_style(data)
        configure_cache(data, output / 'tile-cache')
        security_configured = security_hashes(data)
        save(output/'security-configured.json',security_configured)
        save(output/'fixture-origins.json',fixture)
        result['geoserver_fixture_files'] = {str(p.relative_to(data)): digest(p) for p in sorted(data.rglob('*')) if p.is_file()}
        start('geoserver', 'initial')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for body in fixture['geofence_rule_bodies']:
            request = urllib.request.Request(config['geoserver_url'] + 'rest/geofence/rules', data=body.encode(),
                headers={'Authorization': 'Bearer ' + tokens.access_token, 'Content-Type':'application/xml'}, method='POST')
            with opener.open(request, timeout=30) as response:
                if response.status not in (200,201): raise RuntimeError('GeoFence rule provisioning failed')
        credentials = {'admin': tokens.access_token}
        for identity in ('reader', 'outsider'):
            browser = OAuthBrowser(config['site_url'].rstrip('/'), config['client_id'], config['redirect_uri'], config['client_secret'])
            grant = browser.authorize('fixture-' + identity, config['passwords']['fixture-' + identity])
            issued = browser.exchange(grant)
            private.extend(browser.secrets.sensitive_values())
            private.extend([issued.access_token, issued.refresh_token, grant.code, grant.verifier, grant.state])
            credentials[identity] = issued.access_token
        security_before = security_hashes(data)
        # Native startup and first authenticated administration create CSP/keystore/schema metadata.
        # Original filters, role service and ACL bytes must remain unchanged.
        critical=list(security_configured)
        if any(security_before.get(n)!=security_configured[n] for n in critical): raise RuntimeError('startup changed configured security inputs')
        save(output/'security-active.json',security_before)
        save(output/'security-startup-delta.json',{'added':sorted(set(security_before)-set(security_configured)),
            'changed':sorted(n for n in security_configured if security_before.get(n)!=security_configured[n])})
        result['initial'] = exercise(config['geoserver_url'], output, credentials, private, phase='initial')
        before_restart = cache_manifest(output / 'tile-cache')
        cache_config_before = fixture_hashes()
        save(output / 'cache-configuration.json',cache_config_before)
        if security_hashes(data) != security_before: raise RuntimeError('security configuration changed')
        for name in ('geoserver', 'geonode'): stop_service(name,'initial')
        for name in ('geonode', 'geoserver'): start(name, 'restart')
        result['restarts'] += 1
        if cache_manifest(output / 'tile-cache') != before_restart: raise RuntimeError('cache bytes changed on restart')
        if fixture_hashes() != cache_config_before: raise RuntimeError('cache configuration changed on restart')
        result['restart'] = exercise(config['geoserver_url'], output, credentials, private, phase='restart')
        if security_hashes(data) != security_before: raise RuntimeError('security configuration changed on restart')
        result['security_configuration'] = security_before
        result['cache_after'] = cache_manifest(output / 'tile-cache')
        if fixture_hashes() != cache_config_before: raise RuntimeError('fixture data/config changed during final phase')
        result['result_exit_code'] = 0
    except Exception as error:
        result['error'] = {'type':type(error).__name__, 'message':str(error) if not any(v and v in str(error) for v in private) else 'redacted fixture error'}
    finally:
        for name, pair in list(processes.items()):
            try: stop_service(name,'restart' if result['restarts'] else 'initial'); result['cleanup'][name] = True
            except Exception as error: result['cleanup'][name] = type(error).__name__; result['result_exit_code'] = 1
        if provisioned:
            try: command('cleanup'); result['cleanup']['stored_credentials_invalidated'] = True
            except Exception as error: result['cleanup']['credentials_error'] = type(error).__name__; result['result_exit_code'] = 1
        try:
            if (output / 'geoserver-data').exists(): scrub_secrets(output / 'geoserver-data')
        except Exception as error: result['cleanup']['geoserver_secret_error'] = type(error).__name__; result['result_exit_code'] = 1
        result['diagnostic_secret_hits'] = sum(c.leaks for c in captures)
        result['diagnostic_security_failures'] = sum(c.security_failures for c in captures)
        if result['diagnostic_security_failures']: result['result_exit_code'] = 1
        save(output / 'backend-result.json', result)
    return result['result_exit_code']


if __name__ == '__main__':
    raise SystemExit(run_child(json.loads(Path(sys.argv[1]).read_text())))
