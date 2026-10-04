#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare a finite owned health-timer repair; execution is a separate step.

Never invokes the prior build recipe's child/main, Podman, rootlessport, a
container, inherited native suites, checkpoint tests, or a namespace helper.
Only the new standalone finite-plan/job-order Go unit is executed after separate review.
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
PRIOR = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-systemd-build-001')
PINS = {
    PRIOR / 'build-executed.py': '6535869b1ad0392fb155242f1d84eb583b3f5ad7a30e1c5093b9f1a767a9e5a0',
    PRIOR / 'offline-executed.py': 'ed658e05bc1cde8b008835b146bf2be73487313f581ce66da31d5644b3766ace',
    PRIOR / 'result.json': '81693d5bb1915127a68ed38901d6e934d1dd55c376e4fd42dffb5e09316695e7',
    PRIOR / 'invocation.json': '7746b7db7625d29f25eb5c001a44c5e0321c3305fae96d307d92a58d3d3c0d1f',
    PRIOR / 'preparation.json': '29df4a295c6496fb6a5c8402f7572631cedef1a0d0678a997ea9b39f1b48caba',
    PRIOR / 'toolchain.json': '88c9dfab2f03d59019b96d94ca119c5a3aa12cf8509c0da7547747123e19f60a',
    PRIOR / 'owned-source.patch': 'fdd938036b1e51d220cffe325a893b6d26775f06fd790453abdfe5739af48d23',
    PRIOR / 'MODIFICATIONS.txt': 'b2840e8188584403d242d7e4f3be46760020c6ea0a75a17453733a157dc39349',
    Path('/home/revelberry/Projects/AmbisGIS/source-archives/plt01-container/obs-source/systemd-0092d42418b02d521cc36341d1a6c3b2/systemd-261.2.tar.xz'): 'cc84192fe4c7bc1373df650e6cbb81109d4fff268f9afac12edd3856fde95fef',
}
SOURCE_SHA = 'c5589a69705c903daaaea53c61cdd758adc9ed08a0296e9124f6f2d5f446a71b'
TAGS = 'apparmor,seccomp,systemd,exclude_graphdriver_btrfs'
ANCHOR = '\tcmd := []string{"--property", "LogLevelMax=notice"}'
BRANCH = '\tplan, err := ambisgisHealthTimerPlan(os.Getenv("AMBISGIS_HEALTH_TIMER_PROFILE"), rootless.IsRootless(), podman, os.Getenv("PATH"), c.runtime.storageConfig.GraphRoot, hcUnitName, c.ID(), interval, isStartup, specgenutil.GlobalPodmanArgs(c.runtime.storageConfig, c.runtime.config, logrus.IsLevelEnabled(logrus.DebugLevel)))\n\tif err != nil {\n\t\treturn err\n\t}\n\tif plan != nil {\n\t\tconn, err := systemd.ConnectToDBUS()\n\t\tif err != nil {\n\t\t\treturn fmt.Errorf("unable to get systemd connection to add owned healthchecks: %w", err)\n\t\t}\n\t\tdefer conn.Close()\n\t\tctx, cancel := context.WithTimeout(context.Background(), ambisgisHealthTimerTimeout)\n\t\tdefer cancel()\n\t\treturn ambisgisCommitHealthTimer(ctx, plan, func(ctx context.Context, job chan<- string) error {\n\t\t\t_, err := conn.StartTransientUnitAux(ctx, plan.UnitName+".timer", "fail", plan.Timer, plan.Aux, job)\n\t\t\treturn err\n\t\t}, func(unitName string) error {\n\t\t\tc.state.HCUnitName = unitName\n\t\t\treturn c.save()\n\t\t})\n\t}\n\n'
HELPER = '// SPDX-License-Identifier: Apache-2.0\n// AmbisGIS modification, 2026-10-04: finite owned development health timer.\npackage libpod\n\nimport (\n\t"context"\n\t"time"\n\t"errors"\n\t"fmt"\n\t"path/filepath"\n\t"reflect"\n\t"regexp"\n\t"strings"\n\n\t"github.com/coreos/go-systemd/v22/dbus"\n\tgodbus "github.com/godbus/dbus/v5"\n)\n\nconst ambisgisHealthTimerTimeout = 30 * time.Second\n\ntype ambisgisMonotonicTimer struct {\n\tBase string\n\tUsec uint64\n}\n\ntype ambisgisHealthTimer struct {\n\tUnitName string\n\tTimer []dbus.Property\n\tAux []dbus.PropertyCollection\n}\n\n// These inputs come from the already verified owned launcher and native engine\n// configuration, never a public unit/property API. An empty marker preserves\n// native behavior. A selected but unsupported profile must not fall back.\nfunc ambisgisHealthTimerPlan(profile string, rootless bool, executable, envPath, graphRoot, unitName, cid, interval string, startup bool, global []string) (*ambisgisHealthTimer, error) {\n\tif profile == "" { return nil, nil }\n\tif profile != "development-v1" || !rootless || startup || interval != "15s" {\n\t\treturn nil, errors.New("unsupported owned health timer profile")\n\t}\n\tvalidPath := regexp.MustCompile(`^/[A-Za-z0-9_./-]+$`)\n\tfor _, path := range []string{executable, graphRoot} {\n\t\tif !validPath.MatchString(path) || filepath.Clean(path) != path {\n\t\t\treturn nil, errors.New("unsupported owned health timer path")\n\t\t}\n\t}\n\tbundleRoot := filepath.Dir(filepath.Dir(filepath.Dir(executable)))\n\troot := filepath.Dir(filepath.Dir(graphRoot))\n\tif bundleRoot == "/" || root == "/" || executable != filepath.Join(bundleRoot, "runtime/engine/podman") || graphRoot != filepath.Join(root, "runtime/storage") {\n\t\treturn nil, errors.New("owned health timer layout differs")\n\t}\n\tpath := filepath.Join(bundleRoot, "runtime/bin") + ":" + filepath.Join(bundleRoot, "runtime/helpers")\n\tif envPath != path { return nil, errors.New("owned health timer PATH differs") }\n\tif !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(cid) || !regexp.MustCompile(`^`+regexp.QuoteMeta(cid)+`-[a-f0-9]+$`).MatchString(unitName) {\n\t\treturn nil, errors.New("owned health timer identity differs")\n\t}\n\texpected := []string{\n\t\t"--root", graphRoot, "--runroot", filepath.Join(root,"runtime/run"),\n\t\t"--log-level", "warning", "--cgroup-manager", "systemd",\n\t\t"--tmpdir", filepath.Join(root,"runtime/tmp"), "--network-config-dir", filepath.Join(root,"runtime/networks"),\n\t\t"--volumepath", filepath.Join(root,"runtime/storage/volumes"), "--transient-store=false",\n\t\t"--hooks-dir", filepath.Join(root,"runtime/hooks"), "--runtime", "runc",\n\t\t"--storage-driver", "vfs", "--events-backend", "file",\n\t}\n\tif !reflect.DeepEqual(global, expected) { return nil, errors.New("owned health timer native arguments differ") }\n\tcommand := append([]string{filepath.Join(bundleRoot,"runtime/bin/healthcheck-timer")}, global...)\n\tcommand = append(command, "healthcheck", "run", "--ignore-result", cid)\n\t// Retained systemd261.2 quote_command_line leaves this restricted nonempty\n\t// alphabet unchanged. Paths with spaces, escapes, expansions, percent or\n\t// control bytes are unsupported in this profile, not silently normalized.\n\tdescription := "[systemd-run] " + strings.Join(command, " ")\n\tproperty := func(name string, value any) dbus.Property { return dbus.Property{Name:name, Value:godbus.MakeVariant(value)} }\n\treturn &ambisgisHealthTimer{\n\t\tUnitName:unitName,\n\t\tTimer:[]dbus.Property{\n\t\t\tdbus.PropDescription(description),\n\t\t\tproperty("TimersMonotonic", []ambisgisMonotonicTimer{{"OnUnitInactiveSec",15000000}}),\n\t\t\tproperty("AccuracyUSec",uint64(1000000)), property("RemainAfterElapse",false),\n\t\t},\n\t\tAux:[]dbus.PropertyCollection{{Name:unitName+".service", Properties:[]dbus.Property{\n\t\t\tdbus.PropDescription(description), property("LogLevelMax",int32(5)),\n\t\t\tproperty("StartLimitIntervalUSec",uint64(0)), property("WorkingDirectory",root),\n\t\t\tproperty("Environment",[]string{"PATH="+path}), dbus.PropExecStart(command,false),\n\t\t}}},\n\t}, nil\n}\n\n// Injected functions make completion/state ordering testable without connecting\n// to systemd. The production start function uses the already verified native\n// private connection and one StartTransientUnitAux(..., "fail", ...).\nfunc ambisgisCommitHealthTimer(ctx context.Context, plan *ambisgisHealthTimer, start func(context.Context, chan<- string) error, save func(string) error) error {\n\tif plan == nil || ctx == nil { return errors.New("missing owned health timer plan/context") }\n\tif err := ctx.Err(); err != nil { return fmt.Errorf("owned health timer %s not submitted: %w",plan.UnitName,err) }\n\tjob := make(chan string,1)\n\tuncertain := func(err error) error { return fmt.Errorf("owned health timer %s creation/persistence uncertain; reconcile exact timer and service before retry: %w",plan.UnitName,err) }\n\t// A failed call can mean a lost reply after creation or a pre-existing\n\t// mode=fail collision. Never remove a unit whose ownership is unestablished.\n\tif err := start(ctx,job); err != nil { return uncertain(err) }\n\tselect {\n\tcase result := <-job:\n\t\tif result != "done" { return uncertain(fmt.Errorf("expected job done but received %q",result)) }\n\tcase <-ctx.Done():\n\t\treturn uncertain(ctx.Err())\n\t}\n\tif err := ctx.Err(); err != nil { return uncertain(err) }\n\tif err := save(plan.UnitName); err != nil { return uncertain(err) }\n\treturn nil\n}\n'
TEST = '// SPDX-License-Identifier: Apache-2.0\npackage libpod\n\nimport (\n\t"context"\n\t"errors"\n\t"reflect"\n\t"strings"\n\t"testing"\n\n\t"github.com/coreos/go-systemd/v22/dbus"\n)\n\n// This test is compiled by exactly this file plus the pure helper. No libpod\n// package init/TestMain, connection, engine, process or namespace is executed.\nfunc TestAmbisGISHealthTimer(t *testing.T) {\n\tcid := strings.Repeat("a",64)\n\tglobal := []string{"--root","/installation/runtime/storage","--runroot","/installation/runtime/run","--log-level","warning","--cgroup-manager","systemd","--tmpdir","/installation/runtime/tmp","--network-config-dir","/installation/runtime/networks","--volumepath","/installation/runtime/storage/volumes","--transient-store=false","--hooks-dir","/installation/runtime/hooks","--runtime","runc","--storage-driver","vfs","--events-backend","file"}\n\tbuild := func(profile string, rootless bool, executable, path, graph, unit, id, interval string, startup bool, args []string) (*ambisgisHealthTimer,error) { return ambisgisHealthTimerPlan(profile,rootless,executable,path,graph,unit,id,interval,startup,args) }\n\tvalid := func() *ambisgisHealthTimer {\n\t\tp,e := build("development-v1",true,"/bundle/runtime/engine/podman","/bundle/runtime/bin:/bundle/runtime/helpers","/installation/runtime/storage",cid+"-123",cid,"15s",false,global)\n\t\tif e != nil || p == nil { t.Fatalf("valid plan: %v",e) };return p\n\t}\n\tt.Run("native_unselected",func(t *testing.T) {\n\t\tp,e:=build("",false,"invalid","invalid","invalid","","","0",true,nil)\n\t\tif p!=nil || e!=nil { t.Fatal("empty marker altered native behavior") }\n\t})\n\tt.Run("wire_properties",func(t *testing.T) {\n\t\tp:=valid()\n\t\tif p.UnitName!=cid+"-123" || len(p.Aux)!=1 || p.Aux[0].Name!=cid+"-123.service" { t.Fatal("unit identity") }\n\t\tcheck:=func(props []dbus.Property,names,sigs []string) {\n\t\t\tif len(props)!=len(names) { t.Fatal("property membership") }\n\t\t\tfor i,row:=range props { if row.Name!=names[i] || row.Value.Signature().String()!=sigs[i] { t.Fatalf("property %s signature %s",row.Name,row.Value.Signature()) } }\n\t\t}\n\t\tcheck(p.Timer,[]string{"Description","TimersMonotonic","AccuracyUSec","RemainAfterElapse"},[]string{"s","a(st)","t","b"})\n\t\tcheck(p.Aux[0].Properties,[]string{"Description","LogLevelMax","StartLimitIntervalUSec","WorkingDirectory","Environment","ExecStart"},[]string{"s","i","t","s","as","a(sasb)"})\n\t\tmon:=reflect.ValueOf(p.Timer[1].Value.Value());if mon.Len()!=1 || mon.Index(0).Field(0).String()!="OnUnitInactiveSec" || mon.Index(0).Field(1).Uint()!=15000000 { t.Fatal("interval") }\n\t\tif p.Timer[2].Value.Value()!=uint64(1000000) || p.Timer[3].Value.Value()!=false {t.Fatal("timer defaults")}\n\t\ts:=p.Aux[0].Properties\n\t\tif s[1].Value.Value()!=int32(5) || s[2].Value.Value()!=uint64(0) || s[3].Value.Value()!="/installation" || !reflect.DeepEqual(s[4].Value.Value(),[]string{"PATH=/bundle/runtime/bin:/bundle/runtime/helpers"}) {t.Fatal("service properties")}\n\t\texec:=reflect.ValueOf(s[5].Value.Value());if exec.Len()!=1 || exec.Index(0).Field(0).String()!="/bundle/runtime/bin/healthcheck-timer" || exec.Index(0).Field(2).Bool() {t.Fatal("exec identity or ignore-error bit")}\n\t\targv:=exec.Index(0).Field(1).Interface().([]string)\n\t\twant:=append([]string{"/bundle/runtime/bin/healthcheck-timer"},global...);want=append(want,"healthcheck","run","--ignore-result",cid)\n\t\tif !reflect.DeepEqual(argv,want) {t.Fatal("exec arguments")}\n\t\tdescription:="[systemd-run] "+strings.Join(want," ")\n\t\tif p.Timer[0].Value.Value()!=description || s[0].Value.Value()!=description {t.Fatal("native finite description")}\n\t})\n\tt.Run("reject_profile_and_paths",func(t *testing.T) {\n\t\tfor _,bad:=range []string{"profile","rootful","startup","interval","executable","path","graph","unit","cid","traversal","spaces","percent","dollar","colon","newline"} {\n\t\t\tprofile:="development-v1";rootless:=true;startup:=false;interval:="15s";executable:="/bundle/runtime/engine/podman";path:="/bundle/runtime/bin:/bundle/runtime/helpers";graph:="/installation/runtime/storage";unit:=cid+"-123";id:=cid\n\t\t\tswitch bad {case "profile":profile="other";case "rootful":rootless=false;case "startup":startup=true;case "interval":interval="30s";case "executable":executable="/bundle/runtime/engine/other";case "path":path+=" :/usr/bin";case "graph":graph="/installation/storage";case "unit":unit="other-123";case "cid":id="not-a-cid";case "traversal":graph="/installation/../installation/runtime/storage";case "spaces":executable="/bad bundle/runtime/engine/podman";case "percent":graph="/bad%n/runtime/storage";case "dollar":graph="/bad$HOME/runtime/storage";case "colon":executable="/bad:bundle/runtime/engine/podman";case "newline":graph="/bad\\nroot/runtime/storage"}\n\t\t\tif p,e:=build(profile,rootless,executable,path,graph,unit,id,interval,startup,global);e==nil || p!=nil {t.Errorf("accepted %s",bad)}\n\t\t}\n\t})\n\tt.Run("reject_native_argument_drift",func(t *testing.T) {\n\t\tfor i:=range global {args:=append([]string{},global...);args[i]+="-changed";if p,e:=build("development-v1",true,"/bundle/runtime/engine/podman","/bundle/runtime/bin:/bundle/runtime/helpers","/installation/runtime/storage",cid+"-123",cid,"15s",false,args);e==nil || p!=nil {t.Errorf("accepted changed argument %d",i)}}\n\t\tfor _,args:=range [][]string{global[:len(global)-1],append(append([]string{},global...),"--module","other")} {if p,e:=build("development-v1",true,"/bundle/runtime/engine/podman","/bundle/runtime/bin:/bundle/runtime/helpers","/installation/runtime/storage",cid+"-123",cid,"15s",false,args);e==nil || p!=nil {t.Fatal("accepted membership drift")}}\n\t})\n\tt.Run("job_done_before_save",func(t *testing.T) {\n\t\tp:=valid();events:=[]string{}\n\t\te:=ambisgisCommitHealthTimer(context.Background(),p,func(_ context.Context,ch chan<-string)error{events=append(events,"start");ch<-"done";return nil},func(name string)error{if name!=p.UnitName {t.Fatal("save name")};events=append(events,"save");return nil})\n\t\tif e!=nil || !reflect.DeepEqual(events,[]string{"start","save"}) {t.Fatal("completion ordering")}\n\t})\n\tt.Run("manager_error_no_save",func(t *testing.T) {\n\t\twant:=errors.New("manager failed");saved:=false;e:=ambisgisCommitHealthTimer(context.Background(),valid(),func(_ context.Context,ch chan<-string)error{return want},func(string)error{saved=true;return nil})\n\t\tif !errors.Is(e,want)||saved || !strings.Contains(e.Error(),cid+"-123") {t.Fatal("manager failure/identity lost")}\n\t})\n\tt.Run("job_failure_no_save",func(t *testing.T) {\n\t\tfor _,state:=range []string{"failed","timeout","canceled",""} {saved:=false;e:=ambisgisCommitHealthTimer(context.Background(),valid(),func(_ context.Context,ch chan<-string)error{ch<-state;return nil},func(string)error{saved=true;return nil});if e==nil||saved {t.Fatal("job failure saved")}}\n\t})\n\tt.Run("closed_job_no_save",func(t *testing.T) {\n\t\tsaved:=false;e:=ambisgisCommitHealthTimer(context.Background(),valid(),func(_ context.Context,ch chan<-string)error{close(ch);return nil},func(string)error{saved=true;return nil});if e==nil||saved {t.Fatal("closed job saved")}\n\t})\n\tt.Run("save_error_preserved",func(t *testing.T) {\n\t\twant:=errors.New("save failed");e:=ambisgisCommitHealthTimer(context.Background(),valid(),func(_ context.Context,ch chan<-string)error{ch<-"done";return nil},func(string)error{return want});if !errors.Is(e,want)||!strings.Contains(e.Error(),cid+"-123") {t.Fatal("save failure/identity lost")}\n\t})\n\tt.Run("nil_plan_no_call",func(t *testing.T) {\n\t\tcalled:=false;e:=ambisgisCommitHealthTimer(context.Background(),nil,func(_ context.Context,ch chan<-string)error{called=true;return nil},func(string)error{called=true;return nil});if e==nil||called {t.Fatal("nil plan dispatched")}\n\t})\n\tt.Run("canceled_wait_no_save",func(t *testing.T) {\n\t\tctx,cancel:=context.WithCancel(context.Background());defer cancel();saved:=false\n\t\te:=ambisgisCommitHealthTimer(ctx,valid(),func(ctx context.Context,ch chan<-string)error{cancel();return nil},func(string)error{saved=true;return nil})\n\t\tif !errors.Is(e,context.Canceled)||saved||!strings.Contains(e.Error(),cid+"-123") {t.Fatal("cancellation/identity lost")}\n\t})\n\tt.Run("late_job_send_buffered",func(t *testing.T) {\n\t\tctx,cancel:=context.WithCancel(context.Background());defer cancel();var late chan<-string\n\t\te:=ambisgisCommitHealthTimer(ctx,valid(),func(ctx context.Context,ch chan<-string)error{late=ch;cancel();return nil},func(string)error{t.Fatal("unexpected save");return nil})\n\t\tif !errors.Is(e,context.Canceled) {t.Fatal("cancellation")}\n\t\tselect {case late<-"done": default:t.Fatal("late job would block listener")}\n\t})\n\n\tt.Run("canceled_before_start_no_call",func(t *testing.T) {\n\t\tctx,cancel:=context.WithCancel(context.Background());cancel();called:=false\n\t\te:=ambisgisCommitHealthTimer(ctx,valid(),func(ctx context.Context,ch chan<-string)error{called=true;return nil},func(string)error{called=true;return nil})\n\t\tif !errors.Is(e,context.Canceled)||called||!strings.Contains(e.Error(),"not submitted") {t.Fatal("canceled request dispatched")}\n\t})\n\tt.Run("done_after_cancel_no_save",func(t *testing.T) {\n\t\tctx,cancel:=context.WithCancel(context.Background());defer cancel();saved:=false\n\t\te:=ambisgisCommitHealthTimer(ctx,valid(),func(ctx context.Context,ch chan<-string)error{ch<-"done";cancel();return nil},func(string)error{saved=true;return nil})\n\t\tif !errors.Is(e,context.Canceled)||saved {t.Fatal("late done saved")}\n\t})\n\n}\n'
CASES = ('native_unselected', 'wire_properties', 'reject_profile_and_paths', 'reject_native_argument_drift', 'job_done_before_save', 'manager_error_no_save', 'job_failure_no_save', 'closed_job_no_save', 'save_error_preserved', 'nil_plan_no_call', 'canceled_wait_no_save', 'late_job_send_buffered', 'canceled_before_start_no_call', 'done_after_cancel_no_save')


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
    text=(source/'libpod/healthcheck_linux.go').read_text()
    if text.count(BRANCH)!=1 or text.count('conn.StartTransientUnitAux(')!=1:
        raise AssertionError('Finite owned timer path is absent or changed')
    if (source/'libpod/ambisgis_health_timer.go').read_text()!=HELPER:
        raise AssertionError('Finite plan helper changed')


