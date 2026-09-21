#!/usr/bin/env python3
"""Disposable source-backed GeoServer configuration, never a product policy authority.

The servlet launcher must append ``file:<output>/fixture-context.xml`` to the
inherited Spring contextConfigLocation. No inherited data directory is copied.
All runtime credentials are newly generated; the caller supplies the OAuth client
secret in memory and must call scrub_secrets after stopping the application.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import secrets
import struct
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

MARKER = '.ambisgis-configured-auth-fixture'
WORKSPACE = 'fixture'
IDENTITIES = ('fixture-reader', 'fixture-outsider', 'fixture-admin', 'fixture-disabled')
LAYERS = {'public_points': 'PUBLIC_WITNESS', 'private_points': 'PRIVATE_WITNESS'}
SOURCE_PATHS = (
    'src/community/security/oauth2-geonode/src/main/java/org/geoserver/security/oauth2/GeoNodeOAuth2AuthenticationProvider.java',
    'src/community/security/oauth2-geonode/src/main/java/org/geoserver/security/oauth2/GeoNodeOAuth2FilterConfig.java',
    'src/main/src/main/java/org/geoserver/security/config/PreAuthenticatedUserNameFilterConfig.java',
    'src/main/src/main/java/org/geoserver/security/password/URLMasterPasswordProvider.java',
    'src/main/src/main/java/org/geoserver/security/xml/XMLUserGroupService.java',
    'src/main/src/main/java/org/geoserver/security/xml/XMLRoleService.java',
    'src/extension/geofence/geofence-server/src/main/java/org/geoserver/geofence/server/rest/RulesRestController.java',
    'src/extension/geofence/geofence-server/src/main/java/org/geoserver/geofence/server/rest/xml/JaxbRule.java',
)


def _element(parent, tag, value=None, **attrs):
    result = ET.SubElement(parent, tag, attrs)
    if value is not None:
        result.text = str(value)
    return result


def _named(tag, name, class_name, **fields):
    result = ET.Element(tag)
    for key, value in dict(id='fixture-' + name, name=name, className=class_name, **fields).items():
        _element(result, key, value)
    return result


def _xml(root):
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='unicode') + '\n'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _point_files(label):
    """One Point shape and one dBASE III record; no third-party generator needed."""
    def header(words):
        return struct.pack('>7i', 9994, 0, 0, 0, 0, 0, words) + struct.pack(
            '<2i8d', 1000, 1, 1., 2., 1., 2., 0., 0., 0., 0.)
    shape = struct.pack('<idd', 1, 1., 2.)
    shp = header(64) + struct.pack('>2i', 1, 10) + shape
    shx = header(54) + struct.pack('>2i', 50, 10)
    descriptor = b'label\0\0\0\0\0\0' + b'C' + bytes(4) + bytes([32, 0]) + bytes(14)
    dbf = (struct.pack('<4BIHH20x', 3, 126, 1, 1, 1, 65, 33) + descriptor
           + b'\r ' + label.encode('ascii').ljust(32, b' ') + b'\x1a')
    prj = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
           '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]\n')
    return {'shp': shp, 'shx': shx, 'dbf': dbf, 'prj': prj.encode(), 'cpg': b'UTF-8\n'}


def geofence_rules():
    """Native RulesRestController POST bodies, provisioned by the fixture admin."""
    result = []
    for priority, layer, role in ((10, 'public_points', None), (20, 'private_points', 'ROLE_FIXTURE_READER')):
        rule = ET.Element('Rule')
        for name, value in (('priority', priority), ('workspace', WORKSPACE), ('layer', layer),
                            ('roleName', role), ('access', 'ALLOW')):
            if value is not None:
                _element(rule, name, value)
        result.append(_xml(rule))
    # Native GeoFence DENY discards catalog mode; a lower-priority fixed-layer
    # EXCLUDE rule retains MIXED mode, hiding capabilities while challenging
    # direct data access through the real SecureCatalog. Earlier reader ALLOW wins.
    fallback = ET.Element('Rule')
    for name, value in (('priority', 30), ('workspace', WORKSPACE),
                        ('layer', 'private_points'), ('access', 'ALLOW')):
        _element(fallback, name, value)
    details = _element(fallback, 'layerDetails')
    for name, value in (('layerType', 'VECTOR'), ('cqlFilterRead', 'EXCLUDE'),
                        ('cqlFilterWrite', 'EXCLUDE'), ('catalogMode', 'MIXED')):
        _element(details, name, value)
    result.append(_xml(fallback))
    return result


def prepare(source_root, output, identity_base_url, client_id, client_secret, *, cache_seconds=2,
            stateless_bearer_authentication=False):
    """Generate a fresh data directory and return a publishable, secret-free manifest.

    ``source_root`` is the retained reactor's source directory or its geoserver
    subdirectory. Output is exclusively new and may not exist, including symlinks.
    URLs are restricted to explicit IPv4 loopback. Secret values are never returned.
    """
    source_root, output = Path(source_root).resolve(), Path(output).absolute()
    gs = source_root / 'geoserver' if (source_root / 'geoserver').is_dir() else source_root
    parsed = urlsplit(identity_base_url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('identity URL must be an explicit loopback HTTP origin')
    if type(stateless_bearer_authentication) is not bool:
        raise ValueError('stateless bearer fixture option must be an explicit boolean')
    if not isinstance(cache_seconds, int) or not 1 <= cache_seconds <= 60:
        raise ValueError('fixture cache lifetime must be 1..60 seconds')
    if not isinstance(client_id, str) or not client_id or not isinstance(client_secret, str) or len(client_secret) < 24:
        raise ValueError('provide a disposable client ID and at least 24 secret characters')
    source_records = []
    for name in SOURCE_PATHS:
        path = gs / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('missing regular retained configuration source: ' + name)
        source_records.append({'path': name, 'sha256': _sha(path)})
    if output.exists() or output.is_symlink():
        raise FileExistsError('fixture output must be new')
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)

    def write(name, data):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))
        path.chmod(0o600)

    def xml(name, root):
        write(name, _xml(root))

    write(MARKER, b'')
    write('security/version.properties', 'version=2.6\n')
    security = ET.Element('security')
    _element(security, 'roleServiceName', 'fixture')
    _element(security, 'authProviderNames')  # no username/password or inherited default provider
    _element(security, 'configPasswordEncrypterName', 'pbePasswordEncoder')
    _element(security, 'encryptingUrlParams', 'false')
    chains = _element(security, 'filterChain')
    for name, path, interceptor in (
            ('rest', '/rest.*,/rest/**,/gwc/rest.*,/gwc/rest/**', 'restInterceptor'),
            ('default', '/**', 'interceptor')):
        chain = _element(chains, 'filters', name=name,
                         **{'class': 'org.geoserver.security.ServiceLoginFilterChain',
                            'interceptorName': interceptor, 'exceptionTranslationName': 'exception',
                            'path': path, 'disabled': 'false', 'allowSessionCreation': 'false',
                            'ssl': 'false', 'matchHTTPMethod': 'false'})
        _element(chain, 'filter', 'fixture-oauth')
        _element(chain, 'filter', 'anonymous')
    remember = _element(security, 'rememberMeService')
    _element(remember, 'className', 'org.geoserver.security.rememberme.GeoServerTokenBasedRememberMeServices')
    _element(remember, 'key', secrets.token_urlsafe(32))
    xml('security/config.xml', security)

    filter_prefix = 'org.geoserver.security.filter.'
    for name, tag, cls, fields in (
            ('anonymous', 'anonymousAuthentication', 'GeoServerAnonymousAuthenticationFilter', {}),
            ('exception', 'exceptionTranslation', 'GeoServerExceptionTranslationFilter', {}),
            ('contextNoAsc', 'contextPersistence', 'GeoServerSecurityContextPersistenceFilter', {'allowSessionCreation': 'false'}),
            ('contextAsc', 'contextPersistence', 'GeoServerSecurityContextPersistenceFilter', {'allowSessionCreation': 'true'}),
            ('interceptor', 'securityInterceptor', 'GeoServerSecurityInterceptorFilter', {'allowIfAllAbstainDecisions': 'false', 'securityMetadataSource': 'geoserverMetadataSource'}),
            ('restInterceptor', 'securityInterceptor', 'GeoServerSecurityInterceptorFilter', {'allowIfAllAbstainDecisions': 'false', 'securityMetadataSource': 'restFilterDefinitionMap'})):
        xml('security/filter/' + name + '/config.xml', _named(tag, name, filter_prefix + cls, **fields))
    origin = identity_base_url.rstrip('/')
    oauth = _named('geoNodeOauth2Authentication', 'fixture-oauth',
                   'org.geoserver.security.oauth2.GeoNodeOAuthAuthenticationFilter',
                   roleSource='UserGroupService', userGroupServiceName='fixture', roleServiceName='fixture',
                   cliendId=client_id, clientSecret=client_secret,
                   accessTokenUri=origin + '/token', userAuthorizationUri=origin + '/authorize',
                   checkTokenEndpointUrl=origin + '/verify_token', redirectUri=origin + '/unused_callback',
                   logoutUri=origin + '/logout', scopes='read', enableRedirectAuthenticationEntryPoint='false',
                   forceAccessTokenUriHttps='false', forceUserAuthorizationUriHttps='false',
                   loginEndpoint='/j_spring_oauth2_geonode_login', logoutEndpoint='/j_spring_oauth2_geonode_logout',
                   allowUnSecureLogging='false')
    if stateless_bearer_authentication:
        _element(oauth, 'statelessBearerAuthentication', 'true')
    oauth.find('roleSource').set('class', 'org.geoserver.security.config.PreAuthenticatedUserNameFilterConfig$PreAuthenticatedUserNameRoleSource')
    xml('security/filter/fixture-oauth/config.xml', oauth)
    for name, minimum in (('default', 12), ('master', 24)):
        xml('security/pwpolicy/' + name + '/config.xml', _named('passwordPolicy', name,
            'org.geoserver.security.validation.PasswordValidatorImpl', uppercaseRequired='false',
            lowercaseRequired='false', digitRequired='false', minLength=minimum, maxLength=-1))
    master = ET.Element('masterPassword')
    _element(master, 'providerName', 'fixture')
    xml('security/masterpw.xml', master)
    xml('security/masterpw/fixture/config.xml', _named('urlProvider', 'fixture',
        'org.geoserver.security.password.URLMasterPasswordProvider', readOnly='true',
        url='file:passwd', encrypting='false'))
    write('security/masterpw/fixture/passwd', secrets.token_urlsafe(48))
    xml('security/usergroup/fixture/config.xml', _named('userGroupService', 'fixture',
        'org.geoserver.security.xml.XMLUserGroupService', fileName='users.xml', checkInterval=0,
        validating='true', passwordEncoderName='plainTextPasswordEncoder', passwordPolicyName='default'))
    users = ET.Element('userRegistry', {'version': '1.0', 'xmlns': 'http://www.geoserver.org/security/users'})
    user_list = _element(users, 'users')
    for user in IDENTITIES:
        _element(user_list, 'user', enabled=str(user != 'fixture-disabled').lower(), name=user,
                 password='plain:' + secrets.token_urlsafe(48))
    _element(users, 'groups')
    xml('security/usergroup/fixture/users.xml', users)
    xml('security/role/fixture/config.xml', _named('roleService', 'fixture',
        'org.geoserver.security.xml.XMLRoleService', fileName='roles.xml', checkInterval=0,
        validating='true', adminRoleName='FIXTURE_ADMIN', groupAdminRoleName='FIXTURE_GROUP_ADMIN'))
    roles = ET.Element('roleRegistry', {'version': '1.0', 'xmlns': 'http://www.geoserver.org/security/roles'})
    role_list = _element(roles, 'roleList')
    for role in ('FIXTURE_ADMIN', 'FIXTURE_GROUP_ADMIN', 'ROLE_FIXTURE_READER'):
        _element(role_list, 'role', id=role)
    user_list = _element(roles, 'userList')
    for user, role in (('fixture-reader', 'ROLE_FIXTURE_READER'), ('fixture-admin', 'FIXTURE_ADMIN'),
                       ('fixture-disabled', 'ROLE_FIXTURE_READER')):
        user_roles = _element(user_list, 'userRoles', username=user)
        _element(user_roles, 'roleRef', roleID=role)
    _element(roles, 'groupList')
    xml('security/role/fixture/roles.xml', roles)
    write('security/rest.properties', '/**;GET,HEAD,OPTIONS,POST,PUT,DELETE=ROLE_ADMINISTRATOR\n')
    write('security/services.properties', 'wfs.Transaction=ROLE_ADMINISTRATOR\n')
    write('security/layers.properties', '*.*.r=ROLE_ADMINISTRATOR\n*.*.w=ROLE_ADMINISTRATOR\nmode=HIDE\n')
    write('geofence/geofence-server.properties', 'ruleReaderBackend=ruleReaderService\nruleReaderFrontend=cachedRuleReader\nuseRolesToFilter=true\nacceptedRoles=ROLE_FIXTURE_READER\ngrantWriteToWorkspacesToAuthenticatedUsers=false\n')
    write('geofence/geofence-datasource-ovr.properties',
          'geofenceConfigurationManager.configuration.servicesUrl=internal:/\n'
          'geofenceEntityManagerFactory.jpaPropertyMap[hibernate.hbm2ddl.auto]=update\n'
          'geofenceDataSource.username=fixture-db\n'
          'geofenceDataSource.password=' + secrets.token_urlsafe(48) + '\n')
    write('fixture-context.xml', '<beans xmlns="http://www.springframework.org/schema/beans" '
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xsi:schemaLocation="http://www.springframework.org/schema/beans http://www.springframework.org/schema/beans/spring-beans.xsd">\n'
          '<bean id="authCacheLifecycleHandler" class="org.geoserver.security.auth.GuavaAuthenticationCacheImpl">'
          '<constructor-arg value="1000"/><constructor-arg value="' + str(cache_seconds) + '"/>'
          '<constructor-arg value="' + str(cache_seconds) + '"/><constructor-arg value="1"/>'
          '<constructor-arg value="3"/></bean>\n</beans>\n')

    global_info = ET.Element('global')
    settings = _element(global_info, 'settings')
    for key, value in (('id', 'fixture-settings'), ('charset', 'UTF-8'), ('numDecimals', 8),
                       ('verbose', 'false'), ('verboseExceptions', 'false')):
        _element(settings, key, value)
    jai = _element(global_info, 'jai')
    for key, value in (('allowInterpolation', 'false'), ('recycling', 'false'),
                       ('tilePriority', 5), ('tileThreads', 2), ('memoryCapacity', 0.1),
                       ('memoryThreshold', 0.75), ('imageIOCache', 'false')):
        _element(jai, key, value)
    _element(global_info, 'globalServices', 'true')
    xml('global.xml', global_info)
    wfs = ET.Element('wfs')
    for key, value in (('id', 'fixture-wfs'), ('name', 'WFS'), ('enabled', 'true'),
                       ('title', 'Disposable authorization fixture'), ('serviceLevel', 'BASIC'), ('maxFeatures', 10)):
        _element(wfs, key, value)
    xml('wfs.xml', wfs)
    workspace = ET.Element('workspace')
    _element(workspace, 'id', 'fixture-workspace')
    _element(workspace, 'name', WORKSPACE)
    xml('workspaces/fixture/workspace.xml', workspace)
    xml('workspaces/default.xml', workspace)
    namespace = ET.Element('namespace')
    for key, value in (('id', 'fixture-namespace'), ('prefix', WORKSPACE), ('uri', 'urn:ambisgis:configured-auth-fixture')):
        _element(namespace, key, value)
    xml('workspaces/fixture/namespace.xml', namespace)
    for layer, label in LAYERS.items():
        for suffix, data in _point_files(label).items():
            write('data/' + layer + '.' + suffix, data)
        store = ET.Element('dataStore')
        for key, value in (('id', 'fixture-store-' + layer), ('name', layer), ('type', 'Shapefile'), ('enabled', 'true')):
            _element(store, key, value)
        _element(_element(store, 'workspace'), 'id', 'fixture-workspace')
        params = _element(store, 'connectionParameters')
        _element(params, 'entry', 'file:data/' + layer + '.shp', key='url')
        _element(params, 'entry', 'urn:ambisgis:configured-auth-fixture', key='namespace')
        _element(params, 'entry', 'false', key='create spatial index')
        xml('workspaces/fixture/' + layer + '/datastore.xml', store)
        feature = ET.Element('featureType')
        for key, value in (('id', 'fixture-feature-' + layer), ('name', layer), ('nativeName', layer),
                           ('title', layer), ('srs', 'EPSG:4326'), ('projectionPolicy', 'FORCE_DECLARED'), ('enabled', 'true')):
            _element(feature, key, value)
        _element(_element(feature, 'namespace'), 'id', 'fixture-namespace')
        _element(_element(feature, 'store', **{'class': 'dataStore'}), 'id', 'fixture-store-' + layer)
        for bounds in ('nativeBoundingBox', 'latLonBoundingBox'):
            bbox = _element(feature, bounds)
            for key, value in (('minx', 1), ('maxx', 1), ('miny', 2), ('maxy', 2), ('crs', 'EPSG:4326')):
                _element(bbox, key, value)
        xml('workspaces/fixture/' + layer + '/' + layer + '/featuretype.xml', feature)
        layer_info = ET.Element('layer')
        for key, value in (('id', 'fixture-layer-' + layer), ('name', layer), ('type', 'VECTOR'), ('enabled', 'true')):
            _element(layer_info, key, value)
        _element(_element(layer_info, 'resource', **{'class': 'featureType'}), 'id', 'fixture-feature-' + layer)
        xml('workspaces/fixture/' + layer + '/' + layer + '/layer.xml', layer_info)

    return {'format': 1, 'scope': 'disposable inherited-component enforcement fixture',
            'source_definitions': source_records, 'workspace': WORKSPACE, 'identities': list(IDENTITIES),
            'layers': LAYERS.copy(), 'cache_seconds': cache_seconds,
            'stateless_bearer_authentication': bool(stateless_bearer_authentication),
            'spring_context': str(output / 'fixture-context.xml'),
            'geofence_rule_path': '/rest/geofence/rules', 'geofence_rule_bodies': geofence_rules(),
            'files': [{'path': str(p.relative_to(output)), 'sha256': _sha(p)}
                      for p in sorted(output.rglob('*')) if p.is_file()],
            'limitations': ['Synthetic identity endpoint, not GeoNode server acceptance.',
                            ('Opt-in bearer mode retains native token cache expiry; existing HTTP sessions suppress cache writes.'
                             if stateless_bearer_authentication else
                             'Native OAuth session scope may suppress authentication-cache writes.'),
                            'New local XML credentials are not reachable by a configured password authentication provider.',
                            'GeoFence rules must be posted through the real API before resource assertions.']}


def scrub_secrets(output):
    """Redact only a marked task-created fixture after its application is stopped."""
    output = Path(output)
    marker = output / MARKER
    if output.is_symlink() or not marker.is_file() or marker.is_symlink():
        raise ValueError('refuse to scrub an unmarked fixture')
    redacted = []
    for path in sorted((output / 'security').rglob('*')):
        if path.is_symlink():
            raise ValueError('refuse to scrub fixture containing symlinks')
        if not path.is_file():
            continue
        relative = str(path.relative_to(output))
        if path.suffix == '.xml':
            root = ET.parse(path).getroot()
            changed = False
            for element in root.iter():
                if element.tag.rsplit('}', 1)[-1] in ('clientSecret', 'key'):
                    element.text = 'REDACTED-DISPOSABLE-CREDENTIAL'
                    changed = True
                if 'password' in element.attrib:
                    element.set('password', 'REDACTED-DISPOSABLE-CREDENTIAL')
                    changed = True
            if changed:
                path.write_text(_xml(root), encoding='utf-8')
                redacted.append(relative)
        elif path.name in ('passwd', 'masterpw.digest', 'masterpw.info', 'geoserver.jceks'):
            path.write_bytes(b'REDACTED-DISPOSABLE-CREDENTIAL\n')
            redacted.append(relative)
    properties = output / 'geofence/geofence-datasource-ovr.properties'
    if properties.is_symlink():
        raise ValueError('refuse to scrub fixture containing symlinks')
    if properties.is_file():
        lines = properties.read_text(encoding='utf-8').splitlines()
        lines = ['geofenceDataSource.password=REDACTED-DISPOSABLE-CREDENTIAL'
                 if line.startswith('geofenceDataSource.password=') else line for line in lines]
        properties.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        redacted.append(str(properties.relative_to(output)))
    return redacted
