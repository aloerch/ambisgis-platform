import unittest
from native_reports import parse_report

class NativeReportTests(unittest.TestCase):
    def test_actual_records_required_not_claimed_suite_count(self):
        with self.assertRaisesRegex(ValueError,'disagree'):
            parse_report(b'<testsuite name="x" tests="5" failures="0" errors="0" skipped="0"/>','count-only')
    def test_child_failure_cannot_be_hidden_by_zero_counter(self):
        with self.assertRaisesRegex(ValueError,'disagree'):
            parse_report(b'<testsuite name="x" tests="1" failures="0" errors="0" skipped="0"><testcase classname="x" name="broken"><failure/></testcase></testsuite>','masked-failure')
    def test_counts_and_case_identities_are_required(self):
        for xml in (b'<testsuite name="x" tests="0"/>',b'<testsuite name="x" tests="1" failures="0" errors="0" skipped="0"><testcase name="missing-class"/></testsuite>'):
            with self.subTest(xml=xml),self.assertRaises(ValueError): parse_report(xml,'bad')
    def test_suite_level_failure_cannot_be_ignored(self):
        with self.assertRaisesRegex(ValueError,'suite outcome'):
            parse_report(b'<testsuite name="x" tests="1" failures="0" errors="0" skipped="0"><testcase classname="x" name="pass"/><failure/></testsuite>','suite-failure')
    def test_flaky_retry_is_not_a_pass(self):
        with self.assertRaisesRegex(ValueError,'retries'):
            parse_report(b'<testsuite name="x" tests="1" failures="0" errors="0" skipped="0"><testcase classname="x" name="retried"><flakyFailure/></testcase></testsuite>','flaky')
    def test_encoding_aware_dtd_guard_retained_for_reports(self):
        from audit import AuditError
        for encoding in ('utf-8','utf-16','utf-32'):
            with self.subTest(encoding=encoding),self.assertRaises(AuditError):
                parse_report('<!DOCTYPE testsuite [<!ENTITY name "expanded">]><testsuite name="&name;" tests="0" failures="0" errors="0" skipped="0"/>'.encode(encoding),'encoded')
    def test_pass_skip_and_class_rule_error_accounted(self):
        xml=b'<testsuite name="x" tests="3" failures="0" errors="1" skipped="1"><testcase classname="x" name="passed"/><testcase classname="x" name="skipped"><skipped/></testcase><testcase classname="x" name=""><error/></testcase></testsuite>'
        _,counts=parse_report(xml,'valid')
        self.assertEqual(counts,{'tests':3,'failures':0,'errors':1,'skipped':1})

if __name__=='__main__':unittest.main()
