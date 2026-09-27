#!/usr/bin/env python3
"""Validate the curated QSOL-SYNTHESIS corpus and its evidence boundaries."""
from __future__ import annotations
import csv
import json
import pathlib
import re
import sys

DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
ALLOWED_MATRIX_VALUES = {"documented", "partial", "not-found"}
ALLOWED_LINK_RELATIONS = {"repository-associated-publication", "lineage-reference"}
NON_MECHANISM_RELATIONS = {
    "implementation-dependency",
    "evidence-dependency",
    "promotion-dependency",
    "historical-lineage",
    "shared-methodological-principle",
    "shared-provenance-architecture",
    "shared-validation-architecture",
    "analogous-computational-structure",
}
ALLOWED_SUPPORT_TAGS = {"inventory", "publication-linking", "doi-linking"}


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_id_for_project(project_id: str) -> str:
    return f"src:{project_id.removeprefix('project:')}:readme"


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    data = root / "data"
    errors: list[str] = []

    def fail(message: str) -> None:
        errors.append(message)

    projects_doc = read_json(data / "projects.json")
    publications_doc = read_json(data / "publications.json")
    themes_doc = read_json(data / "themes.json")
    relationships_doc = read_json(data / "relationships.json")
    links_doc = read_json(data / "project-publication-links.json")
    sources_doc = read_json(data / "source-index.json")

    curated_docs = [projects_doc, publications_doc, themes_doc, relationships_doc, links_doc, sources_doc]
    dates = {doc.get("generated_at") for doc in curated_docs}
    if len(dates) != 1:
        fail(f"curated generated_at values must agree: {sorted(str(x) for x in dates)}")

    projects = projects_doc.get("projects", [])
    pubs = publications_doc.get("publications", [])
    themes = themes_doc.get("themes", [])
    rels = relationships_doc.get("relationships", [])
    links = links_doc.get("links", [])
    sources = sources_doc.get("sources", [])

    project_ids = [p.get("id") for p in projects]
    if None in project_ids or len(project_ids) != len(set(project_ids)):
        fail("project IDs must be non-null and unique")
    project_set = set(project_ids)

    repos = [p.get("repo") for p in projects]
    if None in repos or len(repos) != len(set(repos)):
        fail("project repo identifiers must be non-null and unique")
    repo_set = set(repos)

    pub_ids = [p.get("id") for p in pubs]
    if None in pub_ids or len(pub_ids) != len(set(pub_ids)):
        fail("publication IDs must be non-null and unique")
    pub_set = set(pub_ids)

    doi_seen: set[str] = set()
    for pub in pubs:
        doi = pub.get("doi")
        if doi:
            if not DOI_RE.match(doi):
                fail(f"invalid DOI syntax: {doi}")
            if doi in doi_seen:
                fail(f"duplicate DOI: {doi}")
            doi_seen.add(doi)
        assoc = pub.get("repository_association")
        if assoc and assoc not in project_set:
            fail(f"publication association missing project: {pub.get('id')} -> {assoc}")

    theme_names = [t.get("name") for t in themes]
    if None in theme_names or len(theme_names) != len(set(theme_names)):
        fail("theme names must be non-null and unique")
    theme_set = set(theme_names)
    theme_ids = {t.get("id") for t in themes}

    for project in projects:
        for theme in project.get("themes", []):
            if theme not in theme_set:
                fail(f"unknown project theme: {project.get('id')} -> {theme}")

    for link in links:
        if link.get("project_id") not in project_set:
            fail(f"publication link project missing: {link.get('project_id')}")
        if link.get("publication_id") not in pub_set:
            fail(f"publication link publication missing: {link.get('publication_id')}")
        relation = link.get("relation")
        if relation not in ALLOWED_LINK_RELATIONS:
            fail(f"unknown publication link relation: {relation}")
        if relation == "repository-associated-publication":
            pub = next((p for p in pubs if p.get("id") == link.get("publication_id")), None)
            if pub and pub.get("repository_association") != link.get("project_id"):
                fail(f"publication ownership mismatch: {link.get('publication_id')}")

    for rel in rels:
        if rel.get("source") not in project_set:
            fail(f"relationship source missing: {rel.get('source')}")
        if rel.get("target") not in project_set:
            fail(f"relationship target missing: {rel.get('target')}")
        if rel.get("source") == rel.get("target"):
            fail(f"self relationship is not allowed: {rel.get('source')}")
        if rel.get("relation_type") not in NON_MECHANISM_RELATIONS:
            fail(f"unknown/unreviewed relationship type: {rel.get('relation_type')}")
        if rel.get("mechanism_claim") is not False:
            fail(f"current relationship classes must set mechanism_claim=false: {rel.get('source')} -> {rel.get('target')}")
        theme = rel.get("theme")
        if theme and f"theme:{theme}" not in theme_ids:
            fail(f"relationship theme missing: {theme}")
        evidence = rel.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x.startswith("https://github.com/") for x in evidence):
            fail(f"relationship requires first-party GitHub evidence: {rel.get('source')} -> {rel.get('target')}")

    source_ids = [s.get("source_id") for s in sources]
    if None in source_ids or len(source_ids) != len(set(source_ids)):
        fail("source IDs must be non-null and unique")
    source_by_id = {s["source_id"]: s for s in sources if s.get("source_id")}

    for src in sources:
        repository = src.get("repository")
        if repository is not None and repository not in repo_set:
            fail(f"source repository is not a curated project repository: {src.get('source_id')} -> {repository}")
        supports = src.get("supports")
        if not isinstance(supports, list):
            fail(f"source supports must be a list: {src.get('source_id')}")
            continue
        for support in supports:
            if support not in ALLOWED_SUPPORT_TAGS and support not in theme_set:
                fail(f"unknown source support tag: {src.get('source_id')} -> {support}")

    for project in projects:
        sid = source_id_for_project(project["id"])
        src = source_by_id.get(sid)
        if not src:
            fail(f"project source missing from source index: {sid}")
            continue
        if src.get("repository") != project.get("repo"):
            fail(f"project source repository mismatch: {sid}")
        supported = set(src.get("supports", []))
        for theme in project.get("themes", []):
            if theme not in supported:
                fail(f"project theme lacks source support: {project['id']} -> {theme}")

    matrix_path = root / "evidence" / "project-theme-matrix.csv"
    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = [c for c in (reader.fieldnames or []) if c != "project_id"]
        if set(columns) != theme_set or len(columns) != len(theme_set):
            fail("matrix theme columns must match the theme registry exactly")
        rows = list(reader)

    matrix_ids = [row.get("project_id") for row in rows]
    if len(matrix_ids) != len(set(matrix_ids)):
        fail("matrix project rows must be unique")
    if set(matrix_ids) != project_set:
        fail("matrix project rows must match projects.json exactly")

    for row in rows:
        pid = row.get("project_id")
        sid = source_id_for_project(pid)
        supports = set(source_by_id.get(sid, {}).get("supports", []))
        for theme in theme_set:
            value = row.get(theme)
            if value not in ALLOWED_MATRIX_VALUES:
                fail(f"invalid matrix value: {pid} {theme}={value}")
            if value in {"documented", "partial"} and theme not in supports:
                fail(f"matrix evidence not backed by source index: {pid} -> {theme}")

    # Documentation hygiene: bootstrap placeholders are not acceptable in a synthesis baseline.
    for directory in ("paper", "themes", "projects"):
        for path in (root / directory).glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if "Bootstrap placeholder" in text or "Draft section. This bootstrap" in text:
                fail(f"placeholder prose remains: {path.relative_to(root)}")

    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validation OK: {len(projects)} projects, {len(pubs)} publications, {len(rels)} relationships")
    return 0


if __name__ == "__main__":
    sys.exit(main())
