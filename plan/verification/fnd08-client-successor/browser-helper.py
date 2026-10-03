"""Validate the actual merged-client build in a fresh loopback-only namespace."""
import argparse
from datetime import datetime,timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,r):p.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
def state(build,inputs):
    roots={'mapstore-client':build/'client','mapstore':build/'client/geonode_mapstore_client/client/MapStore2'}
    return {name:{path:sha(roots[name]/path) if (roots[name]/path).is_file() else None for path in rows}
            for name,rows in inputs.items()}

def main(a):
    a.output.mkdir(parents=True,exist_ok=False)
    result=json.loads((a.build/'result.json').read_text())
    if result['result_exit_code'] or result['source_selection']['mapstore-client']['commit']!='c1f6ad9df52f08ac3bfd7211db9e3ee744b21407':
        raise ValueError('Actual successful merged-client build required')
    ns=os.readlink('/proc/self/ns/net')
    if ns==a.parent_namespace:raise ValueError('A fresh network namespace is required')
    subprocess.run(['/usr/bin/ip','link','set','lo','up'],check=True)
    interfaces=json.loads(subprocess.check_output(['/usr/bin/ip','-j','address','show']))
    if {r['ifname'] for r in interfaces}!={'lo'}:raise ValueError('Unexpected external interface')
    probes=[]
    for family,address in ((socket.AF_INET,('203.0.113.1',443)),(socket.AF_INET6,('2001:db8::1',443))):
        with socket.socket(family,socket.SOCK_STREAM) as s:
            s.settimeout(2);code=s.connect_ex(address)
            if code not in (errno.ENETUNREACH,errno.EHOSTUNREACH):raise ValueError('External route available')
            probes.append({'family':family.name,'errno':code,'passed':True})
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen()
        with socket.create_connection(listener.getsockname()) as sender:
            receiver,_=listener.accept()
            with receiver:sender.sendall(b'loopback');assert receiver.recv(8)==b'loopback'
    original=json.loads((a.build/'source-inputs.json').read_text());before=state(a.build,original)
    write(a.output/'source-state-before.json',before)
    node=a.build/'toolchain/node-v24.18.1-linux-x64/bin/node';client=a.build/'client/geonode_mapstore_client/client'
    home=a.output/'home';home.mkdir()
    env={'PATH':str(node.parent)+':/usr/bin:/bin','HOME':str(home),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
         'TZ':'UTC','CI':'true','NODE_OPTIONS':'--max-old-space-size=8192','npm_config_offline':'true'}
    command=[sys.executable,str(a.platform/'build-support/frontend/native_tests.py'),'--client',str(client),
             '--node',str(node),'--chrome',str(a.chrome),'--output',str(a.output/'results'),'--port','19943']
    report={'started_at':datetime.now(timezone.utc).isoformat(),'build_receipt':{'path':str(a.build/'result.json'),'sha256':sha(a.build/'result.json')},
            'command':command,'parent_network_namespace':a.parent_namespace,'network_namespace':ns,'interfaces':interfaces,
            'routes':json.loads(subprocess.check_output(['/usr/bin/ip','-j','route','show','table','all'])),
            'external_probes':probes,'loopback_positive_control':True,'chromium_sandbox_disabled':False,
            'scope':'Actual fresh merged-client native tests with isolated loopback; not a hostile-code/filesystem sandbox.',
            'runner_sha256':sha(Path(__file__)),'native_helper_sha256':sha(a.platform/'build-support/frontend/native_tests.py')}
    write(a.output/'namespace.json',report)
    with (a.output/'run.log').open('x') as log:r=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
    report.update(command_exit_code=r.returncode,source_state_before_after_equal=before==state(a.build,original),finished_at=datetime.now(timezone.utc).isoformat())
    write(a.output/'namespace.json',report)
    if r.returncode or not report['source_state_before_after_equal']:raise ValueError('Native tests or source immutability failed')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('build','platform','output','chrome'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--parent-namespace',required=True);main(p.parse_args())
