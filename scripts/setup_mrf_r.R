# Install the sole external-engine package into a project-specific library.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) > 1L) stop("Usage: Rscript scripts/setup_mrf_r.R [library-path]")
library_path <- if (length(args)) args[1] else "runs/r-library"
dir.create(library_path, recursive=TRUE, showWarnings=FALSE)
.libPaths(c(normalizePath(library_path), .libPaths()))
required_version <- "2.4.6"
installed <- tryCatch(as.character(packageVersion("pracma")), error=function(e) "")
if (installed != required_version) {
  package_file <- tempfile(fileext=".tar.gz")
  package_name <- paste0("pracma_", required_version, ".tar.gz")
  urls <- c(
    paste0("https://cloud.r-project.org/src/contrib/", package_name),
    paste0("https://cloud.r-project.org/src/contrib/Archive/pracma/", package_name)
  )
  downloaded <- FALSE
  for (url in urls) {
    result <- tryCatch(
      suppressWarnings(download.file(url, package_file, mode="wb", quiet=TRUE)),
      error=function(e) 1L
    )
    if (result == 0L) { downloaded <- TRUE; break }
  }
  if (!downloaded) stop("Could not download pinned pracma from CRAN")
  if (unname(tools::md5sum(package_file)) != "cd38dfab15df0e2fe0d56ac40644ef29") {
    stop("Pinned pracma source checksum differs from CRAN metadata")
  }
  install.packages(package_file, repos=NULL, type="source", lib=library_path)
  unlink(package_file)
}
stopifnot(as.character(packageVersion("pracma")) == required_version)
cat(R.version.string, "\npracma", as.character(packageVersion("pracma")),
    "\nlibrary", normalizePath(library_path), "\n")
