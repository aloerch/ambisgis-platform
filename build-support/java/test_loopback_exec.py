"""Real child-wrapper enforcement and failure-receipt regressions."""
import copy
import errno
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT=Path(__file__).with_name('loopback_exec.py')
spec=importlib.util.spec_from_file_location('loopback_exec',SCRIPT)
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def evaluate(nr,args=(),arch=0xc000003e):
    values={0:nr,4:arch,**{16+8*i:v & 0xffffffff for i,v in enumerate(args)}}
    pc=0;acc=0;program=runner.instructions()
    while pc<len(program):
        code,yes,no,k=program[pc]
        if code==0x20:acc=values.get(k,0)
        elif code==0x54:acc &= k
        elif code==0x15:pc+=yes if acc==k else no
        elif code==0x45:pc+=yes if acc & k else no
        elif code==0x06:return k
        else:raise AssertionError(code)
        pc+=1
    raise AssertionError('filter lacks terminal action')


class PolicyTests(unittest.TestCase):
    def test_filter_denies_alternate_connection_paths_and_device_changes(self):
        for nr,arguments in [(44,(1,0,0,runner.FASTOPEN,0,0)),(46,(1,0,runner.FASTOPEN)),(307,(1,0,0,runner.FASTOPEN)),(53,(socket.AF_UNIX,socket.SOCK_DGRAM,0)),(53,(socket.AF_UNIX,socket.SOCK_SEQPACKET,0)),(53,(socket.AF_INET,socket.SOCK_STREAM,0)),(53,(socket.AF_UNIX,socket.SOCK_STREAM,1)),(56,(0x10000000,)),(56,(0x8000,))]:
            with self.subTest(nr=nr,args=arguments):self.assertEqual(evaluate(nr,arguments),runner.DENY)
        for nr in (109,112,157,272,308,317,425,426,427,438):self.assertEqual(evaluate(nr),runner.DENY)
        for nr in (435,436):self.assertEqual(evaluate(nr),runner.ENOSYS)
        for nr in (41,42,49,54):self.assertEqual(evaluate(nr),runner.NOTIFY)
        self.assertEqual(evaluate(41,arch=0x40000003),runner.KILL)
        self.assertEqual(evaluate(0x40000029),runner.KILL)

    def test_filter_preserves_normal_stream_ipc_and_transport_flags(self):
        for flags in (0,socket.SOCK_CLOEXEC,socket.SOCK_NONBLOCK,socket.SOCK_CLOEXEC|socket.SOCK_NONBLOCK):
            self.assertEqual(evaluate(53,(socket.AF_UNIX,socket.SOCK_STREAM|flags,0)),runner.ALLOW)
        for nr,args in [(44,(1,0,0,0,0,0)),(46,(1,0,0)),(307,(1,0,0,0)),(56,(0x4111,)),(1,(1,0,0)),(3,(1,))]:
            self.assertEqual(evaluate(nr,args),runner.ALLOW)

    def test_probe_schema_rejects_missing_duplicate_failed_and_extra_results(self):
        valid={'schema_version':1,'parent':[{'id':p,'passed':True} for p in runner.probe_ids()],'exec_child':[{'id':p,'passed':True} for p in runner.probe_ids()]}
        self.assertTrue(runner.validate_probes(valid)['all_passed'])
        invalid=[]
        value=copy.deepcopy(valid);value['parent'].pop();invalid.append(value)
        value=copy.deepcopy(valid);value['exec_child'][0]=value['exec_child'][1];invalid.append(value)
        value=copy.deepcopy(valid);value['parent'][0]['passed']=False;invalid.append(value)
        value=copy.deepcopy(valid);value['parent'][0]['passed']=1;invalid.append(value)
        value=copy.deepcopy(valid);value['parent'][0]['ignored']='extra';invalid.append(value)
        invalid.extend([{},[],{'schema_version':1,'parent':[], 'exec_child':[]}])
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):runner.validate_probes(value)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ambisgis-loopback-test-')
        self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def execute(self,code='pass',timeout=10):
        evidence=self.root/'runtime.json'
        result=subprocess.run([sys.executable,str(SCRIPT),'--evidence',str(evidence),'--timeout',str(timeout),'--',sys.executable,'-c',code],capture_output=True,text=True,timeout=timeout+15)
        self.assertTrue(evidence.exists(),result.stderr)
        return result,json.loads(evidence.read_text())
    def injected(self,setup):
        evidence=self.root/'runtime.json';probes=self.root/'runtime.probes.json'
        code=f"import sys,os;sys.path.insert(0,{str(SCRIPT.parent)!r});import loopback_exec as m;os.environ['AMBISGIS_LOOPBACK_PROBES']={str(probes)!r}\n{setup}\nraise SystemExit(m.run(['/bin/true'],m.Path({str(evidence)!r}),10))"
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=25)
        self.assertTrue(evidence.exists(),result.stderr)
        return result,json.loads(evidence.read_text())

    def test_real_parent_exec_and_fork_probes_release_socket_descriptions(self):
        result,receipt=self.execute()
        self.assertEqual(result.returncode,0,result.stderr)
        checked=runner.verify_receipt(self.root/'runtime.json',0)
        self.assertEqual(checked['network_probes']['parent_probes'],len(runner.probe_ids()))
        self.assertEqual(receipt['broker_counts']['socket'],receipt['broker_counts']['released'])

    def test_last_close_after_fork_keeps_child_listener_usable(self):
        code='''import os,socket
s=socket.socket();s.bind(('127.0.0.1',0));s.listen(1);endpoint=s.getsockname()
r,w=os.pipe();child=os.fork()
if child==0:
 os.close(w);os.read(r,1);s.settimeout(2);peer,_=s.accept();peer.sendall(b'ok');peer.close();s.close();os._exit(0)
s.close();os.close(r);os.write(w,b'x');os.close(w)
with socket.socket() as c:
 c.settimeout(2);c.connect(endpoint);assert c.recv(2)==b'ok'
_,status=os.waitpid(child,0);assert os.waitstatus_to_exitcode(status)==0
'''
        result,receipt=self.execute(code)
        self.assertEqual(result.returncode,0,result.stderr)
        runner.verify_receipt(self.root/'runtime.json',0)

    def test_worker_thread_applies_socket_options_to_accepted_stream(self):
        code="""import socket,threading
with socket.socket() as listener:
 listener.bind(('127.0.0.1',0));listener.listen(1)
 errors=[]
 def client():
  try:
   with socket.socket() as c:
    c.connect(listener.getsockname());c.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
    assert c.recv(2)==b'ok'
  except BaseException as e:errors.append(str(e))
 t=threading.Thread(target=client);t.start()
 peer,_=listener.accept()
 with peer:
  peer.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);peer.sendall(b'ok')
 t.join(3);assert not t.is_alive() and not errors,errors
"""
        result,receipt=self.execute(code)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertGreater(receipt['broker_counts']['pidfd_copies'],0)
        self.assertEqual(receipt['datagram_packets_received'],0)
        self.assertTrue(receipt['datagram_sentinels_closed'])

    def test_successful_command_cannot_leave_grandchild_running(self):
        child_file=self.root/'child.pid'
        code=f"import os,time; child=os.fork();open({str(child_file)!r},'w').write(str(child)) if child else None;time.sleep(60) if child==0 else None"
        result,receipt=self.execute(code)
        self.assertEqual(result.returncode,0,result.stderr)
        pid=int(child_file.read_text());self.assertFalse(Path(f'/proc/{pid}').exists())
        self.assertTrue(receipt['task_process_group_stopped'])
        self.assertIn(pid,[item['pid'] for item in receipt['reaped_descendants']])

    def test_timeout_is_failed_and_group_stopped(self):
        result,receipt=self.execute('import time;time.sleep(60)',timeout=1)
        self.assertEqual(result.returncode,125,result.stderr)
        self.assertEqual(receipt['status'],'failed');self.assertTrue(receipt['task_process_group_stopped'])
        self.assertTrue(any(e['type']=='TimeoutError' for e in receipt['errors']))
        with self.assertRaises(RuntimeError):runner.verify_receipt(self.root/'runtime.json',0)

    def test_sigterm_retains_failed_receipt_and_cleans_descendant(self):
        evidence=self.root/'runtime.json';child_file=self.root/'child.pid'
        code=f"import os,time;open({str(child_file)!r},'w').write(str(os.getpid()));time.sleep(60)"
        process=subprocess.Popen([sys.executable,str(SCRIPT),'--evidence',str(evidence),'--','/usr/bin/python3','-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            until=time.monotonic()+10
            while not child_file.exists() and process.poll() is None and time.monotonic()<until:time.sleep(.01)
            self.assertTrue(child_file.exists())
            process.send_signal(signal.SIGTERM);stdout,stderr=process.communicate(timeout=10)
            self.assertEqual(process.returncode,125,stderr)
            receipt=json.loads(evidence.read_text());self.assertTrue(receipt['task_process_group_stopped'])
            self.assertFalse(Path('/proc/'+child_file.read_text()).exists())
            self.assertTrue(any(e['type']=='InterruptedError' for e in receipt['errors']))
        finally:
            if process.poll() is None:process.kill();process.communicate()

    def test_nonzero_command_exit_is_preserved(self):
        result,receipt=self.execute('raise SystemExit(17)')
        self.assertEqual(result.returncode,17,result.stderr)
        self.assertEqual(receipt['command_exit_code'],17)
        runner.verify_receipt(self.root/'runtime.json',17)
        with self.assertRaises(RuntimeError):runner.verify_receipt(self.root/'runtime.json',0)

    def test_missing_or_tampered_probe_evidence_cannot_report_success(self):
        code="import os;os.unlink(os.environ['AMBISGIS_LOOPBACK_PROBES'])"
        result,receipt=self.execute(code)
        self.assertEqual(result.returncode,125,result.stderr)
        self.assertEqual(receipt['command_exit_code'],0)
        self.assertEqual(receipt['status'],'failed')

    def test_preflight_failure_still_has_unsuccessful_receipt(self):
        result,receipt=self.injected("def fail():raise RuntimeError('injected preflight')\nm.check_platform=fail")
        self.assertEqual(result.returncode,125,result.stderr)
        self.assertIsNone(receipt['command_exit_code']);self.assertEqual(receipt['errors'][0]['stage'],'preflight')

    def test_cleanup_failure_overrides_command_success(self):
        result,receipt=self.injected("original=m.Broker.close\ndef fail(self):\n original(self)\n raise OSError('injected close failure')\nm.Broker.close=fail")
        self.assertEqual(result.returncode,125,result.stderr)
        self.assertEqual(receipt['command_exit_code'],0);self.assertFalse(receipt['broker_sockets_closed'])
        self.assertTrue(any(e['stage']=='socket-cleanup' for e in receipt['errors']))

    def test_shutdown_verification_failure_overrides_command_success(self):
        result,receipt=self.injected("original=m.stop_group\ndef fail(*args,**kwargs):\n original(*args,**kwargs)\n raise RuntimeError('injected shutdown verification failure')\nm.stop_group=fail")
        self.assertEqual(result.returncode,125,result.stderr)
        self.assertEqual(receipt['command_exit_code'],0);self.assertFalse(receipt['task_process_group_stopped'])
        self.assertTrue(any(e['stage']=='process-cleanup' for e in receipt['errors']))

    def test_external_verifier_rejects_changed_probe_bytes(self):
        result,receipt=self.execute();self.assertEqual(result.returncode,0,result.stderr)
        Path(receipt['probe_receipt']['path']).write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'changed'):runner.verify_receipt(self.root/'runtime.json',0)

if __name__=='__main__':unittest.main()
