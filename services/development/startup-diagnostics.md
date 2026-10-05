# Bounded startup diagnostics

The fixed service entrypoint continues to exit nonzero on startup exceptions.
Its service_start_failed JSON now contains a fixed stage, code and category.
The database stages are input, identity, storage, password, password_cleanup,
initdb, server, readiness and bootstrap. Other service exceptions use entrypoint.
Stages locate an operation; they do not assert its cause or successful completion.

Codes/categories are fixed pairs: invalid_input/validation, os_failure/os_error,
child_failed/child_exit, timeout/timeout, operation_failed/runtime and
unexpected/unexpected. Only known Python exception classes select these pairs;
unknown classes do not expose their names. Validated OS errno values and child
return codes may be included as integers. Boolean, missing, malformed and
out-of-range metadata is rejected or omitted. The final JSON projection
revalidates the entire fixed metadata object.

Exception values, filenames, SQL, DSNs, credentials, argv, child output and
tracebacks are never projected. Existing generic detail text remains.
Native command stdout handling and stderr suppression are unchanged; the helper
does not add output capture, network access, configuration authority or recovery.
A diagnostic such as initdb/child_failed with child_returncode 1 identifies the
failed operation, not a locale, permission or database cause.

The password file retains its fixed location, mode0600 and exclusive creation.
If opening it fails or a file already exists, this attempt never deletes it.
Once created, both password writing and initdb execution are inside its existing
finally cleanup. A cleanup error remains nonzero and sets cleanup_failed=true.
When both an operation and password removal fail, the original fixed failure is
preserved with that flag; the cleanup exception's text is not emitted.
No password-file deletion failure is suppressed. This does not reset an existing
database or change credential material.

Database commands, native privilege audits, server arguments, readiness timeout
and retry behavior, signal forwarding and server-finally wait remain in place.
An observed child exit during readiness supplies its bounded return code; expiry
of the existing deadline supplies timeout. The ready server's SystemExit status
is preserved. No locale settings, owned-source selection or image recipe change
is included.

Tests use synthetic temporary files and inert child/process doubles, including
secret-bearing errors/output, malformed metadata, exclusive ownership and
cleanup failures. They do not run PostgreSQL, a service, a container or a native
engine, and do not establish installed-product acceptance. Failed baseline and
fixture corrections are retained in the private execution evidence.
