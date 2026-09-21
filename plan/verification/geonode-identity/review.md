# Scoped engineering review

The source/build, native-verifier and fixture/runtime work received independent
cross-review before publication. Review is engineering evidence; it does not
replace the owner's new authentication/security or license decisions.

Material findings corrected in executable code:

- Native tokeninfo did not establish confidential-client authentication, bind the
  token to that client, reject inactive users or isolate session-aware lookup.
  Baseline HTTP failures are retained. The source repair defaults off and checks
  all four conditions; it removes token reflection only in the strict branch.
- User-Basic and session-control middleware ran before that view. Exact-resolved-
  callback guards keep client credentials separate and preserve browser state.
  Real Django Client tests cover malformed Basic, stale sessions and ordinary
  user authentication outside this endpoint.
- A previously installed bytecode cache could weaken source-origin checks.
  Every runtime now uses a fresh private Python cache; installed owned files are
  matched to source-built wheels and unexpected files/symlinks are rejected.
- The response scanner originally treated intended token/cookie delivery too
  broadly. It now allows only explicit token fields/headers in their expected
  channels, rejects configuration secrets even there, and handles strict tokeninfo
  omission separately. Duplicate headers remain visible. Native logout messages
  require their own narrowly scoped, decoded-content policy.
- Source redaction could hide a credential emission from downstream scans. Known
  credentials, credential-field patterns and private-key counters now fail the
  receipt before sanitized retention. Conservative opaque-value counters remain
  separately reported. Capture controls are required on both service starts.
- Native disabled-login routing and a page containing multiple CSRF forms invalidated
  guessed harness assumptions. Expected routing now comes from native URL reversal;
  the exact same-origin form action is selected with duplicate-form rejection.
- Provisioning could commit before diagnostic capture failed. Cleanup is now
  attempted whenever provisioning starts; source secrets are invalidated even if
  the provisioning command does not obtain a successful receipt. Scrub failures
  explicitly fail the final result. Supervisor termination permits its task-process
  cleanup handler to run.

- A fixed four-identity request order aligned with servlet worker rotation and
  missed sequential mixed-identity reuse despite correct individual outcomes.
  Each round now rotates the order; all request counts, identity counts and the
  required observed mixed-worker evidence remain unchanged. Independent review
  found no weakened acceptance condition in this adjustment.

All 38 selected native Django cases passed during repaired attempts. Source-transform,
protocol, diagnostic and integrity tests run separately from these native tests.
The final evidence index records current full counts and successful HTTP evidence;
failed attempts retain their original failure state.

Accepted scope limits are explicit: manual GeoServer XML role projection; no
GeoServer browser SSO acceptance from GeoNode-cookie tests; concurrency attribution
for resource requests rather than inferred individual verifier calls; WARNING/ERROR
live logging plus targeted strict-helper DEBUG tests; intermediate login/consent
HTML represented by safe protocol metadata rather than a claim of exhaustive
response-secret scanning; the retained PostgreSQL supervisor exception; and
incomplete dependency/toolchain/license closure. These are not waived product gates.
