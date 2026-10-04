#!/usr/bin/env python3
"""Select retained PLT-01 image bytes; no import of selected product packages.

This recipe creates a fresh, reviewable selection and projection receipts before
the independent assembler runs. Package scripts and product services never run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import zipfile

import assemble as a
import relocate_proj
import locale_projection

GEO = '2d28e100c16e5f5c99b9c5cc20da2f75b3d7eaa4'
CLIENT = 'c1f6ad9df52f08ac3bfd7211db9e3ee744b21407'
PG = '2ff1375b5dd8bf09d8cb0e795974528180fd75ca'
GIS = '9816f82458db774e62906cfb2c4f01f8b262c862'
GS = 'fd2fe1dfcc78fa974bdb81673872879336312077'
GT = '3363c3d4ae8adfe3ed2024c27f92ec63855093be'
GWC = 'b4e9a30c8e2be00b9aa87fb17324efa8e489ac22'
WAR = '115a6a74e32847ded96c127531039e348f8be823badbf5643afbc72b00c5180b'


def ref(path, expected=None):
    path = a.regular(path); sha = a.digest(path)
    if expected and sha != expected: raise ValueError('retained identity differs: ' + str(path))
    return {'path': str(path), 'sha256': sha}


def save(path, value):
    path.write_bytes(a.encoded(value)); return ref(path)


def put(rows, name, value):
    a.relative(name)
    if name in rows:
        old = rows[name]
        # Distro packages can supply the same exact soname. Retain a single
        # physical member only when type, content/target and mode are identical.
        compare = lambda v: {k: x for k, x in v.items() if k not in ('origin', 'file')} | (
            {'sha256': v['file']['sha256']} if 'file' in v else {})
        if compare(old) != compare(value): raise ValueError('conflicting selected member: ' + name)
        old['origin'] += '; ' + value['origin']
    else: rows[name] = value


def file_row(path, origin, permissions=None, expected=None):
    value = ref(path, expected)
    return {'kind': 'file', 'file': value, 'origin': origin,
            'mode': a.mode(permissions if permissions is not None else stat.S_IMODE(Path(path).stat().st_mode))}


def verify_original_tree(root, inventory):
    value = a.document(inventory)
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != set(value): raise ValueError('retained producer membership differs')
    for name, row in value.items():
        a.relative(name); path = root / name
        if isinstance(row, str): row = {'sha256': row}
        if 'symlink' in row:
            if not path.is_symlink() or os.readlink(path) != row['symlink']: raise ValueError('retained link differs')
        elif path.is_symlink() or a.digest(a.regular(path)) != row['sha256']:
            raise ValueError('retained producer member changed: ' + name)


def tree_inventory(root):
    entries = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory) / name; relative = a.relative(str(path.relative_to(root)))
            metadata = path.lstat()
            if path.is_symlink(): row = {'kind': 'symlink', 'target': os.readlink(path)}
            elif path.is_dir(): row = {'kind': 'directory', 'mode': stat.S_IMODE(metadata.st_mode)}
            elif path.is_file(): row = {'kind': 'file', 'mode': stat.S_IMODE(metadata.st_mode),
                                        'bytes': metadata.st_size, 'sha256': a.digest(path)}
            else: raise ValueError('special source member')
            entries[relative] = row
    return {'schema_version': 1, 'entries': entries}


def main(args):
    work, custody = a.checked_path(args.work), a.checked_path(args.custody)
    output = a.checked_path(args.output); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    generated = output / 'generated'; generated.mkdir(mode=0o700)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=a.ROOT, text=True).strip()
    components, groups, proofs = [], {}, []

    def mapped(identifier, rows, provenance, revision=None):
        inventory = save(output / (identifier + '.json'), {'schema_version': 1, 'entries': rows})
        components.append({'id': identifier, 'kind': 'mapped', 'inventory': inventory,
                           'revision': revision, 'provenance': provenance}); return identifier

    def add_tree(identifier, root, destination, provenance, revision=None):
        inventory = save(output / (identifier + '.json'), tree_inventory(root))
        components.append({'id': identifier, 'kind': 'tree', 'root': str(root), 'destination': destination,
                           'inventory': inventory, 'revision': revision, 'provenance': provenance}); return identifier

    def add_wheel(identifier, path, sha, provenance, revision=None):
        components.append({'id': identifier, 'kind': 'wheel', 'archive': ref(path, sha),
                           'destination': 'opt/ambisgis/python-site', 'revision': revision, 'provenance': provenance})
        return identifier

    # Signed RPM extraction remains inert. Select full CPython stdlib and its
    # signed ELF/data closure; no package-management or container-engine binaries.
    payload_path = work / 'plt01-image-inputs/payload-001/receipt.json'
    payload_ref = ref(payload_path, '24b9de32cc79a9836bc6dc82cb9d84b00a7b2bea4b23b9c7f725246170b30ce4')
    payload = a.document(payload_path)
    if payload['failures'] or payload['package_code_executed']: raise ValueError('inert Python payload failed')
    system = {}; package_projections = []
    for package in payload['packages']:
        selected = []
        for item in package['files']:
            name = item['path']; kind = item['kind']
            keep = (name.startswith(('usr/lib64/', 'usr/lib/python3.12/', 'usr/share/licenses/'))
                    or name in ('usr/bin/python3.12', 'usr/bin/bash', 'usr/bin/sh'))
            if not keep or kind == 'directory': continue
            origin = package['archive_sha256'] + ':' + name
            if kind == 'file':
                row = file_row(Path(package['directory']) / name, origin,
                               int(item['signed_mode'], 8) & 0o7777, item['sha256'])
            elif kind == 'symlink': row = {'kind': kind, 'target': item['target'], 'origin': origin}
            else: raise ValueError('unsupported signed package member')
            if name.endswith('/site-packages/zzzz-import-failed-hooks.pth'):
                # Distro host import reporting is not part of the product. Keep
                # its exact source bytes in notices, outside Python startup.
                name = 'opt/ambisgis/notices/python-host-startup/' + Path(name).name
            put(system, name, row); selected.append(name)
        if selected: package_projections.append({'identity': package['identity'], 'archive_sha256': package['archive_sha256'], 'members': selected})
    inert_path = work / 'plt01-runtime/inert-002/runtime-payload.json'
    inert = a.document(inert_path)
    equal_overlaps = []
    for item in inert['files']:
        name = item['path']
        if name.startswith('runtime/lib64/'):
            destination = 'usr/lib64/' + name.split('runtime/lib64/', 1)[1]
            if destination in system:
                resolved, visited = destination, set()
                while system[resolved]['kind'] == 'symlink':
                    if resolved in visited: raise ValueError('cyclic selected package link')
                    visited.add(resolved); resolved = a.link_target(resolved, system[resolved]['target'])
                if system[resolved]['file']['sha256'] != item['sha256']:
                    raise ValueError('Python/runtime common library bytes differ')
                ref(work / 'plt01-runtime/inert-002' / name, item['sha256'])
                equal_overlaps.append({'path': destination, 'resolved': resolved, 'sha256': item['sha256'],
                                       'selection': 'preserve original signed Python-closure mode/link'})
                continue
            put(system, destination,
                file_row(work / 'plt01-runtime/inert-002' / name, item['archive_sha256'] + ':' + item['package_member'],
                         0o755 if 'ld-linux' in name else 0o644, item['sha256']))
        elif '/notices/' in name:
            put(system, 'opt/ambisgis/notices/runtime/' + name.split('/notices/', 1)[1],
                file_row(work / 'plt01-runtime/inert-002' / name, 'retained runtime notices', 0o644, item['sha256']))
    for name, target in [('bin', 'usr/bin'), ('lib64', 'usr/lib64'),
                         ('opt/ambisgis/python/bin/python3', '/usr/bin/python3.12')]:
        put(system, name, {'kind': 'symlink', 'target': target, 'origin': 'explicit image layout'})
    for name, text in {'etc/nsswitch.conf': 'passwd: files\ngroup: files\nhosts: files dns\n',
                       'etc/passwd': 'root:x:0:0:root:/tmp:/bin/sh\nnobody:x:65534:65534:nobody:/tmp:/bin/sh\n',
                       'etc/group': 'root:x:0:\nnobody:x:65534:\n'}.items():
        path = generated / name.replace('/', '-'); path.write_text(text)
        put(system, name, file_row(path, 'owned fixed image account/resolver skeleton; keep-id user supplied at runtime', 0o644))
    projection_ref = save(output / 'rpm-projection.json', {'packages': package_projections,
        'equal_runtime_overlaps': equal_overlaps,
        'python_payload': payload_ref, 'runtime_payload': ref(inert_path),
        'source_custody': [ref(work / 'plt01-image-inputs/sources-001.json'),
                           ref(work / 'plt01-container-inputs/source-acquisition-002.json'),
                           ref(args.python_lock, 'fc7449babfee72a361da2ad309c463a4ec33ef89a28fbfdc2fa63e5d882bfefd')],
        'scripts_executed': False, 'mode_projection': 'signed ordinary bits; no capabilities, setuid or package scripts'})
    common = [mapped('system-python', system, [payload_ref, ref(inert_path), projection_ref])]
    locale_rows, locale_provenance = locale_projection.select(
        work, custody, args.locale_payload, system, generated / 'locale-notices')
    common.append(mapped('glibc-c-utf8', locale_rows, locale_provenance))

    modules = {}
    for source, destination in [('services/development/ambisgis_development', 'ambisgis_development'),
                                ('services/control-plane/ambisgis_policy', 'ambisgis_policy'),
                                ('services/control-plane/ambisgis_render', 'ambisgis_render')]:
        names = subprocess.check_output(['git', 'ls-files', source], cwd=a.ROOT, text=True).splitlines()
        if not names: raise ValueError('owned module tree is missing')
        for name in names:
            path = a.ROOT / name
            if not path.is_file(): raise ValueError('tracked service source missing')
            expected = subprocess.check_output(['git', 'show', revision + ':' + name], cwd=a.ROOT)
            if path.read_bytes() != expected: raise ValueError('platform service source is not committed')
            put(modules, 'opt/ambisgis/modules/' + destination + '/' + str(path.relative_to(a.ROOT / source)),
                file_row(path, 'owned platform ' + revision + ':' + name, 0o644))
    for name, module in [('service', 'entrypoint'), ('health', 'health')]:
        path = generated / name
        path.write_text('#!/bin/sh\nexec /opt/ambisgis/python/bin/python3 -s -P -m ambisgis_development.' + module + ' "$@"\n')
        put(modules, 'opt/ambisgis/bin/' + name, file_row(path, 'owned fixed launcher', 0o755))
    platform_proof = save(output / 'platform-source.json', {'commit': revision, 'members': modules,
         'generator': ref(Path(__file__)), 'license_policy': ref(a.ROOT / 'plan/docs/08-repositories-and-licensing.md')})
    common.append(mapped('platform-services', modules, [platform_proof], revision))
    platform_notice = generated / 'PLATFORM-NOTICE.txt'
    platform_notice.write_text('AmbisGIS owned development modules\nSource revision: ' + revision +
        '\nFirst-party modules retain the existing GPL-3.0-or-later declaration.\n'
        'The accompanying GPL-3.0 text and exact module sources are carried with this image.\n'
        'Third-party components keep their separate notices and source provenance.\n'
        'This development artifact is not an approved product distribution.\n')
    common.append(mapped('platform-notices', {
        'opt/ambisgis/notices/platform/NOTICE.txt': file_row(platform_notice, 'existing owned-module license declaration', 0o644),
        'opt/ambisgis/notices/platform/GPL-3.0.txt': file_row(args.gpl3_notice, 'retained complete GPL version 3 text', 0o644,
            '2ca9503d76d1ffab14f599b4741382eec11face60ad1f0d7a41897809003a286')}, [platform_proof], revision))

    # Native PG/PostGIS producer inventory covers all installed bytes/links.
    native = work / 'fnd08-native/final-pair-002/build-1'
    native_result = a.document(native / 'result.json')
    if native_result['result_exit_code'] or native_result['owned_sources']['postgresql']['commit'] != PG or native_result['owned_sources']['postgis']['commit'] != GIS:
        raise ValueError('owned database source selection differs')
    native_manifest = ref(native / 'output-manifest.json', '27a5d9bce8171ccad052750a1c5f4d08a533d5f6df7a4aa804f02e50efe68e86')
    verify_original_tree(native / 'prefix', Path(native_manifest['path']))
    groups['database'] = [add_tree('postgres-postgis', native / 'prefix', 'opt/ambisgis/postgres',
                         [ref(native / 'result.json'), native_manifest, ref(native / 'source-inputs.json')],
                         {'postgresql': PG, 'postgis': GIS})]
    native_sources = a.document(native / 'source-inputs.json')
    native_notices = {}
    for component, names in [('postgresql', ['COPYRIGHT']), ('postgis', ['COPYING', 'LICENSE.TXT'])]:
        for name in names:
            put(native_notices, 'opt/ambisgis/notices/' + component + '/' + name,
                file_row(native / 'sources' / component / name, 'exact owned source notice', 0o644,
                         native_sources[component][name]))
    groups['database'].append(mapped('database-notices', native_notices, [ref(native / 'source-inputs.json')]))
    support = work / 'postgis-slice/run-003/prefix'
    support_inventory = ref(native / 'support-inputs.json', native_result['support_inputs_sha256'])
    verify_original_tree(support, Path(support_inventory['path']))
    derived_proj = generated / 'libproj.so.25.9.6.2'
    relocation = relocate_proj.repair(support / 'lib/libproj.so.25.9.6.2', derived_proj)
    relocation_ref = save(output / 'proj-relocation.json', relocation)
    support_rows = {}
    for name, row in a.document(Path(support_inventory['path'])).items():
        destination = 'opt/ambisgis/support/' + name
        if 'symlink' in row:
            put(support_rows, destination, {'kind': 'symlink', 'target': row['symlink'], 'origin': 'retained spatial support ' + name})
        else:
            source = derived_proj if name == 'lib/libproj.so.25.9.6.2' else support / name
            expected = relocation['derived_sha256'] if source == derived_proj else row['sha256']
            permissions = 0o755 if (support / name).stat().st_mode & 0o111 else 0o644
            put(support_rows, destination, file_row(source, 'retained support ' + name +
                ('; explicit DT_NEEDED relocation, original=' + relocation['original_sha256'] if source == derived_proj else ''),
                permissions, expected))
    ref(support / 'lib/libproj.so.25.9.6.2', relocate_proj.ORIGINAL_SHA256)
    support_id = mapped('spatial-support', support_rows, [support_inventory, ref(native / 'result.json'), relocation_ref])
    support_source_manifest = ref(a.ROOT / 'build-support/postgis/inputs.json', native_result['support_manifest_sha256'])
    support_notices = {}
    for item in a.document(Path(support_source_manifest['path']))['inputs']:
        ref(custody / 'postgis-slice' / item['artifact'], item['sha256'])
        for notice in item['license_evidence']:
            put(support_notices, 'opt/ambisgis/notices/spatial/' + notice['retained_path'],
                file_row(custody / 'postgis-slice' / notice['retained_path'],
                         item['sha256'] + ':' + notice['original_path'], 0o644, notice['sha256']))
    support_notice_id = mapped('spatial-notices', support_notices, [support_source_manifest])
    groups['database'] += [support_id, support_notice_id]

    catalog = work / 'fnd08-client-successor/catalog-pair-001/build-2'
    catalog_proof = ref(catalog / 'result.json', '5982168ff7bf2715a674c1e44ccf7646f2e9aa495b8e8a7176bf75d3f077a293')
    result = a.document(catalog / 'result.json')
    if result['source_selection']['geonode']['commit'] != GEO or result['source_selection']['mapstore-client']['commit'] != CLIENT:
        raise ValueError('owned catalog source selection differs')
    catalog_manifest = ref(catalog / 'output-manifest.json', result['output_manifest_sha256'])
    verify_original_tree(catalog / 'artifacts', Path(catalog_manifest['path']))
    group = []
    for path in sorted((catalog / 'artifacts').glob('*.whl')):
        identifier, source = ('geonode', GEO) if path.name.startswith('geonode-') else ('mapstore-client', CLIENT)
        group.append(add_wheel(identifier, path, a.digest(path), [catalog_proof, catalog_manifest, ref(catalog / 'source-inputs.json')], source))
    dep_root = custody / 'geonode-identity-v2'
    dep_manifest = ref(dep_root / 'manifest.json', result['dependency_manifest_sha256'])
    retained = a.document(dep_root / 'manifest.json')
    for row in retained['files']:
        a.relative(row['path']); ref(dep_root / row['path'], row['sha256'])
    dependencies = a.document(dep_root / 'python-components.json')
    for item in dependencies['components']:
        if item['name'].lower().replace('_', '-') in ('geonode', 'django-geonode-mapstore-client'): continue
        identifier = 'python-' + re.sub('[^a-z0-9-]', '-', item['name'].lower())
        group.append(add_wheel(identifier, dep_root / 'wheels' / item['wheel'], item['sha256'],
                               [dep_manifest, ref(dep_root / 'python-components.json')]))
    group.append(add_tree('python-notices', dep_root / 'notices', 'opt/ambisgis/notices/python', [dep_manifest]))
    waitress = custody / 'plt01-waitress'
    waitress_id = add_wheel('waitress', waitress / 'waitress-3.0.2-py3-none-any.whl',
                           'c56d67fd6e87c2ee598b76abdd4e96cfad1f24cacdea5078d382b1f9d7b5ed2e',
                           [ref(waitress / 'archive-inputs.json'), ref(waitress / 'waitress-3.0.2.tar.gz',
                            '682aaaf2af0c44ada4abfb70ded36393f0e307f4ab9456a215ce0020baefc31f')])
    notices = {}
    with tarfile.open(waitress / 'waitress-3.0.2.tar.gz') as archive:
        for name in ('LICENSE.txt', 'COPYRIGHT.txt'):
            data = archive.extractfile('waitress-3.0.2/' + name).read(); path = generated / ('waitress-' + name); path.write_bytes(data)
            put(notices, 'opt/ambisgis/notices/waitress/' + name, file_row(path, 'exact waitress source member ' + name, 0o644))
    common += [waitress_id, mapped('waitress-notices', notices, [ref(waitress / 'archive-inputs.json')])]
    groups['catalog'] = group + [support_id, support_notice_id]
    groups['gateway'] = []

    # Retain exact final WAR, projected tested profile and new compiled filters.
    final = work / 'fnd08-postmerge-final/run-001'
    java = work / 'fnd08-java/run-005'
    java_proof = ref(java / 'result.json', 'a243c8123af156c5030579ceb8471f2a51a3394ddca9ce4f8377b245f4da58e4')
    java_revisions = {'geoserver': GS, 'geotools': GT, 'geowebcache': GWC}
    if {name: row['commit'] for name, row in a.document(java / 'result.json')['source_successor'].items()} != java_revisions:
        raise ValueError('owned Java source selection differs')
    war = java / 'work/source/geoserver/src/web/app/target/geoserver.war'
    java_rows = {'opt/ambisgis/geoserver/application.war': file_row(war, 'owned GeoServer ' + GS, 0o644, WAR),
                 'opt/ambisgis/geoserver/runtime-profile.json': file_row(final / 'runtime-profile.json', 'accepted final profile projection', 0o644,
                  '960d30000604a44483fd9638d4b205b0b6e09019d104ce5c504a396a272838a7')}
    profile = a.document(final / 'runtime-profile.json')
    with zipfile.ZipFile(war) as archive:
        for key in ('renderer', 'imageio', 'json'):
            member = profile[key + '_member']; data = archive.read(member)
            if hashlib.sha256(data).hexdigest() != profile[key + '_sha256']: raise ValueError('Java profile member differs')
            path = generated / Path(member).name; path.write_bytes(data)
            put(java_rows, 'opt/ambisgis/geoserver/lib/' + path.name, file_row(path, WAR + ':' + member, 0o644))
    servlet = final / 'maps-001/servlet'
    servlet_manifest = ref(a.ROOT / 'build-support/java/runtime-inputs.json', '5f78d1404b249b2d468703e3e8a7f2de43fe71c1fb0e39db8e3a55de29faf118')
    if a.document(servlet / 'staged.json')['manifest_sha256'] != servlet_manifest['sha256']:
        raise ValueError('servlet staging source manifest differs')
    expected_jars = {Path(row['binary']['maven_path']).name: row['binary']['sha256']
                     for row in a.document(Path(servlet_manifest['path']))['artifacts']}
    if {row['name']: row['sha256'] for row in a.document(servlet / 'staged.json')['libraries']} != expected_jars:
        raise ValueError('servlet staging members differ from pinned manifest')
    for item in a.document(servlet / 'staged.json')['libraries']:
        put(java_rows, 'opt/ambisgis/geoserver/servlet/' + item['name'], file_row(servlet / 'lib' / item['name'],
            'retained servlet closure', 0o644, item['sha256']))
    classes = args.java_classes
    compile_receipt = a.document(classes / 'result.json')
    if compile_receipt['exit_codes'] != [0, 0]: raise ValueError('native launcher compile failed')
    for name, sha in compile_receipt['classes'].items():
        if name.startswith('DevelopmentFilterChecks'): continue
        put(java_rows, 'opt/ambisgis/geoserver/launcher/' + name, file_row(classes / 'classes' / name, 'reviewed owned launcher compile', 0o644, sha))
    for path, sha in compile_receipt['source'].items(): ref(Path(path), sha)
    groups['geoserver'] = [mapped('geoserver', java_rows, [java_proof, ref(final / 'postmerge-smoke.json'),
        servlet_manifest, ref(classes / 'result.json')], java_revisions)]
    jdk = work / 'java-resolution/toolchain/jdk-17.0.20.1+1'
    jdk_archive = custody / 'java-resolution/toolchain/OpenJDK17U-jdk_x64_linux_hotspot_17.0.20.1_1.tar.gz'
    # Compare installed files to the retained publisher archive, never accept a
    # newly inventoried JDK as its own independent source identity.
    archive_receipt = a.document(Path(str(jdk_archive) + '.receipt.json'))
    expected_sha = archive_receipt.get('sha256')
    if not expected_sha: raise ValueError('retained JDK archive receipt lacks identity')
    ref(jdk_archive, expected_sha)
    observed = set()
    with tarfile.open(jdk_archive) as archive:
        for item in archive:
            parts = item.name.rstrip('/').split('/', 1)
            if len(parts) == 1: continue
            name = a.relative(parts[1]); path = jdk / name
            if item.isdir(): continue
            observed.add(name)
            if item.issym():
                if not path.is_symlink() or os.readlink(path) != item.linkname: raise ValueError('JDK link differs')
            elif item.isfile():
                source = hashlib.sha256(archive.extractfile(item).read()).hexdigest()
                ref(path, source)
            else: raise ValueError('unsupported retained JDK member')
    if observed != {str(p.relative_to(jdk)) for p in jdk.rglob('*') if p.is_file() or p.is_symlink()}:
        raise ValueError('JDK installed membership differs')
    groups['geoserver'].append(add_tree('java-runtime', jdk, 'opt/ambisgis/java',
        [ref(jdk_archive), ref(Path(str(jdk_archive) + '.receipt.json')), ref(custody / 'java-resolution/toolchain/license-inventory.json')]))
    selection = {'schema_version': 1, 'platform_revision': revision, 'epoch': 1790899200,
                 'components': components, 'images': {role: common + groups[role] for role in a.ROLES}}
    save(output / 'selection.json', selection)
    print(json.dumps({'selection': str(output / 'selection.json'), 'sha256': a.digest(output / 'selection.json'),
                      'components': len(components), 'runtime_executed': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--custody', type=Path, required=True)
    parser.add_argument('--java-classes', type=Path, required=True)
    parser.add_argument('--python-lock', type=Path, required=True)
    parser.add_argument('--locale-payload', type=Path, required=True)
    parser.add_argument('--gpl3-notice', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
