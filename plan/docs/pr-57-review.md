# PR #57 — source recovery and compatibility evidence review

Review only [PR #57](https://github.com/aloerch/ambisgis-platform/pull/57),
branch `fnd-02/java-source-compatibility`, target `ambisgis/main`.
Repository `aloerch/ambisgis-platform`: ID `1376927351`, node `R_kgDOUhI-dw`;
authenticated owner `aloerch`: ID `15285626`. FND-02 remains **In progress**.
The published PR summary and final verification receipt record the exact final
head/full Git tree. The tested Java subtree is
`d6ca199d12cb0e963748b5a6a58a8cca0e3c72dd`; implementation repairs are committed
through `c3c12251b61777df79d2ef1ddd8cfb8fdc108c16`.

## Actual prerequisites, target and remaining diff

Owner `aloerch` merged #54 at `8393fc46b9b979b05faa416f5998e0159ecd1e33`
on 2026-09-20T20:09:12Z, then #55 on 2026-09-20T20:50:29Z from reviewed head
`8eeb408f296b7c6152fae2ef5edef65161f674ac`. The latter merge/current main is
`bb3680802d7f7d5c500180ec12e66d32d81d0aa0`; its parents are the #54 merge and
the exact reviewed #55 head. Its tree is the reviewed #55 tree
`c7353aa55c9cd874ec8b98ad38e70839f5e50a3b`. Database #51, Jupyter #53 and
GOV-02 #52 merge commits are verified ancestors.

Normal merge `dc250cd854ae87bfb80657148efe937a69c381dc` has parents previous
#57 head `7d3063f89c20b5e028b0151a6648a79e4ef14a83` and actual current main.
Only root/plan STATUS conflicted; the resolution combines #57 native evidence
with merged #55/governance updates. It preserves all earlier evidence and commits.
The merge's remaining Java patch against main is byte-identical to the old patch
against #55's `9e1b2e1bca26d00b200a39f58a4a0890d43fca98`, SHA256
`30ad136c869235aec6ed88e31003589ab6e4481827e3ad18e1cc615529362154`.
All 96 original changed paths remained, without a checkpoint replay or omission.
#55's encoding-aware parser and its tests remain byte-identical to merged main.
#57 was explicitly retargeted to main after verification of the actual #55 merge.
These are ordinary dependent branches, not a managed stack.

The remaining scope is the 64-artifact source supplement, recovered-source probes,
bounded owned-source compilation/native runners, recorded EMF repair, private
GeoFence database fixture, verified GDAL staging, isolated logging witness,
ADR 004 and actual historical evidence. #56's separate importer regression and
tracking implementation are not included. No candidate source revision,
dependency/profile selection, fixture behavior or product capability changed
in this preparation.

## Two material engineering findings corrected

1. **Encoded POM declarations in the source supplement (P2).** Its separate
   ASCII scan allowed UTF-16 DTD/internal entity expansion despite #55's fix.
   The source-accounting path now uses the existing encoding-aware parser as a
   validity guard, preserving original declaration text/scope. Two new end-to-end
   tests cover internal/empty/external declarations and benign non-ASCII licenses
   across six encodings. The expected failing run is retained. Independent repair
   `fc376c13deecae500c312775a4bce6e068a1cb68` is integrated as `c3c12251`.
2. **Success after source-verification failure (P1).** The compatibility runner
   could keep result exit zero if hashing original source raised after Maven
   succeeded. It now always fails the receipt on that exception while retaining
   Maven's actual exit and the original error. The regression reproduces a
   PermissionError, confirms the failed final receipt, and retains its red/green
   runs. Independent repair `71e747401bc249420fe547caff6e518c9eb274db` is
   integrated as `4a78597`.

[Source review](../verification/pr57-review/source-review.txt) and
[compatibility review](../verification/pr57-review/compatibility-review.txt)
found no additional material issue in their bounded scopes. These are engineering
assessments, not human approval or final security/license review.

## Checks actually run

- **218 Java tooling tests, 175 package tests, and all four strict schema/example
  checks passed, with no failures/errors/skips.** Tests were discovered from the
  documented root/plan directories. Package/schema checks use the verified
  Python 3.13.15/jsonschema 4.26.0 validation environment.
- **Real 64-artifact source accounting:** both runs exit **2**, explicitly retaining
  12 unresolved and four partial cases. The corrected report is byte-identical
  to the before report, SHA256
  `6a13f947af9b42750f50e030beaf1674cf06eac2203756ed4e3312bc43aa8155`.
  No retained declaration or disposition changed.
- **Fresh selected native XML resolver probe:** 12 passed, zero failures/errors/
  skips, Maven and receipt exit 0. It uses 9,214 retained Maven inputs, fresh source/
  repository copies, actual IPv4/IPv6 socket denial, completed unchanged-source
  checks and verified toolchain. Result SHA256
  `25b8a12860c1b9618d89f6b594a6a0c2f1a213468f9b3983c49989bf750f8699`.
  GeoServer extension-profile warnings in this selected GeoTools reactor remain
  in the log; this is not a full extension-profile or broad XML run.
- Frozen custody verified: resolution 34,118 files; source supplement 337;
  parent research 93; additional research 115; compatibility 33,580. Original
  manifests and bytes are unchanged. Installed toolchain verification passed
  for 342 files, 208 symlinks and 103 directories. Signature trust and complete
  toolchain bootstrap remain open.
- A read-only historical audit verified 22 receipt pairs and 533 native XML
  report hashes/counts. All six successful Maven/native runs explicitly
  completed original-source checks without body/finalization/shutdown errors.
  This was evidence verification, not native reexecution.

Commands, outputs, source identity, failed regressions, original operational
errors and hashes are in [the review receipts](../verification/pr57-review/README.md).
The initial research-custody invocation used an incompatible manifest filename/
schema; both diagnostics are preserved and verification passed using the actual
files with an explicit in-memory schema adapter, without editing their manifests.
Raw JavaCSV logs retain CRLF evidence: whole-diff whitespace checking reports those
six historical log files and one verbatim failing-regression line in
`parser/before-tests.txt`. Source/docs checks excluding exactly those seven raw
outputs pass.
No failure evidence was normalized or removed. The first final-head package/schema
check caught two empty failed-command stdout captures named `.json`; only their
extensions were corrected to `.stdout`, preserving all bytes and diagnostics.
The failing check is retained; the validator was not weakened.

Only the selected XML resolver native probe was rerun. Broad XML, MapFish,
referencing, GeoFence, importer/GDAL, Huldra, JavaCSV, JGridShift, logging and
historical database/Jupyter native suites were not rerun. No dependency graph,
component source or fixture changed to justify repeating them. Their original
successes, skips and failures remain historical and explicit.

## Tracking and owner decision

[Complete Project readback](../verification/pr57-review/project/README.md)
confirms **66 planned tasks + four PR items =70 items**, all unarchived. The
unchanged `is:pr is:open` filter matches #57/#56; merged #54/#55 remain retained.
All task fields, identities, parent Evidence, seven views, 24 fields and fifteen
repository links are preserved. #55's built-in Status alone changed Todo → Done
since its prior receipt; FND-02 is In progress and GOV-02 is Merged. **Zero Project
mutations** were needed. No importer was rerun.

Preflight enumerated all PR comments/reviews/requests and review threads to their
terminal pages; there were no outstanding requests or unresolved threads. Parent
issue discussion was read and retained. All 20 existing worktrees were clean,
with no native build/database process using the selected checkout; repairs used
two separate local worktrees. The current mergeability, checks and exact published
head are read back again after push. No GitHub CI result is implied by local tests.

The requested owner decision is whether this **bounded source-recovery and
compatibility-evidence checkpoint**, including the two scoped repairs and its
explicit omissions, is acceptable for your separate GitHub merge to main.
GitHub mergeability alone does not establish that conclusion.

Acceptance does **not** close the 12 unresolved/four partial source cases or turn
48 structural dispositions into reproducible source-to-binary closure. Broad XML
still has one socket-fixture error/four skips; MapFish still has 17 errored case
identities/six skips. JavaCSV's 16 Linux-default failures, six importer proprietary
fixture skips, combined logging/OAuth/policy/runtime gaps, schema repackaging and
rights, host/toolchain closure, final source/license/security reviews, canonical
baselines, FND-07/FND-08, P1/P6, FND-02 completion and release remain open.

No PR was merged or auto-merge enabled. Approval here does not authorize an agent
merge, #56 acceptance, branch deletion, waiver of required reviews, or the next
HTTP/XML/printing/logging/OAuth engineering slice. **#56 is next in the chosen
review order and has not been prepared in this run.**
