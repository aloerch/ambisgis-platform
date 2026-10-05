"""Derived native engine configuration; catalog owns policy and metadata.

Persistent storage holds synthetic diagnostic assets and installation markers.
Each container has a private ephemeral native configuration, so migration
credentials never enter a shared volume or the serving container.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .common import DATA, inputs, read, save

ENGINE = Path('/opt/ambisgis/geoserver')
RUNTIME = Path('/tmp/ambisgis-engine')
POINTS = b'_=the_geom:Point:srid=4326,object_id:Integer,label:String\nprivate_points.1=POINT (1 1)|1|PRIVATE_A\nprivate_points.2=POINT (2 2)|2|PRIVATE_B\n'
STYLE = b'''<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc">
<NamedLayer><Name>private_points</Name><UserStyle><Title>Synthetic installation points</Title><FeatureTypeStyle><Rule>
<PointSymbolizer><Graphic><Mark><WellKnownName>circle</WellKnownName><Fill><CssParameter name="fill">#2078b4</CssParameter></Fill>
<Stroke><CssParameter name="stroke">#123047</CssParameter><CssParameter name="stroke-width">2</CssParameter></Stroke></Mark><Size>20</Size></Graphic></PointSymbolizer>
</Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>
'''


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): value.update(block)
    return value.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(value if isinstance(value, bytes) else value.encode()); stream.flush(); os.fsync(stream.fileno())


def xml(tag, **fields):
    value = ET.Element(tag)
    for key, text in fields.items(): ET.SubElement(value, key).text = str(text)
    return value


def child(parent, tag, text=None, **attributes):
    node = ET.SubElement(parent, tag, attributes)
    if text is not None: node.text = str(text)
    return node


def configuration(product, secrets, initialize):
    """Generate from fixed owned schema definitions; no inherited data-dir copy."""
    if RUNTIME.exists() or RUNTIME.is_symlink():
        raise ValueError('engine runtime directory must be fresh within this container')
    RUNTIME.mkdir(mode=0o700)
    data = RUNTIME / 'data'
    def emit(name, element):
        ET.indent(element, space='  ')
        write(data / name, ET.tostring(element, encoding='utf-8') + b'\n')
    def named(tag, name, cls, **fields):
        return xml(tag, id='development-' + name, name=name, className=cls, **fields)
    write(data / '.ambisgis-derived', product['install_id'])
    write(data / 'security/version.properties', 'version=2.6\n')
    security = xml('security', roleServiceName='transport', configPasswordEncrypterName='pbePasswordEncoder', encryptingUrlParams='false')
    child(security, 'authProviderNames')  # No native username/password administrator.
    chains = child(security, 'filterChain')
    for name, path, interceptor in [('rest', '/rest.*,/rest/**,/gwc/rest.*,/gwc/rest/**', 'restInterceptor'), ('default', '/**', 'interceptor')]:
        chain = child(chains, 'filters', name=name, **{'class': 'org.geoserver.security.ServiceLoginFilterChain',
                      'interceptorName': interceptor, 'exceptionTranslationName': 'exception', 'path': path,
                      'disabled': 'false', 'allowSessionCreation': 'false', 'ssl': 'false', 'matchHTTPMethod': 'false'})
        child(chain, 'filter', 'anonymous')
    remember = child(security, 'rememberMeService')
    child(remember, 'className', 'org.geoserver.security.rememberme.GeoServerTokenBasedRememberMeServices')
    child(remember, 'key', secrets['engine_admin'])
    emit('security/config.xml', security)
    for name, tag, cls, fields in [
            ('anonymous', 'anonymousAuthentication', 'GeoServerAnonymousAuthenticationFilter', {}),
            ('exception', 'exceptionTranslation', 'GeoServerExceptionTranslationFilter', {}),
            ('contextNoAsc', 'contextPersistence', 'GeoServerSecurityContextPersistenceFilter', {'allowSessionCreation': 'false'}),
            ('contextAsc', 'contextPersistence', 'GeoServerSecurityContextPersistenceFilter', {'allowSessionCreation': 'false'}),
            ('interceptor', 'securityInterceptor', 'GeoServerSecurityInterceptorFilter', {'allowIfAllAbstainDecisions': 'false', 'securityMetadataSource': 'geoserverMetadataSource'}),
            ('restInterceptor', 'securityInterceptor', 'GeoServerSecurityInterceptorFilter', {'allowIfAllAbstainDecisions': 'false', 'securityMetadataSource': 'restFilterDefinitionMap'})]:
        emit('security/filter/' + name + '/config.xml', named(tag, name, 'org.geoserver.security.filter.' + cls, **fields))
    for name in ('default', 'master'):
        emit('security/pwpolicy/' + name + '/config.xml', named('passwordPolicy', name,
             'org.geoserver.security.validation.PasswordValidatorImpl', uppercaseRequired='false', lowercaseRequired='false', digitRequired='false', minLength=24, maxLength=-1))
    emit('security/masterpw.xml', xml('masterPassword', providerName='transport'))
    emit('security/masterpw/transport/config.xml', named('urlProvider', 'transport',
         'org.geoserver.security.password.URLMasterPasswordProvider', readOnly='true', url='file:passwd', encrypting='false'))
    write(data / 'security/masterpw/transport/passwd', secrets['engine_admin'])
    emit('security/role/transport/config.xml', named('roleService', 'transport',
         'org.geoserver.security.xml.XMLRoleService', fileName='roles.xml', checkInterval=0,
         validating='true', adminRoleName='UNREACHABLE_ADMIN', groupAdminRoleName='UNREACHABLE_GROUP_ADMIN'))
    registry = ET.Element('roleRegistry', {'version': '1.0', 'xmlns': 'http://www.geoserver.org/security/roles'})
    for name in ('roleList', 'userList', 'groupList'): child(registry, name)
    emit('security/role/transport/roles.xml', registry)
    # The selected native parser accepts these six methods. Unsupported PATCH
    # invalidates the entire rule; the mandatory owned filter denies non-GETs.
    write(data / 'security/rest.properties', '/**;GET,HEAD,OPTIONS,POST,PUT,DELETE=ROLE_ADMINISTRATOR\n')
    write(data / 'security/services.properties', 'wfs.Transaction=ROLE_ADMINISTRATOR\n')
    write(data / 'security/layers.properties', '*.*.r=ROLE_ADMINISTRATOR\n*.*.w=ROLE_ADMINISTRATOR\nmode=HIDE\n')
    write(data / 'geofence/geofence-server.properties', 'ruleReaderBackend=ruleReaderService\nruleReaderFrontend=ruleReaderService\nuseRolesToFilter=false\ngrantWriteToWorkspacesToAuthenticatedUsers=false\n')
    role = 'ambisgis_transport_owner' if initialize else 'ambisgis_transport_reader'
    password = secrets['transport_migrator' if initialize else 'transport_reader']
    write(data / 'geofence/geofence-datasource-ovr.properties',
          'geofenceConfigurationManager.configuration.servicesUrl=internal:/\n'
          'geofenceEntityManagerFactory.jpaPropertyMap[hibernate.hbm2ddl.auto]=' + ('update' if initialize else 'validate') + '\n'
          'geofenceVendorAdapter.databasePlatform=org.hibernate.spatial.dialect.postgis.PostgisDialect\n'
          'geofenceDataSource.driverClassName=org.postgresql.Driver\n'
          'geofenceDataSource.url=jdbc:postgresql://database:5432/ambisgis_transport?sslmode=disable&gssEncMode=disable\n'
          'geofenceDataSource.username=' + role + '\ngeofenceDataSource.password=' + password + '\n')
    global_info = ET.Element('global')
    global_info.append(xml('settings', id='development-settings', charset='UTF-8', numDecimals=8, verbose='false', verboseExceptions='false'))
    # XStreamPersister aliases imageProcessing to jai. Its absence is not
    # repaired by GeoServerInfoImpl.readResolve; make native defaults explicit.
    global_info.append(xml('jai', allowInterpolation='false', recycling='false',
                           tilePriority=5, tileThreads=7, memoryCapacity=0.5,
                           memoryThreshold=0.75, imageIOCache='false', pngEncoderType='PNGJ'))
    emit('global.xml', global_info)
    emit('wfs.xml', xml('wfs', id='development-wfs', name='WFS', enabled='true', title='Synthetic installation query', serviceLevel='BASIC', maxFeatures=2))
    emit('wms.xml', xml('wms', id='development-wms', name='WMS', enabled='true', title='Synthetic installation map'))
    workspace = xml('workspace', id='development-workspace', name='fixture')
    emit('workspaces/fixture/workspace.xml', workspace); emit('workspaces/default.xml', workspace)
    emit('workspaces/fixture/namespace.xml', xml('namespace', id='development-namespace', prefix='fixture', uri='urn:ambisgis:installation-diagnostic'))
    store = xml('dataStore', id='development-store', name='diagnostic', type='Properties', enabled='true')
    child(child(store, 'workspace'), 'id', 'development-workspace')
    params = child(store, 'connectionParameters')
    child(params, 'entry', str(DATA / 'assets'), key='directory')
    child(params, 'entry', 'urn:ambisgis:installation-diagnostic', key='namespace')
    emit('workspaces/fixture/diagnostic/datastore.xml', store)
    feature = xml('featureType', id='development-feature', name='private_points', nativeName='private_points',
                  title='Synthetic installation points', srs='EPSG:4326', projectionPolicy='FORCE_DECLARED', enabled='true')
    child(child(feature, 'namespace'), 'id', 'development-namespace')
    child(child(feature, 'store', **{'class': 'dataStore'}), 'id', 'development-store')
    for bounds in ('nativeBoundingBox', 'latLonBoundingBox'):
        feature.append(xml(bounds, minx=0, miny=0, maxx=4, maxy=4, crs='EPSG:4326'))
    emit('workspaces/fixture/diagnostic/private_points/featuretype.xml', feature)
    layer = xml('layer', id='development-layer', name='private_points', type='VECTOR', enabled='true')
    child(child(layer, 'resource', **{'class': 'featureType'}), 'id', 'development-feature')
    child(child(layer, 'defaultStyle'), 'id', 'development-style')
    emit('workspaces/fixture/diagnostic/private_points/layer.xml', layer)
    style = xml('style', id='development-style', name='diagnostic', filename='diagnostic.sld', format='sld')
    style.append(xml('languageVersion', version='1.0.0')); emit('styles/diagnostic.xml', style)
    write(data / 'styles/diagnostic.sld', STYLE)
    assets = [DATA / 'assets/private_points.properties', DATA / 'assets/diagnostic.sld', data / 'styles/diagnostic.sld']
    write(RUNTIME / 'assets.tsv', ''.join(str(path) + '\t' + digest(path) + '\n' for path in assets))
    profile = json.loads((ENGINE / 'runtime-profile.json').read_text())
    if (profile['schema_version'] != 1 or profile['profile'] != 'NO-ORACLE-NO-JPEG2000-headless-Temurin17'
            or profile['war_sha256'] != digest(ENGINE / 'application.war')):
        raise ValueError('owned Java profile does not bind application bytes')
    for key, name in [('renderer', 'marlin-0.9.4.8.jar'), ('imageio', 'jai_imageio-1.1.jar'), ('json', 'json-lib-2.4.2-geoserver.jar')]:
        if profile[key + '_member'] != 'WEB-INF/lib/' + name or profile[key + '_sha256'] != digest(ENGINE / 'lib' / name):
            raise ValueError('owned Java profile member changed')
    write(RUNTIME / 'launch.properties', 'install_id=' + product['install_id'] + '\npolicy_key=' + secrets['policy_key'] + '\nwar_sha256=' + profile['war_sha256'] + '\n')


def run(initialize=False):
    product, secrets = inputs()
    identity = {'schema_version': 1, 'install_id': product['install_id'], 'purpose': 'developer-engine'}
    marker = DATA / 'installation.json'
    if marker.exists():
        if read(marker) != identity: raise ValueError('engine volume belongs to another installation')
    else:
        if not initialize or any(DATA.iterdir()): raise ValueError('refuse unmarked engine volume')
        save(marker, identity)
    fd = os.open(DATA / 'initialization.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, (fcntl.LOCK_EX if initialize else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        if not initialize and not (DATA / 'initialized.json').exists(): raise ValueError('geoserver-init must complete first')
        assets = DATA / 'assets'
        if assets.is_symlink(): raise ValueError('diagnostic asset directory cannot redirect')
        assets.mkdir(mode=0o700, exist_ok=True)
        for name, value in [('private_points.properties', POINTS), ('diagnostic.sld', STYLE)]:
            path = assets / name
            if path.exists():
                if path.is_symlink() or path.read_bytes() != value: raise ValueError('diagnostic assets changed')
            elif initialize and not (DATA / 'initialized.json').exists(): write(path, value)
            else: raise ValueError('persistent diagnostic asset is missing')
        configuration(product, secrets, initialize)
        command = ['/opt/ambisgis/java/bin/java', '--patch-module', 'java.desktop=' + str(ENGINE / 'lib/marlin-0.9.4.8.jar'),
                   '--add-exports', 'java.desktop/sun.java2d.pipe=ALL-UNNAMED', '-Dsun.java2d.opengl=false', '-Duser.home=/tmp',
                   '-Dsun.java2d.renderer=sun.java2d.marlin.DMarlinRenderingEngine', '-Djava.awt.headless=true',
                   '-cp', str(ENGINE / 'launcher') + ':' + str(ENGINE / 'servlet/*'),
                   'DevelopmentGeoServer', 'initialize' if initialize else 'serve']
        if initialize:
            result = subprocess.run(command, timeout=180)
            if result.returncode or (RUNTIME / 'initialized').read_text() != product['install_id']:
                raise ValueError('native transport initialization did not finish')
            if not (DATA / 'initialized.json').exists(): save(DATA / 'initialized.json', identity)
        else:
            # Serving holds no initialization lock; subsequent init is safe and
            # has its own ephemeral config and exclusive initialization lock.
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd); fd = None
            os.execv(command[0], command)
    finally:
        if fd is not None: os.close(fd)


def initialize(): run(True)
def main(): run(False)
