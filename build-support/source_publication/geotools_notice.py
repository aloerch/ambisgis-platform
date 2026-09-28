#!/usr/bin/env python3
"""Prepare only the authorized two-file GeoTools notice successor, locally.

Default: inspect bound inputs without writing. --prepare requires inherited
Internet socket denial and a fresh output. --verify rechecks a retained receipt.
No network client, remote ref operation, lifecycle build or publication exists.
"""
from __future__ import annotations
import argparse
import difflib
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
PLATFORM = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('geotools_custody', PLATFORM/'build-support/source_restore/common.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
BASE = 'aac73e9b89821331e77f67f1dd0921e541a78cfc'
BASE_TREE = 'acfbe55e74aa9cc9d1134fadeefc4218390ad9ad'
OLD = 'f51fa68803c465f28a85c155e3e951df0d8788f7'
OLD_TREE = '60750f787dabf1a08e646e7d5f3f1497e560e94e'
CANDIDATE = '0d7a61818d73ad27135f9bb0756797bd2c4f7e10c717d3536517534eca57cf99'
AUTH_BODY = '87d79df2d4458d9570c269ff9d20310c4117f7d82c2dc23d4588ca505900da1f'
AUTH_URL = 'https://github.com/aloerch/ambisgis-platform/issues/6#issuecomment-5863464446'
PREDECESSOR = 'source-archives/ambisgis-geotools-9a4f847e8b83.bundle'
PREDECESSOR_SHA = 'c738143f1179d2a8964e11f84bfa84a24c463c95cef4e9c459b31d8b37454212'
OLD_REPO = 'build-worktrees/source-baseline-restore/run-001/repos/geotools'
REF = 'refs/heads/ambisgis/review/fnd-07-notices-v1'
ROWS = {
    'build/maven/xmlcodegen/pom.xml': {
        'sha256': 'bf9d93ada08207b72f98754a19d9f9cec4b17264c43deb08ecea2eab4e5702d1',
        'functional_date': '2026-09-20',
        'functional_platform_commit': 'd229468e1cef44f81d9be837068e0a80166b7eb7',
        'description': 'Pinned EMF common/ecore dependency management to 2.15.0.'},
    'modules/plugin/imagemosaic/pom.xml': {
        'sha256': '55ddcec1c65d32aaca83da069c854346f045fe55ca8fa024ae47ba25a6ee9bd9',
        'functional_date': '2026-09-21',
        'functional_platform_commit': 'e1b960588c51beb35f83c5f1c5d137e85a0d414c',
        'description': 'Removed Oracle-only test dependency and unused provided ojdbc14.'}}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def authorize(document):
    comment = document.get('comment', {})
    C.require(comment.get('id') == 5863464446 and comment.get('html_url') == AUTH_URL,
              'Wrong owner decision')
    C.require(comment.get('user', {}).get('login') == 'aloerch' and
              comment.get('user', {}).get('id') == 15285626, 'Wrong owner identity')
    C.require(comment.get('created_at') == '2026-09-28T04:35:51Z' and
              comment.get('updated_at') == '2026-09-28T04:35:51Z', 'Owner decision date changed')
    C.require(digest(comment.get('body', '').encode()) == AUTH_BODY and
              document.get('body_sha256') == AUTH_BODY, 'Owner decision body changed')
    return {'url': AUTH_URL, 'author': 'aloerch', 'author_id': 15285626,
            'created_at': comment['created_at'], 'body_sha256': AUTH_BODY,
            'scope': 'local GeoTools repair only; changed-source publication remains unapproved'}


def xml_configuration(data):
    C.require(b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper(), 'XML declarations forbidden')
    root = ET.fromstring(data)
    def node(el):
        return (el.tag, tuple(sorted(el.attrib.items())), el.text, el.tail,
                tuple(node(child) for child in el))
    return node(root)


def insert_notice(data, comment):
    """Insert outside the root element; preserve every original byte."""
    C.require(b'\r' not in data and data.count(b'<project ') == 1, 'Unexpected XML layout')
    C.require(comment.startswith(b'<!--\n') and comment.endswith(b'-->\n') and
              b'--' not in comment[4:-4], 'Unsafe XML comment')
    at = data.index(b'<project ')
    C.require(data[:at].startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n') and
              data[:at].endswith(b'-->\n'), 'Original XML header differs')
    result = data[:at] + comment + data[at:]
    C.require(xml_configuration(result) == xml_configuration(data), 'Effective XML configuration changed')
    C.require(result[:at] + result[at+len(comment):] == data, 'Change exceeds insertion')
    return result


def repair_pom(path, data, notice_date):
    C.require(path in ROWS, 'Path outside two-file scope')
    row = ROWS[path]
    C.require(digest(data) == row['sha256'], 'POM input hash changed: ' + path)
    C.require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', notice_date) is not None and
              date.fromisoformat(notice_date) >= date(2026, 9, 28), 'Invalid/backdated notice date')
    comment = ('<!--\n'
        '  AmbisGIS modification notice (original licenses and copyrights retained).\n'
        f"  Functional change recorded {row['functional_date']}: {row['description']}\n"
        '  Accepted source changes materialized 2026-09-22 (UTC-07:00).\n'
        f'  This notice added {notice_date} (UTC); no effective POM behavior changed.\n'
        '-->\n').encode()
    return insert_notice(data, comment), comment


