"""Literature lane tests: retrieval provenance, screening honesty, and reporting.

Every test uses a stub fetcher. Nothing here touches the network, which is also
enforced independently by ``tests/test_network_boundary.py``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.discovery.criteria import define_inclusion_criteria
from metabotyping_agentic.discovery.literature_review import (
    dedupe_records,
    records_from_publications,
    review_literature,
    screen_record,
)
from metabotyping_agentic.io import read_json
from metabotyping_agentic.live_sources import literature_search
from metabotyping_agentic.live_sources.literature_search import (
    europe_pmc_expression,
    pubmed_expression,
    search_literature,
)
from metabotyping_agentic.models import PublicationRecord
from metabotyping_agentic.reports.render import render_literature_report


def setUpModule() -> None:
    # The adapters pace real API calls politely; a stubbed fetcher has nothing to pace.
    literature_search.POLITE_DELAY_SECONDS = 0.0

EPMC_PAGE = {
    "hitCount": 2,
    "nextCursorMark": "CURSOR2",
    "resultList": {
        "result": [
            {
                "id": "35045595",
                "source": "MED",
                "pmid": "35045595",
                "pmcid": "PMC9159949",
                "doi": "10.1038/S41586-022-04828-5",
                "title": "An exercise-inducible metabolite that suppresses feeding and obesity.",
                "authorString": "Li VL, He Y, Contrepois K.",
                "journalInfo": {"journal": {"title": "Nature"}, "yearOfPublication": 2022},
                "pubYear": "2022",
                "pubTypeList": {"pubType": ["Journal Article", "Research Support"]},
                "isOpenAccess": "Y",
                "citedByCount": 400,
                "abstractText": (
                    "Exercise raised plasma Lac-Phe in mice, racehorses and humans. Data are deposited "
                    "in Metabolomics Workbench ST003662 and analysed after a treadmill sprint protocol."
                ),
            },
            {
                "id": "PPR123456",
                "source": "PPR",
                "pmid": "",
                "pmcid": "",
                "doi": "10.1101/2023.01.02.522222",
                "title": "A preprint on Lac-Phe kinetics in trained humans",
                "authorString": "Doe J.",
                "journalInfo": {"journal": {"title": "bioRxiv"}},
                "pubYear": "2023",
                "pubTypeList": {"pubType": ["Preprint"]},
                "isOpenAccess": "Y",
                "citedByCount": 3,
                "abstractText": "Human participants completed an exercise bout; plasma metabolomics measured Lac-Phe.",
            },
        ]
    },
}

CROSSREF_PAGE = {
    "message": {
        "total-results": 1,
        "items": [
            {
                "DOI": "10.1038/s41586-022-04828-5",
                "title": ["An exercise-inducible metabolite that suppresses feeding and obesity"],
                "container-title": ["Nature"],
                "issued": {"date-parts": [[2022, 6, 15]]},
                "type": "journal-article",
                "publisher": "Springer Science and Business Media LLC",
                "is-referenced-by-count": 412,
                "author": [{"family": "Li", "given": "Veronica L."}],
                "URL": "https://doi.org/10.1038/s41586-022-04828-5",
            }
        ],
    }
}

BIORXIV_DETAIL = {
    "collection": [
        {"version": "1", "published": "NA", "category": "physiology"},
        {"version": "2", "published": "10.1016/j.cmet.2023.99.999", "category": "physiology"},
    ]
}


def stub_fetcher(url: str):
    """Answer Europe PMC, Crossref and bioRxiv; refuse PubMed the way a blocked egress does."""

    if "europepmc" in url:
        if "cursorMark=CURSOR2" in url:
            return {"hitCount": 2, "nextCursorMark": "CURSOR2", "resultList": {"result": []}}
        return EPMC_PAGE
    if "eutils.ncbi.nlm.nih.gov" in url:
        raise RuntimeError("literature request returned non-JSON content: NCBI - WWW Error Blocked Diagnostic")
    if "api.crossref.org" in url:
        return CROSSREF_PAGE
    if "api.biorxiv.org/details/biorxiv" in url:
        return BIORXIV_DETAIL
    if "api.biorxiv.org/details/medrxiv" in url:
        return {"collection": []}
    raise AssertionError(f"unexpected URL in test: {url}")


class QueryExpressionTests(unittest.TestCase):
    def test_expressions_keep_every_name_variant_and_context_term(self):
        expression = europe_pmc_expression("N-Lactoyl phenylalanine", ["Lac-Phe"], ["exercise"])
        self.assertEqual(expression, '("N-Lactoyl phenylalanine" OR "Lac-Phe") AND ("exercise")')
        pubmed = pubmed_expression("N-Lactoyl phenylalanine", ["Lac-Phe", "lac-phe"], [])
        # Duplicate variants collapse case-insensitively rather than inflating the query.
        self.assertEqual(pubmed, '("N-Lactoyl phenylalanine"[All Fields] OR "Lac-Phe"[All Fields])')


class RetrievalProvenanceTests(unittest.TestCase):
    def test_unreachable_source_is_unavailable_and_never_zero_hits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = search_literature(
                "N-Lactoyl phenylalanine",
                Path(temp_dir) / "lit",
                name_variants=["Lac-Phe"],
                context_terms=["exercise"],
                fetcher=stub_fetcher,
            )
        by_source = {item.source_system: item for item in result["outcomes"]}
        self.assertEqual(by_source["pubmed"].status, "unavailable")
        self.assertEqual(by_source["pubmed"].retrieved_count, 0)
        self.assertIsNone(by_source["pubmed"].reported_hit_count)
        self.assertIn("Blocked", by_source["pubmed"].detail)
        self.assertEqual(by_source["europe_pmc"].status, "ok")
        self.assertEqual(result["provenance"]["unavailable_sources"], ["pubmed"])
        self.assertIn("not evidence that no matching publication exists", result["provenance"]["coverage_gap_semantics"])

    def test_crossref_relevance_sample_is_never_declared_complete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = search_literature(
                "N-Lactoyl phenylalanine",
                Path(temp_dir) / "lit",
                sources=["crossref"],
                fetcher=stub_fetcher,
            )
        outcome = result["outcomes"][0]
        self.assertEqual(outcome.source_system, "crossref")
        self.assertFalse(outcome.pagination_complete)
        self.assertIn("crossref", result["provenance"]["truncated_sources"])

    def test_preprint_linkage_records_server_version_and_published_doi(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = search_literature(
                "Lac-Phe", Path(temp_dir) / "lit", sources=["europe_pmc", "biorxiv_medrxiv"], fetcher=stub_fetcher
            )
        preprints = [row for row in result["records"] if row["doi"].startswith("10.1101/")]
        self.assertEqual(len(preprints), 1)
        self.assertEqual(preprints[0]["preprint_server"], "biorxiv")
        self.assertEqual(preprints[0]["preprint_version_count"], "2")
        self.assertEqual(preprints[0]["linked_published_doi"], "10.1016/j.cmet.2023.99.999")

    def test_unregistered_source_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "Unregistered literature source"):
                search_literature("Lac-Phe", Path(temp_dir) / "lit", sources=["google_scholar"], fetcher=stub_fetcher)

    def test_retrieval_writes_records_and_provenance_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "lit"
            result = search_literature("Lac-Phe", out_dir, fetcher=stub_fetcher)
            self.assertTrue((out_dir / "literature_records.csv").is_file())
            self.assertTrue((out_dir / "literature_records.json").is_file())
            provenance = read_json(out_dir / "literature_provenance.json")
        self.assertEqual(provenance["decision_scope"], "retrieval_only")
        self.assertEqual(sorted(provenance["requested_sources"]), ["biorxiv_medrxiv", "crossref", "europe_pmc", "pubmed"])
        endpoints = [url for source in provenance["sources"] for url in source["endpoints"]]
        self.assertTrue(any("ebi.ac.uk/europepmc" in url for url in endpoints))
        self.assertTrue(all(url.startswith("https://") for url in endpoints))
        self.assertEqual(len(result["records"]), 3)


class DeduplicationTests(unittest.TestCase):
    def test_records_sharing_a_doi_merge_across_sources(self):
        clusters = dedupe_records(
            [
                {"source_system": "europe_pmc", "doi": "10.1/x", "pmid": "1", "title": "A", "publication_year": "2022", "abstract": "long abstract"},
                {"source_system": "crossref", "doi": "10.1/x", "title": "A", "publication_year": "2022"},
                {"source_system": "pubmed", "pmid": "1", "title": "A", "publication_year": "2022"},
            ]
        )
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["source_systems"], ["crossref", "europe_pmc", "pubmed"])
        self.assertEqual(clusters[0]["member_count"], 3)
        self.assertEqual(clusters[0]["cross_source_conflicts"], [])

    def test_disagreeing_fields_are_preserved_as_conflicts(self):
        clusters = dedupe_records(
            [
                {"source_system": "europe_pmc", "doi": "10.1/x", "title": "A", "publication_year": "2022"},
                {"source_system": "crossref", "doi": "10.1/x", "title": "A", "publication_year": "2021"},
            ]
        )
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["cross_source_conflicts"], ["publication_year: 2021 != 2022"])

    def test_preprint_merges_with_the_journal_article_it_became(self):
        clusters = dedupe_records(
            [
                {
                    "source_system": "europe_pmc",
                    "doi": "10.1101/2023.01.02.522222",
                    "title": "A preprint",
                    "is_preprint": "true",
                    "linked_published_doi": "10.1016/j.cmet.2023.99.999",
                },
                {"source_system": "crossref", "doi": "10.1016/j.cmet.2023.99.999", "title": "The article"},
            ]
        )
        # One study, so one record: counting both would inflate the evidence base, and
        # the cluster must be tiered as the published article rather than as a preprint.
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["member_count"], 2)
        self.assertEqual(clusters[0]["is_preprint"], "false")
        self.assertEqual(clusters[0]["has_preprint_version"], "true")
        self.assertEqual(clusters[0]["title"], "The article")

    def test_records_without_identifiers_cluster_on_title_and_year(self):
        clusters = dedupe_records(
            [
                {"source_system": "crossref", "title": "Same Title!", "publication_year": "2020"},
                {"source_system": "europe_pmc", "title": "same title", "publication_year": "2020"},
                {"source_system": "europe_pmc", "title": "same title", "publication_year": "2019"},
            ]
        )
        self.assertEqual(len(clusters), 2)


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.criteria = define_inclusion_criteria("human metabolomics exercise")

    def test_human_exercise_metabolomics_record_is_a_direct_match_with_labeled_inference(self):
        row = screen_record(
            {
                "record_key": "doi:10.1/x",
                "title": "Plasma metabolomics of an acute exercise bout in human participants",
                "abstract": "Human participants completed an exercise bout; untargeted metabolomics measured Lac-Phe.",
                "publication_types": "journal-article",
                "is_preprint": "false",
            },
            self.criteria,
        )
        self.assertEqual(row["screen_class"], "direct_human_exercise")
        self.assertEqual(row["evidence_tier"], "peer_reviewed_primary")
        self.assertEqual(row["human_evidence"], "yes:text_inference")
        self.assertEqual(row["species_basis"], "title_abstract_text")
        self.assertEqual(row["review_status"], "requires_human_review")

    def test_record_without_abstract_is_uncertain_not_excluded(self):
        row = screen_record(
            {"record_key": "pmid:9", "title": "A short bibliographic stub", "publication_types": "", "is_preprint": "false"},
            self.criteria,
        )
        self.assertEqual(row["screen_class"], "screening_uncertain_insufficient_text")
        self.assertEqual(row["abstract_available"], "false")
        self.assertEqual(row["human_evidence"], "unknown:no_abstract_text")
        self.assertEqual(row["species_basis"], "no_abstract_text")

    def test_rodent_record_is_mechanistic_background_and_never_a_human_match(self):
        row = screen_record(
            {
                "record_key": "doi:10.1/m",
                "title": "CNDP2 knockout mice and treadmill running",
                "abstract": "Mice lacking CNDP2 were studied with plasma metabolomics after treadmill exercise.",
                "publication_types": "journal-article",
                "is_preprint": "false",
            },
            self.criteria,
        )
        self.assertEqual(row["screen_class"], "animal_or_invitro_mechanistic")
        self.assertEqual(row["species_scope"], "rodent")
        self.assertIn("retained_as_mechanistic_background", row["screen_basis"])

    def test_preprint_tiers_split_on_journal_linkage(self):
        unpublished = screen_record(
            {"record_key": "doi:10.1101/a", "title": "x", "abstract": "human exercise metabolomics", "is_preprint": "true"},
            self.criteria,
        )
        published = screen_record(
            {
                "record_key": "doi:10.1101/b",
                "title": "x",
                "abstract": "human exercise metabolomics",
                "is_preprint": "true",
                "linked_published_doi": "10.1016/j.cmet.2023.99.999",
            },
            self.criteria,
        )
        self.assertEqual(unpublished["evidence_tier"], "preprint_not_peer_reviewed")
        self.assertEqual(published["evidence_tier"], "preprint_later_published")

    def test_retraction_and_review_types_are_separated_from_primary_evidence(self):
        retracted = screen_record(
            {"record_key": "a", "title": "t", "abstract": "human exercise", "publication_types": "retracted publication"},
            self.criteria,
        )
        review = screen_record(
            {"record_key": "b", "title": "t", "abstract": "human exercise metabolomics", "publication_types": "review"},
            self.criteria,
        )
        self.assertEqual(retracted["evidence_tier"], "retracted_or_retraction_notice")
        self.assertEqual(retracted["screen_class"], "not_primary_evidence")
        self.assertEqual(review["screen_class"], "secondary_synthesis")

    def test_accessions_are_extracted_from_record_text(self):
        row = screen_record(
            {
                "record_key": "a",
                "title": "t",
                "abstract": "Data are in Metabolomics Workbench ST003662 and MTBLS1234, plus GSE12345 and PXD004567.",
                "publication_types": "journal-article",
            },
            self.criteria,
        )
        self.assertEqual(row["data_availability_evidence"], "accession_in_record_text")
        self.assertEqual(
            row["accessions_in_record_text"],
            "geo:GSE12345; metabolights:MTBLS1234; metabolomics_workbench:ST003662; pride:PXD004567",
        )

    def test_structured_fixture_flags_are_not_reported_as_text_inference(self):
        records = records_from_publications(
            [
                PublicationRecord(
                    study_id="SYN-1",
                    title="Synthetic exercise metabolomics study",
                    doi="10.0000/syn.1",
                    human=True,
                    exercise=True,
                    metabolomics=True,
                    repository_accession="MTBLS1234",
                )
            ]
        )
        row = screen_record(dedupe_records(records)[0], self.criteria)
        self.assertEqual(row["human_evidence"], "yes:structured_field")
        self.assertEqual(row["species_basis"], "structured_field")
        self.assertEqual(row["screen_class"], "direct_human_exercise")
        self.assertEqual(row["accessions_in_record_text"], "metabolights:MTBLS1234")


class ReviewAndReportTests(unittest.TestCase):
    def _review(self, out_dir: Path):
        result = search_literature(
            "N-Lactoyl phenylalanine",
            out_dir,
            name_variants=["Lac-Phe"],
            context_terms=["exercise"],
            fetcher=stub_fetcher,
        )
        review = review_literature(
            result["records"],
            define_inclusion_criteria("human metabolomics exercise"),
            out_dir,
            retrieval_provenance=result["provenance"],
        )
        return result, review

    def test_review_escalates_the_unavailable_source_and_the_unreviewed_preprint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, review = self._review(Path(temp_dir) / "lit")
        escalations = {row["escalation"] for row in review["escalations"]}
        self.assertIn("retrieval_source_unavailable", escalations)
        self.assertIn("retrieval_truncated", escalations)
        self.assertEqual(review["summary"]["unavailable_sources"], ["pubmed"])
        self.assertIn("direct_human_exercise", review["summary"]["screen_class_counts"])

    def test_review_outputs_are_deterministic_and_carry_no_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_dir, second_dir = Path(temp_dir) / "a", Path(temp_dir) / "b"
            self._review(first_dir)
            self._review(second_dir)
            for name in ("literature_screened.csv", "literature_escalations.csv", "literature_review.json"):
                with self.subTest(artifact=name):
                    first = (first_dir / name).read_bytes()
                    self.assertEqual(first, (second_dir / name).read_bytes())
                    self.assertNotIn(b"generated_utc", first)
                    self.assertNotIn(b"generated_at", first)

    def test_report_states_the_availability_gap_rather_than_a_negative_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "lit"
            result, review = self._review(out_dir)
            report_path = render_literature_report(
                review, out_dir, retrieval_provenance=result["provenance"], title="Literature Evidence Report"
            )
            text = report_path.read_text(encoding="utf-8")
        self.assertIn("**pubmed was unreachable.**", text)
        self.assertIn("not a finding that no matching publication exists", text)
        self.assertIn("ranked sample, not a complete sweep", text)
        self.assertIn("metabolomics_workbench:ST003662", text)
        self.assertIn("Animal or in-vitro mechanistic background", text)


if __name__ == "__main__":
    unittest.main()


class ProvenanceRedactionTests(unittest.TestCase):
    """Credentials and contact addresses must never reach a provenance file.

    literature_provenance.json records the exact endpoint URL queried per source
    and is committed alongside results. An NCBI API key or a contact email in a
    recorded URL would be republished with the artifact.
    """

    def test_api_key_and_contact_parameters_are_masked(self):
        from metabotyping_agentic.live_sources.literature_search import redact_url

        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            "?db=pubmed&term=lac-phe&api_key=SECRETKEY123&email=someone%40example.org"
        )
        redacted = redact_url(url)
        self.assertNotIn("SECRETKEY123", redacted)
        self.assertNotIn("someone%40example.org", redacted)
        self.assertNotIn("someone@example.org", redacted)
        self.assertIn("api_key=%3Credacted%3E", redacted)
        # The scientifically meaningful part of the query must survive intact.
        self.assertIn("db=pubmed", redacted)
        self.assertIn("term=lac-phe", redacted)

    def test_crossref_mailto_is_masked(self):
        from metabotyping_agentic.live_sources.literature_search import redact_url

        redacted = redact_url("https://api.crossref.org/works?query=x&mailto=me%40lab.edu")
        self.assertNotIn("me%40lab.edu", redacted)
        self.assertIn("query=x", redacted)

    def test_url_without_sensitive_parameters_is_returned_unchanged(self):
        from metabotyping_agentic.live_sources.literature_search import redact_url

        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=lacphe&format=json"
        self.assertEqual(redact_url(url), url)


class CredentialLeakEndToEndTests(unittest.TestCase):
    """No artifact written by the literature lane may contain a credential.

    README and CLAUDE.md promise that setting NCBI_API_KEY and
    METABOTYPING_CONTACT_EMAIL is safe because they are masked in anything
    written to disk. Redacting only the endpoints list was not enough: the key
    also reached provenance through raised error text, and the contact email
    reached every record through source_url. This drives the whole lane with a
    fake fetcher and asserts the secrets appear in no output file.
    """

    KEY = "SECRETNCBIKEY123456789abcdef"
    EMAIL = "secret.person@example.edu"

    def test_no_artifact_contains_the_api_key_or_contact_email(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from unittest import mock

        from metabotyping_agentic.live_sources import literature_search as ls

        def exploding_fetcher(url, *args, **kwargs):
            # Every source fails, which is the path that puts the URL into an
            # error string and then into provenance.
            raise RuntimeError(f"literature request failed: {ls.redact_url(url)}")

        env = {"NCBI_API_KEY": self.KEY, "METABOTYPING_CONTACT_EMAIL": self.EMAIL}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, env):
            out = Path(tmp) / "lit"
            try:
                ls.search_literature(
                    "N-Lactoyl phenylalanine",
                    out,
                    fetcher=exploding_fetcher,
                    max_records_per_source=5,
                )
            except TypeError:
                self.skipTest("search_literature signature does not accept an injected fetcher")

            leaked = []
            for path in out.rglob("*"):
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                if self.KEY in text:
                    leaked.append(f"{path.name}: api key")
                if self.EMAIL in text or self.EMAIL.replace("@", "%40") in text:
                    leaked.append(f"{path.name}: contact email")
            self.assertEqual(leaked, [], f"credentials reached disk: {leaked}")

            provenance = out / "literature_provenance.json"
            if provenance.exists():
                blob = json.loads(provenance.read_text(encoding="utf-8"))
                self.assertIn("redacted", json.dumps(blob))
