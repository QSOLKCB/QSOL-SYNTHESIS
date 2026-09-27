#!/usr/bin/env python3
"""Collect public GitHub organization metadata for QSOL-SYNTHESIS."""
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


def _request(url: str, token: str | None, cache_dir: pathlib.Path, ttl_seconds: int) -> dict | list:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = urllib.parse.quote(url, safe="") + ".json"
    cache_file = cache_dir / key
    if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < ttl_seconds:
        return json.loads(cache_file.read_text(encoding="utf-8"))

    headers = {"User-Agent": "QSOL-SYNTHESIS-collector"}
    if token:
        headers["Authorization"] = f"token {token}"
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
    parser.add_argument("--output", default="data/github-repositories.json")
    parser.add_argument("--cache-dir", default="data/cache/github")
    parser.add_argument("--ttl-seconds", type=int, default=86400)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()

    token = os.environ.get(args.token_env)
    cache_dir = pathlib.Path(args.cache_dir)

    repos = _request(f"{API}/orgs/{args.org}/repos?per_page=100&type=public", token, cache_dir, args.ttl_seconds)
    if not isinstance(repos, list):
        raise RuntimeError("Unexpected GitHub repos response format")

    normalized: list[dict] = []
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        releases_url = f"{API}/repos/{args.org}/{name}/releases?per_page=5"
        try:
            releases = _request(releases_url, token, cache_dir, args.ttl_seconds)
        except RuntimeError:
            releases = []

        first_party_files = {}
        for candidate in ["README.md", "CITATION.cff", ".zenodo.json"]:
            url = f"{API}/repos/{args.org}/{name}/contents/{candidate}"
            try:
                meta = _request(url, token, cache_dir, args.ttl_seconds)
                first_party_files[candidate] = {"exists": True, "sha": meta.get("sha")}
            except RuntimeError:
                first_party_files[candidate] = {"exists": False}

        normalized.append(
            {
                "name": name,
                "full_name": repo.get("full_name"),
                "html_url": repo.get("html_url"),
                "description": repo.get("description"),
                "default_branch": repo.get("default_branch"),
                "archived": repo.get("archived"),
                "visibility": "public" if not repo.get("private") else "private",
                "updated_at": repo.get("updated_at"),
                "releases": [
                    {
                        "tag_name": r.get("tag_name"),
                        "name": r.get("name"),
                        "published_at": r.get("published_at"),
                        "html_url": r.get("html_url"),
                    }
                    for r in releases if isinstance(r, dict)
                ],
                "first_party_files": first_party_files,
            }
        )

    output = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "organization": args.org,
        "collection_notes": "Public metadata only. No archives downloaded.",
        "repositories": sorted(normalized, key=lambda r: r["name"].lower()),
    }
    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(normalized)} repos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
