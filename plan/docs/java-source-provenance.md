# FND-02 Java source provenance supplement

This slice accounts for every one of the **64** previously recorded missing Maven
source classifiers. It retains source candidates for **39**, embedded Java source
for **4**, source/generation inputs for **3**, and verifies **2** metadata-only
artifacts. **12 remain unresolved and 4 remain partial.** These are structural
source-inventory categories, not 48 independently rebuilt or legally approved
artifacts. FND-02 remains In progress.

The [64-coordinate machine report](../verification/java-source-provenance.json)
contains exact binary/source hashes, actual test-classpath or declaration evidence,
source revisions, original notice/header hashes, attempted remedies and limits.
The [source lock](../../build-support/java/source-closure-inputs.json) is consumed
by the [validator/recovery command](../../build-support/java/source-closure.md).
Full class-by-class mappings and original attempts remain under
`/home/revelberry/Projects/AmbisGIS/source-archives/java-source-closure`;
`java-resolution` and `java-audit` custody were not modified.

## Concrete repairs and findings

Missing classifiers concealed embedded source in bndlib and three JSR305 releases,
and empty Maven marker/aggregator packages in listenablefuture and flexmark-all.
Exact publisher release archives recover ASM, ANTLR, H2, PicoContainer, XML Resolver,
Apache XML Commons, DBCP, JSch, Ant, BCEL, Velocity, Eclipse, JLine and other source
inputs. Debug-stripped class files use an explicitly labeled top-level declaration
inference; other classes use their original SourceFile attributes. Those checks
cannot establish byte-identical or semantic source/binary equivalence.

JavaCSV's original CVS binary exactly matches the selected Maven binary; the
contemporaneous source revisions were reconstructed independently and retained
with their original LGPL headers and extraction recipe. Its native test outcomes
are reported by the separate JavaCSV checkpoint. PostgreSQL JDBC's seven template
class mappings and thirteen generated translation classes retain original `.java.in`
and `.po` inputs plus the exact gettext script; that generator/toolchain was not
executed or accepted. ANTLR's shared source template is also explicit.

Four important partial correspondences remain. Commons Codec 1.2 contains
SoundexUtils absent from the official 1.2 source tag. AspectJ weaver embeds five
BEA classes absent from its source release. GroboUtils's original source covers
388 of 1,006 classes; its original third-party bundle retains binaries, not full
corresponding sources. Marlin's selected binary matches the publisher release,
but OGLRenderQueue and its QueueFlusher class are absent from that release's source;
the preceding deleted source was compiled/inspected separately and differs, so it
was not attached as matching source. Eclipse resources' exact v20070604 qualifier
also requires correspondence evidence despite complete structural coverage.

Oracle ojdbc14 remains a provided dependency of the selected image mosaic path.
Its unavailable corresponding source is not waived or removed. The other unresolved
entries retain specific source/repository/download attempts. A failed HTTP request,
binary-only release, HTTP-200 HTML page, or successor project's different version
is not accepted as source. Complete actual runtime use for plugin/transitive-only
records remains open; absence of a direct declaration never means unused.

## Executed checks

The [JGridShift probe](../verification/java-source-jgridshift-result.json) compiled
all four recovered 1.3 core sources using the verified retained JDK, with annotation
processing disabled and Internet socket creation denied. Public API output matches
the selected binary. Fresh probe 02 verified every completed denial receipt and
unchanged source hashes. The historical core tree has no test sources; no native
test or numeric/grid acceptance is claimed. Earlier probe 01 is preserved.

**174 Java tooling tests**, **175 package tests**, and **four strict schema/example
checks** passed without failures or skips in their final runs. The initial host
Python package run skipped seven jsonschema-dependent cases; its output is retained
and the full suite was rerun in the existing validation venv. Source verification
returns **2**, correctly reporting the remaining partial/unresolved inputs. Initial
relative-path, source-attribute and archive-name parsing failures and their fixes
are preserved in custody, along with failed acquisitions. These checks are separate
from GeoTools/GeoFence/MapFish/JavaCSV/Huldra compilation and native tests recorded
in the broader compatibility checkpoint, and from GIS release acceptance.

## Per-coordinate accounting

The last column is mapped source classes + explicitly mapped generation-input
classes / binary classes. "Source candidate" is structural inventory coverage.

