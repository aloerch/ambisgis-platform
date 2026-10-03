# Synthetic corpus inputs

SPDX-License-Identifier: GPL-3.0-or-later

The generator, hand-authored expectations, project template and generated data
are wholly synthetic first-party fixture material under the existing project
license policy. They contain no copied organization data, proprietary samples,
private schemas, credentials or real-person records. Third-party runtime
libraries and the separately retained QGIS Vera font keep their own terms; no
font or library bytes are embedded here.

`expected-small.json` is a separately written semantic oracle for twelve rows,
not output from the query implementation. `templates/rich-style.qgs` is an
actual project authored and reopened with the retained owned QGIS runtime. Its
local paths resolve inside each generated corpus. Layer IDs are fixed fixture
identities, not product service registrations.

Generate into a new directory with `tools/synthetic_corpus.py generate` from
the plan root. Generated large datasets are local verification artifacts and
are not checked into Git. See `docs/fnd-06-synthetic-corpus.md` for commands,
actual checks and capability limits.
