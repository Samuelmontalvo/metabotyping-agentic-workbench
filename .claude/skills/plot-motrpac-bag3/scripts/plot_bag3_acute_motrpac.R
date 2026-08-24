#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)

usage <- function() {
  cat(paste0(
    "Usage:\n",
    "  Rscript plot_bag3_acute_motrpac.R --input precawg_plot_data.tsv --out-dir reports_live/motrpac_bag3\n\n",
    "Options:\n",
    "  --input, --inputs   One or more local PRECAWG app CSV/TSV/TXT exports. May be repeated.\n",
    "  --out-dir           Output directory. Default: reports_live/motrpac_bag3\n",
    "  --gene              Gene symbol to plot. Default: BAG3\n",
    "  --feature-id        Expected BAG3 feature ID. Default: ENSG00000151929.10\n",
    "  --value-type        raw or fold_change. Default: raw\n",
    "  --p-threshold       Adjusted p-value fill threshold. Default: 0.05\n",
    "  --source-url        Source app URL for provenance.\n",
    "  --helper            Optional MoTrPAC R helper path for colors.\n",
    "  --exclude-control   Omit Control/CON rows. Default includes controls to match PRECAWG.\n",
    "  --help              Show this message.\n"
  ))
}

parse_args <- function(args) {
  opts <- list(
    inputs = character(),
    out_dir = "reports_live/motrpac_bag3",
    gene = "BAG3",
    feature_id = "ENSG00000151929.10",
    value_type = "raw",
    p_threshold = 0.05,
    source_url = "https://data-viz.motrpac-data.org/precawg/",
    helper = "src/metabotyping_agentic/plotting/motrpac_plot_helpers.R",
    include_control = TRUE
  )
  i <- 1
  while (i <= length(args)) {
    arg <- args[[i]]
    if (arg %in% c("--help", "-h")) {
      usage()
      quit(status = 0)
    } else if (arg %in% c("--input", "--inputs")) {
      i <- i + 1
      while (i <= length(args) && !startsWith(args[[i]], "--")) {
        opts$inputs <- c(opts$inputs, unlist(strsplit(args[[i]], ",", fixed = TRUE)))
        i <- i + 1
      }
      next
    } else if (arg == "--out-dir") {
      opts$out_dir <- args[[i + 1]]
      i <- i + 2
      next
    } else if (arg == "--gene") {
      opts$gene <- args[[i + 1]]
      i <- i + 2
      next
    } else if (arg == "--feature-id") {
      opts$feature_id <- args[[i + 1]]
      i <- i + 2
      next
    } else if (arg == "--value-type") {
      opts$value_type <- args[[i + 1]]
      i <- i + 2
      next
    } else if (arg == "--p-threshold") {
      opts$p_threshold <- as.numeric(args[[i + 1]])
      i <- i + 2
      next
    } else if (arg == "--source-url") {
      opts$source_url <- args[[i + 1]]
      i <- i + 2
      next
    } else if (arg == "--helper") {
      opts$helper <- args[[i + 1]]
      i <- i + 2
      next
    } else if (arg == "--include-control") {
      opts$include_control <- TRUE
      i <- i + 1
      next
    } else if (arg == "--exclude-control") {
      opts$include_control <- FALSE
      i <- i + 1
      next
    } else if (!startsWith(arg, "--")) {
      opts$inputs <- c(opts$inputs, arg)
      i <- i + 1
      next
    } else {
      stop("Unknown option: ", arg, call. = FALSE)
    }
  }
  opts$inputs <- unique(opts$inputs[nzchar(opts$inputs)])
  opts$value_type <- match.arg(opts$value_type, c("raw", "fold_change"))
  if (!is.finite(opts$p_threshold)) {
    stop("--p-threshold must be numeric.", call. = FALSE)
  }
  opts
}

clean_name <- function(x) {
  x <- tolower(trimws(x))
  x <- gsub("[^a-z0-9]+", "_", x)
  gsub("^_|_$", "", x)
}

first_present <- function(df, candidates) {
  normalized <- clean_name(names(df))
  candidate_norm <- clean_name(candidates)
  idx <- match(candidate_norm, normalized)
  idx <- idx[!is.na(idx)]
  if (length(idx) == 0) {
    return(NA_character_)
  }
  names(df)[idx[[1]]]
}

