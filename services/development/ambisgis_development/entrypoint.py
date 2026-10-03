"""Fixed-role container entrypoint; no operator-supplied module or command."""
import json
import sys


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 1 or arguments[0] not in {'database', 'catalog-init', 'catalog', 'geoserver-init', 'geoserver', 'gateway'}:
        raise ValueError('one fixed service role is required')
    role = arguments[0]
    if role == 'database':
        from .database import main as run
    elif role == 'catalog-init':
        from .catalog import initialize as run
    elif role == 'catalog':
        from .catalog import main as run
    elif role == 'geoserver-init':
        from .geoserver import initialize as run
    elif role == 'geoserver':
        from .geoserver import main as run
    else:
        from .gateway import main as run
    run()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Never emit exception values/locals containing database URLs or secrets.
        print(json.dumps({'event': 'service_start_failed', 'detail': 'Inspect installation state and owned dependency readiness.'}), file=sys.stderr)
        raise SystemExit(1)
