#!/usr/bin/env python3
"""Collect Zenodo candidate records for QSOL-SYNTHESIS.

This script is conservative by design. It records query evidence and does not
fabricate metadata when Zenodo is unreachable.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

ZENODO_API = "https://zenodo.org/api/records"


def fetch(query: str, size: int = 20) -> dict:
    params = urllib.parse.urlencode({"q": query, "size": size})
    url = f"{ZENODO_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "QSOL-SYNTHESIS-collector"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/zenodo-records.json")
    parser.add_argument("--queries", nargs="*", default=["Trent Slade", "QSOL", "QSOL-IMC", "QSOLKCB"])
    args = parser.parse_args()

    result = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "source": "zenodo-api",
        "query_results": [],
        "records": [],
        "notes": [],
    }

    index: dict[str, dict] = {}
    for q in args.queries:
        try:
            payload = fetch(q)
            hits = payload.get("hits", {}).get("hits", [])
            result["query_results"].append({"query": q, "hit_count": len(hits)})
            for hit in hits:
                doi = hit.get("doi")
                rec = {
                    "record_id": hit.get("id"),
                    "doi": doi,
                    "conceptdoi": hit.get("conceptdoi"),
                    "title": hit.get("metadata", {}).get("title"),
                    "publication_date": hit.get("metadata", {}).get("publication_date"),
                    "resource_type": hit.get("metadata", {}).get("resource_type", {}).get("type"),
                    "version": hit.get("metadata", {}).get("version"),
                    "url": hit.get("links", {}).get("self_html"),
                    "query": q,
                }
                key = doi or str(rec["record_id"])
                if key not in index:
                    index[key] = rec
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            result["query_results"].append({"query": q, "error": str(exc)})

    result["records"] = sorted(index.values(), key=lambda r: (r.get("doi") or "", r.get("record_id") or 0))
    if not result["records"]:
        result["notes"].append("No Zenodo records collected; network or DNS may be unavailable in this environment.")

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(result['records'])} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
