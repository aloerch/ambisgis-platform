"""Persistent native catalog initialization and bounded product operations."""
from datetime import timedelta
import hmac
import json
import os
from pathlib import Path
import re
import uuid

from .common import DATA, SAMPLE, inputs, read, response, save, serve
from .startup_diagnostics import stage as startup_stage


def setup(role):
    os.environ['AMBISGIS_SERVICE_ROLE'] = role
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ambisgis_development.catalog_settings'
    from .catalog_compat import activate_distutils
    activate_distutils()
    import django
    django.setup()


def initialize():
    with startup_stage('catalog_input'):
        product, secrets = inputs()
    with startup_stage('catalog_identity'):
        marker = DATA / 'installation.json'
        identity = {'schema_version': 1, 'install_id': product['install_id'], 'purpose': 'developer-catalog'}
        if marker.exists():
            if read(marker) != identity:
                raise ValueError('catalog data belongs to another installation')
        else:
            if any(DATA.iterdir()):
                raise ValueError('will not adopt an unmarked catalog volume')
            save(marker, identity)
        keypath = DATA / 'oidc-key.pem'
        if not keypath.exists():
            if (DATA / 'initialized.json').exists():
                raise ValueError('persistent issuer key is missing; do not silently rotate it')
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
            value = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            fd = os.open(keypath, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as output: output.write(value)
        if keypath.is_symlink() or keypath.stat().st_mode & 0o077:
            raise ValueError('issuer signing key must be private')
    with startup_stage('catalog_setup'):
        setup('catalog-init')
    with startup_stage('catalog_models'):
        from django.core.management import call_command
        from django.db import connection, transaction
        from django.contrib.auth import get_user_model
        from django.utils.crypto import constant_time_compare
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.sites.models import Site
        from django.utils import timezone
        from allauth.account.models import EmailAddress
        from geonode.base.models import ResourceBase
        from guardian.models import UserObjectPermission, GroupObjectPermission
        from guardian.shortcuts import assign_perm
        from oauth2_provider.models import get_application_model, get_access_token_model
    with startup_stage('catalog_lock'):
        lock_key = str(uuid.UUID(product['install_id']).int & ((1 << 63) - 1))
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [lock_key])
            if not cursor.fetchone()[0]: raise ValueError('another catalog initialization is running')
    try:
        with startup_stage('catalog_migrations'):
            call_command('migrate', interactive=False, verbosity=0)
        with startup_stage('catalog_bootstrap'):
            User, Application = get_user_model(), get_application_model()
            resource_uuid = str(uuid.uuid5(uuid.UUID(product['install_id']), 'diagnostic-private-points'))
            with transaction.atomic():
                app, created = Application.objects.get_or_create(client_id=secrets['oauth_client'], defaults={
                    'name': 'AmbisGIS development', 'client_secret': secrets['oauth_secret'],
                    'client_type': Application.CLIENT_CONFIDENTIAL, 'authorization_grant_type': Application.GRANT_AUTHORIZATION_CODE,
                    'redirect_uris': product['public_origin'] + '/oauth/callback', 'skip_authorization': False})
                if (app.name != 'AmbisGIS development' or app.redirect_uris != product['public_origin'] + '/oauth/callback'
                        or app.skip_authorization or app.client_type != Application.CLIENT_CONFIDENTIAL
                        or app.authorization_grant_type != Application.GRANT_AUTHORIZATION_CODE
                        or not constant_time_compare(secrets['oauth_secret'], app.client_secret)):
                    raise ValueError('conflicting native OAuth application')
                users = {}
                for role in ('owner', 'viewer'):
                    name = product[role]
                    user, created = User.objects.get_or_create(username=name, defaults={
                        'email': name + '@example.invalid', 'is_active': True, 'is_staff': False, 'is_superuser': False})
                    if created:
                        user.set_password(secrets[role + '_password']); user.save(update_fields=['password'])
                        EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={'verified': True, 'primary': True})
                    if user.is_superuser or user.is_staff:
                        raise ValueError('developer sample principals must not be administrators')
                    users[role] = user
                health, created = User.objects.get_or_create(username='installation-health', defaults={
                    'email': 'installation-health@example.invalid', 'is_active': True, 'is_staff': False, 'is_superuser': False})
                if created:
                    health.set_unusable_password(); health.save(update_fields=['password'])
                if health.has_usable_password() or health.is_staff or health.is_superuser:
                    raise ValueError('health identity must be a noninteractive reader')
                if app.user_id is None:
                    app.user = users['owner']; app.save(update_fields=['user'])
                elif app.user_id != users['owner'].pk:
                    raise ValueError('native OAuth application belongs to another principal')
                resource, created = ResourceBase.objects.get_or_create(uuid=resource_uuid, defaults={
                    'alternate': SAMPLE, 'title': 'Private installation sample', 'abstract': 'Synthetic unmanaged diagnostic data; not a managed branch layer.',
                    'owner': users['owner'], 'is_published': True, 'is_approved': True, 'resource_type': 'dataset'})
                if resource.alternate != SAMPLE or resource.owner_id != users['owner'].pk or ResourceBase.objects.filter(alternate=SAMPLE).count() != 1:
                    raise ValueError('conflicting diagnostic catalog binding')
                if created:
                    content_type = ContentType.objects.get_for_model(resource)
                    UserObjectPermission.objects.filter(object_pk=str(resource.pk), content_type=content_type).delete()
                    GroupObjectPermission.objects.filter(object_pk=str(resource.pk), content_type=content_type).delete()
                    assign_perm('view_resourcebase', users['owner'], resource)
                    assign_perm('change_resourcebase', users['owner'], resource)
                    assign_perm('view_resourcebase', health, resource)
                # A generated machine credential is restricted by native guardian to
                # this sample only. User-facing acceptance uses real HTTP OAuth grants.
                token, created = get_access_token_model().objects.get_or_create(token=secrets['health_token'], defaults={
                    'user': health, 'application': app, 'scope': 'read', 'expires': timezone.now() + timedelta(days=365)})
                if token.user_id != health.pk or token.application_id != app.pk or token.scope != 'read':
                    raise ValueError('health token has a conflicting native binding')
                Site.objects.update_or_create(id=1, defaults={'domain': product['public_origin'].split('//', 1)[1], 'name': 'AmbisGIS development'})
        # Static assets and browser sessions are persistent; repeated init does
        # not reset user passwords, resource metadata, grants or issued tokens.
        with startup_stage('catalog_static'):
            call_command('collectstatic', interactive=False, verbosity=0)
            if not (DATA / 'initialized.json').exists():
                save(DATA / 'initialized.json', {'install_id': product['install_id'], 'resource_uuid': resource_uuid})
        print(json.dumps({'event': 'catalog_initialized', 'install_id': product['install_id'], 'resource_uuid': resource_uuid}), flush=True)
    finally:
        with startup_stage('catalog_unlock'):
            with connection.cursor() as cursor: cursor.execute('SELECT pg_advisory_unlock(%s)', [lock_key])


