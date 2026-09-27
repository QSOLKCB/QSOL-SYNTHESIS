#!/usr/bin/env python3
"""Collect raw Zenodo discovery metadata without promoting it into the curated corpus."""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://zenodo.org/api/records"
ZENODO_DOI_RE = re.compile(r"^10\.5281/zenodo\.(\d+)$", re.IGNORECASE)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "QSOL-SYNTHESIS-collector"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalise(hit: dict, discovered_by: str) -> dict:
    metadata = hit.get("metadata") or {}
    resource = metadata.get("resource_type") or {}
    return {
        "record_id": hit.get("id"),
        "doi": hit.get("doi"),
        "conceptdoi": hit.get("conceptdoi"),
        "title": metadata.get("title"),
        "publication_date": metadata.get("publication_date"),
        "resource_type": resource.get("type"),
        "version": metadata.get("version"),
        "creators": [c.get("name") for c in metadata.get("creators", []) if isinstance(c, dict)],
        "url": (hit.get("links") or {}).get("self_html"),
        "discovered_by": [discovered_by],
    }


def merge_record(index: dict[str, dict], rec: dict) -> None:
    key = str(rec.get("record_id") or rec.get("doi") or rec.get("title"))
    if key in index:
        seen = set(index[key].get("discovered_by", []))
        seen.update(rec.get("discovered_by", []))
        index[key]["discovered_by"] = sorted(seen)
    else:
        index[key] = rec


def query_all(query: str, per_page: int, max_pages: int):
    page = 1
    total = None
    while page <= max_pages:
        params = urllib.parse.urlencode({"q": query, "size": per_page, "page": page, "sort": "mostrecent"})
        payload = get_json(f"{API}?{params}")
        hits_obj = payload.get("hits") or {}
        if total is None:
            raw_total = hits_obj.get("total", 0)
            total = raw_total.get("value", 0) if isinstance(raw_total, dict) else int(raw_total or 0)
        hits = hits_obj.get("hits", [])
        yield total, hits
        if not hits or len(hits) < per_page:
            break
        page += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/raw/zenodo-records.json")
    parser.add_argument("--queries", nargs="*", default=["Trent Slade", "QSOL-IMC", "QSOLKCB"])
    parser.add_argument("--publications", default="data/publications.json",
                        help="Curated publication registry; its DOIs are looked up exactly when possible.")
    parser.add_argument("--projects", default="data/projects.json")
    parser.add_argument("--include-project-queries", action="store_true")
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()

    queries = list(args.queries)
    projects_path = pathlib.Path(args.projects)
    if args.include_project_queries and projects_path.exists():
        doc = json.loads(projects_path.read_text(encoding="utf-8"))
        queries.extend(p.get("name") for p in doc.get("projects", []) if p.get("name"))

    result = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "kind": "raw-discovery",
        "source": "zenodo-api",
        "query_results": [],
        "records": [],
        "errors": [],
    }
    index: dict[str, dict] = {}

    for query in dict.fromkeys(queries):
        try:
            seen = 0
            reported_total = 0
            pages = 0
            for total, hits in query_all(query, args.per_page, args.max_pages):
                reported_total = total
                pages += 1
                seen += len(hits)
                for hit in hits:
                    merge_record(index, normalise(hit, f"query:{query}"))
            result["query_results"].append({
                "query": query,
                "reported_total": reported_total,
                "retrieved": seen,
                "pages": pages,
                "truncated": seen < reported_total,
            })
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            result["errors"].append({"query": query, "error": str(exc)})

    pubs_path = pathlib.Path(args.publications)
    if pubs_path.exists():
        pubs = json.loads(pubs_path.read_text(encoding="utf-8")).get("publications", [])
        for pub in pubs:
            doi = pub.get("doi")
            if not doi:
                continue
            m = ZENODO_DOI_RE.match(doi)
            try:
                if m:
                    hit = get_json(f"{API}/{m.group(1)}")
                    merge_record(index, normalise(hit, f"exact-doi:{doi}"))
                else:
                    for _, hits in query_all(f'doi:"{doi}"', args.per_page, 1):
                        for hit in hits:
                            merge_record(index, normalise(hit, f"exact-doi:{doi}"))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                result["errors"].append({"doi": doi, "error": str(exc)})

    result["records"] = sorted(index.values(), key=lambda r: (r.get("record_id") or 0, r.get("doi") or ""))
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(result['records'])} unique records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
