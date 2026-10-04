"""Small inert assembly negatives; selected executables are never run."""
from pathlib import Path
import hashlib
from unittest import mock
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


class OwnedNativePairAssemblyTests(unittest.TestCase):
    SOURCES = (
        'LICENSE', 'libpod/ambisgis_oci_environment.go', 'libpod/ambisgis_oci_environment_test.go',
        'pkg/systemd/dbus.go', 'pkg/systemd/ambisgis_user_socket.go', 'pkg/systemd/ambisgis_user_socket_test.go',
        'libpod/healthcheck_linux.go', 'libpod/ambisgis_health_timer.go', 'libpod/ambisgis_health_timer_test.go',
        'libpod/container_inspect.go', 'libpod/define/container_inspect.go',
        'libpod/ambisgis_inspect_sysctls.go', 'libpod/ambisgis_inspect_sysctls_test.go',
        'cmd/rootlessport/main.go', 'cmd/rootlessport/ambisgis_rootlessport.go',
        'cmd/rootlessport/ambisgis_rootlessport_test.go',
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.native = self.base / 'native'
        self.native.mkdir(); self.producers = self.base / 'producers'; self.producers.mkdir()
        self.pins = {}
        def put(name, data):
            path = self.native / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data); self.pins[path] = hashlib.sha256(data).hexdigest()
            return self.pins[path]
        self.put = put
        recipe = b'# inert fixture only, never executed\n'
        for name in ('podman_health_timer_build.py', 'podman_rootlessport_build.py'):
            (self.producers / name).write_bytes(recipe)
        recipe_hash = put('build-executed.py', recipe)
        put('bin/podman', b'inert engine bytes'); put('bin/rootlessport', b'inert helper bytes')
        put('bin/unshipped.test', b'not a runtime artifact')
        patched = {}
        for name in self.SOURCES:
            patched[name] = {'kind': 'file', 'sha256': put('source/' + name, ('inert ' + name).encode())}
        patch = self.native / 'predecessor.patch'; put('predecessor.patch', b'inert retained patch')
        self.preparation = {'vendor_unchanged': True, 'patched': patched,
                            'existing_patches': [{'file': str(patch), 'sha256': self.pins[patch]}]}
        put('preparation.json', build.encoded(self.preparation))
        put('invocation.json', build.encoded({'recipe_sha256': recipe_hash}))
        put('owned-source.patch', b'inert successor patch'); put('MODIFICATIONS.txt', b'inert notice')
        self.record_names = ('preparation.json', 'invocation.json', 'owned-source.patch', 'MODIFICATIONS.txt')
        self.result = {'exit_code': 0, 'unchanged': {'source': True, 'prior_source': True,
                       'baseline': True, 'toolchain': True}, 'records': {}}
        self.refresh()
        for name, value in (('PODMAN', self.native), ('PINS', self.pins),
                            ('__file__', str(self.producers / 'build_bundle.py'))):
            patcher = mock.patch.object(build, name, value); patcher.start(); self.addCleanup(patcher.stop)
        self.writer = build.Writer(self.base / 'out')

    def refresh(self):
        self.put('preparation.json', build.encoded(self.preparation))
        self.result['records'] = {name: self.pins[self.native / name] for name in self.record_names}
        self.put('result.json', build.encoded(self.result))

    def test_exact_pair_and_all_composed_source_notices_are_retained(self):
        build.add_owned_podman(self.writer)
        executable = {name for name, row in self.writer.rows.items() if row['mode'] & 0o111}
        self.assertEqual(executable, {'runtime/engine/podman', 'runtime/helpers/rootlessport'})
        prefix = 'runtime/notices/podman-owned-build/source/'
        self.assertEqual({name[len(prefix):] for name in self.writer.rows if name.startswith(prefix)}, set(self.SOURCES))
        for name in self.SOURCES:
            self.assertEqual((self.writer.root / prefix / name).read_bytes(), (self.native / 'source' / name).read_bytes())
        self.assertEqual((self.writer.root / 'runtime/notices/podman-owned-build/prior-patches/0-predecessor.patch').read_bytes(), b'inert retained patch')
        self.assertFalse(any('unshipped.test' in name for name in self.writer.rows))

    def test_failed_build_refused_before_copy(self):
        self.result['exit_code'] = 1; self.refresh()
        with self.assertRaises(ValueError): build.add_owned_podman(self.writer)
        self.assertEqual(self.writer.rows, {})

    def test_changed_source_custody_refused_before_copy(self):
        self.result['unchanged']['source'] = False; self.refresh()
        with self.assertRaises(ValueError): build.add_owned_podman(self.writer)
        self.assertEqual(self.writer.rows, {})

    def test_binary_drift_refused(self):
        (self.native / 'bin/podman').write_bytes(b'changed binary')
        with self.assertRaises(ValueError): build.add_owned_podman(self.writer)
        self.assertFalse((self.writer.root / 'runtime/engine/podman').exists())

    def test_local_composed_recipe_drift_refused(self):
        (self.producers / 'podman_rootlessport_build.py').write_bytes(b'changed recipe')
        with self.assertRaises(ValueError): build.add_owned_podman(self.writer)
        self.assertEqual(self.writer.rows, {})

    def test_composed_source_notice_drift_refused(self):
        (self.native / 'source/cmd/rootlessport/ambisgis_rootlessport.go').write_bytes(b'changed source')
        with self.assertRaises(ValueError): build.add_owned_podman(self.writer)
        self.assertFalse((self.writer.root / 'runtime/notices/podman-owned-build/source/cmd/rootlessport/ambisgis_rootlessport.go').exists())

    def test_vendor_change_refused_before_copy(self):
        self.preparation['vendor_unchanged'] = False; self.refresh()
        with self.assertRaises(ValueError): build.add_owned_podman(self.writer)
        self.assertEqual(self.writer.rows, {})


if __name__ == '__main__': unittest.main()
