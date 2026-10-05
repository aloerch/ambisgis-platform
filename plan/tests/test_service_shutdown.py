"""Actual shared serve control flow with inert signal/server collaborators.

No real signal, worker, listener, application, database or network runs here.
Retained Waitress behavior and a separate real loopback fixture are reviewed
independently; these tests exercise first-party ownership and failure cleanup.
"""
from contextlib import nullcontext
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/development'))
from ambisgis_development import common


class ServeFixture:
    def __init__(self):
        self.calls = []
        self.old_handlers = {15: object(), 2: object()}
        self.handlers = self.old_handlers.copy()
        self.signal_number = 15
        self.signal_install_error = None
        self.start_error = self.create_error = self.listen_error = None
        self.loop_error = self.shutdown_error = self.close_error = None
        self.worker_stuck = False
        self.stop_during_create = False
        self.empty_map = False
        self.application = object()
        self.server = SimpleNamespace(adj=SimpleNamespace(asyncore_use_poll=True), print_listen=self.listen)
        self.signal = ModuleType('signal')
        self.signal.SIGTERM = 15; self.signal.SIGINT = 2
        self.signal.signal = self.set_signal
        self.dispatcher = SimpleNamespace(lock=nullcontext(), threads=set(),
                                         set_thread_count=self.start, shutdown=self.shutdown)
        self.waitress = ModuleType('waitress')
        self.waitress.create_server = self.create
        self.waitress.serve = self.legacy_serve
        self.waitress.wasyncore = SimpleNamespace(loop=self.loop, close_all=self.close)
        self.task = ModuleType('waitress.task')
        self.task.ThreadedTaskDispatcher = lambda: self.dispatcher

    def set_signal(self, number, handler):
        if number == self.signal_install_error and callable(handler):
            raise ValueError('synthetic signal installation failure')
        previous = self.handlers[number]
        self.handlers[number] = handler
        return previous

    def start(self, count):
        self.calls.append(('workers', count)); self.dispatcher.threads.update(range(count))
        if self.start_error: raise self.start_error

    def stop(self):
        handler = self.handlers[self.signal_number]
        if not callable(handler): raise RuntimeError('synthetic unhandled termination')
        before = self.calls.copy()
        handler(self.signal_number, None); handler(self.signal_number, None)
        # The handler only changes its private stop flag, even on repeats.
        if self.calls != before: raise AssertionError('signal handler performed cleanup')

    def create(self, app, *, map=None, _dispatcher=None, **options):
        self.calls.append(('create', app, options))
        self.map = {} if map is None else map
        self.supplied_dispatcher = _dispatcher
        self.map[1] = object(); self.map[2] = object()  # listener and active channel
        if self.stop_during_create: self.stop()
        if self.create_error: raise self.create_error
        if self.empty_map: self.map.clear()
        return self.server

    def listen(self, text):
        self.calls.append(('listen', text))
        if self.listen_error: raise self.listen_error

    def loop(self, **kw):
        self.calls.append(('loop', kw))
        if self.loop_error: raise self.loop_error
        self.stop()

    def shutdown(self, *, timeout=5):
        self.calls.append(('shutdown', timeout))
        if self.shutdown_error: raise self.shutdown_error
        if not self.worker_stuck: self.dispatcher.threads.clear()
        return True  # Retained Waitress can also return True with live workers.

    def close(self, channels):
        self.calls.append(('close', channels.copy()))
        if self.close_error: raise self.close_error
        channels.clear()

    def legacy_serve(self, app, **options):
        # Baseline collaborator: expose absence of first-party signal ownership;
        # this is not a simulated native PID1 or installed Waitress result.
        self.start(options['threads'])
        self.create(app, **options)
        self.loop(map=self.map, timeout=1, use_poll=True)

    def run(self, port=8000):
        with patch.dict(sys.modules, {'signal': self.signal, 'waitress': self.waitress, 'waitress.task': self.task}), \
                patch('logging.basicConfig'):
            return common.serve(self.application, port)


