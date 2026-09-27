"""Does Scotch flavour follow geography — and does Whisky Advocate reward any flavour? Every README number comes from here.

    python python/run_analysis.py      # ~30 s; writes results/
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.stats import rankdata, spearmanr
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

from whisky.data import FLAVOURS, REVIEWS, ROOT, haversine_km, load_atlas, load_reviews, text_alignment

OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
SEED = 20260926
N_PERM = 9999
K_GEO = 5          # geographic neighbours used to predict a distillery's profile


def pca(X: np.ndarray):
    """Covariance PCA — all 12 scores share the 0-4 scale; standardising would inflate near-constant Tobacco."""
    Xc = X - X.mean(0)
    _, s, vt = np.linalg.svd(Xc, full_matrices=False)
    vt *= np.sign(vt[np.arange(len(vt)), np.abs(vt).argmax(1)])[:, None]   # largest loading positive (R does the same)
    return Xc @ vt.T, vt, s ** 2 / (s ** 2).sum()


def holm(p: np.ndarray) -> np.ndarray:
    o = np.argsort(p)
    adj = np.maximum.accumulate((len(p) - np.arange(len(p))) * p[o])
    out = np.empty_like(p)
    out[o] = np.minimum(adj, 1)
    return out


def mantel(D1: np.ndarray, D2: np.ndarray, rng) -> tuple[float, float]:
    """Spearman Mantel test, one-sided (closer distilleries taste more alike)."""
    iu = np.triu_indices_from(D1, 1)
    r1 = rankdata(D1[iu])
    R2 = np.zeros_like(D2)
    R2[iu] = rankdata(D2[iu])
    R2 = R2 + R2.T
    stat = lambda p: np.corrcoef(r1, R2[np.ix_(p, p)][iu])[0, 1]
    obs = stat(np.arange(len(D1)))
    null = np.array([stat(rng.permutation(len(D1))) for _ in range(N_PERM)])
    return round(float(obs), 4), round(float((1 + (null >= obs).sum()) / (N_PERM + 1)), 4)


def spearman_perm(M: np.ndarray, y: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """Spearman rho of every column of M with y; two-sided permutation p (the same shuffles for every column)."""
    z = lambda v: (v - v.mean(0)) / v.std(0)
    Rm, ry = z(np.apply_along_axis(rankdata, 0, M)), z(rankdata(y))
    rho = Rm.T @ ry / len(y)
    null = np.stack([ry[rng.permutation(len(y))] for _ in range(N_PERM)]) @ Rm / len(y)
    return rho, (1 + (np.abs(null) >= np.abs(rho) - 1e-12).sum(0)) / (N_PERM + 1)


def geo_knn_skill(X: np.ndarray, G: np.ndarray) -> np.ndarray:
    """Leave-one-out: predict each distillery's scores from its K_GEO nearest neighbours on the map.
    Skill = 1 - RMSE(neighbours) / RMSE(mean of all other distilleries); > 0 means location helps."""
    n = len(X)
    D = G + np.diag(np.full(n, np.inf))
    nb = np.argsort(D, axis=1, kind="stable")[:, :K_GEO]
    pred = X[nb].mean(1)
    loo_mean = (X.sum(0) - X) / (n - 1)
    rmse = lambda P: np.sqrt(((X - P) ** 2).mean(0))
    return 1 - rmse(pred) / rmse(loo_mean)


def main() -> None:
    rng = np.random.default_rng(SEED)
    a = load_atlas()
    X = a[FLAVOURS].to_numpy(float)
    n = len(a)

    # ---- 1. flavour map (PCA) ----
    scores, vt, var = pca(X)
    load = pd.DataFrame(vt[:3].T, index=FLAVOURS, columns=["PC1", "PC2", "PC3"]).round(4)
    load.to_csv(OUT / "pca_loadings.csv")

    # ---- 2. clusters: Ward, k chosen by silhouette; k-means as a robustness check ----
    Z = linkage(X, "ward")
    sil = {k: round(float(silhouette_score(X, fcluster(Z, k, "maxclust"))), 4) for k in range(2, 9)}
    k = max(sil, key=sil.get)
    ward = fcluster(Z, k, "maxclust")
    km = KMeans(k, n_init=50, random_state=SEED).fit_predict(X)
    prof = a.assign(cluster=ward).groupby("cluster")[FLAVOURS].mean().round(2)
    prof["n"] = np.bincount(ward)[1:]
    prof["members"] = [", ".join(a.loc[ward == c, "distillery"].head(6)) for c in prof.index]
    prof.to_csv(OUT / "cluster_profiles.csv")

    # ---- 3. does flavour follow geography? ----
    G = haversine_km(a["lat"].to_numpy(), a["lon"].to_numpy())
    F = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
    keep = ~a["islay"].to_numpy()
    mantel_all = mantel(F, G, rng)
    mantel_no_islay = mantel(F[np.ix_(keep, keep)], G[np.ix_(keep, keep)], rng)
    skill = geo_knn_skill(X, G)
    null = np.array([geo_knn_skill(X[rng.permutation(n)], G) for _ in range(999)])
    p = (1 + (null >= skill).sum(0)) / 1000
    skill_no_islay = geo_knn_skill(X[keep], G[np.ix_(keep, keep)])
    geo = pd.DataFrame({"attribute": FLAVOURS, "skill": skill.round(4), "p_perm": p.round(4),
                        "p_holm": holm(p).round(4), "skill_without_islay": skill_no_islay.round(4),
                        "rho_longitude": [round(float(spearmanr(X[:, j], a["lon"]).statistic), 4) for j in range(12)],
                        "rho_latitude": [round(float(spearmanr(X[:, j], a["lat"]).statistic), 4) for j in range(12)]})
    geo.to_csv(OUT / "geography.csv", index=False)
    print(geo.to_string(index=False))

    # ---- 4. Whisky Advocate: price → points, and which atlas flavours go with higher scores ----
    metrics = {"atlas": {"n": n, "islay": int((~keep).sum()), "styles": a["style"].value_counts().to_dict(),
                         "distinct_points": int(len(a[["lat", "lon"]].drop_duplicates())),
                         "sharing_a_point": int(a.duplicated(["lat", "lon"], keep=False).sum()),
                         "pca_var": [round(float(v), 4) for v in var[:3]], "silhouette": sil, "k": k,
                         "ari_ward_kmeans": round(float(adjusted_rand_score(ward, km)), 4)},
               "geography": {"mantel_rho": mantel_all[0], "mantel_p": mantel_all[1],
                             "mantel_rho_without_islay": mantel_no_islay[0], "mantel_p_without_islay": mantel_no_islay[1],
                             "k_neighbours": K_GEO, "n_perm": N_PERM}}
    pd.DataFrame({"distillery": a["distillery"], "cluster": ward, "kmeans": km,
                  "pc1": scores[:, 0].round(4), "pc2": scores[:, 1].round(4)}).to_csv(OUT / "atlas_scores.csv", index=False)

    if REVIEWS.exists():
        r = load_reviews(atlas=a)
        pr = r.dropna(subset=["price_usd"]).copy()
        lp = np.log2(pr["price_usd"])
        ols = sm.OLS(pr["points"], sm.add_constant(lp)).fit()
        ols_age = sm.OLS(pr["points"], sm.add_constant(pd.DataFrame(
            {"lp": lp, "age": pr["age"].fillna(0), "has_age": pr["age"].notna().astype(float)}))).fit()
        r.loc[pr.index, "residual"] = pr["points"] - ols.fittedvalues
        lo, hi = ols.conf_int().iloc[1]
        by = (r.dropna(subset=["distillery"]).groupby("distillery")
              .agg(n=("points", "size"), median_points=("points", "median"), median_price=("price_usd", "median"),
                   median_residual=("residual", "median")).round(3))
        by.to_csv(OUT / "distillery_scores.csv")
        big = by[by["n"] >= 5].join(a.set_index("distillery")[FLAVOURS])
        rho, p2 = spearman_perm(big[FLAVOURS].to_numpy(float), big["median_points"].to_numpy(), rng)
        fv = pd.DataFrame({"attribute": FLAVOURS, "rho": rho.round(4), "p_perm": p2.round(4), "p_holm": holm(p2).round(4)})
        fv.to_csv(OUT / "flavour_vs_points.csv", index=False)
        print(fv.to_string(index=False))
        metrics["whisky_advocate"] = {
            "n_reviews": int(len(r)), "n_single_malt": int((r["category"] == "Single Malt Scotch").sum()),
            "n_linked": int(r["distillery"].notna().sum()), "n_distilleries_linked": int(r["distillery"].nunique()),
            "n_distilleries_5plus": int(len(big)), "n_priced": int(len(pr)),
            "price_spearman": round(float(spearmanr(pr["price_usd"], pr["points"]).statistic), 4),
            "points_per_doubling": round(float(ols.params.iloc[1]), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)],
            "points_per_doubling_age_adjusted": round(float(ols_age.params["lp"]), 3),
            "intercept": round(float(ols.params.iloc[0]), 4), "slope": round(float(ols.params.iloc[1]), 4),
            "age_price_spearman": round(float(spearmanr(pr["age"], pr["price_usd"], nan_policy="omit").statistic), 4),
            "text_alignment": text_alignment(r)}
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=1, ensure_ascii=False))
    print(json.dumps(metrics, indent=1))


if __name__ == "__main__":
    main()
