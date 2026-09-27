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

    matrix = root / "evidence" / "project-theme-matrix.csv"
    with matrix.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("project_id") not in endpoint_ids:
                fail(errors, f"matrix project_id missing from projects registry: {row.get('project_id')}")

    doi_seen = {}
    for pub in pubs:
        doi = pub.get("doi")
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
