"""Private persistent installation state (new first-party GPL-3.0-or-later code)."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


class InstallError(ValueError):
    """An actionable installation failure safe to show without exception locals."""


def checked_path(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise InstallError('Use an absolute path without parent traversal.')
    for item in (path, *path.parents):
        try:
            mode = item.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise InstallError('Installation and bundle paths cannot contain symlinks.')
    return path


def private_directory(value, *, create=False):
    path = checked_path(value)
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.stat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise InstallError('Installation directories must belong to you and have mode 0700.')
    return path


def digest(path):
    result = hashlib.sha256()
    with checked_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InstallError('Duplicate JSON keys are not supported.')
        result[key] = value
    return result


def read_json(path, *, private=False):
    path = checked_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise InstallError('Configuration must be a regular file.')
        if private and (metadata.st_uid != os.getuid() or metadata.st_mode & 0o077):
            raise InstallError('Private configuration must belong to you and have mode 0600.')
        if metadata.st_size > 8 * 1024 * 1024:
            raise InstallError('Configuration exceeds the supported size.')
        return json.load(stream, object_pairs_hook=no_duplicate_keys)


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def atomic_write(path, value, *, replace=False):
    path = checked_path(path)
    private_directory(path.parent)
    data = value if isinstance(value, bytes) else canonical(value)
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # A competing writer cannot replace state while initialization runs.
            os.link(temporary, path, follow_symlinks=False)
        parent = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        os.unlink(temporary) if Path(temporary).exists() else None


@contextmanager
def locked(directory, *, existing_only=False):
    directory = private_directory(directory)
    # A contender inspecting an unmarked root must never create its lock.
    flags = os.O_RDWR | os.O_NOFOLLOW | (0 if existing_only else os.O_CREAT)
    try:
        descriptor = os.open(directory / '.lock', flags, 0o600)
    except FileNotFoundError as error:
        if existing_only:
            raise InstallError('Installation lock is absent; unmarked state was preserved.') from error
        raise
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            raise InstallError('Installation lock has unsafe ownership or permissions.')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise InstallError('Another installation command is already running.') from error
        yield
    finally:
        os.close(descriptor)
