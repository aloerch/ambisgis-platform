"""Actual new-WAR JSON and NO-JPEG2000 HTTP probes in the combined GWC fixture.

The caller owns runtime containment, credentials, fresh cache and final teardown.
Nothing here substitutes a response or decodes JPEG2000. The negative fixture is
an integrity-checked historical data file, not a prior acceptance result.
"""
import hashlib
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
import zipfile
from remediation_mosaic import request, require, sha, save, secrets

PROFILE = 'NO-ORACLE-NO-JPEG2000-headless-Temurin17'
MESSAGE = b'JPEG2000 is unsupported in the AmbisGIS NO-JPEG2000 Java/server profile.'
JP2 = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/imaging/final-war-probe-02/fixtures/JPEG2000-selected.img')
JP2_SHA = 'd7855b050f69cfb0077d280a4ab717da92bc348e3f4cb4a62550daf2598a6d79'
PDF_INPUTS = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/json-jpeg2000-remediation/imaging/probe-07/fixtures')
PDF_HASHES = {'jp2-embedded.pdf':'034b65463bc85b854ef322de9729e5c1ff805566a41a01d747893ee628cc1e6b',
              'ordinary-embedded.pdf':'8d8d54c12bc91e9261e3eb8c1e034eab85b2348ddb16418ae4dc0ea43db99c9d'}


def enabled(runtime): return (runtime.get('java_profile') or {}).get('profile') == PROFILE


def fixtures():
    data = JP2.read_bytes()
    require(sha(data) == JP2_SHA and data[:12] == b'\x00\x00\x00\x0cjP  \r\n\x87\n', 'retained JPEG2000 fixture changed')
    offset = 0; raw = None
    while offset + 8 <= len(data):
        length = int.from_bytes(data[offset:offset+4], 'big')
        require(length >= 8 and offset + length <= len(data), 'invalid retained JP2 box')
        if data[offset+4:offset+8] == b'jp2c': raw = data[offset+8:offset+length]
        offset += length
    require(raw is not None and raw.startswith(b'\xff\x4f\xff\x51'), 'retained data lacks raw codestream')
    return data, raw