def notice_patch(before, notice_date):
    return ''.join(''.join(difflib.unified_diff(before[p].decode().splitlines(True),
        repair_pom(p, before[p], notice_date)[0].decode().splitlines(True),
        fromfile='a/'+p, tofile='b/'+p, n=3)) for p in ROWS).encode()


def publication_proposal():
    return {'review_ref': REF, 'canonical_ref': 'refs/heads/ambisgis/main',
            'creation_only': True, 'expected_old_commit': None,
            'expected_old_scope': 'proposal only; fresh live absence and repository settings must be recorded separately and rechecked before future writes',
            'preserve_default': 'main', 'preserve_actions_enabled': False}


def recovery_result():
    return {'verified': True, 'comparison_equal': True, 'fsck': 'passed',
            'independent_object_store': True, 'alternates_shared_objects_donor_fallback': False}


def network_denied():
    import errno
    import socket
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            sock = socket.socket(family, socket.SOCK_STREAM)
        except OSError as exc:
            C.require(exc.errno == errno.EPERM, 'Unexpected socket failure')
        else:
            sock.close()
            raise ValueError('Preparation requires inherited Internet socket denial')


def inputs(workspace, authorization):
    C.require(C.sha(PLATFORM/'plan/candidates/fnd-02-candidate.json') == CANDIDATE, 'Accepted manifest changed')
    authority = authorize(json.loads(Path(authorization).read_text()))
    source = C.confined(workspace, OLD_REPO)
    C.independent(source)
    C.require(C.git(source, 'rev-parse', OLD+'^{tree}').strip().decode() == OLD_TREE, 'Wrong old source tree')
    C.require(C.git(source, 'rev-list', '--parents', '-n', '1', OLD).decode().split() == [OLD, BASE], 'Wrong old source parent')
    C.require(C.git(source, 'rev-parse', BASE+'^{tree}').strip().decode() == BASE_TREE, 'Wrong accepted base tree')
    C.require(C.git(source, 'diff', '--name-only', BASE, OLD).decode().splitlines() == sorted(ROWS), 'Wrong functional source paths')
    before = {p: C.git(source, 'show', OLD+':'+p) for p in ROWS}
    for p, data in before.items():
        C.require(digest(data) == ROWS[p]['sha256'], 'Wrong source POM')
    bundle = C.verified_file(workspace, PREDECESSOR, PREDECESSOR_SHA, 449194517)
    C.require(not C.bundle_header(bundle)['prerequisites'], 'Base history has external prerequisites')
    return source, before, bundle, authority


