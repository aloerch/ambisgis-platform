"""Client boundary tests only; fake responses never count as GeoNode acceptance."""
import base64
from email.message import Message
import hashlib
import json
import unittest
from unittest.mock import patch
import urllib.parse
import urllib.request

from protocol_probe import (AuthorizationCode, OAuthBrowser, ProtocolError, Response,
                            SecretRegistry, TokenSet, form_fields, loopback_url,
                            pkce_challenge, scan_response, _NoRedirect)

ORIGIN = 'http://127.0.0.1:8123'
CALLBACK = 'http://127.0.0.1:8124/callback'


def browser(**kwargs):
    return OAuthBrowser(ORIGIN, 'fixture-client', CALLBACK, **kwargs)


def response(body=b'', status=200, headers=(), path='/o/authorize/'):
    return Response(status, list(headers), body, ORIGIN + path)


def form(fields, action='', method='post'):
    from html import escape
    return (f'<form method="{method}" action="{escape(action, quote=True)}">' +
            ''.join(f'<input type="hidden" name="{escape(k, quote=True)}" value="{escape(v, quote=True)}">'
                    for k, v in fields) + '</form>').encode()


class RawResponse:
    def __init__(self, body=b'', status=200, headers=()):
        self.body, self.status = body, status
        self.headers = Message()
        for k, v in headers:
            self.headers[k] = v

    def read(self, size):
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class OriginTests(unittest.TestCase):
    def test_non_loopback_ambiguous_and_credential_urls_rejected(self):
        for value in ('http://localhost:8123/', 'http://127.1:8123/', 'https://127.0.0.1:8123/',
                      'http://127.0.0.1/', 'http://127.0.0.1:0/', 'http://user@127.0.0.1:8123/',
                      'http://127.0.0.1:8123/#fragment', 'http://127.0.0.1:8123/\\evil',
                      'http://127.0.0.1:8123/\nsecret'):
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                loopback_url(value)

    def test_cross_origin_request_rejected_before_transport(self):
        client = browser()
        with patch.object(client._opener, 'open') as opened:
            for path in ('http://example.com/', '//127.0.0.1:8124/path', 'http://127.0.0.1:8124/path'):
                with self.assertRaises(ProtocolError):
                    client.request('POST', path, form={'password': 'secret'})
            opened.assert_not_called()

    def test_header_routing_and_cookie_overrides_rejected(self):
        for header in ('Host', 'cOoKiE', 'Proxy-Authorization'):
            with self.subTest(header=header), self.assertRaises(ProtocolError):
                browser().request('POST', '/', headers={header: 'secret'})

    def test_urljoin_cannot_hide_control_characters(self):
        client = browser()
        with patch.object(client._opener, 'open') as opened:
            for target in ('\n/account/login/', '/account/lo\ngin/', '\t' + ORIGIN):
                with self.assertRaises(ProtocolError):
                    client.request('GET', target)
            opened.assert_not_called()

    def test_callback_not_a_request_destination(self):
        with self.assertRaises(ProtocolError):
            browser().request('GET', CALLBACK)

    def test_auto_redirect_disabled(self):
        request = urllib.request.Request(ORIGIN)
        self.assertIsNone(_NoRedirect().redirect_request(request, None, 302, '', {}, CALLBACK))

    def test_environment_proxy_is_not_used(self):
        with patch.dict('os.environ', {'http_proxy': 'http://example.com:99'}):
            client = browser()
        self.assertFalse(any(isinstance(handler, urllib.request.ProxyHandler) and handler.proxies
                             for handler in client._opener.handlers))

    def test_cookies_are_separate_per_identity(self):
        self.assertIsNot(browser().cookies, browser().cookies)


class CallbackTests(unittest.TestCase):
    def test_pkce_rfc7636_vector(self):
        self.assertEqual(pkce_challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'),
                         'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM')

    def test_pkce_rejects_short_unicode_and_bad_characters(self):
        for value in ('a' * 42, 'a' * 129, '/' * 50, 'ü' * 50):
            with self.assertRaises(ProtocolError):
                pkce_challenge(value)

    def test_callback_requires_state_and_exact_registered_target(self):
        client = browser()
        for location in (CALLBACK + '?code=secret', CALLBACK + '?code=secret&state=wrong',
                         CALLBACK + '/?code=secret&state=expected',
                         'http://127.0.0.1:9124/callback?code=secret&state=expected',
                         CALLBACK + '?code=secret&state=expected#fragment'):
            with self.subTest(location=location), self.assertRaises(ProtocolError):
                client.callback_code(location, 'expected', 'v' * 43)

    def test_duplicate_state_or_code_denied(self):
        for query in ('state=good&state=good&code=secret', 'state=good&code=a&code=b'):
            with self.assertRaises(ProtocolError):
                browser().callback_code(CALLBACK + '?' + query, 'good', 'v' * 43)

    def test_authorization_error_never_becomes_code_success(self):
        with self.assertRaises(ProtocolError):
            browser().callback_code(CALLBACK + '?code=secret&state=good&error=access_denied', 'good', 'v' * 43)

    def test_callback_code_is_memory_only_and_registered_for_scrubbing(self):
        client = browser()
        code = client.callback_code(CALLBACK + '?state=good&code=code-secret', 'good', 'v' * 43)
        self.assertEqual(code.code, 'code-secret')
        self.assertNotIn('code-secret', repr(code))
        self.assertNotIn('code-secret', client.secrets.redact('value code-secret'))


