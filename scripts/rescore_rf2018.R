# Independent base-R arithmetic check, not another fitted forecasting model.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 3L) stop("prediction CSV, metric CSV, verification CSV")
p <- read.csv(args[1], stringsAsFactors=FALSE)
m <- read.csv(args[2], stringsAsFactors=FALSE)
if (any(!is.finite(p$actual)) || any(!is.finite(p$prediction))) stop("Nonfinite forecast")
base <- p[p$model == "AR4", ]
base <- base[order(base$target_date), ]
if (nrow(base) != 48L || anyDuplicated(base$target_date)) stop("Invalid AR grid")
denom <- sqrt(mean((base$actual-base$prediction)^2))
checks <- lapply(unique(p$model), function(name) {
  x <- p[p$model == name, ]
  x <- x[order(x$target_date), ]
  if (!identical(x$target_date,base$target_date) || anyDuplicated(x$target_date) ||
      max(abs(x$actual-base$actual)) > 1e-14) stop("Mismatched outcomes/dates")
  actual <- c(n=nrow(x), RMSE=sqrt(mean((x$actual-x$prediction)^2)),
              MAE=mean(abs(x$actual-x$prediction)))
  actual <- c(actual, RMSE_over_AR4=unname(actual["RMSE"])/denom)
  reported <- as.numeric(m[m$model == name, names(actual)])
  if (length(reported) != 4L || max(abs(actual-reported)) > 1e-12) stop("Metric differs")
  data.frame(model=name, t(actual), max_difference=max(abs(actual-reported)))
})
verified <- do.call(rbind, checks)
options(digits=17)
write.csv(verified, args[3], row.names=FALSE)
print(verified)
