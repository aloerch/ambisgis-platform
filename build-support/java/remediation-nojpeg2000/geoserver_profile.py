"""Exact-source capability guard for the separately selected NO-JPEG2000 variant."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prepare(source):
    source = Path(source)
    manifest = HERE / 'geoserver-repairs.json'
    rows = json.loads(manifest.read_text())
    for row in rows:
        path = source / row['path']
        if path.is_symlink() or sha(path) != row['before_sha256'] or path.read_text().count(row['before']) != 1:
            raise ValueError('NO-JPEG2000 service guard requires exact source: ' + row['path'])
    sources = []
    for name in ('NoJpeg2000Policy.java', 'NoJpeg2000Filter.java'):
        target = source / 'geoserver/src/main/src/main/java/org/geoserver/filters' / name
        if target.exists():
            raise ValueError('refuse to overwrite existing candidate source: ' + str(target))
        sources.append((HERE / name, target))
    for row in rows:
        path = source / row['path']
        path.write_text(path.read_text().replace(row['before'], row['after']))
        if sha(path) != row['after_sha256']:
            raise ValueError('NO-JPEG2000 service source output mismatch')
    additions = []
    for original, target in sources:
        target.write_bytes(original.read_bytes())
        additions.append({'path': str(target.relative_to(source)), 'sha256': sha(target),
                          'provenance': 'independently authored AmbisGIS candidate capability guard'})
    return {'profile': 'NO-JPEG2000', 'manifest_sha256': sha(manifest), 'additions': additions,
            'repairs': [{k: row[k] for k in ('path', 'before_sha256', 'after_sha256', 'reason')} for row in rows],
            'rejection': 'HTTP 415, explicit JPEG2000 unsupported message; bounded prefix inspection without decoding',
            'limits': {'scope': 'Java/server profile only; XML OGC requests retain native structured format rejection.',
                       'zip_upload': 'New explicit 1 GiB compressed-body and 10000-member limits; HTTP 413 and transient cleanup. Direct non-ZIP upload bounds unchanged.',
                       'retained_native_staging': 'Multipart parser may stage its input before this guard; this bounded change is not a general multipart parser redesign.'}}
