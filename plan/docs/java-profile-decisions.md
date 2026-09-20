# Java capability profile and bootstrap disposition

The bounded compilation probes retain ADR 003's explicit profiles:
`importer,oauth2-geonode,geofence-server,geofence-server-postgres,printing,postgis`.
This selects inputs for compatibility work; it does not adopt the donor image,
its data directory, or its deployment/security configuration.

| Capability/path | Choice for this slice | Required later evidence |
|---|---|---|
| Referencing and XML | Compile/test the owned GeoTools dependency order, using inspected fixed schema resources. | Complete resource/source/notice closure and affected offline resolver tests. |
| Importer | Keep selected because the exact owned GeoNode helper creates an importer Client. The donor extension workflow's omission is not adopted. | Real publication fixtures, failure compensation and policy enforcement. No direct managed-branch writes are enabled. |
| OAuth | Keep `oauth2-geonode` and its owned core/web dependencies selected. GeoNode's exact settings name the corresponding login/logout endpoints. | Actual authentication denial, roles, token handling and canonical-policy integration tests; security review. |
| GeoFence PostgreSQL | Keep both server profiles and PostgreSQL test input selection. Both distinct GeoTools version properties remain aligned to 34.5 for this experiment. | Compile/API compatibility followed by a real isolated PostgreSQL test database and authorization fixtures. |
| Printing | Keep the exact MapFish 2.4.1 source candidate and GT34.5 override. No snapshot substitution or blanket compatibility claim. | Compile and real PDF/image/legend behavior plus controlled, reviewed print configuration. |
| WPS and WPS download/GeoFence hooks | Outside this bounded probe, matching the owned GeoNode application's `WPS_ENABLED` default of false. The donor image's enabling profile/data file is not an authoritative product requirement. | Explicit capability choice and process authorization/resource limits before enabling WPS. Required service, metadata, branch editing, apps, notebooks and QGIS publishing remain unchanged. |
| Other driver/style/vector-tile profiles | No blanket adoption of the donor recipe's list. | Subsequent capability-specific source/build/runtime gates; successful core probes do not advertise them. |

[Declaration hashes](../verification/java-profile-decisions.json) identify the
exact owned settings/helper bytes. The original recipe discrepancy and full
profile list remain in [the audit](java-dependency-audit.md). The owned
source revisions and candidate overrides remain those in ADR 003. Compilation
results and deliberate native test selections are reported separately; input
selection never means runtime acceptance.

## Bootstrap and asset provenance

[File evidence](../verification/java-bootstrap-provenance.json) records 46 exact
security, GeoFence, printing and WPS/data-readme members from retained extension
commit `b4e2fc4b7596cae051ee233417f39e3e33b5e6c5`. The archive SHA256 is
`c5fc10ffd52e7807e5aa0370666a8f7f3b8a63864a6107b12b47496c891aa265`.
Only paths, sizes and hashes are published; configuration values and credential
store contents are not copied into evidence or a deployment. The data README's
statement about published data is not treated as a source-code/asset license.

The north-arrow asset has a concrete provenance improvement. Its 4,828 bytes
match the publisher's SVG exactly, SHA256
`d307e75e7a6b7da858580bc582f38cee9204c25fb89647f80b91f9c884d827fc`.
The [publisher's permanent rights record](https://commons.wikimedia.org/w/index.php?title=File:Arrow_North_CFCF.svg&oldid=1036216605)
attributes it to Carlos Francisco Cruz Fierro and records a public-domain
dedication. Both original SVG and rights-page bytes, URLs, retrieval time and
hashes are retained under
`/home/revelberry/Projects/AmbisGIS/source-archives/java-profile-evidence`.
This is byte-matched rights evidence for that asset, not legal/brand approval
for the whole inherited printing configuration or logos.

The remaining inherited configuration/assets still lack established file-level
rights in this slice. No source-portfolio or deployment decision is needed to
continue isolated compilation. Before actual owned service bootstrap, implement
reviewed configuration from the canonical product model, generate fresh
credentials, and use controlled print fixtures/assets with explicit provenance.
Do not activate the inherited users/keystore, live download scripts, Docker
entrypoint or workflow. Those concrete unresolved runtime/rights gates are
preserved; retaining a recipe does not satisfy them.
