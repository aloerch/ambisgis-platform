# 03 — Geodatabase semantics and branch-style editing

PostgreSQL and PostGIS are source-owned, buildable AmbisGIS foundations. No dependency on a future upstream branch-versioning feature or upstream patch acceptance is permitted. Preserve their mature transaction/storage behavior initially while implementing domain semantics in the owned geodatabase module; allow justified engine changes subject to transaction, compatibility and recovery tests.

## 1. Purpose and definition

This subproject is the highest correctness-risk new component. PostgreSQL/PostGIS supplies storage, spatial types/indexes, transactions, and concurrency. PostgreSQL MVCC does **not** by itself supply persistent named workspaces, user-facing reconcile/post, conflict resolution, version permissions, or service-based edit governance. [S13–S14] Kart, GeoGig, and QGIS versioning demonstrate that open-source spatial version control exists; P0 must assess them before deciding how much to reuse. [S15–S17]

AmbisGIS branch editing is a defined **application workflow**, not an imitation of Esri's internal SDE tables. Users create a named branch from DEFAULT, edit privately or collaboratively, inspect changes, reconcile against DEFAULT, resolve conflicts, and post approved changes. The public Esri workflow informs requirements, but native correctness is independent of Esri protocol compatibility. [S20, S23]

V1 supports branches directly from DEFAULT, one organization per deployment, and a version group containing related layers in one managed geodatabase. Nested branches, disconnected replicas, cross-database atomic post, geodatabase engine impersonation, and Esri VersionManagementServer protocol support are separate future work.

## 2. Required invariants

1. **Isolation:** a branch reads its captured base plus its own accepted edits; later DEFAULT changes do not appear until an explicit reconcile is accepted.
2. **Stable identity:** a feature UUID identifies the same logical feature across branches, revisions and service overwrites. Geometry and array position are not identity.
3. **No lost updates:** stale branch heads or stale feature revisions cannot overwrite newer committed work.
4. **Atomic logical edit:** all supported operations in a version-group transaction succeed together or none change visible feature/attachment/relationship state.
5. **Atomic post:** an authorized, conflict-free candidate is revalidated and promoted to DEFAULT inside one database transaction, with audit and outbox events.
6. **No hidden bypass:** ordinary users, notebooks, GeoServer WFS-T, and direct QGIS database editing cannot mutate managed versioned tables.
7. **Reproducibility:** retained commits and snapshots reconstruct the declared feature state; history refers to an exact schema and rule revision.
8. **Safe retention:** no snapshot/revision/blob referenced by a live branch, retained history, publication or recovery checkpoint is garbage-collected.
9. **Constraint integrity:** domains, nullability, relationships, natural-key uniqueness and chosen rules hold in each committed branch state and again in the posted DEFAULT state.
10. **Crash integrity:** a client timeout cannot turn one idempotent request into two commits, and process failure cannot create a half-posted group.

An implementation that stores an `updated_at` column and chooses the latest row globally fails several of these invariants. So does keeping a database transaction open for the lifetime of a user's branch.

## 3. Storage design: correctness first

Use **typed per-dataset current-state tables**, immutable snapshot tables, and an append-only revision ledger. Do not store every feature attribute solely in an untyped JSON blob. Geometry remains a typed PostGIS column with an explicit SRID and Z/M policy. JSON is appropriate for request payloads, diffs, and extension metadata, not a replacement for relational constraints or spatial indexes.

V1 deliberately uses **eager, bounded branch snapshots**. At branch creation, capture a consistent DEFAULT state and materialize the branch's editable current state. This costs storage proportional to dataset size and branch count. That is an explicit initial tradeoff for simpler isolation and merge correctness. P0 measures representative sizes; quotas may restrict supported branch sizes until structural sharing or copy-on-write is proven. Do not advertise constant-cost branch creation.

The logical model is stable even if later storage uses shared immutable snapshots and deltas. Every optimization must pass the same reference and concurrency tests before replacing the initial implementation.

### Core entities

