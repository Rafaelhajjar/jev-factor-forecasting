# Prepare the native TVP dependencies in a project-local library, never globally.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) > 1L) stop("Usage: Rscript scripts/setup_tvp_r.R [library-path]")
script <- sub("^--file=", "", commandArgs()[grepl("^--file=", commandArgs())][1])
source(file.path(dirname(script), "setup_mrf_r.R")) # Pinned pracma; same library argument.
pins <- list(
  fGarch=c(version="4052.93", archive="4052.93", md5="32a1168ed48ef43d8f53f22fa736b46e"),
  matrixcalc=c(version="1.0.6", archive="1.0-6", md5="3b7acd84cfbe8085fab05d2f40ff0c79")
)
for (p in names(pins)) {
  pin <- pins[[p]]
  installed <- tryCatch(as.character(packageVersion(p)), error=function(e) "")
  if (installed == pin["version"]) next
  # Imports may evolve; every actual fit records all loaded namespace versions.
  dependencies <- tools::package_dependencies(
    p, available.packages(repos="https://cloud.r-project.org"),
    recursive=TRUE, which=c("Depends", "Imports", "LinkingTo")
  )[[1]]
  absent <- dependencies[!vapply(dependencies, requireNamespace, logical(1), quietly=TRUE)]
  if (length(absent)) {
    install.packages(absent, lib=library_path, repos="https://cloud.r-project.org", dependencies=NA)
  }
  archive <- tempfile(fileext=".tar.gz")
  filename <- paste0(p, "_", pin["archive"], ".tar.gz")
  urls <- c(
    paste0("https://cloud.r-project.org/src/contrib/", filename),
    paste0("https://cloud.r-project.org/src/contrib/Archive/", p, "/", filename)
  )
  downloaded <- FALSE
  for (url in urls) {
    status <- tryCatch(suppressWarnings(download.file(url, archive, mode="wb", quiet=TRUE)),
                       error=function(e) 1L)
    if (status == 0L) { downloaded <- TRUE; break }
  }
  if (!downloaded || unname(tools::md5sum(archive)) != pin["md5"]) {
    stop(paste("Pinned source download/checksum failed for", p))
  }
  install.packages(archive, lib=library_path, repos=NULL, type="source")
  unlink(archive)
  if (as.character(packageVersion(p)) != pin["version"]) stop(paste("Wrong installed version:", p))
}
cat("Pinned native TVP dependencies ready in", normalizePath(library_path), "\n")
