#!/usr/bin/env python3
"""Run candidate PostGIS regression targets on a fresh, private PostgreSQL cluster.

The build directory must be RUN/build/postgis, created by build.py, with the
same RUN/prefix and completed source-identity receipts. Per-invocation Perl
artifacts remain separate so normal, self-upgrade, raster and topology tests
cannot overwrite one another's evidence. This is not earlier-version upgrade
coverage; run validate_database.py's two upgrade phases for that evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from validate_database import Probe, TARGET_POSTGIS, contained, digest, require, write_json

CANDIDATES = {'postgis': '9816f82458db774e62906cfb2c4f01f8b262c862',
              'postgresql': '2ff1375b5dd8bf09d8cb0e795974528180fd75ca'}


def parse_results(output: str) -> dict:
    summaries = [dict(run=int(run), failure_events=int(failed)) for run, failed in
                 re.findall(r'^Run tests:\s*(\d+)\s*\nFailed:\s*(\d+)\s*$', output, re.MULTILINE)]
    skips = [line for line in output.splitlines() if re.search(r'\bskip(?:ped|ping)?\b', line, re.I)]
    # "Skipping upgrade test ..." is control flow, not a skipped SQL test.
    test_skips = [line for line in skips if re.search(r'\bskipped\s+\(', line, re.I)]
    run = sum(item['run'] for item in summaries)
    failures = sum(item['failure_events'] for item in summaries)
    complete = bool(summaries) and run > 0
    return dict(summaries=summaries, tests_run=run, failure_events=failures,
                test_skips=len(test_skips), skip_messages=skips,
                tests_passed=run - len(test_skips) if complete and failures == 0 else None,
                complete=complete)


def record_perl(argv: list[str]) -> int:
    """Transparent make PERL launcher; ordinary Perl tools are passed through."""
    perl = os.environ['AMBISGIS_REAL_PERL']
    if not any(Path(arg).name == 'run_test.pl' for arg in argv):
        os.execv(perl, [perl, *argv])
    root = Path(os.environ['AMBISGIS_REGRESSION_ARTIFACTS'])
    invocation = Path(tempfile.mkdtemp(prefix='invocation-', dir=root))
    artifacts = invocation / 'artifacts'
    artifacts.mkdir()
    env = dict(os.environ, PGIS_REG_TMPDIR=str(artifacts))
    record = dict(command=[perl, *argv], cwd=os.getcwd(), artifact_dir=str(artifacts),
                  environment={key: env[key] for key in ('PGIS_REG_TMPDIR', 'PGHOST', 'PGPORT',
                                                        'PGUSER', 'POSTGIS_REGRESS_DB')},
                  status='running', started_at=time.time(), exit_status=None)
    write_json(invocation / 'command.json', record)
    started = time.monotonic()
    with (invocation / 'output.log').open('w') as output:
        process = subprocess.Popen([perl, *argv], env=env, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, bufsize=1)
        try:
            for line in process.stdout:
                output.write(line)
                output.flush()
                sys.stdout.write(line)
                sys.stdout.flush()
            returncode = process.wait()
        finally:
            process.stdout.close()
    record.update(exit_status=returncode, status='passed' if returncode == 0 else 'failed',
                  duration_seconds=time.monotonic() - started,
                  output_sha256=digest(invocation / 'output.log'),
                  results=parse_results((invocation / 'output.log').read_text(errors='replace')))
    write_json(invocation / 'command.json', record)
    return returncode


def verify_build(build: Path, prefix: Path) -> dict:
    require(build.name == 'postgis' and build.parent.name == 'build',
            '--build-dir must be the candidate RUN/build/postgis directory')
    run = build.parent.parent
    require((run / 'prefix').resolve() == prefix.resolve(), 'Build and installation prefix belong to different runs')
    identities = {}
    for name, commit in CANDIDATES.items():
        receipt = run / 'logs' / f'{name}-built.json'
        recorded = json.loads(receipt.read_text())
        source = recorded['input']
        require(source['name'] == name and source['commit'] == commit, f'Wrong {name} source candidate')
        marker = run / 'sources' / name / '.input-sha256'
        require(marker.read_text().strip() == source['sha256'], f'{name} extraction identity differs')
        identities[name] = dict(receipt=str(receipt), receipt_sha256=digest(receipt), input=source)
    makefile = build / 'GNUmakefile'
    match = re.search(r'^top_srcdir\s*=\s*(.+)$', makefile.read_text(), re.MULTILINE)
    require(match is not None, 'Cannot establish configured PostGIS source directory')
    source_dir = contained(build / match[1], run / 'sources/postgis')
    require((source_dir / 'regress/run_test.pl').is_file(), 'Configured source has no regression runner')
    identities['postgis']['configured_source_dir'] = str(source_dir)
    identities['postgis']['regression_runner_sha256'] = digest(source_dir / 'regress/run_test.pl')
    identities['postgis']['configured_makefile_sha256'] = digest(makefile)
    return identities


def terminate_group(process: subprocess.Popen) -> None:
    # Only the process group created by this invocation, never unrelated services.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_target(probe: Probe, build: Path, target: str, launcher: Path, perl: str) -> dict:
    root = probe.log_dir / target
    root.mkdir()
    env = {key: value for key, value in probe.env.items()
           if not key.startswith(('POSTGIS_', 'RUNTEST', 'MAKE'))
           and key not in ('MFLAGS', 'PERL5OPT', 'PERL5LIB', 'PERLLIB', 'PERL5DB')}
    env.update(AMBISGIS_REAL_PERL=perl, AMBISGIS_REGRESSION_ARTIFACTS=str(root),
               POSTGIS_REGRESS_DB='ambisgis_' + probe.nonce[:16] + '_' + target.replace('-', '_'))
    # Explicit -j1 prevents concurrent upstream runners sharing their own DB name.
    argv = ['make', '-j1', '-C', str(build), target, 'PERL=' + str(launcher), 'RUNTESTFLAGS=']
    output = root / 'make.log'
    record = dict(name=target, argv=argv, cwd=str(probe.run_dir), build_directory=str(build),
                  log=str(output), artifact_root=str(root), started_at=time.time(), status='running',
                  environment={key: env[key] for key in ('PGHOST', 'PGPORT', 'PGUSER', 'PGDATABASE',
                      'PROJ_DATA', 'PROJ_LIB', 'PROJ_NETWORK', 'GDAL_DATA', 'LD_LIBRARY_PATH',
                      'PATH', 'POSTGIS_REGRESS_DB', 'AMBISGIS_REAL_PERL', 'AMBISGIS_REGRESSION_ARTIFACTS')})
    probe.report['commands'].append(record)
    probe.save()
    start = time.monotonic()
    try:
        with output.open('w') as stream:
            process = subprocess.Popen(argv, cwd=probe.run_dir, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                returncode = process.wait(timeout=probe.args.timeout)
            except BaseException:
                terminate_group(process)
                raise
        record['exit_status'] = returncode
    except subprocess.TimeoutExpired:
        record.update(exit_status=None, timed_out=True)
    finally:
        record['duration_seconds'] = time.monotonic() - start
        record['log_sha256'] = digest(output)
        record['results'] = parse_results(output.read_text(errors='replace'))
        record['invocations'] = []
        for receipt in sorted(root.glob('invocation-*/command.json')):
            invocation = json.loads(receipt.read_text())
            invocation['receipt'] = str(receipt)
            # Preserve actual final artifact names, including diff/error files.
            invocation['artifacts'] = [dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path))
                                      for path in sorted(receipt.parent.rglob('*')) if path.is_file()]
            record['invocations'].append(invocation)
        results = record['results']
        passed = (record.get('exit_status') == 0 and results['complete'] and
                  results['failure_events'] == 0 and results['test_skips'] == 0 and
                  bool(record['invocations']) and
                  all(item.get('exit_status') == 0 and item.get('results', {}).get('complete')
                      for item in record['invocations']))
        record['status'] = 'passed' if passed else 'failed'
        probe.save()
    return record


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--build-dir', required=True)
    parser.add_argument('--timeout', type=int, default=1800, help='Seconds per make target')
    for component in ('geos', 'proj', 'gdal', 'json-c', 'protobuf-c'):
        parser.add_argument('--expected-' + component)
    args = parser.parse_args(argv)
    args.phase, args.upgrade_state = 'regression', None
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    probe = None
    try:
        probe = Probe(args)
        print(f'Regression report: {probe.log_dir / "report.json"}', flush=True)
        build = Path(args.build_dir).resolve()
        probe.report['build_inputs'] = verify_build(build, probe.prefix)
        probe.report['kind'] = 'ambisgis-postgis-regression-probe-v1'
        probe.report['limits'].append('Upstream suite self-upgrade cases do not establish an earlier-version upgrade.')
        probe.preflight()
        probe.start()
        probe.extensions('identity_probe', TARGET_POSTGIS)
        probe.versions('identity_probe', TARGET_POSTGIS)
        perl = shutil.which('perl', path=os.defpath)
        require(perl is not None, 'Host Perl is required by the retained source regression runner')
        launcher = probe.run_dir / 'record-perl'
        launcher.write_text('#!' + sys.executable + '\nimport sys\nsys.path.insert(0, ' +
                            repr(str(Path(__file__).resolve().parent)) + ')\n' +
                            'from regress_database import record_perl\nsys.exit(record_perl(sys.argv[1:]))\n')
        launcher.chmod(0o700)
        probe.report['perl'] = dict(path=perl, sha256=digest(Path(perl)))
        probe.report['suites'] = []
        for target in ('check-regress', 'installcheck-base'):
            print(f'Running {target} on owned disposable cluster', flush=True)
            try:
                result = run_target(probe, build, target, launcher, perl)
                probe.report['suites'].append(dict(target=target, status=result['status'],
                                                  results=result['results'], log=result['log']))
                if result['status'] != 'passed':
                    probe.report['failures'].append(f'{target} failed or omitted expected test evidence: {result["log"]}')
            except Exception as exc:
                # A failure in one target must not hide the other target's outcome.
                probe.report['suites'].append(dict(target=target, status='failed', error=str(exc)))
                probe.report['failures'].append(f'{target}: {exc}')
        probe.report['status'] = 'failed' if probe.report['failures'] else 'passed'
    except (Exception, KeyboardInterrupt) as exc:
        if probe:
            probe.report['status'] = 'failed'
            probe.report['failures'].append(str(exc))
        print(f'Regression validation failed: {exc}', file=sys.stderr)
    finally:
        if probe:
            try:
                probe.stop()
            except (Exception, KeyboardInterrupt) as exc:
                probe.report['status'] = 'failed'
                probe.report['failures'].append(f'Cluster shutdown failed: {exc}')
            probe.report['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            probe.save()
            try:
                probe.socket_dir.rmdir()
            except OSError:
                pass
    return 0 if probe and probe.report['status'] == 'passed' else 1


if __name__ == '__main__':
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt('Regression probe interrupted; stopping own cluster and process group')
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
