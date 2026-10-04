#!/usr/bin/env python3
"""Adversarial guards for signed metadata comparison; no package execution."""
import unittest

from audit import compare_dependencies, safe_filename


class AuditGuards(unittest.TestCase):
    def test_context_flags_do_not_change_version_relation(self):
        compare_dependencies([{'name': '/bin/sh'}],
                             [{'name': '/bin/sh', 'flags': 768, 'evr': ''}])

    def test_version_relation_and_epoch_are_authoritative(self):
        expected = [{'name': 'library', 'flags': 'GE', 'epoch': '1', 'ver': '3', 'rel': '2'}]
        compare_dependencies(expected, [{'name': 'library', 'flags': 12, 'evr': '1:3-2'}])
        for flags, evr in [(8, '1:3-2'), (12, '3-2'), (12, '1:4-2')]:
            with self.subTest(flags=flags, evr=evr), self.assertRaises(ValueError):
                compare_dependencies(expected, [{'name': 'library', 'flags': flags, 'evr': evr}])

    def test_omitted_or_added_dependencies_fail(self):
        with self.assertRaises(ValueError):
            compare_dependencies([{'name': 'required'}], [])
        with self.assertRaises(ValueError):
            compare_dependencies([], [{'name': 'unexpected', 'flags': 0, 'evr': ''}])

    def test_default_zero_epoch_and_separate_rpm_format_handling(self):
        compare_dependencies([{'name': 'p', 'flags': 'EQ', 'ver': '1', 'rel': '1'}],
                             [{'name': 'p', 'flags': 8, 'evr': '0:1-1'},
                              {'name': 'rpmlib(FileDigests)', 'flags': 10, 'evr': '4.6.0-1'}])

    def test_pruned_requires_returned_for_explicit_provider_proof(self):
        extra = compare_dependencies([], [{'name': 'libc.so.6(GLIBC_2.2.5)(64bit)', 'flags': 0, 'evr': ''}], allow_extra=True)
        self.assertEqual(extra, {('libc.so.6(GLIBC_2.2.5)(64bit)', 0, '')})
        with self.assertRaises(ValueError):
            compare_dependencies([{'name': 'unproven'}], [], allow_extra=True)

    def test_untrusted_file_names(self):
        self.assertEqual(safe_filename('/usr/bin/podman'), '/usr/bin/podman')
        self.assertEqual(safe_filename(r'/usr/lib/systemd/system/system-systemd\x2dcryptsetup.slice'),
                         r'/usr/lib/systemd/system/system-systemd\x2dcryptsetup.slice')
        for name in ('relative', '//etc/passwd', '/usr/../etc/passwd', '/usr//bin/p', '/usr/./bin/p', '/usr/evil\\name', '/usr/a\x00b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_filename(name)


if __name__ == '__main__':
    unittest.main()
