"""Export what the static app needs into web/data/whisky.json, plus the README figures.

    python python/build_web.py      # after run_analysis.py
"""
from __future__ import annotations

import json
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from whisky.data import FLAVOURS, REF, REVIEWS, ROOT, load_atlas, load_reviews

RES, WEB, FIG = ROOT / "results", ROOT / "web" / "data", ROOT / "docs"
WEB.mkdir(parents=True, exist_ok=True)
FIG.mkdir(exist_ok=True)
STYLES = ["peated", "sherried", "light", "honeyed"]
LAT0, SCALE, BOX = 57.0, 150.0, (-7.75, -0.6, 54.55, 59.45)      # map window: lon min/max, lat min/max (no Shetland)


def project(lon, lat):
    """Equirectangular map units (y down) — plenty for a country the size of Scotland."""
    x = (np.asarray(lon) - BOX[0]) * np.cos(np.radians(LAT0)) * SCALE
    return np.round(x, 1), np.round((BOX[3] - np.asarray(lat)) * SCALE, 1)


def fan_out(x, y, r=5.0):
    """Distilleries sharing a postcode point are spread on a small circle so every one stays clickable."""
    x, y = x.astype(float).copy(), y.astype(float).copy()
    for _, idx in pd.DataFrame({"x": x, "y": y}).groupby(["x", "y"]).groups.items():
        if len(idx) > 1:
            ang = 2 * np.pi * np.arange(len(idx)) / len(idx)
            x[idx] += r * np.cos(ang); y[idx] += r * np.sin(ang)
    return np.round(x, 1), np.round(y, 1)


