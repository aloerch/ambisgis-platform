# AmbisGIS

AmbisGIS is an independently maintained GIS product under development. This repository holds the product plan, shared contracts and future control plane, gateway, publishing, portal and release orchestration.

Start with [the revision 2 plan](plan/README.md), [source ownership requirements](plan/docs/11-independent-product-and-source-ownership.md), and [delivery governance](plan/docs/12-github-projects-and-delivery.md). Individual specifications and machine-readable tasks are authoritative; the design book is a generated reference.

No GIS product capability or binary release is available yet. Repository creation and package tests do not establish source-build independence or GIS acceptance. AmbisGIS is a provisional name; binary branding and licensing remain review gates.

Run package checks from `plan/`:

```sh
python3 -m unittest discover -s tests -v
python3 tools/validate_package.py --require-schemas
```
