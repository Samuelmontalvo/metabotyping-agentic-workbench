# Can we train a classifier that predicts species from Metabolomics Workbench metabolite data?

**Status:** feasibility assessment — advisory, requires human review before any lane is built
**Date:** 2026-08-21
**Evidence:** read-only probe of the public Metabolomics Workbench (MW) REST API + local repo audit
**Scope:** retrieval and feasibility appraisal only. No harmonization mapping is approved by this document.

---

## Short answer

Yes, trivially — and the trivial version is a mirage. Species in MW is a **study-level constant**
(4,765 of 4,772 studies with a species record list exactly one organism; only 7, or 0.15%, list more
than one), so a sample-level classifier's label is a deterministic function of study identity, and any
high accuracy it reports is study/lab/platform recognition wearing a species label. The honest version
— cross-study, out-of-lab species identification — is blocked by a measured constraint that is much
harder than the modeling: **of 3,936 distinct RefMet names across the 32 probed studies that expose a
named metabolite list, zero appear in all 32, and only five (Alanine, Arginine, Glutamine, Methionine,
Tryptophan) appear in ≥50% of studies of every species.** We measured the empirical consequence
directly: a single feature carrying no biology whatsoever — the order of magnitude of the numbers in
the deposited file — separates 11 of 12 probed studies by species, while every biologically motivated
ratio feature we computed *overlaps* across species. The three-class framing also hides a second
problem: human-versus-rodent has gene-loss-grade markers, but **rat-versus-mouse has none** — no
uricase, *Gulo*, *Cyp2c70* or glucocorticoid difference to find — so a headline three-class number
would be carried almost entirely by one boundary. Recommendation: do not build the classifier as
asked. Build the confound audit and publish the coverage census as a reusability ceiling for MW.

---

## What the data actually looks like

One call to `/rest/study/study_id/ST/species` returns species for all 4,772 studies that carry a
species record, across 481 distinct Latin names. The label is free; a correct classifier therefore has
**zero information gain** over a metadata lookup.

| Species | Studies |
|---|---|
| *Homo sapiens* | 1,854 |
| *Mus musculus* | 1,463 |
| *Rattus norvegicus* | 257 |
| *Escherichia coli* | 54 |
| *Plasmodium falciparum* | 53 |
| *Drosophila melanogaster* | 32 |
| all others (475 names) | ≤ 27 each |

Only human, mouse and rat have enough studies to support a mammalian three-class problem — the
14th-largest class is already at 14 studies, so **the 481-class question is not on the table; this is
silently a 3-class problem.** Platform composition is itself species-dependent, and two strata contain
**zero** rat studies (MS direct-infusion 37/31/0, CE-MS 9/16/0), so platform alone partially determines
"not rat". Specimen
type is heavily confounded with species — the classifier's easiest route to the label is the tissue,
not the chemistry:

| Sample source | Human | Mouse | Rat | Human share |
|---|---|---|---|---|
| Blood | 618 | 259 | 51 | 67% |
| Cultured cells | 373 | 85 | 14 | 79% |
| Urine | 115 | 22 | 5 | 81% |
| Liver | 18 | 181 | 24 | 8% |
| Brain | 16 | 90 | 17 | 13% |
| Muscle | 19 | 75 | 17 | 17% |
| Kidney | 5 | 36 | 17 | 9% |

**The design cell.** The only cell in which the three species are comparably represented on a common
specimen and platform is `Sample source ∈ {Blood, Plasma, Serum, Whole blood} AND analysis_type =
LC-MS`: **458 human / 213 mouse / 44 rat studies**, 124,580 / 11,880 / 4,135 samples (140,595 total,
88.6% human; one human study alone contributes 11,560). All numbers below refer to this cell.

---

## Why the naive classifier is a mirage

Because species is nested within study, every study-level property is a perfect proxy for the label.
A pooled sample-level classifier can reach the label through any of these channels without touching
species biology:

1. **Study identity** — recoverable from the feature-panel membership vector alone (see next section).
2. **Numeric magnitude of the deposited values** — measured below; the single strongest channel.
3. **Deposited-data processing convention** — whether the matrix is raw response or median-scaled.
4. **Units string** — 749 distinct unit strings across human/mouse/rat analyses. (The per-analysis
   frequency distribution is unmeasured, so this field cannot be described as effectively controlled
   *or* as uncontrolled at population scale — only as not standardized.)
