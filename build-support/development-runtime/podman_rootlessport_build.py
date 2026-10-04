#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the owned descriptor-relative rootlessport repair; native execution requires separate review.

This recipe preserves prior source/toolchain custody and prepares only standalone
helper regressions plus the normal engine/helper builds. No engine is executed.
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


BUILD = '/home/revelberry/Projects/AmbisGIS/build-worktrees/plt01-podman-build'
BUILD = Path(BUILD)
PRIOR = Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001')
INSPECT_REVIEW = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/trust/plt01-created-state-root-review-001/result.json')
PINS = {
    Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001/build-executed.py'): '8521ca59f18e8df93e3a1f0a0d4f701dc0fbe284530bcda4c8291c66d20455f2',
    Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001/offline-executed.py'): 'ed658e05bc1cde8b008835b146bf2be73487313f581ce66da31d5644b3766ace',
    Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001/invocation.json'): 'a2830cbbedd94d05712b699ca86c2d022b39c922e6c81725022496297ab65887',
    Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001/preparation.json'): '0e8d3491e8ddd7916ac5f8a6015b3b458fd1e7f42a093a74ea6d5112754cb957',
    Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001/toolchain.json'): '88c9dfab2f03d59019b96d94ca119c5a3aa12cf8509c0da7547747123e19f60a',
    Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001/owned-source.patch'): 'aad28aaf40cf811848e689fcd6443787090b20a47442314e0e5b50bb2557ac68',
    Path('/home/revelberry/Projects/AmbisGIS_Codex_Plan/plt01-runtime-checks/podman-inspect-build-001/MODIFICATIONS.txt'): '43094d2fa34801b8a647df68f79eaa226ca405db8c87636a1b440a44d5cd6f65',
    Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/trust/plt01-created-state-root-review-001/result.json'): 'e69d11cbde8e31f56456cc775bb0bf486db90102ddd65d50ad636557ef85b5d5',
}
SOURCE_SHA = '416eaed431671fabf5c8f71ab287edbdc3b5465213739f8492bed30bc6ab6fe7'
TAGS = 'apparmor,seccomp,systemd,exclude_graphdriver_btrfs'
ANCHORS = [('\tdriver, err := rkbuiltin.NewParentDriver(&logrusWriter{prefix: "parent: "}, stateDir)', '\tstateDirectory, statePath, err := ambisgisRootlessportDirectory(stateDir)\n\tif err != nil {\n\t\treturn err\n\t}\n\tdefer stateDirectory.Close()\n\tdriver, err := rkbuiltin.NewParentDriver(&logrusWriter{prefix: "parent: "}, statePath)'), ('\topaque := driver.OpaqueForChild()', '\topaque, err := ambisgisRootlessportChildOpaque(driver.OpaqueForChild(), statePath, 3)\n\tif err != nil {\n\t\treturn err\n\t}'), ('\tcmd.Stdin = childQuitR', '\tcmd.Stdin = childQuitR\n\tcmd.ExtraFiles = []*os.File{stateDirectory}'), ('\t// start the child driver\n\tquit := make(chan struct{})\n\terrCh := make(chan error)\n\tgo func() {\n\t\td := rkbuiltin.NewChildDriver(os.Stderr)\n\t\tdErr := d.RunChildDriver(opaque, quit, "")\n\t\terrCh <- dErr\n\t}()\n\tdefer func() {\n\t\tlogrus.Info("Stopping child driver")\n\t\tquit <- struct{}{}\n\t\tif err := <-errCh; err != nil {\n\t\t\tlogrus.WithError(err).Warn("Child driver returned error on exit")\n\t\t}\n\t}()\n\n\t// wait for stdin to be closed\n\tif _, err := io.ReadAll(os.Stdin); err != nil {\n\t\treturn err\n\t}\n\treturn nil', '\treturn ambisgisRunRootlessportChild(os.Stdin, func(quit <-chan struct{}) error {\n\t\td := rkbuiltin.NewChildDriver(os.Stderr)\n\t\treturn d.RunChildDriver(opaque, quit, "")\n\t}, ambisgisRootlessportShutdownTimeout)')]
HELPER = '// SPDX-License-Identifier: Apache-2.0\n// AmbisGIS modification: descriptor-relative owned rootlessport state and child lifecycle.\npackage main\n\nimport (\n    "errors"\n    "fmt"\n    "io"\n    "os"\n    "path/filepath"\n    "time"\n    "golang.org/x/sys/unix"\n)\n\nconst ambisgisRootlessportShutdownTimeout = 3 * time.Second\n\nfunc ambisgisRootlessportDirectory(stateDir string) (*os.File, string, error) {\n    fd, err := unix.Open(stateDir, unix.O_PATH|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)\n    if err != nil { return nil, "", err }\n    directory := os.NewFile(uintptr(fd), stateDir)\n    return directory, fmt.Sprintf("/proc/self/fd/%d", fd), nil\n}\n\nfunc ambisgisRootlessportChildOpaque(parent map[string]string, parentPath string, childFD int) (map[string]string, error) {\n    if childFD < 3 || len(parent) != 2 { return nil, errors.New("invalid owned port driver descriptor contract") }\n    result := make(map[string]string, 2)\n    for key, name := range map[string]string{"builtin.socketpath": ".bp.sock", "builtin.readypipepath": ".bp-ready.pipe"} {\n        if parent[key] != filepath.Join(parentPath, name) { return nil, errors.New("unexpected built-in port driver path") }\n        result[key] = filepath.Join(fmt.Sprintf("/proc/self/fd/%d", childFD), name)\n    }\n    return result, nil\n}\n\n// Early driver failure must reach main even while the parent keeps stdin open.\n// Buffered completions avoid abandoning a sender when the other event wins.\nfunc ambisgisRunRootlessportChild(input io.Reader, driver func(<-chan struct{}) error, stopTimeout time.Duration) error {\n    if stopTimeout <= 0 { return errors.New("invalid child shutdown bound") }\n    quit := make(chan struct{})\n    done := make(chan error, 1)\n    inputDone := make(chan error, 1)\n    go func() { done <- driver(quit) }()\n    go func() { _, err := io.Copy(io.Discard, input); inputDone <- err }()\n    select {\n    case err := <-done:\n        close(quit)\n        if err == nil { return errors.New("port driver exited before parent shutdown") }\n        return err\n    case inputErr := <-inputDone:\n        close(quit)\n        timer := time.NewTimer(stopTimeout)\n        defer timer.Stop()\n        select {\n        case driverErr := <-done:\n            if inputErr != nil { return inputErr }\n            return driverErr\n        case <-timer.C:\n            return errors.New("port driver shutdown timed out")\n        }\n    }\n}\n'
TEST = '// SPDX-License-Identifier: Apache-2.0\npackage main\n\nimport (\n    "context"\n    "errors"\n    "io"\n    "net"\n    "os"\n    "os/exec"\n    "path/filepath"\n    "strings"\n    "testing"\n    "time"\n)\n\nfunc TestAmbisGISRootlessportSocket(t *testing.T) {\n    for _, child := range []bool{false, true} {\n        name := "parent_bind"; if child { name = "child_descriptor" }\n        t.Run(name, func(t *testing.T) {\n            state := filepath.Join(t.TempDir(), strings.Repeat("a",80), strings.Repeat("b",80))\n            if err := os.MkdirAll(state,0700); err != nil { t.Fatal(err) }\n            if len(filepath.Join(state,".bp.sock")) <= 108 { t.Fatal("fixture is not a long pathname") }\n            directory, short, err := ambisgisRootlessportDirectory(state)\n            if err != nil { t.Fatal(err) }; defer directory.Close()\n            listener, err := net.ListenUnix("unix",&net.UnixAddr{Name:filepath.Join(short,".bp.sock"),Net:"unix"})\n            if err != nil { t.Fatal(err) }; defer listener.Close()\n            if err := listener.SetDeadline(time.Now().Add(3*time.Second)); err != nil { t.Fatal(err) }\n            received := make(chan error,1)\n            go func() {\n                conn, err := listener.AcceptUnix(); if err != nil { received<-err; return }; defer conn.Close()\n                conn.SetDeadline(time.Now().Add(time.Second))\n                data := make([]byte,3); _, err = io.ReadFull(conn,data)\n                if err == nil && string(data)!="ok3" { err=errors.New("wrong fixture payload") }; received<-err\n            }()\n            if child {\n                opaque, err := ambisgisRootlessportChildOpaque(map[string]string{"builtin.socketpath":filepath.Join(short,".bp.sock"),"builtin.readypipepath":filepath.Join(short,".bp-ready.pipe")},short,3)\n                if err != nil || opaque["builtin.socketpath"]!="/proc/self/fd/3/.bp.sock" { t.Fatal("bad child descriptor projection",err) }\n                ctx,cancel:=context.WithTimeout(context.Background(),3*time.Second);defer cancel()\n                cmd:=exec.CommandContext(ctx,os.Args[0],"-test.run=^TestAmbisGISRootlessportChildDescriptor$","-test.count=1")\n                cmd.Env=append(os.Environ(),"AMBISGIS_ROOTLESSPORT_FD_CHECK=1")\n                cmd.ExtraFiles=[]*os.File{directory}\n                output,err:=cmd.CombinedOutput();if err!=nil {t.Fatalf("owned descriptor child failed: %v %s",err,output)}\n            } else {\n                conn,err:=net.DialTimeout("unix",filepath.Join(short,".bp.sock"),time.Second)\n                if err!=nil {t.Fatal(err)};_,err=conn.Write([]byte("ok3"));conn.Close();if err!=nil {t.Fatal(err)}\n            }\n            if err:=<-received;err!=nil {t.Fatal(err)}\n        })\n    }\n    t.Run("child_listener",func(t *testing.T){\n        state:=filepath.Join(t.TempDir(),strings.Repeat("c",80),strings.Repeat("d",80))\n        if err:=os.MkdirAll(state,0700);err!=nil {t.Fatal(err)}\n        directory,short,err:=ambisgisRootlessportDirectory(state);if err!=nil {t.Fatal(err)};defer directory.Close()\n        readyR,readyW,err:=os.Pipe();if err!=nil {t.Fatal(err)};defer readyR.Close();defer readyW.Close()\n        if err:=readyR.SetReadDeadline(time.Now().Add(3*time.Second));err!=nil {t.Fatal(err)}\n        ctx,cancel:=context.WithTimeout(context.Background(),3*time.Second);defer cancel()\n        cmd:=exec.CommandContext(ctx,os.Args[0],"-test.run=^TestAmbisGISRootlessportChildListener$","-test.count=1")\n        cmd.Env=append(os.Environ(),"AMBISGIS_ROOTLESSPORT_LISTEN_CHECK=1")\n        cmd.ExtraFiles=[]*os.File{directory,readyW};cmd.Stdout=io.Discard;cmd.Stderr=io.Discard\n        if err:=cmd.Start();err!=nil {t.Fatal(err)}\n        defer func(){cancel();if cmd.ProcessState==nil {cmd.Wait()}}()\n        readyW.Close()\n        token:=make([]byte,1);if _,err:=io.ReadFull(readyR,token);err!=nil || token[0]!=\'1\' {t.Fatal("child listener not ready",err)}\n        conn,err:=net.DialTimeout("unix",filepath.Join(short,".bp.sock"),time.Second);if err!=nil {t.Fatal(err)};defer conn.Close()\n        if err:=conn.SetDeadline(time.Now().Add(time.Second));err!=nil {t.Fatal(err)}\n        if _,err:=conn.Write([]byte("ok3"));err!=nil {t.Fatal(err)}\n        response:=make([]byte,3);if _,err:=io.ReadFull(conn,response);err!=nil || string(response)!="ok3" {t.Fatal("child did not verify unlink before directory close",err)}\n        if err:=cmd.Wait();err!=nil {t.Fatal("child listener failed",err)}\n        if _,err:=os.Lstat(filepath.Join(state,".bp.sock"));!os.IsNotExist(err) {t.Fatal("socket survived listener close",err)}\n    })\n\n}\n\nfunc TestAmbisGISRootlessportChildDescriptor(t *testing.T) {\n    if os.Getenv("AMBISGIS_ROOTLESSPORT_FD_CHECK")!="1" { return }\n    conn,err:=net.DialTimeout("unix","/proc/self/fd/3/.bp.sock",time.Second)\n    if err!=nil {t.Fatal(err)};defer conn.Close()\n    if _,err=conn.Write([]byte("ok3"));err!=nil {t.Fatal(err)}\n}\n\n\nfunc TestAmbisGISRootlessportChildListener(t *testing.T) {\n    if os.Getenv("AMBISGIS_ROOTLESSPORT_LISTEN_CHECK")!="1" {return}\n    directory:=os.NewFile(3,"owned fixture directory");defer directory.Close()\n    ready:=os.NewFile(4,"owned fixture readiness");defer ready.Close()\n    path:="/proc/self/fd/3/.bp.sock"\n    listener,err:=net.ListenUnix("unix",&net.UnixAddr{Name:path,Net:"unix"});if err!=nil {t.Fatal(err)};defer listener.Close()\n    if err:=listener.SetDeadline(time.Now().Add(time.Second));err!=nil {t.Fatal(err)}\n    if _,err:=ready.Write([]byte("1"));err!=nil {t.Fatal(err)};ready.Close()\n    conn,err:=listener.AcceptUnix();if err!=nil {t.Fatal(err)};defer conn.Close()\n    if err:=conn.SetDeadline(time.Now().Add(time.Second));err!=nil {t.Fatal(err)}\n    data:=make([]byte,3);if _,err:=io.ReadFull(conn,data);err!=nil || string(data)!="ok3" {t.Fatal("fixture read failed",err)}\n    if err:=listener.Close();err!=nil {t.Fatal(err)}\n    if _,err:=os.Lstat(path);!os.IsNotExist(err) {t.Fatal("listener did not unlink socket",err)}\n    if info,err:=os.Stat("/proc/self/fd/3");err!=nil || !info.IsDir() {t.Fatal("directory closed before socket unlink",err)}\n    if _,err:=conn.Write([]byte("ok3"));err!=nil {t.Fatal(err)}\n}\n\nfunc TestAmbisGISRootlessportInput(t *testing.T) {\n    t.Run("symlink_rejected",func(t *testing.T){\n        root:=t.TempDir(); link:=filepath.Join(root,"link")\n        if err:=os.Symlink(root,link);err!=nil {t.Fatal(err)}\n        file,_,err:=ambisgisRootlessportDirectory(link);if file!=nil {file.Close()};if err==nil {t.Fatal("symlink admitted")}\n    })\n    t.Run("regular_file_rejected",func(t *testing.T){\n        path:=filepath.Join(t.TempDir(),"file");if err:=os.WriteFile(path,nil,0600);err!=nil {t.Fatal(err)}\n        file,_,err:=ambisgisRootlessportDirectory(path);if file!=nil {file.Close()};if err==nil {t.Fatal("regular file admitted")}\n    })\n    t.Run("opaque_contract",func(t *testing.T){\n        good:=map[string]string{"builtin.socketpath":"/proc/self/fd/8/.bp.sock","builtin.readypipepath":"/proc/self/fd/8/.bp-ready.pipe"}\n        for _,bad:=range []map[string]string{{}, {"builtin.socketpath":"/other/.bp.sock","builtin.readypipepath":good["builtin.readypipepath"]},{"builtin.socketpath":good["builtin.socketpath"],"builtin.readypipepath":good["builtin.readypipepath"],"extra":"value"}} {\n            if _,err:=ambisgisRootlessportChildOpaque(bad,"/proc/self/fd/8",3);err==nil {t.Fatal("bad opaque map admitted")}\n        }\n        if _,err:=ambisgisRootlessportChildOpaque(good,"/proc/self/fd/8",2);err==nil {t.Fatal("stdio descriptor admitted")}\n    })\n}\n\ntype ambisgisErrorReader struct {err error}\nfunc (r ambisgisErrorReader) Read([]byte)(int,error){return 0,r.err}\n\nfunc TestAmbisGISRootlessportLifecycle(t *testing.T) {\n    t.Run("early_error",func(t *testing.T){\n        input,writer:=io.Pipe();defer input.Close();defer writer.Close()\n        want:=errors.New("fixture driver failure")\n        result:=make(chan error,1)\n        go func(){result<-ambisgisRunRootlessportChild(input,func(<-chan struct{})error{return want},time.Second)}()\n        select {case err:=<-result:if err!=want {t.Fatal("lost driver failure")};case <-time.After(time.Second):t.Fatal("early error blocked on stdin")}\n    })\n    t.Run("early_nil",func(t *testing.T){\n        input,writer:=io.Pipe();defer input.Close();defer writer.Close()\n        if err:=ambisgisRunRootlessportChild(input,func(<-chan struct{})error{return nil},time.Second);err==nil {t.Fatal("early nil accepted")}\n    })\n    t.Run("normal_eof",func(t *testing.T){\n        stopped:=make(chan struct{})\n        err:=ambisgisRunRootlessportChild(strings.NewReader(""),func(quit<-chan struct{})error{<-quit;close(stopped);return nil},time.Second)\n        if err!=nil {t.Fatal(err)};select{case <-stopped:default:t.Fatal("driver was not stopped")}\n    })\n    t.Run("input_error",func(t *testing.T){\n        want:=errors.New("fixture reader error")\n        if err:=ambisgisRunRootlessportChild(ambisgisErrorReader{want},func(quit<-chan struct{})error{<-quit;return nil},time.Second);err!=want {t.Fatal("lost input error")}\n    })\n    t.Run("shutdown_bound",func(t *testing.T){\n        release:=make(chan struct{});finished:=make(chan struct{})\n        defer func(){close(release);select{case <-finished:case <-time.After(time.Second):t.Error("fixture worker leaked")}}()\n        start:=time.Now();err:=ambisgisRunRootlessportChild(strings.NewReader(""),func(<-chan struct{})error{<-release;close(finished);return nil},20*time.Millisecond)\n        if err==nil || time.Since(start)>time.Second {t.Fatal("shutdown deadline not honored")}\n    })\n}\n'
BASELINE = '// SPDX-License-Identifier: Apache-2.0\n// AmbisGIS modification: descriptor-relative owned rootlessport state and child lifecycle.\npackage main\n\nimport (\n    "errors"\n    "fmt"\n    "io"\n    "os"\n    "path/filepath"\n    "time"\n    "golang.org/x/sys/unix"\n)\n\nconst ambisgisRootlessportShutdownTimeout = 3 * time.Second\n\nfunc ambisgisRootlessportDirectory(stateDir string) (*os.File, string, error) {\n    fd, err := unix.Open(stateDir, unix.O_PATH|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)\n    if err != nil { return nil, "", err }\n    directory := os.NewFile(uintptr(fd), stateDir)\n    return directory, stateDir, nil\n}\n\nfunc ambisgisRootlessportChildOpaque(parent map[string]string, parentPath string, childFD int) (map[string]string, error) {\n    if childFD < 3 || len(parent) != 2 { return nil, errors.New("invalid owned port driver descriptor contract") }\n    result := make(map[string]string, 2)\n    for key, name := range map[string]string{"builtin.socketpath": ".bp.sock", "builtin.readypipepath": ".bp-ready.pipe"} {\n        if parent[key] != filepath.Join(parentPath, name) { return nil, errors.New("unexpected built-in port driver path") }\n        result[key] = filepath.Join(fmt.Sprintf("/proc/self/fd/%d", childFD), name)\n    }\n    return result, nil\n}\n\n// Early driver failure must reach main even while the parent keeps stdin open.\n// Buffered completions avoid abandoning a sender when the other event wins.\nfunc ambisgisRunRootlessportChild(input io.Reader, driver func(<-chan struct{}) error, stopTimeout time.Duration) error {\n    if stopTimeout <= 0 { return errors.New("invalid child shutdown bound") }\n    quit := make(chan struct{})\n    done := make(chan error, 1)\n    inputDone := make(chan error, 1)\n    go func() { done <- driver(quit) }()\n    go func() { _, err := io.Copy(io.Discard, input); inputDone <- err }()\n    select {\n    case err := <-done:\n        close(quit)\n        if err == nil { return errors.New("port driver exited before parent shutdown") }\n        return err\n    case inputErr := <-inputDone:\n        close(quit)\n        timer := time.NewTimer(stopTimeout)\n        defer timer.Stop()\n        select {\n        case driverErr := <-done:\n            if inputErr != nil { return inputErr }\n            return driverErr\n        case <-timer.C:\n            return errors.New("port driver shutdown timed out")\n        }\n    }\n}\n'

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
    # The independently reviewed inspect source is prepared, not yet built.
    # Its verifier binds the entire prepared tree/toolchain and completed
    # health-timer predecessor; do not invent an inspect execution result.
    previous = retained_predecessor()
    helper, _, prior, _ = previous.verified_preparation(PRIOR, PINS[PRIOR/'invocation.json'])
    review = json.loads(INSPECT_REVIEW.read_text())
    if review['status'] != 'PASS_INDEPENDENT_SOURCE_AND_INERT_REVIEW_NATIVE_PENDING' or review['findings']:
        raise ValueError('Independent prepared inspect source review required')
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
    text=(source/'cmd/rootlessport/main.go').read_text()
    for old,new in ANCHORS:
        if text.count(new)!=1: raise AssertionError('Owned rootlessport callsite changed')
    for name,data in [('ambisgis_rootlessport.go',HELPER),('ambisgis_rootlessport_test.go',TEST)]:
        if (source/'cmd/rootlessport'/name).read_text()!=data: raise AssertionError('Owned rootlessport helper changed')


