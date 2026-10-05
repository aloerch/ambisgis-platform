/* SPDX-License-Identifier: GPL-3.0-or-later */
/** Finite parser regressions only; never substitute for actual authorization tests. */
public final class DevelopmentFilterChecks {
    private static int cases;
    private static int diagnosticCases;
    private static int threadCases;
    private static void threadVerify(boolean value) {
        threadCases++;
        if (!value) throw new AssertionError("post-stop thread diagnostic guard " + threadCases);
    }

    private static final class ThreadFixture implements DevelopmentGeoServer.ThreadSource {
        long[] ids;
        DevelopmentGeoServer.ThreadSample[] samples;
        int calls;
        boolean fail;
        ThreadFixture(long[] ids, DevelopmentGeoServer.ThreadSample... samples) {
            this.ids = ids; this.samples = samples;
        }
        public long currentId() { return 1; }
        public long[] ids() { return ids; }
        public DevelopmentGeoServer.ThreadSample[] samples(long[] selected, int depth) {
            calls++;
            threadVerify(depth == 32 && java.util.Arrays.equals(selected, ids) && selected != ids);
            if (fail) throw new HostileFailure();
            return samples;
        }
    }

    private static DevelopmentGeoServer.ThreadSample sample(long id, boolean daemon, String name, StackTraceElement... stack) {
        return new DevelopmentGeoServer.ThreadSample(id, daemon, Thread.State.WAITING, name, stack);
    }

    private static void nativeThreadBridge() throws Exception {
        String secretName = "synthetic-password=DO_NOT_EMIT-/private/thread-path";
        java.util.concurrent.CountDownLatch ready = new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.CountDownLatch release = new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.atomic.AtomicBoolean failed = new java.util.concurrent.atomic.AtomicBoolean();
        Thread owned = new Thread(() -> {
            ready.countDown();
            try {
                if (!release.await(5, java.util.concurrent.TimeUnit.SECONDS)) failed.set(true);
            } catch (InterruptedException unexpected) { failed.set(true); }
        }, secretName);
        owned.setDaemon(false);
        try {
            owned.start();
            threadVerify(ready.await(2, java.util.concurrent.TimeUnit.SECONDS));
            long deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(2);
            while (owned.getState() != Thread.State.TIMED_WAITING && System.nanoTime() < deadline) Thread.sleep(1);
            threadVerify(owned.getState() == Thread.State.TIMED_WAITING);
            DevelopmentGeoServer.ThreadSource source = DevelopmentGeoServer.nativeThreads();
            threadVerify(java.util.Arrays.stream(source.ids()).anyMatch(id -> id == owned.getId()));
            DevelopmentGeoServer.ThreadSample[] rows = source.samples(new long[]{owned.getId()}, 32);
            threadVerify(rows.length == 1 && rows[0] != null && rows[0].id() == owned.getId());
            threadVerify(!rows[0].daemon() && rows[0].state() == Thread.State.TIMED_WAITING);
            threadVerify(rows[0].stack().length > 0 && rows[0].stack().length <= 32);
            String result = DevelopmentGeoServer.threadSnapshot(source);
            threadVerify(result.contains("\"id\":" + owned.getId() + ",\"state\":\"TIMED_WAITING\""));
            threadVerify(!result.contains(secretName) && !result.contains("private/thread-path"));
        } finally {
            release.countDown();
            owned.join(2000);
            threadVerify(!owned.isAlive());
        }
        threadVerify(!failed.get());
    }

