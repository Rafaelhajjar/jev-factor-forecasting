# Independent process adapter, not a copy of the separately sourced GPL engine.
# Invocation and source checksum are controlled by replication.py.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 5) stop("Expected engine, matrix, settings DCF, output, R library")
.libPaths(c(args[5], .libPaths()))
suppressPackageStartupMessages(library(pracma))
settings <- as.list(read.dcf(args[3])[1, ])
data <- as.matrix(read.csv(args[2], check.names=FALSE))
ntrain <- as.integer(settings$ntrain)
oos <- seq.int(ntrain + 1L, nrow(data))
train <- seq_len(ntrain)
if (ntrain < 20 || length(oos) < 1) stop("Invalid fitting/test split")
data[oos, 1] <- mean(data[train, 1]) # Never use held-out targets, even for scaling.
centers <- colMeans(data[train, , drop=FALSE])
spreads <- apply(data[train, , drop=FALSE], 2, sd)
if (any(!is.finite(data)) || any(spreads <= 1e-12)) stop("Nonfinite or constant input")
data <- sweep(sweep(data, 2, centers, "-"), 2, spreads, "/")
xnames <- strsplit(settings$xnames, ",", fixed=TRUE)[[1]]
xpos <- match(xnames, colnames(data))
if (anyNA(xpos)) stop("Linear predictors missing")
engine <- new.env(parent=globalenv())
source(args[1], local=engine)
if (settings$standardization == "train_only") {
  # Adapter boundary override: the unmodified source standardizes all supplied
  # rows. We explicitly fit moments on training rows for a causal run.
  engine$standard <- function(Y) {
    mu <- colMeans(Y[train, , drop=FALSE])
    sigma <- apply(Y[train, , drop=FALSE], 2, sd)
    list(Y=sweep(sweep(Y, 2, mu, "-"), 2, sigma, "/"), mean=mu, std=sigma)
  }
} else if (settings$standardization != "native_all_supplied_rows") {
  stop("Unknown standardization mode")
}
prior_mean <- NULL
prior_var <- NULL
if (settings$prior == "OLS") {
  prior_mean <- as.numeric(qr.solve(cbind(1, data[train, xpos]), data[train, 1]))
  prior_var <- c(100, rep(1, length(xpos)))
} else if (settings$prior != "zero") stop("Unknown prior")
set.seed(as.integer(settings$seed))
compiler::enableJIT(3)
started <- proc.time()[[3]]
fit <- engine$MRF(
  data=data, x.pos=xpos, y.pos=1L, S.pos=seq.int(2L, ncol(data)), oos.pos=oos,
  minsize=as.integer(settings$minsize), mtry.frac=as.numeric(settings$mtry),
  min.leaf.frac.of.x=as.numeric(settings$MLF), VI=FALSE,
  cheap.look.at.GTVPs=FALSE, prior.mean=prior_mean, prior.var=prior_var,
  subsampling.rate=0.75, rw.regul=as.numeric(settings$RWR),
  block.size=as.integer(settings$block), trend.pos=match("trend", colnames(data)),
  trend.push=as.numeric(settings$trend_push), fast.rw=TRUE,
  ridge.lambda=as.numeric(settings$ridge_lambda), B=as.integer(settings$trees),
  resampling.opt=2L, printb=FALSE
)
beta <- fit$betas.raw[oos, , drop=FALSE]
pred <- as.numeric(fit$pred)
reconstructed <- rowSums(cbind(1, data[oos, xpos]) * beta)
if (max(abs(pred - reconstructed)) > 1e-8) stop("Author coefficient decomposition mismatch")
beta[, -1] <- sweep(beta[, -1, drop=FALSE] * spreads[1], 2, spreads[xpos], "/")
beta[, 1] <- beta[, 1] * spreads[1] + centers[1] -
  rowSums(sweep(beta[, -1, drop=FALSE], 2, centers[xpos], "*"))
colnames(beta) <- c("intercept", xnames)
output <- data.frame(prediction=pred * spreads[1] + centers[1], beta)
write.csv(output, args[4], row.names=FALSE)
runtime <- c(
  R_version=R.version.string, pracma_version=as.character(packageVersion("pracma")),
  elapsed_seconds=as.character(proc.time()[[3]] - started),
  standardization=settings$standardization, prior=settings$prior
)
write.dcf(as.data.frame(as.list(runtime)), paste0(args[4], ".runtime.dcf"))
