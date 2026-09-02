# Scientific review — 2026-09-01

Reviewed at `4c9e3eb` (main, after the `lawrence-comments` merge) with the
uncommitted `reports_live/exercise_studies/` work and its renderer. Method: ran
the full regression suite, audited every statistical routine that feeds a
published number, re-derived the headline Lac-Phe statistic independently,
regenerated the pilot from the documented command and diffed it against the
committed artifacts, and read the scoring, mirage, crosswalk, alignment,
classifier and plotting code for scientific rather than software defects.

This document separates three things: what was verified and holds, what was
defective and is now fixed, and what is a scientific policy question that the
authors should decide rather than a defect I should silently change.

## Summary

| # | Finding | Severity | Status |
| --- | --- | --- | --- |
| 1 | Rat pass1b-06 volcano pooled male and female strata; every feature plotted twice, contrast id claimed "male" | High | Fixed |
| 2 | MoTrPAC human volcano labeled eleven per-platform FDR families as one study-wide adjustment | High | Fixed |
| 3 | Volcano feature identity was the RefMet name (shared by isomers, repeat features, platforms); no duplicate guard | Medium | Fixed |
| 4 | Internal-standard rows plotted as biological analytes in the rat volcano (21 per sex) | Medium | Fixed |
| 5 | `mw_exercise_studies.csv`: keyword sweep presented as an exercise-study list; 44/66 titles carry no exercise term | Medium | Fixed (screened, routed to review) |
| 6 | `classify_mw_timepoint` substring matching: `prediabetes`, `prednisone`, `Sample source:Blood` classified as pre; `CTR2` as time 0; no tests | Medium | Fixed |
| 7 | Committed `data/extracted/` stale relative to `run-pilot` (missing provenance key; ten legacy cards) | Medium | Fixed |
| 8 | Unit conversion applied glucose's molar-mass factor to any mmol/L→mg/dL pair | Low–Medium | Fixed |
| 9 | `gender` mapped to `sex` as a plain synonym with no construct caveat | Low | Fixed |
| 10 | `not_reported` platform described as "reported" and credited in the recommender | Low | Fixed |
| 11 | Dataset-readiness score has no human-participant gate and credits modality subscores regardless of data availability | Medium | Scope gate applied (§3.1, option A); availability gate still proposed |
| 12 | MoTrPAC alignment credits documented absence for genetics only | Low | Documented (§3.2) |
| 13 | Paired t-test accepted at n=3 pairs (df=2); pair count not carried in the ST004303 cached table | Low | Documented (§3.3) |
| 14 | Lac-Phe report CIs are reconstructed from (effect, p, n); headline text does not say so | Low | Documented (§3.4) |
| 15 | Rat volcano table has no retrieval provenance; ST004303 pools MIE+SIE arms; 1P/4P timing unverified | Low | Documented in manifest (§3.5) |
| 16 | Working `.venv` lacks `pydantic`, `pyarrow`, `pytest`; suite runs on the `_compat` fallback | Info | Documented (§3.6) |

Verification after the changes: 295 tests pass (282 before; thirteen added),
`ruff` clean over `src`, `tests`, `scripts`, strict readiness gate PASS, pilot
output byte-identical with and without `pydantic`. The only benchmark metrics
that moved are the two quality metrics redefined by the scope gate (§3.1).

## 1. What was verified and holds

- **Multiple-testing.** All four Benjamini–Hochberg implementations
  (`motrpac_volcano_compare.bh_adjust`, `plotting.benjamini_hochberg`,
  `volcano_compare._bh_fdr`, `run_metabolite_effect_search.bh_adjust_p_values`)
  compute the step-up running minimum in reverse rank order, clamp to 1, and
  are NaN-safe. Correct.
- **Paired t-test** via the regularized incomplete beta
  `I_x(df/2, 1/2)` with `x = df/(df+t²)` is the exact two-sided p. Correct.
- **Exact two-sided sign test** (`biomarker_reproduction._exact_two_sided_sign_test`)
  doubles the smaller tail with `math.comb`, caps at 1, and keeps the exact
  fraction. Independently recomputed for 92 of 116 higher-after pairs:
  `1.4181822700488305e-10`, identical to the published value.
- **Fisher right tail** (`fisher_right_tail_p_value`) is the exact hypergeometric
  upper tail in integer arithmetic. Correct.
- **AUROC** is the Mann–Whitney pair count with half credit for ties. Correct.
- **Diagonal LDA** pools within-class variance on `n−2`, standardizes, and uses
  the log prior ratio minus half the squared-centroid difference as the
  intercept. Correct for the stated model; the perfect synthetic score is
  expected and is labeled as such.
