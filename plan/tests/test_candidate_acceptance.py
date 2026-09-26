"""Separate real decision linkage: immutable candidate and later gates stay intact."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('acceptance_candidate', Path(__file__).resolve().parents[1] / 'tools/validate_candidate.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class CandidateAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.record_path = self.root / m.ACCEPTANCE
        self.record = m.read_json(m.PLATFORM / m.ACCEPTANCE)
        for ref in [self.record['candidate'], self.record['comment'], self.record['merged_pr'],
                    self.record['replacement_inputs'], self.record['existing_combination_evidence']]:
            target = self.root / ref['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(m.PLATFORM / ref['path'], target)
        self.manifest = self.root / self.record['candidate']['path']
        self.document = m.read_json(self.manifest)
        self.write_record()

    def write_record(self):
        self.record_path.write_text(json.dumps(self.record))

    def check(self):
        return m.validate_acceptance(self.record_path, self.manifest, self.document, self.root)

    def rewrite_evidence(self, key, mutate):
        path = self.root / self.record[key]['path']
        value = m.read_json(path)
        mutate(value)
        path.write_text(json.dumps(value))
        self.record[key]['sha256'] = m.sha(path)
        self.write_record()

    def test_real_decision_accepts_only_development(self):
        result = self.check()
        self.assertTrue(result['owner_acceptance'])
        self.assertFalse(result['distribution_permission'])
        self.assertEqual(result['accepted_criteria'], ['C1', 'C2', 'C3', 'C4'])
        self.assertIn('FND-07', result['not_accepted'])
        self.assertIn('FND-08', result['not_accepted'])
        self.assertEqual(m.sha(self.manifest), m.ACCEPTED_MANIFEST_SHA256)
        self.assertIn('final owner candidate, capability and maintenance acceptance ungranted', self.document['status'])
        report = m.render_acceptance(result)
        self.assertIn('eligibility remains exit 2', report)

    def test_changed_manifest_bytes_reject_even_same_parsed_json(self):
        self.manifest.write_bytes(self.manifest.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'manifest hash mismatch'):
            self.check()

    def test_changed_document_rejected(self):
        self.document['roots'][0]['commit'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'document differs'):
            self.check()

    def test_different_owner_comment_cannot_replace_explicit_decision(self):
        self.rewrite_evidence('comment', lambda c: c.update(id=123))
        with self.assertRaisesRegex(ValueError, 'Wrong owner acceptance comment'):
            self.check()

    def test_same_account_agent_handoff_does_not_count_as_acceptance(self):
        self.rewrite_evidence('comment', lambda c: c.update(body='Agent handoff: PR merged and issue closed.'))
        body = m.read_json(self.root / self.record['comment']['path'])['body']
        self.record['comment']['body_sha256'] = m.hashlib.sha256(body.encode()).hexdigest()
        self.write_record()
        with self.assertRaisesRegex(ValueError, 'decision text changed'):
            self.check()

    def test_author_id_contradiction_rejected(self):
        self.rewrite_evidence('comment', lambda c: c['user'].update(id=1))
        with self.assertRaisesRegex(ValueError, 'Wrong owner acceptance author'):
            self.check()

    def test_wrong_merge_rejected(self):
        self.rewrite_evidence('merged_pr', lambda c: c.update(merge_commit_sha='0' * 40))
        with self.assertRaisesRegex(ValueError, 'head or merge mismatch'):
            self.check()

    def test_later_gate_cannot_be_granted(self):
        self.record['not_accepted'].remove('distribution')
        self.write_record()
        with self.assertRaisesRegex(ValueError, 'later gates changed'):
            self.check()

    def test_changed_replacement_bytes_rejected(self):
        (self.root / self.record['replacement_inputs']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Changed owner acceptance evidence'):
            self.check()

    def test_missing_comment_rejected(self):
        (self.root / self.record['comment']['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.check()

    def test_evidence_escape_rejected(self):
        self.record['comment']['path'] = '../owner-comment.json'
        self.write_record()
        with self.assertRaisesRegex(ValueError, 'Unsafe relative path'):
            self.check()

    def test_cli_reports_current_decision_but_eligibility_stays_closed(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        result = {'inventory': {'status': 'valid'}, 'selection': {'blockers': []},
                  'acceptance': {'owner_acceptance': False, 'distribution_permission': False}}
        args = [str(self.manifest), '--platform-root', str(self.root), '--workspace-root', str(self.root)]
        with patch.object(m, 'validate', side_effect=lambda *a: copy.deepcopy(result)):
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(m.main(args + ['--eligibility']), 2)
            actual = json.loads(output.getvalue())
            self.assertTrue(actual['acceptance']['owner_acceptance'])
            self.assertFalse(actual['acceptance']['distribution_permission'])
            self.assertEqual(actual['selection']['status'], 'selected-for-development')
            with redirect_stdout(StringIO()):
                self.assertEqual(m.main(args + ['--report']), 0)


if __name__ == '__main__':
    unittest.main()
