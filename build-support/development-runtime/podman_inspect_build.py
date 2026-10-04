#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare faithful owned inspect sysctls; execution is a separate step.

Never invokes the prior build recipe's child/main, Podman, rootlessport, a
container, inherited native suites, checkpoint tests, or a namespace helper.
Only the new standalone projection/source-contract Go unit is executed after separate review.
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
PRIOR = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-health-timer-build-001')
PINS = {
    PRIOR / 'build-executed.py': 'a0f513009df3356e360f59521b29f790c5273aeb5049d9c6f346b2369653741d',
    PRIOR / 'offline-executed.py': 'ed658e05bc1cde8b008835b146bf2be73487313f581ce66da31d5644b3766ace',
    PRIOR / 'result.json': '8123fb4804541ce686918e4984fd00e6c4adb46240e7a31a5ed2720fca99f343',
    PRIOR / 'invocation.json': '286b69204edd418d2defb008cc60ba4a3026c2589708bdb5ba893989a036f8ea',
    PRIOR / 'preparation.json': '23550906b7ee3d58252c201c2c824c18c1b1cc1d207f3f64516351b0f73f64cf',
    PRIOR / 'toolchain.json': '88c9dfab2f03d59019b96d94ca119c5a3aa12cf8509c0da7547747123e19f60a',
    PRIOR / 'owned-source.patch': 'f3b15a9d64ffb19acee386cfcdfb2add717993305867d0ce6c0635c4fcd2d677',
    PRIOR / 'MODIFICATIONS.txt': 'ecc8e57ccad52420cdc212293a96023c313294928c8d489a4301c9e3247efbcd',
}
SOURCE_HASHES = {'libpod/container_inspect.go': 'ed36322c3628096e7fb8c16d25a60c2d176ff2e655927cbe9995b52872ff2322', 'libpod/define/container_inspect.go': '1e19c3800b77d16cb5c2a72f7e401ba2f0992a26179a173105ff2fb475153b1b'}
ANCHORS = {'libpod/container_inspect.go': '\thostConfig := new(define.InspectContainerHostConfig)\n', 'libpod/define/container_inspect.go': 'type InspectContainerHostConfig struct {\n'}
ADDITIONS = {'libpod/container_inspect.go': '\thostConfig.Sysctls = ambisgisInspectSysctls(ctrSpec)\n', 'libpod/define/container_inspect.go': '\t// Sysctls faithfully reports the spec selected by native inspection.\n\tSysctls map[string]string `json:"Sysctls"`\n'}
TAGS = 'apparmor,seccomp,systemd,exclude_graphdriver_btrfs'
HELPER = '// SPDX-License-Identifier: Apache-2.0\npackage libpod\n\nimport (\n    "maps"\n    spec "github.com/opencontainers/runtime-spec/specs-go"\n)\n\n// ambisgisInspectSysctls projects the spec selected by native inspection.\n// Configured containers use persisted intent; initialized containers use the\n// native realized spec selection. Never invent defaults or modify the source.\nfunc ambisgisInspectSysctls(value *spec.Spec) map[string]string {\n    if value == nil || value.Linux == nil { return nil }\n    return maps.Clone(value.Linux.Sysctl)\n}\n'
TEST = '// SPDX-License-Identifier: Apache-2.0\npackage libpod\n\nimport (\n    "go/ast"\n    "go/parser"\n    "go/token"\n    "reflect"\n    "strconv"\n    "testing"\n    spec "github.com/opencontainers/runtime-spec/specs-go"\n)\n\nfunc TestAmbisGISInspectSysctls(t *testing.T) {\n    t.Run("nil_spec",func(t *testing.T){if ambisgisInspectSysctls(nil)!=nil {t.Fatal("nil changed")}})\n    t.Run("nil_linux",func(t *testing.T){if ambisgisInspectSysctls(&spec.Spec{})!=nil {t.Fatal("nil changed")}})\n    t.Run("nil_map",func(t *testing.T){if ambisgisInspectSysctls(&spec.Spec{Linux:&spec.Linux{}})!=nil {t.Fatal("nil changed")}})\n    t.Run("empty_map",func(t *testing.T){v:=ambisgisInspectSysctls(&spec.Spec{Linux:&spec.Linux{Sysctl:map[string]string{}}});if v==nil||len(v)!=0 {t.Fatal("empty changed")}})\n    t.Run("faithful_values",func(t *testing.T){\n        values:=map[string]string{"net.ipv6.conf.all.disable_ipv6":"1","net.ipv6.conf.default.disable_ipv6":"0","unrecognized.key":"literal"}\n        if !reflect.DeepEqual(ambisgisInspectSysctls(&spec.Spec{Linux:&spec.Linux{Sysctl:values}}),values){t.Fatal("values normalized or omitted")}\n    })\n    t.Run("independent_copy",func(t *testing.T){\n        values:=map[string]string{"key":"original"};v:=ambisgisInspectSysctls(&spec.Spec{Linux:&spec.Linux{Sysctl:values}})\n        v["key"]="returned";v["added"]="new";if len(values)!=1||values["key"]!="original"{t.Fatal("source mutated")}\n        values["key"]="source";if v["key"]!="returned"{t.Fatal("result aliases source")}\n    })\n    t.Run("actual_wire_field",func(t *testing.T){\n        file,e:=parser.ParseFile(token.NewFileSet(),"libpod/define/container_inspect.go",nil,0);if e!=nil{t.Fatal(e)}\n        count:=0\n        ast.Inspect(file,func(n ast.Node)bool{\n            decl,ok:=n.(*ast.TypeSpec);if !ok||decl.Name.Name!="InspectContainerHostConfig"{return true}\n            fields,ok:=decl.Type.(*ast.StructType);if !ok{t.Fatal("wrong host type")}\n            for _,field:=range fields.Fields.List{for _,name:=range field.Names{if name.Name=="Sysctls"{\n                count++;m,ok:=field.Type.(*ast.MapType);if !ok{t.Fatal("not map")}\n                key,k:=m.Key.(*ast.Ident);value,v:=m.Value.(*ast.Ident);if !k||!v||key.Name!="string"||value.Name!="string"{t.Fatal("wrong map")}\n                if field.Tag==nil{t.Fatal("missing tag")};tag,e:=strconv.Unquote(field.Tag.Value);if e!=nil||tag!=`json:"Sysctls"`{t.Fatal("wire field changed")}\n            }}};return false\n        });if count!=1{t.Fatal("missing or duplicate field")}\n    })\n    t.Run("actual_generator_call",func(t *testing.T){\n        file,e:=parser.ParseFile(token.NewFileSet(),"libpod/container_inspect.go",nil,0);if e!=nil{t.Fatal(e)};count:=0\n        for _,decl:=range file.Decls{fn,ok:=decl.(*ast.FuncDecl);if !ok||fn.Name.Name!="generateInspectContainerHostConfig"{continue}\n            ast.Inspect(fn.Body,func(n ast.Node)bool{a,ok:=n.(*ast.AssignStmt);if !ok||len(a.Lhs)!=1||len(a.Rhs)!=1{return true}\n                l,ok:=a.Lhs[0].(*ast.SelectorExpr);if !ok||l.Sel.Name!="Sysctls"{return true};count++\n                object,ok:=l.X.(*ast.Ident);if !ok||object.Name!="hostConfig"{t.Fatal("wrong destination")}\n                call,ok:=a.Rhs[0].(*ast.CallExpr);if !ok||len(call.Args)!=1{t.Fatal("wrong call")}\n                f,ok:=call.Fun.(*ast.Ident);if !ok||f.Name!="ambisgisInspectSysctls"{t.Fatal("wrong helper")}\n                arg,ok:=call.Args[0].(*ast.Ident);if !ok||arg.Name!="ctrSpec"{t.Fatal("wrong spec")};return true\n            })\n        };if count!=1{t.Fatal("missing or duplicate projection")}\n    })\n}\n'
CASES = ('nil_spec', 'nil_linux', 'nil_map', 'empty_map', 'faithful_values', 'independent_copy', 'actual_wire_field', 'actual_generator_call')


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
        raise ValueError('Prior owned health-timer producer incomplete')
    for name, identity in result['records'].items():
        if Path(name).name != name or sha(helper.checked_path(PRIOR/name)) != identity:
            raise ValueError('Prior build record changed')
    if inventory(helper, PRIOR/'bin') != result['artifacts']:
        raise ValueError('Prior producer artifact closure changed')
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


