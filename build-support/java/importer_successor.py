#!/usr/bin/env python3
"""Build the owned importer lifecycle successor from locked, retained inputs.

The original FND-08 source selections remain available in owned_successor.py.
This recipe selects owned GeoServer and GeoTools successors and runs the new real
executor lifecycle cases after a fresh offline aggregate build. It does not
publish, install a service, or establish PLT-01 acceptance.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

import owned_successor as owned

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'importer-successor-inputs.json'
BASE = owned.SOURCES['geoserver']['commit']


def selection(value):
    if (type(value) is not dict or set(value) != {'schema_version', 'predecessor', 'sources', 'retained_inputs_sha256'}
            or value['schema_version'] != 1 or value['predecessor'] != BASE
            or type(value['sources']) is not dict or set(value['sources']) != set(owned.SOURCES)):
        raise ValueError('Importer source selection schema differs')
    if (type(value['retained_inputs_sha256']) is not str
            or not re.fullmatch('[0-9a-f]{64}', value['retained_inputs_sha256'])):
        raise ValueError('Retained input selection hash is unresolved or invalid')
    result = value['sources']
    for name, row in result.items():
        if (type(row) is not dict or set(row) != {'commit', 'tree', 'repository_id'}
                or row['repository_id'] != owned.SOURCES[name]['repository_id']
                or any(type(row[k]) is not str or not re.fullmatch('[0-9a-f]{40}', row[k])
                       for k in ('commit', 'tree'))):
            raise ValueError('Importer source identity is unresolved or invalid')
        if name == 'geowebcache' and row != owned.SOURCES[name]:
            raise ValueError('Unchanged owned root selection differs')
    if result['geoserver']['commit'] == BASE:
        raise ValueError('Importer successor must differ from predecessor')
    if result['geotools']['commit'] == owned.SOURCES['geotools']['commit']:
        raise ValueError('GeoTools source identity successor must differ from predecessor')
    return result


def execute(command, cwd, env, stream, timeout):
    """Retain the child PID until final abnormal-path process-group signals.

    Only this newly created session is signalled. WNOWAIT prevents a reaped
    leader's PID from being reused before its descendants receive cleanup.
    """
    if type(timeout) is not int or timeout <= 0:
        raise ValueError('A positive finite timeout is required')
    child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    identity_retained = True

    def observe_exit(seconds):
        nonlocal identity_retained
        deadline = time.monotonic() + seconds
        while True:
            try:
                event = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                identity_retained = False
                raise
            if event is not None:
                if event.si_pid != child.pid:
                    identity_retained = False
                    raise RuntimeError('Owned wrapper wait identity differs')
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, seconds)
            time.sleep(min(0.05, remaining))

    def send(sig):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            pass

    try:
        observe_exit(timeout)
    except BaseException:
        try:
            if identity_retained:
                send(signal.SIGTERM)
                try:
                    observe_exit(10)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if identity_retained:
                try:
                    send(signal.SIGKILL)
                finally:
                    child.wait(timeout=10)
        raise
    return child.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('recovered', 'geotools-repo', 'geoserver-repo', 'custody',
                'toolchain-custody', 'tools', 'output'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    inputs = json.loads(MANIFEST.read_text())
    sources = selection(inputs)
    # The exact full tree is checked by export_owned before native execution.
    # Preserve the accepted baseline's shared history; no replacement snapshot.
    owned.git(args.geoserver_repo, 'merge-base', '--is-ancestor', BASE,
              sources['geoserver']['commit'])
    owned.git(args.geotools_repo, 'merge-base', '--is-ancestor',
              owned.SOURCES['geotools']['commit'], sources['geotools']['commit'])
    return owned.build(args, selections=sources, task='PLT-01',
                       purpose='owned importer queue lifecycle successor',
                       test_module='org.geoserver.importer:gs-importer-core',
                       test_selector='org.geoserver.importer.ImporterShutdownTest', expected_test_count=3,
                       expected_retained_inputs_sha256=inputs['retained_inputs_sha256'],
                       scm_metadata=True,
                       executor=execute)


if __name__ == '__main__':
    raise SystemExit(main())
