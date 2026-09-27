# Recovery Under Transformation

Recovery is a useful cross-domain comparison precisely because the domains are not equivalent.

In UFT-ID, recovery is an explicit deterministic operation that can return a proposed state to an admissible set. Its role is formal and diagnostic. Source: `src:uft-id-3-0:readme`.

In QEC, recovery concerns error-correction and decoder behaviour around encoded logical information. The repository's broader governance machinery preserves canonical baselines while candidate decoders prove replay and behavioural equivalence before promotion. Source: `src:qec:readme`.

QSOLQEC explores representations and decoders more permissively. QSOL-QEC-BRIDGE then acts as a promotion airlock: a candidate must be translated, independently reproduced and checked against relevant QEC contracts. Bridge success does not equal QEC adoption. Sources: `src:qsolqec:readme`, `src:qsol-qec-bridge:readme`, `src:qec:readme`.

In PSYCLE-LINUX, the damaged object is not a quantum state but compatibility across time and platform. Original Psycle remains the behavioural reference; candidate Linux engines are compared against it, and only demonstrated gaps justify targeted correction. Source: `src:psycle-linux:readme`.

RIVET frames portability similarly at the semantic level. Application meaning and required capabilities should survive changes in host platform where those capabilities exist. Source: `src:rivet:readme`.

The common structure is constrained correction under a preserved reference. The critical difference is what “correct” means in each domain. QSOL-SYNTHESIS therefore uses recovery as an analogous computational/methodological structure, never as evidence that the underlying physical processes are the same.
