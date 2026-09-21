"""Guarded source selection for the explicitly limited NO-ORACLE candidate."""
import json
from pathlib import Path
from resolution import sha


def excluded_input(maven_path):
    return maven_path.startswith(('com/oracle/', 'com/oracle/database/'))


def prepare(source):
    manifest = Path(__file__).with_name('no-oracle-repairs.json')
    rows = json.loads(manifest.read_text())
    for row in rows:
        path = Path(source) / row['path']
        if path.is_symlink() or sha(path) != row['before_sha256'] or path.read_text().count(row['before']) != 1:
            raise ValueError('NO-ORACLE requires exact inspected source: ' + row['path'])
    for row in rows:
        path = Path(source) / row['path']
        path.write_text(path.read_text().replace(row['before'], row['after']))
        if sha(path) != row['after_sha256']:
            raise ValueError('NO-ORACLE source repair output mismatch')
    return {'profile': 'NO-ORACLE', 'manifest_sha256': sha(manifest),
            'repairs': [{key: row[key] for key in ('path', 'before_sha256', 'after_sha256', 'reason')} for row in rows],
            'unsupported': ['Oracle-backed data stores/imports', 'Oracle-backed mosaic indexes'],
            'retained': ['PostGIS', 'non-Oracle mosaics', 'vector/raster services', 'printing', 'authorization'],
            'long_term_oracle_requirement': 'Unimplemented in this profile; future separately tested source-owned capability.',
            'dormant_oracle_declarations': 'Original source and optional unselected profiles remain; historical source gaps are not closed.',
            'mosaic_source': 'Shared classes under catalog/oracle are retained because PostGIS and SQLServer depend on them; no Oracle driver imports are used by active mosaic main sources.'}


def inspect_artifacts(build, jar_entries, class_origins, libraries):
    """Inspect identities and functionality, never a broad word/notice deletion."""
    import hashlib
    import io
    import zipfile
    baseline = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/geonode-role-propagation/aggregate-repaired-02/work/source/geoserver/src/web/app/target/geoserver.war')
    if sha(baseline) != 'a3cea4ad28ca7c3447b2eeae7a631e624a9e50e7973972c43f2d7d91eab25a52':
        raise ValueError('original Oracle-containing baseline changed')
    forbidden_hashes = set()
    originals = []
    with zipfile.ZipFile(baseline) as war:
        for name in ('WEB-INF/lib/ojdbc17-23.26.2.0.0.jar', 'WEB-INF/lib/gt-jdbc-oracle-34.5.jar'):
            data = war.read(name)
            with zipfile.ZipFile(io.BytesIO(data)) as jar:
                members = [n for n in jar.namelist() if n.endswith(('.class', '.so', '.dll', '.dylib'))]
                forbidden_hashes.update(hashlib.sha256(jar.read(n)).hexdigest() for n in members)
                originals.append({'member': name, 'sha256': hashlib.sha256(data).hexdigest(), 'class_native_members': len(members)})
    for library in libraries:
        if library['name'].startswith(('ojdbc', 'gt-jdbc-oracle', 'gs-oracle')):
            raise ValueError('excluded Oracle library reintroduced')
    for jar, entries in jar_entries.items():
        for entry in entries:
            name = entry['path']
            if (name.startswith(('oracle/', 'org/geotools/data/oracle/')) or 'libtfojdbc' in name
                    or entry['sha256'] in forbidden_hashes or name.endswith('/OraclePanel.class')):
                raise ValueError('excluded Oracle class/native identity remains: ' + jar + '/' + name)
    # The dependency mirror and resolved local repository both exclude driver groups.
    for folder in ('retained-repository', 'fresh-m2'):
        forbidden = [str(p.relative_to(Path(build)/folder)) for p in (Path(build)/folder).rglob('*.jar')
                     if excluded_input(str(p.relative_to(Path(build)/folder)))]
        if forbidden: raise ValueError('active proprietary driver build input remains')
    required = ('org/geotools/gce/imagemosaic/ImageMosaicReader.class',
                'org/geotools/gce/imagemosaic/catalog/postgis/PostgisDatastoreWrapper.class',
                'org/geotools/data/postgis/PostgisNGDataStoreFactory.class',
                'org/geoserver/importer/web/ImportDataPage$Source.class')
    if not all(name in class_origins for name in required):
        raise ValueError('retained mosaic/PostGIS/importer definition missing')
    return {'profile': 'NO-ORACLE', 'originals': originals,
            'original_class_native_fingerprints_checked': len(forbidden_hashes),
            'excluded_class_driver_native_matches': [], 'active_driver_inputs': [],
            'retained_required_definitions': list(required), 'notices_unchanged_by_word_filter': True,
            'limitations': 'Exact class/provider/native identities and original-byte fingerprints; arbitrary rewritten unknown code cannot be excluded by byte scanning alone. Runtime datasource/mosaic tests remain separate.'}
