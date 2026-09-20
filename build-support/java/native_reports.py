"""Strict native report validation shared by receipts and case comparisons."""
from collections import Counter
import re
from audit import parse_xml


def parse_report(data, label):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError('native report exceeds bounded parser size')
    suite = parse_xml(data, label)
    if suite.tag != 'testsuite' or not suite.get('name'):
        raise ValueError('native report must identify a testsuite')
    if any(child.tag not in ('properties', 'testcase', 'system-out', 'system-err') for child in suite):
        raise ValueError('unsupported native suite outcome or nested suite')
    counts = {}
    for key in ('tests', 'failures', 'errors', 'skipped'):
        value = suite.get(key)
        if value is None or not re.fullmatch(r'[0-9]+', value):
            raise ValueError('native report count is missing or malformed')
        counts[key] = int(value)
    outcomes = Counter()
    cases = suite.findall('testcase')
    for case in cases:
        if not case.get('classname') or case.get('name') is None:
            raise ValueError('native testcase identity is missing')
        if any(child.tag not in ('failure', 'error', 'skipped', 'system-out', 'system-err') for child in case):
            raise ValueError('unsupported native outcome, including retries/flakes')
        markers = [child.tag for child in case if child.tag in ('failure', 'error', 'skipped')]
        if len(markers) > 1:
            raise ValueError('contradictory native testcase outcomes')
        outcome = markers[0] if markers else 'passed'
        if not case.get('name') and outcome != 'error':
            raise ValueError('empty testcase name is only valid for class-rule error')
        outcomes[outcome] += 1
    actual = {'tests': len(cases), 'failures': outcomes['failure'],
              'errors': outcomes['error'], 'skipped': outcomes['skipped']}
    if counts != actual:
        raise ValueError('native report counters disagree with testcase outcomes')
    return suite, counts
