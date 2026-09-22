/* Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0 */
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;

/** Verifies runtime defining JAR and loaded resource bytes against the selected WAR. */
public final class ClassOriginWitness {
    public static void main(String[] args) throws Exception {
        if (args.length == 0 || args.length % 3 != 0) throw new AssertionError("missing origin triples");
        for (int i = 0; i < args.length; i += 3) {
            Class<?> type = Class.forName(args[i], false, ClassOriginWitness.class.getClassLoader());
            Path expected = Path.of(args[i + 1]).toRealPath();
            Path actual = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
            if (!actual.equals(expected)) throw new AssertionError("wrong class origin: " + type.getName() + " " + actual);
            String resource = "/" + type.getName().replace('.', '/') + ".class";
            String digest;
            try (var stream = type.getResourceAsStream(resource)) {
                if (stream == null) throw new AssertionError("class resource missing: " + resource);
                digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes()));
            }
            if (!digest.equals(args[i + 2])) throw new AssertionError("wrong class bytes: " + type.getName());
            System.out.println("class_origin=" + type.getName() + " jar=" + actual + " sha256=" + digest);
        }
    }
}
