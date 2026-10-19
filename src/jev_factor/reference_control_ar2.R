# Independent QR check for the plain-control AR(2) filter; no forest fitting.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 3) stop("Expected matrix, training length, directory")
options(digits=17)
data <- read.csv(args[1], check.names=FALSE)
ntrain <- as.integer(args[2])
if (ntrain < 4 || ntrain >= nrow(data)) stop("Invalid training length")
x <- cbind(intercept=1, as.matrix(data[, c("y_lag1", "y_lag2")]))
y <- data$target[seq_len(ntrain)]
beta <- qr.solve(x[seq_len(ntrain), , drop=FALSE], y)
prediction <- as.vector(x %*% beta)
write.csv(data.frame(term=colnames(x), coefficient=as.vector(beta)),
          file.path(args[3], "beta.csv"), row.names=FALSE)
write.csv(data.frame(prediction=prediction), file.path(args[3], "prediction.csv"), row.names=FALSE)
write.csv(data.frame(residual=y-prediction[seq_len(ntrain)]),
          file.path(args[3], "residual.csv"), row.names=FALSE)
cat(R.version.string, "\n")
