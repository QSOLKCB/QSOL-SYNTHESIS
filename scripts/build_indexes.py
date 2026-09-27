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
    dates = {projects_doc.get("generated_at"), publications_doc.get("generated_at")}
    dates.discard(None)
    if len(dates) != 1:
        raise RuntimeError(f"curated generated_at values disagree: {sorted(dates)}")
    generated_at = next(iter(dates))

    projects = projects_doc.get("projects", [])
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
        if repository != project.get("repo"):
            raise RuntimeError(
                f"project {project.get('id')} source repository {repository!r} "
                f"does not match {project.get('repo')!r}"
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

    for pub in publications_doc.get("publications", []):
        try:
            kind, repository, branch, path = parse_source(pub.get("source"))
        except RuntimeError as exc:
            raise RuntimeError(f"publication {pub.get('id')} has no traceable source: {exc}") from exc

        if kind == "external":
            if not publication_external_source_matches(pub, path):
                raise RuntimeError(
                    f"publication {pub.get('id')} external source does not match its DOI/concept DOI"
                )
            association = pub.get("repository_association")
            repository = project_repo_by_id.get(association)
            if repository is None:
                raise RuntimeError(
                    f"publication {pub.get('id')} external source requires a valid repository_association"
                )

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
