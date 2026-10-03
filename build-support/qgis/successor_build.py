#!/usr/bin/env python3
"""FND-08 exact QGIS source successor adapter for the preserved build recipe.

The historical producer is loaded without changing its source. Only its source
commit and per-attempt source authority directory change. Native/spatial/XML/
support verification continues through the unchanged original common module.
This never accepts an old binary as a new build.
"""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1]
COMMIT = '86af40542b219b0da6df1a43914413443330c0c0'
TREE = '84ea1b18fdf5721819fee34fe06cdef7ea82afdc'
PRODUCER_SHA = '0a4dc0d027b09ff04d47b4c2f561ced3e1e7e39f43ee234404727cb774a5d70a'
RECEIPT_SHA = 'f9828bf21e349a596c3ed16c58287c4f26dce1a271aab5f4cf15ab336f20d4eb'
ARCHIVE_ROOT = 'qgis-successor'
sys.path.insert(0, str(PLATFORM / 'build-support/source_publication'))
import qgis_snapshot as publication
from common import require, sha, save, inventory


def identity(commit, tree):
    require(commit == COMMIT and tree == TREE, 'unapproved QGIS successor identity')


def checked_relative(path):
    value = PurePosixPath(path)
    require(path and not value.is_absolute() and '..' not in value.parts and '\\' not in path,
            'unsafe source path')
    return value


def verify_archive(archive, expected):
    actual = {}
    with tarfile.open(archive) as source:
        for member in source:
            path = checked_relative(member.name)
            require(path.parts[0] == ARCHIVE_ROOT, 'wrong source archive root')
            if member.isdir():
                continue
            relative = '/'.join(path.parts[1:])
            require(relative and relative not in actual, 'duplicate source archive path')
            if member.issym():
                mode, data = '120000', member.linkname.encode()
            else:
                require(member.isfile(), 'unsupported source archive object')
                mode = '100755' if member.mode & 0o111 else '100644'
                with source.extractfile(member) as content:
                    data = content.read()
            actual[relative] = {'mode':mode, 'oid':publication.blob_id(data)}
    require(actual == expected, 'complete source archive differs from approved tree')
    return {'source_entries':len(actual), 'bytes':archive.stat().st_size, 'sha256':sha(archive)}


def create_archive(repo, expected, archive):
    require(not archive.exists() and not archive.is_symlink(), 'fresh source archive required')
    reader = publication.Blobs(repo)
    try:
        with tarfile.open(archive, 'x', format=tarfile.PAX_FORMAT) as target:
            root = tarfile.TarInfo(ARCHIVE_ROOT)
            root.type = tarfile.DIRTYPE; root.mode = 0o755
            target.addfile(root)
            for path, row in sorted(expected.items()):
                checked_relative(path)
                data = reader.read(row['oid'])
                require(publication.blob_id(data) == row['oid'], 'source blob mismatch')
                entry = tarfile.TarInfo(ARCHIVE_ROOT + '/' + path)
                if row['mode'] == '120000':
                    entry.type = tarfile.SYMTYPE; entry.mode = 0o777; entry.linkname = data.decode()
                    target.addfile(entry)
                else:
                    require(row['mode'] in ('100644','100755'), 'unsupported source mode/gitlink')
                    entry.mode = int(row['mode'][-3:],8); entry.size = len(data)
                    target.addfile(entry, io.BytesIO(data))
    finally:
        reader.close()
    return verify_archive(archive, expected)


def configure_command(command, spatial):
    """Pin the same SQLite already required by the historical origin guard."""
    command = list(command)
    if command[0] == 'cmake' and '-S' in command:
        key = '-Dpkgcfg_lib_PC_SPATIALITE_sqlite3='
        require(not any(str(value).startswith(key) for value in command), 'duplicate SQLite discovery override')
        command.append(key + str(spatial / 'lib/libsqlite3.so'))
    return command


def load_producer(authority, spatial):
    require(sha(HERE / 'build.py') == PRODUCER_SHA, 'historical QGIS producer changed')
    spec = importlib.util.spec_from_file_location('qgis_successor_producer', HERE / 'build.py')
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    require(producer.COMMIT == publication.BASE and producer.HERE == HERE,
            'historical producer source binding changed')
    producer.COMMIT = COMMIT
    producer.HERE = authority
    original_run = producer.run
    def run_with_selected_sqlite(command, *args, **kwargs):
        return original_run(configure_command(command, spatial), *args, **kwargs)
    producer.run = run_with_selected_sqlite
    return producer


