# Native catalog OAuth bootstrap comparison

The selected `geonode-oauth-toolkit` 2.2.3.1 Application model stores
`client_secret` as a plain CharField. Its validator compares that stored value
with the supplied client secret. The owned GeoNode token-info implementation
uses Django `constant_time_compare` for this same native contract.

The development initializer now uses that constant-time raw-secret comparison.
Django's `check_password` expects an encoded user-password hash and rejects the
matching generated raw client secret. This correction does not hash, rotate or
rewrite an existing client secret. Application name, redirect URI, client and
grant types, authorization setting, owner binding, principal privileges,
resource binding, token binding, transaction and advisory-lock behavior remain
unchanged; a conflict still stops initialization.

Portable regressions call the actual initializer with synthetic model and
transaction collaborators. They cover creation, repetition with retained
credentials/metadata, wrong secrets, unsupported stored password hashes and
existing metadata/owner/privilege/resource/token conflicts. A separate retained
Django/OAuth source witness exercises the selected comparison functions with
synthetic values. Neither check runs Django setup, model persistence, a database
or a native service. Actual attempt013 reported only
`catalog_bootstrap/invalid_input/validation`; its exact exception frame was not
observed. This source defect and its regression do not establish the original
failure's exact cause or installation acceptance. A rebuilt ordinary
installation must verify the resulting behavior.