def source_contract(source):
    for name, identity in SOURCE_HASHES.items():
        text = (source/name).read_text()
        if text.count(ANCHORS[name]+ADDITIONS[name]) != 1:
            raise AssertionError('Faithful inspect projection is absent or changed')
        if hashlib.sha256(text.replace(ADDITIONS[name], '', 1).encode()).hexdigest() != identity:
            raise AssertionError('Unselected native source changed')
    for name, data in (('ambisgis_inspect_sysctls.go', HELPER), ('ambisgis_inspect_sysctls_test.go', TEST)):
        if (source/'libpod'/name).read_text() != data:
            raise AssertionError('Projection helper or tests changed')


def patch(source):
    originals = {}
    for name, identity in SOURCE_HASHES.items():
        path = source/name
        if sha(path) != identity: raise ValueError('Exact retained inspect source required')
        originals[name] = path.read_text()
        if originals[name].count(ANCHORS[name]) != 1: raise ValueError('Native inspect anchor changed')
    names = ('ambisgis_inspect_sysctls.go', 'ambisgis_inspect_sysctls_test.go')
    if any((source/'libpod'/name).exists() for name in names): raise ValueError('Repair already present')
    delta = ''
    selection = []
    for name, original in originals.items():
        changed = original.replace(ANCHORS[name], ANCHORS[name]+ADDITIONS[name])
        (source/name).write_text(changed)
        delta += ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
        selection.append({'file':name, 'before_sha256':SOURCE_HASHES[name], 'after_sha256':sha(source/name)})
    for name, data in zip(names, (HELPER, TEST)):
        (source/'libpod'/name).write_text(data)
        delta += ''.join(difflib.unified_diff([], data.splitlines(True), fromfile='/dev/null', tofile='b/libpod/'+name))
    source_contract(source)
    return delta, originals, selection


