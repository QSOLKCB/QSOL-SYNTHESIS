#!/usr/bin/env python3
"""Validation checks for QSOL-SYNTHESIS data files."""
from __future__ import annotations
import csv
import json
import pathlib
import re
import sys

DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], message: str):
    errors.append(message)


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    data = root / "data"
    errors: list[str] = []

    projects_doc = read_json(data / "projects.json")
    publications_doc = read_json(data / "publications.json")
    themes_doc = read_json(data / "themes.json")
    relationships_doc = read_json(data / "relationships.json")
    links_doc = read_json(data / "project-publication-links.json")
    source_index_doc = read_json(data / "source-index.json")

    projects = projects_doc.get("projects", [])
    pubs = publications_doc.get("publications", [])
    themes = themes_doc.get("themes", [])
    rels = relationships_doc.get("relationships", [])

    project_ids = [p.get("id") for p in projects]
    if len(project_ids) != len(set(project_ids)):
        fail(errors, "project IDs must be unique")

    pub_ids = [p.get("id") for p in pubs]
    if len(pub_ids) != len(set(pub_ids)):
        fail(errors, "publication IDs must be unique")

    for pub in pubs:
        doi = pub.get("doi")
        if doi and not DOI_RE.match(doi):
            fail(errors, f"invalid DOI syntax: {doi}")

    theme_ids = {t.get("id") for t in themes}
    theme_names = {t.get("name") for t in themes if t.get("name")}

    for project in projects:
        for theme_name in project.get("themes", []):
            if theme_name not in theme_names:
                fail(errors, f"project theme not present in themes registry: {project.get('id')} -> {theme_name}")

    theme_dir = root / "themes"
    for theme_name in theme_names:
        expected = theme_dir / f"{theme_name.replace('_', '-')}.md"
        if not expected.exists():
            fail(errors, f"missing theme documentation file: {expected.relative_to(root)}")
    allowed_composite_theme_pages = {
        "representation-and-referent",
        "observation-and-measurement",
        "determinism-and-truth",
        "recovery-under-transformation",
        "provenance-and-replay",
        "evidence-and-authority",
        "externalised-state",
        "oracle-candidate-parity",
        "falsification-and-nonclaims",
        "preservation-and-compatibility",
        "minimal-sufficient-systems",
    }
    for theme_file in theme_dir.glob("*.md"):
        normalized = theme_file.stem.replace("-", "_")
        if normalized in theme_names:
            continue
        if theme_file.stem in allowed_composite_theme_pages:
            continue
        fail(errors, f"theme file not represented in themes registry or allowed composite set: themes/{theme_file.name}")

    endpoint_ids = set(project_ids)
    for rel in rels:
        if rel.get("source") not in endpoint_ids:
            fail(errors, f"relationship source missing: {rel.get('source')}")
        if rel.get("target") not in endpoint_ids:
            fail(errors, f"relationship target missing: {rel.get('target')}")
        if rel.get("theme") and f"theme:{rel.get('theme')}" not in theme_ids:
            fail(errors, f"relationship theme missing: {rel.get('theme')}")
        if rel.get("relation_type", "").startswith("analog") and rel.get("mechanism_claim") is not False:
            fail(errors, "analogical relationships must set mechanism_claim=false")

    for link in links_doc.get("links", []):
        if link.get("project_id") not in endpoint_ids:
            fail(errors, f"publication link project missing: {link.get('project_id')}")
        if link.get("publication_id") not in set(pub_ids):
            fail(errors, f"publication link publication missing: {link.get('publication_id')}")

    for src in source_index_doc.get("sources", []):
        supports = src.get("supports")
        if not isinstance(supports, list):
            fail(errors, f"source index supports must be list: {src.get('source_id')}")
            continue
        allowed_support_tags = {"inventory", "publication-linking", "doi-linking"}
        for support in supports:
            if support in allowed_support_tags:
                continue
            if support not in theme_names:
                fail(errors, f"source index support tag is neither registered theme nor known support tag: {src.get('source_id')} -> {support}")

    matrix = root / "evidence" / "project-theme-matrix.csv"
    with matrix.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        matrix_columns = [c for c in (reader.fieldnames or []) if c and c != "project_id"]
        for col in matrix_columns:
            if col not in theme_names:
                fail(errors, f"matrix column not present in themes registry: {col}")
        for registered in theme_names:
            if registered not in matrix_columns:
                fail(errors, f"themes registry value missing from matrix columns: {registered}")
        for row in reader:
            if row.get("project_id") not in endpoint_ids:
                fail(errors, f"matrix project_id missing from projects registry: {row.get('project_id')}")

    doi_seen = {}
    for pub in pubs:
        doi = pub.get("doi")
        if not doi:
            continue
        if doi in doi_seen:
            fail(errors, f"duplicate DOI in publications.json: {doi}")
        doi_seen[doi] = pub.get("id")

    if errors:
        print("VALIDATION FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