read_table <- function(path) {
  ext <- tolower(gsub("\\.gz$", "", tools::file_ext(path)))
  con <- if (grepl("\\.gz$", path)) gzfile(path, open = "rt") else path
  if (ext == "csv") {
    read.csv(con, check.names = FALSE, stringsAsFactors = FALSE, comment.char = "")
  } else {
    read.delim(con, check.names = FALSE, stringsAsFactors = FALSE, comment.char = "")
  }
}

as_text <- function(x) {
  x <- as.character(x)
  x[is.na(x)] <- ""
  trimws(x)
}

as_number <- function(x) {
  suppressWarnings(as.numeric(as.character(x)))
}

standalone_token <- function(values, token) {
  pattern <- paste0("(^|[^A-Za-z0-9])", token, "([^A-Za-z0-9]|$)")
  grepl(pattern, values, ignore.case = TRUE)
}

normalize_group <- function(values) {
  values <- as_text(values)
  out <- rep("unknown", length(values))
  out[grepl("ADUEndur|Endurance|(^|[^A-Za-z0-9])EE([^A-Za-z0-9]|$)", values, ignore.case = TRUE)] <- "Endurance"
  out[grepl("ADUResist|Resistance|(^|[^A-Za-z0-9])RE([^A-Za-z0-9]|$)", values, ignore.case = TRUE)] <- "Resistance"
  out[grepl("ADUControl|Control|(^|[^A-Za-z0-9])CON([^A-Za-z0-9]|$)", values, ignore.case = TRUE)] <- "Control"
  out
}

normalize_timepoint <- function(values) {
  values <- as_text(values)
  lower <- tolower(values)
  out <- rep("unknown", length(values))
  out[grepl("pre[_ -]*exercise|baseline|(^|[^a-z0-9])pre([^a-z0-9]|$)", lower)] <- "Pre-Exercise"
  out[grepl("during[_ -]*20|20[_ -]*min", lower)] <- "During 20 Min"
  out[grepl("during[_ -]*40|40[_ -]*min", lower)] <- "During 40 Min"
  out[grepl("post[_ -]*10|10[_ -]*min", lower)] <- "Post 10 Min"
  out[grepl("post[_ -]*(15|30|45)|(15|30|45)[_ -]*min", lower)] <- "Post 15/30/45 Min"
  out[grepl("3[._ -]*5[_ -]*4[_ -]*(hr|hour)|post[_ -]*4[_ -]*(hr|hour)|4[_ -]*(hr|hour)", lower)] <- "Post 3.5/4 Hour"
  out[grepl("24[_ -]*(hr|hour)", lower)] <- "Post 24 Hour"
  out
}

infer_tissue_from_path <- function(path) {
  base <- tolower(basename(path))
  from_code <- regmatches(base, regexpr("t[0-9]+-[a-z0-9-]+", base))
  if (length(from_code) > 0 && nzchar(from_code)) {
    return(sub("^t[0-9]+-", "", from_code))
  }
  known <- c("plasma", "blood", "muscle", "adipose", "pbmc", "serum")
  hit <- known[vapply(known, function(k) grepl(k, base, fixed = TRUE), logical(1))]
  if (length(hit) > 0) {
    return(hit[[1]])
  }
  "unknown"
}

infer_omics_from_path <- function(path) {
  lower <- tolower(path)
  if (grepl("transcript", lower)) return("Transcriptomics")
  if (grepl("proteom", lower)) return("Proteomics")
  if (grepl("phospho", lower)) return("Phosphoproteomics")
  if (grepl("metab", lower)) return("Metabolomics")
  "unknown"
}

extract_numerator <- function(values) {
  values <- as_text(values)
  normalized <- gsub("\\s+[Vv][Ss]\\s+", " - ", values)
  vapply(strsplit(normalized, "\\s+-\\s+"), function(parts) {
    if (length(parts) == 0) "" else parts[[1]]
  }, character(1))
}

safe_col <- function(df, col, default = "") {
  if (is.na(col) || !(col %in% names(df))) {
    rep(default, nrow(df))
  } else {
    df[[col]]
  }
}

