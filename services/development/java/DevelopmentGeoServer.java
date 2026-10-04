/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.InputStream;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import javax.servlet.DispatcherType;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.ServerConnector;
import org.eclipse.jetty.server.handler.AbstractHandler;
import org.eclipse.jetty.server.handler.HandlerList;
import org.eclipse.jetty.servlet.FilterHolder;
import org.eclipse.jetty.util.thread.QueuedThreadPool;
import org.eclipse.jetty.webapp.WebAppContext;

/** Persistent developer application; all engines load from the exact retained WAR. */
public final class DevelopmentGeoServer {
    private static void transport(ClassLoader loader, boolean initialize) throws Exception {
        Class<?> extensions = loader.loadClass("org.geoserver.platform.GeoServerExtensions");
        Class<?> api = loader.loadClass("org.geoserver.geofence.services.RuleAdminService");
        Class<?> ruleType = loader.loadClass("org.geoserver.geofence.core.model.Rule");
        Class<?> grantType = loader.loadClass("org.geoserver.geofence.core.model.enums.GrantType");
        Object service = extensions.getMethod("bean", Class.class).invoke(null, api);
        long count = (Long) api.getMethod("getCountAll").invoke(service);
        // Never repair/overwrite an unexpected independently edited transport policy.
        if (count == 0 && initialize) {
            for (String[] row : List.of(new String[]{"10", "WMS", "GETMAP"}, new String[]{"20", "WFS", "GETFEATURE"})) {
                Object rule = ruleType.getConstructor().newInstance();
                ruleType.getMethod("setPriority", long.class).invoke(rule, Long.parseLong(row[0]));
                ruleType.getMethod("setWorkspace", String.class).invoke(rule, "fixture");
                ruleType.getMethod("setLayer", String.class).invoke(rule, "private_points");
                ruleType.getMethod("setService", String.class).invoke(rule, row[1]);
                ruleType.getMethod("setRequest", String.class).invoke(rule, row[2]);
                Object allow = grantType.getField("ALLOW").get(null);
                ruleType.getMethod("setAccess", grantType).invoke(rule, allow);
                api.getMethod("insert", ruleType).invoke(service, rule);
            }
        }
        if ((Long) api.getMethod("getCountAll").invoke(service) != 2L)
            throw new IllegalStateException("unexpected transport rule count");
        for (String[] row : List.of(new String[]{"10", "WMS", "GETMAP"}, new String[]{"20", "WFS", "GETFEATURE"})) {
            Object summary = api.getMethod("getRuleByPriority", long.class).invoke(service, Long.parseLong(row[0]));
            if (summary == null) throw new IllegalStateException("missing transport rule");
            long id = (Long) summary.getClass().getMethod("getId").invoke(summary);
            Object rule = api.getMethod("get", long.class).invoke(service, id);
            for (var pair : Map.of("getWorkspace", "fixture", "getLayer", "private_points",
                    "getService", row[1], "getRequest", row[2]).entrySet()) {
                if (!pair.getValue().equals(ruleType.getMethod(pair.getKey()).invoke(rule)))
                    throw new IllegalStateException("transport projection changed");
            }
            if (!"ALLOW".equals(String.valueOf(ruleType.getMethod("getAccess").invoke(rule))))
                throw new IllegalStateException("transport projection changed");
            for (String getter : List.of("getUsername", "getRolename", "getInstance", "getAddressRange",
                    "getValidAfter", "getValidBefore", "getSubfield", "getRuleLimits", "getLayerDetails"))
                if (ruleType.getMethod(getter).invoke(rule) != null)
                    throw new IllegalStateException("unexpected transport policy field");
        }
    }

