"""Run with python3 -m installer; no package installation or network resolution."""
import argparse
import json
from pathlib import Path
import sys

from . import config, runtime
from .state import InstallError


def main(argv=None):
    parser = argparse.ArgumentParser(prog='ambisgis', description='Persistent loopback developer installation')
    commands = parser.add_subparsers(dest='command', required=True)
    initialize = commands.add_parser('init')
    initialize.add_argument('--directory', type=Path, required=True)
    initialize.add_argument('--bundle', type=Path, required=True)
    initialize.add_argument('--bundle-sha256', required=True)
    initialize.add_argument('--port', type=int)
    initialize.add_argument('--owner')
    initialize.add_argument('--viewer')
    for name in ('up', 'status', 'doctor'):
        command = commands.add_parser(name)
        command.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = config.initialize(args.directory, args.bundle, args.bundle_sha256,
                                       port=args.port, owner=args.owner, viewer=args.viewer)
        else:
            result = getattr(runtime, args.command)(args.directory)
        print(json.dumps(result, sort_keys=True))
        return 0 if args.command == 'init' or result.get('ready', result.get('readiness', {}).get('ready', False)) else 1
    except InstallError as error:
        print(json.dumps({'command': args.command, 'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        # JSON/parser/native errors can contain credentials, paths or response
        # bodies. Known diagnostics use InstallError; never reflect raw failures.
        print(json.dumps({'command': args.command, 'ok': False,
                          'error': 'Installation input or runtime operation failed; verify file permissions, bundle identity and prerequisites.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