def complete_comparison(repo, old_entries, commit, before, notice_date):
    actual = C.tree_entries(repo, commit)
    expected = {r['path']: r for r in old_entries}
    found = {r['path']: r for r in actual}
    C.require(found.keys() == expected.keys(), 'Complete source membership changed')
    changed = []
    for name, row in found.items():
        if row != expected[name]:
            changed.append(name)
            C.require(name in ROWS and row['mode'] == expected[name]['mode'] == '100644' and
                      row['type'] == expected[name]['type'] == 'blob', 'Unexpected source change: ' + name)
    C.require(sorted(changed) == sorted(ROWS), 'Incorrect notice change boundaries')
    checks = []
    for name in ROWS:
        data = C.git(repo, 'show', commit+':'+name)
        corrected, notice = repair_pom(name, before[name], notice_date)
        C.require(data == corrected, 'Notice output changed')
        checks.append({'path': name, **ROWS[name], 'after_sha256': digest(data),
                       'notice': notice.decode(), 'xml_configuration_equal': True,
                       'all_other_bytes_equal': True})
    C.require(C.git(repo, 'rev-list', '--parents', '-n', '1', commit).decode().split() == [commit, BASE],
              'Corrected publication commit must directly parent accepted base')
    C.require(C.git(repo, 'rev-list', commit, '^'+BASE).decode().split() == [commit], 'Unexpected newly published ancestry')
    C.require(OLD not in C.git(repo, 'rev-list', commit).decode().split(), 'Old unnotified product ancestor exposed')
    return {'tracked_entries': len(actual), 'unchanged_entries': len(actual)-2,
            'changed_paths': sorted(changed), 'files': checks,
            'old_product_is_ancestor': False, 'parent': BASE,
            'tree': C.git(repo, 'rev-parse', commit+'^{tree}').strip().decode()}


MODEL_JAVA = '''import java.nio.file.*;
import java.io.*;
import org.apache.maven.model.Model;
import org.apache.maven.model.io.xpp3.MavenXpp3Reader;
import org.apache.maven.model.io.xpp3.MavenXpp3Writer;
public class PomModel {
  public static void main(String[] a) throws Exception {
    Model m;
    try (Reader r = Files.newBufferedReader(Path.of(a[0]))) {
      m = new MavenXpp3Reader().read(r, true);
    }
    try (Writer w = Files.newBufferedWriter(Path.of(a[1]))) {
      new MavenXpp3Writer().write(w, m);
    }
  }
}
'''


def maven_models(workspace, output, before, corrected):
    spec = importlib.util.spec_from_file_location('geotools_toolchain', PLATFORM/'build-support/java/toolchain.py')
    toolchain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toolchain)
    tools = workspace/'build-worktrees/java-resolution/toolchain'
    manifest = json.loads((PLATFORM/'build-support/java/toolchain-inputs.json').read_text())
    verified = toolchain.verify_extracted(workspace/'source-archives/java-resolution/toolchain', manifest, tools)
    jdk = tools/'jdk-17.0.20.1+1'
    maven = tools/'apache-maven-3.9.16'
    output.mkdir()
    java = output/'PomModel.java'
    java.write_text(MODEL_JAVA)
    env = {k:v for k,v in os.environ.items() if k not in ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'CLASSPATH')}
    classpath = str(maven/'lib/*')
    commands = []
    def execute(argv):
        proc = subprocess.run([str(x) for x in argv], capture_output=True, env=env)
        commands.append({'argv': [str(x) for x in argv], 'exit_code': proc.returncode,
                         'stdout': proc.stdout.decode(errors='replace'), 'stderr': proc.stderr.decode(errors='replace')})
        C.save(output/('command-'+str(len(commands))+'.json'), commands[-1])
        C.require(proc.returncode == 0, 'Retained Maven model parser failed')
    execute([jdk/'bin/javac', '-cp', classpath, java])
    rows = []
    for index, name in enumerate(ROWS):
        hashes = []
        for kind, data in [('before', before[name]), ('after', corrected[name])]:
            source = output/(str(index)+'-'+kind+'.xml')
            model = output/(str(index)+'-'+kind+'-model.xml')
            source.write_bytes(data)
            execute([jdk/'bin/java', '-cp', str(output)+os.pathsep+classpath, 'PomModel', source, model])
            hashes.append(C.sha(model))
        C.require(hashes[0] == hashes[1], 'Maven model changed: '+name)
        rows.append({'path': name, 'before_model_sha256': hashes[0], 'after_model_sha256': hashes[1], 'equal': True})
    return {'toolchain': verified, 'models': rows, 'command_count': len(commands),
            'scope': 'Maven 3.9.16 strict model parser/writer configuration equality; parent/profile/build inputs unchanged by complete source comparison. No effective-POM resolver, lifecycle, package or native/runtime build executed.'}