def unit_result(text):
    name = 'TestAmbisGISInspectSysctls'
    runs = [line.removeprefix('=== RUN   ') for line in text.splitlines() if line.startswith('=== RUN   ')]
    if runs != [name, *[name+'/'+case for case in CASES]]: return False
    for case in CASES:
        if text.count('--- PASS: '+name+'/'+case+' (') != 1: return False
    return text.endswith('PASS\n') and '--- FAIL:' not in text and text.count('--- PASS: '+name+' (') == 1


def command_plan(output):
    go=str(output/'toolchain/usr/lib64/go/1.27/bin/go')
    common=['-x','-p=2','-mod=vendor','-buildvcs=false','-trimpath']
    return [
        ('inspect-compile',[go,'test','-c',*common,'-o',str(output/'bin/inspect.test'),'libpod/ambisgis_inspect_sysctls.go','libpod/ambisgis_inspect_sysctls_test.go'],0),
        ('inspect-unit',[str(output/'bin/inspect.test'),'-test.run=^TestAmbisGISInspectSysctls$','-test.count=1','-test.v'],0),
        ('podman-build',[go,'build',*common,'-tags',TAGS,'-o',str(output/'bin/podman'),'./cmd/podman'],0),
        ('rootlessport-build',[go,'build',*common,'-tags',TAGS,'-o',str(output/'bin/rootlessport'),'./cmd/rootlessport'],0),
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
    for name, text in baseline.items():
        path = output/'baseline'/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    source = inventory(helper, output/'source')
    if set(old)-set(source) or {p for p in old if old[p] != source[p]} != set(SOURCE_HASHES):
        raise ValueError('Repair modified unselected source')
    if set(source)-set(old) != {'libpod/ambisgis_inspect_sysctls.go','libpod/ambisgis_inspect_sysctls_test.go'}:
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
    (output/'MODIFICATIONS.txt').write_text('AmbisGIS modification, 2026-10-04.\nPodman source '+prior['source_commit']+' and all six previously retained repairs are preserved.\nOnly additive HostConfig.Sysctls projects an independent copy of the native selected OCI spec map, preserving nil/empty and every key/value. Configured-state intent is distinct from realized OCI security. No defaults, mutation, command, privilege or lifecycle behavior is introduced.\nOriginal Apache-2.0 LICENSE and all vendor source/notices remain unchanged. No invented revision override or new dependency. Exact patch/source/build hashes identify this derived build.\n')
    invocation={'schema_version':1,'recipe_sha256':sha(Path(__file__)),'inputs':[{'path':str(p),'sha256':s} for p,s in PINS.items()],
        'host_compiler_support':host,'build_environment':env,'commands':command_plan(output),'preparation_sha256':sha(output/'preparation.json'),
        'toolchain_sha256':sha(output/'toolchain.json'),'compiler_commands':helper.inventory(commands),
        'modifications_sha256':sha(output/'MODIFICATIONS.txt'),
        'supervisor':{'path':sys.executable,'sha256':sha(sys.executable)},
        'scope':'Only standalone pure inspect projection and exact source AST guards; no libpod package init/TestMain, D-Bus connection, prior native suites, engine, namespace or held probe. Offline compiler uses retained inputs; host bootstrap remains explicit.'}
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
    source_contract(output/'source')
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
        if name == 'inspect-unit':
            passed = passed and unit_result(log.read_text())
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
    if result['exit_code']: raise ValueError('Owned inspect projection build failed; evidence retained')
    return output/'result.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--execute-prepared',action='store_true');mode.add_argument('--child',action='store_true')
    parser.add_argument('--invocation-sha256');args=parser.parse_args()
    if args.prepare_only: print(prepare(args.output))
    elif not args.invocation_sha256: parser.error('Reviewed invocation hash required')
    elif args.child: raise SystemExit(child(args.output,args.invocation_sha256))
    else: print(execute(args.output,args.invocation_sha256))