def prepare(data, output):
    """Owned deterministic print fixture; no external image or policy authority."""
    from PIL import Image
    out = Path(output) / 'nojpeg2000-http'
    out.mkdir(mode=0o700)
    inputs = out / 'inputs'; inputs.mkdir()
    jp2, raw = fixtures()
    for name, contents in [('known.jp2',jp2),('known.j2k',raw),('disguised.png',jp2)]:
        (inputs/name).write_bytes(contents)
    for name, expected in PDF_HASHES.items():
        body=(PDF_INPUTS/name).read_bytes()
        require(sha(body)==expected,'retained PDF fixture changed: '+name)
        (inputs/name).write_bytes(body)
    image = Image.new('RGB', (64,64), (30,90,180))
    for x in range(32,64):
        for y in range(64): image.putpixel((x,y),(210,80,30))
    for name, kind in [('known.png','PNG'),('known.jpg','JPEG'),('known.tif','TIFF')]:
        image.save(inputs/name, format=kind)
    yaml = "dpis: [72]\nformats: ['*']\nscales: [1000]\nhosts:\n  - !localMatch\n    dummy: true\nlayouts:\n"
    for name in ('known.png','known.jpg','known.tif','known.jp2','known.j2k','disguised.png'):
        yaml += ("  " + name.replace('.','_') + ":\n    mainPage:\n      pageSize: A4\n      items:\n"
                 "        - !text\n          text: 'AmbisGIS actual servlet raster witness'\n          fontSize: 18\n"
                 "        - !image\n          maxWidth: 192\n          maxHeight: 192\n          url: '" + (inputs/name).as_uri() + "'\n")
    yaml += "  remote_map:\n    mainPage:\n      pageSize: A4\n      items:\n        - !map\n          width: 192\n          height: 160\n"
    path=Path(data)/'printing/config.yaml';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(yaml)
    report={'scope':PROFILE,'config_sha256':sha(path.read_bytes()),'inputs':{p.name:{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(inputs.iterdir())},'fixture_source_sha256':JP2_SHA}
    save(out/'fixture.json',report)
    return report


def catalog_state(data):
    data=Path(data)
    return {str(p.relative_to(data)):sha(p.read_bytes()) for root in ('workspaces','data') for p in sorted((data/root).rglob('*')) if p.is_file()}


def rejected(config, token, directory, label, route, **kwargs):
    body=request(config,token,directory,label,route,statuses=(415,),**kwargs)
    require(MESSAGE in body,'explicit unsupported JPEG2000 diagnostic absent: '+label)
    require(len(body)<2048 and b'java.lang.' not in body and b'Exception' not in body,'unsupported response leaked implementation diagnostics')
    return label


def print_spec(layout, output='pdf'):
    return json.dumps({'layout':layout,'outputFormat':output,'dpi':72,'units':'m','srs':'EPSG:4326','layers':[],
                       'pages':[{'center':[0,0],'scale':1000,'rotation':0}]}).encode()


def remote_prints(config,token,directory,root):
    """Serve exact hostile-format data through a finite task-owned loopback fixture."""
    payloads={'/jpeg2000-tile':('image/png',(root/'inputs/known.jp2').read_bytes()),
              '/pdf-jpeg2000-tile':('application/pdf',(root/'inputs/jp2-embedded.pdf').read_bytes()),
              '/ordinary-pdf-tile':('application/pdf',(root/'inputs/ordinary-embedded.pdf').read_bytes())}
    observations=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            path=urlsplit(self.path).path
            if path not in payloads or len(observations)>=20:
                self.send_error(404);return
            mime,data=payloads[path]
            observations.append({'path':path,'content_type':mime,'bytes':len(data),'sha256':sha(data)})
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    report={'result_exit_code':1,'bind_host':'127.0.0.1','observations':observations}
    try:
        # The selected local mosaic has no URL SourceSPIProvider. Observe the
        # inherited route honestly; do not count its empty 202 as JPEG2000 support.
        import remediation_mosaic
        tiles=Path(config['output'])/'geoserver-data/data/fixture/remediation_mosaic'
        before_index=remediation_mosaic.index_evidence(config,tiles)
        harvest_url='http://127.0.0.1:'+str(server.server_port)+'/jpeg2000-tile'
        request(config,token,directory,'remote-harvest-observation',
                'rest/workspaces/fixture/coveragestores/remediation_mosaic/remote.imagemosaic',
                method='POST',body=harvest_url.encode(),content_type='text/plain',statuses=(202,400,415))
        response=json.loads((directory/'remote-harvest-observation-http.json').read_text())
        require(remediation_mosaic.index_evidence(config,tiles)==before_index,'unsupported remote harvest altered native mosaic index')
        report['remote_harvest']={'status':response['status'],'fixture_fetched':bool(observations),
                'index_unchanged':True,'capability_acceptance':False,
                'classification':'Pre-existing unsupported remote source: selected mosaic has no URL SourceSPIProvider; native controller historically discards empty harvest results. No universal remote-harvest guarantee.'}
        for path,mime in [('jpeg2000-tile','image/png'),('pdf-jpeg2000-tile','application/pdf')]:
            spec=json.loads(print_spec('remote_map'))
            spec['units']='degrees'
            spec['layers']=[{'type':'WMS','baseURL':'http://127.0.0.1:'+str(server.server_port)+'/'+path,
                             'layers':['known'],'styles':[''],'format':mime,'singleTile':True,'opacity':1,'version':'1.1.1'}]
            rejected(config,token,directory,'print-remote-'+path,'pdf/print.pdf',method='POST',body=json.dumps(spec).encode(),content_type='application/json')
            require(any(row['path']=='/'+path for row in observations),'actual remote tile was not requested')
        spec['layers'][0]['baseURL']='http://127.0.0.1:'+str(server.server_port)+'/ordinary-pdf-tile'
        response=request(config,token,directory,'print-remote-valid-pdf','pdf/print.pdf',method='POST',body=json.dumps(spec).encode(),content_type='application/json')
        require(response.startswith(b'%PDF-') and len(response)>1500,'ordinary PDF tile print failed after rejection')
        require(any(row['path']=='/ordinary-pdf-tile' for row in observations),'ordinary PDF tile was not fetched')
        report['result_exit_code']=0
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        report['cleanup']={'server_closed':True,'thread_stopped':not thread.is_alive()}
        if thread.is_alive():report['result_exit_code']=1
        save(directory/'remote-print-result.json',report)
    require(report['result_exit_code']==0,'remote fixture cleanup failed')
    return report


def probe(config, token, output, phase='initial'):
    from PIL import Image
    root=Path(output)/'nojpeg2000-http';directory=root/phase;directory.mkdir()
    report={'result_exit_code':1,'phase':phase,'profile':PROFILE,'negative':[]}
    try:
        jp2,raw=fixtures()
        data=Path(output)/'geoserver-data'
        fixed=json.loads((root/'fixture.json').read_text())
        require(sha((data/'printing/config.yaml').read_bytes())==fixed['config_sha256'],'printing configuration changed')
        require({p.name:{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted((root/'inputs').iterdir())}==fixed['inputs'],'print fixture inputs changed')
        before=catalog_state(data)
        if phase=='initial':
            cases=[('jp2','file.jp2','image/jp2',jp2),('raw','file.j2k','image/j2k',raw),
                   ('renamed-jp2','file.geotiff?filename=disguised.tif','image/tiff',jp2),
                   ('renamed-j2k','file.geotiff?filename=disguised.tif','application/octet-stream',raw),
                   ('mime-json','file.geotiff','application/json',jp2),('mime-xml','file.geotiff','application/xml',raw),
                   ('truncated-jp2','file.geotiff','image/tiff',jp2[:8]),('truncated-j2k','file.geotiff','image/tiff',raw[:2])]
            for label,route,mime,payload in cases:
                report['negative'].append(rejected(config,token,directory,'coverage-'+label,
                    'rest/workspaces/fixture/coveragestores/rejected_'+label+'/'+route,method='PUT',body=payload,content_type=mime))
                require(catalog_state(data)==before,'failed raster upload changed catalog/resource data: '+label)
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
                z.writestr('disguised.tif',jp2)
            report['negative'].append(rejected(config,token,directory,'coverage-zip','rest/workspaces/fixture/coveragestores/rejected_zip/file.imagemosaic',
                method='PUT',body=archive.getvalue(),content_type='application/zip'))
            require(catalog_state(data)==before,'rejected raster ZIP changed catalog/resource data')
            # net.sf.json importer parser is exercised by a real context round trip.
            contexts=request(config,token,directory,'imports-before','rest/imports')
            malformed=request(config,token,directory,'imports-malformed','rest/imports',method='POST',body=b'{"import":',content_type='application/json',statuses=(400,))
            require(len(malformed)<8192,'malformed JSON response unbounded')
            require(json.loads(request(config,token,directory,'imports-after-malformed','rest/imports'))==json.loads(contexts),'malformed JSON created an import context')
            payload=json.dumps({'import':{'targetWorkspace':{'workspace':{'name':'fixture'}}}}).encode()
            context=json.loads(request(config,token,directory,'import-create','rest/imports',method='POST',body=payload,content_type='application/json',statuses=(201,)))
            identifier=context.get('import',context).get('id')
            require(type(identifier) is int and identifier>=0,'native importer context ID missing')
            route='rest/imports/'+str(identifier)
            try:
                tasks=json.loads(request(config,token,directory,'tasks-before',route+'/tasks'))
                for label,mime,payload in [('jp2','image/jp2',jp2),('disguised','image/png',raw),('spoofed','application/json',jp2)]:
                    report['negative'].append(rejected(config,token,directory,'import-'+label,route+'/tasks/rejected_'+label+'.png',method='PUT',body=payload,content_type=mime))
                    require(json.loads(request(config,token,directory,'tasks-after-'+label,route+'/tasks'))==tasks,'failed upload created partial import task')
                boundary='AmbisGISBoundedCodecFixture'
                body=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="disguised.png"\r\nContent-Type: image/png\r\n\r\n').encode()+jp2+('\r\n--'+boundary+'--\r\n').encode()
                report['negative'].append(rejected(config,token,directory,'import-multipart',route+'/tasks',method='POST',body=body,content_type='multipart/form-data; boundary='+boundary))
                require(json.loads(request(config,token,directory,'tasks-after-multipart',route+'/tasks'))==tasks,'multipart rejection created partial task')
                for mode in ('direct','multipart'):
                    if mode=='direct':
                        path=route+'/tasks/disguised.zip';upload=archive.getvalue();mime='application/zip';method='PUT'
                    else:
                        path=route+'/tasks';method='POST';mime='multipart/form-data; boundary='+boundary
                        upload=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="disguised.zip"\r\nContent-Type: application/zip\r\n\r\n').encode()+archive.getvalue()+('\r\n--'+boundary+'--\r\n').encode()
                    report['negative'].append(rejected(config,token,directory,'import-zip-'+mode,path,method=method,body=upload,content_type=mime))
                    require(json.loads(request(config,token,directory,'tasks-after-zip-'+mode,route+'/tasks'))==tasks,'ZIP rejection created partial import task')
                # Candidate resource-limit behavior is separate from unsupported codec behavior.
                too_many=io.BytesIO()
                with zipfile.ZipFile(too_many,'w',compression=zipfile.ZIP_STORED) as z:
                    for count in range(10001):z.writestr('ordinary-'+str(count)+'.txt',b'')
                for mode in ('direct','multipart'):
                    if mode=='direct':
                        path=route+'/tasks/too-many.zip';upload=too_many.getvalue();mime='application/zip';method='PUT'
                    else:
                        path=route+'/tasks';method='POST';mime='multipart/form-data; boundary='+boundary
                        upload=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="too-many.zip"\r\nContent-Type: application/zip\r\n\r\n').encode()+too_many.getvalue()+('\r\n--'+boundary+'--\r\n').encode()
                    answer=request(config,token,directory,'zip-limit-'+mode,path,method=method,body=upload,content_type=mime,statuses=(413,))
                    require(b'10000 members' in answer and b'1 GiB' in answer,'ZIP limit must be explicit, not a codec unsupported error')
                    require(json.loads(request(config,token,directory,'tasks-after-limit-'+mode,route+'/tasks'))==tasks,'limit refusal created partial task')
                report['archive_limits']={'compressed_bytes':1073741824,'members':10000,'live_cases':['direct-10001-members','multipart-10001-members'],
                        'expected_status':413,'compressed_byte_bound':'Separately executed source guard sparse-file/declared/private-copy-bound tests; not a live GiB transfer.'}
                require(catalog_state(data)==before,'failed importer uploads changed catalog/resource data')
            finally:
                request(config,token,directory,'import-cleanup',route,method='DELETE',statuses=(200,204))
        params={'SERVICE':'WMS','VERSION':'1.1.1','ReQuEsT':'GetMap','LAYERS':'fixture:remediation_mosaic','STYLES':'remediation_mosaic_style',
                'SRS':'EPSG:4326','BBOX':'0,0,4,4','WIDTH':128,'HEIGHT':128,'FORMAT':'image/jp2'}
        report['negative'].append(rejected(config,token,directory,'wms-output','wms?'+urlencode(params)))
        report['negative'].append(rejected(config,token,directory,'wcs-output','wcs?'+urlencode({'SERVICE':'WCS','VERSION':'2.0.1','REQUEST':'GetCoverage','COVERAGEID':'fixture__remediation_mosaic','FORMAT':'image/jp2'})))
        report['negative'].append(rejected(config,token,directory,'wmts-output','gwc/service/wmts?'+urlencode({'SERVICE':'WMTS','REQUEST':'GetTile','FORMAT':'image/jp2'})))
        for endpoint in ('wms','wcs'):
            capabilities=request(config,token,directory,endpoint+'-capabilities',endpoint+'?SERVICE='+endpoint.upper()+'&REQUEST=GetCapabilities')
            require(not re.search(rb'>\s*(?:image/)?(?:jp2|j2k|jpeg2000)\s*<',capabilities,re.I),'unsupported codec remains advertised')
        # Native print servlet must reject explicit output requests and real image bytes.
        for fmt in ('jp2','j2k','image/jp2','JPEG2000'):
            report['negative'].append(rejected(config,token,directory,'print-output-'+fmt.replace('/','_'),'pdf/create.json',method='POST',body=print_spec('known_png',fmt),content_type='application/json'))
        for layout in ('known_jp2','known_j2k','disguised_png'):
            report['negative'].append(rejected(config,token,directory,'print-input-'+layout,'pdf/print.pdf',method='POST',body=print_spec(layout),content_type='application/json'))
        report['remote_prints']=remote_prints(config,token,directory,root)
        outputs=[]
        for fmt in ('pdf','png','tiff'):
            response=request(config,token,directory,'print-valid-'+fmt,'pdf/print.pdf',method='POST',body=print_spec('known_png',fmt),content_type='application/json')
            metadata=json.loads((directory/('print-valid-'+fmt+'-http.json')).read_text())
            expected_type={'pdf':'application/pdf','png':'image/png','tiff':'image/tiff'}[fmt]
            require(metadata['content_type'].split(';',1)[0].strip()==expected_type,'print content type differs from actual requested format')
            if fmt=='pdf':require(response.startswith(b'%PDF-') and len(response)>1500,'actual PDF missing or truncated')
            else:
                with Image.open(io.BytesIO(response)) as image:
                    rgb=image.convert('RGB'); colors=sum(1 for r,g,b in rgb.getdata() if max(r,g,b)-min(r,g,b)>60)
                    require(rgb.width>300 and rgb.height>300 and colors>2000,'print raster blank/corrupt/truncated')
            outputs.append({'format':fmt,'sha256':sha(response),'bytes':len(response)})
        # A valid request after all failures must still render independent known colors.
        params['FORMAT']='image/png';response=request(config,token,directory,'wms-recovery','wms?'+urlencode(params))
        with Image.open(io.BytesIO(response)) as image:
            image=image.convert('RGB')
            require(max(abs(a-b) for a,b in zip(image.getpixel((32,64)),(40,80,160)))<=2,'valid raster failed after unsupported requests')
        require(catalog_state(data)==before,'negative requests or print outputs mutated catalog/resource state')
        report.update(result_exit_code=0,prints=outputs,catalog_unchanged=True,recovery=True)
    except Exception as error:
        message=str(error)
        for value in secrets(config,token):
            if value:message=message.replace(value,'[REDACTED]')
        report['error']={'type':type(error).__name__,'message':message}
        raise
    finally:save(directory/'result.json',report)
    return report
