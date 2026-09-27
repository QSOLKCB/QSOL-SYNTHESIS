# QSOL-CONTROL

**Repository:** [QSOLKCB/QSOL-CONTROL](https://github.com/QSOLKCB/QSOL-CONTROL)

## Purpose
Human/AI control plane orchestrating ORACLE evidence, NEXUS reasoning, replay, and recovery contracts.

## Research role

- orchestration-control-infrastructure
- compatibility-research

## Documented recurring themes

- [authority_partitioning](../themes/authority-partitioning.md)
- [provenance](../themes/provenance.md)
- [replay](../themes/replay.md)
- [external_state](../themes/external-state.md)
- [preservation](../themes/preservation.md)

## Cross-project connections

- → **project:qsol-oracle** — implementation-dependency; theme: provenance; mechanism_claim=false. CONTROL defines read-only ORACLE adapter and provenance boundaries.
- → **project:qsol-nexus** — implementation-dependency; theme: authority_partitioning; mechanism_claim=false. CONTROL invokes NEXUS council adapters while preserving governance authority separation.
- ← **project:lattice** — implementation-dependency; theme: external_state; mechanism_claim=false. CONTROL references LATTICE structural memory semantics while separating authority.

## Publications and archival records

- No curated publication link is registered yet.

## Claim discipline

This project summary records first-party project framing and synthesis relationships. A theme or relationship tag does not establish a shared physical mechanism, common ontology, or empirical confirmation.

## Sources

- [First-party project source](https://github.com/QSOLKCB/QSOL-CONTROL/blob/main/README.md)
- Source index key: **src:qsol-control:readme**
