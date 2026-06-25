---
name: motrpac-plotting
description: Use when creating or editing MoTrPAC or Metabolomics Workbench comparison plots, including volcano plots, heatmaps, upset plots, palette choices, colors, EE/RE/CON groups, sex colors, and plot styling.
---

# Purpose
Create reviewable MoTrPAC-style visualizations with consistent colors, plot styling, provenance, and explicit metadata evidence.

# Inputs
- Normalized analysis tables with plot variables such as `logFC`, `adj_p_value`, `exercise_group`, `sex`, `tissue`, and `omics`.
- Repo-local plotting helpers such as `src/metabotyping_agentic/plotting/motrpac_plot_helpers.R`.
- Existing repo palette objects or MoTrPAC package palette objects when available.

# Steps
1. Search for repo-local palette or theme objects before adding colors.
2. Prefer existing MoTrPAC functions, package palette objects, or the repo plotting helper over inline hex codes.
3. Use exercise-group colors only for explicit group metadata:
   `EE`, `Endurance`, `ADUEndur`; `RE`, `Resistance`, `ADUResist`; `CON`, `Control`, `ADUControl`.
4. Use sex colors only for explicit sex metadata: male/M/Males or female/F/Females.
5. Treat Metabolomics Workbench like MoTrPAC only when MW factors explicitly map to endurance, resistance, control, male, or female.
6. For volcano plots, preserve significance/direction coloring unless group or sex is intentionally the visual encoding.
7. Add group, sex, tissue, omics, and palette-source annotations when available so color choices are auditable.

# Outputs
- Plot files such as PNG/SVG volcano plots, heatmaps, upset plots, or comparison panels.
- Normalized plot-ready tables retaining available `exercise_group`, `sex`, `tissue`, `omics`, and `palette_source` columns.
- Reports that state exploratory visual comparisons are not harmonized evidence unless a reviewed crosswalk exists.

# Validation Checks
- EE/RE/CON, sex, tissue, omics, and timepoint colors match repo-local or helper mappings.
- Legends display intended labels in stable order and do not imply missing metadata.
- MW colors are neutral unless explicit MW metadata supports MoTrPAC-like group or sex mapping.
- Plot outputs are generated and non-empty when rendering is requested.

# Failure Modes
- Ad hoc plot code silently reassigns established MoTrPAC colors.
- MW group labels are inferred from title or biology rather than source metadata.
- A legend displays group or sex colors when the normalized rows have no explicit group or sex evidence.
- Plot dependencies are unavailable; keep normalized CSV/report outputs intact and fail plot rendering clearly.

# Human-Review Triggers
- A color mapping depends on ambiguous labels, inferred biology, or a nonstandard treatment abbreviation.
- A plot combines MW and MoTrPAC data where visual similarity could be mistaken for validated harmonization.
- A reviewer wants to promote a neutral MW category into EE, RE, CON, male, or female without source factor evidence.

# Evaluation Gates
- FAIR: preserve plot data provenance, metadata columns, palette source, and source accession evidence.
- Reproducibility: plots must be regenerated from declared input files, deterministic rules, and available helper functions.
- Critical evidence: do not hide missing or inferred metadata behind MoTrPAC colors.
- Human review: ambiguous plot mappings must remain visible for reviewer decisions.
- Skill quality rubric: pass only if plot color rules, metadata evidence, validation checks, and failure modes are auditable.
