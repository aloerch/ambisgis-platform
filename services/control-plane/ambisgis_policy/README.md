# Catalog read-policy module

`catalog.py` implements the read-only policy endpoint using the installed owned
GeoNode models and guardian object permissions. `gateway.py` implements the
bounded WFS gateway used by the FND-03 spike. The companion engine filter is
`services/gateway/CatalogPolicyFilter.java`.

The same native catalog is consulted at both boundaries for every request.
These modules hold no user or sharing database and no positive-decision cache.
They expose no administration or sharing mutations. Synthetic test mutations
live in `build-support/geonode/catalog_fixture.py` and never run as part of
request authorization.

This is a source-owned product spike, not an installation artifact. Supported
requests are explicitly limited by the parser. General service registration,
TLS, user-facing sharing, OIDC installation and other output types must be
implemented and tested before expanding that surface. See ADR 011 and the
declared catalog matrix for scope and actual evidence.