5. **Instrument, chromatography, ion mode** — per-analysis metadata that travels with the study.
6. **Institute** — rat is concentrated: 61 institutes, top-5 share 55.3%, versus 439 institutes and
   22.5% for human. Critically, institute is partially **crossed** with species rather than nested —
   Michigan, Mayo and Emory are top-five for both rat and human — which is the argument for
   institute-blocked validation rather than i.i.d. inference.
7. **Deposit size** — one human study contributes 11,560 of 140,595 samples (8.2%), so held-out
   prevalence swings fold to fold and accuracy-against-prevalence is estimand-free in either direction.
8. **Specimen** — the table above.
9. **Missingness pattern** — which cells are null is a study fingerprint.
10. **Platform** — MS direct-infusion and CE-MS contain zero rat studies.

A correction worth stating precisely, because it is easy to get backwards: 99.9% sample-level accuracy
here is **not** below baseline. The majority-class baseline is 88.6% and prevalence-weighted guessing
is 79.3%, so 99.9% is a ~99% error reduction, κ ≈ 0.99. The defect is **estimand mismatch and label
leakage, not baseline shortfall** — the number is large and answers a question nobody asked.

The correct estimand is *cross-study, out-of-lab, panel-fixed species identification with the study as
the unit of analysis*. That makes **n = 715 studies, not 140,595 samples** — and n = 32 studies if
restricted to those exposing a named metabolite list. At n = 44 rat studies, leave-one-study-out recall
is quantized in 2.27% steps; a flawless 44/44 yields a Wilson 95% CI of [0.920, 1.000] and an exact
one-sided 95% lower bound of 0.934. In the named-list design, 11/11 gives only [0.741, 1.000]. **No
honest sentence about rat recall can exceed "at least 93%", and realistically "at least 74%."**

---

## The binding constraint: there is almost no shared feature space

We sampled 55 studies from the design cell (20 human / 20 mouse / 15 rat, largest-first,
de-duplicated by institute) and pulled each one's named-metabolite list.

- **23 of 55 returned an empty list.** Untargeted studies expose no named features through this
  endpoint. Under this project's rules that is a coverage gap requiring escalation, not a zero.
- The 32 survivors (7 human / 14 mouse / 11 rat) span **3,936 distinct RefMet names**.

| Shared-feature threshold | Metabolites |
|---|---|
| present in all 32 studies | **0** |
| present in ≥ 24/32 | **0** |
| present in ≥ 16/32 | 13 |
| present in ≥ 8/32 | 120 |
| in ≥ 80% of studies of *every* species | **0** |
| in ≥ 60% of *every* species | **0** |
| in ≥ 50% of *every* species | **5** — Alanine, Arginine, Glutamine, Methionine, Tryptophan |
| in ≥ 40% of *every* species | 13 |
| in ≥ 30% of *every* species | 25 |

**RefMet name resolution is not the bottleneck.** The median mapped-to-raw name ratio is 0.96 and no
study failed to map. The bottleneck is genuine **assay panel heterogeneity**: different labs measure
different compounds. An honestly-observed dense design matrix is about five columns wide. Anything
wider is built by treating "not in this study's panel" as a value — the 0-imputation mirage.

And the five survivors are the worst possible features for this task: proteinogenic amino acids are the
most homeostatically buffered, least species-discriminative metabolite class, differing across
human/mouse/rat by roughly 1.5–3× and dominated within species by fasting duration and protein intake.
They survived *because* they are platform-ubiquitous, which is the anti-correlate of species specificity.

---

## What signal genuinely exists — and why we could not reach it

The biology is real and, in places, mechanistically hard. Human-versus-rodent differences include
hominoid *UOX* (uricase) pseudogenization (urate several-fold higher in humans; allantoin an enzymatic
end product in rodents but mainly a non-enzymatic ROS product in humans), *Cyp2c70*-dependent
muricholic acids (rodent), the bile-acid amidation switch (glycine-dominant human versus
taurine-dominant mouse), **phenylacetate conjugation — phenylacetylglutamine (PAGln) in primates
versus phenylacetylglycine (PAGly) in rodents**, cortisol versus corticosterone as the dominant
glucocorticoid, *GULO* pseudogenization, and higher rodent plasma taurine. These are far larger than
anything in the shared amino-acid core.

