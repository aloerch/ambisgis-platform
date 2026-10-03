#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare an owned systemd socket-selection repair; execution is a separate step.

Never invokes the prior build recipe's child/main, Podman, rootlessport, a
container, inherited native suites, checkpoint tests, or a namespace helper.
Only the new standalone path-selection Go unit is executed after separate review.
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
PRIOR = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-env-build-002')
PINS = {
    PRIOR / 'build-executed.py': '4647ed2c7ed2698f916e304b8b2460348eaae8f61dcbb9f65603356008d74553',
    PRIOR / 'offline-executed.py': 'ed658e05bc1cde8b008835b146bf2be73487313f581ce66da31d5644b3766ace',
    PRIOR / 'result.json': '3bf0eabd2c2ea5a920561734d66c6a70abae2fbacb9acda8f5602c6ceb881a22',
    PRIOR / 'invocation.json': 'e386aa4a096a0c803729dc4a11ed01bd33314caf8ffd0cbb1aab8dfe78c27fa4',
    PRIOR / 'preparation.json': '6c35101d5395282a3fffa8a0e12643540db91d7de8d34bde9ad432a0adf703e0',
    PRIOR / 'toolchain.json': '88c9dfab2f03d59019b96d94ca119c5a3aa12cf8509c0da7547747123e19f60a',
    PRIOR / 'owned-source.patch': '33ba96feefb088be4c1095624ae5d58493eed66bbe3515dcbbdef1e2a4dcfae6',
    PRIOR / 'MODIFICATIONS.txt': '6f05204cf69cef94df454f92cd5334f5aedd8f8824642529a426c75c4c988095',
}
DBUS_SHA = 'ea49881232a753609ca6513a3697dde3f70716f8f26f06eee5cf40546da5c6bb'
TAGS = 'apparmor,seccomp,systemd,exclude_graphdriver_btrfs'
ASSIGNMENT = '\t\t\tpath := filepath.Join(os.Getenv("XDG_RUNTIME_DIR"), "systemd", "private")'
CALL = '\t\t\tpath := ambisgisSystemdUserSocket(os.Getenv("XDG_RUNTIME_DIR"), os.Getenv("AMBISGIS_SYSTEMD_USER_SOCKET"))'
HELPER = '''// SPDX-License-Identifier: Apache-2.0
// AmbisGIS modification, 2026-10-03: explicit owned user-manager socket selection.
package systemd

import "path/filepath"

// The owned launcher constructs and validates explicitSocket before Podman starts.
// This selector neither connects nor authenticates. Preserve the original
// XDG fallback for other callers and the native peer/authentication path.
func ambisgisSystemdUserSocket(runtimeDir, explicitSocket string) string {
	if explicitSocket != "" {
		return explicitSocket
	}
	return filepath.Join(runtimeDir, "systemd", "private")
}
'''
TEST = '''// SPDX-License-Identifier: Apache-2.0
package systemd

import "testing"

// Compile by these two exact files only: no package init/TestMain, D-Bus,
// socket, namespace, child process, engine or inherited native suite runs.
func TestAmbisGISSystemdUserSocket(t *testing.T) {
	for _, tc := range []struct {
		name string
		runtimeDir string
		explicitSocket string
		want string
	}{
		{"fallback_private", "/private/installation/runtime/run", "", "/private/installation/runtime/run/systemd/private"},
		{"fallback_empty", "", "", "systemd/private"},
		{"explicit_user", "/private/installation/runtime/run", "/run/user/1000/systemd/private", "/run/user/1000/systemd/private"},
		{"explicit_precedence", "/different/private/runtime", "/run/user/2048/systemd/private", "/run/user/2048/systemd/private"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got := ambisgisSystemdUserSocket(tc.runtimeDir, tc.explicitSocket)
			if got != tc.want { t.Errorf("socket got %q want %q", got, tc.want) }
		})
	}
}
'''
BASELINE_PASSES = ('fallback_private', 'fallback_empty')
BASELINE_FAILURES = ('explicit_user', 'explicit_precedence')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def encoded(value): return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def retained_predecessor():
    for path, identity in PINS.items():
        if any(p.is_symlink() for p in (path, *path.parents)) or sha(path) != identity:
            raise ValueError('Retained producer input changed')
    spec = importlib.util.spec_from_file_location('retained_podman_environment_build', PRIOR / 'build-executed.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def retained_helper():
    # Only inert inventory/toolchain/compiler-staging helpers are reused.
    # Never invoke any predecessor prepare, child, execute or main dispatcher.
    return retained_predecessor().retained_helper()


def prior_state():
    previous = retained_predecessor()
    helper, _, prior, _ = previous.verified_preparation(PRIOR, PINS[PRIOR/'invocation.json'])
    result = json.loads((PRIOR/'result.json').read_text())
    if result['exit_code'] or result['unchanged'] != {
            'source': True, 'prior_source': True, 'baseline': True, 'toolchain': True}:
        raise ValueError('Prior owned environment producer incomplete')
    for name, identity in result['records'].items():
        if Path(name).name != name or sha(helper.checked_path(PRIOR/name)) != identity:
            raise ValueError('Prior build record changed')
    if inventory(helper, PRIOR/'bin') != result['artifacts']:
        raise ValueError('Prior producer artifact closure changed')
    original = json.loads(previous.PREPARATION.read_text())
    prior['source_obsinfo'] = original['source_obsinfo']
    prior['existing_patches'] = [*prior['existing_patches'],
        {'file': str(PRIOR/'owned-source.patch'), 'sha256': PINS[PRIOR/'owned-source.patch']}]
    return helper, prior

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


def patch(source):
    path = source / 'pkg/systemd/dbus.go'
    if sha(path) != DBUS_SHA: raise ValueError('Exact retained systemd source required')
    original = path.read_text()
    if original.count(ASSIGNMENT) != 1: raise ValueError('Rootless socket selection changed')
    for name in ('ambisgis_user_socket.go', 'ambisgis_user_socket_test.go'):
        if (source/'pkg/systemd'/name).exists(): raise ValueError('Repair already present')
    changed = original.replace(ASSIGNMENT, CALL)
    if changed.replace(CALL, ASSIGNMENT) != original:
        raise ValueError('Unselected native connection source changed')
    path.write_text(changed)
    (source/'pkg/systemd/ambisgis_user_socket.go').write_text(HELPER)
    (source/'pkg/systemd/ambisgis_user_socket_test.go').write_text(TEST)
    delta = ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
        fromfile='a/pkg/systemd/dbus.go', tofile='b/pkg/systemd/dbus.go'))
    for name, text in [('ambisgis_user_socket.go', HELPER), ('ambisgis_user_socket_test.go', TEST)]:
        delta += ''.join(difflib.unified_diff([], text.splitlines(True),
            fromfile='/dev/null', tofile='b/pkg/systemd/'+name))
    # Faithfully extract the original assignment; inject only its getenv input.
    baseline = ('// SPDX-License-Identifier: Apache-2.0\npackage systemd\nimport "path/filepath"\n'
        'func ambisgisSystemdUserSocket(runtimeDir, _ string) string {\n'
        + ASSIGNMENT.replace('os.Getenv("XDG_RUNTIME_DIR")', 'runtimeDir').lstrip('\t')
        + '\n\treturn path\n}\n')
    selection = {'file': 'pkg/systemd/dbus.go', 'before_sha256': DBUS_SHA,
        'after_sha256': sha(path), 'one_path_assignment_changed': True,
        'evalsymlinks_dial_auth_and_rootful_unchanged': True}
    return delta, baseline, selection


