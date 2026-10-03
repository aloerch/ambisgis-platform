"""One read authority: native tokens, ResourceBase and guardian object grants.

No copied users, grants, decisions or positive cache. This internal endpoint is
read-only. Sharing changes use the catalog transaction and native permission
tables; new requests observe its committed state under READ COMMITTED.
"""
import hmac
import re


def allowed(resource_name, authorization, application_id):
    from django.utils import timezone
    from geonode.base.models import ResourceBase
    from guardian.core import ObjectPermissionChecker
    from guardian.utils import get_anonymous_user
    from oauth2_provider.models import get_access_token_model

    if not re.fullmatch(r"fixture:[a-z_]{1,64}", resource_name or ""):
        return False
    user = get_anonymous_user()
    if authorization:
        if not re.fullmatch(r"Bearer [A-Za-z0-9._~-]{20,512}", authorization):
            return False
        token = get_access_token_model().objects.select_related("user", "application").filter(
            token=authorization[7:], application__client_id=application_id,
            expires__gt=timezone.now(), user__is_active=True).first()
        if token is None or "read" not in token.scope.split():
            return False
        user = token.user
    # Ambiguous inherited names fail closed; no title-based adoption.
    resources = list(ResourceBase.objects.filter(alternate=resource_name)[:2])
    if len(resources) != 1:
        return False
    resource = resources[0]
    if not resource.is_published or not resource.is_approved:
        return False
    return (ObjectPermissionChecker(user).has_perm("view_resourcebase", resource)
            or ObjectPermissionChecker(get_anonymous_user()).has_perm("view_resourcebase", resource))


def wrap(application, *, service_key, application_id):
    if not isinstance(service_key, str) or len(service_key) < 32:
        raise ValueError("catalog policy requires a dedicated generated service key")

    def dispatch(environ, start_response):
        if environ.get("PATH_INFO") != "/internal/policy/read":
            return application(environ, start_response)
        from django.db import close_old_connections
        close_old_connections()
        status = "403 Forbidden"
        try:
            if (environ.get("REQUEST_METHOD") == "GET" and not environ.get("QUERY_STRING")
                    and hmac.compare_digest(environ.get("HTTP_X_AMBISGIS_POLICY_KEY", ""), service_key)
                    and allowed(environ.get("HTTP_X_AMBISGIS_RESOURCE", ""),
                                environ.get("HTTP_AUTHORIZATION", ""), application_id)):
                status = "204 No Content"
        except Exception:
            # Never include credentials, database exceptions, or resource metadata.
            status = "503 Service Unavailable"
        finally:
            close_old_connections()
        start_response(status, [("Cache-Control", "no-store"), ("Content-Length", "0")])
        return [b""]
    return dispatch