def main() -> None:
    a = load_atlas()
    X = a[FLAVOURS].to_numpy(float)
    F = np.sqrt(((X[:, None] - X[None]) ** 2).sum(-1))
    sc = pd.read_csv(RES / "atlas_scores.csv")
    metrics = json.loads((RES / "metrics.json").read_text())
    tr = pd.read_csv(REF / "tr_available.csv", keep_default_na=False)
    tr_idx = {d: [k for k, x in enumerate(tr["distillery"]) if x == d] for d in a["distillery"]}
    on_shelf = np.array([bool(tr_idx[d]) for d in a["distillery"]])

    nb, alt = [], []
    for i in range(len(a)):
        order = [j for j in np.argsort(F[i], kind="stable") if j != i]
        nb.append([[int(j), round(float(F[i, j]), 2)] for j in order[:5]])
        alt.append([[int(j), round(float(F[i, j]), 2)] for j in order if on_shelf[j]][:3])

    x, y = fan_out(*project(a["lon"], a["lat"]))
    d = {"n": a["distillery"].tolist(), "pc": a["postcode"].tolist(), "x": x.tolist(), "y": y.tolist(),
         "lat": a["lat"].round(4).tolist(), "lon": a["lon"].round(4).tolist(), "f": X.astype(int).tolist(),
         "st": [STYLES.index(s) for s in a["style"]], "isl": a["islay"].astype(int).tolist(),
         "p1": sc["pc1"].round(3).tolist(), "p2": sc["pc2"].round(3).tolist(), "nb": nb, "alt": alt,
         "tr": [tr_idx[n] for n in a["distillery"]], "wa": [None] * len(a), "b": [[] for _ in a.index]}

    shelf = tr.drop(columns=["pattern"]).to_dict("records")
    results = {k: metrics[k] for k in ("atlas", "geography")}
    results["geography_table"] = pd.read_csv(RES / "geography.csv").to_dict("records")
    results["loadings"] = pd.read_csv(RES / "pca_loadings.csv", index_col=0)[["PC1", "PC2"]].round(3).T.values.tolist()
    if REVIEWS.exists():
        r = load_reviews(atlas=a)
        ds = pd.read_csv(RES / "distillery_scores.csv").set_index("distillery")
        pos = {n: i for i, n in enumerate(a["distillery"])}
        for name, row in ds.iterrows():
            i = pos[name]
            d["wa"][i] = [int(row.n), row.median_points, None if pd.isna(row.median_price) else row.median_price,
                          None if pd.isna(row.median_residual) else round(row.median_residual, 2)]
            top = (r[r["distillery"] == name].drop_duplicates("name")
                   .sort_values(["points", "price_usd"], ascending=[False, True]).head(5))
            d["b"][i] = [[nm, int(p), None if pd.isna(u) else int(u)] for nm, p, u in zip(top["name"], top["points"], top["price_usd"])]
        for row in shelf:                                   # Whisky Advocate score of each bottle on the Turkish shelf
            pat = tr.loc[tr["product"] == row["product"], "pattern"].iat[0]
            hit = r[r["name"].str.contains(pat, regex=True)] if pat else r.iloc[:0]
            row["wa_points"] = None if hit.empty else float(hit["points"].median())
            row["wa_n"] = int(len(hit))
        wa = metrics["whisky_advocate"]
        pr = r.dropna(subset=["price_usd"])
        edges = [0, 50, 100, 200, 400, 800, np.inf]
        band = pd.cut(pr["price_usd"], edges, right=False)
        g = pr.groupby(band, observed=True)["points"]
        results["price"] = {**{k: wa[k] for k in ("points_per_doubling", "ci95", "price_spearman", "n_priced", "intercept",
                                                  "slope", "points_per_doubling_age_adjusted", "age_price_spearman")},
                            "bands": [[int(iv.left), None if np.isinf(iv.right) else int(iv.right), float(q[0.25]), float(q[0.5]),
                                       float(q[0.75]), int(n)] for (iv, q), n in zip(g.quantile([.25, .5, .75]).unstack().iterrows(), g.size())]}
        results["wa"] = {k: wa[k] for k in ("n_reviews", "n_single_malt", "n_linked", "n_distilleries_linked",
                                            "n_distilleries_5plus", "text_alignment")}
        results["flavour_points"] = pd.read_csv(RES / "flavour_vs_points.csv").to_dict("records")
        v = ds[ds["n"] >= 10].sort_values("median_residual")
        results["value"] = [[n, float(row.median_residual), int(row.n), float(row.median_points)]
                            for n, row in pd.concat([v.head(5), v.tail(5)]).iterrows()]

    outline = json.loads((REF / "scotland_outline.json").read_text())["polygons"]
    paths = []
    for ring in outline:
        px, py = project([p[0] for p in ring], [p[1] for p in ring])
        if px.max() < 0 or py.min() > (BOX[3] - BOX[2]) * SCALE:
            continue
        paths.append("M" + "L".join(f"{u:g},{v:g}" for u, v in zip(px, py)) + "Z")
    W, H = project(BOX[1], BOX[2])
    out = {"generated": pd.Timestamp.now().strftime("%Y-%m-%d"), "flavours": FLAVOURS, "styles": STYLES,
           "map": {"w": float(W), "h": float(H), "path": " ".join(paths)}, "d": d, "shelf": shelf,
           "rules": pd.read_csv(REF / "pairing_rules.csv", keep_default_na=False).to_dict("records"),
           "cheeses": pd.read_csv(REF / "cheeses.csv", keep_default_na=False).to_dict("records"),
           "provinces": pd.read_csv(REF / "provinces.csv")[["province", "lat", "lon"]].values.tolist(),
           "results": results}
    (WEB / "whisky.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("whisky.json", round((WEB / "whisky.json").stat().st_size / 1e3), "kB")
    figures(a, results, paths, W, H, x, y)


def figures(a, results, paths, W, H, x, y) -> None:
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    # 1. map: where the peat is
    fig, ax = plt.subplots(figsize=(5.4, 6.2))
    from matplotlib.path import Path as MPath
    from matplotlib.patches import PathPatch
    for p in paths:
        pts = [tuple(map(float, q.split(","))) for q in re.findall(r"[-\d.]+,[-\d.]+", p)]
        ax.add_patch(PathPatch(MPath(pts + [pts[0]], closed=True), fc="#efe6d8", ec="#b9a88f", lw=0.6))
    peat = a["Smoky"] + a["Medicinal"]
    s = ax.scatter(x, y, c=peat, cmap="YlOrBr", s=26 + 10 * peat, ec="#3b2a1a", lw=0.5, vmin=0, vmax=8)
    left = {"Laphroaig": 12, "Lagavulin": -2, "Ardbeg": -16}           # three Islay neighbours 3 km apart: stack labels
    for i in np.where(peat >= 6)[0]:
        n = a["distillery"][i]
        ax.annotate(n, (x[i], y[i]), xytext=(-16, left[n]) if n in left else (7, -3), textcoords="offset points", fontsize=7.5,
                    ha="right" if n in left else "left", arrowprops={"arrowstyle": "-", "lw": .5, "color": "#6d6358"} if n in left else None)
    ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.set_aspect("equal"); ax.axis("off")
    fig.colorbar(s, ax=ax, shrink=0.45, label="Smoky + Medicinal (0-8)")
    ax.set_title("86 Scotch distilleries — where the peat is", loc="left", fontsize=11)
    fig.tight_layout(); fig.savefig(FIG / "atlas_map.png", dpi=160); plt.close(fig)

    # 2. does location predict taste?
    g = pd.DataFrame(results["geography_table"]).sort_values("skill")
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ys = np.arange(len(g))
    ax.barh(ys - 0.18, g["skill"], height=0.34, color="#93520f", label="all 86 (* Holm p < 0.05, skill > 0)")
    ax.barh(ys + 0.18, g["skill_without_islay"], height=0.34, color="#6b7b8c", alpha=.55, label="without Islay (79)")
    ax.axvline(0, color="#333", lw=1)
    ax.set_yticks(ys, [f + (" *" if p < 0.05 and k > 0 else "") for f, p, k in zip(g["attribute"], g["p_holm"], g["skill"])])
    ax.set_xlabel("Skill of the 5 nearest distilleries vs the plain average (>0 = location helps)")
    ax.legend(frameon=False, loc="lower right", fontsize=8.5)
    ax.set_title("Location predicts peat and iodine — little else", loc="left", fontsize=10.5)
    fig.tight_layout(); fig.savefig(FIG / "geography_skill.png", dpi=160); plt.close(fig)


if __name__ == "__main__":
    main()
