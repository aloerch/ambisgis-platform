# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import io
import unittest

from selection import Selector, key, parse_atom, parse_records, rich_dependency, rpm_overlap, satisfies


def package(name, version='1', release='1', requires=(), provides=(), arch='x86_64'):
    return {'name': name, 'epoch': '0', 'version': version, 'release': release, 'arch': arch,
            'provides': [{'name': name, 'flags': 'EQ', 'epoch': '0', 'ver': version, 'rel': release}, *provides],
            'requires': list(requires), 'files': [], 'publisher_digest': name + version + release}


class SelectionTests(unittest.TestCase):
    def select(self, rows, roots=('app',), host=None):
        selector = Selector(rows, rpm_overlap, lambda name: (host or {}).get(name, []))
        selector.select(roots)
        return selector

    def test_transitive_provider_closure(self):
        rows = [package('app', requires=[{'name': 'libA'}]), package('libA', requires=[{'name': 'libB'}]), package('libB')]
        result = self.select(rows)
        self.assertEqual({x[0] for x in result.selected}, {'app', 'libA', 'libB'})
        self.assertFalse(result.unresolved)
        self.assertEqual(len(result.edges), 3)

    def test_cycles_terminate_without_dropping_edges(self):
        result = self.select([package('app', requires=[{'name': 'other'}]), package('other', requires=[{'name': 'app'}])])
        self.assertEqual(len(result.selected), 2)
        self.assertEqual(len(result.edges), 3)

    def test_no_installed_fallback_for_missing_snapshot_bytes(self):
        host = {'missing': [package('missing')]}
        result = self.select([package('app', requires=[{'name': 'missing'}])], host=host)
        self.assertEqual(len(result.unresolved), 1)
        self.assertEqual(len(result.selected), 1)

    def test_rpm_release_omission_and_epoch_semantics(self):
        provided = parse_atom('lib = 2:1.6.0-1.1')
        self.assertTrue(satisfies(provided, parse_atom('lib = 2:1.6.0'), rpm_overlap))
        self.assertFalse(satisfies(provided, parse_atom('lib >= 2:1.6.0-2'), rpm_overlap))
        self.assertTrue(satisfies(provided, parse_atom('lib > 1:99.0'), rpm_overlap))
        # librpm treats an unversioned virtual capability as unconstrained.
        self.assertTrue(satisfies({'name': 'lib'}, parse_atom('lib >= 1'), rpm_overlap))

    def test_version_constraints_choose_satisfying_provider(self):
        result = self.select([package('app', requires=[parse_atom('lib >= 2')]), package('lib', '1'), package('lib', '2')])
        self.assertIn(key(package('lib', '2')), result.selected)
        self.assertNotIn(key(package('lib', '1')), result.selected)

    def test_ambiguous_provider_is_not_arbitrary_latest(self):
        result = self.select([package('app', requires=[{'name': 'lib'}]), package('lib', '1'), package('lib', '2')])
        self.assertEqual(len(result.unresolved), 1)
        self.assertIn('Ambiguous', result.unresolved[0]['error'])

    def test_installed_exact_identity_only_disambiguates_retained_candidates(self):
        lib1, lib2 = package('lib', '1'), package('lib', '2')
        result = self.select([package('app', requires=[{'name': 'lib'}]), lib1, lib2], host={'lib': [lib1]})
        self.assertIn(key(lib1), result.selected)
        self.assertNotIn(key(lib2), result.selected)

    def test_kernel_conditional_is_active_for_existing_host(self):
        provider = package('kernel-default', provides=[{'name': 'kernel'}, {'name': 'kmod(nf_tables.ko)'}])
        result = self.select([package('app', requires=[{'name': '(kmod(nf_tables.ko) if kernel)'}]), provider], host={'kernel': [provider]})
        self.assertFalse(result.unresolved)
        self.assertIn(key(provider), result.selected)
        self.assertTrue(result.conditionals[0]['active'])

    def test_inactive_host_conditional_remains_explicit(self):
        result = self.select([package('app', requires=[{'name': '(profile if selinux-policy)'}]), package('profile')])
        self.assertEqual(len(result.selected), 1)
        self.assertFalse(result.conditionals[0]['active'])

    def test_condition_rechecked_when_later_provider_becomes_selected(self):
        result = self.select([package('app', requires=[{'name': '(profile if policy)'}, {'name': 'later'}]),
                              package('later', requires=[{'name': 'policy'}]), package('policy'), package('profile')])
        self.assertEqual({x[0] for x in result.selected}, {'app', 'later', 'policy', 'profile'})
        self.assertTrue(result.conditionals[0]['active'])

    def test_active_condition_without_provider_is_unresolved(self):
        result = self.select([package('app', requires=[{'name': '(missing if kernel)'}])], host={'kernel': [package('kernel')]})
        self.assertEqual(len(result.unresolved), 1)

    def test_compound_host_condition_requires_both_terms(self):
        rows = [package('app', requires=[{'name': '(addon if (snapper and btrfsprogs))'}]), package('addon')]
        first = self.select(rows, host={'snapper': [package('snapper')]})
        self.assertFalse(first.conditionals[0]['active'])
        self.assertEqual(len(first.selected), 1)
        second = self.select(rows, host={'snapper': [package('snapper')], 'btrfsprogs': [package('btrfsprogs')]})
        self.assertTrue(second.conditionals[0]['active'])
        self.assertIn(key(package('addon')), second.selected)

    def test_or_records_original_and_selected_alternative(self):
        result = self.select([package('app', requires=[{'name': '(missing or fallback)'}]), package('fallback')])
        self.assertFalse(result.unresolved)
        edge = next(x for x in result.edges if x['from'])
        self.assertEqual(edge['rich_requirement'], '(missing or fallback)')
        self.assertEqual(edge['provider'][0], 'fallback')

    def test_unsupported_rich_syntax_cannot_disappear(self):
        result = self.select([package('app', requires=[{'name': '(one and two)'}]), package('one'), package('two')])
        self.assertEqual(len(result.unresolved), 1)

    def test_conflicting_exact_identity_rejected(self):
        original = package('app')
        changed = copy.deepcopy(original)
        changed['publisher_digest'] = 'changed'
        with self.assertRaises(ValueError):
            self.select([original, changed])

    def test_same_exact_duplicate_is_one_package(self):
        result = self.select([package('app'), package('app')])
        self.assertEqual(len(result.selected), 1)

    def test_explicit_root_cannot_be_missing(self):
        with self.assertRaises(ValueError):
            self.select([])

    def test_unknown_operator_and_range_provides_rejected(self):
        with self.assertRaises(ValueError):
            satisfies(parse_atom('x = 1'), {'name': 'x', 'flags': 'INVALID', 'ver': '1'}, rpm_overlap)
        with self.assertRaises(ValueError):
            satisfies(parse_atom('x >= 1'), parse_atom('x = 1'), rpm_overlap)

    def test_rich_atom_version_and_parentheses(self):
        operation, left, right = rich_dependency('(passt-selinux = 20260612.a9c61ff-1.3 if selinux-policy-targeted)')
        self.assertEqual(operation, 'if')
        self.assertEqual(left['rel'], '1.3')
        self.assertEqual(right['name'], 'selinux-policy-targeted')
        self.assertEqual(rich_dependency('(kmod(foo.ko) if kernel)')[1]['name'], 'kmod(foo.ko)')

    def test_parser_rejects_unsafe_package_location(self):
        xml = b'''<metadata xmlns="http://linux.duke.edu/metadata/common"><package><name>x</name><arch>x86_64</arch><version epoch="0" ver="1" rel="1"/><checksum type="sha256">00</checksum><location href="../escape.rpm"/></package></metadata>'''
        with self.assertRaises(ValueError):
            parse_records(io.BytesIO(xml))

    def test_real_snapshot_prerelease_path_is_preserved(self):
        xml = b'''<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:r="http://linux.duke.edu/metadata/rpm"><package><name>OpenRGB</name><arch>x86_64</arch><version epoch="0" ver="1.0~rc3.1+git0.g5e81e26f" rel="1.1"/><checksum type="sha256">00</checksum><size package="123"/><location href="x86_64/OpenRGB-1.0~rc3.1+git0.g5e81e26f-1.1.x86_64.rpm"/><format><r:sourcerpm>OpenRGB.src.rpm</r:sourcerpm><r:license>GPL-2.0-or-later</r:license></format></package></metadata>'''
        records = parse_records(io.BytesIO(xml))
        self.assertEqual(len(records), 1)
        self.assertIn('1.0~rc3.1', records[0]['location'])


if __name__ == '__main__':
    unittest.main()
