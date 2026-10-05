# Native GeoServer initialization

The private unchanged-image replay of bundle017 observed two configuration
errors: `ImageNInitializer` received null image-processing settings, and the
native REST parser ignored the entire administrator rule because it contained
`PATCH`. The same capture observed the beginning of native context cleanup,
followed later by the existing Python child deadline. It did not identify the
blocking Java call or prove that cleanup or `main` completed. These observations
belong to that replay; they do not supply an unobserved frame for attempt014.

The owned generator now writes the selected native `<jai>` field alias with
explicit `ImageProcessingInfoImpl` defaults. `XStreamPersister` maps this alias
to `imageProcessing`; `GeoServerInfoImpl.readResolve` does not restore an absent
value. The REST rule uses only the six methods accepted by the selected native
`RESTAccessRuleDAO` pattern and keeps `ROLE_ADMINISTRATOR`. The mandatory owned
catalog filter still admits only the two fixed GET map/query projections, so
PATCH, other writes and administrative routes remain denied.

The owned Java launcher emits constant initialization phases around server
start, transport initialization, the initialization marker, server stop and
main completion. A failure record contains only an allowlisted exact exception
class or `OTHER`, never messages, paths, cause chains or dynamic class names.
These records go to the existing stderr stream; no new endpoint, persistent
authority or general logging interface is introduced. Serving mode emits none
of these initialization records. A diagnostic sink failure cannot replace an
application exception or prevent the existing finally-stop action.

The 180-second Java-child and 240-second outer initializer deadlines, entrypoint,
native application inputs and finally-stop semantics are unchanged. There is no
forced JVM exit. `MAIN_COMPLETE` is evidence that the launcher reached its last
milestone, not proof that the JVM exited; process exit remains a separate native
observation. Future failures still require the bounded private capture to retain
full logs, since the public installer discards arbitrary native output.

Four Python checks execute the actual configuration generator on synthetic
files, including retained-pattern invalid-method cases. The original generator
fails the required `<jai>` and accepted-REST-rule checks. This is configuration
contract evidence, not native deserialization or startup acceptance.
`DevelopmentFilterChecks` retains its request-denial checks and adds executable
callback tests for phase ordering, secret-bearing/nested/hostile exceptions,
original exception identity, stop precedence, failing diagnostic sinks and
serving silence. The trusted integrator compiles and runs those Java checks with
the retained toolchain; source preparation alone does not count as a Java test.