def patch(source):
    path=source/'libpod/healthcheck_linux.go'
    if sha(path)!=SOURCE_SHA: raise ValueError('Exact retained healthcheck source required')
    original=path.read_text()
    if original.count(ANCHOR)!=1: raise ValueError('Native createTimer anchor changed')
    names=('ambisgis_health_timer.go','ambisgis_health_timer_test.go')
    if any((path.parent/name).exists() for name in names): raise ValueError('Repair already present')
    changed=original.replace(ANCHOR,BRANCH+ANCHOR)
    if changed.replace(BRANCH,'')!=original: raise ValueError('Unselected native source changed')
    path.write_text(changed)
    for name,data in zip(names,(HELPER,TEST)): (path.parent/name).write_text(data)
    source_contract(source)
    delta=''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/libpod/healthcheck_linux.go',tofile='b/libpod/healthcheck_linux.go'))
    for name,data in zip(names,(HELPER,TEST)):
        delta+=''.join(difflib.unified_diff([],data.splitlines(True),fromfile='/dev/null',tofile='b/libpod/'+name))
    return delta,original,{'file':'libpod/healthcheck_linux.go','before_sha256':SOURCE_SHA,'after_sha256':sha(path),'only_selected_create_timer_branch_added':True,'unselected_start_cleanup_unchanged':True}


