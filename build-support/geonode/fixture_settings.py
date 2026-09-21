"""Loopback-only settings for the full source-owned GeoNode identity fixture.

No apps, middleware, URL patterns, model signals, or migrations are replaced.
This is disposable integration configuration, not a production settings module.
"""
from __future__ import annotations

import importlib
import json
import logging
import re
import os
from pathlib import Path
import stat
from urllib.parse import quote, urlsplit


FIXTURE_USERS = ("fixture-reader", "fixture-outsider", "fixture-disabled", "fixture-admin", "fixture-unmapped")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def read_private_json(path):
    path = Path(path)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
        raise ValueError("Configuration must be a regular owner-only file")
    if metadata.st_uid != os.getuid():
        raise ValueError("Configuration must belong to the current user")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Configuration must be a JSON object")
    return value


def require_loopback_url(value, label, *, trailing_slash=False):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.port
    ):
        raise ValueError(f"{label} must be an explicit loopback HTTP URL without credentials or query")
    if trailing_slash and not value.endswith("/"):
        raise ValueError(f"{label} must end in a slash")
    return parsed


def validate_database(value):
    if not isinstance(value, dict) or value.get("host") not in LOOPBACK_HOSTS:
        raise ValueError("Database must use a literal loopback host")
    if not isinstance(value.get("port"), int) or not 1 <= value["port"] <= 65535:
        raise ValueError("Database must specify a valid integer port")
    for key in ("name", "user", "password"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"Database requires {key}")
    return value


def validate_config(value):
    if type(value.get("strict_verifier", False)) is not bool:
        raise ValueError("strict_verifier must be a JSON boolean")
    if type(value.get("strict_roles", False)) is not bool:
        raise ValueError("strict_roles must be a JSON boolean")
    if value.get("strict_roles") and (not value.get("strict_verifier") or value.get("role_service_username") != "fixture-role-service"
            or not isinstance(value.get("role_service_api_key"), str) or len(value["role_service_api_key"]) < 24):
        raise ValueError("Strict roles require strict verifier and a dedicated generated service credential")
    require_loopback_url(value.get("site_url"), "site_url", trailing_slash=True)
    require_loopback_url(value.get("geoserver_url"), "geoserver_url", trailing_slash=True)
    require_loopback_url(value.get("redirect_uri"), "redirect_uri")
    validate_database(value.get("database"))
    if "runtime_database" in value:
        runtime = validate_database(value["runtime_database"])
        if any(runtime[key] != value["database"][key] for key in ("host", "port", "name")):
            raise ValueError("Runtime role must connect to the same disposable database")
    for key in ("secret_key", "api_key", "client_id", "client_secret", "second_client_id", "second_client_secret"):
        if not isinstance(value.get(key), str) or len(value[key]) < 24:
            raise ValueError(f"{key} must be a generated value of at least 24 characters")
    if value["client_id"] == value["second_client_id"]:
        raise ValueError("OAuth applications must have distinct client IDs")
    if not isinstance(value.get("output"), str) or not Path(value["output"]).is_absolute():
        raise ValueError("output must be an absolute disposable run directory")
    passwords = value.get("passwords", {})
    for name in FIXTURE_USERS:
        password = passwords.get(name, passwords.get(name.removeprefix("fixture-")))
        if not isinstance(password, str) or len(password) < 24:
            raise ValueError(f"A generated password is required for {name}")
    if not (value.get("oidc_rsa_private_key") or value.get("oidc_rsa_private_key_file")):
        raise ValueError("An independently generated OIDC RSA private key is required")
    return value


def load_config(path):
    return validate_config(read_private_json(path))


def database_url(database):
    host = database["host"]
    if ":" in host:
        host = f"[{host}]"
    return (
        f"postgis://{quote(database['user'], safe='')}:{quote(database['password'], safe='')}"
        f"@{host}:{database['port']}/{quote(database['name'], safe='')}"
    )


