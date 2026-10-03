"""Loopback-only synthetic native provider HTTP boundary; no catalog authority."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import uuid

from native import ContractError, Provider, c1_request, koop_data


def serve(config):
    import psycopg2
    audit_file = Path(config['output']) / 'native-audit.jsonl'
    def audit(value):
        with audit_file.open('a') as stream:
            stream.write(json.dumps(value, default=str, sort_keys=True) + '\n')
    database = {('dbname' if k == 'name' else k): v for k, v in config['query_database'].items()}
    provider = Provider(config, lambda: psycopg2.connect(**database, connect_timeout=3), audit)
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def setup(self):
            super().setup()
            self.connection.settimeout(5)
        def log_message(self, *args):
            pass
        def reply(self, status, value):
            payload = json.dumps(value, allow_nan=False, separators=(',', ':')).encode()
            if self.command == 'HEAD': payload = b''
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(payload)
            self.close_connection = True
        def failure(self, status, code, *, retryable=False, remediation='correct_request'):
            self.reply(status, {'schema_version': 1, 'error': {'code': code, 'message': code,
                       'correlation_id': str(uuid.uuid4()), 'retryable': retryable, 'remediation': remediation}})
        def send_error(self, code, message=None, explain=None):
            # Override inherited HTML/error echoes, including unknown methods.
            if code == 501:
                self.failure(405, 'UNSUPPORTED_CAPABILITY')
            elif code in (413, 414, 431):
                self.failure(code, 'LIMIT_EXCEEDED')
            else:
                self.failure(code, 'INVALID_REQUEST')
        def do_POST(self):
            try:
                if len(self.headers.get_all('X-Spike-Key', [])) != 1 or not hmac.compare_digest(self.headers.get('X-Spike-Key', ''), config['backend_key']):
                    raise ContractError('NOT_FOUND_OR_FORBIDDEN')
                if (self.path not in ('/authorize', '/native', '/c1', '/metadata') or self.headers.get('Content-Type') != 'application/json'
                        or self.headers.get('Content-Encoding') or self.headers.get('Transfer-Encoding')
                        or len(self.headers.get_all('Authorization', [])) > 1):
                    raise ContractError('INVALID_REQUEST')
                length = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= length <= 32768:
                    raise ContractError('LIMIT_EXCEEDED')
                def unique(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result: raise ContractError('INVALID_REQUEST')
                        result[key] = value
                    return result
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ContractError('INVALID_REQUEST')
                value = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=unique)
                if not isinstance(value, dict) or set(value) - {'resource', 'query'}:
                    raise ContractError('INVALID_REQUEST')
                resource = value.get('resource')
                if not isinstance(resource, str): raise ContractError('INVALID_REQUEST')
                credential = self.headers.get('Authorization', '')
                provider.authorize(resource, credential)
                if self.path == '/authorize':
                    result = {'authorized': True}
                elif self.path == '/metadata':
                    result = koop_data({'features': [], 'exceeded_transfer_limit': False}, provider.layer)
                elif self.path == '/native':
                    result = provider.query(value.get('query'), resource, credential, already_authorized=True)
                else:
                    query, offset = c1_request(value.get('query'), provider.layer)
                    native_result = provider.query(query, resource, credential, c1_offset=offset, already_authorized=True)
                    result = koop_data(native_result, provider.layer)
                    result['spikeNativeMode'] = query['mode']
                self.reply(200, result)
            except ContractError as error:
                code = error.code
                status = 403 if code == 'NOT_FOUND_OR_FORBIDDEN' else 503 if code == 'POLICY_UNAVAILABLE' else 413 if code == 'LIMIT_EXCEEDED' else 400
                self.failure(status, code, retryable=code == 'POLICY_UNAVAILABLE',
                             remediation='retry_later' if code == 'POLICY_UNAVAILABLE' else 'refresh' if code in ('INVALID_CURSOR', 'REVISION_UNAVAILABLE') else 'correct_request')
            except (ValueError, TypeError, KeyError, RecursionError):
                self.failure(400, 'INVALID_REQUEST')
            except (psycopg2.errors.QueryCanceled, psycopg2.errors.LockNotAvailable):
                self.failure(503, 'LIMIT_EXCEEDED', retryable=True, remediation='retry_later')
            except psycopg2.OperationalError:
                self.failure(503, 'BACKEND_UNAVAILABLE', retryable=True, remediation='retry_later')
            except Exception:
                # Database/backend failures never escape as traces or exception text.
                self.failure(503, 'BACKEND_UNAVAILABLE', remediation='contact_operator')
        def do_GET(self):
            self.failure(405, 'UNSUPPORTED_CAPABILITY')
        do_HEAD = do_GET
        do_PATCH = do_GET
        do_PUT = do_GET
        do_DELETE = do_GET
        do_OPTIONS = do_GET
    server = HTTPServer(('127.0.0.1', config['backend_port']), Handler)
    print(json.dumps({'event': 'native_listening', 'port': config['backend_port']}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    serve(json.loads(args.config.read_text()))
