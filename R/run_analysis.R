# R twin of python/run_analysis.py: same data, same questions, same statistics.
#   Rscript R/run_analysis.R        # ~20 s; writes results/*_r.csv and checks them against the Python results
# Packages: cluster (ships with R); nothing else.

source(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1])), "whisky_data.R"))
suppressPackageStartupMessages(library(cluster))
set.seed(20260926)
N_PERM <- 9999
K_GEO <- 5
OUT <- file.path(ROOT, "results")
dir.create(OUT, showWarnings = FALSE)

a <- load_atlas()
X <- as.matrix(a[, FLAVOURS])
n <- nrow(X)

# ---- 1. flavour map: covariance PCA, largest loading of each PC positive (as in Python) ----
pc <- prcomp(X, center = TRUE, scale. = FALSE)
flip <- sign(pc$rotation[cbind(apply(abs(pc$rotation), 2, which.max), seq_len(ncol(X)))])
rot <- sweep(pc$rotation, 2, flip, `*`)
scores <- sweep(pc$x, 2, flip, `*`)
var_ratio <- pc$sdev^2 / sum(pc$sdev^2)

# ---- 2. clusters: Ward, k by silhouette; k-means as a check ----
ari <- function(x, y) {
  tab <- table(x, y); c2 <- function(v) sum(v * (v - 1) / 2)
  idx <- c2(tab); ea <- c2(rowSums(tab)) * c2(colSums(tab)) / c2(length(x))
  (idx - ea) / ((c2(rowSums(tab)) + c2(colSums(tab))) / 2 - ea)
}
hc <- hclust(dist(X), method = "ward.D2")
sil <- sapply(2:8, function(k) mean(silhouette(cutree(hc, k), dist(X))[, "sil_width"]))
names(sil) <- 2:8
k <- as.integer(names(which.max(sil)))
ward <- cutree(hc, k)
km <- kmeans(X, k, nstart = 50)$cluster

# ---- 3. geography ----
G <- haversine_km(a$lat, a$lon)
Fd <- as.matrix(dist(X))
mantel <- function(D1, D2) {                                   # Spearman Mantel test, one-sided
  iu <- upper.tri(D1)
  r1 <- rank(D1[iu])
  R2 <- matrix(0, nrow(D2), ncol(D2)); R2[iu] <- rank(D2[iu]); R2 <- R2 + t(R2)
  stat <- function(p) cor(r1, R2[p, p][iu])
  obs <- stat(seq_len(nrow(D1)))
  null <- replicate(N_PERM, stat(sample(nrow(D1))))
  c(rho = round(obs, 4), p = round((1 + sum(null >= obs)) / (N_PERM + 1), 4))
}
geo_skill <- function(X, G) {                                  # leave-one-out, 5 nearest on the map vs mean of the rest
  D <- G + diag(Inf, nrow(G))
  nb <- t(apply(D, 1, function(r) order(r, method = "radix")[1:K_GEO]))
  pred <- t(apply(nb, 1, function(j) colMeans(X[j, , drop = FALSE])))
  loo <- (matrix(colSums(X), nrow(X), ncol(X), byrow = TRUE) - X) / (nrow(X) - 1)
  rmse <- function(P) sqrt(colMeans((X - P)^2))
  1 - rmse(pred) / rmse(loo)
}
keep <- !a$islay
m_all <- mantel(Fd, G)
m_no <- mantel(Fd[keep, keep], G[keep, keep])
skill <- geo_skill(X, G)
null <- replicate(999, geo_skill(X[sample(n), ], G))
p_geo <- (1 + rowSums(null >= skill)) / 1000
geo <- data.frame(attribute = FLAVOURS, skill = round(skill, 4), p_perm = round(p_geo, 4),
                  p_holm = round(p.adjust(p_geo, "holm"), 4), skill_without_islay = round(geo_skill(X[keep, ], G[keep, keep]), 4),
                  rho_longitude = round(sapply(FLAVOURS, function(f) cor(a[[f]], a$lon, method = "spearman")), 4),
                  rho_latitude = round(sapply(FLAVOURS, function(f) cor(a[[f]], a$lat, method = "spearman")), 4))
write.csv(geo, file.path(OUT, "geography_r.csv"), row.names = FALSE)

