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
RELEASE_PAGE_SIZE = 100


def request(url: str, token: str | None, cache_dir: pathlib.Path, ttl_seconds: int):
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = urllib.parse.quote(url, safe="") + ".json"
    cache_file = cache_dir / key
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < ttl_seconds:
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"GitHub cached response is not valid JSON: {url}") from exc
    headers = {"User-Agent": "QSOL-SYNTHESIS-collector", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub request failed: {url} -> HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", str(exc))
        raise RuntimeError(f"GitHub request failed: {url} -> {reason}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"GitHub response is not valid JSON: {url}") from exc
    cache_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def collect_release_pages(
    org: str,
    name: str,
    token: str | None,
    cache_dir: pathlib.Path,
    ttl_seconds: int,
    request_fn=request,
) -> tuple[list[dict], bool, str | None]:
    releases: list[dict] = []
    page = 1
    while True:
        url = (
            f"{API}/repos/{org}/{name}/releases"
            f"?per_page={RELEASE_PAGE_SIZE}&page={page}"
        )
        try:
            batch = request_fn(url, token, cache_dir, ttl_seconds)
        except (RuntimeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return releases, False, str(exc)
        if not isinstance(batch, list):
            return releases, False, "unexpected GitHub releases response"
        if any(not isinstance(item, dict) for item in batch):
            releases.extend(item for item in batch if isinstance(item, dict))
            return releases, False, "unexpected GitHub release entry"
        releases.extend(batch)
        if len(batch) < RELEASE_PAGE_SIZE:
            return releases, True, None
        page += 1


def collect_public_repositories(
    org: str,
    token: str | None,
    cache_dir: pathlib.Path,
    ttl_seconds: int,
    include_enrichment: bool,
    request_fn=request,
) -> dict:
    repos = []
    page = 1
    while True:
        batch = request_fn(
            f"{API}/orgs/{org}/repos?per_page=100&type=public&page={page}",
            token,
            cache_dir,
            ttl_seconds,
        )
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected GitHub repositories response")
        for repo in batch:
            if (
                not isinstance(repo, dict)
                or not isinstance(repo.get("name"), str)
                or not repo.get("name")
                or not isinstance(repo.get("full_name"), str)
                or not repo.get("full_name")
                or not isinstance(repo.get("html_url"), str)
                or not repo.get("html_url")
                or not isinstance(repo.get("default_branch"), str)
                or not repo.get("default_branch")
            ):
                raise RuntimeError("Unexpected GitHub repository inventory entry")
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
        if include_enrichment:
            releases, complete, error = collect_release_pages(
                org, name, token, cache_dir, ttl_seconds, request_fn=request_fn
            )
            row["releases"] = releases
            row["releases_complete"] = complete
            if error is not None:
                row["releases_error"] = error

            row["first_party_files"] = {}
            for candidate in ("README.md", "CITATION.cff", ".zenodo.json"):
                try:
                    meta = request_fn(
                        f"{API}/repos/{org}/{name}/contents/{candidate}",
                        token,
                        cache_dir,
                        ttl_seconds,
                    )
                    if not isinstance(meta, dict):
                        row["first_party_files"][candidate] = {
                            "exists": None,
                            "error": "unexpected GitHub contents response",
                        }
                    else:
                        sha = meta.get("sha")
                        if not isinstance(sha, str) or not sha:
                            row["first_party_files"][candidate] = {
                                "exists": None,
                                "error": "GitHub contents response missing file sha",
                            }
                        else:
                            row["first_party_files"][candidate] = {
                                "exists": True,
                                "sha": sha,
                            }
                except (RuntimeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                    message = str(exc)
                    if "HTTP 404" in message:
                        row["first_party_files"][candidate] = {"exists": False}
                    else:
                        row["first_party_files"][candidate] = {
                            "exists": None,
                            "error": message,
                        }
        normalized.append(row)

    return {
        "kind": "raw-discovery",
        "organization": org,
        "count": len(normalized),
        "repositories": sorted(normalized, key=lambda r: r["name"].lower()),
    }


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
    output = collect_public_repositories(
        org=args.org,
        token=token,
        cache_dir=pathlib.Path(args.cache_dir),
        ttl_seconds=args.ttl_seconds,
        include_enrichment=args.include_enrichment,
    )
    output["generated_at"] = time.strftime("%Y-%m-%d")

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({output['count']} repositories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
