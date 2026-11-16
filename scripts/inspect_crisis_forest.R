# Inspect a storage-only replay without calling MRF again or refitting any leaf.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 4L) stop("Expected replay RDS, original raw matrix, ntrain, output")
fit <- readRDS(args[1])
raw <- as.matrix(read.csv(args[2],check.names=FALSE))
ntrain <- as.integer(args[3])
train <- seq_len(ntrain)
data <- fit$model$data
# Match the training-only normalization inside each native tree.
mu <- colMeans(data[train,,drop=FALSE])
sigma <- apply(data[train,,drop=FALSE],2,sd)
native <- as.data.frame(sweep(sweep(data,2,mu,"-"),2,sigma,"/"))
rownames(native) <- NULL
xpos <- fit$model$x.pos
Z <- cbind(1,data[,xpos,drop=FALSE])
centers <- colMeans(raw[train,,drop=FALSE])
spreads <- apply(raw[train,,drop=FALSE],2,sd)
rows <- list()
support <- list()
maximum <- 0
for (b in seq_len(fit$model$B)) {
  leafs <- fit$model$forest[[b]]
  assignment <- integer(nrow(data))
  for (i in seq_len(nrow(leafs))) {
    in_leaf <- which(with(native,eval(parse(text=leafs$FILTER[i]))))
    assignment[in_leaf] <- assignment[in_leaf]+1L
    members <- intersect(in_leaf,train)
    if (length(members)==0L) stop("A retained leaf lacks training support")
    beta <- fit$betas.draws.raw[members[1],,b]
    maximum <- max(maximum,max(abs(sweep(fit$betas.draws.raw[in_leaf,,b,drop=FALSE][,,1],2,beta,"-"))))
    point <- ntrain+1L
    if (point %in% in_leaf) {
      original_beta <- beta
      original_beta[-1] <- beta[-1]*spreads[1]/spreads[xpos]
      original_beta[1] <- beta[1]*spreads[1]+centers[1]-sum(original_beta[-1]*centers[xpos])
      names(original_beta) <- c("intercept",colnames(raw)[xpos])
      rows[[b]] <- data.frame(tree=b, node=leafs$NODE[i], split_sample_n=leafs$NOBS[i],
        training_leaf_n=length(members), path=leafs$FILTER[i],t(original_beta),check.names=FALSE)
      support[[b]] <- data.frame(tree=b,row_index=members,
        used_for_splits=members %in% fit$model$random.vecs[[b]])
    }
  }
  if (any(assignment!=1L)) stop("Leaf paths are not an exhaustive disjoint partition")
  reconstructed <- rowSums(Z*fit$betas.draws.raw[,,b])*spreads[1]+centers[1]
  if (max(abs(reconstructed[-train]-(fit$pred.ensemble[b,]*spreads[1]+centers[1])))>1e-10)
    stop("Tree forecast reconstruction failed")
}
if (maximum>1e-10) stop("Stored coefficient blocks disagree with tree paths")
write.csv(do.call(rbind,rows),file.path(args[4],"crisis-routed-leaves.csv"),row.names=FALSE)
write.csv(do.call(rbind,support),file.path(args[4],"crisis-leaf-support.csv"),row.names=FALSE)
write.csv(data.frame(maximum_within_leaf_coefficient_difference=maximum),
          file.path(args[4],"leaf-verification.csv"),row.names=FALSE)
