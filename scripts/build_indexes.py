#!/usr/bin/env python3
"""Build or verify the deterministic source index from curated synthesis registries."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

GITHUB_BLOB_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/blob/([^/]+)/(.+)$")
ZENODO_RECORD_RE = re.compile(r"^https://zenodo\.org/records/(\d+)/?$")
DOI_SOURCE_RE = re.compile(r"^https://doi\.org/(10\.\d{4,9}/[-._;()/:A-Z0-9]+)$", re.IGNORECASE)
ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.(\d+)$", re.IGNORECASE)


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_repository(value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.casefold()


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
    return f"src:{project_id.removeprefix('project:')}:readme"


def publication_source_id(publication_id: str) -> str:
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
    dates = {
        projects_doc.get("generated_at"),
        publications_doc.get("generated_at"),
        links_doc.get("generated_at"),
    }
    dates.discard(None)
    if len(dates) != 1:
        raise RuntimeError(f"curated generated_at values disagree: {sorted(dates)}")
    generated_at = next(iter(dates))

    projects = projects_doc.get("projects", [])
    publications = publications_doc.get("publications", [])
    links = links_doc.get("links", [])

    ownership_concept_by_publication: dict[str, str | None] = {}
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

    project_repo_by_id = {
        project.get("id"): project.get("repo")
        for project in projects
        if project.get("id") and project.get("repo")
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
        if owner_repository is None:
            raise RuntimeError(
                f"publication {pub.get('id')} requires a valid repository_association"
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
        "generated_from": ["data/projects.json", "data/publications.json"],
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