| Entity | Essential fields / purpose |
|---|---|
| `dataset` | UUID, managed name, geometry/CRS/type descriptor, active schema revision, dataset policy reference. |
| `schema_revision` | Immutable field/domain/subtype/relationship/rule definitions and canonical schema hash. |
| `version_group` | UUID, participating datasets, DEFAULT version, schema generation, constraint scope. |
| `version` | UUID, group, owner, visibility/editors, lifecycle state, base snapshot ID, head commit, optimistic revision. |
| `snapshot` | UUID, group, source version/head, schema generation, creation status, row counts/hashes, retention references. |
| `commit` | UUID, version, parent commit, actor, timestamp, request ID, schema generation, operation/reconcile/post provenance. |
| `feature_identity` | Dataset UUID + feature UUID + immutable integer ObjectID mapping; never recycled. |
| typed `current_*` tables | Composite identity `(version_id, feature_uuid)`, typed fields, geometry, last feature-revision token. |
| typed `snapshot_*` tables | `(snapshot_id, feature_uuid)`, typed feature payload; immutable after snapshot sealing. |
| `feature_revision` | Dataset, feature UUID, commit, operation, before/after references or full typed revision pointer, changed-field mask. |
| `relationship_definition` | Parent/child dataset and keys, cardinality, branch scope, delete policy, revision. |
| `attachment_reference` | Version/feature relationship to immutable blob hash, MIME/name/size, visibility, edit revision. |
| `reconcile_plan` | Source/base/target heads, schema/rule hashes, conflict list, candidate snapshot, resolution revision, status. |
| `idempotency_record` | Principal, operation scope, client key, canonical request hash, transaction result, retention. |
| `audit_event` / `outbox` | Immutable security/edit audit and reliable invalidation/publication events. |

Use UUID primary identity for native APIs. Assign ObjectIDs from a persistent per-dataset sequence/mapping, never `row_number()` or regenerated import order. Keep native JSON large-ID encoding safe. A compatibility profile that only supports 32-bit ObjectIDs must enforce that capacity rather than overflow or silently truncate. Global IDs supplied during import are validated for uniqueness and namespace policy.

## 4. Branch creation and lifecycle

Lifecycle: `creating -> active -> archived -> deletion_pending -> deleted`, with `creation_failed` and explicit recovery paths. Only `active` branches accept edits. Reconcile plans have their own statuses; a UI edit lease is not the database correctness mechanism.

Creation opens a bounded repeatable-read transaction that reads DEFAULT's head and all participating datasets at one consistent snapshot, under a schema-change exclusion mechanism. Populate an immutable base snapshot and branch current rows, validate counts/hashes/constraints, and publish the branch as active only after commit. A worker may do the copying, but must not commit partial tables then label the branch ready. For datasets too large for the bounded copy policy, fail preflight or use a separately proven chunked snapshot algorithm; do not fake consistency across different query times.

Data edits to DEFAULT may proceed during snapshot copying subject to PostgreSQL transaction semantics. Schema changes are serialized against creation. Source credentials and privileged database roles never leave the worker/service. Cancellation removes uncommitted work or marks committed staging for cleanup; it must not expose an incomplete branch.

Visibility: private owner-only, shared with selected editing groups, or read-visible to authorized organization members. These choices never grant access beyond the underlying dataset policy. DEFAULT posting is a distinct permission from ordinary branch editing.

Deletion is logical first. It refuses active operations and retained publication/history references unless the administrator resolves them. Quotas include current/snapshot/history rows, attachments, number of branches, and idle age. Archiving does not silently discard edit history.

## 5. Edit transaction algorithm

Each request supplies version-group ID, branch ID, expected branch head, an idempotency key, and operations with stable feature identity and expected feature revision for updates/deletes. Inserts may use a client-generated UUID. Patch omission means “leave unchanged”; explicit `null` means assign null where permitted. The API canonicalizes requests before hashing them.

Transaction sequence:

1. Authenticate and authorize operation, branch, dataset, fields and selected rows. Obtain a scoped transaction-level lock for the version head/group as required.
2. Look up the idempotency record. Same key and request hash returns the committed original result. Same key with different payload returns conflict. Uncommitted concurrent duplicate requests serialize.
3. Check expected branch head and relevant feature revisions. Return `409 STALE_BRANCH_HEAD` or per-feature revision conflict without applying changes. V1 may serialize commits per branch for simplicity; clients retry only after reloading and reconciling local intent.
4. Apply typed edits to the candidate branch state. Validate fields/domains/subtypes, geometry, ownership, relationship cardinality, natural keys, and request-size limits. Calculate only supported deterministic rule expressions.
5. Stage logical attachment references to previously scanned immutable blobs. Blob upload completion alone never makes an attachment visible. Cascading deletes follow an explicit dataset rule, not an implicit engine default.
6. Record feature revisions, one commit, editor tracking, idempotency result and outbox entries in the same transaction; advance branch head by compare-and-set.
7. Commit, then notify. If the response is lost, retry returns the stored result. A notification failure does not undo committed data, and a queue retry cannot reapply the edit.

