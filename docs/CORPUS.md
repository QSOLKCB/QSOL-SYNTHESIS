# Corpus

## Scope

The baseline is **public-only** and deliberately selective. QSOLKCB contains more public repositories than are included in the curated synthesis. Selection is based on methodological relevance to the research question, not popularity or perceived scientific merit.

At the 2026-09-27 review snapshot, 78 public repositories were observable through the connected GitHub inventory. data/github-repositories.json contains only the high-relevance subset selected for synthesis.

Private repositories are intentionally excluded from this public baseline even when maintainers can access them.

## Raw discovery versus curated corpus

scripts/collect_github.py and scripts/collect_zenodo.py write raw public API observations under data/raw/. These outputs are discovery aids. They do not overwrite:

- data/projects.json
- data/publications.json
- data/project-publication-links.json
- data/relationships.json
- data/themes.json

Promotion into those files requires review.

## Publication linkage

Publication records may be supported by first-party README, CITATION.cff, .zenodo.json, GitHub release metadata, or verified Zenodo metadata. Concept DOI, version DOI, archival predecessor, and lineage reference are kept distinct where the source supports that distinction.

A publication associated with one project may be cited by another project as lineage. That citation does not transfer publication ownership.

## Completeness

The corpus is not exhaustive. Counts are snapshots, repository documentation evolves, and publication metadata may be incomplete. Missing material is treated as unindexed rather than false or nonexistent.
