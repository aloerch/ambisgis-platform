#!/usr/bin/env python3
"""Verify retained audit inputs; optionally restore exact owned Git archives.

This verifies custody of audit evidence, not Maven dependency closure or readiness
for a build. External research inputs must be restored from retained backup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def entries(custody, manifest):
    if custody.is_symlink():
        raise ValueError('custody must not be a symlink')
    root = custody.resolve()
    if manifest.get('schema_version') != 1 or not manifest.get('files'):
        raise ValueError('expected a nonempty version 1 audit manifest')
    seen = set()
    result = []
    for item in manifest['files']:
        relative = PurePosixPath(item['path'])
        if (not relative.parts or relative.is_absolute() or '..' in relative.parts
                or str(relative) != item['path'] or '\\' in item['path']):
            raise ValueError('unsafe or noncanonical custody path')
        if str(relative) in seen:
            raise ValueError('duplicate custody path')
        seen.add(str(relative))
        if not re.fullmatch(r'[0-9a-f]{64}', item['sha256']):
            raise ValueError('invalid SHA256')
        if type(item['size']) is not int or item['size'] < 0:
            raise ValueError('invalid size')
        path = root / relative
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)):
            raise ValueError('symlink in custody path')
        if not path.resolve().is_relative_to(root):
            raise ValueError('custody path escapes root')
        result.append((path, item))
    return result


def verify(custody, manifest):
    records = entries(custody, manifest)
    for path, item in records:
        if not path.is_file() or path.stat().st_size != item['size'] or digest(path) != item['sha256']:
            raise ValueError('missing or changed retained input: ' + item['path'])
    return {'status': 'audit-inputs-verified', 'build_ready': False,
            'files': len(records), 'bytes': sum(item['size'] for _, item in records)}


def local_git(repo, *args, stdout=subprocess.PIPE):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1',
               GIT_TERMINAL_PROMPT='0', GIT_ALLOW_PROTOCOL='')
    command = ['git', '--no-optional-locks', '-c', 'protocol.allow=never',
               '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
               '-C', str(repo), *args]
    return subprocess.run(command, env=env, stdout=stdout,
                          stderr=subprocess.PIPE, check=True).stdout


def restore_owned(custody, manifest, owned_root):
    # Preflight every path before any filesystem mutation.
    records = entries(custody, manifest)
    restored = []
    for path, item in records:
        if path.exists():
            if not path.is_file() or path.stat().st_size != item['size'] or digest(path) != item['sha256']:
                raise ValueError('will not overwrite changed input: ' + item['path'])
            continue
        origin = item.get('origin', {})
        if origin.get('kind') != 'owned-git-archive':
            continue
        url = origin['repository']
        match = re.fullmatch(r'https://github.com/aloerch/ambisgis-(geotools|geowebcache|geoserver|geonode)\.git', url)
        if not match or not re.fullmatch('[0-9a-f]{40}', origin['commit']):
            raise ValueError('unexpected owned source identity')
        name = match[1]
        if origin['prefix'] != name + '/':
            raise ValueError('unexpected archive prefix')
        repo = owned_root / ('ambisgis-' + name)
        config = local_git(repo, 'config', '--local', '--list').decode().splitlines()
        if any(line.lower().startswith('extensions.partialclone=') or
               ('.promisor=' in line.lower() and line.rsplit('=', 1)[-1].lower() not in ('false', 'no', '0'))
               for line in config):
            raise ValueError('partial/promisor source clone is not retained custody')
        actual = local_git(repo, 'remote', 'get-url', 'origin').decode().strip()
        if actual != url:
            raise ValueError('owned source remote mismatch')
        commit = local_git(repo, 'rev-parse', origin['commit'] + '^{commit}').decode().strip()
        if commit != origin['commit']:
            raise ValueError('owned source commit mismatch')
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.restore-', delete=False) as stream:
            temporary = Path(stream.name)
            try:
                local_git(repo, 'archive', '--format=tar', '--prefix=' + origin['prefix'], commit, stdout=stream)
                stream.flush()
                if temporary.stat().st_size != item['size'] or digest(temporary) != item['sha256']:
                    raise ValueError('regenerated source archive does not match retained hash')
                # Exclusive publication: never replace a file created concurrently.
                os.link(temporary, path)
                restored.append(item['path'])
            finally:
                temporary.unlink(missing_ok=True)
    return restored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--custody', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('inputs.json'))
    parser.add_argument('--restore-owned', action='store_true')
    parser.add_argument('--owned-root', type=Path)
    args = parser.parse_args()
    if args.restore_owned and args.owned_root is None:
        parser.error('--restore-owned requires --owned-root')
    manifest = json.loads(args.manifest.read_text())
    restored = restore_owned(args.custody, manifest, args.owned_root) if args.restore_owned else []
    report = verify(args.custody, manifest)
    report.update(manifest_sha256=digest(args.manifest), restored=restored)
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
