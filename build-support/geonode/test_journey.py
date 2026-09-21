"""Regression tests for protocol secret-delivery classification, not GIS acceptance."""
import base64
import json
import unittest
import tempfile
from pathlib import Path

from journey import (disabled_login_evidence, response_secret_policy,
                     source_redaction_evidence, tokeninfo_secret_policy)
from protocol_probe import Response, SecretRegistry


class ResponseSecretPolicyTests(unittest.TestCase):
    def setUp(self):
        self.token = 'a-real-looking-access-value-with-unique-characters'
        self.client_secret = 'a-private-client-value-not-deliverable'
        self.registry = SecretRegistry()
        self.registry.add(self.token, self.client_secret)

    def response(self, value, headers=()):
        return Response(200, list(headers), json.dumps(value).encode(), 'http://127.0.0.1:9876/api/o/v4/tokeninfo')

    def classify(self, response, **kwargs):
        return response_secret_policy(response, self.registry, forbidden=[self.client_secret], **kwargs)

    def test_exact_requested_token_fields_and_header_are_allowed(self):
        response = self.response({'access_token': self.token, 'issued_to': 'fixture-reader'},
                                 [('Authorization', 'Bearer ' + self.token)])
        result = self.classify(response, token_fields={'access_token': self.token}, authorization_token=self.token)
        self.assertTrue(result['passed'])
        self.assertEqual(result['authorized_token_fields'], ['access_token'])

    def test_unrelated_client_secret_still_fails_positive_token_channel(self):
        response = self.response({'access_token': self.token, 'debug': self.client_secret},
                                 [('Authorization', 'Bearer ' + self.token)])
        result = self.classify(response, token_fields={'access_token': self.token}, authorization_token=self.token)
        self.assertFalse(result['passed'])
        self.assertGreater(result['forbidden_configuration_matches'], 0)

    def test_secret_cannot_be_disguised_as_authorized_token(self):
        response = self.response({'access_token': self.client_secret})
        result = self.classify(response, token_fields={'access_token': self.client_secret})
        self.assertFalse(result['passed'])

    def test_duplicate_headers_are_all_scanned(self):
        response = self.response({'access_token': self.token},
            [('X-Diagnostic', 'normal'), ('X-Diagnostic', self.client_secret),
             ('Authorization', 'Bearer ' + self.token)])
        result = self.classify(response, token_fields={'access_token': self.token}, authorization_token=self.token)
        self.assertFalse(result['passed'])
        self.assertTrue(any(h['index'] == 1 and h['name'] == 'x-diagnostic'
                            for h in result['unapproved_header_matches']))

    def test_duplicate_authorization_is_rejected(self):
        response = self.response({'access_token': self.token},
            [('Authorization', 'Bearer ' + self.token), ('Authorization', 'Bearer ' + self.token)])
        self.assertFalse(self.classify(response, token_fields={'access_token': self.token},
                                       authorization_token=self.token)['passed'])

    def test_native_cookie_delivery_on_denial_is_not_a_diagnostic_leak(self):
        cookie = 'csrftoken=csrf_value_for_this_fixture; Path=/; SameSite=Lax'
        self.registry.add(cookie, 'csrf_value_for_this_fixture')
        response = Response(401, [('Set-Cookie', cookie)], b'', 'http://127.0.0.1:9876/api/roles')
        self.assertTrue(self.classify(response)['passed'])

    def test_native_cookie_does_not_hide_private_configuration(self):
        cookie = 'sessionid=' + self.client_secret + '; Path=/'
        self.registry.add(cookie)
        response = self.response({}, [('Set-Cookie', cookie)])
        self.assertFalse(self.classify(response)['passed'])

    def test_token_outside_authorized_field_is_rejected(self):
        response = self.response({'access_token': self.token, 'debug': self.token})
        self.assertFalse(self.classify(response, token_fields={'access_token': self.token})['passed'])


class LogoutCookieTests(unittest.TestCase):
    setUp = ResponseSecretPolicyTests.setUp
    response = ResponseSecretPolicyTests.response
    classify = ResponseSecretPolicyTests.classify

    def message_cookie(self, message='You have signed out.'):
        payload = base64.urlsafe_b64encode(json.dumps([['__json_message', 0, 25, message, '']]).encode()).decode().rstrip('=')
        return 'messages=' + payload + ':fixture_timestamp:fixture_signature; Path=/; HttpOnly; SameSite=Lax'

    def test_native_logout_notice_requires_explicit_response_opt_in(self):
        cookie = self.message_cookie()
        self.registry.add(cookie, cookie.split(';')[0].split('=', 1)[1])
        response = self.response({}, [('Set-Cookie', cookie)])
        self.assertFalse(self.classify(response)['passed'])
        self.assertTrue(self.classify(response, allowed_cookie_names=('sessionid', 'csrftoken', 'messages'))['passed'])

    def test_private_or_token_content_cannot_use_logout_cookie_exemption(self):
        for value in (self.client_secret, self.token):
            for cookie in (self.message_cookie(value), 'messages=' + value + '; Path=/'):
                with self.subTest(value_kind='private-or-token', encoded=cookie.startswith('messages=W')):
                    self.registry.add(cookie)
                    self.assertFalse(self.classify(self.response({}, [('Set-Cookie', cookie)]),
                        allowed_cookie_names=('sessionid', 'csrftoken', 'messages'))['passed'])

    def test_duplicate_messages_and_unrelated_diagnostic_headers_still_fail(self):
        cookie = self.message_cookie()
        self.registry.add(cookie)
        for headers in ([('Set-Cookie', cookie), ('Set-Cookie', cookie)],
                        [('Set-Cookie', cookie), ('X-Diagnostic', self.token)]):
            self.assertFalse(self.classify(self.response({}, headers),
                allowed_cookie_names=('sessionid', 'csrftoken', 'messages'))['passed'])


