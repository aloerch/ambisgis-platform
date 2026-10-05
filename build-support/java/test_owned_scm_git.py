"""Real local Git regression for exports inside an unrelated parent repository."""
from pathlib import Path
import tempfile
import unittest

import owned_scm
import owned_successor


class RealSourceMetadataTests(unittest.TestCase):
    def test_each_export_uses_selected_owned_root_not_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / 'unrelated-parent'
            parent.mkdir()
            owned_scm._git(parent, 'init', '--quiet')
            (parent / 'unrelated.txt').write_text('Unrelated fixture repository\n')
            owned_scm._git(parent, 'add', 'unrelated.txt')
            owned_scm._git(parent, '-c', 'user.name=Fixture',
                           '-c', 'user.email=fixture@example.invalid',
                           'commit', '--quiet', '-m', 'Unrelated parent fixture')
            parent_head = owned_scm._text(parent, 'rev-parse', 'HEAD')
            source = parent / 'exported'
            source.mkdir()
            repos, selected, before = {}, {}, {}
            for family in owned_scm.ROOTS:
                repo = root / ('retained-' + family)
                repo.mkdir()
                owned_scm._git(repo, 'init', '--quiet')
                maven = repo / owned_scm.MAVEN_ROOTS[family]
                maven.mkdir(parents=True, exist_ok=True)
                (maven / 'pom.xml').write_text('<project>' + family + '</project>\n')
                # Exact export must retain files even if Git archive would omit them.
                (repo / '.gitattributes').write_text('kept.txt export-ignore\n')
                (repo / 'kept.txt').write_text('Explicit owned source fixture\n')
                owned_scm._git(repo, 'add', '.')
                owned_scm._git(repo, '-c', 'user.name=Fixture',
                               '-c', 'user.email=fixture@example.invalid',
                               'commit', '--quiet', '-m', 'Selected ' + family)
                head = owned_scm._text(repo, 'rev-parse', 'HEAD')
                tree = owned_scm._text(repo, 'rev-parse', 'HEAD^{tree}')
                repos[family] = repo
                selected[family] = {'commit': head, 'tree': tree}
                owned_successor.export_owned(repo, selected[family], source / family)
                before[family] = owned_scm._source_inventory(source / family)
                self.assertEqual(parent_head, owned_scm._text(source / family, 'rev-parse', 'HEAD'))
            result = owned_scm.prepare(source, repos, selected)
            self.assertEqual(set(owned_scm.ROOTS), set(result['roots']))
            for family in owned_scm.ROOTS:
                exported = source / family
                self.assertEqual(selected[family]['commit'],
                                 owned_scm._text(exported, 'rev-parse', 'HEAD'))
                self.assertEqual(str(exported),
                                 owned_scm._text(exported / owned_scm.MAVEN_ROOTS[family],
                                                 'rev-parse', '--show-toplevel'))
                self.assertEqual(before[family], owned_scm._source_inventory(exported))
                self.assertEqual(selected[family]['commit'],
                                 owned_scm._text(repos[family], 'rev-parse', 'HEAD'))
                self.assertFalse(owned_scm._text(repos[family], 'status', '--porcelain'))
                self.assertTrue((exported / 'kept.txt').is_file())
            self.assertEqual(parent_head, owned_scm._text(parent, 'rev-parse', 'HEAD'))


if __name__ == '__main__':
    unittest.main()
