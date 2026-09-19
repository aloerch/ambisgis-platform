# Local package verification — revision 2

Verified in the preparation environment on 19 September 2026:

- `python3 -m unittest discover -s tests -v`: **55 tests passed**, no skipped tests. This includes mocked repository bootstrap safeguards, four schema/example checks, the illustrative merge reference, and nine ownership/Project-seed tests.
- `python3 tools/validate_package.py --require-schemas`: **passed**. Fifteen repositories, 66 tasks, 24 requirements and 65 source IDs have consistent references; dependencies are acyclic and test IDs are mapped. All four JSON Schema 2020-12 examples validate.
- `python3 tools/export_project_seed.py --out project-seed.json`: **passed**. Generated 66 unique task seeds locally, with dependency/acceptance text and valid initial custom-field options. No remote Project/issue IDs are fabricated.

Browser rendering checks passed at 1440-pixel desktop and 390-pixel mobile widths, with no page-width overflow or JavaScript page errors. Desktop and mobile previews were visually inspected. These are document-layout checks, not application accessibility certification.

The generated HTML and Markdown editions are rebuilt from the revised chapter files/backlog; the old integration-led book is not packaged as a competing instruction source. See the preparation report for HTML structural checks.

These results validate planning utilities and document consistency, **not** the GIS product, its security, a real database merge, upstream source custody, a clean source build or real GitHub API mutation. No remote GitHub repository/Project/issue provisioning occurred. The live Project importer, actual component builds and all product acceptance/independence exercises remain implementation tasks.