def unit_result(text):
    for case in CASES:
        if text.count('=== RUN   TestAmbisGISHealthTimer/'+case+'\n')!=1 or ('--- PASS: TestAmbisGISHealthTimer/'+case+' (') not in text: return False
    return text.endswith('PASS\n') and '--- FAIL:' not in text


def command_plan(output):
    go=str(output/'toolchain/usr/lib64/go/1.27/bin/go')
    common=['-x','-p=2','-mod=vendor','-buildvcs=false','-trimpath']
    return [
        ('timer-compile',[go,'test','-c',*common,'-o',str(output/'bin/timer.test'),'libpod/ambisgis_health_timer.go','libpod/ambisgis_health_timer_test.go'],0),
        ('timer-unit',[str(output/'bin/timer.test'),'-test.run=^TestAmbisGISHealthTimer$','-test.count=1','-test.v'],0),
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
    (output/'baseline/healthcheck_linux.go').write_text(baseline)
    source = inventory(helper, output/'source')
    if [p for p in old if old[p] != source[p]] != ['libpod/healthcheck_linux.go']:
        raise ValueError('Repair modified unselected source')
    if set(source)-set(old) != {'libpod/ambisgis_health_timer.go','libpod/ambisgis_health_timer_test.go'}:
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
    (output/'MODIFICATIONS.txt').write_text('AmbisGIS modification, 2026-10-04.\nPodman source '+prior['source_commit']+' and all five previously retained repairs are preserved.\nOnly explicitly selected development-v1 rootless normal15s health timers use the existing native private DBus connection and one transient timer-plus-auxiliary-service request; partial effects on errors require exact-name reconciliation.\nThe fixed host-context healthcheck-timer launcher and exact finite native arguments preserve private loader/config checks. Native behavior with an empty selector, startTimer and removeTransientFiles remain unchanged.\nAll original Apache-2.0 LICENSE and vendor source/notices remain. No invented revision override or new dependency.\nExact patch/source/build hashes identify this derived build.\n')
    invocation={'schema_version':1,'recipe_sha256':sha(Path(__file__)),'inputs':[{'path':str(p),'sha256':s} for p,s in PINS.items()],
        'host_compiler_support':host,'build_environment':env,'commands':command_plan(output),'preparation_sha256':sha(output/'preparation.json'),
        'toolchain_sha256':sha(output/'toolchain.json'),'compiler_commands':helper.inventory(commands),
        'modifications_sha256':sha(output/'MODIFICATIONS.txt'),
        'supervisor':{'path':sys.executable,'sha256':sha(sys.executable)},
        'scope':'Only standalone finite timer plan and injected job/save tests; no libpod package init/TestMain, D-Bus connection, prior native suites, engine, namespace or held probe. Offline compiler uses retained inputs; host bootstrap remains explicit.'}
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
        if name == 'timer-unit':
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
    if result['exit_code']: raise ValueError('Owned finite health-timer build failed; evidence retained')
    return output/'result.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--execute-prepared',action='store_true');mode.add_argument('--child',action='store_true')
    parser.add_argument('--invocation-sha256');args=parser.parse_args()
    if args.prepare_only: print(prepare(args.output))
    elif not args.invocation_sha256: parser.error('Reviewed invocation hash required')
    elif args.child: raise SystemExit(child(args.output,args.invocation_sha256))
    else: print(execute(args.output,args.invocation_sha256))