**But the three-class problem is really two very different problems.** Human-versus-rodent has
gene-loss-grade markers. **Rat-versus-mouse has none** — both are uricase-positive, *Gulo*-positive,
*Cyp2c70*-positive and corticosterone-dominant. That boundary is graded and compositional only
(bile-acid pool composition and α/β-MCA proportion, the far more extreme mouse hepatic *Fmo3* sexual
dimorphism driving bimodal plasma TMAO, absence of a gallbladder in rats altering postprandial
bile-acid kinetics). Any headline three-class accuracy will be carried almost entirely by the
human/rodent split while hiding a near-chance rat/mouse split — which is exactly what the metadata-only
baseline below already shows.

Three caveats keep even the good markers from being presence/absence-grade. **Identity:** α-/β-muricholic,
hyocholic, ursocholic and cholic acid are all C₂₄H₄₀O₅ with near-identical MS1/MS2, so untargeted
annotations are MSI level 2–3; muricholic/hyocholic series also occur in pig and human neonatal bile,
and *Cyp2c70*-KO or strain/age variation produces MCA-negative mice. **Biology:** PAGln/PAGly are
gut-microbial and vanish in germ-free or antibiotic arms — a design over-represented in mouse deposits;
human hypouricemia or urate-lowering therapy puts human samples inside the rodent urate range; bile-acid
sulfation is human-*enriched*, not human-unique (mouse *Sult2a8* is a bile-acid 7α-sulfotransferase).
**Preanalytics:** ascorbate oxidizes without acid-stabilized collection, so its absence from a panel is
usually a collection artifact rather than a species fact.

The inversion is the whole problem: **the features with the strongest species biology are the least
shared.** Of 32 studies, urate appears in 14, allantoin in 9, taurocholate in 9, glycocholate in 8,
muricholic acid in 3, and ascorbate in 2 (mouse only) — though for ascorbate specifically, absence is more likely
preanalytical than biological.

We tested it anyway. Twelve studies (4 human / 5 mouse / 3 rat) measure ≥8 of a 15-marker species
panel. We pulled their full sample-level matrices from `/rest/study/study_id/<ID>/data` and computed
**within-analysis pairwise log₂ ratios**, which cancel any per-sample multiplicative scale factor —
the only affine-invariant representation available. Study-level medians:

| Ratio | Human | Mouse | Rat | Clean split? |
|---|---|---|---|---|
| log₂(urate / allantoin) | +0.43 (n=2) | −0.27 (n=4) | −2.16 (n=2) | no — overlapping |
| log₂(glycocholate / taurocholate) | +0.46 (n=3) | −4.47 (n=1) | +1.33 (n=1) | no — overlapping |
| log₂(creatine / creatinine) | −0.02 (n=3) | +2.49 (n=5) | +1.60 (n=3) | no — overlapping |
| log₂(taurine / ornithine) | −0.05 (n=3) | +4.19 (n=2) | +1.80 (n=2) | no — overlapping |
| log₂(alanine / glutamine) *(control)* | −0.11 (n=4) | −0.37 (n=4) | 0.00 (n=3) | no (expected) |

Every biologically motivated ratio overlaps. **Two measurements explain why**, and both are new
findings from this probe:

**1. Deposit-processing convention is itself confounded with species.** We tested whether each
deposited matrix is already per-*feature* normalized by measuring the interquartile spread of
per-feature medians. All four human studies come back per-feature median-scaled (IQR ratios 1.01–1.58)
except the single µM study; every rodent study deposits raw response (spreads of 12× to 71,000×).
Per-feature median scaling **mathematically annihilates between-metabolite ratio information** — so the
one scale-invariant escape hatch is unavailable in exactly the class that needs it.

**2. The magnitude of the numbers is the leak.** log₁₀ of the median positive deposited value:

