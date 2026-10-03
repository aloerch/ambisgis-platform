#!/usr/bin/env python3
"""Serialize foreground delivery commands and retain a local recovery checkpoint.

This is a local action-boundary guard, not a supervisor, scheduler or merge gate.
It never resumes/replays a command automatically and never starts Codex. Use the
same private state directory for all integration commands. Run `status` and
reconcile live repository/Project state after interruption before explicit new
work. A crashed wrapper leaves a running checkpoint, never a fabricated success.
After an interrupted or unsuccessful command, run requires --reconciled-run-id
matching the previous UUID. Supply it only after actual live-state readback; it
records integrator acknowledgment, not proof of remote reconciliation.

`stop` creates a persistent STOP marker; current work finishes and subsequent
`run` calls fail closed. It does not terminate a migration or revoke credentials.
Only remove STOP after a verified owner instruction to resume; no CLI operation
clears it. Lock files must never be deleted while work might run. Commands must
stay in the foreground, preserve inherited file descriptors and not daemonize.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import uuid


class RuntimeGuardError(Exception):
    def __init__(self, message, exit_code=65):
        super().__init__(message)
        self.exit_code = exit_code


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def validate_state(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path:
        raise RuntimeGuardError('State directory must not use symlinks')
    if path.exists():
        info = path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise RuntimeGuardError('State directory must be owned and not group/world writable')
    return path


def prepare_state(path):
    path = validate_state(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return validate_state(path)


def checked_fd(path, flags, mode=0o600):
    fd = os.open(path, flags | os.O_NOFOLLOW, mode)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        os.close(fd)
        raise RuntimeGuardError('State entry must be an owned, unshared regular file')
    return fd


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path, value):
    """Publish either the entire new checkpoint or the unchanged previous one."""
    path = Path(path)
    if os.path.lexists(path):
        fd = checked_fd(path, os.O_RDONLY)
        os.close(fd)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_checkpoint(root):
    path = root / 'checkpoint.json'
    try:
        fd = checked_fd(path, os.O_RDONLY)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, encoding='utf-8') as stream:
        record = json.load(stream)
    if (not isinstance(record, dict) or record.get('schema_version') != 1
            or record.get('status') not in ('running', 'completed', 'failed')
            or not isinstance(record.get('run_id'), str)):
        raise RuntimeGuardError('Invalid checkpoint; preserve it and reconcile before running')
    try:
        if str(uuid.UUID(record['run_id'])) != record['run_id']:
            raise ValueError('Noncanonical UUID')
    except ValueError:
        raise RuntimeGuardError('Invalid checkpoint run identity') from None
    return record


def needs_reconciliation(record):
    return bool(record and record['status'] != 'completed' and 'launch_error' not in record)


def archive_checkpoint(root, record):
    # Exclusive creation preserves the previous receipt, including ambiguous outcomes.
    source = (root / 'checkpoint.json').read_bytes()
    path = root / ('history-' + record['run_id'] + '.json')
    try:
        fd = checked_fd(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        fd = checked_fd(path, os.O_RDONLY)
        with os.fdopen(fd, 'rb') as stream:
            if stream.read() != source:
                raise RuntimeGuardError('History collision; preserve and investigate')
        return
    with os.fdopen(fd, 'wb') as stream:
        stream.write(source)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(root)


def acquire_lock(root, create=True):
    fd = checked_fd(root / 'integration.lock', os.O_RDWR | (os.O_CREAT if create else 0))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeGuardError('Integration command already running', 75)
    return fd


def stop_requested(root):
    # Even an incomplete or dangling marker must prevent new work.
    return os.path.lexists(root / 'STOP')


def status(root):
    root = validate_state(root)
    checkpoint = read_checkpoint(root) if root.exists() else None
    held = False
    try:
        fd = acquire_lock(root, create=False)
    except FileNotFoundError:
        pass
    except RuntimeGuardError as error:
        if error.exit_code != 75:
            raise
        held = True
    else:
        os.close(fd)
    return {'schema_version': 1, 'stop_requested': stop_requested(root),
            'integration_lock_held': held, 'checkpoint': checkpoint,
            'reconciliation_required': bool(needs_reconciliation(checkpoint) and not held)}


def stop(root):
    root = prepare_state(root)
    try:
        fd = checked_fd(root / 'STOP', os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump({'schema_version': 1, 'requested_at': timestamp(),
                   'scope': 'next action boundary; owner-authorized removal only'}, stream)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(root)


def run_command(root, command, reconciled_run_id=None):
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise RuntimeGuardError('run requires a foreground command', 64)
    root = prepare_state(root)
    fd = acquire_lock(root)
    try:
        if stop_requested(root):
            raise RuntimeGuardError('STOP is present; a verified owner resume instruction is required', 77)
        previous = read_checkpoint(root)
        if needs_reconciliation(previous) and reconciled_run_id != previous['run_id']:
            raise RuntimeGuardError('Reconcile live effects first, then acknowledge the exact previous run ID', 78)
        if reconciled_run_id is not None and (not previous or reconciled_run_id != previous['run_id']):
            raise RuntimeGuardError('Reconciliation acknowledgment does not match the previous run', 78)
        if previous:
            archive_checkpoint(root, previous)
        record = {'schema_version': 1, 'run_id': str(uuid.uuid4()),
                  'previous_run_id': previous['run_id'] if previous else None,
                  'previous_status': previous['status'] if previous else None,
                  'reconciled_run_id': reconciled_run_id,
                  'wrapper_pid': os.getpid(), 'status': 'running', 'started_at': timestamp(),
                  'executable': Path(command[0]).name}
        # Arguments/environment may contain credentials; never persist them.
        atomic_json(root / 'checkpoint.json', record)
        # The inherited descriptor keeps the same flock after wrapper failure.
        # Explicit LOCK_UN here would release the child's lock too; only close it.
        try:
            child = subprocess.Popen(command, pass_fds=(fd,))
        except OSError as error:
            record.update(status='failed', exit_code=127, finished_at=timestamp(),
                          launch_error=type(error).__name__)
            atomic_json(root / 'checkpoint.json', record)
            return 127
        record['child_pid'] = child.pid
        atomic_json(root / 'checkpoint.json', record)
        result = child.wait()
        record.update(status='completed' if result == 0 else 'failed',
                      exit_code=result, finished_at=timestamp())
        atomic_json(root / 'checkpoint.json', record)
        return result if result >= 0 else 128 - result
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    actions = parser.add_subparsers(dest='action', required=True)
    run = actions.add_parser('run')
    run.add_argument('--reconciled-run-id')
    run.add_argument('command', nargs=argparse.REMAINDER)
    actions.add_parser('status')
    actions.add_parser('stop')
    args = parser.parse_args(argv)
    try:
        if args.action == 'run':
            return run_command(args.state_dir, args.command, args.reconciled_run_id)
        if args.action == 'stop':
            stop(args.state_dir)
        print(json.dumps(status(args.state_dir), sort_keys=True))
        return 0
    except RuntimeGuardError as error:
        print('Delivery runtime: ' + str(error), file=sys.stderr)
        return error.exit_code
    except (OSError, ValueError) as error:
        # Avoid leaking command arguments or malformed checkpoint content.
        print('Delivery runtime state error: ' + type(error).__name__, file=sys.stderr)
        return 65
    except KeyboardInterrupt:
        print('Interrupted; inspect status and reconcile before continuing', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
