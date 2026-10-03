#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Finite private acceptance session using the catalog's native object grants.

No public endpoint, caller-selected object/principal/permission, migration role,
token change, raw SQL or arbitrary program input. A finally block restores the
initially absent diagnostic viewer grant and verifies the entire policy snapshot.
"""
import hashlib
import json
import sys
import uuid


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def fingerprint(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def action(line):
    if not line or len(line) > 128: raise ValueError('bounded action required')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate action field')
            result[key] = value
        return result
    value = json.loads(line, object_pairs_hook=pairs)
    if not isinstance(value, dict) or set(value) != {'action'} or value['action'] not in ('grant', 'revoke', 'finish'):
        raise ValueError('fixed action required')
    return value['action']


class NativePolicy:
    def __init__(self):
        from ambisgis_development.common import inputs, read, DATA, SAMPLE
        from ambisgis_development.catalog import setup
        product, _ = inputs()
        expected = str(uuid.uuid5(uuid.UUID(product['install_id']), 'diagnostic-private-points'))
        if read(DATA/'installation.json') != {'schema_version': 1, 'install_id': product['install_id'], 'purpose': 'developer-catalog'}:
            raise ValueError('catalog installation marker differs')
        if read(DATA/'initialized.json') != {'install_id': product['install_id'], 'resource_uuid': expected}:
            raise ValueError('catalog initialized identity differs')
        setup('catalog')
        from django.conf import settings
        if settings.DATABASES['default']['USER'] != 'ambisgis_catalog_app':
            raise ValueError('serving catalog role required')
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from geonode.base.models import ResourceBase
        from guardian.utils import get_anonymous_user
        self.resource = ResourceBase.objects.get(uuid=expected, alternate=SAMPLE)
        self.viewer = get_user_model().objects.get(username=product['viewer'])
        owner = get_user_model().objects.get(username=product['owner'])
        self.anonymous = get_anonymous_user()
        if (self.resource.owner_id != owner.pk or self.viewer.pk in (owner.pk, self.anonymous.pk)
                or ResourceBase.objects.filter(alternate=SAMPLE).count() != 1):
            raise ValueError('diagnostic native binding differs')
        self.content_type = ContentType.objects.get(app_label=ResourceBase._meta.app_label, model=ResourceBase._meta.model_name)
        self.permission = Permission.objects.get(content_type=self.content_type, codename='view_resourcebase')
        self.identity = {'install_id': product['install_id'], 'resource_uuid': expected,
                         'resource_pk': self.resource.pk, 'viewer_pk': self.viewer.pk, 'owner_pk': owner.pk}
        self.baseline = self.snapshot()
        if (not self.viewer.is_active or self.viewer.is_superuser or self.viewer.is_staff
                or self.readable(self.viewer) or self.readable(self.anonymous)
                or [self.viewer.pk, self.permission.pk] in self.baseline['user_grants']):
            raise ValueError('viewer must initially be an ungranted outsider')
        self.granted = False
        self.touched = False

    def readable(self, user):
        from guardian.core import ObjectPermissionChecker
        return ObjectPermissionChecker(user).has_perm('view_resourcebase', self.resource)

    def snapshot(self):
        from guardian.models import UserObjectPermission, GroupObjectPermission
        from django.contrib.auth.models import Group
        self.resource.refresh_from_db(); self.viewer.refresh_from_db(); self.anonymous.refresh_from_db()
        selector = {'object_pk': str(self.resource.pk), 'content_type': self.content_type}
        def principal(user):
            return {'pk': user.pk, 'username': user.username, 'active': user.is_active,
                    'staff': user.is_staff, 'superuser': user.is_superuser,
                    'groups': sorted(user.groups.values_list('pk', flat=True)),
                    'global_permissions': sorted(user.user_permissions.values_list('pk', flat=True))}
        viewer, anonymous = principal(self.viewer), principal(self.anonymous)
        group_grants = sorted([list(row) for row in GroupObjectPermission.objects.filter(**selector).values_list('group_id', 'permission_id')])
        groups = set(viewer['groups']) | set(anonymous['groups']) | {row[0] for row in group_grants}
        group_globals = [[group.pk, sorted(group.permissions.values_list('pk', flat=True))]
                         for group in Group.objects.filter(pk__in=groups).order_by('pk')]
        return {'resource': {'pk': self.resource.pk, 'uuid': str(self.resource.uuid), 'alternate': self.resource.alternate,
                             'owner_pk': self.resource.owner_id, 'published': self.resource.is_published, 'approved': self.resource.is_approved},
                'viewer': viewer, 'anonymous': anonymous, 'group_global_permissions': group_globals,
                'user_grants': sorted([list(row) for row in UserObjectPermission.objects.filter(**selector).values_list('user_id', 'permission_id')]),
                'group_grants': group_grants}

    def expected(self):
        value = json.loads(encoded(self.baseline))
        if self.granted:
            value['user_grants'].append([self.viewer.pk, self.permission.pk]); value['user_grants'].sort()
        return value

    def change(self, grant):
        from django.db import transaction
        from guardian.shortcuts import assign_perm, remove_perm
        with transaction.atomic():
            if self.snapshot() != self.expected(): raise ValueError('native policy changed outside this session')
            self.touched = True
            (assign_perm if grant else remove_perm)('view_resourcebase', self.viewer, self.resource)
        self.granted = grant
        if self.snapshot() != self.expected() or self.readable(self.viewer) is not grant:
            raise ValueError('native item grant did not commit as expected')
        return {'granted': grant, 'policy_sha256': fingerprint(self.snapshot())}

    def restore(self):
        from django.db import transaction
        from guardian.shortcuts import remove_perm
        # Remove only this initially absent tuple. Never replace whole policy
        # tables or overwrite any unrelated grant, group or principal change.
        if self.touched:
            with transaction.atomic():
                remove_perm('view_resourcebase', self.viewer, self.resource)
        actual = self.snapshot()
        complete = actual == self.baseline and not self.readable(self.viewer) and not self.readable(self.anonymous)
        return {'complete': complete, 'before_sha256': fingerprint(self.baseline), 'after_sha256': fingerprint(actual)}


def run(reader, writer, factory=NativePolicy):
    policy = None; phase = 0; code = 0
    def emit(value): writer.write(encoded(value)+'\n'); writer.flush()
    try:
        policy = factory()
        emit({'event': 'ready', 'identity': policy.identity, 'policy_sha256': fingerprint(policy.baseline)})
        while True:
            line = reader.readline(129)
            if not line: raise ValueError('session ended before finish')
            requested = action(line)
            if requested == 'finish': break
            if phase >= 3 or requested != ('grant', 'revoke', 'grant')[phase]:
                raise ValueError('unexpected permission phase')
            facts = policy.change(requested == 'grant'); phase += 1
            emit({'event': requested, **facts})
    except Exception as error:
        code = 1
        emit({'event': 'failed', 'error_type': type(error).__name__})
    finally:
        cleanup = {'complete': policy is None, 'mutation_started': policy is not None}
        if policy is not None:
            try: cleanup = policy.restore()
            except Exception as error: cleanup = {'complete': False, 'error_type': type(error).__name__}
        emit({'event': 'cleanup', 'sequence_complete': phase == 3, **cleanup})
        if not cleanup['complete']: code = 1
    return code


if __name__ == '__main__':
    if len(sys.argv) != 1: raise SystemExit('no program arguments supported')
    raise SystemExit(run(sys.stdin, sys.stdout))
