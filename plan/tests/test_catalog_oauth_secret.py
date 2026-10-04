"""Exercise actual initialize control flow with synthetic model collaborators.

No Django setup, ORM, database, native libraries or network are executed. The
separate retained-source witness supplies the selected native comparison code.
"""
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import hmac
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/development'))
from ambisgis_development import catalog, startup_diagnostics


class BootstrapFixture:
    def __init__(self, path, *, new_app=False):
        self.data = Path(path)
        self.product = {'install_id': '1927f2e7-9f44-45a6-b430-20317f087fee',
                        'public_origin': 'http://127.0.0.1:9000', 'owner': 'owner', 'viewer': 'viewer'}
        self.secrets = {'oauth_client': 'C' * 64, 'oauth_secret': 'S' * 64,
                        'owner_password': 'O' * 64, 'viewer_password': 'V' * 64, 'health_token': 'T' * 64}
        marker = {'schema_version': 1, 'install_id': self.product['install_id'], 'purpose': 'developer-catalog'}
        (self.data / 'installation.json').write_text(json.dumps(marker))
        (self.data / 'installation.json').chmod(0o600)
        (self.data / 'oidc-key.pem').write_text('synthetic-existing-key')
        (self.data / 'oidc-key.pem').chmod(0o600)
        self.calls = []
        self.tx = []
        self.users = {}
        for pk, name in enumerate(('owner', 'viewer', 'installation-health'), 1):
            self.users[name] = SimpleNamespace(pk=pk, is_staff=False, is_superuser=False,
                has_usable_password=lambda: False, set_password=Mock(), save=Mock())
        self.app = SimpleNamespace(pk=7, user_id=None if new_app else 1,
            name='AmbisGIS development', client_secret=self.secrets['oauth_secret'],
            client_type='confidential', authorization_grant_type='authorization-code',
            redirect_uris=self.product['public_origin'] + '/oauth/callback', skip_authorization=False)
        def save_app(**kwargs):
            self.calls.append(('app_save', kwargs))
            self.app.user_id = self.app.user.pk
        self.app.save = save_app
        self.new_app = new_app
        self.defaults = None
        def get_app(**kwargs):
            self.calls.append(('app_get', kwargs['client_id']))
            self.defaults = kwargs['defaults']
            if self.new_app:
                for key, value in self.defaults.items(): setattr(self.app, key, value)
                self.new_app = False
                return self.app, True
            return self.app, False
        self.Application = SimpleNamespace(CLIENT_CONFIDENTIAL='confidential', GRANT_AUTHORIZATION_CODE='authorization-code',
            objects=SimpleNamespace(get_or_create=get_app))
        def get_user(**kwargs):
            self.calls.append(('user_get', kwargs['username']))
            return self.users[kwargs['username']], False
        self.User = SimpleNamespace(objects=SimpleNamespace(get_or_create=get_user))
        self.resource = SimpleNamespace(alternate=catalog.SAMPLE, owner_id=1, pk=11, title='Retained edited title')
        self.Resource = SimpleNamespace(objects=SimpleNamespace(
            get_or_create=lambda **kw: (self.resource, False),
            filter=lambda **kw: SimpleNamespace(count=lambda: 1)))
        self.token = SimpleNamespace(user_id=3, application_id=7, scope='read')
        self.Token = SimpleNamespace(objects=SimpleNamespace(get_or_create=lambda **kw: (self.token, False)))
        class Cursor:
            def __enter__(inner): return inner
            def __exit__(inner, *exc): return False
            def execute(inner, sql, args): self.calls.append(('sql', sql, args))
            def fetchone(inner): return (True,)
        self.connection = SimpleNamespace(cursor=Cursor)
        @contextmanager
        def atomic():
            self.tx.append('enter')
            try: yield
            except BaseException:
                self.tx.append('rollback_requested'); raise
            else: self.tx.append('commit_requested')
        self.commands = []
        self.compare_calls = []
        def compare(a, b):
            self.compare_calls.append((a, b))
            return hmac.compare_digest(a, b)
        self.compare = compare
        # Baseline-only stand-in: the separate source-pinned witness executes
        # the actual retained Django password-checker functions.
        self.password_check = lambda raw, stored: False
        forbidden = Mock(side_effect=AssertionError('unexpected synthetic model operation'))
        self.attrs = {
            'django.core.management': {'call_command': lambda name, **kw: self.commands.append(name)},
            'django.db': {'connection': self.connection, 'transaction': SimpleNamespace(atomic=atomic)},
            'django.contrib.auth': {'get_user_model': lambda: self.User},
            'django.contrib.auth.hashers': {'check_password': lambda a, b: self.password_check(a, b)},
            'django.utils.crypto': {'constant_time_compare': lambda a, b: self.compare(a, b)},
            'django.contrib.contenttypes.models': {'ContentType': forbidden},
            'django.contrib.sites.models': {'Site': SimpleNamespace(objects=SimpleNamespace(update_or_create=Mock()))},
            'django.utils': {'timezone': SimpleNamespace(now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))},
            'allauth.account.models': {'EmailAddress': forbidden},
            'geonode.base.models': {'ResourceBase': self.Resource},
            'guardian.models': {'UserObjectPermission': forbidden, 'GroupObjectPermission': forbidden},
            'guardian.shortcuts': {'assign_perm': forbidden},
            'oauth2_provider.models': {'get_application_model': lambda: self.Application, 'get_access_token_model': lambda: self.Token},
        }

    def run(self):
        modules = {}
        for name, attrs in self.attrs.items():
            mod = ModuleType(name)
            mod.__dict__.update(attrs)
            modules[name] = mod
        with patch.dict(sys.modules, modules), patch.object(catalog, 'DATA', self.data), patch.object(catalog, 'inputs', return_value=(self.product, self.secrets)), patch.object(catalog, 'setup') as setup, redirect_stdout(StringIO()):
            catalog.initialize()
            setup.assert_called_once_with('catalog-init')


