# Ordinary installation lifecycle check

`lifecycle_check.py` verifies a concrete reviewed development bundle using a
fresh installation directory. It copies the exact verified closure and image
archives to a new bundle location before first initialization, then invokes the
actual `bin/ambisgis` CLI. Use the retained reviewed test interpreter:

```sh
python deploy/development/lifecycle_check.py \
  --bundle /absolute/reviewed-bundle/bundle.json \
  --bundle-sha256 EXACT_REVIEWED_MANIFEST_SHA256 \
  --directory /absolute/new-private-installation \
  --output /absolute/new-private-evidence
```

The installation and evidence directories must be distinct, absent paths. The
helper refuses existing application data. It verifies useful `up`, `status` and
`doctor` behavior, then runs the separately reviewed protected HTTP journey for
both enrolled principals. That journey checks actual map pixels, features,
metadata, denied access and revocation, and cleans up its own issued tokens.

The lifecycle check stops and starts only inspected containers belonging to this
installation. It checks that the previous metadata edit survived before making
any later edit. Installation configuration and credential bytes must remain
unchanged through restart and reinitialization. It then stops the renderer,
requires useful readiness and `doctor` failure, restores it and verifies state
again. A `finally` step stops remaining inspected installation containers; all
persistent data, image storage, configuration and evidence remain available for
inspection. No volume deletion or cleanup of unrelated installations occurs.

Receipts contain selected facts, source hashes and safe error types. Passwords,
tokens and response bodies are kept in memory. CLI output is checked for size and
known secrets after subprocess completion; the 4 MiB check is not streaming
memory enforcement. This helper assumes the exact reviewed CLI producer and a
recorded host shell/loader bootstrap. Subprocesses receive a clean environment.

Five inert tests verify bundle relocation, rejection of unexpected executable
members and existing data, and withholding secret-bearing receipts. They are
helper checks, not GIS acceptance. The initial discovery also ran 56 imported
installer fixture tests successfully; the import was then corrected so the
focused suite runs only its five intended cases.

Actual ordinary lifecycle execution remains pending. The helper always records
`full_installation_acceptance: false`; host isolation, private ports, egress,
resource limits, SELinux behavior and other applicable installation gates need
their own actual evidence. The held targeted container vulnerability probe is
not invoked or replaced by this check. Product release approval remains separate.
