"""Source-owned REST membership configuration for the strict role fixture.

Fixed resource rules remain real GeoFence rules. XML contains identity records
only; no local role membership can rescue an unavailable remote role service.
"""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

ROLE = 'ROLE_FIXTURE-READERS'
ROLE_TTL_MS = 1000
AUTH_TTL_SECONDS = 2
PROPAGATION_DEADLINE_SECONDS = 7
ROLE_FAILURE_DEADLINE_SECONDS = 15
ROLE_FAILURE_CONFIRMATION_SECONDS = 35


def configure(data_dir, fixture, config):
    data_dir = Path(data_dir)
    role_path = data_dir / 'security/role/fixture/config.xml'
    root = ET.Element('authKeyRESTRoleService')
    fields = dict(id='fixture-remote-role-service', name='fixture',
        className='org.geoserver.security.GeoServerRestRoleService',
        baseUrl=config['site_url'].rstrip('/'), rolesRESTEndpoint='/api/roles',
        adminRoleRESTEndpoint='/api/adminRole', usersRESTEndpoint='/api/users',
        rolesJSONPath='$.groups', adminRoleJSONPath='$.adminRole',
        usersJSONPath="$.users[?(@.username=='${username}')].groups",
        authApiKey=config['role_service_api_key'], cacheConcurrencyLevel=4,
        cacheMaximumSize=100, cacheExpirationTime=ROLE_TTL_MS,
        strictGeoNodeRoles='true', connectTimeout=1500, readTimeout=1500)
    for key, value in fields.items(): ET.SubElement(root, key).text = str(value)
    ET.indent(root)
    role_path.write_text(ET.tostring(root, encoding='unicode') + '\n')
    # Do not retain inactive privileged XML membership as a fallback service.
    roles = data_dir / 'security/role/fixture/roles.xml'
    roles.write_text('<roleRegistry xmlns="http://www.geoserver.org/security/roles" version="1.0"><roleList/><userList/><groupList/></roleRegistry>\n')
    properties = data_dir / 'geofence/geofence-server.properties'
    properties.write_text(properties.read_text().replace('ROLE_FIXTURE_READER', ROLE))
    fixture['geofence_rule_bodies'] = [body.replace('ROLE_FIXTURE_READER', ROLE) for body in fixture['geofence_rule_bodies']]
    fixture.update(role_authority='GeoNode exact active user membership over authenticated HTTP; local UGS identity-only',
                   role_service_class=fields['className'], role_cache_ms=ROLE_TTL_MS,
                   propagation_deadline_seconds=PROPAGATION_DEADLINE_SECONDS,
                   canonical_role=ROLE, administrative_mapping='admin -> ROLE_ADMIN -> ROLE_ADMINISTRATOR',
                   url_key_authentication_enabled=False)
    fixture['limitations'] = ['Local user records are identity-only; automatic user provisioning unaccepted.',
        'Fixed GeoFence resource rules, not full GeoNode object-sharing synchronization.',
        'Single process bearer fixture; browser/multi-node propagation unaccepted.']
    for item in fixture['files']:
        item['sha256'] = hashlib.sha256((data_dir / item['path']).read_bytes()).hexdigest()
    return fixture


def assert_configuration_stable(data_dir, before):
    after = configuration_hashes(data_dir)
    if after != before: raise RuntimeError('membership test changed local security or resource rules')
    return after


def configuration_hashes(data_dir):
    data_dir = Path(data_dir)
    paths = ('security/role/fixture/config.xml', 'security/role/fixture/roles.xml',
             'security/usergroup/fixture/users.xml', 'security/filter/fixture-oauth/config.xml',
             'geofence/geofence-server.properties')
    return {name: hashlib.sha256((data_dir / name).read_bytes()).hexdigest() for name in paths}
