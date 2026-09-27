# Provenance, Replay, and Evidence

Many repositories treat provenance as executable infrastructure.

QEC's canonical JSON, SHA-256 identities, replay validation and source-bound claim enforcement make computation auditable as an artifact chain. UFF uses similar machinery to freeze source identities, distinguish integrity-only bundles from admitted replay evidence, and separate replay from statistical or physical calibration. E8_MUSIC records source, canonical signal, PCM and WAV identities so each transformation can be reconstructed without pretending the hashes validate the underlying science. SPECTRAL uses manifests, fingerprints and deterministic modes for the same general reason.

This suggests an important formulation:

RESULT = VALUE + SOURCE IDENTITY + METHOD + TRANSFORMATION IDENTITY + CLAIM BOUNDARY

That is not literally the schema of every project, but it captures the direction of the evidence architecture.

Replay then becomes a test of whether the declared computational history is internally reproducible. It can catch substitution, hidden transformation, incompatible implementation, or accidental drift. It cannot demonstrate that the source data were honestly generated, that a statistical model is appropriate, or that a physical interpretation is correct unless those questions are separately operationalized.

The same distinction appears in preservation work. PSYCLE-LINUX does not treat a successful build as proof of behavioural compatibility; it retains source and reference identities plus observed parity evidence.

This is why provenance is central to the synthesis. It converts “trust me, this is the same result” into a chain that can be inspected—and just as importantly, it exposes where the chain stops.
