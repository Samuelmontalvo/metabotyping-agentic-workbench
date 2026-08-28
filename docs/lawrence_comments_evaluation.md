# Lawrence-comments evaluation

This ledger records the work requested after the 2026-08-27 meeting. It separates
implemented software from the strength of the scientific evidence: a workflow can
be complete while external or clinical validation remains partial or blocked.

## Action-item status

| Action item | Implementation status | Evidence status | Evidence and remaining work |
| --- | --- | --- | --- |
| Commit between feature changes | **Done** | Auditable branch history | Work is isolated on `lawrence-comments`; cohort portability, provenance hardening, Hardik comparison, medication classification, MoTrPAC refresh, the biomarker directional check, its evidence/numerical hardening, and final evaluation are checkpointed separately. |
| Reproduce a known biomarker-paper result (Goal 1) | **Implemented with a narrower claim** | **Partial** | The Lac-Phe case asks whether a repository-derived Collectionpoint After-versus-Before contrast points in the paper-reported direction. It is explicitly `post_hoc_repository_after_vs_before_directional_check`: the raw factor/codebook is not bound, exercise timing is therefore unverified, cohort independence is not established, selection was post hoc, and the paper's analysis was not rerun. This is not an established reproduction or corroboration. |
| Build a common-medication classifier (Goal 2) | **Implemented for statin exposure** | **Synthetic only** | A deterministic diagonal-LDA classifier is trained and scored on labeled, cohort-disjoint synthetic files. It is not clinically validated and must not be used to infer medication exposure in a person. |
| Generalize to unseen cohorts (Goal 3) | **Implemented at the input-contract level** | **Synthetic only** | A checksummed bundle with two held-out synthetic studies runs without pilot-fixture fallback. This demonstrates interface portability, not external human-cohort validity. |
| Create cold, labeled train/test files | **Done** | Reproducible synthetic fixture | The split contains 48 training samples from two cohorts and 24 test samples from a disjoint third cohort. The manifest binds train, test, and feature catalog by SHA-256 and requires disjoint sample IDs, cohort IDs, and declared feature vectors. |
| Compare against Hardik's harmonization results | **Comparator implemented** | **Blocked on reference** | The comparator requires the exact `(source_study, source_variable)` universe. Because `data/external/hardik_harmonization_results.csv` is not present, the committed result is `blocked_missing_reference` and every agreement metric is null. No curator decisions were invented. |
| Complete agent evaluation | **Implemented** | **Offline; external independence unestablished** | The structural audit covers 25 paired skills, 23 canonical agents, and 2 deprecated aliases. The behavioral readiness gate passes 282/282 tests over synthetic fixtures and checksum-bound cached public artifacts and owns every one of the 29 discovered test modules exactly once. Hidden-gold agent execution, independent agent-system comparison, and external-cohort validation remain outstanding. |
| Attempt MoTrPAC evaluation | **Metadata-readiness refresh completed** | **Partial** | ST004303 scores 0.636 (`low`) and ST003807 scores 0.545 (`low`). Unknown genetics evidence remains unknown. These scores assess planning metadata, not protocol equivalence or biological replication. |

## Recorded results

### Goal 1: Lac-Phe repository After-versus-Before directional check

The case uses the cached Metabolomics Workbench ST003662/AN006016 evidence bundle
and validates the declared analysis row, MetStat measurement locator,
assay/platform metadata, sample matrix, input hashes, evidence source, and
licence fields before analysis. It separately binds the raw and screened
literature records; paper-direction support must appear in retrieved
title/abstract text, and the query string never counts as evidence. Cached source
p/FDR values are reported as not independently recomputed, while group means are
recomputed from the bound values and reconciled with the cached row.

