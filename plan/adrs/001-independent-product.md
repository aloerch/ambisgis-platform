# ADR 001 — Independent product ownership

Status: accepted planning requirement from the user clarification, 19 September 2026.

Context: revision 1 optimized for a cohesive integration using thin forks and externally supplied database/desktop engines. The user requires independently maintained forked and combined software rather than dependence on future donor decisions.

Decision: adopt the source/build/repair/consolidation requirements of chapter 11, the fifteen-repository manifest and the GitHub Project governance of chapter 12. AmbisGIS is the provisional brand. Preserve donor source history and licenses; product development uses controlled branches and releases. No forced upstream sync or thin-patch constraint.

Consequences: AmbisGIS is responsible for code custody, transitive build inputs, vulnerability repair, migrations and the complete tested release. More source/build maintenance is intentional. Useful algorithms and security/process boundaries are retained. Unnecessary duplicate product authorities are removed.

Verification: FND-07/FND-08, OWN-01/OWN-02, SEC-04 and GOV-01/GOV-02. None of the product acceptance drills is claimed complete by the plan.
