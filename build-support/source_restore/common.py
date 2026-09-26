"""Confined, offline source-custody primitives. Never consult upstream remotes."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def confined(base, relative, *, exists=True):
    base = Path(base).absolute()
    require(base.resolve(strict=True) == base, 'Symlink in confinement root')
    require(isinstance(relative, str) and relative and '\\' not in relative and '\x00' not in relative,
            'Unsafe relative path')
    require(not PurePosixPath(relative).is_absolute() and
            all(x not in ('', '.', '..') for x in relative.split('/')), 'Unsafe relative path')
    path = base
    for part in relative.split('/'):
        path = path / part
        require(not path.is_symlink(), 'Symlink in confined path: ' + str(path))
    require(path.resolve(strict=exists).is_relative_to(base), 'Path escapes confinement')
    return path


def fresh(base, relative):
    path = confined(base, relative, exists=False)
    require(not path.exists(), 'Output already exists: ' + str(path))
    require(path.parent.is_dir(), 'Output parent must already exist')
    path.mkdir()
    return path


def verified_file(base, relative, digest, size=None):
    require(bool(re.fullmatch('[0-9a-f]{64}', digest)), 'Invalid SHA256')
    path = confined(base, relative)
    require(path.is_file(), 'Required input missing: ' + relative)
    require(size is None or path.stat().st_size == size, 'Changed input size: ' + relative)
    require(sha(path) == digest, 'Changed input bytes: ' + relative)
    return path


def git_environment():
    # No inherited config injection, alternates, custom object dirs or credential helpers.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1',
               GIT_ALLOW_PROTOCOL='file', GIT_LFS_SKIP_SMUDGE='1',
               GIT_OPTIONAL_LOCKS='0', LC_ALL='C')
    return env


def git(repo, *args, input=None):
    result = subprocess.run(['git', '--no-replace-objects', '-c', 'core.hooksPath=/dev/null',
                             '-c', 'core.autocrlf=false', '-c', 'core.fsmonitor=false',
                             '-c', 'maintenance.auto=false', '-c', 'gc.auto=0',
                             '-C', str(repo), *args], input=input, env=git_environment(),
                            capture_output=True)
    require(result.returncode == 0, 'Git failed: ' + ' '.join(args[:3]) + ': ' +
            result.stderr.decode(errors='replace')[-2000:])
    return result.stdout


def bundle_header(path):
    with Path(path).open('rb') as stream:
        require(stream.readline() in (b'# v2 git bundle\n', b'# v3 git bundle\n'), 'Not a Git bundle')
        refs, prerequisites = {}, []
        while True:
            line = stream.readline()
            require(line, 'Truncated bundle header')
            if line == b'\n':
                break
            if line.startswith(b'@'):
                require(line == b'@object-format=sha1\n', 'Unsupported bundle capability')
                continue
            if line.startswith(b'-'):
                prerequisites.append(line[1:41].decode())
                continue
            commit, ref = line.decode().rstrip('\n').split(' ', 1)
            require(bool(re.fullmatch('[0-9a-f]{40}', commit)), 'Invalid bundle object')
            require(ref not in refs, 'Duplicate bundle ref')
            refs[ref] = commit
        require(refs, 'Bundle contains no refs')
        return {'refs': refs, 'prerequisites': prerequisites}


def independent(repo):
    g = Path(repo) / '.git'
    require(Path(repo).resolve() == Path(repo).absolute(), 'Repository path symlink forbidden')
    require(g.is_dir() and not g.is_symlink(), 'Repository must have independent Git directory')
    require((g/'objects').is_dir() and not (g/'objects').is_symlink(), 'Object store root symlink forbidden')
    require(not (g/'objects/info/alternates').exists() and
            not (g/'objects/info/http-alternates').exists(), 'Git alternates forbidden')
    require(not (g/'shallow').exists(), 'Shallow history forbidden')
    require(not list((g/'objects').rglob('*.promisor')), 'Partial objects forbidden')
    for p in (g/'objects').rglob('*'):
        require(not p.is_symlink(), 'Object store symlink forbidden')
        if p.is_file():
            require(p.stat().st_nlink == 1, 'Shared/hardlinked Git objects forbidden')
    config = git(repo, 'config', '--local', '--list').decode().lower()
    require(not any(x in config for x in ('partialclone', 'promisor', 'filter.', 'include.', 'includeif.', 'remote.')),
            'Unexpected repository configuration')


def restore_bundle(bundle, repo, commit, expected_refs=None):
    require(bool(re.fullmatch('[0-9a-f]{40}', commit)), 'Invalid source revision')
    require(not Path(repo).exists(), 'Repository collision')
    require(all(not p.is_symlink() for p in (Path(repo), *Path(repo).parents)), 'Repository parent symlink forbidden')
    header = bundle_header(bundle)
    require(not header['prerequisites'], 'Bundle requires missing predecessor chain')
    if expected_refs is not None:
        require(header['refs'] == expected_refs, 'Bundle refs changed')
    Path(repo).mkdir()
    git(repo, 'init', '--template=', '--initial-branch=custody-empty')
    git(repo, 'bundle', 'verify', str(bundle))
    # Unbundle copies the archive objects into a wholly independent object store.
    git(repo, 'bundle', 'unbundle', str(bundle))
    for ref, oid in header['refs'].items():
        if ref != 'HEAD':
            require(ref.startswith('refs/') and not ref.startswith('refs/replace/'), 'Unsafe archived ref')
            target = 'refs/custody/' + ref.removeprefix('refs/')
            git(repo, 'update-ref', target, oid, '0'*40)
    require(git(repo, 'cat-file', '-t', commit).strip() == b'commit', 'Missing selected source commit')
    git(repo, 'checkout', '--detach', commit)
    independent(repo)
    git(repo, 'fsck', '--full', '--no-reflogs')
    return header


def tree_entries(repo, revision='HEAD'):
    out = []
    for item in git(repo, 'ls-tree', '-r', '-z', '-l', revision).split(b'\x00'):
        if not item:
            continue
        meta, name = item.split(b'\t', 1)
        mode, kind, oid, size = meta.decode().split()
        out.append({'path': name.decode(), 'mode': mode, 'type': kind, 'oid': oid,
                    'size': None if size == '-' else int(size)})
    return out


def audit_assets(repo, lfs_payloads=None):
    entries = tree_entries(repo)
    links = [x for x in entries if x['mode'] == '160000']
    pointers = []
    candidates = [x for x in entries if x['type'] == 'blob' and x['size'] <= 1024]
    # Bounded blob batch avoids thousands of processes and never invokes filters.
    if candidates:
        raw = git(repo, 'cat-file', '--batch', input=('\n'.join(x['oid'] for x in candidates)+'\n').encode())
        cursor = 0
        for entry in candidates:
            end = raw.index(b'\n', cursor)
            _, kind, size = raw[cursor:end].split()
            require(kind == b'blob', 'Invalid asset blob')
            size = int(size); data = raw[end+1:end+1+size];cursor = end+size+2
            if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
                match = re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n?', data)
                require(match is not None, 'Malformed/unsupported LFS pointer: ' + entry['path'])
                digest, count = match[1].decode(), int(match[2])
                payload = (lfs_payloads or {}).get(digest)
                require(payload is not None, 'Missing required LFS payload: ' + entry['path'])
                require(Path(payload).is_file() and not Path(payload).is_symlink() and
                        Path(payload).stat().st_size == count and sha(payload) == digest, 'Invalid LFS payload')
                pointers.append(dict(entry, sha256=digest, bytes=count))
    for entry in entries:
        if entry['mode'] == '120000':
            path = Path(repo) / entry['path']
            require(path.is_symlink() and path.resolve().is_relative_to(Path(repo).resolve()),
                    'Source symlink escape: '+entry['path'])
    notices = [x for x in entries if re.search(r'(^|/)(copying|copyright|licen[cs]e|notice|authors)([./_-]|$)', x['path'], re.I)]
    require(notices, 'Required copyright/license assets missing')
    return {'gitlinks': links, 'lfs_pointers': pointers,
            'lfs_scan': 'All tracked blobs up to 1024 bytes; unsupported pointer forms rejected',
            'tracked_entries': len(entries), 'notice_paths': notices}