| Species | Studies | log₁₀(median value) range |
|---|---|---|
| human | 4 | −0.04 … +0.95 |
| mouse | 5 | −0.03 … +6.93 |
| rat | 3 | +4.58 … +6.25 |

A single threshold at log₁₀ = 1.0 classifies **11 of 12 studies correctly** (4/4 human, 7/8 rodent;
one mouse study overlaps) with zero metabolite biology involved. This is the mirage in its most literal
form: the exponent tells you the species.

Where the data *are* calibrated, the biology shows up exactly as predicted — ST001669 (human, µmol/L)
gives log₂(glyco/tauro-cholate) = +2.82 and ST002881 (mouse) gives −4.47, a 7.3 log₂ gap in the
mechanistically correct direction. But **only 1 of these 12 studies reports true concentrations.** That
is the finding: the signal is real and the corpus as deposited cannot carry it.

---

## The benchmark any metabolite model must beat

The assessments flagged this as unmeasured, so we measured it. Categorical naive Bayes on **metadata
only — no metabolite values at all** — under leave-one-institute-out CV across 590 institutes and 3,517
human/mouse/rat studies:

| Metadata feature set | Accuracy | Balanced acc. | Recall h / m / r |
|---|---|---|---|
| majority class (*human*) | 0.517 | 0.333 | 1.00 / 0.00 / 0.00 |
| specimen only | 0.668 | 0.505 | 0.849 / 0.536 / 0.128 |
| + platform | 0.666 | 0.504 | 0.842 / 0.541 / 0.128 |
| + units string | 0.653 | 0.496 | 0.817 / 0.539 / 0.132 |
| + instrument / chromatography / ion mode | 0.647 | 0.498 | 0.803 / 0.539 / 0.152 |
| + institute | 0.623 | **0.511** | 0.763 / 0.513 / 0.257 |

So: **balanced accuracy 0.51 with rat recall 0.13–0.26, from metadata alone.** This is the
pre-registered bar. A metabolite-based classifier that does not clear 0.51 balanced accuracy under
leave-one-institute-out has demonstrated nothing, and one that clears it only by a margin inside its
own confidence interval may not be described as using metabolite biology.

---

## The honest study design, if it is run anyway

Steps 1–3 are measurement deliverables in their own right. If they fail, the study stops there and
reports a coverage gap — not a null result.

1. **Cohort.** Design cell as defined; record the exact drop count at every filter step, no silent
   truncation. Pre-register sensitivity cells (rat LC-MS all specimens = 218 studies; all rat = 257;
   rat blood any platform = 51) and price the precision-versus-confounding trade explicitly.
2. **Measure retrievability before modeling.** Pull `/metabolites` for all 715 studies and publish the
   per-study named-list yield, the in-cell institute distribution, the units-string frequency
   distribution, and how many of the 7 multi-organism studies fall inside the cell. All four are
   currently **unmeasured**; the 23/55 empty rate is a largest-first sample, not a population rate.
3. **Eligibility gate.** Admit a study only if it reports absolute concentrations **or** passes the
   per-feature-normalization test above. On the probed sample this admits roughly 8 of 12 studies and
   near-zero human studies — which is itself the result.
4. **Two disjoint, pre-registered arms.**
   - **Arm A (biology).** The targeted species panel plus the ≥40% shared tier (13 names), with
     per-study coverage recorded. Isomer-ambiguous identities (muricholic series) enter as *unresolved
     identity* and are escalated, not scored.
   - **Arm B (mirage).** Metadata and fingerprint only — binary RefMet name vector, units string,
     analysis type, ion mode, institute, sample count, deposited-value magnitude. **No abundances.**
     Arm B is the leakage ceiling, and the A-minus-B margin is the single most informative number in
     the study.
5. **Representation.** Within-sample compositional coordinates: log then CLR or pairwise log-ratios.
   On the five-name shared basis, exactly four log-ratio coordinates are provably invariant to a
   study-level scalar. Never jointly batch-correct across studies. Never use per-study z-scoring as the
   primary representation — because species is nested in study, per-study centering deletes the
   between-study mean shift, which *is* the species mean shift; and it is degenerate anyway where
   studies have 1–3 samples, which occurs in this cell. Note the deployment consequence: any
   representation requiring per-study standardization at inference is **transductive** and cannot
   classify a single unseen sample at all.
