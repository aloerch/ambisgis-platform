"""Persistent catalog settings generated from the sole product configuration.

Native GeoNode models, migrations, signals and OAuth issuer remain in use.
Only the bounded developer routes are exposed; asynchronous publication/jobs
are not enabled by this installation foundation.
"""
import importlib
import logging
import os
import re
from urllib.parse import quote

from .common import DATA, inputs

PRODUCT, PRIVATE = inputs()
MIGRATING = os.environ.get('AMBISGIS_SERVICE_ROLE') == 'catalog-init'
DATABASE_ROLE = 'ambisgis_catalog_owner' if MIGRATING else 'ambisgis_catalog_app'
PASSWORD = PRIVATE['catalog_migrator' if MIGRATING else 'catalog_runtime']
os.environ.update({
    'DATABASE_URL': 'postgis://' + DATABASE_ROLE + ':' + quote(PASSWORD, safe='') + '@database:5432/ambisgis_catalog',
    'DEFAULT_BACKEND_DATASTORE': '', 'SECRET_KEY': PRIVATE['django_key'],
    'SITEURL': PRODUCT['public_origin'] + '/', 'SITE_HOST_SCHEMA': 'http',
    'SITE_HOST_NAME': '127.0.0.1', 'SITE_HOST_PORT': str(PRODUCT['public_origin'].rsplit(':', 1)[1]),
    'GEOSERVER_LOCATION': PRODUCT['engine_origin'] + '/geoserver/',
    'GEOSERVER_PUBLIC_LOCATION': PRODUCT['public_origin'] + '/engine-disabled/',
    'GEOSERVER_WEB_UI_LOCATION': PRODUCT['public_origin'] + '/engine-disabled/',
    'GEOSERVER_ADMIN_USER': 'unavailable-in-serving-role',
    'GEOSERVER_ADMIN_PASSWORD': 'unavailable-in-serving-role',
    'GEOSERVER_FACTORY_PASSWORD': 'unavailable-in-serving-role',
    'OAUTH2_API_KEY': PRIVATE['policy_key'], 'OAUTH2_DEFAULT_BACKEND_CLIENT_NAME': 'AmbisGIS development',
    'DEBUG': 'False', 'MEMCACHED_ENABLED': 'False', 'ASYNC_SIGNALS': 'False',
    'UPDATE_RESOURCE_LINKS_AT_MIGRATE': 'False', 'EMAIL_ENABLE': 'False',
    'DJANGO_EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
    'SESSION_COOKIE_SECURE': 'False', 'CSRF_COOKIE_SECURE': 'False', 'SECURE_SSL_REDIRECT': 'False',
})
SOURCE = importlib.import_module('geonode.settings')
globals().update({key: value for key, value in vars(SOURCE).items() if key.isupper()})
ROOT_URLCONF = 'geonode.urls'
SECRET_KEY = PRIVATE['django_key']
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'catalog']
CSRF_TRUSTED_ORIGINS = [PRODUCT['public_origin']]
USE_X_FORWARDED_HOST = False
SECURE_PROXY_SSL_HEADER = None
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
MEDIA_ROOT = str(DATA / 'media')
STATIC_ROOT = str(DATA / 'static')
UPLOAD_ROOT = str(DATA / 'uploads')
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
# Native ASYNC_SIGNALS=False executes catalog hooks synchronously. There is no
# task worker/queue API in this profile and no durable-jobs claim. Do not inherit
# an unused localhost Redis result service from the source defaults.
CELERY_RESULT_BACKEND = None
OAUTH2_BACKEND_TOKENINFO_STRICT = True
CACHES = {alias: {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'ambisgis-' + alias}
          for alias in ('default', 'services', 'memcached')}
OAUTH2_PROVIDER = dict(SOURCE.OAUTH2_PROVIDER, OIDC_RSA_PRIVATE_KEY=(DATA / 'oidc-key.pem').read_text(), PKCE_REQUIRED=True)


class Redacted(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        for value in PRIVATE.values():
            message = message.replace(value, '[redacted]')
        message = re.sub(r'(?i)(Bearer|Basic)\s+[^\s\"<>]+', r'\1 [redacted]', message)
        message = re.sub(r'(?i)(password|access_token|refresh_token|client_secret|authorization|cookie)([\s\"\x27]*[:=][\s\"\x27]*)[^\s,}\"\x27]+', r'\1\2[redacted]', message)
        # Exception locals/traceback text can contain DSNs or authentication forms.
        import json
        return json.dumps({'event': 'catalog_log', 'level': record.levelname,
                           'message': message, 'exception_type': record.exc_info[0].__name__ if record.exc_info else None})


LOGGING = {'version': 1, 'disable_existing_loggers': True,
           'formatters': {'redacted': {'()': Redacted}},
           'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'redacted'}},
           'root': {'handlers': ['console'], 'level': 'WARNING'},
           'loggers': {name: {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}
                       for name in ('django', 'geonode', 'oauthlib', 'oauth2_provider', 'celery')}}
