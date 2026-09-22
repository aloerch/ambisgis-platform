"""Content-pinned local replacements; never publish these as donor releases."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from resolution import sha


def apply(repository, rows, manifest_path):
    manifest_path = Path(manifest_path).resolve()
    selection = json.loads(manifest_path.read_text())
    if selection.get('schema_version') != 1 or not selection.get('variant_id') or not selection.get('replacements'):
        raise ValueError('replacement manifest requires explicit variant and nonempty selection')
    by_path = {r['maven_path']: r for r in rows}
    seen = set()
    verified = []
    for item in selection['replacements']:
        name = item['maven_path']; relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or name in seen or not name.endswith('.jar'):
            raise ValueError('unsafe, duplicate or non-JAR replacement path')
        seen.add(name)
        original = by_path.get(name)
        if original is None or original['sha256'] != item['original_sha256'] or sha(repository / name) != item['original_sha256']:
            raise ValueError('replacement original identity mismatch: ' + name)
        output = Path(item['path'])
        if not output.is_absolute() or output.is_symlink() or sha(output) != item['sha256'] or not item.get('variant_id'):
            raise ValueError('replacement output identity mismatch')
        if not item.get('source_evidence'):
            raise ValueError('replacement requires source evidence')
        for evidence in item['source_evidence']:
            path = Path(evidence['path'])
            if not path.is_absolute() or path.is_symlink() or sha(path) != evidence['sha256']:
                raise ValueError('replacement source evidence identity mismatch')
        verified.append(item)
    replacements = {}
    for item in verified:
        name = item['maven_path']; target = repository / name
        shutil.copyfile(item['path'], target)
        if sha(target) != item['sha256']: raise ValueError('replacement copy changed')
        replacements[name] = {**by_path[name], 'sha256': item['sha256'], 'bytes': target.stat().st_size,
            'repository': 'ambisgis-local-variant', 'original_record': by_path[name],
            'variant_id': item['variant_id'], 'variant_source_evidence': item['source_evidence'],
            'resolution_coordinate_only': True, 'publisher_release_identity': False}
        for suffix in ('.sha1', '.sha256', '.sha512', '.md5', '.asc'):
            side = name + suffix
            if side not in by_path: continue
            sidepath = repository / side
            if suffix == '.asc':
                sidepath.unlink()
                replacements[side] = None
            else:
                digest = hashlib.new(suffix[1:], target.read_bytes()).hexdigest()
                sidepath.write_text(digest + '\n')
                replacements[side] = {**by_path[side], 'sha256': sha(sidepath), 'bytes': sidepath.stat().st_size,
                    'repository': 'ambisgis-local-variant', 'original_record': by_path[side],
                    'variant_id': item['variant_id'], 'generated_local_checksum': True}
    result = [replacements.get(row['maven_path'], row) for row in rows]
    return [row for row in result if row is not None], {'manifest': str(manifest_path),
        'manifest_sha256': sha(manifest_path), 'variant_id': selection['variant_id'], 'replacements': verified,
        'distribution_or_donor_publication': False}
