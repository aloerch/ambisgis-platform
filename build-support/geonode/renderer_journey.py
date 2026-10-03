"""Actual owned QGIS/GeoServer WMS, native catalog, and no cached decisions."""
import concurrent.futures
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlencode, urlsplit
import xml.etree.ElementTree as ET

from protocol_probe import OAuthBrowser, SecretRegistry
from journey import LiveEvidence
from configured_auth_probe import Matrix
import configured_auth_fixture
import runtime_inputs
from ambisgis_render.boundary import FIELDS

HERE = Path(__file__).resolve().parent


def exercise(invocation, config, private):
    from run import Capture, digest, save, stop
    output = Path(config['output']); runtime = invocation['runtime']
    origin = config['site_url'].rstrip('/'); fixture = Path(config['renderer_fixture'])
    registry = SecretRegistry(); registry.add(*private)
    browsers, processes, captures = [], {}, []
    identity = LiveEvidence(output/'geonode-runtime.log', registry, browsers, private)
    report = {'result_exit_code':1, 'authority':'GeoNode ResourceBase/guardian/native OAuth tokens',
              'requests':[], 'mutations':[], 'images':[], 'cleanup':{}, 'positive_decision_cache':False}
    data = output/'geoserver-data'; keyfile = output/'policy-key.txt'
    keyfile.write_text(config['policy_key']); keyfile.chmod(0o600)
    ports={'gateway':config['gateway_port'],'geoserver':urlsplit(config['geoserver_url']).port,'qgis':config['qgis_port']}
    routes={'gateway':'/map','geoserver':'/geoserver/wms','qgis':'/qgis'}

    def start(name, command, ready, environment=None):
        p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',env=environment or invocation['environment'])
        c=Capture(p,output/(name+'.log'),identity.sensitive); processes[name]=(p,c); captures.append(c)
        deadline=time.monotonic()+150
        while time.monotonic()<deadline and p.poll() is None:
            if c.path.exists() and ready(c.path): return
            time.sleep(.2)
        raise RuntimeError('service not ready: '+name)
    def stopped(name):
        p,c=processes.pop(name);stop(p,c)
        report['cleanup'][name]={'stopped':p.poll() is not None,'secret_hits':c.security_failures}
    def command(label,argv,environment=None):
        p=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',env=environment or invocation['environment'])
        c=Capture(p,output/(label+'.log'),identity.sensitive);captures.append(c)
        try: code=p.wait(timeout=120)
        except subprocess.TimeoutExpired:
            stop(p,c);raise RuntimeError('fixture command timed out')
        c.finish()
        if code or c.security_failures: raise RuntimeError('fixture command failed: '+label)
        return c.path
    def mutation(action):
        path=command('mutation-%02d'%len(report['mutations']),[invocation['python'],str(HERE/'catalog_fixture.py'),'--config',invocation['config'],action])
        records=[]
        for line in path.read_text().splitlines():
            try: row=json.loads(line)
            except ValueError:continue
            if row.get('event')=='catalog_committed':records.append(row)
        if len(records)!=1:raise RuntimeError('missing native transaction acknowledgment')
        report['mutations'].append(records[0])
    def catalog(label):
        start(label,[invocation['python'],str(HERE/'manage_fixture.py'),'--config',invocation['config'],'serve'],lambda p:'"event": "listening"' in p.read_text())
    def engine(label,protected):
        target=output/label
        cmd=runtime_inputs.launcher_command(Path(runtime['java_home']),Path(runtime['servlet']),Path(runtime['launcher']),Path(runtime['war']),data,target,
                                            port=ports['geoserver'],java_profile=runtime.get('java_profile'))
        if protected:
            cmd[1:1]=['-Dambisgis.catalog.origin='+origin,'-Dambisgis.catalog.keyFile='+str(keyfile),
                      '-Dambisgis.catalog.filter=CatalogMapPolicyFilter','-Dambisgis.maps.bindings='+str(output/'java-bindings.tsv'),
                      '-Dambisgis.maps.bindingsSha256='+digest(output/'java-bindings.tsv')]
        start(label,cmd,lambda p:(target/'ready.json').exists(),{'PATH':str(Path(runtime['java_home'])/'bin')+':/usr/bin:/bin','LANG':'C.UTF-8'})
    def request(case,route,layer='public_points',principal=None,allowed=True,path=None,method='GET',headers=None,header_pairs=()):
        query=urlencode(dict(FIELDS,layers='fixture:'+layer))
        target=path or routes[route]+'?'+query
        if path and route=='geoserver' and not target.startswith('/geoserver/'):
            target='/geoserver'+target
        supplied=dict(headers or {})
        if principal:supplied['Authorization']='Bearer '+tokens[principal]
        c=http.client.HTTPConnection('127.0.0.1',ports[route],timeout=20); began=time.monotonic_ns()
        try:
            c.putrequest(method,target)
            for key,value in [*supplied.items(),*header_pairs]:c.putheader(key,value)
            c.endheaders();response=c.getresponse();body=response.read(4*1024*1024+1)
            passed=(response.status==200 and body.startswith(b'\x89PNG\r\n\x1a\n')) if allowed else (response.status in (401,403,404,503) and not body)
            passed=passed and response.getheader('Cache-Control')=='no-store' and response.getheader('Set-Cookie') is None
            passed=passed and all(not value or value.encode() not in body for value in identity.sensitive())
            row={'case':case,'route':route,'layer':layer,'principal':principal,'expected_allow':allowed,'status':response.status,
                 'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'start_monotonic_ns':began,'end_monotonic_ns':time.monotonic_ns(),'passed':passed}
            report['requests'].append(row)
            if not passed:raise RuntimeError('map assertion failed: '+case+'/'+route)
            if allowed:
                target=output/('map-'+case+'-'+route+'.png');target.write_bytes(body)
                report['images'].append({'path':str(target),'route':route,'layer':layer,'case':case})
        finally:c.close()
    def all_routes(case,**kwargs):
        for route in routes:request(case,route,**kwargs)

    try:
        catalog('geonode-runtime');tokens={}
        for name in ('reader','outsider','admin'):
            browser=OAuthBrowser(origin,config['client_id'],config['redirect_uri'],config['client_secret']);browsers.append(browser)
            grant=browser.authorize('fixture-'+name,config['passwords']['fixture-'+name]);issued=browser.exchange(grant)
            if issued.scope!='read':raise RuntimeError('native scope differs')
            tokens[name]=issued.access_token;registry.add(issued.access_token,issued.refresh_token,grant.code,grant.verifier,grant.state)
        mutation('initialize')
        command('extra-catalog',[invocation['python'],str(HERE/'renderer_fixture.py'),'--config',invocation['config']])
        configured_auth_fixture.LAYERS.update(group_points='GROUP_WITNESS',parcels='PARCEL_WITNESS')
        configured_auth_fixture.prepare(Path(runtime['source']),data,origin,config['client_id'],config['client_secret'],stateless_bearer_authentication=True)
        oauth=data/'security/filter/fixture-oauth/config.xml';xml=ET.parse(oauth);xml.getroot().find('checkTokenEndpointUrl').text=origin+'/api/o/v4/tokeninfo';xml.write(oauth)
        properties=Path(runtime['database_properties']).read_text();registry.add(*(line.split('=',1)[1] for line in properties.splitlines() if line.startswith('geofenceDataSource.password=')))
        (data/'geofence/geofence-datasource-ovr.properties').write_text(properties)
        # Replace only this newly allocated fixture's geometry/style artifacts before boot.
        for layer in configured_auth_fixture.LAYERS:
            for p in (fixture/'geoserver'/layer).iterdir():shutil.copyfile(p,data/'data'/p.name)
            style_name='fixture-style-'+layer
            (data/'styles').mkdir(exist_ok=True)
            shutil.copyfile(fixture/(layer+'.sld'),data/'styles'/(style_name+'.sld'))
            (data/'styles'/(style_name+'.xml')).write_text('<style><id>'+style_name+'</id><name>'+style_name+'</name><filename>'+style_name+'.sld</filename><format>sld</format><languageVersion><version>1.1.0</version></languageVersion></style>')
            definition=data/'workspaces/fixture'/layer/layer/'layer.xml';xml=ET.parse(definition);style=ET.SubElement(xml.getroot(),'defaultStyle');ET.SubElement(style,'id').text=style_name;xml.write(definition)
            feature=data/'workspaces/fixture'/layer/layer/'featuretype.xml';xml=ET.parse(feature)
            for bbox in ('nativeBoundingBox','latLonBoundingBox'):
                for name,value in [('minx','0'),('miny','0'),('maxx','4'),('maxy','4')]:xml.getroot().find(bbox+'/'+name).text=value
            xml.write(feature)
        (data/'wms.xml').write_text('<wms><id>fixture-wms</id><name>WMS</name><enabled>true</enabled><title>Synthetic WMS fixture</title></wms>')
        engine('engine-provision',False)
        matrix=Matrix(ports['geoserver'],identity,stateless=True)
        matrix.request('transport-rule','/rest/geofence/rules',tokens['admin'],'POST','<Rule><priority>1</priority><workspace>fixture</workspace><access>ALLOW</access></Rule>',{'Content-Type':'application/xml'},expected=(200,201),excludes=());matrix.require_last()
        stopped('engine-provision')
        security=data/'security/config.xml';xml=ET.parse(security)
        for chain in xml.getroot().find('filterChain'):
            for item in list(chain):
                if item.tag=='filter' and item.text=='fixture-oauth':chain.remove(item)
        xml.write(security)
        (data/'security/role/fixture/roles.xml').write_text('<roleRegistry xmlns="http://www.geoserver.org/security/roles" version="1.0"><roleList/><userList/><groupList/></roleRegistry>')
        java=[]
        for layer in configured_auth_fixture.LAYERS:
            paths=list((data/'data').glob(layer+'.*'))+list((data/'styles').glob('fixture-style-'+layer+'.*'))+list((data/'workspaces/fixture'/layer).rglob('*.xml'))
            java.extend('fixture:'+layer+'\t'+str(p)+'\t'+digest(p) for p in sorted(paths))
        (output/'java-bindings.tsv').write_text('\n'.join(java)+'\n')
        files=[p for p in (fixture/'packaged/content').rglob('*') if p.is_file()]
        assets=[{'path':str(p),'sha256':digest(p)} for p in files]
        entries={'fixture:'+name:{'renderer':'qgis-server' if name in ('rich_points','elevation') else 'geoserver','assets':assets}
                 for name in ('public_points','private_points','group_points','parcels','rich_points','elevation')}
        save(output/'map-bindings.json',entries)
        common={'bindings':str(output/'map-bindings.json'),'bindings_sha256':digest(output/'map-bindings.json'),
                'catalog_origin':origin,'policy_key_file':str(keyfile)}
        sys.path.insert(0,str(HERE.parent/'qgis'))
        from runtime import build_environment
        from renderer_artifacts import verify_stage
        report['qgis_stage_before'] = verify_stage(config['qgis_config'])
        qdir=output/'qgis-runtime';qdir.mkdir()
        qconfig=dict(config['qgis_config'],**common,output=str(qdir),port=ports['qgis'],
                     project=str(fixture/'packaged/content/project.qgs'),ready_file=str(qdir/'ready.json'))
        qenv=build_environment(qconfig,qdir);qenv['PYTHONPATH']=str(HERE)+':'+qenv['PYTHONPATH']
        save(qdir/'runtime-config.json',qconfig)
        engine('engine-protected',True)
        def qgis(label):start(label,[qconfig['python'],'-m','ambisgis_render.qgis_server',str(qdir/'runtime-config.json')],lambda p:'"event": "listening"' in p.read_text(),qenv)
        qgis('qgis-protected')
        gateway=dict(common,port=ports['gateway'],targets={'geoserver':'http://127.0.0.1:'+str(ports['geoserver'])+'/geoserver/wms',
                                                        'qgis-server':'http://127.0.0.1:'+str(ports['qgis'])+'/qgis'})
        save(output/'gateway-config.json',gateway)
        start('gateway',[invocation['python'],str(HERE/'renderer_gateway.py'),str(output/'gateway-config.json')],lambda p:'"event": "listening"' in p.read_text())
        for principal in (None,'reader','outsider'):all_routes('public-'+str(principal),principal=principal)
        all_routes('private-owner',layer='private_points',principal='reader')
        all_routes('private-anonymous',layer='private_points',allowed=False)
        all_routes('private-outsider',layer='private_points',principal='outsider',allowed=False)
        all_routes('group-member',layer='group_points',principal='reader')
        all_routes('group-owner',layer='group_points',principal='outsider')
        all_routes('parcels-public',layer='parcels')
        for route in ('gateway','qgis'):
            request('rich-owner',route,layer='rich_points',principal='reader')
            request('rich-anonymous',route,layer='rich_points',allowed=False)
            request('raster-owner',route,layer='elevation',principal='reader')
            request('raster-anonymous',route,layer='elevation',allowed=False)
            request('raster-outsider',route,layer='elevation',principal='outsider',allowed=False)
        request('rich-sld-not-supported','geoserver',layer='rich_points',principal='reader',allowed=False)
        request('raster-sld-not-supported','geoserver',layer='elevation',principal='reader',allowed=False)
        for action,case,layer,principal,allow in [('group-remove','group-revoked','group_points','reader',False),('group-add','group-restored','group_points','reader',True),
            ('private-share','private-shared','private_points','outsider',True),('private-revoke','private-revoked','private_points','outsider',False),
            ('public-revoke','public-revoked','public_points',None,False),('public-restore','public-restored','public_points',None,True)]:
            mutation(action);all_routes(case,layer=layer,principal=principal,allowed=allow)
            if any(row['start_monotonic_ns']<report['mutations'][-1]['ack_monotonic_ns'] for row in report['requests'][-3:]):raise RuntimeError('pre-commit revocation assertion')
        for route in routes:
            query=routes[route]+'?'+urlencode(dict(FIELDS,layers='fixture:private_points'))
            for index,suffix in enumerate(('&LAYERS=fixture:public_points','&SLD=http://127.0.0.1/x','&MAP=/etc/passwd','&FORMAT=image/jpeg','&FILTER=1','&STYLES=other')):
                request('bad-query-'+str(index),route,path=query+suffix,principal='reader',allowed=False)
            for index,path in enumerate(('/rest/workspaces.json','/web/','/ows','/gwc/service/wms','/wfs')):
                request('admin-'+str(index),route,path=path,principal='admin',allowed=False)
            request('write',route,method='POST',principal='admin',allowed=False)
            request('invalid-bearer-public',route,headers={'Authorization':'Bearer invalid-credential-1234567890'},allowed=False)
            request('duplicate-authorization',route,principal='reader',header_pairs=[('Authorization','Bearer invalid-credential-1234567890')],allowed=False)
            request('forged-resource-header',route,layer='private_points',principal='outsider',
                    headers={'X-Ambisgis-Resource':'fixture:public_points','X-Ambisgis-Policy-Key':'untrusted-value'},allowed=False)
            request('unsupported-width',route,path=routes[route]+'?'+urlencode(dict(FIELDS,layers='fixture:public_points',width='8192')),allowed=False)
            request('capabilities-default-deny',route,path=routes[route]+'?SERVICE=WMS&REQUEST=GetCapabilities',allowed=False)
        mutation('group-remove')
        def concurrent_read(index):
            route=list(routes)[index%3];principal='reader' if index%2 else 'outsider'
            request('concurrent-'+str(index),route,layer='group_points',principal=principal,allowed=principal=='outsider')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(concurrent_read,range(24)))
        stopped('geonode-runtime');all_routes('catalog-outage',allowed=False)
        catalog('geonode-restart');all_routes('restart-revocation',layer='group_points',principal='reader',allowed=False)
        stopped('engine-protected');engine('engine-restart',True)
        stopped('qgis-protected');qgis('qgis-restart')
        all_routes('engine-restart-public');all_routes('engine-restart-revoked',layer='group_points',principal='reader',allowed=False)
        mutation('revoke-reader-tokens');all_routes('revoked-token',layer='private_points',principal='reader',allowed=False)
        for route in ('gateway','qgis'):request('raster-token-revoked',route,layer='elevation',principal='reader',allowed=False)
        # Mutating an approved renderer asset invalidates every subsequent map request.
        target=fixture/'packaged/content/assets/public_points.geojson';target.write_bytes(target.read_bytes()+b'\n')
        request('asset-tamper-gateway','gateway',allowed=False);request('asset-tamper-qgis','qgis',allowed=False)
        gs=data/'styles/fixture-style-public_points.sld';gs.write_bytes(gs.read_bytes()+b'\n')
        request('asset-tamper-geoserver','geoserver',allowed=False)
        save(output/'image-check-input.json',{'images':report['images'],'desktop':str(fixture),'output':str(output/'image-checks.json')})
        command('image-checks',[invocation['python'],str(HERE/'render_image_checks.py'),str(output/'image-check-input.json')])
        report['image_checks_sha256']=digest(output/'image-checks.json')
        report['qgis_stage_after'] = verify_stage(config['qgis_config'])
        if report['qgis_stage_before'] != report['qgis_stage_after']:raise RuntimeError('QGIS stage changed')
        report['result_exit_code']=0
    except Exception as error:report['error']={'type':type(error).__name__,'message':str(error)}
    finally:
        for name in list(processes):
            try:stopped(name)
            except Exception as error:report['cleanup'][name]=type(error).__name__;report['result_exit_code']=1
        keyfile.write_text('SCRUBBED DISPOSABLE SERVICE CREDENTIAL\n')
        report['diagnostic_secret_hits']=sum(c.security_failures for c in captures)
        if report['diagnostic_secret_hits']:report['result_exit_code']=1
        if data.exists():configured_auth_fixture.scrub_secrets(data)
        save(output/'renderer-result.json',report)
    return report
