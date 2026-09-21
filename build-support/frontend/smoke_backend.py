#!/usr/bin/env python3
"""Scoped public-map fixture using the unchanged #61 backend and strict guards.

The backend child runs under the existing loopback supervisor. The real browser
is a separate sandboxed process; no mock API, alternate catalogue or dev server.
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


def stage_frontend(source, destination):
    """Replace the collected MapStore tree with exactly one compiled artifact tree."""
    source, destination = Path(source).resolve(), Path(destination)
    if not (source / 'dist/js/gn-map.js').is_file():
        raise ValueError('compiled gn-map.js is missing')
    if destination.name != 'mapstore' or destination.is_symlink():
        raise ValueError('destination must be the disposable collected MapStore directory')
    files = {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('frontend artifact contains a symlink')
        if path.is_file():
            files[str(path.relative_to(source))] = digest(path)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    if any(digest(destination / name) != value for name, value in files.items()):
        raise RuntimeError('staged frontend differs from compiled output')
    return files


def manage(config_path, action):
    import fixture_settings
    config = fixture_settings.load_config(config_path)
    os.environ['AMBISGIS_GEONODE_CONFIG'] = str(config_path)
    values = fixture_settings.owned_settings(config, runtime=action in ('serve', 'cleanup'))
    # Supported settings prevent implicit public basemap/geocoder acquisition.
    values.update(MAPSTORE_BASELAYERS=[], MAPSTORE_INCLUDE_NOMINATIM_IN_CUSTOM_SEARCH_SERVICES=False)
    # GeoNode's inherited /gs routes target the configured internal GeoServer
    # and preserve native authorization. Keep browser-facing OWS/print same-origin.
    public_location = config['site_url'] + 'gs/'
    values['GEOSERVER_PUBLIC_LOCATION'] = public_location
    values['OGC_SERVER'] = {key:dict(value) for key,value in values['OGC_SERVER'].items()}
    values['OGC_SERVER']['default']['PUBLIC_LOCATION'] = public_location
    from django.conf import settings
    settings.configure(**values)
    import django
    django.setup()
    import manage_fixture as native
    from django.core.management import call_command
    native.module_evidence(config, action)
    if action == 'check':
        call_command('check')
    elif action == 'migrate':
        call_command('migrate', interactive=False, verbosity=1)
        native.migration_evidence(config, action)
    elif action == 'initialize':
        native.initialize(config)
        manifest = stage_frontend(config['frontend'], Path(config['output']) / 'static/mapstore')
        save(Path(config['output']) / 'served-frontend-manifest.json', manifest)
    elif action == 'provision':
        native.provision(config)
        from django.contrib.auth import get_user_model
        from guardian.shortcuts import assign_perm, get_anonymous_user
        from geonode.maps.models import Map
        from geonode.base.models import ResourceBase
        # Native ORM stores this disposable public map; browser obtains it over
        # the real permission-checked resource API. No direct managed-table SQL.
        blob = {'version': 2, 'map': {
            'projection': 'EPSG:3857', 'center': {'x': 1, 'y': 2, 'crs': 'EPSG:4326'},
            'zoom': 7, 'maxExtent': [-20037508.34, -20037508.34, 20037508.34, 20037508.34],
            'layers': [{'id': 'public-witness', 'type': 'wms', 'name': 'fixture:public_points',
                'title': 'AmbisGIS public witness', 'url': config['site_url'] + 'gs/wms',
                'format': 'image/png', 'version': '1.1.1', 'visibility': True, 'singleTile': True,
                'params': {'TRANSPARENT': True}, 'bbox': {'crs': 'EPSG:4326',
                    'bounds': {'minx': 0, 'miny': 1, 'maxx': 2, 'maxy': 3}}}]
        }}
        resource = Map.objects.create(uuid=str(uuid.uuid4()),
            owner=get_user_model().objects.get(username='fixture-admin'),
            title='AmbisGIS owned frontend public witness', abstract='Synthetic point at longitude 1, latitude 2.',
            resource_type='map', blob=blob, is_published=True, is_approved=True)
        assign_perm('base.view_resourcebase', get_anonymous_user(), resource.resourcebase_ptr)
        # Read back the actual permission rather than assuming map publication grants it.
        if not resource.is_public or ResourceBase.objects.get(pk=resource.pk).blob != blob:
            raise RuntimeError('native public map provisioning did not persist')
        save(Path(config['output']) / 'public-map.json', {'id': resource.pk,
            'route': '/maps/' + str(resource.pk) + '/embed', 'configuration': blob})
    elif action == 'serve':
        native.assert_runtime_role(config)
        native.serve(config)
    elif action == 'cleanup':
        native.assert_runtime_role(config)
        native.cleanup(config)
    else:
        raise ValueError('unsupported scoped fixture action')


def add_wms_style(data_dir):
    """Declare native WMS and a synthetic red point style; fixed ACLs stay unchanged."""
    data_dir = Path(data_dir)
    (data_dir / 'styles').mkdir(exist_ok=True)
    (data_dir / 'wms.xml').write_text('<wms><id>fixture-wms</id><name>WMS</name><enabled>true</enabled><title>AmbisGIS public witness</title><maxBuffer>25</maxBuffer></wms>\n')
    (data_dir / 'styles/witness.xml').write_text('<style><id>fixture-witness-style</id><name>witness</name><filename>witness.sld</filename></style>\n')
    (data_dir / 'styles/witness.sld').write_text('''<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld"><NamedLayer><Name>witness</Name><UserStyle><Title>Public witness</Title><FeatureTypeStyle><Rule><PointSymbolizer><Graphic><Mark><WellKnownName>circle</WellKnownName><Fill><CssParameter name="fill">#e60000</CssParameter></Fill><Stroke><CssParameter name="stroke">#550000</CssParameter></Stroke></Mark><Size>28</Size></Graphic></PointSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>\n''')
    path = data_dir / 'workspaces/fixture/public_points/public_points/layer.xml'
    tree = ET.parse(path)
    ET.SubElement(ET.SubElement(tree.getroot(), 'defaultStyle'), 'id').text = 'fixture-witness-style'
    tree.write(path, encoding='unicode')


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
        process = subprocess.Popen([invocation['python'], str(HERE / 'smoke_backend.py'), 'manage', invocation['config'], action],
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

    def start(name, label):
        if name == 'geonode':
            cmd = [invocation['python'], str(HERE / 'smoke_backend.py'), 'manage', invocation['config'], 'serve']
            env = invocation['environment']
        else:
            cmd = runtime_inputs.launcher_command(Path(runtime['java_home']), Path(runtime['servlet']), Path(runtime['launcher']),
                Path(runtime['war']), output / 'geoserver-data', output / ('geoserver-' + label), port=urlsplit(config['geoserver_url']).port, java_profile=runtime.get('java_profile'))
            cmd[1:1] = ['-Dsun.net.client.defaultReadTimeout=1500', '-Dsun.net.client.defaultConnectTimeout=1500']
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
        result['geoserver_fixture_files'] = {str(p.relative_to(data)): digest(p) for p in sorted(data.rglob('*')) if p.is_file()}
        start('geoserver', 'initial')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for body in fixture['geofence_rule_bodies']:
            request = urllib.request.Request(config['geoserver_url'] + 'rest/geofence/rules', data=body.encode(),
                headers={'Authorization': 'Bearer ' + tokens.access_token, 'Content-Type':'application/xml'}, method='POST')
            with opener.open(request, timeout=30) as response:
                if response.status not in (200,201): raise RuntimeError('GeoFence rule provisioning failed')
        public_map = json.loads((output / 'public-map.json').read_text())
        save(output / 'ready-initial.json', {'origin': config['site_url'].rstrip('/'), 'geoserver_origin': config['geoserver_url'].rstrip('/'),
            'route': public_map['route'], 'map_id': public_map['id'], 'war_sha256': digest(runtime['war'])})
        deadline = time.monotonic() + 360
        while not (output / 'stop.request').exists() and time.monotonic() < deadline:
            if (output / 'restart.request').exists() and result['restarts'] == 0:
                for name in ('geoserver','geonode'): stop(*processes.pop(name))
                for name in ('geonode','geoserver'): start(name, 'restart')
                result['restarts'] += 1
                save(output / 'ready-restart.json', {'same_war': digest(runtime['war']) == runtime['war_sha256'],
                    'same_frontend': json.loads((output / 'served-frontend-manifest.json').read_text()) ==
                        {str(p.relative_to(output / 'static/mapstore')):digest(p) for p in sorted((output / 'static/mapstore').rglob('*')) if p.is_file()}})
            if any(process.poll() is not None for process,capture in processes.values()):
                raise RuntimeError('serving process stopped unexpectedly')
            time.sleep(.2)
        if not (output / 'stop.request').exists(): raise RuntimeError('browser coordinator timeout')
        result['result_exit_code'] = 0
    except Exception as error:
        result['error'] = {'type':type(error).__name__, 'message':str(error) if not any(v and v in str(error) for v in private) else 'redacted fixture error'}
    finally:
        for name, pair in list(processes.items()):
            try: stop(*pair); result['cleanup'][name] = True
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
    if sys.argv[1] == 'manage': manage(Path(sys.argv[2]), sys.argv[3])
    else: raise SystemExit(run_child(json.loads(Path(sys.argv[2]).read_text())))
