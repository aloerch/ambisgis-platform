"""Exact disposable-source repairs for the selected aggregate package lifecycle."""
import json
from pathlib import Path
from resolution import sha


def prepare(source):
    """Attach owned model sources and explicitly mediate selected EMF dependencies."""
    rows = json.loads(Path(__file__).with_name('combined_logging-repairs.json').read_text())
    # Validate all inputs before writing any repair.
    for row in rows:
        path = Path(source) / row['path']
        if sha(path) != row['before_sha256'] or path.read_text().count(row['before']) != 1:
            raise ValueError('aggregate lifecycle repair requires exact retained source: ' + row['path'])
    for row in rows:
        path = Path(source) / row['path']
        path.write_text(path.read_text().replace(row['before'], row['after']))
        if sha(path) != row['after_sha256']:
            raise ValueError('aggregate lifecycle repair output mismatch')
    return {'purpose': 'owned-selected-aggregate-build-repairs',
            'repairs': [{key: row[key] for key in ('path', 'before_sha256', 'after_sha256', 'reason')} for row in rows],
            'source_revision_changed': False, 'runtime_source_changed': False}
