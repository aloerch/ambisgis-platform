"""Real process tests for delivery serialization and truthful crash recovery."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

TOOL = Path(__file__).parents[1] / 'tools/delivery_runtime.py'
spec = importlib.util.spec_from_file_location('delivery_runtime', TOOL)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class DeliveryRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.processes = []
        self.addCleanup(self.cleanup_processes)

    def cleanup_processes(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def command(self, *args):
        return [sys.executable, str(TOOL), '--state-dir', str(self.state), *args]

    def call(self, *args):
        return subprocess.run(self.command(*args), capture_output=True, text=True, timeout=5)

    def wait_for(self, predicate):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(0.01)
        self.fail('Fixture process did not reach expected state')

    def start_waiting_child(self):
        ready, release = self.root / 'ready', self.root / 'release'
        code = (
            "from pathlib import Path; import time; "
            f"Path({str(ready)!r}).write_text('ready'); "
            f"release = Path({str(release)!r}); "
            "exec('while not release.exists():\\n time.sleep(0.01)')"
        )
        process = subprocess.Popen(self.command('run', sys.executable, '-c', code),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.processes.append(process)
        self.addCleanup(lambda: release.touch())
        self.wait_for(ready.exists)
        self.wait_for(lambda: json.loads((self.state / 'checkpoint.json').read_text()).get('child_pid'))
        return process, release

    def test_missing_status_is_read_only(self):
        result = self.call('status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['checkpoint'], None)
        self.assertFalse(self.state.exists())

    def test_success_then_new_command_preserves_predecessor(self):
        first = self.call('run', sys.executable, '-c', 'pass', 'secret-fixture-not-for-checkpoint')
        self.assertEqual(first.returncode, 0, first.stderr)
        before = json.loads((self.state / 'checkpoint.json').read_text())
        self.assertEqual(before['status'], 'completed')
        self.assertNotIn('secret-fixture', (self.state / 'checkpoint.json').read_text())
        second = self.call('run', '--', sys.executable, '-c', 'raise SystemExit(7)')
        self.assertEqual(second.returncode, 7, second.stderr)
        after = json.loads((self.state / 'checkpoint.json').read_text())
        self.assertEqual(after['status'], 'failed')
        self.assertEqual(after['exit_code'], 7)
        self.assertEqual(after['previous_run_id'], before['run_id'])
        self.assertNotEqual(after['run_id'], before['run_id'])

    def test_duplicate_process_refused_without_checkpoint_change(self):
        process, release = self.start_waiting_child()
        before = (self.state / 'checkpoint.json').read_bytes()
        duplicate = self.call('run', sys.executable, '-c', 'raise SystemExit(99)')
        self.assertEqual(duplicate.returncode, 75, duplicate.stderr)
        self.assertEqual((self.state / 'checkpoint.json').read_bytes(), before)
        status = json.loads(self.call('status').stdout)
        self.assertTrue(status['integration_lock_held'])
        release.touch()
        self.assertEqual(process.communicate(timeout=5)[1], '')
        self.assertEqual(process.returncode, 0)

    def test_crashed_wrapper_keeps_child_lock_then_releases(self):
        process, release = self.start_waiting_child()
        process.kill()
        process.wait(timeout=5)
        checkpoint = json.loads((self.state / 'checkpoint.json').read_text())
        duplicate = self.call('run', sys.executable, '-c', 'pass')
        self.assertEqual(duplicate.returncode, 75, duplicate.stderr)
        release.touch()
        process.communicate(timeout=5)
        self.wait_for(lambda: not json.loads(self.call('status').stdout)['integration_lock_held'])
        status = json.loads(self.call('status').stdout)
        self.assertTrue(status['reconciliation_required'])
        self.assertEqual(status['checkpoint']['status'], 'running')
        self.assertEqual(status['checkpoint']['run_id'], checkpoint['run_id'])
        before = (self.state / 'checkpoint.json').read_bytes()
        self.assertEqual(self.call('run', sys.executable, '-c', 'pass').returncode, 78)
        self.assertNotEqual(self.call('run', '--reconciled-run-id', 'wrong', sys.executable, '-c', 'pass').returncode, 0)
        self.assertEqual((self.state / 'checkpoint.json').read_bytes(), before)
        # The integrator acknowledges actual live readback, not merely status inspection.
        result = self.call('run', '--reconciled-run-id', checkpoint['run_id'], sys.executable, '-c', 'pass')
        self.assertEqual(result.returncode, 0, result.stderr)
        archived = self.state / ('history-' + checkpoint['run_id'] + '.json')
        self.assertEqual(archived.read_bytes(), before)
        self.assertEqual(json.loads((self.state / 'checkpoint.json').read_text())['reconciled_run_id'], checkpoint['run_id'])

    def test_failed_command_requires_readback_acknowledgment(self):
        self.assertEqual(self.call('run', sys.executable, '-c', 'raise SystemExit(8)').returncode, 8)
        previous = json.loads((self.state / 'checkpoint.json').read_text())
        self.assertEqual(self.call('run', sys.executable, '-c', 'pass').returncode, 78)
        self.assertEqual(self.call('run', '--reconciled-run-id', previous['run_id'], sys.executable, '-c', 'pass').returncode, 0)

    def test_stop_persists_and_blocks_next_action_boundary(self):
        process, release = self.start_waiting_child()
        self.assertEqual(self.call('stop').returncode, 0)
        original_stop = (self.state / 'STOP').read_bytes()
        self.assertEqual(self.call('stop').returncode, 0)
        self.assertEqual((self.state / 'STOP').read_bytes(), original_stop)
        self.assertIsNone(process.poll())
        release.touch()
        process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0)
        before = (self.state / 'checkpoint.json').read_bytes()
        self.assertEqual(self.call('run', sys.executable, '-c', 'pass').returncode, 77)
        self.assertEqual((self.state / 'checkpoint.json').read_bytes(), before)
        self.assertTrue(json.loads(self.call('status').stdout)['stop_requested'])
        self.assertNotEqual(self.call('resume').returncode, 0)
        self.assertTrue((self.state / 'STOP').exists())

    def test_atomic_checkpoint_failure_keeps_previous_json(self):
        runtime.prepare_state(self.state)
        path = self.state / 'checkpoint.json'
        runtime.atomic_json(path, {'schema_version': 1, 'value': 'old'})
        with mock.patch.object(runtime.os, 'replace', side_effect=OSError('synthetic rename failure')):
            with self.assertRaisesRegex(OSError, 'synthetic'):
                runtime.atomic_json(path, {'schema_version': 1, 'value': 'new'})
        self.assertEqual(json.loads(path.read_text())['value'], 'old')
        self.assertEqual(sorted(p.name for p in self.state.iterdir()), ['checkpoint.json'])

    def test_corrupt_checkpoint_fails_closed(self):
        self.state.mkdir()
        (self.state / 'checkpoint.json').write_text('{broken')
        marker = self.root / 'must-not-run'
        result = self.call('run', sys.executable, '-c', f'open({str(marker)!r}, "w").close()')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertEqual((self.state / 'checkpoint.json').read_text(), '{broken')

    def test_missing_executable_records_failure_and_releases_lock(self):
        result = self.call('run', str(self.root / 'no-such-command'))
        self.assertEqual(result.returncode, 127)
        checkpoint = json.loads((self.state / 'checkpoint.json').read_text())
        self.assertEqual(checkpoint['status'], 'failed')
        self.assertEqual(checkpoint['exit_code'], 127)
        self.assertEqual(self.call('run', sys.executable, '-c', 'pass').returncode, 0)

    def test_symlink_lock_and_checkpoint_refused(self):
        self.state.mkdir()
        outside = self.root / 'outside'
        outside.write_text('untouched')
        for name in ('integration.lock', 'checkpoint.json'):
            with self.subTest(name=name):
                target = self.state / name
                if target.exists():
                    target.unlink()
                target.symlink_to(outside)
                self.assertNotEqual(self.call('run', sys.executable, '-c', 'pass').returncode, 0)
                self.assertEqual(outside.read_text(), 'untouched')
                target.unlink()


if __name__ == '__main__':
    unittest.main()
