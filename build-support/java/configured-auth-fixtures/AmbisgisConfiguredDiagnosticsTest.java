/* SPDX-License-Identifier: GPL-3.0-or-later */
package org.geoserver.security.oauth2;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertSame;
import static org.junit.Assert.assertTrue;

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.logging.Handler;
import java.util.logging.LogRecord;
import java.util.logging.Logger;
import javax.servlet.ServletException;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Configuration;
import org.apache.logging.log4j.core.config.LoggerConfig;
import org.apache.logging.log4j.core.config.Property;
import org.geoserver.security.auth.GuavaAuthenticationCacheImpl;
import org.junit.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.client.OAuth2RestTemplate;
import org.springframework.security.oauth2.client.filter.OAuth2ClientAuthenticationProcessingFilter;
import org.springframework.security.oauth2.client.resource.OAuth2AccessDeniedException;
import org.springframework.security.oauth2.client.token.grant.code.AuthorizationCodeResourceDetails;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;

/** Native diagnostic regressions; disposable values and captured exceptions stay in memory. */
public class AmbisgisConfiguredDiagnosticsTest {
    private static final String CONTROL = "AMBISGIS_NATIVE_CONFIGURED_DIAGNOSTIC_CONTROL";

    private static String stack(Throwable thrown) {
        if (thrown == null) return "";
        StringWriter output = new StringWriter();
        thrown.printStackTrace(new PrintWriter(output));
        return output.toString();
    }

    /** Capture the actual native logger whether its current factory uses JUL or Log4j2. */
    private static class Capture implements AutoCloseable {
        final Logger logger;
        final List<String> messages = Collections.synchronizedList(new ArrayList<>());
        final java.util.logging.Level previousLevel;
        final boolean previousParent;
        final Handler jul;
        final LoggerContext context;
        final Configuration configuration;
        final LoggerConfig previousConfig;
        final AbstractAppender memory;

        Capture(Logger actual) {
            logger = actual;
            previousLevel = logger.getLevel();
            previousParent = logger.getUseParentHandlers();
            logger.setLevel(java.util.logging.Level.FINE);
            logger.setUseParentHandlers(false);
            jul = new Handler() {
                @Override public void publish(LogRecord record) {
                    messages.add(record.getMessage() + stack(record.getThrown()));
                    if (record.getParameters() != null)
                        for (Object value : record.getParameters()) messages.add(String.valueOf(value));
                }
                @Override public void flush() {}
                @Override public void close() {}
            };
            jul.setLevel(java.util.logging.Level.ALL);
            logger.addHandler(jul);
            context = (LoggerContext) LogManager.getContext(false);
            configuration = context.getConfiguration();
            previousConfig = configuration.getLoggers().get(logger.getName());
            memory = new AbstractAppender("ConfiguredMemoryOnly", null, null, false, Property.EMPTY_ARRAY) {
                @Override public void append(LogEvent event) {
                    messages.add(event.getMessage().getFormattedMessage() + stack(event.getThrown()));
                }
            };
            memory.start();
            LoggerConfig isolated = new LoggerConfig(logger.getName(), Level.DEBUG, false);
            isolated.addAppender(memory, Level.ALL, null);
            configuration.removeLogger(logger.getName());
            configuration.addLogger(logger.getName(), isolated);
            context.updateLoggers();
            logger.fine(CONTROL);
            assertTrue("Actual native diagnostic logger must reach memory capture",
                    messages.stream().anyMatch(message -> message.contains(CONTROL)));
        }

        void assertPrivate(String marker) {
            assertFalse("Native diagnostic exposed a disposable credential, identity or provider response",
                    messages.stream().anyMatch(message -> message.contains(marker)));
        }

        @Override public void close() {
            logger.removeHandler(jul);
            logger.setLevel(previousLevel);
            logger.setUseParentHandlers(previousParent);
            configuration.removeLogger(logger.getName());
            if (previousConfig != null) configuration.addLogger(logger.getName(), previousConfig);
            context.updateLoggers();
            memory.stop();
            messages.clear();
        }
    }

    private static class ProbeFilter extends GeoServerOAuthAuthenticationFilter {
        ProbeFilter(RuntimeException failure, Authentication accepted) {
            super(new GeoServerOAuth2FilterConfig(),
                    new GeoServerOAuthRemoteTokenServices(new GeoServerAccessTokenConverter()) {},
                    null, new OAuth2RestTemplate(new AuthorizationCodeResourceDetails()));
            filter = new OAuth2ClientAuthenticationProcessingFilter("/") {
                @Override public Authentication attemptAuthentication(
                        HttpServletRequest request, HttpServletResponse response) {
                    if (failure != null) throw failure;
                    return accepted;
                }
            };
        }
        @Override protected void configureRestTemplate() {}
        static Logger actualLogger() { return LOGGER; }
        String principal() throws Exception {
            return getPreAuthenticatedPrincipal(new MockHttpServletRequest(), new MockHttpServletResponse());
        }
        String cookie(String value) {
            MockHttpServletRequest request = new MockHttpServletRequest();
            request.setCookies(new Cookie(SESSION_COOKIE_NAME, value));
            return getCustomSessionCookieValue(request);
        }
    }

