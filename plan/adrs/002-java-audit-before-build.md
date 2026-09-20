# ADR 002 — Resolve the Java extension inputs before building

Status: bounded FND-02 engineering audit decision, 19 September 2026. This is not
approval of a canonical product baseline, license combination or runtime profile.

Context: the selected owned GeoTools 34.5 / GeoWebCache 1.28.5 / GeoServer 2.28.5
versions agree, but GeoNode 5.1.0 requires extension behavior beyond a vanilla
WAR. Its default printing path reaches MapFish `2.4-SNAPSHOT`. A frozen snapshot
POM is not source-to-binary provenance. Inherited GeoNode image recipes also use
moving inputs. Maven default formatting can mutate source during `validate`.

Decision: retain exact source and declarative audit evidence first. Treat the
complete Maven/toolchain/extension closure as unresolved until actual effective
resolution and source/artifact custody are verified. Keep original declarations,
malformed POMs and diagnostic outcomes. Do not silently remove printing or infer
GeoNode compatibility from successful core compilation. Evaluate a recorded
MapFish release source separately; no substitution is made in this audit.

Consequences: no Java build or product acceptance is claimed by this checkpoint.
Future builds use isolated owned-source copies, reviewed local settings, fixed
inputs and artifact-origin checks. Inherited deployment namespaces/workflows stay
inactive. No new public repositories or extra product authorities are introduced.

Evidence: [audit findings](../docs/java-dependency-audit.md),
[audit input manifest](../../build-support/java/inputs.json), and
[verification record](../verification/java-dependency-audit.json).
