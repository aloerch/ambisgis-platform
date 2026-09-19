#!/usr/bin/env python3
"""Export a read-only snapshot of local FND-02 build evidence.

No builds, tests, cluster starts, downloads or acceptance decisions occur here.
Version/ldd queries inspect trusted local tools and built artifacts. Counts are
quoted from actual summaries; CTest command success never implies that every
internal assertion or optional fixture ran. --workspace replaces its absolute
path with <workspace> in JSON, but is not a general secret scrubber. Review the
result before publication. The output must be a new file outside the build run.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ENV_KEYS = set('PATH HOME TMPDIR LANG LC_ALL TZ CC CXX CFLAGS CXXFLAGS CPPFLAGS '
               'LDFLAGS LD_LIBRARY_PATH PKG_CONFIG_LIBDIR CMAKE_PREFIX_PATH '
               'PROJ_DATA PROJ_LIB PROJ_NETWORK GDAL_DATA PGHOST PGPORT PGUSER '
               'PGDATABASE'.split())
TOOLS = 'gcc g++ cc c++ ld as ar ranlib cmake ctest make ninja python3 perl autoconf automake aclocal libtoolize pkg-config bison flex m4 bash tar sed awk git'.split()
BINARIES = 'pg_config postgres initdb pg_ctl psql pg_dump pg_restore geos-config geosop proj projinfo cs2cs gdal-config gdalinfo ogrinfo protoc protoc-c sqlite3'.split()
TEST_ARTIFACTS = {'LastTest.log', 'LastTestsFailed.log', 'LastTestsDisabled.log',
                  'CTestCostData.txt', 'Test.xml', 'CMakeCache.txt',
                  'CTestTestfile.cmake', 'regression.diffs', 'regression.out',
                  'regress_log', 'test-suite.log'}
SUMMARY = re.compile(r'(tests? (?:passed|failed|skipped)|tests? out of|tests? from|'
                     r'\[\s*(?:PASSED|FAILED|SKIPPED)\s*\]|'
                     r'^(?:Run Summary:|\s*(?:suites|tests|asserts)\s+\d)|'
                     r'CUnit Internal Test Results|Total Number of Assertions:|'
                     r'^\s*Failures:|^All \d+ tests passed|'
                     r'^\s*(?:Passed|Failed|Skipped|PASS|FAIL|SKIP):?\s*\d+|'
                     r'^(?:Ran|Total) \d+ tests|errors were expected|'
                     r'Failed to parse xstc/|No tests were found)', re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def metadata(path):
    result = {'path': str(path)}
    try:
        before = path.stat()
        if not path.is_file():
            return dict(result, error='not a regular file')
        with path.open('rb') as stream:
            value = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = path.stat()
        result.update(resolved_path=str(path.resolve()), bytes=after.st_size,
                      sha256=value, mtime_ns=after.st_mtime_ns,
                      stable_during_hash=(before.st_size, before.st_mtime_ns) ==
                                         (after.st_size, after.st_mtime_ns))
    except OSError as exc:
        result['error'] = str(exc)
    return result


def safe_environment(value):
    return {key: val for key, val in value.items() if key in ENV_KEYS}


def sanitize_records(value):
    """Copy recorded data but never export arbitrary environment variables."""
    if isinstance(value, dict):
        return {key: safe_environment(val) if key == 'environment' and isinstance(val, dict)
                else sanitize_records(val) for key, val in value.items()}
    if isinstance(value, list):
        return [sanitize_records(item) for item in value]
    return value


def parse_summaries(text):
    lines = text.splitlines()
    observed = [{'line': number, 'text': line} for number, line in enumerate(lines, 1)
                if SUMMARY.search(line)]
    ctest = [{'reported_pass_percent': int(m[1]), 'reported_failed': int(m[2]),
              'reported_total': int(m[3])}
             for m in re.finditer(r'(\d+)% tests passed, (\d+) tests failed out of (\d+)', text)]
    postgres = [{'reported_passed': int(m[1])}
                for m in re.finditer(r'^\s*All (\d+) tests passed\.\s*$', text, re.M)]
    pg_failed = [{'reported_failed': int(m[1]), 'reported_total': int(m[2])}
                 for m in re.finditer(r'(\d+) of (\d+) tests failed', text)]
    gtest = []
    for match in re.finditer(r'^\[\s*(PASSED|FAILED|SKIPPED)\s*\]\s+(\d+) tests?(?:[.,]|$)', text, re.M):
        gtest.append({'reported_status': match[1], 'reported_count': int(match[2])})
    cunit = []
    for match in re.finditer(r'^\s*(suites|tests|asserts)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(?:\s+(\d+))?\s*$', text, re.M):
        cunit.append({'kind': match[1], 'column_counts': [int(x) for x in match.groups()[1:] if x],
                      'meaning': 'columns must be interpreted with the retained Run Summary header'})
    return {'observed_summary_lines': observed, 'ctest_summary_counts': ctest,
            'postgres_all_passed_summaries': postgres, 'postgres_failure_summaries': pg_failed,
            'gtest_reported_counts': gtest, 'cunit_summary_rows': cunit,
            'counting_limit': 'Observed summaries may overlap; do not sum wrapper and internal counts.'}


def read_json(path, problems):
    try:
        return sanitize_records(json.loads(path.read_text()))
    except (OSError, ValueError) as exc:
        problems.append({'path': str(path), 'error': str(exc)})
        return None


def read_commands(run, problems):
    path = run / 'logs/commands.jsonl'
    completed = []
    try:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            try:
                record = sanitize_records(json.loads(line))
                record['receipt_line'] = number
                completed.append(record)
            except ValueError as exc:
                problems.append({'path': str(path), 'line': number, 'error': str(exc)})
    except OSError as exc:
        problems.append({'path': str(path), 'error': str(exc)})
    known = {(r.get('log'), r.get('started_utc')) for r in completed}
    for path in sorted((run / 'logs').glob('command-*.json')):
        record = read_json(path, problems)
        if record and (record.get('log'), record.get('started_utc')) not in known:
            record['standalone_receipt'] = str(path)
            completed.append(record)
    for record in completed:
        if record.get('log'):
            path = Path(record['log'])
            if not path.is_absolute():
                path = run / path
            if not path.resolve().is_relative_to(run):
                problems.append({'path': str(path), 'error': 'command log outside run; not read'})
                continue
            record['observed_log'] = metadata(path)
            expected = record.get('log_sha256')
            record['recorded_log_hash_matches'] = (record['observed_log'].get('sha256') == expected
                                                   if expected else None)
            try:
                record['test_summaries'] = parse_summaries(path.read_text(errors='replace'))
            except OSError:
                pass
    return completed


def query(argv, cwd, prefix=None):
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
    if prefix:
        env['LD_LIBRARY_PATH'] = f'{prefix}/lib:{prefix}/lib64'
    record = {'command': list(map(str, argv)), 'cwd': str(cwd),
              'environment': env, 'observed_at': now()}
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=30, check=False)
        record.update(exit_status=result.returncode, output=result.stdout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        record.update(exit_status=None, error=str(exc))
    return record


def tool_inventory(run):
    inventory = []
    for name in TOOLS:
        path = Path('/usr/bin') / name
        record = {'name': name, 'identity': metadata(path), 'custody': 'unretained host tool'}
        if path.is_file():
            record['version_query'] = query([str(path), '--version'], run)
        inventory.append(record)
    return inventory


def runtime_inventory(run):
    prefix = run / 'prefix'
    paths = {prefix / 'bin' / name for name in BINARIES if (prefix / 'bin' / name).is_file()}
    for directory in (prefix / 'lib', prefix / 'lib64', prefix / 'lib/postgresql'):
        paths.update(path for path in directory.glob('*.so*') if path.is_file())
    # Each real object is queried once; record aliases without duplicating ldd output.
    aliases = {}
    for path in sorted(paths):
        aliases.setdefault(path.resolve(), []).append(str(path))
    artifacts, dependencies = [], {}
    for path, names in sorted(aliases.items()):
        record = {'identity': metadata(path), 'aliases': names,
                  'ldd': query(['/usr/bin/ldd', str(path)], run, prefix)}
        for line in record['ldd'].get('output', '').splitlines():
            match = re.search(r'=>\s+(/\S+)|^\s*(/\S+)\s+\(', line)
            if not match:
                continue
            resolved = Path(match[1] or match[2]).resolve()
            if str(resolved) not in dependencies:
                dependencies[str(resolved)] = {
                    'identity': metadata(resolved),
                    'custody': ('built in selected prefix; see source receipts'
                                if resolved.is_relative_to(prefix.resolve()) else 'unretained host library')}
        if any(Path(name).name in ('postgres', 'pg_config', 'psql', 'protoc', 'protoc-c') for name in names):
            record['version_query'] = query([str(path), '--version'], run, prefix)
        artifacts.append(record)
    return {'artifacts': artifacts, 'resolved_libraries': list(dependencies.values()),
            'limit': 'ldd covers observed dynamic linkage; no claim of static/compiler/sysroot closure.'}


def collect(args):
    run = args.run.resolve()
    problems = []
    manifest = read_json(args.inputs, problems)
    if manifest is None:
        raise ValueError('Cannot collect without a readable input manifest')
    report = {'schema_version': 1, 'kind': 'ambisgis-postgis-build-evidence-snapshot',
              'collection_started_utc': now(), 'run': str(run),
              'kernel': {'system': os.uname().sysname, 'release': os.uname().release,
                         'version': os.uname().version, 'machine': os.uname().machine},
              'collector': metadata(Path(__file__)), 'input_manifest': metadata(args.inputs),
              'manifest': manifest, 'collection_problems': problems,
              'acceptance': 'not assessed; snapshot is not release or whole-product independence acceptance',
              'limits': ['Concurrent build files can change while collected; per-file hash stability is recorded.',
                         'Historical failed commands remain failures even after a later successful retry.',
                         'Latest LastTest.log may replace an earlier test run; command logs retain historical summaries.',
                         'Compiler, libc, libstdc++, loader and other reported host inputs remain unretained.',
                         'No byte-identical rebuild, full dependency closure or upstream-disconnected repair is claimed.']}
    try:
        with (run / 'build.lock').open('rb') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                report['build_lock_held'] = False
            except BlockingIOError:
                report['build_lock_held'] = True
    except FileNotFoundError:
        report['build_lock_held'] = None
    commands = read_commands(run, problems)
    report['commands'] = commands
    report['command_counts'] = {
        'recorded': len(commands),
        'exited_zero': sum(r.get('exit_status') == 0 for r in commands),
        'exited_nonzero': sum(isinstance(r.get('exit_status'), int) and r['exit_status'] != 0 for r in commands),
        'no_exit_status': sum(r.get('exit_status') is None for r in commands)}
    report['built_component_records'] = []
    for path in sorted((run / 'logs').glob('*-built.json')):
        report['built_component_records'].append({'identity': metadata(path), 'record': read_json(path, problems)})
    report['retained_inputs'] = []
    for item in manifest['inputs']:
        entry = {'name': item['name'], 'artifact': item['artifact'], 'recorded_sha256': item['sha256']}
        if args.custody:
            entry['observed'] = metadata(args.custody / item['artifact'])
            entry['hash_matches'] = entry['observed'].get('sha256') == item['sha256']
        else:
            entry['observation'] = 'Manifest identity only; --custody not supplied'
        report['retained_inputs'].append(entry)
    artifacts, tests, database_reports = [], [], []
    declarations = {}
    # Traverse only evidence-bearing build/log/database directories; source trees
    # and a database cluster's raw storage files are not published or hashed here.
    roots = [run / 'logs', run / 'build']
    roots += [p for p in run.iterdir() if p.is_dir() and p.name not in
              ('logs', 'build', 'sources', 'prefix', 'home', 'tmp')]
    for root in roots:
        for directory, subdirs, names in os.walk(root, followlinks=False):
            subdirs[:] = sorted(s for s in subdirs if s not in ('data', 'pgdata', 'base', 'global', 'pg_wal', '.git'))
            for name in sorted(names):
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                in_logs = path.is_relative_to(run / 'logs')
                if in_logs or name in TEST_ARTIFACTS or name in ('report.json', 'upgrade-state.json'):
                    artifacts.append(metadata(path))
                if name in ('LastTest.log', 'test-suite.log', 'regression.out', 'regress_log'):
                    text = path.read_text(errors='replace')
                    tests.append({'path': str(path), 'summaries': parse_summaries(text),
                                  'ctest_wrapper_passed_markers': len(re.findall(r'^Test Passed\.$', text, re.M)),
                                  'ctest_wrapper_failed_markers': len(re.findall(r'^Test Failed\.$', text, re.M))})
                if name == 'CTestTestfile.cmake':
                    component = path.relative_to(run / 'build').parts[0]
                    found = re.findall(r'^add_test\((?:"([^"]+)"|([^\s)]+))', path.read_text(), re.M)
                    declarations.setdefault(component, []).extend({'name': a or b, 'file': str(path)} for a, b in found)
                if name == 'report.json':
                    value = read_json(path, problems)
                    if value and value.get('kind') == 'ambisgis-postgis-database-probe-v1':
                        for command in value.get('commands', []):
                            for field in ('log', 'input_sql'):
                                if not command.get(field):
                                    continue
                                evidence_path = Path(command[field])
                                if not evidence_path.resolve().is_relative_to(run):
                                    problems.append({'path': str(evidence_path), 'error': 'database evidence outside run; not read'})
                                    continue
                                observation = metadata(evidence_path)
                                artifacts.append(observation)
                                command['observed_' + field] = observation
                                if field == 'log' and command.get('log_sha256'):
                                    command['recorded_log_hash_matches'] = observation.get('sha256') == command['log_sha256']
                        database_reports.append({'identity': metadata(path), 'report': value})
    report['evidence_artifacts'] = artifacts
    report['latest_test_logs'] = tests
    report['ctest_static_registration'] = {
        component: {'observed_add_test_declarations': len(rows), 'declarations': rows,
                    'limit': 'Static generated declarations; executed counts come from actual ctest summaries.'}
        for component, rows in declarations.items()}
    report['database_reports'] = database_reports
    report['host_tools'] = tool_inventory(run)
    report['runtime'] = runtime_inventory(run)
    report['snapshot_status'] = 'incomplete_or_unverified_snapshot'
    report['snapshot_reason'] = 'No independent slice-completion receipt is defined; inspect explicit component and database results.'
    report['collection_finished_utc'] = now()
    return report


def normalize(value, workspace):
    if isinstance(value, str):
        return value.replace(str(workspace), '<workspace>')
    if isinstance(value, list):
        return [normalize(item, workspace) for item in value]
    if isinstance(value, dict):
        return {normalize(key, workspace): normalize(item, workspace) for key, item in value.items()}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--custody', type=Path, help='Also hash actual retained source archives')
    parser.add_argument('--workspace', type=Path, help='Replace this absolute path with <workspace> in output')
    args = parser.parse_args()
    if not args.run.is_dir():
        parser.error('--run must be an existing run directory')
    if args.output.resolve().is_relative_to(args.run.resolve()):
        parser.error('--output must be outside --run to avoid modifying collected evidence')
    if args.output.exists() or args.output.is_symlink():
        parser.error('--output must be a new file')
    report = collect(args)
    if args.workspace:
        report = normalize(report, args.workspace.resolve())
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'snapshot_status': report['snapshot_status'],
                      'command_counts': report['command_counts'],
                      'collection_problems': len(report['collection_problems'])}))


if __name__ == '__main__':
    main()
