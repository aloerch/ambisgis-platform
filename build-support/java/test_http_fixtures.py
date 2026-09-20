"""Fail-closed fixture integrity/lifecycle checks; native Java evidence is separate."""
import difflib
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import http_fixtures


def digest(data):
    return hashlib.sha256(data).hexdigest()


class HttpFixtureTests(unittest.TestCase):
    def inputs(self, root, target='mapfish'):
        source = root / 'source'
        source.mkdir()
        output = root / 'output'
        output.mkdir()
        fixture = root / 'fixtures'
        fixture.mkdir()
        original, modified = b'bind wildcard\nassert unchanged\n', b'bind loopback\nassert unchanged\n'
        (source / 'fixture.java').write_bytes(original)
        (source / 'capabilities.xml').write_bytes(b'<capabilities/>')
        overlay = ''.join(difflib.unified_diff(original.decode().splitlines(True),
                            modified.decode().splitlines(True), 'a/fixture.java', 'b/fixture.java')).encode()
        (fixture / 'fixture.patch').write_bytes(overlay)
        hosts = b'127.0.0.1 localhost\n192.0.2.1 www.google.com\n'
        manifest = {'hosts': {'content': hosts.decode(), 'sha256': digest(hosts)}, 'targets': {target: {
            'path': 'fixture.java', 'patch': 'fixture.patch', 'before_sha256': digest(original),
            'after_sha256': digest(modified), 'patch_sha256': digest(overlay),
            'retained_test_files': {'capabilities.xml': digest(b'<capabilities/>')},
        }}}
        (fixture / 'manifest.json').write_text(json.dumps(manifest))
        return source, output, fixture

    def prepare(self, root, target='mapfish'):
        source, output, fixture = self.inputs(root, target)
        with patch.object(http_fixtures, 'FIXTURES', fixture):
            report = http_fixtures.prepare(source, output, target)
        return source, output, report

    def additional_helper(self, source, fixture):
        original, modified = b'client default address\n', b'client loopback address\n'
        (source / 'helper.java').write_bytes(original)
        overlay = ''.join(difflib.unified_diff(original.decode().splitlines(True),
                            modified.decode().splitlines(True), 'a/helper.java', 'b/helper.java')).encode()
        patch_path = fixture / 'fixture.patch'
        patch_path.write_bytes(patch_path.read_bytes() + overlay)
        manifest_path = fixture / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['targets']['mapfish']['patch_sha256'] = digest(patch_path.read_bytes())
        manifest['targets']['mapfish']['additional_patches'] = [{
            'path': 'helper.java', 'before_sha256': digest(original), 'after_sha256': digest(modified),
            'reason': 'test-only explicit client loopback address'}]
        manifest_path.write_text(json.dumps(manifest))

    def test_all_helper_patch_inputs_and_outputs_are_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output, fixture = self.inputs(Path(temp))
            self.additional_helper(source, fixture)
            with patch.object(http_fixtures, 'FIXTURES', fixture):
                report = http_fixtures.prepare(source, output, 'mapfish')
            self.assertEqual((source / 'helper.java').read_text(), 'client loopback address\n')
            self.assertEqual(report['additional_patches'][0]['path'], 'helper.java')
            self.assertFalse(report['assertions_changed'])

    def test_changed_additional_helper_fails_before_any_source_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output, fixture = self.inputs(Path(temp))
            self.additional_helper(source, fixture)
            (source / 'helper.java').write_text('unreviewed helper')
            with patch.object(http_fixtures, 'FIXTURES', fixture), self.assertRaisesRegex(ValueError, 'input differs'):
                http_fixtures.prepare(source, output, 'mapfish')
            self.assertEqual((source / 'fixture.java').read_text(), 'bind wildcard\nassert unchanged\n')
            self.assertFalse((output / 'http-fixture').exists())

    def test_wrong_additional_helper_output_hash_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output, fixture = self.inputs(Path(temp))
            self.additional_helper(source, fixture)
            manifest_path = fixture / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['targets']['mapfish']['additional_patches'][0]['after_sha256'] = '0' * 64
            manifest_path.write_text(json.dumps(manifest))
            with patch.object(http_fixtures, 'FIXTURES', fixture), self.assertRaisesRegex(ValueError, 'output differs'):
                http_fixtures.prepare(source, output, 'mapfish')
            self.assertFalse((output / 'http-fixture/prepared.json').exists())

    def events(self, output, entries):
        (output / 'http-fixture/events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in entries))

    def test_real_patch_retains_original_assertions_and_fixed_hosts(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output, report = self.prepare(Path(temp))
            self.assertEqual((source / 'fixture.java').read_text(), 'bind loopback\nassert unchanged\n')
            self.assertEqual((source / 'capabilities.xml').read_bytes(), b'<capabilities/>')
            self.assertFalse(report['assertions_changed'])
            self.assertEqual((output / 'http-fixture/hosts').read_text(),
                             '127.0.0.1 localhost\n192.0.2.1 www.google.com\n')
            self.assertTrue(all(str(output) in option for option in report['java_properties']))

    def test_source_or_resource_drift_fails_before_any_patch(self):
        for name in ('fixture.java', 'capabilities.xml'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                source, output, fixture = self.inputs(Path(temp))
                (source / name).write_bytes(b'changed input')
                with patch.object(http_fixtures, 'FIXTURES', fixture), self.assertRaises(ValueError):
                    http_fixtures.prepare(source, output, 'mapfish')
                self.assertFalse((output / 'http-fixture').exists())

    def test_fixture_source_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output, fixture = self.inputs(Path(temp))
            (source / 'capabilities.xml').rename(source / 'elsewhere.xml')
            (source / 'capabilities.xml').symlink_to('elsewhere.xml')
            with patch.object(http_fixtures, 'FIXTURES', fixture), self.assertRaisesRegex(ValueError, 'symlinks'):
                http_fixtures.prepare(source, output, 'mapfish')

    def test_bad_patch_checksum_fails_before_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output, fixture = self.inputs(Path(temp))
            (fixture / 'fixture.patch').write_text('not the reviewed patch')
            with patch.object(http_fixtures, 'FIXTURES', fixture), self.assertRaisesRegex(ValueError, 'checksum'):
                http_fixtures.prepare(source, output, 'mapfish')
            self.assertIn('bind wildcard', (source / 'fixture.java').read_text())

    def test_wrong_output_digest_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output, fixture = self.inputs(Path(temp))
            path = fixture / 'manifest.json'
            manifest = json.loads(path.read_text())
            manifest['targets']['mapfish']['after_sha256'] = '0' * 64
            path.write_text(json.dumps(manifest))
            with patch.object(http_fixtures, 'FIXTURES', fixture), self.assertRaisesRegex(ValueError, 'output differs'):
                http_fixtures.prepare(source, output, 'mapfish')
            self.assertFalse((output / 'http-fixture/prepared.json').exists())

    def test_completed_lifecycles_include_bound_but_unstarted_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            _, output, _ = self.prepare(Path(temp))
            self.events(output, [
                {'event': 'bound', 'port': 13000}, {'event': 'ready', 'port': 13000},
                {'event': 'response', 'port': 13000, 'path': '/500', 'status': 500},
                {'event': 'response', 'port': 13000, 'path': '/notImage', 'status': 200},
                {'event': 'stopped', 'port': 13000},
                {'event': 'bound', 'port': 13001}, {'event': 'stopped', 'port': 13001}])
            result = http_fixtures.finalize(output, 'mapfish')
            self.assertEqual(result['servers_ready'], 1)
            self.assertEqual(result['servers_stopped'], 2)
            self.assertTrue(result['all_owned_servers_stopped'])
            self.assertEqual(result['completed_responses'], [
                {'path': '/500', 'status': 500, 'count': 1},
                {'path': '/notImage', 'status': 200, 'count': 1}])

    def test_missing_readiness_cleanup_and_invalid_order_fail_closed(self):
        for sequence in ([], ['bound'], ['bound', 'ready'], ['bound', 'stopped'], ['ready', 'stopped'],
                         ['bound', 'ready', 'ready', 'stopped'], ['bound', 'ready', 'stopped', 'stopped']):
            with self.subTest(sequence=sequence), tempfile.TemporaryDirectory() as temp:
                _, output, _ = self.prepare(Path(temp))
                self.events(output, [{'event': action, 'port': 13000} for action in sequence])
                with self.assertRaises(ValueError):
                    http_fixtures.finalize(output, 'mapfish')
                self.assertFalse((output / 'http-fixture/completed.json').exists())

    def test_malformed_lifecycle_events_fail_closed(self):
        for event in ({'event': 'bound', 'port': True}, {'event': 'bound', 'port': 0},
                      {'event': 'bound', 'port': 65536}, {'event': 'bound', 'port': 13000, 'extra': True}):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as temp:
                _, output, _ = self.prepare(Path(temp))
                self.events(output, [event])
                with self.assertRaisesRegex(ValueError, 'malformed'):
                    http_fixtures.finalize(output, 'mapfish')

    def test_malformed_or_unreviewed_response_is_refused(self):
        valid = {'event': 'response', 'port': 13000, 'path': '/notImage', 'status': 200}
        for changes in ({'path': '/notImage?secret=omitted'}, {'path': []}, {'status': True},
                        {'status': 500}, {'body': 'never retained'}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as temp:
                _, output, _ = self.prepare(Path(temp))
                self.events(output, [{'event': 'bound', 'port': 13000},
                                     {'event': 'ready', 'port': 13000}, dict(valid, **changes)])
                with self.assertRaisesRegex(ValueError, 'malformed'):
                    http_fixtures.finalize(output, 'mapfish')

    def test_responses_require_ready_owned_server(self):
        for prefix in ([], ['bound'], ['bound', 'ready', 'stopped']):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as temp:
                _, output, _ = self.prepare(Path(temp))
                self.events(output, [{'event': operation, 'port': 13000} for operation in prefix] + [
                    {'event': 'response', 'port': 13000, 'path': '/notImage', 'status': 200}])
                with self.assertRaisesRegex(ValueError, 'outside ready'):
                    http_fixtures.finalize(output, 'mapfish')

    def test_expected_error_assertions_alone_cannot_replace_http_response_evidence(self):
        for routes in ([], ['/500'], ['/notImage']):
            with self.subTest(routes=routes), tempfile.TemporaryDirectory() as temp:
                _, output, _ = self.prepare(Path(temp))
                self.events(output, [{'event': 'bound', 'port': 13000}, {'event': 'ready', 'port': 13000}] + [
                    {'event': 'response', 'port': 13000, 'path': route,
                     'status': http_fixtures.RESPONSE_STATUSES[route]} for route in routes] + [
                    {'event': 'stopped', 'port': 13000}])
                with self.assertRaisesRegex(ValueError, 'responses missing'):
                    http_fixtures.finalize(output, 'mapfish')
                self.assertFalse((output / 'http-fixture/completed.json').exists())

    def test_changed_hosts_fail_finalization(self):
        with tempfile.TemporaryDirectory() as temp:
            _, output, _ = self.prepare(Path(temp), 'xml')
            (output / 'http-fixture/hosts').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                http_fixtures.finalize(output, 'xml')

    def test_wrong_target_fails_finalization(self):
        with tempfile.TemporaryDirectory() as temp:
            _, output, _ = self.prepare(Path(temp), 'xml')
            with self.assertRaisesRegex(ValueError, 'changed'):
                http_fixtures.finalize(output, 'mapfish')

    def test_fixture_is_not_available_for_unreviewed_targets(self):
        with self.assertRaisesRegex(ValueError, 'only supports'):
            http_fixtures.prepare(Path('/nonexistent'), Path('/nonexistent'), 'oauth')

    def test_checked_paths_cannot_escape_source(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ('../escape', '/tmp/escape', 'nested/../../escape'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unsafe'):
                    http_fixtures._checked_file(Path(temp), name)


if __name__ == '__main__':
    unittest.main()
