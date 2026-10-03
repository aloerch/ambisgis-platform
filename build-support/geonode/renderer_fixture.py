"""Additional synthetic native catalog objects; same FND03 authority/tables."""
import argparse
import json
import os
from pathlib import Path


def main(config_path):
    os.environ.update(AMBISGIS_GEONODE_CONFIG=str(config_path), AMBISGIS_GEONODE_RUNTIME='1', DJANGO_SETTINGS_MODULE='fixture_settings')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from geonode.base.models import ResourceBase
    from guardian.models import UserObjectPermission, GroupObjectPermission
    from guardian.shortcuts import assign_perm
    from guardian.utils import get_anonymous_user
    with transaction.atomic():
        owner = get_user_model().objects.get(username='fixture-reader')
        for name, public in [('rich_points', False), ('parcels', True), ('elevation', False)]:
            resource = ResourceBase.objects.create(title='Synthetic ' + name, alternate='fixture:' + name,
                owner=owner, is_published=True, is_approved=True, resource_type='dataset')
            content_type = ContentType.objects.get_for_model(resource)
            UserObjectPermission.objects.filter(object_pk=str(resource.pk), content_type=content_type).delete()
            GroupObjectPermission.objects.filter(object_pk=str(resource.pk), content_type=content_type).delete()
            assign_perm('view_resourcebase', owner, resource)
            if public: assign_perm('view_resourcebase', get_anonymous_user(), resource)
    print(json.dumps({'event': 'renderer_catalog_committed'}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--config', type=Path, required=True)
    main(p.parse_args().config)
