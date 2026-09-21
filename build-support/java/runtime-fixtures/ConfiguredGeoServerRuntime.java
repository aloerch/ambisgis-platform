/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.io.File;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.net.URI;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HexFormat;
import java.util.List;
import java.util.zip.ZipFile;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.ServerConnector;
import org.eclipse.jetty.util.thread.QueuedThreadPool;
import org.eclipse.jetty.webapp.WebAppContext;

/** Trusted fixture launcher. All application classes/configuration come from the exact WAR. */
public final class ConfiguredGeoServerRuntime {
    private static String quote(String value) {
        StringBuilder result = new StringBuilder("\"");
        for (char c : value.toCharArray()) {
            if (c == '\\' || c == '"') result.append('\\').append(c);
            else if (c < 32) result.append(String.format("\\u%04x", (int)c));
            else result.append(c);
        }
        return result.append('"').toString();
    }

    private static String hash(Path file) throws Exception {
        try (InputStream input = Files.newInputStream(file)) {
            return hash(input);
        }
    }

    private static String hash(InputStream input) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[65536];
        int count;
        while ((count = input.read(buffer)) >= 0) hash.update(buffer, 0, count);
        return HexFormat.of().formatHex(hash.digest());
    }

    private static String origin(Class<?> type) {
        return type.getProtectionDomain().getCodeSource().getLocation().toString();
    }

    private static String inheritedContexts(Path war) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);
        try (ZipFile archive = new ZipFile(war.toFile());
                InputStream input = archive.getInputStream(archive.getEntry("WEB-INF/web.xml"))) {
            NodeList parameters = factory.newDocumentBuilder().parse(input).getElementsByTagName("context-param");
            String result = null;
            for (int i = 0; i < parameters.getLength(); i++) {
                Element parameter = (Element) parameters.item(i);
                if (parameter.getElementsByTagName("param-name").item(0).getTextContent().trim()
                        .equals("contextConfigLocation")) {
                    if (result != null) throw new IllegalArgumentException("duplicate inherited contexts");
                    result = parameter.getElementsByTagName("param-value").item(0).getTextContent().trim();
                }
            }
            if (result == null || result.isBlank()) throw new IllegalArgumentException("missing inherited contexts");
            return result;
        }
    }

    private static String xml(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    private static String strings(Object values) {
        List<String> result = new ArrayList<>();
        for (Object value : (Iterable<?>) values) result.add(quote(String.valueOf(value)));
        return "[" + String.join(",", result) + "]";
    }

    private static String securitySummary(ClassLoader loader, Class<?> extensions) throws Exception {
        Class<?> managerType = loader.loadClass("org.geoserver.security.GeoServerSecurityManager");
        Object manager = extensions.getMethod("bean", Class.class).invoke(null, managerType);
        Object oauthConfig = managerType.getMethod("loadFilterConfig", String.class, boolean.class)
                .invoke(manager, "fixture-oauth", true);
        if (oauthConfig == null) throw new IllegalStateException("configured OAuth filter is missing");
        Class<?> configType = oauthConfig.getClass();
        boolean stateless = false;
        boolean optionSupported = true;
        try {
            stateless = (Boolean) configType.getMethod("isStatelessBearerAuthentication").invoke(oauthConfig);
        } catch (NoSuchMethodException historical) {
            optionSupported = false;
        }
        Object securityConfig = managerType.getMethod("getSecurityConfig").invoke(manager);
        Object filterChain = securityConfig.getClass().getMethod("getFilterChain").invoke(securityConfig);
        Object chains = filterChain.getClass().getMethod("getRequestChains").invoke(filterChain);
        List<String> definitions = new ArrayList<>();
        for (Object chain : (Iterable<?>) chains) {
            Class<?> type = chain.getClass();
            definitions.add("{\"name\":" + quote(String.valueOf(type.getMethod("getName").invoke(chain)))
                    + ",\"patterns\":" + strings(type.getMethod("getPatterns").invoke(chain))
                    + ",\"filter_names\":" + strings(type.getMethod("getFilterNames").invoke(chain))
                    + ",\"compiled_filter_names\":" + strings(type.getMethod("getCompiledFilterNames").invoke(chain))
                    + ",\"allow_session_creation\":" + type.getMethod("isAllowSessionCreation").invoke(chain)
                    + ",\"disabled\":" + type.getMethod("isDisabled").invoke(chain) + "}");
        }
        return "{\"filter_config_class\":" + quote(configType.getName())
                + ",\"role_source\":" + quote(String.valueOf(configType.getMethod("getRoleSource").invoke(oauthConfig)))
                + ",\"user_group_service\":" + quote(String.valueOf(configType.getMethod("getUserGroupServiceName").invoke(oauthConfig)))
                + ",\"stateless_option_supported\":" + optionSupported
                + ",\"stateless_bearer_authentication\":" + stateless
                + ",\"chains\":[" + String.join(",", definitions) + "]}";
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 3 || args.length > 4)
            throw new IllegalArgumentException("WAR DATA_DIR NEW_RUNTIME_DIR [PORT]");
        Path war = Path.of(args[0]).toAbsolutePath();
        Path data = Path.of(args[1]).toRealPath();
        Path runtime = Path.of(args[2]).toAbsolutePath();
        if (!Files.isRegularFile(war, LinkOption.NOFOLLOW_LINKS) || !war.toString().endsWith(".war"))
            throw new IllegalArgumentException("require exact regular WAR file");
        for (String required : List.of("security/config.xml", ".ambisgis-configured-auth-fixture")) {
            if (!Files.isRegularFile(data.resolve(required), LinkOption.NOFOLLOW_LINKS))
                throw new IllegalArgumentException("require marked disposable configured data directory");
        }
        int port = args.length == 4 ? Integer.parseInt(args[3]) : 0;
        if (port < 0 || port > 65535) throw new IllegalArgumentException("invalid port");
        Files.createDirectory(runtime);
        Path temp = Files.createDirectory(runtime.resolve("webapp-temp"));
        String warHash = hash(war);
        Path deployedWar = Files.createDirectory(runtime.resolve("artifact")).resolve("application.war");
        Files.copy(war, deployedWar);
        if (!warHash.equals(hash(deployedWar))) throw new IllegalStateException("WAR staging changed bytes");
        System.setProperty("GEOSERVER_DATA_DIR", data.toString());
        System.setProperty("GEOSERVER_REQUIRE_FILE", data.resolve(".ambisgis-configured-auth-fixture").toString());
        System.setProperty("java.awt.headless", "true");
        QueuedThreadPool pool = new QueuedThreadPool(16, 4);
        pool.setName("ambisgis-fixture-worker");
        Server server = new Server(pool);
        server.setStopAtShutdown(true);
        server.setStopTimeout(10000);
        ServerConnector connector = new ServerConnector(server, 1, 1);
        connector.setHost("127.0.0.1");
        connector.setPort(port);
        server.addConnector(connector);
        Path requests = Files.createFile(runtime.resolve("requests.jsonl"));
        Object requestLogLock = new Object();
        server.setRequestLog((request, response) -> {
            String fixtureCase = request.getHeader("X-AmbisGIS-Fixture-Case");
            if (fixtureCase == null) return;
            if (!fixtureCase.matches("[A-Za-z0-9_./:-]{1,160}"))
                throw new IllegalArgumentException("unsafe fixture case identifier");
            String record = "{\"case\":" + quote(fixtureCase) + ",\"thread\":"
                    + quote(Thread.currentThread().getName()) + ",\"status\":" + response.getStatus() + "}\n";
            synchronized (requestLogLock) {
                try {
                    Files.writeString(requests, record, StandardOpenOption.APPEND);
                } catch (java.io.IOException failure) {
                    throw new IllegalStateException("fixture request audit write failed");
                }
            }
        });
        WebAppContext app = new WebAppContext();
        app.setContextPath("/geoserver");
        // Jetty otherwise may reuse Maven's sibling exploded geoserver/ directory.
        // The new artifact directory has no sibling application/; extraction starts from this exact WAR.
        app.setWar(deployedWar.toString());
        app.setExtractWAR(true);
        app.setTempDirectory(temp.toFile());
        app.setPersistTempDirectory(true);
        app.setParentLoaderPriority(false);
        app.setThrowUnavailableOnStartupException(true);
        app.setInitParameter("GEOSERVER_DATA_DIR", data.toString());
        Path fixtureContext = data.resolve("fixture-context.xml");
        if (Files.exists(fixtureContext, LinkOption.NOFOLLOW_LINKS)) {
            if (!Files.isRegularFile(fixtureContext, LinkOption.NOFOLLOW_LINKS))
                throw new IllegalArgumentException("fixture context must be a regular file");
            String contexts = inheritedContexts(war) + " " + fixtureContext.toUri();
            Path override = runtime.resolve("fixture-web-override.xml");
            String descriptor = "<web-app xmlns=\"http://xmlns.jcp.org/xml/ns/javaee\" version=\"3.1\">"
                    + "<context-param><param-name>contextConfigLocation</param-name><param-value>"
                    + xml(contexts) + "</param-value></context-param></web-app>";
            Files.writeString(override, descriptor, StandardOpenOption.CREATE_NEW);
            app.setOverrideDescriptor(override.toString());
        }
        server.setHandler(app);
        try {
            server.start();
            if (!app.isAvailable() || app.getUnavailableException() != null)
                throw new IllegalStateException("GeoServer web application unavailable", app.getUnavailableException());
            if (!warHash.equals(hash(war)) || !warHash.equals(hash(deployedWar)))
                throw new IllegalStateException("WAR changed during startup");
            Path webRoot = app.getBaseResource().getFile().toPath().toRealPath();
            if (!webRoot.startsWith(temp.toRealPath()))
                throw new IllegalStateException("Jetty reused an external exploded application");
            ClassLoader loader = app.getClassLoader();
            Thread.currentThread().setContextClassLoader(loader);
            Class<?> extensions = loader.loadClass("org.geoserver.platform.GeoServerExtensions");
            Class<?> resourceLoader = loader.loadClass("org.geoserver.platform.GeoServerResourceLoader");
            Object resources = extensions.getMethod("bean", Class.class).invoke(null, resourceLoader);
            File actual = (File) resourceLoader.getMethod("getBaseDirectory").invoke(resources);
            if (!actual.toPath().toRealPath().equals(data))
                throw new IllegalStateException("GeoServer activated an unexpected data directory");
            // Reflective diagnostics use the same context loader as servlet worker dispatch.
            Thread.currentThread().setContextClassLoader(loader);
            List<String> origins = new ArrayList<>();
            for (String name : List.of("org.geoserver.security.GeoServerSecurityManager",
                    "org.geoserver.security.auth.GuavaAuthenticationCacheImpl",
                    "org.geoserver.security.oauth2.GeoServerOAuth2FilterConfig",
                    "org.geoserver.security.oauth2.GeoNodeOAuth2FilterConfig",
                    "org.geoserver.security.oauth2.GeoServerOAuthAuthenticationFilter",
                    "org.geoserver.security.oauth2.GeoServerOAuthAuthenticationFilter$StatelessBearerSecurityContext",
                    "org.geoserver.security.oauth2.GeoServerOAuthRemoteTokenServices",
                    "org.geoserver.security.oauth2.GeoServerAccessTokenConverter",
                    "org.geoserver.security.oauth2.services.GeoNodeTokenServices",
                    "org.geoserver.geofence.services.DefaultUserResolver",
                    "org.mapfish.print.PDFUtils", "org.geoserver.importer.Importer")) {
                Class<?> type = loader.loadClass(name);
                String location = origin(type);
                Path loadedJar = Path.of(URI.create(location)).toRealPath();
                Path expectedJar = webRoot.resolve("WEB-INF/lib").resolve(loadedJar.getFileName()).toRealPath();
                if (!loadedJar.equals(expectedJar) || !loadedJar.startsWith(webRoot.resolve("WEB-INF/lib")))
                    throw new IllegalStateException("application class did not load from extracted WAR: " + name);
                String entryName = "WEB-INF/lib/" + loadedJar.getFileName();
                String jarHash = hash(loadedJar);
                try (ZipFile archive = new ZipFile(war.toFile());
                        InputStream input = archive.getInputStream(archive.getEntry(entryName))) {
                    if (!jarHash.equals(hash(input))) throw new IllegalStateException("loaded JAR differs from exact WAR: " + name);
                }
                int definitions = Collections.list(loader.getResources(name.replace('.', '/') + ".class")).size();
                if (definitions != 1) throw new IllegalStateException("duplicate application class: " + name);
                origins.add(quote(name) + ":{\"origin\":" + quote(location) + ",\"war_entry\":" + quote(entryName)
                        + ",\"jar_sha256\":" + quote(jarHash) + ",\"definitions\":" + definitions + "}");
            }
            // Enable only the selected native security categories, retaining actual configured appenders.
            Class<?> level = loader.loadClass("org.apache.logging.log4j.Level");
            Object debug = level.getField("DEBUG").get(null);
            Class<?> configurator = loader.loadClass("org.apache.logging.log4j.core.config.Configurator");
            configurator.getMethod("setLevel", String.class, level).invoke(null, "org.geoserver.security", debug);
            configurator.getMethod("setLevel", String.class, level).invoke(null, "org.geoserver.security.oauth2", debug);
            // Positive logger-capture control using the application's actual repaired OAuth logger.
            Class<?> oauth = loader.loadClass("org.geoserver.security.oauth2.GeoServerOAuthRemoteTokenServices");
            Field field = oauth.getDeclaredField("LOGGER");
            field.setAccessible(true);
            Object logger = field.get(null);
            System.out.println("AMBISGIS_OAUTH_LOGGER implementation=" + logger.getClass().getName()
                    + " origin=" + origin(logger.getClass()));
            // Configurator's caller-selected context need not be GeoServer's selected logger context.
            // Configure the exact retained SLF4J delegate instead of assuming they are the same.
            if (!logger.getClass().getName().equals("org.apache.logging.slf4j.Log4jLogger"))
                throw new IllegalStateException("unexpected OAuth logger implementation: " + logger.getClass().getName());
            Field delegateField = logger.getClass().getDeclaredField("logger");
            delegateField.setAccessible(true);
            Object nativeLogger = delegateField.get(logger);
            nativeLogger.getClass().getMethod("setLevel", level).invoke(nativeLogger, debug);
            Class<?> loggerApi = loader.loadClass("org.slf4j.Logger");
            if (!((Boolean) loggerApi.getMethod("isDebugEnabled").invoke(logger)))
                throw new IllegalStateException("OAuth DEBUG capture is not enabled");
            loggerApi.getMethod("debug", String.class).invoke(logger, "AMBISGIS_CONFIGURED_OAUTH_LOG_CAPTURE_CONTROL");
            Class<?> cacheType = loader.loadClass("org.geoserver.security.auth.GuavaAuthenticationCacheImpl");
            Field cacheField = cacheType.getDeclaredField("LOGGER");
            cacheField.setAccessible(true);
            java.util.logging.Logger cacheLogger = (java.util.logging.Logger) cacheField.get(null);
            cacheLogger.setLevel(java.util.logging.Level.FINE);
            if (!cacheLogger.isLoggable(java.util.logging.Level.FINE))
                throw new IllegalStateException("cache FINE capture is not enabled");
            cacheLogger.fine("AMBISGIS_CONFIGURED_CACHE_LOG_CAPTURE_CONTROL");
            String json = "{\"port\":" + connector.getLocalPort() + ",\"host\":\"127.0.0.1\","
                    + "\"context_path\":\"/geoserver\",\"war_sha256\":" + quote(warHash)
                    + ",\"deployed_war\":" + quote(deployedWar.toString())
                    + ",\"extracted_web_root\":" + quote(webRoot.toString())
                    + ",\"data_directory\":" + quote(actual.toPath().toRealPath().toString())
                    + ",\"worker_max\":16,\"jetty_origin\":" + quote(origin(Server.class))
                    + ",\"servlet_api_origin\":" + quote(origin(javax.servlet.Servlet.class))
                    + ",\"security_configuration\":" + securitySummary(loader, extensions)
                    + ",\"application_class_origins\":{" + String.join(",", origins) + "}}\n";
            Files.writeString(runtime.resolve("ready.json"), json, StandardOpenOption.CREATE_NEW);
            System.out.println("AMBISGIS_CONFIGURED_RUNTIME_READY port=" + connector.getLocalPort());
            server.join();
        } finally {
            server.stop();
        }
    }
}
