"""Boundary tests for disposable runtime configuration and secret-safe HTTP evidence."""
import contextlib
import copy
import io
import json
import logging
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from fixture_settings import (
    FIXTURE_USERS, SafeApplicationLog, database_url, load_config, source_environment, strict_verifier_options, validate_config,
)
from manage_fixture import observed_application


class FixtureConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "output": "/tmp/disposable-geonode-example",
            "database": {"host": "127.0.0.1", "port": 5544, "name": "fixture", "user": "migrator", "password": "db password:@"},
            "runtime_database": {"host": "127.0.0.1", "port": 5544, "name": "fixture", "user": "runtime", "password": "runtime password"},
            "site_url": "http://127.0.0.1:8123/",
            "geoserver_url": "http://127.0.0.1:8124/geoserver/",
            "redirect_uri": "http://127.0.0.1:8125/callback",
            "secret_key": "example-secret-key-value-not-a-runtime-secret",
            "api_key": "example-api-key-value-not-a-runtime-secret",
            "client_id": "example-client-id-not-a-runtime-secret",
            "client_secret": "example-client-secret-not-a-runtime-secret",
            "second_client_id": "example-second-client-id-not-a-runtime-secret",
            "second_client_secret": "example-second-client-secret-not-a-runtime-secret",
            "passwords": {name: "example-password-not-a-runtime-secret" for name in FIXTURE_USERS},
            "oidc_rsa_private_key_file": "/tmp/disposable-generated-oidc-key.pem",
        }

    def test_rejects_remote_services_callbacks_and_credential_urls(self):
        for key in ("site_url", "geoserver_url", "redirect_uri"):
            for value in ("http://example.invalid:8000/", "http://127.0.0.1/", "http://user:pass@127.0.0.1:8000/",
                          "http://127.0.0.1:8000/?token=secret", "http://127.0.0.1:8000/#fragment"):
                with self.subTest(key=key, value=value):
                    config = dict(self.config, **{key: value})
                    with self.assertRaises(ValueError):
                        validate_config(config)

    def test_rejects_remote_or_different_runtime_database(self):
        for field, value in (("host", "db.example.invalid"), ("port", 6000), ("name", "other")):
            config = copy.deepcopy(self.config)
            config["runtime_database"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_config(config)

    def test_requires_distinct_oauth_clients_and_generated_secrets(self):
        for override in ({"second_client_id": self.config["client_id"]}, {"api_key": "default"},
                         {"passwords": {}}, {"oidc_rsa_private_key_file": ""}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                validate_config(dict(self.config, **override))

    def test_strict_verifier_cannot_be_claimed_by_unpatched_source(self):
        baseline = SimpleNamespace()
        patched = SimpleNamespace(OAUTH2_BACKEND_TOKENINFO_STRICT=False)
        self.assertEqual(strict_verifier_options(self.config, baseline), {})
        self.assertEqual(strict_verifier_options(dict(self.config, strict_verifier=True), patched),
                         {"OAUTH2_BACKEND_TOKENINFO_STRICT": True})
        self.assertEqual(strict_verifier_options(self.config, patched), {"OAUTH2_BACKEND_TOKENINFO_STRICT": False})
        with self.assertRaises(ValueError):
            strict_verifier_options(dict(self.config, strict_verifier=True), baseline)
        for value in ("true", "False", 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_config(dict(self.config, strict_verifier=value))

    def test_owner_only_regular_config_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(self.config))
            path.chmod(0o600)
            self.assertEqual(load_config(path), self.config)
            path.chmod(0o640)
            with self.assertRaises(ValueError):
                load_config(path)
            path.chmod(0o600)
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                load_config(link)

    def test_runtime_uses_dml_role_and_migrator_uses_owner_role(self):
        self.assertIn("runtime:", source_environment(self.config, runtime=True)["DATABASE_URL"])
        self.assertIn("migrator:", source_environment(self.config, runtime=False)["DATABASE_URL"])
        self.assertEqual(source_environment(self.config)["DJANGO_EMAIL_BACKEND"], "django.core.mail.backends.locmem.EmailBackend")
        self.assertEqual(source_environment(self.config)["BROKER_URL"], "memory://")

    def test_database_credentials_are_url_encoded(self):
        url = database_url(self.config["database"])
        self.assertIn("db%20password%3A%40", url)
        self.assertNotIn("db password:@", url)


class SafeLoggingTests(unittest.TestCase):
    def test_native_wsgi_request_and_response_are_preserved_without_token_logging(self):
        secret = "sensitive-code-and-token"
        received = {}
        environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/o/token/", "QUERY_STRING": f"code={secret}",
                   "HTTP_AUTHORIZATION": f"Bearer {secret}", "HTTP_COOKIE": f"sessionid={secret}",
                   "HTTP_X_AMBISGIS_CORRELATION_ID": "integration-case-01", "wsgi.input": io.BytesIO(secret.encode())}
        def application(request, start):
            self.assertIs(request, environ)
            received["body"] = request["wsgi.input"].read()
            start("200 OK", [("Content-Type", "application/json"), ("Set-Cookie", secret)])
            return [secret.encode()]
        def start(status, headers, exc_info=None):
            received["status"] = status
            received["headers"] = headers
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            body = b"".join(observed_application(application)(environ, start))
        self.assertEqual(body, secret.encode())
        self.assertEqual(received["body"], secret.encode())
        self.assertIn(("Set-Cookie", secret), received["headers"])
        self.assertNotIn(secret, output.getvalue())
        evidence = json.loads(output.getvalue())
        self.assertEqual(evidence["correlation_id"], "integration-case-01")
        self.assertEqual(evidence["status"], 200)

    def test_log_formatter_redacts_secret_arguments_and_exception_messages(self):
        record = logging.LogRecord("oauthlib", logging.ERROR, "source.py", 1, "token=%s", ("sensitive-token",),
                                   (ValueError, ValueError("sensitive-password"), None))
        formatter = SafeApplicationLog()
        formatter.secrets = ["sensitive-token"]
        rendered = formatter.format(record)
        self.assertEqual(json.loads(rendered)["message"], "token=[REDACTED]")
        self.assertEqual(json.loads(rendered)["exception_type"], "ValueError")
        self.assertEqual(json.loads(rendered)["source_diagnostic_redactions"], 1)
        self.assertNotIn("sensitive", rendered)

    def test_log_formatter_preserves_positive_control_and_redacts_unknown_oauth_values(self):
        formatter = SafeApplicationLog()
        for message, expected in (("AMBISGIS_GEONODE_LOG_CAPTURE_CONTROL", "AMBISGIS_GEONODE_LOG_CAPTURE_CONTROL"),
                                  ("GeoNode diagnostics active", "GeoNode diagnostics active"),
                                  ("access_token=unknown-small-token", "access_token=[REDACTED]"),
                                  ("Bearer dynamic-token", "Bearer [REDACTED]"),
                                  ("native token " + "t" * 30, "native token [REDACTED OPAQUE VALUE]")):
            record = logging.LogRecord("geonode", logging.WARNING, "source.py", 1, message, (), None)
            rendered = json.loads(formatter.format(record))
            self.assertEqual(rendered["message"], expected)
            self.assertEqual(rendered["source_diagnostic_redactions"], 0)

    def test_formatter_reports_underlying_credential_and_key_masking(self):
        formatter = SafeApplicationLog()
        messages = (
            ("Bearer dynamic-token", 1, 0, 0),
            ("access_token=dynamic-token", 1, 0, 0),
            ("-----BEGIN PRIVATE KEY-----\nfake-private-material\n-----END PRIVATE KEY-----", 0, 1, 0),
            ("native identifier " + "x" * 31, 0, 0, 1),
            ("AMBISGIS_GEONODE_LOG_CAPTURE_CONTROL", 0, 0, 0),
        )
        for message, fields, keys, opaque in messages:
            with self.subTest(fields=fields, keys=keys, opaque=opaque):
                record = logging.LogRecord("geonode", logging.WARNING, "source.py", 1, message, (), None)
                rendered = json.loads(formatter.format(record))
                self.assertEqual(rendered["source_diagnostic_redactions"], 0)
                self.assertEqual(rendered["source_credential_field_redactions"], fields)
                self.assertEqual(rendered["source_private_key_redactions"], keys)
                self.assertEqual(rendered["source_opaque_value_redactions"], opaque)
                self.assertNotIn("dynamic-token", rendered["message"])
                self.assertNotIn("fake-private-material", rendered["message"])


if __name__ == "__main__":
    unittest.main()
