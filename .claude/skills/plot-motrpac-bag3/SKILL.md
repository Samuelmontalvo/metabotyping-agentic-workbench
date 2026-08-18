---
name: plot-motrpac-bag3
description: Use when plotting BAG3 from MoTrPAC human PRECAWG and rat Data Hub sources, especially human Feature Trajectories from https://data-viz.motrpac-data.org/precawg/ and rat pass1b-06 gene-centric transcriptomics rows from https://motrpac-data.org/. Supports app-downloaded plots/data, saved public search API JSON, or local app-like exports; preserves provenance and routes inferred BAG3, species, group, tissue, assay, or timepoint evidence to review.
---

# Purpose
Create reviewable BAG3 plots from MoTrPAC sources. For human PRECAWG, reproduce Feature Trajectory plots that match the app style: grey facet strips for feature/tissue/assay, acute timepoint on the x-axis, log2 transformed value or log2 fold change on the y-axis, exercise-group trajectories with error bars, and point fill indicating adjusted p-value threshold. For rat pass1b-06, plot exact BAG3 gene-centric Data Hub rows as tissue-faceted timewise training effects while keeping the rat differential evidence separate from the human acute raw-value trajectory.

# Inputs
- Preferred live source: `https://data-viz.motrpac-data.org/precawg/`, Feature Trajectories tab.
- Preferred app configuration for the BAG3 example:
  - Tissue: `Muscle` or all relevant human tissues when requested.
  - Assay: `RNA-Seq` unless the user asks for another assay or all assays.
  - Identifier type: `Gene symbols`.
  - Gene: `BAG3`.
  - Feature ID: `ENSG00000151929.10` when available.
  - Feature value type: `Log2 raw value` to reproduce the screenshot; use `Log2 fold change` only when requested.
  - Group samples by: `Exercise group`.
  - Plot layout: `Linear`.
- App-downloaded plot data, when available, from the download icon or "data behind plot" export.
- Local app-like CSV/TSV/TXT exports with columns such as `feature_id`, `gene_symbol`, `tissue`, `assay`, `exercise_group`, `timepoint`, `log2_transformed_value`, `log2_raw_value`, `log2_fold_change`, `mean`, `se`, `adj_p_value`, or related schema variants.
- Differential-analysis tables with columns such as `contrast`, `logFC`, `log2fc`, `estimate`, `p_value`, `adj_p_value`, `tissue`, `omics`, `gene_symbol`, `feature_name`, `assay`, or related schema variants.
- Subject-level abundance tables with columns such as `subject_id`, `sample_id`, `exercise_group`, `timepoint`, `tissue`, `gene_symbol`, `abundance`, `expression`, `intensity`, or related schema variants.
- Optional provenance manifests that declare the PRECAWG app URL, selected controls, download date, MoTrPAC release, object path, tissue, assay, and feature identifier.
- Rat companion source: `https://motrpac-data.org/`, gene-centric public search API `https://search.motrpac-data.org/search/api`, with query shape `ktype=gene`, `keys=BAG3`, `study=pass1b06`, `omics=transcriptomics`, and fields such as `gene_symbol`, `feature_id`, `tissue`, `assay`, `sex`, `comparison_group`, `logFC`, `logFC_se`, `shrunk_logFC`, `shrunk_logFC_se`, `p_value`, and `adj_p_value`.
- Saved rat API JSON responses with exact BAG3 rows. For rat BAG3 transcriptomics, expected feature ID is `ensrnog00000020298` when returned by the Data Hub API.
- Bundled human helper: `scripts/plot_bag3_acute_motrpac.R`.
- Bundled rat helper: `scripts/plot_rat_bag3_from_search_api.R`.

# Steps
1. Use the PRECAWG app as the canonical plotting source when live access is allowed.
   - Navigate to `https://data-viz.motrpac-data.org/precawg/`.
   - Select the Feature Trajectories tab.
   - Configure tissue, assay, identifier type, BAG3, and feature ID as above.
   - Use the app's download controls for the plot and underlying data when possible.
   - Record the app URL, controls, download date, and any unavailable controls in provenance.
2. Fall back to local app-downloaded or app-like exports when live access is unavailable.
   - Do not fabricate synthetic MoTrPAC results or use unrelated DataHub differential files as a substitute for the PRECAWG Feature Trajectory plot.
   - A local file is acceptable only when it preserves enough app-style fields to identify BAG3, feature ID, tissue, assay, group, timepoint, value type, and adjusted p-value evidence.
