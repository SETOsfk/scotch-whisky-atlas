"""Computational Whisky Wheel on 2,247 Whisky Advocate reviews.

1. Extraction check on 40 hand-labelled hold-out reviews (never read while the dictionary was written).
2. The dataset: every review as binary attributes + subcategory and category counts (no review text).
3. 90+ prediction as in Dong, Guo, Rajana & Chen (2020) and Dong, Atkison & Chen (2021): naive Bayes, linear SVM,
   logistic regression; random 5-fold CV as in the papers and 5-fold CV grouped by distillery/brand.
4. External check: distillery profiles read from the reviews vs Wishart's panel scores in the atlas (12 flavours).

Reviews: Kaggle koki25ando/22000-scotch-whisky-reviews (2018 upload). Its texts belong to their rows; the 2020
re-upload used by run_analysis.py does not (see data/README.md).
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.naive_bayes import BernoulliNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MinMaxScaler
from sklearn.svm import LinearSVC
from statsmodels.stats.multitest import multipletests

from whisky.data import FLAVOURS, REF, ROOT, load_atlas, load_reviews
from whisky.wheel import extract, features, load_wheel, norm

RAW = ROOT / "data" / "raw" / "scotch_review.csv"
OUT = ROOT / "results"
DERIVED = ROOT / "data" / "derived"
SEED = 2026

# Wheel attributes behind each Wishart flavour. Fixed before the correlation was computed.
WISHART = {
    "Body": ["FULL BODY", "VISCOUS", "CHEWY", "OILY"],
    "Sweetness": ["SWEET", "SUGAR", "SYRUP", "CANDY", "FUDGE", "TOFFEE", "CARAMEL"],
    "Smoky": ["SMOKE", "BONFIRE", "PEAT", "KILN", "ASH", "TAR", "COAL", "BURNT"],
    "Medicinal": ["IODINE", "MEDICINAL", "SEAWEED", "BRINE", "SALT", "SEA AIR"],
    "Tobacco": ["TOBACCO", "LEATHER", "FEINTY"],
    "Honey": ["HONEY", "VANILLA", "CUSTARD"],
    "Spicy": ["SPICE", "WOOD SPICE", "BAKING SPICE", "EXOTIC SPICE", "PEPPER", "CINNAMON", "CLOVE", "NUTMEG", "GINGER", "ANISE", "ALLSPICE"],
    "Winey": ["SHERRY", "OLOROSO", "PX", "FINO", "PORT", "MADEIRA", "RED WINE", "WINE", "RAISIN", "SULTANA", "FIG", "PRUNE", "DATE", "DRIED FRUIT", "FRUITCAKE"],
    "Nutty": ["NUTTY", "ALMOND", "MARZIPAN", "HAZELNUT", "WALNUT", "PECAN", "BRAZIL NUT", "PEANUT", "CHESTNUT", "COCONUT"],
    "Malty": ["MALT", "BARLEY", "GRAIN", "BISCUIT", "MASH", "OATS", "BREAD"],
    "Fruity": "category:FRUITY",
    "Floral": "floral",
}


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


def holdout(df: pd.DataFrame, wheel, file: str) -> dict:
    """Hand phrases found by the wheel (recall) and wheel attributes that sit on a hand phrase (precision)."""
    _, forms, pat = wheel
    h = pd.read_csv(REF / file)
    per, caught_all, correct_all = [], 0, 0
    n_hand = n_attr = 0
    for i, phrases in zip(h["id"], h["phrases"]):
        t = norm(df.loc[df["id"] == i, "description"].iloc[0])
        hand = {p: [(m.start(), m.end()) for m in re.finditer(rf"(?<![\w']){re.escape(norm(p))}(?![\w'])", t)]
                for p in phrases.split("|")}
        got = extract(t, forms, pat)
        caught = [p for p, occ in hand.items() if any(overlaps(o, (s, e)) for o in occ for _, s, e in got)]
        attrs = {}
        for n, s, e in got:
            attrs[n] = attrs.get(n, False) or any(overlaps((s, e), o) for occ in hand.values() for o in occ)
        per.append({"id": int(i), "hand": len(hand), "caught": len(caught), "attributes": len(attrs),
                    "on_hand_phrase": sum(attrs.values()),
                    "missed": [p for p in hand if p not in caught], "extra": [n for n, ok in attrs.items() if not ok]})
        n_hand += len(hand); caught_all += len(caught); n_attr += len(attrs); correct_all += sum(attrs.values())
    rate = [r["caught"] / r["hand"] for r in per]
    return {"reviews": len(per), "hand_phrases": n_hand, "recall": round(caught_all / n_hand, 4),
            "precision": round(correct_all / n_attr, 4), "per_review_rate_mean": round(float(np.mean(rate)), 4),
            "per_review_rate_min": round(float(np.min(rate)), 4), "reviews_detail": per}


def level_onehot(X: pd.DataFrame) -> pd.DataFrame:
    """Counts → indicators 0,1,2,3+ (the binarisation Le et al. 2023 used for naive Bayes)."""
    c = X.clip(upper=3)
    return pd.concat({f"{col}={k}": (c[col] == k).astype(int) for col in c for k in range(4)}, axis=1)


def evaluate(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, model: str, grouped: bool) -> dict:
    make = {"NB": lambda: BernoulliNB(alpha=1.0),
            "SVM": lambda: make_pipeline(MinMaxScaler(), LinearSVC(C=0.1, dual="auto", max_iter=20000)),
            "LR": lambda: make_pipeline(MinMaxScaler(), LogisticRegression(C=0.5, max_iter=5000))}[model]
    cv = (StratifiedGroupKFold(5, shuffle=True, random_state=SEED).split(X, y, groups) if grouped
          else StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y))
    pred, score = np.zeros(len(y), int), np.zeros(len(y))
    for tr, te in cv:
        m = make().fit(X.iloc[tr], y[tr])
        pred[te] = m.predict(X.iloc[te])
        score[te] = m.decision_function(X.iloc[te]) if model == "SVM" else m.predict_proba(X.iloc[te])[:, 1]
    return {"accuracy": accuracy_score(y, pred), "precision": precision_score(y, pred, zero_division=0),
            "recall": recall_score(y, pred), "f1": f1_score(y, pred), "auc": roc_auc_score(y, score)}


def main() -> None:
    OUT.mkdir(exist_ok=True); DERIVED.mkdir(parents=True, exist_ok=True)
    wheel = load_wheel()
    tax = wheel[0]
    atlas = load_atlas()
    df = load_reviews(RAW, atlas)
    df["description"] = df["description"].fillna("")

    # A: labelled before the dictionary was written, but read while labelling (optimistic).
    # B: labelled after the dictionary was frozen; the dictionary was not changed afterwards (the number to quote).
    ex = {"A_read_before_dictionary": holdout(df, wheel, "wheel_holdout.csv"),
          "B_after_freeze": holdout(df, wheel, "wheel_holdout_b.csv")}
    (OUT / "wheel_extraction.json").write_text(json.dumps(ex, indent=1))
    brief = {k: {m: v for m, v in e.items() if m != "reviews_detail"} for k, e in ex.items()}
    print("hold-out:", brief)

    N, S, C = features(df["description"], wheel)
    used = N.columns[N.sum() > 0]
    N = N[used]
    y = (df["points"] >= 90).to_numpy().astype(int)
    brand = df["name"].str.lower().str.replace(r"^the ", "", regex=True).str.extract(r"^([a-z'’]+)")[0]
    groups = df["distillery"].fillna(brand).fillna("?").to_numpy()

    data = pd.concat([df[["id", "name", "category", "points", "price_usd", "distillery"]].assign(label90=y),
                      N, S.add_prefix("sub:"), C.add_prefix("cat:")], axis=1)
    data.to_csv(DERIVED / "whisky_wheel_dataset.csv", index=False)

    sets = {"C": C, "S": S, "N": N, "CN": pd.concat([C, N], axis=1), "CSN": pd.concat([C, S, N], axis=1)}
    rows = []
    for fs, X in sets.items():
        Xnb = X if fs == "N" else pd.concat([level_onehot(X[[c for c in X if c not in N]]), X[[c for c in X if c in N]]], axis=1)
        for model in ["NB", "SVM", "LR"]:
            for grouped in [False, True]:
                r = evaluate(Xnb if model == "NB" else X, y, groups, model, grouped)
                rows.append({"features": fs, "model": model, "cv": "grouped" if grouped else "random", **{k: round(v, 4) for k, v in r.items()}})
    base = 1 - y.mean()
    rows.append({"features": "-", "model": "always 89 or below", "cv": "-", "accuracy": round(base, 4), "precision": 0, "recall": 0, "f1": 0, "auc": 0.5})
    models = pd.DataFrame(rows)
    models.to_csv(OUT / "wheel_models.csv", index=False)
    print(models.to_string())

    # Does the critic's verdict leak into the words? Flavour-only vs descriptor-only attributes.
    overall = tax.index[tax["category"] == "OVERALL"]
    verdict = tax.index[(tax["category"] == "OVERALL") & tax["subcategory"].isin(["DESCRIPTORS", "BALANCE"])]
    flav = N[[c for c in N if c not in overall]]
    desc = N[[c for c in N if c in verdict]]
    ablation = {name: round(evaluate(X, y, groups, "LR", True)["auc"], 4) for name, X in
                [("all attributes", N), ("flavour and structure only", flav), ("verdict words only", desc)]}
    print("ablation AUC (LR, grouped):", ablation)

    lr = make_pipeline(MinMaxScaler(), LogisticRegression(C=0.5, max_iter=5000)).fit(flav, y)
    coef = pd.Series(lr[-1].coef_[0], index=flav.columns)
    top = pd.DataFrame({"coef": coef, "share_90plus": flav[y == 1].mean(), "share_below": flav[y == 0].mean(), "n": flav.sum()})
    top = top[top["n"] >= 20].sort_values("coef")
    top = pd.concat([top.tail(12)[::-1], top.head(12)]).round(3)
    top.to_csv(OUT / "wheel_top_attributes.csv")

    # External check against Wishart's distillery scores.
    fams = {k: (list(tax.index[tax["category"] == v.split(":")[1]]) if isinstance(v, str) and v.startswith("category:")
                else list(tax.index[(tax["category"] == "FLORAL") & (tax["subcategory"] != "HONEY")]) + ["GRASS", "LEAFY", "HAY", "HERBAL", "TEA", "MINT"]
                if v == "floral" else v) for k, v in WISHART.items()}
    linked = df["distillery"].notna()
    counts = df.loc[linked, "distillery"].value_counts()
    keep = counts[counts >= 5].index
    prof = pd.DataFrame({f: N.reindex(columns=a, fill_value=0).loc[linked].max(axis=1) for f, a in fams.items()})
    prof = prof.groupby(df.loc[linked, "distillery"]).mean().loc[keep]
    ref = atlas.set_index("distillery").loc[keep, FLAVOURS]
    res = []
    for f in FLAVOURS:
        rho, p = spearmanr(prof[f], ref[f])
        res.append({"flavour": f, "rho": round(rho, 3), "p": p})
    wish = pd.DataFrame(res)
    wish["p_holm"] = multipletests(wish["p"], method="holm")[1]
    wish = wish.round({"p": 4, "p_holm": 4})
    wish.to_csv(OUT / "wheel_wishart.csv", index=False)
    print(f"Wishart check on {len(keep)} distilleries:\n", wish.to_string())

    summary = {
        "reviews": int(len(df)), "share_90plus": round(float(y.mean()), 4),
        "wheel": {"categories": int(tax["category"].nunique()), "subcategories": int(tax.groupby(["category", "subcategory"]).ngroups),
                  "normalized": int(len(tax)), "normalized_used": int(len(used)), "specific_forms": int(len(wheel[1]))},
        "attributes_per_review_mean": round(float(N.sum(axis=1).mean()), 2),
        "reviews_without_attribute": int((N.sum(axis=1) == 0).sum()),
        "holdout": brief,
        "baseline_accuracy": round(float(base), 4), "ablation_auc": ablation,
        "wishart_distilleries": int(len(keep)),
    }
    (OUT / "wheel_metrics.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
