#!/usr/bin/env python3
"""Stage reviewed palette packaging around freshly built successor binaries.

The source publication adapter supplies all palette/notice bytes. Every other
installed file must remain byte-identical to this attempt's new build manifest.
This neither imports an old binary stage nor mutates the compiler's output.
"""
import argparse
import json
from pathlib import Path
import shutil

from common import require, sha, save, inventory, verify_inventory
from successor_build import COMMIT, TREE, RECEIPT_SHA, publication
from publication_selection import publication_variant_stage
from resource_selection import RESOURCE, NOTICE_ROOT


def verify_build(attempt):
    report = json.loads((attempt/'result.json').read_text())
    require((report.get('commit'), report.get('tree'), report.get('state'), report.get('result_exit_code'))
            == (COMMIT, TREE, 'compiled-staged', 0), 'successful exact successor build required')
    compile_root = attempt/'compile'
    require(not (compile_root/'failure.json').exists(), 'failed producer cannot supply binaries')
    manifest_path = compile_root/'output-manifest.json'
    success_path = compile_root/'success.json'
    require(sha(manifest_path) == report['output_manifest_sha256'] and
            sha(success_path) == report['producer_success_sha256'], 'build evidence changed')
    manifest = json.loads(manifest_path.read_text())
    success = json.loads(success_path.read_text())
    require(manifest['source_commit'] == COMMIT and success['state'] == 'compiled-staged' and
            success['manifest_sha256'] == sha(manifest_path), 'producer identity mismatch')
    prefix = compile_root/'prefix'
    require(Path(manifest['prefix']).resolve() == prefix.resolve(), 'build prefix substitution')
    verify_inventory(prefix, manifest['files'])
    return prefix, manifest


def outside_resources(rows):
    return [row for row in rows if not row['path'].startswith((RESOURCE, NOTICE_ROOT))]


def verify_composition(baseline, staged, projection):
    require(outside_resources(baseline) == outside_resources(staged),
            'non-resource build output changed during packaging')
    selected = [row for row in staged if row['path'].startswith((RESOURCE, NOTICE_ROOT))]
    require(selected == projection, 'resource output differs from exact source projection')


def run(args):
    output = args.output.resolve()
    require(not output.exists() and not output.is_symlink(), 'fresh successor stage required')
    attempt = args.build_attempt.resolve()
    prefix, manifest = verify_build(attempt)
    trusted = publication.trusted_receipt(args.publication_receipt.resolve(), RECEIPT_SHA)
    expected = json.loads(Path(trusted['expected_tree']['path']).read_text())
    forbidden = json.loads(Path(trusted['forbidden_objects']['path']).read_text())
    provenance = json.loads(Path(trusted['provenance']['path']).read_text())
    repository = args.source_repository.resolve()
    publication.verify_repository(repository, COMMIT, TREE, expected, forbidden)
    output.mkdir(parents=True)
    report = {'result_exit_code':1, 'source_commit':COMMIT, 'source_tree':TREE,
              'build_result_sha256':sha(attempt/'result.json'),
              'build_manifest_sha256':sha(attempt/'compile/output-manifest.json'),
              'recipe_sha256':sha(Path(__file__)), 'scope':'private new-binary resource packaging; runtime separate'}
    try:
        projection = output/'resources'
        resources = publication_variant_stage(repository, COMMIT, TREE, expected, provenance,
            args.selection.resolve(), args.accepted_manifest.resolve(), projection, output/'resources-replay')
        save(output/'resource-projection.json', resources)
        staged = output/'prefix'
        shutil.copytree(prefix, staged, symlinks=True)
        for path in staged.rglob('*'):
            if path.is_symlink():
                require(path.resolve().is_relative_to(staged), 'staged symlink escapes new prefix')
        # Only this disposable new copy is changed. Metadata from omitted
        # collections moves to notices according to the pinned projection.
        for root in (RESOURCE, NOTICE_ROOT):
            target = staged/root
            if target.exists():
                require(target.is_dir() and not target.is_symlink(), 'unexpected resource directory')
                shutil.rmtree(target)
            shutil.copytree(projection/root, target)
        rows = inventory(staged)
        verify_composition(manifest['files'], rows, inventory(projection))
        verify_inventory(prefix, manifest['files'])
        save(output/'manifest.json', {'prefix':str(staged), 'files':rows,
             'source_commit':COMMIT, 'source_tree':TREE, 'build_manifest_sha256':report['build_manifest_sha256']})
        report.update(result_exit_code=0, unchanged_nonresource_entries=len(outside_resources(rows)),
                      resource_entries=len(inventory(projection)), manifest_sha256=sha(output/'manifest.json'))
    except Exception as error:
        report['error'] = {'type':type(error).__name__, 'message':str(error)}
        raise
    finally:
        save(output/'result.json', report)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('build-attempt','source-repository','publication-receipt','selection','accepted-manifest','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))
