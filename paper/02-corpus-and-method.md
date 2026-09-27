# Corpus and Method

## Scope

The baseline corpus is public-only. It selects methodologically important QSOLKCB repositories rather than treating every repository in the organisation as equally relevant. Selection criteria include explicit research questions, reusable evidence/provenance architecture, repeated citation by other projects, formal or experimental significance, and direct relevance to the recurring themes under study.

Raw public discovery and curated synthesis are deliberately separated. scripts/collect_github.py and scripts/collect_zenodo.py write discovery snapshots under data/raw/. They do not automatically rewrite the curated project, publication, theme, or relationship registries. Promotion from discovery into the synthesis is a reviewed research act.

## Source hierarchy

The baseline prefers first-party sources: repository README files, CITATION.cff, .zenodo.json, release metadata, and project documentation. Zenodo API metadata is useful for verification and enrichment, but a failed external lookup does not authorize fabricated metadata. Representative indexed anchors include `src:uff:readme`, `src:e8-music:readme`, and `src:zenodo-22026554`.

data/source-index.json provides stable internal source identifiers. Project README sources also carry the theme tags they support. The project-theme matrix is validated against those source supports.

## Relationship classes

The graph distinguishes implementation dependency, evidence dependency, promotion dependency, historical lineage, methodological similarity, provenance similarity, validation-architecture similarity, and computational analogy. These labels prevent a conceptual similarity from masquerading as a mechanism claim.

Every current relationship edge is mechanism_claim=false. A future claim of shared physical mechanism would require a distinct relationship class and evidence appropriate to that much stronger assertion.

## Matrix semantics

The project-theme matrix uses documented, partial, and not-found. In the baseline, documented means the indexed first-party source supports the theme. not-found means the theme was not established by the indexed synthesis source; it does **not** mean the project lacks that property in every file or future release.

## Limitations

This is not an exhaustive bibliometric study and does not replace external peer review of the underlying scientific claims. It is a synthesis of the programme's own public artifacts and methodological relationships. The result is therefore strongest when describing documented architecture and weakest when making claims about historical motivation that are not explicitly recorded.

See docs/CORPUS.md and docs/METHODOLOGY.md for the operational rules.
