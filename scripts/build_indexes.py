#!/usr/bin/env python3
"""Build normalized indexes from collected data files."""
from __future__ import annotations
import json
import pathlib


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_prefer_specific(existing: dict, generated: dict) -> dict:
    out = dict(existing)
    for key, value in generated.items():
        if value is None:
            continue
        if key not in out:
            out[key] = value
            continue
        current = out.get(key)
        if current in (None, "", "unknown") and value not in (None, "", "unknown"):
            out[key] = value
            continue
        if key == "source_type" and current == "github-readme" and value == "github-repository":
            continue
        if key == "branch_or_commit" and current not in (None, "", "unknown") and value == "unknown":
            continue
        if key == "supports" and isinstance(current, list) and isinstance(value, list):
            out[key] = sorted({*current, *value})
            continue
        if current in (None, "", "unknown"):
            out[key] = value
    return out


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    data = root / "data"

    repos = read_json(data / "github-repositories.json")
    zen = read_json(data / "zenodo-records.json")

    existing_path = data / "source-index.json"
    existing = read_json(existing_path) if existing_path.exists() else {"sources": []}
    existing_by_id = {s.get("source_id"): s for s in existing.get("sources", []) if isinstance(s, dict)}

    generated_candidates = [v for v in [repos.get("generated_at"), zen.get("generated_at"), existing.get("generated_at")] if v]
    if not generated_candidates:
        raise RuntimeError("Cannot derive deterministic generated_at from inputs; set generated_at in collected source files first.")
    if len(set(generated_candidates)) > 1:
        raise RuntimeError(f"Inconsistent generated_at values across inputs: {generated_candidates}")
    generated_at = generated_candidates[0]
    source_index = {
        "generated_at": generated_at,
        "generated_from": ["data/github-repositories.json", "data/zenodo-records.json"],
        "sources": [],
    }

    for repo in repos.get("repositories", []):
        source_id = f"src:{repo.get('name','').lower().replace('_','-').replace('.','-')}:readme"
        generated = {
            "source_id": source_id,
            "repository": repo.get("full_name"),
            "path": "README.md",
            "branch_or_commit": repo.get("default_branch"),
            "access_date": repos.get("generated_at"),
            "source_type": "github-readme",
            "supports": ["inventory"],
        }
        current = existing_by_id.get(source_id, {})
        source_index["sources"].append(merge_prefer_specific(current, generated))

    for rec in zen.get("records", []):
        source_id = f"src:zenodo-{rec.get('record_id')}"
        if source_id in existing_by_id:
            source_index["sources"].append(existing_by_id[source_id])
            continue
        generated = {
            "source_id": source_id,
            "repository": rec.get("repository_association"),
            "path": rec.get("evidence") or rec.get("url"),
            "branch_or_commit": None,
            "access_date": zen.get("generated_at"),
            "source_type": "publication-metadata",
            "supports": ["publication-linking", "doi-linking"],
        }
        current = existing_by_id.get(source_id, {})
        source_index["sources"].append(merge_prefer_specific(current, generated))

    appended_ids = {s.get("source_id") for s in source_index["sources"]}
    for src_id, src in existing_by_id.items():
        if src_id not in appended_ids:
            source_index["sources"].append(src)

    (data / "source-index.json").write_text(json.dumps(source_index, indent=2) + "\n", encoding="utf-8")
    print("updated data/source-index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
