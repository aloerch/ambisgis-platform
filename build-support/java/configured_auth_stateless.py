"""Guarded opt-in stateless bearer repair and native regressions for configured OAuth.

No network or source archive mutation. Explicit selection is required.
Native session regressions also run against the diagnostic-only baseline.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath

from resolution_inventory import read_file

MANIFEST = Path(__file__).with_name('configured-auth-stateless.json')
FIXTURES = Path(__file__).with_name('configured-auth-stateless-fixtures')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest():
    return json.loads(MANIFEST.read_text())


def path_under(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name:
        raise ValueError('unsafe configured stateless repair path')
    path = Path(root) / relative
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != Path(root).parent):
        raise ValueError('configured stateless repair refuses symlinks')
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('configured stateless repair escapes source root')
    return path


def prepare(source, repair=False, tests=True):
    source = Path(source)
    specification = manifest()
    changes, injected, staged = [], [], []
    for row in specification['sources']:
        path = path_under(source, row['path'])
        original = read_file(path)
        if sha(original) != row['before_sha256']:
            raise ValueError('configured stateless repair requires exact source')
        text = original.decode('utf-8')
        for replacement in row['replacements']:
            count = replacement['count']
            if type(count) is not int or count < 1 or text.count(replacement['before']) != count:
                raise ValueError('ambiguous configured stateless replacement')
            text = text.replace(replacement['before'], replacement['after'])
        changed = text.encode('utf-8')
        if sha(changed) != row['after_sha256']:
            raise ValueError('configured stateless predicted output mismatch')
        if repair:
            staged.append((path, changed, False))
            changes.append({key: row[key] for key in ('path', 'purpose', 'before_sha256', 'after_sha256')})
    if tests:
        for row in specification['fixtures']:
            destination = path_under(source, row['path'])
            if destination.exists():
                raise ValueError('configured stateless test must not overwrite existing source')
            fixture = path_under(FIXTURES, row['file'])
            data = read_file(fixture)
            if sha(data) != row['sha256']:
                raise ValueError('configured stateless native fixture changed')
            staged.append((destination, data, True))
            injected.append({'path': row['path'], 'sha256': row['sha256']})
    # All input, output, count, destination and native-fixture checks precede every write.
    for path, data, exclusive in staged:
        if exclusive:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
        else:
            path.write_bytes(data)
        if sha(read_file(path)) != sha(data):
            raise ValueError('configured stateless written source changed')
    return {'purpose': 'explicit opt-in request bearer authentication without browser session authority',
            'manifest_sha256': sha(MANIFEST.read_bytes()),
            'repair_applied': bool(repair), 'repairs': changes, 'injected_sources': injected,
            'source_application_order': [row['path'] for row in changes],
            'required_preceding_repairs': ['oauth-redaction.json', 'oauth-principal.json', 'configured-auth-repairs.json'],
            'inspected_sources': {row['path']: row['before_sha256'] for row in specification['sources']},
            'inspected_fixtures': specification['fixtures'] if tests else [],
            'native_test_count': sum(row['test_count'] for row in specification['fixtures']) if tests else 0,
            'authentication_decision_changed': bool(repair), 'default_browser_behavior_changed': False,
            'requires_explicit_filter_option': 'statelessBearerAuthentication',
            'stateless_requires_provisioned_user_for_user_group_service': bool(repair),
            'cache_key_or_cache_policy_changed': bool(repair),
            'cache_policy_note': 'Retains native token cache expiry and session-present write suppression; ignores cookie-only cache keys in opt-in mode',
            'human_security_review_required': True, 'source_closure_or_release_acceptance': False}
