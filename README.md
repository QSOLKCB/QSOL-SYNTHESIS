# QSOL-SYNTHESIS

**Cross-project research synthesis of recurring structures across QSOL-IMC.**

## Central research question

> How do the major QSOL-IMC research projects relate to one another, and what recurring ideas connect them across repositories and publications?

## Working thesis

A recurring methodological pattern appears around **trustworthy transformations**: preserving meaningful structure under transformation while keeping observation, representation, computation, provenance, validation, authority, and interpretation epistemically distinct.

This is an investigative synthesis, not a claim that the projects share one physical mechanism or ontology.

## Current synthesis

The first public baseline identifies recurring structures around:

- representation versus referent;
- observation as an explicit transform;
- determinism versus truth;
- provenance and replay;
- oracle → candidate → parity;
- recovery under transformation;
- externalised state and semantic transport;
- authority partitioning;
- falsification and explicit nonclaims;
- preservation and compatibility.

The long-form first draft lives in [paper/](paper/). Start with [the abstract](paper/00-abstract.md) and [trustworthy transformations](paper/05-trustworthy-transformations.md).

## Research architecture

~~~text
SOURCE / STATE
      |
      v
TRANSFORMATION
      |
      v
OBSERVATION
      |
      v
COMPARISON / VALIDATION
      |
      +----> REJECT / QUALIFY
      |
      v
RECOVERY / PRESERVATION
      |
      v
PROVENANCE
      |
      v
INTERPRETATION WITH CLAIM BOUNDARIES
~~~

Not every project implements every stage.

## Evidence model

QSOL-SYNTHESIS separates three things:

1. **Raw discovery** — public API observations written under data/raw/.
2. **Curated corpus** — reviewed project/publication/theme/relationship records under data/.
3. **Interpretive synthesis** — project summaries, theme essays, and the paper draft.

Raw discovery never automatically becomes curated evidence.

## Reproduce and validate the curated baseline

~~~bash
python scripts/build_indexes.py --check
python scripts/validate_sources.py
~~~

To refresh raw public discovery without changing the curated synthesis:

~~~bash
python scripts/collect_github.py
python scripts/collect_zenodo.py
~~~

The collectors write under data/raw/ by default.

## Claim boundaries

- recurring structure != shared mechanism
- formal analogy != physical identity
- replayability != truth
- determinism != empirical validation
- simulation != physical validation
- raw discovery != curated evidence
- publication != confirmation

See [docs/CLAIM-BOUNDARIES.md](docs/CLAIM-BOUNDARIES.md).

## Repository map

- data/ — curated registries and source index
- data/raw/ — optional raw API discovery snapshots
- projects/ — evidence-linked project summaries
- themes/ — atomic theme indexes and cross-project essays
- paper/ — substantive first-draft synthesis
- evidence/ — project-theme matrix
- figures/ — lightweight diagrams
- scripts/ — collectors, deterministic index builder, and validator
- docs/ — corpus, methodology, glossary, claim boundaries, research evolution

## Status

**v0.1 research baseline candidate.** The repository now contains a substantive first-pass synthesis and validation contract, but it remains intentionally revisable as additional repositories, publications, and counterexamples are reviewed.

Licence: MPL-2.0.