- **Pearson r** for the lactate coupling uses `fsum` and guards zero variance.
- **Review gating.** In the crosswalk only an exact-name match can reach 0.96;
  every synonym or partial match tops out at 0.88 < 0.90, so nothing non-exact
  auto-accepts. The recommender excludes non-human and non-blood MW
  candidates as designed.
- **Reproducibility.** Two isolated pilot runs match byte-for-byte, and a
  throwaway venv with `pydantic` 2.13 produces the same bytes as the
  standard-library fallback, so the fallback is not a hidden source of drift.
- **Network boundary** is enforced by AST scan and the documented allowlist
  matches the enforced one.

## 2. Defects fixed

### 2.1 Rat pass1b-06 volcano pooled the sexes (High)

`data/live/volcano_motrpac_pass1b06_plasma_8w.csv` holds 1077 male and 1077
female rows; every RefMet name appears exactly twice. The renderer drew all
2154 rows as one volcano under a contrast id reading `..._8w_male_vs_baseline_context`
with `n_features=2154`. That double-counts every feature, mixes two test
families whose `adj_p_value` were computed separately, and mislabels the
female half as male. MoTrPAC's timewise DA is trained-versus-sedentary within
sex; there is no pooled family to plot.

Fix: `scripts/render_exercise_studies_refmet_volcanoes.py` renders one figure
per sex with the contrast stated as 8-week trained versus sex-matched sedentary
control, records `fdr_scope` as the per-sex timewise family, and writes the
provenance status of the table (no request log exists; see §3.5). The pooled
PNG/CSV were withdrawn.

### 2.2 MoTrPAC human FDR scope (High)

`volcano_motrpac_human_plasma_endur_post.csv` concatenates eleven platform DA
tables (`metab-u-lrppos` 627 rows … `metab-t-imm-crt` 1). Each `adj_p_value`
was adjusted inside its own platform table. The renderer declared
`fdr_scope="within_study_all_tested_features"`, which is false: the y-axis is
eleven families overlaid, and a threshold line at 0.05 means eleven different
things. Fix: scope recorded as
`within_each_platform_da_table_as_released_by_motrpac_v1.3_dream_acute`, the
figure title and manifest say "11 platform DA tables overlaid", and the
platform list is written to the manifest.

### 2.3 Feature identity and the missing duplicate guard (Medium)

Feature ids were set to the RefMet name. RefMet names are shared by isomers
and repeat features (10 duplicates in ST004303), by the same analyte on
several platforms (226 in the MoTrPAC human table), and — found only because
the guard now exists — by one rat source label reported under two RefMet lipid
names within one sex (`pi(38:3)>pi(18:0_20:3)_feature2`). `prepare_volcano_data`
accepted all of this silently, although the heatmap and hierarchy paths
already reject duplicates.

Fix: `prepare_volcano_data` raises `PlotValidationError` on a duplicate
feature id within a contrast (test added); the renderer uses the
(source label, RefMet name) pair, which is unique per stratum in every cached
table, with the rule written to the manifest.

### 2.4 Internal standards plotted as analytes (Medium)

Rows such as `gtinternalstandard_pe(33:1(d7))…_[istd]` are QC features. They
are now excluded from the biological volcano (21 per sex) and counted in the
manifest rather than dropped invisibly.

### 2.5 The "exercise studies" list (Medium)

`reports_live/exercise_studies/mw_exercise_studies.csv` (66 studies) has no
generating script and no recorded query. Its titles include a lung-cancer
"training set", "Lyme Disease Biosignature Training", six sleep-apnea
cardiovascular panels, and cardiolipin, cardiomyocyte and cardiomyopathy
studies. Sixty-four of the 66 titles match the sweep
`exercis|train|fitness|sport|athlet|cardio` and no title in
`data/live/mw_human_candidates.csv` matches it without being in the list; the
two that do not match (ST002185, ST003929) show the retrieval also read text
beyond the title. That is an inference about how the list was made, not its
provenance, and is recorded as such.

Fix: `scripts/screen_mw_exercise_study_titles.py` screens each title with
explicit patterns and ambiguous-phrase exclusions: 19 support an exercise
context, 3 match only an ambiguous phrase, 44 contain no exercise term. Every
row is `requires_human_review`, the evidence basis is `title_text_only`, and
the summary states that absence of a title term is a screening outcome, not
evidence of absence. The list itself is left unchanged so the input is
auditable.

### 2.6 `classify_mw_timepoint` (Medium)

The fallback branch tested bare substrings: `"pre" in text`, `":b" in text`,
`"r2" in text`, `"r3" in text`. On real factor strings that means
`Diagnosis:prediabetes`, `Treatment:prednisone`, `Pressure:…` and
`Sample source:Blood` (`:b` in `:blood`) all classify as the pre sample, and
`CTR2`, `Group:R30`, `time 05` classify as post timepoints. Because
`compute_mw_volcano_stats` pairs any participant with a `pre` and a post
sample, this can build a contrast the study never ran. The README and
CHANGELOG already listed the function as untested.

