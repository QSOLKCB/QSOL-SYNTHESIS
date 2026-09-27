# Observation and Representation

Observation is one of the strongest bridges between the projects because it makes representational choices visible.

UFT-ID explicitly permits one fine trajectory to have different observed behaviour under different coarse-grainings. This establishes, at the framework level, that a property of an observation need not be a property of the underlying fine state. Source: `src:uft-id-3-0:readme`.

QSOL-MAP turns that warning into an engineering stack. A sampled signal, deterministic acoustic observation, learned tokenization, semantic interpretation and human report occupy different layers. No layer is allowed to silently promote itself into another. Source: `src:qsol-map:readme`.

E8_MUSIC and SPECTRAL use a similar separation for perceptual receivers. Canonical source-forced paths freeze receiver choices and preserve source identities; interpretive modes openly expose authored musical parameters. The distinction matters because an audible pattern can be reproducible without being an intrinsic physical sound emitted by the source. Sources: `src:e8-music:readme`, `src:spectral:readme`.

GEO-REASON applies the same logic to AI representations. Hidden-state geometry is measured under a chosen capture and representation procedure. Even a stable geometric effect would not, by itself, prove a mechanism of reasoning. Source: `src:qsol-geo-reason:readme`.

UFF adds the observational problem of scientific catalogues and model comparison. Replay can show that the declared computation was performed; calibration and external science are still required before stronger physical conclusions. Source: `src:uff:readme`.

Across these cases, the observer is part of the system description. That recurring design choice is a major reason representation/referent confusion is less likely to pass unnoticed.
