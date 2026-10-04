# Transport sequence metadata

The owned initializer uses the transport owner with Hibernate schema `update`;
serving uses the transport reader with schema `validate`. Retained Hibernate
5.6.15.Final `PostgisDialect` inherits the query
`select * from information_schema.sequences`. The selected PostgreSQL source
shows a sequence in that view to its owner or a role with SELECT, UPDATE or
USAGE. The previous bootstrap granted no sequence privilege to the reader, so
an existing owner-created sequence could be invisible to validation.

The reader now receives SELECT on future sequences created by
`ambisgis_transport_owner` in `public`. Bootstrap also grants SELECT on existing
sequences filtered by that exact owner, schema and relation kind, quoting both
identifier components. It does not grant on every sequence in the schema.
Existing-state checks run before mutation and again afterward. Object/default
ACL checks allow only that SELECT and still reject USAGE, UPDATE, grant options,
PUBLIC grants, other owners/schemas and other serving roles. Catalog sequence
USAGE/SELECT and table permissions are unchanged. SELECT permits sequence value
and metadata reads; PostgreSQL still requires USAGE or UPDATE for `nextval`, and
UPDATE for `setval`. No reader DDL, transport writes or privilege delegation is
authorized.

Seven inert tests check emitted policy and bootstrap ordering. They do not
execute PostgreSQL. The extended `deploy/development/database_probe.py` uses
only its fresh marked owned cluster with a private Unix socket and no TCP
listener. It exercises the actual Hibernate lookup, fresh/default and existing
sequence visibility, quoted identifiers, unrelated owner/schema exclusion,
unchanged sequence state, denied advancement/DDL/delegation, and poisoned
object/default ACL rejection before mutation. Its existing cases and owned
cluster cleanup remain required. Actual baseline/fixed execution is a separate
integrator step; neither these source checks nor that fixture constitutes full
installation acceptance or retrospectively proves the exact state of attempt016.
