#!/usr/bin/env python3
"""Build normalized indexes from collected data files."""
from __future__ import annotations
import json
import pathlib


def read_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    data = root / "data"

    repos = read_json(data / "github-repositories.json")
    zen = read_json(data / "zenodo-records.json")

    source_index = {
        "generated_from": ["data/github-repositories.json", "data/zenodo-records.json"],
        "sources": [],
    }

    for repo in repos.get("repositories", []):
        source_index["sources"].append(
            {
                "source_id": f"src:repo:{repo.get('name','').lower()}",
                "repository": repo.get("full_name"),
                "path": "README.md",
                "source_type": "github-repository",
                "supports": ["inventory"],
            }
        )

    for rec in zen.get("records", []):
        source_index["sources"].append(
            {
                "source_id": f"src:zenodo:{rec.get('record_id')}",
                "repository": None,
                "path": rec.get("url"),
                "source_type": "zenodo-record",
                "supports": ["publication-linking"],
            }
        )

    (data / "source-index.json").write_text(json.dumps(source_index, indent=2) + "\n", encoding="utf-8")
    print("updated data/source-index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
