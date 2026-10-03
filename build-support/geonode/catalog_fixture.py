"""Synthetic catalog setup and committed native sharing mutations, never mocks."""
import argparse
import json
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('action', choices=('initialize', 'group-remove', 'group-add', 'public-revoke', 'public-restore', 'private-share', 'private-revoke', 'disable-reader', 'enable-reader', 'revoke-reader-tokens', 'gateway'))
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if not config.get('catalog_policy'):
        raise ValueError('explicit catalog policy fixture required')
    if args.action == 'gateway':
        from ambisgis_policy.gateway import application
        from manage_fixture import QuietRequestHandler, ThreadedWSGIServer
        from wsgiref.simple_server import make_server
        from urllib.parse import urlsplit
        engine = urlsplit(config['geoserver_url'])
        app = application(config['site_url'].rstrip('/'), f'http://127.0.0.1:{engine.port}', config['policy_key'])
        with make_server('127.0.0.1', config['gateway_port'], app, server_class=ThreadedWSGIServer, handler_class=QuietRequestHandler) as server:
            print(json.dumps({'event':'listening'}), flush=True)
            server.serve_forever()
        return
    os.environ.update(AMBISGIS_GEONODE_CONFIG=args.config, AMBISGIS_GEONODE_RUNTIME='1', DJANGO_SETTINGS_MODULE='fixture_settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from geonode.base.models import ResourceBase
    from guardian.shortcuts import assign_perm, remove_perm
    from guardian.models import UserObjectPermission, GroupObjectPermission
    from guardian.utils import get_anonymous_user
    from oauth2_provider.models import get_access_token_model
    reader = get_user_model().objects.get(username='fixture-reader')
    outsider = get_user_model().objects.get(username='fixture-outsider')
    group = Group.objects.get(name='fixture-readers')
    anonymous = get_anonymous_user()
    with transaction.atomic():
        if args.action == 'initialize':
            resources = {}
            for name, owner in (('public_points', reader), ('private_points', reader), ('group_points', outsider)):
                resource = ResourceBase.objects.create(title='Synthetic ' + name, alternate='fixture:' + name,
                    owner=owner, is_published=True, is_approved=True, resource_type='dataset')
                # Remove native defaults for these new synthetic objects only.
                content_type = ContentType.objects.get_for_model(resource)
                UserObjectPermission.objects.filter(object_pk=str(resource.pk), content_type=content_type).delete()
                GroupObjectPermission.objects.filter(object_pk=str(resource.pk), content_type=content_type).delete()
                assign_perm('view_resourcebase', owner, resource)
                resources[name] = resource
            assign_perm('view_resourcebase', anonymous, resources['public_points'])
            assign_perm('view_resourcebase', group, resources['group_points'])
        elif args.action in ('group-remove', 'group-add'):
            getattr(reader.groups, 'remove' if args.action == 'group-remove' else 'add')(group)
        elif args.action in ('public-revoke', 'public-restore'):
            resource = ResourceBase.objects.get(alternate='fixture:public_points')
            (remove_perm if args.action == 'public-revoke' else assign_perm)('view_resourcebase', anonymous, resource)
        elif args.action in ('private-share', 'private-revoke'):
            resource = ResourceBase.objects.get(alternate='fixture:private_points')
            (remove_perm if args.action == 'private-revoke' else assign_perm)('view_resourcebase', outsider, resource)
        elif args.action in ('disable-reader', 'enable-reader'):
            reader.is_active = args.action == 'enable-reader'
            reader.save(update_fields=['is_active'])
        else:
            get_access_token_model().objects.filter(user=reader).delete()
    print(json.dumps({'event':'catalog_committed', 'action':args.action, 'ack_monotonic_ns':time.monotonic_ns()}), flush=True)


if __name__ == '__main__':
    main()
