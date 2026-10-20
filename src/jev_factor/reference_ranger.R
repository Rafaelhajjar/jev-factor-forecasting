# Original process boundary. No author/package source is redistributed here.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 6L) stop("matrix, AR matrix, settings, output, R library, fit/audit")
.libPaths(c(args[5], .libPaths()))
suppressPackageStartupMessages(library(ranger))
if (as.character(packageVersion("ranger")) != "0.18.0") stop("Expected pinned ranger 0.18.0")
s <- as.list(read.dcf(args[3])[1, ])
d <- as.matrix(read.csv(args[1], check.names=FALSE))
a <- as.matrix(read.csv(args[2], check.names=FALSE))
n <- as.integer(s$ntrain)
if (any(!is.finite(d)) || any(!is.finite(a)) || n < 20L || n >= nrow(d)) stop("Invalid input")
tr <- seq_len(n)
te <- seq.int(n+1L, nrow(d))
if (!identical(d[,1], a[,1])) stop("Targets differ")
x <- d[, -1, drop=FALSE]
y <- d[tr, 1]
options(digits=17)
if (args[6] == "fit") {
  fit <- ranger::ranger(
    x=x[tr,,drop=FALSE], y=y, num.trees=as.integer(s$trees),
    min.node.size=as.integer(s$min_node_size), min.bucket=1L,
    mtry=as.integer(s$mtry), replace=as.logical(s$replace),
    sample.fraction=as.numeric(s$sample_fraction), splitrule="variance",
    num.threads=1L, seed=as.integer(s$seed), importance="none",
    keep.inbag=TRUE, oob.error=FALSE, write.forest=TRUE, verbose=FALSE
  )
  saveRDS(fit, paste0(args[4], ".rds"))
} else if (args[6] == "audit") {
  fit <- readRDS(paste0(args[4], ".rds"))
} else stop("Unknown mode")
if (fit$num.trees != as.integer(s$trees) || fit$mtry != as.integer(s$mtry) ||
    fit$min.node.size != as.integer(s$min_node_size)) stop("Forest settings differ")
pred <- as.numeric(predict(fit, data=x[te,,drop=FALSE], num.threads=1L)$predictions)
per_tree <- predict(fit, data=x[te,,drop=FALSE], predict.all=TRUE, num.threads=1L)$predictions
# Separately traverse every stored tree; terminal values are checked against
# bootstrap/subsample weighted means of training y, never held-out outcomes.
traverse <- function(tree, query) {
  child <- fit$forest$child.nodeIDs[[tree]]
  variable <- fit$forest$split.varIDs[[tree]]
  value <- fit$forest$split.values[[tree]]
  vapply(seq_len(nrow(query)), function(row) {
    node <- 1L
    repeat {
      if (child[[1]][node] == 0L && child[[2]][node] == 0L) return(as.integer(node))
      node <- 1L + if (query[row, variable[node]+1L] <= value[node])
        child[[1]][node] else child[[2]][node]
    }
  }, integer(1))
}
max_leaf_error <- 0
manual <- matrix(NA_real_, nrow=length(te), ncol=fit$num.trees)
for (tree in seq_len(fit$num.trees)) {
  train_nodes <- traverse(tree, x[tr,,drop=FALSE])
  test_nodes <- traverse(tree, x[te,,drop=FALSE])
  weights <- fit$inbag.counts[[tree]]
  if (length(weights) != n || any(weights < 0) || sum(weights) <= 0) stop("Invalid inbag")
  if (!as.logical(s$replace) && any(weights > 1)) stop("Replacement in subsample")
  if (sum(weights) != floor(n*as.numeric(s$sample_fraction))) stop("Sample size differs")
  means <- vapply(unique(c(train_nodes, test_nodes)), function(node) {
    selected <- train_nodes == node
    if (sum(weights[selected]) == 0) stop("Empty sampled leaf")
    weighted.mean(y[selected], weights[selected])
  }, numeric(1))
  names(means) <- unique(c(train_nodes, test_nodes))
  nodes <- as.integer(names(means))
  max_leaf_error <- max(max_leaf_error, abs(means - fit$forest$split.values[[tree]][nodes]))
  manual[,tree] <- means[as.character(test_nodes)]
}
if (max_leaf_error > 1e-10 || max(abs(manual-per_tree)) > 1e-10 ||
    max(abs(rowMeans(manual)-pred)) > 1e-10) stop("Independent forest traversal differs")
beta <- qr.solve(cbind(1, a[tr,-1,drop=FALSE]), a[tr,1])
ar_pred <- as.numeric(cbind(1, a[te,-1,drop=FALSE]) %*% beta)
out <- data.frame(prediction=pred, AR4=ar_pred)
if (args[6] == "fit") {
  write.csv(out, args[4], row.names=FALSE)
} else {
  saved <- as.matrix(read.csv(args[4]))
  if (max(abs(saved-as.matrix(out))) > 1e-10) stop("Saved predictions differ")
}
runtime <- list(
  R_version=R.version.string, ranger_version=as.character(packageVersion("ranger")),
  trees=fit$num.trees, mtry=fit$mtry, min_node_size=fit$min.node.size,
  min_bucket=1L, replace=s$replace, sample_fraction=s$sample_fraction,
  max_leaf_error=max_leaf_error, max_manual_prediction_error=max(abs(rowMeans(manual)-pred)),
  heldout_targets_not_used=TRUE, mode=args[6]
)
write.dcf(as.data.frame(runtime), paste0(args[4], ".", args[6], ".dcf"))
cat("Verified", fit$num.trees, "trees;", length(te), "predictions; mode", args[6], "\n")
