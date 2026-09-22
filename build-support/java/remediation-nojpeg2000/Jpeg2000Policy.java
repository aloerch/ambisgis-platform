/* Copyright 2026 AmbisGIS contributors. SPDX-License-Identifier: Apache-2.0 */
package org.mapfish.print;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.util.Locale;
import com.lowagie.text.BadElementException;
import com.lowagie.text.Image;
import com.lowagie.text.Utilities;

/** The selected Java/server profile intentionally has no JPEG2000 capability. */
public final class Jpeg2000Policy {
    public static final String MESSAGE =
        "JPEG2000 is unsupported in the AmbisGIS NO-JPEG2000 Java/server profile.";
    public static final int MAX_IMAGE_BYTES = 64 * 1024 * 1024;
    public static final int URL_TIMEOUT_MILLIS = 30000;
    public static final String LIMIT_MESSAGE = "Print image exceeds the 64 MiB input limit.";
    private Jpeg2000Policy() { }

    public static final class InputLimit extends IllegalArgumentException {
        private static final long serialVersionUID = 1L;
        public InputLimit() { super(LIMIT_MESSAGE); }
    }

    private static Throwable nestedFailure(Throwable failure) {
        // OpenPDF ExceptionConverter predates chained exceptions and exposes
        // getException() instead of setting Throwable.getCause().
        if (failure instanceof com.lowagie.text.ExceptionConverter)
            return ((com.lowagie.text.ExceptionConverter)failure).getException();
        return failure.getCause();
    }

    public static boolean isLimit(Throwable failure) {
        for (int i = 0; failure != null && i < 32; i++, failure = nestedFailure(failure)) {
            if (failure instanceof InputLimit) return true;
        }
        return false;
    }

    public static final class UnsupportedFormat extends IllegalArgumentException {
        private static final long serialVersionUID = 1L;
        public UnsupportedFormat() { super(MESSAGE); }
    }

    public static boolean isUnsupported(Throwable failure) {
        // Bounded traversal also tolerates adversarial cyclic exception causes.
        for (int i = 0; failure != null && i < 32; i++, failure = nestedFailure(failure)) {
            if (failure instanceof UnsupportedFormat) return true;
        }
        return false;
    }

    public static void checkOutput(String format) {
        if (format == null) return;
        String value = format.trim().toLowerCase(Locale.ROOT);
        int parameter = value.indexOf(';');
        if (parameter >= 0) value = value.substring(0, parameter).trim();
        if (value.startsWith("image/")) value = value.substring(6);
        if (value.startsWith("x-")) value = value.substring(2);
        value = value.replace(" ", "").replace("-", "").replace("_", "");
        if (value.equals("jp2") || value.equals("j2k") || value.equals("j2c")
                || value.equals("jpc") || value.equals("jpf") || value.equals("jpx") || value.equals("jpm")
                || value.equals("mj2") || value.equals("jpeg2000")
                || value.equals("jpeg-2000") || value.equals("x-jpeg2000")) {
            throw new UnsupportedFormat();
        }
    }

    public static void checkContent(byte[] bytes) {
        // SOC identifies a raw JPEG2000 codestream, including truncated streams.
        boolean codestream = bytes.length >= 2 && (bytes[0] & 255) == 255
                && (bytes[1] & 255) == 79;
        // JPEG2000 family signature box; filename/MIME cannot bypass this check.
        boolean container = bytes.length >= 8 && bytes[0] == 0 && bytes[1] == 0
                && bytes[2] == 0 && bytes[3] == 12 && bytes[4] == 'j'
                && bytes[5] == 'P' && bytes[6] == ' ' && bytes[7] == ' ';
        if (codestream || container) throw new UnsupportedFormat();
    }

    public static Image load(byte[] bytes) throws BadElementException, IOException {
        checkContent(bytes);
        if (bytes.length > MAX_IMAGE_BYTES) throw new InputLimit();
        return Image.getInstance(bytes);
    }

    public static Image load(String filename) throws BadElementException, IOException {
        return load(Utilities.toURL(filename));
    }

    public static byte[] readBounded(InputStream input) throws IOException {
        long deadline = System.nanoTime() + URL_TIMEOUT_MILLIS * 1000000L;
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = input.read(buffer)) != -1) {
            if (System.nanoTime() > deadline) throw new java.net.SocketTimeoutException("Print image read timed out.");
            if ((long) bytes.size() + read > MAX_IMAGE_BYTES) throw new InputLimit();
            bytes.write(buffer, 0, read);
        }
        return bytes.toByteArray();
    }

    public static void checkPdf(com.lowagie.text.pdf.PdfReader reader) {
        // Resolve PDF filter names through the parser, including indirect objects
        // and arrays; string searching cannot safely identify compressed objects.
        for (int i = 0; i < reader.getXrefSize(); i++) {
            com.lowagie.text.pdf.PdfObject object = reader.getPdfObject(i);
            if (!(object instanceof com.lowagie.text.pdf.PdfDictionary)) continue;
            com.lowagie.text.pdf.PdfObject filter = com.lowagie.text.pdf.PdfReader.getPdfObject(
                ((com.lowagie.text.pdf.PdfDictionary)object).get(com.lowagie.text.pdf.PdfName.FILTER));
            if (com.lowagie.text.pdf.PdfName.JPXDECODE.equals(filter)) throw new UnsupportedFormat();
            if (filter instanceof com.lowagie.text.pdf.PdfArray) {
                com.lowagie.text.pdf.PdfArray filters = (com.lowagie.text.pdf.PdfArray) filter;
                for (int n = 0; n < filters.size(); n++) {
                    if (com.lowagie.text.pdf.PdfName.JPXDECODE.equals(filters.getDirectObject(n)))
                        throw new UnsupportedFormat();
                }
            }
        }
    }

    public static com.lowagie.text.pdf.PdfReader loadPdf(String filename) throws IOException {
        java.net.URLConnection connection = Utilities.toURL(filename).openConnection();
        connection.setConnectTimeout(URL_TIMEOUT_MILLIS);
        connection.setReadTimeout(URL_TIMEOUT_MILLIS);
        if (connection.getContentLengthLong() > MAX_IMAGE_BYTES) throw new InputLimit();
        try (InputStream input = connection.getInputStream()) {
            com.lowagie.text.pdf.PdfReader reader = new com.lowagie.text.pdf.PdfReader(readBounded(input));
            try { checkPdf(reader); return reader; }
            catch (RuntimeException failure) { reader.close(); throw failure; }
        }
    }

    public static Image load(URL url) throws BadElementException, IOException {
        // One read: changing a name or racing a second fetch cannot bypass checks.
        java.net.URLConnection connection = url.openConnection();
        connection.setConnectTimeout(URL_TIMEOUT_MILLIS);
        connection.setReadTimeout(URL_TIMEOUT_MILLIS);
        if (connection.getContentLengthLong() > MAX_IMAGE_BYTES) throw new InputLimit();
        try (InputStream input = connection.getInputStream()) {
            Image image = load(readBounded(input));
            image.setUrl(url);
            return image;
        }
    }
}
