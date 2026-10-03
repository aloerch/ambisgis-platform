"""Retain one exact candidate; no npm resolution, lifecycle, or package imports."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

from custody import (COMMIT, TREE, REPOSITORY_ID, NODE_SHA256, archive_files,
                     production_lock, require, save, sha, source_manifest, verify_inventory, verify_sri)


def download(url, path):
    require(urlsplit(url).scheme == 'https' and urlsplit(url).hostname in
            ('registry.npmjs.org', 'codeload.github.com'), 'unapproved acquisition origin')
    with urlopen(url, timeout=90) as response:
        require(urlsplit(response.url).hostname == urlsplit(url).hostname, 'cross-origin redirect')
        with path.open('xb') as stream:
            shutil.copyfileobj(response, stream)


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', 'repos/koopjs/koop/' + path], text=True))


def retain(output, previous):
    require(not output.exists(), 'fresh custody output required')
    output.mkdir(parents=True)
    (output / 'registry').mkdir()
    (output / 'metadata').mkdir()
    identity = json.loads(subprocess.check_output(['gh', 'api', 'repos/koopjs/koop'], text=True))
    require(identity['id'] == REPOSITORY_ID and identity['full_name'] == 'koopjs/koop', 'source repository identity differs')
    commit = api('commits/' + COMMIT)
    require(commit['sha'] == COMMIT and commit['commit']['tree']['sha'] == TREE, 'source commit/tree differs')
    tree = api('git/trees/' + TREE + '?recursive=1')
    save(output / 'source-repository.json', identity)
    save(output / 'source-commit.json', commit)
    save(output / 'source-tree.json', tree)
    source_url = 'https://codeload.github.com/koopjs/koop/tar.gz/' + COMMIT
    download(source_url, output / 'source.tar.gz')
    files, source_rows = source_manifest(output / 'source.tar.gz', tree)
    save(output / 'source-files.json', source_rows)
    (output / 'original-package-lock.json').write_bytes(files['package-lock.json'])
    root, unresolved_lock, unused = production_lock(files, allow_unresolved_for_acquisition=True)
    missing = {}
    for path, row in unresolved_lock['packages'].items():
        if path.startswith('node_modules/') and not row.get('link') and (not row.get('resolved') or not row.get('integrity')):
            name = path.rsplit('node_modules/', 1)[1]
            missing[name + '@' + row['version']] = (name, row['version'])

    def supplement(item):
        identity, (name, version) = item
        metadata_url = 'https://registry.npmjs.org/' + quote(name, safe='@') + '/' + quote(version, safe='')
        metadata_path = output / 'metadata' / ('supplement-' + hashlib.sha256(identity.encode()).hexdigest() + '.json')
        download(metadata_url, metadata_path)
        metadata = json.loads(metadata_path.read_text())
        require(metadata['name'] == name and metadata['version'] == version, 'supplement metadata identity differs')
        require(metadata['dist']['tarball'].startswith('https://registry.npmjs.org/'), 'supplement origin differs')
        require(metadata['dist'].get('integrity'), 'supplement lacks integrity')
        return identity, {'name': name, 'version': version, 'resolved': metadata['dist']['tarball'],
                          'integrity': metadata['dist']['integrity'], 'metadata_url': metadata_url,
                          'metadata': str(metadata_path.relative_to(output)), 'metadata_sha256': sha(metadata_path),
                          'identity_provenance': 'New explicit exact-version registry metadata; identity absent from original lock.'}

    with ThreadPoolExecutor(max_workers=4) as pool:
        supplements = dict(pool.map(supplement, missing.items()))
    save(output / 'resolution-supplements.json', supplements)
    root, lock, reconciliation = production_lock(files, supplements)
    save(output / 'package.json', root)
    save(output / 'reconciliation.json', reconciliation)
    source_notices = {path: {'sha256': hashlib.sha256(data).hexdigest(), 'text': data.decode()}
                      for path, data in files.items()
                      if Path(path).name.lower() in ('license', 'notice', 'copying')}
    save(output / 'source-notices.json', source_notices)
    prior = json.loads((previous / 'registry-inventory.json').read_text())
    by_integrity = {row['integrity']: row for row in prior}
    jobs = {}
    for path, row in lock['packages'].items():
        if not path.startswith('node_modules/') or row.get('link'):
            continue
        require(row.get('resolved') and row.get('integrity'), 'registry closure has missing archive identity')
        url = row['resolved']
        require(url.startswith('https://registry.npmjs.org/'), 'nonregistry production resolution')
        key = hashlib.sha256(row['integrity'].encode()).hexdigest()
        name = path.rsplit('node_modules/', 1)[1]
        jobs[key] = {'name': name, 'version': row['version'], 'url': url, 'integrity': row['integrity']}
        row['resolved'] = 'file:registry/' + key + '.tgz'

    def acquire(item):
        key, job = item
        archive = output / 'registry' / (key + '.tgz')
        prior_row = by_integrity.get(job['integrity'])
        if prior_row:
            source = previous / prior_row['archive']
            require(sha(source) == prior_row['sha256'], 'previous retained archive changed')
            shutil.copyfile(source, archive)
            reuse = str(source)
        else:
            download(job['url'], archive)
            reuse = None
        verify_sri(archive, job['integrity'])
        metadata_url = 'https://registry.npmjs.org/' + quote(job['name'], safe='@') + '/' + quote(job['version'], safe='')
        metadata_path = output / 'metadata' / (key + '.json')
        supplemented = supplements.get(job['name'] + '@' + job['version'])
        if supplemented:
            shutil.copyfile(output / supplemented['metadata'], metadata_path)
        else:
            download(metadata_url, metadata_path)
        metadata = json.loads(metadata_path.read_text())
        require(metadata['name'] == job['name'] and metadata['version'] == job['version'], 'registry metadata identity differs')
        require(metadata['dist']['tarball'] == job['url'], 'registry archive origin differs')
        if metadata['dist'].get('integrity'):
            verify_sri(archive, metadata['dist']['integrity'])
        require(hashlib.sha1(archive.read_bytes()).hexdigest() == metadata['dist']['shasum'], 'registry metadata tar digest differs')
        members = archive_files(archive)
        manifests = [name for name in members if len(Path(name).parts) == 2 and name.endswith('/package.json')]
        require(len(manifests) == 1, 'ambiguous package manifest')
        package = json.loads(members[manifests[0]])
        require(package['name'] == job['name'] and package['version'] == job['version'], 'archive package identity differs')
        notices = [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
                   for name, data in members.items() if any(word in Path(name).name.lower() for word in ('license', 'licence', 'notice', 'copying'))]
        binary = [name for name in members if name.endswith(('.node', '.wasm', '.so', '.dll', '.exe'))]
        return {**job, 'archive': str(archive.relative_to(output)), 'sha256': sha(archive),
                'bytes': archive.stat().st_size, 'metadata': str(metadata_path.relative_to(output)),
                'metadata_sha256': sha(metadata_path), 'reused_retained_archive': reuse,
                'package_manifest': package, 'notices': notices, 'binary_members': binary,
                'source_members': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
                                   for name, data in members.items()
                                   if name.endswith(('.js', '.cjs', '.mjs', '.ts', '.cc', '.cpp', '.c', '.h', '.map'))],
                'lifecycle': {k: v for k, v in package.get('scripts', {}).items()
                              if k in ('preinstall', 'install', 'postinstall', 'prepare')},
                'source_scope': 'Actual npm source/generated files inventoried; standalone source rebuild qualification is separate.'}

    with ThreadPoolExecutor(max_workers=4) as pool:
        inventory = sorted(pool.map(acquire, jobs.items()), key=lambda row: (row['name'], row['version']))
    save(output / 'registry-inventory.json', inventory)
    save(output / 'package-lock.json', lock)
    require(sha(previous / 'node.tar.xz') == NODE_SHA256, 'retained Node archive differs')
    shutil.copyfile(previous / 'node.tar.xz', output / 'node.tar.xz')
    manifest = {'source_repository': 'https://github.com/koopjs/koop', 'source_repository_id': REPOSITORY_ID,
                'source_commit': COMMIT, 'source_tree': TREE, 'source_archive_url': source_url,
                'registry_archives': len(inventory), 'source_files': len(source_rows),
                'package_execution': False, 'lifecycle_policy': 'All dependency lifecycle scripts remain disabled.',
                'files': [{'path': str(path.relative_to(output)), 'sha256': sha(path), 'bytes': path.stat().st_size}
                          for path in sorted(output.rglob('*')) if path.is_file()]}
    save(output / 'manifest.json', manifest)
    verify_inventory(output)
    print(json.dumps({'output': str(output), 'manifest_sha256': sha(output / 'manifest.json'),
                      'registry_archives': len(inventory), 'source_files': len(source_rows)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    args = parser.parse_args()
    retain(args.output.resolve(), args.previous.resolve())
