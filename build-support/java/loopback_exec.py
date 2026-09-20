#!/usr/bin/env python3
"""Trusted fixture runner: brokered loopback TCP, no host security changes.

Linux x86_64 only. Internet sockets are created by this unprivileged parent,
bound to device lo before atomic seccomp ADDFD injection. bind/connect use a
copied, validated loopback sockaddr and never CONTINUE. The supervisor duplicates
the notifying thread's actual socket, performs the operation and closes its copy.
UDP descriptors are permanently shut down for interface ioctls only; all their
bind/connect/setsockopt calls are denied. Other families, socket import/tracing/io_uring,
FASTOPEN and changing the device restriction are denied. AF_UNIX stream
socketpairs provide anonymous IPC. This is not a hostile-code, filesystem or
process sandbox and does not restrict which existing loopback services may be
contacted. Use only trusted fixture commands with disposable credentials.
"""
import argparse
import array
import ctypes as C
import errno
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'postgis'))
from offline_exec import SockFilter, SockFprog, check_platform, close_inherited_descriptors

LIB = C.CDLL(None, use_errno=True)
ALLOW, DENY, NOTIFY, KILL = 0x7fff0000, 0x50000 | errno.EPERM, 0x7fc00000, 0x80000000
ENOSYS = 0x50000 | errno.ENOSYS
FASTOPEN = 0x20000000
SO_BINDTOIFINDEX = 62

class Data(C.Structure):
    _fields_ = [('nr', C.c_int), ('arch', C.c_uint), ('ip', C.c_ulonglong), ('args', C.c_ulonglong * 6)]
class Request(C.Structure):
    _fields_ = [('id', C.c_ulonglong), ('pid', C.c_uint), ('flags', C.c_uint), ('data', Data)]
class Response(C.Structure):
    _fields_ = [('id', C.c_ulonglong), ('value', C.c_longlong), ('error', C.c_int), ('flags', C.c_uint)]
class AddFD(C.Structure):
    _fields_ = [('id', C.c_ulonglong), ('flags', C.c_uint), ('srcfd', C.c_uint), ('newfd', C.c_uint), ('newfd_flags', C.c_uint)]
class IOVec(C.Structure):
    _fields_ = [('base', C.c_void_p), ('length', C.c_size_t)]


def ioctl(fd, number, obj):
    result = LIB.ioctl(fd, C.c_ulong(number), C.byref(obj))
    if result < 0:
        number = C.get_errno()
        raise OSError(number, os.strerror(number))
    return result


def instructions():
    p = [(0x20,0,0,4),(0x15,1,0,0xc000003e),(0x06,0,0,KILL),
         (0x20,0,0,0),(0x45,0,1,0x40000000),(0x06,0,0,KILL)]
    # Prevent group/session escape, new filters, namespaces, socket import,
    # tracing and alternate io_uring networking. clone3/close_range use ENOSYS
    # so libc falls back to clone / individually observed close operations.
    for nr in (101,109,112,157,272,308,317,425,426,427,438):
        p += [(0x15,0,1,nr),(0x06,0,0,DENY)]
    for nr in (435,436):
        p += [(0x15,0,1,nr),(0x06,0,0,ENOSYS)]
    for nr in (41,42,49,54):
        p += [(0x15,0,1,nr),(0x06,0,0,NOTIFY)]
    # clone: namespaces and CLONE_PARENT are unnecessary for fixture children.
    p += [(0x15,0,4,56),(0x20,0,0,16),(0x45,0,1,0x7e028000),
          (0x06,0,0,DENY),(0x06,0,0,ALLOW)]
    # sendto/sendmsg/sendmmsg must not connect implicitly through TCP Fast Open.
    for nr,offset in ((44,40),(46,32),(307,40)):
        p += [(0x15,0,4,nr),(0x20,0,0,offset),(0x45,0,1,FASTOPEN),
              (0x06,0,0,DENY),(0x06,0,0,ALLOW)]
    # Anonymous AF_UNIX SOCK_STREAM pairs only, with normal CLOEXEC/NONBLOCK
    # flags and protocol zero. Datagram pairs can address external Unix peers.
    pair=[(0x20,0,0,16),(0x15,1,0,socket.AF_UNIX),(0x06,0,0,DENY),
          (0x20,0,0,24),(0x54,0,0,0xffffffff ^ (socket.SOCK_CLOEXEC|socket.SOCK_NONBLOCK)),
          (0x15,1,0,socket.SOCK_STREAM),(0x06,0,0,DENY),
          (0x20,0,0,32),(0x15,1,0,0),(0x06,0,0,DENY),(0x06,0,0,ALLOW)]
    p += [(0x15,0,len(pair),53),*pair]
    p += [(0x15,0,6,54),(0x20,0,0,24),(0x15,0,4,1),(0x20,0,0,32),
          (0x15,1,0,25),(0x15,0,1,SO_BINDTOIFINDEX),(0x06,0,0,DENY),(0x06,0,0,ALLOW)]
    return p


