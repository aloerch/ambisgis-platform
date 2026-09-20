# Recovered Huldra source and Marlin correspondence probes

The exact Huldra 0.7.1 release source was recovered from the publisher fork's
`0.7.1` branch at `efb66d8bfe782a66a78cb8c4b7ddd2be7212a9f9`. Its POM
declares 0.7.1 and its BigInt source accounts for all four retained binary
classes. The original license is retained. Archive SHA256:
`3985701f0a8ef56a0d5408f2bfac9890e01efeb70751e946b9c34a3d1647a497`.

Two fresh probes compiled the unchanged main and original test source with
retained Temurin 17.0.20.1+1, `javac -source 7 -target 7`, JUnit 4.12 and
Hamcrest 1.3, all selected by verified hashes. Both passed **19 original native
JUnit tests, zero failures/errors/skips**, comparing arithmetic with JDK
BigInteger. Original random tests remain unseeded. The final runner also checks
actual IPv4/IPv6 denial receipts, exact executed-test count, source integrity,
and refusal to overwrite prior runs. Three guard tests cover changed source,
preserved prior evidence and invalid network-denial reports. Java 7 target
bytecode on this JDK is not a Java 7 runtime compatibility claim.

The reusable recipe is `build-support/java/huldra_probe.py --help`. Provide the
retained source blob above, Java Maven/toolchain custody and installed tools
recorded in the resolution handoff, and a **new** output directory. It fetches
nothing and invokes no Maven/deployment lifecycle. Actual final command/log/class
hashes are in [machine evidence](../verification/java-recovered-source-probes.json);
raw runs remain under `build-worktrees/java-compatibility/huldra-0{1,2}`.
This compiles recovered repair source; it does not assert that its class bytes
match the publisher binary or approve full dependency/bootstrap/license closure.

## Marlin: a verified source discrepancy remains

The publisher's v0_9_4_8 release JAR exactly matches retained
`org.marlin:marlin:0.9.4.8`, SHA256
`44c3c3620102749844e58f668523f073db127efbd0b233ec9b13b3205db1362f`.
The similarly named Git tag points to old 0.7 source and is rejected as an exact
0.9.4.8 source assignment. The publisher's `jdk` branch revision
`5b1cbb57c39082cc444807daec401dd033754af7` instead declares the matching
`0.9.4.8-Unsafe-OpenJDK11` version. It covers 43 of 44 top-level source paths
required by the 87 packaged classes, but omits `OGLRenderQueue.java`.

Supported commit readback shows that exact release-day commit removed the
OpenGL source. The preceding version at
`aeeb57fa32f175cb970994b9ae5d3b173990ce6e` was retained and successfully compiled
in a separate socket-denied probe, producing its two classes. Neither class
was byte-identical to the publisher output. Disassembly establishes substantive
differences: the publisher QueueFlusher uses a volatile needsFlush field and a
different thread-group helper/Thread constructor. Those are not just ZIP
timestamps or debug metadata. The attempted source is therefore **not** marked
as the exact source for those packaged classes.

Retained JDK source inspection and OpenJDK/JetBrains source-history queries did
not establish the exact missing variant. Public API rate-limit failures were
preserved; authenticated read-only queries recovered the deletion history. An
initial local receipt-schema KeyError occurred before any copying and its
corrected check is retained. All original source archives and frozen Java
resolution custody remain unchanged.

The next engineering remedy is a clean controlled Marlin build from explicit
source, then affected Java2D/rendering tests and a deliberate module-patch
profile choice. Until then this artifact remains partial source correspondence.
Do not substitute the preceding source, drop rendering functionality, or infer
security/legal/product acceptance from either exploratory compilation.

Supplementary source research (including exact Huldra/Marlin and four Apache
release archives) is frozen under `source-archives/java-source-closure-parent`,
with manifest identity in the machine evidence. The main 64-gap inventory
records each source disposition separately.
