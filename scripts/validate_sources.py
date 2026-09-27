#!/usr/bin/env python3
"""Validate the curated QSOL-SYNTHESIS corpus and its evidence boundaries."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys

DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GITHUB_REPO_RE = re.compile(r"^https://github\.com/([^/]+/[^/#?]+)(?:/|$)")
GITHUB_BLOB_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/blob/([^/]+)/(.+)$")
ZENODO_RECORD_RE = re.compile(r"^https://zenodo\.org/records/\d+/?$")
DOI_SOURCE_RE = re.compile(r"^https://doi\.org/10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)

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
ALLOWED_SOURCE_TYPES = {"github-readme", "publication-metadata"}


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_id_for_project(project_id: str) -> str:
    return f"src:{project_id.removeprefix('project:')}:readme"


def valid_date(value) -> bool:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        return dt.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def github_repository(url: str | None) -> str | None:
    if not isinstance(url, str):
        return None
    match = GITHUB_REPO_RE.match(url)
    return match.group(1) if match else None


def traceable_publication_source(url: str | None) -> bool:
    if not isinstance(url, str) or not url:
        return False
    return bool(
        GITHUB_BLOB_RE.fullmatch(url)
        or ZENODO_RECORD_RE.fullmatch(url)
        or DOI_SOURCE_RE.fullmatch(url)
    )


def validate(root: pathlib.Path) -> list[str]:
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

    curated_docs = {
        "projects.json": projects_doc,
        "publications.json": publications_doc,
        "themes.json": themes_doc,
        "relationships.json": relationships_doc,
        "project-publication-links.json": links_doc,
        "source-index.json": sources_doc,
    }
    date_values = []
    for name, doc in curated_docs.items():
        value = doc.get("generated_at")
        if not valid_date(value):
            fail(f"{name} generated_at must use a real YYYY-MM-DD date: {value!r}")
        date_values.append(value)
    if len(set(date_values)) != 1:
        fail(f"curated generated_at values must agree: {sorted(str(x) for x in set(date_values))}")
    corpus_date = date_values[0] if date_values else None

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
    repo_by_project = {p.get("id"): p.get("repo") for p in projects}
    repo_casefold = {repo.casefold(): repo for repo in repo_set if isinstance(repo, str)}

    for project in projects:
        source = project.get("source")
        match = GITHUB_BLOB_RE.fullmatch(source or "")
        if not match:
            fail(f"project source must be a traceable GitHub blob URL: {project.get('id')}")
        elif match.group(1) != project.get("repo"):
            fail(f"project source repository mismatch: {project.get('id')} -> {match.group(1)}")

    pub_ids = [p.get("id") for p in pubs]
    if None in pub_ids or len(pub_ids) != len(set(pub_ids)):
        fail("publication IDs must be non-null and unique")
    pub_set = set(pub_ids)

    doi_seen: dict[str, str] = {}
    for pub in pubs:
        doi = pub.get("doi")
        if doi:
            if not DOI_RE.fullmatch(doi):
                fail(f"invalid DOI syntax: {doi}")
            normalized_doi = doi.casefold()
            if normalized_doi in doi_seen:
                fail(f"duplicate DOI ignoring case: {doi} conflicts with {doi_seen[normalized_doi]}")
            doi_seen[normalized_doi] = doi
        concept_doi = pub.get("concept_doi")
        if concept_doi and not DOI_RE.fullmatch(concept_doi):
            fail(f"invalid concept DOI syntax: {concept_doi}")
        assoc = pub.get("repository_association")
        if assoc and assoc not in project_set:
            fail(f"publication association missing project: {pub.get('id')} -> {assoc}")
        if not traceable_publication_source(pub.get("source")):
            fail(f"publication requires a traceable source URL: {pub.get('id')}")
        source_repo = github_repository(pub.get("source"))
        if source_repo and source_repo.casefold() not in repo_casefold:
            fail(f"publication source repository is outside the curated corpus: {pub.get('id')} -> {source_repo}")

    theme_names = [t.get("name") for t in themes]
    if None in theme_names or len(theme_names) != len(set(theme_names)):
        fail("theme names must be non-null and unique")
    theme_set = set(theme_names)

    theme_id_list = [t.get("id") for t in themes]
    if None in theme_id_list or len(theme_id_list) != len(set(theme_id_list)):
        fail("theme IDs must be non-null and unique")
    theme_ids = set(theme_id_list)
    for theme in themes:
        if theme.get("id") != f"theme:{theme.get('name')}":
            fail(f"theme ID/name mismatch: {theme.get('id')} vs {theme.get('name')}")

    for project in projects:
        project_themes = project.get("themes", [])
        if len(project_themes) != len(set(project_themes)):
            fail(f"project themes must be unique: {project.get('id')}")
        for theme in project_themes:
            if theme not in theme_set:
                fail(f"unknown project theme: {project.get('id')} -> {theme}")

    link_keys = []
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
        evidence = link.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            fail(f"publication link requires evidence: {link.get('project_id')} -> {link.get('publication_id')}")
        link_keys.append((link.get("project_id"), link.get("publication_id"), relation))
    if len(link_keys) != len(set(link_keys)):
        fail("project-publication links must be unique")

    relationship_keys = []
    for rel in rels:
        source_id = rel.get("source")
        target_id = rel.get("target")
        if source_id not in project_set:
            fail(f"relationship source missing: {source_id}")
        if target_id not in project_set:
            fail(f"relationship target missing: {target_id}")
        if source_id == target_id:
            fail(f"self relationship is not allowed: {source_id}")
        if rel.get("relation_type") not in NON_MECHANISM_RELATIONS:
            fail(f"unknown/unreviewed relationship type: {rel.get('relation_type')}")
        if rel.get("mechanism_claim") is not False:
            fail(f"current relationship classes must set mechanism_claim=false: {source_id} -> {target_id}")
        theme = rel.get("theme")
        if theme and f"theme:{theme}" not in theme_ids:
            fail(f"relationship theme missing: {theme}")

        evidence = rel.get("evidence")
        endpoint_repos = {
            repo_by_project.get(source_id, "").casefold(),
            repo_by_project.get(target_id, "").casefold(),
        }
        if not isinstance(evidence, list) or not evidence:
            fail(f"relationship requires first-party GitHub evidence: {source_id} -> {target_id}")
        else:
            for url in evidence:
                evidence_repo = github_repository(url)
                if evidence_repo is None:
                    fail(f"relationship evidence must be a GitHub repository URL: {source_id} -> {target_id}: {url!r}")
                elif evidence_repo.casefold() not in endpoint_repos:
                    fail(
                        f"relationship evidence repository must match an endpoint: "
                        f"{source_id} -> {target_id}: {evidence_repo}"
                    )
        relationship_keys.append((source_id, target_id, rel.get("relation_type"), theme))
    if len(relationship_keys) != len(set(relationship_keys)):
        fail("relationships must be unique by endpoints, type, and theme")

    source_ids = [s.get("source_id") for s in sources]
    if None in source_ids or len(source_ids) != len(set(source_ids)):
        fail("source IDs must be non-null and unique")
    source_by_id = {s["source_id"]: s for s in sources if s.get("source_id")}

    for src in sources:
        repository = src.get("repository")
        path = src.get("path")
        source_type = src.get("source_type")
        if source_type not in ALLOWED_SOURCE_TYPES:
            fail(f"unknown source type: {src.get('source_id')} -> {source_type}")
        if not isinstance(repository, str) or not repository:
            fail(f"source repository must be traceable: {src.get('source_id')}")
        elif repository not in repo_set:
            fail(f"source repository is not a curated project repository: {src.get('source_id')} -> {repository}")
        if not isinstance(path, str) or not path:
            fail(f"source path must be traceable: {src.get('source_id')}")
        access_date = src.get("access_date")
        if not valid_date(access_date):
            fail(f"source access_date must use a real YYYY-MM-DD date: {src.get('source_id')} -> {access_date!r}")
        elif corpus_date is not None and access_date != corpus_date:
            fail(f"source access_date must match curated generated_at: {src.get('source_id')}")

        supports = src.get("supports")
        if not isinstance(supports, list):
            fail(f"source supports must be a list: {src.get('source_id')}")
            continue
        if len(supports) != len(set(supports)):
            fail(f"source supports must be unique: {src.get('source_id')}")
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
        thematic_supports = set(src.get("supports", [])) & theme_set
        project_themes = set(project.get("themes", []))
        if thematic_supports != project_themes:
            fail(
                f"project/source theme support mismatch: {project['id']} "
                f"project={sorted(project_themes)} source={sorted(thematic_supports)}"
            )

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
                continue
            supported = theme in supports
            positive = value in {"documented", "partial"}
            if positive and not supported:
                fail(f"matrix evidence not backed by source index: {pid} -> {theme}")
            if supported and not positive:
                fail(f"matrix denies declared theme support: {pid} -> {theme}")

    for directory in ("paper", "themes", "projects"):
        for path in (root / directory).glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if "Bootstrap placeholder" in text or "Draft section. This bootstrap" in text:
                fail(f"placeholder prose remains: {path.relative_to(root)}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[1],
        help="Repository root to validate (used by deterministic regression tests).",
    )
    args = parser.parse_args(argv)

    errors = validate(args.root)
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    projects = read_json(args.root / "data" / "projects.json").get("projects", [])
    pubs = read_json(args.root / "data" / "publications.json").get("publications", [])
    rels = read_json(args.root / "data" / "relationships.json").get("relationships", [])
    print(f"Validation OK: {len(projects)} projects, {len(pubs)} publications, {len(rels)} relationships")
    return 0


if __name__ == "__main__":
    sys.exit(main())
