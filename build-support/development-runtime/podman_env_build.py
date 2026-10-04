#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare an owned ordinary-OCI environment repair; execution is a separate step.

Never invokes the prior build recipe's child/main, Podman, rootlessport, a
container, inherited native suites, checkpoint tests, or a namespace helper.
Only the new standalone string-construction Go unit is executed after review.
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

BUILD = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/plt01-podman-build')
PRIOR = BUILD / 'build-002'
PREPARATION = BUILD / 'preparation-002/preparation.json'
PINS = {
    PRIOR / 'build-executed.py': '3a9c5296340713e36fdd8262cfa3fccb296ac627cccd64b53701ad3c4dd4bdd0',
    PRIOR / 'offline-executed.py': 'ed658e05bc1cde8b008835b146bf2be73487313f581ce66da31d5644b3766ace',
    PRIOR / 'result.json': '0f65a25904208c2239bf7a6f53448331e1739fdd2a3919ba6b11cf10b39c9591',
    PRIOR / 'invocation.json': 'bcfaf2b4a884036d030aa3f25b55aff0e08798256591b10bd53fadc4734c5782',
    PREPARATION: '658d3de3f3f47e28f9df16556fe93d7213a3b0de9b042395df56fd14de5de3fe',
    BUILD / 'payload-002/receipt.json': '4157844e49b38d1dd5640de880b90a8df20fb0ba2c3ce6eb1a6227233a16fd8f',
    BUILD / 'sources-002.json': '15abaf87fa3422002a0e2ead720405f2ae8e78d28f6640442187bba5c4b35c2a',
}
OCI_SHA = 'ad0bdeff0bbad458e82cc747f1dca088197752ee27bd3b0dc03966e339db64f5'
METHODS = ('StartContainer', 'UpdateContainer', 'killContainer', 'DeleteContainer', 'PauseContainer', 'UnpauseContainer')
TAGS = 'apparmor,seccomp,systemd,exclude_graphdriver_btrfs'
ASSIGNMENT = '\tenv := []string{fmt.Sprintf("XDG_RUNTIME_DIR=%s", runtimeDir)}'
WITH_PATH = ASSIGNMENT + '\n\tif path, ok := os.LookupEnv("PATH"); ok {\n\t\tenv = append(env, fmt.Sprintf("PATH=%s", path))\n\t}'
CALL = '\tenv := ambisgisOrdinaryOCIEnvironment(runtimeDir, rootless.IsRootless(), os.LookupEnv)'
HELPER = '''// SPDX-License-Identifier: Apache-2.0
// AmbisGIS modification, 2026-10-03: ordinary host OCI child environment only.
package libpod

// The owned launcher validates these host paths and the user bus before Podman
// starts. Never inherit the whole environment or alter the container's env.
// Keep the existing conmon rule excluding the user session bus when rootful.
func ambisgisOrdinaryOCIEnvironment(runtimeDir string, isRootless bool, lookup func(string) (string, bool)) []string {
	env := []string{"XDG_RUNTIME_DIR=" + runtimeDir}
	keys := []string{"PATH", "LD_LIBRARY_PATH"}
	if isRootless {
		keys = append(keys, "DBUS_SESSION_BUS_ADDRESS")
	}
	for _, key := range keys {
		if value, present := lookup(key); present {
			env = append(env, key+"="+value)
		}
	}
	return env
}
'''
TEST = '''// SPDX-License-Identifier: Apache-2.0
package libpod

import (
	"reflect"
	"testing"
)

// Compiled with only the production helper file. No libpod init/TestMain,
// container, child process, bus, namespace, engine or inherited suite runs.
func TestAmbisGISOrdinaryOCIEnvironment(t *testing.T) {
	for _, tc := range []struct {
		name string
		rootless bool
		input map[string]string
		want []string
	}{
		{"absent", true, map[string]string{}, []string{"XDG_RUNTIME_DIR=/private/run"}},
		{"complete", true, map[string]string{"PATH":"/private/bin:/private/helpers", "LD_LIBRARY_PATH":"/private/lib64", "DBUS_SESSION_BUS_ADDRESS":"unix:path=/run/user/1207/bus", "LD_PRELOAD":"/untrusted.so", "LD_AUDIT":"/audit.so", "HOME":"/untrusted", "XDG_RUNTIME_DIR":"/untrusted", "CONTAINER_HOST":"ssh://untrusted"}, []string{"XDG_RUNTIME_DIR=/private/run", "PATH=/private/bin:/private/helpers", "LD_LIBRARY_PATH=/private/lib64", "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1207/bus"}},
		{"present_empty", true, map[string]string{"PATH":"", "LD_LIBRARY_PATH":"", "DBUS_SESSION_BUS_ADDRESS":""}, []string{"XDG_RUNTIME_DIR=/private/run", "PATH=", "LD_LIBRARY_PATH=", "DBUS_SESSION_BUS_ADDRESS="}},
		{"rootful", false, map[string]string{"PATH":"/private/bin", "LD_LIBRARY_PATH":"/private/lib64", "DBUS_SESSION_BUS_ADDRESS":"unix:path=/run/user/1207/bus"}, []string{"XDG_RUNTIME_DIR=/private/run", "PATH=/private/bin", "LD_LIBRARY_PATH=/private/lib64"}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var queried []string
			got := ambisgisOrdinaryOCIEnvironment("/private/run", tc.rootless, func(key string) (string, bool) { queried=append(queried,key); value,ok:=tc.input[key]; return value,ok })
			if !reflect.DeepEqual(got,tc.want) { t.Errorf("environment got %q want %q", got,tc.want) }
			keys:=[]string{"PATH","LD_LIBRARY_PATH"}
			if tc.rootless { keys=append(keys,"DBUS_SESSION_BUS_ADDRESS") }
			if !reflect.DeepEqual(queried,keys) { t.Errorf("queried keys got %q want %q",queried,keys) }
		})
	}
}
'''


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def encoded(value): return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def retained_helper():
    for path, identity in PINS.items():
        if any(p.is_symlink() for p in (path, *path.parents)) or sha(path) != identity:
            raise ValueError('Retained producer input changed')
    spec = importlib.util.spec_from_file_location('retained_podman_build', PRIOR / 'build-executed.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def inventory(helper, root, *, retained_toolchain=False):
    helper.checked_path(root)
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            # The signed toolchain intentionally omits non-/usr state such as
            # /var. Its retained dangling links are allowed only inside this
            # root and still bound by the complete signed staging manifest.
            if not path.resolve(strict=not retained_toolchain).is_relative_to(root): raise ValueError('Source link escapes retained tree')
        elif not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError('Unsupported source member')
    return helper.inventory(root)


def method(text, name):
    anchor = 'func (r *ConmonOCIRuntime) ' + name + '('
    if text.count(anchor) != 1: raise ValueError('Ordinary OCI method boundary changed')
    begin = text.index(anchor)
    end = text.find('\nfunc ', begin + len(anchor))
    return text[begin:end if end >= 0 else len(text)]


def patch(source):
    path = source / 'libpod/oci_conmon_common.go'
    if sha(path) != OCI_SHA: raise ValueError('Exact retained OCI source required')
    original = path.read_text(); changed = original; callsites = []
    for name in METHODS:
        block = method(original, name)
        expected = WITH_PATH if name in METHODS[:2] else ASSIGNMENT
        if block.count(expected) != 1: raise ValueError('Exact ordinary child environment changed')
        replacement = block.replace(expected, CALL)
        changed = changed.replace(block, replacement)
        callsites.append({'method': name, 'before_sha256': hashlib.sha256(block.encode()).hexdigest(),
                          'after_sha256': hashlib.sha256(replacement.encode()).hexdigest()})
    if method(changed, 'CheckpointContainer') != method(original, 'CheckpointContainer'):
        raise ValueError('Excluded checkpoint source changed')
    # Verify all destinations before the first write.
    for name in ('ambisgis_oci_environment.go', 'ambisgis_oci_environment_test.go'):
        if (source / 'libpod' / name).exists(): raise ValueError('Repair already present')
    path.write_text(changed)
    (source / 'libpod/ambisgis_oci_environment.go').write_text(HELPER)
    (source / 'libpod/ambisgis_oci_environment_test.go').write_text(TEST)
    delta = ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                       fromfile='a/libpod/oci_conmon_common.go', tofile='b/libpod/oci_conmon_common.go'))
    for name, text in [('ambisgis_oci_environment.go', HELPER), ('ambisgis_oci_environment_test.go', TEST)]:
        delta += ''.join(difflib.unified_diff([], text.splitlines(True), fromfile='/dev/null', tofile='b/libpod/' + name))
    # The negative is an exact extracted StartContainer environment block with
    # only its OS lookup dependency injected. It is not a container invocation.
    baseline = ('// SPDX-License-Identifier: Apache-2.0\npackage libpod\nimport "fmt"\n'
        'func ambisgisOrdinaryOCIEnvironment(runtimeDir string, _ bool, lookup func(string) (string, bool)) []string {\n'
        + WITH_PATH.replace('os.LookupEnv', 'lookup') + '\n\treturn env\n}\n')
    return delta, baseline, callsites