load_one <- function(path, gene, feature_id, value_type, source_url) {
  df <- read_table(path)
  if (nrow(df) == 0) {
    return(list(rows = data.frame(), provenance = data.frame(
      source_file = path,
      source_url = source_url,
      total_rows = 0,
      bag3_rows = 0,
      mode = "empty",
      columns = paste(names(df), collapse = ";"),
      warnings = "empty file",
      stringsAsFactors = FALSE
    )))
  }

  feature_col <- first_present(df, c("feature_id", "featureid", "ensembl_id", "ensembl_gene_id", "id", "gene_id"))
  feature_values <- as_text(safe_col(df, feature_col, ""))
  feature_match <- if (nzchar(feature_id)) {
    toupper(feature_values) == toupper(feature_id)
  } else {
    rep(FALSE, nrow(df))
  }

  gene_cols <- unique(stats::na.omit(c(
    first_present(df, c("gene_symbol", "symbol", "external_gene_name", "protein_gene_symbol")),
    first_present(df, c("gene", "gene_name", "genes", "geneid", "gene_id")),
    first_present(df, c("feature_name", "feature", "analyte", "protein", "name"))
  )))
  if (length(gene_cols) == 0) {
    gene_match <- feature_match
    match_basis <- ifelse(feature_match, "exact_feature_id_match", "missing_gene_column")
    gene_value <- rep("", nrow(df))
    gene_column <- rep("", nrow(df))
  } else {
    exact_cols <- intersect(gene_cols, unique(stats::na.omit(c(
      first_present(df, c("gene_symbol", "symbol", "external_gene_name", "protein_gene_symbol")),
      first_present(df, c("gene", "gene_name", "genes"))
    ))))
    exact_matrix <- sapply(gene_cols, function(col) toupper(as_text(df[[col]])) == toupper(gene))
    token_matrix <- sapply(gene_cols, function(col) standalone_token(as_text(df[[col]]), gene))
    exact_match <- if (is.matrix(exact_matrix)) apply(exact_matrix, 1, any) else as.logical(exact_matrix)
    token_match <- if (is.matrix(token_matrix)) apply(token_matrix, 1, any) else as.logical(token_matrix)
    gene_match <- exact_match | feature_match | token_match
    match_basis <- ifelse(
      exact_match,
      "exact_symbol_match",
      ifelse(feature_match, "exact_feature_id_match", ifelse(token_match, "token_match_requires_review", "not_matched"))
    )
    gene_value <- vapply(seq_len(nrow(df)), function(i) {
      vals <- as_text(unlist(df[i, gene_cols, drop = FALSE], use.names = FALSE))
      vals <- vals[nzchar(vals)]
      if (length(vals) == 0) "" else paste(unique(vals), collapse = " | ")
    }, character(1))
    gene_column <- paste(gene_cols, collapse = ";")
    if (length(exact_cols) == 0) {
      match_basis[gene_match] <- "token_match_requires_review"
    }
  }

  group_col <- first_present(df, c("exercise_group", "group", "arm", "condition", "intervention", "training_group"))
  time_col <- first_present(df, c("timepoint", "time_point", "time", "visit", "collection_time", "sample_time", "acute_timepoint"))
  tissue_col <- first_present(df, c("tissue", "sample_matrix", "biospecimen", "organ", "tissue_id", "motrpac_tissue", "matrix"))
  assay_col <- first_present(df, c("assay", "omics", "ome", "assay_type", "platform", "technology", "data_type"))
  contrast_col <- first_present(df, c("contrast", "comparison", "label", "model_term", "term"))
  effect_col <- first_present(df, c("log2_fold_change", "logFC", "log2fc", "log2FoldChange", "estimate", "coef", "coefficient", "beta"))
  p_col <- first_present(df, c("p_value", "pvalue", "p.val", "pval", "P.Value", "p"))
  fdr_col <- first_present(df, c("adj_p_value", "adj.p.value", "padj", "q_value", "fdr", "adj_p"))
  raw_value_col <- first_present(df, c(
    "log2_transformed_value", "log2 transformed value", "log2_raw_value", "log2 raw value",
    "transformed_value", "raw_value", "mean", "mean_value", "value", "y",
    "abundance", "expression", "intensity", "normalized_intensity", "measurement", "counts", "log2_expression"
  ))
  value_col <- if (value_type == "fold_change") effect_col else raw_value_col
  se_col <- first_present(df, c("se", "sem", "stderr", "std_error", "standard_error", "y_se"))
  lower_col <- first_present(df, c("lower", "ymin", "ci_lower", "mean_lower", "lower_ci"))
  upper_col <- first_present(df, c("upper", "ymax", "ci_upper", "mean_upper", "upper_ci"))
  subject_col <- first_present(df, c("subject_id", "participant_id", "individual_id", "person_id", "sample_id", "biosample_id"))

  contrast_values <- safe_col(df, contrast_col, "")
  numerator_values <- extract_numerator(contrast_values)
  group_values <- safe_col(df, group_col, "")
  group <- normalize_group(group_values)
  missing_group <- group == "unknown"
  group[missing_group] <- normalize_group(numerator_values[missing_group])

  time_values <- safe_col(df, time_col, "")
  timepoint <- normalize_timepoint(time_values)
  missing_time <- timepoint == "unknown"
  timepoint[missing_time] <- normalize_timepoint(numerator_values[missing_time])

  tissue_source <- if (is.na(tissue_col)) "filename_inferred" else "column"
  tissue <- as_text(safe_col(df, tissue_col, infer_tissue_from_path(path)))
  tissue[!nzchar(tissue)] <- infer_tissue_from_path(path)
  assay_source <- if (is.na(assay_col)) "filename_inferred" else "column"
  assay <- as_text(safe_col(df, assay_col, infer_omics_from_path(path)))
  assay[!nzchar(assay)] <- infer_omics_from_path(path)

  mode <- if (value_type == "raw" && !is.na(value_col) && is.na(subject_col)) {
    "precawg_feature_trajectory"
  } else if (value_type == "fold_change" && !is.na(effect_col)) {
    "differential_summary"
  } else if (!is.na(value_col) && !is.na(subject_col)) {
    "subject_abundance"
  } else {
    "unrecognized"
  }

  rows <- data.frame(
    source_file = path,
    source_url = source_url,
    source_row = seq_len(nrow(df)),
    data_mode = mode,
    gene = gene,
    expected_feature_id = feature_id,
    feature_id = feature_values,
    feature_id_column = ifelse(!is.na(feature_col), feature_col, ""),
    gene_column = gene_column,
    gene_value = gene_value,
    match_basis = match_basis,
    review_status = ifelse(match_basis %in% c("exact_symbol_match", "exact_feature_id_match"), "accepted_exact", "requires_human_review"),
    exercise_group = group,
    timepoint = timepoint,
    tissue = tissue,
    tissue_source = tissue_source,
    assay = assay,
    assay_source = assay_source,
    contrast = as_text(contrast_values),
    effect = if (!is.na(effect_col)) as_number(df[[effect_col]]) else NA_real_,
    p_value = if (!is.na(p_col)) as_number(df[[p_col]]) else NA_real_,
    adj_p_value = if (!is.na(fdr_col)) as_number(df[[fdr_col]]) else NA_real_,
    subject_id = as_text(safe_col(df, subject_col, "")),
    abundance = if (!is.na(value_col)) as_number(df[[value_col]]) else NA_real_,
    app_value = if (!is.na(value_col) && mode == "precawg_feature_trajectory") as_number(df[[value_col]]) else NA_real_,
    app_se = if (!is.na(se_col)) as_number(df[[se_col]]) else NA_real_,
    app_lower = if (!is.na(lower_col)) as_number(df[[lower_col]]) else NA_real_,
    app_upper = if (!is.na(upper_col)) as_number(df[[upper_col]]) else NA_real_,
    value_type = value_type,
    statistic_column = ifelse(!is.na(effect_col), effect_col, ""),
    abundance_column = ifelse(!is.na(value_col), value_col, ""),
    stringsAsFactors = FALSE
  )
  rows <- rows[gene_match, , drop = FALSE]

  warnings <- character()
  if (length(gene_cols) == 0 && is.na(feature_col)) warnings <- c(warnings, "missing gene and feature ID columns")
  if (is.na(group_col) && is.na(contrast_col)) warnings <- c(warnings, "missing group and contrast columns")
  if (is.na(time_col) && is.na(contrast_col)) warnings <- c(warnings, "missing timepoint and contrast columns")
  if (is.na(tissue_col)) warnings <- c(warnings, "tissue inferred from filename")
  if (is.na(assay_col)) warnings <- c(warnings, "assay inferred from filename")
  if (mode == "unrecognized") warnings <- c(warnings, "no recognized PRECAWG trajectory, effect, or subject-level abundance columns")
  if (length(warnings) == 0) warnings <- ""

  provenance <- data.frame(
    source_file = path,
    source_url = source_url,
    total_rows = nrow(df),
    bag3_rows = nrow(rows),
    mode = mode,
    columns = paste(names(df), collapse = ";"),
    warnings = paste(warnings, collapse = "; "),
    stringsAsFactors = FALSE
  )
  list(rows = rows, provenance = provenance)
}