def prepare(workspace, authorization, output):
    network_denied()
    old_repo, before, predecessor, authority = inputs(workspace, authorization)
    C.require(output.absolute() == output.resolve() and all(not x.is_symlink() for x in (output, *output.parents)), 'Unsafe output path')
    output.mkdir(parents=False, exist_ok=False)
    C.save(output/'started.json', {'started_at': datetime.now(timezone.utc).isoformat(), 'authority': authority})
    old_refs = C.git(old_repo, 'show-ref')
    old_status = C.git(old_repo, 'status', '--porcelain')
    old_entries = C.tree_entries(old_repo, OLD)
    notice_date = datetime.now(timezone.utc).date().isoformat()
    source = output/'source'
    C.restore_bundle(predecessor, source, BASE)
    corrected = {}
    for name, data in before.items():
        corrected[name], _ = repair_pom(name, data, notice_date)
        C.confined(source, name).write_bytes(corrected[name])
    C.git(source, 'add', '--', *ROWS)
    C.require(C.git(source, 'diff', '--cached', '--name-only').decode().splitlines() == sorted(ROWS), 'Unexpected staged source')
    C.git(source, '-c', 'user.name=AmbisGIS source publication repair',
          '-c', 'user.email=source-publication@ambisgis.invalid', '-c', 'commit.gpgsign=false',
          'commit', '-m', 'Preserve accepted GeoTools changes with in-file modification notices\n\n'
          'Replayed from the accepted base; old product remains separately retained.\n'
          'Local source-only publication candidate; no source publication or release approved.')
    commit = C.git(source, 'rev-parse', 'HEAD').strip().decode()
    C.git(source, 'update-ref', REF, commit, '0'*40)
    comparison = complete_comparison(source, old_entries, commit, before, notice_date)
    models = maven_models(workspace, output/'maven-models', before, corrected)
    # The patch is against the old tested product; it contains only the two notices.
    (output/'geotools-notices.patch').write_bytes(notice_patch(before, notice_date))
    delta = output/'geotools-notices.bundle'
    C.git(source, 'bundle', 'create', str(delta), REF, '^'+BASE)
    C.require(C.bundle_header(delta) == {'refs': {REF: commit}, 'prerequisites': [BASE]}, 'Incorrect corrected bundle chain')
    restored = output/'recovered'
    C.restore_bundle(predecessor, restored, BASE)
    C.git(restored, 'bundle', 'verify', str(delta))
    C.git(restored, 'bundle', 'unbundle', str(delta))
    C.git(restored, 'update-ref', REF, commit, '0'*40)
    C.git(restored, 'checkout', '--detach', commit)
    C.independent(restored)
    C.git(restored, 'fsck', '--full', '--no-reflogs')
    recovery = complete_comparison(restored, old_entries, commit, before, notice_date)
    C.require(recovery == comparison, 'Restored source differs')
    C.require(C.git(old_repo, 'show-ref') == old_refs and C.git(old_repo, 'status', '--porcelain') == old_status,
              'Original source refs or worktree changed')
    receipt = {'schema_version': 1, 'kind': 'accepted-functional-composition-publication-sidecar',
        'task': 'FND-07', 'repository': 'aloerch/ambisgis-geotools', 'repository_id': 1376927869,
        'completed_at': datetime.now(timezone.utc).isoformat(), 'authorization': authority,
        'accepted_candidate': {'path': 'plan/candidates/fnd-02-candidate.json', 'sha256': CANDIDATE, 'unchanged': True},
        'base_commit': BASE, 'base_tree': BASE_TREE, 'old_product_commit': OLD, 'old_product_tree': OLD_TREE,
        'commit': commit, 'tree': comparison['tree'], 'notice_added_utc_date': notice_date,
        'source': str(source), 'recovered': str(restored), 'comparison': comparison,
        'maven_configuration': models, 'recovery': recovery_result(),
        'bundle_chain': [ {'path': str(predecessor), 'sha256': PREDECESSOR_SHA, 'prerequisites': []},
            {'path': str(delta), 'sha256': C.sha(delta), 'bytes': delta.stat().st_size, 'prerequisites': [BASE], 'ref': REF}],
        'patch': {'path': str(output/'geotools-notices.patch'), 'sha256': C.sha(output/'geotools-notices.patch')},
        'implementation_sha256': C.sha(Path(__file__)),
        'original_source_preserved': True, 'publication_authorized': False, 'remote_writes': 0,
        'proposal': publication_proposal(),
        'limits': ['Source-only successor: old artifacts/receipts remain bound to old source.',
                   'No new package identity or Java service/native/runtime test claimed.',
                   'Original licenses/copyrights and all other source bytes retained; no blanket rights clearance.',
                   'Changed-source publication and final FND-07 acceptance require subsequent owner decision; FND-08 unstarted.']}
    finish_receipt(workspace, authorization, output, receipt)
    return receipt


