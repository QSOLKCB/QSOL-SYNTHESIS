# Corpus scope

## Selection strategy

This bootstrap corpus prioritizes repositories that are methodologically central, repeatedly cited across QSOLKCB project READMEs, or explicitly connected to provenance/replay/claim-boundary work.

## Public-only scope

Only public repositories and first-party public files were used.

## Completeness limits

- Organization scan was performed via GitHub MCP tooling (`search_repositories`) and shows 75 public repositories at collection time.
- The committed `data/github-repositories.json` currently contains a curated high-relevance subset, not the full 75-entry inventory.
- Not all repositories were deeply summarized in this bootstrap pass.
- Some named targets from the brief (for example `LEAF`) were not found in the observed public organization snapshot.

## Publication linkage limits

Zenodo DNS/API access was unavailable from this environment, so publication records are currently sourced from first-party README/CITATION/.zenodo metadata. These links are marked as metadata-derived and need follow-up Zenodo API verification.
