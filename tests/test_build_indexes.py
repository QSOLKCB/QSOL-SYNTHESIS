from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from scripts import build_indexes


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class BuildIndexesRegressionTests(unittest.TestCase):
    def fixture(self) -> pathlib.Path:
        temp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        (temp / "data").mkdir()
        for name in ("projects.json", "publications.json", "project-publication-links.json"):
            shutil.copy2(REPO_ROOT / "data" / name, temp / "data" / name)
        return temp

    def read(self, root: pathlib.Path, name: str) -> dict:
        return json.loads((root / "data" / name).read_text(encoding="utf-8"))

    def write(self, root: pathlib.Path, name: str, doc: dict) -> None:
        (root / "data" / name).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    def test_rejects_publication_without_traceable_source(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        publications["publications"][0]["source"] = None
        self.write(root, "publications.json", publications)

        with self.assertRaisesRegex(RuntimeError, "publication .* no traceable source"):
            build_indexes.build(root)

    def test_rejects_unparseable_publication_source(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        publications["publications"][0]["source"] = "not-a-source"
        self.write(root, "publications.json", publications)

        with self.assertRaisesRegex(RuntimeError, "publication .* no traceable source"):
            build_indexes.build(root)

    def test_rejects_project_source_from_wrong_repository(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        projects["projects"][0]["source"] = "https://github.com/unrelated/repo/blob/main/README.md"
        self.write(root, "projects.json", projects)

        with self.assertRaisesRegex(RuntimeError, "source repository"):
            build_indexes.build(root)

    def test_rejects_external_publication_source_with_unrelated_doi(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        publications["publications"][0]["source"] = "https://doi.org/10.5281/zenodo.99999999"
        self.write(root, "publications.json", publications)

        with self.assertRaisesRegex(RuntimeError, "external source does not match"):
            build_indexes.build(root)

    def test_equivalent_repository_case_is_canonicalized(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        project = projects["projects"][0]
        declared_repo = project["repo"]
        project["source"] = project["source"].replace(declared_repo, declared_repo.swapcase())
        self.write(root, "projects.json", projects)

        built = build_indexes.build(root)
        source_id = build_indexes.project_source_id(project["id"])
        row = next(row for row in built["sources"] if row["source_id"] == source_id)
        self.assertEqual(row["repository"], declared_repo)

    def test_rejects_version_concept_doi_without_curated_ownership_binding(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        concept = next(
            pub for pub in publications["publications"]
            if pub.get("resource_type") == "concept-doi"
        )
        version = next(
            pub for pub in publications["publications"]
            if pub.get("repository_association") == concept.get("repository_association")
            and pub.get("resource_type") != "concept-doi"
        )
        version["concept_doi"] = concept["doi"]
        self.write(root, "publications.json", publications)

        with self.assertRaisesRegex(
            RuntimeError,
            "publication concept DOI disagrees with curated ownership binding",
        ):
            build_indexes.build(root)

    def test_generated_date_can_advance_without_old_index_state(self):
        root = self.fixture()
        for name in ("projects.json", "publications.json", "project-publication-links.json"):
            doc = self.read(root, name)
            doc["generated_at"] = "2099-01-02"
            self.write(root, name, doc)

        built = build_indexes.build(root)
        self.assertEqual(built["generated_at"], "2099-01-02")
        self.assertTrue(all(row["access_date"] == "2099-01-02" for row in built["sources"]))


if __name__ == "__main__":
    unittest.main()