def finish_receipt(workspace, authorization, output, receipt):
    # A success receipt is created only after the final source/patch/model checks.
    # Failed runs retain their output and a separate explicit failure record.
    try:
        _verify_contents(workspace, authorization, output, receipt)
    except Exception as exc:
        C.save(output/'failed.json', {'status': 'failed', 'integrity_verified': False,
               'error': str(exc), 'commit': receipt.get('commit'),
               'at': datetime.now(timezone.utc).isoformat()})
        raise
    receipt['status'] = 'verified'
    C.save(output/'receipt.json', receipt)


def verify(workspace, authorization, output, receipt_sha256):
    C.require(re.fullmatch('[0-9a-f]{64}', receipt_sha256 or '') is not None,
              'Trusted receipt SHA256 is required')
    C.require(C.sha(output/'receipt.json') == receipt_sha256, 'Receipt identity digest changed')
    receipt = json.loads((output/'receipt.json').read_text())
    C.require(receipt.get('status') == 'verified', 'Receipt is not a completed integrity check')
    _verify_contents(workspace, authorization, output, receipt)
    return {'verified': True, 'commit': receipt['commit'], 'tree': receipt['tree'],
            'receipt_sha256': receipt_sha256}


def _verify_contents(workspace, authorization, output, receipt):
    old_repo, before, _, authority = inputs(workspace, authorization)
    C.require(receipt['authorization'] == authority and receipt['accepted_candidate']['sha256'] == CANDIDATE and
              receipt['repository_id'] == 1376927869 and receipt['base_commit'] == BASE and
              receipt['old_product_commit'] == OLD and receipt['old_product_tree'] == OLD_TREE,
              'Receipt identity changed')
    C.require(receipt['publication_authorized'] is False and receipt['remote_writes'] == 0 and
              receipt['kind'] == 'accepted-functional-composition-publication-sidecar' and
              receipt['repository'] == 'aloerch/ambisgis-geotools' and receipt['task'] == 'FND-07' and
              receipt['accepted_candidate'] == {'path': 'plan/candidates/fnd-02-candidate.json', 'sha256': CANDIDATE, 'unchanged': True} and
              receipt['proposal'] == publication_proposal() and receipt['recovery'] == recovery_result(), 'Receipt scope changed')
    C.require(receipt['implementation_sha256'] == C.sha(Path(__file__)), 'Recipe changed since preparation')
    C.require(receipt['base_tree'] == BASE_TREE and receipt['original_source_preserved'] is True and
              receipt['proposal']['review_ref'] == REF and receipt['proposal']['canonical_ref'] == 'refs/heads/ambisgis/main' and
              receipt['proposal']['creation_only'] is True and receipt['proposal']['preserve_default'] == 'main' and
              receipt['proposal']['preserve_actions_enabled'] is False, 'Receipt proposal changed')
    C.require(receipt['source'] == str(output/'source') and receipt['recovered'] == str(output/'recovered') and
              receipt['bundle_chain'][0] == {'path': str(workspace/PREDECESSOR), 'sha256': PREDECESSOR_SHA, 'prerequisites': []} and
              receipt['bundle_chain'][1]['path'] == str(output/'geotools-notices.bundle') and
              receipt['bundle_chain'][1]['prerequisites'] == [BASE] and
              receipt['bundle_chain'][1]['ref'] == REF, 'Receipt paths or predecessor changed')
    C.require((output/'maven-models/PomModel.java').read_text() == MODEL_JAVA, 'Maven parser probe changed')
    models = receipt['maven_configuration']['models']
    C.require(len(models) == 2 and receipt['maven_configuration']['command_count'] == 5, 'Maven model receipt incomplete')
    for index, name in enumerate(ROWS):
        hashes = [C.sha(output/'maven-models'/(str(index)+'-'+kind+'-model.xml')) for kind in ('before','after')]
        C.require(hashes[0] == hashes[1] and models[index] == {'path': name, 'before_model_sha256': hashes[0],
                  'after_model_sha256': hashes[1], 'equal': True}, 'Maven model output or receipt changed')
        for kind, data in [('before', before[name]), ('after', repair_pom(name, before[name], receipt['notice_added_utc_date'])[0])]:
            C.require((output/'maven-models'/(str(index)+'-'+kind+'.xml')).read_bytes() == data, 'Maven input changed')
    for index in range(1,6):
        C.require(json.loads((output/'maven-models'/('command-'+str(index)+'.json')).read_text())['exit_code'] == 0,
                  'Maven model command failed')
    expected_patch = notice_patch(before, receipt['notice_added_utc_date'])
    C.require((output/'geotools-notices.patch').read_bytes() == expected_patch and
              receipt['patch'] == {'path': str(output/'geotools-notices.patch'), 'sha256': digest(expected_patch)},
              'Patch differs from exact two-file notice insertion')
    delta = output/'geotools-notices.bundle'
    C.require(C.sha(delta) == receipt['bundle_chain'][1]['sha256'] and
              C.bundle_header(delta) == {'refs': {REF: receipt['commit']}, 'prerequisites': [BASE]}, 'Bundle changed')
    old_entries = C.tree_entries(old_repo, OLD)
    for folder in ('source', 'recovered'):
        repo = output/folder
        C.independent(repo)
        C.require(C.git(repo, 'status', '--porcelain') == b'', 'Working source changed')
        C.require(C.git(repo, 'rev-parse', REF).decode().strip() == receipt['commit'] and
                  C.git(repo, 'rev-parse', 'HEAD').decode().strip() == receipt['commit'], 'Local source ref changed')
        result = complete_comparison(repo, old_entries, receipt['commit'], before, receipt['notice_added_utc_date'])
        C.require(result == receipt['comparison'] and result['tree'] == receipt['tree'], 'Receipt source comparison changed')
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace-root', required=True, type=Path)
    p.add_argument('--authorization', required=True, type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--receipt-sha256', help='Trusted frozen receipt digest; required with --verify')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--verify', action='store_true')
    a = p.parse_args()
    if a.prepare or a.verify:
        if a.output is None:
            p.error('--output is required')
        if a.verify and a.receipt_sha256 is None:
            p.error('--receipt-sha256 is required with --verify')
        result = prepare(a.workspace_root.resolve(), a.authorization, a.output.absolute()) if a.prepare else verify(a.workspace_root.resolve(), a.authorization, a.output.absolute(), a.receipt_sha256)
    else:
        _, before, bundle, authority = inputs(a.workspace_root.resolve(), a.authorization)
        result = {'read_only': True, 'authority': authority, 'base': BASE, 'old_product': OLD,
                  'paths': list(before), 'predecessor': str(bundle)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
