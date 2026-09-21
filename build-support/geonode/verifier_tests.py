"""Native ORM/HTTP regressions copied into the repaired source distribution.

Run as geonode.api.test_backend_tokeninfo.StrictBackendTokenInfoTests with the
complete GeoNode application and a disposable migrated PostgreSQL database.
No security decision, user model, token store, view or middleware is mocked.
"""
import base64
from datetime import timedelta
import logging
from urllib.parse import quote_plus

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model


@override_settings(OAUTH2_BACKEND_TOKENINFO_STRICT=True)
class StrictBackendTokenInfoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Application = get_application_model()
        cls.primary_secret = 'native-primary-secret-with-sufficient-length'
        cls.secondary_secret = 'native-secondary-secret-with-sufficient-length'
        cls.primary = Application.objects.create(
            name='Native strict primary backend client',
            client_id='native-primary-client', client_secret=cls.primary_secret,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris='http://127.0.0.1:19999/callback', skip_authorization=False)
        cls.secondary = Application.objects.create(
            name='Native secondary backend client', client_id='native-secondary-client',
            client_secret=cls.secondary_secret, client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris='http://127.0.0.1:19999/callback', skip_authorization=False)
        cls.public = Application.objects.create(
            name='Native public client', client_id='native-public-client',
            client_secret='native-public-secret', client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris='http://127.0.0.1:19999/callback', skip_authorization=False)
        Application.objects.get_or_create(name=settings.OAUTH2_DEFAULT_BACKEND_CLIENT_NAME, defaults={
            'client_id': 'native-signal-support-client', 'client_secret': 'native-signal-support-secret',
            'client_type': Application.CLIENT_CONFIDENTIAL, 'authorization_grant_type': Application.GRANT_AUTHORIZATION_CODE,
            'redirect_uris': 'http://127.0.0.1:19999/callback', 'skip_authorization': False})
        User = get_user_model()
        cls.reader = User.objects.create_user('strict-native-reader', 'strict-reader@example.invalid', 'native-user-password')
        cls.outsider = User.objects.create_user('strict-native-outsider', 'strict-outsider@example.invalid', 'native-user-password')
        cls.admin = User.objects.create_superuser('strict-native-admin', 'strict-admin@example.invalid', 'native-admin-password')

    def setUp(self):
        self.endpoint = reverse('tokeninfo')
        self.http = Client(enforce_csrf_checks=True, HTTP_HOST='127.0.0.1')
        self.token = self.make_token()

    def make_token(self, user=None, application=None, value='native-access-token-witness', expires=None):
        return get_access_token_model().objects.create(
            user=self.reader if user is None else user,
            application=self.primary if application is None else application,
            token=value, expires=expires or timezone.now() + timedelta(seconds=120), scope='read')

    def auth(self, application=None, secret=None):
        app = self.primary if application is None else application
        value = quote_plus(app.client_id) + ':' + quote_plus(app.client_secret if secret is None else secret)
        return 'Basic ' + base64.b64encode(value.encode()).decode()

    def post(self, token=None, authorization=None, http=None, data=None):
        return (http or self.http).post(self.endpoint,
            data={'token': self.token.token if token is None else token} if data is None else data,
            HTTP_AUTHORIZATION=self.auth() if authorization is None else authorization)

    def assert_denied(self, response, status=403):
        self.assertEqual(response.status_code, status)
        self.assertNotIn(self.token.token, response.content.decode())
        self.assertNotIn(self.primary_secret, response.content.decode())
        self.assertNotIn('Authorization', response)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Pragma'], 'no-cache')

    def test_confidential_client_own_active_token_succeeds(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['client_id'], self.primary.client_id)
        self.assertEqual(response.json()['issued_to'], self.reader.username)
        self.assertEqual(response.json()['scope'], 'read')

    def test_response_has_no_token_or_authorization_header(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('access_token', response.json())
        self.assertNotIn(self.token.token, response.content.decode())
        self.assertNotIn('Authorization', response)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Pragma'], 'no-cache')

    def test_expiry_is_remaining_milliseconds(self):
        response = self.post()
        remaining = response.json()['expires_in']
        self.assertGreater(remaining, 100000)
        self.assertLessEqual(remaining, 120000)
        self.assertIsInstance(remaining, int)

    def test_missing_client_authentication_denied(self):
        self.assert_denied(self.post(authorization=''), 401)

    def test_wrong_client_secret_denied(self):
        self.assert_denied(self.post(authorization=self.auth(secret='wrong-secret')), 401)

    def test_unknown_client_denied_without_reflection(self):
        auth = 'Basic ' + base64.b64encode(b'unknown-native-client:private-secret').decode()
        response = self.post(authorization=auth)
        self.assert_denied(response, 401)
        self.assertNotIn('unknown-native-client', response.content.decode())
        self.assertNotIn('private-secret', response.content.decode())

    def test_malformed_basic_encodings_are_uniform_and_secret_free(self):
        for auth in ('Basic not*base64', 'Basic ' + base64.b64encode(b'no-colon').decode(),
                     'Basic ' + base64.b64encode(b'\xff:bad').decode(), 'Basic ', 'Bearer witness',
                     self.auth() + ',' + self.auth()):
            with self.subTest(auth_kind=auth.split(' ', 1)[0]):
                self.assert_denied(self.post(authorization=auth), 401)

    def test_empty_secret_rejected_even_if_application_stores_empty(self):
        self.primary.client_secret = ''
        self.primary.save(update_fields=['client_secret'])
        self.assert_denied(self.post(authorization=self.auth()), 401)

    def test_public_client_cannot_introspect(self):
        token = self.make_token(application=self.public, value='native-public-token')
        self.assert_denied(self.post(token.token, self.auth(self.public)), 401)

    def test_body_client_credentials_do_not_replace_basic(self):
        self.assert_denied(self.post(authorization='', data={'token': self.token.token,
            'client_id': self.primary.client_id, 'client_secret': self.primary_secret}), 401)

    def test_wrong_basic_does_not_fall_back_to_valid_body_credentials(self):
        self.assert_denied(self.post(authorization=self.auth(secret='wrong-secret'),
            data={'token': self.token.token, 'client_id': self.primary.client_id,
                  'client_secret': self.primary_secret}), 401)

    def test_second_application_token_denied_to_primary_client(self):
        token = self.make_token(application=self.secondary, value='native-secondary-token')
        self.assert_denied(self.post(token.token))

    def test_primary_application_token_denied_to_second_client(self):
        self.assert_denied(self.post(authorization=self.auth(self.secondary)))

    def test_second_client_own_token_has_positive_control(self):
        token = self.make_token(application=self.secondary, value='native-secondary-token')
        response = self.post(token.token, self.auth(self.secondary))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['client_id'], self.secondary.client_id)

    def test_duplicate_token_values_rejected(self):
        self.assert_denied(self.post(data={'token': [self.token.token, 'other-native-token']}), 400)

    def test_empty_missing_and_oversized_token_values_rejected(self):
        for data in ({}, {'token': ''}, {'token': 'x' * 256}):
            with self.subTest(kind='missing' if not data else 'present'):
                self.assert_denied(self.post(data=data), 400)

    def test_get_query_token_rejected(self):
        self.assert_denied(self.http.get(self.endpoint, {'token': self.token.token}, HTTP_AUTHORIZATION=self.auth()), 405)

    def test_expired_token_denied(self):
        self.token.expires = timezone.now() - timedelta(seconds=1)
        self.token.save(update_fields=['expires'])
        self.assert_denied(self.post())

    def test_revoked_token_denied(self):
        value = self.token.token
        self.token.revoke()
        self.assert_denied(self.post(value))

    def test_inactive_user_denied_after_prior_success(self):
        self.assertEqual(self.post().status_code, 200)
        self.reader.is_active = False
        self.reader.save(update_fields=['is_active'])
        self.assert_denied(self.post())

    def test_deleted_user_and_cascaded_token_denied(self):
        value = self.token.token
        self.reader.delete()
        self.assert_denied(self.post(value))

    def test_token_without_user_denied(self):
        self.token.user = None
        self.token.save(update_fields=['user'])
        self.assert_denied(self.post())

    def test_blank_principal_denied(self):
        self.reader.username = '   '
        self.reader.save(update_fields=['username'])
        self.assert_denied(self.post())

    def test_reader_session_does_not_authenticate_client(self):
        self.http.force_login(self.reader)
        self.assert_denied(self.post(authorization=''), 401)

    def test_administrator_session_does_not_authenticate_client(self):
        self.http.force_login(self.admin)
        self.assert_denied(self.post(authorization=''), 401)

    def test_session_token_cannot_replace_posted_other_user_token(self):
        self.http.force_login(self.reader)
        session = self.http.session
        session['access_token'] = self.token.token
        session.save()
        token = self.make_token(user=self.outsider, value='native-outsider-token')
        response = self.post(token.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['issued_to'], self.outsider.username)
        self.assertEqual(self.http.session['access_token'], self.token.token)

    def test_valid_browser_session_cannot_replace_invalid_posted_token(self):
        self.http.force_login(self.reader)
        session = self.http.session
        session['access_token'] = self.token.token
        session.save()
        self.assert_denied(self.post('nonexistent-native-token'))
        self.assertEqual(self.http.session['access_token'], self.token.token)

    def test_expired_browser_token_does_not_flush_context_for_backend_verification(self):
        self.http.force_login(self.reader)
        self.token.expires = timezone.now() - timedelta(seconds=1)
        self.token.save(update_fields=['expires'])
        session = self.http.session
        session['access_token'] = self.token.token
        session.save()
        original_cookie = self.http.cookies[settings.SESSION_COOKIE_NAME].value
        other = self.make_token(user=self.outsider, value='native-active-other-token')
        response = self.post(other.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['issued_to'], self.outsider.username)
        self.assertEqual(self.http.session['_auth_user_id'], str(self.reader.pk))
        self.assertEqual(self.http.session['access_token'], self.token.token)
        self.assertEqual(self.http.cookies[settings.SESSION_COOKIE_NAME].value, original_cookie)

    def test_ordinary_user_basic_authentication_still_runs_outside_tokeninfo(self):
        value = self.reader.username + ':native-user-password'
        authorization = 'Basic ' + base64.b64encode(value.encode()).decode()
        response = self.http.get(reverse('userinfo'), HTTP_AUTHORIZATION=authorization)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sub'], str(self.reader.pk))

    def test_invalid_client_does_not_flush_expired_browser_context(self):
        self.http.force_login(self.reader)
        self.token.expires = timezone.now() - timedelta(seconds=1)
        self.token.save(update_fields=['expires'])
        session = self.http.session
        session['access_token'] = self.token.token
        session.save()
        original_cookie = self.http.cookies[settings.SESSION_COOKIE_NAME].value
        self.assert_denied(self.post(authorization=self.auth(secret='invalid-client-secret')), 401)
        self.assertEqual(self.http.session['_auth_user_id'], str(self.reader.pk))
        self.assertEqual(self.http.session['access_token'], self.token.token)
        self.assertEqual(self.http.cookies[settings.SESSION_COOKIE_NAME].value, original_cookie)

    def test_strict_guard_does_not_cover_other_views(self):
        from django.test import RequestFactory
        from geonode.api.backend_tokeninfo import is_strict_backend_request
        factory = RequestFactory()
        self.assertTrue(is_strict_backend_request(factory.post(self.endpoint)))
        self.assertFalse(is_strict_backend_request(factory.get(reverse('userinfo'))))
        self.assertFalse(is_strict_backend_request(factory.get('/native-route-does-not-exist')))
        with override_settings(OAUTH2_BACKEND_TOKENINFO_STRICT=False):
            self.assertFalse(is_strict_backend_request(factory.post(self.endpoint)))

    def test_credential_components_form_url_decoded(self):
        self.secondary.client_id = 'native+client space'
        self.secondary.client_secret = 'native+secret:colon space'
        self.secondary.save(update_fields=['client_id', 'client_secret'])
        token = self.make_token(application=self.secondary, value='native-encoding-token')
        response = self.post(token.token, self.auth(self.secondary))
        self.assertEqual(response.status_code, 200)

    def test_debug_logger_control_has_no_credential_reflection(self):
        logger = logging.getLogger('geonode.api.backend_tokeninfo')
        with self.assertLogs(logger, level='DEBUG') as captured:
            logger.debug('AMBISGIS_STRICT_VERIFIER_NATIVE_LOG_CONTROL')
            self.assert_denied(self.post(authorization=self.auth(secret='wrong-private-secret')), 401)
            self.assert_denied(self.post('invalid-private-token'))
        text = '\n'.join(captured.output)
        self.assertEqual(text.count('AMBISGIS_STRICT_VERIFIER_NATIVE_LOG_CONTROL'), 1)
        for value in (self.token.token, self.primary_secret, 'wrong-private-secret', 'invalid-private-token'):
            self.assertNotIn(value, text)

    @override_settings(OAUTH2_BACKEND_TOKENINFO_STRICT=False)
    def test_default_compatibility_branch_preserves_native_tokeninfo_response(self):
        response = self.http.post(self.endpoint, {'token': self.token.token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['access_token'], self.token.token)
        self.assertEqual(response.json()['user_id'], self.reader.pk)
