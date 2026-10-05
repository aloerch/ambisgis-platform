# Faithful inspect sysctls for never-started development containers

The retained Podman source labels internal `Configured` state as `created`.
It has persisted configuration but no realized OCI config file until native
initialization. Lifecycle015 retained a GeoServer serving row in exactly that
state. The installer previously required `OCIConfigPath` for every present
container, so that row cannot pass the old cleanup inventory validator. This
finding is separate from the still-unreconciled gateway starter and the original
`up` failure; it does not establish either cause or completed cleanup.

`podman_inspect_build.py` derives from the exact completed health-timer producer.
Its additive `HostConfig.Sysctls` field copies the sysctl map from the same
`ctrSpec` already selected by native inspection. The helper preserves nil,
empty, unknown keys and literal values and returns an independent map. It does
not infer the map from command arguments, use the lossy `generate spec`
projection, read the native database independently or initialize a container.
Both existing production-file changes and the two new standalone Go files are
bound by exact source hashes. Previous source repairs, vendor bytes, toolchain,
notices and offline execution controls remain bound to the predecessor.

The installer accepts missing or empty `OCIConfigPath` only for exact native
`created` state with false running/paused/dead/OOM/restarting flags, zero integer
PIDs and exit code, empty native error, no restored/checkpointed flag, and the
native zero start/finish timestamps. That branch requires the complete exact
IPv4-only sysctl map from the owned inspect field. Every common image/ownership,
ports, environment, user, command, capabilities, security option, namespace,
network, tmpfs and bind-mount check remains in force. Missing field, wrong type,
partial map, extra key or any differing value rejects the row.

The resulting process receipt explicitly reports `created` with
`configuration_validation: created_intent`. This proves configured intent only.
Any present OCI path is still checked using the original private-file validation
and exact realized sysctls. All other states retain that file requirement; an
invalid, missing, escaped or unsafe named file never falls back to intent.
Existing initialized/running/stopped receipt shapes remain unchanged.

## Verification and pending native work

Focused Python fixtures first fail against the retained installer baseline and
then pass the corrected validator. They deny process, socket and native-library
execution. Existing security-drift, tmpfs, OCI and network guards are retained.
Pure producer tests reject changed native inputs or duplicate patches before
writing, verify exact field/callsite source, and bind the four-command future
plan. The standalone Go unit checks map fidelity/non-aliasing and parses the
actual production declaration and callsite. It never loads libpod package
initializers, TestMain, engines, namespaces or inherited qualification suites.

Only inert preparation is authorized for the source author. Compiler execution,
the eight Go subcases, binary builds, and actual old/new ordinary inspect checks
remain unperformed until separate review and root execution. The ordinary
regression must bind a fresh owned fixture, verify old missing-field rejection,
new exact intended sysctls on never-started state, and realized OCI behavior for
initialized/running/stopped states. It must retain exact identities and normal
owned cleanup without changing user data or the held targeted probe. No bundle
selection, existing installation cleanup or PLT acceptance follows from these
source fixtures or preparation alone.
