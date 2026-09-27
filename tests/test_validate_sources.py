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
    "github-repositories.json",
    "zenodo-records.json",
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

    def test_project_url_must_match_declared_repository(self):
        root = self.fixture()
        doc = self.read_json(root, "projects.json")
        doc["projects"][0]["url"] = "https://github.com/unrelated/fabricated"
        self.write_json(root, "projects.json", doc)

        self.assert_has(validate_sources.validate(root), "project URL must match repository")

    def test_curated_github_registry_must_match_project_registry(self):
        root = self.fixture()
        doc = self.read_json(root, "github-repositories.json")
        doc["repositories"][0]["full_name"] = "QSOLKCB/FABRICATED"
        self.write_json(root, "github-repositories.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "curated GitHub registry repositories must match projects.json exactly",
        )

    def test_curated_zenodo_registry_must_match_publications(self):
        root = self.fixture()
        doc = self.read_json(root, "zenodo-records.json")
        doc["records"][0]["doi"] = "10.5281/zenodo.99999999"
        self.write_json(root, "zenodo-records.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "curated Zenodo DOI set must match Zenodo publications exactly",
        )

    def test_relationship_evidence_must_reference_an_endpoint_repository(self):
        root = self.fixture()
        doc = self.read_json(root, "relationships.json")
        doc["relationships"][0]["evidence"] = [
            "https://github.com/unrelated-owner/unrelated-repo/blob/main/README.md"
        ]
        self.write_json(root, "relationships.json", doc)

        self.assert_has(validate_sources.validate(root), "evidence repository must match an endpoint")

    def test_every_publication_association_requires_an_ownership_link(self):
        root = self.fixture()
        doc = self.read_json(root, "project-publication-links.json")
        ownership_index = next(
            i for i, link in enumerate(doc["links"])
            if link.get("relation") == "repository-associated-publication"
        )
        doc["links"].pop(ownership_index)
        self.write_json(root, "project-publication-links.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "repository-associated-publication links must exactly match publication associations",
        )

    def test_extra_ownership_link_without_matching_association_is_rejected(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        links = self.read_json(root, "project-publication-links.json")
        pub = pubs["publications"][0]
        wrong_project = next(
            project["id"]
            for project in self.read_json(root, "projects.json")["projects"]
            if project["id"] != pub["repository_association"]
        )
        links["links"].append({
            "project_id": wrong_project,
            "publication_id": pub["id"],
            "relation": "repository-associated-publication",
            "evidence": [pub["source"]],
        })
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "repository-associated-publication links must exactly match publication associations",
        )

    def test_lineage_evidence_must_come_from_referencing_project(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        projects = self.read_json(root, "projects.json")["projects"]
        links = self.read_json(root, "project-publication-links.json")
        pub = pubs["publications"][0]
        wrong_project = next(
            project for project in projects
            if project["id"] != pub["repository_association"]
            and project["repo"] != validate_sources.github_repository(pub["source"])
        )
        links["links"].append({
            "project_id": wrong_project["id"],
            "publication_id": pub["id"],
            "relation": "lineage-reference",
            "evidence": [pub["source"]],
        })
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "publication link evidence is not traceable to the linked project/publication",
        )

    def test_existing_lineage_reference_is_accepted(self):
        self.assertEqual(validate_sources.validate(REPO_ROOT), [])

    def test_publication_link_evidence_must_be_traceable(self):
        root = self.fixture()
        doc = self.read_json(root, "project-publication-links.json")
        doc["links"][0]["evidence"] = ["fabricated-evidence"]
        self.write_json(root, "project-publication-links.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "publication link evidence is not traceable to the linked project/publication",
        )

    def test_publication_external_source_must_match_declared_doi(self):
        root = self.fixture()
        doc = self.read_json(root, "publications.json")
        doc["publications"][0]["source"] = "https://doi.org/10.5281/zenodo.99999999"
        self.write_json(root, "publications.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "publication external source does not match DOI/concept DOI",
        )

    def test_concept_doi_cannot_borrow_unrelated_publication_identity(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        first = pubs["publications"][0]
        unrelated = next(
            pub for pub in pubs["publications"][1:]
            if pub.get("repository_association") != first.get("repository_association")
            and pub.get("doi")
        )
        first["concept_doi"] = unrelated["doi"]
        self.write_json(root, "publications.json", pubs)

        self.assert_has(
            validate_sources.validate(root),
            "concept DOI repository association mismatch",
        )

    def test_concept_doi_requires_curated_zenodo_record(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        pubs["publications"][0]["concept_doi"] = "10.5281/zenodo.99999999"
        self.write_json(root, "publications.json", pubs)

        self.assert_has(
            validate_sources.validate(root),
            "concept DOI missing curated Zenodo record",
        )

    def test_concept_doi_must_point_to_concept_record(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        target = next(
            pub for pub in pubs["publications"]
            if pub.get("resource_type") != "concept-doi"
            and pub.get("doi")
        )
        owner = target.get("repository_association")
        other = next(
            pub for pub in pubs["publications"]
            if pub.get("repository_association") == owner
            and pub.get("id") != target.get("id")
        )
        other["concept_doi"] = target["doi"]
        self.write_json(root, "publications.json", pubs)

        self.assert_has(
            validate_sources.validate(root),
            "concept DOI must resolve to a curated concept-doi record",
        )

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