def command_plan(output):
    go = str(output / 'toolchain/usr/lib64/go/1.27/bin/go')
    common = ['-x', '-p=2', '-mod=vendor', '-buildvcs=false', '-trimpath']
    unit = ['-test.run=^TestAmbisGISOrdinaryOCIEnvironment$', '-test.count=1', '-test.v']
    return [
        ('baseline-compile', [go, 'test', '-c', *common, '-o', str(output/'bin/baseline.test'), str(output/'baseline/environment.go'), str(output/'baseline/environment_test.go')], 0),
        ('baseline-unit', [str(output/'bin/baseline.test'), *unit], 1),
        ('environment-compile', [go, 'test', '-c', *common, '-o', str(output/'bin/environment.test'), 'libpod/ambisgis_oci_environment.go', 'libpod/ambisgis_oci_environment_test.go'], 0),
        ('environment-unit', [str(output/'bin/environment.test'), *unit], 0),
        ('podman-build', [go, 'build', *common, '-tags', TAGS, '-o', str(output/'bin/podman'), './cmd/podman'], 0),
        ('rootlessport-build', [go, 'build', *common, '-tags', TAGS, '-o', str(output/'bin/rootlessport'), './cmd/rootlessport'], 0),
    ]


def prepare(output):
    helper = retained_helper(); output = helper.checked_path(output, new=True)
    prior = json.loads(PREPARATION.read_text()); result = json.loads((PRIOR/'result.json').read_text())
    if not prior['all_patches_applied'] or not prior['original_unchanged'] or result['exit_code'] or not result['source_unchanged']:
        raise ValueError('Prior producer incomplete')
    old = inventory(helper, PRIOR/'source')
    if old != prior['patched']: raise ValueError('Prior complete source differs')
    for row in [prior['source_archive'], prior['source_obsinfo'], *prior['patches']]:
        if sha(helper.checked_path(row['file'])) != row['sha256']: raise ValueError('Source custody changed')
    payload = json.loads((BUILD/'payload-002/receipt.json').read_text())
    custody = json.loads((BUILD/'sources-002.json').read_text())
    if payload['failures'] or custody['failures']: raise ValueError('Incomplete toolchain custody')
    source_rows = []
    for group in custody['results']:
        revision = group['listing_url'].split('?rev=', 1)[1]; flavor = group.get('multibuild_flavor')
        directory = group['source_package'] + ('_' + flavor if flavor else '') + '-' + revision
        for row in group['files']:
            path = Path('/home/revelberry/Projects/AmbisGIS/source-archives/plt01-podman-build/obs-source')/directory/row['name']
            if sha(helper.checked_path(path)) != row['sha256']: raise ValueError('Toolchain source changed')
            source_rows.append({'path': str(path), 'sha256': row['sha256']})
    os.umask(0o077); output.mkdir(parents=True)
    shutil.copytree(PRIOR/'source', output/'source', symlinks=True)
    for name in ('baseline', 'toolchain', 'bin', 'command-bin', 'home', 'cache', 'modcache', 'gopath', 'tmp'):
        (output/name).mkdir()
    delta, baseline, callsites = patch(output/'source')
    (output/'owned-source.patch').write_text(delta)
    (output/'baseline/environment.go').write_text(baseline)
    (output/'baseline/environment_test.go').write_text(TEST)
    source = inventory(helper, output/'source')
    if [p for p in old if old[p] != source[p]] != ['libpod/oci_conmon_common.go']:
        raise ValueError('Repair modified unselected source')
    if set(source)-set(old) != {'libpod/ambisgis_oci_environment.go','libpod/ambisgis_oci_environment_test.go'}:
        raise ValueError('Unexpected added source')
    staged = helper.stage_toolchain(payload, output/'toolchain')
    prefix = output/'toolchain'; commands = output/'command-bin'
    wrapper = commands/'cc'
    wrapper.write_text(helper.compiler_wrapper(prefix/'usr/bin/gcc-16',prefix,prefix/'usr/lib64/gcc/x86_64-suse-linux/16',commands)); wrapper.chmod(0o700)
    for name,target in {'as':'as','ld':'ld.bfd','ar':'ar','pkg-config':'pkgconf'}.items():
        (commands/name).symlink_to(prefix/'usr/bin'/target)
    (commands/'go').symlink_to(prefix/'usr/lib64/go/1.27/bin/go')
    host = []
    for name in ('/bin/sh','/lib64/ld-linux-x86-64.so.2','/usr/lib64/libc.so.6'):
        actual=Path(name).resolve(); selected=prefix/str(actual).lstrip('/')
        if sha(actual)!=sha(selected): raise ValueError('Host compiler support differs')
        info=actual.stat()
        host.append({'path':name,'resolved':str(actual),'sha256':sha(actual),'retained':str(selected),
                     'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid})
    env={'HOME':str(output/'home'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PATH':str(commands),'TMPDIR':str(output/'tmp'),
         'GOROOT':str(prefix/'usr/lib64/go/1.27'),'GOTOOLCHAIN':'local','GOPROXY':'off','GOSUMDB':'off','GOWORK':'off','GOENV':'off',
         'GOCACHE':str(output/'cache'),'GOMODCACHE':str(output/'modcache'),'GOPATH':str(output/'gopath'),'GOMAXPROCS':'2','CGO_ENABLED':'1',
         'CC':str(wrapper),'PKG_CONFIG':str(commands/'pkg-config'),'PKG_CONFIG_LIBDIR':str(prefix/'usr/lib64/pkgconfig')+':'+str(prefix/'usr/share/pkgconfig'),
         'PKG_CONFIG_SYSROOT_DIR':str(prefix),'LD_LIBRARY_PATH':str(prefix/'usr/lib64')}
    prep={'prior_source':old,'patched':source,'callsites':callsites,'baseline':inventory(helper,output/'baseline'),
          'vendor_unchanged':all(source[n]==v for n,v in old.items() if n.startswith('vendor/')),
          'existing_patches':prior['patches'],'source_archive':prior['source_archive'],'source_commit':prior['source_commit'],
          'new_patch_sha256':sha(output/'owned-source.patch'),'retained_toolchain_sources':source_rows}
    (output/'preparation.json').write_bytes(encoded(prep)); (output/'toolchain.json').write_bytes(encoded(staged))
    (output/'MODIFICATIONS.txt').write_text('AmbisGIS modification, 2026-10-03.\nPodman source '+prior['source_commit']+' and all three previously retained repairs are preserved.\nOnly six ordinary OCI host-child environment constructions use the added explicit allow-list helper.\nRootful session-bus exclusion remains; no container/init/conmon/checkpoint/restore environment changes.\nThe original Apache-2.0 LICENSE and all vendor source/notices remain in the complete source tree.\nNo source revision is invented or overridden. Exact source/patch/build hashes identify this derived build.\n')
    invocation={'schema_version':1,'recipe_sha256':sha(Path(__file__)),'inputs':[{'path':str(p),'sha256':s} for p,s in PINS.items()],
        'host_compiler_support':host,'build_environment':env,'commands':command_plan(output),'preparation_sha256':sha(output/'preparation.json'),
        'toolchain_sha256':sha(output/'toolchain.json'),'compiler_commands':helper.inventory(commands),
        'modifications_sha256':sha(output/'MODIFICATIONS.txt'),
        'supervisor':{'path':sys.executable,'sha256':sha(sys.executable)},
        'scope':'Only standalone production env helper and its four pure subcases; no libpod init/TestMain, prior native suites, engine, namespace or held probe. Offline compiler uses retained inputs; host bootstrap remains explicit.'}
    (output/'invocation.json').write_bytes(encoded(invocation))
    shutil.copyfile(Path(__file__),output/'build-executed.py');shutil.copyfile(PRIOR/'offline-executed.py',output/'offline-executed.py')
    return output/'invocation.json'


def verified_preparation(output, identity):
    helper=retained_helper(); output=helper.checked_path(output)
    if sha(output/'invocation.json')!=identity: raise ValueError('Reviewed invocation changed')
    v=json.loads((output/'invocation.json').read_text())
    if sha(Path(__file__))!=v['recipe_sha256'] or sha(output/'build-executed.py')!=v['recipe_sha256']:
        raise ValueError('Reviewed recipe changed')
    for name,key in [('preparation.json','preparation_sha256'),('toolchain.json','toolchain_sha256')]:
        if sha(output/name)!=v[key]: raise ValueError('Reviewed preparation record changed')
    p=json.loads((output/'preparation.json').read_text()); t=json.loads((output/'toolchain.json').read_text())
    if sha(output/'owned-source.patch')!=p['new_patch_sha256'] or sha(output/'MODIFICATIONS.txt')!=v['modifications_sha256']:
        raise ValueError('Source patch or notice changed')
    if inventory(helper,output/'source')!=p['patched'] or inventory(helper,output/'baseline')!=p['baseline'] or inventory(helper,output/'toolchain',retained_toolchain=True)!=t['inventory']:
        raise ValueError('Prepared bytes changed')
    if json.loads(encoded(command_plan(output)))!=v['commands']: raise ValueError('Compiler/test command plan changed')
    if sha(output/'offline-executed.py')!=PINS[PRIOR/'offline-executed.py']: raise ValueError('Socket-denial helper changed')
    commands=output/'command-bin'
    if {p.name for p in commands.iterdir()}!=set(v['compiler_commands']) or helper.inventory(commands)!=v['compiler_commands']:
        raise ValueError('Compiler command closure changed')
    for path in commands.iterdir():
        if path.is_symlink() and not path.resolve(strict=True).is_relative_to(output/'toolchain'):
            raise ValueError('Compiler link escapes toolchain')
    for row in v['host_compiler_support']:
        actual=Path(row['path']).resolve();info=actual.stat()
        if str(actual)!=row['resolved'] or sha(actual)!=row['sha256'] or (stat.S_IMODE(info.st_mode),info.st_uid,info.st_gid)!=(row['mode'],row['uid'],row['gid']):
            raise ValueError('Host compiler support changed')
    if sha(sys.executable)!=v['supervisor']['sha256']: raise ValueError('Validation supervisor changed')
    if inventory(helper,PRIOR/'source')!=p['prior_source']: raise ValueError('Prior source changed')
    for row in [p['source_archive'],*p['existing_patches']]:
        if sha(helper.checked_path(row['file']))!=row['sha256']: raise ValueError('Prior source custody changed')
    for row in p['retained_toolchain_sources']:
        if sha(helper.checked_path(row['path']))!=row['sha256']: raise ValueError('Toolchain source custody changed')
    return helper,v,p,t


def child(output, identity):
    _,v,_,_=verified_preparation(output,identity); rows=[]; code=0
    for name,command,expected in v['commands']:
        log=output/(name+'.log')
        with log.open('xb') as stream:
            run=subprocess.run(command,cwd=output/'source',env=v['build_environment'],stdout=stream,stderr=subprocess.STDOUT)
        passed=run.returncode==expected
        if name=='baseline-unit':
            text=log.read_text()
            passed=passed and all('--- FAIL: TestAmbisGISOrdinaryOCIEnvironment/'+case in text for case in ('absent','complete','present_empty','rootful'))
        rows.append({'name':name,'command':command,'expected_exit':expected,'exit_code':run.returncode,'passed':passed,'log':str(log),'log_sha256':sha(log)})
        if not passed: code=1;break
    (output/'commands.json').write_bytes(encoded({'commands':rows,'exit_code':code,'scope':v['scope']}))
    return code


def execute(output, identity):
    helper,v,p,t=verified_preparation(output,identity)
    if any((output/n).exists() for n in ('network.json','commands.json','result.json')): raise ValueError('Execution output already exists')
    command=[sys.executable,'-B',str(output/'offline-executed.py'),'--evidence',str(output/'network.json'),'--',sys.executable,'-B',str(output/'build-executed.py'),'--child','--output',str(output),'--invocation-sha256',identity]
    run=subprocess.run(command,cwd=output,env={'HOME':str(output/'home'),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'})
    unchanged={'source':inventory(helper,output/'source')==p['patched'],'prior_source':inventory(helper,PRIOR/'source')==p['prior_source'],
               'baseline':inventory(helper,output/'baseline')==p['baseline'],'toolchain':inventory(helper,output/'toolchain',retained_toolchain=True)==t['inventory']}
    records={n:sha(output/n) for n in ('invocation.json','preparation.json','toolchain.json','owned-source.patch','MODIFICATIONS.txt','commands.json','network.json') if (output/n).is_file()}
    result={'schema_version':1,'exit_code':run.returncode if run.returncode else (0 if all(unchanged.values()) else 1),'unchanged':unchanged,'outer_command':command,
            'artifacts':inventory(helper,output/'bin'),'records':records,'podman_executed':False,'container_executed':False,'inherited_native_suites_executed':False,'held_probe_executed':False,'full_installation_acceptance':False}
    (output/'result.json').write_bytes(encoded(result))
    if result['exit_code']: raise ValueError('Owned environment build failed; evidence retained')
    return output/'result.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--execute-prepared',action='store_true');mode.add_argument('--child',action='store_true')
    parser.add_argument('--invocation-sha256');args=parser.parse_args()
    if args.prepare_only: print(prepare(args.output))
    elif not args.invocation_sha256: parser.error('Reviewed invocation hash required')
    elif args.child: raise SystemExit(child(args.output,args.invocation_sha256))
    else: print(execute(args.output,args.invocation_sha256))
