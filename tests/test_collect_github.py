from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from scripts import collect_github


class CollectGithubRegressionTests(unittest.TestCase):
    def repo(self):
        return {
            "name": "TEST",
            "full_name": "QSOLKCB/TEST",
            "html_url": "https://github.com/QSOLKCB/TEST",
            "description": "test",
            "default_branch": "main",
            "archived": False,
            "private": False,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }

    def test_release_enrichment_paginates_to_completion(self):
        calls = []

        def fake(url, token, cache_dir, ttl_seconds):
            calls.append(url)
            if "/orgs/QSOLKCB/repos" in url:
                return [self.repo()]
            if "/releases?" in url and url.endswith("&page=1"):
                return [{"id": i} for i in range(100)]
            if "/releases?" in url and url.endswith("&page=2"):
                return [{"id": 100}]
            if "/contents/" in url:
                return {"sha": "abc"}
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            result = collect_github.collect_public_repositories(
                "QSOLKCB", None, pathlib.Path(tmp), 0, True, request_fn=fake
            )

        row = result["repositories"][0]
        self.assertEqual(len(row["releases"]), 101)
        self.assertTrue(row["releases_complete"])
        release_calls = [url for url in calls if "/releases?" in url]
        self.assertEqual(len(release_calls), 2)

    def test_enrichment_errors_remain_unknown_not_absent(self):
        def fake(url, token, cache_dir, ttl_seconds):
            if "/orgs/QSOLKCB/repos" in url:
                return [self.repo()]
            if "/releases?" in url:
                return []
            if "/contents/" in url:
                raise RuntimeError("GitHub request failed -> HTTP 403")
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            result = collect_github.collect_public_repositories(
                "QSOLKCB", None, pathlib.Path(tmp), 0, True, request_fn=fake
            )

        files = result["repositories"][0]["first_party_files"]
        self.assertTrue(all(item["exists"] is None for item in files.values()))
        self.assertTrue(all("error" in item for item in files.values()))

    def test_release_error_marks_collection_incomplete(self):
        def fake(url, token, cache_dir, ttl_seconds):
            if "/orgs/QSOLKCB/repos" in url:
                return [self.repo()]
            if "/releases?" in url and url.endswith("&page=1"):
                return [{"id": i} for i in range(100)]
            if "/releases?" in url and url.endswith("&page=2"):
                raise RuntimeError("rate limited")
            if "/contents/" in url:
                return {"sha": "abc"}
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            result = collect_github.collect_public_repositories(
                "QSOLKCB", None, pathlib.Path(tmp), 0, True, request_fn=fake
            )

        row = result["repositories"][0]
        self.assertEqual(len(row["releases"]), 100)
        self.assertFalse(row["releases_complete"])
        self.assertIn("rate limited", row["releases_error"])

    def test_malformed_enrichment_json_is_preserved_as_uncertainty(self):
        def fake(url, token, cache_dir, ttl_seconds):
            if "/orgs/QSOLKCB/repos" in url:
                return [self.repo()]
            if "/releases?" in url:
                raise json.JSONDecodeError("bad json", "not-json", 0)
            if "/contents/" in url:
                return {"sha": "abc"}
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            result = collect_github.collect_public_repositories(
                "QSOLKCB", None, pathlib.Path(tmp), 0, True, request_fn=fake
            )

        row = result["repositories"][0]
        self.assertEqual(row["releases"], [])
        self.assertFalse(row["releases_complete"])
        self.assertIn("bad json", row["releases_error"])

    def test_non_object_content_response_is_unknown(self):
        def fake(url, token, cache_dir, ttl_seconds):
            if "/orgs/QSOLKCB/repos" in url:
                return [self.repo()]
            if "/releases?" in url:
                return []
            if "/contents/" in url:
                return []
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            result = collect_github.collect_public_repositories(
                "QSOLKCB", None, pathlib.Path(tmp), 0, True, request_fn=fake
            )

        files = result["repositories"][0]["first_party_files"]
        self.assertTrue(all(item["exists"] is None for item in files.values()))
        self.assertTrue(all("unexpected GitHub contents response" in item["error"] for item in files.values()))

    def test_malformed_release_entry_marks_collection_incomplete(self):
        def fake(url, token, cache_dir, ttl_seconds):
            if "/releases?" in url:
                return [{"id": 1}, None]
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            releases, complete, error = collect_github.collect_release_pages(
                "QSOLKCB", "TEST", None, pathlib.Path(tmp), 0, request_fn=fake
            )

        self.assertEqual(releases, [{"id": 1}])
        self.assertFalse(complete)
        self.assertEqual(error, "unexpected GitHub release entry")

    def test_malformed_repository_inventory_entry_is_rejected(self):
        def fake(url, token, cache_dir, ttl_seconds):
            if "/orgs/QSOLKCB/repos" in url:
                return [{}]
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                RuntimeError,
                "Unexpected GitHub repository inventory entry",
            ):
                collect_github.collect_public_repositories(
                    "QSOLKCB", None, pathlib.Path(tmp), 0, False, request_fn=fake
                )

    def test_duplicate_repository_identity_across_pages_is_rejected(self):
        page_one = []
        for i in range(100):
            row = self.repo()
            row["name"] = f"TEST{i}"
            row["full_name"] = f"QSOLKCB/TEST{i}"
            row["html_url"] = f"https://github.com/QSOLKCB/TEST{i}"
            page_one.append(row)

        def fake(url, token, cache_dir, ttl_seconds):
            if "page=1" in url:
                return page_one
            if "page=2" in url:
                return [dict(page_one[-1])]
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                RuntimeError,
                "Duplicate GitHub repository inventory identity",
            ):
                collect_github.collect_public_repositories(
                    "QSOLKCB", None, pathlib.Path(tmp), 0, False, request_fn=fake
                )



if __name__ == "__main__":
    unittest.main()
