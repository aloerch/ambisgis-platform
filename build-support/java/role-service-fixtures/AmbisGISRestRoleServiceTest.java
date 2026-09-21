/* (c) 2026 AmbisGIS contributors.
 * Licensed under GPL 2.0, matching the inherited GeoServer module.
 */
package org.geoserver.security;

import static org.junit.Assert.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

import com.google.common.base.Ticker;
import com.google.common.cache.CacheBuilder;
import java.io.IOException;
import java.util.Locale;
import java.util.Set;
import java.util.SortedSet;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.geoserver.security.impl.GeoServerRole;
import org.junit.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.client.ExpectedCount;
import org.springframework.web.client.RestTemplate;

/** Native source regressions; these mock transport and do not establish HTTP integration. */
public class AmbisGISRestRoleServiceTest {
    private static final String BASE = "http://roles.invalid";
    private static final String READER = "{\"users\":[{\"username\":\"reader\",\"groups\":[\"fixture-readers\"]}]}";
    private static final String ADMIN = "{\"users\":[{\"username\":\"reader\",\"groups\":[\"admin\"]}]}";

    private static final class Fixture {
        final GeoServerRestRoleServiceConfig config = new GeoServerRestRoleServiceConfig();
        final GeoServerRestRoleService service;
        final MockRestServiceServer server;
        Fixture() throws IOException {
            config.setBaseUrl(BASE);
            option(config, "setStrictGeoNodeRoles", true);
            config.setAuthApiKey("synthetic-service-key");
            config.setCacheExpirationTime(1000);
            service = new GeoServerRestRoleService(config);
            RestTemplate template = new RestTemplate();
            server = MockRestServiceServer.createServer(template);
            service.setRestTemplate(template);
        }
        void users(String path, String payload) {
            server.expect(requestTo(BASE + "/api/users/" + path))
                    .andExpect(header("Authorization", "ApiKey synthetic-service-key"))
                    .andRespond(withSuccess(payload, MediaType.APPLICATION_JSON));
        }
        void admin() {
            server.expect(requestTo(BASE + "/api/adminRole"))
                    .andRespond(withSuccess("{\"adminRole\":\"admin\"}", MediaType.APPLICATION_JSON));
        }
        void reader() { users("reader", READER); admin(); }
    }

    // Baseline source has no strict option. Reflection lets the same native cases run
    // against it and preserve concrete failing assertions instead of compiler failures.
    private static void option(GeoServerRestRoleServiceConfig config, String name, Object value) {
        try {
            config.getClass().getMethod(name, value instanceof Boolean ? boolean.class : int.class).invoke(config, value);
        } catch (NoSuchMethodException baseline) {
            // Deliberately exercise inherited behavior when the new option is unavailable.
        } catch (ReflectiveOperationException failure) {
            throw new AssertionError(failure);
        }
    }
    private static Object optionValue(GeoServerRestRoleServiceConfig config, String name) {
        try {
            return config.getClass().getMethod(name).invoke(config);
        } catch (ReflectiveOperationException failure) {
            throw new AssertionError("Required finite strict role-service option unavailable: " + name, failure);
        }
    }

    private static void assertReader(SortedSet<GeoServerRole> roles) {
        assertEquals(Set.of(new GeoServerRole("ROLE_FIXTURE-READERS")), roles);
    }
    private static void deniedPayload(String payload) throws Exception {
        Fixture f = new Fixture();
        f.users("reader", payload);
        assertTrue(f.service.getRolesForUser("reader").isEmpty());
        f.server.verify();
    }

