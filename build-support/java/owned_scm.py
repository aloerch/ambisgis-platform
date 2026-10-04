"""Per-root SCM custody for the serial, owned Java aggregate producer.

Git metadata borrows objects from explicitly declared retained repositories.
Those object stores must remain available; this is not a standalone source clone.
No source checkout, network fetch, global configuration or donor write is used.
The caller supplies reviewed parent POMs with reactor injection/run-once disabled.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import zipfile


ROOTS = ('geotools', 'geoserver', 'geowebcache')
MAVEN_ROOTS = {'geotools': '.', 'geoserver': 'src', 'geowebcache': 'geowebcache'}
EMBEDDED_COUNTS = {'geotools': 49, 'geoserver': 40, 'geowebcache': 11}
LOCALES = ('', '_ca', '_cs', '_da', '_de', '_el', '_es', '_fr', '_hu', '_it',
           '_ja', '_ko', '_lt', '_nl', '_no', '_pl', '_pt', '_pt_BR', '_ro',
           '_ru', '_sv', '_tr', '_zh')
REVISION_RESOURCES = {'GeoServerApplication' + x + '.properties' for x in LOCALES}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _selections(selections):
    if type(selections) is not dict or set(selections) != set(ROOTS):
        raise ValueError('Expected exactly three owned roots')
    for row in selections.values():
        if type(row) is not dict or any(type(row.get(k)) is not str or
                not re.fullmatch('[0-9a-f]{40}', row[k]) for k in ('commit', 'tree')):
            raise ValueError('SCM identity must be an immutable commit and tree')


def _directory(path):
    path = Path(path).absolute()
    if path.resolve(strict=True) != path or not path.is_dir():
        raise ValueError('SCM directory must be canonical and not a symlink')
    return path


def git_environment():
    # A new mapping, not a filtered copy: GIT_CONFIG_COUNT/PARAMETERS, HOME,
    # GIT_DIR/WORK_TREE, LD_PRELOAD and user CI branch overrides cannot enter.
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_TERMINAL_PROMPT': '0',
            'GIT_ALLOW_PROTOCOL': 'file', 'GIT_OPTIONAL_LOCKS': '0'}


def _git(repo, *args):
    return subprocess.check_output(
        ['/usr/bin/git', '--no-replace-objects', '-c', 'core.hooksPath=/dev/null',
         '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-C', str(repo), *args],
        env=git_environment(), stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
        timeout=120)


def _text(repo, *args):
    return _git(repo, *args).decode('utf-8').strip()


def _source_inventory(root):
    result = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        parent = Path(parent)
        if '.git' in directories:
            if parent != root:
                raise ValueError('Nested Git metadata in selected source')
            directories.remove('.git')
        for name in directories + files:
            p = parent / name
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError('Unsupported selected source entry')
            if name == '.git':
                raise ValueError('Unexpected Git metadata file')
            if stat.S_ISREG(mode):
                result[p.relative_to(root).as_posix()] = [sha(p), stat.S_IMODE(mode)]
    return result


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _nearest(repo, expected):
    if Path(_text(repo, 'rev-parse', '--show-toplevel')) != expected:
        raise ValueError('Git discovered a different source root')


def prepare(source, repos, selections):
    """Attach genuine detached metadata to exact exports, without checking out.

    Only fresh staging clones and each export's new .git are mutated. A failure
    may leave already attached metadata; the fresh build must then be abandoned.
    """
    _selections(selections)
    if type(repos) is not dict or set(repos) != set(ROOTS):
        raise ValueError('Expected exactly the declared retained repositories')
    source = _directory(source)
    inputs = {}
    # Validate all roots before creating any metadata.
    for name in ROOTS:
        root, repo = _directory(source / name), _directory(repos[name])
        if os.path.lexists(root / '.git'):
            raise ValueError('Export already has Git metadata')
        original = _source_inventory(root)
        bare = _text(repo, 'rev-parse', '--is-bare-repository')
        if bare == 'true':
            if Path(_text(repo, 'rev-parse', '--absolute-git-dir')) != repo:
                raise ValueError('Declared bare repository identity differs')
        elif bare == 'false':
            _nearest(repo, repo)
        else:
            raise ValueError('Invalid declared repository type')
        commit, tree = selections[name]['commit'], selections[name]['tree']
        if (_text(repo, 'rev-parse', commit + '^{commit}') != commit or
                _text(repo, 'rev-parse', commit + '^{tree}') != tree):
            raise ValueError('Declared source commit/tree differs')
        objects = Path(_text(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'objects'))
        objects = _directory(objects)
        inputs[name] = (root, repo, original, objects)
    records = {}
    for name in ROOTS:
        root, repo, original, objects = inputs[name]
        commit, tree = selections[name]['commit'], selections[name]['tree']
        with tempfile.TemporaryDirectory(prefix='owned-scm-', dir=source.parent) as temporary:
            stage = Path(temporary)
            template = stage / 'empty-template'
            template.mkdir()
            clone = stage / 'clone'
            _git(stage, 'clone', '--shared', '--no-checkout', '--no-tags',
                 '--template=' + str(template), '-c', 'core.hooksPath=/dev/null',
                 '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '--', str(repo), str(clone))
            _git(clone, 'update-ref', '--no-deref', 'HEAD', commit)
            _git(clone, 'read-tree', commit)
            metadata = clone / '.git'
            if metadata.is_symlink() or not metadata.is_dir():
                raise ValueError('Clone metadata is not a real directory')
            alternates = metadata / 'objects/info/alternates'
            if alternates.read_text() != str(objects) + '\n':
                raise ValueError('Shared clone object store differs from declared input')
            if (metadata / 'HEAD').read_text() != commit + '\n':
                raise ValueError('Clone HEAD is not detached at selected commit')
            os.rename(metadata, root / '.git')
        _nearest(root, root)
        _nearest(root / MAVEN_ROOTS[name], root)
        if (_text(root, 'rev-parse', 'HEAD') != commit or
                _text(root, 'rev-parse', 'HEAD^{tree}') != tree):
            raise ValueError('Attached metadata changed selected identity')
        # Verify index IDs/modes directly, without a refresh, checkout or filters.
        tree_rows = _git(repo, 'ls-tree', '-r', '-z', commit).split(b'\0')
        index_rows = _git(root, 'ls-files', '--stage', '-z').split(b'\0')
        expected = []
        selected_paths = set()
        for row in tree_rows:
            if row:
                info, path = row.split(b'\t', 1)
                mode, kind, oid = info.split()
                if kind != b'blob' or mode not in (b'100644', b'100755'):
                    raise ValueError('Unsupported selected Git tree entry')
                filename = path.decode('utf-8')
                relative = PurePosixPath(filename)
                if (relative.is_absolute() or relative.as_posix() != filename or
                        '..' in relative.parts or filename not in original):
                    raise ValueError('Selected tree and export paths differ')
                data = (root / filename).read_bytes()
                blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                if (blob.encode() != oid or original[filename][1] !=
                        (0o755 if mode == b'100755' else 0o644)):
                    raise ValueError('Export bytes or mode differ from selected Git blob')
                selected_paths.add(filename)
                expected.append(mode + b' ' + oid + b' 0\t' + path)
        if selected_paths != set(original) or index_rows != expected + [b'']:
            raise ValueError('Attached Git index differs from selected tree')
        if _source_inventory(root) != original:
            raise ValueError('SCM preparation changed exported source bytes or modes')
        records[name] = {'commit': commit, 'tree': tree, 'repository': str(repo),
                         'object_store': str(objects), 'object_store_must_remain_available': True,
                         'alternates_sha256': sha(root / '.git/objects/info/alternates'),
                         'source_files': len(original), 'source_inventory_sha256': _digest(original),
                         'nearest_root_verified': True, 'index_verified': True,
                         'source_bytes_and_modes_unchanged': True}
    return {'roots': records, 'serial_reactor_required': True, 'network_fetch': False}


def _archive(stream):
    archive = zipfile.ZipFile(stream)
    names = archive.namelist()
    if len(names) != len(set(names)):
        archive.close()
        raise ValueError('Duplicate archive member')
    if sum(n.lower() == 'meta-inf/manifest.mf' for n in names) != 1:
        archive.close()
        raise ValueError('Missing or ambiguous manifest')
    return archive


def _manifest(archive):
    lines = archive.read('META-INF/MANIFEST.MF').decode('utf-8').splitlines()
    unfolded = []
    for line in lines:
        if not line:
            break
        if line.startswith(' '):
            if not unfolded:
                raise ValueError('Invalid manifest continuation')
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    result = {}
    for line in unfolded:
        key, separator, value = line.partition(': ')
        key = key.lower()
        if not separator or key in result or not re.fullmatch('[a-z0-9_-]+', key):
            raise ValueError('Ambiguous manifest attribute')
        result[key] = value
    return result


def _revision(manifest, family, commit, required):
    key = 'implementation-version' if family == 'geowebcache' else 'git-revision'
    value = manifest.get(key)
    if value is None and not required:
        return False
    valid = value == commit
    if family == 'geowebcache':
        valid = (type(value) is str and value.endswith('/' + commit) and
                 bool(value[:-41]) and '${' not in value and
                 not any(ord(c) < 32 or ord(c) == 127 for c in value))
    if not valid:
        raise ValueError('Owned artifact revision differs: ' + family)
    return True


def _resources(archive, commit, required=False):
    names = {}
    for path in archive.namelist():
        name = PurePosixPath(path).name
        if name in REVISION_RESOURCES:
            if name in names:
                raise ValueError('Localized GeoServer revision resource is ambiguous')
            names[name] = path
    if required and set(names) != REVISION_RESOURCES:
        raise ValueError('Localized GeoServer revision membership differs')
    for name in names.values():
        revisions = re.findall(r'^\s*(?:#\s*)?build\.revision\s*=\s*([^\r\n]*)',
                               archive.read(name).decode('latin1'), re.MULTILINE)
        # Extension/test translation bundles share these basenames without
        # publishing a revision. Any revision they do publish remains exact.
        if (required or revisions) and revisions != [commit]:
            raise ValueError('Localized GeoServer revision differs')
    return len(names)


def verify_artifacts(source, artifacts, selections):
    """Verify the fixed aggregate's actual bytes; never trust a manifest alone."""
    _selections(selections)
    source = _directory(source)
    built = {}
    by_name = {}
    checked = []
    for row in artifacts['built']:
        name = row['path']
        relative = PurePosixPath(name)
        if (relative.is_absolute() or relative.as_posix() != name or
                '..' in relative.parts or '\\' in name or name in built):
            raise ValueError('Invalid or duplicate built artifact path')
        p = source / name
        if p.resolve(strict=True) != p or not p.is_file() or p.parent.name != 'target':
            raise ValueError('Built artifact escapes selected source')
        if sha(p) != row['sha256'] or p.stat().st_size != row['bytes']:
            raise ValueError('Built artifact bytes changed')
        built[name] = row
        family = relative.parts[0]
        if family in ROOTS and p.suffix == '.jar':
            by_name.setdefault(p.name, []).append((family, row['sha256']))
            with _archive(p) as z:
                present = _revision(_manifest(z), family, selections[family]['commit'], False)
                resources = 0
                if family == 'geoserver' and not p.name.endswith(('-sources.jar', '-test-sources.jar')):
                    resources = _resources(z, selections[family]['commit'],
                                           p.name.startswith('gs-web-core-') and
                                           not p.name.endswith('-tests.jar'))
                checked.append({'path': name, 'revision_present': present, 'localized_resources': resources})
    actual = {p.relative_to(source).as_posix() for p in source.rglob('*')
              if p.is_file() and p.parent.name == 'target' and p.suffix in ('.jar', '.war')}
    if set(built) != actual:
        raise ValueError('Built artifact inventory is incomplete')
    war = Path(artifacts['war'])
    if (war.resolve(strict=True) != war or not war.is_relative_to(source) or
            war.relative_to(source).as_posix() not in built or
            sha(war) != artifacts['war_sha256']):
        raise ValueError('WAR identity differs')
    if {n for n in built if n.endswith('.war')} != {war.relative_to(source).as_posix()}:
        raise ValueError('Expected exactly the selected aggregate WAR')
    embedded, counts = [], dict.fromkeys(ROOTS, 0)
    with _archive(war) as z:
        _revision(_manifest(z), 'geoserver', selections['geoserver']['commit'], True)
        for name in z.namelist():
            base = Path(name).name
            if not (name.startswith('WEB-INF/lib/') and base.endswith('.jar')):
                continue
            family = next((f for prefix, f in (('gt-', 'geotools'), ('gs-', 'geoserver'),
                           ('gwc-', 'geowebcache'), ('geowebcache-', 'geowebcache'))
                           if base.startswith(prefix)), None)
            if family is None:
                continue
            if name != 'WEB-INF/lib/' + base:
                raise ValueError('Owned WAR member path is ambiguous')
            data = z.read(name)
            digest = hashlib.sha256(data).hexdigest()
            if by_name.get(base) != [(family, digest)]:
                raise ValueError('Embedded owned JAR does not match unique built module')
            with _archive(io.BytesIO(data)) as jar:
                _revision(_manifest(jar), family, selections[family]['commit'], True)
                if family == 'geoserver':
                    _resources(jar, selections[family]['commit'], base.startswith('gs-web-core-'))
            counts[family] += 1
            embedded.append({'entry': name, 'sha256': digest})
    if counts != EMBEDDED_COUNTS:
        raise ValueError('Fixed owned aggregate family membership differs')
    reported = artifacts['owned_embedded_jars']
    if sorted(embedded, key=lambda x: x['entry']) != sorted(reported, key=lambda x: x['entry']):
        raise ValueError('Reported embedded owned inventory differs')
    if sum(x['entry'].startswith('WEB-INF/lib/gs-web-core-') for x in embedded) != 1:
        raise ValueError('Expected one GeoServer localized revision module')
    return {'war_sha256': sha(war), 'embedded_counts': counts,
            'embedded_owned_jars': len(embedded), 'other_owned_manifests': checked,
            'localized_revision_resources': len(REVISION_RESOURCES),
            'per_root_revisions_verified': {k: selections[k]['commit'] for k in ROOTS}}
