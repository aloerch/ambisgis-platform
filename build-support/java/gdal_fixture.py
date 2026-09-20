"""Expose only verified retained GDAL tools to the importer probe."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from resolution import sha


def prepare(prefix, archive, output):
    metadata = Path(__file__).resolve().parents[2] / 'plan/verification/postgis-slice.json'
    expected = json.loads(metadata.read_text())['output_archive']
    if sha(archive) != expected['sha256']:
        raise ValueError('native output archive does not match retained database evidence')
    verified = []
    with tarfile.open(archive) as tf:
        for member in tf:
            relative = PurePosixPath(member.name)
            if not relative.parts or relative.parts[0] != 'prefix' or '..' in relative.parts:
                raise ValueError('unsafe native output archive path')
            path = prefix.joinpath(*relative.parts[1:])
            if member.isfile() or member.islnk():
                if member.islnk():
                    link = PurePosixPath(member.linkname)
                    if not link.parts or link.parts[0] != "prefix" or ".." in link.parts:
                        raise ValueError("unsafe native hardlink target")
                with tf.extractfile(member) as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if path.is_symlink() or sha(path) != digest:
                    raise ValueError('installed native artifact differs: ' + str(path))
                verified.append({'path': str(path), 'sha256': digest})
            elif member.issym():
                if not path.is_symlink() or str(path.readlink()) != member.linkname:
                    raise ValueError('installed native link differs: ' + str(path))
            elif not member.isdir():
                raise ValueError('unexpected native archive entry')
    binaries = output / 'native-bin'
    binaries.mkdir()
    staged = []
    for name in ('gdal_translate', 'gdaladdo', 'gdalwarp'):
        source = prefix / 'bin' / name
        if not any(row['path'] == str(source) for row in verified):
            raise ValueError('required GDAL binary absent from frozen archive')
        destination = binaries / name
        shutil.copy2(source, destination)
        if sha(source) != sha(destination):
            raise ValueError('staged GDAL binary changed')
        staged.append({'path': str(destination), 'sha256': sha(destination)})
    return {'archive': str(archive), 'archive_sha256': expected['sha256'],
            'verified_files': verified, 'staged_binaries': staged,
            'environment': {'LD_LIBRARY_PATH': str(prefix / 'lib') + ':' + str(prefix / 'lib64'),
                            'GDAL_DATA': str(prefix / 'share/gdal'),
                            'PROJ_DATA': str(prefix / 'share/proj'), 'PROJ_NETWORK': 'OFF'}}