def unit_result(text, baseline):
    cases = (*BASELINE_PASSES, *BASELINE_FAILURES)
    for case in cases:
        status = 'FAIL' if baseline and case in BASELINE_FAILURES else 'PASS'
        if text.count('=== RUN   TestAmbisGISSystemdUserSocket/'+case+'\n') != 1:
            return False
        if ('--- '+status+': TestAmbisGISSystemdUserSocket/'+case+' (') not in text:
            return False
    return text.endswith(('FAIL' if baseline else 'PASS')+'\n')

def command_plan(output):
    go = str(output / 'toolchain/usr/lib64/go/1.27/bin/go')
    common = ['-x', '-p=2', '-mod=vendor', '-buildvcs=false', '-trimpath']
    unit = ['-test.run=^TestAmbisGISSystemdUserSocket$', '-test.count=1', '-test.v']
    return [
        ('baseline-compile', [go, 'test', '-c', *common, '-o', str(output/'bin/baseline.test'), str(output/'baseline/socket.go'), str(output/'baseline/socket_test.go')], 0),
        ('baseline-unit', [str(output/'bin/baseline.test'), *unit], 1),
        ('socket-compile', [go, 'test', '-c', *common, '-o', str(output/'bin/socket.test'), 'pkg/systemd/ambisgis_user_socket.go', 'pkg/systemd/ambisgis_user_socket_test.go'], 0),
        ('socket-unit', [str(output/'bin/socket.test'), *unit], 0),
        ('podman-build', [go, 'build', *common, '-tags', TAGS, '-o', str(output/'bin/podman'), './cmd/podman'], 0),
        ('rootlessport-build', [go, 'build', *common, '-tags', TAGS, '-o', str(output/'bin/rootlessport'), './cmd/rootlessport'], 0),
    ]