summarize_subject_rows <- function(rows) {
  key_cols <- c("source_file", "source_url", "data_mode", "gene", "expected_feature_id", "feature_id", "match_basis", "review_status", "exercise_group", "timepoint", "tissue", "tissue_source", "assay", "assay_source", "value_type")
  split_key <- interaction(rows[, key_cols], drop = TRUE, sep = "||")
  parts <- split(rows, split_key)
  out <- lapply(parts, function(d) {
    values <- d$abundance[!is.na(d$abundance)]
    data.frame(
      source_file = paste(unique(d$source_file), collapse = ";"),
      source_url = paste(unique(d$source_url), collapse = ";"),
      data_mode = "subject_abundance",
      gene = unique(d$gene)[[1]],
      expected_feature_id = unique(d$expected_feature_id)[[1]],
      feature_id = paste(unique(d$feature_id[nzchar(d$feature_id)]), collapse = ";"),
      match_basis = paste(unique(d$match_basis), collapse = ";"),
      review_status = ifelse(any(d$review_status != "accepted_exact"), "requires_human_review", "accepted_exact"),
      exercise_group = unique(d$exercise_group)[[1]],
      timepoint = unique(d$timepoint)[[1]],
      tissue = unique(d$tissue)[[1]],
      tissue_source = unique(d$tissue_source)[[1]],
      assay = paste(unique(d$assay), collapse = ";"),
      assay_source = paste(unique(d$assay_source), collapse = ";"),
      contrast = "",
      plot_y = mean(values, na.rm = TRUE),
      plot_se = if (length(values) > 1) stats::sd(values, na.rm = TRUE) / sqrt(length(values)) else NA_real_,
      plot_lower = NA_real_,
      plot_upper = NA_real_,
      n = length(values),
      p_value = NA_real_,
      adj_p_value = NA_real_,
      value_type = unique(d$value_type)[[1]],
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, out)
}

prepare_plot_rows <- function(rows, include_control) {
  allowed_groups <- if (include_control) c("Control", "Endurance", "Resistance") else c("Endurance", "Resistance")
  rows <- rows[rows$exercise_group %in% allowed_groups, , drop = FALSE]
  rows <- rows[rows$timepoint != "unknown" & rows$tissue != "unknown", , drop = FALSE]
  if (nrow(rows) == 0) {
    return(rows)
  }
  modes <- unique(rows$data_mode)
  modes <- modes[modes != "unrecognized"]
  if (length(modes) == 0) {
    stop("No recognized BAG3 rows with effect or subject-level abundance columns.", call. = FALSE)
  }
  if ("precawg_feature_trajectory" %in% modes) {
    out <- rows[rows$data_mode == "precawg_feature_trajectory" & !is.na(rows$app_value), , drop = FALSE]
    out$plot_y <- out$app_value
    out$plot_se <- out$app_se
    out$plot_lower <- out$app_lower
    out$plot_upper <- out$app_upper
    out$n <- NA_integer_
    return(out)
  }
  if ("differential_summary" %in% modes) {
    out <- rows[rows$data_mode == "differential_summary" & !is.na(rows$effect), , drop = FALSE]
    out$plot_y <- out$effect
    out$plot_se <- NA_real_
    out$plot_lower <- NA_real_
    out$plot_upper <- NA_real_
    out$n <- NA_integer_
    return(out)
  }
  summarize_subject_rows(rows[rows$data_mode == "subject_abundance" & !is.na(rows$abundance), , drop = FALSE])
}

timepoint_order <- c(
  "Pre-Exercise",
  "During 20 Min",
  "During 40 Min",
  "Post 10 Min",
  "Post 15/30/45 Min",
  "Post 3.5/4 Hour",
  "Post 24 Hour"
)

group_color <- function(group) {
  if (group %in% c("Endurance", "EE", "ADUEndur")) return("#e66101")
  if (group %in% c("Resistance", "RE", "ADUResist")) return("#1b9e77")
  if (group %in% c("Control", "CON", "ADUControl")) return("#7570b3")
  "#666666"
}

plot_all_tissues <- function(plot_rows, out_png, p_threshold) {
  present_timepoints <- timepoint_order[timepoint_order %in% plot_rows$timepoint]
  if (length(present_timepoints) == 0) {
    stop("No BAG3 rows with recognized PRECAWG acute timepoint values.", call. = FALSE)
  }
  plot_rows$timepoint <- factor(plot_rows$timepoint, levels = present_timepoints)
  plot_rows <- plot_rows[!is.na(plot_rows$timepoint), , drop = FALSE]
  panel_key <- interaction(plot_rows$feature_id, plot_rows$tissue, plot_rows$assay, drop = TRUE, sep = "||")
  panels <- split(plot_rows, panel_key)
  if (length(panels) == 0) {
    stop("No BAG3 rows with recognized tissue and acute timepoint values.", call. = FALSE)
  }
  n_panels <- length(panels)
  n_col <- min(3, n_panels)
  n_row <- ceiling(n_panels / n_col)
  height <- max(850, 420 * n_row)
  width <- max(1200, 520 * n_col)
  grDevices::png(out_png, width = width, height = height, res = 130)
  on.exit(grDevices::dev.off(), add = TRUE)
  old_par <- par(no.readonly = TRUE)
  on.exit(par(old_par), add = TRUE)
  par(mfrow = c(n_row, n_col), mar = c(10.5, 5, 5, 1.5), oma = c(0, 0, 3, 0))

  y_label <- if (unique(plot_rows$value_type)[[1]] == "fold_change") {
    "Log2 fold change"
  } else {
    "Log2 transformed value"
  }
  lower <- ifelse(!is.na(plot_rows$plot_lower), plot_rows$plot_lower,
                  plot_rows$plot_y - ifelse(is.na(plot_rows$plot_se), 0, plot_rows$plot_se))
  upper <- ifelse(!is.na(plot_rows$plot_upper), plot_rows$plot_upper,
                  plot_rows$plot_y + ifelse(is.na(plot_rows$plot_se), 0, plot_rows$plot_se))
  y_range <- range(lower, upper, na.rm = TRUE)
  if (!all(is.finite(y_range)) || diff(y_range) == 0) {
    y_range <- y_range + c(-1, 1)
  }
  y_pad <- diff(y_range) * 0.03
  y_range <- y_range + c(-y_pad, y_pad)

  group_levels <- c("Control", "Endurance", "Resistance")
  for (d in panels) {
    plot(seq_along(present_timepoints), rep(NA_real_, length(present_timepoints)),
         ylim = y_range, xaxt = "n", xlab = "", ylab = y_label, main = "")
    grid(col = "#e6e6e6", lty = 1)
    axis(1, at = seq_along(present_timepoints), labels = present_timepoints, las = 2, cex.axis = 0.75)
    mtext("Timepoint", side = 1, line = 5)
    if (unique(plot_rows$value_type)[[1]] == "fold_change") {
      abline(h = 0, col = "#999999", lty = 2)
    }
    usr <- par("usr")
    strip_h <- diff(usr[3:4]) * 0.08
    strip_labels <- c(
      ifelse(nzchar(unique(d$feature_id)[[1]]), paste0(unique(d$gene)[[1]], ": ", unique(d$feature_id)[[1]]), unique(d$gene)[[1]]),
      unique(d$tissue)[[1]],
      unique(d$assay)[[1]]
    )
    old_xpd <- par("xpd")
    par(xpd = NA)
    for (j in seq_along(strip_labels)) {
      y0 <- usr[4] + strip_h * (length(strip_labels) - j)
      y1 <- y0 + strip_h
      rect(usr[1], y0, usr[2], y1, col = "#e6e6e6", border = "#333333")
      text(mean(usr[1:2]), (y0 + y1) / 2, strip_labels[[j]], font = 2, cex = 0.85)
    }
    par(xpd = old_xpd)

    for (group in group_levels[group_levels %in% unique(d$exercise_group)]) {
      dg <- d[d$exercise_group == group, , drop = FALSE]
      offset <- ifelse(group == "Control", -0.08, ifelse(group == "Endurance", 0, 0.08))
      x <- as.integer(dg$timepoint) + offset
      ord <- order(x)
      x <- x[ord]
      y <- dg$plot_y[ord]
      se <- dg$plot_se[ord]
      lo <- dg$plot_lower[ord]
      hi <- dg$plot_upper[ord]
      p <- dg$adj_p_value[ord]
      col <- group_color(group)
      if (sum(!is.na(y)) > 1) {
        lines(x, y, col = col, lwd = 2)
      }
      has_interval <- !is.na(lo) & !is.na(hi)
      if (any(has_interval)) {
        arrows(x[has_interval], lo[has_interval], x[has_interval], hi[has_interval],
               angle = 90, code = 3, length = 0.04, col = col)
      }
      has_se <- !has_interval & !is.na(se)
      if (any(has_se)) {
        arrows(x[has_se], y[has_se] - se[has_se], x[has_se], y[has_se] + se[has_se],
               angle = 90, code = 3, length = 0.04, col = col)
      }
      is_sig <- !is.na(p) & p < p_threshold
      points(x[!is_sig], y[!is_sig], pch = 21, col = col, bg = "white", lwd = 1.5, cex = 1.15)
      points(x[is_sig], y[is_sig], pch = 19, col = col, cex = 1.15)
    }
    legend_groups <- group_levels[group_levels %in% unique(d$exercise_group)]
    legend(
      "bottom",
      inset = c(0, -0.55),
      legend = c(legend_groups, paste0("Adj-p >= ", p_threshold), paste0("Adj-p < ", p_threshold)),
      col = c(vapply(legend_groups, group_color, character(1)), "#000000", "#000000"),
      pt.bg = c(rep(NA, length(legend_groups)), "white", "#000000"),
      pch = c(rep(19, length(legend_groups)), 21, 19),
      lty = c(rep(1, length(legend_groups)), NA, NA),
      horiz = TRUE,
      bty = "n",
      cex = 0.75,
      xpd = NA
    )
  }
  title("Feature trajectories for the features in gene: BAG3", outer = TRUE)
}

write_summary <- function(path, plot_rows, provenance, warnings) {
  mode <- if (nrow(plot_rows) > 0) unique(plot_rows$data_mode)[[1]] else "none"
  lines <- c(
    "# MoTrPAC PRECAWG BAG3 Feature Trajectories",
    "",
    paste0("- Data mode: `", mode, "`."),
    paste0("- Source app: ", paste(unique(provenance$source_url), collapse = ", ")),
    paste0("- Input files: ", length(unique(provenance$source_file)), "."),
    paste0("- Plotted rows: ", nrow(plot_rows), "."),
    paste0("- Tissues: ", paste(sort(unique(plot_rows$tissue)), collapse = ", ")),
    paste0("- Groups: ", paste(sort(unique(plot_rows$exercise_group)), collapse = ", ")),
    paste0("- Assays: ", paste(sort(unique(plot_rows$assay)), collapse = ", ")),
    paste0("- Value type: ", paste(sort(unique(plot_rows$value_type)), collapse = ", ")),
    "",
    "## Interpretation Boundary",
    "",
    if (mode == "precawg_feature_trajectory") {
      "The plot reproduces the PRECAWG Human Data Visualization Feature Trajectories grammar from app-downloaded or app-like trajectory summaries."
    } else if (mode == "differential_summary") {
      "The plot shows local MoTrPAC differential-analysis summary effects for BAG3. It is not a subject-level trajectory unless the source rows contain subject/sample abundance values."
    } else {
      "The plot shows locally summarized subject-level BAG3 abundance by group, timepoint, tissue, and assay. It should not be described as an official app export unless the source file came from the PRECAWG app."
    },
    "",
    "## Validation Warnings",
    "",
    if (length(warnings) == 0) "- none" else paste0("- ", warnings)
  )
  writeLines(lines, path)
}

opts <- parse_args(args)
if (length(opts$inputs) == 0) {
  usage()
  stop("At least one --input file is required.", call. = FALSE)
}
missing_inputs <- opts$inputs[!file.exists(opts$inputs)]
if (length(missing_inputs) > 0) {
  stop("Missing input files: ", paste(missing_inputs, collapse = ", "), call. = FALSE)
}

if (file.exists(opts$helper)) {
  try(source(opts$helper), silent = TRUE)
}

dir.create(opts$out_dir, recursive = TRUE, showWarnings = FALSE)
loaded <- lapply(
  opts$inputs,
  load_one,
  gene = opts$gene,
  feature_id = opts$feature_id,
  value_type = opts$value_type,
  source_url = opts$source_url
)
rows <- do.call(rbind, lapply(loaded, `[[`, "rows"))
provenance <- do.call(rbind, lapply(loaded, `[[`, "provenance"))

raw_path <- file.path(opts$out_dir, "bag3_acute_raw_matches.csv")
plot_data_path <- file.path(opts$out_dir, "bag3_acute_plot_data.csv")
provenance_path <- file.path(opts$out_dir, "bag3_acute_provenance.csv")
summary_path <- file.path(opts$out_dir, "bag3_acute_summary.md")
png_path <- file.path(opts$out_dir, "bag3_feature_trajectories.png")

utils::write.csv(provenance, provenance_path, row.names = FALSE)

if (is.null(rows) || nrow(rows) == 0) {
  utils::write.csv(data.frame(), raw_path, row.names = FALSE)
  write_summary(summary_path, data.frame(), provenance, c("No BAG3 rows matched local inputs."))
  stop("No BAG3 rows matched local inputs.", call. = FALSE)
}

utils::write.csv(rows, raw_path, row.names = FALSE)
plot_rows <- prepare_plot_rows(rows, opts$include_control)
if (nrow(plot_rows) == 0) {
  utils::write.csv(plot_rows, plot_data_path, row.names = FALSE)
  write_summary(summary_path, plot_rows, provenance, c("No BAG3 rows had exercise-group, tissue, assay, timepoint, and recognized data-mode evidence."))
  stop("No BAG3 rows had exercise-group, tissue, assay, timepoint, and recognized data-mode evidence.", call. = FALSE)
}

warnings <- unique(unlist(strsplit(paste(provenance$warnings, collapse = "; "), ";\\s*")))
warnings <- warnings[nzchar(warnings)]
review_rows <- plot_rows[
  plot_rows$review_status != "accepted_exact" |
    plot_rows$tissue_source != "column" |
    plot_rows$assay_source != "column",
  ,
  drop = FALSE
]
if (nrow(review_rows) > 0) {
  warnings <- unique(c(warnings, "Some plotted rows require human review for BAG3 identity or inferred tissue/assay metadata."))
}

utils::write.csv(plot_rows, plot_data_path, row.names = FALSE)
plot_all_tissues(plot_rows, png_path, opts$p_threshold)
write_summary(summary_path, plot_rows, provenance, warnings)

if (!file.exists(png_path) || file.info(png_path)$size <= 0) {
  stop("Plot rendering failed: output PNG is missing or empty.", call. = FALSE)
}

cat("Wrote:\n")
cat(" - ", normalizePath(png_path, mustWork = FALSE), "\n", sep = "")
cat(" - ", normalizePath(plot_data_path, mustWork = FALSE), "\n", sep = "")
cat(" - ", normalizePath(provenance_path, mustWork = FALSE), "\n", sep = "")
cat(" - ", normalizePath(summary_path, mustWork = FALSE), "\n", sep = "")
