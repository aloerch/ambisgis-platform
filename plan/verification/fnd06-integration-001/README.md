# FND-06 reviewed integration checkpoint

This checkpoint joins the initial shared contracts, deterministic corpus and
complete Koop custody/offline-install repair. FND-06 remains In progress in
[draft PR77](https://github.com/aloerch/ambisgis-platform/pull/77).

[evidence.json](evidence.json) binds the exact tested local commit, original
independent review receipts, actual install receipt and raw combined test logs.
All 502 package tests, ten schema/example checks and 21 custody guards pass
without skips. The deliberate negative fixture prints a failed receipt after
the package test runner reports OK; that expected rejection is not a suite failure.

The separate corpus evidence retains actual owned-QGIS small, 100,000-address
and 1,000,000-address native runs, failed engineering attempts and actual
malformed-input rejections. The independent reviewer also ran the small native
success and two rejection paths and scanned all 1.1 million generated rows.

The fresh offline install contains 213 registry packages and six workspace
packages, with 39 optional-only packages omitted and every installed byte checked.
It executed neither lifecycle hooks nor package code. Runtime invocation and
its results remain a separate evidence set. The exact tr46 notice/data provenance
question, broader rights duties and security limits are not waived by installation.

No original product requirement, task acceptance criterion, phase exit or human-only
evaluation changes to passed from this checkpoint. The 93-item Project observation
records the separate draft PR item and preserves unrelated planning and history.
