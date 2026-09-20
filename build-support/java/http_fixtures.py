"""Retained embedded HTTP fixtures for controlled XML/MapFish native probes.

This module never provides network isolation itself. Callers must execute the
patched Java tests under a separately verified loopback-only runtime boundary.
Only disposable source copies may be passed to prepare().
"""
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess

from resolution import sha, write_json

FIXTURES = Path(__file__).resolve().with_name('fixtures') / 'http'
RESPONSE_STATUSES = {'/500': 500, '/notImage': 200, '/capabilities': 200,
                     '/testServer': 200, '/e2egeoserver/gwc/service/wmts': 200}
REQUIRED_RESPONSES = {'/500', '/notImage'}


def _checked_file(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(part in ('', '.', '..') for part in path.parts):
        raise ValueError('unsafe fixture manifest path')
    current = root
    if not stat.S_ISDIR(current.lstat().st_mode):
        raise ValueError('fixture source root must be a real directory')
    for part in path.parts:
        current = current / part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError('fixture source symlinks are refused')
    if not stat.S_ISREG(current.lstat().st_mode):
        raise ValueError('fixture source must be a regular file')
    return current


def _manifest():
    return json.loads((FIXTURES / 'manifest.json').read_text())


def prepare(source, output, target):
    """Verify test inputs, patch fixture endpoints, and retain exact JVM options."""
    if target not in ('xml', 'mapfish'):
        raise ValueError('HTTP fixture only supports XML and MapFish')
    source, output = Path(source).absolute(), Path(output).absolute()
    manifest = _manifest()
    selected = manifest['targets'][target]
    patch = _checked_file(FIXTURES, selected['patch'])
    if sha(patch) != selected['patch_sha256']:
        raise ValueError('fixture patch checksum mismatch')
    changes = [selected, *selected.get('additional_patches', [])]
    for change in changes:
        changed = _checked_file(source, change['path'])
        if sha(changed) != change['before_sha256']:
            raise ValueError('fixture patch input differs from retained owned source: ' + change['path'])
    for name, digest in selected['retained_test_files'].items():
        if sha(_checked_file(source, name)) != digest:
            raise ValueError('retained test source/data changed: ' + name)
    hosts = manifest['hosts']['content'].encode('ascii')
    if hashlib.sha256(hosts).hexdigest() != manifest['hosts']['sha256']:
        raise ValueError('fixture hosts checksum mismatch')
    directory = output / 'http-fixture'
    directory.mkdir(exist_ok=False)
    (directory / 'hosts').write_bytes(hosts)
    # --check keeps malformed or nonapplicable patches from partially applying.
    for arguments in (['--check'], []):
        applied = subprocess.run(['git', 'apply', *arguments, str(patch)], cwd=source,
                                 capture_output=True, text=True, timeout=10)
        if applied.returncode:
            raise ValueError('fixture patch failed: ' + applied.stdout + applied.stderr)
    for change in changes:
        if sha(_checked_file(source, change['path'])) != change['after_sha256']:
            raise ValueError('fixture patch output differs from reviewed overlay: ' + change['path'])
    report = {
        'schema_version': 1, 'target': target, 'manifest_sha256': sha(FIXTURES / 'manifest.json'),
        'patch': {key: selected[key] for key in ('path', 'before_sha256', 'after_sha256', 'patch_sha256')},
        'additional_patches': selected.get('additional_patches', []),
        'retained_test_files': selected['retained_test_files'],
        'hosts_sha256': manifest['hosts']['sha256'],
        'java_properties': ['-Djdk.net.hosts.file=' + str(directory / 'hosts'),
                            '-Dambisgis.fixture.events=' + str(directory / 'events.jsonl')],
        'server_owner': 'native test JVM; no external fixture service',
        'socket_scope': '127.0.0.1, ephemeral ports; separate runtime isolation required',
        'readiness': ('WireMockClassRule startup barrier' if target == 'xml' else
                      'HTTP 200 on private readiness path; 2000 ms connect/read timeouts'),
        'cleanup': ('WireMockClassRule teardown and parent process-group timeout' if target == 'xml' else
                    'test teardown stops each owned HttpServer; parent process-group timeout'),
        'assertions_changed': False,
        'new_skips': False,
    }
    write_json(directory / 'prepared.json', report)
    return report


def finalize(output, target):
    """Verify retained fixture inputs and successful MapFish server cleanup."""
    if target not in ('xml', 'mapfish'):
        raise ValueError('HTTP fixture only supports XML and MapFish')
    directory = Path(output) / 'http-fixture'
    prepared = json.loads((directory / 'prepared.json').read_text())
    if prepared['target'] != target or sha(directory / 'hosts') != prepared['hosts_sha256']:
        raise ValueError('fixture preparation/hosts changed during execution')
    result = {'target': target, 'hosts_unchanged': True}
    if target == 'mapfish':
        path = directory / 'events.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines()]
        if not events:
            raise ValueError('native HTTP fixture lifecycle evidence missing')
        active = {}
        started = stopped = 0
        responses = Counter()
        for event in events:
            if (not isinstance(event, dict) or type(event.get('port')) is not int or
                    not 1 <= event['port'] <= 65535 or not isinstance(event.get('event'), str)):
                raise ValueError('malformed native HTTP fixture event')
            port, operation = event['port'], event['event']
            if operation == 'response':
                if (set(event) != {'event', 'port', 'path', 'status'} or
                        not isinstance(event['path'], str) or event['path'] not in RESPONSE_STATUSES or
                        type(event['status']) is not int or event['status'] != RESPONSE_STATUSES[event['path']]):
                    raise ValueError('malformed native HTTP fixture response event')
                if active.get(port) != 'ready':
                    raise ValueError('native HTTP response outside ready fixture lifecycle')
                responses[event['path']] += 1
                continue
            if set(event) != {'event', 'port'}:
                raise ValueError('malformed native HTTP fixture event')
            if operation == 'bound' and port not in active:
                active[port] = 'bound'
            elif operation == 'ready' and active.get(port) == 'bound':
                active[port] = 'ready'
                started += 1
            elif operation == 'stopped' and port in active:
                del active[port]
                stopped += 1
            else:
                raise ValueError('invalid native HTTP fixture lifecycle ordering')
        if active or not started:
            raise ValueError('native HTTP fixtures were not ready and cleanly stopped')
        if not REQUIRED_RESPONSES.issubset(responses):
            raise ValueError('required native HTTP error/non-image responses missing')
        result.update(events_sha256=sha(path), servers_ready=started, servers_stopped=stopped,
                      all_owned_servers_stopped=True,
                      completed_responses=[{'path': route, 'status': RESPONSE_STATUSES[route], 'count': count}
                                           for route, count in sorted(responses.items())],
                      response_evidence='headers/body written and response stream closed; client assertions remain authoritative')
    write_json(directory / 'completed.json', result)
    return result
