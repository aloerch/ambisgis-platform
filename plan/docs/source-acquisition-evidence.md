# Source acquisition evidence — preparation for FND-02

Recorded 19 September 2026. Eleven authorized public source forks have complete local Git histories and verified retained Git bundles. This evidence supports review of the initial source candidates. It does not approve product baselines, licenses, a compatible build tuple, or full source/dependency custody.

[FND-01](https://github.com/aloerch/ambisgis-platform/issues/2) is **Merged** after owner-approved [PR #1](https://github.com/aloerch/ambisgis-platform/pull/1), commit `2215a91511a53601464eef46d383cd3557cfa3a8`. [FND-02](https://github.com/aloerch/ambisgis-platform/issues/3) is now in progress; this evidence does not complete it or advance [FND-07](https://github.com/aloerch/ambisgis-platform/issues/6). FND-02 requires a human License/Brand review and real build/smoke evidence.

The [machine-readable record](../verification/source-acquisition.json) contains owned repository IDs, donor parents, exact commits, verification results, workflow paths and blob IDs, and 46 license/notice file records with original filenames, blob IDs, SHA256 hashes and owned GitHub URLs. All values come from observed API or local Git/archive evidence. No unresolved release-lock value was fabricated or filled by assumption.

## Observed source candidates

Authenticated owner `aloerch`, owned repository IDs, public visibility, donor parents, and exact HTTPS origins were verified before cloning. The commits below were the default heads observed during bootstrap and match the retained donor observations. They are acquisition snapshots, **not approved product baselines**. No `ambisgis/main` branch or default-branch change was made in these forks by this acquisition.

| Owned repository | Repository ID | Observed branch | Observed commit | Remote branches / tags |
|---|---:|---|---|---:|
| ambisgis-postgresql | 1376927644 | `master` | `c62b330912e2095dc8dee2f749adf7e5d94ca611` | 39 / 692 |
| ambisgis-postgis | 1376927690 | `master` | `84890ccbe53549130de8a2b75a72ab3a54b570d1` | 38 / 316 |
| ambisgis-qgis | 1376927721 | `master` | `09d73a2b827841320e798d1f18c84a4776dbd265` | 130 / 314 |
| ambisgis-jupyterhub | 1376927753 | `main` | `929ef417d1e337a17a5e3ebfdd0e0143b021f91d` | 9 / 103 |
| ambisgis-jupyterlab | 1376927783 | `main` | `5ad633d6747371452c2f5fe465d18a70b8f3195d` | 40 / 48752 |
| ambisgis-geotools | 1376927869 | `main` | `9a4f847e8b83875169e279999659052a0cc2bf14` | 64 / 240 |
| ambisgis-geowebcache | 1376927892 | `main` | `821bae4793863555321cd7a935137c80b8eded73` | 80 / 212 |
| ambisgis-geoserver | 1376927947 | `main` | `98c7c567a9fa3b691915fa2fc613d90d90d78b62` | 110 / 237 |
| ambisgis-geonode | 1376927978 | `master` | `ddfdc44cabf13931fb1d53d35809699d6e4766ae` | 30 / 491 |
| ambisgis-mapstore-client | 1376928013 | `master` | `673a854c4b3b0694f8e9e6d81cc10ce5846d8ac7` | 95 / 60 |
| ambisgis-mapstore | 1376928043 | `master` | `0eedc8b7184d3b753d0581963814726f1e5ec8eb` | 153 / 66 |

Each clone used full history without checkout, object filtering, depth limits, or submodule initialization. All branch and tag refs were fetched from the owned origin without forced updates. Original ancestry, license files, build scripts, workflow files, and donor branch/tag references remain in Git and in the bundles. No donor remote was added. Reference tags and branches do not authorize automatic donor synchronization or determine an AmbisGIS release.

`git fsck --connectivity-only` returned zero for all eleven clones. This checks Git connectivity; it is not a complete integrity, license, build, or GIS product acceptance test. Partial-clone configuration, promisor packs, and shallow markers were absent.

## Retained Git archives

Eleven `git bundle --all` files contain **11,609,671,470 bytes (10.812 GiB)**. `git bundle verify` returned zero for each; every recorded local/remote/tag ref and `HEAD` matched the bundle. Each bundle has zero external Git-object prerequisites. SHA256 values below were computed over the actual retained bytes.

| Owned repository | Bundle bytes | Bundle SHA256 |
|---|---:|---|
| ambisgis-postgresql | 804532351 | `9480530afa7045636f0e0ea6636e42ec688cd477d8355089e29499e8e6837c6c` |
| ambisgis-postgis | 307823739 | `bc2bdd1cc3ae18ca532120c854b4502ff5b78762262876cc546fd20bf1e2c4cf` |
| ambisgis-qgis | 5735009887 | `16115faa63138821a443f416abcedfc824d53c552952b21d7d95d5c86ad4fb65` |
| ambisgis-jupyterhub | 37379597 | `876157a2a00c166f4c8417d90f872f521dbc93bd08972303a28f264f003c304f` |
| ambisgis-jupyterlab | 325510384 | `96f80e5ed46ef306b4c4a414c215a95fdf148b9c288aacb2c05257c9f2bd462f` |
| ambisgis-geotools | 449194517 | `c738143f1179d2a8964e11f84bfa84a24c463c95cef4e9c459b31d8b37454212` |
| ambisgis-geowebcache | 14633334 | `10dfc62c08e8028f6dddf96692bec2a5bec2db0feba21ae75153db9aa5366a47` |
| ambisgis-geoserver | 657339763 | `1e4a84dbb27c6fb52714f43997305fa0b1aa85632e31326dc026ed2d49dd554b` |
| ambisgis-geonode | 498966440 | `c5bac3dfb45f503397275a3739b115bd7434bebab1e90d5624375189c68514bd` |
| ambisgis-mapstore-client | 2093037430 | `263740e7d437e77f50bc8c665b30ff69398d12823d7b2527531371cdbcc0fbd2` |
| ambisgis-mapstore | 686244028 | `f9ce607c7fdfd070f8bdafd50b8cea288cc85bd2e9ae8e27763188c1500c02c4` |

Archive locations in the JSON use `source-archives/...` paths relative to the local multi-repository workspace. This directory is outside `ambisgis-platform`; neither bundles nor retained license bytes are committed in this PR or represented as remotely available artifacts. The 46 original license/notice files occupy 400,354 bytes under `source-archives/license-evidence/`. Their retained bytes were checked against both Git blob identities and recorded SHA256 values.

The bundles preserve Git objects only. Required LFS objects, submodule sources beyond observed local availability, generated files, native libraries, CRS grids, fonts, installer inputs, toolchains and the transitive build dependency closure have not been established. A clean restore, no-upstream rebuild, independent repair, or usable product build has not been demonstrated.

## License and dependency findings requiring review

- **GeoNode:** at `ddfdc44cabf13931fb1d53d35809699d6e4766ae`, the preserved [`LICENSE`](https://github.com/aloerch/ambisgis-geonode/blob/ddfdc44cabf13931fb1d53d35809699d6e4766ae/LICENSE) header states GPL version 2 or later, while its separator and reproduced complete text identify GPL version 3. Both facts require review of exact release/file scope and intended combinations. This evidence does not choose a license or assert that these statements are incompatible.
- **GeoTools:** at `9a4f847e8b83875169e279999659052a0cc2bf14`, [`LICENSE.md`](https://github.com/aloerch/ambisgis-geotools/blob/9a4f847e8b83875169e279999659052a0cc2bf14/LICENSE.md) contains LGPL 2.1 text; [`licenses/README.md`](https://github.com/aloerch/ambisgis-geotools/blob/9a4f847e8b83875169e279999659052a0cc2bf14/licenses/README.md) says version 2 or later and includes a standard-header example specifying 2.1. File-header scope remains unresolved. Font, ColorBrewer, Creative Commons, EPSG, OGC and other notices were retained without deciding which assets will ship.
- **GeoWebCache:** the core license text is nested at [`geowebcache/LICENSE.txt`](https://github.com/aloerch/ambisgis-geowebcache/blob/821bae4793863555321cd7a935137c80b8eded73/geowebcache/LICENSE.txt), containing LGPL version 3. The lack of a root license file is not absence of a license. Separate Blueprint and OpenLayers notices were also retained.
- **GeoServer and other donors:** preserve the actual selected-file terms and component exceptions. GeoServer's EMF/XSD/OSHI exception and supplementary notices require applicability review. Top-level QGIS/PostGIS/Jupyter/MapStore notices do not establish licensing of every dependency, submodule or asset. No blanket relicensing or copyright reassignment is implied.
- **GeoNode build tuple:** [`pyproject.toml:97`](https://github.com/aloerch/ambisgis-geonode/blob/ddfdc44cabf13931fb1d53d35809699d6e4766ae/pyproject.toml#L97) obtains the MapStore client from `archive/refs/heads/master.zip`; [`docker-compose.yml:96`](https://github.com/aloerch/ambisgis-geonode/blob/ddfdc44cabf13931fb1d53d35809699d6e4766ae/docker-compose.yml#L96) uses `geonode/geoserver:2.28.x-latest`. Both references float. `geoserver-restconfig==2.0.16` pins a client package version, not GeoServer server source or an image digest. These manifests are not an approved production lock and were not executed.
- **MapStore client linkage:** commit `673a854c4b3b0694f8e9e6d81cc10ce5846d8ac7` records a MapStore2 gitlink at `57868404efd4a29c6faf99ab046f1a746fa0ba34`. That commit exists in the owned MapStore clone. [`.gitmodules`](https://github.com/aloerch/ambisgis-mapstore-client/blob/673a854c4b3b0694f8e9e6d81cc10ce5846d8ac7/.gitmodules) still names the donor URL and `master` branch. No submodule was initialized, and presence of a commit does not approve a compatible tuple or complete submodule custody.

The 127 inherited GitHub workflow paths were inventoried and preserved at exact commits. Their contents, permissions, package coordinates, download/install scripts and update behavior have not been fully audited. Acquisition did not execute donor code or workflows, enable workflows, install secrets, publish packages, or change remote defaults. Product builds must use reviewed owned namespaces and retained inputs.

## Next review decisions and acceptance work

1. Preserve the verified FND-01 merge as dependency evidence. Choose exact candidate component commits with a documented rationale; verify PostgreSQL/PostGIS mirror commits against canonical provenance and check required assets. Default heads alone do not make this decision.
2. Resolve or explicitly block selected-file license scope, including GeoNode and GeoTools findings; decide included extensions, fonts, datasets, drivers and other assets. Preserve all original notices, record corresponding-source obligations, and obtain the required human License/Brand review. AmbisGIS remains a provisional name.
3. Inspect owned GeoServer/GeoTools/GeoWebCache extensions and GeoNode/MapStore/client relationships, then propose an immutable source/image/runtime tuple. Enumerate every remaining null as a blocker. Build and smoke-test the selected combination before claiming `T-LOCK-01`.
4. Audit inherited workflows, package destinations, downloads and update checks. Prepare reviewed setup changes before creating `ambisgis/main` from approved baselines or making it the product default. Preserve donor reference history and prohibit automatic donor synchronization.
5. For FND-07, enumerate and retain required LFS objects, submodule commits, dependency source/build artifacts, generated tools, base-image packages and toolchains with actual hashes. Close the retained-input inventory before `T-OWN-01`; recover selected baselines from controlled storage and verify ancestry, licenses and assets.
6. FND-08 must produce owned builds with actual regression and smoke results. Later independence gates require a clean environment with upstream hosts blocked, recorded toolchain/base-image provenance, rebuild and independent synthetic-defect repair. Canonical-model, database, REST, browser, notebook, security, upgrade and recovery gates remain required.

The required package checks validate this design package only. They do not validate a GIS distribution, donor build, license decision, disconnected rebuild, or release. No task is marked Verified, Merged or Released by this evidence record.

Validation on this branch used the isolated validation environment from `plan/`: `python3 -m unittest discover -s tests -v` passed all **55 tests**, with no failures, errors or skips; `python3 tools/validate_package.py --require-schemas` passed plan/dependency checks and all four schema/example checks. Additional evidence checks verified 11 archive records, 46 retained license hashes, 127 workflow paths, retained pending gates, and absence of absolute local paths or token patterns.

## Owned PostgreSQL candidate build probe

The exact owned PostgreSQL acquisition commit `c62b330912e2095dc8dee2f749adf7e5d94ca611` was built in a separate local `fnd-02/postgresql-build` worktree with unmodified default configure settings. Configure and `make -j4` passed; `make -j4 check` passed **239 real core regression tests**, with zero failures or skip markers. The temporary test cluster shut down cleanly and the source worktree remained clean. No global installation or remote source changes occurred.

[The path-normalized build record](../verification/postgresql-candidate-build.json) contains actual commands, source/tree IDs, compiler/library versions and hashes, executable hashes and log hashes. The original report and logs are retained locally. Build time was 47.820 seconds and the core regression command took 5.977 seconds on this environment; these are observations, not product performance guarantees.

This candidate identifies as PostgreSQL **20devel** and has not been selected as a product baseline. GCC 15.2.0, ICU 77.1, readline 8.3, zlib 1.3.1 and the remaining host toolchain/libraries are observed inputs whose complete source/build closure is not retained. Static build-script inspection is not network-denial evidence. TAP/check-world, PostGIS integration, AmbisGIS branch/concurrency/authorization/restore tests, an upstream-disconnected rebuild and independent repair remain unrun. The probe establishes build feasibility and does not satisfy FND-08 or approve an immutable product tuple.
