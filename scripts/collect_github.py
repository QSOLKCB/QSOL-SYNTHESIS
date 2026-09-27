#!/usr/bin/env python3
"""Collect raw public GitHub organisation metadata for QSOL-SYNTHESIS."""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"


def request(url: str, token: str | None, cache_dir: pathlib.Path, ttl_seconds: int):
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = urllib.parse.quote(url, safe="") + ".json"
    cache_file = cache_dir / key
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < ttl_seconds:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    headers = {"User-Agent": "QSOL-SYNTHESIS-collector", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub request failed: {url} -> HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub request failed: {url} -> {exc.reason}") from exc
    cache_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", default="QSOLKCB")
    parser.add_argument("--output", default="data/raw/github-repositories.json")
    parser.add_argument("--cache-dir", default=".cache/qsol-synthesis/github")
    parser.add_argument("--ttl-seconds", type=int, default=86400)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--include-enrichment", action="store_true")
    args = parser.parse_args()

    token = os.environ.get(args.token_env)
    cache_dir = pathlib.Path(args.cache_dir)
    repos = []
    page = 1
    while True:
        batch = request(
            f"{API}/orgs/{args.org}/repos?per_page=100&type=public&page={page}",
            token,
            cache_dir,
            args.ttl_seconds,
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected GitHub repositories response")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    normalized = []
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        row = {
            "name": name,
            "full_name": repo.get("full_name"),
            "html_url": repo.get("html_url"),
            "description": repo.get("description"),
            "default_branch": repo.get("default_branch"),
            "archived": repo.get("archived"),
            "visibility": "private" if repo.get("private") else "public",
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
        }
        if args.include_enrichment:
            row["releases"] = request(
                f"{API}/repos/{args.org}/{name}/releases?per_page=20",
                token, cache_dir, args.ttl_seconds
            )
            row["first_party_files"] = {}
            for candidate in ("README.md", "CITATION.cff", ".zenodo.json"):
                try:
                    meta = request(
                        f"{API}/repos/{args.org}/{name}/contents/{candidate}",
                        token, cache_dir, args.ttl_seconds
                    )
                    row["first_party_files"][candidate] = {"exists": True, "sha": meta.get("sha")}
                except RuntimeError:
                    row["first_party_files"][candidate] = {"exists": False}
        normalized.append(row)

    output = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "kind": "raw-discovery",
        "organization": args.org,
        "count": len(normalized),
        "repositories": sorted(normalized, key=lambda r: r["name"].lower()),
    }
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(normalized)} repositories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
