/* SPDX-License-Identifier: GPL-3.0-or-later */
package org.geoserver.security.oauth2;

import org.junit.Test;
import com.sun.net.httpserver.HttpServer;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.geoserver.security.oauth2.services.GeoNodeTokenServices;
import org.springframework.security.oauth2.provider.OAuth2Authentication;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.access.SecurityConfig;
import org.springframework.security.access.vote.AffirmativeBased;
import org.springframework.security.access.vote.AuthenticatedVoter;
import org.springframework.security.access.vote.RoleVoter;

/** Actual selected GeoNode token service over local HTTP; no token values are printed. */
public final class AmbisgisGeoNodeHttpTest {

    @Test
    public void actualTokenServiceOverHttp() throws Exception {
        int failures = 0;
        int cases = 0;
        // Ephemeral fixture values are used only by the task-local loopback endpoint.
        String token = UUID.randomUUID().toString();
        String client = "ambisgis-fixture";
        String secret = UUID.randomUUID().toString();
        String authorization = "Basic " + Base64.getEncoder().encodeToString(
                (client + ":" + secret).getBytes(StandardCharsets.UTF_8));
        AtomicBoolean validRequest = new AtomicBoolean(true);
        AtomicInteger calls = new AtomicInteger();
        HttpServer server = HttpServer.create(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0), 0);
        String valid = "{\"client_id\":\"ambisgis-fixture\",\"issued_to\":\"fixture-reader\",\"expires_in\":60000}";
        String[][] responses = {
            {"valid", "200", valid},
            {"missing-token", "200", valid},
            {"empty-token", "200", valid},
            {"wrong-client", "200", valid},
            {"wrong-secret", "200", valid},
            {"invalid", "400", "{\"error\":\"invalid_token\"}"},
            {"unauthorized", "401", "{}"},
            {"server-error", "500", "{}"},
            {"malformed", "200", "[broken"},
            {"missing-client", "200", "{\"issued_to\":\"fixture-reader\"}"},
            {"invalid-geonode", "403", "{\"error\":\"No access_token from server.\"}"},
            {"expired-geonode", "403", "{\"error\":\"No access_token from server.\"}"},
            {"missing-principal", "200", "{\"client_id\":\"ambisgis-fixture\",\"expires_in\":60000}"},
            {"empty-principal", "200", valid.replace("fixture-reader", "")},
            {"blank-principal", "200", valid.replace("fixture-reader", "   ")},
            {"non-string-principal", "200", valid.replace("\"fixture-reader\"", "42")},
            {"role-injection", "200", valid.replace("60000}", "60000,\"authorities\":[\"ROLE_ADMINISTRATOR\"]}")}
        };
        for (String[] row : responses) {
            server.createContext("/" + row[0], exchange -> {
                calls.incrementAndGet();
                byte[] request = exchange.getRequestBody().readAllBytes();
                boolean accepted = exchange.getRequestMethod().equals("POST")
                        && exchange.getRequestURI().getRawQuery() == null
                        && authorization.equals(exchange.getRequestHeaders().getFirst("Authorization"))
                        && ("token=" + token).equals(new String(request, StandardCharsets.UTF_8));
                boolean negativeCredential = row[0].equals("missing-token") || row[0].equals("empty-token")
                        || row[0].equals("wrong-client") || row[0].equals("wrong-secret");
                if (accepted == negativeCredential) validRequest.set(false);
                byte[] response = (accepted ? row[2] : "{\"error\":\"invalid_request\"}").getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(accepted ? Integer.parseInt(row[1]) : 403, response.length);
                try (var out = exchange.getResponseBody()) { out.write(response); }
            });
        }
        server.start();
        try {
            for (String[] row : responses) {
                GeoNodeTokenServices service = new GeoNodeTokenServices();
                service.setClientId(row[0].equals("wrong-client") ? "other-fixture" : client);
                service.setClientSecret(row[0].equals("wrong-secret") ? "other-fixture" : secret);
                service.setCheckTokenEndpointUrl("http://127.0.0.1:" + server.getAddress().getPort() + "/" + row[0]);
                OAuth2Authentication authentication = null;
                String result = "denied";
                try {
                    String presented = row[0].equals("missing-token") ? null : row[0].equals("empty-token") ? "" : token;
                    authentication = service.loadAuthentication(presented);
                    result = "accepted";
                } catch (RuntimeException ignored) {
                    // Deliberately never print exception messages: the native invalid-token exception contains the token.
                }
                boolean shouldAccept = row[0].equals("valid") || row[0].equals("role-injection");
                boolean passed = shouldAccept ? authentication != null && authentication.isAuthenticated()
                        && "fixture-reader".equals(authentication.getName())
                        && "ambisgis-fixture".equals(authentication.getOAuth2Request().getClientId())
                        && authentication.getAuthorities().isEmpty() : authentication == null;
                if (shouldAccept && authentication != null) {
                    // The selected Spring decision manager exercises a fixed fixture resource.
                    // This is not the configured GeoServer servlet or canonical product policy.
                    AffirmativeBased decisions = new AffirmativeBased(java.util.List.of(new RoleVoter(), new AuthenticatedVoter()));
                    try {
                        decisions.decide(authentication, "fixture-authenticated-resource",
                                SecurityConfig.createList("IS_AUTHENTICATED_FULLY"));
                    } catch (AccessDeniedException denied) {
                        passed = false;
                    }
                    boolean privilegedDenied = false;
                    try {
                        decisions.decide(authentication, "fixture-administrator-resource",
                                SecurityConfig.createList("ROLE_ADMINISTRATOR"));
                    } catch (AccessDeniedException denied) {
                        privilegedDenied = true;
                    }
                    passed = passed && privilegedDenied;
                    System.out.printf("authorization_case=%s authenticated_allowed=%s administrator_denied=%s%n",
                            row[0], passed, privilegedDenied);
                }
                if (!passed) failures++;
                cases++;
                System.out.printf("case=%s expected=%s observed=%s authenticated=%s passed=%s%n", row[0],
                        shouldAccept ? "accepted-without-injected-roles" : "denied", result,
                        authentication != null && authentication.isAuthenticated(), passed);
            }
            boolean transport = validRequest.get() && calls.get() == responses.length;
            if (!transport) failures++;
            System.out.printf("transport_basic_form_no_query=%s requests=%d cases=%d failures=%d%n",
                    transport, calls.get(), cases, failures);
        } finally {
            server.stop(0);
        }
        if (failures != 0) throw new AssertionError("OAuth candidate failed " + failures + " bounded runtime cases");
    }
}
