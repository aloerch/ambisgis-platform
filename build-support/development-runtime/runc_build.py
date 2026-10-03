#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline owned runc relocation build; no engine or container execution.

The one native test executes only the production bootstrap-environment helper.
All source/vendor/compiler inputs are retained; old producer outputs stay intact.
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

BUILD = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/plt01-podman-build')
PRIOR = BUILD / 'build-002'
ARCHIVE = Path('/home/revelberry/Projects/AmbisGIS/source-archives/plt01-container/obs-source/runc-64446271a17ff823ebb1b17b0b955d06/runc-1.5.1.tar.xz')
PINS = {
    ARCHIVE: 'db743b39fd7de8da88adce5a61a54529a494928cd59227fffb622f5cb4ba6ef9',
    PRIOR / 'build-executed.py': '3a9c5296340713e36fdd8262cfa3fccb296ac627cccd64b53701ad3c4dd4bdd0',
    PRIOR / 'offline-executed.py': 'ed658e05bc1cde8b008835b146bf2be73487313f581ce66da31d5644b3766ace',
    BUILD / 'payload-002/receipt.json': '4157844e49b38d1dd5640de880b90a8df20fb0ba2c3ce6eb1a6227233a16fd8f',
    BUILD / 'sources-002.json': '15abaf87fa3422002a0e2ead720405f2ae8e78d28f6640442187bba5c4b35c2a',
}
CONTAINER_SHA = '7e271bc45f332cfd5f406ae284a8d8bf7bca8acd49e9adb45e364328bac5c889'
INIT_SHA = 'fd94c3f85b63c6ac87cbce2f25ff4654e37fdebbef84e5c4e0a0b64e1208d166'
TAGS = 'seccomp,urfave_cli_no_docs,libpathrs'
HELPER = '''// ambisgisInitEnvironment preserves only the owned launcher's validated
// library path for the sealed init executable's loader. The normal init
// Clearenv boundary and container process environment remain unchanged.
func ambisgisInitEnvironment(getenv func(string) string) []string {
	env := []string{"GOMAXPROCS=" + getenv("GOMAXPROCS")}
	if libraryPath := getenv("LD_LIBRARY_PATH"); libraryPath != "" {
		env = append(env, "LD_LIBRARY_PATH="+libraryPath)
	}
	return env
}

'''
NATIVE_TEST = '''// SPDX-License-Identifier: Apache-2.0
package libcontainer

import (
	"reflect"
	"testing"
)

// Only environment construction runs: no container, namespace, child or init.
func TestAmbisGISInitEnvironment(t *testing.T) {
	for _, tc := range []struct {
		name string
		input map[string]string
		want []string
	}{
		{"absent", map[string]string{}, []string{"GOMAXPROCS="}},
		{"owned", map[string]string{"GOMAXPROCS":"2", "LD_LIBRARY_PATH":"/private/relocated-bundle/runtime/lib64"}, []string{"GOMAXPROCS=2", "LD_LIBRARY_PATH=/private/relocated-bundle/runtime/lib64"}},
		{"unrelated", map[string]string{"GOMAXPROCS":"1", "LD_LIBRARY_PATH":"", "LD_PRELOAD":"/untrusted.so", "LD_AUDIT":"/audit.so", "PATH":"/untrusted", "_LIBCONTAINER_INITPIPE":"99"}, []string{"GOMAXPROCS=1"}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var queried []string
			got := ambisgisInitEnvironment(func(key string) string { queried=append(queried,key); return tc.input[key] })
			if !reflect.DeepEqual(got,tc.want) { t.Fatalf("unexpected bootstrap environment: %q",got) }
			if !reflect.DeepEqual(queried,[]string{"GOMAXPROCS","LD_LIBRARY_PATH"}) { t.Fatalf("unexpected inherited keys: %q",queried) }
		})
	}
}
'''


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def encoded(value): return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def retained_helper():
    for path, expected in PINS.items():
        if any(p.is_symlink() for p in (path, *path.parents)) or sha(path) != expected:
            raise ValueError('Retained input changed')
    spec = importlib.util.spec_from_file_location('retained_podman_build', PRIOR / 'build-executed.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def extract(archive, destination):
    """One pinned tree, including its single known internal source symlink."""
    seen = set(); total = 0; links = []
    with tarfile.open(archive) as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'runc-1.5.1':
                raise ValueError('Source member escapes expected tree')
            known_link = (member.issym() and member.name == 'runc-1.5.1/libcontainer/nsenter/test/escape.c'
                          and member.linkname == '../escape.c')
            if member.name in seen or not (member.isdir() or member.isfile() or known_link):
                raise ValueError('Duplicate or unsupported source member')
            seen.add(member.name)
            if str(path) != member.name.rstrip('/'):
                raise ValueError('Noncanonical source member')
            target = destination.joinpath(*path.parts[1:])
            if known_link: links.append((target, member.linkname)); continue
            if member.isdir(): target.mkdir(mode=0o700, parents=True, exist_ok=True); continue
            total += member.size
            if member.size > 16 * 1024 * 1024 or total > 128 * 1024 * 1024:
                raise ValueError('Source archive bound exceeded')
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with target.open('xb') as output, tar.extractfile(member) as source:
                shutil.copyfileobj(source, output)
            target.chmod(0o600)
    for target, link in links:
        resolved = Path(os.path.abspath(target.parent / link))
        if not resolved.is_relative_to(destination) or not resolved.is_file() or any(p.is_symlink() for p in target.parents):
            raise ValueError('Pinned source link is not contained')
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.symlink_to(link)


def patch(source):
    path = source / 'libcontainer/container_linux.go'
    if sha(path) != CONTAINER_SHA or sha(source / 'libcontainer/init_linux.go') != INIT_SHA:
        raise ValueError('Exact native source required')
    original = path.read_text()
    anchor = 'func (c *Container) newParentProcess(p *Process) (parentProcess, error) {'
    assignment = '\tcmd.Env = append(cmd.Env, "GOMAXPROCS="+os.Getenv("GOMAXPROCS"))'
    if original.count(anchor) != 1 or original.count(assignment) != 1:
        raise ValueError('Native source boundary changed')
    changed = original.replace(anchor, HELPER + anchor).replace(assignment, '\tcmd.Env = ambisgisInitEnvironment(os.Getenv)')
    path.write_text(changed)
    test = source / 'libcontainer/ambisgis_environment_test.go'
    with test.open('x') as stream: stream.write(NATIVE_TEST)
    return ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                      fromfile='a/libcontainer/container_linux.go', tofile='b/libcontainer/container_linux.go'))


