# Initializer failure evidence

A failed one-shot initializer is removed by the existing Compose command. The
runtime keeps its nonzero status and generic error message, and now carries an
optional `startup_failure` object from the owned service's fixed JSON record.
The CLI revalidates that object, and the lifecycle receipt revalidates the CLI
envelope before retaining it. This identifies a reported stage/category; it
does not establish the underlying cause or a successful operation.

Only the finite service stage/code/category contract and validated numeric errno,
child status and cleanup flag can survive. Raw output, detail text, exception
values, paths, SQL, credentials and tracebacks are discarded. Unknown fields,
invalid types, duplicate JSON keys, mismatched categories, ambiguous records and
oversized records produce the existing generic failure without metadata. No raw
stream is written to a log by this change. Ordinary warning text is ignored;
any malformed or oversized JSON object line withholds metadata, even when
another valid failure record is present. Existing bounded subprocess capture,
cleanup, command arguments and initializer removal stay in place.

The service and installer validators live in their separately packaged modules;
the focused test binds their finite contracts and exercises emitted records.
Other tests cover secret-bearing noise, malformed metadata, CLI validation and
actual lifecycle receipt projection with inert producer doubles. The retained
baseline demonstrates that the prior runtime discarded a valid startup record.
Actual installation behavior still requires the reviewed native lifecycle run.