def prepare(output):
    helper, prior = prior_state(); output = helper.checked_path(output, new=True)
    old = inventory(helper, PRIOR/'source')
    if old != prior['patched']: raise ValueError('Prior complete source differs')
    for row in [prior['source_archive'], prior['source_obsinfo'], *prior['existing_patches']]:
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
    delta, baseline, selection = patch(output/'source')
    (output/'owned-source.patch').write_text(delta)
    (output/'baseline/socket.go').write_text(baseline)
    (output/'baseline/socket_test.go').write_text(TEST)
    source = inventory(helper, output/'source')
    if [p for p in old if old[p] != source[p]] != ['pkg/systemd/dbus.go']:
        raise ValueError('Repair modified unselected source')
    if set(source)-set(old) != {'pkg/systemd/ambisgis_user_socket.go','pkg/systemd/ambisgis_user_socket_test.go'}:
        raise ValueError('Unexpected added source')
    staged = helper.stage_toolchain(payload, output/'toolchain')
    if staged != json.loads((PRIOR/'toolchain.json').read_text()):
        raise ValueError('Retained toolchain manifest differs from predecessor')
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
    prep={'prior_source':old,'patched':source,'selection':selection,'baseline':inventory(helper,output/'baseline'),
          'vendor_unchanged':all(source[n]==v for n,v in old.items() if n.startswith('vendor/')),
          'existing_patches':prior['existing_patches'],'source_archive':prior['source_archive'],'source_obsinfo':prior['source_obsinfo'],'source_commit':prior['source_commit'],
          'new_patch_sha256':sha(output/'owned-source.patch'),'retained_toolchain_sources':source_rows}
    (output/'preparation.json').write_bytes(encoded(prep)); (output/'toolchain.json').write_bytes(encoded(staged))
    (output/'MODIFICATIONS.txt').write_text('AmbisGIS modification, 2026-10-03.\nPodman source '+prior['source_commit']+' and all four previously retained repairs are preserved.\nOnly the rootless systemd private-socket path selection uses the explicit owned launcher value when nonempty.\nThe original XDG fallback, EvalSymlinks, Dial, native AuthExternal rootless UID, and rootful connection remain unchanged.\nThe owned launcher validates the exact existing user-manager socket; this selector does not connect or change host policy.\nThe original Apache-2.0 LICENSE and all vendor source/notices remain in the complete source tree.\nNo source revision is invented or overridden. Exact source/patch/build hashes identify this derived build.\n')
    invocation={'schema_version':1,'recipe_sha256':sha(Path(__file__)),'inputs':[{'path':str(p),'sha256':s} for p,s in PINS.items()],
        'host_compiler_support':host,'build_environment':env,'commands':command_plan(output),'preparation_sha256':sha(output/'preparation.json'),
        'toolchain_sha256':sha(output/'toolchain.json'),'compiler_commands':helper.inventory(commands),
        'modifications_sha256':sha(output/'MODIFICATIONS.txt'),
        'supervisor':{'path':sys.executable,'sha256':sha(sys.executable)},
        'scope':'Only standalone socket-path selector and its four pure subcases; no systemd package init/TestMain, prior native suites, engine, namespace or held probe. Offline compiler uses retained inputs; host bootstrap remains explicit.'}
    (output/'invocation.json').write_bytes(encoded(invocation))
    shutil.copyfile(Path(__file__),output/'build-executed.py');shutil.copyfile(PRIOR/'offline-executed.py',output/'offline-executed.py')
    return output/'invocation.json'


