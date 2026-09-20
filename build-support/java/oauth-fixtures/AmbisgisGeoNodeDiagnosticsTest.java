/* SPDX-License-Identifier: GPL-3.0-or-later */
package org.geoserver.security.oauth2;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Configuration;
import org.apache.logging.log4j.core.config.LoggerConfig;
import org.apache.logging.log4j.core.config.Property;
import org.geoserver.security.oauth2.services.GeoNodeTokenServices;
import org.junit.Test;
import org.slf4j.LoggerFactory;
import org.springframework.security.oauth2.common.exceptions.InvalidTokenException;

/** Diagnostics regression: dynamically generated fixture values are held only in memory. */
public class AmbisgisGeoNodeDiagnosticsTest {
    private static class ExposedService extends GeoNodeTokenServices {
        void transform(Map<String, Object> response) { transformNonStandardValuesToStandardValues(response); }
        void verify(String token, Map<String, Object> response) { verifyTokenResponse(token, response); }
    }

    @Test
    public void responseDiagnosticsDoNotExposeFixtureValues() {
        String category = GeoServerOAuthRemoteTokenServices.class.getName();
        LoggerContext context = (LoggerContext) LogManager.getContext(false);
        Configuration config = context.getConfiguration();
        LoggerConfig old = config.getLoggers().get(category);
        List<String> messages = new ArrayList<>();
        AbstractAppender memory = new AbstractAppender("AmbisgisMemoryOnly", null, null, false, Property.EMPTY_ARRAY) {
            @Override public void append(LogEvent event) { messages.add(event.getMessage().getFormattedMessage()); }
        };
        memory.start();
        LoggerConfig isolated = new LoggerConfig(category, Level.DEBUG, false);
        isolated.addAppender(memory, Level.DEBUG, null);
        config.removeLogger(category);
        config.addLogger(category, isolated);
        context.updateLoggers();
        try {
            LoggerFactory.getLogger(category).debug("AMBISGIS_CAPTURE_CONTROL");
            assertTrue("Actual logger must reach the nonadditive memory appender",
                    messages.stream().anyMatch(message -> message.contains("AMBISGIS_CAPTURE_CONTROL")));
            String marker = UUID.randomUUID().toString();
            Map<String, Object> response = new HashMap<>();
            response.put("issued_to", "fixture-reader");
            response.put("access_token", marker);
            new ExposedService().transform(response);
            // No captured content or marker appears in assertion messages or test reports.
            assertFalse("Sensitive response content appeared in diagnostics",
                    messages.stream().anyMatch(message -> message.contains(marker)));
        } finally {
            config.removeLogger(category);
            if (old != null) config.addLogger(category, old);
            context.updateLoggers();
            memory.stop();
            messages.clear();
        }
    }

    @Test
    public void rejectionExceptionDoesNotExposeFixtureValue() {
        String marker = UUID.randomUUID().toString();
        try {
            new ExposedService().verify(marker, Map.of("error", "denied"));
            fail("Invalid token response must be rejected");
        } catch (InvalidTokenException expected) {
            assertFalse("Sensitive request content appeared in rejection diagnostic",
                    expected.getMessage().contains(marker));
        }
    }
    @Test
    public void reflectedErrorDiagnosticsDoNotExposeFixtureValue() {
        // Spring RemoteTokenServices uses getClass(), so this actual subclass is the category.
        String category = ExposedService.class.getName();
        LoggerContext context = (LoggerContext) LogManager.getContext(false);
        Configuration config = context.getConfiguration();
        LoggerConfig old = config.getLoggers().get(category);
        List<String> messages = new ArrayList<>();
        AbstractAppender memory = new AbstractAppender("AmbisgisErrorMemoryOnly", null, null, false, Property.EMPTY_ARRAY) {
            @Override public void append(LogEvent event) { messages.add(event.getMessage().getFormattedMessage()); }
        };
        memory.start();
        LoggerConfig isolated = new LoggerConfig(category, Level.DEBUG, false);
        isolated.addAppender(memory, Level.DEBUG, null);
        config.removeLogger(category);
        config.addLogger(category, isolated);
        context.updateLoggers();
        try {
            org.apache.commons.logging.LogFactory.getLog(ExposedService.class).debug("AMBISGIS_ERROR_CAPTURE_CONTROL");
            assertTrue("Inherited logger must reach the nonadditive memory appender",
                    messages.stream().anyMatch(message -> message.contains("AMBISGIS_ERROR_CAPTURE_CONTROL")));
            String marker = UUID.randomUUID().toString();
            try {
                new ExposedService().verify(marker, Map.of("error", marker));
                fail("Invalid token response must be rejected");
            } catch (InvalidTokenException expected) {
                // The separately named exception regression checks the exception's contents.
            }
            assertFalse("Sensitive reflected response content appeared in diagnostics",
                    messages.stream().anyMatch(message -> message.contains(marker)));
        } finally {
            config.removeLogger(category);
            if (old != null) config.addLogger(category, old);
            context.updateLoggers();
            memory.stop();
            messages.clear();
        }
    }

}
