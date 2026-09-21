"""Real GeoNode issuance -> unchanged configured GeoServer WAR integration.

The only identity adapter below reads passive request counts and provides secret
redaction to the existing HTTP assertion helper. It implements no identity server,
issues no synthetic valid token and cannot manufacture application responses.
"""
import base64
import concurrent.futures
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

from protocol_probe import OAuthBrowser, ProtocolError, SecretRegistry, form_fields, scan_response

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'java'))
from configured_auth_probe import Matrix, wfs
from configured_auth_fixture import prepare, scrub_secrets
from configured_auth_evidence import validate_geojson
import runtime_inputs


def native_logout_message(value):
    """Decode only the bounded native logout notification, never an identity input.

    This checks the signed-cookie payload's exact message shape; it does not
    claim to verify its signature. Cookie identity is not used for authorization.
    """
    try:
        if not isinstance(value, str) or len(value) > 4096:
            return False
        payload, timestamp, signature = value.rsplit(':', 2)
        if not timestamp or not signature:
            return False
        compressed = payload.startswith('.')
        payload = payload[1:] if compressed else payload
        raw = base64.b64decode(payload + '=' * (-len(payload) % 4), altchars=b'-_', validate=True)
        if compressed:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(raw, 8193)
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                return False
        if len(raw) > 8192:
            return False
        messages = json.loads(raw.decode('latin-1'))
        if not isinstance(messages, list) or len(messages) != 1:
            return False
        message = messages[0]
        return (isinstance(message, list) and len(message) in (4, 5)
                and message[0] == '__json_message' and type(message[1]) is int and message[1] in (0, 1)
                and type(message[2]) is int and message[2] == 25
                and message[3] == 'You have signed out.'
                and (len(message) == 4 or message[4] == ''))
    except (ValueError, UnicodeError, zlib.error):
        return False


def response_secret_policy(response, registry, *, token_fields=None, authorization_token=None, forbidden=(),
                           allowed_cookie_names=('sessionid', 'csrftoken')):
    """Allow exact OAuth token fields and native cookie delivery, never arbitrary secrets.

    Every header occurrence remains visible. Native session/CSRF cookies are
    credential-delivery channels even on a 401 response, but unexpected cookie
    names, duplicate cookies, private configuration values, and secrets in other
    fields/headers still fail. Returned evidence contains names/counts only.
    """
    raw_scan = scan_response(response, registry)
    for row in raw_scan['header_matches']:
        row['name'] = response.headers[row['index']][0].lower()
    secrets_all = set(registry.sensitive_values())
    forbidden_registry = SecretRegistry()
    forbidden_registry.add(*forbidden)
    body = response.body.decode('utf-8', errors='replace')
    valid = set(allowed_cookie_names) <= {'sessionid', 'csrftoken', 'messages'}
    allowed_fields = []
    try:
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('duplicate JSON field')
                value[key] = item
            return value
        parsed = json.loads(body, object_pairs_hook=unique)
        decoded_body = json.dumps(parsed, ensure_ascii=False)
    except (ValueError, UnicodeError):
        parsed, decoded_body = None, body
        if token_fields:
            valid = False
    forbidden_hits = forbidden_registry.matches(decoded_body)
    masked = parsed.copy() if isinstance(parsed, dict) else None
    for name, expected in (token_fields or {}).items():
        if expected is None:
            continue
        if (name not in ('access_token', 'refresh_token', 'id_token') or not isinstance(expected, str)
                or not expected or masked is None or masked.get(name) != expected):
            valid = False
            continue
        masked[name] = '[AUTHORIZED_TOKEN_FIELD]'
        allowed_fields.append(name)
    body_remaining = json.dumps(masked, ensure_ascii=False) if masked is not None else decoded_body
    unapproved_body = registry.matches(body_remaining)
    header_hits, allowed_headers = [], []
    cookie_counts = {}
    authorization_count = len(response.values('authorization'))
    for index, (name, value) in enumerate(response.headers):
        lower = name.lower()
        forbidden_hits += forbidden_registry.matches(name + ': ' + value)
        excluded = set()
        if lower == 'authorization' and authorization_token is not None:
            if authorization_count != 1 or value != 'Bearer ' + authorization_token:
                valid = False
            else:
                allow = SecretRegistry(); allow.add(authorization_token)
                excluded.update(allow.sensitive_values())
                allowed_headers.append({'index': index, 'name': lower, 'delivery': 'requested bearer token'})
        elif lower == 'set-cookie':
            cookie = SimpleCookie()
            try:
                cookie.load(value)
            except Exception:
                cookie = SimpleCookie()
            cookie_name = next(iter(cookie), None)
            if (len(cookie) != 1 or cookie_name not in allowed_cookie_names
                    or (cookie_name == 'messages' and not native_logout_message(cookie[cookie_name].value))):
                valid = False
            else:
                cookie_name = next(iter(cookie))
                cookie_counts[cookie_name] = cookie_counts.get(cookie_name, 0) + 1
                if cookie_counts[cookie_name] != 1:
                    valid = False
                allow = SecretRegistry(); allow.add(value, cookie[cookie_name].value)
                excluded.update(allow.sensitive_values())
                allowed_headers.append({'index': index, 'name': lower, 'cookie_name': cookie_name,
                                        'delivery': 'exact native logout notification' if cookie_name == 'messages' else 'native session or CSRF cookie'})
        hits = sum((name + ': ' + value).count(secret) for secret in secrets_all - excluded if secret)
        if hits:
            header_hits.append({'index': index, 'name': lower, 'matches': hits,
                                **({'cookie_name': next(iter(cookie), None)} if lower == 'set-cookie' else {})})
    return {'passed': valid and not forbidden_hits and not unapproved_body and not header_hits,
            'raw_scan': raw_scan, 'unapproved_body_matches': unapproved_body,
            'unapproved_header_matches': header_hits, 'forbidden_configuration_matches': forbidden_hits,
            'authorized_token_fields': allowed_fields, 'authorized_headers': allowed_headers,
            'protocol_structure_valid': valid}