3. For rat BAG3 requests, use gene-centric Data Hub evidence rather than the rat cluster UI when exact gene rows are needed.
   - Query or load a saved response from `https://search.motrpac-data.org/search/api`.
   - Require exact `BAG3` in `gene_symbol`; record rat feature ID, tissue, assay, sex, comparison group, logFC/shrunk logFC, standard errors, p-value, and adjusted p-value.
   - Plot rat training timepoints (`1w`, `2w`, `4w`, `8w`) as differential effects, not as human-style acute raw-value trajectories.
   - When both human and rat are requested, generate separate plots and state that protocol, value type, model, and species differ.
4. Inventory every input file.
   - Read CSV, TSV, or TXT files deterministically.
   - Preserve `source_file`, source row number, app URL/download columns when available, and all columns used to identify BAG3, feature ID, group, timepoint, tissue, assay, value type, and statistic.
5. Match BAG3 conservatively.
   - Prefer exact `BAG3` in explicit gene-symbol columns such as `gene_symbol`, `symbol`, `external_gene_name`, or `protein_gene_symbol`.
   - Prefer `ENSG00000151929.10` in explicit `feature_id`, `ensembl_id`, or related feature identifier columns when available.
   - For rat transcriptomics, prefer exact `BAG3` in `gene_symbol` and preserve rat feature ID `ensrnog00000020298` when returned.
   - Accept free-text feature columns only when `BAG3` is a standalone token; mark the match as `token_match_requires_review`.
   - Do not merge BAG3 with BAG3-like symbols, gene aliases, protein names, or pathway terms unless a declared annotation source maps the row to BAG3.
6. Normalize MoTrPAC acute metadata to the app labels.
   - Map `ADUEndur`, `Endurance`, or `EE` to display label `Endurance`.
   - Map `ADUResist`, `Resistance`, or `RE` to display label `Resistance`.
   - Map `ADUControl`, `Control`, or `CON` to display label `Control`; keep control in the plot when reproducing the PRECAWG app style unless the user asks for EE/RE only.
   - Normalize acute timepoints to display labels such as `Pre-Exercise`, `Post 15/30/45 Min`, `Post 3.5/4 Hour`, and `Post 24 Hour`.
   - Parse group and timepoint from `contrast` only when direct metadata columns are absent.
7. Keep data modes separate.
   - If app-exported trajectory summaries are present, plot the exported group means, uncertainty intervals, and adjusted p-value status directly.
   - If subject-level abundance columns and subject/sample IDs are present, summarize BAG3 abundance by group, timepoint, tissue, and assay with `n`, mean, SD, and SE. Label the output as a local reproduction of the app-style trajectory, not an official app export.
   - If differential-analysis statistics are present, plot BAG3 effect sizes only when the user selected `Log2 fold change`; label the plot as differential evidence.
   - Rat Data Hub timewise rows are differential evidence; do not relabel them as human PRECAWG raw trajectories.
   - Do not combine differential-analysis rows and subject-level abundance summaries in the same panel.
8. Render the PRECAWG-style trajectory.
   - Prefer repo-local MoTrPAC colors from `src/metabotyping_agentic/plotting/motrpac_plot_helpers.R` when available.
   - Use the app-like display colors: Control purple, Endurance orange, Resistance green.
   - Use open circles for `Adj-p >= threshold` and filled circles for `Adj-p < threshold`.
   - Render facet strips in the order `feature_id`, `tissue`, `assay` unless the user requests another order.
   - Use one panel per tissue/assay/feature combination, with timepoint on the x-axis and the selected BAG3 value type on the y-axis.
9. Render rat BAG3 timewise differential plots.
   - Use tissue facets and sex-colored trajectories for the returned `comparison_group` values.
   - Use `shrunk_logFC` with `shrunk_logFC_se` when available; otherwise fall back to `logFC` and `logFC_se`.
   - Use open circles for `Adj-p >= 0.05` and filled circles for `Adj-p < 0.05`.
   - Generate an all-tissue plot when requested, and a skeletal-muscle subset when comparing to the human muscle RNA-Seq plot.
10. Write machine-readable outputs and a concise report.
   - Include normalized plot rows, file-level provenance, validation warnings, and a caption that states whether the data are differential-analysis summary rows or subject-level observations.

Run the helper from the repository root, for example:

```bash
Rscript .agents/skills/plot-motrpac-bag3/scripts/plot_bag3_acute_motrpac.R \
  --input data/motrpac_precawg_downloads/*.csv data/motrpac_precawg_downloads/*.tsv \
  --out-dir reports/motrpac_bag3
```

For a saved rat Data Hub gene-search JSON response:

```bash
Rscript .agents/skills/plot-motrpac-bag3/scripts/plot_rat_bag3_from_search_api.R \
  --json reports/motrpac_bag3/rat_bag3_search_api_response.json \
  --out-dir reports/motrpac_bag3
```