def install():
    check_platform()
    sizes = (C.c_ushort * 3)()
    if LIB.syscall(317,3,0,C.byref(sizes)) or tuple(sizes) != (C.sizeof(Request),C.sizeof(Response),C.sizeof(Data)):
        raise RuntimeError('unsupported seccomp notification structure sizes')
    program = (SockFilter * len(instructions()))(*(SockFilter(*r) for r in instructions()))
    descriptor = SockFprog(len(program),program)
    if LIB.prctl(38,1,0,0,0):
        raise OSError(C.get_errno(), 'no_new_privs failed')
    fd = LIB.syscall(317,1,8,C.byref(descriptor))
    if fd < 0:
        raise OSError(C.get_errno(), 'seccomp notification installation failed')
    return fd


def address(pid, ptr, size):
    if size not in (16,28):
        raise OSError(errno.EPERM, 'unsupported sockaddr')
    buf = C.create_string_buffer(size)
    local, remote = IOVec(C.addressof(buf),size), IOVec(ptr,size)
    result = LIB.process_vm_readv(pid,C.byref(local),1,C.byref(remote),1,0)
    if result != size:
        raise OSError(errno.EFAULT, 'cannot copy complete sockaddr')
    raw = bytes(buf)
    family = int.from_bytes(raw[:2],sys.byteorder)
    port = int.from_bytes(raw[2:4],'big')
    if family == socket.AF_INET and size == 16:
        host = socket.inet_ntop(family,raw[4:8]); value = (host,port)
    elif family == socket.AF_INET6 and size == 28:
        host = socket.inet_ntop(family,raw[8:24])
        value = (host,port,0,int.from_bytes(raw[24:28],sys.byteorder))
    else:
        raise OSError(errno.EPERM, 'unsupported sockaddr family')
    ip = ipaddress.ip_address(host)
    effective = ip.ipv4_mapped if isinstance(ip,ipaddress.IPv6Address) and ip.ipv4_mapped else ip
    if not effective.is_loopback:
        raise OSError(errno.EPERM, 'non-loopback endpoint refused')
    return family,value


def group_members(pgid):
    """Read only this task's group; disappearing processes are expected."""
    found={}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal(): continue
        try: fields=(entry/'stat').read_text().rsplit(')',1)[1].split()
        except (FileNotFoundError,ProcessLookupError): continue
        if int(fields[2])==pgid: found[int(entry.name)]=fields[0]
    return found


def copied_socket(pid,fd):
    """Duplicate the notifying thread's OFD; Linux PIDFD_THREAD is O_EXCL."""
    pidfd=os.pidfd_open(pid,os.O_EXCL)
    try:
        duplicate=LIB.syscall(438,pidfd,int(fd),0)
        if duplicate<0:raise OSError(C.get_errno(),'cannot duplicate notifying thread socket')
    finally:os.close(pidfd)
    try:return socket.socket(fileno=duplicate)
    except BaseException:os.close(duplicate);raise


def copied_bytes(pid,pointer,size):
    if size>4096:raise OSError(errno.EPERM,'bounded socket option length exceeded')
    data=C.create_string_buffer(size)
    local,remote=IOVec(C.addressof(data),size),IOVec(pointer,size)
    if LIB.process_vm_readv(pid,C.byref(local),1,C.byref(remote),1,0)!=size:
        raise OSError(errno.EFAULT,'cannot copy complete socket option')
    return bytes(data)


def check_stream(s):
    if s.type & 0xf != socket.SOCK_STREAM or s.family not in (socket.AF_INET,socket.AF_INET6,socket.AF_UNIX):
        raise OSError(errno.EPERM,'ioctl-only datagram traffic/options are forbidden')
    if s.family!=socket.AF_UNIX and s.getsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,16)!=b'lo\0':
        raise OSError(errno.EPERM,'socket device restriction is missing')


