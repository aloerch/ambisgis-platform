"""Strict fixture response assertions and secret-free, fail-closed HTTP receipts."""
import json
from pathlib import Path


def validate_geojson(body, marker):
    """Require the actual synthetic point feature, not an echoed witness string."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate GeoJSON member')
            result[key] = value
        return result
    try:
        if not isinstance(marker, str) or not marker:
            return False
        document = json.loads(body, object_pairs_hook=unique_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite GeoJSON number')))
        if not isinstance(document, dict) or document.get('type') != 'FeatureCollection':
            return False
        features = document.get('features')
        if not isinstance(features, list) or len(features) != 1:
            return False
        feature = features[0]
        if not isinstance(feature, dict) or feature.get('type') != 'Feature':
            return False
        geometry, properties = feature.get('geometry'), feature.get('properties')
        if not isinstance(geometry, dict) or geometry.get('type') != 'Point' or not isinstance(properties, dict):
            return False
        coordinates = geometry.get('coordinates')
        return (isinstance(coordinates, list) and len(coordinates) == 2
                and all(type(value) in (int, float) for value in coordinates)
                and coordinates == [1, 2] and properties.get('label') == marker)
    except (ValueError, TypeError, UnicodeError):
        return False


def redact(value, secrets):
    """Return a sanitized JSON-compatible copy and the number of occurrences."""
    if isinstance(secrets, (str, bytes)):
        raise TypeError('secret values must be an iterable of strings')
    needles = set(secrets)
    if any(not isinstance(secret, str) for secret in needles):
        raise TypeError('secret values must be strings')
    needles = sorted((secret for secret in needles if secret), key=lambda secret: (-len(secret), secret))
    replacement = '[REDACTED_FIXTURE_VALUE]'
    if any(secret in replacement for secret in needles):
        replacement = ''
    count = 0
    def visit(item):
        nonlocal count
        if isinstance(item, str):
            for secret in needles:
                count += item.count(secret)
                item = item.replace(secret, replacement)
            return item
        if isinstance(item, dict):
            return {visit(key): visit(content) for key, content in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(content) for content in item]
        if item is None or type(item) in (bool, int, float):
            return item
        raise TypeError('receipt contains a non-JSON value')
    return visit(value), count


def _failed_cleanup(value):
    if isinstance(value, dict):
        return any((key == 'forced_kill' and content is True)
                   or (key != 'forced_kill' and _failed_cleanup(content))
                   for key, content in value.items())
    if isinstance(value, (list, tuple)):
        return any(_failed_cleanup(content) for content in value)
    return value is False


def finalize_report(report, path, secrets):
    """Write one immutable receipt; diagnostic/cleanup failures override success.

    Filesystem errors propagate so the outer supervisor must preserve failure.
    Redaction occurs on the complete report before any bytes reach its new file.
    """
    sanitized, count = redact(report, secrets)
    sanitized['receipt_secret_redactions'] = count
    failure_fields = ('error', 'capture_errors', 'finalization_error', 'finalization_errors', 'cleanup_errors',
                      'diagnostic_leaks', 'response_leaks', 'residual_secret_files_redacted')
    scenarios = sanitized.get('scenario_results')
    controls = sanitized.get('logger_capture_controls')
    if (count or any(sanitized.get(name) for name in failure_fields)
            or _failed_cleanup(sanitized.get('cleanup', {}))
            or sanitized.get('protocol', {}).get('violations')
            or (scenarios is not None and (not scenarios or any(row.get('passed') is not True for row in scenarios)))
            or (controls is not None and (not controls or any(value != 1 for value in controls.values())))):
        sanitized['result_exit_code'] = 1
    if type(sanitized.get('result_exit_code')) is not int or sanitized['result_exit_code'] not in (0, 1):
        sanitized['result_exit_code'] = 1
    text = json.dumps(sanitized, indent=2, sort_keys=True, allow_nan=False) + '\n'
    with Path(path).open('x') as output:
        output.write(text)
    return sanitized
