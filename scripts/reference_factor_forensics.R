# Independent base-R checks of the crisis-window training PCA and MAFs.
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 7L) stop("Expected training z, query z, SW flags, MAF training matrix, output, levels, codes")
x <- as.matrix(read.csv(args[1], check.names=FALSE))
q <- as.matrix(read.csv(args[2], check.names=FALSE))
sw <- read.csv(args[3])$selected == 1
maf <- as.matrix(read.csv(args[4], check.names=FALSE))
if (ncol(x) != 247L || sum(sw) != 125L || ncol(maf) != 8L*ncol(x))
  stop("Unexpected forensic input dimensions")
for (kind in c("all", "SW125")) {
  kept <- if (kind == "all") rep(TRUE, ncol(x)) else sw
  fit <- prcomp(x[,kept], center=TRUE, scale.=FALSE, rank.=5L)
  write.csv(t(fit$rotation[,1:5]), file.path(args[5], paste0(kind,"_rotation.csv")), row.names=FALSE)
  write.csv(predict(fit, q[,kept])[,1:5], file.path(args[5], paste0(kind,"_scores.csv")), row.names=FALSE)
}
rotations <- lapply(seq_len(ncol(x)), function(j) {
  fit <- prcomp(maf[,seq.int((j-1L)*8L+1L,j*8L)], center=TRUE, scale.=FALSE, rank.=2L)
  rotation <- t(fit$rotation[,1:2])
  colnames(rotation) <- paste0("lag",1:8)
  data.frame(series_index=j-1L, component=1:2, rotation)
})
write.csv(do.call(rbind,rotations),file.path(args[5],"MAF_rotation.csv"),row.names=FALSE)
writeLines(R.version.string,file.path(args[5],"runtime.txt"))
levels <- as.matrix(read.csv(args[6],check.names=FALSE))
codes <- read.csv(args[7])$code
convert <- function(v,code) {
  if(code==1L) return(v)
  if(code==2L) return(c(NA_real_,diff(v)))
  if(code==3L) return(c(NA_real_,NA_real_,diff(v,differences=2)))
  if(code %in% 4:6) {
    logs <- ifelse(v>0,log(ifelse(v>0,v,NA_real_)),NA_real_)
    if(code==4L) return(logs)
    if(code==5L) return(c(NA_real_,diff(logs)))
    return(c(NA_real_,NA_real_,diff(logs,differences=2)))
  }
  if(code==7L) {
    growth <- c(NA_real_,v[-1]/head(v,-1)-1)
    out <- c(NA_real_,diff(growth))
    out[!is.finite(out)] <- NA_real_
    return(out)
  }
  stop("Unknown transformation")
}
transformed <- vapply(seq_len(ncol(levels)),function(j) convert(levels[,j],codes[j]),numeric(nrow(levels)))
colnames(transformed) <- colnames(levels)
write.csv(transformed,file.path(args[5],"independent-transformed.csv"),row.names=FALSE)
training_raw <- transformed[seq_len(nrow(x))+2L,,drop=FALSE]
med <- apply(training_raw,2,median,na.rm=TRUE)
quartiles <- apply(training_raw,2,quantile,probs=c(.25,.75),type=5,na.rm=TRUE)
iqr <- quartiles[2,]-quartiles[1,]
query_raw <- transformed[seq_len(nrow(q))+2L,,drop=FALSE]
mask <- abs(sweep(query_raw,2,med,"-")) > matrix(10*iqr,nrow(q),ncol(q),byrow=TRUE)
mask[is.na(mask)] <- FALSE
write.csv(mask*1L,file.path(args[5],"independent-outlier-mask.csv"),row.names=FALSE)
write.csv(data.frame(median=med,IQR=iqr),file.path(args[5],"independent-outlier-thresholds.csv"),row.names=FALSE)
