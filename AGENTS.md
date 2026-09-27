# AGENTS

Guidance for contributors and coding agents working in QSOL-SYNTHESIS.

- Keep synthesis conservative and source-traceable.
- Label analogies as analogies.
- Keep mechanism claims `false` unless primary evidence supports stronger linkage.
- Do not fabricate DOI metadata, dates, or repository relationships.
- Preserve uncertainty explicitly.
- Raw API discovery is not curated evidence.
- Add a deterministic regression for every correctness or evidence-integrity bug fixed in `scripts/`.
- Treat publication ownership, lineage, DOI/concept-DOI identity, and duplicate curated registries as cross-file invariants; a local field check is not sufficient.
- Before finalizing edits, run:
  - `python -m unittest discover -s tests -v`
  - `python scripts/build_indexes.py --check`
  - `python scripts/validate_sources.py`