def child(output):
    invocation = json.loads((output / 'invocation.json').read_text())
    env = invocation['build_environment']; source = output / 'source'
    go = str(output / 'toolchain/usr/lib64/go/1.27/bin/go')
    common = ['-x', '-p=2', '-mod=vendor', '-buildvcs=false', '-trimpath', '-tags', TAGS]
    commands = [
        ('bootstrap-test-compile', [go, 'test', '-c', *common, '-o', str(output / 'bin/bootstrap.test'), './libcontainer']),
        # A descriptive patch label is not a Git commit. Leave upstream's
        # default revision metadata untouched; custody binds real byte hashes.
        ('runc-build', [go, 'build', *common, '-buildmode=pie', '-o', str(output / 'bin/runc'), '.']),
        ('bootstrap-environment-unit', [str(output / 'bin/bootstrap.test'), '-test.run=^TestAmbisGISInitEnvironment$', '-test.count=1', '-test.v']),
    ]
    rows = []
    for name, command in commands:
        log = output / (name + '.log')
        with log.open('xb') as stream:
            run = subprocess.run(command, cwd=source, env=env, stdout=stream, stderr=subprocess.STDOUT)
        rows.append({'name': name, 'command': command, 'exit_code': run.returncode, 'log': str(log), 'log_sha256': sha(log)})
        if run.returncode: break
    (output / 'commands.json').write_bytes(encoded({'commands': rows, 'exit_code': rows[-1]['exit_code'],
        'native_test_scope': 'Only TestAmbisGISInitEnvironment constructs strings; no runc CLI, container, namespace or vulnerability test execution.'}))
    return rows[-1]['exit_code']


