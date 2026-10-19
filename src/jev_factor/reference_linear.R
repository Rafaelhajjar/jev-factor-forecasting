# Independent base-R QR check of the Python least-squares benchmark forecasts.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 3L) stop("Expected masked matrix CSV, ntrain and output CSV")
data <- read.csv(args[1], check.names=FALSE)
ntrain <- as.integer(args[2])
if (ntrain < 20L || ntrain >= nrow(data)) stop("Invalid train/test split")
train <- data[seq_len(ntrain), , drop=FALSE]
test <- data[seq.int(ntrain + 1L, nrow(data)), , drop=FALSE]
ar_terms <- paste0("y_lag", 1:4)
factor_terms <- c("F1_lag1", "F1_lag2", "F2_lag1", "F2_lag2")
ar <- lm(reformulate(ar_terms, response="target"), data=train)
fa <- lm(reformulate(c(ar_terms, factor_terms), response="target"), data=train)
result <- data.frame(AR4=as.numeric(predict(ar, test)), FA_AR=as.numeric(predict(fa, test)))
if (any(!is.finite(as.matrix(result)))) stop("Nonfinite QR predictions")
write.csv(result, args[3], row.names=FALSE)
cat(R.version.string, "\n")
