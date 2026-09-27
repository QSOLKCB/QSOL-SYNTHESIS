# Methodology

## Repository discovery

1. Enumerate public `QSOLKCB` repositories.
2. Prioritize research-heavy repositories using first-party descriptions.
3. Extract candidate publication metadata from README, `CITATION.cff`, and `.zenodo.json`.

## Relationship classification

Relationship edges are labelled by type (formal, implementation, historical, methodological, provenance, analogy). Analogical edges default to `mechanism_claim=false`.

## DOI handling

- DOI strings are preserved exactly as observed.
- DOI syntax is validated.
- Concept/version distinction is stored when explicit source evidence exists.
- No DOI metadata is invented when Zenodo lookup cannot be completed.

## Uncertainty policy

When sources conflict or are incomplete, records are marked as unresolved rather than normalized away.

## Refresh process

Run:

```bash
python scripts/collect_github.py
python scripts/collect_zenodo.py
python scripts/build_indexes.py
python scripts/validate_sources.py
```

Then review diffs manually before updating synthesis prose.