def build(output, prepare_only=False):
    helper = retained_helper(); output = helper.checked_path(output, new=True)
    payload = json.loads((BUILD / 'payload-002/receipt.json').read_text())
    custody = json.loads((BUILD / 'sources-002.json').read_text())
    if payload['failures'] or custody['failures']: raise ValueError('Incomplete retained custody')
    for group in custody['results']:
        revision = group['listing_url'].split('?rev=', 1)[1]; flavor = group.get('multibuild_flavor')
        directory = group['source_package'] + ('_' + flavor if flavor else '') + '-' + revision
        for row in group['files']:
            path = Path('/home/revelberry/Projects/AmbisGIS/source-archives/plt01-podman-build/obs-source') / directory / row['name']
            if sha(helper.checked_path(path)) != row['sha256']: raise ValueError('Retained toolchain source changed')
    os.umask(0o077); output.mkdir(parents=True)
    for name in ('original', 'source', 'toolchain', 'bin', 'command-bin', 'home', 'cache', 'modcache', 'gopath', 'tmp'):
        (output / name).mkdir()
    extract(ARCHIVE, output / 'original')
    shutil.copytree(output / 'original', output / 'source', dirs_exist_ok=True, symlinks=True)
    (output / 'owned-source.patch').write_text(patch(output / 'source'))
    staged = helper.stage_toolchain(payload, output / 'toolchain')
    (output / 'toolchain.json').write_bytes(encoded(staged))
    prefix = output / 'toolchain'; commands = output / 'command-bin'
    wrapper = commands / 'cc'
    wrapper.write_text(helper.compiler_wrapper(prefix / 'usr/bin/gcc-16', prefix, prefix / 'usr/lib64/gcc/x86_64-suse-linux/16', commands)); wrapper.chmod(0o700)
    for name, target in {'as':'as','ld':'ld.bfd','ar':'ar','pkg-config':'pkgconf'}.items():
        (commands / name).symlink_to(prefix / 'usr/bin' / target)
    host = []
    for name in ('/bin/sh', '/lib64/ld-linux-x86-64.so.2', '/usr/lib64/libc.so.6'):
        actual = Path(name).resolve(); selected = prefix / str(actual).lstrip('/')
        if sha(actual) != sha(selected): raise ValueError('Host compiler support differs')
        host.append({'path': name, 'resolved': str(actual), 'sha256': sha(actual), 'retained': str(selected)})
    env = {'HOME':str(output/'home'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PATH':str(commands),
        'TMPDIR':str(output/'tmp'),'GOROOT':str(prefix/'usr/lib64/go/1.27'),'GOTOOLCHAIN':'local','GOPROXY':'off','GOSUMDB':'off','GOWORK':'off','GOENV':'off',
        'GOCACHE':str(output/'cache'),'GOMODCACHE':str(output/'modcache'),'GOPATH':str(output/'gopath'),'GOMAXPROCS':'2','CGO_ENABLED':'1',
        'CC':str(wrapper),'PKG_CONFIG':str(commands/'pkg-config'),'PKG_CONFIG_LIBDIR':str(prefix/'usr/lib64/pkgconfig')+':'+str(prefix/'usr/share/pkgconfig'),
        'PKG_CONFIG_SYSROOT_DIR':str(prefix),'LD_LIBRARY_PATH':str(prefix/'usr/lib64')}
    original, source = helper.inventory(output/'original'), helper.inventory(output/'source')
    preparation = {'original':original,'patched':source,'patch_sha256':sha(output/'owned-source.patch'),
        'init_clearenv_source_unchanged':sha(output/'source/libcontainer/init_linux.go')==INIT_SHA}
    (output/'preparation.json').write_bytes(encoded(preparation))
    invocation = {'schema_version':1,'recipe_sha256':sha(Path(__file__)),'inputs':[{'path':str(p),'sha256':s} for p,s in PINS.items()],
        'host_compiler_support':host,'build_environment':env,'tags':TAGS,'preparation_sha256':sha(output/'preparation.json'),
        'supervisor':{'path':sys.executable,'sha256':sha(sys.executable)},'scope':'Compiler plus one string-only native unit test, existing socket denial; not a hostile filesystem sandbox or complete toolchain bootstrap.'}
    (output/'invocation.json').write_bytes(encoded(invocation))
    shutil.copyfile(Path(__file__),output/'build-executed.py');shutil.copyfile(PRIOR/'offline-executed.py',output/'offline-executed.py')
    if prepare_only: return output/'invocation.json'
    command=[sys.executable,'-B',str(output/'offline-executed.py'),'--evidence',str(output/'network.json'),'--',sys.executable,'-B',str(output/'build-executed.py'),'--child','--output',str(output)]
    run=subprocess.run(command,cwd=output,env={'HOME':str(output/'home'),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'})
    unchanged={'source':helper.inventory(output/'source')==source,'original':helper.inventory(output/'original')==original,'toolchain':helper.inventory(prefix)==staged['inventory']}
    result={'schema_version':1,'exit_code':run.returncode if run.returncode else (0 if all(unchanged.values()) else 1),
        'unchanged':unchanged,'outer_command':command,'artifacts':helper.inventory(output/'bin'),'records':{n:sha(output/n) for n in ['invocation.json','preparation.json','toolchain.json','commands.json','network.json','owned-source.patch']},
        'runc_cli_executed':False,'container_executed':False,'held_targeted_probe_executed':False,'full_installation_acceptance':False}
    (output/'result.json').write_bytes(encoded(result))
    if result['exit_code']: raise ValueError('Owned relocation build/test failed; retained result records the failure')
    return output/'result.json'


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--child',action='store_true');parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    if args.child: raise SystemExit(child(args.output))
    print(build(args.output,args.prepare_only))
