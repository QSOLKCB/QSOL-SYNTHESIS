# Methodology

## 1. Discover

Raw collectors enumerate public repositories and candidate Zenodo records. Discovery outputs are stored separately from the curated synthesis.

## 2. Curate

A project enters data/projects.json only after a first-party source establishes its purpose and relevance. A publication enters data/publications.json only when its identifier and project relationship are supported by first-party or verified publication metadata.

## 3. Classify relationships

Current relationship classes include:

- implementation-dependency
- evidence-dependency
- promotion-dependency
- historical-lineage
- shared-methodological-principle
- shared-provenance-architecture
- shared-validation-architecture
- analogous-computational-structure

All current classes are non-mechanism relationships. mechanism_claim must therefore be false.

## 4. Tag themes

Project theme tags are backed by the indexed first-party project source. build_indexes.py places those theme names in the corresponding source-index supports list.

The project-theme matrix is generated from the curated project registry and validated against those source supports.

## 5. Synthesize

Theme essays and paper sections compare documented structures across domains. Comparisons must name the level of similarity: formal, implementation, evidence, historical, methodological, or analogical.

## 6. Search for disconfirming cases

The central “trustworthy transformations” thesis is not assumed universal. Counterexamples, weak fits, creative projects, and projects without oracle/replay structures are useful tests of whether the thesis is too broad.

## 7. Reproduce the curated index

~~~bash
python scripts/build_indexes.py --check
python scripts/validate_sources.py
~~~

Raw network refreshes are optional and non-authoritative:

~~~bash
python scripts/collect_github.py
python scripts/collect_zenodo.py
~~~
