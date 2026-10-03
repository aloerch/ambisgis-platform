"""Constrained WFS spike gateway; unsupported routes and methods fail closed."""
import http.client
import re
from urllib.parse import parse_qsl, urlsplit


def resource(path, query, method):
    if method != "GET" or path != "/wfs" or len(query) > 2048:
        return None
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    fields = {key.lower(): value for key, value in pairs}
    if len(fields) != len(pairs) or set(fields) != {"service", "version", "request", "typename", "outputformat"}:
        return None
    if (fields["service"] != "WFS" or fields["version"] != "1.0.0"
            or fields["request"] != "GetFeature" or fields["outputformat"] != "application/json"
            or not re.fullmatch(r"fixture:[a-z_]{1,64}", fields["typename"])):
        return None
    return fields["typename"]


def decision(origin, key, name, authorization):
    target = urlsplit(origin)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=2)
    try:
        connection.request("GET", "/internal/policy/read", headers={
            "X-AmbisGIS-Policy-Key": key, "X-AmbisGIS-Resource": name,
            "Authorization": authorization})
        response = connection.getresponse()
        return response.status == 204 and response.getheader("Location") is None
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def application(catalog_origin, engine_origin, service_key):
    for origin in (catalog_origin, engine_origin):
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path:
            raise ValueError("spike requires explicit private loopback origins")
    engine = urlsplit(engine_origin)

    def serve(environ, start_response):
        name = resource(environ.get("PATH_INFO", ""), environ.get("QUERY_STRING", ""), environ.get("REQUEST_METHOD"))
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        body, status, content_type = b"", 403, "text/plain"
        if name and decision(catalog_origin, service_key, name, authorization):
            connection = http.client.HTTPConnection(engine.hostname, engine.port, timeout=10)
            try:
                connection.request("GET", "/geoserver/wfs?" + environ["QUERY_STRING"], headers={"Authorization": authorization})
                response = connection.getresponse()
                body = response.read(1024 * 1024 + 1)
                if len(body) > 1024 * 1024:
                    raise ValueError("bounded spike response exceeded")
                status, content_type = response.status, response.getheader("Content-Type", "application/octet-stream")
            except (OSError, http.client.HTTPException, ValueError):
                body, status = b"", 503
            finally:
                connection.close()
        start_response(str(status) + " " + http.client.responses.get(status, "Response"), [
            ("Content-Type", content_type), ("Cache-Control", "no-store"), ("Content-Length", str(len(body)))])
        return [body]
    return serve
