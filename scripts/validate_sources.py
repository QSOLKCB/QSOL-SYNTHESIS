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
ZENODO_RECORD_RE = re.compile(r"^https://zenodo\.org/records/(\d+)/?$")
DOI_SOURCE_RE = re.compile(r"^https://doi\.org/(10\.\d{4,9}/[-._;()/:A-Z0-9]+)$", re.IGNORECASE)
ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.(\d+)$", re.IGNORECASE)
SOURCE_ID_RE = re.compile(r"\bsrc:[A-Za-z0-9._-]+(?::[A-Za-z0-9._-]+)*\b")
PROJECT_ID_RE = re.compile(r"^project:[A-Za-z0-9._-]+$")
PUBLICATION_ID_RE = re.compile(r"^publication:[A-Za-z0-9._-]+$")
ZENODO_PUBLICATION_ID_RE = re.compile(r"^publication:zenodo-(\d+)$")
DOT_EDGE_RE = re.compile(
    r'^\s*"([^"]+)"\s*->\s*"([^"]+)"\s*\[label="([^"\\]+)\\n([^"]+)"\];\s*$',
    re.MULTILINE,
)
PROJECT_SUMMARY_REPO_RE = re.compile(
    r"\*\*Repository:\*\*\s*\[[^\]]+\]\(https://github\.com/([^/]+/[^/)]+)\)"
)

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
BILATERAL_RELATIONS = {
    "shared-methodological-principle",
    "shared-provenance-architecture",
    "shared-validation-architecture",
    "analogous-computational-structure",
}
SUMMARY_PUBLICATIONS_SECTION_RE = re.compile(
    r"^## Publications and archival records\s*$\n(?P<body>.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
DOI_TOKEN_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
ALLOWED_SUPPORT_TAGS = {"inventory", "publication-linking", "doi-linking"}
ALLOWED_SOURCE_TYPES = {"github-readme", "publication-metadata"}


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_id_for_project(project_id: str | None) -> str | None:
    if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
        return None
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


def normalize_repository(value: str | None) -> str | None:
    """Return the case-insensitive GitHub repository identity."""
    if not isinstance(value, str) or not value:
        return None
    return value.casefold()


def github_blob_identity(url: str | None) -> tuple[str, str, str] | None:
    """Return canonical repository identity plus exact ref/path for a GitHub blob."""
    if not isinstance(url, str):
        return None
    match = GITHUB_BLOB_RE.fullmatch(url)
    if not match:
        return None
    repository = normalize_repository(match.group(1))
    if repository is None:
        return None
    return repository, match.group(2), match.group(3)


def github_blob_source_matches(candidate: str | None, curated: str | None) -> bool:
    candidate_identity = github_blob_identity(candidate)
    return candidate_identity is not None and candidate_identity == github_blob_identity(curated)


def traceable_publication_source(url: str | None) -> bool:
    if not isinstance(url, str) or not url:
        return False
    return bool(
        GITHUB_BLOB_RE.fullmatch(url)
        or ZENODO_RECORD_RE.fullmatch(url)
        or DOI_SOURCE_RE.fullmatch(url)
    )


def publication_external_source_matches(pub: dict, source_url: str | None) -> bool:
    if not isinstance(source_url, str):
        return False

    identifiers = {
        value.casefold()
        for value in (pub.get("doi"), pub.get("concept_doi"))
        if isinstance(value, str) and value
    }

    doi_match = DOI_SOURCE_RE.fullmatch(source_url)
    if doi_match:
        return doi_match.group(1).casefold() in identifiers

    record_match = ZENODO_RECORD_RE.fullmatch(source_url)
    if record_match:
        allowed_record_ids = set()
        for identifier in identifiers:
            zenodo_match = ZENODO_DOI_RE.fullmatch(identifier)
            if zenodo_match:
                allowed_record_ids.add(zenodo_match.group(1))
        return record_match.group(1) in allowed_record_ids

    return False


def publication_link_evidence_is_valid(
    url: str,
    relation: str,
    project_repo: str | None,
    project_source: str | None,
    publication: dict | None,
    repository_by_project: dict[str, str],
) -> bool:
    if publication is None or not traceable_publication_source(url):
        return False

    evidence_repo = github_repository(url)

    owner_repo = repository_by_project.get(publication.get("repository_association"))

    if relation == "lineage-reference":
        # A lineage assertion needs evidence from the referencing project and
        # evidence that identifies the selected publication. Per-URL validation
        # accepts only those two evidence classes; the link-level validator
        # below requires that both classes are present.
        if evidence_repo is not None:
            return (
                github_blob_source_matches(url, project_source)
                or github_blob_source_matches(url, publication.get("source"))
            )
        return publication_external_source_matches(publication, url)

    if relation == "repository-associated-publication":
        # Each evidence item must bind either the asserted owner project or the
        # selected publication. The link-level validator requires both classes.
        if evidence_repo is not None:
            return (
                github_blob_source_matches(url, project_source)
                or github_blob_source_matches(url, publication.get("source"))
            )

        return publication_external_source_matches(publication, url)

    return False


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
    github_doc = read_json(data / "github-repositories.json")
    zenodo_doc = read_json(data / "zenodo-records.json")

    curated_docs = {
        "projects.json": projects_doc,
        "publications.json": publications_doc,
        "themes.json": themes_doc,
        "relationships.json": relationships_doc,
        "project-publication-links.json": links_doc,
        "source-index.json": sources_doc,
        "github-repositories.json": github_doc,
        "zenodo-records.json": zenodo_doc,
    }
    date_values = []
    for name, doc in curated_docs.items():
        value = doc.get("generated_at")
        if not valid_date(value):
            fail(f"{name} generated_at must use a real YYYY-MM-DD date: {value!r}")
        elif dt.date.fromisoformat(value) > dt.date.today():
            fail(f"{name} generated_at must not be in the future: {value!r}")
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
    invalid_project_ids = [
        project_id
        for project_id in project_ids
        if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id)
    ]
    if invalid_project_ids:
        fail(
            f"project IDs must be non-empty strings in the project: namespace: "
            f"{invalid_project_ids!r}"
        )
    if len(project_ids) != len(set(project_ids)):
        fail("project IDs must be unique")
    project_set = set(project_ids)
    project_by_id = {p.get("id"): p for p in projects if p.get("id")}

    summary_paths = [p.get("summary_path") for p in projects]
    if (
        any(
            not isinstance(path, str)
            or not path.startswith("projects/")
            or not path.endswith(".md")
            for path in summary_paths
        )
        or len(summary_paths) != len(set(summary_paths))
    ):
        fail("project summary_path values must be unique project Markdown paths")

    repos = [p.get("repo") for p in projects]
    normalized_repos = [normalize_repository(repo) for repo in repos]
    if None in normalized_repos or len(normalized_repos) != len(set(normalized_repos)):
        fail("project repo identifiers must be non-null and unique ignoring case")
    repo_normalized_set = {repo for repo in normalized_repos if repo is not None}
    repo_by_project = {p.get("id"): p.get("repo") for p in projects}
    project_by_repo = {
        normalize_repository(p.get("repo")): p
        for p in projects
        if normalize_repository(p.get("repo")) is not None
    }

    for project in projects:
        expected_url = f"https://github.com/{project.get('repo')}"
        project_url = project.get("url")
        if not isinstance(project_url, str) or project_url.casefold() != expected_url.casefold():
            fail(
                f"project URL must match repository: {project.get('id')} "
                f"expected {expected_url!r}, got {project.get('url')!r}"
            )
        source = project.get("source")
        match = GITHUB_BLOB_RE.fullmatch(source or "")
        if not match:
            fail(f"project source must be a traceable GitHub blob URL: {project.get('id')}")
        elif normalize_repository(match.group(1)) != normalize_repository(project.get("repo")):
            fail(f"project source repository mismatch: {project.get('id')} -> {match.group(1)}")

    github_rows = github_doc.get("repositories", [])
    github_full_names = [row.get("full_name") for row in github_rows]
    normalized_github_names = [normalize_repository(name) for name in github_full_names]
    if (
        None in normalized_github_names
        or len(normalized_github_names) != len(set(normalized_github_names))
    ):
        fail("curated GitHub registry repository identifiers must be non-null and unique ignoring case")
    if {name for name in normalized_github_names if name is not None} != repo_normalized_set:
        fail("curated GitHub registry repositories must match projects.json exactly")
    if github_doc.get("selected_count") != len(github_rows):
        fail("curated GitHub selected_count must equal repository row count")
    total_count = github_doc.get("total_count_observed")
    if not isinstance(total_count, int) or isinstance(total_count, bool) or total_count < len(github_rows):
        fail("curated GitHub total_count_observed must be an integer >= selected_count")

    for row in github_rows:
        project = project_by_repo.get(normalize_repository(row.get("full_name")))
        if project is None:
            continue
        if row.get("name") != project.get("name"):
            fail(f"curated GitHub project name mismatch: {row.get('full_name')}")
        row_url = row.get("html_url")
        project_url = project.get("url")
        if (
            not isinstance(row_url, str)
            or not isinstance(project_url, str)
            or row_url.casefold() != project_url.casefold()
        ):
            fail(f"curated GitHub project URL mismatch: {row.get('full_name')}")
        if row.get("classification") != project.get("role"):
            fail(f"curated GitHub classification mismatch: {row.get('full_name')}")
        curated_source = row.get("source")
        if not isinstance(curated_source, str) or not GITHUB_BLOB_RE.fullmatch(curated_source):
            fail(f"curated GitHub source must be a traceable blob URL: {row.get('full_name')}")
        elif not github_blob_source_matches(curated_source, project.get("source")):
            fail(
                f"project source must match independently curated GitHub source: "
                f"{row.get('full_name')}"
            )
        curated_publication_dois = row.get("publication_dois")
        normalized_curated_dois = (
            [doi.casefold() for doi in curated_publication_dois]
            if isinstance(curated_publication_dois, list)
            and all(isinstance(doi, str) and doi for doi in curated_publication_dois)
            else []
        )
        if (
            not isinstance(curated_publication_dois, list)
            or len(normalized_curated_dois) != len(curated_publication_dois)
            or len(normalized_curated_dois) != len(set(normalized_curated_dois))
        ):
            fail(
                f"curated GitHub publication_dois must be a unique string list: "
                f"{row.get('full_name')}"
            )
        else:
            expected_publication_dois = {
                pub.get("doi").casefold()
                for pub in pubs
                if (
                    pub.get("repository_association") == project.get("id")
                    and isinstance(pub.get("doi"), str)
                    and pub.get("doi")
                )
            }
            actual_publication_dois = set(normalized_curated_dois)
            if actual_publication_dois != expected_publication_dois:
                fail(
                    f"curated GitHub publication ownership mismatch: "
                    f"{row.get('full_name')} expected={sorted(expected_publication_dois)} "
                    f"actual={sorted(actual_publication_dois)}"
                )

        publication_sources = row.get("publication_sources")
        if not isinstance(publication_sources, dict):
            fail(
                f"curated GitHub publication_sources must be an object: "
                f"{row.get('full_name')}"
            )
        else:
            source_keys = [
                key.casefold()
                for key in publication_sources
                if isinstance(key, str) and key
            ]
            if (
                len(source_keys) != len(publication_sources)
                or len(source_keys) != len(set(source_keys))
                or any(
                    not isinstance(url, str) or not traceable_publication_source(url)
                    for url in publication_sources.values()
                )
            ):
                fail(
                    f"curated GitHub publication_sources must have unique DOI keys "
                    f"and traceable source URLs: {row.get('full_name')}"
                )
            else:
                expected_publication_sources = {
                    pub.get("doi").casefold(): pub.get("source")
                    for pub in pubs
                    if (
                        pub.get("repository_association") == project.get("id")
                        and isinstance(pub.get("doi"), str)
                        and pub.get("doi")
                    )
                }
                actual_publication_sources = {
                    doi.casefold(): url
                    for doi, url in publication_sources.items()
                }
                if actual_publication_sources != expected_publication_sources:
                    fail(
                        f"curated GitHub publication source binding mismatch: "
                        f"{row.get('full_name')}"
                    )

    pub_ids = [p.get("id") for p in pubs]
    invalid_pub_ids = [
        publication_id
        for publication_id in pub_ids
        if not isinstance(publication_id, str)
        or not PUBLICATION_ID_RE.fullmatch(publication_id)
    ]
    if invalid_pub_ids:
        fail(
            f"publication IDs must be non-empty strings in the publication: namespace: "
            f"{invalid_pub_ids!r}"
        )
    if len(pub_ids) != len(set(pub_ids)):
        fail("publication IDs must be unique")
    pub_set = set(pub_ids)

    doi_seen: dict[str, str] = {}
    for pub in pubs:
        doi = pub.get("doi")
        publication_id = pub.get("id")
        zenodo_id_match = (
            ZENODO_PUBLICATION_ID_RE.fullmatch(publication_id)
            if isinstance(publication_id, str)
            else None
        )
        zenodo_doi_match = (
            ZENODO_DOI_RE.fullmatch(doi)
            if isinstance(doi, str)
            else None
        )
        if zenodo_id_match is not None:
            if (
                zenodo_doi_match is None
                or zenodo_id_match.group(1) != zenodo_doi_match.group(1)
            ):
                fail(
                    f"Zenodo publication ID must match declared DOI record: "
                    f"{publication_id} -> {doi!r}"
                )
        elif zenodo_doi_match is not None:
            fail(
                f"Zenodo DOI publication must use matching publication:zenodo-* ID: "
                f"{publication_id!r} -> {doi}"
            )
        if not isinstance(doi, str) or not doi.strip():
            fail(f"publication DOI must be a non-empty identifier: {pub.get('id')}")
        else:
            if not DOI_RE.fullmatch(doi):
                fail(f"invalid DOI syntax: {doi}")
            normalized_doi = doi.casefold()
            if normalized_doi in doi_seen:
                fail(f"duplicate DOI ignoring case: {doi} conflicts with {doi_seen[normalized_doi]}")
            doi_seen[normalized_doi] = doi
        concept_doi = pub.get("concept_doi")
        if concept_doi is not None and (
            not isinstance(concept_doi, str) or not DOI_RE.fullmatch(concept_doi)
        ):
            fail(f"invalid concept DOI syntax: {concept_doi!r}")
        if pub.get("resource_type") == "concept-doi":
            if (
                not isinstance(concept_doi, str)
                or not concept_doi
                or not isinstance(doi, str)
                or concept_doi.casefold() != doi.casefold()
            ):
                fail(
                    f"concept-doi publication must self-identify with concept_doi equal to doi: "
                    f"{pub.get('id')}"
                )
        assoc = pub.get("repository_association")
        if assoc and assoc not in project_set:
            fail(f"publication association missing project: {pub.get('id')} -> {assoc}")
        source_url = pub.get("source")
        if not traceable_publication_source(source_url):
            fail(f"publication requires a traceable source URL: {pub.get('id')}")
        source_repo = github_repository(source_url)
        if source_repo and normalize_repository(source_repo) not in repo_normalized_set:
            fail(f"publication source repository is outside the curated corpus: {pub.get('id')} -> {source_repo}")
        if source_repo is not None:
            owner_repo = repo_by_project.get(assoc)
            if normalize_repository(source_repo) != normalize_repository(owner_repo):
                fail(
                    f"publication source repository must match associated repository: "
                    f"{pub.get('id')} -> {source_repo}"
                )
            owner_row = next(
                (
                    row
                    for row in github_rows
                    if normalize_repository(row.get("full_name"))
                    == normalize_repository(owner_repo)
                ),
                None,
            )
            owner_sources = owner_row.get("publication_sources") if owner_row else None
            expected_source = None
            if isinstance(owner_sources, dict) and isinstance(doi, str):
                expected_source = next(
                    (
                        url
                        for manifest_doi, url in owner_sources.items()
                        if isinstance(manifest_doi, str)
                        and manifest_doi.casefold() == doi.casefold()
                    ),
                    None,
                )
            if expected_source is None or not github_blob_source_matches(
                source_url, expected_source
            ):
                fail(
                    f"publication GitHub source must match independently curated source: "
                    f"{pub.get('id')}"
                )
        elif traceable_publication_source(source_url):
            if not publication_external_source_matches(pub, source_url):
                fail(f"publication external source does not match DOI/concept DOI: {pub.get('id')}")

    publication_by_id = {pub.get("id"): pub for pub in pubs}
    publication_by_doi = {
        pub.get("doi").casefold(): pub
        for pub in pubs
        if isinstance(pub.get("doi"), str) and pub.get("doi")
    }

    zenodo_rows = zenodo_doc.get("records", [])
    zenodo_dois = [row.get("doi") for row in zenodo_rows]
    valid_zenodo_dois = [
        doi
        for doi in zenodo_dois
        if isinstance(doi, str) and doi
    ]
    if len(valid_zenodo_dois) != len(zenodo_dois):
        fail("curated Zenodo DOI identifiers must be non-empty strings")
    if len({doi.casefold() for doi in valid_zenodo_dois}) != len(valid_zenodo_dois):
        fail("curated Zenodo DOI identifiers must be unique ignoring case")
    expected_zenodo_dois = {
        doi
        for doi in publication_by_doi
        if ZENODO_DOI_RE.fullmatch(doi)
    }
    if {doi.casefold() for doi in zenodo_dois if isinstance(doi, str)} != expected_zenodo_dois:
        fail("curated Zenodo DOI set must match Zenodo publications exactly")

    zenodo_by_doi = {
        row.get("doi").casefold(): row
        for row in zenodo_rows
        if isinstance(row.get("doi"), str) and row.get("doi")
    }

    for row in zenodo_rows:
        doi = row.get("doi")
        if not isinstance(doi, str):
            continue
        pub = publication_by_doi.get(doi.casefold())
        if pub is None:
            continue
        if "concept_doi" not in row:
            fail(f"curated Zenodo concept_doi must be explicit for {doi}")
        for field in ("title", "version", "resource_type", "repository_association", "concept_doi"):
            if row.get(field) != pub.get(field):
                fail(f"curated Zenodo {field} mismatch for {doi}")
        if row.get("evidence") != pub.get("source"):
            fail(f"curated Zenodo evidence/source mismatch for {doi}")
        match = ZENODO_DOI_RE.fullmatch(doi)
        if match and row.get("record_id") != int(match.group(1)):
            fail(f"curated Zenodo record_id mismatch for {doi}")

    # A declared Zenodo concept DOI must resolve inside the curated Zenodo
    # registry to a concept record associated with the same project. This
    # prevents a syntactically valid DOI from borrowing another publication's
    # identity or lineage.
    for pub in pubs:
        concept_doi = pub.get("concept_doi")
        if concept_doi is None:
            continue
        if not isinstance(concept_doi, str):
            continue
        concept_row = zenodo_by_doi.get(concept_doi.casefold())
        if concept_row is None:
            fail(f"concept DOI missing curated Zenodo record: {pub.get('id')} -> {concept_doi}")
            continue
        if concept_row.get("repository_association") != pub.get("repository_association"):
            fail(
                f"concept DOI repository association mismatch: "
                f"{pub.get('id')} -> {concept_doi}"
            )
        if concept_row.get("resource_type") != "concept-doi":
            fail(
                f"concept DOI must resolve to a curated concept-doi record: "
                f"{pub.get('id')} -> {concept_doi}"
            )

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
            if "concept_doi" not in link:
                fail(f"publication ownership link must declare concept_doi: {link.get('publication_id')}")
            else:
                link_concept_doi = link.get("concept_doi")
                if link_concept_doi is not None and (
                    not isinstance(link_concept_doi, str)
                    or not DOI_RE.fullmatch(link_concept_doi)
                ):
                    fail(
                        f"publication ownership link has invalid concept_doi: "
                        f"{link.get('publication_id')} -> {link_concept_doi!r}"
                    )
                if pub is not None:
                    pub_concept_doi = pub.get("concept_doi")
                    comparable_pub = (
                        pub_concept_doi.casefold()
                        if isinstance(pub_concept_doi, str)
                        else pub_concept_doi
                    )
                    comparable_link = (
                        link_concept_doi.casefold()
                        if isinstance(link_concept_doi, str)
                        else link_concept_doi
                    )
                    if comparable_pub != comparable_link:
                        fail(
                            f"publication concept DOI disagrees with curated ownership binding: "
                            f"{link.get('publication_id')}"
                        )
        evidence = link.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            fail(f"publication link requires evidence: {link.get('project_id')} -> {link.get('publication_id')}")
        else:
            publication = publication_by_id.get(link.get("publication_id"))
            project = project_by_id.get(link.get("project_id"), {})
            project_repo = project.get("repo")
            project_source = project.get("source")
            for url in evidence:
                if not isinstance(url, str) or not publication_link_evidence_is_valid(
                    url, relation, project_repo, project_source, publication, repo_by_project
                ):
                    fail(
                        f"publication link evidence is not traceable to the linked project/publication: "
                        f"{link.get('project_id')} -> {link.get('publication_id')}: {url!r}"
                    )
            if relation == "repository-associated-publication" and publication is not None:
                owner_bound = any(
                    isinstance(url, str)
                    and (
                        github_blob_source_matches(url, project_source)
                        or (
                            github_blob_source_matches(url, publication.get("source"))
                            and normalize_repository(github_repository(url))
                            == normalize_repository(project_repo)
                        )
                    )
                    for url in evidence
                )
                publication_bound = any(
                    isinstance(url, str)
                    and (
                        github_blob_source_matches(url, publication.get("source"))
                        or publication_external_source_matches(publication, url)
                    )
                    for url in evidence
                )
                if not owner_bound or not publication_bound:
                    fail(
                        f"publication ownership evidence must bind both asserted project "
                        f"and selected publication: "
                        f"{link.get('project_id')} -> {link.get('publication_id')}"
                    )
            if relation == "lineage-reference" and publication is not None:
                project_bound = any(
                    isinstance(url, str)
                    and github_blob_source_matches(url, project_source)
                    for url in evidence
                )
                publication_bound = any(
                    isinstance(url, str)
                    and (
                        github_blob_source_matches(url, publication.get("source"))
                        or publication_external_source_matches(publication, url)
                    )
                    for url in evidence
                )
                if not project_bound or not publication_bound:
                    fail(
                        f"lineage reference evidence must bind both referencing project and selected publication: "
                        f"{link.get('project_id')} -> {link.get('publication_id')}"
                    )
        link_keys.append((link.get("project_id"), link.get("publication_id"), relation))
    if len(link_keys) != len(set(link_keys)):
        fail("project-publication links must be unique")

    expected_ownership_links = {
        (pub.get("repository_association"), pub.get("id"))
        for pub in pubs
        if pub.get("repository_association")
    }
    actual_ownership_links = {
        (link.get("project_id"), link.get("publication_id"))
        for link in links
        if link.get("relation") == "repository-associated-publication"
    }
    if actual_ownership_links != expected_ownership_links:
        missing = sorted(expected_ownership_links - actual_ownership_links)
        extra = sorted(actual_ownership_links - expected_ownership_links)
        fail(
            "repository-associated-publication links must exactly match publication associations: "
            f"missing={missing} extra={extra}"
        )

    expected_lineage_links = {
        (rel.get("target"), rel.get("publication_id"))
        for rel in rels
        if rel.get("relation_type") == "historical-lineage"
        and rel.get("publication_id") is not None
    }
    actual_lineage_links = {
        (link.get("project_id"), link.get("publication_id"))
        for link in links
        if link.get("relation") == "lineage-reference"
    }
    if actual_lineage_links != expected_lineage_links:
        missing = sorted(expected_lineage_links - actual_lineage_links)
        extra = sorted(actual_lineage_links - expected_lineage_links)
        fail(
            f"lineage-reference links must exactly match historical-lineage declarations: "
            f"missing={missing} extra={extra}"
        )

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
        relation_type = rel.get("relation_type")
        if relation_type not in NON_MECHANISM_RELATIONS:
            fail(f"unknown/unreviewed relationship type: {relation_type}")
        if relation_type == "historical-lineage":
            publication_id = rel.get("publication_id")
            lineage_publication = publication_by_id.get(publication_id)
            if lineage_publication is None:
                fail(
                    f"historical-lineage relationship must bind a curated publication: "
                    f"{source_id} -> {target_id}: {publication_id}"
                )
            elif lineage_publication.get("repository_association") != source_id:
                fail(
                    f"historical-lineage publication must belong to the origin project: "
                    f"{source_id} -> {target_id}: {publication_id}"
                )
        elif "publication_id" in rel:
            fail(
                f"non-lineage relationship must not declare publication_id: "
                f"{source_id} -> {target_id}"
            )
        if rel.get("mechanism_claim") is not False:
            fail(f"current relationship classes must set mechanism_claim=false: {source_id} -> {target_id}")
        theme = rel.get("theme")
        if theme and f"theme:{theme}" not in theme_ids:
            fail(f"relationship theme missing: {theme}")
        elif theme:
            endpoint_theme_sets = [
                set(project_by_id.get(endpoint_id, {}).get("themes", []))
                for endpoint_id in (source_id, target_id)
            ]
            if relation_type in BILATERAL_RELATIONS:
                if not all(theme in themes_for_endpoint for themes_for_endpoint in endpoint_theme_sets):
                    fail(
                        f"bilateral relationship theme must be supported by both endpoints: "
                        f"{source_id} -> {target_id}: {theme}"
                    )
            elif not any(theme in themes_for_endpoint for themes_for_endpoint in endpoint_theme_sets):
                fail(
                    f"relationship theme is not supported by either endpoint: "
                    f"{source_id} -> {target_id}: {theme}"
                )

        evidence = rel.get("evidence")
        endpoint_repos = {
            normalize_repository(repo_by_project.get(source_id)),
            normalize_repository(repo_by_project.get(target_id)),
        }
        endpoint_sources = {
            github_blob_identity(project_by_id.get(endpoint_id, {}).get("source"))
            for endpoint_id in (source_id, target_id)
        }
        endpoint_sources.discard(None)
        if not isinstance(evidence, list) or not evidence:
            fail(f"relationship requires first-party GitHub evidence: {source_id} -> {target_id}")
        else:
            evidence_identities = set()
            for url in evidence:
                evidence_repo = github_repository(url)
                identity = github_blob_identity(url)
                if evidence_repo is None:
                    fail(f"relationship evidence must be a GitHub repository URL: {source_id} -> {target_id}: {url!r}")
                elif normalize_repository(evidence_repo) not in endpoint_repos:
                    fail(
                        f"relationship evidence repository must match an endpoint: "
                        f"{source_id} -> {target_id}: {evidence_repo}"
                    )
                elif identity not in endpoint_sources:
                    fail(
                        f"relationship evidence must match a curated endpoint source: "
                        f"{source_id} -> {target_id}: {url!r}"
                    )
                else:
                    evidence_identities.add(identity)
            if relation_type in BILATERAL_RELATIONS and evidence_identities != endpoint_sources:
                fail(
                    f"bilateral relationship evidence must cover both endpoints: "
                    f"{source_id} -> {target_id}"
                )
        relationship_keys.append((source_id, target_id, rel.get("relation_type"), theme))
    if len(relationship_keys) != len(set(relationship_keys)):
        fail("relationships must be unique by endpoints, type, and theme")

    graph_path = root / "figures" / "theme-network.dot"
    graph_text = graph_path.read_text(encoding="utf-8") if graph_path.exists() else ""
    graph_edges = DOT_EDGE_RE.findall(graph_text)
    actual_graph_edges = set(graph_edges)
    expected_graph_edges = {
        (
            rel.get("source"),
            rel.get("target"),
            rel.get("relation_type"),
            rel.get("theme"),
        )
        for rel in rels
    }
    if len(graph_edges) != len(actual_graph_edges):
        fail("relationship graph contains duplicate edges")
    if actual_graph_edges != expected_graph_edges:
        missing = sorted(expected_graph_edges - actual_graph_edges)
        extra = sorted(actual_graph_edges - expected_graph_edges)
        fail(
            f"relationship graph must match data/relationships.json exactly: "
            f"missing={missing} extra={extra}"
        )

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
        elif normalize_repository(repository) not in repo_normalized_set:
            fail(f"source repository is not a curated project repository: {src.get('source_id')} -> {repository}")
        if not isinstance(path, str) or not path:
            fail(f"source path must be traceable: {src.get('source_id')}")
        access_date = src.get("access_date")
        if not valid_date(access_date):
            fail(f"source access_date must use a real YYYY-MM-DD date: {src.get('source_id')} -> {access_date!r}")
        elif dt.date.fromisoformat(access_date) > dt.date.today():
            fail(f"source access_date must not be in the future: {src.get('source_id')} -> {access_date!r}")
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
        sid = source_id_for_project(project.get("id"))
        if sid is None:
            continue
        src = source_by_id.get(sid)
        if not src:
            fail(f"project source missing from source index: {sid}")
            continue
        if normalize_repository(src.get("repository")) != normalize_repository(project.get("repo")):
            fail(f"project source repository mismatch: {sid}")
        thematic_supports = set(src.get("supports", [])) & theme_set
        project_themes = set(project.get("themes", []))
        if thematic_supports != project_themes:
            fail(
                f"project/source theme support mismatch: {project['id']} "
                f"project={sorted(project_themes)} source={sorted(thematic_supports)}"
            )

    atomic_project_source_ids = {
        sid
        for project in projects
        if (sid := source_id_for_project(project.get("id"))) is not None
    }

    for theme in themes:
        theme_name = theme.get("name")
        if not isinstance(theme_name, str):
            continue
        atomic_theme_path = root / "themes" / f"{theme_name.replace('_', '-')}.md"
        if not atomic_theme_path.exists():
            fail(f"atomic theme document missing: {atomic_theme_path.relative_to(root)}")
            continue
        atomic_text = atomic_theme_path.read_text(encoding="utf-8")
        actual_members = {
            source_ref
            for source_ref in SOURCE_ID_RE.findall(atomic_text)
            if source_ref in atomic_project_source_ids
        }
        expected_members = {
            source_id_for_project(project.get("id"))
            for project in projects
            if theme_name in project.get("themes", [])
        }
        expected_members.discard(None)
        if actual_members != expected_members:
            fail(
                f"atomic theme membership must match source support: {theme_name} "
                f"expected={sorted(expected_members)} actual={sorted(actual_members)}"
            )
        for source_ref in actual_members:
            supports = set(source_by_id.get(source_ref, {}).get("supports", []))
            if theme_name not in supports:
                fail(
                    f"atomic theme member is not supported by source index: "
                    f"{theme_name} -> {source_ref}"
                )

    matrix_path = root / "evidence" / "project-theme-matrix.csv"
    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = [c for c in (reader.fieldnames or []) if c != "project_id"]
        if set(columns) != theme_set or len(columns) != len(theme_set):
            fail("matrix theme columns must match the theme registry exactly")
        rows = list(reader)
        if any(None in row for row in rows):
            fail("matrix rows must match the declared header width exactly")

    matrix_ids = [row.get("project_id") for row in rows]
    if len(matrix_ids) != len(set(matrix_ids)):
        fail("matrix project rows must be unique")
    if set(matrix_ids) != project_set:
        fail("matrix project rows must match projects.json exactly")

    for row in rows:
        pid = row.get("project_id")
        sid = source_id_for_project(pid)
        if sid is None:
            continue
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

    expected_project_summary_ids = {
        sid
        for project in projects
        if (sid := source_id_for_project(project.get("id"))) is not None
    }
    project_summary_counts: dict[str, int] = {}

    for directory in ("paper", "themes", "projects"):
        for path in (root / directory).glob("*.md"):
            text = path.read_text(encoding="utf-8")
            if "Bootstrap placeholder" in text or "Draft section. This bootstrap" in text:
                fail(f"placeholder prose remains: {path.relative_to(root)}")
            source_refs = sorted(set(SOURCE_ID_RE.findall(text)))
            if directory == "projects":
                project_refs = [
                    source_ref
                    for source_ref in source_refs
                    if source_ref in expected_project_summary_ids
                ]
                if len(project_refs) != 1:
                    fail(
                        f"project summary must identify exactly one curated project source: "
                        f"{path.relative_to(root)}"
                    )
                else:
                    project_summary_counts[project_refs[0]] = (
                        project_summary_counts.get(project_refs[0], 0) + 1
                    )
                    repo_match = PROJECT_SUMMARY_REPO_RE.search(text)
                    summary_repo = normalize_repository(
                        repo_match.group(1) if repo_match else None
                    )
                    summary_project = project_by_repo.get(summary_repo)
                    expected_summary_source = (
                        source_id_for_project(summary_project.get("id"))
                        if summary_project is not None
                        else None
                    )
                    if expected_summary_source != project_refs[0]:
                        fail(
                            f"project summary source does not match its repository: "
                            f"{path.relative_to(root)} -> {project_refs[0]}"
                        )
                    summary_project_by_source = next(
                        (
                            project
                            for project in projects
                            if source_id_for_project(project.get("id")) == project_refs[0]
                        ),
                        None,
                    )
                    actual_summary_path = path.relative_to(root).as_posix()
                    if (
                        summary_project_by_source is None
                        or summary_project_by_source.get("summary_path") != actual_summary_path
                    ):
                        fail(
                            f"project summary path does not match curated summary_path: "
                            f"{actual_summary_path} -> {project_refs[0]}"
                        )
                    if summary_project_by_source is not None:
                        section_match = SUMMARY_PUBLICATIONS_SECTION_RE.search(text)
                        section_text = section_match.group("body") if section_match else ""
                        actual_publication_dois = [
                            doi.casefold()
                            for doi in DOI_TOKEN_RE.findall(section_text)
                        ]
                        expected_publication_dois = sorted(
                            publication_by_id[link.get("publication_id")]["doi"].casefold()
                            for link in links
                            if (
                                link.get("project_id") == summary_project_by_source.get("id")
                                and link.get("relation") in ALLOWED_LINK_RELATIONS
                                and link.get("publication_id") in publication_by_id
                                and isinstance(
                                    publication_by_id[link.get("publication_id")].get("doi"),
                                    str,
                                )
                            )
                        )
                        if (
                            len(actual_publication_dois) != len(set(actual_publication_dois))
                            or sorted(actual_publication_dois) != expected_publication_dois
                        ):
                            fail(
                                f"project summary publications must match curated links: "
                                f"{actual_summary_path} expected={expected_publication_dois} "
                                f"actual={sorted(actual_publication_dois)}"
                            )
            for source_ref in source_refs:
                if source_ref not in source_by_id:
                    fail(
                        f"unknown source index reference in synthesis document: "
                        f"{path.relative_to(root)} -> {source_ref}"
                    )
            if (
                directory == "paper"
                and re.match(r"^(?:0[2-9]|1[0-4])-", path.name)
                and not source_refs
            ):
                fail(
                    f"substantive paper section requires source index references: "
                    f"{path.relative_to(root)}"
                )

    actual_project_summary_ids = set(project_summary_counts)
    if actual_project_summary_ids != expected_project_summary_ids:
        missing = sorted(expected_project_summary_ids - actual_project_summary_ids)
        extra = sorted(actual_project_summary_ids - expected_project_summary_ids)
        fail(
            f"project summaries must cover projects.json exactly: "
            f"missing={missing} extra={extra}"
        )
    duplicate_project_summaries = sorted(
        source_id
        for source_id, count in project_summary_counts.items()
        if count != 1
    )
    if duplicate_project_summaries:
        fail(
            f"project summaries must be unique by curated project source: "
            f"{duplicate_project_summaries}"
        )

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
