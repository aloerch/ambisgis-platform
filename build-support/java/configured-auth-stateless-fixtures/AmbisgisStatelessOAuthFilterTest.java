/* AmbisGIS configured-service regression. GPL-2.0, matching the owned GeoServer module. */
package org.geoserver.security.oauth2;

import static org.junit.Assert.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import java.io.Serializable;
import java.lang.reflect.Method;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import javax.servlet.ServletException;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletResponse;
import org.geoserver.security.GeoServerRoleService;
import org.geoserver.security.GeoServerSecurityManager;
import org.geoserver.security.GeoServerUserGroupService;
import org.geoserver.security.auth.GuavaAuthenticationCacheImpl;
import org.geoserver.security.config.PreAuthenticatedUserNameFilterConfig.PreAuthenticatedUserNameRoleSource;
import org.geoserver.security.impl.GeoServerRole;
import org.geoserver.security.impl.GeoServerUser;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.client.DefaultOAuth2ClientContext;
import org.springframework.security.oauth2.client.OAuth2RestOperations;
import org.springframework.security.oauth2.client.token.grant.code.AuthorizationCodeResourceDetails;
import org.springframework.security.oauth2.common.exceptions.InvalidTokenException;
import org.springframework.security.oauth2.provider.OAuth2Authentication;
import org.springframework.security.oauth2.provider.OAuth2Request;
import org.springframework.security.oauth2.provider.authentication.OAuth2AuthenticationDetails;
import org.springframework.security.web.context.HttpRequestResponseHolder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;

/** Native doFilter tests; the configured WAR probe separately exercises real HTTP/XML/GeoFence. */
public class AmbisgisStatelessOAuthFilterTest {
    private static final GeoServerRole READER = new GeoServerRole("ROLE_FIXTURE_READER");
    private static final String TOKEN = "synthetic-reader-token";
    private GeoServerOAuth2FilterConfig config;
    private GeoServerOAuthAuthenticationFilter filter;
    private GeoServerOAuthRemoteTokenServices tokens;
    private OAuth2RestOperations template;
    private GeoServerUserGroupService users;
    private GuavaAuthenticationCacheImpl cache;

    @Before
    public void setUp() throws Exception {
        SecurityContextHolder.clearContext();
        config = new GeoServerOAuth2FilterConfig();
        config.setName("fixture-oauth");
        config.setRoleSource(PreAuthenticatedUserNameRoleSource.UserGroupService);
        config.setUserGroupServiceName("fixture");
        config.setCliendId("synthetic-client");
        config.setClientSecret("synthetic-secret");
        config.setScopes("read");
        config.setEnableRedirectAuthenticationEntryPoint(false);
        config.setCheckTokenEndpointUrl("http://127.0.0.1:1/verify_token");
        config.setLoginEndpoint("/unused-login");
        config.setLogoutEndpoint("/unused-logout");
        setStateless(true);

        tokens = mock(GeoServerOAuthRemoteTokenServices.class);
        template = mock(OAuth2RestOperations.class);
        // These native browser collaborators allow the identical fixture to compile and
        // expose the failing session behavior before the opt-in property exists.
        DefaultOAuth2ClientContext browser = new DefaultOAuth2ClientContext();
        when(template.getResource()).thenReturn(new AuthorizationCodeResourceDetails());
        when(template.getOAuth2ClientContext()).thenReturn(browser);
        when(template.getAccessToken()).thenAnswer(invocation -> browser.getAccessToken());
        clearInvocations(template);

        GeoServerSecurityManager manager = mock(GeoServerSecurityManager.class);
        users = mock(GeoServerUserGroupService.class);
        GeoServerRoleService roles = mock(GeoServerRoleService.class);
        when(manager.loadUserGroupService("fixture")).thenReturn(users);
        when(manager.getActiveRoleService()).thenReturn(roles);
        when(roles.getRolesForUser(anyString())).thenReturn(new TreeSet<>());
        cache = new GuavaAuthenticationCacheImpl(100, 2, 2, 1, 1);
        when(manager.getAuthenticationCache()).thenReturn(cache);
        provision("fixture-reader", true, Set.of(READER));
        provision("fixture-outsider", true, Collections.emptySet());
        provision("fixture-disabled", false, Set.of(READER));
        filter = new GeoServerOAuthAuthenticationFilter(config, tokens, null, template) {};
        filter.setSecurityManager(manager);
        filter.initializeFromConfig(config);
        when(tokens.loadAuthentication(TOKEN)).thenReturn(identity("fixture-reader"));
    }

