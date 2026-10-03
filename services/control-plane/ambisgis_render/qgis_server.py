"""Owned QGIS Server native access-control adapter for the finite map profile.

Single-process sequential QGIS dispatch: its native API is not thread safe.
The installed project is a provisioner-approved immutable desktop export, not
an arbitrary uploaded project, and the only decision authority is the catalog.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
from urllib.parse import urlencode, urlsplit

from .boundary import Bindings, decision, resource, FIELDS


def serve(config):
    from qgis.core import QgsApplication, QgsProject
    from qgis.PyQt.QtGui import QFontDatabase
    from qgis.server import (QgsAccessControlFilter, QgsBufferServerRequest,
                             QgsBufferServerResponse, QgsServer)
    QgsApplication.setPrefixPath(config['qgis_prefix'], True)
    app = QgsApplication([], False); app.initQgis()
    assert QFontDatabase.addApplicationFont(config['font_file']) >= 0
    bindings = Bindings(config['bindings'], config['bindings_sha256'])
    key = Path(config['policy_key_file']).read_text().strip()
    project = QgsProject(); assert project.read(config['project'])
    assert all(layer.isValid() for layer in project.mapLayers().values())
    native = QgsServer()

    class CatalogAccess(QgsAccessControlFilter):
        def __init__(self, iface):
            super().__init__(iface)
            self.current = None
            self.reads = 0
        def layerPermissions(self, layer):
            rights = QgsAccessControlFilter.LayerPermissions()
            rights.canRead = rights.canInsert = rights.canUpdate = rights.canDelete = False
            if self.current:
                name, bearer = self.current
                rights.canRead = ('fixture:' + layer.name() == name and bindings.valid(name)
                                  and decision(config['catalog_origin'], key, name, bearer))
                if rights.canRead: self.reads += 1
            return rights
        def allowToEdit(self, layer, feature): return False
        def cacheKey(self): return ''

    access = CatalogAccess(native.serverInterface())
    native.serverInterface().registerAccessControl(access, 1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def request(self):
            status, body = 403, b''
            try:
                parts = urlsplit(self.path)
                name = resource(self.command, parts.path, parts.query, route='/qgis')
                if len(self.headers.get_all('Authorization', [])) > 1: name = None
                access.current = None; access.reads = 0
                if name and bindings.valid(name):
                    access.current = (name, self.headers.get('Authorization', ''))
                    # Canonical input excludes caller MAP/SLD/FILE_NAME/plugins/extra layers.
                    query = dict(FIELDS, layers=name.split(':', 1)[1])
                    request = QgsBufferServerRequest('http://127.0.0.1/qgis?' + urlencode(query))
                    response = QgsBufferServerResponse()
                    native.handleRequest(request, response, project)
                    candidate = bytes(response.body())
                    if access.reads and response.statusCode() == 200 and candidate.startswith(b'\x89PNG\r\n\x1a\n') and len(candidate) <= 4 * 1024 * 1024:
                        status, body = 200, candidate
            except Exception:
                status, body = 503, b''
            finally: access.current = None
            self.send_response(status)
            self.send_header('Content-Type', 'image/png' if body else 'text/plain')
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = request

    from runtime_common import loaded_origins, provider_origins, python_origins, sha
    report = {'loaded_origins': loaded_origins(config), 'provider_origins': provider_origins(config),
              'python_origins': python_origins(config), 'hook': 'QgsAccessControlFilter.layerPermissions',
              'policy_authority': 'native GeoNode catalog endpoint', 'threading': 'sequential native QGIS dispatch'}
    server_library = (Path(config['qgis_prefix']) / 'lib/libqgis_server.so').resolve()
    mappings = {Path(path).resolve() for path in report['loaded_origins']['all_mapped_files']
                if Path(path).name.startswith('libqgis_server.so')}
    if mappings != {server_library}:raise RuntimeError('selected native QGIS Server was not mapped')
    report['native_server'] = {'path': str(server_library), 'sha256': sha(server_library)}
    Path(config['ready_file']).write_text(json.dumps(report, indent=2) + '\n')
    with HTTPServer(('127.0.0.1', config['port']), Handler) as http:
        print(json.dumps({'event': 'listening'}), flush=True)
        http.serve_forever()


if __name__ == '__main__': serve(json.loads(Path(sys.argv[1]).read_text()))
