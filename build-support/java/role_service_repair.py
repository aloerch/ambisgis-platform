"""Guarded owned REST role-service repair and native regressions.

No network or source archive mutation. Explicit selection is required.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath

from resolution_inventory import read_file

MANIFEST = Path(__file__).with_name('role-service-repairs.json')
FIXTURES = Path(__file__).with_name('role-service-fixtures')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest():
    return json.loads(MANIFEST.read_text())


def path_under(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name:
        raise ValueError('unsafe REST role-service repair path')
    path = Path(root) / relative
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != Path(root).parent):
        raise ValueError('REST role-service repair refuses symlinks')
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('REST role-service repair escapes source root')
    return path


def prepare(source, repair=False, tests=True):
    source = Path(source)
    specification = manifest()
    changes, injected, staged = [], [], []
    for row in specification['sources']:
        path = path_under(source, row['path'])
        original = read_file(path)
        if sha(original) != row['before_sha256']:
            raise ValueError('REST role-service repair requires exact source')
        text = original.decode('utf-8')
        for replacement in row['replacements']:
            count = replacement['count']
            if type(count) is not int or count < 1 or text.count(replacement['before']) != count:
                raise ValueError('ambiguous REST role-service replacement')
            text = text.replace(replacement['before'], replacement['after'])
        changed = text.encode('utf-8')
        if sha(changed) != row['after_sha256']:
            raise ValueError('REST role-service predicted output mismatch')
        if repair:
            staged.append((path, changed, False))
            changes.append({key: row[key] for key in ('path', 'purpose', 'before_sha256', 'after_sha256')})
    if tests:
        for row in specification['fixtures']:
            destination = path_under(source, row['path'])
            if destination.exists():
                raise ValueError('REST role-service test must not overwrite existing source')
            fixture = path_under(FIXTURES, row['file'])
            data = read_file(fixture)
            if sha(data) != row['sha256']:
                raise ValueError('REST role-service native fixture changed')
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
            raise ValueError('REST role-service written source changed')
    return {'purpose': 'bounded authenticated GeoNode role membership with exact identity binding',
            'manifest_sha256': sha(MANIFEST.read_bytes()),
            'repair_applied': bool(repair), 'repairs': changes, 'injected_sources': injected,
            'source_application_order': [row['path'] for row in changes],
            'required_preceding_repairs': [],
            'inspected_sources': {row['path']: row['before_sha256'] for row in specification['sources']},
            'inspected_fixtures': specification['fixtures'] if tests else [],
            'native_test_count': sum(row['test_count'] for row in specification['fixtures']) if tests else 0,
            'authentication_decision_changed': bool(repair), 'default_browser_behavior_changed': False,
            'requires_explicit_role_service_option': 'strictGeoNodeRoles',
            'cache_policy_note': 'Per-instance expireAfterWrite; successful hits never renew snapshots; expired lookups fail closed',
            'human_security_review_required': True, 'source_closure_or_release_acceptance': False}
