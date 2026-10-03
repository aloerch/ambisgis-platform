import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from koop_runtime_inputs import corpus_binding, digest, verify_blob


class RuntimeInputGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = self.root / 'addresses.ndjson'
        self.payload.write_bytes(b'{"synthetic":true}\n')
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_text(json.dumps({'addresses': 1, 'files': {'addresses.ndjson': {
            'sha256': digest(self.payload), 'bytes': self.payload.stat().st_size}}}))
        self.selected = digest(self.manifest)

    def test_changed_payload_rejected_before_execution(self):
        corpus_binding(self.root, self.selected)
        self.payload.write_bytes(b'{"synthetic":false}\n')
        with self.assertRaisesRegex(ValueError, 'payload identity'): corpus_binding(self.root, self.selected)

    def test_missing_payload_rejected_before_execution(self):
        self.payload.unlink()
        with self.assertRaisesRegex(ValueError, 'missing/nonregular'): corpus_binding(self.root, self.selected)

    def test_relabelled_manifest_rejected(self):
        self.manifest.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'manifest identity'): corpus_binding(self.root, self.selected)

    def test_contract_blob_changed_or_missing(self):
        original = self.payload.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(original)).encode() + b'\0' + original).hexdigest()
        verify_blob(self.payload, blob)
        self.payload.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'reviewed checkpoint'): verify_blob(self.payload, blob)
        self.payload.unlink()
        with self.assertRaisesRegex(ValueError, 'missing/nonregular'): verify_blob(self.payload, blob)
