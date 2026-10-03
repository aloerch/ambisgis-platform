"""Loopback prototype entry point; the map adapter owns no authorization data."""
import json
from pathlib import Path
import sys
from wsgiref.simple_server import make_server
from manage_fixture import ThreadedWSGIServer, QuietRequestHandler
from ambisgis_render.boundary import Bindings, gateway

config = json.loads(Path(sys.argv[1]).read_text())
bindings = Bindings(config['bindings'], config['bindings_sha256'])
app = gateway(config['catalog_origin'], Path(config['policy_key_file']).read_text().strip(), bindings, config['targets'])
with make_server('127.0.0.1', config['port'], app, server_class=ThreadedWSGIServer, handler_class=QuietRequestHandler) as server:
    print(json.dumps({'event': 'listening'}), flush=True)
    server.serve_forever()
