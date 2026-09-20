import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from combined_logging_probe import inspect_war, REQUIRED, WATCHED


class PackagedLoggingInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def war(self, extra=None, omit=None):
        known = {}
        with zipfile.ZipFile(self.root / 'candidate.war', 'w') as war:
            for name in REQUIRED:
                payload = io.BytesIO()
                with zipfile.ZipFile(payload, 'w') as jar:
                    jar.writestr(WATCHED[0], ('class fixture for ' + name).encode())
                data = payload.getvalue()
                known[name] = {hashlib.sha256(data).hexdigest()}
                if name != omit:
                    war.writestr('WEB-INF/lib/' + name, data)
            for name, content in (extra or {}).items():
                war.writestr(name, content)
        return known

    def test_retains_all_selected_components_and_detects_api_definitions(self):
        hashes = self.war(extra={'data/security/users.xml': b'inert inherited fixture'})
        result = inspect_war(self.root / 'candidate.war', hashes, self.root / 'lib')
        self.assertEqual(len(result['libraries']), len(REQUIRED))
        self.assertEqual(len(result['logging_resources'][WATCHED[0]]), len(REQUIRED))
        self.assertFalse((self.root / 'data').exists())

    def test_missing_selected_capability_refused(self):
        hashes = self.war(omit=REQUIRED[1])
        with self.assertRaisesRegex(ValueError, 'selected capabilities missing'):
            inspect_war(self.root / 'candidate.war', hashes, self.root / 'lib')

    def test_unknown_artifact_bytes_refused(self):
        hashes = self.war(extra={'WEB-INF/lib/unknown.jar': b'untracked'})
        with self.assertRaisesRegex(ValueError, 'absent from verified'):
            inspect_war(self.root / 'candidate.war', hashes, self.root / 'lib')

    def test_path_traversal_refused_even_in_inert_members(self):
        hashes = self.war(extra={'../outside': b'invalid'})
        with self.assertRaisesRegex(ValueError, 'unsafe WAR'):
            inspect_war(self.root / 'candidate.war', hashes, self.root / 'lib')

    def test_nested_library_refused(self):
        hashes = self.war(extra={'WEB-INF/lib/extra/nested.jar': b'invalid'})
        with self.assertRaisesRegex(ValueError, 'nested library'):
            inspect_war(self.root / 'candidate.war', hashes, self.root / 'lib')

    def test_known_digest_cannot_impersonate_another_artifact_filename(self):
        known = self.war()
        # The WAR's first digest is known, but belongs to a different identity.
        known[REQUIRED[0]] = known[REQUIRED[1]]
        with self.assertRaisesRegex(ValueError, 'absent from verified'):
            inspect_war(self.root / 'candidate.war', known, self.root / 'lib')

    def test_unaccounted_webinf_classes_refused(self):
        known = self.war(extra={'WEB-INF/classes/application.properties': b'unaccounted'})
        with self.assertRaisesRegex(ValueError, 'outside the bounded library classpath'):
            inspect_war(self.root / 'candidate.war', known, self.root / 'lib')


if __name__ == '__main__':
    unittest.main()
