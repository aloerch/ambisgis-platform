#!/usr/bin/env python3
"""Runs only inside unchanged loopback supervisor, with real QGIS binaries."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from runtime_common import LAYERS, image_witness, loaded_origins, require, save, sha


class Capture:
    def __init__(self, process, path, secrets):
        self.process, self.path, self.secrets = process, Path(path), secrets
        self.errors, self.secret_hits = [], 0
        self.thread = threading.Thread(target=self.copy, daemon=True); self.thread.start()

    def copy(self):
        try:
            with self.path.open('x') as out:
                for raw in self.process.stdout:
                    for value in self.secrets:
                        if value and value in raw:
                            self.secret_hits += 1; raw = raw.replace(value,'[REDACTED_FIXTURE_VALUE]')
                    out.write(raw); out.flush()
        except Exception as error: self.errors.append(type(error).__name__)

    def finish(self):
        self.thread.join(10)
        require(not self.thread.is_alive() and not self.errors, 'diagnostic capture failed')
        require(not self.secret_hits, 'secret emitted in child diagnostic')


def stop(process, capture):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=10)
            capture.finish()
            raise RuntimeError('task-owned child required forced termination')
    capture.finish()


def command(argv, config, name, secrets, timeout=120):
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    capture = Capture(process, Path(config['output'])/(name+'.log'), secrets)
    try:
        code = process.wait(timeout=timeout)
        capture.finish(); require(code == 0, name+' exited unsuccessfully')
        return {'command':argv,'exit_code':code,'log_sha256':sha(capture.path)}
    finally:
        if process.poll() is None: stop(process,capture)


def server(config, secrets):
    from qgis.PyQt.QtGui import QImage
    output = Path(config['output'])
    result = {'implementation':'native qgis_mapserver HTTP process', 'sequential':True, 'runs':[],
              'wms':{'version':'1.1.1','srs':'EPSG:4326','bbox':[0,0,4,4],'axis_order':'longitude,latitude','size':[512,512]}}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    for iteration in range(2):
        argv = [config['server'], '-p', str(output/'fixture.qgs'), '127.0.0.1:'+str(port)]
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        capture = Capture(process,output/f'server-{iteration}.log',secrets)
        run = {'command':argv,'pid':process.pid,'responses':[]}; result['runs'].append(run)
        try:
            deadline = time.monotonic()+45
            while True:
                require(process.poll() is None, 'native QGIS server exited before readiness')
                if capture.path.exists() and 'QGIS Development Server listening on http://127.0.0.1:' in capture.path.read_text(): break
                require(time.monotonic()<deadline, 'native QGIS server readiness timeout'); time.sleep(.1)
            requests = [('capabilities',{'REQUEST':'GetCapabilities'})]
            requests += [('combined',{'REQUEST':'GetMap','LAYERS':'known_raster,local_points,database_points'})]
            if iteration == 0:
                requests += [('local',{'REQUEST':'GetMap','LAYERS':'known_raster,local_points'}),
                             ('database',{'REQUEST':'GetMap','LAYERS':'known_raster,database_points'})]
            for name, parameters in requests:
                query = {'SERVICE':'WMS','VERSION':'1.1.1',**parameters}
                if name != 'capabilities': query.update(STYLES='',SRS='EPSG:4326',BBOX='0,0,4,4',WIDTH='512',HEIGHT='512',FORMAT='image/png',TRANSPARENT='FALSE')
                url = 'http://127.0.0.1:'+str(port)+'/?'+urllib.parse.urlencode(query)
                with opener.open(url,timeout=30) as response:
                    content = response.read(4000000)
                    require(response.status == 200, 'WMS HTTP status failed')
                    content_type = response.headers.get_content_type()
                suffix = '.xml' if name == 'capabilities' else '.png'
                path = output/f'server-{iteration}-{name}{suffix}'; path.write_bytes(content)
                evidence = {'request':query,'http_status':200,'content_type':content_type,'bytes':len(content),'sha256':sha(path)}
                if name == 'capabilities':
                    document = ET.fromstring(content)
                    require(document.tag.split('}')[-1] in ('WMT_MS_Capabilities','WMS_Capabilities'), 'WMS XML exception or wrong document')
                    advertised = {element.text for element in document.iter() if element.tag.split('}')[-1] == 'Name'}
                    require(set(LAYERS).issubset(advertised), 'WMS fixture layer identities missing')
                    evidence['layers'] = sorted(set(LAYERS)&advertised)
                else:
                    require(content_type == 'image/png' and content.startswith(b'\x89PNG\r\n\x1a\n'), 'GetMap did not return PNG')
                    evidence['render'] = image_witness(QImage(str(path)), (0,0,4,4),local=name!='database',database=name!='local')
                run['responses'].append(evidence)
            run['loaded_origins'] = loaded_origins(config,process.pid)
        finally:
            stop(process,capture)
            run['exit_code'] = process.returncode
            run['stopped'] = process.poll() is not None
            require(process.returncode == 0, 'native server shutdown failed')
            with socket.socket() as probe:
                require(probe.connect_ex(('127.0.0.1',port)) != 0, 'task server listener remains after stop')
    result['actual_http_requests'] = sum(len(run['responses']) for run in result['runs'])
    result['restart_demonstrated'] = True
    return result


def main(config):
    output = Path(config['output']); report = {'result_exit_code':1}
    secret_values = [Path(config['pgpass']).read_text().strip().rsplit(':',1)[-1]]
    try:
        here = Path(__file__).resolve().parent
        report['fixture_command'] = command([config['python'],str(here/'fixture.py'),config['config_path']],config,'fixture',secret_values)
        report['desktop_command'] = command([config['desktop'],'--nologo','--noversioncheck','--noplugins',
            '--profiles-path',str(output/'profiles'),'--profile','f02-04','--project',str(output/'fixture.qgs'),
            '--code',str(here/'desktop_witness.py')], config,'desktop',secret_values,150)
        report['desktop'] = json.loads((output/'desktop-result.json').read_text())
        require(report['desktop']['result_exit_code'] == 0, 'desktop receipt failed')
        report['server'] = server(config,secret_values)
        report['result_exit_code'] = 0
    except Exception as error:
        message = str(error)
        for value in secret_values: message = message.replace(value,'[REDACTED_FIXTURE_VALUE]')
        report['error'] = {'type':type(error).__name__,'message':message}
    finally: save(output/'child-result.json',report)
    return report['result_exit_code']


if __name__ == '__main__': raise SystemExit(main(json.loads(Path(sys.argv[1]).read_text())))
