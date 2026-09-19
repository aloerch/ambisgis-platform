# FND-02 Jupyter slice — active engineering checkpoint

Repository `aloerch/ambisgis-platform` (ID 1376927351); separate worktree
`/home/revelberry/Projects/AmbisGIS/ambisgis-platform-jupyter`, branch
`fnd-02/jupyter-runtime`, based on verified PR #51 merge
`a3c2e2e696ea11bdc10c2ad202a240fbd0137f45`. FND-02 remains In progress.
No merge is authorized. Frozen database feature head remains unchanged.

Selected owned Hub 6.0.1 `3e516c6f382b481e815ec455befb2f14d80d337b` and
Lab 4.6.3 `e7255a9334c12ad8f9cb15db27584215fab5ece2`; Node24.21.0,
Python3.13.15 host. Exact dependencies and notices are in build-support/jupyter.
Retained store: `/home/revelberry/Projects/AmbisGIS/source-archives/jupyter-slice`.
Builds: `/home/revelberry/Projects/AmbisGIS/build-worktrees/jupyter-slice`.
Preserve every acquisition, run, failed probe and offline receipt.

Run001 compiled both owned wheels and frontends under socket denial. Real Lab
kernel/save/reopen/shutdown passed, but Hub startup found omitted owned runtime
package data. The recipe now explicitly includes/checks those five original data
files. Initial Hub native collection exposed missing host PAM; isolated retained
Linux-PAM1.7.2 core libraries fixed it (137 native tests passed). Lab Python69,
Hub JSX55, Lab coreutils62 and nbformat6 passed. Those are selected native suites,
not browser or notebook product acceptance. Run002 is the clean corrected build;
consult its build-report.json before starting probes. This checkpoint will be
replaced with final exact results/PR before session completion.

GOV-02 is independently reviewed in PR #52, branch
`gov-02/saved-view-reconciliation`, head
`cb871e82f15be7363c3dc0e786923e9572d77d11`. Owner observations plus API readback
resolve most view settings. Issue #9 still needs two precise owner observations:
view5's Review gate restriction and view4's built-in Status hidden/derived-only
behavior. See PR #52's reconciliation guide. These do not block Jupyter work.
