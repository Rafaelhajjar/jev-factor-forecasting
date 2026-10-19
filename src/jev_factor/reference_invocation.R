# Read-only integration probe. Execute the real adapter and native initialization,
# then deliberately stop before noise injection, split search or any tree fitting.
probe_args <- commandArgs(trailingOnly=TRUE)
if (length(probe_args) != 6) stop("Expected engine, matrix, settings, library, adapter, directory")
engine_path <- normalizePath(probe_args[1])
directory <- probe_args[6]
captured <- new.env(parent=emptyenv())
adapter_env <- new.env(parent=globalenv())
adapter_env$commandArgs <- function(trailingOnly=FALSE) {
  if (!trailingOnly) stop("Probe expects trailing adapter arguments")
  c(probe_args[1:3], file.path(directory, "must_not_be_a_forecast.csv"), probe_args[4])
}
adapter_env$source <- function(file, local=FALSE, ...) {
  if (normalizePath(file) != engine_path || !is.environment(local)) stop("Unexpected source request")
  base::source(file, local=local, ...)
  native_mrf <- local$MRF
  local$MRF <- function(...) {
    captured$top <- list(...)
    native_mrf(...)
  }
  # Locate an exact AST assignment, not a guessed source-line offset. At this
  # point the unmodified native function has standardized data, translated the
  # prior, and applied its dimension-dependent parent-size guard.
  expressions <- as.list(body(local$one.mrf.tree))
  before_data_copy <- which(vapply(expressions, function(e) {
    is.call(e) && (identical(e[[1]], as.name("<-")) || identical(e[[1]], as.name("="))) &&
      identical(e[[2]], as.name("data.ori"))
  }, logical(1)))
  if (length(before_data_copy) != 1) stop("Pinned native initialization boundary changed")
  local$.capture_native_initialization <- function(frame) {
    captured$native <- as.list(frame)
    stop(structure(list(message="Native initialization captured", call=NULL),
                   class=c("mrf_initialization_captured", "error", "condition")))
  }
  suppressMessages(trace("one.mrf.tree", where=local, at=before_data_copy,
                        tracer=quote(.capture_native_initialization(environment())), print=FALSE))
  invisible(NULL)
}
stopped <- FALSE
tryCatch(base::source(probe_args[5], local=adapter_env),
         mrf_initialization_captured=function(e) { stopped <<- TRUE })
if (!stopped || is.null(captured$native) || is.null(captured$top)) stop("Probe did not capture native initialization")
if (file.exists(file.path(directory, "must_not_be_a_forecast.csv"))) stop("Probe unexpectedly fitted a forecast")
top <- captured$top
native <- captured$native
data <- native$data
training <- seq_len(min(native$oos.pos) - 1L)
linear <- native$z.pos
state <- native$x.pos
features <- rbind(
  data.frame(role="linear", name=colnames(data)[linear], position=linear),
  data.frame(role="state", name=colnames(data)[state], position=state)
)
write.csv(features, file.path(directory, "features.csv"), row.names=FALSE)
write.csv(data.frame(mean=native$prior.mean, precision=native$prior.var),
          file.path(directory, "prior.csv"), row.names=FALSE)
metadata <- c(
  R_version=R.version.string, pracma_version=as.character(packageVersion("pracma")),
  native_rows=nrow(data), native_columns=ncol(data), training_rows=length(training),
  forecast_rows=length(native$oos.pos), target_position=native$y.pos,
  nominal_parent_size=top$minsize, effective_parent_size=native$minsize,
  mtry_fraction=native$frac, mtry_state_candidates=round(length(state)*native$frac),
  ridge_lambda=native$regul.lambda, RWR=native$rw.regul, MLF=native$min.leaf.fracz,
  HRW=native$HRW,
  trend_position_in_state=native$trend.pos, trend_push=native$trend.push,
  subsampling_rate=top$subsampling.rate, block_size=top$block.size,
  resampling_option=top$resampling.opt, declared_trees=top$B,
  fast_RW=native$fast.rw, VI=top$VI, cheap_coefficient_plot=top$cheap.look.at.GTVPs,
  ERT=native$ET, no_RW_trespassing=native$no.rw.trespassing,
  default_state_priorities=is.null(native$prob.vec),
  maximum_masked_target_magnitude=max(abs(data[native$oos.pos, native$y.pos])),
  maximum_training_mean=max(abs(colMeans(data[training, , drop=FALSE]))),
  maximum_training_std_error=max(abs(apply(data[training, , drop=FALSE], 2, sd)-1))
)
write.dcf(as.data.frame(as.list(metadata)), file.path(directory, "invocation.dcf"))
