"""Exact Koop source/production graph custody; never executes acquired code."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

COMMIT = '333518a19d43adf2fd12faed1a3be52d9c90dd3f'
TREE = '3357f74aa588b18703f26cdb5b5a5f7809d7d150'
REPOSITORY_ID = 11542346
WORKSPACES = ('cache-memory', 'core', 'featureserver', 'logger', 'output-geoservices', 'winnow')
VERSIONS = {'cache-memory': '6.0.0', 'core': '10.4.19', 'featureserver': '9.3.0',
            'logger': '5.0.0', 'output-geoservices': '8.1.25', 'winnow': '5.0.4'}
NODE_SHA256 = 'd6c664df3f3f61458e8c277585571328522d705166723a7c7823a9253a4d15a0'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def regular(root, relative):
    parts = PurePosixPath(relative)
    require(relative and not parts.is_absolute() and '..' not in parts.parts
            and '\\' not in relative, 'unsafe retained path')
    path = Path(root) / relative
    require(path.is_file() and not path.is_symlink()
            and not any(p.is_symlink() for p in path.parents), 'missing/nonregular retained input')
    return path


def verify_sri(path, integrity):
    matches = []
    for token in integrity.split():
        algorithm, encoded = token.split('-', 1)
        require(algorithm in ('sha1', 'sha256', 'sha384', 'sha512'), 'unsupported input digest')
        matches.append(hashlib.new(algorithm, Path(path).read_bytes()).digest()
                       == base64.b64decode(encoded, validate=True))
    require(matches and all(matches), 'archive integrity mismatch')


def archive_files(path):
    """Read regular files only; never extract archive-supplied paths or links."""
    files = {}
    total = 0
    with tarfile.open(path) as archive:
        for member in archive:
            parts = PurePosixPath(member.name)
            require(not parts.is_absolute() and '..' not in parts.parts and '\\' not in member.name,
                    'unsafe archive member')
            if member.isdir():
                continue
            require(member.isfile(), 'archive links/special files are not allowed')
            require(member.name not in files and len(parts.parts) > 1, 'duplicate/root archive member')
            total += member.size
            require(total <= 512 * 1024 * 1024 and member.size <= 128 * 1024 * 1024,
                    'archive size limit')
            files[member.name] = archive.extractfile(member).read()
    require(files, 'empty archive')
    return files


def source_manifest(archive_path, tree):
    require(tree.get('sha') == TREE and not tree.get('truncated'), 'wrong/incomplete source tree')
    verify_git_tree(tree)
    files = archive_files(archive_path)
    prefixes = {PurePosixPath(name).parts[0] for name in files}
    require(len(prefixes) == 1, 'source archive has multiple roots')
    stripped = {str(PurePosixPath(name).relative_to(next(iter(prefixes)))): data
                for name, data in files.items()}
    entries = {row['path']: row for row in tree['tree'] if row['type'] == 'blob'}
    require(set(entries) == set(stripped), 'source archive/tree file set differs')
    rows = {}
    for path, data in stripped.items():
        row = entries[path]
        require(row['mode'] in ('100644', '100755'), 'unreviewed source Git mode')
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        require(blob == row['sha'], 'source archive/Git blob differs')
        rows[path] = {'git_blob': blob, 'git_mode': row['mode'],
                      'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return stripped, rows


def verify_git_tree(tree):
    """Recompute Git trees, so a relabeled API JSON cannot supply new blobs."""
    folders = {'': []}
    expected = {'': TREE}
    seen = set()
    for row in tree['tree']:
        path = PurePosixPath(row['path'])
        require(not path.is_absolute() and '..' not in path.parts and row['path'] not in seen,
                'unsafe/duplicate Git tree entry')
        seen.add(row['path'])
        parent = str(path.parent)
        parent = '' if parent == '.' else parent
        require(row['type'] in ('blob', 'tree'), 'unreviewed Git entry type')
        if row['type'] == 'tree':
            require(row['mode'] == '040000', 'invalid tree mode')
            folders.setdefault(row['path'], [])
            expected[row['path']] = row['sha']
        folders.setdefault(parent, []).append(row)
    for folder, rows in folders.items():
        encoded = b''
        for row in sorted(rows, key=lambda r: (PurePosixPath(r['path']).name +
                                               ('/' if r['type'] == 'tree' else '')).encode()):
            mode = '40000' if row['type'] == 'tree' else row['mode']
            encoded += (mode + ' ' + PurePosixPath(row['path']).name).encode() + b'\0' + bytes.fromhex(row['sha'])
        actual = hashlib.sha1(b'tree ' + str(len(encoded)).encode() + b'\0' + encoded).hexdigest()
        require(expected.get(folder) == actual, 'Git tree content hash differs')


def resolve(packages, parent, name):
    require(name and not name.startswith(('.', '/')) and '..' not in name.split('/'), 'invalid package name')
    current = PurePosixPath(parent)
    while True:
        if current.name != 'node_modules':
            path = str(current / 'node_modules' / name)
            if path in packages:
                return path
        if str(current) == '.':
            break
        current = current.parent
    raise ValueError('unresolved locked dependency: ' + parent + ' -> ' + name)


def production_lock(source_files, resolution_records=None, *, allow_unresolved_for_acquisition=False):
    original = json.loads(source_files['package-lock.json'])
    require(original.get('lockfileVersion') == 2, 'unexpected original lock schema')
    packages = original['packages']
    root = {'name': 'ambisgis-fnd06-koop-spike', 'version': '0.0.0', 'private': True,
            'workspaces': ['packages/' + name for name in WORKSPACES],
            'dependencies': {'@koopjs/koop-core': VERSIONS['core']}}
    selected = {'': root}
    reconciliation = []
    for name in WORKSPACES:
        path = 'packages/' + name
        manifest = json.loads(source_files[path + '/package.json'])
        require(manifest['version'] == VERSIONS[name], 'workspace source version differs')
        old = packages[path]
        row = {key: manifest[key] for key in ('name', 'version', 'license', 'engines', 'dependencies',
                                            'optionalDependencies', 'peerDependencies', 'peerDependenciesMeta')
               if key in manifest}
        reconciliation.append({'path': path, 'original_lock': old, 'selected_source': row})
        selected[path] = row
        packages[path] = row
        link = 'node_modules/' + manifest['name']
        require(packages[link] == {'resolved': path, 'link': True}, 'workspace link differs')
        selected[link] = packages[link]
    pending = list('packages/' + name for name in WORKSPACES)
    visited = set()
    edges = []
    while pending:
        parent = pending.pop()
        if parent in visited:
            continue
        visited.add(parent)
        row = packages[parent]
        for kind in ('dependencies', 'optionalDependencies', 'peerDependencies'):
            for name, constraint in row.get(kind, {}).items():
                optional_peer = kind == 'peerDependencies' and row.get('peerDependenciesMeta', {}).get(name, {}).get('optional')
                try:
                    target = resolve(packages, parent, name)
                except ValueError:
                    if optional_peer:
                        edges.append({'from': parent, 'name': name, 'constraint': constraint,
                                      'kind': kind, 'absent_optional_peer': True})
                        continue
                    raise
                dest = packages[target]
                actual = dest['resolved'] if dest.get('link') else target
                edges.append({'from': parent, 'name': name, 'constraint': constraint,
                              'kind': kind, 'to': target, 'version': packages[actual]['version']})
                if target not in selected:
                    selected[target] = {k: v for k, v in dest.items() if k not in ('dev', 'devOptional')}
                pending.append(actual)
    supplements_used = []
    resolution_records = resolution_records or {}
    for path, row in selected.items():
        if not path.startswith('node_modules/') or row.get('link'):
            continue
        if row.get('resolved') and row.get('integrity'):
            continue
        name = path.rsplit('node_modules/', 1)[1]
        identity = name + '@' + row['version']
        supplement = resolution_records.get(identity)
        if supplement is None and allow_unresolved_for_acquisition:
            continue
        require(supplement is not None, 'unresolved registry archive identity: ' + identity)
        require(supplement['name'] == name and supplement['version'] == row['version'],
                'supplemented registry version differs')
        require(supplement.get('resolved', '').startswith('https://registry.npmjs.org/')
                and supplement.get('integrity'), 'supplemented archive identity incomplete')
        for field in ('resolved', 'integrity'):
            require(not row.get(field) or row[field] == supplement[field], 'supplement changes existing archive identity')
            row[field] = supplement[field]
        supplements_used.append({'path': path, 'identity': identity, 'source': 'explicit exact-version registry metadata'})
    require(set(resolution_records) == {r['identity'] for r in supplements_used}, 'unexpected archive identity supplement')
    lock = {'name': root['name'], 'version': root['version'], 'lockfileVersion': 3,
            'requires': True, 'packages': selected}
    return root, lock, {'workspaces': reconciliation, 'edges': edges,
                        'original_lock_sha256': hashlib.sha256(source_files['package-lock.json']).hexdigest(),
                        'production_entries': len(selected), 'original_entries': len(original['packages']),
                        'archive_identity_supplements': supplements_used,
                        'policy': 'Exact versions and graph from original lock; missing archive identities explicitly supplemented from retained exact-version metadata. No dev graph or semver resolution.'}


def verify_inventory(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'retained input root must be regular directory')
    require(not any(path.is_symlink() for path in root.rglob('*')), 'symlink in retained inventory')
    manifest = json.loads(regular(root, 'manifest.json').read_text())
    require(manifest['source_commit'] == COMMIT and manifest['source_tree'] == TREE, 'candidate source identity differs')
    rows = manifest['files']
    require(len({r['path'] for r in rows}) == len(rows), 'duplicate inventory path')
    expected = {r['path'] for r in rows} | {'manifest.json'}
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if not p.is_dir()}
    require(actual == expected, 'retained input file set differs')
    for row in rows:
        path = regular(root, row['path'])
        require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], 'retained input digest differs')
    lock = json.loads(regular(root, 'package-lock.json').read_text())
    source_files, source_rows = source_manifest(regular(root, 'source.tar.gz'),
                                               json.loads(regular(root, 'source-tree.json').read_text()))
    supplements = json.loads(regular(root, 'resolution-supplements.json').read_text())
    for identity, supplement in supplements.items():
        metadata_path = regular(root, supplement['metadata'])
        require(sha(metadata_path) == supplement['metadata_sha256'], 'supplement metadata hash differs')
        metadata = json.loads(metadata_path.read_text())
        require(metadata['name'] == supplement['name'] and metadata['version'] == supplement['version']
                and identity == metadata['name'] + '@' + metadata['version'], 'supplement metadata identity differs')
        require(metadata['dist']['tarball'] == supplement['resolved']
                and metadata['dist']['integrity'] == supplement['integrity'], 'supplement metadata archive differs')
    package, expected_lock, unused = production_lock(source_files, supplements)
    require(json.loads(regular(root, 'package.json').read_text()) == package, 'root package identity differs')
    require(set(lock['packages']) == set(expected_lock['packages']), 'production lock graph differs')
    for path, row in expected_lock['packages'].items():
        selected = lock['packages'][path]
        if not path.startswith('node_modules/') or row.get('link'):
            require(selected == row, 'workspace/root lock identity differs')
            continue
        require(row.get('resolved') and row.get('integrity'), 'unresolved registry input')
        expected_row = dict(row)
        archive = 'registry/' + hashlib.sha256(row['integrity'].encode()).hexdigest() + '.tgz'
        expected_row['resolved'] = 'file:' + archive
        require(selected == expected_row, 'registry lock identity differs')
        verify_sri(regular(root, archive), row['integrity'])
    require(json.loads(regular(root, 'source-files.json').read_text()) == source_rows, 'source inventory differs')
    require(sha(regular(root, 'node.tar.xz')) == NODE_SHA256, 'retained Node differs')
    return manifest
