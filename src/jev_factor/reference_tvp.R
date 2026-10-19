# Execute the external GPL entry point; trace records only, not algorithm changes.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 3L) stop("Expected external source, R library, fit directory")
options(digits=17)
.libPaths(c(normalizePath(args[2]), .libPaths()))
suppressPackageStartupMessages({
  library(pracma)
  library(fGarch)
  library(matrixcalc)
})
for (p in names(c(pracma="2.4.6", fGarch="4052.93", matrixcalc="1.0.6"))) {
  expected <- c(pracma="2.4.6", fGarch="4052.93", matrixcalc="1.0.6")[[p]]
  if (as.character(packageVersion(p)) != expected) stop(paste("Wrong version of", p))
}
destination <- normalizePath(args[3])
setwd(destination) # The unmodified native hush() creates its own NUL scratch file.
training <- read.csv("train.csv", check.names=FALSE)
forecast_x <- as.matrix(read.csv("forecast_x.csv", check.names=FALSE))
settings <- read.dcf("settings.dcf")[1, ]
scope <- new.env(parent=globalenv())
scope$.native_capture <- new.env(parent=emptyenv())
sys.source(normalizePath(args[1]), envir=scope)
trace("CV.KF.MV", exit=quote({
  .native_capture$first <- list(folds=index, errors=PMSE)
}), where=scope, print=FALSE)
trace("cv.univariate", exit=quote({
  .native_capture$second <- list(folds=index, errors=PMSE)
}), where=scope, print=FALSE)
trace("tvp.ridge", exit=quote({
  .native_capture$final <- list(
    first_lambda=lambda1, second_lambda=usethislambda1, increment_weights=sigmasq,
    first_index=match(lambda1, lambdavec), second_index=match(usethislambda1, lambdavec),
    garch_input=e, sigma=garchstuff@sigma.t, garch_coefficients=coef(garchstuff),
    garch_convergence=garchstuff@fit$convergence
  )
}), where=scope, print=FALSE)
result <- scope$tvp.ridge(
  X=as.matrix(training[, -1, drop=FALSE]), Y=as.matrix(training$target),
  lambda.candidates=as.numeric(strsplit(settings["lambda_candidates"], ",", fixed=TRUE)[[1]]),
  oosX=as.numeric(forecast_x[1, ]), lambda2=as.numeric(settings["lambda2"]),
  kfold=as.integer(settings["kfold"]), CV.plot=FALSE, CV.2SRR=TRUE,
  sig.u.param=as.numeric(settings["sig_u"]), sig.eps.param=as.numeric(settings["sig_eps"]),
  ols.prior=as.numeric(settings["ols_prior"])
)
captured <- scope$.native_capture
rr <- t(result$betas.rr[1,,])
second <- t(result$betas.2srr[1,,])
colnames(rr) <- colnames(second) <- c("intercept", colnames(training)[-1])
write.csv(rr, "beta_rr.csv", row.names=FALSE)
write.csv(second, "beta_2srr.csv", row.names=FALSE)
write.csv(data.frame(rr=as.vector(result$yhat.rr), second=as.vector(result$yhat.2srr)),
          "fitted.csv", row.names=FALSE)
write.csv(data.frame(prediction=as.vector(cbind(1, forecast_x) %*% second[nrow(second),])),
          "predictions.csv", row.names=FALSE)
write.csv(data.frame(first=captured$first$folds, second=captured$second$folds),
          "folds.csv", row.names=FALSE)
write.csv(captured$first$errors, "cv_first.csv", row.names=FALSE)
write.csv(captured$second$errors, "cv_second.csv", row.names=FALSE)
write.csv(data.frame(weight=captured$final$increment_weights),
          "increment_weights.csv", row.names=FALSE)
write.csv(data.frame(input=as.vector(captured$final$garch_input),
                     sigma=captured$final$sigma, weight=as.vector(result$sig.eps)),
          "volatility.csv", row.names=FALSE)
coefficients <- captured$final$garch_coefficients
write.csv(data.frame(term=names(coefficients), coefficient=as.numeric(coefficients)),
          "garch_coefficients.csv", row.names=FALSE)
runtime <- c(
  R_version=R.version.string, version_pracma=as.character(packageVersion("pracma")),
  version_fGarch=as.character(packageVersion("fGarch")),
  version_matrixcalc=as.character(packageVersion("matrixcalc")),
  lambda_step1=format(captured$final$first_lambda, digits=17),
  lambda_step2=format(captured$final$second_lambda, digits=17),
  lambda_step1_index=as.character(captured$final$first_index),
  lambda_step2_index=as.character(captured$final$second_index),
  lambda_returned=format(result$lambdas[1], digits=17),
  public_first_forecast=format(result$forecast[1], digits=17),
  garch_convergence=as.character(captured$final$garch_convergence)
)
for (p in sort(loadedNamespaces())) {
  runtime[paste0("namespace_", p)] <- as.character(packageVersion(p))
}
write.dcf(as.data.frame(as.list(runtime)), file="native.dcf", width=10000)
cat("Pinned native TVP completed; both CV stages and final lambda captured\n")