    @Test public void strictReaderUsesCanonicalRole() throws Exception {
        Fixture f = new Fixture(); f.reader();
        assertReader(f.service.getRolesForUser("reader")); f.server.verify();
    }
    @Test public void authoritativeAdministratorMapsToSystemRole() throws Exception {
        Fixture f = new Fixture(); f.users("reader", ADMIN); f.admin();
        assertEquals(Set.of(GeoServerRole.ADMIN_ROLE), f.service.getRolesForUser("reader")); f.server.verify();
    }
    @Test public void missingIdentityHasNoRoles() throws Exception {
        deniedPayload("{\"users\":[]}");
    }
    @Test public void mismatchedUsernameCannotAcquireAdministrativeRole() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"someone-else\",\"groups\":[\"admin\"]}]}");
    }
    @Test public void usernameCaseIsNotNormalized() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"Reader\",\"groups\":[\"admin\"]}]}");
    }
    @Test public void duplicateUsersAreAmbiguousAndDenied() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"reader\",\"groups\":[\"admin\"]},{\"username\":\"reader\",\"groups\":[]}]}");
    }
    @Test public void partialMalformedRoleArrayIsAtomic() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"reader\",\"groups\":[\"admin\",17]}]}");
    }
    @Test public void mixedCaseRoleCannotAliasGrant() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"reader\",\"groups\":[\"Admin\"]}]}");
    }
    @Test public void rolePrefixCannotAliasGrant() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"reader\",\"groups\":[\"role_admin\"]}]}");
    }
    @Test public void systemRoleCannotBypassAdministrativeMapping() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"reader\",\"groups\":[\"administrator\"]}]}");
    }
    @Test public void missingGroupsFailsClosed() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"reader\"}]}");
    }
    @Test public void truncatedJsonFailsClosed() throws Exception {
        deniedPayload("{\"users\":[{\"username\":\"reader\",\"groups\":[\"admin\"]}");
    }
    @Test public void administrativeMappingFailureCannotPreservePartialRoles() throws Exception {
        Fixture f = new Fixture(); f.users("reader", ADMIN);
        f.server.expect(requestTo(BASE + "/api/adminRole")).andRespond(withStatus(HttpStatus.FORBIDDEN));
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }
    @Test public void malformedAdminMappingCannotPromoteReader() throws Exception {
        Fixture f = new Fixture(); f.users("reader", READER);
        f.server.expect(requestTo(BASE + "/api/adminRole"))
                .andRespond(withSuccess("{\"adminRole\":\"fixture-readers\"}", MediaType.APPLICATION_JSON));
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }
    @Test public void configuredAdminOverrideIsRejectedInStrictMode() throws Exception {
        GeoServerRestRoleServiceConfig config = new GeoServerRestRoleServiceConfig();
        option(config, "setStrictGeoNodeRoles", true); config.setAdminRoleName("fixture-readers");
        assertThrows(IOException.class, () -> new GeoServerRestRoleService(config));
    }
    @Test public void rejectedServiceCredentialsHaveNoRoles() throws Exception {
        Fixture f = new Fixture();
        f.server.expect(requestTo(BASE + "/api/users/reader")).andRespond(withStatus(HttpStatus.UNAUTHORIZED));
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }
    @Test public void transportFailureHasNoRoles() throws Exception {
        Fixture f = new Fixture();
        f.server.expect(requestTo(BASE + "/api/users/reader")).andRespond(request -> { throw new java.net.SocketTimeoutException("synthetic timeout"); });
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }
    @Test public void independentServiceCannotReadAnotherCredentialSnapshot() throws Exception {
        Fixture authorized = new Fixture(); Fixture denied = new Fixture();
        authorized.reader();
        denied.server.expect(requestTo(BASE + "/api/users/reader")).andRespond(withStatus(HttpStatus.FORBIDDEN));
        assertReader(authorized.service.getRolesForUser("reader"));
        assertTrue(denied.service.getRolesForUser("reader").isEmpty());
        authorized.server.verify(); denied.server.verify();
    }
    @Test public void credentialRotationDoesNotReuseSnapshot() throws Exception {
        Fixture f = new Fixture(); f.reader();
        f.server.expect(requestTo(BASE + "/api/users/reader"))
                .andExpect(header("Authorization", "ApiKey revoked-synthetic-key"))
                .andRespond(withStatus(HttpStatus.FORBIDDEN));
        assertReader(f.service.getRolesForUser("reader"));
        f.config.setAuthApiKey("revoked-synthetic-key");
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }
    @Test public void usernameIsEncodedAndNeverInterpolatedIntoJsonPath() throws Exception {
        Fixture f = new Fixture();
        String username = "reader/../admin";
        f.users("reader%2F..%2Fadmin", "{\"users\":[{\"username\":\"admin\",\"groups\":[\"admin\"]}]}");
        assertTrue(f.service.getRolesForUser(username).isEmpty()); f.server.verify();
    }
    @Test public void localeCannotChangeRoleIdentity() throws Exception {
        Locale previous = Locale.getDefault();
        try {
            Locale.setDefault(Locale.forLanguageTag("tr-TR"));
            Fixture f = new Fixture(); f.reader();
            assertReader(f.service.getRolesForUser("reader")); f.server.verify();
        } finally { Locale.setDefault(previous); }
    }
    @Test public void successfulHitsNeverRenewAbsoluteSnapshotExpiry() throws Exception {
        Fixture f = new Fixture();
        AtomicLong nanos = new AtomicLong();
        f.service.cachedResponses = CacheBuilder.newBuilder().expireAfterWrite(1000, TimeUnit.MILLISECONDS)
                .ticker(new Ticker() { @Override public long read() { return nanos.get(); } }).build();
        f.reader(); f.users("reader", "{\"users\":[{\"username\":\"reader\",\"groups\":[]}]}");
        assertReader(f.service.getRolesForUser("reader"));
        for (int i = 1; i <= 9; i++) {
            nanos.set(TimeUnit.MILLISECONDS.toNanos(i * 100));
            assertReader(f.service.getRolesForUser("reader"));
        }
        nanos.set(TimeUnit.MILLISECONDS.toNanos(1001));
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }
    @Test public void expiredSnapshotFailureAndRecoveryHaveNoStaleFallback() throws Exception {
        Fixture f = new Fixture();
        AtomicLong nanos = new AtomicLong();
        f.service.cachedResponses = CacheBuilder.newBuilder().expireAfterWrite(1000, TimeUnit.MILLISECONDS)
                .ticker(new Ticker() { @Override public long read() { return nanos.get(); } }).build();
        f.reader();
        f.server.expect(requestTo(BASE + "/api/users/reader")).andRespond(withStatus(HttpStatus.FORBIDDEN));
        f.reader();
        assertReader(f.service.getRolesForUser("reader"));
        nanos.set(TimeUnit.MILLISECONDS.toNanos(1001));
        assertTrue(f.service.getRolesForUser("reader").isEmpty());
        assertReader(f.service.getRolesForUser("reader")); f.server.verify();
    }
    @Test public void malformedGlobalRoleListIsAtomic() throws Exception {
        Fixture f = new Fixture();
        f.server.expect(requestTo(BASE + "/api/roles"))
                .andRespond(withSuccess("{\"groups\":[\"admin\",17]}", MediaType.APPLICATION_JSON));
        assertTrue(f.service.getRoles().isEmpty()); f.server.verify();
    }
    @Test public void missingAdministrativeEndpointReturnsNullWithoutFallbackException() throws Exception {
        Fixture f = new Fixture();
        f.server.expect(requestTo(BASE + "/api/adminRole")).andRespond(withStatus(HttpStatus.FORBIDDEN));
        assertNull(f.service.getAdminRole()); f.server.verify();
    }
    @Test public void finiteTimeoutDefaultsAndConfiguredValues() {
        GeoServerRestRoleServiceConfig c = new GeoServerRestRoleServiceConfig();
        assertEquals(false, optionValue(c, "isStrictGeoNodeRoles"));
        assertEquals(30000, optionValue(c, "getConnectTimeout")); assertEquals(30000, optionValue(c, "getReadTimeout"));
        option(c, "setConnectTimeout", 1500); option(c, "setReadTimeout", 1200);
        assertEquals(1500, optionValue(c, "getConnectTimeout")); assertEquals(1200, optionValue(c, "getReadTimeout"));
        option(c, "setConnectTimeout", 0); option(c, "setReadTimeout", -1);
        assertEquals(30000, optionValue(c, "getConnectTimeout")); assertEquals(30000, optionValue(c, "getReadTimeout"));
    }

    private static void deniedDocument(String payload) throws Exception {
        Fixture f = new Fixture(); f.users("reader", payload);
        // The previous repaired candidate can parse ambiguous syntax and request
        // admin mapping. Let it complete so its privilege grant fails an assertion.
        f.server.expect(ExpectedCount.between(0, 1), requestTo(BASE + "/api/adminRole"))
                .andRespond(withSuccess("{\"adminRole\":\"admin\"}", MediaType.APPLICATION_JSON));
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }

    @Test public void duplicateUsernameKeysAreRejected() throws Exception {
        deniedDocument("{\"users\":[{\"username\":\"someone-else\",\"username\":\"reader\",\"groups\":[\"admin\"]}]}");
    }
    @Test public void duplicateGroupsKeysAreRejected() throws Exception {
        deniedDocument("{\"users\":[{\"username\":\"reader\",\"groups\":[],\"groups\":[\"admin\"]}]}");
    }
    @Test public void trailingGarbageIsNotACompleteRoleDocument() throws Exception {
        deniedDocument(ADMIN + " trailing-garbage");
    }
    @Test public void multipleJsonDocumentsAreRejected() throws Exception {
        deniedDocument(ADMIN + " {}");
    }
    @Test public void unquotedKeysAreRejected() throws Exception {
        deniedDocument("{users:[{username:\"reader\",groups:[\"admin\"]}]}");
    }
    @Test public void singleQuotedJsonIsRejected() throws Exception {
        deniedDocument("{'users':[{'username':'reader','groups':['admin']}]}");
    }
    @Test public void trailingArrayCommaIsRejected() throws Exception {
        deniedDocument("{\"users\":[{\"username\":\"reader\",\"groups\":[\"admin\",]}]}");
    }
    @Test public void duplicateAdministrativeMappingKeysAreRejected() throws Exception {
        Fixture f = new Fixture(); f.users("reader", ADMIN);
        f.server.expect(requestTo(BASE + "/api/adminRole"))
                .andRespond(withSuccess("{\"adminRole\":\"outsider\",\"adminRole\":\"admin\"}", MediaType.APPLICATION_JSON));
        assertTrue(f.service.getRolesForUser("reader").isEmpty()); f.server.verify();
    }
    @Test public void duplicateGlobalGroupsKeysAreRejected() throws Exception {
        Fixture f = new Fixture();
        f.server.expect(requestTo(BASE + "/api/roles"))
                .andRespond(withSuccess("{\"groups\":[],\"groups\":[\"admin\"]}", MediaType.APPLICATION_JSON));
        assertTrue(f.service.getRoles().isEmpty()); f.server.verify();
    }
    @Test public void roleByNameValidatesEntireArrayBeforeReturningGrant() throws Exception {
        Fixture f = new Fixture();
        f.server.expect(requestTo(BASE + "/api/roles"))
                .andRespond(withSuccess("{\"groups\":[\"admin\",17]}", MediaType.APPLICATION_JSON));
        assertNull(f.service.getRoleByName("ROLE_ADMIN")); f.server.verify();
    }
    @Test public void groupRoleLookupCannotBypassStrictGlobalJson() throws Exception {
        Fixture f = new Fixture();
        f.server.expect(requestTo(BASE + "/api/roles"))
                .andRespond(withSuccess("{groups:[\"admin\"]}", MediaType.APPLICATION_JSON));
        assertTrue(f.service.getRolesForGroup("admin").isEmpty()); f.server.verify();
    }
}