class CatalogOAuthSecretTests(unittest.TestCase):
    def assert_unlocked(self, fixture):
        self.assertIn(('sql', 'SELECT pg_advisory_unlock(%s)', [str(__import__('uuid').UUID(fixture.product['install_id']).int & ((1 << 63) - 1))]), fixture.calls)

    def assert_conflict(self, fixture, *, before_users=True):
        with self.assertRaises(startup_diagnostics.StartupFailure) as caught: fixture.run()
        record = startup_diagnostics.failure_record(caught.exception)
        self.assertEqual({k: record[k] for k in ('stage', 'code', 'category')},
                         {'stage': 'catalog_bootstrap', 'code': 'invalid_input', 'category': 'validation'})
        self.assertNotIn(fixture.secrets['oauth_secret'], json.dumps(record))
        self.assertEqual(fixture.tx, ['enter', 'rollback_requested'])
        self.assertEqual(fixture.commands, ['migrate'])
        self.assertFalse((fixture.data / 'initialized.json').exists())
        self.assert_unlocked(fixture)
        if before_users: self.assertFalse(any(c[0] == 'user_get' for c in fixture.calls))

    def test_new_native_raw_secret_application_completes_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp, new_app=True); f.run()
            self.assertEqual(f.app.client_secret, f.secrets['oauth_secret'])
            self.assertEqual(f.defaults['client_secret'], f.secrets['oauth_secret'])
            self.assertEqual(f.compare_calls, [(f.secrets['oauth_secret'], f.app.client_secret)])
            self.assertEqual(f.app.user_id, 1)
            self.assertEqual(f.tx, ['enter', 'commit_requested'])
            self.assertEqual(f.commands, ['migrate', 'collectstatic'])
            self.assertTrue((f.data / 'initialized.json').is_file())
            self.assert_unlocked(f)

    def test_reinitialization_preserves_secret_identity_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp); f.run()
            before = {p.name: p.read_bytes() for p in f.data.iterdir()}
            f.run()
            self.assertEqual(before, {p.name: p.read_bytes() for p in f.data.iterdir()})
            self.assertEqual(f.app.client_secret, f.secrets['oauth_secret'])
            self.assertEqual(f.resource.title, 'Retained edited title')
            self.assertEqual(f.tx, ['enter', 'commit_requested'] * 2)
            self.assertFalse(any(c[0] == 'app_save' for c in f.calls))
            for user in f.users.values(): user.set_password.assert_not_called()

    def test_wrong_native_secret_is_rejected_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp); f.app.client_secret = 'W' * 64
            self.assert_conflict(f)
            self.assertEqual(f.app.client_secret, 'W' * 64)
            self.assertEqual(f.compare_calls, [(f.secrets['oauth_secret'], 'W' * 64)])

    def test_password_hash_string_is_not_adopted_as_native_raw_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp); f.app.client_secret = 'pbkdf2_sha256$1000$synthetic$salt'
            self.assert_conflict(f)

    def test_conflicting_application_metadata_still_fails_closed(self):
        for attr, value in [('name', 'Another app'), ('redirect_uris', 'http://127.0.0.1:9001/oauth/callback'),
                            ('skip_authorization', True), ('client_type', 'public'),
                            ('authorization_grant_type', 'password')]:
            with self.subTest(attribute=attr), tempfile.TemporaryDirectory() as tmp:
                f = BootstrapFixture(tmp); setattr(f.app, attr, value)
                self.assert_conflict(f)
                self.assertEqual(f.compare_calls, [])

    def test_existing_foreign_owner_still_fails_without_adoption(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp); f.app.user_id = 99
            self.assert_conflict(f, before_users=False)
            self.assertEqual(f.app.user_id, 99)
            self.assertFalse(any(c[0] == 'app_save' for c in f.calls))

    def test_privileged_sample_user_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp); f.users['owner'].is_staff = True
            self.assert_conflict(f, before_users=False)

    def test_conflicting_resource_binding_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp); f.resource.owner_id = 99
            self.assert_conflict(f, before_users=False)

    def test_conflicting_health_token_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = BootstrapFixture(tmp); f.token.application_id = 99
            self.assert_conflict(f, before_users=False)


if __name__ == '__main__': unittest.main()
