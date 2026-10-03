/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.*;
import javax.servlet.*;
import javax.servlet.http.*;

/** Mandatory, finite WMS engine profile using the existing native catalog. */
public final class CatalogMapPolicyFilter implements Filter {
    private final String origin;
    private final String key;
    private final Map<String,List<String[]>> assets = new HashMap<>();
    private static final Map<String,String> FIELDS = Map.of(
        "service", "WMS", "version", "1.1.1", "request", "GetMap", "styles", "",
        "srs", "EPSG:4326", "bbox", "0,0,4,4", "width", "512", "height", "512",
        "format", "image/png", "transparent", "FALSE");
    private static String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    public CatalogMapPolicyFilter() throws Exception {
        origin = System.getProperty("ambisgis.catalog.origin");
        if (origin == null || !origin.matches("http://127\\.0\\.0\\.1:[0-9]{1,5}")) throw new IllegalArgumentException("catalog origin required");
        key = Files.readString(Path.of(System.getProperty("ambisgis.catalog.keyFile"))).trim();
        if (!key.matches("[A-Za-z0-9_-]{32,128}")) throw new IllegalArgumentException("service credential required");
        byte[] bytes = Files.readAllBytes(Path.of(System.getProperty("ambisgis.maps.bindings")));
        if (!sha(bytes).equals(System.getProperty("ambisgis.maps.bindingsSha256"))) throw new IllegalArgumentException("bindings changed");
        for (String line : new String(bytes, StandardCharsets.UTF_8).split("\n")) {
            String[] row = line.split("\t", -1);
            if (row.length != 3 || !row[0].matches("fixture:[a-z][a-z_]{0,63}") || !Path.of(row[1]).isAbsolute()
                    || !row[2].matches("[0-9a-f]{64}")) throw new IllegalArgumentException("invalid asset binding");
            assets.computeIfAbsent(row[0], ignored -> new ArrayList<>()).add(row);
        }
        if (assets.isEmpty() || assets.size() > 16) throw new IllegalArgumentException("invalid asset set");
    }
    private String resource(HttpServletRequest request) {
        if (!request.getMethod().equals("GET") || !request.getRequestURI().equals("/geoserver/wms")) return null;
        String query = request.getQueryString(); if (query == null || query.length() > 2048) return null;
        Map<String,String> fields = new HashMap<>();
        for (String pair : query.split("&", -1)) {
            String[] parts = pair.split("=", 2); if (parts.length != 2) return null;
            String name = URLDecoder.decode(parts[0], StandardCharsets.UTF_8).toLowerCase(Locale.ROOT);
            if (fields.putIfAbsent(name, URLDecoder.decode(parts[1], StandardCharsets.UTF_8)) != null) return null;
        }
        Set<String> keys = new HashSet<>(FIELDS.keySet()); keys.add("layers");
        if (!fields.keySet().equals(keys)) return null;
        for (var entry : FIELDS.entrySet()) if (!entry.getValue().equals(fields.get(entry.getKey()))) return null;
        String name = fields.get("layers"); return assets.containsKey(name) ? name : null;
    }
    private boolean intact(String name) throws Exception {
        for (String[] row : assets.get(name)) {
            Path path = Path.of(row[1]);
            for (Path p = path; p != null; p = p.getParent()) if (Files.isSymbolicLink(p)) return false;
            if (!Files.isRegularFile(path) || Files.size(path) > 32 * 1024 * 1024 || !sha(Files.readAllBytes(path)).equals(row[2])) return false;
        }
        return true;
    }
    public void doFilter(ServletRequest input, ServletResponse output, FilterChain chain) throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) input;
        HttpServletResponse response = (HttpServletResponse) output;
        response.setHeader("Cache-Control", "no-store"); boolean allowed = false;
        HttpURLConnection connection = null;
        try {
            String name = resource(request);
            if (Collections.list(request.getHeaders("Authorization")).size() > 1) name = null;
            if (name != null && intact(name)) {
                connection = (HttpURLConnection) new URL(origin + "/internal/policy/read").openConnection();
                connection.setConnectTimeout(1500); connection.setReadTimeout(1500); connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("X-AmbisGIS-Policy-Key", key); connection.setRequestProperty("X-AmbisGIS-Resource", name);
                if (request.getHeader("Authorization") != null) connection.setRequestProperty("Authorization", request.getHeader("Authorization"));
                allowed = connection.getResponseCode() == 204 && connection.getHeaderField("Location") == null;
            }
        } catch (Exception denied) { /* Empty denial; never reflect data or credentials. */ }
        finally { if (connection != null) connection.disconnect(); }
        if (allowed) chain.doFilter(input, output);
        else { response.setStatus(403); response.setContentLength(0); }
    }
}
