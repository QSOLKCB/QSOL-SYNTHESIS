# README4AI

## Scope

QSOL-SYNTHESIS is a synthesis layer over source repositories. It does not override source-project claim boundaries.

## Data authority

- data/raw/ is discovery material only.
- data/projects.json, data/publications.json, data/relationships.json and data/themes.json are curated synthesis inputs.
- data/source-index.json maps internal evidence identifiers to first-party sources.
- evidence/project-theme-matrix.csv is descriptive and must agree with curated source supports.

## Hard rules

1. Source repositories remain authoritative for their own project claims.
2. Structural similarity does not imply shared physical mechanism.
3. Inferred or analogical relationships must remain labelled as such.
4. Absence from the corpus means unavailable/not-yet-indexed, not false.
5. A not-found matrix cell means not established by the indexed synthesis source, not absent from the project.
6. DOI/publication links must be supported by first-party or verified publication metadata.
7. Raw API discovery does not automatically enter the curated corpus.
8. Reproducibility artifacts do not become scientific confirmation.
9. Never collapse computation, evidence, interpretation, governance, and physical claims.

## Preferred entrypoints

- data/projects.json
- data/publications.json
- data/relationships.json
- data/source-index.json
- evidence/project-theme-matrix.csv
- docs/CLAIM-BOUNDARIES.md
- paper/00-abstract.md

## Citation discipline

Synthesis prose uses source IDs such as src:qec:readme. Resolve them through data/source-index.json before repeating a factual claim.
