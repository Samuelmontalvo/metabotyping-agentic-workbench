"""Offline tests for the Metabolomics Workbench compound, gene/protein, and mass contexts.

Every fixture is a wire shape the live service was observed to return. The service
answers HTTP 200 for success, for a rejected request, and for a genuine miss, so
these tests pin the classification to the content type and body rather than the
status code, and pin the adduct-verification and candidate-set guardrails.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.io import read_csv_rows
from metabotyping_agentic.live_sources import metabolomics_workbench as mw

GLUCOSE_HMDB = json.dumps(
    {
        "hmdb_id": "HMDB0000122",
        "regno": "37288",
        "formula": "C6H12O6",
        "exactmass": "180.063390",
        "inchi_key": "WQZGKKKJIJFFOK-VFUOTHLCSA-N",
        "name": "Beta-D-Glucose",
        "sys_name": "(2R,3R,4S,5S,6R)-6-(hydroxymethyl)oxane-2,3,4,5-tetrol",
        "pubchem_cid": "64689",
        "kegg_id": "C00221",
        "chebi_id": "15903",
    }
)

FORMULA_ROWS = json.dumps(
    {
        "Row1": {"formula": "C20H34O", "name": "Geranylgeraniol", "regno": "28467"},
        "Row2": {"formula": "C20H34O", "name": "Phytol", "regno": "28468"},
    }
)

PROTEIN_ROWS = json.dumps(
    {
        "Row1": {
            "uniprot_id": "Q13085",
            "mgp_id": "MGP000016",
            "gene_id": "31",
            "gene_symbol": "ACACA",
            "gene_name": "acetyl-CoA carboxylase alpha",
            "taxid": "9606",
            "species": "Human",
            "refseq_id": "NP_942131",
        },
        "Row2": {
            "uniprot_id": "Q13085",
            "mgp_id": "MGP000016",
            "gene_id": "31",
            "gene_symbol": "ACACA",
            "gene_name": "acetyl-CoA carboxylase alpha",
            "taxid": "9606",
            "species": "Human",
            "refseq_id": "NP_942133",
        },
    }
)

MOVERZ_REFMET = (
    "Input m/z\tMatched m/z\tDelta\tName\tSystematic name\tFormula\tIon\tCategory\tMain class\tSub class\n"
    "255.2\t255.1955\t.0045\t5-Hydroxyculmorin\t(1S,2R)-x\tC15H26O3\t[M+H]+\tOther\tOther\tOther\n"
)
MOVERZ_NEUTRAL_FALLBACK = (
    "Input m/z\tMatched m/z\tDelta\tName\tSystematic name\tFormula\tIon\tCategory\tMain class\tSub class\n"
    "255.2\t255.1955\t.0045\tSomething\tsys\tC15H26O3\tNeutral\tOther\tOther\tOther\n"
)
MOVERZ_LIPIDS_BROKEN = (
    "Input m/z\tMatched m/z\tDelta\tName\tFormula\tIon\n"
    "513.45\t513.4495.0005\tDG(30:1)\tC33H62O5\t[M-2H]2-\t\n"
)
MOVERZ_HEADER_ONLY = (
    "Input m/z\tMatched m/z\tDelta\tName\tSystematic name\tFormula\tIon\tCategory\tMain class\tSub class\n"
)

EXACTMASS_BULK = "PC 34:1</br>\n[M+H]+</br>\n760.585077</br>\nC42H83NO8P"
EXACTMASS_MOLECULAR = "PC 16:0_18:1</br>\nPC 34:1</br>\n[M+H]+</br>\n760.585077</br>\nC42H83NO8P"

HTML_ERROR = "This input item (bogus) is not allowed<br> Choose from: 'regno','formula'"


def _json_fetcher(body: str, *, status: int = 200, content_type: str = "application/json"):
    return lambda url: mw.MwRawResponse(url, status, content_type, body)


def _text_fetcher(body: str, *, status: int = 200, content_type: str = "text/html"):
    return lambda url: mw.MwRawResponse(url, status, content_type, body)


class MwResponseClassificationTests(unittest.TestCase):
    def test_status_code_is_never_the_success_signal(self):
        cases = [
            (mw.MwRawResponse("u", 200, "application/json", GLUCOSE_HMDB), "ok"),
            (mw.MwRawResponse("u", 200, "application/json", "[]"), "no_hits"),
            (mw.MwRawResponse("u", 200, "text/html; charset=UTF-8", HTML_ERROR), "request_rejected"),
            (mw.MwRawResponse("u", 404, "text/html", ""), "unavailable"),
            (mw.MwRawResponse("u", None, "", "", transport_error="timed out"), "unavailable"),
        ]
        for response, expected in cases:
            with self.subTest(expected=expected):
                status, _payload, _detail = mw.classify_mw_response(response)
                self.assertEqual(status, expected)
                self.assertEqual(response.http_status in (200, None), expected != "unavailable" or response.http_status is None)

    def test_a_rejected_request_is_not_a_coverage_gap(self):
        rejected, _, _ = mw.classify_mw_response(
            mw.MwRawResponse("u", 200, "text/html", HTML_ERROR)
        )
        missing, _, _ = mw.classify_mw_response(mw.MwRawResponse("u", 200, "application/json", "[]"))
        self.assertNotEqual(rejected, missing)

    def test_flat_and_row_keyed_shapes_both_normalize(self):
        self.assertEqual(len(mw.mw_rows(json.loads(GLUCOSE_HMDB))), 1)
        self.assertEqual(len(mw.mw_rows(json.loads(FORMULA_ROWS))), 2)


class CompoundLookupTests(unittest.TestCase):
    def test_identifier_normalization_is_applied_and_recorded(self):
        self.assertEqual(
            mw.normalize_compound_identifier("hmdb_id", "HMDB122"),
            ("HMDB0000122", "zero_padded_hmdb_id:HMDB122->HMDB0000122"),
        )
        self.assertEqual(
            mw.normalize_compound_identifier("chebi_id", "CHEBI:24229"),
            ("24229", "stripped_chebi_prefix:CHEBI:24229->24229"),
        )
        self.assertEqual(mw.normalize_compound_identifier("regno", "11"), ("11", "none"))

    def test_sparse_all_record_reports_absent_cross_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.lookup_compound(
                "HMDB122",
                Path(tmp) / "c",
                input_item="hmdb_id",
                fetcher=_json_fetcher(GLUCOSE_HMDB),
            )
            row = result["rows"][0]
            self.assertEqual(row["regno"], "37288")
            # lm_id and metacyc_id are absent keys in this record, not empty values.
            self.assertEqual(row["lm_id"], "not_reported")
            self.assertEqual(row["metacyc_id"], "not_reported")
            self.assertEqual(row["measurement_established"], "not_established")

    def test_multiple_records_are_a_candidate_set_and_never_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.lookup_compound(
                "C20H34O",
                Path(tmp) / "c",
                input_item="formula",
                output_item="name",
                fetcher=_json_fetcher(FORMULA_ROWS),
            )
            self.assertEqual(len(result["rows"]), 2)
            for row in result["rows"]:
                self.assertEqual(row["candidate_set_size"], 2)
                self.assertEqual(row["identity_status"], "multiple_candidates_requires_human_review")

    def test_undocumented_input_items_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.lookup_compound(
                "CHEBI:24229",
                Path(tmp) / "c",
                input_item="chebi_id",
                fetcher=_json_fetcher(GLUCOSE_HMDB),
            )
            self.assertEqual(result["rows"][0]["input_item_support"], "undocumented_may_be_withdrawn")

    def test_unsupported_items_and_slashes_fail_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                mw.lookup_compound("x", Path(tmp) / "c", input_item="bogus")
            with self.assertRaises(ValueError):
                mw.lookup_compound("x", Path(tmp) / "c", output_item="png")
            with self.assertRaises(ValueError):
                mw.lookup_compound("C(=O)/C", Path(tmp) / "c", input_item="smiles")


class MgpLookupTests(unittest.TestCase):
    def test_records_never_claim_a_metabolite_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.lookup_mgp_gene_protein(
                "Q13085",
                Path(tmp) / "g",
                context="protein",
                input_item="uniprot_id",
                fetcher=_json_fetcher(PROTEIN_ROWS),
            )
            self.assertEqual(len(result["rows"]), 2)
            for row in result["rows"]:
                self.assertEqual(
                    row["metabolite_link_established"],
                    "not_established_no_compound_field_in_source",
                )
                self.assertEqual(row["species_coverage"], "human_only_taxid_9606")
                self.assertEqual(row["annotation_currency"], "unknown_no_build_date")

    def test_substring_search_is_labelled_as_such(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.lookup_mgp_gene_protein(
                "carboxylase",
                Path(tmp) / "g",
                context="gene",
                input_item="gene_name",
                fetcher=_json_fetcher(PROTEIN_ROWS),
            )
            self.assertTrue(
                all(row["match_basis"] == "unanchored_substring_match" for row in result["rows"])
            )

    def test_non_human_taxid_is_refused_rather_than_reported_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                mw.lookup_mgp_gene_protein(
                    "10116", Path(tmp) / "g", context="gene", input_item="taxid"
                )
            self.assertIn("species_not_covered_by_source", str(ctx.exception))


class MassSearchTests(unittest.TestCase):
    def test_verified_adduct_match_is_emitted_as_a_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "m"
            result = mw.search_moverz(
                255.2, out, adduct="M+H", tolerance_da=0.02, fetcher=_text_fetcher(MOVERZ_REFMET)
            )
            self.assertEqual(result["status"], "ok")
            row = result["rows"][0]
            self.assertEqual(row["echoed_adduct"], "[M+H]+")
            self.assertTrue(row["adduct_verified"])
            self.assertEqual(row["identification_status"], "candidate_not_an_identification")
            self.assertEqual(read_csv_rows(out / "mw_moverz_matches.csv")[0]["name"], "5-Hydroxyculmorin")

    def test_silent_neutral_fallback_is_discarded_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.search_moverz(
                255.2,
                Path(tmp) / "m",
                adduct="M+Bogus",
                tolerance_da=0.02,
                fetcher=_text_fetcher(MOVERZ_NEUTRAL_FALLBACK),
            )
            self.assertEqual(result["status"], "adduct_not_supported_silent_neutral_fallback")
            self.assertEqual(result["rows"], [])

    def test_dot_notation_adduct_matches_the_echoed_plus_form(self):
        body = MOVERZ_REFMET.replace("[M+H]+", "[M+Cl]-")
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.search_moverz(
                255.2, Path(tmp) / "m", adduct="M.Cl", tolerance_da=0.02, fetcher=_text_fetcher(body)
            )
            self.assertEqual(result["status"], "ok")

    def test_lipids_column_bug_is_recovered_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.search_moverz(
                513.45,
                Path(tmp) / "m",
                adduct="M-2H",
                tolerance_da=0.2,
                database="LIPIDS",
                fetcher=_text_fetcher(MOVERZ_LIPIDS_BROKEN),
            )
            self.assertEqual(result["status"], "ok")
            row = result["rows"][0]
            self.assertEqual(row["matched_mz"], "513.4495")
            self.assertEqual(row["delta"], ".0005")
            self.assertTrue(row["column_recovery_applied"])

    def test_header_only_body_is_no_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.search_moverz(
                1.0, Path(tmp) / "m", tolerance_da=0.02, fetcher=_text_fetcher(MOVERZ_HEADER_ONLY)
            )
            self.assertEqual(result["status"], "no_hits")

    def test_non_positive_tolerance_and_bad_database_fail_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                mw.search_moverz(255.2, Path(tmp) / "m", tolerance_da=0)
            with self.assertRaises(ValueError):
                mw.search_moverz(255.2, Path(tmp) / "m", database="BOGUS")
            with self.assertRaises(ValueError):
                mw.search_moverz(255.2, Path(tmp) / "m", adduct="M.KFormate-H")


class ExactMassTests(unittest.TestCase):
    def test_bulk_and_molecular_notation_both_parse_from_the_end(self):
        for body in (EXACTMASS_BULK, EXACTMASS_MOLECULAR):
            with self.subTest(body=body.splitlines()[0]):
                with tempfile.TemporaryDirectory() as tmp:
                    result = mw.compute_exact_mass(
                        "PC(34:1)", Path(tmp) / "e", adduct="M+H", fetcher=_text_fetcher(body)
                    )
                    self.assertEqual(result["status"], "ok")
                    row = result["rows"][0]
                    self.assertEqual(row["exact_mz"], "760.585077")
                    self.assertEqual(row["ion_formula"], "C42H83NO8P")
                    self.assertEqual(
                        row["identification_status"], "computed_value_not_a_measurement"
                    )

    def test_slash_notation_is_rewritten_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.compute_exact_mass(
                "PC(16:0/18:1)", Path(tmp) / "e", fetcher=_text_fetcher(EXACTMASS_MOLECULAR)
            )
            self.assertEqual(
                result["rows"][0]["notation_rewrite_applied"],
                "slash_to_underscore:PC(16:0/18:1)->PC(16:0_18:1)",
            )

    def test_hyphen_chain_separator_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                mw.compute_exact_mass("PC(16:0-18:1)", Path(tmp) / "e")


class MwReviewRegressionTests(unittest.TestCase):
    """Regressions for defects an adversarial review of this lane confirmed."""

    def test_an_adduct_whose_formula_ends_in_a_digit_still_verifies(self):
        cases = [
            ("M+H", "[M+H]+", True),
            ("M-H", "[M-H]-", True),
            ("M-2H", "[M-2H]2-", True),
            ("M+NH4", "[M+NH4]+", True),
            ("M+Na", "[M+Na]+", True),
            ("M.Cl", "[M+Cl]-", True),
            ("M+HCOO", "[M+HCOO]-", True),
            ("M+H", "Neutral", False),
            ("M+H", "[M+Na]+", False),
            ("M+NH4", "[M+NH]+", False),
            ("M+H", "", False),
        ]
        for requested, echoed, expected in cases:
            with self.subTest(requested=requested, echoed=echoed):
                self.assertEqual(mw._adducts_match(requested, echoed), expected)

    def test_an_ammonium_match_is_not_discarded_as_a_neutral_fallback(self):
        body = MOVERZ_REFMET.replace("[M+H]+", "[M+NH4]+")
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.search_moverz(
                255.2, Path(tmp) / "m", adduct="M+NH4", tolerance_da=0.02,
                fetcher=_text_fetcher(body),
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(len(result["rows"]), 1)

    def test_an_empty_object_is_not_written_as_a_fabricated_compound_record(self):
        self.assertEqual(mw.mw_rows({}), [])
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.lookup_compound(
                "11", Path(tmp) / "c", input_item="regno", fetcher=_json_fetcher("{}")
            )
            self.assertEqual(result["status"], "no_hits")
            self.assertEqual(result["rows"], [])

    def test_moverz_distinguishes_an_html_error_and_an_empty_body_from_a_zero_match(self):
        cases = [
            (_text_fetcher(HTML_ERROR), "request_rejected"),
            (_text_fetcher("<html><body>Service unavailable</body></html>"), "request_rejected"),
            (_text_fetcher(""), "unavailable"),
            (_text_fetcher(MOVERZ_HEADER_ONLY), "no_hits"),
        ]
        for fetcher, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as tmp:
                    result = mw.search_moverz(
                        255.2, Path(tmp) / "m", tolerance_da=0.02, fetcher=fetcher
                    )
                    self.assertEqual(result["status"], expected)

    def test_exactmass_reports_an_empty_body_as_unavailable_not_as_a_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.compute_exact_mass(
                "PC(34:1)", Path(tmp) / "e", fetcher=_text_fetcher("")
            )
            self.assertEqual(result["status"], "unavailable")

    def test_bulk_notation_does_not_write_the_ion_label_into_the_composition_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            bulk = mw.compute_exact_mass(
                "PC(34:1)", Path(tmp) / "b", fetcher=_text_fetcher(EXACTMASS_BULK)
            )["rows"][0]
            self.assertEqual(bulk["resolved_name"], "PC 34:1")
            self.assertEqual(bulk["resolved_bulk_composition"], "PC 34:1")
            self.assertNotIn("[M+H]+", bulk["resolved_bulk_composition"])

            molecular = mw.compute_exact_mass(
                "PC(16:0_18:1)", Path(tmp) / "m", fetcher=_text_fetcher(EXACTMASS_MOLECULAR)
            )["rows"][0]
            self.assertEqual(molecular["resolved_name"], "PC 16:0_18:1")
            self.assertEqual(molecular["resolved_bulk_composition"], "PC 34:1")

    def test_a_lipids_delta_of_one_dalton_or_more_is_split_against_the_input_mz(self):
        # matched 512.4495, delta 1.0005 -> the concatenated cell is "512.44951.0005".
        body = (
            "Input m/z\tMatched m/z\tDelta\tName\tFormula\tIon\n"
            "513.45\t512.44951.0005\tDG(30:1)\tC33H62O5\t[M-2H]2-\t\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.search_moverz(
                513.45, Path(tmp) / "m", adduct="M-2H", tolerance_da=1.5,
                database="LIPIDS", fetcher=_text_fetcher(body),
            )
            self.assertEqual(result["status"], "ok")
            row = result["rows"][0]
            self.assertEqual(row["matched_mz"], "512.4495")
            self.assertEqual(row["delta"], "1.0005")

    def test_an_unsplittable_lipids_cell_is_not_reported_as_recovered(self):
        body = (
            "Input m/z\tMatched m/z\tDelta\tName\tFormula\tIon\n"
            "513.45\t999.1111.2222\tDG(30:1)\tC33H62O5\t[M-2H]2-\t\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.search_moverz(
                513.45, Path(tmp) / "m", adduct="M-2H", tolerance_da=0.2,
                database="LIPIDS", fetcher=_text_fetcher(body),
            )
            self.assertTrue(all(not row["column_recovery_applied"] for row in result["rows"]))

    def test_mgp_rows_carry_the_measurement_guardrail_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mw.lookup_mgp_gene_protein(
                "Q13085", Path(tmp) / "g", context="protein", input_item="uniprot_id",
                fetcher=_json_fetcher(PROTEIN_ROWS),
            )
            self.assertTrue(
                all(row["measurement_established"] == "not_established" for row in result["rows"])
            )
            self.assertIn("measurement_established", read_csv_rows(result["records_path"])[0])


if __name__ == "__main__":
    unittest.main()