class Broker:
    def __init__(self,fd,pgid):
        self.fd=fd;self.pgid=pgid
        self.counts={'socket':0,'bind':0,'connect':0,'setsockopt':0,'denied':0,'released':0,'ioctl_only_datagram':0,'pidfd_copies':0}

    def handle(self):
        req=Request()
        try:ioctl(self.fd,0xc0502100,req)
        except OSError as e:
            if e.errno in (errno.EINTR,errno.ENOENT):return
            raise
        response=Response(req.id,0,0,0);args=req.data.args
        try:
            if req.data.nr==41:
                family,kind,protocol=map(int,args[:3]);base_kind=kind & 0xf
                allowed_kind=socket.SOCK_STREAM|socket.SOCK_DGRAM|socket.SOCK_CLOEXEC|socket.SOCK_NONBLOCK
                allowed_protocol=(0,socket.IPPROTO_TCP) if base_kind==socket.SOCK_STREAM else (0,socket.IPPROTO_UDP)
                if family not in (socket.AF_INET,socket.AF_INET6) or base_kind not in (socket.SOCK_STREAM,socket.SOCK_DGRAM) or kind & ~allowed_kind or protocol not in allowed_protocol:
                    raise OSError(errno.EPERM,'only TCP and ioctl-only UDP descriptor types are permitted')
                with socket.socket(family,kind,protocol) as s:
                    s.setsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,b'lo\0')
                    if s.getsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,16)!=b'lo\0':raise RuntimeError('device enforcement failed')
                    if base_kind==socket.SOCK_DGRAM:
                        # Linux sets both shutdown flags before reporting that an
                        # unconnected UDP socket has no peer. Mandatory probes
                        # require addressed sends to fail before Java may start.
                        try:s.shutdown(socket.SHUT_RDWR)
                        except OSError as exc:
                            if exc.errno!=errno.ENOTCONN:raise
                        self.counts['ioctl_only_datagram']+=1
                    ioctl(self.fd,0x40182103,AddFD(req.id,2,s.fileno(),0,os.O_CLOEXEC if kind & socket.SOCK_CLOEXEC else 0))
                    self.counts['socket']+=1
                self.counts['released']+=1
                return
            elif req.data.nr in (42,49,54):
                ioctl(self.fd,0x40082102,C.c_ulonglong(req.id))
                with copied_socket(req.pid,args[0]) as s:
                    self.counts['pidfd_copies']+=1
                    check_stream(s)
                    if req.data.nr==54:
                        level,option=int(args[1]),int(args[2])
                        if level==socket.SOL_SOCKET and option in (socket.SO_BINDTODEVICE,SO_BINDTOIFINDEX):
                            raise OSError(errno.EPERM,'device restriction changes are forbidden')
                        value=copied_bytes(req.pid,args[3],args[4])
                        ioctl(self.fd,0x40082102,C.c_ulonglong(req.id))
                        s.setsockopt(level,option,value);self.counts['setsockopt']+=1
                    else:
                        family,endpoint=address(req.pid,args[1],args[2])
                        if s.family!=family:raise OSError(errno.EPERM,'socket address family mismatch')
                        ioctl(self.fd,0x40082102,C.c_ulonglong(req.id))
                        if req.data.nr==49:s.bind(endpoint);self.counts['bind']+=1
                        else:
                            signal.setitimer(signal.ITIMER_REAL,2)
                            try:result=s.connect_ex(endpoint)
                            finally:signal.setitimer(signal.ITIMER_REAL,0)
                            response.error=-result;self.counts['connect']+=1
            else:raise RuntimeError('unexpected broker syscall')
        except OSError as e:response.error=-(e.errno or errno.EPERM);self.counts['denied']+=1
        try:ioctl(self.fd,0xc0182101,response)
        except OSError as e:
            if e.errno!=errno.ENOENT:raise

    def close(self):os.close(self.fd)


def alarm(_signum,_frame):
    raise OSError(errno.ETIMEDOUT,'bounded broker connect timed out')


def interrupted(signum,_frame):
    raise InterruptedError(f'runner received signal {signum}')