6. **The nuisance that does not cancel.** A purely multiplicative per-*sample* or per-*study* gain
   cancels exactly under log-ratio coordinates. What does not cancel is the **analysis × feature
   interaction** — analyte-specific response factor, ion suppression, recovery, derivatisation bias —
   which is a per-study constant on the log-ratio scale and therefore aliased with species. This is the
   formal reason the empirical ratio table above overlaps: the ratios cancelled the easy nuisance and
   were defeated by the hard one.
7. **Missingness.** Tri-state observed / absent-from-panel / unmeasured. Absent is never 0, never
   imputed, never LOD-filled.
8. **Evaluation.** Study cluster as the unit of analysis; effective n ≤ 715, never 140,595. Report
   **both** leave-one-study-out and leave-one-institute-out, with institute-blocked as primary because
   institute is partially crossed with species.
9. **Negative controls, all in the same table as the headline.** Arm B; metadata-only (0.511 measured
   above); units-string only; panel-membership only; deposited-magnitude only (11/12 measured above);
   per-study z-scored replicate of Arm A (a collapse here is the *expected and informative* result);
   and a label-permutation null of ≥1,000 draws **stratified within institute × platform**.
10. **Reference baselines.** Primary comparison is 3-class chance at 33.3% balanced accuracy. Report
    study-level majority 458/715 = 64.1% and stratified 50.3%; sample-level 88.6% and 79.3% are
    prevalence-dependent references only. Always state the rat fold count actually used.
11. **Pre-registered falsification.** The classifier is declared a mirage unless *all* hold: (i) the
    Arm A minus Arm B margin has a leave-one-institute-out interval excluding zero; (ii) the margin
    survives specimen-matched *and* platform-matched subcells; (iii) permutation p < 0.01 under
    institute-stratified permutation; (iv) rat recall's exact one-sided 95% lower bound exceeds the
    64.1% study-level majority; (v) at least one mechanistic panel marker carries non-trivial weight
    with MSI-level identity evidence. Any failure is published as a finding about MW's deposition
    structure. Report the rat/mouse split separately from human/rodent — a three-class headline hides a
    near-chance rat/mouse boundary that has no gene-loss marker to find.
12. **The allowed final claim.** Best case, all 44 rat studies usable and every rat fold correct:
    *"Under leave-one-institute-out grouped CV within the blood + LC-MS design cell (715 study clusters;
    458/213/44), macro-recall was X; rat recall 44/44, exact one-sided 95% lower bound 0.934, two-sided
    Wilson width 0.080, grain 1/44 = 2.27%, rule-of-three miss ceiling 6.8%."* Realistic case, at the
    measured named-list yield of 11 usable rat folds: grain 9.1%, Wilson width 0.259 at 11/11, exact
    one-sided lower bound 0.762; at 10/11 the interval is [0.623, 0.984]. Institute clustering widens
    all of these by an amount not computable until the in-cell institute count is measured. Unless
    criterion (i) is met, the finding must be worded *"distinguishes study/platform/site contexts that
    happen to differ in species"* — never as a species signature. Anything quoted to a tenth of a
    percent at sample level is false precision.

---

## What it would take in this repo

**The framework already answers this question in code.** `_assess_quantitative`
([assay_harmonization.py:777-806](src/metabotyping_agentic/harmonization/assay_harmonization.py:777))
returns `non_absolute_values_not_poolable` — *"values are assay-specific; direct raw-value pooling is
prohibited"* — with status `NON_COMBINABLE` and confidence 0.10 for any non-absolute pair. Since 11 of
12 probed studies report non-absolute values, `evaluate_assay_pair` blocks the pooled matrix today,
without a new agent. The escape hatch the code offers, `STUDY_SPECIFIC_EFFECTS_META_ANALYSIS`
([assay_harmonization.py:1082](src/metabotyping_agentic/harmonization/assay_harmonization.py:1082)), is
unavailable here: there is no within-study species contrast to meta-analyze in 99.85% of MW.

**Governance — proposals requiring human approval, not changes to make unilaterally:**

