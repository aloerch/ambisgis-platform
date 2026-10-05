# Initialization JVM thread observation

The second private GeoServer initialization replay emitted `SERVER_STOPPED` and
`MAIN_COMPLETE`, then reached the unchanged Python 180-second timeout. The final
phase precedes launcher return; it does not independently prove that `main`
returned or identify a surviving thread. The temporary Java marker also does not
establish the durable marker, which Python writes only after successful JVM exit.

Initialization now observes threads immediately after a successful `server.stop()`
and `SERVER_STOPPED`, before `MAIN_COMPLETE`. Serving mode neither collects nor
emits this observation. Start/body/stop behavior, exception precedence and deadlines
are unchanged. Observation or output failure cannot replace an application
exception or prevent stop. There is no interrupt, executor shutdown or forced exit.

The retained Java 17 `ThreadMXBean` supplies IDs and `getThreadInfo(ids, 32)`.
More than 256 IDs yields `THREAD_OVERFLOW` without requesting stacks. A raced-away
thread is counted; the current thread and daemon threads are omitted from rows.
An empty result is a point-in-time observation, not a stable cleanup assertion.
The ID enumeration itself is a JVM allocation; the limit bounds subsequent stack
collection and serialized output, not all internal VM memory or observation time.

One JSON record has event `geoserver_post_stop_threads`, schema version 1, and
status `OBSERVED`, `THREAD_OVERFLOW`, `OUTPUT_OVERFLOW` or `UNAVAILABLE`.
`OBSERVED` includes `scanned`, `raced_away`, `daemon_omitted`, `current_omitted`
and `non_daemon` rows. Each row contains numeric `id`, Java `state`, a fixed
`name_family`, `possibly_truncated`, and a list of fixed frame symbols. Exactly
32 returned frames means *possibly* truncated; the API does not establish that
an additional frame exists. The complete ASCII record is limited to 512 KiB;
overflow emits a fixed status instead of a partial record.

No raw thread names, class/method names, file names, line numbers, module names,
exception messages, causes, paths or configuration values are serialized. Unknown
names/symbols become `OTHER`. Name families are hints only: default executor,
Guava authentication cache, authkey synchronization, GT authority disposer and
resource loader. A prefix hint does not prove thread ownership. Idle scheduled
executor frames can identify only a pool family, not the task that created it.
Existing private output capture and credential screening still apply.

The exact class/method switch is derived from retained inputs, with no prefix-based
symbol authorization:

| Vocabulary | Retained source |
| --- | --- |
| JDK wait/park, executor, queue, condition, future and timer methods | JDK 17.0.20.1+1 `lib/src.zip`, SHA-256 `cbc429f64abf85ca18f38a95007b8c6ebbd96642650db0c8ca17461ca8e8cbda`; actual methods checked in retained `java.base.jmod` |
| `RESOURCE_MAPPER_RUN` | `AsynchResourceIterator.java`, SHA-256 `cdd9f54935e4fd9817a6e7d949d0c8b5dc8b6be49ad4e227258fd0ca481e53f4` |
| `AUTHKEY_SYNC_RUN` | `GeoServerAuthenticationKeyProvider.java`, SHA-256 `00448c29658839ea86bf0923e7aa3f9856bc0f7f774b2138e73233486327c16c` |
| `GWC_DELETE_RUN` | `FileBlobStore.java`, SHA-256 `65d7fb4786274cc93d325f73c7fab1da8caf1f3ccf225ea26d24856d5a808ebe` |

The three native classes are present in the selected owned WAR, SHA-256
`115a6a74e32847ded96c127531039e348f8be823badbf5643afbc72b00c5180b`.
The private static inventory binds all 24 accepted class/method pairs to exact
class bytes and source members. It does not show that any candidate thread ran.
In particular, authkey mapper construction creates a default scheduled executor,
but the current owned filter configuration does not establish mapper instantiation.

`DevelopmentFilterChecks` retains its 63 request and 66 phase checks and adds
synthetic snapshot checks for redaction, unknown symbols, bounds, disappearing
threads, malformed observations, diagnostic failures, serving silence and lifecycle
order/exception precedence. The additional management bridge case creates one
test-owned non-daemon thread with a synthetic secret-like name, observes its exact
ID/state/daemon/stack through the real `ThreadMXBean` adapter, checks output privacy,
then releases and joins it in `finally`. Its wait and join are bounded. The author
does not execute Java; root compilation/checks and the next private initializer
observation are separate gates.
This diagnostic is not a JVM lifetime repair or installation acceptance.
