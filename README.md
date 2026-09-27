# QSOL-SYNTHESIS

QSOL-SYNTHESIS is a documentation-first research repository for cross-project synthesis across the public QSOL-IMC (`QSOLKCB`) corpus.

## Central research question

> How do the major QSOL-IMC research projects relate to one another, and what recurring ideas connect them across repositories and publications?

## Working thesis (investigative)

A recurring methodological pattern appears around **trustworthy transformations**: preserving meaningful structure under transformation while keeping observation, representation, computation, provenance, validation, and interpretation epistemically distinct.

This is a hypothesis to test, refine, qualify, or reject.

## Research architecture (working model)

```text
SOURCE / STATE
      |
      v
TRANSFORMATION
      |
      v
OBSERVATION
      |
      v
VALIDATION
      |
      +----> REJECT
      |
      v
RECOVERY / PRESERVATION
      |
      v
PROVENANCE
      |
      v
INTERPRETATION
```

Not every project implements every stage.

## Claim-boundary rules

- recurring structure != shared mechanism
- formal analogy != physical identity
- replayability != truth
- determinism != empirical validation
- simulation != physical validation

See [`docs/CLAIM-BOUNDARIES.md`](docs/CLAIM-BOUNDARIES.md).

## Repository structure

- `data/`: normalized metadata registries
- `projects/`: concise project summaries
- `themes/`: theme essays
- `paper/`: long-form synthesis draft sections
- `evidence/`: project-theme matrix
- `figures/`: lightweight diagrams (`mermaid`, `dot`)
- `scripts/`: reproducible metadata collection and validation
- `docs/`: corpus/methodology and claim boundary guidance

## Reproducing collection

```bash
python scripts/collect_github.py
python scripts/collect_zenodo.py
python scripts/build_indexes.py
python scripts/validate_sources.py
```

## Current status

Bootstrap corpus created with conservative evidence labels. Zenodo API verification remains partially blocked by environment DNS limits and is explicitly marked where unresolved.
