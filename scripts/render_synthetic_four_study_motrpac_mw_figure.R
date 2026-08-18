#!/usr/bin/env Rscript

# Deterministic, synthetic four-study MoTrPAC/MW multi-panel figure.
# Values demonstrate a reviewable visualization workflow; they are not biological results.

args <- commandArgs(trailingOnly = TRUE)
out_dir <- if (length(args)) args[[1]] else "reports/synthetic_four_study_figure"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

seed <- 20260729
set.seed(seed)

studies <- data.frame(
  study_id = c("MOTRPAC-HUMAN-ACUTE", "MOTRPAC-HUMAN-TRAINING", "ST004303", "ST003807"),
  display = c(
    "MoTrPAC human acute EE",
    "MoTrPAC human 8-week EE",
    "MW ST004303",
    "MW ST003807"
  ),
  source = c("MoTrPAC", "MoTrPAC", "Metabolomics Workbench", "Metabolomics Workbench"),
  contrast = c(
    "post-exercise / pre-exercise",
    "week 8 / baseline",
    "post-exercise / pre-exercise",
    "trained / baseline"
  ),
  effect_scale = "synthetic log2 fold-change",
  fdr_method = "Benjamini-Hochberg",
  stringsAsFactors = FALSE
)

metabolites <- c(
  "Leucine", "Lactate", "Citrate", "Succinate", "Pyruvate",
  "Kynurenine", "Tryptophan", "CAR 2:0", "CAR 4:0;OH", "Alanine",
  "Glutamine", "Malate"
)

patterns <- rbind(
  c(1.35, 1.75, -0.85, 0.70, 1.10, -0.65, -0.45, 1.05, 0.75, 0.55, -0.30, 0.50),
  c(0.65, 0.45, 0.70, 1.05, 0.35, -0.55, 0.30, 0.60, 1.15, 0.40, 0.55, 0.85),
  c(1.55, 1.20, -1.10, 0.45, 0.80, -0.95, -0.30, 1.25, 0.55, 0.70, -0.20, 0.35),
  c(0.75, 0.60, 0.45, 0.90, 0.25, -0.40, 0.50, 0.45, 1.05, 0.35, 0.65, 0.75)
)
colnames(patterns) <- metabolites

make_study <- function(index, n = 96) {
  named_effect <- patterns[index, ] + rnorm(length(metabolites), 0, 0.12)
  background_n <- n - length(metabolites)
  effect <- c(named_effect, rnorm(background_n, 0, 0.52))
  feature <- c(metabolites, sprintf("%s_feature_%03d", studies$study_id[index], seq_len(background_n)))
  signal <- pmin(7, 0.45 + abs(effect) * 2.55 + rexp(n, rate = 1.8))
  p_value <- pmax(10^-signal, .Machine$double.xmin)
  fdr <- p.adjust(p_value, method = "BH")
  data.frame(
    study_id = studies$study_id[index],
    source = studies$source[index],
    contrast = studies$contrast[index],
    feature_id = feature,
    accepted_canonical_name = ifelse(seq_len(n) <= length(metabolites), feature, NA),
    log2_fold_change = effect,
    p_value = p_value,
    fdr = fdr,
    fdr_method = "Benjamini-Hochberg",
    fdr_family_n = n,
    synthetic_seed = seed,
    stringsAsFactors = FALSE
  )
}

results <- do.call(rbind, lapply(seq_len(nrow(studies)), make_study))
write.csv(results, file.path(out_dir, "four_study_differential_results.csv"), row.names = FALSE)
write.csv(studies, file.path(out_dir, "study_contrast_metadata.csv"), row.names = FALSE)

heatmap_data <- results[!is.na(results$accepted_canonical_name), ]
heatmap_data <- heatmap_data[order(match(heatmap_data$accepted_canonical_name, metabolites)), ]
write.csv(
  heatmap_data[, c("study_id", "source", "contrast", "accepted_canonical_name",
                   "log2_fold_change", "p_value", "fdr", "synthetic_seed")],
  file.path(out_dir, "cross_study_heatmap_data.csv"),
  row.names = FALSE
)

blue <- "#0072B2"
orange <- "#D55E00"
neutral <- "#B7B7B7"

