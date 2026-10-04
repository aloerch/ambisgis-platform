"""Filesystem-only user-manager endpoint guards; never connects or starts a child."""
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import ambisgis_runtime as adapter
from installer.state import InstallError


class UserManagerSocketTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.user = self.base / 'user'
        self.user.mkdir(mode=0o700)
        self.systemd = self.user / 'systemd'
        self.systemd.mkdir(mode=0o755)
        self.bus = self.user / 'bus'
        self.private = self.systemd / 'private'
        for endpoint, mode in [(self.bus, 0o666), (self.private, 0o700)]:
            sock = socket.socket(socket.AF_UNIX)
            self.addCleanup(sock.close)
            sock.bind(str(endpoint))
            endpoint.chmod(mode)
        self.native = Path('/run/user') / str(os.getuid())
        checked = adapter.checked_path
        self.requests = []
        def mapped(path):
            path = Path(path)
            self.requests.append(path)
            if path.is_relative_to(self.native):
                path = self.user / path.relative_to(self.native)
            return checked(path)
        guard = patch.object(adapter, 'checked_path', side_effect=mapped)
        guard.start()
        self.addCleanup(guard.stop)
        no_child = patch('subprocess.Popen', side_effect=AssertionError('No subprocess permitted'))
        no_child.start()
        self.addCleanup(no_child.stop)

    def environment(self, **kwargs):
        return adapter.child_environment(self.base / 'installation', self.base / 'bundle', **kwargs)

    def test_constructs_manager_socket_without_inheriting_or_replacing_private_xdg(self):
        with patch.dict(os.environ, {'AMBISGIS_SYSTEMD_USER_SOCKET': '/untrusted/private',
                                     'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/untrusted/bus',
                                     'XDG_RUNTIME_DIR': '/untrusted/run'}):
            env = self.environment()
        self.assertEqual(env.get('AMBISGIS_SYSTEMD_USER_SOCKET'), str(self.private))
        self.assertEqual(env['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=' + str(self.bus))
        self.assertEqual(env['XDG_RUNTIME_DIR'], str(self.base / 'installation/runtime/run'))
        self.assertIn(self.native, self.requests)

    def test_no_bus_mode_has_no_manager_authority(self):
        with patch.dict(os.environ, {'AMBISGIS_SYSTEMD_USER_SOCKET': '/untrusted/private'}):
            env = self.environment(bus=False)
        self.assertNotIn('AMBISGIS_SYSTEMD_USER_SOCKET', env)
        self.assertNotIn('DBUS_SESSION_BUS_ADDRESS', env)
        self.assertEqual(self.requests, [])

    def test_owned_health_profile_is_constructed_without_inheriting_selector(self):
        for inherited in (None, '', 'untrusted-profile', 'development-v1'):
            with self.subTest(inherited=inherited), patch.dict(os.environ, {}, clear=True):
                if inherited is not None:
                    os.environ['AMBISGIS_HEALTH_TIMER_PROFILE'] = inherited
                env = self.environment()
                self.assertEqual(env.get('AMBISGIS_HEALTH_TIMER_PROFILE'), 'development-v1')
                self.assertEqual(env['AMBISGIS_SYSTEMD_USER_SOCKET'], str(self.private))

    def test_no_bus_mode_does_not_select_native_health_profile(self):
        with patch.dict(os.environ, {'AMBISGIS_HEALTH_TIMER_PROFILE': 'development-v1'}):
            env = self.environment(bus=False)
        self.assertNotIn('AMBISGIS_HEALTH_TIMER_PROFILE', env)
        self.assertNotIn('AMBISGIS_SYSTEMD_USER_SOCKET', env)
        self.assertEqual(self.requests, [])

    def test_missing_or_regular_file_manager_endpoint_is_rejected(self):
        self.private.unlink()
        with self.assertRaises((InstallError, OSError)):
            self.environment()
        self.private.write_bytes(b'inert')
        self.private.chmod(0o700)
        with self.assertRaises(InstallError):
            self.environment()

    def test_symlink_at_every_manager_component_is_rejected(self):
        for endpoint in [self.private, self.systemd, self.user]:
            with self.subTest(endpoint=endpoint.name):
                saved = endpoint.with_name(endpoint.name + '-original')
                endpoint.rename(saved)
                endpoint.symlink_to(saved, target_is_directory=saved.is_dir())
                try:
                    with self.assertRaises(InstallError):
                        self.environment()
                finally:
                    endpoint.unlink()
                    saved.rename(endpoint)

    def test_wrong_owner_at_each_endpoint_and_parent_is_rejected(self):
        original = Path.stat
        for target in [self.user, self.systemd, self.private, self.bus]:
            def wrong_owner(path, *args, **kwargs):
                info = original(path, *args, **kwargs)
                if path == target:
                    return SimpleNamespace(st_uid=os.getuid() + 1, st_mode=info.st_mode)
                return info
            with self.subTest(target=target.name), patch.object(Path, 'stat', wrong_owner):
                with self.assertRaises(InstallError):
                    self.environment()

    def test_unsafe_permissions_on_runtime_parent_and_socket_are_rejected(self):
        for target, unsafe in [(self.user, 0o750), (self.systemd, 0o775),
                               (self.systemd, 0o757), (self.private, 0o710), (self.private, 0o701)]:
            original = stat.S_IMODE(target.stat().st_mode)
            target.chmod(unsafe)
            try:
                with self.subTest(target=target.name, mode=oct(unsafe)), self.assertRaises(InstallError):
                    self.environment()
            finally:
                target.chmod(original)

    def test_session_bus_must_still_be_a_socket(self):
        self.bus.unlink()
        self.bus.write_bytes(b'inert')
        with self.assertRaises(InstallError):
            self.environment()


if __name__ == '__main__':
    unittest.main()
