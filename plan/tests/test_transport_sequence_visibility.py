"""Inert bootstrap emission/order guards; PostgreSQL semantics need the real probe."""
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/development'))
from ambisgis_development import database


class SQLRecorder:
    def __init__(self, bad_audit=None):
        self.calls = []
        self.audits = 0
        self.bad_audit = bad_audit

    def __call__(self, statement, password, *, database='postgres'):
        self.calls.append((database, statement))
        if statement.startswith('WITH serving'):
            self.audits += 1
            return '1' if self.audits == self.bad_audit else '0'
        if statement.startswith('SELECT pg_get_userbyid(datdba)'):
            return 'ambisgis_transport_owner' if 'ambisgis_transport' in statement else 'ambisgis_catalog_owner'
        if statement.startswith('SELECT extversion'): return '3.5.7'
        if statement.startswith('SELECT count(*) FROM pg_database'): return '1'
        if statement.startswith('SELECT count(*) FROM pg_roles') and ' AND ' not in statement: return '1'
        return '0'


class TransportSequenceVisibility(unittest.TestCase):
    def bootstrap(self, recorder=None):
        recorder = recorder or SQLRecorder()
        with patch.object(database, 'sql', recorder):
            database.bootstrap({}, {'database_admin': 'inert'})
        return recorder

    def test_future_transport_sequences_get_select_only_for_owned_public_schema(self):
        calls = self.bootstrap().calls
        sql = '\n'.join(s for db, s in calls if db == 'ambisgis_transport')
        self.assertRegex(sql, r'ALTER DEFAULT PRIVILEGES FOR ROLE ambisgis_transport_owner IN SCHEMA public\s+GRANT SELECT ON SEQUENCES TO ambisgis_transport_reader;')
        self.assertNotRegex(sql, r'GRANT (?:USAGE|UPDATE|ALL)[^;]*ON SEQUENCES')

    def test_existing_backfill_filters_owner_schema_kind_and_quotes_identifiers(self):
        calls = self.bootstrap().calls
        blocks = [s for db, s in calls if db == 'ambisgis_transport' and 'DO $transport_sequences$' in s]
        self.assertEqual(len(blocks), 1)
        sql = blocks[0]
        for token in ("c.relkind='S'", "n.nspname='public'", "c.relowner='ambisgis_transport_owner'::regrole",
                      "format('GRANT SELECT ON SEQUENCE %I.%I TO ambisgis_transport_reader'"):
            self.assertIn(token, sql)
        self.assertNotIn('ALL SEQUENCES', sql)

    def test_transport_object_audit_allows_only_matching_read_privilege(self):
        sql = database.privilege_audit('ambisgis_transport')
        sequence = sql.split("UNION ALL SELECT 'sequence:'", 1)[1].split("UNION ALL SELECT 'function:'", 1)[0]
        for token in ("r.rolname='ambisgis_transport_reader'", "rolname='ambisgis_transport_owner'",
                      "c.nspname='public'", "p.priv IN ('SELECT')", "p.priv||' WITH GRANT OPTION'"):
            self.assertIn(token, sequence)
        self.assertIn("ARRAY['USAGE','SELECT','UPDATE']", sequence)

    def test_transport_default_audit_does_not_authorize_usage_update_or_public(self):
        sql = database.privilege_audit('ambisgis_transport').split("UNION ALL SELECT 'default_acl:'", 1)[1]
        for token in ("a.grantee=r.oid", "r.rolname='ambisgis_transport_reader'", "rolname='ambisgis_transport_owner'",
                      "nspname='public'", "d.defaclobjtype='S' AND a.privilege_type IN ('SELECT')", 'a.is_grantable'):
            self.assertIn(token, sql)

    def test_catalog_sequence_usage_select_and_table_dml_are_preserved(self):
        sql = database.privilege_audit('ambisgis_catalog')
        self.assertIn("p.priv IN ('USAGE','SELECT')", sql)
        self.assertIn("a.privilege_type IN ('USAGE','SELECT')", sql)
        self.assertIn("p.priv IN ('SELECT','INSERT','UPDATE','DELETE')", sql)
        self.assertNotIn("IN ('USAGE','SELECT','UPDATE')", sql)

    def test_existing_unsafe_privilege_rejected_before_any_mutation(self):
        recorder = SQLRecorder(bad_audit=1)
        with self.assertRaisesRegex(ValueError, 'unexpected effective object privileges'):
            self.bootstrap(recorder)
        self.assertTrue(recorder.calls)
        self.assertTrue(all(s.startswith(('SELECT', 'WITH')) for _, s in recorder.calls))

    def test_post_bootstrap_audit_remains_required(self):
        recorder = SQLRecorder(bad_audit=3)
        with self.assertRaisesRegex(ValueError, 'unexpected effective object privileges'):
            self.bootstrap(recorder)
        self.assertEqual(recorder.audits, 3)
        self.assertTrue(any('GRANT SELECT ON SEQUENCES' in s for _, s in recorder.calls))


if __name__ == '__main__': unittest.main()