class FormTests(unittest.TestCase):
    def test_logout_selects_exact_action_among_native_csrf_forms(self):
        fields = [('csrfmiddlewaretoken', 'csrf')]
        page = response(form(fields, action='/account/login/') + form(fields, action='/account/logout/'))
        destination, selected = browser()._form(page, ('csrfmiddlewaretoken',), '/account/logout/')
        self.assertEqual(destination, ORIGIN + '/account/logout/')
        self.assertEqual(selected['csrfmiddlewaretoken'], 'csrf')

    def test_duplicate_expected_action_and_foreign_action_fail_closed(self):
        fields = [('csrfmiddlewaretoken', 'csrf')]
        for page in (form(fields, action='/account/logout/') * 2,
                     form(fields, action='http://example.com/account/logout/')):
            with self.assertRaises(ProtocolError):
                browser()._form(response(page), ('csrfmiddlewaretoken',), '/account/logout/')

    def test_csrf_and_hidden_values_html_decoded(self):
        result = response(form([('csrfmiddlewaretoken', 'token'), ('state', '<state&value>')]))
        action, fields = form_fields(result, ('state',))
        self.assertEqual(fields['state'], '<state&value>')
        self.assertEqual(action, '')

    def test_ambiguous_duplicate_missing_csrf_and_get_forms_rejected(self):
        valid = [('csrfmiddlewaretoken', 'csrf'), ('state', 'state')]
        cases = [form(valid) * 2, form(valid + [('state', 'changed')]),
                 form([('state', 'state')]), form(valid, method='get')]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ProtocolError):
                form_fields(response(body), ('state',))

    def test_ambiguous_attributes_and_invalid_encoding_are_safe_failures(self):
        for body in (b'<form method=post><input name=state name=other></form>', b'\xffsecret-password'):
            with self.assertRaises(ProtocolError) as caught:
                form_fields(response(body), ('state',))
            self.assertNotIn('secret-password', str(caught.exception))

    def test_form_action_cannot_send_credentials_off_origin(self):
        client = browser()
        body = form([('csrfmiddlewaretoken', 'csrf'), ('login', ''), ('password', '')],
                    'http://127.0.0.1:8124/steal')
        with patch.object(client, 'request') as request, self.assertRaises(ProtocolError):
            client._submit_login(response(body, path='/account/login/'), 'reader', 'secret-password', None)
        request.assert_not_called()

    def test_login_next_cannot_replace_authorization_target(self):
        client = browser()
        body = form([('csrfmiddlewaretoken', 'csrf'), ('login', ''), ('password', ''), ('next', '/other')])
        with patch.object(client, 'request') as request, self.assertRaises(ProtocolError):
            client._submit_login(response(body, path='/account/login/'), 'reader', 'secret-password', '/o/authorize/')
        request.assert_not_called()

    def test_login_submits_csrf_and_native_fields(self):
        client = browser()
        body = form([('csrfmiddlewaretoken', 'csrf-secret'), ('login', ''), ('password', '')])
        with patch.object(client, 'request', return_value=response(status=302)) as request:
            client._submit_login(response(body, path='/account/login/'), 'reader', 'password-secret', '/o/authorize/')
        args, kwargs = request.call_args
        self.assertEqual(args, ('POST', ORIGIN + '/account/login/'))
        self.assertEqual(kwargs['form']['csrfmiddlewaretoken'], 'csrf-secret')
        self.assertEqual(kwargs['form']['login'], 'reader')
        self.assertEqual(kwargs['form']['password'], 'password-secret')
        self.assertEqual(kwargs['headers']['Referer'], ORIGIN + '/account/login/')


