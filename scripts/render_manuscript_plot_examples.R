#!/usr/bin/env Rscript

# Render deterministic synthetic examples for the software manuscript.
# These values demonstrate output structure only and are not biological results.

args <- commandArgs(trailingOnly = TRUE)
output_dir <- if (length(args) >= 1) args[[1]] else "docs/manuscript/figures"
data_dir <- if (length(args) >= 2) args[[2]] else "data/examples/plot_examples"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(data_dir, recursive = TRUE, showWarnings = FALSE)

seed <- 20260712
set.seed(seed)

okabe_orange <- "#D55E00"
okabe_blue <- "#0072B2"
neutral <- "#A8A8A8"

make_volcano <- function(n, forced) {
  labels <- sprintf("Feature_%03d", seq_len(n))
  log2fc <- rnorm(n, mean = 0, sd = 0.72)
  p_value <- 10^runif(n, min = -3.0, max = -0.02)
  for (i in seq_along(forced$name)) {
    labels[[i]] <- forced$name[[i]]
    log2fc[[i]] <- forced$log2fc[[i]]
    p_value[[i]] <- forced$p_value[[i]]
  }
  fdr <- p.adjust(p_value, method = "BH")
  data.frame(
    metabolite = labels,
    log2fc = log2fc,
    p_value = p_value,
    fdr = fdr,
    neg_log10_p = -log10(p_value),
    provenance = sprintf("synthetic_seed_%s", seed),
    stringsAsFactors = FALSE
  )
}

mw <- make_volcano(
  72,
  data.frame(
    name = c("Leucine", "Lactate", "CAR 2:0", "Citrate", "Kynurenine"),
    log2fc = c(1.75, 1.30, 1.10, -1.25, -1.05),
    p_value = c(0.00002, 0.00015, 0.0004, 0.00008, 0.0003)
  )
)

motrpac <- make_volcano(
  92,
  data.frame(
    name = c("Alloisoleucine", "CAR 4:0;OH", "Succinate", "Tryptophan", "Pyruvate"),
    log2fc = c(2.05, 1.55, 1.20, -1.45, -1.10),
    p_value = c(0.000001, 0.00003, 0.0002, 0.00002, 0.0003)
  )
)

heat_metabolites <- c(
  "Leucine", "Lactate", "Citrate", "Succinate",
  "CAR 2:0", "CAR 4:0;OH", "Kynurenine", "Tryptophan"
)
heat_contrasts <- c(
  "MW acute", "MW training", "MoTrPAC EE acute",
  "MoTrPAC RE acute", "MoTrPAC EE 8 wk", "MoTrPAC CON 8 wk"
)
heat_values <- matrix(
  c(
     1.8,  0.7,  1.4,  0.5,  0.8,  0.1,
     1.4,  0.3,  1.1,  0.4,  0.5, -0.1,
    -1.1,  0.4, -0.7,  0.2,  0.6,  0.0,
    -0.5,  0.8,  0.3,  0.6,  1.0,  0.1,
     1.2,  0.5,  0.9,  0.4,  0.7,  0.0,
     0.6,  1.0,  1.4,  0.8,  1.2,  0.2,
    -0.8, -0.2, -0.5,  0.1, -0.4,  0.0,
     0.5,  0.1,  0.6, -0.3,  0.2,  0.0
  ),
  nrow = length(heat_metabolites),
  byrow = TRUE,
  dimnames = list(heat_metabolites, heat_contrasts)
)

write.csv(mw, file.path(data_dir, "mock_mw_style_volcano.csv"), row.names = FALSE)
write.csv(motrpac, file.path(data_dir, "mock_motrpac_style_volcano.csv"), row.names = FALSE)
heat_long <- data.frame(
  metabolite = rep(rownames(heat_values), times = ncol(heat_values)),
  contrast = rep(colnames(heat_values), each = nrow(heat_values)),
  standardized_effect = as.vector(heat_values),
  provenance = sprintf("synthetic_seed_%s", seed),
  stringsAsFactors = FALSE
)
write.csv(heat_long, file.path(data_dir, "mock_cross_study_heatmap.csv"), row.names = FALSE)