# Outputs
- `reports/motrpac_bag3/bag3_feature_trajectories.png`
- `reports/motrpac_bag3/bag3_acute_plot_data.csv`
- `reports/motrpac_bag3/bag3_acute_provenance.csv`
- `reports/motrpac_bag3/bag3_acute_summary.md`
- `reports/motrpac_bag3/rat_bag3_pass1b06_transcriptomics_timewise_rows.csv`
- `reports/motrpac_bag3/rat_bag3_pass1b06_transcriptomics_timewise_all_tissues.png`
- `reports/motrpac_bag3/rat_bag3_pass1b06_transcriptomics_timewise_skeletal_muscle.png`
- `reports/motrpac_bag3/rat_bag3_pass1b06_transcriptomics_timewise_provenance.csv`
- A clear missing-data note when the PRECAWG app export, BAG3 rows, feature ID, exercise-group labels, timepoints, tissue, or assay metadata are unavailable.

# Validation Checks
- Every plotted row includes `source_file`, source row number, source URL or app-export provenance, BAG3 match basis, feature ID, exercise group, acute timepoint, tissue, assay, selected value type, and data mode.
- BAG3 rows are exact symbol or exact feature-ID matches, or are visibly marked as review-required token matches.
- Endurance, Resistance, and Control labels are normalized only from explicit group columns or parseable MoTrPAC contrast strings.
- Tissue and assay are not inferred from biology; filename-derived values are marked as inferred and should be reviewed.
- App-exported trajectory plots preserve app-provided means, error bars, and adjusted p-value status; locally summarized subject-level plots report `n` per group/timepoint/tissue/assay.
- Rat plots preserve species, study, feature ID, tissue, assay, sex, training timepoint, effect estimate, uncertainty, and p-value metadata; rat timewise differential rows are not mixed with human acute raw trajectories.
- PNG and CSV outputs are generated and non-empty when rendering is requested.

# Failure Modes
- PRECAWG app access or app-downloaded data are unavailable; do not fabricate MoTrPAC rows or replace them with mock BAG3 values.
- BAG3 appears only in ambiguous free text, aliases, pathway terms, or unrelated BAG-family symbols.
- Group, tissue, assay, or timepoint labels are inferred from filenames or titles without review flags.
- A differential-analysis table is presented as the PRECAWG Feature Trajectory raw-value plot.
- Rat Data Hub training rows are presented as direct human acute-bout equivalents without a protocol/value-type warning.
- RNA-Seq, proteomics, and other assays are averaged together without an explicit reviewed decision.
- The plot silently drops source-file provenance, PRECAWG app URL evidence, selected controls, or missing metadata warnings.

# Human-Review Triggers
- BAG3 identity depends on a token match outside a dedicated gene-symbol column.
- BAG3 feature ID differs from `ENSG00000151929.10`, is absent, or appears in a non-feature column.
- Rat BAG3 feature ID differs from `ensrnog00000020298`, is absent, or appears in a non-feature column.
- Group, timepoint, tissue, or assay metadata are parsed from `contrast` or filenames instead of explicit app/export columns.
- Multiple assays provide BAG3 rows for the same tissue/timepoint/group and the user wants a single combined estimate.
- The user wants Endurance vs Resistance interpreted as a biological difference without matched protocol, tissue, timepoint, assay, and model evidence.
- The user wants human acute PRECAWG and rat pass1b-06 training effects interpreted as a direct cross-species statistical comparison.
- PRECAWG app-style trajectories are requested but only differential-analysis summary rows are available.

# Evaluation Gates
- FAIR: preserve metadata, source-file provenance, PRECAWG app URL, selected controls, MoTrPAC release/object path when available, tissue, assay, group, timepoint, feature ID, and BAG3 match evidence for every plotted row.
- Reproducibility: plots must be regenerated from declared local input files, deterministic column normalization rules, and the bundled script; record all inputs in the provenance CSV.
- Critical evidence: distinguish exact, token-matched, inferred, missing, app-exported, locally summarized, and review-required evidence; do not imply PRECAWG app-exported raw trajectories when only summary differential statistics are present.
- Human review: route ambiguous BAG3 identity, inferred metadata, mixed assays, and unsupported Endurance-vs-Resistance interpretation to reviewer decisions.
- Skill quality rubric: pass only if the outputs include plot data, provenance, validation warnings, rendering status, data-mode labels, and a concise interpretation of what the BAG3 plot does and does not support.

# Implementation
- Deterministic implementations: `.agents/skills/plot-motrpac-bag3/scripts/plot_bag3_acute_motrpac.R`, `.agents/skills/plot-motrpac-bag3/scripts/plot_rat_bag3_from_search_api.R`, and `src/metabotyping_agentic/plotting/motrpac_plot_helpers.R`.
