#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)

usage <- function() {
  cat(paste0(
    "Usage:\n",
    "  Rscript plot_rat_bag3_from_search_api.R --json rat_bag3_search_api_response.json --out-dir reports_live/motrpac_bag3\n\n",
    "Options:\n",
    "  --json       Saved MoTrPAC Data Hub gene-search JSON response.\n",
    "  --out-dir    Output directory. Default: reports_live/motrpac_bag3\n",
    "  --help       Show this message.\n"
  ))
}

parse_args <- function(args) {
  opts <- list(
    json = "reports_live/motrpac_bag3/rat_bag3_search_api_response.json",
    out_dir = "reports_live/motrpac_bag3"
  )
  i <- 1
  while (i <= length(args)) {
    arg <- args[[i]]
    if (arg %in% c("--help", "-h")) {
      usage()
      quit(status = 0)
    } else if (arg == "--json") {
      opts$json <- args[[i + 1]]
      i <- i + 2
      next
    } else if (arg == "--out-dir") {
      opts$out_dir <- args[[i + 1]]
      i <- i + 2
      next
    } else {
      stop("Unknown option: ", arg, call. = FALSE)
    }
  }
  opts
}

opts <- parse_args(args)
dir.create(opts$out_dir, recursive = TRUE, showWarnings = FALSE)

required <- c("jsonlite", "ggplot2", "dplyr", "readr")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  stop("Missing required R packages: ", paste(missing, collapse = ", "), call. = FALSE)
}

api <- jsonlite::fromJSON(opts$json, simplifyVector = FALSE)
headers <- unlist(api$result$headers, use.names = FALSE)
rows <- api$result$data
if (length(rows) == 0) {
  stop("No rat BAG3 rows returned in ", opts$json, call. = FALSE)
}

df <- as.data.frame(do.call(rbind, lapply(rows, function(x) {
  x <- unlist(x, use.names = FALSE)
  names(x) <- headers
  x
})), stringsAsFactors = FALSE, check.names = FALSE)

num_cols <- intersect(c(
  "logFC", "logFC_se", "shrunk_logFC", "shrunk_logFC_se",
  "p_value", "adj_p_value", "selection_fdr",
  "comparison_average_intensity", "comparison_average_intensity_se",
  "reference_average_intensity", "reference_average_intensity_se"
), names(df))
for (col in num_cols) {
  df[[col]] <- suppressWarnings(as.numeric(df[[col]]))
}

df <- df |>
  dplyr::mutate(
    source_url = "https://motrpac-data.org/",
    search_api_url = "https://search.motrpac-data.org/search/api",
    source_json = opts$json,
    study = "pass1b06",
    query_gene = "BAG3",
    match_basis = dplyr::if_else(gene_symbol == "BAG3", "exact_gene_symbol", "review_required"),
    comparison_group = factor(comparison_group, levels = c("1w", "2w", "4w", "8w")),
    sex = factor(sex, levels = c("female", "male")),
    point_fill = dplyr::if_else(!is.na(adj_p_value) & adj_p_value < 0.05, "Adj-p < 0.05", "Adj-p >= 0.05"),
    estimate = dplyr::coalesce(shrunk_logFC, logFC),
    estimate_se = dplyr::coalesce(shrunk_logFC_se, logFC_se),
    ci_low = estimate - estimate_se,
    ci_high = estimate + estimate_se
  )

if (!all(df$gene_symbol == "BAG3")) {
  warning("Some returned rows are not exact BAG3 gene_symbol matches.")
}

tissue_order <- c(
  "gastrocnemius", "vastus lateralis", "heart", "blood rna", "liver",
  "brown adipose", "white adipose", "kidney", "lung", "colon",
  "small intestine", "spleen", "adrenal", "hypothalamus", "hippocampus",
  "cortex", "vena cava", "testes", "ovaries"
)
df$tissue <- factor(df$tissue, levels = unique(c(tissue_order, sort(unique(as.character(df$tissue))))))

rows_csv <- file.path(opts$out_dir, "rat_bag3_pass1b06_transcriptomics_timewise_rows.csv")
readr::write_csv(df, rows_csv)

provenance <- data.frame(
  artifact = c(
    basename(opts$json),
    "rat_bag3_pass1b06_transcriptomics_timewise_rows.csv",
    "rat_bag3_pass1b06_transcriptomics_timewise_all_tissues.png",
    "rat_bag3_pass1b06_transcriptomics_timewise_skeletal_muscle.png"
  ),
  source_url = "https://motrpac-data.org/",
  search_api_url = "https://search.motrpac-data.org/search/api",
  query = "ktype=gene; keys=BAG3; study=pass1b06; omics=transcriptomics; size=10000",
  row_count = nrow(df),
  bag3_match_basis = paste(sort(unique(df$match_basis)), collapse = ";"),
  notes = c(
    "Raw JSON response saved from the public MoTrPAC Data Hub gene search API.",
    "Normalized exact BAG3 rows used for rat plotting.",
    "All returned rat tissues, sex-stratified timewise training contrasts.",
    "Skeletal muscle subset for comparison with the human PRECAWG muscle RNA-Seq plot."
  ),
  stringsAsFactors = FALSE
)
readr::write_csv(provenance, file.path(opts$out_dir, "rat_bag3_pass1b06_transcriptomics_timewise_provenance.csv"))