    @After
    public void tearDown() {
        SecurityContextHolder.clearContext();
        if (cache != null) cache.destroy();
    }

    private void setStateless(boolean value) throws Exception {
        try {
            Method setter = config.getClass().getMethod("setStatelessBearerAuthentication", boolean.class);
            setter.invoke(config, value);
        } catch (NoSuchMethodException baseline) {
            // Baseline has browser-only behavior: runtime assertions must fail, not compilation.
        }
    }

    private void provision(String name, boolean enabled, Set<GeoServerRole> authorities) throws Exception {
        GeoServerUser user = new GeoServerUser(name);
        user.setEnabled(enabled);
        user.setAuthorities(authorities);
        when(users.getUserByUsername(name)).thenReturn(user);
        when(users.loadUserByUsername(name)).thenReturn(user);
    }

    private OAuth2Authentication identity(String name) {
        Map<String, Serializable> extensions = new HashMap<>();
        HashMap<String, String> claims = new HashMap<>();
        claims.put("issued_to", name);
        claims.put("roles", "ROLE_ADMINISTRATOR");
        extensions.put(GeoServerOAuthAuthenticationFilter.OAUTH2_ACCESS_TOKEN_CHECK_KEY, claims);
        OAuth2Request request = new OAuth2Request(Collections.emptyMap(), "synthetic-client",
                Collections.emptyList(), true, Set.of("read"), null, null, null, extensions);
        // Identity-provider authorities deliberately disagree with configured local policy.
        return new OAuth2Authentication(request, new UsernamePasswordAuthenticationToken(
                name, "not-a-password", Set.of(GeoServerRole.ADMIN_ROLE)));
    }

    private MockHttpServletRequest request(String token) {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/wfs");
        if (token != null) request.addHeader("Authorization", "Bearer " + token);
        return request;
    }

    private Authentication invoke(MockHttpServletRequest request) throws Exception {
        Authentication[] observed = new Authentication[1];
        filter.doFilter(request, new MockHttpServletResponse(), (req, resp) -> {
            observed[0] = SecurityContextHolder.getContext().getAuthentication();
        });
        return observed[0];
    }

    private SecurityContext browserSession(MockHttpServletRequest request) {
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(new UsernamePasswordAuthenticationToken(
                "browser-reader", "not-a-password", Set.of(READER)));
        MockHttpSession session = new MockHttpSession();
        session.setAttribute(HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY, context);
        request.setSession(session);
        request.setCookies(new Cookie("JSESSIONID", session.getId()),
                new Cookie(GeoServerOAuthAuthenticationFilter.SESSION_COOKIE_NAME, "custom-browser-cookie"));
        SecurityContextHolder.setContext(context); // actual persistence filter's loaded session context
        return context;
    }

    @Test
    public void defaultsKeepBrowserSessionContract() throws Exception {
        GeoServerOAuth2FilterConfig defaults = new GeoServerOAuth2FilterConfig();
        try {
            assertEquals(Boolean.FALSE, defaults.getClass().getMethod("isStatelessBearerAuthentication").invoke(defaults));
        } catch (NoSuchMethodException baseline) {
            // An unmodified config also has only its historical browser behavior.
        }
        setStateless(false);
        MockHttpServletRequest request = request(null);
        SecurityContext browser = browserSession(request);
        assertSame(browser.getAuthentication(), invoke(request));
        assertSame(browser, SecurityContextHolder.getContext());
        assertFalse(((MockHttpSession) request.getSession(false)).isInvalid());
        verifyNoInteractions(tokens, template);
    }

    @Test
    public void missingBearerRemainsAnonymousWithoutSessionOrTemplate() throws Exception {
        MockHttpServletRequest request = request(null);
        assertNull(invoke(request));
        assertNull(request.getSession(false));
        verifyNoInteractions(tokens, template);
    }

    @Test
    public void cookieCannotAuthorizeMissingBearerAndBrowserIsPreserved() throws Exception {
        MockHttpServletRequest request = request(null);
        SecurityContext browser = browserSession(request);
        Authentication prior = browser.getAuthentication();
        assertNull(invoke(request));
        assertSame(browser, SecurityContextHolder.getContext());
        assertSame(prior, browser.getAuthentication());
        assertSame(browser, request.getSession(false).getAttribute(
                HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY));
        assertFalse(((MockHttpSession) request.getSession(false)).isInvalid());
        verifyNoInteractions(tokens, template);
    }

