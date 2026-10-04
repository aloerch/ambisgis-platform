# Catalog and gateway shutdown

The shared first-party `common.serve` owns the retained Waitress 3.0.2
dispatcher and a private channel map. SIGTERM and SIGINT handlers only request
a stop. The main thread checks that request between single event-loop polls
configured with a 0.25-second wait timeout, then requests worker shutdown with
Waitress's five second timeout and closes the channel map. Previous signal handlers are
restored even if startup, the event loop or cleanup raises.

Waitress's shutdown return value does not prove its workers terminated. The
wrapper checks the protected worker set and fails with a fixed error if it is
still nonempty. It does not interrupt worker threads or claim that arbitrary
requests can always complete within five seconds. Queued requests may be
cancelled and buffered responses are not guaranteed to drain. Pending tasks
retain the dependency's normal cancellation behavior. Existing WSGI applications, service
ports, request limits and proxy settings are unchanged.

The retained dependency installs no SIGTERM handler in `serve` or `run`.
Lifecycle attempt 015's catalog stop required the native runtime's SIGKILL
fallback after 45 seconds and exited 137; the database exited zero. Those
observations do not identify an original Python signal-handler frame or explain
the earlier gateway startup failure.

Fourteen inert tests exercise the actual first-party control flow with synthetic
signal/server collaborators, including partial startup and cleanup failures.
They do not send signals, run Waitress workers or bind sockets. A separate
reviewed loopback-only fixture must verify real Waitress termination before
installed service shutdown is credited. Full installation acceptance remains
separate.
