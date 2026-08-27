"""Offline tests for the MetGENE gene-centric annotation lane.

Every fixture below is a wire shape the live service was observed to return. The
point of the suite is that the five ways MetGENE can answer "nothing" stay five
distinct recorded states, and that no row ever asserts a measurement.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.discovery.gene_metabolite_evidence import (
    build_gene_metabolite_evidence,
    build_inference_ledger,
)
from metabotyping_agentic.io import read_csv_rows
from metabotyping_agentic.live_sources import metgene

SUMMARY_BODY = '[{"Pathways":4,"Reactions":1,"Metabolites":5,"Studies":273,"Genes":"HMGCR","_row":"HMGCR"}]'

METABOLITES_BODY = json.dumps(
    [
        [
            {
                "Gene": "3156",
                "KEGG_COMPOUND_ID": "C00005",
                "REFMET_NAME": "NADPH",
                "KEGG_REACTION_ID": "R02082",
                "METSTAT_LINK": "http://www.metabolomicsworkbench.org/data/metstat_hist.php?refmet_name=NADPH",
            },
            {
                "Gene": "3156",
                "KEGG_COMPOUND_ID": "C00080",
                "REFMET_NAME": "",
                "KEGG_REACTION_ID": "R02082",
                "METSTAT_LINK": "http://www.metabolomicsworkbench.org/data/metstat_hist.php?refmet_name=",
            },
        ]
    ]
)

REACTIONS_BODY = json.dumps(
    [
        [
            {
                "Gene": "3156",
                "KEGG_REACTION_ID": ["R02082"],
                "KEGG_REACTION_NAME": ["(R)-mevalonate:NADP+ oxidoreductase (CoA acylating)"],
                "KEGG_REACTION_EQN": ["(R)-Mevalonate + CoA + 2 NADP+ <=> ..."],
                "_row": "R02082",
            }
        ]
    ]
)

STUDIES_BODY = json.dumps(
    [
        {
            "KEGG_COMPOUND_ID": '<a href="https://www.genome.jp/entry/cpd:C00005">C00005</a>',
            "REFMET_NAME": "NADPH",
            "STUDY_ID": "ST000076 ST000202 ST000276",
        }
    ]
)

NO_SUMMARY_HTML = (
    "<h3>No summaries found for genes: PPARGC1A</h3><p> No summaries found in Metabolomics "
    "Workbench for the specified genes.</p>"
)


def _fetcher(bodies: dict[str, metgene.RawResponse]):
    def fetch(url: str) -> metgene.RawResponse:
        for context in metgene.METGENE_CONTEXTS:
            if f"/rest/{context}/" in url:
                response = bodies[context]
                return metgene.RawResponse(
                    url,
                    response.http_status,
                    response.content_type,
                    response.body,
                    response.transport_error,
                )
        raise AssertionError(f"unexpected url: {url}")

    return fetch


def _no_delay() -> None:
    """Tests opt out of the polite inter-request delay explicitly."""


def _ok(body: str) -> metgene.RawResponse:
    return metgene.RawResponse("", 200, "application/json; charset=UTF-8", body)


HAPPY_PATH = {
    "summary": _ok(SUMMARY_BODY),
    "metabolites": _ok(METABOLITES_BODY),
    "reactions": _ok(REACTIONS_BODY),
    "studies": _ok(STUDIES_BODY),
}


class MetGeneUrlTests(unittest.TestCase):
    def test_all_nine_slots_are_present_and_unused_filters_are_literal_na(self):
        url = metgene.metgene_url("metabolites", "hsa", "SYMBOL", "HMGCR")
        self.assertEqual(
            url,
            "https://bdcw.org/MetGENE/rest/metabolites/species/hsa/GeneIDType/SYMBOL"
            "/GeneInfoStr/HMGCR/anatomy/NA/disease/NA/phenotype/NA/viewType/json",
        )

    def test_spaces_become_plus_and_are_never_percent_encoded(self):
        url = metgene.metgene_url("studies", "hsa", "SYMBOL", "HMGCR", anatomy="Fibroblast cells")
        self.assertIn("/anatomy/Fibroblast+cells/", url)
        self.assertNotIn("%20", url)

    def test_multi_gene_request_is_refused(self):
        with self.assertRaises(ValueError):
            metgene.metgene_url("summary", "hsa", "SYMBOL", "HMGCR,PPARGC1A")

    def test_unsupported_species_context_and_id_type_fail_loudly(self):
        with self.assertRaises(ValueError):
            metgene.metgene_url("pathways", "hsa", "SYMBOL", "HMGCR")
        with self.assertRaises(ValueError):
            metgene.metgene_url("summary", "zebrafish", "SYMBOL", "HMGCR")
        with self.assertRaises(ValueError):
            metgene.metgene_url("summary", "hsa", "BOGUSID", "HMGCR")


class MetGeneClassificationTests(unittest.TestCase):
    def test_each_empty_shape_is_a_distinct_status(self):
        cases = [
            (metgene.RawResponse("u", 200, "application/json", "[[]]"), "metabolites", "no_hits"),
            (metgene.RawResponse("u", 200, "application/json", "[]"), "studies", "no_hits"),
            (
                metgene.RawResponse("u", 200, "application/json", NO_SUMMARY_HTML),
                "summary",
                "gene_not_annotated",
            ),
            (
                metgene.RawResponse("u", 500, "text/plain", "Internal server error"),
                "summary",
                "gene_unresolved_or_source_error",
            ),
            (
                metgene.RawResponse("u", 200, "application/json", ""),
                "studies",
                "indeterminate_empty_body",
            ),
            (metgene.RawResponse("u", 403, "text/html", "<title>403</title>"), "studies", "unavailable"),
            (
                metgene.RawResponse("u", None, "", "", transport_error="timed out"),
                "studies",
                "unavailable",
            ),
        ]
        for response, context, expected in cases:
            with self.subTest(expected=expected):
                status, _payload, _detail = metgene.classify_metgene_response(response, context)
                self.assertEqual(status, expected)

    def test_a_zero_row_answer_is_never_an_unavailable_source(self):
        no_hits, _, _ = metgene.classify_metgene_response(
            metgene.RawResponse("u", 200, "application/json", "[[]]"), "metabolites"
        )
        unavailable, _, _ = metgene.classify_metgene_response(
            metgene.RawResponse("u", None, "", "", transport_error="dns failure"), "metabolites"
        )
        self.assertNotEqual(no_hits, unavailable)

    def test_double_and_single_nesting_are_unwrapped_by_context(self):
        self.assertEqual(len(metgene.metgene_rows("metabolites", json.loads(METABOLITES_BODY))), 2)
        self.assertEqual(len(metgene.metgene_rows("studies", json.loads(STUDIES_BODY))), 1)

    def test_study_row_traps_are_handled(self):
        row = metgene.metgene_rows("studies", json.loads(STUDIES_BODY))[0]
        self.assertEqual(metgene.strip_kegg_anchor(row["KEGG_COMPOUND_ID"]), "C00005")
        self.assertEqual(
            metgene.split_study_ids(row["STUDY_ID"]), ["ST000076", "ST000202", "ST000276"]
        )


class MetGeneLookupTests(unittest.TestCase):
    def test_licence_gate_withholds_kegg_derived_rows_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hmgcr"
            result = metgene.lookup_gene_metabolite_annotations(
                "HMGCR", out, species="hsa", fetcher=_fetcher(HAPPY_PATH), delay=_no_delay
            )
            self.assertFalse((out / "metgene_metabolites.csv").exists())
            self.assertTrue((out / "metgene_provenance.json").exists())
            self.assertTrue((out / "metgene_escalations.csv").exists())
            self.assertFalse(result["provenance"]["persisted_kegg_derived_fields"])
            reasons = [row["status"] for row in result["escalations"]]
            self.assertIn(metgene.LICENCE_UNACKNOWLEDGED, reasons)

    def test_acknowledged_run_writes_labelled_annotation_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hmgcr"
            result = metgene.lookup_gene_metabolite_annotations(
                "HMGCR",
                out,
                species="hsa",
                acknowledge_licence_review=True,
                fetcher=_fetcher(HAPPY_PATH),
                delay=_no_delay,
            )
            metabolites = read_csv_rows(out / "metgene_metabolites.csv")
            self.assertEqual(len(metabolites), 2)
            for row in metabolites:
                self.assertEqual(row["measurement_established"], "not_established")
                self.assertEqual(row["evidence_type"], "gene_product_reaction_annotation")
                self.assertEqual(row["review_status"], "requires_human_review")
            # A compound with no standardized name is recorded as unmapped, not dropped.
            self.assertEqual(
                sorted(row["refmet_mapping_status"] for row in metabolites),
                ["absent_no_refmet_mapping", "mapped"],
            )
            # The echoed identifier is Entrez even though a symbol was queried.
            self.assertTrue(
                all(row["identifier_echo_status"] == "echo_differs_from_query" for row in metabolites)
            )

            studies = read_csv_rows(out / "metgene_study_candidates.csv")
            self.assertEqual(len(studies), 3)
            self.assertTrue(all(row["repository_refetch_required"] == "True" for row in studies))
            self.assertTrue(
                all(row["evidence_type"] == "annotation_derived_study_candidate" for row in studies)
            )
            self.assertEqual(result["provenance"]["pathway_count_precomputed"], 4)

    def test_pathway_listing_is_recorded_as_not_retrievable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = metgene.lookup_gene_metabolite_annotations(
                "HMGCR", Path(tmp) / "g", species="hsa", fetcher=_fetcher(HAPPY_PATH), delay=_no_delay
            )
            self.assertEqual(
                result["provenance"]["pathway_listing_status"], "not_retrievable_by_api"
            )

    def test_every_non_ok_context_produces_a_reviewer_question(self):
        bodies = dict(HAPPY_PATH)
        bodies["studies"] = metgene.RawResponse("", 200, "application/json", "")
        bodies["metabolites"] = metgene.RawResponse("", 500, "text/plain", "Internal server error")
        with tempfile.TemporaryDirectory() as tmp:
            result = metgene.lookup_gene_metabolite_annotations(
                "HMGCR", Path(tmp) / "g", species="hsa", fetcher=_fetcher(bodies), delay=_no_delay
            )
            statuses = {row["context"]: row["status"] for row in result["escalations"]}
            self.assertEqual(statuses["studies"], "indeterminate_empty_body")
            self.assertEqual(statuses["metabolites"], "gene_unresolved_or_source_error")
            for row in result["escalations"]:
                self.assertTrue(row["reviewer_question"])
                self.assertTrue(row["evidence_needed"])
            self.assertEqual(
                result["provenance"]["unresolved_gene_contexts"], ["metabolites"]
            )
            self.assertEqual(result["provenance"]["indeterminate_contexts"], ["studies"])

    def test_phenotype_filter_is_recorded_as_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = metgene.lookup_gene_metabolite_annotations(
                "HMGCR",
                Path(tmp) / "g",
                species="hsa",
                phenotype="BMI",
                fetcher=_fetcher(HAPPY_PATH),
                delay=_no_delay,
            )
            self.assertEqual(
                result["provenance"]["phenotype_filter_effect"], "unverified_suspected_noop"
            )


class GeneMetaboliteEvidenceTests(unittest.TestCase):
    def test_each_hop_states_what_it_does_not_establish(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hmgcr"
            metgene.lookup_gene_metabolite_annotations(
                "HMGCR",
                out,
                species="hsa",
                acknowledge_licence_review=True,
                fetcher=_fetcher(HAPPY_PATH),
                delay=_no_delay,
            )
            evidence = build_gene_metabolite_evidence(out, out)
            hops = {row["hop"] for row in evidence["ledger"]}
            self.assertEqual(
                hops,
                {
                    "pathway_count",
                    "gene_to_reaction",
                    "reaction_to_compound",
                    "compound_to_standard_name",
                    "standard_name_to_study",
                },
            )
            for row in evidence["ledger"]:
                self.assertTrue(row["does_not_establish"])
                self.assertEqual(row["measurement_established"], "not_established")

    def test_no_recorded_status_is_evidence_of_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hmgcr"
            metgene.lookup_gene_metabolite_annotations(
                "HMGCR",
                out,
                species="hsa",
                acknowledge_licence_review=True,
                fetcher=_fetcher(HAPPY_PATH),
                delay=_no_delay,
            )
            evidence = build_gene_metabolite_evidence(out, out)
            self.assertTrue(evidence["coverage"])
            self.assertTrue(all(row["is_evidence_of_absence"] is False for row in evidence["coverage"]))

    def test_ledger_is_deterministic(self):
        rows = [
            {
                "queried_gene": "HMGCR",
                "queried_gene_id_type": "SYMBOL",
                "queried_species": "hsa",
                "kegg_compound_id": "C00005",
                "kegg_reaction_id": "R02082",
                "refmet_name": "NADPH",
                "refmet_mapping_status": "mapped",
                "source_url": "u",
            }
        ]
        first = build_inference_ledger(metabolite_rows=rows)
        second = build_inference_ledger(metabolite_rows=list(reversed(rows)))
        self.assertEqual(first, second)


class MetGeneReviewRegressionTests(unittest.TestCase):
    """Regressions for defects an adversarial review of this lane confirmed."""

    def test_a_context_that_was_not_requested_is_never_written_as_an_empty_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hmgcr"
            result = metgene.lookup_gene_metabolite_annotations(
                "HMGCR",
                out,
                species="hsa",
                contexts=["summary"],
                acknowledge_licence_review=True,
                fetcher=_fetcher(HAPPY_PATH),
                delay=_no_delay,
            )
            self.assertTrue((out / "metgene_summary.csv").exists())
            for name in ("metgene_metabolites.csv", "metgene_reactions.csv", "metgene_study_candidates.csv"):
                self.assertFalse((out / name).exists(), f"{name} was written for an unrequested context")
            prov = result["provenance"]
            self.assertEqual(prov["contexts_requested"], ["summary"])
            self.assertEqual(prov["contexts_not_requested"], ["metabolites", "reactions", "studies"])
            # A count of zero would assert the source answered with nothing.
            self.assertEqual(sorted(prov["row_counts"]), ["summary"])
            not_requested = {
                row["context"] for row in result["escalations"] if row["status"] == "not_requested"
            }
            self.assertEqual(not_requested, {"metabolites", "reactions", "studies"})

    def test_a_narrowed_run_removes_a_stale_table_from_a_wider_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hmgcr"
            metgene.lookup_gene_metabolite_annotations(
                "HMGCR", out, species="hsa", acknowledge_licence_review=True,
                fetcher=_fetcher(HAPPY_PATH), delay=_no_delay,
            )
            self.assertTrue((out / "metgene_metabolites.csv").exists())
            metgene.lookup_gene_metabolite_annotations(
                "HMGCR", out, species="hsa", contexts=["summary"], acknowledge_licence_review=True,
                fetcher=_fetcher(HAPPY_PATH), delay=_no_delay,
            )
            self.assertFalse((out / "metgene_metabolites.csv").exists())

    def test_the_pathway_count_is_withheld_with_the_other_kegg_derived_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            withheld = metgene.lookup_gene_metabolite_annotations(
                "HMGCR", Path(tmp) / "a", species="hsa",
                fetcher=_fetcher(HAPPY_PATH), delay=_no_delay,
            )["provenance"]
            self.assertFalse(withheld["persisted_kegg_derived_fields"])
            self.assertIsNone(withheld["pathway_count_precomputed"])
            self.assertEqual(withheld["pathway_count_status"], "withheld_pending_licence_review")

            persisted = metgene.lookup_gene_metabolite_annotations(
                "HMGCR", Path(tmp) / "b", species="hsa", acknowledge_licence_review=True,
                fetcher=_fetcher(HAPPY_PATH), delay=_no_delay,
            )["provenance"]
            self.assertEqual(persisted["pathway_count_precomputed"], 4)
            self.assertEqual(persisted["pathway_count_status"], "retrieved")

    def test_appraising_a_withheld_record_set_fails_instead_of_reporting_an_empty_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hmgcr"
            metgene.lookup_gene_metabolite_annotations(
                "HMGCR", out, species="hsa", fetcher=_fetcher(HAPPY_PATH), delay=_no_delay,
            )
            with self.assertRaises(ValueError) as ctx:
                build_gene_metabolite_evidence(out, out)
            self.assertIn("licence", str(ctx.exception))

    def test_html_prefixed_json_is_not_read_as_an_unannotated_gene(self):
        mixed = metgene.RawResponse(
            "u",
            200,
            "application/json",
            "<h3>No summaries found for genes: PPARGC1A</h3>" + SUMMARY_BODY,
        )
        status, _payload, detail = metgene.classify_metgene_response(mixed, "summary")
        self.assertEqual(status, "unavailable")
        self.assertIn("partial multi-gene match", detail)

    def test_a_missing_echo_is_not_recorded_as_a_verified_match(self):
        self.assertEqual(metgene._echo_status("", "HMGCR"), "no_echo_returned")
        self.assertEqual(metgene._echo_status("not_reported", "HMGCR"), "no_echo_returned")
        self.assertEqual(metgene._echo_status("HMGCR", "HMGCR"), "echo_matches_query")
        self.assertEqual(metgene._echo_status("3156", "HMGCR"), "echo_differs_from_query")

    def test_a_null_inside_an_array_field_is_not_written_as_the_string_none(self):
        self.assertEqual(metgene._first({"KEGG_REACTION_NAME": [None]}, "KEGG_REACTION_NAME"), "")
        self.assertEqual(
            metgene._first({"KEGG_REACTION_NAME": [None, "R1"]}, "KEGG_REACTION_NAME"), "R1"
        )

    def test_path_metacharacters_and_gene_lists_are_refused(self):
        for value in ("Blood/Plasma", "Blood?x", "Blood#1", "a%20b"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    metgene.metgene_url("studies", "hsa", "SYMBOL", "HMGCR", anatomy=value)
        for gene in ("HMGCR,PPARGC1A", "HMGCR__PPARGC1A", "HMGCR PPARGC1A", "HMGCR+PPARGC1A", "HMGCR;PPARGC1A"):
            with self.subTest(gene=gene):
                with self.assertRaises(ValueError):
                    metgene.metgene_url("summary", "hsa", "SYMBOL", gene)

    def test_the_polite_delay_is_not_keyed_on_fetcher_identity_or_context_index(self):
        calls: list[str] = []

        def wrapped(url: str) -> metgene.RawResponse:
            return _fetcher(HAPPY_PATH)(url)

        with tempfile.TemporaryDirectory() as tmp:
            # A wrapped live-style fetcher still gets the delay; only an explicit
            # no-op delay opts out.
            metgene.lookup_gene_metabolite_annotations(
                "HMGCR", Path(tmp) / "a", species="hsa", contexts=["studies"],
                fetcher=wrapped, delay=lambda: calls.append("slept"),
            )
            # One request means no inter-request sleep, even though "studies" is last
            # in the context tuple.
            self.assertEqual(calls, [])
            metgene.lookup_gene_metabolite_annotations(
                "HMGCR", Path(tmp) / "b", species="hsa", contexts=["reactions", "studies"],
                fetcher=wrapped, delay=lambda: calls.append("slept"),
            )
            self.assertEqual(calls, ["slept"])


if __name__ == "__main__":
    unittest.main()
