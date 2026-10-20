# Install into an explicitly supplied task-local library, not the system library.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 1L) stop("Usage: Rscript scripts/setup_ranger_r.R TASK_LOCAL_R_LIBRARY")
dir.create(args[1], recursive=TRUE, showWarnings=FALSE)
.libPaths(c(normalizePath(args[1]), .libPaths()))
if (!requireNamespace("ranger", quietly=TRUE)) {
  install.packages("ranger", lib=args[1], repos="https://cloud.r-project.org")
}
if (as.character(packageVersion("ranger")) != "0.18.0") {
  stop("This experiment pins ranger 0.18.0. Install that version from CRAN Archive; do not silently upgrade.")
}
cat(R.version.string, "\nranger", as.character(packageVersion("ranger")), "\n")