    @Test
    public void authenticationCacheDiagnosticsDoNotExposeKeys() throws Exception {
        Field field = GuavaAuthenticationCacheImpl.class.getDeclaredField("LOGGER");
        field.setAccessible(true);
        try (Capture capture = new Capture((Logger) field.get(null))) {
            String marker = UUID.randomUUID().toString();
            GuavaAuthenticationCacheImpl cache = new GuavaAuthenticationCacheImpl(8, 60, 60, 60, 1);
            Authentication identity = new UsernamePasswordAuthenticationToken("fixture-reader", null, Collections.emptyList());
            try {
                assertNull(cache.get("fixture-oauth", marker));
                cache.put("fixture-oauth", marker, identity);
                assertSame(identity, cache.get("fixture-oauth", marker));
                cache.remove("fixture-oauth", marker);
                assertNull(cache.get("fixture-oauth", marker));
                cache.put("fixture-oauth", marker, identity, 30, 30);
                assertSame(identity, cache.get("fixture-oauth", marker));
                cache.removeAll("fixture-oauth");
                assertTrue(cache.isEmpty());
                capture.assertPrivate(marker);
            } finally { cache.destroy(); }
        }
    }

    @Test
    public void unauthorizedResponseDiagnosticsArePrivate() throws Exception {
        String marker = UUID.randomUUID().toString();
        RuntimeException unauthorized = HttpClientErrorException.create("fixture denial " + marker, HttpStatus.UNAUTHORIZED, "fixture",
                HttpHeaders.EMPTY, marker.getBytes(StandardCharsets.UTF_8), StandardCharsets.UTF_8);
        try (Capture capture = new Capture(ProbeFilter.actualLogger())) {
            assertNull(new ProbeFilter(unauthorized, null).principal());
            capture.assertPrivate(marker);
        }
    }

    @Test
    public void providerExceptionDiagnosticsArePrivate() throws Exception {
        String marker = UUID.randomUUID().toString();
        List<RuntimeException> failures = List.of(
                new ResourceAccessException(marker, new IOException(marker)),
                new BadCredentialsException(marker, new OAuth2AccessDeniedException(marker)),
                new BadCredentialsException(marker, new IOException(marker)));
        try (Capture capture = new Capture(ProbeFilter.actualLogger())) {
            for (RuntimeException failure : failures) assertNull(new ProbeFilter(failure, null).principal());
            capture.assertPrivate(marker);
        }
    }

    @Test
    public void customCookieDiagnosticDoesNotExposeCredential() {
        String marker = UUID.randomUUID().toString();
        try (Capture capture = new Capture(ProbeFilter.actualLogger())) {
            assertTrue("Cookie extraction behavior must remain unchanged",
                    marker.equals(new ProbeFilter(null, null).cookie(marker)));
            capture.assertPrivate(marker);
        }
    }

    @Test
    public void acceptedPrincipalDiagnosticDoesNotExposeIdentity() throws Exception {
        String marker = UUID.randomUUID().toString();
        Authentication identity = new UsernamePasswordAuthenticationToken(marker, null, Collections.emptyList());
        try (Capture capture = new Capture(ProbeFilter.actualLogger())) {
            assertTrue("Accepted identity must remain unchanged", marker.equals(new ProbeFilter(null, identity).principal()));
            capture.assertPrivate(marker);
        }
    }

    @Test
    public void servletResolutionExceptionDiagnosticIsPrivate() {
        String marker = UUID.randomUUID().toString();
        SecurityContextHolder.clearContext();
        try (Capture capture = new Capture(ProbeFilter.actualLogger())) {
            ProbeFilter probe = new ProbeFilter(null, null) {
                @Override protected String getPreAuthenticatedPrincipal(
                        HttpServletRequest request, HttpServletResponse response) throws ServletException {
                    throw new ServletException(marker);
                }
            };
            probe.doAuthenticate(new MockHttpServletRequest(), new MockHttpServletResponse());
            assertNull(SecurityContextHolder.getContext().getAuthentication());
            capture.assertPrivate(marker);
        } finally { SecurityContextHolder.clearContext(); }
    }
}
