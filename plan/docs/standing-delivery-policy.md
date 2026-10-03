# Standing delivery policy — 2026-10-02

## Verified authority and precedence

The controlling authorization is the [unaltered owner-supplied Codex task](../authorizations/2026-10-02-standing-delegation.md), SHA256 `40d4bac51de35df99aa81f7c16db45f54644145272ce0a5f424aca208f38c402`, supplied on 2026-10-02 America/Los_Angeles in thread `01a1001c-60c3-7680-a640-54a47bbe6be7`. The GitHub principal was independently verified as `aloerch` (ID `15285626`), platform repository ID `1376927351`. This provenance is an automation record of the Codex task, not an owner-authored GitHub comment or review submission.

Owner task sections 2 and 5 explicitly delegate routine engineering, independent automated review, eligible merges, tracking and continuation, including this workflow-conversion PR. They explicitly direct updates to root/plan agent instructions. Within that authority this policy supersedes older process-only owner-review and continuation stops, including the former FND-07-only boundary. It does not supersede platform/tool restrictions, product acceptance, rights obligations or excluded actions. Historical receipts, manifests and approvals remain unchanged and mean exactly what they originally recorded. FND-02 stays accepted/Merged.

## Unchanged scope and boundaries

Deliver all R01–R24 and applicable P0–P7 acceptance, not merely P1. Use only the verified fifteen repositories and existing Project `PVT_kwHOAOk9es4Bj_k-` (#2). Preserve canonical catalog/policy, geodatabase, registry and configuration authorities, owned sources/build inputs and independent repair. The [requirements matrix](delivery-requirements-matrix.md) records implementation and remaining real tests.

No unrelated repositories, allow-list expansion, replacement hosting, force push, history/release/repository deletion, private/employer data, upstream contact, purchases, credentials/scopes installation or production changes. No commercial launch, new legal commitments, rights waiver, invented trademark clearance or unavailable signing identity. Disposable test databases may be reset only after verifying job ownership and absence of user data. Blocking vulnerabilities, integrity failures and unresolved material redistribution issues remain blockers. Human-subject usability and manual assistive-technology evaluation remain human-only; unperformed tests never pass.

## Execution and review

Select work from live dependency evidence; read/claim the issue and use a separate branch/worktree. One integrator owns shared contracts, migrations and mutations. Preserve human discussion, assignments, Project IDs/views/archive decisions and live progress. Define failing acceptance tests; implement; run actual relevant tests; inspect the diff. Obtain a separate-context review of the final diff and evidence. Shared-account agents are not distinct GitHub approvers.

Bind tests/review to repo, base/head, changed locks and actual commands. Missing/failing checks, stale evidence, material findings, unexpected source/rights changes, secrets, destructive or out-of-scope changes fail closed. Base/head movement requires revalidation. A label, model-written PASS or unrelated tests cannot authorize a merge. Gate/tests/workflow changes need explicit independent scrutiny against previous acceptance; a change may not weaken its own merge gate. For bootstrap use external integrator policy and separate-context review; thereafter run the gate from current base. CI/package checks are not GIS acceptance.

Only after the same gates pass may an eligible owner-controlled PR merge normally at the exact tested/reviewed head. Prefer auto-merge with required checks. Never administrator bypass, direct-to-main implementation, dismissal of legitimate findings or arbitrary outside-contributor auto-merges. Verify remote merge and integrated smoke tests, reconcile evidence and continue.

Settings authorization is limited to PR auto-merge, proven exact required checks and removing conflicting routine mandatory-human-review rules. Preserve unrelated controls/history protections and record before/after. Audit workflows, triggers, actions/inputs, permissions and publication before enabling. Build jobs have no merge/Project/signing credentials; never enable inherited workflows wholesale. Missing permissions do not permit scope escalation.

## Exact initial publications and later acceptance

The owner task section 4 authorizes only the exact GeoTools `3363c3d4ae8adfe3ed2024c27f92ec63855093be` / tree `ebb65f687763ce40445eb02f6ce710dc1eaa1e00` and QGIS `86af40542b219b0da6df1a43914413443330c0c0` / tree `84ea1b18fdf5721819fee34fe06cdef7ea82afdc` successors and destinations in the unchanged [PR #71 proposal](../verification/canonical-and-publication-repairs/next-source-publication.json). Verify principal, IDs, integrity, settings and destinations freshly. Create absent refs only, exact values are no-ops, other values are collisions; preserve existing refs/defaults/disabled Actions. Independently recover owned remote objects, verify notices/boundaries and replay without mutation.

QGIS acceptance covers the parentless snapshot's reachable source with exactly 1,130 exclusions and all 265 ColorBrewer palettes. It does not certify/purge/change other public refs or fork-network content. Preserve original source/manifest/receipts, add linked successor records and rebuild under new identities; old binaries never become new-source builds. FND-07 acceptance and subsequent FND-08 work are delegated when unchanged criteria actually pass. Later reviewed engineering may advance product branches normally.

Compliant project-owned experimental/MVP prereleases are authorized only after distribution/technical gates, with corresponding source, notices, SBOM/manifests/checksums and exact-byte verification. Download the candidate and repeat clean installation/smoke tests. Unsigned evaluations are labeled accurately and do not pass mandatory signing gates. Production deployment remains excluded.

## Continuation and stop

The actual runner is the existing Codex native-goal thread `01a1001c-60c3-7680-a640-54a47bbe6be7`, integrator `/root`, maximum three delegated workers plus integrator. Native continuation is active; no recursive supervisor or new service is installed. Installed `codex-cli 0.160.0`, supported `codex exec resume <SESSION_ID>` and existing ChatGPT login were inspected. Host tools use the existing `flatpak-spawn --host` bridge; credentials are never copied.

The owner can revoke/stop in this thread or pause/clear the native goal. Honor platform limits, quota and interruption. Save a concise ledger and reconcile live/local state on resume. Use one integration lock, bounded retries/backoff and readback after ambiguous writes. Checkpoint truthfully if continuation is unavailable; do not imply that a saved checkpoint is a running process. Continue independent safe work through external gates, and batch only genuine owner setup/decision requests. Delegation ends at scoped MVP delivery or revocation.

The shared integration state directory on this runner is `/home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/integration`. All foreground remote-write commands use this same guard (after external gate verification where required):

```sh
python3 plan/tools/delivery_runtime.py --state-dir /home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/integration run -- COMMAND ARGUMENTS
python3 plan/tools/delivery_runtime.py --state-dir /home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/integration status
python3 plan/tools/delivery_runtime.py --state-dir /home/revelberry/Projects/AmbisGIS/build-worktrees/delivery-control/integration stop
```

The stop command is safe to repeat and prevents the next guarded action; it deliberately lets an active migration finish. STOP remains until a verified owner resume instruction; there is no automatic clear. Use native goal stop/revocation to halt the agent effort. A crashed wrapper's foreground child retains the lock. After an interrupted/unsuccessful action, inspect the checkpoint and actual remote effects, then explicitly pass `run --reconciled-run-id EXACT_PREVIOUS_UUID -- COMMAND`. The acknowledgment is a record of integrator readback, not machine proof of remote state. Prior checkpoints are preserved before advancing; no ambiguous command is automatically replayed.
