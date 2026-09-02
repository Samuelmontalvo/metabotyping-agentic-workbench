"""Screen the Metabolomics Workbench candidate list in ``mw_exercise_studies.csv`` by title.

``reports_live/exercise_studies/mw_exercise_studies.csv`` is a keyword-retrieved candidate list:
no query string, endpoint, or retrieval date was recorded for it, and its 66 titles include
lung-cancer "training set" and Lyme "biosignature training" studies, sleep-apnea cardiovascular
panels, and cardiolipin/cardiomyocyte work. A list like that is not an exercise-study catalog
until each title is screened, and a title screen is inference, not a design classification.

This offline script writes, next to the input:

- ``mw_exercise_studies_screened.csv`` — one row per study with the matched terms, the
  title-inference class, and ``review_status=requires_human_review`` on every row.
- ``mw_exercise_studies_screening.json`` — counts, the exact patterns used, and the provenance
  statement for the input list.

Classes (title text only; abstract, design, and factor evidence are not consulted):

- ``title_supports_exercise_context``: an exercise/training/sport/physical-activity term appears
  in an exercise sense.
- ``title_ambiguous_term_only``: the only matches are phrases where the word means something
  else ("training set", "biosignature training", "fitness to hypoxia", "breathing exercises").
- ``title_no_exercise_term``: no exercise term at all; the study was most likely retrieved by a
  non-exercise keyword such as "cardio".
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IN_PATH = REPO_ROOT / "reports_live" / "exercise_studies" / "mw_exercise_studies.csv"
OUT_CSV = IN_PATH.with_name("mw_exercise_studies_screened.csv")
OUT_JSON = IN_PATH.with_name("mw_exercise_studies_screening.json")

# Phrases in which an exercise-looking word carries a different meaning. Checked first and
# removed from the title before the exercise terms are matched.
AMBIGUOUS_PHRASES: dict[str, str] = {
    "training_set_ml": r"\btraining\s*set\b",
    "biosignature_training_ml": r"\bbiosignature\s+training\b",
    "fitness_biological_sense": r"\bfitness\s+to\s+hypoxia\b",
    "breathing_exercises": r"\bbreathing\s+exercises?\b",
}

EXERCISE_TERMS: dict[str, str] = {
    "exercise": r"\bexercis(?:e|es|ed|ing)\b",
    "post_exercise": r"\bpost[- ]exercise\b",
    "exercise_induced": r"\bexercise[- ]induced\b",
    "training": r"\btraining\b",
    "training_induced": r"\btraining[- ]induced\b",
    "athlete": r"\bathlet\w*",
    "sport": r"\bsports?\b",
    "endurance": r"\bendurance\b",
    "hiit_or_interval": r"\bhiit\b|\bhigh[- ]intensity\s+interval\b",
    "physical_activity": r"\bphysical\s+activity\b",
    "cardiorespiratory_fitness": r"\bcardiorespiratory\s+fitness\b",
    "marathon_running_cycling": r"\bmarathon\b|\brunning\b|\bcycling\b",
    "resistance_training": r"\bresistance\s+training\b",
}

# Retrieval hypothesis: 64 of the 66 titles match this sweep, and no title in
# data/live/mw_human_candidates.csv matches it without being in the list. The two
# non-matching titles (ST002185, ST003929) show the retrieval also read something
# beyond the title (abstract or keywords). Recorded as an inference about how the
# list was produced, not as its provenance.
RETRIEVAL_HYPOTHESIS = r"exercis|train|fitness|sport|athlet|cardio"


def screen_title(title: str) -> tuple[str, list[str], list[str]]:
    working = title
    ambiguous_hits: list[str] = []
    for label, pattern in AMBIGUOUS_PHRASES.items():
        if re.search(pattern, working, flags=re.IGNORECASE):
            ambiguous_hits.append(label)
            working = re.sub(pattern, " ", working, flags=re.IGNORECASE)
    term_hits = [
        label
        for label, pattern in EXERCISE_TERMS.items()
        if re.search(pattern, working, flags=re.IGNORECASE)
    ]
    if term_hits:
        return "title_supports_exercise_context", term_hits, ambiguous_hits
    if ambiguous_hits:
        return "title_ambiguous_term_only", term_hits, ambiguous_hits
    return "title_no_exercise_term", term_hits, ambiguous_hits


def main() -> None:
    with IN_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    screened = []
    for row in rows:
        title = row.get("title") or ""
        klass, term_hits, ambiguous_hits = screen_title(title)
        screened.append(
            {
                "study_id": row.get("study_id", ""),
                "title": title,
                "species": row.get("species", ""),
                "title_inference_class": klass,
                "exercise_terms_matched": ";".join(term_hits),
                "ambiguous_phrases_matched": ";".join(ambiguous_hits),
                "retrieval_sweep_match": bool(re.search(RETRIEVAL_HYPOTHESIS, title, re.IGNORECASE)),
                "evidence_basis": "title_text_only",
                "review_status": "requires_human_review",
            }
        )

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(screened[0].keys()))
        writer.writeheader()
        writer.writerows(screened)

    counts: dict[str, int] = {}
    for item in screened:
        counts[item["title_inference_class"]] = counts.get(item["title_inference_class"], 0) + 1
    summary = {
        "input": {
            "path": str(IN_PATH.relative_to(REPO_ROOT)),
            "sha256": hashlib.sha256(IN_PATH.read_bytes()).hexdigest(),
            "rows": len(rows),
            "provenance_status": "retrieval_query_and_endpoint_not_recorded",
            "retrieval_hypothesis": {
                "pattern": RETRIEVAL_HYPOTHESIS,
                "titles_matching": sum(item["retrieval_sweep_match"] for item in screened),
                "titles_not_matching": [
                    item["study_id"] for item in screened if not item["retrieval_sweep_match"]
                ],
                "note": (
                    "Most input titles match this sweep and no title in "
                    "data/live/mw_human_candidates.csv matches it without being in the list; the "
                    "titles that do not match show the retrieval also read text beyond the title. "
                    "This is an inference about how the list was produced, not a recorded query."
                ),
            },
        },
        "outputs": {
            "screened_csv": str(OUT_CSV.relative_to(REPO_ROOT)),
        },
        "class_counts": dict(sorted(counts.items())),
        "patterns": {
            "ambiguous_phrases": AMBIGUOUS_PHRASES,
            "exercise_terms": EXERCISE_TERMS,
        },
        "evidence_basis": "title_text_only",
        "interpretation_limits": [
            "A title term is inference about study context; it does not establish an exercise "
            "intervention, a sampled timepoint, or a blood-derived matrix.",
            "A study with no exercise term in its title may still contain an exercise arm; "
            "absence here is a screening outcome, not evidence of absence.",
            "Every row is routed to human review; nothing in this file is an inclusion decision.",
        ],
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"class_counts": summary["class_counts"], "rows": len(rows)}, indent=2))
    for item in screened:
        if item["title_inference_class"] != "title_supports_exercise_context":
            print(f"  {item['study_id']}  {item['title_inference_class']:30}  {item['title'][:80]}")


if __name__ == "__main__":
    main()
