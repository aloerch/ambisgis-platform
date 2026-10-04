"""Pure DNS observer fixtures; no live /proc, engine, socket or signals."""
import copy
import hashlib
from pathlib import Path
import stat
import os
import tempfile
import unittest
from unittest.mock import patch

import dns_observation as dns

UID=1000
ROOT=Path('/private/installation')
BUNDLE=Path('/private/bundle')
INSTALL='aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
HASH='a'*64
def meta(mode=stat.S_IFREG|0o600,ino=1):
    return {'mode':mode,'uid':UID,'dev':4,'ino':ino}

class Fixture:
    def __init__(self, expected):
        self.expected=expected
        self.files={expected.pidfile:b'1234', expected.entry:b'private DNS fixture\n'}
        self.entries={'aardvark.pid',expected.entry.name}
        self.metas={expected.root:meta(stat.S_IFDIR|0o700),expected.directory:meta(stat.S_IFDIR|0o700),
                    expected.executable:meta(stat.S_IFREG|0o700,55),expected.netns:meta(stat.S_IFREG|0o444,900)}
        self.capture={'pid':1234,'start_ticks':77,'state':'S','pgrp':1234,'session':1234,'uid':[UID]*4,
            'uid_map':[[0,UID,1],[1,100000,65536]],'gid_map':[[0,UID,1],[1,100000,65536]],
            'exe_path':str(expected.executable),'exe_sha256':HASH,'exe_identity':[4,55],
            'arguments':[str(expected.executable),'--config',str(expected.directory),'-p','53','run'],
            'namespaces':{'net':[4,900],'user':[4,901],'mnt':[4,902]},
            'observer_namespaces':{'net':[4,800],'user':[4,801],'mnt':[4,802]},
            'cgroup':'0::/user.slice/user-1000.slice/session-1.scope\n'}
        self.calls=[]
    def metadata(self,path):
        self.calls.append(('metadata',str(path)))
        if path in self.files:return meta()
        if path in self.metas:return self.metas[path]
        raise FileNotFoundError()
    def read(self,path,limit):
        self.calls.append(('read',str(path)))
        if path not in self.files:raise FileNotFoundError()
        value=self.files[path]
        if isinstance(value,Exception):raise value
        if len(value)>limit:raise dns.ObservationError('input_too_large')
        return value
    def names(self,path):
        self.calls.append(('names',str(path)));return set(self.entries)
    def identity(self,pid):
        return self.process(pid)
    def process(self,pid):
        self.calls.append(('process',pid))
        if isinstance(self.capture,Exception):raise self.capture
        if self.capture is None:raise FileNotFoundError()
        return copy.deepcopy(self.capture)

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.expect=dns.from_verified(ROOT,{'install_id':INSTALL,'bundle':{'path':str(BUNDLE/'bundle.json')}},
            BUNDLE,{'files':[{'path':'runtime/helpers/aardvark-dns','sha256':HASH}]},UID)
        self.reader=Fixture(self.expect)
    def running(self):return dns.observe_running(self.expect,reader=self.reader)
    def test_exact_native_paths(self):
        self.assertEqual(self.expect.directory,ROOT/'runtime/run/networks/aardvark-dns')
        self.assertEqual(self.expect.netns,ROOT/'runtime/run/networks/rootless-netns/rootless-netns')
        self.assertEqual(self.expect.entry.name,'ambisgis-'+INSTALL.replace('-','')+'_internal%int')
    def test_running_identity_and_no_raw_arguments(self):
        r=self.running()
        self.assertEqual(r['status'],'verified');self.assertFalse(r['cleanup_verified'])
        self.assertEqual(r['identity']['start_ticks'],77)
        self.assertEqual((r['identity']['pgrp'],r['identity']['session']),(1234,1234))
        self.assertNotIn('arguments',str(r));self.assertNotIn('private DNS fixture',str(r))
    def test_missing_pidfile_fails_before_any_process_read(self):
        del self.reader.files[self.expect.pidfile]
        self.assertEqual(self.running()['status'],'failed')
        self.assertFalse(any(c[0]=='process' for c in self.reader.calls))
    def test_bad_pidfile_never_becomes_process_authority(self):
        for raw in (b'0',b'-1',b'1',b'1234\nsecret',b'01234',b'1234 5',b'9'*40):
            with self.subTest(raw=raw):
                self.reader.files[self.expect.pidfile]=raw;self.reader.calls=[]
                self.assertEqual(self.running()['status'],'failed')
                self.assertFalse(any(c[0]=='process' for c in self.reader.calls))
    def test_wrong_executable_arguments_or_uid_fails(self):
        for field,value in [('exe_sha256','b'*64),('exe_path','/other'),('exe_identity',[4,56]),
            ('arguments',['/bin/sh','SECRET']),('uid',[0]*4),('uid_map',[[0,0,4294967295]])]:
            with self.subTest(field=field):
                original=self.reader.capture[field];self.reader.capture[field]=value
                r=self.running();self.assertEqual(r['status'],'failed');self.assertNotIn('SECRET',str(r))
                self.reader.capture[field]=original
    def test_namespace_mismatch_and_host_namespace_fail(self):
        for value in ([4,999],[4,800]):
            self.reader.capture['namespaces']['net']=value
            self.assertEqual(self.running()['status'],'failed')
    def test_proc_unavailable_never_passes(self):
        for error in (PermissionError(),ProcessLookupError()):
            self.reader.capture=error
            self.assertIn(self.running()['status'],('failed','unsupported'))
    def test_unknown_config_entry_or_unprivate_root_fails(self):
        self.reader.entries.add('other-network')
        self.assertEqual(self.running()['status'],'failed')
        self.reader.entries.remove('other-network')
        self.reader.metas[self.expect.root]=meta(stat.S_IFDIR|0o755)
        self.assertEqual(self.running()['status'],'failed')
    def test_stop_requires_prior_success_and_same_binding(self):
        for prior in ({}, {'status':'failed'}, {'status':'verified','binding':'other'}):
            r=dns.observe_stopped(self.expect,prior,reader=self.reader)
            self.assertFalse(r['cleanup_verified']);self.assertEqual(r['classification'],'prior_identity_required')
    def test_gone_and_empty_config_verifies_cleanup(self):
        prior=self.running();self.reader.capture=None;self.reader.files.clear();self.reader.entries.clear()
        r=dns.observe_stopped(self.expect,prior,reader=self.reader)
        self.assertTrue(r['cleanup_verified']);self.assertEqual(r['classification'],'gone')
    def test_live_pid_without_pidfile_is_retained(self):
        prior=self.running();self.reader.files.clear();self.reader.entries.clear()
        r=dns.observe_stopped(self.expect,prior,reader=self.reader)
        self.assertEqual(r['classification'],'live_retained');self.assertFalse(r['cleanup_verified'])
    def test_pid_reuse_never_cleanup_pass(self):
        prior=self.running();self.reader.capture['start_ticks']=78
        self.reader.files.clear();self.reader.entries.clear()
        r=dns.observe_stopped(self.expect,prior,reader=self.reader)
        self.assertEqual(r['classification'],'pid_reused');self.assertFalse(r['cleanup_verified'])
    def test_stale_pidfile_and_remaining_config_distinguished(self):
        prior=self.running();self.reader.capture=None
        del self.reader.files[self.expect.entry];self.reader.entries.remove(self.expect.entry.name)
        r=dns.observe_stopped(self.expect,prior,reader=self.reader)
        self.assertEqual(r['classification'],'pidfile_retained')
        self.reader.files.pop(self.expect.pidfile);self.reader.entries.remove('aardvark.pid')
        self.reader.files[self.expect.entry]=b'private';self.reader.entries.add(self.expect.entry.name)
        r=dns.observe_stopped(self.expect,prior,reader=self.reader)
        self.assertEqual(r['classification'],'config_retained');self.assertFalse(r['cleanup_verified'])
    def test_replaced_pidfile_and_permission_fail_immediately(self):
        prior=self.running();self.reader.files[self.expect.pidfile]=b'9999'
        self.assertEqual(dns.observe_stopped(self.expect,prior,reader=self.reader)['classification'],'pidfile_changed')
        self.reader.files[self.expect.pidfile]=PermissionError()
        self.assertEqual(dns.observe_stopped(self.expect,prior,reader=self.reader)['status'],'unsupported')
    def test_factory_rejects_unbound_identity(self):
        for uid in (0,True,-1):
            with self.assertRaises(dns.ObservationError):
                dns.from_verified(ROOT,{'install_id':INSTALL,'bundle':{'path':str(BUNDLE/'bundle.json')}},
                    BUNDLE,{'files':[{'path':'runtime/helpers/aardvark-dns','sha256':HASH}]},uid)
    def test_proc_stat_parser_handles_parentheses_and_rejects_changed_identity(self):
        raw=b'1234 (aardvark (test)) S '+b'0 '*18+b'77 '+b'0 '*10
        self.assertEqual(dns.parse_stat(raw,1234),(77,'S'))
        with self.assertRaises(dns.ObservationError):dns.parse_stat(raw,9999)
        with self.assertRaises(dns.ObservationError):dns.parse_stat(raw.replace(b") S ",b") RS "),1234)
    def test_scoped_reader_only_never_runs_default_reader(self):
        with patch.object(dns,'FilesystemReader',side_effect=AssertionError('live filesystem forbidden')):
            self.assertEqual(self.running()['status'],'verified')

    def test_mapping_parser_is_bounded(self):
        self.assertEqual(dns.parse_map(b"0 1000 1\n1 100000 65536\n"),
                         [[0,1000,1],[1,100000,65536]])
        for raw in (b"",b"0 0 0",b"0 1",b"-1 1000 1",b"0 0 4294967297"):
            with self.subTest(raw=raw),self.assertRaises(dns.ObservationError):
                dns.parse_map(raw)
    def test_reader_cleanup_identity_anchors_directory_and_needs_no_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);raw=b"1234 (gone exe) Z "+b"0 "*18+b"77 "+b"0 "*10
            (path/"stat").write_bytes(raw)
            original=os.open; calls=[]
            def scoped_open(name,*args,**kwargs):
                calls.append((str(name),kwargs.get("dir_fd")))
                if str(name)=="/proc/1234":name=path
                elif str(name).startswith("/proc/"):raise AssertionError("live proc forbidden")
                return original(name,*args,**kwargs)
            with patch.object(dns.os,"open",side_effect=scoped_open):
                self.assertEqual(dns.FilesystemReader().identity(1234),
                                 {"pid":1234,"start_ticks":77})
            self.assertEqual(calls[0],("/proc/1234",None))
            self.assertTrue(all(name=="stat" and fd is not None for name,fd in calls[1:]))
            (path/"stat").unlink()
            with patch.object(dns.os,"open",side_effect=scoped_open),self.assertRaises(dns.ObservationError):
                dns.FilesystemReader().identity(1234)
    def test_reader_rejects_symlink_special_and_oversize_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);target=path/"file";target.write_bytes(b"12345")
            link=path/"link";link.symlink_to(target)
            reader=dns.FilesystemReader()
            with self.assertRaises(dns.ObservationError):reader.read(link,10)
            with self.assertRaises(dns.ObservationError):reader.read(target,4)
            os.mkfifo(path/"fifo")
            with self.assertRaises(dns.ObservationError):reader.read(path/"fifo",10)
    def test_config_changed_during_capture_fails(self):
        original=self.reader.process
        def change(pid):
            value=original(pid);self.reader.files[self.expect.entry]=b"changed";return value
        self.reader.process=change
        self.assertEqual(self.running()["classification"],"configuration_changed")
    def test_stop_identity_does_not_depend_on_readable_executable(self):
        prior=self.running()
        self.reader.capture["arguments"]=[]
        self.reader.capture["exe_path"]="/gone (deleted)"
        self.assertEqual(dns.observe_stopped(self.expect,prior,reader=self.reader)["classification"],
                         "live_retained")

    def test_proc_reader_ignores_status_counters_but_rejects_uid_drift(self):
        # Every /proc open is redirected to inert files; no real process observation.
        for changed_uid,changed_session in ((False,False),(True,False),(False,True)):
            with self.subTest(changed_uid=changed_uid,changed_session=changed_session),tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);process=base/"process";observer=base/"observer"
                process.mkdir();observer.mkdir()
                for directory in (process,observer):
                    (directory/"ns").mkdir()
                    for kind in ("net","user","mnt"):(directory/"ns"/kind).write_bytes(b"")
                binary=base/"binary";binary.write_bytes(b"inert executable fixture")
                (process/"exe").symlink_to(binary)
                raw=b"1234 (aardvark) S 1 1234 1234 "+b"0 "*15+b"77 "+b"0 "*10
                values={"stat":raw,"cmdline":b"fixed\0","uid_map":b"0 1000 1\n",
                        "gid_map":b"0 1000 1\n","cgroup":b"0::/user.slice\n",
                        "status":b"Uid:\t1000\t1000\t1000\t1000\nvoluntary_ctxt_switches:\t1\n"}
                for name,data in values.items():(process/name).write_bytes(data)
                original_open,original_link=os.open,os.readlink
                reads=0
                stat_reads=0
                def opened(name,*args,**kwargs):
                    nonlocal reads,stat_reads
                    if str(name)=="/proc/1234":name=process
                    elif str(name)=="/proc/self":name=observer
                    elif str(name).startswith("/proc/"):raise AssertionError("live proc forbidden")
                    if name=="stat":
                        stat_reads+=1
                        if stat_reads==2 and changed_session:
                            (process/"stat").write_bytes(raw.replace(b"S 1 1234 1234",b"S 1 1234 2000"))
                    if name=="status":
                        reads+=1
                        if reads==2:
                            uid=1001 if changed_uid else 1000
                            (process/"status").write_text("Uid:\t"+"\t".join([str(uid)]*4)+
                                "\nvoluntary_ctxt_switches:\t999\n")
                    return original_open(name,*args,**kwargs)
                def linked(name,*args,**kwargs):
                    if str(name).startswith("ns/"):return str(name)[3:]+":[900]"
                    return original_link(name,*args,**kwargs)
                with patch.object(dns.os,"open",side_effect=opened),patch.object(dns.os,"readlink",side_effect=linked):
                    if changed_uid or changed_session:
                        with self.assertRaisesRegex(dns.ObservationError,"process_changed"):
                            dns.FilesystemReader().process(1234)
                    else:
                        self.assertEqual(dns.FilesystemReader().process(1234)["uid"],[1000]*4)

    def test_host_namespace_placeholder_preserves_identity_without_acceptance(self):
        self.reader.metas[self.expect.netns]["dev"]=88
        prior=self.running()
        self.assertEqual(prior["status"],"unsupported")
        self.assertTrue(prior["identity_verified"])
        self.assertFalse(prior["namespace_binding_verified"])
        self.reader.capture=None;self.reader.files.clear();self.reader.entries.clear()
        stopped=dns.observe_stopped(self.expect,prior,reader=self.reader)
        self.assertEqual(stopped["status"],"unsupported")
        self.assertTrue(stopped["daemon_cleanup_verified"])
        self.assertFalse(stopped["cleanup_verified"])
    def test_missing_binding_preserves_identity_but_mismatch_cannot_authorize_cleanup(self):
        del self.reader.metas[self.expect.netns]
        self.assertEqual(self.running()["classification"],"namespace_binding_unavailable")
        self.reader.metas[self.expect.netns]=meta(stat.S_IFREG|0o444,999)
        prior=self.running()
        self.assertEqual(prior["classification"],"namespace_binding_mismatch")
        self.assertEqual(dns.observe_stopped(self.expect,prior,reader=self.reader)["classification"],
                         "prior_identity_required")

    def test_session_fields_are_observed_without_assuming_setsid_succeeded(self):
        self.reader.capture["pgrp"]=2000;self.reader.capture["session"]=2000
        observed=self.running()
        self.assertEqual(observed["status"],"verified")
        self.assertEqual(observed["identity"]["session"],2000)
        raw=b"1234 (daemon) S 1 1234 2000 "+b"0 "*15+b"77 "+b"0 "*10
        self.assertEqual(dns.parse_session(raw,1234),(1234,2000))
        with self.assertRaises(dns.ObservationError):
            dns.parse_session(raw.replace(b"S 1 1234",b"S 1 -1"),1234)

    def test_unavailable_namespace_never_downgrades_conclusive_cleanup_failure(self):
        self.reader.metas[self.expect.netns]["dev"]=88
        prior=self.running()
        for kind in ("live_retained","pid_reused","pidfile_retained","config_retained"):
            with self.subTest(kind=kind):
                self.reader=Fixture(self.expect)
                if kind=="pid_reused":self.reader.capture["start_ticks"]=78
                if kind in ("pidfile_retained","config_retained"):self.reader.capture=None
                if kind=="pidfile_retained":
                    del self.reader.files[self.expect.entry];self.reader.entries.remove(self.expect.entry.name)
                if kind=="config_retained":
                    del self.reader.files[self.expect.pidfile];self.reader.entries.remove("aardvark.pid")
                observed=dns.observe_stopped(self.expect,prior,reader=self.reader)
                self.assertEqual(observed["classification"],kind)
                self.assertEqual(observed["status"],"failed")
                self.assertFalse(observed["cleanup_verified"])

if __name__=='__main__':unittest.main()
