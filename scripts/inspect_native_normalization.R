# Isolated initialization-only comparison. Never run or score a tree.
# Arguments: pinned engine, primary matrix, primary settings, R library,
# repository root, fresh output directory, train_only|native_all_supplied_rows.
task_args <- commandArgs(trailingOnly=TRUE)
if (length(task_args) != 7L) stop("Expected seven normalization-probe arguments")
mode <- task_args[7L]
if (!(mode %in% c("train_only", "native_all_supplied_rows"))) stop("Unknown probe mode")
directory <- task_args[6L]
if (file.exists(directory)) stop("Choose a fresh normalization-probe directory")
dir.create(directory, recursive=TRUE)
settings_path <- normalizePath(task_args[3L])
settings_original <- base::read.dcf(settings_path)
if (settings_original[1L, "standardization"] != "train_only" ||
    settings_original[1L, "prior"] != "OLS") stop("Requires the original primary settings")
root <- normalizePath(task_args[5L])
adapter <- file.path(root, "src", "jev_factor", "reference_mrf.R")
probe <- file.path(root, "src", "jev_factor", "reference_invocation.R")

# Only this R process changes its in-memory setting. The actual adapter/probe,
# downloaded engine, matrix and settings on disk remain untouched.
read.dcf <- function(file, ...) {
  value <- base::read.dcf(file, ...)
  if (normalizePath(file) == settings_path) value[1L, "standardization"] <- mode
  value
}
commandArgs <- function(trailingOnly=FALSE) {
  if (!trailingOnly) stop("Probe expects trailing arguments")
  c(task_args[1:4], adapter, directory)
}
base::source(probe, local=globalenv())

# The reused probe stops the actual native function after normalization/prior
# conversion, before noise injection, split search or any fitted forecast.
native <- captured$native
top <- captured$top
moments <- native$std.stuff
train <- seq_len(min(native$oos.pos) - 1L)
zpos <- native$z.pos
ypos <- native$y.pos
provided <- top$prior.mean
literal <- provided
literal[-1L] <- provided[-1L] * moments$std[zpos] / moments$std[ypos]
literal[1L] <- (provided[1L] - moments$mean[ypos] +
                sum(moments$mean[zpos] * literal[-1L])) / moments$std[ypos]
correct <- provided
correct[-1L] <- provided[-1L] * moments$std[zpos] / moments$std[ypos]
correct[1L] <- (provided[1L] - moments$mean[ypos] +
                sum(moments$mean[zpos] * provided[-1L])) / moments$std[ypos]
qr_prior <- as.numeric(qr.solve(cbind(1, native$data[train, zpos]),
                               native$data[train, ypos]))
stopifnot(max(abs(literal - native$prior.mean)) < 1e-12,
          max(abs(correct - qr_prior)) < 1e-12,
          max(abs(native$data[native$oos.pos, ypos])) < 1e-12,
          !file.exists(file.path(directory, "must_not_be_a_forecast.csv")))
if (mode == "train_only") {
  stopifnot(max(abs(native$prior.mean - qr_prior)) < 1e-12)
}
write.csv(data.frame(
  term=c("intercept", colnames(native$data)[zpos]),
  supplied_prior=provided,
  captured_prior=native$prior.mean,
  QR_OLS_prior=qr_prior,
  mathematically_transformed_prior=correct,
  literal_source_formula=literal
), file.path(directory, "prior_comparison.csv"), row.names=FALSE)
write.csv(data.frame(
  name=colnames(native$data), mean=moments$mean, SD=moments$std
), file.path(directory, "normalization_moments.csv"), row.names=FALSE)
summary <- data.frame(
  mode=mode, training_rows=length(train), forecast_rows=length(native$oos.pos),
  state_columns=length(native$x.pos),
  maximum_training_mean=max(abs(colMeans(native$data[train, , drop=FALSE]))),
  maximum_training_SD_error=max(abs(apply(native$data[train, , drop=FALSE], 2, sd)-1)),
  target_inner_SD=moments$std[ypos],
  maximum_state_inner_center=max(abs(moments$mean[native$x.pos])),
  maximum_state_inner_SD_error=max(abs(moments$std[native$x.pos]-1)),
  maximum_source_prior_QR_difference=max(abs(native$prior.mean-qr_prior)),
  source_prior_intercept_minus_QR=native$prior.mean[1L]-qr_prior[1L],
  maximum_source_prior_slope_QR_difference=max(abs(native$prior.mean[-1L]-qr_prior[-1L])),
  maximum_literal_source_formula_difference=max(abs(native$prior.mean-literal)),
  maximum_correct_transformation_QR_difference=max(abs(correct-qr_prior)),
  masked_target_maximum=max(abs(native$data[native$oos.pos, ypos])),
  forests_fitted=0L, forecast_scores_computed=FALSE
)
write.csv(summary, file.path(directory, "normalization_summary.csv"), row.names=FALSE)
print(summary, row.names=FALSE)