class StrictTokenInfoPolicyTests(unittest.TestCase):
    def setUp(self):
        self.token = 'unique-opaque-fixture-bearer-value'
        self.registry = SecretRegistry()
        self.registry.add(self.token)

    def response(self, value, headers=()):
        return Response(200, list(headers), json.dumps(value).encode(), 'http://127.0.0.1:9876/api/o/v4/tokeninfo')

    def test_strict_native_response_omits_bearer_material(self):
        result = tokeninfo_secret_policy(self.response({'issued_to': 'fixture-reader', 'expires_in': 5000}),
                                        self.registry, self.token, strict=True)
        self.assertTrue(result['passed'])
        self.assertTrue(result['strict_token_omission'])

    def test_strict_profile_rejects_legacy_token_echo(self):
        response = self.response({'access_token': self.token}, [('Authorization', 'Bearer ' + self.token)])
        self.assertFalse(tokeninfo_secret_policy(response, self.registry, self.token, strict=True)['passed'])
        self.assertTrue(tokeninfo_secret_policy(response, self.registry, self.token, strict=False)['passed'])

    def test_source_redaction_counter_is_not_hidden_by_scrubbed_text(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'initial.log', Path(directory) / 'restart.log'
            first.write_text(json.dumps({'message': '[REDACTED]', 'source_diagnostic_redactions': 2}) + '\n')
            second.write_text(json.dumps({'message': 'control', 'source_diagnostic_redactions': 0}) + '\n')
            result = source_redaction_evidence([first, second])
            self.assertEqual(result['source_diagnostic_redactions'], 2)
            self.assertEqual(len(result['logs']), 2)

    def test_malformed_source_counter_cannot_report_zero_leaks(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'source.log'
            log.write_text(json.dumps({'source_diagnostic_redactions': '0'}) + '\n')
            self.assertEqual(source_redaction_evidence([log])['invalid_counter_records'], 1)


class NativeDisabledLoginTests(unittest.TestCase):
    def test_only_native_receipt_exact_same_origin_redirect_passes(self):
        origin = 'http://127.0.0.1:9876'
        requests = [{'method': 'POST', 'path': '/account/login/', 'status': 302}]
        provisioning = {'disabled_login_redirect_path': '/account/moderation_sent/6/'}
        def outcome(location, status=302):
            response = Response(status, [('Location', location)], b'', origin + '/account/login/')
            return disabled_login_evidence(response, requests, origin, provisioning)['passed']
        self.assertTrue(outcome('/account/moderation_sent/6/'))
        self.assertFalse(outcome('/account/moderation_sent/7/'))
        self.assertFalse(outcome('https://other.example/account/moderation_sent/6/'))
        self.assertFalse(outcome('/account/moderation_sent/6/?next=anything'))
        self.assertFalse(outcome('/account/moderation_sent/6/', 200))
        self.assertFalse(disabled_login_evidence(None, requests, origin, provisioning)['passed'])

    def test_missing_native_receipt_cannot_accept_any_redirect(self):
        response = Response(302, [('Location', '/account/moderation_sent/6/')], b'',
                            'http://127.0.0.1:9876/account/login/')
        result = disabled_login_evidence(response,
            [{'method': 'POST', 'path': '/account/login/', 'status': 302}], 'http://127.0.0.1:9876', {})
        self.assertFalse(result['passed'])


class SourceCounterTests(unittest.TestCase):
    def test_credential_and_private_key_redactions_gate_even_if_text_is_clean(self):
        for field in ('source_credential_field_redactions', 'source_private_key_redactions'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                log = Path(directory) / 'source.log'
                log.write_text(json.dumps({field: 1, 'message': '[REDACTED]'}) + '\n')
                result = source_redaction_evidence([log])
                self.assertEqual(result[field], 1)
                self.assertFalse(result['passed'])

    def test_opaque_identifier_candidates_report_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'source.log'
            log.write_text(json.dumps({'source_opaque_value_redactions': 3}) + '\n')
            result = source_redaction_evidence([log])
            self.assertEqual(result['source_opaque_value_redactions'], 3)
            self.assertTrue(result['passed'])


if __name__ == '__main__':
    unittest.main()
