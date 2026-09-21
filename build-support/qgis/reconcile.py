#!/usr/bin/env python3
"""Audit a completed build whose only failure was the inherited metadata addition.

This never reruns compilation/installation or edits the failed attempt. It binds
its seven completed phases and publishes a separate reconciliation receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

import build as qgis_build
from common import COMMIT, HERE, PLATFORM, environment, inventory, require, save, sha, verify_inventory, verify_selected, verify_xml

PHASES = ('configure', 'compile', 'stage', 'staged-crs-sync',
          'native-test-compile', 'desktop-linkage', 'server-linkage')
# Exact reviewed snapshots from build-06, before the generated-source guard fix.
EXECUTED_RECIPE_HASHES = {
    'acquisition.py': 'c7001c5e466c631fd28bee93ba995e64dd54d4a368bea8b709f17f97bcf417c1',
    'build.py': '53f91bdc558f13140c02fc996d06437317df204186fabaef58f22b71a81f4d93',
    'common.py': '2ee5eb4ebdd71b1730769047bb9a89a7842bcd0790a586d1d0509438f0a34fce',
    'offline_exec.py': 'ed658e05bc1cde8b008835b146bf2be73487313f581ce66da31d5644b3766ace',
    'profile-inputs.json': '91bfcfca3a7d8f8639713c2b14c47ca7dd9948f706cb45582e3105b66970e25c',
    'source-inputs.json': 'c36214078c03ec7f6a6055fe1aa112b17e6696853e2687578daa8b253239188c',
    'support-inputs.json': '7636a34b1823e071dc9662522d8f79be3085953eaed2d64ad6fcd34d1cb37d47',
}


def artifact(path):
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def verify_phase(attempt, name, expected_command):
    command_path = attempt / (name + '-command.json')
    network_path = attempt / (name + '-network.json')
    log = attempt / (name + '.log')
    command = json.loads(command_path.read_text())
    proof = json.loads(network_path.read_text())
    argv = command.get('argv', [])
    require(command.get('exit_code') == 0 and command.get('log_sha256') == sha(log),
            'Failed phase or changed phase log: ' + name)
    require(len(argv) >= 6 and argv[2:5] == ['--evidence', str(network_path), '--']
            and argv[5:] == expected_command and command.get('cwd') == str(attempt),
            'Unexpected phase command: ' + name)
    require(Path(argv[1]).name == 'offline_exec.py'
            and sha(Path(argv[1])) == EXECUTED_RECIPE_HASHES['offline_exec.py'],
            'Unreviewed phase offline runner: ' + name)
    probes = proof.get('probes', [])
    require(proof.get('status') == 'completed' and proof.get('command_exit_code') == 0
            and proof.get('command') == expected_command
            and proof.get('kernel_state', {}).get('no_new_privs') == 1
            and proof.get('kernel_state', {}).get('seccomp_mode') == 2
            and len(probes) == 4
            and [p.get('family') for p in probes] == ['AF_INET', 'AF_INET6', 'AF_UNIX', 'AF_UNIX']
            and all(p.get('passed') is True for p in probes),
            'Phase network enforcement failed: ' + name)
    return {'command': artifact(command_path), 'network': artifact(network_path),
            'log': artifact(log), 'environment': command['environment']}


def archive_inventory(archive, specification):
    require(archive.is_file() and not archive.is_symlink()
            and archive.stat().st_size == specification['bytes']
            and sha(archive) == specification['sha256'], 'Owned archive changed')
    rows = []
    with tarfile.open(archive) as stream:
        for member in stream:
            path = Path(member.name)
            require(not path.is_absolute() and path.parts[0] == specification['root']
                    and '..' not in path.parts, 'Invalid owned archive member')
            relative = str(Path(*path.parts[1:]))
            if member.issym():
                rows.append({'path': relative, 'link': member.linkname})
            elif member.isfile():
                with stream.extractfile(member) as content:
                    digest = hashlib.file_digest(content, 'sha256').hexdigest()
                rows.append({'path': relative, 'bytes': member.size, 'sha256': digest})
            else:
                require(member.isdir(), 'Unexpected owned archive entry type')
    return sorted(rows, key=lambda row: row['path'])


def reconcile(attempt, output):
    require(attempt.is_dir() and not attempt.is_symlink(), 'Expected retained build attempt')
    require(not output.exists() and not output.is_symlink()
            and not output.is_relative_to(attempt), 'Fresh separate audit output required')
    output.mkdir(parents=True)
    try:
        recipe_dir = output / 'recipe'
        recipe_dir.mkdir()
        for path in (Path(__file__), HERE / 'build.py', HERE / 'common.py',
                     PLATFORM / 'build-support/postgis/offline_exec.py'):
            shutil.copyfile(path, recipe_dir / path.name)
        original = json.loads((attempt / 'receipt.json').read_text())
        require(original['commit'] == COMMIT, 'Wrong attempt source commit')
        verify_inventory(attempt / 'recipe', original['recipe'])
        require(set(EXECUTED_RECIPE_HASHES) == {p.name for p in (attempt / 'recipe').iterdir()},
                'Unexpected executed recipe contents')
        for name, digest in EXECUTED_RECIPE_HASHES.items():
            require(sha(attempt / 'recipe' / name) == digest, 'Unreviewed executed recipe: ' + name)
        for name in ('source-inputs.json', 'profile-inputs.json', 'support-inputs.json'):
            require(sha(HERE / name) == EXECUTED_RECIPE_HASHES[name], 'Current input authority differs')
        spec = json.loads((attempt / 'recipe/source-inputs.json').read_text())
        require(spec['commit'] == COMMIT and spec['repository'] == 'aloerch/ambisgis-qgis'
                and spec['repository_id'] == 1376927721, 'Wrong owned source authority')
        source = attempt / 'sources' / spec['archive']['root']
        failure = json.loads((attempt / 'failure.json').read_text())
        require(failure == {'type': 'ValueError', 'message': 'Retained prefix changed: ' + str(source)}
                and not (attempt / 'success.json').exists(), 'Attempt failure is not the reviewed source guard')
        originals = [artifact(attempt / name) for name in
                     ('failure.json', 'receipt.json', 'source-manifest.json', 'configuration.json')]
        native = Path(original['native_prefix'])
        spatial = Path(original['spatial_prefix'])
        support = Path(original['support_prefix'])
        xml = Path(original['xml_profile']['prefix'])
        selected = verify_selected(native, spatial, support)
        xml_authority = verify_xml(xml)
        require(original['selected_profile'] == selected and original['xml_profile'] == xml_authority,
                'Attempt inputs differ from selected authorities')
        verify_inventory(native, original['base_inventory'])
        before = json.loads((attempt / 'source-manifest.json').read_text())
        require(sorted(before, key=lambda row: row['path']) == archive_inventory(Path(spec['archive']['path']), spec['archive']),
                'Original source inventory differs from the retained owned archive')
        qgis_build.verify_source_delta(source, before)
        configuration = json.loads((attempt / 'configuration.json').read_text())
        builddir, prefix = attempt / 'build', attempt / 'prefix'
        require(configuration['source'] == str(source) and configuration['build'] == str(builddir)
                and configuration['prefix'] == str(prefix), 'Unexpected configured paths')
        cache = qgis_build.cache_entries(builddir / 'CMakeCache.txt')
        require(configuration['cache'] == {k: list(v) for k, v in cache.items()}, 'Effective cache changed')
        qgis_build.check_config(cache, native, spatial, support, xml)
        jobs = str(original['jobs'])
        crs = 'from qgis.core import QgsApplication,QgsCoordinateReferenceSystem; a=QgsApplication([],False); QgsApplication.setPrefixPath('+repr(str(prefix))+',True); a.initQgis(); result=QgsCoordinateReferenceSystem.syncDatabase(); print("staged_crs_sync",result,QgsApplication.srsDatabaseFilePath()); assert result>=0; a.exitQgis()'
        expected = {
            'configure': ['cmake', '-S', str(source), '-B', str(builddir), '-G', 'Ninja', *configuration['flags']],
            'compile': ['cmake', '--build', str(builddir), '--parallel', jobs, '--target', *qgis_build.TARGETS],
            'stage': ['cmake', '--install', str(builddir)],
            'staged-crs-sync': ['/usr/bin/python3.13', '-c', crs],
            'native-test-compile': ['cmake', '--build', str(builddir), '--parallel', jobs, '--target', *qgis_build.TEST_TARGETS],
            'desktop-linkage': ['ldd', str(prefix / 'bin/qgis')],
            'server-linkage': ['ldd', str(prefix / 'bin/qgis_mapserver')],
        }
        phases = {name: verify_phase(attempt, name, expected[name]) for name in PHASES}
        base_env = phases['configure']['environment']
        require(base_env['PYTHONDONTWRITEBYTECODE'] == '1'
                and base_env['PYTHONNOUSERSITE'] == '1' and base_env['PROJ_NETWORK'] == 'OFF',
                'Unexpected execution environment')
        for name, phase in phases.items():
            env = base_env.copy()
            if name == 'staged-crs-sync':
                env['QGIS_PREFIX_PATH'] = str(prefix)
                env['PYTHONPATH'] = str(prefix / 'share/qgis/python') + ':' + base_env['PYTHONPATH']
                env['LD_LIBRARY_PATH'] = str(prefix / 'lib') + ':' + base_env['LD_LIBRARY_PATH']
            require(phase['environment'] == env, 'Phase environment changed: ' + name)
        require(not any(marker in (attempt / 'stage.log').read_text() for marker in
                        ('CRSs synchronization not possible', 'CRSs could not be updated')), 'Stage reported CRS failure')
        crs_line = (attempt / 'staged-crs-sync.log').read_text().strip().split()
        require(len(crs_line) == 3 and crs_line[0] == 'staged_crs_sync' and int(crs_line[1]) >= 0
                and Path(crs_line[2]) == prefix / 'share/qgis/resources/srs.db', 'Staged CRS proof mismatch')
        for name in ('desktop-linkage', 'server-linkage'):
            require('not found' not in (attempt / (name + '.log')).read_text(), 'Unresolved staged library')
        artifacts = []
        for name in ('bin/qgis', 'bin/qgis_mapserv.fcgi', 'bin/qgis_mapserver',
                     'lib/libqgis_core.so', 'lib/libqgis_gui.so', 'lib/libqgis_server.so',
                     'share/qgis/python/qgis/_core.so', 'share/qgis/python/qgis/_gui.so',
                     'share/qgis/python/qgis/_server.so'):
            path = prefix / name
            require(path.is_file() and path.resolve().is_relative_to(prefix), 'Missing or external staged artifact: ' + name)
            artifacts.append(artifact(path))
        binaries = []
        for name in qgis_build.TEST_TARGETS:
            path = builddir / 'output/bin' / name
            require(path.is_file() and not path.is_symlink(), 'Missing native target: ' + name)
            with path.open('rb') as stream:
                require(stream.read(4) == b'\x7fELF', 'Missing native ELF target: ' + name)
            binaries.append(artifact(path))
        env = environment(output, native, support, spatial, xml)
        generated = qgis_build.reproduce_generated_source(source, before, prefix, env, output)
        for row in originals:
            require(sha(Path(row['path'])) == row['sha256'], 'Original attempt evidence changed')
        verify_selected(native, spatial, support)
        verify_xml(xml)
        save(output / 'receipt.json', {'kind': 'post-build-reconciliation', 'build_attempt': str(attempt),
             'original_failure_preserved': artifact(attempt / 'failure.json'), 'original_evidence': originals,
             'executed_recipe_hashes': EXECUTED_RECIPE_HASHES, 'audit_recipe': inventory(recipe_dir),
             'phases': phases, 'generated_source': generated, 'staged_artifacts': artifacts,
             'native_test_binaries': binaries, 'selected_profile': selected, 'xml_profile': xml_authority,
             'compile_repeated': False, 'install_repeated': False, 'native_tests_executed': False})
        save(output / 'output-manifest.json', {'prefix': str(prefix), 'files': inventory(prefix),
             'source_commit': COMMIT, 'build_attempt': str(attempt),
             'generated_version_sha256': sha(builddir / 'qgsversion.h'),
             'configuration_sha256': sha(attempt / 'configuration.json')})
        save(output / 'success.json', {'state': 'compiled-staged', 'verification_kind': 'post-build-reconciliation',
             'manifest_sha256': sha(output / 'output-manifest.json'), 'receipt_sha256': sha(output / 'receipt.json'),
             'original_attempt_failed_guard_preserved': True, 'compile_repeated': False,
             'acceptance': 'Runtime and native assertions remain separate gates; this audit is not a rebuild.'})
    except Exception as exc:
        save(output / 'failure.json', {'type': type(exc).__name__, 'message': str(exc)})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reconcile(args.attempt.resolve(), args.output.resolve())