# ---- 4. Whisky Advocate ----
wa <- NULL
if (file.exists(REVIEWS)) {
  r <- load_reviews(atlas = a)
  pr <- r[!is.na(r$price_usd), ]
  fit <- lm(points ~ log2(price_usd), data = pr)
  fit_age <- lm(points ~ log2(price_usd) + ifelse(is.na(age), 0, age) + !is.na(age), data = pr)
  r$residual <- NA; r$residual[!is.na(r$price_usd)] <- residuals(fit)
  linked <- r[!is.na(r$distillery), ]
  by <- do.call(rbind, lapply(split(linked, linked$distillery), function(g) data.frame(
    distillery = g$distillery[1], n = nrow(g), median_points = median(g$points),
    median_price = median(g$price_usd, na.rm = TRUE), median_residual = round(median(g$residual, na.rm = TRUE), 3))))
  write.csv(by, file.path(OUT, "distillery_scores_r.csv"), row.names = FALSE)
  big <- merge(by[by$n >= 5, ], a[, c("distillery", FLAVOURS)], by = "distillery")
  z <- function(v) (v - mean(v)) / sqrt(mean((v - mean(v))^2))
  Rm <- apply(big[, FLAVOURS], 2, function(v) z(rank(v))); ry <- z(rank(big$median_points))
  rho <- as.vector(crossprod(Rm, ry)) / nrow(big)
  nullr <- t(replicate(N_PERM, as.vector(crossprod(Rm, sample(ry))) / nrow(big)))
  p_fp <- (1 + colSums(abs(nullr) >= matrix(abs(rho) - 1e-12, N_PERM, 12, byrow = TRUE))) / (N_PERM + 1)
  fv <- data.frame(attribute = FLAVOURS, rho = round(rho, 4), p_perm = round(p_fp, 4), p_holm = round(p.adjust(p_fp, "holm"), 4))
  write.csv(fv, file.path(OUT, "flavour_vs_points_r.csv"), row.names = FALSE)
  ci <- confint(fit)[2, ]
  wa <- list(n_linked = sum(!is.na(r$distillery)), n_distilleries_5plus = nrow(big),
             points_per_doubling = round(unname(coef(fit)[2]), 3), ci95 = round(unname(ci), 3),
             points_per_doubling_age_adjusted = round(unname(coef(fit_age)[2]), 3),
             price_spearman = round(cor(pr$price_usd, pr$points, method = "spearman"), 4),
             text_alignment = text_alignment(r))
}

# ---- report + parity with Python ----
cat(sprintf("PCA variance: %s\nsilhouette: %s  (k = %d, ARI Ward vs k-means %.4f)\n",
            paste(round(var_ratio[1:3], 4), collapse = " "), paste(round(sil, 4), collapse = " "), k, ari(ward, km)))
cat(sprintf("Mantel rho %.4f (p %.4f); without Islay %.4f (p %.4f)\n", m_all["rho"], m_all["p"], m_no["rho"], m_no["p"]))
print(geo[, c("attribute", "skill", "p_holm", "skill_without_islay")], row.names = FALSE)
if (!is.null(wa)) { str(wa); print(fv, row.names = FALSE) }

py <- file.path(OUT, "metrics.json")
if (file.exists(py)) {
  M <- jsonlite::fromJSON(py)
  chk <- c(pca = max(abs(round(var_ratio[1:3], 4) - M$atlas$pca_var)),
           loadings = max(abs(round(rot[, 1:3], 4) - as.matrix(read.csv(file.path(OUT, "pca_loadings.csv"), row.names = 1)))),
           silhouette_k2 = abs(round(sil[["2"]], 4) - M$atlas$silhouette[["2"]]),
           mantel = abs(m_all[["rho"]] - M$geography$mantel_rho) + abs(m_no[["rho"]] - M$geography$mantel_rho_without_islay),
           skill = max(abs(geo$skill - read.csv(file.path(OUT, "geography.csv"))$skill)))
  if (!is.null(wa)) chk <- c(chk, slope = abs(wa$points_per_doubling - M$whisky_advocate$points_per_doubling),
                             rho = max(abs(fv$rho - read.csv(file.path(OUT, "flavour_vs_points.csv"))$rho)),
                             linked = abs(wa$n_linked - M$whisky_advocate$n_linked),
                             alignment = max(abs(unlist(wa$text_alignment) - unlist(M$whisky_advocate$text_alignment))))
  cat("\nParity with Python (max abs difference; p-values differ only by random permutations):\n")
  print(signif(chk, 3))
  cat(sprintf("Silhouettes for k >= 3 differ by up to %.3f: with integer scores many Ward merges tie, and R and SciPy break ties differently. Both pick k = %d.\n",
              max(abs(round(sil, 4) - unlist(M$atlas$silhouette))), k))
}
