"""Stdlib HTTP client for the disposable, real GeoNode identity fixture.

GeoNode 5.1.0 geonode/urls.py mounts CustomLoginView at /account/login/,
allauth at /account/, and Django OAuth Toolkit at /o/. Its login template uses
POST, csrfmiddlewaretoken and allauth's login/password fields. Endpoint paths
are configurable so source-selected toolkit routes remain the authority.

This module does not start services, provision identities, write receipts or
print credentials. Response bodies and OAuth results contain secrets IN MEMORY;
only explicit receipt()/scan_response() results are suitable for evidence.
Unit tests of this client are not GeoNode integration acceptance.
"""
import base64
from dataclasses import dataclass, field
import hashlib
from html.parser import HTMLParser
from http.cookiejar import CookieJar, DefaultCookiePolicy
from http.cookies import SimpleCookie
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request


class ProtocolError(RuntimeError):
    """Static diagnostic only: never include a response or credential value."""


class SecretRegistry:
    def __init__(self):
        self._values = set()

    def add(self, *values):
        for value in values:
            if isinstance(value, str) and value:
                self._values.update((value, urllib.parse.quote(value, safe=''),
                                     urllib.parse.quote_plus(value, safe='')))

    def matches(self, text):
        return sum(text.count(value) for value in self._values if value)

    def redact(self, text):
        for value in sorted(self._values, key=len, reverse=True):
            text = text.replace(value, '[REDACTED_FIXTURE_VALUE]')
        return text

    def sensitive_values(self):
        """Return an in-memory snapshot for the surrounding diagnostic scrubber."""
        return tuple(self._values)

    def __repr__(self):
        return '<SecretRegistry values withheld>'


@dataclass(repr=False)
class Response:
    status: int
    headers: list
    body: bytes
    url: str

    def __repr__(self):
        return '<Response status=%d body_bytes=%d headers=%d>' % (self.status, len(self.body), len(self.headers))

    def values(self, name):
        return [v for k, v in self.headers if k.lower() == name.lower()]

    def one(self, name, required=False):
        values = self.values(name)
        if len(values) > 1 or (required and len(values) != 1):
            raise ProtocolError('missing or duplicate protocol header')
        return values[0] if values else None

    def receipt(self):
        # Do not retain Location, cookies, URL queries, raw bodies or header values.
        return {'status': self.status, 'body_size': len(self.body),
                'body_sha256': hashlib.sha256(self.body).hexdigest(),
                'header_count': len(self.headers),
                'set_cookie_header_count': len(self.values('set-cookie'))}


def scan_response(response, registry):
    """Scan EVERY header occurrence; callers decide which protocol secrets are expected.

    Tokens in successful token bodies and cookies are intentional protocol output,
    so a nonzero count is not automatically an application diagnostic leak.
    """
    hits = [{'index': i, 'matches': registry.matches(k + ': ' + v)}
            for i, (k, v) in enumerate(response.headers)]
    return {'body_matches': registry.matches(response.body.decode('utf-8', errors='replace')),
            'header_matches': [row for row in hits if row['matches']],
            'header_count': len(response.headers)}


def loopback_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 or ord(c) == 127 for c in value) or '\\' in value:
        raise ProtocolError('invalid fixture URL')
    try:
        parsed = urllib.parse.urlsplit(value)
        valid = (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                 and parsed.port is not None and parsed.port > 0
                 and parsed.username is None and parsed.password is None
                 and not parsed.fragment)
    except ValueError:
        raise ProtocolError('invalid fixture URL') from None
    if not valid:
        raise ProtocolError('fixture URL must use explicit IPv4 loopback HTTP')
    return parsed