    private static void threadDiagnostics() throws Exception {
        String secret = "synthetic-password=DO_NOT_EMIT-/private/path";
        StackTraceElement known = new StackTraceElement(secret, secret, secret,
                "java.util.concurrent.ThreadPoolExecutor", "getTask", secret, 987654);
        StackTraceElement unknown = new StackTraceElement(secret, secret, secret, 456789);
        ThreadFixture fixture = new ThreadFixture(new long[]{1, 2, 3, 4}, sample(1, false, secret),
                sample(2, true, secret, unknown), null, sample(4, false, secret, known, unknown));
        String result = DevelopmentGeoServer.threadSnapshot(fixture);
        threadVerify(result.contains("\"raced_away\":1") && result.contains("\"daemon_omitted\":1")
                && result.contains("\"current_omitted\":1"));
        threadVerify(result.contains("\"id\":4") && result.contains("\"frames\":[\"EXECUTOR_GET_TASK\",\"OTHER\"]"));
        threadVerify(!result.contains(secret) && !result.contains("987654") && !result.contains("456789"));
        threadVerify(!result.contains("java.util") && result.contains("\"name_family\":\"OTHER\""));
        threadVerify(DevelopmentGeoServer.frameSymbol(null).equals("OTHER"));
        threadVerify(DevelopmentGeoServer.frameSymbol(new StackTraceElement("java.util.concurrent.ThreadPoolExecutor.evil", "getTask", secret, 1)).equals("OTHER"));
        threadVerify(DevelopmentGeoServer.frameSymbol(new StackTraceElement("java.util.concurrent.ThreadPoolExecutor", secret, secret, 1)).equals("OTHER"));
        for (String[] pair : new String[][]{{"pool-12-thread-3", "DEFAULT_EXECUTOR"},
                {"GuavaAuthCache-0-1", "GUAVA_AUTH_CACHE"}, {"GeoServerAuthenticationKey-2-1", "AUTHKEY_SYNC"},
                {"GT authority factory disposer", "GT_AUTHORITY_DISPOSER"}, {"Loader" + secret, "RESOURCE_LOADER_CANDIDATE"},
                {"pool-1-thread-2/" + secret, "OTHER"}, {secret, "OTHER"}, {"x".repeat(161), "OTHER"}})
            threadVerify(DevelopmentGeoServer.threadFamily(pair[0]).equals(pair[1]));
        threadVerify(DevelopmentGeoServer.threadFamily(null).equals("OTHER"));
        ThreadFixture empty = new ThreadFixture(new long[0]);
        threadVerify(DevelopmentGeoServer.threadSnapshot(empty).contains("\"non_daemon\":[]"));
        ThreadFixture overflow = new ThreadFixture(new long[257]);
        threadVerify(DevelopmentGeoServer.threadSnapshot(overflow).contains("THREAD_OVERFLOW") && overflow.calls == 0);
        StackTraceElement[] full = new StackTraceElement[32]; java.util.Arrays.fill(full, known);
        result = DevelopmentGeoServer.threadSnapshot(new ThreadFixture(new long[]{2}, sample(2, false, "pool-1-thread-1", full)));
        threadVerify(result.contains("\"possibly_truncated\":true"));
        result = DevelopmentGeoServer.threadSnapshot(new ThreadFixture(new long[]{2}, sample(2, false, "pool-1-thread-1", known)));
        threadVerify(result.contains("\"possibly_truncated\":false"));
        // Worst allowed projection is complete, ASCII and below the explicit
        // output bound; no unknown text is copied even in every frame/name.
        long[] manyIds = new long[256]; DevelopmentGeoServer.ThreadSample[] many = new DevelopmentGeoServer.ThreadSample[256];
        for (int i = 0; i < many.length; i++) { manyIds[i] = i + 2; many[i] = sample(i + 2, false, secret, full); }
        result = DevelopmentGeoServer.threadSnapshot(new ThreadFixture(manyIds, many));
        threadVerify(result.contains("\"scanned\":256") && result.length() < DevelopmentGeoServer.THREAD_OUTPUT_LIMIT);
        threadVerify(result.chars().allMatch(c -> c < 128) && !result.contains(secret));
        java.util.List<ThreadFixture> malformed = java.util.List.of(
                new ThreadFixture(null), new ThreadFixture(new long[]{0}), new ThreadFixture(new long[]{2, 2}),
                new ThreadFixture(new long[]{2}), new ThreadFixture(new long[]{2}, sample(3, false, secret)),
                new ThreadFixture(new long[]{2}, new DevelopmentGeoServer.ThreadSample(2, false, null, secret, full)),
                new ThreadFixture(new long[]{2}, new DevelopmentGeoServer.ThreadSample(2, false, Thread.State.WAITING, secret, null)),
                new ThreadFixture(new long[]{2}, sample(2, false, secret, new StackTraceElement[33])));
        for (ThreadFixture bad : malformed) {
            java.util.List<String> events = new java.util.ArrayList<>();
            DevelopmentGeoServer.Progress progress = new DevelopmentGeoServer.Progress(true, events::add);
            progress.afterStop(() -> events.add(DevelopmentGeoServer.threadSnapshot(bad)));
            threadVerify(events.equals(java.util.List.of(DevelopmentGeoServer.threadStatus("UNAVAILABLE"))));
        }
        try { DevelopmentGeoServer.threadStatus(secret); throw new AssertionError("unknown status accepted"); }
        catch (IllegalArgumentException expected) { threadVerify(true); }
        java.util.List<String> events = new java.util.ArrayList<>();
        DevelopmentGeoServer.Progress progress = new DevelopmentGeoServer.Progress(true, events::add);
        DevelopmentGeoServer.lifecycle(progress, () -> {}, () -> {}, () -> {}, () -> {
            threadVerify(events.get(events.size() - 1).contains("SERVER_STOPPED"));
            events.add(DevelopmentGeoServer.threadSnapshot(fixture));
        });
        threadVerify(events.get(events.size() - 2).contains("geoserver_post_stop_threads"));
        threadVerify(events.get(events.size() - 1).contains("MAIN_COMPLETE"));
        // Collection failure, sink failure and hostile exceptions cannot alter
        // successful completion or native body/stop exception precedence.
        for (Throwable problem : new Throwable[]{new HostileFailure(), new AssertionError(secret)}) {
            events.clear();
            DevelopmentGeoServer.lifecycle(progress, () -> {}, () -> {}, () -> {}, () -> {
                if (problem instanceof Error error) throw error; throw (RuntimeException) problem;
            });
            threadVerify(events.get(events.size() - 2).contains("UNAVAILABLE") && events.get(events.size() - 1).contains("MAIN_COMPLETE"));
        }
        events.clear(); fixture.fail = true;
        DevelopmentGeoServer.lifecycle(progress, () -> {}, () -> {}, () -> {}, () -> events.add(DevelopmentGeoServer.threadSnapshot(fixture)));
        threadVerify(events.stream().anyMatch(e -> e.contains("UNAVAILABLE")));
        Exception body = new java.io.IOException(secret), stop = new IllegalStateException(secret);
        for (boolean stopFails : new boolean[]{false, true}) {
            int[] observations = {0}; events.clear();
            try {
                DevelopmentGeoServer.lifecycle(progress, () -> {}, () -> { throw body; }, () -> {
                    if (stopFails) throw stop;
                }, () -> { observations[0]++; throw new HostileFailure(); });
                throw new AssertionError("application exception lost");
            } catch (Exception actual) { threadVerify(actual == (stopFails ? stop : body)); }
            threadVerify(observations[0] == (stopFails ? 0 : 1));
            threadVerify(events.stream().noneMatch(e -> e.contains("MAIN_COMPLETE") || e.contains(secret)));
        }
        int[] actions = {0};
        DevelopmentGeoServer.Progress sinkFailure = new DevelopmentGeoServer.Progress(true, value -> { throw new HostileFailure(); });
        DevelopmentGeoServer.lifecycle(sinkFailure, () -> actions[0]++, () -> actions[0]++, () -> actions[0]++, () -> { throw new HostileFailure(); });
        threadVerify(actions[0] == 3);
        DevelopmentGeoServer.Progress serving = new DevelopmentGeoServer.Progress(false, value -> { throw new AssertionError("serving emitted"); });
        DevelopmentGeoServer.lifecycle(serving, () -> {}, () -> {}, () -> {}, () -> { throw new AssertionError("serving observed threads"); });
        threadVerify(true);
        nativeThreadBridge();
        System.out.println("post_stop_thread_diagnostic_cases=" + threadCases);
    }
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
        threadDiagnostics();
    }
}