class EvidenceTests(unittest.TestCase):
    def test_duplicate_headers_all_scanned(self):
        registry = SecretRegistry()
        registry.add('private-secret')
        value = response(b'private-secret', headers=[('X-Diagnostic', 'clean'),
            ('X-Diagnostic', 'private-secret'), ('Set-Cookie', 'private-secret')])
        scan = scan_response(value, registry)
        self.assertEqual(scan['header_count'], 3)
        self.assertEqual([row['index'] for row in scan['header_matches']], [1, 2])
        self.assertGreater(scan['body_matches'], 0)
        self.assertNotIn('private-secret', json.dumps(scan))

    def test_receipt_and_repr_never_include_body_headers_or_query(self):
        value = response(b'body-secret', headers=[('Location', '/?code=header-secret')], path='/?token=url-secret')
        self.assertNotIn('secret', json.dumps(value.receipt()))
        self.assertNotIn('secret', repr(value))
        self.assertEqual(value.receipt()['body_sha256'], hashlib.sha256(b'body-secret').hexdigest())

    def test_duplicate_location_rejected(self):
        with self.assertRaises(ProtocolError):
            response(headers=[('Location', '/a'), ('Location', '/b')]).one('location')

    def test_transport_exception_does_not_reflect_credentials(self):
        client = browser()
        with patch.object(client._opener, 'open', side_effect=RuntimeError('password-secret')):
            with self.assertRaises(ProtocolError) as caught:
                client.request('GET', '/')
        self.assertNotIn('password-secret', str(caught.exception))

    def test_response_cookies_registered_without_persisting_headers(self):
        client = browser()
        raw = RawResponse(headers=[('Set-Cookie', 'sessionid=cookie-secret; Path=/'),
                                   ('Set-Cookie', 'csrftoken=csrf-secret; Path=/')])
        with patch.object(client._opener, 'open', return_value=raw):
            value = client.request('GET', '/account/login/')
        self.assertEqual(value.receipt()['set_cookie_header_count'], 2)
        self.assertNotIn('cookie-secret', json.dumps(client.records))
        self.assertNotIn('csrf-secret', client.secrets.redact('csrf-secret'))

    def test_body_capture_is_bounded(self):
        with patch.object(browser_client := browser(), '_opener') as opener:
            opener.open.return_value = RawResponse(b'x' * (2 * 1024 * 1024 + 1))
            with self.assertRaises(ProtocolError):
                browser_client.request('GET', '/')


class GrantTests(unittest.TestCase):
    def test_token_request_preserves_bad_verifier_for_actual_negative_probe(self):
        client = browser(client_secret='client-secret')
        denied = response(b'{"error":"invalid_grant"}', status=400, path='/o/token/')
        with patch.object(client, 'request', return_value=denied) as request:
            result = client.token_request({'grant_type': 'authorization_code', 'code': 'code-secret',
                                           'code_verifier': 'deliberately-wrong'})
        self.assertEqual(result.status, 400)
        self.assertEqual(request.call_args.kwargs['form']['code_verifier'], 'deliberately-wrong')
        self.assertEqual(request.call_args.kwargs['form']['client_id'], 'fixture-client')
        self.assertTrue(request.call_args.kwargs['headers']['Authorization'].startswith('Basic '))

    def test_token_receipt_keeps_values_in_memory_only(self):
        client = browser()
        value = response(json.dumps({'access_token': 'access-secret', 'refresh_token': 'refresh-secret',
                        'expires_in': 30, 'token_type': 'Bearer', 'scope': 'read'}).encode())
        tokens = client._tokens(value)
        self.assertEqual(tokens.access_token, 'access-secret')
        self.assertNotIn('access-secret', repr(tokens))
        self.assertNotIn('refresh-secret', repr(tokens))
        self.assertNotIn('access-secret', client.secrets.redact('access-secret'))

    def test_error_or_malformed_token_response_fails_closed(self):
        for value in (response(b'{"error":"secret"}', status=400), response(b'not-json-secret'),
                      response(b'{"access_token":"secret","expires_in":true,"token_type":"Bearer"}')):
            with self.assertRaises(ProtocolError) as caught:
                browser()._tokens(value)
            self.assertNotIn('secret', str(caught.exception))

    def test_duplicate_json_token_fields_are_rejected(self):
        with self.assertRaises(ProtocolError):
            browser()._tokens(response(b'{"access_token":"first","access_token":"second","token_type":"Bearer","expires_in":60}'))

    def test_different_callback_grant_refused_before_request(self):
        client = browser()
        grant = AuthorizationCode('secret-code', 'v' * 43, 'state', 'http://127.0.0.1:99/other')
        with patch.object(client, 'token_request') as token_request, self.assertRaises(ProtocolError):
            client.exchange(grant)
        token_request.assert_not_called()

    def test_consent_parameter_tampering_refused(self):
        client = browser()
        def fake_request(method, path, **kwargs):
            params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(path).query))
            params.update(csrfmiddlewaretoken='csrf', redirect_uri='http://127.0.0.1:99/steal')
            return Response(200, [], form(list(params.items())), path)
        with patch.object(client, 'request', side_effect=fake_request) as request:
            with self.assertRaises(ProtocolError):
                client.authorize()
        self.assertEqual(request.call_count, 1)

    def test_consent_wiring_and_callback_state_using_fake_responses_only(self):
        client = browser()
        requests = []
        def fake_request(method, path, **kwargs):
            requests.append((method, path, kwargs))
            if method == 'GET':
                params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(path).query))
                params['csrfmiddlewaretoken'] = 'csrf-secret'
                return Response(200, [], form(list(params.items())), path)
            params = kwargs['form']
            self.assertEqual(params['allow'], 'Authorize')
            return Response(302, [('Location', CALLBACK + '?' + urllib.parse.urlencode(
                {'code': 'code-secret', 'state': params['state']}))], b'', path)
        with patch.object(client, 'request', side_effect=fake_request):
            grant = client.authorize()
        self.assertEqual(grant.code, 'code-secret')
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(requests[0][1]).query))
        self.assertEqual(query['code_challenge_method'], 'S256')
        self.assertEqual(query['code_challenge'], pkce_challenge(grant.verifier))
        self.assertEqual(len(requests), 2)


if __name__ == '__main__':
    unittest.main()
