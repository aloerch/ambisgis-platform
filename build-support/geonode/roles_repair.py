"""Guarded opt-in role endpoint repair, layered on the strict tokeninfo source.

This transforms exact owned source before a wheel rebuild. Legacy endpoint
behavior remains the default. No installed package is modified by this recipe.
"""
from pathlib import Path
import hashlib

import verifier_repair

SOURCE_COMMIT = verifier_repair.SOURCE_COMMIT
SETTING = 'OAUTH2_ROLE_SERVICE_STRICT'
BASELINE = dict(verifier_repair.REPAIRED_EXISTING)
HELPER_PATH = 'geonode/api/backend_roles.py'
TEST_PATH = 'geonode/api/test_backend_roles.py'
HELPER_SOURCE = '''"""Explicit authenticated read-only role authority for the owned GeoServer.

No session, OAuth token, email alias or untrusted role field supplies membership.
Canonical lowercase group names are the only ordinary role source. The reserved
admin group is synthetic and follows active Profile.is_superuser exclusively.
"""
from functools import wraps
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.urls import Resolver404, resolve
from django.utils.crypto import constant_time_compare

GROUP = re.compile(r"[a-z][a-z0-9_-]{0,149}\\Z", re.ASCII)
USERNAME = re.compile(r"[A-Za-z0-9_.@+-]{1,150}\\Z", re.ASCII)
RESERVED = frozenset(("admin", "administrator", "group_admin", "group-admin", "authenticated", "anonymous", "any", "root"))
REQUIRED_PERMISSIONS = frozenset(("people.view_profile", "auth.view_group"))


def is_strict_role_request(request):
    if not getattr(settings, "OAUTH2_ROLE_SERVICE_STRICT", False):
        return False
    try:
        match = resolve(request.path_info)
    except Resolver404:
        return False
    from geonode.api.views import roles, users, admin_role
    return match.func in (roles, users, admin_role)


def backend_role_service(kind):
    def decorate(view):
        from geonode.decorators import superuser_or_apiauth
        legacy = superuser_or_apiauth()(view)
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if getattr(settings, "OAUTH2_ROLE_SERVICE_STRICT", False):
                return strict_role_response(request, kind)
            return legacy(request, *args, **kwargs)
        return wrapped
    return decorate


def _response(value, status=200):
    response = JsonResponse(value, status=status)
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    if status == 405:
        response["Allow"] = "GET"
    return response


def _service_authenticated(request):
    username = getattr(settings, "OAUTH2_ROLE_SERVICE_USERNAME", "")
    key = getattr(settings, "OAUTH2_ROLE_SERVICE_API_KEY", "")
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not isinstance(username, str) or not USERNAME.fullmatch(username):
        return False
    if not isinstance(key, str) or not key or len(key) > 4096 or any(char.isspace() for char in key):
        return False
    if not isinstance(header, str) or len(header) > 4103:
        return False
    parts = header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "apikey" or not constant_time_compare(parts[1], key):
        return False
    # A fresh model instance avoids Django's per-instance permission cache. Key
    # possession alone cannot bypass identity disable/deletion/permission removal.
    user = get_user_model().objects.filter(username=username, is_active=True).first()
    if user is None or user.is_staff or user.is_superuser:
        return False
    return user.has_perms(REQUIRED_PERMISSIONS)


def _safe_group(name):
    return bool(isinstance(name, str) and GROUP.fullmatch(name)
                and name not in RESERVED and not name.startswith("role_"))


def _groups(user):
    groups = sorted(name for name in user.groups.values_list("name", flat=True) if _safe_group(name))
    if user.is_superuser:
        groups.append("admin")
    return groups


def strict_role_response(request, kind):
    if not _service_authenticated(request):
        return _response({"error": "invalid_service_credentials"}, 401)
    if request.method != "GET":
        return _response({"error": "invalid_request"}, 405)
    path = request.path_info
    if request.GET:
        return _response({"error": "invalid_request"}, 400)
    if kind == "roles" and path in ("/api/roles", "/api/roles/"):
        groups = sorted(name for name in Group.objects.values_list("name", flat=True) if _safe_group(name))
        return _response({"groups": groups + ["admin"]})
    if kind == "admin" and path in ("/api/adminRole", "/api/adminRole/"):
        return _response({"adminRole": "admin"})
    if kind != "users" or (path not in ("/api/users", "/api/users/") and not path.startswith("/api/users/")):
        return _response({"error": "invalid_request"}, 404)
    username = path[len("/api/users/"):] if path.startswith("/api/users/") else ""
    if username and not USERNAME.fullmatch(username):
        return _response({"error": "invalid_request"}, 400)
    users = get_user_model().objects.filter(is_active=True).order_by("username")
    if username:
        users = users.filter(username=username)
    return _response({"users": [{"username": user.username, "groups": _groups(user)}
                               for user in users if USERNAME.fullmatch(user.username)]})
'''


