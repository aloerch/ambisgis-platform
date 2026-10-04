/* SPDX-License-Identifier: GPL-3.0-or-later */
/** Finite parser regressions only; never substitute for actual authorization tests. */
public final class DevelopmentFilterChecks {
    private static int cases;
    private static int diagnosticCases;
    private static void verify(boolean value) {
        diagnosticCases++;
        if (!value) throw new AssertionError("finite initialization diagnostic guard " + diagnosticCases);
    }
    private static final class HostileFailure extends RuntimeException {
        @Override public String getMessage() { throw new AssertionError("message must not be read"); }
        @Override public String getLocalizedMessage() { throw new AssertionError("localized message must not be read"); }
        @Override public synchronized Throwable getCause() { throw new AssertionError("cause must not be read"); }
        @Override public String toString() { throw new AssertionError("text must not be read"); }
    }
    private static void diagnostics() throws Exception {
        String secret = "synthetic-password=DO_NOT_EMIT-/private/path";
        java.util.List<String> events = new java.util.ArrayList<>();
        java.util.List<String> actions = new java.util.ArrayList<>();
        DevelopmentGeoServer.Progress progress = new DevelopmentGeoServer.Progress(true, events::add);
        DevelopmentGeoServer.lifecycle(progress, () -> actions.add("start"), () -> {
            actions.add("body");
            progress.at(DevelopmentGeoServer.Phase.TRANSPORT_START);
            progress.at(DevelopmentGeoServer.Phase.TRANSPORT_COMPLETE);
            progress.at(DevelopmentGeoServer.Phase.WAR_RECHECK);
            progress.at(DevelopmentGeoServer.Phase.INITIALIZED_MARKER);
        }, () -> actions.add("stop"));
        verify(actions.equals(java.util.List.of("start", "body", "stop")));
        verify(events.size() == 9);
        for (DevelopmentGeoServer.Phase phase : DevelopmentGeoServer.Phase.values())
            verify(events.contains("{\"event\":\"geoserver_initialization_phase\",\"phase\":\"" + phase.name() + "\"}"));
        verify(events.get(events.size() - 1).contains("MAIN_COMPLETE"));
        for (Exception failure : new Exception[]{new java.io.IOException(secret),
                new java.lang.reflect.InvocationTargetException(new HostileFailure(), secret),
                new HostileFailure(), new IllegalArgumentException(secret)}) {
            events.clear(); actions.clear();
            try {
                DevelopmentGeoServer.lifecycle(progress, () -> actions.add("start"), () -> {
                    progress.at(DevelopmentGeoServer.Phase.TRANSPORT_START); throw failure;
                }, () -> actions.add("stop"));
                throw new AssertionError("application failure was swallowed");
            } catch (Exception actual) { verify(actual == failure); }
            verify(actions.equals(java.util.List.of("start", "stop")));
            verify(events.stream().anyMatch(e -> e.contains("geoserver_initialization_failure") && e.contains("TRANSPORT_START")));
            verify(events.stream().noneMatch(e -> e.contains(secret) || e.contains("private/path") || e.contains("MAIN_COMPLETE")));
            for (String event : events) verify(event.matches("\\{\"event\":\"geoserver_initialization_(phase|failure)\",\"phase\":\"[A-Z_]+\"(,\"exception_class\":\"(IOException|InvocationTargetException|OTHER|IllegalArgumentException)\")?\\}"));
        }
        Exception original = new IllegalStateException(secret);
        events.clear(); actions.clear();
        try {
            DevelopmentGeoServer.lifecycle(progress, () -> { throw original; },
                    () -> actions.add("body"), () -> actions.add("stop"));
            throw new AssertionError("start failure was swallowed");
        } catch (Exception actual) { verify(actual == original); }
        verify(actions.equals(java.util.List.of("stop")));
        verify(events.stream().anyMatch(e -> e.contains("geoserver_initialization_failure") && e.contains("SERVER_START")));
        Exception shutdown = new java.io.IOException(secret);
        events.clear();
        try {
            DevelopmentGeoServer.lifecycle(progress, () -> {}, () -> { throw original; }, () -> { throw shutdown; });
            throw new AssertionError("stop failure was swallowed");
        } catch (Exception actual) { verify(actual == shutdown); }
        verify(events.stream().anyMatch(e -> e.contains("geoserver_initialization_failure") && e.contains("SERVER_STOP")));
        verify(events.stream().noneMatch(e -> e.contains(secret) || e.contains("SERVER_STOPPED") || e.contains("MAIN_COMPLETE")));
        // Every emission checkpoint may fail; native actions and finally-stop
        // must still run, without replacing an existing application exception.
        for (int failAt = 1; failAt <= 5; failAt++) {
            final int selected = failAt;
            int[] calls = {0}; actions.clear();
            DevelopmentGeoServer.Progress unavailable = new DevelopmentGeoServer.Progress(true, value -> {
                if (++calls[0] == selected) throw new IllegalStateException(secret);
            });
            DevelopmentGeoServer.lifecycle(unavailable, () -> actions.add("start"),
                    () -> actions.add("body"), () -> actions.add("stop"));
            verify(actions.equals(java.util.List.of("start", "body", "stop")));
        }
        actions.clear();
        DevelopmentGeoServer.Progress broken = new DevelopmentGeoServer.Progress(true, value -> { throw new AssertionError(secret); });
        try {
            DevelopmentGeoServer.lifecycle(broken, () -> {}, () -> { throw original; }, () -> actions.add("stop"));
            throw new AssertionError("original failure was swallowed");
        } catch (Exception actual) { verify(actual == original); }
        verify(actions.equals(java.util.List.of("stop")));
        actions.clear();
        DevelopmentGeoServer.lifecycle(new DevelopmentGeoServer.Progress(false, value -> { throw new AssertionError("serving emitted init diagnostics"); }),
                () -> actions.add("start"), () -> actions.add("body"), () -> actions.add("stop"));
        verify(actions.equals(java.util.List.of("start", "body", "stop")));
        System.out.println("finite_initialization_diagnostic_cases=" + diagnosticCases);
    }
    private static void check(boolean expected, String method, String path, String query) {
        cases++;
        if (DevelopmentCatalogFilter.supported(method, path, query) != expected)
            throw new AssertionError("finite request guard " + cases);
    }
    public static void main(String[] arguments) throws Exception {
        String wfs = "service=WFS&version=1.0.0&request=GetFeature&typename=fixture%3Aprivate_points&outputformat=application%2Fjson";
        String wms = "service=WMS&version=1.1.1&request=GetMap&layers=fixture%3Aprivate_points&styles=&srs=EPSG%3A4326&bbox=0%2C0%2C4%2C4&width=512&height=512&format=image%2Fpng&transparent=FALSE";
        check(true, "GET", "/geoserver/wfs", wfs);
        check(true, "GET", "/geoserver/wms", wms);
        check(true, "GET", "/geoserver/wfs", wfs.replace("service=", "SERVICE="));
        for (String method : new String[]{"POST", "PATCH", "PUT", "DELETE", "HEAD", "OPTIONS"}) {
            check(false, method, "/geoserver/wfs", wfs); check(false, method, "/geoserver/wms", wms);
        }
        for (String path : new String[]{"/geoserver/rest/workspaces", "/geoserver/web/", "/geoserver/ows", "/geoserver/wfs/", "/geoserver//wfs", "/geoserver/wfs;ignored", "/geoserver/%77fs", "/wfs", "/geoserver/gwc/service/wms"}) {
            check(false, "GET", path, wfs); check(false, "GET", path, wms);
        }
        for (String extra : new String[]{"&LAYERS=fixture%3Aprivate_points", "&width=512", "&WIDTH=512", "&%77idth=512", "&sld=http%3A%2F%2Fexample.invalid%2Fstyle", "&viewparams=x", "&filter=x", "&", "&broken", "&x=%FF", "&x=%"}) {
            check(false, "GET", "/geoserver/wfs", wfs + extra); check(false, "GET", "/geoserver/wms", wms + extra);
        }
        check(false, "GET", "/geoserver/wfs", wfs.replace("private_points", "other_points"));
        check(false, "GET", "/geoserver/wfs", wfs.replace("GetFeature", "Transaction"));
        check(false, "GET", "/geoserver/wfs", wfs.replace("1.0.0", "2.0.0"));
        check(false, "GET", "/geoserver/wms", wms.replace("512", "4096"));
        check(false, "GET", "/geoserver/wms", wms.replace("styles=", "styles=other"));
        check(false, "GET", "/geoserver/wms", wms.replace("image%2Fpng", "image%2Fjpeg"));
        check(false, "GET", "/geoserver/wms", "x".repeat(2049));
        check(false, "GET", "/geoserver/wms", null);
        System.out.println("finite_request_guard_cases=" + cases);
        diagnostics();
    }
}