Fix: fallback tokens are matched on alphanumeric-token boundaries
(`pre`/`pre_exercise`/`baseline`/`before`/`b`, `time 0`/`r2`, `time 60`/`r3`);
an explicit `Time:` factor remains authoritative. Tests cover the documented
conventions (ST001789-style `Group:Pre`, `_B/_R2/_R3` sample ids; ST004303
`Time:1P/4P`) and the eight substrings that previously misclassified. The
function still cannot verify that a label means exercise timing; that stays a
review question.

### 2.7 Committed pilot artifacts were stale (Medium)

Regenerating with the documented `run-pilot --out reports` changed every
`study_SYN-*.json` card (the committed copies lacked the
`publication_evidence` provenance key the extractor has emitted since the
initial import) and produced none of the ten unsuffixed `dataset_SYN-*.json`
cards tracked since `afb5eb9`. A reviewer diffing a fresh run against the
repository would have concluded the pipeline is not reproducible. The cards
were regenerated and the legacy files removed (nothing referenced them). This
was verified not to be an environment effect (§1, reproducibility).

### 2.8–2.10 Smaller correctness fixes

- `choose_transform` held `{("mmol/l","mg/dl"), ("mmol/l","mg/dl")}` and applied
  glucose's 18.0182 factor to any variable with that unit pair. Conversions
  are now keyed by common variable; a non-glucose analyte with that pair routes
  to review.
- `gender` is a listed synonym of `sex`. The mapping is now capped at 0.78 with
  the evidence "Gender and sex are distinct constructs; confirm whether the
  source variable recorded biological sex or gender identity", and the review
  packet asks exactly that instead of "confidence insufficient". This is the
  only change that moved a committed artifact (one crosswalk row; statuses and
  benchmark metrics unchanged).
- The quality rationale tested `!= "unknown"` while the subscores used the
  three-value unreported set, so a `not_reported` platform was scored as
  unknown and described as reported; the recommender gave it +0.01. One
  shared set now.

## 3. Findings documented, not changed

### 3.1 Dataset-readiness scoring has no scope or availability gate (option A applied after review)

The two benchmark disagreements are not noise; they are the scorer's design:

| Study | Expert | Predicted | Why |
| --- | --- | --- | --- |
| SYN-ANIMAL-MET (rat muscle) | 0.20 | 0.688 | `human` only adds 0.2 to design rigor; nothing else penalizes a non-human study, so it outscores SYN-OMICS-GEN (human, 1200 participants). The recommender *excludes* this study as out of scope on the same fixtures. |
| SYN-EXER-NODATA (no accession, metadata, codebook or data) | 0.33 | 0.484 | Modality subscores have floors of 0.25–0.35 when absent and full credit when present regardless of whether any data exist; CPET alone contributes 0.085. |

Two principled options, neither applied because either changes published
numbers, needs a `rule_set_version` bump, and the gold set has ten cases so
any tuning risks fitting to it:

- **A. Scope gate, as in MoTrPAC alignment.** Add `scope_status`
  (`in_scope_human` / `out_of_scope_non_human` / `human_status_unknown`) to
  `QualityScore`; report the numeric score only for in-scope studies and add
  `scope_status` to the gold. This makes the scorer consistent with the
  recommender and the alignment tier without inventing a cap.
- **B. Availability gate.** Multiply the modality subscores by a
  data-availability factor derived from `has_data_files` / restricted-with-
  metadata status, so a mirage cannot collect modality credit. This is
  consistent with the non-negotiable that a missing codebook is scientific
  risk, not a formatting issue.

Recommendation: A first (it is a labeling change, not a re-weighting), then
decide B with the expert who wrote the gold scores.

**Applied (scoring rule set 0.3.0, benchmark rule set 0.3.0).** Option A is
implemented as described: `QualityScore.scope_status` is derived from the study
card's three-valued `human` evidence; a documented non-human study's
`overall_score` is `null` with subscores retained and a rationale line; an
undocumented status keeps a triage score and is flagged. The gold fixture
declares `SYN-ANIMAL-MET` out of scope (the expert's 0.20 encoded that
judgement); the numeric metric is now 8/9 = 0.889 over gold studies not
declared out of scope, and `scope_status_accuracy` is 10/10. A withheld
prediction is accepted by the benchmark only for a declared out-of-scope row,
so a missing number can never masquerade as a scope decision. Option B remains
open: `SYN-EXER-NODATA` (0.484 vs 0.33) is the one numeric disagreement left.