def sha(value):
    return hashlib.sha256(value).hexdigest()


def transform_existing(relative, data):
    if relative not in BASELINE or sha(data) != BASELINE[relative]:
        raise ValueError('GeoNode role repair requires exact strict-verifier source: ' + relative)
    if relative == 'geonode/api/views.py':
        anchor = b'from ..decorators import superuser_or_apiauth\n'
        if data.count(anchor) != 1:
            raise ValueError('GeoNode role import anchor mismatch')
        data = data.replace(anchor, anchor + b'from .backend_roles import backend_role_service\n')
        for view, kind in ((b'roles', b'roles'), (b'users', b'users'), (b'admin_role', b'admin')):
            before = b'@superuser_or_apiauth()\ndef ' + view + b'(request):\n'
            after = b'@backend_role_service("' + kind + b'")\ndef ' + view + b'(request):\n'
            if data.count(before) != 1:
                raise ValueError('GeoNode role view anchor mismatch')
            data = data.replace(before, after)
        return data
    if relative == 'geonode/security/middleware.py':
        anchor = b'from geonode.api.backend_tokeninfo import is_strict_backend_request\n'
        check = b'if is_strict_backend_request(request):'
        if data.count(anchor) != 1 or data.count(check) != 2:
            raise ValueError('GeoNode role middleware anchor mismatch')
        return data.replace(anchor, anchor + b'from geonode.api.backend_roles import is_strict_role_request\n').replace(
            check, b'if is_strict_backend_request(request) or is_strict_role_request(request):')
    anchor = b'OAUTH2_BACKEND_TOKENINFO_STRICT = False\n'
    if data.count(anchor) != 1:
        raise ValueError('GeoNode role setting anchor mismatch')
    return data.replace(anchor, anchor + b'\n# Explicit role-service opt-in; credentials are separate from tokeninfo.\n'
                        b'OAUTH2_ROLE_SERVICE_STRICT = False\n'
                        b'OAUTH2_ROLE_SERVICE_USERNAME = ""\n'
                        b'OAUTH2_ROLE_SERVICE_API_KEY = ""\n')


def expected_files():
    # The existing-file digests are generated from exact checked-in owned source
    # by the recipe author, never accepted dynamically from the build tree.
    return dict(REPAIRED_EXISTING, **{HELPER_PATH: sha(HELPER_SOURCE.encode()),
                TEST_PATH: sha(Path(__file__).with_name('roles_tests.py').read_bytes())})


REPAIRED_EXISTING = {'geonode/security/middleware.py': '8ef5c0ef7f913fde289b13f7ac1d4549bbaddd9c43dc3dd4b196866ef21b1b5e', 'geonode/api/views.py': 'e8b6a906c85f25cb6e4377aa1796a46398e4c8669c460f77cccd88cec2131c3c', 'geonode/settings.py': '143847a418454e97a1f6af72fba43624431815a5285af31971f0e8f5928a5537'}


def apply(source_root):
    root = Path(source_root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('GeoNode role repair requires a regular source directory')
    expected = expected_files()
    paths = {relative: verifier_repair._path(root, relative) for relative in expected}
    current = {relative: sha(path.read_bytes()) if path.is_file() else None for relative, path in paths.items()}
    repeated = current == expected
    if not repeated:
        for relative, digest in BASELINE.items():
            if current[relative] != digest:
                raise ValueError('GeoNode role repair baseline mismatch: ' + relative)
        if any(paths[name].exists() for name in (HELPER_PATH, TEST_PATH)):
            raise ValueError('GeoNode role helper/test collision')
        outputs = {relative: transform_existing(relative, paths[relative].read_bytes()) for relative in BASELINE}
        outputs.update({HELPER_PATH: HELPER_SOURCE.encode(), TEST_PATH: Path(__file__).with_name('roles_tests.py').read_bytes()})
        if {relative: sha(data) for relative, data in outputs.items()} != expected:
            raise ValueError('GeoNode role repair output hash guard failed')
        for relative, data in outputs.items():
            paths[relative].write_bytes(data)
    if any(not path.is_file() or sha(path.read_bytes()) != expected[relative] for relative, path in paths.items()):
        raise ValueError('GeoNode role repair readback mismatch')
    return {'schema_version': 1, 'repair': 'geonode-strict-backend-roles', 'source_commit': SOURCE_COMMIT,
            'setting': SETTING, 'default': False, 'applied': True, 'already_applied': repeated,
            'authority': 'Active exact Profile usernames, canonical groups, and is_superuser; no email alias or session fallback.',
            'service_authentication': 'Separate ApiKey plus active nonstaff nonsuperuser configured Profile with people.view_profile and auth.view_group.',
            'middleware_scope': 'Only the three exact resolved role callbacks bypass user header parsing and session expiry in strict role mode.',
            'files': [{'path': name, 'before_sha256': BASELINE.get(name), 'after_sha256': digest}
                      for name, digest in sorted(expected.items())]}
