#!/usr/bin/env python3
"""Build the experimental FND-02 native stack from verified retained archives.

No downloads, system installations, or implicit resume. Each selected component
is configured and built in the supplied run directory. Select components to
resume a recorded run; choose a new directory for a clean rebuild.
"""
import argparse
import datetime as dt
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
ORDER = ['zlib', 'sqlite', 'libxml2', 'cunit', 'googletest', 'json-c',
         'jpeg', 'libpng', 'tiff', 'geos', 'curl', 'proj', 'protobuf',
         'protobuf-c', 'gdal', 'postgresql', 'postgis-upgrade', 'postgis']


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def extract_verified(artifact, expected, destination):
    if digest(artifact) != expected:
        raise ValueError(f'integrity mismatch: {artifact}')
    if destination.exists():
        raise ValueError(f'refusing to reuse extracted source directory: {destination}')
    destination.mkdir(parents=True)
    with tarfile.open(artifact) as archive:
        archive.extractall(destination, filter='data')
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError(f'expected one archive source root: {artifact}')
    return roots[0]


def build_environment(prefix, run):
    # Deliberately omit user package/config/credential/environment injections.
    # Host compiler, libc, loader and build utilities remain explicit gaps.
    env = {
        'PATH': f'{prefix}/bin:/usr/bin:/bin',
        'HOME': str(run / 'home'), 'TMPDIR': str(run / 'tmp'),
        'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
        'CC': '/usr/bin/gcc', 'CXX': '/usr/bin/g++',
        'CFLAGS': '-O2 -std=gnu17', 'CXXFLAGS': '-O2 -std=c++17',
        'CPPFLAGS': f'-I{prefix}/include',
        'LDFLAGS': f'-L{prefix}/lib -Wl,-rpath,{prefix}/lib',
        'LD_LIBRARY_PATH': str(prefix / 'lib'),
        'PKG_CONFIG_LIBDIR': f'{prefix}/lib/pkgconfig:{prefix}/share/pkgconfig',
        'CMAKE_PREFIX_PATH': str(prefix),
        'PROJ_DATA': str(prefix / 'share/proj'),
        'PROJ_LIB': str(prefix / 'share/proj'), 'PROJ_NETWORK': 'OFF',
    }
    for name in ('home', 'tmp'):
        (run / name).mkdir(exist_ok=True)
    return env


def assert_cunit_internal_results(output):
    # test_cunit returns zero even when an internal assertion fails.
    summary = output.rsplit('CUnit Internal Test Results', 1)
    if len(summary) != 2:
        raise RuntimeError('CUnit self-test summary missing')
    count = re.search(r'Total Number of Assertions:\s*(\d+)', summary[1])
    failures = re.search(r'Failures:\s*(\d+)', summary[1])
    if not count or int(count[1]) == 0 or not failures or int(failures[1]) != 0:
        raise RuntimeError('CUnit internal assertion failure or empty test run')


def require_generated_files(paths):
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f'generator omitted required output: {path}')


def require_gdal_raster_drivers(output):
    observed = set(re.findall(r'^\s{2}(.+?)\s+-', output, re.M))
    required = {'VRT', 'GTiff', 'AAIGrid', 'DTED', 'PNG', 'JPEG', 'MEM', 'EHdr'}
    if missing := required - observed:
        raise RuntimeError(f'GDAL omitted required raster drivers: {sorted(missing)}')


