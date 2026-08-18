# MoTrPAC plotting helpers for base-R renderers.
# Keep this file dependency-light so live plots can render without extra packages.

MOTRPAC_EXERCISE_GROUP_COLORS <- c(
  EE = "#d95f02",
  Endurance = "#d95f02",
  ADUEndur = "#d95f02",
  RE = "#1b9e77",
  Resistance = "#1b9e77",
  ADUResist = "#1b9e77",
  CON = "#7570b3",
  Control = "#7570b3",
  ADUControl = "#7570b3"
)

MOTRPAC_SEX_COLORS <- c(
  male = "#5555ff",
  M = "#5555ff",
  Males = "#5555ff",
  female = "#f95c6f",
  F = "#f95c6f",
  Females = "#f95c6f"
)

MOTRPAC_TISSUE_COLORS <- c(
  blood = "#d7191c",
  plasma = "#d7191c",
  muscle = "#abd9e9",
  adipose = "#ffffbf"
)

MOTRPAC_OMICS_COLORS <- c(
  Transcriptomics = "#377EB8",
  Proteomics = "#228833",
  Metabolomics = "#6D4B08",
  metabolomics = "#6D4B08",
  ATAC = "#882255",
  Phosphoproteomics = "#F3A02B",
  Methylation = "#D687B5"
)

MOTRPAC_ACUTE_TIMEPOINT_COLORS <- c(
  pre_exercise = "#BEBEBE",
  during_20_min = "#FDE725",
  during_40_min = "#BAD071",
  post_10_min = "#D1BBD7",
  post_15_30_45_min = "#AE76A3",
  post_3.5_4_hr = "#882E72",
  post_24_hr = "#61194F"
)

motrpac_package_palette <- function(object_name) {
  package_name <- "MotrpacHumanPreSuspensionAnalysis"
  if (!requireNamespace(package_name, quietly = TRUE)) {
    return(NULL)
  }
  tryCatch(getExportedValue(package_name, object_name), error = function(e) NULL)
}

motrpac_palette <- function(kind) {
  if (kind == "exercise_group") {
    pkg <- motrpac_package_palette("HUMAN_EXERCISE_GROUP_COLORS")
    if (!is.null(pkg) && all(c("ADUEndur", "ADUResist", "ADUControl") %in% names(pkg))) {
      return(c(
        EE = unname(pkg["ADUEndur"]),
        RE = unname(pkg["ADUResist"]),
        CON = unname(pkg["ADUControl"]),
        pkg
      ))
    }
    return(MOTRPAC_EXERCISE_GROUP_COLORS)
  }
  if (kind == "sex") {
    pkg <- motrpac_package_palette("HUMAN_SEX_COLORS")
    if (!is.null(pkg) && all(c("male", "female") %in% names(pkg))) {
      return(c(
        pkg,
        Males = unname(pkg["male"]),
        Females = unname(pkg["female"]),
        M = unname(pkg["male"]),
        F = unname(pkg["female"])
      ))
    }
    return(MOTRPAC_SEX_COLORS)
  }
  if (kind == "tissue") {
    pkg <- motrpac_package_palette("HUMAN_TISSUE_COLORS")
    if (!is.null(pkg) && "blood" %in% names(pkg)) {
      return(c(plasma = unname(pkg["blood"]), pkg))
    }
    return(MOTRPAC_TISSUE_COLORS)
  }
  if (kind == "omics") {
    pkg <- motrpac_package_palette("HUMAN_OME_COLORS")
    if (!is.null(pkg) && length(names(pkg)) > 0) {
      return(pkg)
    }
    return(MOTRPAC_OMICS_COLORS)
  }
  if (kind == "acute_timepoint") {
    pkg <- motrpac_package_palette("HUMAN_ACUTE_TIMEPOINT_COLORS")
    if (!is.null(pkg) && length(names(pkg)) > 0) {
      return(pkg)
    }
    return(MOTRPAC_ACUTE_TIMEPOINT_COLORS)
  }
  c()
}

motrpac_palette_color <- function(kind, value, fallback = "#666666") {
  pal <- motrpac_palette(kind)
  if (is.null(value) || is.na(value) || value == "" || !(value %in% names(pal))) {
    return(fallback)
  }
  unname(pal[value])
}

motrpac_significance_colors <- function(log_fc, adj_p_value) {
  p <- as.numeric(adj_p_value)
  x <- as.numeric(log_fc)
  sig <- !is.na(p) & p < 0.05
  ifelse(sig & x > 0, "#b2182b", ifelse(sig & x < 0, "#2166ac", "#80808055"))
}

motrpac_unique_values <- function(data, column) {
  if (!(column %in% colnames(data))) {
    return(character())
  }
  values <- unique(as.character(data[[column]]))
  values <- values[!is.na(values) & values != "" & values != "unknown"]
  sort(values)
}

motrpac_context_items <- function(data) {
  items <- list()
  groups <- motrpac_unique_values(data, "exercise_group")
  for (value in groups) {
    items[[length(items) + 1]] <- list(
      label = paste("Group:", value),
      color = motrpac_palette_color("exercise_group", value),
      source = "exercise_group"
    )
  }
  sexes <- motrpac_unique_values(data, "sex")
  for (value in sexes) {
    items[[length(items) + 1]] <- list(
      label = paste("Sex:", value),
      color = motrpac_palette_color("sex", value),
      source = "sex"
    )
  }
  items
}

motrpac_draw_context <- function(data) {
  items <- motrpac_context_items(data)
  if (length(items) == 0) {
    return(invisible(NULL))
  }
  usr <- par("usr")
  x <- usr[1] + 0.02 * (usr[2] - usr[1])
  y <- usr[4] - 0.06 * (usr[4] - usr[3])
  step <- 0.055 * (usr[4] - usr[3])
  for (i in seq_along(items)) {
    text(x, y - (i - 1) * step, labels = items[[i]]$label, adj = 0, cex = 0.68, col = items[[i]]$color)
  }
  invisible(NULL)
}
