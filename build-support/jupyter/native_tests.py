#!/usr/bin/env python3
"""Run bounded native Hub/Lab tests against an existing owned-source build.

HTTP fixtures require loopback networking. This driver does not enforce external
network denial. It uses retained dependencies and prohibits package acquisition.
Each invocation creates a new private evidence directory and preserves old runs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


SUITES = ('hub-python', 'lab-python', 'hub-jsx', 'lab-coreutils', 'lab-nbformat')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def redact(text):
    # Preserve diagnostic structure while removing generated authentication data.
    return re.sub(r'(?i)(\b(?:token|password|secret)(?:=|\s*:\s*)[\"\']?)[^\s\"\'&<>]+', r'\1[REDACTED]', text)


def counts(path, kind):
    if kind == 'pytest':
        cases = list(ET.parse(path).getroot().iter('testcase'))
        return {'total': len(cases), **{name: sum(case.find(tag) is not None for case in cases)
                for name, tag in [('failed', 'failure'), ('errors', 'error'), ('skipped', 'skipped')]}}
    data = json.loads(path.read_text())
    return {name: data[key] for name, key in [('total', 'numTotalTests'), ('passed', 'numPassedTests'),
            ('failed', 'numFailedTests'), ('skipped', 'numPendingTests')]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--suite', choices=SUITES, action='append')
    parser.add_argument('--pam-library-dir', type=Path, help='Isolated built Linux-PAM library directory; never installs host PAM configuration')
    args = parser.parse_args()
    run = args.run.resolve()
    output = (args.output or run/'native-tests').absolute()
    build_report = run/'build-report.json'
    build = json.loads(build_report.read_text())
    if build['status'] != 'passed':
        raise ValueError('native tests require a successful build report')
    for wheel in build['wheels']:
        path = run/wheel['path']
        if not path.resolve().is_relative_to(run) or digest(path) != wheel['sha256']:
            raise ValueError('built wheel mismatch: '+str(path))
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ('home', 'tmp', 'logs'):
        (output/name).mkdir(mode=0o700)
    report = {
        'started': now(), 'status': 'running', 'run': str(run),
        'recipe_sha256': digest(Path(__file__)), 'build_report_sha256': digest(build_report),
        'wheels': build['wheels'], 'commands': [],
        'scope': 'Selected native source suites using dependencies from the isolated build environments.',
        'network': 'Loopback permitted; upstream HTTP fixtures use Tornado bind_unused_port at 127.0.0.1. External network denial is not enforced by this driver.',
        'omissions': ['Full upstream Python and frontend suites', 'Real browser/accessibility tests',
                      'Production authentication, tenant isolation and spatial profiles'],
    }
    (output/'native_tests.py').write_bytes(Path(__file__).read_bytes())
    hub, lab = run/'sources/jupyterhub', run/'sources/jupyterlab'
    pam_library_dir = args.pam_library_dir.resolve() if args.pam_library_dir else None
    if pam_library_dir:
        report['pam_libraries'] = []
        for name in ('libpam.so', 'libpam.so.0', 'libpam_misc.so', 'libpam_misc.so.0'):
            path = pam_library_dir/name
            if not path.is_file() or not path.resolve().is_relative_to(pam_library_dir):
                raise ValueError('unsafe or missing isolated PAM library: '+str(path))
            report['pam_libraries'].append({'path': str(path), 'resolved': str(path.resolve()), 'sha256': digest(path)})
    base_env = {
        'HOME': str(output/'home'), 'TMPDIR': str(output/'tmp'),
        'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'PYTHONNOUSERSITE': '1',
        'PIP_CONFIG_FILE': os.devnull, 'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
        'npm_config_offline': 'true', 'npm_config_ignore_scripts': 'true',
        'npm_config_audit': 'false', 'npm_config_fund': 'false',
        'npm_config_update_notifier': 'false', 'npm_config_cache': str(output/'npm-cache'),
        'YARN_ENABLE_NETWORK': 'false', 'YARN_ENABLE_SCRIPTS': 'false',
        'YARN_ENABLE_TELEMETRY': 'false', 'NODE_OPTIONS': '--max-old-space-size=6144',
        'JUPYTER_PLATFORM_DIRS': '1',
    }

    if pam_library_dir:
        base_env['LD_LIBRARY_PATH'] = str(pam_library_dir)

    def save():
        (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')

    def command(name, argv, cwd, pyenv='user', result=None, kind=None):
        env = dict(base_env)
        env['PATH'] = ':'.join(str(x) for x in [run/(pyenv+'-env/bin'), run/'build-env/bin',
                              run/'sources/node-v24.21.0-linux-x64/bin', Path('/usr/bin'), Path('/bin')])
        env['JEST_JUNIT_OUTPUT_DIR'] = str(output)
        env['JEST_JUNIT_OUTPUT_NAME'] = name+'-junit.xml'
        log = output/'logs'/(name+'.log')
        item = {'name': name, 'argv': [str(x) for x in argv], 'cwd': str(cwd),
                'started': now(), 'log': str(log.relative_to(output))}
        report['commands'].append(item)
        save()
        print('starting '+name, flush=True)
        started = time.monotonic()
        with log.open('x') as stream:
            process = subprocess.Popen(item['argv'], cwd=cwd, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                returncode = process.wait(timeout=900)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                returncode = 124
                item['timeout_seconds'] = 900
        log.write_text(redact(log.read_text(errors='replace')))
        item.update(exit_code=returncode, finished=now(), duration_seconds=round(time.monotonic()-started, 3),
                    log_sha256=digest(log))
        if result and result.exists():
            try:
                item['counts'] = counts(result, kind)
            except (ValueError, KeyError, ET.ParseError) as exc:
                item['result_parse_error'] = str(exc)
            result.write_text(redact(result.read_text(errors='replace')))
            item['result'] = str(result.relative_to(output))
            item['result_sha256'] = digest(result)
        junit = output/(name+'-junit.xml')
        if junit.exists():
            junit.write_text(redact(junit.read_text(errors='replace')))
        save()
        print(name+' '+json.dumps({k: item[k] for k in ('exit_code', 'counts') if k in item}), flush=True)
        return returncode

    selected = args.suite or SUITES
    for suite in selected:
        if suite.endswith('-python'):
            is_hub = suite == 'hub-python'
            cwd = hub if is_hub else lab
            pyenv = 'hub' if is_hub else 'user'
            prefix = 'jupyterhub/tests/' if is_hub else 'jupyterlab/tests/'
            modules = ['test_utils.py', 'test_slugs.py', 'test_objects.py', 'test_version.py'] if is_hub else [
                'test_extensions.py', 'test_plugin_manager_handler.py', 'test_custom_css_handler.py']
            result = output/(suite+'.xml')
            command(suite, [run/(pyenv+'-env/bin/python'), '-m', 'pytest',
                    *[prefix+x for x in modules], '--junitxml='+str(result),
                    '--basetemp='+str(output/(suite+'-tmp')), '-o', 'cache_dir='+str(output/(suite+'-cache'))],
                    cwd, pyenv, result, 'pytest')
        else:
            if suite == 'lab-nbformat':
                code = command('lab-testing-build', ['npm', 'run', 'build'], lab/'packages/testing')
                if code:
                    report['commands'].append({'name': suite, 'status': 'blocked',
                                               'reason': 'native testing package did not compile'})
                    save()
                    continue
            cwd = hub/'jsx' if suite == 'hub-jsx' else lab/'packages'/suite.removeprefix('lab-')
            result = output/(suite+'.json')
            command(suite, ['npm', 'test', '--', '--runInBand', '--json', '--outputFile='+str(result)],
                    cwd, result=result, kind='jest')
    report['status'] = 'passed' if all(item.get('exit_code') == 0 and 'result_parse_error' not in item
                                      for item in report['commands']) else 'failed'
    report['finished'] = now()
    save()
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
