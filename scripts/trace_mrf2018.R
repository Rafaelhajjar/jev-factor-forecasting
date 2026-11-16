# Storage-only replay of the frozen adapter; never edits the adapter or GPL engine.
# The Python driver verifies source checksums before invoking this script.
trace_args <- commandArgs(trailingOnly=TRUE)
if (length(trace_args) != 6) stop("Expected adapter, engine, matrix, settings, output, R library")
diagnostic_args <- trace_args[-1]
adapter_text <- paste(readLines(trace_args[1]), collapse="\n")
replace_once <- function(text, old, new) {
  hits <- gregexpr(old, text, fixed=TRUE)[[1]]
  if (length(hits) != 1L || hits[1] < 0) stop("Frozen adapter instrumentation anchor changed")
  sub(old, new, text, fixed=TRUE)
}
adapter_text <- replace_once(adapter_text,
  "args <- commandArgs(trailingOnly=TRUE)", "args <- diagnostic_args")
adapter_text <- replace_once(adapter_text,
  "resampling.opt=2L, printb=FALSE", "resampling.opt=2L, printb=FALSE, keep.forest=TRUE")
replay <- new.env(parent=globalenv())
eval(parse(text=adapter_text), envir=replay)
with(replay, {
  Z <- cbind(1, data[, xpos, drop=FALSE])
  individual <- vapply(seq_len(as.integer(settings$trees)), function(b) {
    rowSums(Z * fit$betas.draws.raw[, , b]) * spreads[1] + centers[1]
  }, numeric(nrow(data)))
  expected <- t(fit$pred.ensemble) * spreads[1] + centers[1]
  if (max(abs(individual[oos, , drop=FALSE] - expected)) > 1e-10)
    stop("Per-tree coefficient reconstruction failed")
  colnames(individual) <- paste0("tree_", seq_len(ncol(individual)))
  observed <- data[, 1] * spreads[1] + centers[1]
  observed[oos] <- NA_real_
  write.csv(data.frame(row_index=seq_len(nrow(data)),
    role=ifelse(seq_len(nrow(data)) <= ntrain, "train", "forecast"),
    observed_training_target=observed, individual),
    paste0(args[4], ".trees.csv"), row.names=FALSE)
  leaves <- do.call(rbind, lapply(seq_along(fit$model$forest), function(b) {
    leaf <- fit$model$forest[[b]]
    data.frame(tree=b, node=leaf$NODE, n_split_sample=leaf$NOBS,
               path=leaf$FILTER, stringsAsFactors=FALSE)
  }))
  write.csv(leaves, paste0(args[4], ".leaves.csv"), row.names=FALSE)
  saveRDS(fit, paste0(args[4], ".fit.rds"))
})