| Exact coordinate | Selected-use evidence | Source accounting |
|---|---|---|
| `antlr:antlr:2.7.7` | Test JVM: model, persistence, persistence-pg-test | Source/generation inputs (224+0/224) |
| `asm:asm:3.2` | Plugin acquisition; runtime unproven | Source candidate (23+0/23) |
| `asm:asm:3.3.1` | Plugin acquisition; runtime unproven | Source candidate (23+0/23) |
| `asm:asm-commons:3.2` | Plugin acquisition; runtime unproven | Source candidate (22+0/22) |
| `asm:asm-tree:3.2` | Plugin acquisition; runtime unproven | Source candidate (28+0/28) |
| `biz.aQute:bndlib:0.0.145` | Plugin acquisition; runtime unproven | Embedded sources (19+0/19) |
| `classworlds:classworlds:1.1-alpha-2` | Plugin acquisition; runtime unproven | Unresolved (0+0/22) |
| `com.google.code.findbugs:jsr305:1.3.9` | Plugin acquisition; runtime unproven | Embedded sources (35+0/35) |
| `com.google.code.findbugs:jsr305:2.0.0` | Plugin acquisition; runtime unproven | Embedded sources (34+0/34) |
| `com.google.code.findbugs:jsr305:2.0.1` | Plugin acquisition; runtime unproven | Embedded sources (34+0/34) |
| `com.google.code.typica:typica:1.3` | Transitive/declaration evidence; runtime unproven | Unresolved (0+0/296) |
| `com.google.guava:listenablefuture:9999.0-empty-to-avoid-conflict-with-guava` | Test JVM: persistence, persistence-pg-test, referencing | Metadata only (0+0/0) |
| `com.h2database:h2:1.1.119` | Declared compile, test | Source candidate (470+0/470) |
| `com.jcraft:jsch:0.1.23` | Plugin acquisition; runtime unproven | Source candidate (90+0/90) |
| `com.jcraft:jsch:0.1.38` | Plugin acquisition; runtime unproven | Source candidate (110+0/110) |
| `com.vladsch.flexmark:flexmark-all:0.42.14` | Plugin acquisition; runtime unproven | Metadata only (0+0/0) |
| `commons-codec:commons-codec:1.2` | Plugin acquisition; runtime unproven | Partial (18+0/19) |
| `commons-dbcp:commons-dbcp:1.2.2` | Test JVM: persistence, persistence-pg-test | Source candidate (51+0/51) |
| `commons-lang:commons-lang:1.0` | Plugin acquisition; runtime unproven | Source candidate (35+0/35) |
| `commons-logging:commons-logging-api:1.0.4` | Plugin acquisition; runtime unproven | Source candidate (13+0/13) |
| `de.zeigermann.xml:xml-im-exporter:1.1` | Transitive/declaration evidence; runtime unproven | Source candidate (15+0/15) |
| `dom4j:dom4j:1.1` | Plugin acquisition; runtime unproven | Unresolved (0+0/333) |
| `doxia:doxia-core:1.0-alpha-4` | Plugin acquisition; runtime unproven | Source candidate (140+0/140) |
| `doxia:doxia-sink-api:1.0-alpha-4` | Plugin acquisition; runtime unproven | Source candidate (2+0/2) |
| `geronimo-spec:geronimo-spec-jta:1.0.1B-rc4` | Plugin acquisition; runtime unproven | Unresolved (0+0/17) |
| `jakarta-regexp:jakarta-regexp:1.4` | Plugin acquisition; runtime unproven | Source candidate (17+0/17) |
| `jline:jline:0.9.1` | Plugin acquisition; runtime unproven | Source candidate (32+0/32) |
| `nekohtml:xercesMinimal:1.9.6.2` | Plugin acquisition; runtime unproven | Source candidate (42+0/42) |
| `net.sourceforge.javacsv:javacsv:2.0` | Test JVM: referencing | Source candidate (12+0/12) |
| `org.apache.ant:ant:1.8.1` | Plugin acquisition; runtime unproven | Source candidate (873+0/873) |
| `org.apache.ant:ant-launcher:1.8.1` | Plugin acquisition; runtime unproven | Source candidate (5+0/5) |
| `org.apache.ant:ant-nodeps:1.8.1` | Plugin acquisition; runtime unproven | Source candidate (205+0/205) |
| `org.apache.bcel:bcel:5.2` | Plugin acquisition; runtime unproven | Source candidate (383+0/383) |
| `org.apache.servicemix.bundles:org.apache.servicemix.bundles.antlr:2.7.7_5` | Plugin acquisition; runtime unproven | Source/generation inputs (224+0/224) |
| `org.apache.velocity:velocity:1.5` | Plugin acquisition; runtime unproven | Source candidate (246+0/246) |
| `org.apache.velocity:velocity-tools:2.0` | Plugin acquisition; runtime unproven | Source candidate (187+0/187) |
| `org.aspectj:aspectjrt:1.5.4` | Test JVM: persistence, persistence-pg-test | Source candidate (127+0/127) |
| `org.aspectj:aspectjweaver:1.5.4` | Test JVM: persistence, persistence-pg-test | Partial (1088+0/1093) |
| `org.codehaus.plexus:plexus-i18n:1.0-beta-10` | Plugin acquisition; runtime unproven | Source candidate (7+0/7) |
| `org.codehaus.plexus:plexus-interactivity-jline:1.0-alpha-5` | Plugin acquisition; runtime unproven | Source candidate (1+0/1) |
| `org.eclipse.core:resources:3.3.0-v20070604` | Plugin acquisition; runtime unproven | Source candidate (330+0/330) |
| `org.eclipse.jdt:core:3.1.1` | Plugin acquisition; runtime unproven | Source candidate (1256+0/1256) |
| `org.netbeans.lib:cvsclient:20060125` | Plugin acquisition; runtime unproven | Unresolved (0+0/221) |
| `org.sonatype.sisu:sisu-inject-plexus:2.1.1` | Plugin acquisition; runtime unproven | Unresolved (0+0/160) |
| `oro:oro:2.0.7` | Plugin acquisition; runtime unproven | Source candidate (62+0/62) |
| `picocontainer:picocontainer:1.2` | Declared compile | Source candidate (101+0/101) |
| `plexus:plexus-utils:1.0.3` | Plugin acquisition; runtime unproven | Unresolved (0+0/67) |
| `postgresql:postgresql:8.3-603.jdbc4` | Transitive/declaration evidence; runtime unproven | Source/generation inputs (176+13/189) |
| `regexp:regexp:1.2` | Transitive/declaration evidence; runtime unproven | Source candidate (16+0/16) |
| `velocity:velocity:1.5` | Plugin acquisition; runtime unproven | Source candidate (246+0/246) |
| `xerces:xercesImpl:2.7.1` | Declared compile | Source candidate (870+0/870) |
| `xerces:xercesImpl:2.9.1` | Plugin acquisition; runtime unproven | Source candidate (894+0/894) |
| `xml-apis:xml-apis-ext:1.3.04` | Transitive/declaration evidence; runtime unproven | Source candidate (192+0/192) |
| `xmlpull:xmlpull:1.1.3.1` | Transitive/declaration evidence; runtime unproven | Unresolved (0+0/4) |
| `com.oracle:ojdbc14:10.2.0.3.0` | Declared provided | Unresolved (0+0/624) |
| `it.geosolutions.jgridshift:jgridshift-core:1.3` | Test JVM: referencing, xml | Source candidate (4+0/4) |
| `javax.media:jai_imageio:1.1` | Declared compile | Unresolved (0+0/559) |
| `net.sf.json-lib:json-lib:2.4.2-geoserver` | Declared compile | Unresolved (0+0/83) |
| `net.sourceforge.groboutils:groboutils-core:5` | Declared test | Partial (388+0/1006) |
| `opendap:opendap:2.1` | Declared compile | Unresolved (0+0/257) |
| `org.apache.xml:xml-commons-resolver:1.2` | Test JVM: xml | Source candidate (30+0/30) |
| `org.huldra.math:bigint:0.7.1` | Transitive/declaration evidence; runtime unproven | Source candidate (4+0/4) |
| `org.marlin:marlin:0.9.4.8` | Declared compile | Partial (85+0/87) |
| `org.opengeo:geodb:0.9` | Test JVM: persistence | Source candidate (8+0/8) |
