#!/usr/bin/env python3
"""Read-only hashes of explicitly selected historical evidence; no services run.

Only stdout or the requested new /tmp result receives output. Referenced runtime
artifacts, receipts and historical source/recipe files are never modified.
"""
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--repo', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
workspace = Path('/home/revelberry/Projects/AmbisGIS')
refs = []
indexes = []

def load(rel):
    p = args.repo / rel
    indexes.append({'path': str(p), 'sha256': hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()})
    return json.loads(p.read_text())

def add(group, r):
    refs.append({'group': group, **r})

def absolute_refs(group, value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and value['path'].startswith('/') and isinstance(value.get('sha256'), str):
            add(group, value)
        for child in value.values():
            absolute_refs(group, child)
    elif isinstance(value, list):
        for child in value:
            absolute_refs(group, child)

q = load('plan/verification/qgis-candidate/evidence.json')
j = load('plan/verification/jupyter-slice.json')
p = load('plan/verification/postgis-slice.json')
for r in q['references'].values(): add('qgis', r)
for r in q['input_authorities'].values(): add('qgis', r)
for r in j['reports']: add('jupyter', r)
for r in j['build']['wheels']:
    add('jupyter', dict(r, path=str(workspace / 'build-worktrees/jupyter-slice/run-002' / r['path'])))
for run in p['runs']:
    if run['run'] == 'run-003':
        add('database', run['full_snapshot'])
        add('database', run['build_receipts'])
        for r in run['database_reports'] + run['regression_reports']: add('database', r['report'])
        for r in run['runtime']['artifacts']: add('database', r['identity'])
add('database', p['output_archive'])
for group, rel in [('identity', 'plan/verification/geonode-role-propagation/evidence.json'),
                   ('frontend', 'plan/verification/frontend-completion/evidence.json'),
                   ('frontend', 'plan/verification/frontend-completion/browser-evidence-summary.json')]:
    absolute_refs(group, load(rel))

# Historical selected Java successes remain tied to their own source/classpath.
# All evidence_files in these run records are resolved relative to their receipt.
java_http = load('plan/verification/java-http/run-index.json')
for run in java_http['runs']:
    if run['run'] in ('xml-http-04', 'mapfish-http-05', 'oauth-http-principal-01', 'combined-logging-final-03'):
        add('java-http', {'path': run['receipt'], 'sha256': run['receipt_sha256']})
        for r in run.get('evidence_files', []):
            add('java-http', dict(r, path=str(Path(run['receipt']).parent / r['name'])))
java_native = load('plan/verification/java-compatibility.json')
for run in java_native['runs']:
    if run.get('result_exit_code') == 0:
        add('java-native', {'path': run['receipt'], 'sha256': run['receipt_sha256']})
        if run.get('log'): add('java-native', run['log'])

rows = []
for r in refs:
    path = Path(r['path'].replace('<workspace>', str(workspace)))
    row = {'group': r['group'], 'path': str(path), 'expected_sha256': r['sha256']}
    try:
        with path.open('rb') as stream:
            row['actual_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        row['actual_bytes'] = path.stat().st_size
        row['passed'] = row['actual_sha256'] == r['sha256']
        # Older identity records may call byte size 'size'.
        expected_size = r.get('bytes', r.get('size'))
        if expected_size is not None:
            row['expected_bytes'] = expected_size
            row['passed'] = row['passed'] and row['actual_bytes'] == expected_size
    except OSError as exc:
        row['passed'] = False
        row['error'] = str(exc)
    rows.append(row)

result = {'schema_version': 1,
          'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Current read-only hash/size check of enumerated historical references; not native/runtime reruns, recursive custody closure, or task acceptance.',
          'script_sha256': hashlib.file_digest(Path(__file__).open('rb'), 'sha256').hexdigest(),
          'indexes': indexes,
          'selected_reference_records': len(rows),
          'unique_paths': len({r['path'] for r in rows}),
          'groups': dict(collections.Counter(r['group'] for r in rows)),
          'passed_records': sum(r['passed'] for r in rows),
          'problems': [r for r in rows if not r['passed']],
          'references': rows}
with args.output.open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('indexes','references')}, indent=2))
raise SystemExit(bool(result['problems']))