def run(args):
    output = args.output.resolve()
    require(not output.exists() and not output.is_symlink(), 'fresh successor attempt required')
    require(1 <= args.jobs <= 6, 'parallelism must be 1..6')
    identity(COMMIT, TREE)
    trusted = publication.trusted_receipt(args.publication_receipt.resolve(), RECEIPT_SHA)
    expected = json.loads(Path(trusted['expected_tree']['path']).read_text())
    forbidden = json.loads(Path(trusted['forbidden_objects']['path']).read_text())
    provenance = json.loads(Path(trusted['provenance']['path']).read_text())
    repo = args.source_repository.resolve()
    verified = publication.verify_repository(repo, COMMIT, TREE, expected, forbidden)
    require(len(provenance['omitted_files']) == 1130, 'wrong source exclusion count')
    require(len([path for path in expected if path.startswith('resources/cpt-city-qgis-min/cb/') and path.endswith('.svg')]) == 265,
            'ColorBrewer palette count changed')
    output.mkdir(parents=True)
    report = {'task':'FND-08', 'state':'started', 'commit':COMMIT, 'tree':TREE,
              'source_repository':str(repo), 'source_verification':verified,
              'historical_producer_sha256':PRODUCER_SHA, 'publication_receipt_sha256':RECEIPT_SHA,
              'adapter_sha256':sha(Path(__file__)), 'jobs':args.jobs,
              'acceptance':'new compile only; runtime, native, repeated-build and drift checks are separate'}
    save(output/'started.json',report)
    try:
        authority = output/'authority'; authority.mkdir()
        for name in ('build.py','common.py','profile-inputs.json','support-inputs.json'):
            shutil.copyfile(HERE/name, authority/name)
        shutil.copyfile(Path(__file__),authority/'successor_build.py')
        archive = output/'qgis-successor.tar'
        archive_record = create_archive(repo, expected, archive)
        source = json.loads((HERE/'source-inputs.json').read_text())
        source.update(commit=COMMIT,tree=TREE,tag=None,tag_object=None,
            scope='FND-08 exact source successor; support profile unchanged; not a release lock',
            archive={'path':str(archive),'root':ARCHIVE_ROOT,**archive_record})
        notices = []
        reader = publication.Blobs(repo)
        try:
            for old in source['source_notices']:
                data = reader.read(expected[old['path']]['oid'])
                notices.append({'path':old['path'],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            for name in (publication.NOTICE, publication.PROVENANCE):
                data = reader.read(expected[name]['oid'])
                notices.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        finally: reader.close()
        source['source_notices'] = notices
        save(authority/'source-inputs.json',source)
        save(output/'authority.json',{'overrides':{'producer.COMMIT':COMMIT,'producer.HERE':str(authority)},
             'configure_extra_flags':{'pkgcfg_lib_PC_SPATIALITE_sqlite3':str(args.spatial.resolve()/'lib/libsqlite3.so')},
             'unchanged_dependency_authority':str(HERE),'files':inventory(authority),
             'archive':archive_record,'new_binary_required':True})
        producer = load_producer(authority,args.spatial.resolve())
        producer.build(output/'compile',args.native.resolve(),args.spatial.resolve(),args.support.resolve(),
                       args.support_inventory.resolve(),args.jobs,args.xml.resolve())
        require(sha(HERE/'build.py') == PRODUCER_SHA, 'historical producer changed during build')
        verify_archive(archive,expected)
        report.update(state='compiled-staged',result_exit_code=0,
            output_manifest_sha256=sha(output/'compile/output-manifest.json'),
            producer_success_sha256=sha(output/'compile/success.json'))
    except Exception as error:
        report.update(state='failed',result_exit_code=1,error={'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        save(output/'result.json',report)
    return 0


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source-repository','publication-receipt','output','native','spatial','support','support-inventory','xml'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=4)
    raise SystemExit(run(parser.parse_args()))
