# FND-06: exact tr46 notice supplement

The [supplement](../../build-support/koop/notices/tr46-0.0.3/) supplies missing notices and source provenance for the unchanged `tr46@0.0.3` archive, SHA-256 `164ae1eb32cea353551bbc7f9358dcaae4ffabbe65ec37a92ca464a9570a2a0a`. It is separately identified and does not claim that the original npm archive contained these notices. No candidate-002 archive, lock, installed package, runtime source or shared Koop installer is modified.

The [standalone verifier](../../build-support/koop/tr46_notices.py) checks every input against a reviewed manifest hash, all five archive members, original source/git-tree identities, both complete notices and exact reconstruction of the generated mapping table. It uses only the Python standard library and local retained files. It does not import third-party code, run lifecycle scripts, install packages or make network requests.

## Historical grants and exact source coverage

The selected source `a8009f9ce80ff5dbe71dd71e203afe4e4c878d28` is the direct parent of [the official license-only addition](https://github.com/jsdom/tr46/commit/3a6f29721e7063b9ffd421e461a54beae6170001). That commit adds only `LICENSE.md`, carrying the complete MIT grant and copyright 2016 Sebastian Mayr. The verifier recomputes root and nested Git tree objects and checks that all thirteen pre-existing entries are identical. The actual roots are `7b86f219be315cb2c5b99768c2b1642cf2b262ae` and `8fd3089743b3401643611efce88105a92303456a`; the retained API response's top-level `sha` echoes the requested commit and is not used as the root-tree hash. Four npm members match the historical source blobs exactly. This uses a particular grant over identical source, not a present-day license inference.

The fifth member, `lib/mappingTable.json`, is generated data. The pinned [Unicode 8.0.0 source](https://www.unicode.org/Public/idna/8.0.0/IdnaMappingTable.txt), SHA-256 `5e9f5929130b713e698162ac5b60a99ccfb831606686b1c50777cd920b55dee2`, reconstructs its 8,179 rows and 260,049 bytes exactly. The full historical Unicode copyright/permission text comes from [section 1 of the official ICU 56.1 source](https://github.com/unicode-org/icu/blob/24c90c0693a0ba7aea00986c34676b55f766cfac/icu4c/license.html#L58), file blob `878232262db9d54ea4265337799b36b79999cbc1`. The original HTML is retained; the verifier extracts and compares the complete section title/text, including notice conditions, disclaimer and promotional-use restriction. Other sections of that historical HTML are provenance context, not asserted tr46 obligations.

`MIT-LICENSE.txt` retains the exact upstream bytes. `UNICODE-LICENSE.txt` retains the full section text with markup removed. `NOTICE.txt` explicitly describes the modification: comments are removed, hexadecimal ranges and replacements become integers, and rows become compact JSON. That statement accompanies the software and its documentation as required by the retained Unicode notice. The original generator is retained as source evidence; its floating network fetch is never executed. Rebuilds use the pinned local Unicode input.

The narrow `.gitattributes` inside this bundle preserves original whitespace in four exact third-party files: the Unicode notice, original mapping generator, historical ICU HTML and Unicode 8.0.0 data (including its blank line at EOF). These files are hash-verified. First-party helper, tests and documentation still receive ordinary whitespace checks.

## Verify, stage and independently check the staged source

Run from the platform root. Supply the actual retained archive, not an npm package name or network URL:

```sh
TR46_ARCHIVE=/retained/candidate-002/registry/365413f62144e1b6242d1bf5312aebee2b6a73df29813d92e374458361ab7fba.tgz
python3 build-support/koop/tr46_notices.py verify --archive "$TR46_ARCHIVE"
python3 build-support/koop/tr46_notices.py stage --archive "$TR46_ARCHIVE" --output /existing/work/tr46-stage
python3 build-support/koop/tr46_notices.py verify-stage --archive "$TR46_ARCHIVE" --output /existing/work/tr46-stage
```

The output directory must be new, its parent must already exist and neither it nor its ancestors may be symlinks. Inputs and existing destinations are never overwritten. A partial new output remains for diagnosis after failure; select another new path for a retry. The staged layout is:

```text
software/notices/tr46-0.0.3/{MIT-LICENSE.txt,UNICODE-LICENSE.txt,NOTICE.txt}
documentation/notices/tr46-0.0.3/{MIT-LICENSE.txt,UNICODE-LICENSE.txt,NOTICE.txt}
source/tr46-0.0.3/supplement/       complete pinned source/notice/provenance inputs
source/tr46-0.0.3/original-npm-archive.tgz
source/tr46-0.0.3/generated/mappingTable.json
source/tr46-0.0.3/tr46_notices.py
stage-manifest.json
```

The archive is copied byte for byte; archive-supplied paths are never extracted. To recheck using only the staged source plus Python, invoke the staged verifier with explicit paths:

```sh
python3 /existing/work/tr46-stage/source/tr46-0.0.3/tr46_notices.py verify-stage \
  --archive /existing/work/tr46-stage/source/tr46-0.0.3/original-npm-archive.tgz \
  --bundle /existing/work/tr46-stage/source/tr46-0.0.3/supplement \
  --output /existing/work/tr46-stage
```

The verifier reconstructs the expected staged bytes from approved inputs and checks exact file/directory membership. Editing a stage manifest cannot authorize missing, changed or additional files. Symlinks and special files are rejected. This is trusted local packaging tooling, not a sandbox against concurrent malicious filesystem writers.

## Actual checks and remaining integration

[Selected evidence](../verification/fnd06-tr46-notices/evidence.json) binds the helper, input manifest, actual fresh stage, independent staged-verifier result, socket-denial receipts and unchanged input snapshots. [Fourteen targeted tests](../verification/fnd06-tr46-notices/test_tr46_notices.py) exercise the real archive and reconstruction, two identical fresh stages, self-contained verification, rewritten manifests, missing/extra/symlink inputs, existing destination preservation, archive tampering/unsafe members, forged source trees and invalid code-point ranges. They require `TR46_ARCHIVE`; no unavailable-input case silently passes or skips:

```sh
export TR46_ARCHIVE
python3 plan/verification/fnd06-tr46-notices/test_tr46_notices.py -v
```

The actual staged check runs under the existing socket-denial wrapper. Its scope and limits remain unchanged: non-AF_UNIX sockets are denied, while the filesystem and Unix services are not isolated. These results establish this supplement's integrity and checkability; they are not GIS runtime tests.

The required plan suite also passes 502 tests and all ten schema/example checks. Those package checks do not constitute rights clearance or product acceptance. The final printed failed receipt in the package log is expected output from an existing negative test; the unittest suite itself exits successfully.

The integrator must carry the staged notices into the selected software and associated documentation, preserve source availability and other dependencies' terms, and bind them to any later product manifest. This change neither adopts Koop nor approves its broader rights/security posture or product distribution. Those gates remain separate under chapters 08 and 11.
