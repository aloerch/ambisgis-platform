"""Synthetic files/ZIPs and a fake Git boundary only; no child/native execution."""
import copy
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

import owned_scm as candidate


def selections():
    return {name: {'commit': str(i + 1) * 40, 'tree': str(i + 4) * 40}
            for i, name in enumerate(candidate.ROOTS)}


class FakeGit:
    def __init__(self, source, repos, selected):
        self.source, self.repos, self.selected = source, repos, selected
        self.calls, self.clones = [], {}
        self.parent_discovery = False
        self.wrong_index = False
        self.wrong_alternate = False
        self.trees = {}
        for family in candidate.ROOTS:
            root = source / family
            entries = []
            for name, (_, mode) in sorted(candidate._source_inventory(root).items()):
                data = (root / name).read_bytes()
                oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                entries.append((name, mode, oid))
            self.trees[family] = entries

    def __call__(self, repo, *args):
        repo = Path(repo)
        self.calls.append((repo, args))
        if args[0] == 'clone':
            origin, clone = map(Path, args[-2:])
            family = next(k for k, v in self.repos.items() if v == origin)
            self.clones[clone] = family
            metadata = clone / '.git'
            (metadata / 'objects/info').mkdir(parents=True)
            alternate = origin / 'objects'
            if self.wrong_alternate:
                alternate = origin.parent / 'unrelated-objects'
            (metadata / 'objects/info/alternates').write_text(str(alternate) + '\n')
            (metadata / 'HEAD').write_text('ref: refs/heads/fixture\n')
            return b''
        family = self.clones.get(repo) or next(
            (k for k in candidate.ROOTS if repo == self.repos[k] or
             repo == self.source / k or repo == self.source / k / candidate.MAVEN_ROOTS[k]), None)
        if family is None:
            raise AssertionError('Unexpected fake Git directory')
        row = self.selected[family]
        if args == ('rev-parse', '--is-bare-repository'):
            return b'false\n'
        if args == ('rev-parse', '--show-toplevel'):
            if self.parent_discovery:
                return str(self.source.parent).encode() + b'\n'
            path = self.repos[family] if repo == self.repos[family] else self.source / family
            return str(path).encode() + b'\n'
        if args == ('rev-parse', '--path-format=absolute', '--git-path', 'objects'):
            return str(self.repos[family] / 'objects').encode() + b'\n'
        if args[0] == 'rev-parse':
            return (row['tree'] if args[1].endswith('^{tree}') else row['commit']).encode() + b'\n'
        if args[:3] == ('update-ref', '--no-deref', 'HEAD'):
            (repo / '.git/HEAD').write_text(args[3] + '\n')
            return b''
        if args[0] == 'read-tree':
            return b''
        if args[0] in ('ls-tree', 'ls-files'):
            rows = []
            for name, mode, oid in self.trees[family]:
                if self.wrong_index and args[0] == 'ls-files':
                    oid = 'a' * 40
                text = ('100755' if mode == 0o755 else '100644') + ' '
                text += ('blob ' + oid if args[0] == 'ls-tree' else oid + ' 0')
                rows.append((text + '\t' + name).encode())
            return b'\0'.join(rows) + b'\0'
        raise AssertionError('Unexpected fake Git arguments')


class MetadataPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.repos = {}
        self.selected = selections()
        for name in candidate.ROOTS:
            maven = self.source / name / candidate.MAVEN_ROOTS[name]
            maven.mkdir(parents=True)
            (maven / 'pom.xml').write_text('<project/>\n')
            (maven / 'pom.xml').chmod(0o644)
            self.repos[name] = self.root / 'repos' / name
            (self.repos[name] / 'objects').mkdir(parents=True)
        self.fake = FakeGit(self.source, self.repos, self.selected)

    def prepare(self):
        with mock.patch.object(candidate, '_git', side_effect=self.fake), \
                mock.patch.object(candidate.subprocess, 'check_output', side_effect=AssertionError('native denied')):
            return candidate.prepare(self.source, self.repos, self.selected)

    def test_real_metadata_shape_detached_index_and_unchanged_source(self):
        before = {k: candidate._source_inventory(self.source / k) for k in candidate.ROOTS}
        result = self.prepare()
        self.assertTrue(result['serial_reactor_required'])
        self.assertEqual(set(candidate.ROOTS), set(result['roots']))
        for name in candidate.ROOTS:
            self.assertEqual(before[name], candidate._source_inventory(self.source / name))
            self.assertEqual(self.selected[name]['commit'] + '\n',
                             (self.source / name / '.git/HEAD').read_text())
            self.assertTrue(result['roots'][name]['object_store_must_remain_available'])
        commands = [args for _, args in self.fake.calls]
        clones = [args for args in commands if args[0] == 'clone']
        self.assertEqual(3, len(clones))
        for args in clones:
            self.assertIn('--shared', args)
            self.assertIn('--no-checkout', args)
            self.assertIn('core.hooksPath=/dev/null', args)
        self.assertFalse(any(args[0] in ('fetch', 'checkout', 'reset', 'push') for args in commands))

    def test_wrong_nearest_parent_refused_before_clone(self):
        self.fake.parent_discovery = True
        with self.assertRaisesRegex(ValueError, 'different source root'):
            self.prepare()
        self.assertFalse(any(args[0] == 'clone' for _, args in self.fake.calls))

    def test_wrong_shared_object_store_refused(self):
        self.fake.wrong_alternate = True
        with self.assertRaisesRegex(ValueError, 'object store'):
            self.prepare()

    def test_wrong_index_refused(self):
        self.fake.wrong_index = True
        with self.assertRaisesRegex(ValueError, 'index differs'):
            self.prepare()

    def test_export_bytes_must_match_the_declared_tree(self):
        (self.source / 'geotools/pom.xml').write_text('<unrelated/>\n')
        with self.assertRaisesRegex(ValueError, 'selected Git blob'):
            self.prepare()

    def test_export_mode_must_match_the_declared_tree(self):
        (self.source / 'geotools/pom.xml').chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'mode differ from selected Git blob'):
            self.prepare()

    def test_existing_or_nested_metadata_refused(self):
        for location in ('.git', 'nested/.git'):
            with self.subTest(location=location):
                p = self.source / 'geotools' / location
                p.mkdir(parents=True)
                with self.assertRaises(ValueError):
                    self.prepare()
                p.rmdir()

    def test_process_environment_excludes_inherited_controls(self):
        with mock.patch.dict(os.environ, {'GIT_DIR': '/unrelated', 'GIT_CONFIG_COUNT': '9',
                                         'GIT_CONFIG_PARAMETERS': 'hostile', 'LD_PRELOAD': '/unrelated'}):
            env = candidate.git_environment()
        self.assertNotIn('GIT_DIR', env)
        self.assertNotIn('GIT_CONFIG_COUNT', env)
        self.assertNotIn('GIT_CONFIG_PARAMETERS', env)
        self.assertNotIn('LD_PRELOAD', env)
        self.assertEqual('/dev/null', env['GIT_CONFIG_GLOBAL'])
        self.assertEqual('file', env['GIT_ALLOW_PROTOCOL'])

    def test_git_boundary_is_fixed_and_bounded(self):
        with mock.patch.object(candidate.subprocess, 'check_output', return_value=b'fixture') as call:
            candidate._git(self.source, 'rev-parse', 'HEAD')
        self.assertEqual('/usr/bin/git', call.call_args.args[0][0])
        self.assertEqual(120, call.call_args.kwargs['timeout'])
        self.assertEqual(candidate.git_environment(), call.call_args.kwargs['env'])


def jar(family, commit, *, revision=True, duplicate=None, properties=None, resource_text=None):
    buffer = io.BytesIO()
    key = 'Implementation-Version' if family == 'geowebcache' else 'Git-Revision'
    value = 'HEAD/' + commit if family == 'geowebcache' else commit
    manifest = 'Manifest-Version: 1.0\r\n'
    if revision:
        manifest += key + ': ' + value + '\r\n'
    if duplicate == 'attribute':
        manifest += key.lower() + ': ' + value + '\r\n'
    manifest += '\r\n'
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr('META-INF/MANIFEST.MF', manifest)
        if duplicate == 'member':
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                z.writestr('META-INF/MANIFEST.MF', manifest)
        for name, value in (properties or {}).items():
            z.writestr(name, 'build.revision = ' + value + '\n')
        for name, text in (resource_text or {}).items():
            z.writestr(name, text)
    return buffer.getvalue()


class ArtifactRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name)
        self.selected = selections()
        self.modules = {}
        prefixes = {'geotools': 'gt-', 'geoserver': 'gs-', 'geowebcache': 'gwc-'}
        for family, count in candidate.EMBEDDED_COUNTS.items():
            for i in range(count):
                name = prefixes[family] + 'fixture-' + str(i) + '.jar'
                props = None
                if family == 'geoserver' and i == 0:
                    name = 'gs-web-core-fixture.jar'
                    props = dict.fromkeys(candidate.REVISION_RESOURCES, self.selected[family]['commit'])
                self.modules[name] = (family, jar(family, self.selected[family]['commit'], properties=props))

    def materialize(self, *, war_revision=None, extra=None):
        built, embedded = [], []
        for name, (family, data) in self.modules.items():
            path = self.source / family / name[:-4] / 'target' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            built.append({'path': path.relative_to(self.source).as_posix(),
                          'sha256': candidate.sha(path), 'bytes': len(data)})
            embedded.append({'entry': 'WEB-INF/lib/' + name, 'sha256': candidate.sha(path)})
        if extra:
            name, data = extra
            family = 'geoserver' if name.startswith('gs-') else 'geotools'
            path = self.source / family / 'extra' / 'target' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            built.append({'path': path.relative_to(self.source).as_posix(),
                          'sha256': candidate.sha(path), 'bytes': len(data)})
        war = self.source / 'geoserver/web/target/geoserver.war'
        war.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(war, 'w') as z:
            commit = self.selected['geoserver']['commit'] if war_revision is None else war_revision
            z.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\nGit-Revision: ' + commit + '\n\n')
            for name, (_, data) in self.modules.items():
                z.writestr('WEB-INF/lib/' + name, data)
        built.append({'path': war.relative_to(self.source).as_posix(),
                      'sha256': candidate.sha(war), 'bytes': war.stat().st_size})
        return {'built': built, 'war': str(war), 'war_sha256': candidate.sha(war),
                'owned_embedded_jars': embedded}

    def verify(self, **kwargs):
        with mock.patch.object(candidate.subprocess, 'check_output', side_effect=AssertionError('native denied')):
            return candidate.verify_artifacts(self.source, self.materialize(**kwargs), self.selected)

    def test_all_primary_families_war_and23_localized_resources(self):
        result = self.verify()
        self.assertEqual(100, result['embedded_owned_jars'])
        self.assertEqual(23, result['localized_revision_resources'])
        self.assertEqual(candidate.EMBEDDED_COUNTS, result['embedded_counts'])

    def test_wrong_revision_in_each_family_and_war(self):
        for family in candidate.ROOTS:
            name = next(n for n, (f, _) in self.modules.items() if f == family)
            original = self.modules[name]
            self.modules[name] = (family, jar(family, 'd' * 40))
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, 'revision differs'):
                self.verify()
            self.modules[name] = original
        with self.assertRaisesRegex(ValueError, 'revision differs'):
            self.verify(war_revision='d' * 40)

    def test_missing_revision_on_primary_is_not_optional(self):
        name = 'gt-fixture-0.jar'
        self.modules[name] = ('geotools', jar('geotools', '1' * 40, revision=False))
        with self.assertRaisesRegex(ValueError, 'revision differs'):
            self.verify()

    def test_duplicate_archive_and_manifest_attributes_fail(self):
        name = 'gt-fixture-0.jar'
        for duplicate in ('member', 'attribute'):
            self.modules[name] = ('geotools', jar('geotools', '1' * 40, duplicate=duplicate))
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, '[Dd]uplicate|[Aa]mbiguous'):
                self.verify()

    def test_missing_and_wrong_localized_revision_fail(self):
        props = dict.fromkeys(candidate.REVISION_RESOURCES, self.selected['geoserver']['commit'])
        for wrong in (None, 'd' * 40, '${build.commit.id}'):
            p = copy.deepcopy(props)
            if wrong is None:
                del p['GeoServerApplication_fr.properties']
            else:
                p['GeoServerApplication_fr.properties'] = wrong
            self.modules['gs-web-core-fixture.jar'] = ('geoserver', jar('geoserver', '2' * 40, properties=p))
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, 'Localized'):
                self.verify()

    def test_packaged_resources_and_duplicate_basenames(self):
        props = {'org/geoserver/web/' + n: self.selected['geoserver']['commit']
                 for n in candidate.REVISION_RESOURCES}
        self.modules['gs-web-core-fixture.jar'] = ('geoserver', jar('geoserver', '2' * 40, properties=props))
        self.verify()
        props['GeoServerApplication.properties'] = self.selected['geoserver']['commit']
        self.modules['gs-web-core-fixture.jar'] = ('geoserver', jar('geoserver', '2' * 40, properties=props))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.verify()

    def test_non_core_translation_resources_need_no_revision(self):
        # The retained OAuth2 module packages these same translation basenames
        # without build.revision; only web-core supplies the version resources.
        props = {'GeoServerApplication.properties': 'OAuth2.title=OAuth2\n',
                 'GeoServerApplication_ko.properties': 'OAuth2.title=OAuth2\n'}
        self.modules['gs-fixture-1.jar'] = (
            'geoserver', jar('geoserver', '2' * 40, resource_text=props))
        self.assertEqual(100, self.verify()['embedded_owned_jars'])

    def test_present_optional_revision_must_be_unique_and_exact(self):
        name = 'org/geoserver/web/GeoServerApplication.properties'
        for text in ('build.revision = ' + 'd' * 40 + '\n',
                     'build.revision = ${build.commit.id}\n',
                     ('build.revision = ' + '2' * 40 + '\n') * 2):
            with self.subTest(text=text):
                self.modules['gs-fixture-1.jar'] = (
                    'geoserver', jar('geoserver', '2' * 40, resource_text={name: text}))
                with self.assertRaisesRegex(ValueError, 'Localized'):
                    self.verify()

    def test_optional_resource_duplicate_basenames_still_fail(self):
        props = {'GeoServerApplication.properties': 'title=OAuth2\n',
                 'org/geoserver/web/GeoServerApplication.properties': 'title=OAuth2\n'}
        self.modules['gs-fixture-1.jar'] = (
            'geoserver', jar('geoserver', '2' * 40, resource_text=props))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.verify()

    def test_core_translation_only_or_partial_revision_resources_fail(self):
        for missing in (set(candidate.REVISION_RESOURCES), {'GeoServerApplication_ko.properties'}):
            props = {n: ('title=GeoServer\n' if n in missing else
                         'build.revision = ' + '2' * 40 + '\n')
                     for n in candidate.REVISION_RESOURCES}
            self.modules['gs-web-core-fixture.jar'] = (
                'geoserver', jar('geoserver', '2' * 40, resource_text=props))
            with self.subTest(missing=len(missing)), self.assertRaisesRegex(ValueError, 'Localized'):
                self.verify()

    def test_unembedded_main_core_also_requires_all_revision_resources(self):
        # A second main version in the built inventory must be checked even if
        # the selected WAR embeds the other, fully valid core module.
        for props in ({}, {'GeoServerApplication.properties': '2' * 40}):
            with self.subTest(resources=len(props)), self.assertRaisesRegex(ValueError, 'Localized'):
                self.verify(extra=('gs-web-core-extra.jar',
                                   jar('geoserver', '2' * 40, properties=props)))

    def test_core_duplicate_revision_still_fails(self):
        props = dict.fromkeys(candidate.REVISION_RESOURCES, 'build.revision = ' + '2' * 40 + '\n')
        props['GeoServerApplication.properties'] *= 2
        self.modules['gs-web-core-fixture.jar'] = (
            'geoserver', jar('geoserver', '2' * 40, resource_text=props))
        with self.assertRaisesRegex(ValueError, 'Localized'):
            self.verify()

    def test_core_classifiers_are_not_required_version_resource_sets(self):
        # Test resources are translations, while source resources intentionally
        # retain Maven placeholders. Neither classifier is the built main JAR.
        for classifier, text in (
                ('tests', 'test.translation=value\n'),
                ('sources', 'build.revision = @build.revision@\n'),
                ('test-sources', 'build.revision = @build.revision@\n')):
            with self.subTest(classifier=classifier):
                name = 'gs-web-core-extra-' + classifier + '.jar'
                try:
                    self.verify(extra=(name, jar('geoserver', '2' * 40, resource_text={
                        'GeoServerApplication.properties': text})))
                finally:
                    (self.source / 'geoserver/extra/target' / name).unlink(missing_ok=True)

    def test_optional_source_manifest_absence_but_present_wrong_rejected(self):
        self.verify(extra=('gt-extra-sources.jar', jar('geotools', '1' * 40, revision=False)))
        with self.assertRaisesRegex(ValueError, 'revision differs'):
            self.verify(extra=('gt-extra-sources.jar', jar('geotools', 'd' * 40)))

    def test_changed_or_omitted_built_inventory_cannot_pass(self):
        artifacts = self.materialize()
        for change in ('omit', 'hash', 'duplicate', 'reported'):
            altered = copy.deepcopy(artifacts)
            if change == 'omit':
                altered['built'].pop(0)
            elif change == 'hash':
                altered['built'][0]['sha256'] = 'a' * 64
            elif change == 'duplicate':
                altered['built'].append(altered['built'][0])
            else:
                altered['owned_embedded_jars'].pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                candidate.verify_artifacts(self.source, altered, self.selected)

    def test_missing_family_member_fails_fixed_membership(self):
        del self.modules['gwc-fixture-0.jar']
        with self.assertRaisesRegex(ValueError, 'membership'):
            self.verify()

    def test_manifest_continuation_is_unfolded_before_exact_comparison(self):
        data = jar('geowebcache', '3' * 40)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            text = z.read('META-INF/MANIFEST.MF').decode()
        text = text.replace('3' * 40, '3' * 20 + '\r\n ' + '3' * 20)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as z:
            z.writestr('META-INF/MANIFEST.MF', text)
        self.modules['gwc-fixture-0.jar'] = ('geowebcache', buffer.getvalue())
        self.verify()


if __name__ == '__main__':
    unittest.main()
