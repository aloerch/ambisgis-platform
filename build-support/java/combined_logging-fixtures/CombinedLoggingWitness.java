/* SPDX-License-Identifier: GPL-3.0-or-later */
import java.lang.reflect.Field;
import java.util.Collections;
import org.slf4j.LoggerFactory;

/** Exercises real selected component logger fields on the complete candidate WAR classpath. */
public final class CombinedLoggingWitness {
    private static Object nativeLogger(String name) throws Exception {
        Class<?> type = Class.forName(name);
        Field field = type.getDeclaredField("LOGGER");
        field.setAccessible(true);
        Object logger = field.get(null);
        System.out.printf("native_logger=%s implementation=%s origin=%s%n", name, logger.getClass().getName(),
                type.getProtectionDomain().getCodeSource().getLocation());
        return logger;
    }

    public static void main(String[] args) throws Exception {
        ClassLoader loader = CombinedLoggingWitness.class.getClassLoader();
        int apis = Collections.list(loader.getResources("org/slf4j/LoggerFactory.class")).size();
        int binders = Collections.list(loader.getResources("org/slf4j/impl/StaticLoggerBinder.class")).size();
        int providers = Collections.list(loader.getResources("META-INF/services/org.slf4j.spi.SLF4JServiceProvider")).size();
        String factory = LoggerFactory.getILoggerFactory().getClass().getName();
        System.out.printf("api_definitions=%d legacy_binders=%d provider_descriptors=%d factory=%s%n",
                apis, binders, providers, factory);
        if (apis != 1 || binders != 0 || providers != 1
                || !factory.equals("org.apache.logging.slf4j.Log4jLoggerFactory")) {
            throw new AssertionError("Combined candidate must select one SLF4J2 API/provider without legacy binders");
        }
        for (String resource : new String[] {"org/apache/commons/logging/LogFactory.class",
                "org/apache/log4j/Logger.class", "org/apache/logging/log4j/LogManager.class",
                "org/apache/logging/log4j/core/LoggerContext.class"}) {
            int definitions = Collections.list(loader.getResources(resource)).size();
            System.out.printf("logging_resource=%s definitions=%d%n", resource, definitions);
            if (definitions != 1) throw new AssertionError("Ambiguous native logging API: " + resource);
        }
        // Explicit witness settings mirror the inspected native APIs, not a running service configuration.
        org.geotools.util.logging.Logging.ALL.setLoggerFactory("org.geotools.util.logging.Log4J2LoggerFactory");
        String jul = java.util.logging.LogManager.getLogManager().getClass().getName();
        String jcl = org.apache.commons.logging.LogFactory.getFactory().getClass().getName();
        System.out.printf("jul_manager=%s commons_logging_factory=%s%n", jul, jcl);
        if (!jul.equals("org.apache.logging.log4j.jul.LogManager")
                || !jcl.equals("org.apache.logging.log4j.jcl.LogFactoryImpl")) {
            throw new AssertionError("Expected native JUL and Commons Logging bridges to Log4j2");
        }
        ((java.util.logging.Logger) nativeLogger("org.geoserver.platform.GeoServerExtensions"))
                .severe("AMBISGIS_NATIVE_GEOSERVER");
        ((org.apache.logging.log4j.Logger) nativeLogger("org.geoserver.geofence.services.DefaultUserResolver"))
                .error("AMBISGIS_NATIVE_GEOFENCE");
        ((org.apache.logging.log4j.Logger) nativeLogger("org.mapfish.print.PDFUtils"))
                .error("AMBISGIS_NATIVE_PRINTING");
        ((org.slf4j.Logger) nativeLogger("org.geoserver.security.oauth2.GeoServerOAuthRemoteTokenServices"))
                .error("AMBISGIS_NATIVE_OAUTH");
        ((org.apache.commons.logging.Log) nativeLogger("org.pvalsecc.concurrent.Watchdog"))
                .error("AMBISGIS_NATIVE_PRINTING_COMMONS");
        java.util.logging.Logger.getLogger("ambisgis.jul").severe("AMBISGIS_JUL_BRIDGE");
        org.apache.log4j.Logger.getLogger("ambisgis.legacy.api").error("AMBISGIS_LOG4J1_API_BRIDGE");
    }
}
