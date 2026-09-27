# Determinism and Truth

Determinism is pervasive in QSOL-IMC, but the mature repositories generally treat it as an **audit property**, not a truth criterion.

QEC uses canonical hashing and replay-safe validation to establish artifact identity and reproducibility. UFF explicitly separates replay verification from ensemble calibration and physical truth. E8_MUSIC proves or tests transform properties while stating that transform correctness is distinct from implementation conformance, scientific validation, and physical truth. NEXUS states that deterministic instrument output does not become authoritative merely because it replays.

The synthesis implication is important: deterministic systems reduce uncertainty about **what computation occurred**. They do not, by themselves, reduce uncertainty about **whether the model corresponds to nature**.

That distinction connects software engineering and research methodology across the corpus without claiming they are the same discipline.

Primary sources: src:qec:readme, src:uff:readme, src:e8-music:readme, src:qsol-nexus:readme.
