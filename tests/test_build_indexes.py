from __future__ import annotations

import datetime as dt
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
        for name in (
            "projects.json",
            "publications.json",
            "project-publication-links.json",
            "github-repositories.json",
            "relationships.json",
        ):
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

    def test_rejects_project_id_outside_namespace(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        projects["projects"][0]["id"] = projects["projects"][0]["id"].removeprefix("project:")
        self.write(root, "projects.json", projects)

        with self.assertRaisesRegex(RuntimeError, "invalid project ID namespace"):
            build_indexes.build(root)

    def test_rejects_publication_id_outside_namespace(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        links = self.read(root, "project-publication-links.json")
        publication = publications["publications"][0]
        old_id = publication["id"]
        new_id = old_id.removeprefix("publication:")
        publication["id"] = new_id
        for link in links["links"]:
            if link.get("publication_id") == old_id:
                link["publication_id"] = new_id
        self.write(root, "publications.json", publications)
        self.write(root, "project-publication-links.json", links)

        with self.assertRaisesRegex(RuntimeError, "invalid publication ID namespace"):
            build_indexes.build(root)

    def test_rejects_project_source_path_outside_curated_binding(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        project = next(
            project for project in projects["projects"]
            if project.get("id") == "project:qsol-ark"
        )
        project["source"] = "https://github.com/QSOLKCB/QSOL-ARK/blob/main/DOES-NOT-EXIST.md"
        self.write(root, "projects.json", projects)

        with self.assertRaisesRegex(RuntimeError, "does not match independently curated source"):
            build_indexes.build(root)

    def test_rejects_project_source_from_wrong_repository(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        project = next(
            project for project in projects["projects"]
            if project.get("id") == "project:qec"
        )
        project["source"] = "https://github.com/unrelated/repo/blob/main/README.md"
        self.write(root, "projects.json", projects)

        with self.assertRaisesRegex(RuntimeError, "source repository"):
            build_indexes.build(root)

    def test_rejects_external_publication_source_with_unrelated_doi(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        publications["publications"][0]["source"] = "https://doi.org/10.5281/zenodo.99999999"
        self.write(root, "publications.json", publications)

        with self.assertRaisesRegex(
            RuntimeError,
            "publication ownership evidence must bind both asserted project and selected publication",
        ):
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

    def test_rejects_ownership_reassignment_without_repository_manifest_support(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        links = self.read(root, "project-publication-links.json")
        pub = next(
            p for p in publications["publications"]
            if p["id"] == "publication:zenodo-22026554"
        )
        pub["repository_association"] = "project:galaxy"
        pub["source"] = "https://doi.org/10.5281/zenodo.22026554"
        link = next(
            link for link in links["links"]
            if link.get("publication_id") == pub["id"]
            and link.get("relation") == "repository-associated-publication"
        )
        link["project_id"] = "project:galaxy"
        link["evidence"] = ["https://doi.org/10.5281/zenodo.22026554"]
        self.write(root, "publications.json", publications)
        self.write(root, "project-publication-links.json", links)

        with self.assertRaisesRegex(
            RuntimeError,
            "publication ownership disagrees with curated GitHub registry",
        ):
            build_indexes.build(root)

    def test_rejects_zenodo_publication_id_doi_mismatch(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        links = self.read(root, "project-publication-links.json")
        pub = next(
            p for p in publications["publications"]
            if p["id"] == "publication:zenodo-22026554"
        )
        old_id = pub["id"]
        pub["id"] = "publication:zenodo-99999999"
        for link in links["links"]:
            if link.get("publication_id") == old_id:
                link["publication_id"] = pub["id"]
        self.write(root, "publications.json", publications)
        self.write(root, "project-publication-links.json", links)

        with self.assertRaisesRegex(
            RuntimeError,
            "Zenodo publication ID must match declared DOI record",
        ):
            build_indexes.build(root)

    def test_future_generated_date_is_rejected(self):
        root = self.fixture()
        for name in (
            "projects.json",
            "publications.json",
            "project-publication-links.json",
            "github-repositories.json",
            "relationships.json",
        ):
            doc = self.read(root, name)
            doc["generated_at"] = "2999-01-01"
            self.write(root, name, doc)

        with self.assertRaisesRegex(RuntimeError, "must not be in the future"):
            build_indexes.build(root)

    def test_rejects_case_only_duplicate_curated_publication_dois(self):
        root = self.fixture()
        github = self.read(root, "github-repositories.json")
        row = next(
            row for row in github["repositories"]
            if row.get("full_name") == "QSOLKCB/UFF"
        )
        row["publication_dois"].append("10.5281/ZENODO.22026554")
        self.write(root, "github-repositories.json", github)

        with self.assertRaisesRegex(RuntimeError, "unique publication_dois"):
            build_indexes.build(root)

    def test_rejects_fabricated_publication_github_path(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        links = self.read(root, "project-publication-links.json")
        pub = next(
            pub for pub in publications["publications"]
            if pub["id"] == "publication:zenodo-22026554"
        )
        fabricated = "https://github.com/QSOLKCB/UFF/blob/main/DOES-NOT-EXIST.md"
        pub["source"] = fabricated
        link = next(
            link for link in links["links"]
            if link.get("relation") == "repository-associated-publication"
            and link.get("publication_id") == pub["id"]
        )
        link["evidence"] = [fabricated]
        self.write(root, "publications.json", publications)
        self.write(root, "project-publication-links.json", links)

        with self.assertRaisesRegex(
            RuntimeError,
            "publication GitHub source does not match independently curated source",
        ):
            build_indexes.build(root)

    def test_rejects_missing_declared_lineage_link(self):
        root = self.fixture()
        links = self.read(root, "project-publication-links.json")
        links["links"] = [
            link for link in links["links"]
            if link.get("relation") != "lineage-reference"
        ]
        self.write(root, "project-publication-links.json", links)

        with self.assertRaisesRegex(
            RuntimeError,
            "lineage-reference links must exactly match historical-lineage declarations",
        ):
            build_indexes.build(root)

    def test_rejects_lineage_publication_from_unrelated_origin(self):
        root = self.fixture()
        relationships = self.read(root, "relationships.json")
        rel = next(
            rel for rel in relationships["relationships"]
            if rel.get("relation_type") == "historical-lineage"
        )
        rel["source"] = "project:qsolqec"
        self.write(root, "relationships.json", relationships)

        with self.assertRaisesRegex(
            RuntimeError,
            "historical-lineage publication must belong to the origin project",
        ):
            build_indexes.build(root)

    def test_rejects_bilateral_relationship_without_both_endpoint_sources(self):
        root = self.fixture()
        relationships = self.read(root, "relationships.json")
        rel = next(
            rel for rel in relationships["relationships"]
            if rel.get("relation_type") == "shared-validation-architecture"
        )
        rel["target"] = "project:spectral"
        rel["evidence"] = [
            "https://github.com/QSOLKCB/GALAXY/blob/main/README.md"
        ]
        self.write(root, "relationships.json", relationships)

        with self.assertRaisesRegex(
            RuntimeError,
            "bilateral relationship evidence must cover both endpoints",
        ):
            build_indexes.build(root)

    def test_rejects_non_string_publication_title(self):
        root = self.fixture()
        publications = self.read(root, "publications.json")
        publications["publications"][0]["title"] = 123
        self.write(root, "publications.json", publications)

        with self.assertRaisesRegex(
            RuntimeError,
            "publication title must be a non-empty string",
        ):
            build_indexes.build(root)

    def test_rejects_non_atomic_project_theme_slug(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        project = next(
            project for project in projects["projects"]
            if project.get("id") == "project:res-rag-viz"
        )
        project["themes"] = [
            "../projects/res-rag-viz" if theme == "visualisation" else theme
            for theme in project["themes"]
        ]
        self.write(root, "projects.json", projects)

        with self.assertRaisesRegex(
            RuntimeError,
            "project themes must use the atomic theme slug namespace",
        ):
            build_indexes.build(root)

    def test_rejects_bilateral_theme_not_supported_by_both_endpoints(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        uff = next(
            project for project in projects["projects"]
            if project.get("id") == "project:uff"
        )
        uff["themes"] = [theme for theme in uff["themes"] if theme != "provenance"]
        self.write(root, "projects.json", projects)

        with self.assertRaisesRegex(
            RuntimeError,
            "bilateral relationship theme must be supported by both endpoints",
        ):
            build_indexes.build(root)

    def test_generated_date_can_advance_without_old_index_state(self):
        root = self.fixture()
        current_date = dt.date.today().isoformat()
        for name in (
            "projects.json",
            "publications.json",
            "project-publication-links.json",
            "github-repositories.json",
            "relationships.json",
        ):
            doc = self.read(root, name)
            doc["generated_at"] = current_date
            self.write(root, name, doc)

        built = build_indexes.build(root)
        self.assertEqual(built["generated_at"], current_date)
        self.assertTrue(all(row["access_date"] == current_date for row in built["sources"]))

    def test_rejects_non_string_project_name(self):
        root = self.fixture()
        projects = self.read(root, "projects.json")
        project = next(
            project for project in projects["projects"]
            if project.get("id") == "project:uft-id-3-0"
        )
        project["name"] = 123
        self.write(root, "projects.json", projects)

        with self.assertRaisesRegex(
            RuntimeError,
            "project name must be a non-empty string",
        ):
            build_indexes.build(root)

    def test_rejects_relationship_evidence_from_endpoint_without_theme(self):
        root = self.fixture()
        relationships = self.read(root, "relationships.json")
        rel = next(
            rel for rel in relationships["relationships"]
            if rel.get("source") == "project:qsol-qec-bridge"
            and rel.get("target") == "project:qsolqec"
            and rel.get("theme") == "provenance"
        )
        rel["evidence"] = [
            "https://github.com/QSOLKCB/QSOLQEC/blob/main/README.md"
        ]
        self.write(root, "relationships.json", relationships)

        with self.assertRaisesRegex(
            RuntimeError,
            "relationship evidence must come from an endpoint supporting the theme",
        ):
            build_indexes.build(root)



if __name__ == "__main__":
    unittest.main()
