#!/usr/bin/env python3
"""Build Linux-PAM shared libraries for the isolated native-test fixture.

Use the parent build's network-denial wrapper. Only libpam/libpam_misc are built;
no modules, helpers, host installation or authentication tests run here.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


SOURCE_SHA256 = '3d86b6383fb5fd9eb9578d2cd47d92801191f4bf3f9bc61419bfefc8aa1e531a'
TOOL_PATH = '/usr/bin:/bin'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    if digest(args.archive) != SOURCE_SHA256:
        raise ValueError('Linux-PAM source hash mismatch')
    tools = {}
    for name in ('meson', 'ninja', 'gcc', 'ld', 'ar', 'pkg-config', 'ldd'):
        found = shutil.which(name, path=TOOL_PATH)
        if found is None:
            raise ValueError('required host tool missing: '+name)
        tools[name] = {'path': found, 'sha256': digest(found)}
    run = args.run.resolve()
    run.mkdir(parents=True, exist_ok=False)
    for name in ('home', 'tmp', 'logs', 'prefix/lib', 'prefix/share/licenses/Linux-PAM'):
        (run/name).mkdir(parents=True)
    recipe = Path(__file__).read_bytes()
    (run/'build_pam.py').write_bytes(recipe)
    report = {
        'source_sha256': SOURCE_SHA256, 'recipe_sha256': hashlib.sha256(recipe).hexdigest(),
        'started': now(), 'status': 'running', 'commands': [], 'host_tools': tools,
        'scope': 'Only libpam/libpam_misc; no authentication modules, helpers, system installation, host PAM configuration or OS-account tests.',
        'license': 'BSD-3-Clause OR GPL-2.0-or-later (project metadata; retain source notices)',
        'host_dependency_limit': 'Tool executable hashes do not retain compiler, Meson Python modules, headers, libc or the complete host toolchain.',
    }
    prefix, build = run/'prefix', run/'build'
    env = {'PATH': TOOL_PATH, 'HOME': str(run/'home'), 'TMPDIR': str(run/'tmp'),
           'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'PYTHONNOUSERSITE': '1',
           'CC': tools['gcc']['path'], 'LD_LIBRARY_PATH': str(prefix/'lib')}

    def save():
        (run/'report.json').write_text(json.dumps(report, indent=2)+'\n')

    def command(name, argv):
        log = run/'logs'/(name+'.log')
        record = {'name': name, 'argv': [str(item) for item in argv],
                  'log': str(log.relative_to(run)), 'started': now()}
        report['commands'].append(record)
        save()
        with log.open('x') as stream:
            result = subprocess.run(record['argv'], env=env, cwd=run,
                                    stdout=stream, stderr=subprocess.STDOUT)
        record.update(exit_code=result.returncode, log_sha256=digest(log), finished=now())
        save()
        print(name, result.returncode, flush=True)
        if result.returncode:
            raise RuntimeError('Linux-PAM command failed: '+str(log))

    try:
        with tarfile.open(args.archive) as archive:
            archive.extractall(run, filter='data')
        source = run/'Linux-PAM-1.7.2'
        command('configure', [tools['meson']['path'], 'setup', build, source,
                '--prefix='+str(prefix), '--libdir=lib', '--sysconfdir=etc', '--wrap-mode=nodownload',
                '-Ddocs=disabled', '-Di18n=disabled', '-Dexamples=false', '-Dxtests=false',
                '-Daudit=disabled', '-Deconf=disabled', '-Dselinux=disabled', '-Dlogind=disabled',
                '-Delogind=disabled', '-Dnis=disabled', '-Dpwaccess=disabled',
                '-Dpam_userdb=disabled', '-Dpam_unix=disabled', '-Dvendordir='])
        command('compile', [tools['ninja']['path'], '-C', build,
                'libpam/libpam.so.0.85.1', 'libpam_misc/libpam_misc.so.0.82.1'])
        for module in ('libpam', 'libpam_misc'):
            for path in (build/module).glob(module+'.so*'):
                if path.is_dir():
                    continue
                destination = prefix/'lib'/path.name
                if path.is_symlink():
                    target = os.readlink(path)
                    if Path(target).name != target:
                        raise ValueError('unexpected library symlink: '+str(path))
                    destination.symlink_to(target)
                else:
                    shutil.copy2(path, destination)
        shutil.copy2(source/'COPYING', prefix/'share/licenses/Linux-PAM/COPYING')
        for name in ('libpam.so', 'libpam.so.0', 'libpam_misc.so', 'libpam_misc.so.0'):
            path = prefix/'lib'/name
            if not path.is_file() or not path.resolve().is_relative_to(prefix/'lib'):
                raise ValueError('missing or unsafe built library: '+str(path))
        report['artifacts'] = [
            {'path': str(path.relative_to(run)), 'sha256': digest(path), 'size': path.stat().st_size}
            for path in sorted((prefix/'lib').glob('*')) if not path.is_symlink()]
        report['symlinks'] = {str(path.relative_to(run)): os.readlink(path)
                              for path in sorted((prefix/'lib').glob('*')) if path.is_symlink()}
        command('linked-libraries', [tools['ldd']['path'], prefix/'lib/libpam.so.0',
                                    prefix/'lib/libpam_misc.so.0'])
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        report['finished'] = now()
        save()


if __name__ == '__main__':
    main()
