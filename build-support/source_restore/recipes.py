"""Replay the accepted FND-02 source selection without compiling or networking.

The candidate stays authoritative. This module produces a restoration receipt,
not another selection manifest. It executes guarded historical source recipes,
checks their output against the tested producer records, and records packaging
separately from editable source. All outputs are private custody material.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import zipfile

CANDIDATE_SHA = '0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99'


def git_environment():
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': '/dev/null',
            'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_ATTR_NOSYSTEM': '1',
            'GIT_ALLOW_PROTOCOL': 'file', 'GIT_LFS_SKIP_SMUDGE': '1'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_path(root, relative):
    relative = PurePosixPath(relative)
    require(relative.parts and not relative.is_absolute() and '..' not in relative.parts,
            'unsafe source path: ' + str(relative))
    root = Path(root).absolute()
    path = root.joinpath(*relative.parts)
    require(path.resolve().is_relative_to(root.resolve()), 'source symlink escape: ' + str(path))
    for part in [path, *path.parents]:
        if part == root.parent:
            break
        require(not part.is_symlink(), 'source symlink not allowed: ' + str(part))
    return path


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def checked(root, relative, digest, size=None):
    path = safe_path(root, relative)
    require(path.is_file(), 'required source asset missing: ' + str(path))
    require(sha(path) == digest and (size is None or path.stat().st_size == size),
            'source asset integrity mismatch: ' + str(path))
    return path


def inventory(root):
    """Regular source files only; never follow a link or walk repository internals."""
    root = Path(root)
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != '.git')
        for name in dirs:
            require(not (Path(directory) / name).is_symlink(), 'symlinked source directory')
        for name in sorted(files):
            path = Path(directory) / name
            if name == '.git':
                continue
            require(not path.is_symlink(), 'symlinked source file: ' + str(path))
            result[path.relative_to(root).as_posix()] = sha(path)
    return result


def compare(root, expected, label, exact=True):
    actual = inventory(root)
    require(all(actual.get(p) == digest for p, digest in expected.items()),
            label + ': source bytes differ or are missing: ' + repr(
                [p for p, digest in expected.items() if actual.get(p) != digest][:8]))
    require(not exact or set(actual) == set(expected), label + ': unexpected source files')
    return {'scope': label, 'files_verified': len(expected), 'exact_membership': exact,
            'additional_preserved_source_files': sorted(set(actual)-set(expected)),
            'inventory_sha256': hashlib.sha256(json.dumps(actual, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()}


def archive_entries(path, strip=0):
    """Validate every entry before yielding; links and duplicate paths fail closed."""
    entries = {}
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                require((entry.external_attr >> 16) & 0o170000 != 0o120000,
                        'archive symlink is not allowed')
                parts = PurePosixPath(entry.filename).parts
                require(not PurePosixPath(entry.filename).is_absolute() and '..' not in parts,
                        'unsafe archive member')
                name = '/'.join(parts[strip:])
                require(name and name not in entries, 'duplicate or empty archive member')
                entries[name] = archive.read(entry)
    else:
        with tarfile.open(path) as archive:
            for entry in archive:
                parts = PurePosixPath(entry.name).parts
                require(not PurePosixPath(entry.name).is_absolute() and '..' not in parts,
                        'unsafe archive member')
                if entry.isdir():
                    continue
                require(entry.isfile(), 'non-regular source archive member: ' + entry.name)
                name = '/'.join(parts[strip:])
                require(name and name not in entries, 'duplicate or empty archive member')
                entries[name] = archive.extractfile(entry).read()
    return entries


def write_entries(root, entries):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    for name, data in sorted(entries.items()):
        path = safe_path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Selection:
    def __init__(self, platform, workspace, output):
        self.platform, self.workspace, self.output = map(Path, (platform, workspace, output))
        manifest = checked(self.platform, 'plan/candidates/fnd-02-candidate.json', CANDIDATE_SHA)
        self.candidate = json.loads(manifest.read_text())
        self.records = {r['id']: r for r in self.candidate['records']}
        self.used = {}

    def record(self, name):
        row = self.records[name]
        base = self.platform if row['location']['root'] == 'platform' else self.workspace
        path = checked(base, row['location']['path'], row['sha256'], row.get('bytes'))
        self.used[name] = {'location': row['location'], 'sha256': row['sha256'],
                           'bytes': path.stat().st_size}
        return path

    def document(self, name):
        return json.loads(self.record(name).read_text())

    def platform_recipe(self, relative, expected):
        return checked(self.platform, relative, expected)


def replay_java(selection, repos, output):
    """Replay exactly the pre-compilation aggregate source tree, including vendors."""
    accepted = selection.document('json-nojpeg-build')
    recipes = selection.platform / 'build-support/java'
    # Bind imported helpers and data as a set to the actual executed recipe snapshot.
    for relative, digest in accepted['tooling_manifest'].items():
        checked(selection.platform / 'build-support', relative, digest)
    source = output / 'java-source'
    source.mkdir()
    originals = {}
    for key in ['geotools', 'geowebcache', 'geoserver', 'geofence', 'mapfish']:
        entries = archive_entries(selection.record('source-' + key))
        for name, data in entries.items():
            require(name not in originals, 'overlapping Java source archive')
            originals[name] = hashlib.sha256(data).hexdigest()
            path = safe_path(source, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    saved_path = list(sys.path)
    sys.path.insert(0, str(recipes))
    try:
        resolution = load_module(recipes / 'resolution.py', 'resolution')
        modules = ''.join('<module>' + r + '</module>' for r in resolution.ROOTS)
        (source / 'pom.xml').write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0">'
            '<modelVersion>4.0.0</modelVersion><groupId>org.ambisgis.audit</groupId>'
            '<artifactId>java-resolution</artifactId><version>1</version>'
            '<packaging>pom</packaging><modules>' + modules + '</modules></project>\n')
        patch = recipes / 'compatibility-patches/xmlcodegen-emf.json'
        guard = json.loads(patch.read_text())
        target = safe_path(source, guard['path'])
        require(sha(target) == guard['before_sha256'], 'incorrect Java patch base/order')
        proc = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'apply',
            str(patch.with_suffix('.patch'))], cwd=source, env=git_environment(), capture_output=True, text=True)
        require(proc.returncode == 0 and sha(target) == guard['after_sha256'],
                'guarded XML patch failed: ' + proc.stderr)
        changes = {'xmlcodegen': guard}
        changes['lifecycle'] = load_module(recipes/'combined_logging_patch.py', 'combined_logging_patch').prepare(source)
        compat = load_module(recipes/'compatibility.py', 'compatibility')
        changes['oauth'] = compat.prepare_webapp_oauth(source, principal=True)
        for name in ['configured_auth_repairs', 'configured_auth_stateless', 'role_service_repair']:
            changes[name] = load_module(recipes/(name+'.py'), name).prepare(source, repair=True, tests=False)
        changes['no_oracle'] = load_module(recipes/'no_oracle.py', 'no_oracle').prepare(source)
        changes['no_jpeg2000'] = load_module(recipes/'remediation-nojpeg2000/profile.py', 'restore_nojpeg').prepare(source)
        changes['no_jpeg2000_geoserver'] = load_module(recipes/'remediation-nojpeg2000/geoserver_profile.py', 'restore_nojpeg_geoserver').prepare(source)
    finally:
        sys.path[:] = saved_path
    expected = selection.document('json-nojpeg-source-tree')
    result = {'comparison': compare(source, expected, 'exact tested Java source tree'),
              'transformations': changes, 'roots': {},
              'class_b': ['GeoFence 3.8.3', 'MapFish 2.4.1'],
              'generated_reactor': {'path': 'java-source/pom.xml', 'sha256': sha(source/'pom.xml')}}
    for key in ['geotools', 'geowebcache', 'geoserver']:
        prefix = key + '/'
        selected = {p[len(prefix):]: digest for p, digest in expected.items() if p.startswith(prefix)}
        changed = []
        for name, digest in selected.items():
            if originals.get(prefix+name) != digest:
                target = safe_path(repos[key], name)
                require((not target.exists() and prefix+name not in originals)
                        or (target.is_file() and sha(target) == originals.get(prefix+name)),
                        'fresh repository differs from accepted patch base: ' + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((source / prefix / name).read_bytes())
                changed.append({'path': name, 'before_sha256': originals.get(prefix+name), 'after_sha256': digest})
        result['roots'][key] = {'changes': changed,
            'comparison': compare(repos[key], selected, 'tested ' + key + ' archive file set', exact=False)}
    return result


def replay_geonode(selection, repos):
    receipt = selection.document('geonode-build')
    recipes = selection.platform/'build-support/geonode'
    for key, rel in [('geonode-compatibility-recipe','inputs.py'),
                     ('geonode-verifier-repair','verifier_repair.py'),
                     ('geonode-role-repair','roles_repair.py')]:
        selected = selection.record(key)
        require(sha(recipes/rel) == sha(selected), 'GeoNode recipe differs')
    for key in ['source_repair', 'role_source_repair']:
        for row in receipt[key]['recipe_inputs']:
            checked(recipes, Path(row['path']).name, row['sha256'])
    source = repos['geonode']
    inputs = load_module(recipes/'inputs.py', 'restore_geonode_inputs')
    project = source/'pyproject.toml'
    require(sha(project) == receipt['compatibility_patch']['baseline_sha256'], 'GeoNode declaration base mismatch')
    text, patch = inputs.patch_project(project.read_text())
    project.write_text(text)
    require(sha(project) == receipt['compatibility_patch']['patched_sha256'], 'GeoNode declaration output mismatch')
    saved = list(sys.path)
    sys.path.insert(0, str(recipes))
    try:
        verifier = load_module(recipes/'verifier_repair.py', 'verifier_repair')
        verifier_result = verifier.apply(source)
        roles = load_module(recipes/'roles_repair.py', 'restore_geonode_roles')
        roles_result = roles.apply(source)
    finally:
        sys.path[:] = saved
    entries = archive_entries(selection.record('source-geonode'))
    # This archive deliberately has no path prefix.
    expected = {p: hashlib.sha256(data).hexdigest() for p, data in entries.items()}
    expected['pyproject.toml'] = receipt['compatibility_patch']['patched_sha256']
    expected.update(receipt['source_repair']['expected_files'])
    expected.update(receipt['role_source_repair']['expected_files'])
    return {'comparison': compare(source, expected, 'GeoNode guarded complete archive', exact=False),
            'compatibility': patch, 'verifier': verifier_result, 'roles': roles_result}


def replay_frontend(selection, repos, output):
    rows = selection.document('frontend-replay-source-patches')
    changes = []
    for row in rows:
        key = 'mapstore-client' if row['component'] == 'client' else 'mapstore'
        path = safe_path(repos[key], row['path'])
        require(sha(path) == row['source_sha256'], 'frontend source patch base mismatch')
        data = json.loads(path.read_text())
        if key == 'mapstore-client':
            require(data['devDependencies']['@mapstore/project'] == 'git+https://github.com/geosolutions-it/mapstore-project.git#master', 'client declaration guard')
            data['devDependencies']['@mapstore/project'] = 'file:vendor/project.tar.gz'
        else:
            require(data['dependencies']['@mapstore/patcher'] == 'https://github.com/geosolutions-it/Patcher/tarball/master', 'MapStore declaration guard')
            data['dependencies']['@mapstore/patcher'] = 'file:../vendor/patcher.tar.gz'
        path.write_text(json.dumps(data, indent=2)+'\n')
        require(sha(path) == row['selected_sha256'], 'frontend source output mismatch')
        changes.append({'root': key, 'path': row['path'], 'before_sha256': row['source_sha256'], 'after_sha256': row['selected_sha256']})
    # Retain the exact local dependency declarations and frozen lock beside sources.
    frontend = output/'frontend-inputs'
    frontend.mkdir()
    for key in ['frontend-project-source','frontend-patcher-source','frontend-nomnom-source','frontend-package-lock']:
        src = selection.record(key)
        shutil.copyfile(src, frontend/src.name)
    return {'changes': changes, 'local_inputs': inventory(frontend),
            'packaging': 'Inherited compiled dist/ms-translations removed by accepted frontend recipe before compilation; generated outputs are not source.'}


def replay_notebook(selection, repos):
    receipt = selection.document('jupyter-build')
    recipe = selection.record('jupyter-build-recipe')
    path = repos['jupyterhub']/'MANIFEST.in'
    before = sha(path)
    includes = receipt['hub_archive_packaging']['included_owned_data']
    for relative in includes:
        require(safe_path(repos['jupyterhub'], relative).is_file(), 'required Hub runtime data missing')
    with path.open('a') as stream:
        stream.write('\n# AmbisGIS archive packaging: owned tracked runtime data\n')
        stream.writelines('include '+relative+'\n' for relative in includes)
    require(sha(path) == receipt['hub_archive_packaging']['manifest_sha256'], 'Hub archive packaging output differs')
    return {'jupyterhub': {'changes': [{'path':'MANIFEST.in','before_sha256':before,'after_sha256':sha(path)}],
                           'included_owned_data':includes},
            'jupyterlab': {'changes': [], 'generation': 'Owned workspaces compile static/schemas/themes; wheel packaging excludes development directories and .js.map. No compiled outputs relabeled as source.'},
            'recipe_sha256': sha(recipe)}


def replay_qgis(selection, repos, output):
    source = repos['qgis']
    expected = selection.document('qgis-generated-source')
    for relative, digest in expected['generator_identities'].items():
        checked(source, relative, digest)
    # Original generator emits filesystem enumeration order. Recover its recorded
    # order, then regenerate every row from recovered editable description/ext inputs.
    row = expected['added'][0]
    retained = selection.workspace/'build-worktrees/qgis-candidate/build-06/sources/qgis-3.44.14'/row['path']
    checked(retained.parent, retained.name, row['sha256'], row['bytes'])
    original = json.loads(retained.read_text())
    parsed = load_module(source/'python/plugins/grassprovider/parsed_description.py', 'restore_grass_description')
    descriptions = source/'python/plugins/grassprovider/description'
    generated = {}
    for path in sorted(descriptions.glob('*.txt')):
        description = parsed.ParsedDescription.parse_description_file(path, translate=False)
        if path.parents[1].joinpath('ext', description.name.replace('.', '_')+'.py').exists():
            description.ext_path = description.name.replace('.', '_')
        require(description.name not in generated, 'ambiguous GRASS description name')
        generated[description.name] = description.as_dict()
    order = [r['name'] for r in original]
    require(set(order) == set(generated) and len(order) == len(generated), 'GRASS input membership differs')
    payload = json.dumps([generated[name] for name in order], indent=2).encode()
    require(hashlib.sha256(payload).hexdigest() == row['sha256'], 'GRASS generated source differs')
    generated_path = output/'generated/qgis'/row['path']
    generated_path.parent.mkdir(parents=True, exist_ok=True)
    generated_path.write_bytes(payload)
    save(output/'generated/qgis/generation-order.json', {'input':'accepted generator output row order',
        'accepted_generated_sha256':row['sha256'], 'order':order})
    # Selected palette source view is generated from source, not the staged binaries.
    membership = selection.document('java-gmt-qgis-membership')
    final = selection.document('java-gmt-qgis-output')
    resource_prefix = 'share/qgis/resources/cpt-city-qgis-min/'
    source_prefix = 'resources/cpt-city-qgis-min/'
    resources = output/'qgis-selected-resources'
    resources.mkdir()
    selected_rows = {r['path']: r for r in final['files'] if r['path'].startswith(resource_prefix)}
    # Retain source originals and exact accepted catalogue transformations separately.
    evidence = selection.document('java-gmt-qgis-selection')
    parent = selection.document('qgis-selection-result')
    changes = {r['path']: r for r in parent['catalogue_changes']}
    for r in evidence['catalogue_changes']:
        changes[r['path']] = r
    resource_recipe = selection.platform/'build-support/qgis/resource_selection.py'
    stage_tooling = selection.document('java-gmt-qgis-stage-tooling')
    # Binding for the source-only trim helper comes from accepted executed tooling.
    for row in stage_tooling['files']:
        checked(resource_recipe.parent, row['path'], row['sha256'], row.get('bytes'))
    # Current recipe identity is also in the hash-bound selection result.
    expected_recipe = evidence['executed_recipe']['files_before']['resource_selection.py']['sha256']
    require(sha(resource_recipe) == expected_recipe, 'QGIS resource recipe differs')
    old_path = list(sys.path)
    old_common = sys.modules.pop('common', None)
    sys.path.insert(0, str(resource_recipe.parent))
    try:
        common = load_module(resource_recipe.parent/'common.py','common')
        trim = load_module(resource_recipe, 'restore_qgis_selection').trim_catalogue
        omitted_roots = [r.removeprefix(resource_prefix) for r in membership['omitted_collection_roots']]
        for name, item in selected_rows.items():
            relative = name.removeprefix(resource_prefix)
            src = safe_path(source, source_prefix+relative)
            data = src.read_bytes()
            if relative.startswith('selections/') and relative.endswith('.xml'):
                data, _ = trim(data, omitted_roots)
                data, _ = trim(data, omitted_roots, {'gmt/GMT_dem1'})
            require(hashlib.sha256(data).hexdigest() == item['sha256'], 'selected QGIS resource differs: '+relative)
            dst = safe_path(resources, relative)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
    finally:
        sys.path[:] = old_path
        sys.modules.pop('common', None)
        if old_common is not None:
            sys.modules['common'] = old_common
    require(not set(membership['exclusions']) & set(selected_rows), 'excluded QGIS source selected')
    return {'source_changes': [], 'generated': {'path':str(generated_path.relative_to(output)),
        'sha256':row['sha256'],'records':len(order),'method':'Accepted parser and source inputs, explicit retained emission order; generated file remains derived output'},
        'resource_comparison': {'files_verified':len(selected_rows), 'excluded_palettes':len(membership['exclusions']),
            'inventory_sha256':hashlib.sha256(json.dumps(inventory(resources),sort_keys=True).encode()).hexdigest()},
        'custody': 'Original excluded source assets/notices stay in the core repository under original terms; selected source resources are separate non-distribution output.'}


def replay_vendors(selection, output):
    vendor = output/'vendors'
    vendor.mkdir()
    result = {}
    old = selection.document('java-gmt-source-evidence-0-1')
    manifest_path = checked(selection.platform, 'build-support/java/remediation-source/inputs.json', old['inputs_sha256'])
    inputs = json.loads(manifest_path.read_text())['inputs']
    source_manifest = selection.document('java-gmt-source-evidence-0-0')
    def input_path(key):
        row = inputs[key]
        return checked(selection.workspace, row['path'], row['sha256'], row.get('bytes'))
    aspectj = vendor/'aspectj'
    write_entries(aspectj, archive_entries(input_path('aspectj-source'), strip=1))
    write_entries(aspectj/'embedded-bcel', archive_entries(aspectj/'lib/bcel/bcel-src.zip'))
    version = aspectj/'bridge/src/org/aspectj/bridge/Version.java'
    old_text = 'public static final String text = "DEVELOPMENT";'
    text = version.read_text()
    require(text.count(old_text) == 1, 'AspectJ patch base mismatch')
    version.write_text(text.replace(old_text, 'public static final String text = "1.5.4-ambisgis-source-1";'))
    expected = {r['path'].removeprefix('source/aspectj/'):r['sha256'] for r in source_manifest if r['path'].startswith('source/aspectj/')}
    result['aspectj'] = compare(aspectj, expected, 'AspectJ selected source (including embedded BCEL)')
    notices = vendor/'notices'
    notices.mkdir()
    for key in ['epl-license', 'xmlpull-license']:
        shutil.copyfile(input_path(key), notices/(key+'.txt'))
    xmlpull = vendor/'xmlpull'
    entries = archive_entries(input_path('xpp3-source'))
    selected = {p:data for p,data in entries.items() if p in {
        'org/xmlpull/v1/'+n+'.java' for n in ['XmlPullParser','XmlPullParserException','XmlPullParserFactory','XmlSerializer']}}
    require(len(selected) == 4, 'XMLPull selected source missing')
    write_entries(xmlpull, selected)
    expected = {r['path'].removeprefix('source/xmlpull/'):r['sha256'] for r in source_manifest if r['path'].startswith('source/xmlpull/')}
    result['xmlpull'] = compare(xmlpull, expected, 'Selected XMLPull source API')
    result['aspectj']['compile_selection'] = 'runtime/aspectj5rt/asm/bridge/util/weaver/loadtime/weaver5/loadtime5 src and java5-src plus embedded BCEL; JRockitAgent excluded. Retained binaries are custody only, not recovered editable source.'
    result['historical_json'] = 'Earlier json-lib source variant is not selected or restored as active source.'
    json_root = vendor/'json-compat'
    expected_rows = selection.document('json-nojpeg-source-evidence-3-1')
    entries = {}
    for row in expected_rows:
        path = checked(selection.platform/'build-support/java/remediation-json/src', row['path'], row['sha256'], row['bytes'])
        entries[row['path']] = path.read_bytes()
    write_entries(json_root, entries)
    for name in ['NOTICE.txt']:
        shutil.copyfile(selection.platform/'build-support/java/remediation-json'/name,notices/('json-compat-'+name))
    result['json-compat'] = compare(json_root, {r['path']:r['sha256'] for r in expected_rows}, 'Independent Apache-2.0 JSON compatibility source')
    json_inputs = selection.document('json-nojpeg-source-evidence-3-2')
    supplement = vendor/'json-inputs'
    supplement.mkdir()
    for key, row in json_inputs['inputs'].items():
        if key == 'jackson-core-binary':
            continue
        source = checked(selection.workspace, row['path'], row['sha256'], row.get('bytes'))
        shutil.copyfile(source, supplement/key)
    jackson = json_inputs['inputs']['jackson-core-source']
    write_entries(vendor/'jackson-core', archive_entries(checked(selection.workspace, jackson['path'], jackson['sha256'])))
    result['jackson-core'] = {'version':'2.21.0', 'source_sha256':jackson['sha256'],
        'fastdoubleparser':'Exact source archives, correspondence and original notice files retained in json-inputs; no binary equivalence claimed.'}
    marlin = selection.document('json-nojpeg-source-evidence-4-0')
    marlin_source = vendor/'marlin'
    write_entries(marlin_source, archive_entries(selection.record('json-nojpeg-source-evidence-4-1'), strip=1))
    compare(marlin_source, {r['path']:r['sha256'] for r in marlin['original_source_manifest']}, 'Original Marlin source')
    engine = marlin_source/'src/main/java/sun/java2d/marlin/DMarlinRenderingEngine.java'
    text = engine.read_text()
    needle = '    public DMarlinRenderingEngine() {\n        super();'
    require(text.count(needle) == 1, 'Marlin constructor patch base mismatch')
    text = text.replace('package sun.java2d.marlin;', '// AmbisGIS modification 2026-09-21: enforce headless/no-OpenGL profile; original copyright and Classpath exception retained.\npackage sun.java2d.marlin;')
    text = text.replace(needle, needle+'\n        if (!java.awt.GraphicsEnvironment.isHeadless() || Boolean.getBoolean("sun.java2d.opengl")) {\n            throw new IllegalStateException("'+marlin['identity']+' requires headless=true and opengl=false");\n        }')
    engine.write_text(text)
    version = marlin_source/'src/main/java/sun/java2d/marlin/Version.java'
    text = version.read_text().replace('marlin-0.9.4.8-Unsafe-OpenJDK',marlin['identity'])
    text = text.replace('package sun.java2d.marlin;', '// AmbisGIS modification 2026-09-21: label the owned headless variant; original copyright and Classpath exception retained.\npackage sun.java2d.marlin;')
    version.write_text(text)
    result['marlin'] = compare(marlin_source, {r['path']:r['sha256'] for r in marlin['selected_source_manifest']}, 'Headless Temurin17 Marlin source')
    result['marlin']['compile_exclusion'] = 'src/main/java/sun/java2d/marlin/TestArrayCacheInt.java; headless=true, opengl=false and pinned patch-module renderer required'
    imageio = selection.document('json-nojpeg-source-evidence-5-0')
    all_entries = archive_entries(selection.record('json-nojpeg-source-evidence-5-1'), strip=1)
    imageio_original = vendor/'imageio-original-custody'
    write_entries(imageio_original, {p:d for p,d in all_entries.items() if not p.endswith(('.so','.dll','.jar'))})
    compare(imageio_original, {r['path']:r['sha256'] for r in imageio['original_source_manifest']}, 'ImageIO original source custody (not distribution)')
    source_prefix = 'src/share/classes/'
    entries = {}
    for name, data in all_entries.items():
        if not name.startswith(source_prefix):
            continue
        relative = name.removeprefix(source_prefix)
        leaf = PurePosixPath(relative).name
        excluded = relative.startswith(('com/sun/media/jai/', 'jj2000/', 'com/sun/media/imageio/plugins/jpeg2000/', 'com/sun/media/imageioimpl/plugins/jpeg2000/'))
        excluded |= relative.endswith('.java') and ('CodecLib' in leaf or leaf.startswith('CLib') or leaf == 'MediaLibAccessor.java')
        if not excluded:
            entries[relative] = data
    imageio_selected = vendor/'imageio-selected'
    write_entries(imageio_selected, entries)
    recipe = selection.platform/'build-support/java/remediation-nojpeg2000/build_imageio.py'
    require(sha(recipe) == imageio['recipe']['sha256'], 'ImageIO recipe changed')
    old_path = list(sys.path)
    sys.path.insert(0, str(recipe.parent.parent))
    try:
        helpers = load_module(recipe,'restore_imageio')
        common = imageio_selected/'com/sun/media/imageioimpl/common/PackageUtil.java'
        helpers.replace_guarded(common,'import com.sun.medialib.codec.jiio.Util;','// AmbisGIS Java-only profile has no proprietary codecLib dependency.')
        helpers.replace_guarded(common,'isCodecLibAvailable = Util.isCodecLibAvailable();','isCodecLibAvailable = false; // AmbisGIS: Java-only source build.')
        for name, count in [('TIFFImageReader.java',2),('TIFFImageWriter.java',3)]:
            file = imageio_selected/'com/sun/media/imageioimpl/plugins/tiff'/name
            text = helpers.remove_braced(file.read_text(encoding='iso-8859-1'), 'if(PackageUtil.isCodecLibAvailable())',count)
            file.write_text(text,encoding='iso-8859-1')
        helpers.replace_guarded(imageio_selected/'com/sun/media/imageioimpl/common/ImageUtil.java','import com.sun.medialib.codec.jiio.Util;','// AmbisGIS: unused proprietary codecLib import removed.')
    finally:
        sys.path[:] = old_path
    result['imageio'] = compare(imageio_selected, {r['path']:r['sha256'] for r in imageio['selected_source_manifest']}, 'ImageIO NO-JPEG2000 selected source')
    services = vendor/'imageio-selected-services'
    services.mkdir()
    for file in sorted((imageio_original/'src/share/services').glob('*')):
        if file.name == 'javax.media.jai.OperationRegistrySpi':
            continue
        text = '\n'.join(line for line in file.read_text(encoding='iso-8859-1').splitlines()
            if not (line.startswith('com.') and ('CLib' in line or 'CodecLib' in line or '.jpeg2000.' in line)))+'\n'
        (services/file.name).write_text(text,encoding='iso-8859-1')
    result['imageio']['spi_selection'] = inventory(services)
    result['imageio']['profile_exclusions'] = imageio['profile_exclusions']
    for name in ['LICENSE.txt','COPYRIGHT.txt']:
        shutil.copyfile(imageio_original/name,notices/('imageio-'+name))
    # web-ifc + eight pinned dependency archives remain source inputs, not a WASM rebuild claim.
    lock = selection.document('webifc-source-lock')
    result['webifc'] = []
    for row in [lock['main'], *lock['dependencies']]:
        path = selection.record('webifc-source-'+row['name'])
        source = vendor/'webifc'/row['name']
        write_entries(source, archive_entries(path, strip=1))
        result['webifc'].append({'name':row['name'],'revision':row['revision'],
            'archive_sha256':row['archive']['sha256'],'recovered_files':len(inventory(source))})
    result['classification'] = 'Class B vendored source recovery through existing candidate/replacement policy; no new public fork or redistribution approval.'
    return result


def materialize_recipes(platform, workspace, repos, output):
    """Called only after independent Git restores and network denial are established.

    ``repos`` maps all eleven candidate root IDs to their fresh independent
    repositories at the accepted donor commits. This function never commits or
    changes refs. ``output`` must not exist. Errors deliberately preserve partial
    recovery and never create a successful final receipt.
    """
    platform, workspace, output = map(lambda p:Path(p).absolute(), (platform,workspace,output))
    require(not output.exists() and not output.is_symlink(), 'fresh recipe output required')
    require(all(not p.is_symlink() for p in [output,*output.parents]), 'output symlink escape')
    require(not output.resolve().is_relative_to(platform.resolve()), 'recipe output must be outside frozen platform')
    for root in repos.values():
        require(not output.resolve().is_relative_to(Path(root).resolve()), 'recipe output inside source repository')
    output.mkdir(parents=True, exist_ok=False)
    sys.dont_write_bytecode = True
    selection = Selection(platform,workspace,output)
    require(set(repos) == {r['id'] for r in selection.candidate['roots']}, 'wrong core source roots')
    repos = {k:Path(v).absolute() for k,v in repos.items()}
    before = {}
    for row in selection.candidate['roots']:
        repo = repos[row['id']]
        require(not repo.is_symlink() and (repo/'.git').is_dir(), 'independent source repository required')
        head = subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],env=git_environment(),text=True).strip()
        require(head == row['commit'], 'wrong source revision: '+row['id'])
        dirty = subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-C',str(repo),'status','--porcelain','--untracked-files=all'],env=git_environment(),text=True)
        require(not dirty, 'fresh source repository is dirty: '+row['id'])
        before[row['id']] = inventory(repo)
    result = {'candidate_manifest_sha256':CANDIDATE_SHA,'status':'running', 'core':{}, 'limits':[
        'Source-only recovery; no compilation, product build, publication, release or remote promotion.',
        'Compiler/OS/bootstrap closure and full disconnected repair remain FND-08/OWN-02.',
        'Historical excluded source retains original rights and non-distribution status.']}
    try:
        result['java'] = replay_java(selection,repos,output)
        result['geonode'] = replay_geonode(selection,repos)
        result['frontend'] = replay_frontend(selection,repos,output)
        result['notebook'] = replay_notebook(selection,repos)
        result['qgis'] = replay_qgis(selection,repos,output)
        result['vendors'] = replay_vendors(selection,output)
        for key, repo in repos.items():
            after = inventory(repo)
            changes = [{'path':p,'before_sha256':before[key].get(p),'after_sha256':after.get(p)}
                for p in sorted(set(before[key])|set(after)) if before[key].get(p) != after.get(p)]
            # Complete file comparison records unchanged source as well as approved deltas.
            result['core'][key] = {'original_files':len(before[key]),'recovered_files':len(after),
                'changes':changes,'unchanged_files':sum(after.get(p)==digest for p,digest in before[key].items()),
                'source_inventory_sha256':hashlib.sha256(json.dumps(after,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
            save(output/'core-inventories'/(key+'.json'), after)
        result['accepted_records_verified'] = selection.used
        # Copy compact governing evidence so verification does not require old worktrees.
        for key in list(selection.used):
            path = selection.record(key)
            if path.suffix == '.json':
                target = output/'evidence'/(key+'.json')
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,target)
        result['status'] = 'passed'
    except BaseException as error:
        result['status'] = 'failed'
        result['error'] = {'type':type(error).__name__,'message':str(error)}
        save(output/'failed-recipes.json',result)
        raise
    save(output/'recipes-receipt.json',result)
    return result