def source_environment(config, runtime=False):
    """Set source-supported settings before importing geonode.settings."""
    site = urlsplit(config["site_url"])
    database = config.get("runtime_database", config["database"]) if runtime else config["database"]
    return {
        "DATABASE_URL": database_url(database),
        "DEFAULT_BACKEND_DATASTORE": "",
        "SECRET_KEY": config["secret_key"],
        "SITEURL": config["site_url"],
        "SITE_HOST_SCHEMA": "http",
        "SITE_HOST_NAME": site.hostname,
        "SITE_HOST_PORT": str(site.port),
        "GEOSERVER_LOCATION": config["geoserver_url"],
        "GEOSERVER_PUBLIC_LOCATION": config["geoserver_url"],
        "GEOSERVER_WEB_UI_LOCATION": config["geoserver_url"],
        "GEOSERVER_ADMIN_USER": config.get("geoserver_admin_user", "fixture-admin"),
        "GEOSERVER_ADMIN_PASSWORD": config.get("geoserver_admin_password", config["secret_key"]),
        "GEOSERVER_FACTORY_PASSWORD": config.get("geoserver_admin_password", config["secret_key"]),
        "OAUTH2_API_KEY": config["api_key"],
        "OAUTH2_DEFAULT_BACKEND_CLIENT_NAME": "AmbisGIS fixture GeoServer",
        "DEBUG": "False",
        "MEMCACHED_ENABLED": "False",
        "ASYNC_SIGNALS": "False",
        "BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
        "CELERY_TASK_ALWAYS_EAGER": "True",
        "CELERY_TASK_EAGER_PROPAGATES": "True",
        "CELERY_TASK_IGNORE_RESULT": "True",
        "UPDATE_RESOURCE_LINKS_AT_MIGRATE": "False",
        "EMAIL_ENABLE": "False",
        "DJANGO_EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "SESSION_COOKIE_SECURE": "False",  # Only this loopback HTTP fixture.
        "CSRF_COOKIE_SECURE": "False",
        "SECURE_SSL_REDIRECT": "False",
        "ALLOWED_HOSTS": "['127.0.0.1', 'localhost', '[::1]']",
        "AUTH_IP_WHITELIST": "127.0.0.1,::1",
        "PROXY_ALLOWED_HOSTS": "['127.0.0.1', 'localhost', '::1']",
    }


