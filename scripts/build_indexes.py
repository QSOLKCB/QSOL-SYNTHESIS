#!/usr/bin/env python3
"""Build or verify the deterministic source index from curated synthesis registries."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

GITHUB_BLOB_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/blob/([^/]+)/(.+)$")
ZENODO_RECORD_RE = re.compile(r"^https://zenodo\.org/records/(\d+)/?$")
DOI_SOURCE_RE = re.compile(r"^https://doi\.org/(10\.\d{4,9}/[-._;()/:A-Z0-9]+)$", re.IGNORECASE)
ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.(\d+)$", re.IGNORECASE)
PROJECT_ID_RE = re.compile(r"^project:[A-Za-z0-9._-]+$")
PUBLICATION_ID_RE = re.compile(r"^publication:[A-Za-z0-9._-]+$")
ZENODO_PUBLICATION_ID_RE = re.compile(r"^publication:zenodo-(\d+)$")


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_repository(value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.casefold()


def github_blob_identity(url: str | None) -> tuple[str, str, str] | None:
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


def parse_source(url: str | None) -> tuple[str, str | None, str | None, str]:
    """Return (kind, repository, branch, path) for a traceable source.

    Curated project sources must be GitHub blob URLs. Publication sources may
    additionally use a Zenodo record URL or DOI URL. Unknown and empty values
    are rejected rather than converted into evidence-free source rows.
    """
    if not isinstance(url, str) or not url.strip():
        raise RuntimeError("source must be a non-empty traceable URL")

    match = GITHUB_BLOB_RE.fullmatch(url)
    if match:
        return "github", match.group(1), match.group(2), match.group(3)

    if ZENODO_RECORD_RE.fullmatch(url) or DOI_SOURCE_RE.fullmatch(url):
        return "external", None, None, url

    raise RuntimeError(f"unsupported source URL: {url}")


def project_source_id(project_id: str) -> str:
    if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
        raise RuntimeError(f"invalid project ID namespace: {project_id!r}")
    return f"src:{project_id.removeprefix('project:')}:readme"


def publication_source_id(publication_id: str) -> str:
    if not isinstance(publication_id, str) or not PUBLICATION_ID_RE.fullmatch(publication_id):
        raise RuntimeError(f"invalid publication ID namespace: {publication_id!r}")
    return f"src:{publication_id.removeprefix('publication:')}"


def publication_external_source_matches(pub: dict, source_url: str) -> bool:
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


def build(root: pathlib.Path) -> dict:
    data = root / "data"
    projects_doc = read_json(data / "projects.json")
    publications_doc = read_json(data / "publications.json")
    links_doc = read_json(data / "project-publication-links.json")
    github_doc = read_json(data / "github-repositories.json")
    relationships_doc = read_json(data / "relationships.json")
    dated_docs = {
        "projects.json": projects_doc.get("generated_at"),
        "publications.json": publications_doc.get("generated_at"),
        "project-publication-links.json": links_doc.get("generated_at"),
        "github-repositories.json": github_doc.get("generated_at"),
        "relationships.json": relationships_doc.get("generated_at"),
    }
    for name, value in dated_docs.items():
        if not isinstance(value, str):
            raise RuntimeError(f"{name} generated_at must be YYYY-MM-DD")
        try:
            parsed = dt.date.fromisoformat(value)
        except ValueError as exc:
            raise RuntimeError(f"{name} generated_at must be YYYY-MM-DD") from exc
        if parsed.isoformat() != value:
            raise RuntimeError(f"{name} generated_at must be YYYY-MM-DD")
        if parsed > dt.date.today():
            raise RuntimeError(f"{name} generated_at must not be in the future: {value}")
    dates = set(dated_docs.values())
    if len(dates) != 1:
        raise RuntimeError(f"curated generated_at values disagree: {sorted(dates)}")
    generated_at = next(iter(dates))

    projects = projects_doc.get("projects", [])
    publications = publications_doc.get("publications", [])
    links = links_doc.get("links", [])
    github_rows = github_doc.get("repositories", [])
    relationships = relationships_doc.get("relationships", [])

    curated_source_by_repo: dict[str, str] = {}
    curated_publication_dois_by_repo: dict[str, set[str]] = {}
    curated_publication_sources_by_repo: dict[str, dict[str, str]] = {}
    for row in github_rows:
        full_name = row.get("full_name")
        source = row.get("source")
        normalized_repo = normalize_repository(full_name)
        if normalized_repo is None:
            raise RuntimeError(f"curated GitHub row requires full_name: {full_name!r}")
        if normalized_repo in curated_source_by_repo:
            raise RuntimeError(f"duplicate curated GitHub repository: {full_name}")
        if not isinstance(source, str):
            raise RuntimeError(f"curated GitHub row requires source: {full_name}")
        publication_dois = row.get("publication_dois")
        normalized_publication_dois = (
            [doi.casefold() for doi in publication_dois]
            if isinstance(publication_dois, list)
            and all(isinstance(doi, str) and doi for doi in publication_dois)
            else []
        )
        if (
            not isinstance(publication_dois, list)
            or len(normalized_publication_dois) != len(publication_dois)
            or len(normalized_publication_dois) != len(set(normalized_publication_dois))
        ):
            raise RuntimeError(
                f"curated GitHub row requires unique publication_dois: {full_name}"
            )
        publication_sources = row.get("publication_sources")
        if not isinstance(publication_sources, dict):
            raise RuntimeError(
                f"curated GitHub row requires publication_sources: {full_name}"
            )
        normalized_source_keys = [
            key.casefold()
            for key in publication_sources
            if isinstance(key, str) and key
        ]
        if (
            len(normalized_source_keys) != len(publication_sources)
            or len(normalized_source_keys) != len(set(normalized_source_keys))
            or any(not isinstance(url, str) or not url for url in publication_sources.values())
        ):
            raise RuntimeError(
                f"curated GitHub row has invalid publication_sources: {full_name}"
            )
        curated_source_by_repo[normalized_repo] = source
        curated_publication_dois_by_repo[normalized_repo] = set(normalized_publication_dois)
        curated_publication_sources_by_repo[normalized_repo] = {
            doi.casefold(): url
            for doi, url in publication_sources.items()
        }

    for project in projects:
        project_id = project.get("id")
        if not isinstance(project_id, str) or not PROJECT_ID_RE.fullmatch(project_id):
            raise RuntimeError(f"invalid project ID namespace: {project_id!r}")

    ownership_concept_by_publication: dict[str, str | None] = {}
    ownership_link_by_publication: dict[str, dict] = {}
    for link in links:
        if link.get("relation") != "repository-associated-publication":
            continue
        publication_id = link.get("publication_id")
        if not isinstance(publication_id, str) or not publication_id:
            raise RuntimeError("publication ownership link requires publication_id")
        if publication_id in ownership_concept_by_publication:
            raise RuntimeError(f"duplicate publication ownership link: {publication_id}")
        if "concept_doi" not in link:
            raise RuntimeError(
                f"publication ownership link must declare concept_doi: {publication_id}"
            )
        expected_concept_doi = link.get("concept_doi")
        if expected_concept_doi is not None and not isinstance(expected_concept_doi, str):
            raise RuntimeError(
                f"publication ownership link concept_doi must be a string or null: "
                f"{publication_id}"
            )
        ownership_concept_by_publication[publication_id] = expected_concept_doi
        ownership_link_by_publication[publication_id] = link

    expected_lineage_links = {
        (rel.get("target"), rel.get("publication_id"))
        for rel in relationships
        if rel.get("relation_type") == "historical-lineage"
        and rel.get("publication_id") is not None
    }
    actual_lineage_links = {
        (link.get("project_id"), link.get("publication_id"))
        for link in links
        if link.get("relation") == "lineage-reference"
    }
    if actual_lineage_links != expected_lineage_links:
        raise RuntimeError(
            f"lineage-reference links must exactly match historical-lineage declarations: "
            f"expected={sorted(expected_lineage_links)} actual={sorted(actual_lineage_links)}"
        )

    project_repo_by_id = {
        project.get("id"): project.get("repo")
        for project in projects
        if project.get("id") and project.get("repo")
    }
    project_by_id = {
        project.get("id"): project
        for project in projects
        if project.get("id")
    }

    sources = []
    for project in projects:
        try:
            kind, repository, branch, path = parse_source(project.get("source"))
        except RuntimeError as exc:
            raise RuntimeError(f"project {project.get('id')} has no traceable source: {exc}") from exc
        if kind != "github":
            raise RuntimeError(f"project {project.get('id')} source must be a GitHub blob URL")
        if normalize_repository(repository) != normalize_repository(project.get("repo")):
            raise RuntimeError(
                f"project {project.get('id')} source repository {repository!r} "
                f"does not match {project.get('repo')!r}"
            )
        repository = project.get("repo")
        curated_source = curated_source_by_repo.get(normalize_repository(repository))
        if curated_source is None:
            raise RuntimeError(
                f"project {project.get('id')} missing independently curated source binding"
            )
        try:
            curated_kind, curated_repository, curated_branch, curated_path = parse_source(curated_source)
        except RuntimeError as exc:
            raise RuntimeError(
                f"project {project.get('id')} curated source is invalid: {exc}"
            ) from exc
        if (
            curated_kind != "github"
            or normalize_repository(curated_repository) != normalize_repository(repository)
            or curated_branch != branch
            or curated_path != path
        ):
            raise RuntimeError(
                f"project {project.get('id')} source does not match independently curated source"
            )
        sources.append({
            "source_id": project_source_id(project["id"]),
            "repository": repository,
            "path": path,
            "branch_or_commit": branch,
            "access_date": generated_at,
            "source_type": "github-readme",
            "supports": sorted({"inventory", *project.get("themes", [])}),
        })

    for pub in publications:
        publication_id = pub.get("id")
        if not isinstance(publication_id, str) or not PUBLICATION_ID_RE.fullmatch(publication_id):
            raise RuntimeError(f"invalid publication ID namespace: {publication_id!r}")
        doi = pub.get("doi")
        zenodo_id_match = ZENODO_PUBLICATION_ID_RE.fullmatch(publication_id)
        zenodo_doi_match = ZENODO_DOI_RE.fullmatch(doi) if isinstance(doi, str) else None
        if zenodo_id_match is not None:
            if (
                zenodo_doi_match is None
                or zenodo_id_match.group(1) != zenodo_doi_match.group(1)
            ):
                raise RuntimeError(
                    f"Zenodo publication ID must match declared DOI record: "
                    f"{publication_id} -> {doi!r}"
                )
        elif zenodo_doi_match is not None:
            raise RuntimeError(
                f"Zenodo DOI publication must use matching publication:zenodo-* ID: "
                f"{publication_id!r} -> {doi}"
            )
        if publication_id not in ownership_concept_by_publication:
            raise RuntimeError(
                f"publication requires a curated ownership concept binding: {publication_id}"
            )
        actual_concept_doi = pub.get("concept_doi")
        expected_concept_doi = ownership_concept_by_publication[publication_id]
        if actual_concept_doi is not None and not isinstance(actual_concept_doi, str):
            raise RuntimeError(
                f"publication {publication_id} concept_doi must be a string or null"
            )
        comparable_actual = (
            actual_concept_doi.casefold()
            if isinstance(actual_concept_doi, str)
            else actual_concept_doi
        )
        comparable_expected = (
            expected_concept_doi.casefold()
            if isinstance(expected_concept_doi, str)
            else expected_concept_doi
        )
        if comparable_actual != comparable_expected:
            raise RuntimeError(
                f"publication concept DOI disagrees with curated ownership binding: "
                f"{publication_id}"
            )

        try:
            kind, repository, branch, path = parse_source(pub.get("source"))
        except RuntimeError as exc:
            raise RuntimeError(f"publication {pub.get('id')} has no traceable source: {exc}") from exc

        association = pub.get("repository_association")
        owner_repository = project_repo_by_id.get(association)
        owner_project = project_by_id.get(association)
        if owner_repository is None or owner_project is None:
            raise RuntimeError(
                f"publication {pub.get('id')} requires a valid repository_association"
            )
        owner_manifest_dois = curated_publication_dois_by_repo.get(
            normalize_repository(owner_repository)
        )
        if (
            owner_manifest_dois is None
            or not isinstance(doi, str)
            or doi.casefold() not in owner_manifest_dois
        ):
            raise RuntimeError(
                f"publication ownership disagrees with curated GitHub registry: "
                f"{publication_id} -> {association}"
            )
        ownership_link = ownership_link_by_publication.get(publication_id)
        if ownership_link is None or ownership_link.get("project_id") != association:
            raise RuntimeError(
                f"publication ownership link does not match asserted repository: "
                f"{publication_id} -> {association}"
            )
        evidence = ownership_link.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise RuntimeError(
                f"publication ownership link requires evidence: {publication_id}"
            )
        owner_bound = any(
            isinstance(url, str)
            and (
                github_blob_source_matches(url, owner_project.get("source"))
                or (
                    github_blob_source_matches(url, pub.get("source"))
                    and normalize_repository(
                        github_blob_identity(url)[0] if github_blob_identity(url) else None
                    )
                    == normalize_repository(owner_repository)
                )
            )
            for url in evidence
        )
        publication_bound = any(
            isinstance(url, str)
            and (
                github_blob_source_matches(url, pub.get("source"))
                or publication_external_source_matches(pub, url)
            )
            for url in evidence
        )
        if not owner_bound or not publication_bound:
            raise RuntimeError(
                f"publication ownership evidence must bind both asserted project "
                f"and selected publication: {publication_id}"
            )

        if kind == "external":
            if not publication_external_source_matches(pub, path):
                raise RuntimeError(
                    f"publication {pub.get('id')} external source does not match its DOI/concept DOI"
                )
        elif normalize_repository(repository) != normalize_repository(owner_repository):
            raise RuntimeError(
                f"publication {pub.get('id')} source repository {repository!r} "
                f"does not match associated repository {owner_repository!r}"
            )
        else:
            owner_source_map = curated_publication_sources_by_repo.get(
                normalize_repository(owner_repository), {}
            )
            expected_source = (
                owner_source_map.get(doi.casefold())
                if isinstance(doi, str)
                else None
            )
            if expected_source is None:
                raise RuntimeError(
                    f"publication {publication_id} missing independently curated source"
                )
            expected_kind, expected_repo, expected_branch, expected_path = parse_source(
                expected_source
            )
            if (
                expected_kind != "github"
                or normalize_repository(expected_repo)
                != normalize_repository(repository)
                or expected_branch != branch
                or expected_path != path
            ):
                raise RuntimeError(
                    f"publication GitHub source does not match independently curated source: "
                    f"{publication_id}"
                )

        repository = owner_repository
        sources.append({
            "source_id": publication_source_id(pub["id"]),
            "repository": repository,
            "path": path,
            "branch_or_commit": branch,
            "access_date": generated_at,
            "source_type": "publication-metadata",
            "supports": ["doi-linking", "publication-linking"],
        })

    sources.sort(key=lambda row: row["source_id"])
    return {
        "generated_at": generated_at,
        "generated_from": [
            "data/projects.json",
            "data/publications.json",
            "data/project-publication-links.json",
            "data/github-repositories.json",
            "data/relationships.json",
        ],
        "sources": sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "data" / "source-index.json"
    generated = build(root)
    rendered = json.dumps(generated, indent=2) + "\n"

    if args.check:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != rendered:
            print("data/source-index.json is stale; run python scripts/build_indexes.py", file=sys.stderr)
            return 1
        print("Source index OK")
        return 0

    path.write_text(rendered, encoding="utf-8")
    print("updated data/source-index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