def verified_preparation(output, identity):
    helper,_=prior_state(); output=helper.checked_path(output)
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
    for row in [p['source_archive'],p['source_obsinfo'],*p['existing_patches']]:
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
        if name in ('baseline-unit', 'socket-unit'):
            passed = passed and unit_result(log.read_text(), baseline=name=='baseline-unit')
        rows.append({'name':name,'command':command,'expected_exit':expected,'exit_code':run.returncode,'passed':passed,'log':str(log),'log_sha256':sha(log)})
        if not passed: code=1;break
    (output/'commands.json').write_bytes(encoded({'commands':rows,'exit_code':code,'scope':v['scope']}))
    return code


def execute(output, identity):
    helper,v,p,t=verified_preparation(output,identity)
    if any((output/n).exists() for n in ('network.json','commands.json','result.json')): raise ValueError('Execution output already exists')
    if any(list((output/name).iterdir()) for name in ('bin','home','cache','modcache','gopath','tmp')):
        raise ValueError('Fresh execution directories required')
    command=[sys.executable,'-B',str(output/'offline-executed.py'),'--evidence',str(output/'network.json'),'--',sys.executable,'-B',str(output/'build-executed.py'),'--child','--output',str(output),'--invocation-sha256',identity]
    run=subprocess.run(command,cwd=output,env={'HOME':str(output/'home'),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'})
    unchanged={'source':inventory(helper,output/'source')==p['patched'],'prior_source':inventory(helper,PRIOR/'source')==p['prior_source'],
               'baseline':inventory(helper,output/'baseline')==p['baseline'],'toolchain':inventory(helper,output/'toolchain',retained_toolchain=True)==t['inventory']}
    records={n:sha(output/n) for n in ('invocation.json','preparation.json','toolchain.json','owned-source.patch','MODIFICATIONS.txt','commands.json','network.json') if (output/n).is_file()}
    result={'schema_version':1,'exit_code':run.returncode if run.returncode else (0 if all(unchanged.values()) else 1),'unchanged':unchanged,'outer_command':command,
            'artifacts':inventory(helper,output/'bin'),'records':records,'podman_executed':False,'container_executed':False,'inherited_native_suites_executed':False,'held_probe_executed':False,'full_installation_acceptance':False}
    (output/'result.json').write_bytes(encoded(result))
    if result['exit_code']: raise ValueError('Owned user-manager socket build failed; evidence retained')
    return output/'result.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--execute-prepared',action='store_true');mode.add_argument('--child',action='store_true')
    parser.add_argument('--invocation-sha256');args=parser.parse_args()
    if args.prepare_only: print(prepare(args.output))
    elif not args.invocation_sha256: parser.error('Reviewed invocation hash required')
    elif args.child: raise SystemExit(child(args.output,args.invocation_sha256))
    else: print(execute(args.output,args.invocation_sha256))