Among 137 queried rows, 116 had complete positive Before/After values and 92 were
higher After. Mean paired log2 change was 1.1586026041398587, corresponding to a
geometric-mean fold change of 2.2324109131516057; the exact two-sided sign-test
p-value was 1.4181822700488305e-10. The numerical direction is consistent with
the paper-reported direction, but only as a hypothesis-generating repository
check. The historical cached provenance calls the contrast post-exercise versus
pre-exercise; because this case binds no raw factor/codebook snapshot, that
timing interpretation is not independently verified. Metabolite identity,
whole-blood matrix/method compatibility, timing, dataset independence, and the
post-hoc selection boundary remain explicit review gates. Twenty-one incomplete
or nonpositive pairs are excluded, and no missingness sensitivity analysis is
claimed.

Tracked evidence:

- `reports_live/biomarker_reproduction/lacphe_li_2022/report.md`
- `reports_live/biomarker_reproduction/lacphe_li_2022/result.json`
- `reports_live/biomarker_reproduction/lacphe_li_2022/manifest.json`

### Goal 2: synthetic statin classifier

The cold test contains 12 observed positives and 12 observed negatives. All 24
were scored and none abstained in the committed fixture: TP=12, TN=12, FP=0,
FN=0; accuracy, balanced accuracy, positive precision, positive recall, F1, and
AUROC are all 1.0. The training-majority baseline accuracy is 0.5. These perfect
numbers are expected from an intentionally separable synthetic fixture and are
not an estimate of human-cohort performance, calibration, confounding, adherence,
dose response, or medication-combination effects.

Tracked evidence:

- `data/examples/medication_classifier/split_manifest.json`
- `reports/medication_classifier/model_card.md`
- `reports/medication_classifier/metrics.json`
- `reports/medication_classifier/run_manifest.json`

### Goal 3: unseen-cohort bundle

The committed run reports `synthetic_interface_generalization_pass` for two
synthetic studies and seven variables. All declared hashes and publication/
repository universes match, no built-in fallback was used, and three uncertain
crosswalk rows remain routed to human review. `external_validation` remains
false by design.

Tracked evidence:

- `data/examples/unseen_cohort/manifest.json`
- `reports/unseen_cohort_generalization/cohort_generalization_report.md`
- `reports/unseen_cohort_generalization/cohort_run_manifest.json`

### Hardik and MoTrPAC boundaries

The Hardik artifact is a valid blocked evaluation, not a failed attempt to make
up a score. Once the reference is supplied, the same command will first enforce
an exact evaluation universe and then calculate agreement with explicit
denominators.

The MoTrPAC artifacts are likewise intentionally narrow: they inventory metadata
needed to plan comparison and preserve unknown evidence states. They do not fit
MoTrPAC models from raw data or demonstrate replication of a MoTrPAC biological
result.

## Verification and commit checkpoints

- Strict behavioral readiness: 282 passed; 0 failed, errored, skipped, expected
  failures, or unexpected successes.
- Gate coverage: all 29 discovered test modules have exactly one scientific-risk
  owner; adding an unmapped passing module now fails the gate.
- Skill/agent contract audit: 25 paired skills, 23 paired canonical agents, 2
  paired deprecated aliases, and 0 inventory issues; all reported scores are 1.0.
- Fresh Goal 1, Goal 2, Goal 3, and MoTrPAC runs reproduce their committed
  artifacts byte-for-byte.

Feature checkpoints on `lawrence-comments`:

- `b0b8a5b` — explicit unseen-cohort bundle workflow
- `7ef46ee` — unseen-cohort provenance boundary hardening
- `f596277` — review-gated Hardik harmonization comparator
- `806e1b8` — cold synthetic statin classifier evaluation
- `6eed950` — live MoTrPAC metadata-readiness refresh
- `f5bcf9c` — initial Lac-Phe directional benchmark
- `9031df7` — biomarker evidence and numerical-boundary hardening
- `bfb27d3` — repository-dataset label clarification

## Release decision

The branch is suitable for review as an offline, provenance-preserving evaluation
scaffold. It is **not** evidence that the statin classifier is clinically useful,
that the workbench generalizes to independent human cohorts, that the original
Lac-Phe paper was exactly reproduced, or that agreement with Hardik has been
measured. Those claims require the missing independent datasets/reference and
human adjudication.