def pkce_challenge(verifier):
    if (not isinstance(verifier, str) or not 43 <= len(verifier) <= 128
            or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~' for c in verifier)):
        raise ProtocolError('invalid PKCE verifier')
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')


class _Forms(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag in ('form', 'input') and len({key for key, _ in attrs}) != len(attrs):
            raise ProtocolError('duplicate authentication element attribute')
        attrs = dict(attrs)
        if tag == 'form':
            if self.current is not None:
                raise ProtocolError('nested authentication form')
            self.current = {'action': attrs.get('action', ''), 'method': attrs.get('method', 'get').lower(), 'fields': []}
            self.forms.append(self.current)
        elif tag == 'input' and self.current is not None and 'disabled' not in attrs:
            if attrs.get('name') and attrs.get('type', 'text').lower() not in ('submit', 'button', 'checkbox', 'radio', 'file'):
                self.current['fields'].append((attrs['name'], attrs.get('value', '')))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def form_fields(response, required, action_matches=None):
    if response.status != 200:
        raise ProtocolError('authentication form response was not successful')
    parser = _Forms()
    try:
        parser.feed(response.body.decode('utf-8', errors='strict'))
    except (UnicodeError, ValueError):
        raise ProtocolError('invalid authentication form encoding') from None
    candidates = [form for form in parser.forms if set(required) <= {k for k, _ in form['fields']}
                  and (action_matches is None or action_matches(form['action']))]
    if len(candidates) != 1 or candidates[0]['method'] != 'post':
        raise ProtocolError('missing or ambiguous POST authentication form')
    form = candidates[0]
    fields = {}
    for name, value in form['fields']:
        if name in fields:
            raise ProtocolError('duplicate authentication form field')
        fields[name] = value
    if not fields.get('csrfmiddlewaretoken'):
        raise ProtocolError('missing authentication form CSRF token')
    return form['action'], fields


@dataclass(repr=False)
class AuthorizationCode:
    code: str
    verifier: str
    state: str
    redirect_uri: str

    def __repr__(self):
        return '<AuthorizationCode values withheld>'


@dataclass(repr=False)
class TokenSet:
    access_token: str
    refresh_token: str | None
    scope: str
    expires_in: int
    response: Response = field(repr=False)

    def __repr__(self):
        return '<TokenSet values withheld>'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OAuthBrowser:
    """One CookieJar per browser identity; no environment proxies or auto redirects."""
    def __init__(self, origin, client_id, redirect_uri, client_secret=None, scope='read', *,
                 login_path='/account/login/', authorize_path='/o/authorize/',
                 token_path='/o/token/', revoke_path='/o/revoke_token/', timeout=20):
        parsed = loopback_url(origin)
        if parsed.path not in ('', '/') or parsed.query:
            raise ProtocolError('identity origin must not contain a path or query')
        callback = loopback_url(redirect_uri)
        if callback.query or not callback.path:
            raise ProtocolError('fixture callback must have a path and no query')
        self.origin = origin.rstrip('/')
        self.client_id, self.client_secret = client_id, client_secret
        self.redirect_uri, self.scope, self.timeout = redirect_uri, scope, timeout
        self.login_path, self.authorize_path = login_path, authorize_path
        self.token_path, self.revoke_path = token_path, revoke_path
        for path in (login_path, authorize_path, token_path, revoke_path):
            self._local(path)
        self.secrets = SecretRegistry()
        self.secrets.add(client_secret)
        self.cookies = CookieJar(policy=DefaultCookiePolicy(strict_domain=True,
                                                            strict_ns_domain=DefaultCookiePolicy.DomainStrict))
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                        _NoRedirect(), urllib.request.HTTPCookieProcessor(self.cookies))
        self.records = []
        self.last_response = None  # Sensitive protocol output stays in memory only.

    def _local(self, target, base=None):
        if not isinstance(target, str) or any(ord(c) < 33 or ord(c) == 127 for c in target) or '\\' in target:
            raise ProtocolError('invalid fixture request target')
        value = urllib.parse.urljoin(base or self.origin + '/', target)
        parsed = loopback_url(value)
        origin = urllib.parse.urlsplit(self.origin)
        if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
            raise ProtocolError('cross-origin identity request refused')
        return value

    def request(self, method, path, *, form=None, headers=None):
        url = self._local(path)
        method = method.upper()
        role_negative_method = method in ('PUT', 'DELETE') and urllib.parse.urlsplit(url).path in ('/api/roles', '/api/adminRole', '/api/users')
        if (method not in ('GET', 'POST') and not role_negative_method) or (method == 'GET' and form is not None):
            raise ProtocolError('unsupported fixture HTTP operation')
        h = dict(headers or {})
        if any(k.lower() in ('host', 'cookie', 'proxy-authorization') for k in h):
            raise ProtocolError('caller cannot override fixture routing or cookies')
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        if data is not None:
            h['Content-Type'] = 'application/x-www-form-urlencoded'
        request = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            try:
                raw = self._opener.open(request, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                raw = error
            with raw:
                body = raw.read(2 * 1024 * 1024 + 1)
                if len(body) > 2 * 1024 * 1024:
                    raise ProtocolError('fixture response exceeds capture limit')
                response = Response(raw.status, list(raw.headers.items()), body, url)
        except ProtocolError:
            raise
        except Exception:
            raise ProtocolError('fixture HTTP transport failed') from None
        for header in response.values('set-cookie'):
            self.secrets.add(header)
            cookie = SimpleCookie()
            try:
                cookie.load(header)
                self.secrets.add(*(item.value for item in cookie.values()))
            except Exception:
                raise ProtocolError('invalid fixture cookie header') from None
        self.last_response = response
        self.records.append(dict(method=method, path=urllib.parse.urlsplit(url).path, **response.receipt()))
        return response

    def _form(self, response, required, endpoint):
        expected = urllib.parse.urlsplit(self._local(endpoint))
        def action_matches(action):
            candidate = urllib.parse.urlsplit(self._local(action or response.url, response.url))
            return candidate.path == expected.path
        action, fields = form_fields(response, required, action_matches)
        destination = self._local(action or response.url, response.url)
        actual = urllib.parse.urlsplit(destination)
        if actual.path != expected.path:
            raise ProtocolError('authentication form action changed endpoint')
        self.secrets.add(fields['csrfmiddlewaretoken'])
        return destination, fields

    def _submit_login(self, response, username, password, next_url):
        if not username or not password:
            raise ProtocolError('fixture login credentials are required')
        self.secrets.add(password)
        destination, fields = self._form(response, ('csrfmiddlewaretoken', 'login', 'password'), self.login_path)
        if next_url is not None:
            expected = self._local(next_url)
            if fields.get('next') and self._local(fields['next']) != expected:
                raise ProtocolError('login form changed authorization return target')
            fields['next'] = expected
        elif fields.get('next'):
            self._local(fields['next'])
        fields.update(login=username, password=password)
        return self.request('POST', destination, form=fields, headers={'Referer': response.url})

    def login(self, username, password, next_url=None):
        path = self.login_path
        if next_url is not None:
            path += '?' + urllib.parse.urlencode({'next': self._local(next_url)})
        response = self._submit_login(self.request('GET', path), username, password, next_url)
        if response.status not in (302, 303):
            raise ProtocolError('fixture login did not redirect successfully')
        target = self._local(response.one('location', required=True), response.url)
        if next_url is not None and target != self._local(next_url):
            raise ProtocolError('fixture login redirected to an unexpected target')
        return response

    def callback_code(self, location, state, verifier):
        parsed = loopback_url(location)
        registered = urllib.parse.urlsplit(self.redirect_uri)
        if (parsed.scheme, parsed.netloc, parsed.path) != (registered.scheme, registered.netloc, registered.path):
            raise ProtocolError('authorization callback does not match registered redirect')
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if any(len(values) != 1 for values in params.values()):
            raise ProtocolError('duplicate authorization callback parameter')
        if not secrets.compare_digest(params.get('state', [''])[0].encode('utf-8'), state.encode('utf-8')):
            raise ProtocolError('authorization callback state mismatch')
        if 'error' in params or not params.get('code', [''])[0]:
            raise ProtocolError('authorization was denied or returned no code')
        code = params['code'][0]
        self.secrets.add(code)
        return AuthorizationCode(code, verifier, state, self.redirect_uri)

    def authorize(self, username=None, password=None, *, approve=True):
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        self.secrets.add(state, verifier)
        parameters = {'client_id': self.client_id, 'response_type': 'code', 'redirect_uri': self.redirect_uri,
                      'scope': self.scope, 'state': state, 'code_challenge': pkce_challenge(verifier),
                      'code_challenge_method': 'S256'}
        authorization_url = self._local(self.authorize_path) + '?' + urllib.parse.urlencode(parameters)
        response = self.request('GET', authorization_url)
        submitted_login = submitted_consent = False
        for _ in range(8):
            if response.status in (302, 303):
                location = urllib.parse.urljoin(response.url, response.one('location', required=True))
                parsed = loopback_url(location)
                callback = urllib.parse.urlsplit(self.redirect_uri)
                if (parsed.netloc, parsed.path) == (callback.netloc, callback.path):
                    return self.callback_code(location, state, verifier)
                destination = self._local(location)
                if parsed.path not in (self.login_path, self.authorize_path):
                    raise ProtocolError('unexpected authorization redirect endpoint')
                response = self.request('GET', destination)
                continue
            path = urllib.parse.urlsplit(response.url).path
            if path == self.login_path and not submitted_login:
                response = self._submit_login(response, username, password, authorization_url)
                submitted_login = True
                continue
            if path == self.authorize_path and not submitted_consent:
                destination, fields = self._form(response, ('csrfmiddlewaretoken', 'client_id', 'state'), self.authorize_path)
                for key, expected in parameters.items():
                    if fields.get(key) != expected:
                        raise ProtocolError('consent form changed authorization parameters')
                if approve:
                    fields['allow'] = 'Authorize'
                else:
                    fields.pop('allow', None)
                response = self.request('POST', destination, form=fields, headers={'Referer': response.url})
                submitted_consent = True
                continue
            raise ProtocolError('authorization flow did not reach a valid callback')
        raise ProtocolError('authorization redirect limit exceeded')

    def _client_auth(self, form):
        form = dict(form)
        form['client_id'] = self.client_id
        headers = {}
        if self.client_secret is not None:
            # RFC 6749 client password Basic credentials use form-url-encoded components.
            value = urllib.parse.quote_plus(self.client_id) + ':' + urllib.parse.quote_plus(self.client_secret)
            basic = 'Basic ' + base64.b64encode(value.encode()).decode()
            self.secrets.add(value, basic, basic[6:])
            headers['Authorization'] = basic
        return form, headers

    def token_request(self, form):
        """Raw endpoint response permits deliberate invalid-code/PKCE integration probes."""
        for name in ('code', 'code_verifier', 'refresh_token'):
            self.secrets.add(form.get(name))
        form, headers = self._client_auth(form)
        return self.request('POST', self.token_path, form=form, headers=headers)

    def _tokens(self, response):
        if response.status != 200:
            raise ProtocolError('token endpoint rejected the fixture grant')
        try:
            def unique_pairs(pairs):
                result = {}
                for key, item in pairs:
                    if key in result:
                        raise ValueError()
                    result[key] = item
                return result
            value = json.loads(response.body, object_pairs_hook=unique_pairs)
            self.secrets.add(value.get('access_token'), value.get('refresh_token'), value.get('id_token'))
            access = value['access_token']
            refresh = value.get('refresh_token')
            expiry = value['expires_in']
            if (not isinstance(access, str) or not access or value['token_type'].lower() != 'bearer'
                    or type(expiry) is not int or expiry <= 0
                    or not isinstance(value.get('scope', ''), str)
                    or (refresh is not None and (not isinstance(refresh, str) or not refresh))):
                raise ValueError()
            self.secrets.add(access, refresh, value.get('id_token'))
            return TokenSet(access, refresh, value.get('scope', ''), expiry, response)
        except Exception:
            raise ProtocolError('invalid fixture token response') from None

    def exchange(self, authorization, verifier=None):
        if authorization.redirect_uri != self.redirect_uri:
            raise ProtocolError('authorization belongs to a different callback')
        response = self.token_request({'grant_type': 'authorization_code', 'code': authorization.code,
                        'redirect_uri': self.redirect_uri,
                        'code_verifier': authorization.verifier if verifier is None else verifier})
        return self._tokens(response)

    def refresh(self, refresh_token):
        return self._tokens(self.token_request({'grant_type': 'refresh_token', 'refresh_token': refresh_token}))

    def revoke(self, token, hint='access_token'):
        self.secrets.add(token)
        form, headers = self._client_auth({'token': token, 'token_type_hint': hint})
        return self.request('POST', self.revoke_path, form=form, headers=headers)
