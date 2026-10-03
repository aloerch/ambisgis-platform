# tr46 0.0.3 notice and source supplement

This directory carries exact historical third-party notices and verified source
inputs for one unchanged npm archive. `input-manifest.json` binds every file,
the five archive members and the selected source identities. The standalone
`../../tr46_notices.py` checks the manifest against its reviewed hash, reads the
archive without extracting it, verifies source-tree/blob equivalence and
reconstructs the generated table entirely from local retained bytes.

`MIT-LICENSE.txt` is byte-for-byte the official license-only direct successor's
file. `UNICODE-LICENSE.txt` is the complete title and text of section 1 of the
retained historical official ICU license HTML; markup is removed without
dropping the copyright, grant, conditions, disclaimer or promotion restriction.
The verifier repeats that extraction and compares exact text. Other ICU and
dictionary notices in the provenance HTML are contextual evidence and are not
asserted to govern tr46. The source files retain their respective third-party
terms; the helper and tests are new first-party GPL-3.0-or-later code.

`NOTICE.txt` states that the original archive omitted these notices and clearly
describes the Unicode data transformation. The staging helper places all three
notice files in both `software/notices/tr46-0.0.3/` and
`documentation/notices/tr46-0.0.3/`. It also stages the complete local source and
provenance bundle plus the reconstructed mapping table under
`source/tr46-0.0.3/`. The unchanged original npm archive and this standalone
verifier are copied there too; the complete supplement is in its `supplement/`
subdirectory, so a staged source bundle can be verified without the original
checkout. This is a new packaging input, not an installed runtime or
a finished distribution. A release integrator must carry these paths into the
selected software/documentation and preserve its other notices and obligations.

No network, package manager, third-party script, extraction hook or installed
package is invoked. Existing destinations and symlink ancestors are rejected.
Inputs remain unchanged; interrupted new outputs are preserved for diagnosis.
For commands and actual validation evidence see
`plan/docs/fnd-06-tr46-notice-supplement.md` in the platform repository.
