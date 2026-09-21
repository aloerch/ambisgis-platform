"""Exact-source repair for opt-in GeoNode backend token verification.

The retained 5.1.0 legacy tokeninfo endpoint is intentionally unchanged when the
new setting is False. In opted-in service fixtures, authentication depends on a
confidential application's own Basic credentials and token; a browser session
is neither client authentication nor an alternative token lookup.

This is source transformation before wheel build, never an installed-module
monkeypatch. Unknown, partially edited or symlinked source fails before writes.
"""
from pathlib import Path
import hashlib
import json

SOURCE_COMMIT = 'a1db97e81dfc26c16bb4ee1a5d2b408877af66c9'
SETTING = 'OAUTH2_BACKEND_TOKENINFO_STRICT'
BASELINE = {
    'geonode/api/views.py': '484d2abd190b568c72992cc1202e1d671b89a2ec249a2aaaa0741e1b00cf480c',
    'geonode/security/middleware.py': '5f6fc7a69be15bfa7a6dd68653a39f30ba63d9668cb9721c3a8d8309b85d830e',
    'geonode/settings.py': '652dea658029b136b393752cbaec676fdbf980619110ef293917c9d9a9b8ac75',
}
REPAIRED_EXISTING = {
    # Filled from the exact guarded source transformation, not an upstream revision.
    'geonode/security/middleware.py': 'aeb3ffa97702196d1bd1190dad1353ece007b44f83576aca39f33a6d6872125d',
    'geonode/api/views.py': '23a24a65657d3a8a56ba298e01520afc378edb8e12d5dabd9e1a1432158eeda2',
    'geonode/settings.py': '101c2f802877a62df4ee5e602f401609a68e839920e0587f0a4e7bf735d0c057',
}
HELPER_PATH = 'geonode/api/backend_tokeninfo.py'
TEST_PATH = 'geonode/api/test_backend_tokeninfo.py'
HELPER_SOURCE = '''"""Opt-in confidential-client verifier for the owned GeoServer backend.

This endpoint branch preserves the native milliseconds lifetime contract. It
never consults or mutates browser session identity, and never returns the token.
Selected django-oauth-toolkit 2.2.3.1 stores client_secret as a plain CharField;
this source repair is guarded together with that retained dependency selection.
"""
import base64
import binascii
import logging
from urllib.parse import unquote_plus

from django.conf import settings
from django.http import JsonResponse
from django.urls import Resolver404, resolve
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from oauth2_provider.models import get_access_token_model, get_application_model

logger = logging.getLogger(__name__)


def is_strict_backend_request(request):
    """Recognize only the actual selected view; no path-prefix authentication bypass."""
    if not getattr(settings, "OAUTH2_BACKEND_TOKENINFO_STRICT", False):
        return False
    try:
        match = resolve(request.path_info)
    except Resolver404:
        return False
    from geonode.api.views import verify_token
    return match.func is verify_token


def _response(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    if status == 401:
        response["WWW-Authenticate"] = 'Basic realm="GeoNode backend token verification"'
    if status == 405:
        response["Allow"] = "POST"
    return response


def _credentials(request):
    value = request.META.get("HTTP_AUTHORIZATION", "")
    if not isinstance(value, str) or len(value) > 8192:
        return None
    try:
        scheme, encoded = value.split(" ", 1)
        if scheme.lower() != "basic":
            return None
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        client_id, secret = decoded.split(":", 1)
        client_id, secret = unquote_plus(client_id, errors="strict"), unquote_plus(secret, errors="strict")
    except (ValueError, UnicodeError, binascii.Error):
        return None
    if not client_id or not secret or len(client_id) > 100 or len(secret) > 255:
        return None
    return client_id, secret


def strict_verify_token(request):
    if request.method != "POST":
        return _response({"error": "invalid_request"}, 405)
    supplied = _credentials(request)
    Application = get_application_model()
    application = None
    if supplied is not None:
        client_id, client_secret = supplied
        application = Application.objects.filter(
            client_id=client_id, client_type=Application.CLIENT_CONFIDENTIAL).first()
        if application is None or not application.client_secret or not constant_time_compare(
                application.client_secret, client_secret):
            application = None
    if application is None:
        logger.debug("Strict backend verifier rejected client authentication")
        return _response({"error": "invalid_client"}, 401)
    values = request.POST.getlist("token")
    if (set(request.POST) != {"token"} or len(values) != 1
            or not isinstance(values[0], str) or not values[0] or len(values[0]) > 255):
        logger.debug("Strict backend verifier rejected request shape")
        return _response({"error": "invalid_request"}, 400)
    token = get_access_token_model().objects.select_related("user", "application").filter(
        token=values[0], application_id=application.pk).first()
    if token is None or token.user is None or not token.user.is_active or not token.is_valid():
        logger.debug("Strict backend verifier rejected token or principal")
        return _response({"error": "invalid_token"}, 403)
    username = token.user.get_username()
    if not isinstance(username, str) or not username.strip():
        logger.debug("Strict backend verifier rejected empty principal")
        return _response({"error": "invalid_token"}, 403)
    remaining_ms = int((token.expires - timezone.now()).total_seconds() * 1000)
    if remaining_ms <= 0:
        return _response({"error": "invalid_token"}, 403)
    return _response({"client_id": application.client_id, "issued_to": username,
                      "username": username, "user_id": token.user_id,
                      "scope": token.scope, "expires_in": remaining_ms})
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _tests():
    return Path(__file__).with_name('verifier_tests.py').read_bytes()


def expected_files():
    """Exact post-repair allowlist consumed by the source build validator."""
    return dict(REPAIRED_EXISTING, **{HELPER_PATH: sha(HELPER_SOURCE.encode()), TEST_PATH: sha(_tests())})


def transform_existing(relative, data):
    if relative not in BASELINE or sha(data) != BASELINE[relative]:
        raise ValueError('GeoNode verifier repair requires exact retained source: ' + relative)
    if relative == 'geonode/api/views.py':
        before = b'from django.utils import timezone\n'
        after = b'from django.conf import settings\nfrom django.utils import timezone\n'
        branch = b'def verify_token(request):\n'
        replacement = (b'def verify_token(request):\n'
            b'    if getattr(settings, "OAUTH2_BACKEND_TOKENINFO_STRICT", False):\n'
            b'        from geonode.api.backend_tokeninfo import strict_verify_token\n'
            b'\n'
            b'        return strict_verify_token(request)\n')
        if data.count(before) != 1 or data.count(branch) != 1:
            raise ValueError('GeoNode verifier source anchor mismatch')
        return data.replace(before, after).replace(branch, replacement)
    if relative == 'geonode/security/middleware.py':
        anchor = b'from geonode import geoserver\n'
        basic = b'        user = extract_user_from_headers(request)\n'
        session = b'    def process_request(self, request):\n        if request and request.user and not request.user.is_anonymous:\n'
        if data.count(anchor) != 1 or data.count(basic) != 1 or data.count(session) != 1:
            raise ValueError('GeoNode middleware source anchor mismatch')
        data = data.replace(anchor, anchor + b'from geonode.api.backend_tokeninfo import is_strict_backend_request\n')
        data = data.replace(basic,
            b'        # Backend Basic credentials identify the client, never a browser user.\n'
            b'        if is_strict_backend_request(request):\n'
            b'            return None\n' + basic)
        return data.replace(session,
            b'    def process_request(self, request):\n'
            b'        # Explicit backend verification must not replace or expire browser state.\n'
            b'        if is_strict_backend_request(request):\n'
            b'            return None\n'
            b'        if request and request.user and not request.user.is_anonymous:\n')
    anchor = b'OAUTH2_PROVIDER = {\n'
    if data.count(anchor) != 1:
        raise ValueError('GeoNode settings source anchor mismatch')
    return data.replace(anchor,
        b'# Explicit backend opt-in; inherited browser/tokeninfo behavior is the default.\n'
        b'OAUTH2_BACKEND_TOKENINFO_STRICT = False\n\n' + anchor)


def _path(root, relative):
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError('GeoNode verifier repair refuses source symlinks')
        current = current.parent
    return path


def apply(source_root):
    root = Path(source_root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('GeoNode verifier repair requires a regular source directory')
    expected = expected_files()
    paths = {relative: _path(root, relative) for relative in expected}
    current = {relative: sha(path.read_bytes()) if path.is_file() else None for relative, path in paths.items()}
    repeated = current == expected
    if not repeated:
        # Validate every original/addition first; source drift cannot leave partial edits.
        for relative, required in BASELINE.items():
            if current[relative] != required:
                raise ValueError('GeoNode verifier baseline mismatch: ' + relative)
        if any(paths[name].exists() for name in (HELPER_PATH, TEST_PATH)):
            raise ValueError('GeoNode verifier helper/test collision')
        outputs = {relative: transform_existing(relative, paths[relative].read_bytes()) for relative in BASELINE}
        outputs.update({HELPER_PATH: HELPER_SOURCE.encode(), TEST_PATH: _tests()})
        if {relative: sha(data) for relative, data in outputs.items()} != expected:
            raise ValueError('GeoNode verifier repair output hash guard failed')
        for relative, data in outputs.items():
            paths[relative].write_bytes(data)
    if any(not path.is_file() or sha(path.read_bytes()) != expected[relative] for relative, path in paths.items()):
        raise ValueError('GeoNode verifier repair readback mismatch')
    return {'schema_version': 1, 'repair': 'geonode-strict-backend-tokeninfo', 'source_commit': SOURCE_COMMIT,
            'setting': SETTING, 'default': False,
            'middleware_scope': 'Only exact resolved verify_token view in strict mode skips user Basic resolution and session-expiry mutation; remaining middleware and CSRF configuration unchanged.',
            'applied': True, 'already_applied': repeated,
            'recipe_sha256': sha(Path(__file__).read_bytes()), 'native_tests_source_sha256': sha(_tests()),
            'files': [{'path': relative, 'before_sha256': BASELINE.get(relative), 'after_sha256': expected[relative]}
                      for relative in sorted(expected)]}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    print(json.dumps(apply(parser.parse_args().source_root), indent=2, sort_keys=True))
