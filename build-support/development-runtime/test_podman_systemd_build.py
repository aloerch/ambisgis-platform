"""Inert source/custody/command guards; no Go, socket, engine or runtime execution."""
from pathlib import Path
import tempfile
import unittest

import podman_systemd_build as build


class SystemdSocketTests(unittest.TestCase):
    def fixture(self, root):
        folder = root/'pkg/systemd'; folder.mkdir(parents=True)
        target = folder/'dbus.go'
        target.write_bytes((build.PRIOR/'source/pkg/systemd/dbus.go').read_bytes())
        return target

    def test_only_the_rootless_path_assignment_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = self.fixture(root); before = target.read_text()
            self.assertIn(build.ASSIGNMENT, before)
            self.assertNotIn('AMBISGIS_SYSTEMD_USER_SOCKET', before)
            delta, baseline, selection = build.patch(root)
            after = target.read_text()
            self.assertEqual(after.count(build.CALL), 1)
            self.assertEqual(after.replace(build.CALL, build.ASSIGNMENT), before)
            self.assertTrue(selection['evalsymlinks_dial_auth_and_rootful_unchanged'])
            self.assertEqual((root/'pkg/systemd/ambisgis_user_socket.go').read_text(), build.HELPER)
            self.assertEqual((root/'pkg/systemd/ambisgis_user_socket_test.go').read_text(), build.TEST)
            self.assertIn(build.ASSIGNMENT.replace('os.Getenv("XDG_RUNTIME_DIR")', 'runtimeDir').lstrip('\t'), baseline)
            self.assertNotIn('explicitSocket', baseline)
            self.assertIn('+++ b/pkg/systemd/ambisgis_user_socket_test.go', delta)
            self.assertEqual(len(list(root.rglob('*.go'))), 3)
            with self.assertRaises(ValueError): build.patch(root)

    def test_changed_source_or_existing_helper_is_rejected_before_write(self):
        for variant in ('changed', 'helper', 'test'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); target = self.fixture(root)
                if variant == 'changed': target.write_text(target.read_text()+'\n// altered\n')
                else:
                    name = 'ambisgis_user_socket.go' if variant == 'helper' else 'ambisgis_user_socket_test.go'
                    (target.parent/name).write_text('preserve')
                before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with self.assertRaises(ValueError): build.patch(root)
                self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_exact_six_commands_use_only_standalone_new_units(self):
        plan = build.command_plan(Path('/fresh/job'))
        self.assertEqual([row[0] for row in plan], ['baseline-compile','baseline-unit','socket-compile','socket-unit','podman-build','rootlessport-build'])
        self.assertEqual([row[2] for row in plan], [0,1,0,0,0,0])
        self.assertEqual(plan[0][1][-2:], ['/fresh/job/baseline/socket.go','/fresh/job/baseline/socket_test.go'])
        self.assertEqual(plan[2][1][-2:], ['pkg/systemd/ambisgis_user_socket.go','pkg/systemd/ambisgis_user_socket_test.go'])
        for name, command, _ in plan:
            for forbidden in ('./pkg/systemd','./libpod','./test','checkpoint','native_tests.py','gitCommit','-ldflags'):
                self.assertNotIn(forbidden, ' '.join(command))
            if name.endswith('-unit'):
                self.assertEqual(command[1:], ['-test.run=^TestAmbisGISSystemdUserSocket$','-test.count=1','-test.v'])
            else:
                for option in ('-mod=vendor','-buildvcs=false','-trimpath','-p=2'): self.assertIn(option, command)

    def test_native_log_oracle_requires_fallback_passes_and_specific_baseline_failures(self):
        def log(baseline):
            rows = []
            for case in (*build.BASELINE_PASSES, *build.BASELINE_FAILURES):
                status = 'FAIL' if baseline and case in build.BASELINE_FAILURES else 'PASS'
                rows += ['=== RUN   TestAmbisGISSystemdUserSocket/'+case,
                         '    --- '+status+': TestAmbisGISSystemdUserSocket/'+case+' (0.00s)']
            return '\n'.join(rows)+('\nFAIL\n' if baseline else '\nPASS\n')
        for baseline in (False, True):
            good = log(baseline); self.assertTrue(build.unit_result(good, baseline))
            self.assertFalse(build.unit_result(good.replace('explicit_user', 'unselected'), baseline))
            self.assertFalse(build.unit_result('compiler error\nFAIL\n', baseline))
            self.assertFalse(build.unit_result(good.replace('fallback_private (', 'missing ('), baseline))
        self.assertFalse(build.unit_result(log(False), True))
        self.assertFalse(build.unit_result(log(True), False))

    def test_source_inventory_rejects_escapes_and_specials(self):
        helper = build.retained_helper()
        for variant in ('link', 'fifo'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)/'source'; root.mkdir()
                if variant == 'link': (root/'bad').symlink_to('/etc/passwd')
                else:
                    import os
                    os.mkfifo(root/'bad')
                with self.assertRaises(ValueError): build.inventory(helper, root)

    def test_toolchain_dangling_links_still_must_be_contained(self):
        helper = build.retained_helper()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'toolchain'; root.mkdir()
            link = root/'cache'; link.symlink_to('var/cache')
            with self.assertRaises(FileNotFoundError): build.inventory(helper, root)
            self.assertEqual(build.inventory(helper, root, retained_toolchain=True), {'cache': {'kind':'symlink','target':'var/cache'}})
            link.unlink(); link.symlink_to('../outside')
            with self.assertRaises(ValueError): build.inventory(helper, root, retained_toolchain=True)


if __name__ == '__main__': unittest.main()