class ServiceShutdownTests(unittest.TestCase):
    def assert_released(self, f):
        self.assertEqual(f.handlers, f.old_handlers)
        self.assertIn(('shutdown', 5), f.calls)
        self.assertTrue(any(c[0] == 'close' for c in f.calls))

    def test_sigterm_stops_workers_channels_and_restores_handlers(self):
        f = ServeFixture(); self.assertIsNone(f.run())
        self.assert_released(f); self.assertEqual(f.dispatcher.threads, set()); self.assertEqual(f.map, {})
        self.assertIs(f.supplied_dispatcher, f.dispatcher)
        self.assertEqual([c[0] for c in f.calls], ['workers', 'create', 'listen', 'loop', 'shutdown', 'close'])

    def test_sigint_and_repeated_delivery_only_request_stop(self):
        f = ServeFixture(); f.signal_number = 2; f.run(); self.assert_released(f)
        self.assertEqual(sum(c[0] == 'shutdown' for c in f.calls), 1)

    def test_application_port_and_fixed_security_options_are_preserved(self):
        f = ServeFixture(); f.run(9123)
        create = next(c for c in f.calls if c[0] == 'create')
        self.assertIs(create[1], f.application)
        self.assertEqual(create[2], dict(host='0.0.0.0', port=9123, threads=4, connection_limit=64,
            backlog=64, channel_timeout=20, cleanup_interval=5, max_request_header_size=16384,
            max_request_body_size=65536, expose_tracebacks=False, ident='AmbisGIS',
            clear_untrusted_proxy_headers=True, trusted_proxy=None, channel_request_lookahead=0))

    def test_each_poll_uses_owned_map_and_finite_single_iteration(self):
        f = ServeFixture(); f.run()
        loop = next(c[1] for c in f.calls if c[0] == 'loop')
        self.assertIs(loop['map'], f.map)
        self.assertEqual({k: v for k, v in loop.items() if k != 'map'},
                         {'timeout': 0.25, 'count': 1, 'use_poll': True})

    def test_partial_create_failure_still_releases_owned_resources(self):
        f = ServeFixture(); error = f.create_error = OSError('synthetic bind failure')
        with self.assertRaises(OSError) as caught: f.run()
        self.assertIs(caught.exception, error); self.assert_released(f); self.assertEqual(f.map, {})

    def test_partial_worker_start_failure_still_shuts_down(self):
        f = ServeFixture(); f.start_error = RuntimeError('synthetic worker failure')
        with self.assertRaises(RuntimeError): f.run()
        self.assert_released(f); self.assertEqual(f.dispatcher.threads, set())

    def test_listen_reporting_failure_still_cleans_up(self):
        f = ServeFixture(); f.listen_error = OSError('synthetic logging failure')
        with self.assertRaises(OSError): f.run()
        self.assert_released(f)

    def test_loop_failure_propagates_after_cleanup(self):
        f = ServeFixture(); error = f.loop_error = ValueError('synthetic loop failure')
        with self.assertRaises(ValueError) as caught: f.run()
        self.assertIs(caught.exception, error); self.assert_released(f)

    def test_shutdown_true_with_live_worker_is_not_success(self):
        f = ServeFixture(); f.worker_stuck = True
        with self.assertRaisesRegex(RuntimeError, '^service worker shutdown incomplete$'): f.run()
        self.assert_released(f); self.assertEqual(f.map, {})
        self.assertTrue(f.dispatcher.threads)

    def test_dispatcher_exception_cannot_skip_map_or_handler_cleanup(self):
        f = ServeFixture(); f.shutdown_error = RuntimeError('synthetic shutdown failure')
        with self.assertRaises(RuntimeError): f.run()
        self.assert_released(f); self.assertEqual(f.map, {})

    def test_map_close_exception_cannot_skip_handler_restore(self):
        f = ServeFixture(); f.close_error = RuntimeError('synthetic close failure')
        with self.assertRaises(RuntimeError): f.run()
        self.assert_released(f)

    def test_second_handler_install_failure_restores_first(self):
        f = ServeFixture(); f.signal_install_error = 2
        with self.assertRaises(ValueError): f.run()
        self.assert_released(f); self.assertFalse(any(c[0] == 'workers' for c in f.calls))

    def test_stop_during_create_skips_loop_then_cleans_up(self):
        f = ServeFixture(); f.stop_during_create = True; f.run()
        self.assert_released(f); self.assertFalse(any(c[0] == 'loop' for c in f.calls))

    def test_empty_owned_map_returns_with_cleanup(self):
        f = ServeFixture(); f.empty_map = True; f.run()
        self.assert_released(f); self.assertFalse(any(c[0] == 'loop' for c in f.calls))


if __name__ == '__main__': unittest.main()