def principal(authorization, client_id):
    if not re.fullmatch(r'Bearer [A-Za-z0-9._~-]{20,512}', authorization or ''):
        return None
    from django.utils import timezone
    from oauth2_provider.models import get_access_token_model
    return get_access_token_model().objects.select_related('user').filter(
        token=authorization[7:], application__client_id=client_id,
        expires__gt=timezone.now(), user__is_active=True).first()


def health():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from geonode.base.models import ResourceBase
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")
        row = cursor.fetchone()
        if row[0] != 'ambisgis_catalog_app' or any(row[1:]): return False
        cursor.execute("SELECT ST_SRID(ST_SetSRID(ST_MakePoint(1,2),4326))=4326")
        if cursor.fetchone()[0] is not True: return False
        cursor.execute("SELECT count(*) FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)")
        if cursor.fetchone()[0]: return False
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()): return False
    return ResourceBase.objects.filter(alternate=SAMPLE, is_published=True, is_approved=True).count() == 1


def application():
    product, secrets = inputs()
    setup('catalog')
    from django.core.wsgi import get_wsgi_application
    from django.db import close_old_connections, transaction
    from geonode.base.models import ResourceBase
    from guardian.core import ObjectPermissionChecker
    from ambisgis_policy.catalog import allowed, wrap
    native = wrap(get_wsgi_application(), service_key=secrets['policy_key'], application_id=secrets['oauth_client'])

    def handle(env, start):
        close_old_connections()
        try:
            path, method = env.get('PATH_INFO'), env.get('REQUEST_METHOD')
            if path == '/internal/health' and method == 'GET' and not env.get('QUERY_STRING'):
                if not hmac.compare_digest(env.get('HTTP_X_AMBISGIS_POLICY_KEY', ''), secrets['policy_key']):
                    return response(start, 403)
                ready = health()
                return response(start, 200 if ready else 503, {'install_id': product['install_id'], 'catalog': ready, 'database': ready})
            if path == '/api/v1/installation/sample' and not env.get('QUERY_STRING'):
                token = principal(env.get('HTTP_AUTHORIZATION'), secrets['oauth_client'])
                if token is None or 'read' not in token.scope.split() or not allowed(SAMPLE, env.get('HTTP_AUTHORIZATION'), secrets['oauth_client']):
                    return response(start, 403)
                resource = ResourceBase.objects.get(alternate=SAMPLE)
                if method == 'PATCH':
                    if 'write' not in token.scope.split() or not ObjectPermissionChecker(token.user).has_perm('change_resourcebase', resource):
                        return response(start, 403)
                    if env.get('CONTENT_TYPE', '').split(';')[0] != 'application/json': return response(start, 415)
                    size = int(env.get('CONTENT_LENGTH') or '0')
                    if not 1 <= size <= 4096: return response(start, 400)
                    value = json.loads(env['wsgi.input'].read(size))
                    if set(value) != {'title'} or not isinstance(value['title'], str) or not 1 <= len(value['title']) <= 200:
                        return response(start, 400)
                    with transaction.atomic():
                        resource.title = value['title']; resource.save(update_fields=['title'])
                elif method != 'GET': return response(start, 405)
                return response(start, 200, {'id': resource.uuid, 'title': resource.title, 'synthetic': True, 'managed': False})
            if path == '/internal/policy/read' or path in ('/account/login/', '/account/logout/', '/o/authorize/', '/o/token/', '/o/revoke_token/', '/api/o/v4/tokeninfo'):
                return native(env, start)
            return response(start, 404)
        except Exception:
            return response(start, 503, {'error': 'Catalog dependency unavailable.'})
        finally:
            close_old_connections()
    return handle


def main():
    if not (DATA / 'initialized.json').is_file():
        raise ValueError('catalog-init must finish before serving')
    serve(application())