### 3.2 MoTrPAC alignment credits documented absence only for genetics

`align_one` counts "genetics available or documented absent" as met, but CPET,
body composition and diet are met only when present. Either the
documented-absent rule should apply to every optional modality or the
asymmetry should be stated in the alignment rationale.

### 3.3 Minimum pair count and pair counts in cached tables

`scripts/volcano_compare.py` computes a paired t-test whenever at least three
complete pairs exist (df = 2). That is defensible for a coverage scan but
produces unstable p-values at the low end. `n_pairs` is carried in the scan
lane and in `compute_mw_volcano_stats`, but `volcano_human_ST004303.csv` has no
pair-count column, so its 266 points cannot be filtered by support. Suggest
writing `n_pairs` into every cached volcano table and flagging features below a
declared minimum.

### 3.4 Reconstructed confidence intervals

`render_lacphe_report.paired_ci` recovers the SE from `|effect| / t⁻¹(1−p/2, df)`.
That is exact under the paired-t model the scan lane used, and the forest-plot
footer says so, but the headline sentence and the stratum table present
"95% CI" without the word "reconstructed". A four-word edit.

### 3.5 Provenance and design caveats now written to the manifest

- The rat 8-week table has no retrieval record in `volcano_provenance.json`
  (human mode only); it was committed in `afb5eb9` with no request log. The
  manifest records `retrieval_provenance_not_recorded` and names the producing
  code path.
- ST004303's paired contrast pools the MIE and SIE intensity arms as retrieved,
  and 1P/4P are read as pre/post from the `Time` factor without protocol
  verification.
- `refmet_annotations.csv` still has no RefMet release; 30 of 266, 988 of
  1657, and 756 of 1056 features per stratum are unmatched by exact name. The
  match rate is a property of MoTrPAC's untargeted naming, not a matching-
  column bug (the annotation file has no synonym column).

### 3.6 Environment

The project `.venv` lacks `pydantic`, `pyarrow` and `pytest`, so the suite ran
on the `_compat` fallback and the README's `python -m pytest` path is
unavailable here; `python -m unittest discover` is what works. Outputs are
byte-identical either way (verified), but the documented install is
`pip install -e ".[dev,plotting]"` and CI runs with it. The readiness JSON does
not record the interpreter or whether `pydantic`/`jsonschema` were importable;
recording both would make "282 passed" comparable across machines.

### 3.7 Already-known items, unchanged

MoTrPAC API key in git history (rotation is the owner's call); 25 of 29
`data/live` provenance files without a licence field; no DOI or tag;
`docs/lawrence_comments_evaluation.md` records the 282-test count as of its
date. Seven `.pptx` decks are untracked under `outputs/`; whether to track them
is an authoring decision, not a scientific one.

## 4. Verification record

```
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests   # 288 OK
.venv/bin/ruff check src tests scripts                           # clean
PYTHONPATH=src .venv/bin/python scripts/evaluate_scientific_readiness.py  # pass, 288
PYTHONPATH=src .venv/bin/python -m metabotyping_agentic.cli run-pilot --out reports
PYTHONPATH=src .venv/bin/python scripts/render_exercise_studies_refmet_volcanoes.py
.venv/bin/python scripts/screen_mw_exercise_study_titles.py
```

Artifacts that changed and why (including the scope gate): `data/extracted/quality_scores.json`,
`reports/aim3_evaluation_report.md`, `reports/benchmark_*`,
`data/examples/expert_quality_scores.csv`, `reports/unseen_cohort_generalization/{quality_scores.json,cohort_run_manifest.json}`
(scope gate, §3.1); `data/extracted/crosswalk.{csv,json}`,
`data/review/*.csv`, `reports/aim2_harmonization_report.md`,
`reports/human_review_packet.md` (gender→sex caveat);
`reports/benchmark_{manifest.json,report.md}` (input hashes only);
`data/extracted/metadata_cards/study_*.json`, `data/extracted/study_cards.json`
(regenerated; ten legacy dataset cards removed);
`docs/scientific_readiness_{report.md,results.json}` (288 tests);
`reports_live/exercise_studies/*` (re-rendered per §2.1–2.5).

## 5. Suggested order of next work

1. Decide §3.1 option B (availability gate) with the gold-score author; the
   scope gate is applied.
2. Record retrieval provenance for the rat table by re-fetching it through the
   allowlisted lane, or keep it labeled unverified.
3. Write `n_pairs` into every cached volcano table (§3.3).
4. Reinstall the venv from `pyproject.toml` and record dependency state in the
   readiness JSON (§3.6).
5. Apply documented-absence symmetrically in MoTrPAC alignment (§3.2).