class SafeApplicationLog(logging.Formatter):
    """Keep source diagnostics while redacting config secrets and opaque tokens.

    The runner independently scans/redacts known runtime values as a second
    boundary. Exception class survives; traceback locals/body text do not.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.secrets = []
        config_path = os.environ.get("AMBISGIS_GEONODE_CONFIG")
        if config_path:
            config = load_config(config_path)
            self.secrets = [config[key] for key in ("secret_key", "api_key", "client_secret", "second_client_secret")]
            self.secrets += [config.get("role_service_api_key", "")]
            self.secrets = [value for value in self.secrets if value]
            self.secrets += list(config["passwords"].values())
            self.secrets += [config[key]["password"] for key in ("database", "runtime_database") if key in config]
            if config.get("geoserver_admin_password"):
                self.secrets.append(config["geoserver_admin_password"])

    def format(self, record):
        message = record.getMessage()
        known_redactions = sum(message.count(secret) for secret in set(self.secrets) if secret)
        for secret in sorted(set(self.secrets), key=len, reverse=True):
            message = message.replace(secret, "[REDACTED]")
        message, private_key_redactions = re.subn(r"(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED KEY]", message)
        message, auth_redactions = re.subn(r"(?i)\b(Bearer|Basic|ApiKey)\s+[^\s\"'<>]+", r"\1 [REDACTED]", message)
        message, field_redactions = re.subn(r"(?i)(access_token|refresh_token|client_secret|password|authorization|cookie|code)([\s\"']*[:=][\s\"']*)[^\s,}\"']+", r"\1\2[REDACTED]", message)
        # Native OAuthlib creates 30-character random values, including login
        # hook tokens that the outer HTTP runner has not yet learned.
        opaque_redactions = 0
        def redact_opaque(match):
            nonlocal opaque_redactions
            if match[0] == "AMBISGIS_GEONODE_LOG_CAPTURE_CONTROL":
                return match[0]
            opaque_redactions += 1
            return "[REDACTED OPAQUE VALUE]"
        message = re.sub(r"[A-Za-z0-9_-]{30,}", redact_opaque, message)
        result = {"event": "application_log", "logger": record.name, "level": record.levelname, "message": message, "source_diagnostic_redactions": known_redactions,
                  "source_credential_field_redactions": auth_redactions + field_redactions,
                  "source_private_key_redactions": private_key_redactions,
                  "source_opaque_value_redactions": opaque_redactions,
                  "redaction_count_scope": "Known secret occurrences and credential/PEM pattern matches; opaque candidates may be nonsecret identifiers",
                  "capture_scope": "WARNING and above message text; exception class only; not a full DEBUG logging audit"}
        if record.exc_info and record.exc_info[0]:
            result["exception_type"] = record.exc_info[0].__name__
        return json.dumps(result)


def strict_verifier_options(config, source):
    enabled = config.get("strict_verifier", False)
    supported = hasattr(source, "OAUTH2_BACKEND_TOKENINFO_STRICT")
    if enabled and not supported:
        raise ValueError("Strict verifier requires a source build explicitly supporting OAUTH2_BACKEND_TOKENINFO_STRICT")
    if supported and type(source.OAUTH2_BACKEND_TOKENINFO_STRICT) is not bool:
        raise ValueError("Owned source strict verifier declaration must be a boolean")
    return {"OAUTH2_BACKEND_TOKENINFO_STRICT": enabled} if supported else {}


def owned_settings(config, runtime=False):
    os.environ.update(source_environment(config, runtime))
    source = importlib.import_module("geonode.settings")
    result = {key: value for key, value in vars(source).items() if key.isupper()}
    result.update(strict_verifier_options(config, source))
    if config.get("strict_roles"):
        if not hasattr(source, "OAUTH2_ROLE_SERVICE_STRICT"):
            raise ValueError("Strict roles require rebuilt owned source support")
        result.update(OAUTH2_ROLE_SERVICE_STRICT=True,
                      OAUTH2_ROLE_SERVICE_USERNAME=config["role_service_username"],
                      OAUTH2_ROLE_SERVICE_API_KEY=config["role_service_api_key"])
    key = config.get("oidc_rsa_private_key")
    if not key:
        keypath = Path(config["oidc_rsa_private_key_file"])
        metadata = keypath.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_uid != os.getuid():
            raise ValueError("OIDC signing key must be an owner-only regular file")
        key = keypath.read_text()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    private_key = serialization.load_pem_private_key(key.encode(), password=None)
    if not isinstance(private_key, RSAPrivateKey) or private_key.key_size < 2048:
        raise ValueError("OIDC signing key must be RSA with at least 2048 bits")
    if key.strip() == source.OAUTH2_PROVIDER["OIDC_RSA_PRIVATE_KEY"].strip():
        raise ValueError("The inherited sample OIDC key cannot be used")
    output = Path(config["output"])
    result.update({
        "ROOT_URLCONF": "geonode.urls",
        "SECRET_KEY": config["secret_key"],
        "DEBUG": False,
        "CACHES": {alias: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": f"fixture-{alias}"}
                   for alias in ("default", "services", "memcached")},
        "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "MEDIA_ROOT": str(output / "media"),
        "STATIC_ROOT": str(output / "static"),
        "UPLOAD_ROOT": str(output / "uploads"),
        "LOGGING": {
            "version": 1,
            "disable_existing_loggers": True,
            "formatters": {"safe": {"()": "fixture_settings.SafeApplicationLog"}},
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "safe"}},
            "root": {"handlers": ["console"], "level": "WARNING"},
            "loggers": {name: {"handlers": ["console"], "level": "WARNING", "propagate": False}
                        for name in ("django", "geonode", "oauthlib", "oauth2_provider", "celery")},
        },
    })
    result["OAUTH2_PROVIDER"] = dict(source.OAUTH2_PROVIDER, OIDC_RSA_PRIVATE_KEY=key, PKCE_REQUIRED=True)
    # Explicit whitelist avoids the source environment parser treating IPv6 ':' as a delimiter.
    result["AUTH_IP_WHITELIST"] = ["127.0.0.1", "::1"]
    return result


if __name__ == "fixture_settings" and os.environ.get("AMBISGIS_GEONODE_CONFIG"):
    globals().update(owned_settings(
        load_config(os.environ["AMBISGIS_GEONODE_CONFIG"]),
        runtime=os.environ.get("AMBISGIS_GEONODE_RUNTIME") == "1",
    ))