    @Test
    public void cookieCannotOverrideOutsiderBearer() throws Exception {
        String token = "synthetic-outsider-token";
        when(tokens.loadAuthentication(token)).thenReturn(identity("fixture-outsider"));
        MockHttpServletRequest request = request(token);
        SecurityContext browser = browserSession(request);
        Authentication result = invoke(request);
        assertEquals("fixture-outsider", result.getName());
        assertFalse(result.getAuthorities().contains(READER));
        assertFalse(result.getAuthorities().contains(GeoServerRole.ADMIN_ROLE));
        assertSame(browser, SecurityContextHolder.getContext());
        assertEquals("browser-reader", browser.getAuthentication().getName());
        verify(tokens).loadAuthentication(token);
        verifyNoInteractions(template);
    }

    @Test
    public void currentBearerUsesConfiguredRolesAndPreservesNativeRequestAttributes() throws Exception {
        MockHttpServletRequest request = request(TOKEN);
        Authentication result = invoke(request);
        assertEquals("fixture-reader", result.getName());
        assertTrue(result.getAuthorities().contains(READER));
        assertTrue(result.getAuthorities().contains(GeoServerRole.AUTHENTICATED_ROLE));
        assertFalse(result.getAuthorities().contains(GeoServerRole.ADMIN_ROLE));
        assertEquals(TOKEN, request.getAttribute(OAuth2AuthenticationDetails.ACCESS_TOKEN_VALUE));
        assertEquals(GeoServerOAuthAuthenticationFilter.OAuth2AuthenticationType.BEARER,
                request.getAttribute(GeoServerOAuthAuthenticationFilter.OAUTH2_AUTHENTICATION_TYPE_KEY));
        assertEquals("fixture-reader", ((Map<?, ?>) request.getAttribute(
                GeoServerOAuthAuthenticationFilter.OAUTH2_ACCESS_TOKEN_CHECK_KEY)).get("issued_to"));
        assertNotNull(request.getAttribute(GeoServerOAuthAuthenticationFilter.OAUTH2_AUTHENTICATION_KEY));
        assertNull(request.getSession(false));
        assertNull(SecurityContextHolder.getContext().getAuthentication());
        verifyNoInteractions(template);
    }

    @Test
    public void invalidBearerCannotFallBackToSession() throws Exception {
        String token = "synthetic-invalid-token";
        when(tokens.loadAuthentication(token)).thenThrow(new InvalidTokenException("private remote body"));
        MockHttpServletRequest request = request(token);
        SecurityContext browser = browserSession(request);
        assertNull(invoke(request));
        assertSame(browser, SecurityContextHolder.getContext());
        verify(tokens).loadAuthentication(token);
        verifyNoInteractions(template);
    }

    @Test
    public void disabledAndUnprovisionedIdentitiesCannotAuthenticate() throws Exception {
        for (String name : new String[] {"fixture-disabled", "unknown-identity", "root"}) {
            String token = "synthetic-" + name + "-token";
            when(tokens.loadAuthentication(token)).thenReturn(identity(name));
            MockHttpServletRequest request = request(token);
            assertNull(name, invoke(request));
            assertNull(request.getSession(false));
            assertNull(cache.get("fixture-oauth", token));
        }
        verifyNoInteractions(template);
    }

    @Test
    public void provisionedRootHasOnlyConfiguredRoles() throws Exception {
        provision("root", true, Set.of(READER));
        String token = "synthetic-provisioned-root-token";
        when(tokens.loadAuthentication(token)).thenReturn(identity("root"));
        Authentication result = invoke(request(token));
        assertEquals("root", result.getName());
        assertTrue(result.getAuthorities().contains(READER));
        assertFalse(result.getAuthorities().contains(GeoServerRole.ADMIN_ROLE));
        assertFalse(result.getAuthorities().contains(GeoServerRole.GROUP_ADMIN_ROLE));
        verifyNoInteractions(template);
    }

