# Independent base-R check of the pinned FRED jj=2, DEMEAN=2 recipe.
# Gram-eigen/residual-matrix calculations intentionally differ from Python's
# direct-SVD/tail-sum implementation. This is not execution of MATLAB source.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 6) stop("Expected input, output directory, kmax, maxit, tolerance, state PC count")
x <- as.matrix(read.csv(args[1], check.names=FALSE))
directory <- args[2]
kmax <- as.integer(args[3]); maxit <- as.integer(args[4])
tolerance <- as.numeric(args[5]); state_rank <- as.integer(args[6])
if (any(is.infinite(x)) || any(colSums(!is.na(x))==0) || any(rowSums(!is.na(x))==0)) stop("Invalid input")
med <- apply(x, 2, median, na.rm=TRUE)
quartiles <- apply(x, 2, quantile, probs=c(.25,.75), type=5, na.rm=TRUE)
outlier <- abs(sweep(x, 2, med, "-")) > matrix(10*(quartiles[2,]-quartiles[1,]), nrow(x), ncol(x), byrow=TRUE)
outlier[is.na(outlier)] <- FALSE
x[outlier] <- NA_real_
if (any(colSums(!is.na(x))==0) || any(rowSums(!is.na(x))==0)) stop("Invalid cleaned input")
missing <- is.na(x)
filled <- x
initial <- matrix(colMeans(x, na.rm=TRUE), nrow(x), ncol(x), byrow=TRUE)
filled[missing] <- initial[missing]
step <- function(values) {
  mu <- colMeans(values); sigma <- apply(values, 2, sd)
  if (any(!is.finite(sigma)) || any(sigma<=1e-12)) stop("Invalid series variance")
  z <- sweep(sweep(values, 2, mu, "-"), 2, sigma, "/")
  vectors <- eigen(crossprod(z), symmetric=TRUE)$vectors
  candidates <- c(seq_len(kmax), 0L)
  criteria <- vapply(candidates, function(k) {
    v <- vectors[,seq_len(k),drop=FALSE]
    residual <- z - (z %*% v) %*% t(v)
    log(mean(residual^2)) + k*(nrow(z)+ncol(z))/(nrow(z)*ncol(z))*log(min(dim(z)))
  }, numeric(1))
  best <- which(criteria==min(criteria))
  if (length(best)!=1) stop("Nonunique source criterion minimum")
  rank <- candidates[best]
  basis <- vectors[,seq_len(rank),drop=FALSE]
  list(mu=mu, sigma=sigma, z=z, rank=rank, chat=(z %*% basis) %*% t(basis))
}
state <- step(filled)
history <- data.frame(iteration=0L, rank=state$rank, error=NA_real_)
err <- 999; it <- 0L
while (isTRUE(err>tolerance) && it<maxit) {
  it <- it+1L
  prediction <- sweep(sweep(state$chat, 2, state$sigma, "*"), 2, state$mu, "+")
  filled[missing] <- prediction[missing]
  previous <- state$chat
  state <- step(filled)
  err <- sum((state$chat-previous)^2)/sum(previous^2)
  history <- rbind(history, data.frame(iteration=it, rank=state$rank, error=err))
}
converged <- is.finite(err) && err<=tolerance
reason <- if (converged) "tolerance_met" else if (is.na(err)) "zero_reconstruction_undefined_ratio" else "iteration_cap"
write_matrix <- function(values, filename) {
  result <- as.data.frame(values)
  colnames(result) <- colnames(x)
  write.csv(result, file.path(directory, filename), row.names=FALSE, na="")
}
write_matrix(x, "cleaned.csv")
write_matrix(filled, "filled.csv")
write_matrix(state$z, "standardized.csv")
write.csv(history, file.path(directory, "history.csv"), row.names=FALSE, na="")
rotation <- t(prcomp(state$z, center=TRUE, scale.=FALSE)$rotation[,seq_len(state_rank),drop=FALSE])
write.csv(data.frame(component=seq_len(state_rank), rotation, check.names=FALSE),
          file.path(directory, "rotation.csv"), row.names=FALSE)
write.dcf(as.data.frame(as.list(c(R_version=R.version.string, iterations=it, converged=converged,
                                at_iteration_cap=it==maxit, stopping_reason=reason,
                                training_outliers=sum(outlier)))),
          file.path(directory, "metadata.dcf"))
