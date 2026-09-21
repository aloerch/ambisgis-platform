"""Explicit transport faults after real GeoNode verification, never identity stubs.

Normal requests pass unchanged. A private task-owned file enables one of two
bounded negative fixtures. Receipts label these as transport injection, not
behavior of GeoNode's native successful JSON protocol.
"""
import json
import os
from pathlib import Path
import stat
import time


def fault_mode(output):
    path = Path(output) / 'transport-fault.json'
    try: metadata = path.lstat()
    except FileNotFoundError: return None
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077
            or metadata.st_uid != os.getuid() or metadata.st_size > 100):
        raise ValueError('transport fault control must be a small owner-only regular file')
    value = json.loads(path.read_text())
    if value not in ({'mode': 'delay'}, {'mode': 'truncate'}):
        raise ValueError('unsupported transport fault control')
    return value['mode']


def controlled_transport(application, config):
    def handle(environ, start_response):
        mode = fault_mode(config['output']) if environ.get('PATH_INFO') == '/api/o/v4/tokeninfo' else None
        if mode is None:
            return application(environ, start_response)
        captured, written = {}, []
        def capture(status, headers, exc_info=None):
            captured.update(status=status, headers=headers, exc_info=exc_info)
            return written.append
        response = application(environ, capture)
        try:
            body = b''.join([*written, *response])
        finally:
            if hasattr(response, 'close'): response.close()
        if len(body) > 65536 or not captured:
            raise RuntimeError('unexpected native verification response')
        if captured['status'].split()[0] != '200':
            # A failure of the real verifier remains a real failure; fault tests
            # must prove they reached a valid native response before injection.
            start_response(captured['status'], captured['headers'], captured['exc_info'])
            return [body]
        print(json.dumps({'event': 'native_verifier_transport_fault', 'mode': mode,
                          'native_status': 200, 'native_body_bytes': len(body)}), flush=True)
        if mode == 'delay':
            time.sleep(4)
            start_response(captured['status'], captured['headers'], captured['exc_info'])
            return [body]
        headers = [(key, value) for key, value in captured['headers']
                   if key.lower() not in ('content-length', 'transfer-encoding', 'authorization')]
        start_response(captured['status'], headers + [('Content-Length', '1')])
        return [b'{']
    return handle


def role_fault_mode(output):
    path = Path(output) / 'role-transport-fault.json'
    try: metadata = path.lstat()
    except FileNotFoundError: return None
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077
            or metadata.st_uid != os.getuid() or metadata.st_size > 100):
        raise ValueError('role transport control must be a small owner-only regular file')
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or set(value) != {'mode'} or value['mode'] not in (
            'missing-credential', 'wrong-credential', 'delay', 'truncate', 'short-body', 'malformed', 'duplicate-field', 'trailing-content'):
        raise ValueError('unsupported role transport control')
    return value['mode']


def controlled_role_transport(application, config):
    """Explicit faults on actual role HTTP only; no invented identity/membership.

    Credential faults alter transport input and then execute native authorization.
    Response faults require real authenticated native 200 before corrupting bytes.
    """
    def handle(environ, start_response):
        path = environ.get('PATH_INFO', '')
        eligible = path in ('/api/roles', '/api/adminRole', '/api/users') or path.startswith('/api/users/')
        mode = role_fault_mode(config['output']) if eligible else None
        if mode is None: return application(environ, start_response)
        changed = environ.copy()
        if mode == 'missing-credential': changed.pop('HTTP_AUTHORIZATION', None)
        if mode == 'wrong-credential': changed['HTTP_AUTHORIZATION'] = 'ApiKey invalid-fixture-service-key'
        captured, written = {}, []
        def capture(status, headers, exc_info=None):
            captured.update(status=status, headers=headers, exc_info=exc_info)
            return written.append
        response = application(changed, capture)
        try: body = b''.join([*written, *response])
        finally:
            if hasattr(response, 'close'): response.close()
        if len(body) > 65536 or not captured: raise RuntimeError('unexpected native role response')
        status = int(captured['status'].split()[0])
        print(json.dumps({'event':'native_role_transport_fault','mode':mode,
                          'native_status':status,'native_body_bytes':len(body)}),flush=True)
        if mode in ('missing-credential','wrong-credential') or status != 200:
            start_response(captured['status'],captured['headers'],captured['exc_info']); return [body]
        if mode == 'delay':
            time.sleep(4)
            start_response(captured['status'],captured['headers'],captured['exc_info']); return [body]
        if mode in ('truncate', 'short-body'): bad = b'{'
        elif mode == 'duplicate-field':
            parsed = json.loads(body)
            if not isinstance(parsed, dict) or not parsed: raise RuntimeError('role fault requires native object')
            name = next(iter(parsed))
            # Duplicate real native data; never fabricate a principal or role.
            duplicate = json.dumps({name: parsed[name]}).encode()[1:-1]
            bad = body.rstrip()[:-1] + b',' + duplicate + b'}'
        elif mode == 'trailing-content': bad = body + b' trailing-garbage'
        else: bad = b'not-json-role-response'
        headers = [(k,v) for k,v in captured['headers'] if k.lower() not in ('content-length','transfer-encoding','authorization')]
        start_response(captured['status'],headers + [('Content-Length',str(len(body) if mode == 'short-body' else len(bad)))])
        return [bad]
    return handle