def tokeninfo_secret_policy(response, registry, token, *, strict, forbidden=()):
    options = {} if strict else {'token_fields': {'access_token': token}, 'authorization_token': token}
    policy = response_secret_policy(response, registry, forbidden=forbidden, **options)
    policy['strict_verifier'] = strict
    if strict:
        try:
            value = json.loads(response.body)
        except (ValueError, UnicodeError):
            value = None
        private_shape = (isinstance(value, dict)
                         and not any(name in value for name in ('access_token', 'refresh_token', 'id_token'))
                         and not response.values('authorization'))
        policy['strict_token_omission'] = private_shape
        policy['passed'] = policy['passed'] and private_shape
    return policy


SOURCE_REDACTION_FIELDS = (
    'source_diagnostic_redactions', 'source_credential_field_redactions',
    'source_private_key_redactions', 'source_opaque_value_redactions',
)


def source_redaction_evidence(paths):
    records = []
    for path in paths:
        totals = dict.fromkeys(SOURCE_REDACTION_FIELDS, 0)
        observed, invalid = 0, 0
        if Path(path).exists():
            for line in Path(path).read_text(errors='replace').splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict) or not any(name in row for name in SOURCE_REDACTION_FIELDS):
                    continue
                observed += 1
                for name in SOURCE_REDACTION_FIELDS:
                    count = row.get(name, 0)
                    if type(count) is not int or count < 0:
                        invalid += 1
                    else:
                        totals[name] += count
        records.append({'log': Path(path).name, 'counter_records': observed,
                        **totals, 'invalid_counter_records': invalid})
    result = {'logs': records,
              **{name: sum(row[name] for row in records) for name in SOURCE_REDACTION_FIELDS},
              'invalid_counter_records': sum(row['invalid_counter_records'] for row in records),
              'capture_scope': 'WARNING and above source message text; exception class only; not a full DEBUG audit',
              'opaque_scope': 'Conservative opaque candidates may include non-secret identifiers; reported separately.'}
    result['passed'] = not (result['invalid_counter_records'] or
                            any(result[name] for name in SOURCE_REDACTION_FIELDS[:3]))
    return result


def disabled_login_evidence(response, requests, origin, provisioning):
    expected_path = provisioning.get('disabled_login_redirect_path')
    target = None
    if response is not None and response.status in (302, 303):
        try:
            location = response.one('location')
        except ProtocolError:
            location = None
        if location:
            target = urllib.parse.urlsplit(urllib.parse.urljoin(response.url, location))
    source_origin = urllib.parse.urlsplit(origin)
    last = requests[-1] if requests else {}
    passed = (isinstance(expected_path, str) and expected_path.startswith('/')
              and last.get('method') == 'POST' and last.get('path') == '/account/login/'
              and last.get('status') in (302, 303) and target is not None
              and (target.scheme, target.netloc, target.path) ==
                  (source_origin.scheme, source_origin.netloc, expected_path)
              and not target.query and not target.fragment)
    return {'case': 'disabled-user-login', 'passed': bool(passed),
            'expected_outcome': 'Native login POST redirects to exact same-origin path generated by native reverse.',
            'expected_redirect_path': expected_path,
            'observed_redirect_path': target.path if target is not None else None,
            'requests': requests}


class LiveEvidence:
    """Passive evidence interface, not the synthetic Identity endpoint."""
    def __init__(self, log, registry, browsers, private):
        self.log, self.registry, self.browsers, self.private = Path(log), registry, browsers, private

    def sensitive(self):
        return list(self.registry.sensitive_values()) + self.private + [value for client in self.browsers
                                                                  for value in client.secrets.sensitive_values()]

    @property
    def calls(self):
        rows = []
        if self.log.exists():
            for line in self.log.read_text(errors='replace').splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get('event') == 'http_request' and row.get('path', '').startswith('/api/o/v4/tokeninfo'):
                    rows.append(row)
        return rows


