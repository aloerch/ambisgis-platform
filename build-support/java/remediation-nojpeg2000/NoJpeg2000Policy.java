/* Authored for the AmbisGIS NO-JPEG2000 Java/server candidate, 2026.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
package org.geoserver.filters;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Stream;

/** Candidate capability policy; this class never decodes or converts an image. */
public final class NoJpeg2000Policy {
    public static final String MESSAGE =
            "JPEG2000 is unsupported in the AmbisGIS NO-JPEG2000 Java/server profile.";
    private static final Set<String> FORMATS = Set.of(
            "jp2", "j2k", "j2c", "jpc", "jpf", "jpx", "jpeg2000", "jpeg 2000", "jpeg-2000",
            "image/jp2", "image/j2k", "image/j2c", "image/jpc", "image/jpx", "image/jpeg2000", "image/x-jp2");
    private NoJpeg2000Policy() {}

    public static boolean format(String value) {
        if (value == null) return false;
        return FORMATS.contains(value.split(";", 2)[0].trim().toLowerCase(Locale.ROOT));
    }

    public static boolean filename(String value) {
        if (value == null) return false;
        int dot = value.lastIndexOf('.');
        return dot >= 0 && format(value.substring(dot + 1));
    }

    /** ISO/IEC 15444 signature box or JPEG2000 SOC followed by SIZ; ordinary JPEG differs. */
    public static boolean signature(byte[] value) {
        return value.length >= 4 && ((value[0] & 255) == 255 && (value[1] & 255) == 79
                && (value[2] & 255) == 255 && (value[3] & 255) == 81)
                || value.length >= 12 && value[0] == 0 && value[1] == 0 && value[2] == 0 && value[3] == 12
                && value[4] == 106 && value[5] == 80 && value[6] == 32 && value[7] == 32
                && value[8] == 13 && value[9] == 10 && (value[10] & 255) == 135 && value[11] == 10;
    }

    public static boolean file(Path path) throws IOException {
        if (filename(path.getFileName().toString())) return true;
        try (InputStream input = Files.newInputStream(path)) { return signature(input.readNBytes(12)); }
    }

    /** Inspects only names and twelve signature bytes, without following directory symlinks. */
    public static boolean tree(Path path) throws IOException {
        if (!Files.isDirectory(path)) return file(path);
        try (Stream<Path> files = Files.walk(path)) {
            var iterator = files.filter(Files::isRegularFile).iterator();
            while (iterator.hasNext()) if (file(iterator.next())) return true;
        }
        return false;
    }
}