draw_volcano <- function(data, title, panel_label) {
  significant <- data$fdr < 0.05 & abs(data$log2fc) >= 0.8
  up <- significant & data$log2fc > 0
  down <- significant & data$log2fc < 0
  plot(
    data$log2fc,
    data$neg_log10_p,
    pch = 16,
    col = adjustcolor(neutral, alpha.f = 0.55),
    cex = 0.62,
    xlab = "log2 fold-change",
    ylab = "-log10 p-value",
    main = title,
    cex.main = 0.88,
    cex.lab = 0.78,
    cex.axis = 0.68,
    bty = "l",
    xlim = c(min(data$log2fc) - 0.25, max(data$log2fc) + 0.5),
    ylim = c(0, max(data$neg_log10_p) * 1.12)
  )
  points(data$log2fc[up], data$neg_log10_p[up], pch = 24, bg = okabe_orange, col = okabe_orange, cex = 0.85)
  points(data$log2fc[down], data$neg_log10_p[down], pch = 25, bg = okabe_blue, col = okabe_blue, cex = 0.85)
  abline(v = c(-0.8, 0.8), h = -log10(0.05), lty = 2, lwd = 0.8, col = "#666666")
  labelled <- data[seq_len(5), ]
  text(
    labelled$log2fc,
    labelled$neg_log10_p,
    labels = labelled$metabolite,
    pos = ifelse(labelled$log2fc >= 0, 2, 4),
    cex = 0.52,
    xpd = NA,
    offset = 0.25
  )
  legend(
    "bottomright",
    legend = c("Higher", "Lower", "Not selected"),
    pch = c(24, 25, 16),
    pt.bg = c(okabe_orange, okabe_blue, neutral),
    col = c(okabe_orange, okabe_blue, neutral),
    bty = "n",
    bg = "white",
    cex = 0.55,
    pt.cex = 0.85,
    y.intersp = 1.25
  )
  mtext(panel_label, side = 3, adj = -0.12, line = 1.05, font = 2, cex = 1.05)
}

draw_heatmap <- function(values, panel_label) {
  palette <- colorRampPalette(c("#2166AC", "#F7F7F7", "#B2182B"))(101)
  breaks <- seq(-2.2, 2.2, length.out = 102)
  image(
    x = seq_len(ncol(values)),
    y = seq_len(nrow(values)),
    z = t(values),
    col = palette,
    breaks = breaks,
    axes = FALSE,
    xlab = "",
    ylab = "",
    main = "Reviewed cross-study effects\n(synthetic standardized values)",
    cex.main = 0.88,
    useRaster = TRUE
  )
  axis(1, at = seq_len(ncol(values)), labels = colnames(values), las = 2, tick = FALSE, cex.axis = 0.48, line = -0.4)
  axis(2, at = seq_len(nrow(values)), labels = rownames(values), las = 2, tick = FALSE, cex.axis = 0.56)
  abline(v = seq(1.5, ncol(values) - 0.5, by = 1), h = seq(1.5, nrow(values) - 0.5, by = 1), col = "white", lwd = 0.8)
  for (row_index in seq_len(nrow(values))) {
    for (column_index in seq_len(ncol(values))) {
      value <- values[row_index, column_index]
      text(column_index, row_index, sprintf("%.1f", value), cex = 0.43, col = ifelse(abs(value) > 1.1, "white", "#222222"))
    }
  }
  box(col = "#666666")
  mtext(panel_label, side = 3, adj = -0.12, line = 1.05, font = 2, cex = 1.05)
}

render_figure <- function() {
  layout(matrix(seq_len(3), nrow = 1), widths = c(1, 1, 1.3))
  par(family = "sans", oma = c(2.6, 0.9, 0.6, 0.5))
  par(mar = c(3.2, 4.0, 2.7, 0.8))
  draw_volcano(mw, "MW-style acute contrast\n(synthetic)", "A")
  par(mar = c(3.2, 4.0, 2.7, 0.8))
  draw_volcano(motrpac, "MoTrPAC-style endurance contrast\n(synthetic)", "B")
  par(mar = c(7.4, 5.3, 2.7, 0.8))
  draw_heatmap(heat_values, "C")
  mtext(
    "All values are synthetic. Similar visual patterns do not establish harmonized cohorts or biological replication.",
    side = 1,
    outer = TRUE,
    line = 1.35,
    cex = 0.68,
    font = 2
  )
}

png_path <- file.path(output_dir, "metabotyping_agent_plot_examples.png")
png(png_path, width = 3300, height = 1350, res = 300, type = "cairo")
render_figure()
dev.off()

pdf_path <- file.path(output_dir, "metabotyping_agent_plot_examples.pdf")
pdf(pdf_path, width = 11, height = 4.5, family = "Helvetica", useDingbats = FALSE)
render_figure()
dev.off()

message("Wrote synthetic plot examples to ", png_path, " and ", pdf_path)
