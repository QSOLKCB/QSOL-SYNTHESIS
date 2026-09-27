# Cross-Domain Comparison

Cross-domain comparison is useful only when the comparison object is explicit.

| Domain | Source / state | Transformation | Reference or control | Preserved / tested property | Source |
| --- | --- | --- | --- | --- | --- |
| UFT-ID | informational state | evolution / observation / recovery | declared admissibility and information functional | distinctions among state, observation and recovery | `src:uft-id-3-0:readme` |
| QEC | encoded logical/model state | noise / decode / candidate optimization | canonical decoder and replay contracts | logical/evidence behaviour | `src:qec:readme` |
| QSOLQEC | qudit computation model | alternative representation / backend | dense or bounded reference paths | exact or declared-approximate computation | `src:qsolqec:readme` |
| GALAXY | particle/model state | Barnes-Hut / GPU optimization | direct-force and earlier verified paths | force, trajectory and reproducibility parity | `src:galaxy:readme` |
| E8_MUSIC | mathematical/scientific source | receiver / sonification | frozen canonical profile | declared ratios / deterministic signal identity | `src:e8-music:readme` |
| SEMANTIC-RELAY | writer-derived semantic state | external artifact transport | NULL / SHUFFLED / RANDOM controls | task-relevant answer information | `src:qsol-semantic-relay:readme` |
| PSYCLE-LINUX | historical Psycle behaviour | Linux implementation change | original Psycle and donor oracles | playback/workflow compatibility | `src:psycle-linux:readme` |
| RIVET | application semantics | platform adaptation | capability contract | application behaviour under supported capabilities | `src:rivet:readme` |

The table does not reduce these domains to one formalism. Instead it identifies a common comparative vocabulary: source, transformation, reference, invariant, evidence, and failure.

This vocabulary clarifies both similarities and differences. In QEC the relevant invariants are tied to a declared computational error-correction model. In PSYCLE-LINUX they concern historical software behaviour. In E8_MUSIC they concern source-to-receiver mapping properties. In SEMANTIC-RELAY they concern paired experimental conditions.

The recurring architecture is therefore best understood as an epistemic and engineering pattern. It is strong enough to guide comparison, but intentionally too weak to imply a common physical mechanism.
