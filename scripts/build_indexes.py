#!/usr/bin/env python3
"""Build or verify the deterministic source index from curated synthesis registries."""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import sys

GITHUB_BLOB_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/blob/([^/]+)/(.+)$")


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_source(url: str | None):
    if not url:
        return None, None, None
    match = GITHUB_BLOB_RE.match(url)
    if not match:
        return None, None, url
    return match.group(1), match.group(2), match.group(3)


def project_source_id(project_id: str) -> str:
    return f"src:{project_id.removeprefix('project:')}:readme"


def publication_source_id(publication_id: str) -> str:
    return f"src:{publication_id.removeprefix('publication:')}"


def build(root: pathlib.Path) -> dict:
    data = root / "data"
    projects_doc = read_json(data / "projects.json")
    publications_doc = read_json(data / "publications.json")
    dates = {projects_doc.get("generated_at"), publications_doc.get("generated_at")}
    dates.discard(None)
    if len(dates) != 1:
        raise RuntimeError(f"curated generated_at values disagree: {sorted(dates)}")
    generated_at = next(iter(dates))

    sources = []
    for project in projects_doc.get("projects", []):
        _, branch, path = parse_source(project.get("source"))
        sources.append({
            "source_id": project_source_id(project["id"]),
            "repository": project.get("repo"),
            "path": path or "README.md",
            "branch_or_commit": branch or "main",
            "access_date": generated_at,
            "source_type": "github-readme",
            "supports": sorted({"inventory", *project.get("themes", [])}),
        })

    for pub in publications_doc.get("publications", []):
        repository, branch, path = parse_source(pub.get("source"))
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
