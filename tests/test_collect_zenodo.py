from __future__ import annotations

import argparse
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from scripts import collect_zenodo


class CollectZenodoRegressionTests(unittest.TestCase):
    def test_nonpositive_page_limits_are_rejected(self):
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    collect_zenodo.positive_int(value)

    def test_main_rejects_zero_max_pages_before_network_access(self):
        with self.assertRaises(SystemExit) as ctx:
            collect_zenodo.main([
                "--queries", "probe",
                "--publications", "/does/not/exist",
                "--max-pages", "0",
            ])
        self.assertEqual(ctx.exception.code, 2)

    def test_query_all_paginates(self):
        calls = []

        def fake(url):
            calls.append(url)
            if "page=1" in url:
                return {"hits": {"total": 3, "hits": [{"id": 1}, {"id": 2}]}}
            if "page=2" in url:
                return {"hits": {"total": 3, "hits": [{"id": 3}]}}
            raise AssertionError(url)

        with mock.patch.object(collect_zenodo, "get_json", side_effect=fake):
            pages = list(collect_zenodo.query_all("probe", per_page=2, max_pages=10))

        self.assertEqual(len(pages), 2)
        self.assertEqual(sum(len(hits) for _, hits in pages), 3)
        self.assertTrue(all(total == 3 for total, _ in pages))
        self.assertEqual(len(calls), 2)

    def test_timeout_is_recorded_and_output_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "zenodo.json"
            with mock.patch.object(collect_zenodo, "get_json", side_effect=TimeoutError("timed out")):
                rc = collect_zenodo.main([
                    "--queries", "probe",
                    "--publications", "/does/not/exist",
                    "--projects", "/does/not/exist",
                    "--output", str(output),
                ])

            self.assertEqual(rc, 0)
            doc = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(doc["records"], [])
            self.assertTrue(doc["errors"])
            self.assertEqual(doc["errors"][0]["query"], "probe")

    def test_exact_doi_search_discards_nonmatching_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            output = root / "zenodo.json"
            publications = root / "publications.json"
            publications.write_text(
                json.dumps({"publications": [{"doi": "10.1234/wanted"}]}),
                encoding="utf-8",
            )

            unrelated_hit = {
                "id": 99,
                "doi": "10.1234/unrelated",
                "conceptdoi": "10.1234/also-unrelated",
                "metadata": {"title": "Unrelated", "resource_type": {}},
                "links": {},
            }

            def fake_query_all(query, per_page, max_pages):
                self.assertEqual(query, 'doi:"10.1234/wanted"')
                yield 1, [unrelated_hit]

            with mock.patch.object(collect_zenodo, "query_all", side_effect=fake_query_all):
                rc = collect_zenodo.main([
                    "--queries",
                    "--publications", str(publications),
                    "--projects", str(root / "missing-projects.json"),
                    "--output", str(output),
                ])

            self.assertEqual(rc, 0)
            doc = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(doc["records"], [])
            self.assertTrue(any(
                error.get("doi") == "10.1234/wanted"
                and "no matching DOI or concept DOI" in error.get("error", "")
                for error in doc["errors"]
            ))


if __name__ == "__main__":
    unittest.main()