    private static String hash(Path path) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream stream = Files.newInputStream(path)) {
            byte[] buffer = new byte[65536]; int count;
            while ((count = stream.read(buffer)) > 0) digest.update(buffer, 0, count);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 1 || !Set.of("initialize", "serve").contains(arguments[0]))
            throw new IllegalArgumentException("one fixed mode required");
        boolean initialize = arguments[0].equals("initialize");
        Path state = Path.of("/tmp/ambisgis-engine");
        Properties config = new Properties();
        try (InputStream stream = Files.newInputStream(state.resolve("launch.properties"))) { config.load(stream); }
        String install = config.getProperty("install_id");
        if (!UUID.fromString(install).toString().equals(install)) throw new IllegalArgumentException("invalid install id");
        String key = config.getProperty("policy_key");
        Map<Path, String> assets = new HashMap<>();
        for (String line : Files.readAllLines(state.resolve("assets.tsv"))) {
            String[] row = line.split("\t", -1);
            if (row.length != 2 || !Set.of("/var/lib/ambisgis/assets/private_points.properties",
                    "/var/lib/ambisgis/assets/diagnostic.sld", "/tmp/ambisgis-engine/data/styles/diagnostic.sld").contains(row[0])
                    || !row[1].matches("[0-9a-f]{64}"))
                throw new IllegalArgumentException("invalid diagnostic asset binding");
            assets.put(Path.of(row[0]), row[1]);
        }
        if (assets.size() != 3) throw new IllegalArgumentException("missing diagnostic asset binding");
        Path war = Path.of("/opt/ambisgis/geoserver/application.war");
        if (!hash(war).equals(config.getProperty("war_sha256"))) throw new IllegalStateException("owned WAR changed");
        Path data = state.resolve("data");
        System.setProperty("GEOSERVER_DATA_DIR", data.toString());
        System.setProperty("GEOSERVER_REQUIRE_FILE", data.resolve(".ambisgis-derived").toString());
        System.setProperty("java.awt.headless", "true");
        DevelopmentCatalogFilter policy = new DevelopmentCatalogFilter(key, assets);
        Server server = new Server(new QueuedThreadPool(16, 4));
        server.setStopAtShutdown(true); server.setStopTimeout(10000);
        ServerConnector connector = new ServerConnector(server, 1, 1);
        connector.setHost(initialize ? "127.0.0.1" : "0.0.0.0"); connector.setPort(8080);
        server.addConnector(connector);
        WebAppContext app = new WebAppContext();
        app.setContextPath("/geoserver"); app.setWar(war.toString()); app.setExtractWAR(true);
        app.setTempDirectory(Files.createDirectory(state.resolve("webapp")).toFile());
        app.setPersistTempDirectory(false); app.setParentLoaderPriority(false);
        app.setThrowUnavailableOnStartupException(true);
        app.setInitParameter("GEOSERVER_DATA_DIR", data.toString());
        app.addFilter(new FilterHolder(policy), "/*", EnumSet.allOf(DispatcherType.class));
        AbstractHandler health = new AbstractHandler() {
            public void handle(String target, org.eclipse.jetty.server.Request base,
                    javax.servlet.http.HttpServletRequest request, javax.servlet.http.HttpServletResponse response)
                    throws java.io.IOException {
                if (!target.equals("/health/live")) return;
                base.setHandled(true); response.setHeader("Cache-Control", "no-store");
                List<String> supplied = Collections.list(request.getHeaders("X-AmbisGIS-Policy-Key"));
                if (!request.getMethod().equals("GET") || request.getQueryString() != null || supplied.size() != 1
                        || !MessageDigest.isEqual(key.getBytes(java.nio.charset.StandardCharsets.US_ASCII),
                            supplied.get(0).getBytes(java.nio.charset.StandardCharsets.US_ASCII))) {
                    response.setStatus(403); response.setContentLength(0); return;
                }
                response.setStatus(policy.isReady() ? 200 : 503); response.setContentType("application/json");
                response.getWriter().write("{\"install_id\":\"" + install + "\",\"application\":" + policy.isReady() + "}");
            }
        };
        server.setHandler(new HandlerList(health, app));
        try {
            server.start();
            if (!app.isAvailable() || app.getUnavailableException() != null) throw new IllegalStateException("native engine unavailable");
            Path extracted = app.getBaseResource().getFile().toPath().toRealPath();
            if (!extracted.startsWith(state.resolve("webapp").toRealPath())) throw new IllegalStateException("external exploded WAR reused");
            ClassLoader loader = app.getClassLoader();
            Thread.currentThread().setContextClassLoader(loader);
            transport(loader, initialize);
            if (!hash(war).equals(config.getProperty("war_sha256"))) throw new IllegalStateException("owned WAR changed during start");
            if (initialize) {
                Files.writeString(state.resolve("initialized"), install, StandardOpenOption.CREATE_NEW);
            } else {
                policy.activate();
                System.out.println("AMBISGIS_ENGINE_READY install_id=" + install);
                server.join();
            }
        } finally { server.stop(); }
    }
}
