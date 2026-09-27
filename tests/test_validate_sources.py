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
        for directory in ("data", "evidence", "paper", "themes", "projects", "figures"):
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

    def test_project_id_requires_project_namespace(self):
        root = self.fixture()
        doc = self.read_json(root, "projects.json")
        project = doc["projects"][0]
        project["id"] = project["id"].removeprefix("project:")
        self.write_json(root, "projects.json", doc)

        errors = validate_sources.validate(root)
        self.assert_has(errors, "project IDs must be non-empty strings in the project: namespace")

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

    def test_non_string_curated_zenodo_doi_reports_error_without_crashing(self):
        root = self.fixture()
        doc = self.read_json(root, "zenodo-records.json")
        doc["records"][0]["doi"] = 123
        self.write_json(root, "zenodo-records.json", doc)

        errors = validate_sources.validate(root)
        self.assert_has(errors, "curated Zenodo DOI identifiers must be non-empty strings")

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
            "lineage reference evidence must bind both referencing project and selected publication",
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

        same_owner_versions = [
            pub for pub in pubs["publications"]
            if pub.get("repository_association") == "project:sonification"
            and pub.get("resource_type") != "concept-doi"
            and pub.get("doi")
        ]
        self.assertGreaterEqual(len(same_owner_versions), 2)

        source_record, mutated_record = same_owner_versions[:2]
        mutated_record["concept_doi"] = source_record["doi"]
        self.write_json(root, "publications.json", pubs)

        self.assert_has(
            validate_sources.validate(root),
            "concept DOI must resolve to a curated concept-doi record",
        )

    def test_lineage_reference_must_bind_selected_publication(self):
        root = self.fixture()
        links = self.read_json(root, "project-publication-links.json")
        pubs = self.read_json(root, "publications.json")["publications"]
        lineage = next(link for link in links["links"] if link.get("relation") == "lineage-reference")
        original_publication_id = lineage["publication_id"]
        lineage["publication_id"] = next(
            pub["id"] for pub in pubs if pub["id"] != original_publication_id
        )
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "lineage reference evidence must bind both referencing project and selected publication",
        )

    def test_concept_doi_must_match_exact_zenodo_deposit_mapping(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        concept = next(
            pub for pub in pubs["publications"]
            if pub.get("resource_type") == "concept-doi"
        )
        version = next(
            pub for pub in pubs["publications"]
            if pub.get("repository_association") == concept.get("repository_association")
            and pub.get("resource_type") != "concept-doi"
        )
        version["concept_doi"] = concept["doi"]
        self.write_json(root, "publications.json", pubs)

        self.assert_has(
            validate_sources.validate(root),
            "curated Zenodo concept_doi mismatch",
        )

    def test_repository_identity_uniqueness_is_case_insensitive(self):
        root = self.fixture()
        doc = self.read_json(root, "projects.json")
        first, second = doc["projects"][:2]
        first["repo"] = second["repo"].swapcase()
        self.write_json(root, "projects.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "project repo identifiers must be non-null and unique ignoring case",
        )

    def test_publication_github_source_must_match_associated_repository(self):
        root = self.fixture()
        doc = self.read_json(root, "publications.json")
        target = doc["publications"][0]
        target["source"] = "https://github.com/QSOLKCB/res-rag/blob/main/CITATION.cff"
        self.write_json(root, "publications.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "publication source repository must match associated repository",
        )

    def test_every_publication_requires_nonempty_doi(self):
        root = self.fixture()
        doc = self.read_json(root, "publications.json")
        doc["publications"][0]["doi"] = None
        self.write_json(root, "publications.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "publication DOI must be a non-empty identifier",
        )

    def test_relationship_theme_must_be_supported_by_an_endpoint(self):
        root = self.fixture()
        rels = self.read_json(root, "relationships.json")
        projects = {
            project["id"]: project
            for project in self.read_json(root, "projects.json")["projects"]
        }
        themes = [theme["name"] for theme in self.read_json(root, "themes.json")["themes"]]
        rel = rels["relationships"][0]
        endpoint_themes = (
            set(projects[rel["source"]].get("themes", []))
            | set(projects[rel["target"]].get("themes", []))
        )
        rel["theme"] = next(theme for theme in themes if theme not in endpoint_themes)
        self.write_json(root, "relationships.json", rels)

        self.assert_has(
            validate_sources.validate(root),
            "relationship theme is not supported by either endpoint",
        )

    def test_synthesis_document_source_ids_must_resolve(self):
        root = self.fixture()
        path = root / "projects" / "uff.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("src:uff:readme", text)
        path.write_text(
            text.replace("src:uff:readme", "src:fabricated:readme"),
            encoding="utf-8",
        )

        self.assert_has(
            validate_sources.validate(root),
            "unknown source index reference in synthesis document",
        )

    def test_relationship_evidence_must_match_curated_endpoint_source(self):
        root = self.fixture()
        doc = self.read_json(root, "relationships.json")
        rel = doc["relationships"][0]
        endpoint_repo = validate_sources.github_repository(rel["evidence"][0])
        rel["evidence"] = [
            f"https://github.com/{endpoint_repo}/blob/main/DOES-NOT-EXIST.md"
        ]
        self.write_json(root, "relationships.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "relationship evidence must match a curated endpoint source",
        )

    def test_ownership_evidence_must_identify_selected_publication(self):
        root = self.fixture()
        links = self.read_json(root, "project-publication-links.json")
        pubs = {
            pub["id"]: pub
            for pub in self.read_json(root, "publications.json")["publications"]
        }
        link = next(
            link for link in links["links"]
            if link.get("relation") == "repository-associated-publication"
            and validate_sources.github_repository(pubs[link["publication_id"]].get("source"))
        )
        pub = pubs[link["publication_id"]]
        repo = validate_sources.github_repository(pub["source"])
        link["evidence"] = [f"https://github.com/{repo}/blob/main/DOES-NOT-EXIST.md"]
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "publication link evidence is not traceable to the linked project/publication",
        )

    def test_concept_record_must_retain_self_identity(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        zenodo = self.read_json(root, "zenodo-records.json")
        concept = next(
            pub for pub in pubs["publications"]
            if pub.get("resource_type") == "concept-doi"
        )
        concept["concept_doi"] = None
        zenodo_row = next(
            row for row in zenodo["records"]
            if row.get("doi", "").casefold() == concept["doi"].casefold()
        )
        zenodo_row["concept_doi"] = None
        self.write_json(root, "publications.json", pubs)
        self.write_json(root, "zenodo-records.json", zenodo)

        self.assert_has(
            validate_sources.validate(root),
            "concept-doi publication must self-identify with concept_doi equal to doi",
        )

    def test_null_project_id_reports_error_without_crashing(self):
        root = self.fixture()
        projects = self.read_json(root, "projects.json")
        projects["projects"][0]["id"] = None
        self.write_json(root, "projects.json", projects)

        errors = validate_sources.validate(root)
        self.assert_has(errors, "project IDs must be non-empty strings in the project: namespace")

    def test_substantive_paper_section_requires_source_reference(self):
        root = self.fixture()
        path = root / "paper" / "03-project-families.md"
        text = path.read_text(encoding="utf-8")
        text = validate_sources.SOURCE_ID_RE.sub("source-removed", text)
        path.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "substantive paper section requires source index references",
        )

    def test_version_concept_doi_requires_independent_ownership_binding(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        zenodo = self.read_json(root, "zenodo-records.json")
        concept = next(
            pub for pub in pubs["publications"]
            if pub.get("resource_type") == "concept-doi"
        )
        version = next(
            pub for pub in pubs["publications"]
            if pub.get("repository_association") == concept.get("repository_association")
            and pub.get("resource_type") != "concept-doi"
        )
        version["concept_doi"] = concept["doi"]
        zenodo_row = next(
            row for row in zenodo["records"]
            if row.get("doi", "").casefold() == version["doi"].casefold()
        )
        zenodo_row["concept_doi"] = concept["doi"]
        self.write_json(root, "publications.json", pubs)
        self.write_json(root, "zenodo-records.json", zenodo)

        self.assert_has(
            validate_sources.validate(root),
            "publication concept DOI disagrees with curated ownership binding",
        )

    def test_non_string_concept_doi_reports_error_without_crashing(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        pubs["publications"][0]["concept_doi"] = 123
        self.write_json(root, "publications.json", pubs)

        errors = validate_sources.validate(root)
        self.assert_has(errors, "invalid concept DOI syntax")

    def test_every_curated_project_requires_a_summary_document(self):
        root = self.fixture()
        (root / "projects" / "uff.md").unlink()

        self.assert_has(
            validate_sources.validate(root),
            "project summaries must cover projects.json exactly",
        )

    def test_publication_id_requires_publication_namespace(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        links = self.read_json(root, "project-publication-links.json")
        publication = pubs["publications"][0]
        old_id = publication["id"]
        new_id = old_id.removeprefix("publication:")
        publication["id"] = new_id
        for link in links["links"]:
            if link.get("publication_id") == old_id:
                link["publication_id"] = new_id
        self.write_json(root, "publications.json", pubs)
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "publication IDs must be non-empty strings in the publication: namespace",
        )

    def test_project_summary_source_must_match_its_repository(self):
        root = self.fixture()
        uff = root / "projects" / "uff.md"
        galaxy = root / "projects" / "galaxy.md"
        uff_text = uff.read_text(encoding="utf-8")
        galaxy_text = galaxy.read_text(encoding="utf-8")
        marker = "src:temporary:swap"
        uff_text = uff_text.replace("src:uff:readme", marker)
        galaxy_text = galaxy_text.replace("src:galaxy:readme", "src:uff:readme")
        uff_text = uff_text.replace(marker, "src:galaxy:readme")
        uff.write_text(uff_text, encoding="utf-8")
        galaxy.write_text(galaxy_text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "project summary source does not match its repository",
        )

    def test_atomic_theme_members_must_have_matching_source_support(self):
        root = self.fixture()
        path = root / "themes" / "visualisation.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("src:res-rag-viz:readme", "src:uff:readme")
        path.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "atomic theme membership must match source support",
        )

    def test_project_source_path_must_match_curated_github_registry(self):
        root = self.fixture()
        projects = self.read_json(root, "projects.json")
        project = next(p for p in projects["projects"] if p.get("id") == "project:qsol-ark")
        project["source"] = "https://github.com/QSOLKCB/QSOL-ARK/blob/main/DOES-NOT-EXIST.md"
        self.write_json(root, "projects.json", projects)

        self.assert_has(
            validate_sources.validate(root),
            "project source must match independently curated GitHub source",
        )

    def test_ownership_reassignment_requires_repository_bound_evidence(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        zenodo = self.read_json(root, "zenodo-records.json")
        links = self.read_json(root, "project-publication-links.json")

        pub = next(p for p in pubs["publications"] if p["id"] == "publication:zenodo-22026554")
        pub["repository_association"] = "project:galaxy"
        pub["source"] = "https://doi.org/10.5281/zenodo.22026554"

        row = next(r for r in zenodo["records"] if r["doi"] == "10.5281/zenodo.22026554")
        row["repository_association"] = "project:galaxy"
        row["evidence"] = "https://doi.org/10.5281/zenodo.22026554"

        link = next(
            link for link in links["links"]
            if link.get("publication_id") == pub["id"]
            and link.get("relation") == "repository-associated-publication"
        )
        link["project_id"] = "project:galaxy"
        link["evidence"] = ["https://doi.org/10.5281/zenodo.22026554"]

        self.write_json(root, "publications.json", pubs)
        self.write_json(root, "zenodo-records.json", zenodo)
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "curated GitHub publication ownership mismatch",
        )

    def test_project_summary_must_match_canonical_filename(self):
        root = self.fixture()
        uff = root / "projects" / "uff.md"
        galaxy = root / "projects" / "galaxy.md"
        uff_text = uff.read_text(encoding="utf-8")
        galaxy_text = galaxy.read_text(encoding="utf-8")
        uff.write_text(galaxy_text, encoding="utf-8")
        galaxy.write_text(uff_text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "project summary path does not match curated summary_path",
        )

    def test_zenodo_publication_id_must_match_doi_record(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        links = self.read_json(root, "project-publication-links.json")
        pub = next(p for p in pubs["publications"] if p["id"] == "publication:zenodo-22026554")
        old_id = pub["id"]
        pub["id"] = "publication:zenodo-99999999"
        for link in links["links"]:
            if link.get("publication_id") == old_id:
                link["publication_id"] = pub["id"]
        self.write_json(root, "publications.json", pubs)
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "Zenodo publication ID must match declared DOI record",
        )

    def test_relationship_graph_must_match_registry(self):
        root = self.fixture()
        graph = root / "figures" / "theme-network.dot"
        text = graph.read_text(encoding="utf-8")
        text = text.replace(
            '"project:qsolqec" -> "project:qsol-qec-bridge"',
            '"project:qsolqec" -> "project:uff"',
            1,
        )
        graph.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "relationship graph must match data/relationships.json exactly",
        )

    def test_future_curated_snapshot_dates_are_rejected(self):
        root = self.fixture()
        for name in CURATED_JSON:
            doc = self.read_json(root, name)
            doc["generated_at"] = "2999-01-01"
            if name == "source-index.json":
                for source in doc.get("sources", []):
                    source["access_date"] = "2999-01-01"
            self.write_json(root, name, doc)

        errors = validate_sources.validate(root)
        self.assert_has(errors, "generated_at must not be in the future")
        self.assert_has(errors, "source access_date must not be in the future")

    def test_curated_publication_dois_reject_case_only_duplicates(self):
        root = self.fixture()
        doc = self.read_json(root, "github-repositories.json")
        row = next(
            row for row in doc["repositories"]
            if row.get("full_name") == "QSOLKCB/UFF"
        )
        row["publication_dois"].append("10.5281/ZENODO.22026554")
        self.write_json(root, "github-repositories.json", doc)

        self.assert_has(
            validate_sources.validate(root),
            "curated GitHub publication_dois must be a unique string list",
        )

    def test_publication_github_source_must_match_independent_manifest(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        zenodo = self.read_json(root, "zenodo-records.json")
        links = self.read_json(root, "project-publication-links.json")

        pub = next(p for p in pubs["publications"] if p["id"] == "publication:zenodo-22026554")
        fabricated = "https://github.com/QSOLKCB/UFF/blob/main/DOES-NOT-EXIST.md"
        pub["source"] = fabricated

        row = next(r for r in zenodo["records"] if r.get("doi") == pub["doi"])
        row["evidence"] = fabricated

        link = next(
            link for link in links["links"]
            if link.get("relation") == "repository-associated-publication"
            and link.get("publication_id") == pub["id"]
        )
        link["evidence"] = [fabricated]

        self.write_json(root, "publications.json", pubs)
        self.write_json(root, "zenodo-records.json", zenodo)
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "publication GitHub source must match independently curated source",
        )

    def test_declared_historical_lineage_requires_lineage_link(self):
        root = self.fixture()
        links = self.read_json(root, "project-publication-links.json")
        links["links"] = [
            link for link in links["links"]
            if link.get("relation") != "lineage-reference"
        ]
        self.write_json(root, "project-publication-links.json", links)

        self.assert_has(
            validate_sources.validate(root),
            "lineage-reference links must exactly match historical-lineage declarations",
        )

    def test_historical_lineage_publication_must_belong_to_origin(self):
        root = self.fixture()
        rels = self.read_json(root, "relationships.json")
        rel = next(
            rel for rel in rels["relationships"]
            if rel.get("relation_type") == "historical-lineage"
        )
        old_source = rel["source"]
        rel["source"] = "project:qsolqec"
        self.write_json(root, "relationships.json", rels)

        graph = root / "figures" / "theme-network.dot"
        text = graph.read_text(encoding="utf-8")
        text = text.replace(
            f'"{old_source}" -> "{rel["target"]}"',
            f'"{rel["source"]}" -> "{rel["target"]}"',
            1,
        )
        graph.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "historical-lineage publication must belong to the origin project",
        )

    def test_shared_relationship_requires_evidence_from_both_endpoints(self):
        root = self.fixture()
        rels = self.read_json(root, "relationships.json")
        rel = next(
            rel for rel in rels["relationships"]
            if rel.get("relation_type") == "shared-validation-architecture"
        )
        old_target = rel["target"]
        rel["target"] = "project:spectral"
        rel["evidence"] = [
            "https://github.com/QSOLKCB/GALAXY/blob/main/README.md"
        ]
        self.write_json(root, "relationships.json", rels)

        graph = root / "figures" / "theme-network.dot"
        text = graph.read_text(encoding="utf-8")
        text = text.replace(
            f'"{rel["source"]}" -> "{old_target}"',
            f'"{rel["source"]}" -> "{rel["target"]}"',
            1,
        )
        graph.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "bilateral relationship evidence must cover both endpoints",
        )

    def test_project_summary_publications_must_match_curated_links(self):
        root = self.fixture()
        path = root / "projects" / "uff.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "10.5281/zenodo.22026554",
            "10.5281/zenodo.99999999",
            1,
        )
        path.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "project summary publications must match curated links",
        )

    def test_matrix_rejects_overwide_rows(self):
        root = self.fixture()
        matrix = root / "evidence" / "project-theme-matrix.csv"
        lines = matrix.read_text(encoding="utf-8").splitlines()
        lines[1] = lines[1] + ",documented"
        matrix.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "matrix rows must match the declared header width exactly",
        )

    def test_nonhashable_generated_at_reports_error_without_crashing(self):
        root = self.fixture()
        doc = self.read_json(root, "projects.json")
        doc["generated_at"] = []
        self.write_json(root, "projects.json", doc)

        errors = validate_sources.validate(root)
        self.assert_has(errors, "projects.json generated_at must use a real YYYY-MM-DD date")
        self.assert_has(errors, "curated generated_at values must agree")

    def test_publication_metadata_title_must_be_string(self):
        root = self.fixture()
        pubs = self.read_json(root, "publications.json")
        zenodo = self.read_json(root, "zenodo-records.json")
        pub = pubs["publications"][0]
        pub["title"] = 123
        row = next(
            row for row in zenodo["records"]
            if isinstance(row.get("doi"), str)
            and row["doi"].casefold() == pub["doi"].casefold()
        )
        row["title"] = 123
        self.write_json(root, "publications.json", pubs)
        self.write_json(root, "zenodo-records.json", zenodo)

        self.assert_has(
            validate_sources.validate(root),
            "publication title must be a non-empty string",
        )

    def test_theme_name_must_remain_atomic_slug(self):
        root = self.fixture()
        themes = self.read_json(root, "themes.json")
        theme = next(t for t in themes["themes"] if t["name"] == "visualisation")
        theme["name"] = "../projects/res-rag-viz"
        theme["id"] = "theme:../projects/res-rag-viz"
        self.write_json(root, "themes.json", themes)

        self.assert_has(
            validate_sources.validate(root),
            "theme names must use the atomic theme slug namespace",
        )

    def test_bilateral_relationship_theme_requires_both_endpoint_support(self):
        root = self.fixture()
        projects = self.read_json(root, "projects.json")
        uff = next(p for p in projects["projects"] if p["id"] == "project:uff")
        uff["themes"] = [theme for theme in uff["themes"] if theme != "provenance"]
        self.write_json(root, "projects.json", projects)

        self.assert_has(
            validate_sources.validate(root),
            "bilateral relationship theme must be supported by both endpoints",
        )

    def test_project_summary_first_party_link_must_match_curated_source(self):
        root = self.fixture()
        path = root / "projects" / "uff.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "https://github.com/QSOLKCB/UFF/blob/main/README.md",
            "https://github.com/QSOLKCB/GALAXY/blob/main/README.md",
            1,
        )
        path.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "project summary first-party source link must match curated source",
        )

    def test_project_summary_relationships_must_match_registry(self):
        root = self.fixture()
        path = root / "projects" / "uff.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "project:galaxy",
            "project:qsolqec",
            1,
        )
        path.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "project summary relationships must match curated registry",
        )

    def test_project_summary_publication_relation_type_must_match_registry(self):
        root = self.fixture()
        path = root / "projects" / "uff.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "**repository-associated-publication** — 10.5281/zenodo.22026554",
            "**lineage-reference** — 10.5281/zenodo.22026554",
            1,
        )
        path.write_text(text, encoding="utf-8")

        self.assert_has(
            validate_sources.validate(root),
            "project summary publications must match curated links and relation types",
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
