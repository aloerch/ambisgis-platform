#!/usr/bin/env python3
"""Run unchanged native tests with an exact raw-Git successor fixture binding.

The historical archive materialized one eol=crlf fixture. The successor archive
contains complete Git blob bytes. Only that unused synthetic authentication key
has different fixture bytes; test selections and expected golden outputs stay
unchanged. Reconstruct and check the entire historical fixture digest as well as
the new digest before deriving a separately retained successor manifest.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from common import require, sha, save, inventory
import native_tests
from successor_build import COMMIT, HERE
from successor_stage import verify_build

SELECTION_SHA = '82031c56c96fa920e24eabffe17ff0a086bb6cfa26306c77c8765899b450a52f'
FIXTURE = 'tests/testdata/auth_system/certs_keys/donald_key_DSA_crlf.pem'
RAW_SHA = '36f50d5940edd3e574f25c9a35590b0f3a230d71353c5312eed457e2f55e43df'
CHECKOUT_SHA = '4f86dc58b808e8c1a02be05842c77c69b491626396cefffd367f5dacacdc9a0e'
FIXTURE_SHA = 'f4cbc240fa1c31cc75b3a6de0d79c5324301d0289d4bf41e29e517fedd30e11d'


def checked_newline_pair(raw):
    require(hashlib.sha256(raw).hexdigest() == RAW_SHA and b'\r' not in raw and raw.count(b'\n') == 20,
            'unexpected raw-Git synthetic key fixture')
    checkout = raw.replace(b'\n',b'\r\n')
    require(hashlib.sha256(checkout).hexdigest() == CHECKOUT_SHA,
            'declared CRLF transform differs from frozen fixture')
    return checkout


def selection_for_source(source):
    require(sha(HERE/'native-selection.json') == SELECTION_SHA, 'historical native selection changed')
    previous = native_tests.load_selection(source)
    require((source/'.gitattributes').read_text().splitlines().count(FIXTURE+' text eol=crlf') == 1,
            'exact source does not declare the fixture CRLF attribute')
    new_digest, old_digest = hashlib.sha256(), hashlib.sha256()
    count = new_size = old_size = transformed = 0
    for path in sorted((source/previous['fixture_tree']['path']).rglob('*')):
        require(not path.is_symlink(), 'unexpected fixture symlink')
        if not path.is_file(): continue
        relative = str(path.relative_to(source)); data = path.read_bytes(); old_data = data
        if relative == FIXTURE:
            old_data = checked_newline_pair(data); transformed += 1
        for digest, content in ((new_digest,data),(old_digest,old_data)):
            digest.update(relative.encode()+b'\0'+hashlib.sha256(content).hexdigest().encode()+b'\n')
        count += 1; new_size += len(data); old_size += len(old_data)
    require(transformed == 1 and count == previous['fixture_tree']['file_count'] and
            old_size == previous['fixture_tree']['bytes'] and old_digest.hexdigest() == previous['fixture_tree']['sha256'],
            'fixture changes extend beyond the single declared newline transform')
    require(new_digest.hexdigest() == FIXTURE_SHA and old_size-new_size == 20,
            'unexpected successor fixture tree')
    successor = copy.deepcopy(previous)
    successor['source_commit'] = COMMIT
    successor['fixture_tree'].update(bytes=new_size,sha256=FIXTURE_SHA)
    binding = {'historical_selection_sha256':SELECTION_SHA,'source_commit':COMMIT,
        'fixture_path':FIXTURE,'raw_git_sha256':RAW_SHA,'historical_checkout_sha256':CHECKOUT_SHA,
        'declared_attribute':'text eol=crlf','changed_fixture_files':1,'removed_cr_bytes':20,
        'historical_fixture_tree_reconstructed':True,'successor_fixture_tree':successor['fixture_tree'],
        'unchanged_fields':[key for key in previous if key not in ('source_commit','fixture_tree')],
        'scope':'Exact successor materialization metadata only; selected tests/source/golden assertions unchanged. Synthetic key is not exercised by selected methods.'}
    return successor,binding


def run(attempt, config, output):
    require(not output.exists() and not output.is_symlink(), 'fresh native successor attempt required')
    verify_build(attempt)
    config_doc = json.loads(config.read_text())
    source = attempt/'compile/sources/qgis-successor'
    require(Path(config_doc['qgis_source']).resolve() == source and
            Path(config_doc['qgis_build']).resolve() == attempt/'compile/build', 'native source/build redirected')
    selection,binding = selection_for_source(source)
    output.mkdir(parents=True)
    tooling = output/'tooling'
    for component,names in {'qgis':['native_database.py','native_tests.py'],
        'java':['configured_auth_database.py','loopback_exec.py','geofence_fixture.py'], 'postgis':['offline_exec.py']}.items():
        for name in names:
            target = tooling/component/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(HERE.parent/component/name,target)
    save(tooling/'qgis/native-selection.json',selection)
    save(output/'fixture-binding.json',binding)
    before = inventory(tooling);save(output/'tooling.json',before)
    command = [sys.executable,str(tooling/'qgis/native_database.py'),'--config',str(config),'--output',str(output/'run')]
    report = {'command':command,'result_exit_code':1,
        'fixture_binding_sha256':sha(output/'fixture-binding.json'),
        'tooling_sha256':sha(output/'tooling.json'),'build_result_sha256':sha(attempt/'result.json'),
        'adapter_sha256':sha(Path(__file__))}
    try:
        with (output/'controller.log').open('x') as log:
            code = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                                  env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')).returncode
        require(before == inventory(tooling), 'native tooling changed')
        result = json.loads((output/'run/result.json').read_text())
        report.update(result_exit_code=code or result['result_exit_code'],
                      native_result_sha256=sha(output/'run/result.json'))
    except Exception as error:
        report['error'] = {'type':type(error).__name__,'message':str(error)}
        raise
    finally:
        save(output/'result.json',report)
    return report['result_exit_code']


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build-attempt','config','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.build_attempt.resolve(),args.config.resolve(),args.output.resolve()))