def stop_group(pid,deadline=5,leader_reaped=False):
    """Kill only our new group, reap adopted descendants, verify disappearance."""
    reaped=[];until=time.monotonic()+deadline
    try:os.killpg(pid,signal.SIGKILL)
    except ProcessLookupError:pass
    # If child preflight failed before setsid(), it still shares our old group.
    if not leader_reaped:
        try:os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass
    while True:
        for target in (pid,-pid):
            while True:
                try:ended,status=os.waitpid(target,os.WNOHANG)
                except ChildProcessError:break
                if not ended:break
                reaped.append({'pid':ended,'exit_code':os.waitstatus_to_exitcode(status)})
                if target>0:break
        members=group_members(pid)
        if not members:return reaped
        if time.monotonic()>until:raise RuntimeError('task process group failed to stop: '+str(members))
        try:os.killpg(pid,signal.SIGKILL)
        except ProcessLookupError:pass
        time.sleep(.01)


class Message(C.Structure):
    _fields_=[('name',C.c_void_p),('namelen',C.c_uint),('iov',C.POINTER(IOVec)),('iovlen',C.c_size_t),('control',C.c_void_p),('controllen',C.c_size_t),('flags',C.c_int)]
class MultiMessage(C.Structure):
    _fields_=[('message',Message),('length',C.c_uint)]


def datagram_probe_names():
    return (['device-bound','interface-ioctl']+
            [f'{stage}-{operation}' for stage in ('before','after') for operation in ('sendto','sendmsg','sendmmsg','send','write','writev')]+
            ['bind-denied','connect-denied','options-denied','membership-denied','fork-send-denied'])


def datagram_probes(family):
    rows=[];prefix=family.name+':ioctl-only:'
    host,label=('127.0.0.1','4') if family==socket.AF_INET else ('::1','6')
    endpoint=(host,int(os.environ['AMBISGIS_LOOPBACK_UDP'+label]))
    def passed(name):rows.append({'id':prefix+name,'passed':True})
    def denied(name,action,error):
        try:action()
        except OSError as exc:actual=exc.errno
        else:actual=0
        if actual!=error:raise RuntimeError(f'{prefix}{name}: expected errno {error}, got {actual}')
        passed(name)
    def sendmmsg(s):
        payload=C.create_string_buffer(b'fixture');iov=IOVec(C.addressof(payload),7)
        raw=struct.pack('=H',family)+struct.pack('!H',endpoint[1])
        raw += socket.inet_pton(family,host)+b'\0'*8 if family==socket.AF_INET else b'\0'*4+socket.inet_pton(family,host)+b'\0'*4
        address=C.create_string_buffer(raw)
        message=MultiMessage(Message(C.addressof(address),len(raw),C.pointer(iov),1,None,0,0),0)
        result=LIB.sendmmsg(s.fileno(),C.byref(message),1,0)
        if result<0:raise OSError(C.get_errno(),os.strerror(C.get_errno()))
        return result
    with socket.socket(family,socket.SOCK_DGRAM) as s:
        if s.getsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,16)!=b'lo\0':raise RuntimeError('ioctl descriptor device restriction missing')
        passed('device-bound')
        fcntl.ioctl(s,0x8913,struct.pack('16sH14x',b'lo',0));passed('interface-ioctl')
        for stage in ('before','after'):
            for name,action in [('sendto',lambda:s.sendto(b'fixture',endpoint)),('sendmsg',lambda:s.sendmsg([b'fixture'],[],0,endpoint)),('sendmmsg',lambda:sendmmsg(s)),('send',lambda:s.send(b'fixture')),('write',lambda:os.write(s.fileno(),b'fixture')),('writev',lambda:os.writev(s.fileno(),[b'fixture']))]:
                denied(stage+'-'+name,action,errno.EPIPE if name in ('sendto','sendmsg','sendmmsg') else errno.EDESTADDRREQ)
            if stage=='before':
                denied('bind-denied',lambda:s.bind((host,0)),errno.EPERM)
                denied('connect-denied',lambda:s.connect(endpoint),errno.EPERM)
        denied('options-denied',lambda:s.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,8192),errno.EPERM)
        level,option=(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP) if family==socket.AF_INET else (socket.IPPROTO_IPV6,socket.IPV6_JOIN_GROUP)
        denied('membership-denied',lambda:s.setsockopt(level,option,b'\0'*20),errno.EPERM)
        child=os.fork()
        if child==0:
            try:
                denied('fork-send-denied',lambda:s.sendto(b'fixture',endpoint),errno.EPIPE);os._exit(0)
            except BaseException:os._exit(1)
        _,status=os.waitpid(child,0)
        if os.waitstatus_to_exitcode(status):raise RuntimeError('forked ioctl-only descriptor transmitted')
        passed('fork-send-denied')
    return rows


