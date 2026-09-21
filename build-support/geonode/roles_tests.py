"""Native Django/ORM role-service regressions, included in the rebuilt wheel.

Run geonode.api.test_backend_roles.StrictBackendRolesTests against the complete
native application and disposable PostgreSQL catalog; no authorization mocks.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase, override_settings
from oauth2_provider.models import get_application_model


@override_settings(OAUTH2_ROLE_SERVICE_STRICT=True,
                   OAUTH2_ROLE_SERVICE_USERNAME='native-role-service',
                   OAUTH2_ROLE_SERVICE_API_KEY='native-separate-role-key',
                   OAUTH2_API_KEY='native-legacy-api-key')
class StrictBackendRolesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Application = get_application_model()
        Application.objects.get_or_create(name=settings.OAUTH2_DEFAULT_BACKEND_CLIENT_NAME, defaults={
            'client_id': 'native-roles-signal-client', 'client_secret': 'native-roles-signal-secret',
            'client_type': Application.CLIENT_CONFIDENTIAL,
            'authorization_grant_type': Application.GRANT_AUTHORIZATION_CODE,
            'redirect_uris': 'http://127.0.0.1:19999/callback', 'skip_authorization': False})
        User = get_user_model()
        cls.service = User.objects.create_user('native-role-service', 'native-service@example.invalid')
        cls.service.set_unusable_password()
        cls.service.save(update_fields=['password'])
        cls.permissions = [Permission.objects.get(content_type__app_label=app, codename=code)
                           for app, code in (('people', 'view_profile'), ('auth', 'view_group'))]
        cls.service.user_permissions.set(cls.permissions)
        cls.reader = User.objects.create_user('native-role-reader', 'native-reader@example.invalid', 'native-password')
        cls.outsider = User.objects.create_user('native-role-outsider', 'native-outsider@example.invalid', 'native-password')
        cls.admin = User.objects.create_superuser('native-role-admin', 'native-admin@example.invalid', 'native-password')
        for user in (cls.service, cls.reader, cls.outsider, cls.admin):
            user.groups.clear()
        cls.group = Group.objects.create(name='native-readers')
        cls.reader.groups.add(cls.group)

    def setUp(self):
        self.http = Client(enforce_csrf_checks=True, HTTP_HOST='127.0.0.1')

    def get(self, path='/api/users/native-role-reader', auth='ApiKey native-separate-role-key'):
        return self.http.get(path, HTTP_AUTHORIZATION=auth)

    def assert_denied(self, response, status=401):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertNotIn('native-separate-role-key', response.content.decode())
        self.assertNotIn('Authorization', response)

    def assert_browser_state(self, before):
        # Native maintenance/read-only middleware caches harmless configuration
        # in every request session. This endpoint must not change identity,
        # OAuth/session token data or any other existing browser state.
        after = dict(self.http.session)
        self.assertEqual(set(after.get('config', {})), {'configuration', 'expiration'})
        self.assertEqual(after['config']['configuration'], {'read_only': False, 'maintenance': False})
        self.assertIsInstance(after['config']['expiration'], str)
        self.assertTrue({key: value for key, value in after.items() if key != 'config'} ==
                        {key: value for key, value in before.items() if key != 'config'},
                        'Role lookup changed browser state beyond native configuration cache')

    def groups(self, username='native-role-reader'):
        response = self.get('/api/users/' + username)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['users']), 1)
        self.assertEqual(response.json()['users'][0]['username'], username)
        return response.json()['users'][0]['groups']

    def test_minimum_service_permissions_read_actual_membership(self):
        self.assertFalse(self.service.is_staff)
        self.assertFalse(self.service.is_superuser)
        self.assertFalse(self.service.has_usable_password())
        self.assertIn('native-readers', self.groups())

    def test_roles_and_admin_payloads_use_selected_contract(self):
        self.assertIn('native-readers', self.get('/api/roles').json()['groups'])
        self.assertEqual(self.get('/api/adminRole').json(), {'adminRole': 'admin'})

    def test_missing_key_denied(self):
        self.assert_denied(self.get(auth=''))

    def test_wrong_key_denied(self):
        self.assert_denied(self.get(auth='ApiKey wrong-key'))

    def test_legacy_global_key_cannot_read_strict_roles(self):
        self.assert_denied(self.get(auth='ApiKey native-legacy-api-key'))

    def test_malformed_and_other_authentication_schemes_denied(self):
        for auth in ('Basic malformed:secret', 'Bearer native-separate-role-key',
                     'ApiKey  native-separate-role-key', 'ApiKey native-separate-role-key extra', 'ApiKey'):
            with self.subTest(scheme=auth.split()[0]):
                self.assert_denied(self.get(auth=auth))

    @override_settings(OAUTH2_ROLE_SERVICE_API_KEY='')
    def test_empty_key_never_opens_endpoint(self):
        self.assert_denied(self.get(auth=''))

    @override_settings(OAUTH2_ROLE_SERVICE_API_KEY='rotated-native-role-key')
    def test_revoked_key_denied_and_new_key_recovers(self):
        self.assert_denied(self.get())
        self.assertEqual(self.get(auth='ApiKey rotated-native-role-key').status_code, 200)

    @override_settings(OAUTH2_ROLE_SERVICE_USERNAME='unknown-role-service')
    def test_missing_service_identity_denied(self):
        self.assert_denied(self.get())

    def test_inactive_service_identity_denied(self):
        self.service.is_active = False
        self.service.save(update_fields=['is_active'])
        self.assert_denied(self.get())

    def test_staff_service_identity_denied(self):
        self.service.is_staff = True
        self.service.save(update_fields=['is_staff'])
        self.assert_denied(self.get())

    def test_superuser_service_identity_denied(self):
        self.service.is_superuser = True
        self.service.save(update_fields=['is_superuser'])
        self.assert_denied(self.get())

    def test_each_read_permission_is_required(self):
        for permission in self.permissions:
            with self.subTest(permission=permission.codename):
                self.service.user_permissions.remove(permission)
                self.assert_denied(self.get())
                self.service.user_permissions.add(permission)
                self.assertEqual(self.get().status_code, 200)

    def test_permission_revocation_not_hidden_by_prior_lookup(self):
        self.assertEqual(self.get().status_code, 200)
        self.service.user_permissions.clear()
        self.assert_denied(self.get())

    def test_ordinary_session_cannot_read_without_key(self):
        self.http.force_login(self.reader)
        self.assert_denied(self.get(auth=''))

    def test_admin_session_cannot_bypass_wrong_key(self):
        self.http.force_login(self.admin)
        session_before = dict(self.http.session)
        self.assert_denied(self.get(auth='ApiKey wrong-key'))
        self.assert_browser_state(session_before)

    def test_valid_service_request_preserves_browser_session(self):
        self.http.force_login(self.reader)
        before = dict(self.http.session)
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assert_browser_state(before)

    def test_only_get_supported_and_does_not_mutate_membership(self):
        before = set(self.reader.groups.values_list('pk', flat=True))
        for method in ('post', 'put', 'patch', 'delete'):
            response = getattr(self.http, method)('/api/users/native-role-reader',
                data='{"groups":["admin"]}', content_type='application/json',
                HTTP_AUTHORIZATION='ApiKey native-separate-role-key')
            self.assert_denied(response, 405)
            self.assertEqual(response['Allow'], 'GET')
        self.assertEqual(set(self.reader.groups.values_list('pk', flat=True)), before)

    def test_unknown_and_inactive_users_have_no_roles(self):
        self.assertEqual(self.get('/api/users/no-such-role-identity').json(), {'users': []})
        self.reader.is_active = False
        self.reader.save(update_fields=['is_active'])
        self.assertEqual(self.get().json(), {'users': []})
        self.assertNotIn(self.reader.username, [entry['username'] for entry in self.get('/api/users').json()['users']])

    def test_email_is_not_username_alias(self):
        self.assertEqual(self.get('/api/users/native-reader@example.invalid').json(), {'users': []})

    def test_email_collision_cannot_acquire_another_identity_roles(self):
        self.outsider.email = 'missing-username'
        self.outsider.save(update_fields=['email'])
        self.assertEqual(self.get('/api/users/missing-username').json(), {'users': []})
        self.outsider.email = self.reader.username
        self.outsider.save(update_fields=['email'])
        self.assertIn('native-readers', self.groups())
        self.assertNotIn('native-readers', self.groups('native-role-outsider'))

    def test_case_distinct_usernames_do_not_merge(self):
        User = get_user_model()
        User.objects.create_user('NATIVE-role-reader', 'case-distinct@example.invalid')
        self.assertNotIn('native-readers', self.groups('NATIVE-role-reader'))
        self.assertIn('native-readers', self.groups())

    def test_reserved_user_name_users_is_exact_identity(self):
        get_user_model().objects.create_user('users', 'reserved-users@example.invalid')
        response = self.get('/api/users/users')
        self.assertEqual([entry['username'] for entry in response.json()['users']], ['users'])

    def test_unsafe_username_and_prefix_paths_rejected(self):
        for path, status in (('/api/users/native-role-reader/extra', 400),
                             ('/api/users/native%27reader', 400), ('/api/usersXYZ', 404),
                             ('/api/rolesXYZ', 404), ('/api/adminRoleXYZ', 404)):
            with self.subTest(path=path):
                self.assert_denied(self.get(path), status)

    def test_query_roles_cannot_supply_authority(self):
        self.assert_denied(self.get('/api/users/native-role-outsider?groups=admin'), 400)

    def test_reserved_and_normalization_alias_groups_cannot_grant_admin(self):
        names = ('admin', 'ADMIN', 'administrator', 'group_admin', 'group-admin', 'role_admin',
                 'role_administrator', 'ROLE_ADMINISTRATOR', 'authenticated', 'anonymous',
                 'any', 'root', ' native-readers', 'NATIVE-READERS', 'native readers')
        for name in names:
            group, _ = Group.objects.get_or_create(name=name)
            self.outsider.groups.add(group)
        self.assertEqual(self.groups('native-role-outsider'), [])
        listed = self.get('/api/roles').json()['groups']
        self.assertEqual(listed.count('admin'), 1)
        self.assertFalse(set(names).difference({'admin'}).intersection(listed))

    def test_group_removal_and_restore_are_immediate_in_native_response(self):
        self.assertIn('native-readers', self.groups())
        self.reader.groups.remove(self.group)
        self.assertNotIn('native-readers', self.groups())
        self.reader.groups.add(self.group)
        self.assertIn('native-readers', self.groups())

    def test_only_active_superuser_receives_synthetic_admin(self):
        self.assertIn('admin', self.groups('native-role-admin'))
        self.admin.is_superuser = False
        self.admin.save(update_fields=['is_superuser'])
        self.assertNotIn('admin', self.groups('native-role-admin'))

    def test_staff_user_does_not_receive_admin(self):
        self.outsider.is_staff = True
        self.outsider.save(update_fields=['is_staff'])
        self.assertNotIn('admin', self.groups('native-role-outsider'))

    def test_success_responses_are_uncached_and_token_free(self):
        for path in ('/api/users', '/api/users/native-role-reader', '/api/roles', '/api/adminRole'):
            response = self.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Cache-Control'], 'no-store')
            self.assertEqual(response['Pragma'], 'no-cache')
            self.assertNotIn('native-separate-role-key', response.content.decode())
            self.assertNotIn('access_token', response.json())

    @override_settings(OAUTH2_ROLE_SERVICE_STRICT=False)
    def test_default_off_preserves_inherited_key_and_payload(self):
        self.assertEqual(self.get(auth='ApiKey native-legacy-api-key').status_code, 200)
        self.assertEqual(self.get('/api/adminRole', auth='ApiKey native-legacy-api-key').json(), {'adminRole': 'admin'})

    def test_middleware_scope_matches_only_actual_three_callbacks(self):
        from geonode.api.backend_roles import is_strict_role_request
        from django.test import RequestFactory
        for path in ('/api/roles', '/api/users/native-role-reader', '/api/adminRole'):
            self.assertTrue(is_strict_role_request(RequestFactory().get(path)))
        for path in ('/o/tokeninfo/', '/account/login/', '/no-native-view'):
            self.assertFalse(is_strict_role_request(RequestFactory().get(path)))
