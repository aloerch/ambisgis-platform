"""Small inert assembly negatives; selected executables are never run."""
from pathlib import Path
import tempfile
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

    def test_launcher_clean_environment_and_relocatable_paths(self):
        for mode in ('ambisgis', 'podman', 'compose', 'systemd-run', 'healthcheck-timer'):
            text = build.shell_launcher(mode, public=mode == 'ambisgis').decode()
            self.assertIn('"$base/runtime/engine/env" -i', text)
            self.assertIn('-S -s -P', text)
            self.assertNotIn('/home/', text)
            self.assertNotIn('eval ', text)
            self.assertIn('unset LD_PRELOAD LD_AUDIT', text)


if __name__ == '__main__': unittest.main()