- [CLAUDE.md:51-52](CLAUDE.md:51) — *"persists sample-level values for the queried metabolite only
  (never the full abundance matrix)"*. This is descriptive prose scoped to the single-metabolite scan
  lane, not a Non-Negotiable, and the scan lane already *fetches* `/data` in full. A classifier lane
  still needs an explicit multi-column persistence rule; the safest form is a **pre-declared,
  human-approved RefMet column allowlist** rather than lifting the sentence.
- [CLAUDE.md:19](CLAUDE.md:19) + [tests/test_network_boundary.py](tests/test_network_boundary.py) — a
  new networked module must be added to the AST allowlist. The machine-enforced test is
  `test_only_allowlisted_modules_import_network_clients`; a second test asserts each allowlisted path
  appears in CLAUDE.md, so code and doc must change together. `AGENTS.md` is not read by any test and
  can drift silently.
- [CLAUDE.md:12](CLAUDE.md:12) / [AGENTS.md](AGENTS.md) — a RefMet-keyed cross-study join is exactly the
  name-based merge forbidden without approved mappings. The matrix builder must refuse to run without a
  signed-off crosswalk artifact.
- [source_registry.py](src/metabotyping_agentic/knowledge/source_registry.py) — 27 lanes today, none
  predictive. An unregistered lane is a blocking escalation.

**Dependencies.** Correcting an earlier statement in this session: `.venv/bin/python` (3.14.4)
already has numpy 2.4.6, scipy 1.17.1, pandas 3.0.3 and matplotlib 3.10.9. **Only scikit-learn is
missing.** Add an `ml` extra to [pyproject.toml](pyproject.toml) — never to base `dependencies` — and
keep every third-party ML import function-local or guarded, since `run-pilot` must keep running on a
bare interpreter.

**Modules**, following the existing allowlisted-retrieval / offline-analysis split:
`live_sources/mw_species_cohort.py` (networked; reuses `fetch_json`/`_records` rather than
re-implementing them) → `discovery/species_cohort.py` (design-cell filter) →
`harmonization/cross_study_matrix.py` (tri-state matrix, refuses without approved crosswalk) →
`evaluation/species_model.py` (grouped CV + negative controls) → `reports/render.py` extension.
CLI: `live-build-species-cohort`, `build-species-matrix`, `evaluate-species-model`, each with
`--dry-run` and `--seed`. Outputs to `data/live/species_classifier/<cell>/` and
`reports_live/species_classifier/`. Provenance must extend the existing scan-lane schema with
`cv_scheme`, `group_variable`, `seed`, `class_prevalence`, `per_class_recall`, `permutation_null`,
`negative_control_results`, and per-filter drop counts.

**Cost.** 4 bulk index calls + 1 `/metabolites` call per surviving study ≈ 719 requests, ~12 min at
1 req/s. Roughly 15 person-days, concentrated in the negative-control and tri-state-honesty machinery
— which is the only part that makes the result publishable.

---

## Agent and skill coverage

| Stage | Owner | Verdict |
|---|---|---|
| Cohort assembly | `repository-discovery`, `study-dataset-discovery` | covered |
| Design-cell definition | `define-inclusion-criteria` | partial (advisory only) |
| Feature identity resolution | `metabolite-identity-resolver` | covered |
| Comparability ruling | `assay-harmonization-skeptic` | covered — **and it blocks** |
| Matrix construction | — | **GAP** |
| Model fitting | — | **GAP** |
| Evaluation design | `statistical-estimand-and-synthesis-skeptic` | partial (advisory only) |
| Negative controls | — | **GAP** |
| Interpretation | `metadata-extraction-critic` | partial |
| Escalation | `human-review-packet` | covered |
| Model-card reporting | — | **GAP** |

The structural absence is a **predictive-modeling / leakage-audit role**. It is not forbidden — it is
unconsidered: `DomainReviewRole` ([review/models.py:21](src/metabotyping_agentic/review/models.py:21))
is a closed enum of four reviewer roles, `EXPECTED_CANONICAL_AGENT_NAMES`
([scripts/evaluate_skills.py:25](scripts/evaluate_skills.py:25)) a closed set of 22, and
`docs/agent_architecture_evaluation.md` §4 enumerates 23 archetypes — none containing any modeling,
prediction, classification or leakage concept.

