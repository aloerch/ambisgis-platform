"""Inject bounded real HTTP checks into the exact selected OAuth module's tests."""
import hashlib
import json
from pathlib import Path
from resolution import sha
from resolution_inventory import read_file

MODULE = 'geoserver/src/community/security/oauth2-geonode'
SOURCES = {
    MODULE + '/src/main/java/org/geoserver/security/oauth2/services/GeoNodeTokenServices.java':
        '17ed77734adb1450ab122c5216f07fd3e91cd2ee66d4e21c6235717d60463fbe',
    'geoserver/src/community/security/oauth2/oauth2-core/src/main/java/org/geoserver/security/oauth2/GeoServerOAuthRemoteTokenServices.java':
        '1f34ba9a1a75dba8f9c0f0eab329b9edb9a2ee8832186114ec3101f516ba75ef',
}
FIXTURES = ('AmbisgisGeoNodeHttpTest.java', 'AmbisgisGeoNodeDiagnosticsTest.java')


def repair_rows(name):
    return json.loads(Path(__file__).with_name(name).read_text())


def apply_repairs(source, rows):
    """Preflight exact inputs, replacements and predicted outputs before any write."""
    staged = []
    for row in rows:
        path = source / row['path']
        data = read_file(path)
        if hashlib.sha256(data).hexdigest() != row['before_sha256']:
            raise ValueError('OAuth repair requires exact source/test fixture')
        text = data.decode('utf-8')
        for before, after in row['replacements']:
            if text.count(before) != 1:
                raise ValueError('ambiguous OAuth source repair')
            text = text.replace(before, after)
        data = text.encode('utf-8')
        if hashlib.sha256(data).hexdigest() != row['after_sha256']:
            raise ValueError('OAuth repair predicted output mismatch')
        staged.append((path, data))
    for path, data in staged:
        path.write_bytes(data)
    result = []
    for row in rows:
        if sha(source / row['path']) != row['after_sha256']:
            raise ValueError('OAuth repair output mismatch')
        result.append({key: row[key] for key in ('path', 'before_sha256', 'after_sha256', 'purpose') if key in row})
    return result


def prepare(source, redact=False, principal=False):
    if principal and not redact:
        raise ValueError('principal repair requires the diagnostic repair')
    source = Path(source)
    for name, digest in SOURCES.items():
        if hashlib.sha256(read_file(source / name)).hexdigest() != digest:
            raise ValueError('OAuth HTTP fixture requires exact inspected owned token-service sources')
    destinations = [source / MODULE / 'src/test/java/org/geoserver/security/oauth2' / name for name in FIXTURES]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise ValueError('OAuth test overlay must not overwrite an existing fixture')
    repair = apply_repairs(source, repair_rows('oauth-redaction.json')) if redact else []
    principal_repair = apply_repairs(source, repair_rows('oauth-principal.json')) if principal else []
    injected = []
    for name, destination in zip(FIXTURES, destinations):
        witness = Path(__file__).with_name('oauth-fixtures') / name
        with destination.open('xb') as stream:
            stream.write(witness.read_bytes())
        injected.append({'path': destination.relative_to(source).as_posix(), 'sha256': sha(destination)})
    return {'purpose': 'actual-geonode-token-service-local-http-positive-and-negative-fixture',
            'injected_sources': injected, 'inspected_sources': SOURCES,
            'http_scenarios': 17, 'diagnostic_tests': 3, 'fixture_values_not_intentionally_printed': True,
            'diagnostic_repair': repair, 'principal_repair': principal_repair,
            'authentication_decision_changed': principal, 'human_security_review_required': True,
            'browser_or_canonical_policy_acceptance': False,
            'authorization_scope': 'actual selected Spring decision manager over fixed fixture attributes; no deployed GeoServer filter',
            'protocol': 'owned GeoNode verify_token with invalid/expired HTTP403',
            'expected_baseline_findings': ['malformed successful principal responses require denial evidence'],
            'requires_controlled_loopback_environment': True}