def patch(source):
    path=source/'cmd/rootlessport/main.go'
    if sha(path)!=SOURCE_SHA: raise ValueError('Exact retained rootlessport source required')
    original=path.read_text();changed=original
    names=('ambisgis_rootlessport.go','ambisgis_rootlessport_test.go')
    if any((path.parent/name).exists() for name in names): raise ValueError('Repair already present')
    for old,new in ANCHORS:
        if changed.count(old)!=1: raise ValueError('Native rootlessport anchor changed')
        changed=changed.replace(old,new)
    restored=changed
    for old,new in reversed(ANCHORS): restored=restored.replace(new,old)
    if restored!=original: raise ValueError('Unselected native source changed')
    path.write_text(changed)
    for name,data in zip(names,(HELPER,TEST)): (path.parent/name).write_text(data)
    source_contract(source)
    delta=''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/cmd/rootlessport/main.go',tofile='b/cmd/rootlessport/main.go'))
    for name,data in zip(names,(HELPER,TEST)):
        delta+=''.join(difflib.unified_diff([],data.splitlines(True),fromfile='/dev/null',tofile='b/cmd/rootlessport/'+name))
    return delta,BASELINE,{'file':'cmd/rootlessport/main.go','before_sha256':SOURCE_SHA,'after_sha256':sha(path),'four_exact_owned_callsite_changes':True,'vendor_unchanged':True,'namespace_and_mapping_semantics_unchanged':True}