def exercise(invocation, config, private):
    from run import Capture, digest, save, stop
    output = Path(config['output'])
    runtime = invocation['runtime']
    origin = config['site_url'].rstrip('/')
    registry = SecretRegistry()
    registry.add(*private)
    browsers, processes, captures = [], {}, []
    report = {'result_exit_code': 1, 'identity_is_synthetic': False, 'protocol': [],
              'scenarios': [], 'findings': [], 'cleanup': {}, 'mutations': [], 'transport_faults': [],
              'role_authority': 'Explicitly mirrored GeoServer XML users/roles with GeoFence; no automatic GeoNode role synchronization.',
              'coverage_limits': ['No full browser JavaScript/SSO acceptance.',
                                  'Concurrent verification global windows are not individual request attribution.',
                                  'Malformed response adversaries remain the separate #59 synthetic regression.',
                                  'Delay/truncation are explicitly injected transport faults after a real native200; native output is unchanged without the private fault control.']}
    identity = LiveEvidence(output / 'geonode-runtime.log', registry, browsers, private)
    data_dir = output / 'geoserver-data'
    matrices = []

    def row(case, response, expected, predicate=True, *, token_fields=None, authorization_token=None, tokeninfo_token=None, detail=None,
            allowed_cookie_names=('sessionid', 'csrftoken')):
        registry.add(*(value for browser in browsers for value in browser.secrets.sensitive_values()))
        if tokeninfo_token is not None:
            policy = tokeninfo_secret_policy(response, registry, tokeninfo_token,
                                             strict=config.get('strict_verifier', False), forbidden=private)
        else:
            policy = response_secret_policy(response, registry, token_fields=token_fields,
                                            authorization_token=authorization_token, forbidden=private,
                                            allowed_cookie_names=allowed_cookie_names)
        passed = response.status in expected and bool(predicate) and policy['passed']
        record = dict(case=case, expected_status=list(expected), passed=passed,
                      secret_scan=policy, **response.receipt())
        if detail is not None:
            record['detail'] = detail
        report['protocol'].append(record)
        if not passed:
            report['findings'].append({'case': case, 'observed_status': response.status,
                                       'expectation': 'Recorded fixture isolation/content requirement was not met.'})
        return passed

    def client(second=False):
        value = OAuthBrowser(origin, config['second_client_id' if second else 'client_id'],
                             config['redirect_uri'], config['second_client_secret' if second else 'client_secret'])
        browsers.append(value)
        return value

    issuance_browsers = {}

    def issue(username='fixture-reader', second=False):
        # Reuse each real authenticated session and request a fresh native grant.
        # Repeated new password logins would test account throttling instead of
        # token lifecycle. Different principals/applications keep separate jars.
        key = (username, second)
        if key in issuance_browsers:
            value = issuance_browsers[key]
            grant = value.authorize()
        else:
            value = client(second)
            grant = value.authorize(username, config['passwords'][username])
            issuance_browsers[key] = value
        tokens = value.exchange(grant)
        registry.add(tokens.access_token, tokens.refresh_token, grant.code, grant.verifier, grant.state)
        row('http-issued-' + username + ('-second-client' if second else ''), tokens.response, (200,),
            tokens.scope == 'read', token_fields={'access_token': tokens.access_token, 'refresh_token': tokens.refresh_token},
            detail={'flow': 'authorization_code', 'pkce': 'S256', 'login_and_consent': 'actual HTTP session/CSRF',
                    'requests': value.records.copy()})
        return value, grant, tokens

    def basic(client_id, secret):
        value = 'Basic ' + base64.b64encode((client_id + ':' + secret).encode()).decode()
        registry.add(value, value[6:])
        return value

    verifier = client()
    valid_basic = basic(config['client_id'], config['client_secret'])

    def verify(token, authorization=valid_basic, session=None):
        registry.add(token)
        return (session or verifier).request('POST', '/api/o/v4/tokeninfo', form={'token': token},
                  headers={} if authorization is None else {'Authorization': authorization})

    def parse(response):
        try:
            return json.loads(response.body)
        except (ValueError, UnicodeError):
            return {}

    def mutate(action, username='fixture-reader', token=None, seconds=None):
        index = len(report['mutations'])
        command = [invocation['python'], str(HERE / 'manage_fixture.py'), '--config', invocation['config'],
                   'mutate', '--action', action, '--username', username]
        if seconds is not None:
            command += ['--seconds', str(seconds)]
        token_file = None
        if token is not None:
            token_file = output / ('private-mutation-%03d.json' % index)
            save(token_file, {'access_token': token}, private=True)
            command += ['--token-file', str(token_file)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors='replace', env=invocation['environment'])
        capture = Capture(process, output / ('mutation-%03d.log' % index), identity.sensitive)
        captures.append(capture)
        try:
            try:
                code = process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                stop(process, capture)
                raise RuntimeError('GeoNode mutation timed out') from None
            capture.finish()
            report['mutations'].append({'action': action, 'username': username, 'exit_code': code,
                                        'log_sha256': digest(capture.path), 'diagnostic_secret_hits': capture.leaks, 'requested_seconds': seconds})
            if code or capture.leaks:
                raise RuntimeError('GeoNode fixture mutation failed')
        finally:
            if token_file is not None:
                token_file.write_text('SCRUBBED DISPOSABLE TOKEN\n')

    def start_geonode(label):
        path = output / ('geonode-runtime.log' if label == 'initial' else 'geonode-restart.log')
        command = [invocation['python'], str(HERE / 'manage_fixture.py'), '--config', invocation['config'], 'serve']
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors='replace', env=invocation['environment'])
        capture = Capture(process, path, identity.sensitive)
        processes['geonode'] = (process, capture)
        captures.append(capture)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline and process.poll() is None:
            if path.exists() and '"event": "listening"' in path.read_text(errors='replace'):
                report['geonode_' + label] = {'started': True, 'log': path.name}
                identity.log = path
                return
            time.sleep(.2)
        raise RuntimeError('real GeoNode did not reach listening state')

    def start_geoserver(label):
        target = output / ('geoserver-' + label)
        port = urllib.parse.urlsplit(config['geoserver_url']).port
        command = runtime_inputs.launcher_command(Path(runtime['java_home']), Path(runtime['servlet']),
                    Path(runtime['launcher']), Path(runtime['war']), data_dir, target, port=port)
        command[1:1] = ['-Dsun.net.client.defaultReadTimeout=1500', '-Dsun.net.client.defaultConnectTimeout=1500']
        report['geoserver_client_timeouts_ms'] = {'default_read': 1500, 'default_connect': 1500}
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors='replace', env={'PATH': str(Path(runtime['java_home']) / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        capture = Capture(process, output / ('geoserver-' + label + '.log'), identity.sensitive)
        processes['geoserver'] = (process, capture)
        captures.append(capture)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline and process.poll() is None:
            if (target / 'ready.json').exists():
                ready = json.loads((target / 'ready.json').read_text())
                active = ready.get('security_configuration', {})
                if (active.get('stateless_bearer_authentication') is not True
                        or active.get('role_source') != 'UserGroupService'
                        or active.get('user_group_service') != 'fixture'):
                    raise RuntimeError('loaded GeoServer identity configuration mismatch')
                report['geoserver_' + label] = ready
                return ready['port']
            time.sleep(.2)
        raise RuntimeError('exact GeoServer WAR did not reach ready state')

    def stopped(name, label):
        process, capture = processes.pop(name)
        stop(process, capture)
        report['cleanup'][name + '-' + label] = {'process_stopped': process.poll() is not None,
                                               'capture_stopped': not capture.thread.is_alive(),
                                               'diagnostic_secret_hits': capture.leaks}

    def core(matrix, tokens, restart=False):
        reader, outsider, admin = (tokens[name] for name in ('reader', 'outsider', 'admin'))
        matrix.request('anonymous-public', wfs('public_points'), contains='PUBLIC_WITNESS'); matrix.require_last()
        matrix.request('reader-private', wfs('private_points'), reader, contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
        matrix.request('anonymous-private', wfs('private_points'), expected=(401, 403, 404))
        matrix.request('outsider-private', wfs('private_points'), outsider, expected=(401, 403, 404))
        matrix.request('reader-administration-denied', '/rest/workspaces.json', reader, expected=(401, 403, 404))
        matrix.request('admin-workspaces', '/rest/workspaces.json', admin, contains='fixture', excludes=()); matrix.require_last()
        if restart:
            return
        for route in ('/ows', '/fixture/ows', '/fixture/wfs'):
            matrix.request('reader-' + route, wfs('private_points', route), reader, contains='PRIVATE_WITNESS', excludes=())
            matrix.request('outsider-' + route, wfs('private_points', route), outsider, expected=(401, 403, 404))
        for name, token in (('reader', reader), ('outsider', outsider)):
            allowed = name == 'reader'
            matrix.request(name + '-wfs-post', '/wfs', token, 'POST', urllib.parse.urlsplit(wfs('private_points')).query,
                           {'Content-Type': 'application/x-www-form-urlencoded'}, expected=(200,) if allowed else (401, 403, 404),
                           contains='PRIVATE_WITNESS' if allowed else None, excludes=() if allowed else ('PRIVATE_WITNESS',))
        for suffix in ('', '.xml', '.json'):
            name = 'real_identity_workspace_' + (suffix[1:] or 'plain')
            body = json.dumps({'workspace': {'name': name}}) if suffix == '.json' else '<workspace><name>' + name + '</name></workspace>'
            headers = {'Content-Type': 'application/json' if suffix == '.json' else 'application/xml'}
            for identity_name, token in (('anonymous', None), ('reader', reader), ('outsider', outsider)):
                matrix.request('denied-create-' + identity_name + suffix, '/rest/workspaces' + suffix, token,
                               'POST', body, headers, expected=(401, 403, 404))
                matrix.request('absent-after-create-' + identity_name + suffix, '/rest/workspaces/' + name + '.json',
                               admin, expected=(404,), contains=name, excludes=())
            matrix.request('admin-create' + suffix, '/rest/workspaces' + suffix, admin, 'POST', body, headers,
                           expected=(200, 201), excludes=()); matrix.require_last()
            matrix.request('admin-read' + suffix, '/rest/workspaces/' + name + '.json', admin, contains=name, excludes=()); matrix.require_last()
            for identity_name, token in (('reader', reader), ('outsider', outsider)):
                matrix.request('denied-delete-' + identity_name + suffix, '/rest/workspaces/' + name + suffix,
                               token, 'DELETE', expected=(401, 403, 404))
                matrix.request('present-after-delete-' + identity_name + suffix, '/rest/workspaces/' + name + '.json',
                               admin, contains=name, excludes=())
            matrix.request('admin-delete' + suffix, '/rest/workspaces/' + name + suffix, admin, 'DELETE', excludes=()); matrix.require_last()

    try:
        if digest(runtime['war']) != runtime['war_sha256']:
            raise RuntimeError('retained WAR identity changed')
        start_geonode('initial')
        issued = {name: issue('fixture-' + name) for name in ('reader', 'outsider', 'admin')}
        tokens = {name: value[2].access_token for name, value in issued.items()}
        reader_browser, reader_grant, reader_tokens = issued['reader']
        second_browser, second_grant, second_tokens = issue(second=True)
        # Native issuance negative controls: code replay and incorrect verifier.
        replay = reader_browser.token_request({'grant_type': 'authorization_code', 'code': reader_grant.code,
                      'redirect_uri': config['redirect_uri'], 'code_verifier': reader_grant.verifier})
        row('authorization-code-replay', replay, (400, 401))
        wrong_client = client()
        wrong_grant = wrong_client.authorize('fixture-reader', config['passwords']['fixture-reader'])
        wrong = wrong_client.token_request({'grant_type': 'authorization_code', 'code': wrong_grant.code,
                     'redirect_uri': config['redirect_uri'], 'code_verifier': 'x' * 64})
        row('pkce-wrong-verifier', wrong, (400, 401))
        disabled = client()
        try:
            disabled.authorize('fixture-disabled', config['passwords']['fixture-disabled'])
            report['protocol'].append({'case': 'disabled-user-login', 'passed': False})
        except ProtocolError:
            # Use native provision-time reverse, including this real user's PK.
            # An arbitrary form, template or transport failure is never a denial pass.
            provisioning = json.loads((output / 'provisioning.json').read_text())
            report['protocol'].append(disabled_login_evidence(
                disabled.last_response, disabled.records, origin, provisioning))
        good = verify(tokens['reader'])
        good_json = parse(good)
        units = good_json.get('expires_in')
        units_ok = isinstance(units, (int, float)) and 0 < units <= reader_tokens.expires_in * 1000 and units > max(0, reader_tokens.expires_in - 60) * 1000
        row('tokeninfo-valid-reader', good, (200,), good_json.get('issued_to') == 'fixture-reader'
            and good_json.get('client_id') == config['client_id'],
            tokeninfo_token=tokens['reader'])
        report['protocol'].append({'case': 'tokeninfo-expiry-milliseconds', 'passed': units_ok,
             'issuance_expires_in_seconds': reader_tokens.expires_in, 'verification_expires_in_milliseconds': units,
             'remaining_seconds': units / 1000 if isinstance(units, (int, float)) else None})
        for name, auth in (('missing-client-auth', None), ('wrong-client-secret', basic(config['client_id'], secrets.token_urlsafe(36))),
                           ('other-client-credentials', basic(config['second_client_id'], config['second_client_secret']))):
            row('tokeninfo-' + name, verify(tokens['reader'], auth), (401, 403),
                detail={'requirement': 'Verifier client isolation; observe native behavior without manufacturing denial.'})
        row('tokeninfo-second-application', verify(second_tokens.access_token), (401, 403),
            detail={'requirement': 'Token application must match verifier client.', 'separate_geoserver_check': True})
        row('tokeninfo-invalid', verify(secrets.token_urlsafe(36)), (401, 403))
        session_response = verify(tokens['outsider'], session=reader_browser)
        row('tokeninfo-reader-session-outsider-bearer', session_response, (200,),
            parse(session_response).get('issued_to') == 'fixture-outsider',
            tokeninfo_token=tokens['outsider'])
        # Role endpoint controls remain separate from opaque-token verification.
        role_client = client()
        api_auth = 'ApiKey ' + config['api_key']
        registry.add(api_auth)
        for path in ('/api/roles', '/api/users/fixture-reader', '/api/adminRole'):
            row('roles-no-auth-' + path, role_client.request('GET', path), (401, 403))
            row('roles-wrong-key-' + path, role_client.request('GET', path, headers={'Authorization': 'ApiKey invalid-fixture'}), (401, 403))
            valid = role_client.request('GET', path, headers={'Authorization': api_auth})
            row('roles-valid-key-' + path, valid, (200,), isinstance(parse(valid), dict))
        fixture = prepare(Path(runtime['source']), data_dir, origin, config['client_id'], config['client_secret'],
                          cache_seconds=2, stateless_bearer_authentication=True)
        oauth_file = data_dir / 'security/filter/fixture-oauth/config.xml'
        xml = ET.parse(oauth_file)
        for tag, path in (('checkTokenEndpointUrl', '/api/o/v4/tokeninfo'), ('accessTokenUri', '/o/token/'),
                          ('userAuthorizationUri', '/o/authorize/'), ('logoutUri', '/account/logout/')):
            xml.getroot().find(tag).text = origin + path
        xml.getroot().find('redirectUri').text = config['redirect_uri']
        xml.write(oauth_file, encoding='unicode', xml_declaration=True)
        properties = Path(runtime['database_properties']).read_text()
        registry.add(*(line.split('=', 1)[1] for line in properties.splitlines() if line.startswith('geofenceDataSource.password=')))
        (data_dir / 'geofence/geofence-datasource-ovr.properties').write_text(properties)
        fixture['identity_is_synthetic'] = False
        fixture['identity_route'] = '/api/o/v4/tokeninfo'
        for item in fixture['files']:
            item['sha256'] = digest(data_dir / item['path'])
        save(output / 'geoserver-fixture.json', fixture)
        port = start_geoserver('initial')
        matrix = Matrix(port, identity, stateless=True)
        matrices.append(('initial', matrix))
        for n, body in enumerate(fixture['geofence_rule_bodies']):
            matrix.request('provision-geofence-' + str(n), '/rest/geofence/rules', tokens['admin'], 'POST', body,
                           {'Content-Type': 'application/xml'}, expected=(200, 201), excludes=()); matrix.require_last()
        core(matrix, tokens)
        matrix.request('empty-bearer', wfs('private_points'), '', expected=(401, 403, 404))
        invalid_bearer = secrets.token_urlsafe(36)
        registry.add(invalid_bearer)
        matrix.request('invalid-bearer', wfs('private_points'), invalid_bearer, expected=(401, 403, 404))
        matrix.request('wrong-application-bearer', wfs('private_points'), second_tokens.access_token, expected=(401, 403, 404))
        unmapped = issue('fixture-unmapped')[2].access_token
        unmapped_info = verify(unmapped)
        row('tokeninfo-active-unmapped-principal', unmapped_info, (200,),
            parse(unmapped_info).get('issued_to') == 'fixture-unmapped',
            tokeninfo_token=unmapped)
        matrix.request('active-geonode-principal-absent-from-geoserver', wfs('private_points'), unmapped,
                       expected=(401, 403, 404))
        def fault_controls():
            controls = []
            if identity.log.exists():
                for line in identity.log.read_text(errors='replace').splitlines():
                    try:
                        item = json.loads(line)
                    except ValueError:
                        continue
                    if item.get('event') == 'native_verifier_transport_fault':
                        controls.append(item)
            return controls

        for mode in ('delay', 'truncate'):
            fault_token = issue()[2].access_token
            before = len(fault_controls())
            fault_file = output / 'transport-fault.json'
            save(fault_file, {'mode': mode}, private=True)
            started = time.monotonic()
            try:
                matrix.request('native-verifier-transport-' + mode, wfs('private_points'), fault_token,
                               expected=(401, 403, 404))
                elapsed = time.monotonic() - started
            finally:
                fault_file.unlink(missing_ok=True)
                if mode == 'delay':
                    # Drain the bounded native-response delay after the client times out.
                    time.sleep(4)
            controls = fault_controls()[before:]
            native_valid = bool(controls) and all(item.get('mode') == mode and item.get('native_status') == 200
                and item.get('native_body_bytes', 0) > 0 for item in controls)
            bounded = 1 <= elapsed < 5 if mode == 'delay' else elapsed < 5
            report['transport_faults'].append({'mode': mode, 'elapsed_seconds': round(elapsed, 4),
                'native_response_controls': controls, 'native_valid_response_observed': native_valid,
                'passed': matrix.rows[-1]['passed'] and native_valid and bounded,
                'scope': 'Explicit transport injection after real native token verification; fresh unprimed token.'})
        # Fresh tokens guarantee these are independent of existing GeoServer cache entries.
        expired = issue()[2].access_token
        mutate('expire', token=expired)
        row('tokeninfo-expired', verify(expired), (401, 403))
        matrix.request('fresh-expired', wfs('private_points'), expired, expected=(401, 403, 404))
        revoke_browser, _, revoke_tokens = issue()
        row('native-revocation', revoke_browser.revoke(revoke_tokens.access_token), (200,))
        row('tokeninfo-revoked', verify(revoke_tokens.access_token), (401, 403))
        matrix.request('fresh-revoked', wfs('private_points'), revoke_tokens.access_token, expected=(401, 403, 404))
        disabled_token = issue()[2].access_token
        mutate('disable')
        try:
            row('tokeninfo-disabled-owner', verify(disabled_token), (401, 403))
            matrix.request('fresh-disabled-owner', wfs('private_points'), disabled_token, expected=(401, 403, 404))
        finally:
            mutate('enable')
        # GeoNode group changes are real; mirrored XML is intentionally independent.
        group_cached = issue()[2].access_token
        matrix.request('group-change-cache-prime', wfs('private_points'), group_cached,
                       contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
        group_primed_at = time.monotonic()
        mutate('group-remove')
        try:
            changed = role_client.request('GET', '/api/users/fixture-reader', headers={'Authorization': api_auth})
            payload = parse(changed)
            groups = next((u.get('groups', []) for u in payload.get('users', []) if u.get('username') == 'fixture-reader'), None)
            group_removed = groups is not None and 'fixture-readers' not in groups
            row('geonode-role-removal', changed, (200,), group_removed)
            matrix.request('manual-xml-role-cached-after-geonode-group-removal', wfs('private_points'), group_cached,
                           contains='PRIVATE_WITNESS', excludes=())
            cached_row = matrix.rows[-1]
            cached_elapsed = time.monotonic() - group_primed_at
            # Explicitly establish the second request has outlived this cache entry.
            time.sleep(max(0, fixture['cache_seconds'] + .25 - cached_elapsed))
            matrix.request('manual-xml-role-after-cache-expiry', wfs('private_points'), group_cached,
                           contains='PRIVATE_WITNESS', excludes=())
            fresh_row = matrix.rows[-1]
            report['role_change'] = {
                'native_geonode_group_removed': group_removed,
                'cached_request': {'status': cached_row['status'],
                    'elapsed_after_prime_seconds': round(cached_elapsed, 4),
                    'verification_call_delta_global': cached_row.get('verification_calls', 0)},
                'after_cache_expiry': {'status': fresh_row['status'],
                    'elapsed_after_prime_seconds': round(time.monotonic() - group_primed_at, 4),
                    'verification_call_delta_global': fresh_row.get('verification_calls', 0)},
                'passed': group_removed and cached_row['passed'] and fresh_row['passed']
                    and cached_elapsed < fixture['cache_seconds'] and cached_row.get('verification_calls', 0) == 0
                    and fresh_row.get('verification_calls', 0) >= 1,
                'comparison_limitation': 'Local XML role remains both during cache validity and after fresh real verification; no automatic role projection or unified-policy revocation acceptance.',
                'correlation_scope': 'Sequential controlled verifier-call windows, not per-request trace attribution.',
            }
        finally:
            mutate('group-add')
        # GeoNode sessionid cookies are not GeoServer JSESSIONID browser context.
        # This proves unrelated cookies confer no privilege; #59 native surrounding
        # GeoServer browser-context tests remain historical, not repeated here.
        cookie_header = '; '.join(c.name + '=' + c.value for c in reader_browser.cookies)
        registry.add(cookie_header)
        for name, token, allowed in (('reader-cookie-no-bearer', None, False), ('reader-cookie-outsider', tokens['outsider'], False),
                                     ('reader-cookie-reader', tokens['reader'], True)):
            matrix.request(name, wfs('private_points'), token, headers={'Cookie': cookie_header},
                           expected=(200,) if allowed else (401, 403, 404), contains='PRIVATE_WITNESS' if allowed else None,
                           excludes=() if allowed else ('PRIVATE_WITNESS',))
        report['cookie_scope'] = 'Real GeoNode session cookies sent to GeoServer confer no identity; native GeoServer JSESSIONID browser-context restoration is not newly proven.'
        removed_outsider_token = issue('fixture-outsider')[2].access_token
        logout_browser = issued['outsider'][0]
        logout_page = logout_browser.request('GET', '/account/logout/')
        logout_target, logout_fields = logout_browser._form(logout_page, ('csrfmiddlewaretoken',), '/account/logout/')
        logged_out = logout_browser.request('POST', logout_target, form=logout_fields, headers={'Referer': logout_page.url})
        session_cleared = not any(cookie.name == 'sessionid' and cookie.value for cookie in logout_browser.cookies)
        row('native-geonode-logout', logged_out, (302, 303), session_cleared,
            allowed_cookie_names=('sessionid', 'csrftoken', 'messages'),
            detail={'browser_session_cookie_cleared': session_cleared,
                    'notification_scope': 'Exact native allauth signed-out message payload; no cookie identity acceptance.'})
        after_logout = verify(tokens['outsider'])
        row('oauth-grant-after-browser-logout', after_logout, (200,), parse(after_logout).get('issued_to') == 'fixture-outsider',
            tokeninfo_token=tokens['outsider'], detail={'expectation': 'Explicit code grant is independent from browser session logout; do not infer global token revocation.'})
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=35)
        try:
            for n in range(32):
                name = (None, 'reader', 'outsider', 'admin')[n % 4]
                allowed = name in ('reader', 'admin')
                matrix.request('sequential-' + str(n), wfs('private_points'), tokens.get(name), connection=connection,
                               expected=(200,) if allowed else (401, 403, 404), contains='PRIVATE_WITNESS' if allowed else None,
                               excludes=() if allowed else ('PRIVATE_WITNESS',))
        finally:
            connection.close()
        def parallel(n):
            name = (None, 'reader', 'outsider', 'admin')[n % 4]
            allowed = name in ('reader', 'admin')
            matrix.request('parallel-' + str(n), wfs('private_points'), tokens.get(name),
                           expected=(200,) if allowed else (401, 403, 404), contains='PRIVATE_WITNESS' if allowed else None,
                           excludes=() if allowed else ('PRIVATE_WITNESS',))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(parallel, range(32)))
        passive = [json.loads(line) for line in (output / 'geoserver-initial/requests.jsonl').read_text().splitlines()]
        expected_rows = {item['case']: item for item in matrix.rows if item['case'].startswith(('sequential-', 'parallel-'))}
        correlated = []
        for case, expected in sorted(expected_rows.items()):
            found = [item for item in passive if item.get('case') == case]
            correlated.append({'case': case, 'observed_count': len(found),
                'passed': len(found) == 1 and found[0]['status'] == expected['status'] and expected['passed'],
                'request': found[0] if len(found) == 1 else None})
        workers = {}
        for item in passive:
            if item.get('case', '').startswith('sequential-'):
                workers.setdefault(item['thread'], []).append(item['status'])
        mixed = any(200 in statuses and any(status in (401, 403, 404) for status in statuses) for statuses in workers.values())
        report['resource_request_correlation'] = {'scope': 'Actual GeoServer resource request case/thread/status; no individual verifier attribution.',
            'requests': correlated, 'expected_count': 64, 'mixed_identity_worker_reuse': mixed,
            'passed': len(correlated) == 64 and all(item['passed'] for item in correlated) and mixed}
        # Removal is real catalog state, using an issued token never primed in GeoServer.
        mutate('remove', username='fixture-outsider')
        row('tokeninfo-removed-principal', verify(removed_outsider_token), (401, 403))
        matrix.request('fresh-removed-principal', wfs('private_points'), removed_outsider_token,
                       expected=(401, 403, 404))
        # A valid token must also cease authorizing once its real stored expiry
        # passes, even after a successful lookup has populated the nonzero cache.
        expiry_seconds = 4
        expiring = issue()[2].access_token
        mutate('expire-soon', token=expiring, seconds=expiry_seconds)
        mutation_completed_at = time.monotonic()
        matrix.request('real-expiry-cache-prime', wfs('private_points'), expiring,
                       contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
        expiry_samples = []
        expiry_deadline = mutation_completed_at + expiry_seconds + fixture['cache_seconds'] + 3
        while time.monotonic() < expiry_deadline:
            status, body, _ = matrix.request('real-expiry-cache-observe-' + str(len(expiry_samples)),
                wfs('private_points'), expiring, expected=(200, 401, 403, 404), excludes=())
            legitimate = validate_geojson(body, 'PRIVATE_WITNESS') if status == 200 else 'PRIVATE_WITNESS' not in body
            matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and legitimate
            expiry_samples.append({'elapsed_after_expiry_mutation_completed_seconds':
                                   round(time.monotonic() - mutation_completed_at, 4), 'status': status})
            if status in (401, 403, 404):
                break
            time.sleep(.2)
        expiry_denied = bool(expiry_samples and expiry_samples[-1]['status'] in (401, 403, 404))
        row('tokeninfo-expired-after-cache-prime', verify(expiring), (401, 403))
        report['expiry_cache'] = {'source_expiry_seconds_after_mutation': expiry_seconds,
            'configured_cache_ttl_seconds': fixture['cache_seconds'], 'samples': expiry_samples,
            'denial_observed': expiry_denied, 'passed': expiry_denied,
            'timing_scope': 'Monotonic bounds measured after native ORM mutation command completes; no immediate-expiry claim.',
            'denial_upper_bound_after_mutation_completed_seconds':
                expiry_samples[-1]['elapsed_after_expiry_mutation_completed_seconds'] if expiry_denied else None}
        cache_browser, _, cache_tokens = issue()
        cached = cache_tokens.access_token
        matrix.request('real-cache-prime', wfs('private_points'), cached, contains='PRIVATE_WITNESS', excludes=()); matrix.require_last()
        revoked_at = time.monotonic()
        row('native-cache-token-revocation', cache_browser.revoke(cached), (200,))
        samples = []
        deadline = revoked_at + fixture['cache_seconds'] + 4
        while time.monotonic() < deadline:
            status, body, _ = matrix.request('real-cache-observe-' + str(len(samples)), wfs('private_points'), cached,
                                            expected=(200, 401, 403, 404), excludes=())
            legitimate = validate_geojson(body, 'PRIVATE_WITNESS') if status == 200 else 'PRIVATE_WITNESS' not in body
            matrix.rows[-1]['passed'] = matrix.rows[-1]['passed'] and legitimate
            samples.append({'elapsed_after_revoke_seconds': round(time.monotonic() - revoked_at, 4), 'status': status})
            if status in (401, 403, 404):
                break
            time.sleep(.25)
        eventual = bool(samples and samples[-1]['status'] in (401, 403, 404))
        report['cache'] = {'ttl_seconds': fixture['cache_seconds'], 'samples': samples, 'eventual_denial': eventual,
                           'immediate_revocation_claimed': False, 'passed': eventual,
                           'stale_access_lower_bound_seconds': max((s['elapsed_after_revoke_seconds'] for s in samples if s['status'] == 200), default=0),
                           'denial_observed_upper_bound_seconds': samples[-1]['elapsed_after_revoke_seconds'] if eventual else None}
        # Stop the actual verifier; an unprimed issued token cannot borrow a cached identity.
        outage_token = issue()[2].access_token
        stopped('geonode', 'outage')
        matrix.request('fresh-verifier-unavailable', wfs('private_points'), outage_token, expected=(401, 403, 404))
        stopped('geoserver', 'initial')
        start_geonode('restart')
        port = start_geoserver('restart')
        restart = Matrix(port, identity, stateless=True)
        matrices.append(('restart', restart))
        core(restart, tokens, restart=True)
        restart.request('restart-revoked', wfs('private_points'), cached, expected=(401, 403, 404))
        restart.request('restart-expired', wfs('private_points'), expired, expected=(401, 403, 404))
        persisted_response = verify(tokens['reader'])
        row('restart-persisted-token', persisted_response, (200,),
            parse(persisted_response).get('issued_to') == 'fixture-reader',
            tokeninfo_token=tokens['reader'])
        # Reusing the stored browser cookie after service restart must still perform consent/PKCE.
        persisted_grant = reader_browser.authorize()
        persisted_tokens = reader_browser.exchange(persisted_grant)
        registry.add(persisted_tokens.access_token, persisted_tokens.refresh_token)
        row('restart-persisted-browser-session', persisted_tokens.response, (200,),
            token_fields={'access_token': persisted_tokens.access_token, 'refresh_token': persisted_tokens.refresh_token})
        report['result_exit_code'] = 0
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': registry.redact(str(error))}
        report['result_exit_code'] = 1
    finally:
        for name in list(processes):
            try:
                stopped(name, 'final')
            except Exception as error:
                report['cleanup'][name + '-error'] = type(error).__name__
                report['result_exit_code'] = 1
        if data_dir.exists():
            try:
                scrub_secrets(data_dir)
                report['cleanup']['geoserver_config_scrubbed'] = True
            except Exception as error:
                report['cleanup']['scrub_error'] = type(error).__name__
                report['result_exit_code'] = 1
        for label, matrix in matrices:
            for item in matrix.rows:
                item['round'] = label
                item['verification_call_delta_global'] = item.pop('verification_calls', 0)
                report['scenarios'].append(item)
            if matrix.leaks:
                report.setdefault('resource_response_leaks', []).extend(matrix.leaks)
        all_sensitive = identity.sensitive()
        report['late_diagnostic_secret_hits'] = 0
        from run import redact
        for capture in captures:
            if capture.path.exists():
                raw = capture.path.read_text(errors='replace')
                hits = sum(bool(value) and value in raw for value in all_sensitive)
                if hits:
                    report['late_diagnostic_secret_hits'] += hits
                    capture.path.write_text(redact(raw, all_sensitive))
        report['logger_capture_controls'] = {}
        for label in ('initial', 'restart'):
            gs_log = output / ('geoserver-' + label + '.log')
            gn_log = output / ('geonode-runtime.log' if label == 'initial' else 'geonode-restart.log')
            for kind in ('OAUTH', 'CACHE'):
                marker = 'AMBISGIS_CONFIGURED_' + kind + '_LOG_CAPTURE_CONTROL'
                report['logger_capture_controls']['geoserver-' + label + '-' + kind] = gs_log.read_text().count(marker) if gs_log.exists() else 0
            marker = 'AMBISGIS_GEONODE_LOG_CAPTURE_CONTROL'
            report['logger_capture_controls']['geonode-' + label] = gn_log.read_text().count(marker) if gn_log.exists() else 0
        report['diagnostic_secret_hits'] = sum(c.leaks for c in captures)
        report['source_log_redactions'] = source_redaction_evidence([capture.path for capture in captures])
        report['oauth_request_count'] = sum(len(b.records) for b in browsers)
        report['war_sha256_after'] = digest(runtime['war'])
        if (report['war_sha256_after'] != runtime['war_sha256'] or report['diagnostic_secret_hits']
                or report.get('resource_response_leaks') or report['late_diagnostic_secret_hits']
                or not report['source_log_redactions']['passed']
                or any(count != 1 for count in report['logger_capture_controls'].values())
                or any(not item['passed'] for item in report['protocol'])
                or any(not item['passed'] for item in report['scenarios']) or not report.get('cache', {}).get('passed', False)
                or not report.get('resource_request_correlation', {}).get('passed', False)
                or not report.get('expiry_cache', {}).get('passed', False)
                or not report.get('role_change', {}).get('passed', False)
                or len(report['transport_faults']) != 2 or any(not row['passed'] for row in report['transport_faults'])):
            report['result_exit_code'] = 1
        # Serialize only curated receipts; fail closed if any registered secret escaped them.
        serialized = json.dumps(report, sort_keys=True, indent=2)
        all_sensitive = identity.sensitive()
        hits = sum(bool(value) and value in serialized for value in all_sensitive)
        if hits:
            report['result_exit_code'] = 1
            report['receipt_secret_hits_redacted'] = hits
            from run import redact
            report = json.loads(redact(json.dumps(report), all_sensitive))
        save(output / 'journey-result.json', report)
    return report
