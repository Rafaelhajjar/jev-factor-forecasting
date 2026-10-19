# Independent base-R numerical cross-check. No forecasts or basis choices.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 4L) stop("Expected training matrix, output folder, rank, engine")
x <- as.matrix(read.csv(args[1], check.names=FALSE))
rank <- as.integer(args[3])
if (any(!is.finite(x)) || nrow(x) <= 10L) stop("Invalid training matrix")
fit <- stats::prcomp(x, center=TRUE, scale.=FALSE, rank.=rank)
rotation <- data.frame(component=seq_len(rank), t(fit$rotation[, seq_len(rank), drop=FALSE]), check.names=FALSE)
write.csv(rotation, file.path(args[2], "factor_rotation.csv"), row.names=FALSE)
bank <- vector("list", ncol(x))
for (j in seq_len(ncol(x))) {
  # Row t uses lags 1..8, just as in the primary target-date design.
  lagged <- embed(x[, j], 9L)[, -1, drop=FALSE]
  maf <- stats::prcomp(lagged, center=TRUE, scale.=FALSE, rank.=2L)
  bank[[j]] <- data.frame(series_index=j-1L, component=1:2, t(maf$rotation[, 1:2]))
}
write.csv(do.call(rbind, bank), file.path(args[2], "maf_rotation.csv"), row.names=FALSE)
engine <- new.env(parent=globalenv())
source(args[4], local=engine)
weights <- engine$DV.fun(rep(1, 10L), DV.pref=0.15)
write.csv(data.frame(weight=weights), file.path(args[2], "native_split_weights.csv"), row.names=FALSE)
writeLines(R.version.string, file.path(args[2], "R_version.txt"))