draw_volcano <- function(study_index, panel) {
  dat <- results[results$study_id == studies$study_id[study_index], ]
  selected <- dat$fdr < 0.05 & abs(dat$log2_fold_change) >= 0.8
  cols <- ifelse(selected & dat$log2_fold_change > 0, orange,
                 ifelse(selected & dat$log2_fold_change < 0, blue, neutral))
  plot(
    dat$log2_fold_change, -log10(dat$p_value), pch = 16, col = adjustcolor(cols, 0.78),
    cex = 0.64, bty = "l", xlab = "Synthetic log2 fold-change",
    ylab = expression(-log[10](italic(p))),
    main = paste0(studies$display[study_index], "\n", studies$contrast[study_index]),
    cex.main = 0.88, cex.lab = 0.76, cex.axis = 0.68,
    xlim = c(-2.2, 2.2), ylim = c(0, max(-log10(dat$p_value)) * 1.10)
  )
  abline(v = c(-0.8, 0.8), h = -log10(0.05), lty = 2, col = "#666666", lwd = 0.8)
  labels <- dat[!is.na(dat$accepted_canonical_name) & selected, ]
  labels <- labels[order(labels$p_value), ][seq_len(min(3, nrow(labels))), ]
  if (nrow(labels)) {
    text(labels$log2_fold_change, -log10(labels$p_value),
         labels = labels$accepted_canonical_name, pos = 3, cex = 0.52, xpd = NA)
  }
  mtext(panel, side = 3, adj = -0.11, line = 1.0, font = 2, cex = 1.05)
}

draw_heatmap <- function(panel) {
  mat <- sapply(studies$study_id, function(id) {
    study_rows <- heatmap_data[heatmap_data$study_id == id, ]
    study_rows$log2_fold_change[match(metabolites, study_rows$accepted_canonical_name)]
  })
  rownames(mat) <- metabolites
  colnames(mat) <- studies$display
  colnames(mat) <- studies$display
  palette <- colorRampPalette(c("#2166AC", "#F7F7F7", "#B2182B"))(101)
  image(seq_len(ncol(mat)), seq_len(nrow(mat)), t(mat), col = palette,
        breaks = seq(-2, 2, length.out = 102), axes = FALSE, xlab = "", ylab = "",
        main = "Cross-study heatmap: accepted canonical metabolites",
        cex.main = 0.92, useRaster = TRUE)
  axis(1, seq_len(ncol(mat)), colnames(mat), las = 2, tick = FALSE, cex.axis = 0.62)
  axis(2, seq_len(nrow(mat)), rownames(mat), las = 2, tick = FALSE, cex.axis = 0.65)
  abline(v = seq(1.5, ncol(mat) - 0.5, 1), h = seq(1.5, nrow(mat) - 0.5, 1),
         col = "white", lwd = 0.9)
  for (r in seq_len(nrow(mat))) for (cc in seq_len(ncol(mat))) {
    text(cc, r, sprintf("%.1f", mat[r, cc]), cex = 0.52,
         col = ifelse(abs(mat[r, cc]) >= 1.05, "white", "#222222"))
  }
  box(col = "#666666")
  mtext(panel, side = 3, adj = -0.08, line = 1.0, font = 2, cex = 1.05)
}

render <- function() {
  layout(matrix(c(1, 2, 3, 4, 5, 5), nrow = 2, byrow = TRUE), widths = c(1, 1, 1.2))
  par(family = "sans", oma = c(3.0, 0.7, 1.2, 0.5))
  for (i in seq_len(4)) {
    par(mar = c(3.4, 3.8, 3.0, 0.8))
    draw_volcano(i, LETTERS[i])
  }
  par(mar = c(7.0, 5.5, 3.0, 1.0))
  draw_heatmap("E")
  mtext(
    "SYNTHETIC HUMAN-DATA DEMONSTRATION - BH FDR within each 96-feature study; volcano selection: FDR < 0.05 and |log2FC| >= 0.8.",
    side = 1, outer = TRUE, line = 1.7, cex = 0.68, font = 2
  )
  mtext(
    "Heatmap values are descriptive synthetic effects; visual similarity is not evidence of harmonized replication.",
    side = 1, outer = TRUE, line = 0.7, cex = 0.62
  )
}

png(file.path(out_dir, "motrpac_mw_four_study_multiplot.png"),
    width = 3600, height = 2400, res = 300, type = "cairo")
render()
dev.off()

pdf(file.path(out_dir, "motrpac_mw_four_study_multiplot.pdf"),
    width = 12, height = 8, family = "Helvetica", useDingbats = FALSE)
render()
dev.off()

message("Wrote synthetic four-study figure bundle to ", out_dir)