sex_colors <- c(female = "#f95c6f", male = "#5555ff")

base_plot <- function(plot_df, title, subtitle, ncol = 4) {
  ggplot2::ggplot(plot_df, ggplot2::aes(
    x = comparison_group,
    y = estimate,
    group = sex,
    color = sex
  )) +
    ggplot2::geom_hline(yintercept = 0, linewidth = 0.25, color = "grey55") +
    ggplot2::geom_errorbar(
      ggplot2::aes(ymin = ci_low, ymax = ci_high),
      width = 0.12,
      linewidth = 0.35,
      alpha = 0.85,
      na.rm = TRUE
    ) +
    ggplot2::geom_line(linewidth = 0.55, alpha = 0.9, na.rm = TRUE) +
    ggplot2::geom_point(
      ggplot2::aes(fill = point_fill),
      shape = 21,
      size = 2.2,
      stroke = 0.8,
      na.rm = TRUE
    ) +
    ggplot2::facet_wrap(ggplot2::vars(tissue), ncol = ncol, scales = "free_y") +
    ggplot2::scale_color_manual(values = sex_colors, drop = FALSE) +
    ggplot2::scale_fill_manual(
      values = c("Adj-p < 0.05" = "black", "Adj-p >= 0.05" = "white"),
      breaks = c("Adj-p >= 0.05", "Adj-p < 0.05"),
      drop = FALSE
    ) +
    ggplot2::labs(
      title = title,
      subtitle = subtitle,
      x = "Training timepoint",
      y = "Shrunken log2 fold change vs reference",
      color = "Sex",
      fill = NULL,
      caption = "Source: MoTrPAC Data Hub public gene search API; exact gene_symbol BAG3; study pass1b06; omics transcriptomics."
    ) +
    ggplot2::theme_bw(base_size = 9) +
    ggplot2::theme(
      plot.title = ggplot2::element_text(face = "bold", size = 13),
      plot.subtitle = ggplot2::element_text(size = 9),
      strip.background = ggplot2::element_rect(fill = "grey85", color = "grey35", linewidth = 0.35),
      strip.text = ggplot2::element_text(face = "bold", size = 8),
      panel.grid.minor = ggplot2::element_blank(),
      legend.position = "bottom",
      axis.text.x = ggplot2::element_text(angle = 35, hjust = 1)
    )
}

all_plot <- base_plot(
  df,
  "Rat BAG3 transcriptomics timewise response across MoTrPAC tissues",
  "Pass1b-06 endurance training contrasts; points show female and male estimates by tissue.",
  ncol = 4
)
all_plot_path <- file.path(opts$out_dir, "rat_bag3_pass1b06_transcriptomics_timewise_all_tissues.png")
ggplot2::ggsave(all_plot_path, all_plot, width = 14, height = 12, dpi = 180, bg = "white")

muscle_df <- df |>
  dplyr::filter(as.character(tissue) %in% c("gastrocnemius", "vastus lateralis"))
muscle_plot <- base_plot(
  muscle_df,
  "Rat BAG3 transcriptomics timewise response in skeletal muscle",
  "Pass1b-06 gastrocnemius and vastus lateralis contrasts; shown separately by sex.",
  ncol = 2
)
muscle_plot_path <- file.path(opts$out_dir, "rat_bag3_pass1b06_transcriptomics_timewise_skeletal_muscle.png")
ggplot2::ggsave(muscle_plot_path, muscle_plot, width = 10, height = 5.8, dpi = 180, bg = "white")

summary_lines <- c(
  "# Rat BAG3 MoTrPAC plot",
  "",
  "## Rat Data Hub plot",
  "",
  "- Source: https://motrpac-data.org/ and public search API `https://search.motrpac-data.org/search/api`.",
  "- Query: `ktype=gene`, `keys=BAG3`, `study=pass1b06`, `omics=transcriptomics`, `size=10000`.",
  paste0("- Exact BAG3 rows returned: ", nrow(df), "."),
  paste0("- Tissues returned: ", paste(sort(unique(as.character(df$tissue))), collapse = "; "), "."),
  "- Output: `rat_bag3_pass1b06_transcriptomics_timewise_all_tissues.png`.",
  "- Muscle subset: `rat_bag3_pass1b06_transcriptomics_timewise_skeletal_muscle.png`.",
  "",
  "## Interpretation guardrails",
  "",
  "- Rat plots are pass1b-06 timewise endurance-training differential rows from the Data Hub gene search API.",
  "- Do not present these as human PRECAWG acute-bout raw-value trajectories or as a direct cross-species statistical comparison."
)
writeLines(summary_lines, file.path(opts$out_dir, "rat_bag3_summary.md"))

cat("Wrote:\n")
cat(" - ", rows_csv, "\n", sep = "")
cat(" - ", all_plot_path, "\n", sep = "")
cat(" - ", muscle_plot_path, "\n", sep = "")
cat(" - ", file.path(opts$out_dir, "rat_bag3_summary.md"), "\n", sep = "")