def probe_ids():
    result=[]
    for family in ('AF_INET','AF_INET6'):
        result += [f'{family}:loopback-transfer',f'{family}:close-eof',f'{family}:dup-close',f'{family}:reuse-port']
        hosts=('192.0.2.1','0.0.0.0') if family=='AF_INET' else ('2001:db8::1','::','::ffff:192.0.2.1','::ffff:0.0.0.0')
        result += [f'{family}:{op}:{host}' for host in hosts for op in ('bind','connect')]
    result += ['AF_INET6:mapped-loopback','socket-unix','socket-raw','accepted-stream-option',
               'unix-stream-pair','unix-datagram-pair','unix-seqpacket-pair','device-bound',
               'deny-bind-device','deny-bind-ifindex','deny-fastopen-sendto','deny-fastopen-sendmsg',
               'deny-fastopen-sendmmsg','deny-setsid','deny-setpgid','deny-close-range','deny-clone3',
               'deny-seccomp','deny-io-uring','deny-pidfd-getfd','fork-inheritance']
    result += [f'{family}:ioctl-only:{operation}' for family in ('AF_INET','AF_INET6') for operation in datagram_probe_names()]
    return result


def validate_probes(value):
    if not isinstance(value,dict) or set(value)!={'schema_version','parent','exec_child'} or value['schema_version']!=1:
        raise RuntimeError('invalid network-probe receipt envelope')
    expected=set(probe_ids())
    for stage in ('parent','exec_child'):
        rows=value[stage]
        if not isinstance(rows,list) or len(rows)!=len(expected):raise RuntimeError('incomplete network-probe receipt')
        if any(not isinstance(r,dict) or set(r)!={'id','passed'} or r['passed'] is not True or not isinstance(r['id'],str) for r in rows):
            raise RuntimeError('invalid network-probe result')
        if {r['id'] for r in rows}!=expected:raise RuntimeError('network-probe identities differ')
    return {'schema_version':1,'parent_probes':len(expected),'exec_child_probes':len(expected),'all_passed':True}