class Builder:
    def __init__(self, manifest, custody, run, jobs):
        self.manifest = manifest
        self.inputs = {x['name']: x for x in manifest['inputs']}
        self.custody, self.root, self.jobs = custody, run, jobs
        self.prefix = run / 'prefix'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = (self.root/'build.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close()
            raise
        self.prefix.mkdir(exist_ok=True)
        self.logs = run / 'logs'
        self.logs.mkdir(exist_ok=True)
        recipe_bytes = Path(__file__).read_bytes()
        self.recipe_sha256 = hashlib.sha256(recipe_bytes).hexdigest()
        snapshot = self.logs / f'recipe-{self.recipe_sha256}.py'
        if not snapshot.exists():
            snapshot.write_bytes(recipe_bytes)
        self.env = build_environment(self.prefix, self.root)
        self.receipts = self.logs / 'commands.jsonl'
        self.sequence = max(
            [len(self.receipts.read_text().splitlines()) if self.receipts.exists() else 0]
            + [int(p.stem.split('-')[1]) for p in self.logs.glob('command-*.json')])
        self.component = 'preflight'

    def close(self):
        self.lock.close()

    def command(self, args, cwd, *, env=None, allow_failure=False):
        self.sequence += 1
        args = list(map(str, args))
        log = self.logs / f'{self.sequence:04d}-{self.component}-{Path(args[0]).name}.log'
        record = dict(command=args, cwd=str(cwd), environment=env or self.env,
                      recipe_sha256=self.recipe_sha256,
                      input_identity=self.inputs.get(self.component),
                      started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      component=self.component, log=str(log))
        start = time.monotonic()
        command_record = self.logs / f'command-{self.sequence:04d}.json'
        command_record.write_text(json.dumps(record, indent=2) + '\n')
        print(f'[{self.component}] {self.sequence}: {" ".join(args)}', flush=True)
        try:
            with log.open('w') as output:
                process = subprocess.run(args, cwd=cwd, env=env or self.env,
                                         stdout=output, stderr=subprocess.STDOUT)
            record['exit_status'] = process.returncode
            if process.returncode and not allow_failure:
                print(log.read_text(errors='replace')[-7000:], file=sys.stderr)
                raise RuntimeError(f'command failed ({process.returncode}): {log}')
            return process.returncode
        except BaseException as exc:
            record.setdefault('exit_status', None)
            record['error'] = str(exc)
            raise
        finally:
            self.last_log = log
            record.update(seconds=round(time.monotonic()-start, 3),
                          log_sha256=digest(log) if log.exists() else None)
            command_record.write_text(json.dumps(record, indent=2) + '\n')
            with self.receipts.open('a') as stream:
                stream.write(json.dumps(record, sort_keys=True) + '\n')

    def source(self, name):
        item = self.inputs[name]
        artifact = self.custody / item['artifact']
        directory = self.root / 'sources' / name
        marker = directory / '.input-sha256'
        if directory.exists():
            if not marker.exists() or marker.read_text().strip() != item['sha256']:
                raise ValueError(f'existing extraction has a different or missing identity: {directory}')
            if digest(artifact) != item['sha256']:
                raise ValueError(f'retained archive changed: {artifact}')
            roots = [p for p in directory.iterdir() if p.name != marker.name]
            if len(roots) != 1:
                raise ValueError(f'unexpected source entries: {directory}')
            return roots[0]
        source = extract_verified(artifact, item['sha256'], directory)
        marker.write_text(item['sha256'] + '\n')
        return source

    def cmake(self, source, build, options=(), tests=True):
        self.command(['cmake', '-S', source, '-B', build, '-G', 'Ninja',
                      '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_INSTALL_PREFIX={self.prefix}',
                      '-DCMAKE_INSTALL_LIBDIR=lib', f'-DCMAKE_INSTALL_RPATH={self.prefix}/lib',
                      '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
                      '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF',
                      '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
                      *options], self.root)
        if self.component == 'protobuf':
            # 21.12 test-common omits order dependencies for these generated
            # headers (cmake/tests.cmake). Generate them with its own compiler
            # before any parallel test compilation, retaining all original tests.
            self.command(['cmake', '--build', build, '--target', 'protoc', '-j', self.jobs], self.root)
            self.command([build/'protoc', f'--proto_path={source}/src',
                          f'--cpp_out={source}/src', '--experimental_allow_proto3_optional',
                          *[source/'src/google/protobuf'/f'{name}.proto' for name in
                            ('map_lite_unittest', 'unittest_import_lite',
                             'unittest_import_public_lite', 'unittest_lite')]], self.root)
            generated = [source/'src/google/protobuf'/f'{name}.pb.{suffix}'
                         for name in ('map_lite_unittest', 'unittest_import_lite',
                                      'unittest_import_public_lite', 'unittest_lite')
                         for suffix in ('h', 'cc')]
            require_generated_files(generated)
            (self.logs/'protobuf-lite-generated.json').write_text(json.dumps(
                {str(path): digest(path) for path in generated}, indent=2)+'\n')
        self.command(['cmake', '--build', build, '-j', self.jobs], self.root)
        if tests:
            self.command(['ctest', '--test-dir', build, '--output-on-failure', '--no-tests=error', '-j', self.jobs], self.root)
        self.command(['cmake', '--install', build], self.root)

    def autotools(self, source, build, options=(), test_target='check', autogen=None):
        build.mkdir(parents=True, exist_ok=True)
        if autogen:
            self.command(autogen, source)
        self.command([source / 'configure', f'--prefix={self.prefix}',
                      f'--libdir={self.prefix}/lib', *options], build)
        self.command(['make', f'-j{self.jobs}'], build)
        if test_target:
            self.command(['make', f'-j{self.jobs}', test_target], build)
        self.command(['make', 'install'], build)

    def build(self, name):
        self.component = name
        source = self.source(name)
        build = self.root / 'build' / name
        p = self.prefix
        if name == 'zlib':
            self.autotools(source, build)
        elif name == 'sqlite':
            self.autotools(source, build, ['--disable-readline'], test_target=None)
            self.command([p / 'bin/sqlite3', ':memory:',
                          'PRAGMA integrity_check; SELECT sqlite_version(); SELECT sqrt(4);'], self.root)
            if self.last_log.read_text().splitlines() != ['ok', self.inputs['sqlite']['version'], '2.0']:
                raise RuntimeError('SQLite integrity/version/math probe failed')
        elif name == 'libxml2':
            self.cmake(source, build, ['-DBUILD_SHARED_LIBS=ON', '-DLIBXML2_WITH_PYTHON=OFF',
                                      '-DLIBXML2_WITH_LZMA=OFF', '-DLIBXML2_WITH_ICONV=OFF',
                                      '-DLIBXML2_WITH_ZLIB=ON', '-DLIBXML2_WITH_TESTS=ON'])
        elif name == 'cunit':
            # The release includes config.status; reconfigure its isolated copy in-place.
            self.autotools(source, source, ['--enable-shared', '--enable-test', '--enable-examples',
                                           '--disable-curses'], autogen=['autoreconf', '-fi'])
            self.command([source/'CUnit/Sources/Test/test_cunit'], source)
            assert_cunit_internal_results(self.last_log.read_text())
        elif name == 'googletest':
            self.cmake(source, build, ['-DBUILD_SHARED_LIBS=OFF', '-Dgtest_build_tests=ON',
                                      '-Dgmock_build_tests=ON'])
        elif name == 'json-c':
            self.cmake(source, build, ['-DBUILD_SHARED_LIBS=ON', '-DBUILD_TESTING=ON'])
        elif name == 'jpeg':
            self.autotools(source, build, ['--enable-shared', '--disable-static'])
        elif name == 'libpng':
            self.cmake(source, build, ['-DPNG_SHARED=ON', '-DPNG_STATIC=OFF', '-DPNG_TESTS=ON'])
        elif name == 'tiff':
            self.cmake(source, build, ['-DBUILD_SHARED_LIBS=ON', '-Dtiff-tests=ON',
                                      '-Dtiff-tools=ON', '-Dtiff-docs=OFF',
                                      '-Dlzma=OFF', '-Dzstd=OFF', '-Dwebp=OFF', '-Djbig=OFF',
                                      '-Djpeg12=OFF', '-Dlibdeflate=OFF'])
        elif name == 'geos':
            self.cmake(source, build, ['-DBUILD_SHARED_LIBS=ON', '-DBUILD_TESTING=ON',
                                      '-DBUILD_GEOSOP=ON'])
        elif name == 'curl':
            # PROJ's retained CLI tests require the curl-enabled API variant.
            # This transport is experimental HTTP-only; PROJ networking stays
            # OFF and offline_exec denies network sockets throughout this run.
            flags = ['--enable-debug', '--enable-http', '--disable-docs', '--disable-manual',
                     '--without-ssl', '--without-libpsl', '--without-libidn2',
                     '--without-libgsasl', '--without-librtmp', '--without-libssh2',
                     '--without-libssh', '--without-wolfssh', '--without-nghttp2',
                     '--without-nghttp3', '--without-ngtcp2', '--without-quiche',
                     '--without-msh3', '--without-libuv', '--without-gssapi',
                     '--without-zstd', '--without-brotli', '--disable-ares',
                     f'--with-zlib={p}']
            flags += ['--disable-' + protocol for protocol in
                      ('ftp', 'file', 'ipfs', 'ldap', 'ldaps', 'rtsp', 'dict', 'telnet',
                       'tftp', 'pop3', 'imap', 'smb', 'smtp', 'gopher', 'mqtt', 'websockets')]
            self.autotools(source, build, flags, test_target=None)
            self.command(['make', '-C', build/'lib', 'libcurlu.la', f'-j{self.jobs}'], self.root)
            units = ['unit1300', 'unit1302', 'unit1303', 'unit1305', 'unit1309']
            self.command(['make', '-C', build/'tests/unit', f'-j{self.jobs}', *units], self.root)
            for unit in units:
                self.command([build/'tests/unit'/unit, 'http://unused.invalid'], self.root)
            self.command([p/'bin/curl', '--version'], self.root)
        elif name == 'proj':
            self.env['PYTHONPATH'] = str(self.source('pyyaml')/'lib')
            self.cmake(source, build, ['-DBUILD_SHARED_LIBS=ON', '-DBUILD_TESTING=ON',
                                      '-DENABLE_CURL=ON', '-DBUILD_PROJSYNC=OFF', '-DENABLE_TIFF=ON',
                                      '-DUSE_EXTERNAL_GTEST=ON', '-DTESTING_USE_NETWORK=OFF',
                                      '-DRUN_NETWORK_DEPENDENT_TESTS=OFF'])
        elif name == 'protobuf':
            self.cmake(source, build, ['-Dprotobuf_BUILD_SHARED_LIBS=ON',
                                      '-Dprotobuf_BUILD_TESTS=ON', '-Dprotobuf_USE_EXTERNAL_GTEST=ON'])
        elif name == 'protobuf-c':
            self.autotools(source, build, ['--enable-shared'], autogen=['autoreconf', '-fi'])
        elif name == 'gdal':
            test_source = self.source('gdal-tests')
            if not (source/'autotest').exists():
                (source/'autotest').symlink_to(test_source, target_is_directory=True)
            self.cmake(source, build, ['-DBUILD_SHARED_LIBS=ON', '-DBUILD_TESTING=ON',
                                      '-DGDAL_USE_EXTERNAL_LIBS=OFF', '-DUSE_EXTERNAL_GTEST=ON',
                                      '-DGDAL_USE_ZLIB=ON', '-DGDAL_USE_TIFF=ON',
                                      '-DGDAL_USE_PNG=ON', '-DGDAL_USE_JPEG=ON',
                                      '-DGDAL_USE_GEOTIFF_INTERNAL=ON',
                                      '-DGDAL_BUILD_OPTIONAL_DRIVERS=OFF',
                                      '-DOGR_BUILD_OPTIONAL_DRIVERS=OFF',
                                      '-DGDAL_ENABLE_DRIVER_GTIFF=ON', '-DGDAL_ENABLE_DRIVER_PNG=ON',
                                      '-DGDAL_ENABLE_DRIVER_JPEG=ON', '-DGDAL_ENABLE_DRIVER_RAW=ON',
                                      '-DGDAL_ENABLE_DRIVER_AAIGRID=ON', '-DGDAL_ENABLE_DRIVER_DTED=ON',
                                      '-DOGR_ENABLE_DRIVER_SHAPE=ON',
                                      '-DBUILD_PYTHON_BINDINGS=OFF', '-DBUILD_JAVA_BINDINGS=OFF',
                                      '-DBUILD_CSHARP_BINDINGS=OFF', '-DGDAL_USE_CURL=OFF'])
            self.command([p/'bin/gdalinfo', '--formats'], self.root)
            require_gdal_raster_drivers(self.last_log.read_text())
            self.command([p/'bin/ogrinfo', '--formats'], self.root)
            if not re.search(r'^\s+ESRI Shapefile\s+-', self.last_log.read_text(), re.M):
                raise RuntimeError('GDAL omitted required OGR Shapefile driver')
        elif name == 'postgresql':
            # pg_regress otherwise places sockets below long TMPDIR paths,
            # exceeding Linux's 107-byte UNIX sockaddr limit.
            with tempfile.TemporaryDirectory(prefix='ambisgis-pgr-', dir='/tmp') as sockets:
                self.env['PG_REGRESS_SOCK_DIR'] = sockets
                try:
                    self.autotools(source, build, ['--without-readline', '--with-libxml',
                                                  '--with-zlib'], test_target='check')
                    # Required by the inherited installed TIGER extension suite.
                    for target in ('all', 'check', 'install'):
                        self.command(['make', '-C', build/'contrib/fuzzystrmatch',
                                      f'-j{self.jobs}', target], build)
                finally:
                    self.env.pop('PG_REGRESS_SOCK_DIR', None)
            self.command([p / 'bin/pg_config'], self.root)
            if subprocess.check_output([p/'bin/pg_config', '--bindir'], env=self.env, text=True).strip() != str(p/'bin'):
                raise RuntimeError('pg_config escaped the isolated prefix')
        elif name in ('postgis-upgrade', 'postgis'):
            self.command(['./autogen.sh'], source)
            build.mkdir(parents=True, exist_ok=True)
            self.command([source/'configure', f'--prefix={p}', f'--with-pgconfig={p}/bin/pg_config',
                          f'--with-geosconfig={p}/bin/geos-config', f'--with-gdalconfig={p}/bin/gdal-config',
                          f'--with-projdir={p}', '--without-sfcgal', '--without-gui',
                          '--without-address-standardizer'], build)
            config = (build/'postgis_config.h').read_text()
            for feature in ('HAVE_LIBJSON', 'HAVE_LIBPROTOBUF'):
                if not re.search(r'^#define ' + feature + r' 1$', config, re.M):
                    raise RuntimeError(f'required PostGIS feature silently omitted: {feature}')
            for directory in ('liblwgeom/cunit', 'raster/test/cunit'):
                makefile = (build/directory/'Makefile').read_text()
                if not re.search(r'^CUNIT_LDFLAGS\s*=.*-lcunit', makefile, re.M):
                    raise RuntimeError(f'CUnit was not configured: {directory}')
            self.command(['make', f'-j{self.jobs}'], build)
            self.command(['make', 'check-unit'], build)
            self.command(['make', 'install'], build)
        else:
            raise ValueError(name)
        identity = {'input': self.inputs[name], 'recipe_sha256': self.recipe_sha256,
                    'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
        (self.logs/f'{name}-built.json').write_text(json.dumps(identity, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, default=HERE/'inputs.json')
    parser.add_argument('--custody', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--components', nargs='+', choices=ORDER, required=True)
    args = parser.parse_args()
    if args.jobs < 1 or args.jobs > 32:
        parser.error('--jobs must be between 1 and 32')
    if os.geteuid() == 0:
        parser.error('run as an unprivileged user; this recipe never needs root')
    run = args.run.resolve()
    if run == Path('/') or run.is_relative_to(Path('/usr')) or run.is_relative_to(Path('/etc')):
        parser.error('select an isolated build directory')
    from acquisition import load_manifest
    manifest = load_manifest(args.inputs)
    builder = Builder(manifest, args.custody.resolve(), run, args.jobs)
    try:
        for name in args.components:
            builder.build(name)
    finally:
        builder.close()


if __name__ == '__main__':
    main()
