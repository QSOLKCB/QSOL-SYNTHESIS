# Recurring Structures

The project-theme matrix exposes several motifs that recur often enough to justify cross-project analysis.

## 1. Representation versus referent

UFT-ID, QSOL-MAP, GEO-REASON, E8_MUSIC, SPECTRAL and COSMO all separate a chosen representation from stronger ontological claims. The exact semantics differ, but the shared rule is that a mapping must not silently inherit the authority of its source or vice versa. Sources: `src:uft-id-3-0:readme`, `src:qsol-map:readme`, `src:qsol-geo-reason:readme`, `src:e8-music:readme`, `src:spectral:readme`, `src:cosmo:readme`.

## 2. Observation as an explicit transform

Observation is rarely treated as neutral. Coarse-graining, hidden-state capture, acoustic transforms, catalogue selection and sonification receivers all introduce choices. Those choices become part of the evidence contract. Representative sources: `src:uft-id-3-0:readme`, `src:qsol-geo-reason:readme`, `src:e8-music:readme`, `src:uff:readme`.

## 3. Determinism as auditability

QEC, UFF, E8_MUSIC, SPECTRAL, GALAXY and several infrastructure projects use deterministic artifacts, hashing or replay. Yet their own documentation repeatedly restricts what determinism proves. It identifies computation; it does not establish nature. Sources: `src:qec:readme`, `src:uff:readme`, `src:e8-music:readme`, `src:spectral:readme`, `src:galaxy:readme`.

## 4. Oracle → candidate → parity

GALAXY, QSOLQEC, QEC and PSYCLE-LINUX preserve a reference while a candidate implementation is tested. This makes optimization and migration reversible at the evidence level: the candidate can fail without erasing the baseline. Sources: `src:galaxy:readme`, `src:qsolqec:readme`, `src:qec:readme`, `src:psycle-linux:readme`.

## 5. Provenance and replay

Provenance appears not only in archival projects but in active scientific computation. A result is increasingly represented as value + source identity + method + transformation + replay evidence. Representative sources: `src:qec:readme`, `src:uff:readme`, `src:galaxy:readme`.

## 6. Externalised state

SEMANTIC-RELAY, SUBSTRATE, NEXUS, CONTROL and LATTICE investigate or depend on state that survives beyond one process or model context. The external artifact becomes a bounded carrier whose authority must still be declared. Sources: `src:qsol-semantic-relay:readme`, `src:qsol-substrate:readme`, `src:qsol-nexus:readme`, `src:qsol-control:readme`, `src:lattice:readme`.

## 7. Authority partitioning

SUBSTRATE knows, ORACLE witnesses, NEXUS reasons, CONTROL operates, and QSOL-QEC-BRIDGE validates candidates without owning QEC adoption. The repeated design rule is that capability does not imply authority. Sources: `src:qsol-substrate:readme`, `src:qsol-oracle:readme`, `src:qsol-nexus:readme`, `src:qsol-control:readme`, `src:qsol-qec-bridge:readme`, `src:qec:readme`.

## 8. Falsification and nonclaims

UFT-ID, UFF, GEO-REASON and COSMO increasingly encode evidence ceilings directly. A result is accompanied by statements about the stronger conclusions it does not support. Sources: `src:uft-id-3-0:readme`, `src:uff:readme`, `src:qsol-geo-reason:readme`, `src:cosmo:readme`.

These structures are not universal across every repository. Their importance lies in recurrence across multiple project families, not in total coverage.
