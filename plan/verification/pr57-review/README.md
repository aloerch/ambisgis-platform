# PR #57 review verification

These are current review-preparation observations, separate from historical native
results already committed by PR #57. No PR merge, auto-merge, Project mutation or
new engineering slice was performed. The final exact head/full tree and fresh
remote readback are recorded in the published PR review summary and persistent
`final-checks.json` after this evidence commit.

## Commands and source identity

`checks.json` records current tooling/package/schema commands, directories,
exits and output hashes. The Java implementation tree is
`d6ca199d12cb0e963748b5a6a58a8cca0e3c72dd`, through repair commit
`c3c12251b61777df79d2ef1ddd8cfb8fdc108c16`. The final head is checked again after
committing these evidence/docs files. `ancestry-before.json`,
`merge-verification.json` and `preservation.json` record actual prerequisites,
normal merge, remaining-diff equivalence and unchanged historical receipts.

`parser/` and `compat-finalization/` retain original failing regressions and
passing corrected runs. The independent source/compatibility reviews retain
remaining gaps and distinguish engineering review from owner approval.

`source-accounting-comparison.json` proves complete byte equality before/after the
parser repair; both real64 runs exit2 for the explicit unresolved/partial cases.
Full 7,676,265-byte reports are retained externally, not duplicated here.
Command (from root, each output must be fresh):

```
python3 build-support/java/source_closure.py \
  --triage plan/verification/java-resolution-source-gap-triage.json \
  --manifest build-support/java/source-closure-inputs.json \
  --frozen-maven /home/revelberry/Projects/AmbisGIS/source-archives/java-resolution/maven \
  --supplement /home/revelberry/Projects/AmbisGIS/source-archives/java-source-closure \
  --output /tmp/ambisgis-pr57-review-20260920/source-accounting-after.json
```

`native-probe-summary.json` gives the exact current native command, recipe hash,
result/log hashes and actual12test result; `xml-resolver/` retains its result and
network-denial proof. This is the existing bounded schema-resolver probe, not
broad XML, MapFish or full native acceptance. The full fresh run, source/tooling
copies, Maven repository and logs remain at
`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-compatibility/review-pr57-xml-resolver-01`.

Custody outputs retain original snapshot hashes. The original parent/research
snapshot schemas differ from the generic audit manifest; initial command errors
are retained alongside `verify-research-custody.py`, which validates unchanged
file entries through an explicit in-memory adapter. No archive was edited. The first final-head package/schema check caught two empty
failed-command stdout files named `.json`; they are now correctly named `.stdout`,
with unchanged bytes. `first-final-check-error.json` and the failing output retain
the diagnosis; no validator rule was changed.
Toolchain trust/bootstrap limits remain explicit. Historical-native audit hashes
and counts are reverified by `audit_compatibility_history.py`, not rerun.

`project/` is fully paginated read-only Project evidence: 66 tasks +4PRitems,
current queue57/56, all task fields/archive states preserved, zero mutations.
The six historical JavaCSV native logs contain deliberate CRLF evidence; raw
whole-diff whitespace diagnostics are retained. Source/docs checking excludes
exactly those six logs plus `parser/before-tests.txt`, whose retained unittest
failure contains one trailing-space line. Regression output is preserved verbatim.

## Persistent full record

Complete fresh API/discussion captures, old/merged patches, source reports,
regression records, final check outputs and published PR readback are retained at:

`/home/revelberry/Projects/AmbisGIS/build-worktrees/java-compatibility/review-pr57-preparation-01`

No data is added to the frozen source-archive roots. `files.sha256` covers this
committed receipt directory except itself. Historical receipts elsewhere remain
unchanged. Future exact heads must be reviewed separately.
