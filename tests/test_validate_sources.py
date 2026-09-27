from __future__ import annotations

import csv
import json
import pathlib
import shutil
import tempfile
import unittest

from scripts import validate_sources


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CURATED_JSON = (
    "projects.json",
    "publications.json",
    "themes.json",
    "relationships.json",
    "project-publication-links.json",
    "source-index.json",
)


class ValidateSourcesRegressionTests(unittest.TestCase):
    def fixture(self) -> pathlib.Path:
        root = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        for directory in ("data", "evidence", "paper", "themes", "projects"):
            shutil.copytree(REPO_ROOT / directory, root / directory)
        return root

    def read_json(self, root: pathlib.Path, name: str) -> dict:
        return json.loads((root / "data" / name).read_text(encoding="utf-8"))

    def write_json(self, root: pathlib.Path, name: str, doc: dict) -> None:
        (root / "data" / name).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    def assert_has(self, errors: list[str], text: str) -> None:
        self.assertTrue(any(text in error for error in errors), errors)

    def test_baseline_fixture_validates(self):
        self.assertEqual(validate_sources.validate(REPO_ROOT), [])

    def test_relationship_evidence_must_reference_an_endpoint_repository(self):
        root = self.fixture()
        doc = self.read_json(root, "relationships.json")
        doc["relationships"][0]["evidence"] = [
            "https://github.com/unrelated-owner/unrelated-repo/blob/main/README.md"
        ]
        self.write_json(root, "relationships.json", doc)

        self.assert_has(validate_sources.validate(root), "evidence repository must match an endpoint")

    def test_matrix_cannot_deny_declared_theme_support(self):
        root = self.fixture()
        projects = self.read_json(root, "projects.json")["projects"]
        project = next(p for p in projects if p.get("themes"))
        theme = project["themes"][0]

        matrix = root / "evidence" / "project-theme-matrix.csv"
        with matrix.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0].keys())
        for row in rows:
            if row["project_id"] == project["id"]:
                row[theme] = "not-found"
        with matrix.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        self.assert_has(validate_sources.validate(root), "matrix denies declared theme support")

    def test_generated_at_must_be_real_iso_date(self):
        root = self.fixture()
        for name in CURATED_JSON:
            doc = self.read_json(root, name)
            doc["generated_at"] = "not-a-date"
            self.write_json(root, name, doc)

        self.assert_has(validate_sources.validate(root), "generated_at must use a real YYYY-MM-DD date")

    def test_doi_uniqueness_is_case_insensitive(self):
        root = self.fixture()
        doc = self.read_json(root, "publications.json")
        first = doc["publications"][0]["doi"]
        doc["publications"][1]["doi"] = first.upper()
        self.write_json(root, "publications.json", doc)

        self.assert_has(validate_sources.validate(root), "duplicate DOI ignoring case")

    def test_theme_ids_must_be_unique(self):
        root = self.fixture()
        doc = self.read_json(root, "themes.json")
        doc["themes"][1]["id"] = doc["themes"][0]["id"]
        self.write_json(root, "themes.json", doc)

        self.assert_has(validate_sources.validate(root), "theme IDs must be non-null and unique")

    def test_mechanism_claim_true_is_rejected(self):
        root = self.fixture()
        doc = self.read_json(root, "relationships.json")
        doc["relationships"][0]["mechanism_claim"] = True
        self.write_json(root, "relationships.json", doc)

        self.assert_has(validate_sources.validate(root), "must set mechanism_claim=false")

    def test_missing_matrix_row_is_rejected(self):
        root = self.fixture()
        matrix = root / "evidence" / "project-theme-matrix.csv"
        lines = matrix.read_text(encoding="utf-8").splitlines()
        matrix.write_text("\n".join([lines[0], *lines[2:]]) + "\n", encoding="utf-8")

        self.assert_has(validate_sources.validate(root), "matrix project rows must match projects.json exactly")

    def test_invalid_concept_doi_is_rejected(self):
        root = self.fixture()
        doc = self.read_json(root, "publications.json")
        doc["publications"][0]["concept_doi"] = "not-a-doi"
        self.write_json(root, "publications.json", doc)

        self.assert_has(validate_sources.validate(root), "invalid concept DOI syntax")

    def test_duplicate_source_ids_are_rejected(self):
        root = self.fixture()
        doc = self.read_json(root, "source-index.json")
        duplicate = dict(doc["sources"][0])
        duplicate["path"] = "OTHER.md"
        doc["sources"].append(duplicate)
        self.write_json(root, "source-index.json", doc)

        self.assert_has(validate_sources.validate(root), "source IDs must be non-null and unique")

    def test_missing_publication_association_is_rejected(self):
        root = self.fixture()
        doc = self.read_json(root, "publications.json")
        doc["publications"][0]["repository_association"] = "project:missing"
        self.write_json(root, "publications.json", doc)

        self.assert_has(validate_sources.validate(root), "publication association missing project")

    def test_publication_without_traceable_source_is_rejected(self):
        root = self.fixture()
        doc = self.read_json(root, "publications.json")
        doc["publications"][0]["source"] = None
        self.write_json(root, "publications.json", doc)

        self.assert_has(validate_sources.validate(root), "publication requires a traceable source URL")


if __name__ == "__main__":
    unittest.main()