def run(command,evidence,timeout=1200):
    report={'schema_version':1,'mechanism':'seccomp notification + copied loopback bind/connect + SO_BINDTODEVICE lo',
            'status':'refused','result_exit_code':125,'command':command,'command_exit_code':None,
            'limitations':['trusted test runner, not hostile-code/filesystem/process isolation',
                          'all existing loopback services remain reachable; use disposable fixture credentials only',
                          'TCP transport only; UDP descriptors support interface ioctls with all transmission/options disabled',
                          'requires Linux PIDFD_THREAD and parent pidfd_getfd; every duplicated descriptor is closed immediately']}
    broker=None;pid=None;left=right=None;old_signals={};subreaper=None;errors=[];leader_reaped=False;sentinels=[]
    started=time.monotonic()
    try:
        report['runner_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        check_platform()
        report['closed_inherited_fds']=close_inherited_descriptors()
    except BaseException as exc:errors.append({'stage':'preflight','type':type(exc).__name__,'message':str(exc)})
    try:out=evidence.open('x')
    except BaseException as exc:
        report['errors']=errors+[{'stage':'evidence-open','type':type(exc).__name__,'message':str(exc)}]
        print(json.dumps(report),file=sys.stderr);return 125
    with out:
        try:
            if errors:raise RuntimeError('preflight failed; command not started')
            if timeout<=0:raise ValueError('timeout must be positive')
            previous=C.c_int()
            if LIB.prctl(37,C.byref(previous),0,0,0) or LIB.prctl(36,1,0,0,0):raise OSError(C.get_errno(),'subreaper setup failed')
            subreaper=previous.value
            for sig,handler in ((signal.SIGALRM,alarm),(signal.SIGTERM,interrupted)):
                old_signals[sig]=signal.signal(sig,handler)
            # These two private supervisor receivers detect any UDP probe leak.
            # Children close inherited copies before installing the filter.
            for family,host,label in ((socket.AF_INET,'127.0.0.1','4'),(socket.AF_INET6,'::1','6')):
                sentinel=socket.socket(family,socket.SOCK_DGRAM);sentinels.append(sentinel)
                sentinel.setsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,b'lo\0')
                sentinel.bind((host,0));sentinel.setblocking(False)
                os.environ['AMBISGIS_LOOPBACK_UDP'+label]=str(sentinel.getsockname()[1])
            left,right=socket.socketpair();left.settimeout(5)
            pid=os.fork()
            if pid==0:
                try:
                    left.close();out.close()
                    for sentinel in sentinels:sentinel.close()
                    os.setsid()
                    fd=install()
                    right.sendmsg([b'listener'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
                    right.close();os.close(fd)
                    os.execvpe(sys.executable,[sys.executable,str(Path(__file__).resolve()),'--child',*command],os.environ)
                except BaseException as exc:
                    print(f'loopback child preflight: {type(exc).__name__}: {exc}',file=sys.stderr);os._exit(125)
            right.close();right=None
            message,ancillary,flags,_=left.recvmsg(32,socket.CMSG_SPACE(4));left.close();left=None
            if message!=b'listener' or flags or len(ancillary)!=1 or ancillary[0][:2]!=(socket.SOL_SOCKET,socket.SCM_RIGHTS):
                raise RuntimeError('invalid seccomp listener transfer')
            fds=array.array('i');fds.frombytes(ancillary[0][2])
            if len(fds)!=1:
                for fd in fds:os.close(fd)
                raise RuntimeError('unexpected listener count')
            broker=Broker(fds[0],pid)
            poll=select.poll();poll.register(broker.fd,select.POLLIN)
            while True:
                ended,status=os.waitpid(pid,os.WNOHANG)
                if ended:
                    report['command_exit_code']=os.waitstatus_to_exitcode(status);leader_reaped=True;break
                if time.monotonic()-started>timeout:raise TimeoutError('controlled runtime deadline exceeded')
                for _,event in poll.poll(100):
                    if event & select.POLLIN:broker.handle()
            probe_path=Path(os.environ['AMBISGIS_LOOPBACK_PROBES'])
            probe_bytes=probe_path.read_bytes()
            report['network_probes']=validate_probes(json.loads(probe_bytes))
            report['probe_receipt']={'path':str(probe_path),'sha256':hashlib.sha256(probe_bytes).hexdigest()}
            report['result_exit_code']=report['command_exit_code'] if report['command_exit_code']>=0 else 128-report['command_exit_code']
            report['status']='completed'
        except BaseException as exc:errors.append({'stage':'execution','type':type(exc).__name__,'message':str(exc)})
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            if pid:
                try:
                    report['reaped_descendants']=stop_group(pid,leader_reaped=leader_reaped)
                    report['task_process_group_stopped']=True
                except BaseException as exc:
                    report['task_process_group_stopped']=False
                    errors.append({'stage':'process-cleanup','type':type(exc).__name__,'message':str(exc)})
            for endpoint in (left,right):
                if endpoint is not None:
                    try:endpoint.close()
                    except BaseException as exc:errors.append({'stage':'transfer-cleanup','type':type(exc).__name__,'message':str(exc)})
            report['datagram_packets_received']=0
            report['datagram_sentinels_closed']=True
            for sentinel in sentinels:
                try:
                    try:
                        sentinel.recv(65536);report['datagram_packets_received']+=1
                        raise RuntimeError('ioctl-only datagram probe transmitted a packet')
                    except BlockingIOError:pass
                except BaseException as exc:errors.append({'stage':'datagram-enforcement','type':type(exc).__name__,'message':str(exc)})
                finally:
                    try:sentinel.close()
                    except BaseException as exc:
                        report['datagram_sentinels_closed']=False
                        errors.append({'stage':'datagram-cleanup','type':type(exc).__name__,'message':str(exc)})
            if broker:
                report['broker_counts']=broker.counts
                try:broker.close();report['broker_sockets_closed']=True
                except BaseException as exc:
                    report['broker_sockets_closed']=False
                    errors.append({'stage':'socket-cleanup','type':type(exc).__name__,'message':str(exc)})
            if subreaper is not None and LIB.prctl(36,subreaper,0,0,0):errors.append({'stage':'subreaper-restore','message':os.strerror(C.get_errno())})
            for sig,handler in old_signals.items():signal.signal(sig,handler)
            if errors:report.update(status='failed',result_exit_code=125,errors=errors)
            report['duration_seconds']=round(time.monotonic()-started,3)
            try:json.dump(report,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
            except BaseException as exc:
                report.update(status='failed',result_exit_code=125)
                report.setdefault('errors',[]).append({'stage':'evidence-write','type':type(exc).__name__,'message':str(exc)})
                print(json.dumps(report),file=sys.stderr)
    return report['result_exit_code']


def verify_receipt(path,expected_exit):
    """Require truthful completion, independently checked probes and cleanup."""
    receipt=json.loads(Path(path).read_text())
    if (receipt.get('schema_version')!=1 or receipt.get('status')!='completed'
            or type(expected_exit) is not int
            or receipt.get('command_exit_code')!=expected_exit
            or receipt.get('result_exit_code')!=expected_exit
            or receipt.get('task_process_group_stopped') is not True
            or receipt.get('broker_sockets_closed') is not True
            or receipt.get('datagram_sentinels_closed') is not True
            or receipt.get('datagram_packets_received')!=0
            or receipt.get('errors')):
        raise RuntimeError('controlled-runtime receipt does not prove successful execution and cleanup')
    evidence=receipt.get('probe_receipt')
    if not isinstance(evidence,dict) or set(evidence)!={'path','sha256'}:
        raise RuntimeError('controlled-runtime probe evidence is missing')
    raw=Path(evidence['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=evidence['sha256']:
        raise RuntimeError('controlled-runtime probe evidence changed')
    validated=validate_probes(json.loads(raw))
    if receipt.get('network_probes')!=validated:
        raise RuntimeError('controlled-runtime probe summary differs')
    return receipt


def probes():
    rows=[]
    def passed(ident):rows.append({'id':ident,'passed':True})
    def denied(ident,action,expected=errno.EPERM):
        try:action()
        except OSError as exc:number=exc.errno
        else:number=0
        if number!=expected:raise RuntimeError(f'{ident}: expected errno {expected}, got {number}')
        passed(ident)
    def syscall(nr,*args):
        result=LIB.syscall(nr,*args)
        if result<0:raise OSError(C.get_errno(),os.strerror(C.get_errno()))
        return result
    for family,host in ((socket.AF_INET,'127.0.0.1'),(socket.AF_INET6,'::1')):
        prefix=family.name
        with socket.socket(family,socket.SOCK_STREAM) as server:
            server.bind((host,0));server.listen(2);endpoint=server.getsockname()
            with socket.socket(family,socket.SOCK_STREAM) as client:
                client.settimeout(2);client.connect(endpoint);peer,_=server.accept()
                with peer:
                    peer.settimeout(2);client.sendall(b'fixture')
                    if peer.recv(7)!=b'fixture':raise RuntimeError('loopback transfer failed')
                    passed(prefix+':loopback-transfer')
                    duplicate=socket.socket(fileno=os.dup(client.fileno()))
                    client.close();duplicate.sendall(b'dup')
                    if peer.recv(3)!=b'dup':raise RuntimeError('duplicate socket stopped after original close')
                    passed(prefix+':dup-close');duplicate.close()
                    if peer.recv(1)!=b'':raise RuntimeError('last target close did not produce EOF')
                    passed(prefix+':close-eof')
        # No accepted connection is left here. Reuse tests the listening port.
        with socket.socket(family,socket.SOCK_STREAM) as listener:
            listener.bind((host,0));port=listener.getsockname();listener.listen(1)
        with socket.socket(family,socket.SOCK_STREAM) as listener:listener.bind(port)
        passed(prefix+':reuse-port')
        hosts=('192.0.2.1','0.0.0.0') if family==socket.AF_INET else ('2001:db8::1','::','::ffff:192.0.2.1','::ffff:0.0.0.0')
        for forbidden in hosts:
            for op in ('bind','connect'):
                with socket.socket(family,socket.SOCK_STREAM) as s:
                    s.settimeout(1);denied(f'{prefix}:{op}:{forbidden}',lambda:getattr(s,op)((forbidden,9)))
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as server:
        server.bind(('127.0.0.1',0));server.listen(1)
        with socket.socket(socket.AF_INET6,socket.SOCK_STREAM) as client:
            client.settimeout(2);client.connect(('::ffff:127.0.0.1',server.getsockname()[1]))
            peer,_=server.accept()
            with peer:
                peer.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                if peer.getsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY)!=1:raise RuntimeError('accepted socket option not applied')
            passed('accepted-stream-option')
    passed('AF_INET6:mapped-loopback')
    for ident,family,kind in [('socket-unix',socket.AF_UNIX,socket.SOCK_STREAM),('socket-raw',socket.AF_INET,socket.SOCK_RAW)]:
        denied(ident,lambda:socket.socket(family,kind))
    left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        left.sendall(b'x')
        if right.recv(1)!=b'x':raise RuntimeError('anonymous stream pair failed')
    finally:left.close();right.close()
    passed('unix-stream-pair')
    for ident,kind in [('unix-datagram-pair',socket.SOCK_DGRAM),('unix-seqpacket-pair',socket.SOCK_SEQPACKET)]:
        denied(ident,lambda:socket.socketpair(socket.AF_UNIX,kind))
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        if s.getsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,16)!=b'lo\0':raise RuntimeError('socket device restriction missing')
        passed('device-bound')
        denied('deny-bind-device',lambda:s.setsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,b''))
        denied('deny-bind-ifindex',lambda:s.setsockopt(socket.SOL_SOCKET,SO_BINDTOIFINDEX,0))
        # Valid syscall flags with null payload/address: the filter must reject
        # before any network operation or kernel argument interpretation.
        for ident,nr,args in [('deny-fastopen-sendto',44,(s.fileno(),0,0,FASTOPEN,0,0)),('deny-fastopen-sendmsg',46,(s.fileno(),0,FASTOPEN)),('deny-fastopen-sendmmsg',307,(s.fileno(),0,0,FASTOPEN))]:
            denied(ident,lambda:syscall(nr,*args))
    for ident,nr,args,expected in [('deny-setsid',112,(),errno.EPERM),('deny-setpgid',109,(0,0),errno.EPERM),('deny-close-range',436,(1000000,1000001,0),errno.ENOSYS),('deny-clone3',435,(0,0),errno.ENOSYS),('deny-seccomp',317,(3,0,0),errno.EPERM),('deny-io-uring',425,(0,0),errno.EPERM),('deny-pidfd-getfd',438,(-1,-1,0),errno.EPERM)]:
        denied(ident,lambda:syscall(nr,*args),expected)
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        child=os.fork()
        if child==0:
            try:
                denied('child-only',lambda:s.connect(('192.0.2.1',9)))
                s.close();os._exit(0)
            except BaseException:os._exit(1)
        _,status=os.waitpid(child,0)
        if os.waitstatus_to_exitcode(status):raise RuntimeError('fork child enforcement failed')
        s.bind(('127.0.0.1',0))
    passed('fork-inheritance')
    for family in (socket.AF_INET,socket.AF_INET6):
        rows.extend(datagram_probes(family))
    if {r['id'] for r in rows}!=set(probe_ids()):raise RuntimeError('internal probe identity mismatch')
    return rows


def main():
    if sys.argv[1:2]==['--probe']:
        print(json.dumps(probes()));return 0
    if sys.argv[1:2]==['--child']:
        rows=probes()
        child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--probe'],capture_output=True,text=True,timeout=60)
        if child.returncode:raise RuntimeError('exec child network probes failed: '+child.stderr)
        value={'schema_version':1,'parent':rows,'exec_child':json.loads(child.stdout)}
        validate_probes(value)
        with Path(os.environ['AMBISGIS_LOOPBACK_PROBES']).open('x') as out:json.dump(value,out,indent=2)
        os.execvpe(sys.argv[2],sys.argv[2:],os.environ)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=1200)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    a=parser.parse_args();cmd=a.command[1:] if a.command[:1]==['--'] else a.command
    if not cmd:parser.error('command required')
    probes_path=a.evidence.with_suffix('.probes.json')
    if probes_path.exists():parser.error('probe evidence already exists')
    os.environ['AMBISGIS_LOOPBACK_PROBES']=str(probes_path.resolve())
    return run(cmd,a.evidence,a.timeout)

if __name__=='__main__':raise SystemExit(main())
