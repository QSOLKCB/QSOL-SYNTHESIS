# Provenance and Replay

Provenance is not a decorative metadata layer in the corpus; it is often part of the experimental object.

QEC binds artifacts through canonical serialization, hashes, receipts and replay checks. UFF freezes input identities and distinguishes integrity from replay and calibration. SPECTRAL and E8_MUSIC preserve source-to-render identities and receiver choices. PSYCLE-LINUX records source identities and compatibility evidence so historical behaviour can be compared without silently changing the reference.

Replay answers a narrow but essential question: **can the declared result be reconstructed from the declared inputs and transformation?** Provenance answers: **which inputs, implementation and lineage are being claimed?**

Neither answers whether the scientific interpretation is true. That separation is a recurring design invariant.

Primary sources: src:qec:readme, src:uff:readme, src:spectral:readme, src:e8-music:readme, src:psycle-linux:readme.
