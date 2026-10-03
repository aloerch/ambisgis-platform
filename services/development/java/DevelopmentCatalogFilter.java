/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.*;
import javax.servlet.*;
import javax.servlet.http.*;

/** Mandatory per-request native catalog decision, including direct engine calls. */
public final class DevelopmentCatalogFilter implements Filter {
    private final String key;
    private final Map<Path, String> assets;
    private volatile boolean ready;
    private static final String SAMPLE = "fixture:private_points";
    private static final Map<String, String> WFS = Map.of("service", "WFS", "version", "1.0.0",
            "request", "GetFeature", "typename", SAMPLE, "outputformat", "application/json");
    private static final Map<String, String> WMS = Map.ofEntries(
            Map.entry("service", "WMS"), Map.entry("version", "1.1.1"), Map.entry("request", "GetMap"),
            Map.entry("layers", SAMPLE), Map.entry("styles", ""), Map.entry("srs", "EPSG:4326"),
            Map.entry("bbox", "0,0,4,4"), Map.entry("width", "512"), Map.entry("height", "512"),
            Map.entry("format", "image/png"), Map.entry("transparent", "FALSE"));

    public DevelopmentCatalogFilter(String key, Map<Path, String> assets) {
        if (!key.matches("[A-Za-z0-9_-]{40,128}") || assets.isEmpty())
            throw new IllegalArgumentException("explicit private policy key and assets required");
        this.key = key;
        this.assets = Map.copyOf(assets);
    }

    public void activate() { ready = true; }
    public boolean isReady() { return ready; }

    public static boolean supported(String method, String path, String query) {
        Map<String, String> expected = path.equals("/geoserver/wfs") ? WFS
                : path.equals("/geoserver/wms") ? WMS : null;
        if (!"GET".equals(method) || expected == null || query == null || query.length() > 2048) return false;
        try {
            Map<String, String> fields = new HashMap<>();
            for (String pair : query.split("&", -1)) {
                String[] parts = pair.split("=", 2);
                if (parts.length != 2) return false;
                String name = URLDecoder.decode(parts[0], StandardCharsets.UTF_8).toLowerCase(Locale.ROOT);
                if (fields.putIfAbsent(name, URLDecoder.decode(parts[1], StandardCharsets.UTF_8)) != null) return false;
            }
            return fields.equals(expected);
        } catch (IllegalArgumentException invalidEncoding) { return false; }
    }

    private boolean intact() throws Exception {
        for (var asset : assets.entrySet()) {
            Path path = asset.getKey();
            for (Path p = path; p != null; p = p.getParent()) if (Files.isSymbolicLink(p)) return false;
            if (!Files.isRegularFile(path) || Files.size(path) > 1048576) return false;
            String actual = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
            if (!actual.equals(asset.getValue())) return false;
        }
        return true;
    }

    public void doFilter(ServletRequest input, ServletResponse output, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) input;
        HttpServletResponse response = (HttpServletResponse) output;
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("X-Content-Type-Options", "nosniff");
        boolean allowed = false;
        HttpURLConnection connection = null;
        try {
            String authorization = request.getHeader("Authorization");
            if (ready && supported(request.getMethod(), request.getRequestURI(), request.getQueryString())
                    && Collections.list(request.getHeaders("Authorization")).size() == 1
                    && authorization != null && authorization.matches("Bearer [A-Za-z0-9._~-]{20,512}") && intact()) {
                // Fixed container DNS/origin, never a caller-controlled URI or redirect.
                connection = (HttpURLConnection) URI.create("http://catalog:8000/internal/policy/read").toURL().openConnection();
                connection.setConnectTimeout(1500);
                connection.setReadTimeout(1500);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("X-AmbisGIS-Policy-Key", key);
                connection.setRequestProperty("X-AmbisGIS-Resource", SAMPLE);
                connection.setRequestProperty("Authorization", authorization);
                allowed = connection.getResponseCode() == 204 && connection.getHeaderField("Location") == null;
            }
        } catch (Exception unavailable) { /* Fail closed without reflecting secrets/errors. */ }
        finally { if (connection != null) connection.disconnect(); }
        if (allowed) chain.doFilter(input, output);
        else { response.setStatus(403); response.setContentLength(0); }
    }
}
