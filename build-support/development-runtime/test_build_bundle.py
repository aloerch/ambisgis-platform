"""Small inert assembly negatives; selected executables are never run."""
from pathlib import Path
import tempfile
import subprocess
import unittest

import build_bundle as build


class BundleAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_writer_rejects_existing_output_and_preserves_sentinel(self):
        out = self.base / 'out'; out.mkdir(); (out / 'keep').write_bytes(b'keep')
        with self.assertRaises(FileExistsError): build.Writer(out)
        self.assertEqual((out / 'keep').read_bytes(), b'keep')

    def test_writer_rejects_escape_duplicate_and_symlink_source(self):
        writer = build.Writer(self.base / 'out')
        for name in ('../escape', '/absolute', 'x/../escape', '.', 'x//y'):
            with self.assertRaises(ValueError): writer.put(name, data=b'inert')
        writer.put('bin/helper', data=b'not executable during tests', executable=True)
        with self.assertRaises(ValueError): writer.put('bin/helper', data=b'changed')
        source = self.base / 'source'; source.write_bytes(b'keep'); link = self.base / 'link'; link.symlink_to(source)
        with self.assertRaises(ValueError): writer.put('copy', source=link)
        self.assertEqual(source.read_bytes(), b'keep')

    def test_source_hash_mismatch_rejects_before_copy(self):
        writer = build.Writer(self.base / 'out'); source = self.base / 'source'; source.write_bytes(b'original')
        with self.assertRaises(ValueError): writer.put('copy', source=source, sha256='0' * 64)
        self.assertFalse((writer.root / 'copy').exists())

    def launch_inert_bundle(self, leaf, *, public=True):
        root = self.base / leaf
        (root / 'runtime/engine').mkdir(parents=True)
        entry = root / ('bin/ambisgis' if public else 'runtime/bin/healthcheck-timer')
        entry.parent.mkdir(parents=True)
        entry.write_bytes(build.shell_launcher('ambisgis' if public else 'healthcheck-timer', public=public))
        # A private shell-only sentinel replaces env; no retained interpreter,
        # library, engine, bus, timer or installer CLI is present or invoked.
        sentinel = root / 'runtime/engine/env'
        sentinel.write_text('#!/usr/bin/bash\nprintf "%s\\n" "inert-launch-boundary"\n')
        sentinel.chmod(0o700)
        return subprocess.run(['/usr/bin/bash', str(entry)], cwd=self.base,
                              env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'},
                              capture_output=True, text=True, timeout=5)

    def test_launcher_rejects_unsupported_base_before_loader_or_exec(self):
        for leaf in ('bad space', 'bad:colon', 'bad$variable', 'bad%specifier',
                     'bad\\escape', 'bad\nnewline', 'bad\ttab', 'bad-unicodé'):
            with self.subTest(leaf=leaf):
                run = self.launch_inert_bundle(leaf)
                self.assertEqual(run.returncode, 125)
                self.assertEqual(run.stdout, '')
                self.assertEqual(run.stderr, 'The owned development bundle requires an absolute ASCII path using letters, digits, underscore, dot, slash and hyphen.\n')

    def test_launcher_preserves_trailing_controls_before_rejecting_sibling(self):
        for suffix in ('\n', '\r\n', '\n\n'):
            leaf = 'trailing-' + str(len(suffix)) + '-' + str(ord(suffix[0]))
            sibling = self.launch_inert_bundle(leaf)
            self.assertEqual(sibling.stdout, 'inert-launch-boundary\n')
            with self.subTest(suffix=repr(suffix)):
                run = self.launch_inert_bundle(leaf + suffix)
                self.assertEqual(run.returncode, 125)
                self.assertEqual(run.stdout, '')
                self.assertIn('absolute ASCII path', run.stderr)

    def test_launcher_allows_supported_public_and_health_paths(self):
        for public, leaf in ((True, 'allowed_A-1.2'), (False, '.allowed_B-3')):
            with self.subTest(public=public):
                run = self.launch_inert_bundle(leaf, public=public)
                self.assertEqual(run.returncode, 0)
                self.assertEqual(run.stdout, 'inert-launch-boundary\n')
                self.assertEqual(run.stderr, '')

    def test_launcher_clean_environment_and_relocatable_paths(self):
        for mode in ('ambisgis', 'podman', 'compose', 'systemd-run', 'healthcheck-timer'):
            text = build.shell_launcher(mode, public=mode == 'ambisgis').decode()
            self.assertIn('"$base/runtime/engine/env" -i', text)
            self.assertIn('-S -s -P', text)
            self.assertNotIn('/home/', text)
            self.assertNotIn('eval ', text)
            self.assertIn('unset LD_PRELOAD LD_AUDIT', text)


if __name__ == '__main__': unittest.main()