def unit_result(text,baseline=False):
    cases={'TestAmbisGISRootlessportSocket':('parent_bind','child_descriptor','child_listener')}
    if not baseline: cases.update({'TestAmbisGISRootlessportInput':('symlink_rejected','regular_file_rejected','opaque_contract'),'TestAmbisGISRootlessportLifecycle':('early_error','early_nil','normal_eof','input_error','shutdown_bound')})
    expected='FAIL' if baseline else 'PASS'
    for name,subcases in cases.items():
        for case in subcases:
            if text.count('=== RUN   '+name+'/'+case+'\n')!=1 or ('--- '+expected+': '+name+'/'+case+' (') not in text:return False
    return text.endswith(expected+'\n') and ('--- SKIP:' not in text) and (baseline or '--- FAIL:' not in text)


def command_plan(output):
    go=str(output/'toolchain/usr/lib64/go/1.27/bin/go')
    common=['-x','-p=2','-mod=vendor','-buildvcs=false','-trimpath']
    return retained_predecessor().command_plan(output)[:2] + [
        ('baseline-compile',[go,'test','-c',*common,'-o',str(output/'bin/baseline.test'),str(output/'baseline/rootlessport.go'),str(output/'baseline/rootlessport_test.go')],0),
        ('baseline-unit',[str(output/'bin/baseline.test'),'-test.run=^TestAmbisGISRootlessportSocket$','-test.count=1','-test.timeout=15s','-test.v'],1),
        ('rootlessport-compile',[go,'test','-c',*common,'-o',str(output/'bin/rootlessport.test'),'cmd/rootlessport/ambisgis_rootlessport.go','cmd/rootlessport/ambisgis_rootlessport_test.go'],0),
        ('rootlessport-unit',[str(output/'bin/rootlessport.test'),'-test.run=^TestAmbisGISRootlessport','-test.count=1','-test.timeout=15s','-test.v'],0),
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
    retained_predecessor().source_contract(output/'source')
    (output/'owned-source.patch').write_text(delta)
    (output/'baseline/rootlessport.go').write_text(baseline)
    (output/'baseline/rootlessport_test.go').write_text(TEST)
    source = inventory(helper, output/'source')
    if [p for p in old if old[p] != source[p]] != ['cmd/rootlessport/main.go']:
        raise ValueError('Repair modified unselected source')
    if set(source)-set(old) != {'cmd/rootlessport/ambisgis_rootlessport.go','cmd/rootlessport/ambisgis_rootlessport_test.go'}:
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
    (output/'MODIFICATIONS.txt').write_text('AmbisGIS modification,2026-10-04.\nAll six completed prior repairs plus the independently reviewed prepared inspect-sysctl patch and original licenses/vendor notices are preserved.\nOwned rootlessport state uses retained directory descriptors for parent and child AF_UNIX paths; namespace and port mapping remain native. Early child driver failure is propagated and EOF shutdown has a fixed3second bound. No new dependency/vendor byte changes.\nExact source/patch/build hashes identify this derived build.\n')
    invocation={'schema_version':1,'recipe_sha256':sha(Path(__file__)),'inputs':[{'path':str(p),'sha256':s} for p,s in PINS.items()],
        'host_compiler_support':host,'build_environment':env,'commands':command_plan(output),'preparation_sha256':sha(output/'preparation.json'),
        'toolchain_sha256':sha(output/'toolchain.json'),'compiler_commands':helper.inventory(commands),
        'modifications_sha256':sha(output/'MODIFICATIONS.txt'),
        'supervisor':{'path':sys.executable,'sha256':sha(sys.executable)},
        'scope':'Standalone reviewed inspect projection guards plus owned rootlessport helper tests, fresh private AF_UNIX sockets and self-test subprocesses for both fd directions and unlink-before-close; no existing service, engine, network namespace, bus, inherited native suite or held probe. Network denial and retained compiler inputs preserved.'}
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
    retained_predecessor().source_contract(output/'source')
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
            passed = passed and retained_predecessor().unit_result(log.read_text())
        if name in ('baseline-unit','rootlessport-unit'):
            passed = passed and unit_result(log.read_text(),baseline=name=='baseline-unit')
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
    if result['exit_code']: raise ValueError('Owned finite rootlessport build failed; evidence retained')
    return output/'result.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--execute-prepared',action='store_true');mode.add_argument('--child',action='store_true')
    parser.add_argument('--invocation-sha256');args=parser.parse_args()
    if args.prepare_only: print(prepare(args.output))
    elif not args.invocation_sha256: parser.error('Reviewed invocation hash required')
    elif args.child: raise SystemExit(child(args.output,args.invocation_sha256))
    else: print(execute(args.output,args.invocation_sha256))