V1 supports atomic requests **inside one version group/database**. A multi-geodatabase request is rejected or explicitly modeled as a non-atomic workflow; never claim rollback covers remote systems. No partial commit is represented as success.

## 6. Reconcile model and conflict semantics

For each logical feature, compare **B** (the branch's base snapshot), **O** (current branch state), and **T** (current DEFAULT target). Capture exact source and target heads, schema generation, rule revision and policy context. A reconcile job computes a candidate and conflict list without changing visible branch/DEFAULT data.

For one comparable field:

| Condition | Candidate |
|---|---|
| `O == B` | Take `T`: the branch did not change this value. |
| `T == B` | Take `O`: the target did not change this value. |
| `O == T` | Take the shared value. |
| Otherwise | Explicit conflict requiring resolution. |

Combine non-overlapping field changes automatically. Geometry is **one atomic field** in V1. Compare canonical geometry serialization with a defined byte order, SRID and dimensions; geometric equality in 2D is not sufficient to detect Z/M or precision changes. Do not merge vertex lists heuristically. Null and missing are different in patch interpretation; normalized full schema states remove ambiguity during reconcile.

Feature existence rules precede field comparison. Deletion on one side and unchanged feature on the other merges to deletion. Deletion versus an update conflicts. Independent inserts with different UUIDs are candidates for union but may violate a natural key or relationship constraint. Two different inserts with the same UUID conflict; do not field-merge independent identities. Identical concurrent inserts may coalesce only after payload/schema/attachment equality checks.

Attachments and relationships participate as first-class logical records. Removing an attachment while its descriptive metadata is edited is a conflict. Repointing a child and deleting its new parent must fail final relational validation even when no individual attribute appears conflicted. Validation errors caused by combined candidate changes are reported alongside explicit row conflicts.

The conflict UI shows base/branch/target attributes, a map overlay for geometry, actor/revision information, and safe choices: take branch, take target, or enter a validated replacement. “Prefer branch for all” is an explicit bulk decision requiring authorization and audit, never a default silent overwrite.

## 7. Accept reconcile and post are separate operations

The initial server route inventory is extended with `POST /api/v1/reconciles/{id}/accept`. This operation applies a fully resolved candidate to the **branch only**, after checking that source/target heads and schema/rules still match the plan. It updates the branch's base snapshot to captured target T, advances branch head, and records the accepted plan. DEFAULT remains unchanged. This allows users to inspect the reconciled result before promotion.

A convenience “Reconcile and post” action may orchestrate prepare/resolve/accept/post, but it cannot bypass conflicts or the checks below. The underlying operations remain explicit and auditable.

Post inputs include accepted reconcile ID/revision, expected branch head, expected target head, and idempotency key. Post requires a separate permission and optional review approval bound to those exact hashes. If the branch was edited after acceptance or DEFAULT advanced, the plan is stale and post returns `409 STALE_RECONCILE`. Users must regenerate/accept a current plan; no automatic destructive preference is chosen.

Post transaction:

- Acquire short-lived locks in a globally consistent order for source/target version heads and group metadata; enforce timeout and retry limits.
- Recheck policy, expected heads, schema/rule hashes, approval binding, and unresolved-conflict count.
- Apply the accepted delta against DEFAULT's current state. Revalidate constraints, deterministic calculations, domains, relationships, spatial validity and natural keys inside the transaction.
- Commit one DEFAULT promotion plus associated audit/outbox records. Refresh the branch checkpoint/base to the resulting DEFAULT snapshot, preserving history and stable feature identity. The branch remains active and clean unless the user chose archive-after-post.
- Publish revision/invalidation events only after commit. Render caches use committed revisions, so asynchronous cache maintenance cannot display a mixture of half-posted layers.

Seal the immutable candidate snapshot before the post transaction. When captured heads and schemas still match, its validated state can become the new branch base by reference; do not copy the entire version group while holding the target-head lock. Promotion work is the changed-row delta plus required constraint validation, whose cost must still be measured.

A crash before commit leaves neither head changed. A crash after commit but before response is resolved through the idempotency record. Deadlock/serialization retries rerun the whole bounded transaction and recheck heads. Never retry after replacing expected heads with current values automatically; that would erase the user's concurrency protection.

## 8. Rules, domains, relationships and schema evolution

The schema registry provides field aliases/descriptions, coded/range domains, subtype selectors/defaults, field editability, nullable/length/precision constraints, relationships, and a constrained expression language for calculations/validation. Begin with literal defaults, numeric/string expressions, selected date/UUID generation rules, field references and a small allow-listed spatial operation set. Server-generated actor/time values cannot be client-supplied. No arbitrary eval, SQL fragments, subprocesses or unrestricted Arcade/Python execution in rules.

Calculated values are recomputed/validated consistently after merge. Rule outputs and errors appear in analyzer/edit responses. Determinism includes time values captured once per transaction; external network lookups are asynchronous workflows, not hidden transaction rules.

A version group pins a schema generation. V1 blocks incompatible schema changes while active branches exist. Additive nullable fields may be supported only through an explicit all-branch migration with tested defaults/history behavior. Domain removal, geometry-type/SRID changes, shrinking strings, changing keys, and relationship changes require a migration plan. No arbitrary DDL from the web UI. Preserve old schema descriptors for retained historical reads.

Schema changes and data publication are separate lifecycles. A service overwrite cannot quietly delete a field used by active branches, dashboards, notebooks, or rules. The dependency analyzer reports blockers and supported migration paths.

## 9. Read, render and cache semantics

Native feature reads accept branch ID and optionally an immutable commit/snapshot reference. Branch selection does not grant authorization. Every query includes the correct branch/current or historical snapshot predicate. Cache keys include resource, branch, commit, schema/style revision, normalized query and authorization-policy scope. Default branch UUID alone is not a complete cache key because its head advances.

Initial branch visualization uses the authorized native feature API and client rendering. General WMS/tiles initially render DEFAULT or immutable published snapshots. Branch-aware server rendering requires a separate secure immutable projection adapter with a per-request capability tied to an authorized snapshot; do not interpolate arbitrary branch UUIDs into public SQL-view parameters. A branch WMS capability remains false until implemented and tested.

GeoServer/QGIS Server database roles receive only approved read projections. They do not own managed tables and cannot write versioned data. Direct SQL reads of DEFAULT may be offered to trusted analysts through read-only views with explicit policy limitations; there is no general direct-SQL branch edit capability. PostgreSQL RLS is defense in depth, not a replacement for service policy checks. Connection-pool session context must be set/reset within each transaction and never come from untrusted headers.

## 10. Retention, backup and performance

Retain live branch bases, accepted reconcile snapshots, published snapshots, required historical commits and all referenced blobs. Garbage collection uses explicit reference tracking and a grace period; dry-run reports precede deletion. Backup includes database state, schema migrations, snapshot/blob manifests, service revision registry and decryption-key recovery procedure. Test that restored branches reconcile/post correctly, not merely that PostgreSQL starts.

Benchmark eager snapshots with 100 thousand and 1 million feature fixtures, multi-layer groups, representative geometry/attribute sizes and 10 active branches before choosing production quotas. Track branch creation time, storage amplification, query p95, edit p95, reconcile cost per changed/full row, post lock duration, WAL volume and restore cost. These sizes are proposed test workloads, not validated capacity claims. If eager copies exceed agreed limits, implement shared immutable snapshots/delta indexing behind the same domain API and rerun all oracle tests.

## 11. Required tests

The included `tools/merge_reference.py` demonstrates only existence/field three-way logic; it deliberately does not claim SQL/geometry/relationship completeness. Production tests add a pure state interpreter, randomized operation sequences, and a real PostgreSQL implementation compared after every commit.

Mandatory cases: unchanged branch/changed target; changed branch/unchanged target; equal concurrent change; disjoint fields; same field conflict; delete/update; both delete; duplicate UUID insert; natural-key collision across different UUIDs; geometry/Z/M conflict; child-parent conflict; attachment changes; stale edit head; concurrent reconcile/post; two posts to DEFAULT; target changes during review; schema/rules change; owner loses permission before post; duplicate request with changed payload; worker crash at every transactional boundary; cache invalidation lag; branch deletion with retained snapshots; recovery followed by successful post.

No versioning milestone passes on mocked database tests alone. A release requires independent review of migrations/locking/authorization and a recorded crash/recovery test run.