**Which existing agent blocks the naive proposal.** `assay-harmonization-skeptic`
([.claude/agents/assay-harmonization-skeptic.md:10](.claude/agents/assay-harmonization-skeptic.md:10)):
*"never pool raw relative abundance or feature intensity across studies, jointly batch-correct studies,
convert censored values to zero, use unvalidated method bridges, or infer comparability from names or
correlations."* The naive design does four of those five.

---

## Verdict and recommendation

**Do not build the species classifier as asked.** It answers a question whose answer is already a free
metadata lookup, and the corpus cannot support the honest version: five shared metabolites, one
calibrated study in twelve, and a magnitude channel that reaches the label without biology.

**Build these instead**, in priority order:

1. **A species-detectability audit** over the 3,517 human/mouse/rat studies. Deliverable: the confound
   structure (species × institute × platform × units × specimen) plus the metadata-only baseline
   (0.511 balanced accuracy) — with the classifier repurposed as a **leakage instrument** that
   stress-tests the workbench's own harmonization claims. Publishable, and it needs no new governance.
2. **A cross-study reusability census** for MW: publish the 0-of-3,936 and 5-at-50% coverage numbers,
   the 42% empty-`/metabolites` rate, and the per-feature-normalization finding as a **ceiling
   statement on cross-study MW reuse**. This is a real methodological contribution and generalizes far
   beyond species.
3. **The better-posed scientific question.** Not *which species* — that is known — but **which
   perturbation responses are conserved across species.** Within-study effect sizes are
   affine-invariant, so they survive everything that defeats the classifier, and the repo's Lac-Phe
   cross-species lane already does exactly this. That is where the modeling effort belongs.

---

## Escalations for human review

- **Blocking:** no `predictive_modeling` lane exists in `source_registry.py`. An unregistered
  retrieval/analysis lane is a blocking escalation, not a usable capability.
- **Blocking:** cross-study RefMet join requires an approved crosswalk artifact
  ([CLAUDE.md:12](CLAUDE.md:12)); none exists for this cohort.
- **Blocking:** persisting a multi-feature sample-level matrix needs an explicit approved policy
  ([CLAUDE.md:51-52](CLAUDE.md:51)) or a pre-declared RefMet column allowlist.
- **Coverage gap:** 23 of 55 probed design-cell studies expose no named metabolite list. Cause
  (embargo, endpoint shape, untargeted-only deposition, genuine absence) is **unmeasured** and must be
  adjudicated before any denominator is quoted.
- **Mirage risk:** the deposited-magnitude channel classifies 11/12 studies with no biology. Any model
  report omitting this control is not reviewable.
- **Sampling limit:** the 32-study feature-space result and the 12-study empirical pilot come from a
  largest-first, institute-deduplicated sample, **not a random draw**. Population rates are unmeasured
  and these figures may not be quoted as corpus-wide.
- **Unmeasured:** MSI identification level per feature (the skeptic requires level 1 for raw pooling);
  the 0.96 RefMet-mapped ratio measures name resolution, not identification confidence.
- **Unmeasured:** whether MW's `species` field is curator-entered free text with synonym variants
  across 481 names — i.e. label noise in the outcome itself.
- **Unmeasured, and required before any interval is quoted:** the institute count *inside* the
  715-study design cell (institute clustering widens every CI by an uncomputable amount until this is
  known), the units-string frequency distribution per analysis, and whether any of the 7
  multi-organism studies fall inside the cell.
- **Identity risk:** the muricholic / hyocholic / ursocholic / cholic series are all C₂₄H₄₀O₅ with
  near-identical MS1/MS2. Untargeted annotations are MSI level 2–3 and must enter as *unresolved
  identity*, not as scored features — `assay-harmonization-skeptic` requires MSI level 1 for pooling.
- **Confound, not signal:** PAGln/PAGly are gut-microbial and absent in germ-free and antibiotic arms,
  which are over-represented in mouse deposits; ascorbate absence is usually preanalytical. Neither
  may be read as a species fact without the corresponding design metadata.
