/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import javax.servlet.*;
import javax.servlet.http.*;

/** Mandatory engine boundary. No cached grants or inherited admin routes. */
public final class CatalogPolicyFilter implements Filter {
    private final String origin;
    private final String key;
    public CatalogPolicyFilter() throws Exception {
        origin = System.getProperty("ambisgis.catalog.origin");
        if (origin == null || !origin.matches("http://127\\.0\\.0\\.1:[0-9]{1,5}"))
            throw new IllegalArgumentException("explicit loopback catalog origin required");
        key = Files.readString(Path.of(System.getProperty("ambisgis.catalog.keyFile"))).trim();
        if (!key.matches("[A-Za-z0-9_-]{32,128}")) throw new IllegalArgumentException("invalid service credential");
    }
    private String resource(HttpServletRequest request) {
        if (!request.getMethod().equals("GET") || !request.getRequestURI().equals("/geoserver/wfs")) return null;
        String query = request.getQueryString();
        if (query == null || query.length() > 2048) return null;
        Map<String,String> fields = new HashMap<>();
        for (String pair : query.split("&", -1)) {
            String[] parts = pair.split("=", 2);
            if (parts.length != 2) return null;
            String name = URLDecoder.decode(parts[0], StandardCharsets.UTF_8).toLowerCase(java.util.Locale.ROOT);
            String value = URLDecoder.decode(parts[1], StandardCharsets.UTF_8);
            if (fields.putIfAbsent(name, value) != null) return null;
        }
        if (!fields.keySet().equals(Set.of("service", "version", "request", "typename", "outputformat"))) return null;
        if (!"WFS".equals(fields.get("service")) || !"1.0.0".equals(fields.get("version"))
                || !"GetFeature".equals(fields.get("request")) || !"application/json".equals(fields.get("outputformat"))) return null;
        String name = fields.get("typename");
        return name.matches("fixture:[a-z_]{1,64}") ? name : null;
    }
    public void doFilter(ServletRequest input, ServletResponse output, FilterChain chain) throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) input;
        HttpServletResponse response = (HttpServletResponse) output;
        response.setHeader("Cache-Control", "no-store");
        boolean allowed = false;
        HttpURLConnection connection = null;
        try {
            String name = resource(request);
            if (java.util.Collections.list(request.getHeaders("Authorization")).size() > 1) name = null;
            if (name != null) {
                connection = (HttpURLConnection) new URL(origin + "/internal/policy/read").openConnection();
                connection.setConnectTimeout(1500); connection.setReadTimeout(1500);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("X-AmbisGIS-Policy-Key", key);
                connection.setRequestProperty("X-AmbisGIS-Resource", name);
                String auth = request.getHeader("Authorization");
                if (auth != null) connection.setRequestProperty("Authorization", auth);
                allowed = connection.getResponseCode() == 204 && connection.getHeaderField("Location") == null;
            }
        } catch (Exception denied) { /* Fail closed; no response or credential reflection. */ }
        finally { if (connection != null) connection.disconnect(); }
        if (allowed) chain.doFilter(input, output);
        else { response.setStatus(403); response.setContentLength(0); }
    }
}