    @Test
    public void cacheUsesCurrentBearerAndInvalidationRequiresFreshVerification() throws Exception {
        assertEquals("fixture-reader", invoke(request(TOKEN)).getName());
        assertEquals("fixture-reader", invoke(request(TOKEN)).getName());
        verify(tokens, times(1)).loadAuthentication(TOKEN);
        assertNull(invoke(request(null)));
        cache.removeAll("fixture-oauth");
        when(tokens.loadAuthentication(TOKEN)).thenThrow(new InvalidTokenException("revoked"));
        assertNull(invoke(request(TOKEN)));
        verify(tokens, times(2)).loadAuthentication(TOKEN);
        verifyNoInteractions(template);
    }

    @Test
    public void nonzeroCacheExpiryRequiresFreshVerification() throws Exception {
        assertEquals("fixture-reader", invoke(request(TOKEN)).getName());
        assertNotNull(cache.get("fixture-oauth", TOKEN));
        when(tokens.loadAuthentication(TOKEN)).thenThrow(new InvalidTokenException("expired"));
        Thread.sleep(2200);
        assertNull(invoke(request(TOKEN)));
        verify(tokens, times(2)).loadAuthentication(TOKEN);
        verifyNoInteractions(template);
    }

    @Test
    public void serializedConfigCloneRetainsExplicitOption() throws Exception {
        GeoServerOAuth2FilterConfig copied = (GeoServerOAuth2FilterConfig) config.clone(false);
        try {
            assertEquals(Boolean.TRUE, copied.getClass().getMethod("isStatelessBearerAuthentication").invoke(copied));
        } catch (NoSuchMethodException baseline) {
            fail("explicit stateless bearer option is absent");
        }
    }

    private void assertBrowserSurvivesResponseCommit(String token, boolean sendError) throws Exception {
        MockHttpServletRequest request = request(token);
        SecurityContext browser = browserSession(request);
        HttpSessionSecurityContextRepository repository = new HttpSessionSecurityContextRepository();
        repository.setAllowSessionCreation(false);
        HttpRequestResponseHolder holder = new HttpRequestResponseHolder(request, new MockHttpServletResponse());
        SecurityContextHolder.setContext(repository.loadContext(holder));
        filter.doFilter(holder.getRequest(), holder.getResponse(), (req, resp) -> {
            Authentication observed = SecurityContextHolder.getContext().getAuthentication();
            if (token == null) assertNull(observed);
            else assertEquals("fixture-outsider", observed.getName());
            if (sendError) ((HttpServletResponse) resp).sendError(403);
            else resp.flushBuffer();
            // Assert during the chain: finally-only restoration is too late for a concurrent
            // browser request between response commitment and the outer persistence save.
            assertSame(browser, request.getSession(false).getAttribute(
                    HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY));
            assertEquals("browser-reader", browser.getAuthentication().getName());
        });
        assertSame(browser, SecurityContextHolder.getContext());
        repository.saveContext(SecurityContextHolder.getContext(), holder.getRequest(), holder.getResponse());
        assertSame(browser, request.getSession(false).getAttribute(
                HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY));
        verifyNoInteractions(template);
    }

    @Test
    public void errorResponseWithoutBearerCannotRemoveBrowserContext() throws Exception {
        assertBrowserSurvivesResponseCommit(null, true);
        verifyNoInteractions(tokens);
    }

    @Test
    public void committedOutsiderResponseCannotReplaceBrowserContext() throws Exception {
        String token = "synthetic-committed-outsider-token";
        when(tokens.loadAuthentication(token)).thenReturn(identity("fixture-outsider"));
        assertBrowserSurvivesResponseCommit(token, false);
        verify(tokens).loadAuthentication(token);
    }

    @Test
    public void chainFailureRestoresOriginalBrowserContext() throws Exception {
        MockHttpServletRequest request = request(TOKEN);
        SecurityContext browser = browserSession(request);
        try {
            filter.doFilter(request, new MockHttpServletResponse(), (req, resp) -> {
                assertEquals("fixture-reader", SecurityContextHolder.getContext().getAuthentication().getName());
                throw new ServletException("synthetic downstream failure");
            });
            fail("downstream exception must propagate");
        } catch (ServletException expected) {
            assertEquals("synthetic downstream failure", expected.getMessage());
        }
        assertSame(browser, SecurityContextHolder.getContext());
        assertEquals("browser-reader", browser.getAuthentication().getName());
        verifyNoInteractions(template);
    }
}
