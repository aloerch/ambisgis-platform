#!/usr/bin/env python3
"""Run the exact GeoNode application against private disposable configuration."""
from __future__ import annotations

import argparse
from datetime import timedelta
import hashlib
import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
from socketserver import ThreadingMixIn
import sys
import threading
import weakref
import uuid
from urllib.parse import urlsplit
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

# Load only pure configuration helpers under a different name. Django must own
# the FIRST import of its settings module; pre-import/reload can freeze a partial
# settings object when source imports cause Django lazy settings access.
_CONFIG_SPEC = importlib.util.spec_from_file_location("_fixture_configuration", Path(__file__).with_name("fixture_settings.py"))
_CONFIG = importlib.util.module_from_spec(_CONFIG_SPEC)
_CONFIG_SPEC.loader.exec_module(_CONFIG)
FIXTURE_USERS = _CONFIG.FIXTURE_USERS
load_config = _CONFIG.load_config
read_private_json = _CONFIG.read_private_json


OUTPUT_LOCK = threading.Lock()

def emit(value):
    with OUTPUT_LOCK:
        print(json.dumps(value, sort_keys=True), flush=True)


def module_evidence(config, command):
    from django.conf import settings
    from django.contrib.auth.signals import user_logged_in, user_logged_out
    from django.db.models.signals import post_migrate, post_save
    modules = {}
    module_names = ("geonode", "geonode.settings", "geonode.urls", "geonode.people.models",
                 "geonode.people.signals", "geonode.api.views", "geonode.security.middleware",
                 "geonode.groups.models", "geonode_mapstore_client", "oauth2_provider.models")
    if getattr(settings, "OAUTH2_BACKEND_TOKENINFO_STRICT", False):
        module_names += ("geonode.api.backend_tokeninfo",)
    for name in module_names:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        modules[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    signals = {}
    for name, signal in (("post_save", post_save), ("post_migrate", post_migrate),
                         ("user_logged_in", user_logged_in), ("user_logged_out", user_logged_out)):
        receivers = []
        for entry in signal.receivers:
            receiver = entry[1]
            if isinstance(receiver, weakref.ReferenceType):
                receiver = receiver()
            if receiver is not None:
                receivers.append(f"{getattr(receiver, '__module__', type(receiver).__module__)}.{getattr(receiver, '__qualname__', type(receiver).__qualname__)}")
        signals[name] = sorted(receivers)
    if "geonode.people.signals.profile_post_save" not in signals["post_save"]:
        raise RuntimeError("Native GeoNode user post-save hook is not connected")
    if "geonode.people.signals.do_login" not in signals["user_logged_in"]:
        raise RuntimeError("Native GeoNode login hook is not connected")
    if "geonode.geoserver.apps.set_resource_links" not in signals["post_migrate"]:
        raise RuntimeError("Native GeoNode post-migrate hook is not connected")
    value = {"command": command, "modules": modules, "signals": signals,
             "root_urlconf": settings.ROOT_URLCONF, "auth_user_model": settings.AUTH_USER_MODEL,
             "strict_verifier": getattr(settings, "OAUTH2_BACKEND_TOKENINFO_STRICT", False),
             "strict_verifier_supported_by_source": hasattr(importlib.import_module("geonode.settings"), "OAUTH2_BACKEND_TOKENINFO_STRICT"),
             "middleware": list(settings.MIDDLEWARE), "silenced_system_checks": list(settings.SILENCED_SYSTEM_CHECKS),
             "installed_apps": [item if isinstance(item, str) else type(item).__module__ + "." + type(item).__name__ for item in settings.INSTALLED_APPS],
             "source_origin_scope": "Actual imported module paths and hashes; source/wheel custody checked by build receipt"}
    path = Path(config["output"]) / f"module-origins-{command}.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    emit({"event": "module_evidence", "command": command, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "modules": len(modules)})


def migration_evidence(config, command):
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.recorder import MigrationRecorder
    applied = sorted(MigrationRecorder(connection).applied_migrations())
    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    value = {"command": command, "applied": [{"app": app, "name": name} for app, name in applied],
             "pending": [{"app": migration.app_label, "name": migration.name, "backwards": backwards}
                         for migration, backwards in pending]}
    path = Path(config["output"]) / f"migrations-{command}.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    if pending:
        raise RuntimeError("The complete native GeoNode migration graph is not applied")
    emit({"event": "migration_evidence", "command": command, "applied_count": len(applied),
          "pending_count": 0, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})


def assert_runtime_role(config):
    from django.db import connection
    if "runtime_database" not in config or config["runtime_database"]["user"] == config["database"]["user"]:
        raise ValueError("Serving requires a separate runtime DML role")
    with connection.cursor() as cursor:
        cursor.execute("""SELECT current_user, session_user, r.rolsuper, r.rolcreatedb,
            r.rolcreaterole, r.rolreplication, r.rolbypassrls,
            has_schema_privilege(current_user, 'public', 'CREATE'),
            has_database_privilege(current_user, current_database(), 'CREATE'),
            pg_has_role(current_user, %s, 'MEMBER')
            FROM pg_roles r WHERE r.rolname = current_user""", [config["database"]["user"]])
        row = cursor.fetchone()
        keys = ("current_user", "session_user", "superuser", "create_database", "create_role", "replication", "bypass_rls", "schema_create", "database_create", "member_of_migrator")
        receipt = dict(zip(keys, row))
        if row[0] != config["runtime_database"]["user"] or row[1] != row[0] or any(row[2:]):
            raise RuntimeError("Runtime database role has unexpected identity or schema privileges")
        cursor.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relowner = (SELECT oid FROM pg_roles WHERE rolname = current_user)
            AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'""")
        receipt["owned_relations"] = cursor.fetchone()[0]
        if receipt["owned_relations"]:
            raise RuntimeError("Runtime database role must not own catalog tables")
        for table in ("people_profile", "oauth2_provider_application", "oauth2_provider_accesstoken", "django_session"):
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                cursor.execute("SELECT has_table_privilege(current_user, %s, %s)", [table, privilege])
                if not cursor.fetchone()[0]:
                    raise RuntimeError("Runtime role lacks required fixture DML access")
        receipt["required_dml"] = "verified"
    path = Path(config["output"]) / "runtime-role.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    emit({"event": "runtime_role_verified", **receipt})


def provision(config):
    from django.contrib.auth import get_user_model
    from django.contrib.sites.models import Site
    from django.db import transaction
    from django.urls import reverse
    from allauth.account.models import EmailAddress
    from geonode.groups.models import GroupProfile
    from oauth2_provider.models import get_application_model

    User = get_user_model()
    Application = get_application_model()
    with transaction.atomic():
        applications = []
        for client_key, secret_key, name in (
            ("client_id", "client_secret", "AmbisGIS fixture GeoServer"),
            ("second_client_id", "second_client_secret", "AmbisGIS fixture other client"),
        ):
            # Creating the backend client first preserves native login token hooks.
            app, created = Application.objects.get_or_create(client_id=config[client_key], defaults={
                "name": name,
                "client_secret": config[secret_key],
                "client_type": Application.CLIENT_CONFIDENTIAL,
                "authorization_grant_type": Application.GRANT_AUTHORIZATION_CODE,
                "redirect_uris": config["redirect_uri"],
                "skip_authorization": False,
            })
            if not created and (app.name != name or app.client_type != Application.CLIENT_CONFIDENTIAL
                                or app.authorization_grant_type != Application.GRANT_AUTHORIZATION_CODE
                                or app.redirect_uris != config["redirect_uri"] or app.skip_authorization):
                raise ValueError("Existing OAuth client does not match disposable fixture")
            applications.append(app)
        users = {}
        for username in FIXTURE_USERS:
            admin = username == "fixture-admin"
            user, created = User.objects.get_or_create(username=username, defaults={
                "email": f"{username}@example.invalid", "is_active": username != "fixture-disabled",
                "is_staff": admin, "is_superuser": admin,
            })
            if not created:
                raise ValueError("Provisioning requires fresh disposable fixture users")
            password = config["passwords"].get(username, config["passwords"].get(username.removeprefix("fixture-")))
            user.set_password(password)
            user.save()
            EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={"verified": True, "primary": True})
            users[username] = user
        group, _ = GroupProfile.objects.get_or_create(slug="fixture-readers", defaults={
            "title": "Synthetic fixture readers", "description": "Disposable integration principals", "access": "private",
        })
        group.join(users["fixture-reader"])
        group.join(users["fixture-disabled"])
        for app in applications:
            app.user = users["fixture-admin"]
            app.save(update_fields=["user"])
        site = urlsplit(config["site_url"])
        Site.objects.update_or_create(id=1, defaults={"domain": site.netloc, "name": "AmbisGIS identity fixture"})
    receipt = {"users": list(users), "user_ids": {username: user.pk for username, user in users.items()},
               "disabled_login_redirect_path": reverse("moderator_contacted", kwargs={"inactive_user": users["fixture-disabled"].pk}),
               "applications": len(applications), "group": "fixture-readers", "skip_authorization": False,
               "pkce_required": True,
               "geoserver_users": "manually mirrored XML comparison; no account synchronization claim"}
    (Path(config["output"]) / "provisioning.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    emit({"event": "provisioned", **receipt})


def initialize(config):
    """Stage inherited installed static assets with Django's supported command."""
    from django.conf import settings
    from django.core.management import call_command
    destination = Path(settings.STATIC_ROOT)
    if destination.resolve() != (Path(config["output"]) / "static").resolve() or destination.is_symlink():
        raise ValueError("Static initialization is limited to the disposable run directory")
    call_command("collectstatic", interactive=False, verbosity=1)
    inventory = {}
    for path in sorted(destination.rglob("*")):
        if path.is_symlink():
            raise ValueError("Static initialization must produce copied assets, not links")
        if path.is_file():
            inventory[str(path.relative_to(destination))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if "mapstore/version.txt" not in inventory:
        raise RuntimeError("Inherited MapStore version asset was not collected")
    receipt = {"command": "collectstatic", "asset_count": len(inventory),
               "static_tree_sha256": hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
               "mapstore_version_sha256": inventory["mapstore/version.txt"],
               "scope": "Copied inherited installed static assets; no frontend rebuild, JavaScript, browser or accessibility acceptance"}
    (Path(config["output"]) / "static-initialization.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    emit({"event": "static_assets_initialized", **receipt})


def native_tests(config):
    """Run owned-source Django TestCases with real rollback transactions."""
    import unittest
    labels = (
        "geonode.security.tests.AuthConfigTests.test_basic_auth_payload_round_trip",
        "geonode.security.tests.AuthHandlerTests.test_build_returns_basic_auth_handler",
        "geonode.security.tests.AuthHandlerTests.test_build_raises_for_unsupported_type",
        "geonode.security.tests.AuthHandlerTests.test_basic_auth_handler_get_request_auth",
    )
    if config.get("strict_verifier", False):
        labels += ("geonode.api.test_backend_tokeninfo.StrictBackendTokenInfoTests",)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in labels)
    def test_ids(node):
        if isinstance(node, unittest.TestSuite):
            return [ident for child in node for ident in test_ids(child)]
        return [node.id()]
    collected = test_ids(suite)
    expected_count = suite.countTestCases()
    result = unittest.TestResult()
    suite.run(result)
    value = {"labels": list(labels), "test_ids": collected, "expected_count": expected_count, "tests_run": result.testsRun,
             "strict_verifier": config.get("strict_verifier", False),
             "failures": [test.id() for test, _ in result.failures],
             "errors": [test.id() for test, _ in result.errors],
             "skips": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
             "expected_failures": [test.id() for test, _ in result.expectedFailures],
             "unexpected_successes": [test.id() for test in result.unexpectedSuccesses],
             "scope": "Four unmodified native ORM encryption/auth handler tests plus the owned strict verifier regression suite when enabled; native Django TestCase rollback transactions on disposable catalog; real HTTP identity acceptance is separate"}
    value["passed"] = (result.testsRun == expected_count and expected_count >= 4 and result.wasSuccessful() and not result.skipped
                       and not result.expectedFailures and not result.unexpectedSuccesses)
    path = Path(config["output"]) / "native-tests.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    emit({"event": "native_tests", **value})
    for test, trace in result.failures + result.errors:
        logging.getLogger("geonode.fixture").error("Native test %s failed: %s", test.id(), trace)
    if not value["passed"]:
        raise RuntimeError("Selected native GeoNode tests did not all pass")


def cleanup(config):
    """Invalidate only fixture credentials through native ORM APIs, retain users."""
    import secrets
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import transaction
    from oauth2_provider.models import AccessToken, Grant, IDToken, RefreshToken, get_application_model
    User = get_user_model()
    with transaction.atomic():
        users = list(User.objects.filter(username__in=FIXTURE_USERS))
        if any(user.email != f"{user.username}@example.invalid" for user in users):
            raise RuntimeError("Refuse cleanup for users without fixture identity markers")
        user_ids = [user.pk for user in users]
        clients = get_application_model().objects.filter(client_id__in=(config["client_id"], config["second_client_id"]))
        if any(app.name not in ("AmbisGIS fixture GeoServer", "AmbisGIS fixture other client") for app in clients):
            raise RuntimeError("Refuse cleanup for clients without fixture identity markers")
        counts = {}
        for model in (Grant, RefreshToken, AccessToken, IDToken):
            queryset = model.objects.filter(user_id__in=user_ids, application__in=clients)
            counts[model.__name__] = queryset.count()
            queryset.delete()
        ids = {str(value) for value in user_ids}
        session_ids = [session.session_key for session in Session.objects.all()
                       if str(session.get_decoded().get("_auth_user_id")) in ids]
        counts["Session"] = len(session_ids)
        Session.objects.filter(session_key__in=session_ids).delete()
        for user in users:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        counts["user_passwords_invalidated"] = len(users)
        counts["client_secrets_rotated"] = clients.count()
        for app in clients:
            app.client_secret = secrets.token_urlsafe(48)
            app.save(update_fields=["client_secret"])
    emit({"event": "fixture_credentials_invalidated", "counts": counts,
          "retained_users": len(users), "supported_orm_only": True})


def mutate(args, config):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from geonode.groups.models import GroupProfile
    from oauth2_provider.models import AccessToken

    if args.action == "remove" and args.username != "fixture-outsider":
        raise ValueError("User removal is limited to the disposable fixture-outsider principal")
    user = get_user_model().objects.get(username=args.username)
    if args.action == "remove":
        if user.email != "fixture-outsider@example.invalid":
            raise ValueError("Refuse removal without the generated fixture identity marker")
        from django.db import transaction
        with transaction.atomic():
            total, counts = user.delete()
        emit({"event": "fixture_mutation", "action": "remove", "username": args.username,
              "deleted_records": total, "model_counts": counts, "supported_orm_only": True})
        return
    if args.action in ("disable", "enable"):
        user.is_active = args.action == "enable"
        user.save(update_fields=["is_active"])
    elif args.action in ("group-add", "group-remove"):
        group = GroupProfile.objects.get(slug="fixture-readers")
        (group.join if args.action == "group-add" else group.leave)(user)
    else:
        if not args.token_file:
            raise ValueError("Token mutation requires an owner-only JSON token file")
        value = read_private_json(args.token_file)
        token_value = value.get("access_token")
        if not isinstance(token_value, str) or not token_value:
            raise ValueError("Token file must contain access_token")
        token = AccessToken.objects.get(
            token=token_value, user=user,
            application__client_id__in=(config["client_id"], config["second_client_id"]),
        )
        if args.action in ("expire", "expire-soon"):
            offset = args.seconds if args.action == "expire-soon" else -60
            token.expires = timezone.now() + timedelta(seconds=offset)
            token.save(update_fields=["expires"])
        else:
            token.revoke()
    emit({"event": "fixture_mutation", "action": args.action, "username": args.username,
          "expires_in_seconds": args.seconds if args.action == "expire-soon" else None})


class QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # The standard request line contains authorization codes in the query.
        pass


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def observed_application(application):
    """Transport logging wrapper; it never changes request authentication."""
    def handle(environ, start_response):
        supplied = environ.get("HTTP_X_AMBISGIS_CORRELATION_ID", "")
        correlation = supplied if re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", supplied) else uuid.uuid4().hex
        method = environ.get("REQUEST_METHOD", "")
        path = environ.get("PATH_INFO", "")
        status_code = 500
        def start(status, headers, exc_info=None):
            nonlocal status_code
            status_code = int(status.split(" ", 1)[0])
            return start_response(status, headers, exc_info)
        response = None
        try:
            response = application(environ, start)
            yield from response
        finally:
            if response is not None and hasattr(response, "close"):
                response.close()
            # Only controlled fixture paths; no query, cookies, headers or body.
            safe_path = path if re.fullmatch(r"/[A-Za-z0-9_./-]{0,240}", path) else "[redacted-path]"
            emit({"event": "http_request", "correlation_id": correlation, "method": method,
                  "path": safe_path, "status": status_code})
    return handle


def serve(config):
    from django.core.wsgi import get_wsgi_application
    from transport_faults import controlled_transport
    site = urlsplit(config["site_url"])
    if site.hostname != "127.0.0.1":
        raise ValueError("HTTP fixture listener requires site_url host 127.0.0.1")
    logging.getLogger("geonode.fixture").warning("AMBISGIS_GEONODE_LOG_CAPTURE_CONTROL")
    with make_server(site.hostname, site.port, observed_application(controlled_transport(get_wsgi_application(), config)),
                     server_class=ThreadedWSGIServer, handler_class=QuietRequestHandler) as server:
        emit({"event": "listening", "host": site.hostname, "port": site.port, "application": "geonode.urls"})
        server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("command", choices=("check", "migrate", "provision", "serve", "mutate", "cleanup", "native-tests", "initialize"))
    parser.add_argument("--action", choices=("revoke", "expire", "expire-soon", "disable", "enable", "group-add", "group-remove", "remove"))
    parser.add_argument("--username", choices=FIXTURE_USERS, default="fixture-reader")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--seconds", type=int, choices=range(1, 16), default=5)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    os.environ["AMBISGIS_GEONODE_CONFIG"] = str(args.config.resolve())
    os.environ["AMBISGIS_GEONODE_RUNTIME"] = "1" if args.command in ("serve", "mutate", "cleanup", "native-tests") else "0"
    os.environ["DJANGO_SETTINGS_MODULE"] = "fixture_settings"
    import django
    django.setup()
    from django.apps import apps
    from django.conf import settings
    required = {"geonode.people", "geonode.geoserver", "geonode.groups", "oauth2_provider", "geonode_mapstore_client"}
    loaded = {app.name for app in apps.get_app_configs()}
    if not required.issubset(loaded) or settings.AUTH_USER_MODEL != "people.Profile" or settings.ROOT_URLCONF != "geonode.urls":
        raise RuntimeError("Full native GeoNode app/model/URL configuration did not load")
    if settings.DATABASES["default"]["ENGINE"] != "django.contrib.gis.db.backends.postgis":
        raise RuntimeError("Native GeoNode requires the configured real PostGIS database")
    if getattr(settings, "OAUTH2_BACKEND_TOKENINFO_STRICT", False) is not config.get("strict_verifier", False):
        raise RuntimeError("Loaded owned strict verifier setting differs from explicit fixture choice")
    module_evidence(config, args.command)
    logging.getLogger("geonode.fixture").warning("GeoNode fixture diagnostics active")
    from django.core.management import call_command
    if args.command == "check":
        call_command("check")
    elif args.command == "migrate":
        call_command("migrate", interactive=False, verbosity=1)
        migration_evidence(config, args.command)
    elif args.command == "provision":
        migration_evidence(config, args.command)
        provision(config)
    elif args.command == "initialize":
        initialize(config)
    elif args.command == "native-tests":
        assert_runtime_role(config)
        migration_evidence(config, args.command)
        native_tests(config)
    elif args.command == "cleanup":
        assert_runtime_role(config)
        cleanup(config)
    elif args.command == "mutate":
        if not args.action:
            parser.error("mutate requires --action")
        mutate(args, config)
    else:
        assert_runtime_role(config)
        migration_evidence(config, args.command)
        serve(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
