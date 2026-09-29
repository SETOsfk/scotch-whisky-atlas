"""Data for the wine & whisky finder page (web/finder/data/finder.json).

Whisky: every bottle on the Turkish shelf gets a taste profile from the Computational Whisky Wheel —
its own Whisky Advocate reviews, shrunk toward its distillery's (or brand's) reviews when it has few.
Wine: every Turkish wine gets the profile of the same-style Bordeaux wines sharing one of its grapes, weighted by
the wine app's similarity squared (grape 60 % · body 25 % · oak 15 %), read from their Wine Spectator descriptors.
Sides: sourced pairing rules; prices are dated shelf prices (median of listings per portion).

    python build_finder.py [path/to/wineapp]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from whisky.data import REF, ROOT
from whisky.wheel import load_wheel

WINEAPP = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "wineapp"
OUT = ROOT / "web" / "finder" / "data" / "finder.json"
K = 2   # prior weight in reviews: a bottle with 1 review is 1/3 its own, 2/3 its distillery

WHISKY_CHIPS = [   # id, tr, en, wheel subcategories (category|subcategory) or normalized attributes
    ("smoky", "Dumanlı / turbalı", "Smoky / peaty", ["PHENOLIC|PEATY", "PHENOLIC|SMOKY", "PHENOLIC|BURNT"]),
    ("sea", "İyot / deniz", "Iodine / sea", ["PHENOLIC|MEDICINAL", "TASTE|SALTY", "TASTE|MARITIME"]),
    ("sherry", "Şeri / kuru meyve", "Sherry / dried fruit", ["WOODY|CASK", "FRUITY|DRIED FRUIT"]),
    ("fruit", "Taze meyve", "Fresh fruit", ["FRUITY|ORCHARD", "FRUITY|TROPICAL", "FRUITY|CITRUS", "FRUITY|BERRIES", "FRUITY|FRUIT"]),
    ("floral", "Çiçeksi / çimen", "Floral / grassy", ["FLORAL|NATURAL", "FLORAL|PERFUMED", "GREEN|FRESH", "GREEN|DRIED"]),
    ("honey", "Bal / vanilya", "Honey / vanilla", ["FLORAL|HONEY", "WOODY|VANILLA"]),
    ("sweet", "Karamel / şekerleme", "Caramel / sweets", ["WOODY|CARAMEL", "SWEET|CONFECTIONERY", "SWEET|BAKED"]),
    ("choc", "Çikolata / kahve", "Chocolate / coffee", ["WOODY|CHOCOLATE", "COFFEE"]),
    ("spice", "Baharatlı", "Spicy", ["WOODY|SPICY"]),
    ("nutty", "Fındık / meşe", "Nuts / oak", ["WOODY|NUTTY", "WOODY|NEW WOOD"]),
    ("malt", "Malt / tahıl", "Malt / cereal", ["GRAINY|CEREAL", "GRAINY|MALT", "GRAINY|MASH"]),
    ("leather", "Deri / tütün / toprak", "Leather / tobacco / earth", ["FEINTY|FEINTY", "FEINTY|LEATHER", "FEINTY|TOBACCO", "EARTHY|EARTHY", "EARTHY|MUSTY"]),
]
WINE_CHIPS = [     # id, tr, en, Computational Wine Wheel families (wine app) or descriptors
    ("dark", "Siyah / orman meyvesi", "Dark / forest fruit", ["berry", "fruit_general"]),
    ("tree", "Kiraz / çekirdekli meyve", "Cherry / stone fruit", ["tree_fruit", "candied"]),
    ("citrus", "Narenciye", "Citrus", ["citrus"]),
    ("dried", "Kuru meyve / reçel", "Dried fruit / jam", ["dried_fruit"]),
    ("floral", "Çiçek / ot", "Floral / herbal", ["floral_herbaceous", "herbs", "vegetal"]),
    ("spice", "Baharat", "Spice", ["spice"]),
    ("oak", "Meşe / vanilya", "Oak / vanilla", ["oak"]),
    ("sweet", "Çikolata / karamel / bal", "Chocolate / caramel / honey", ["sweet"]),
    ("roasted", "Kavrulmuş / kahve / duman", "Roasted / coffee / smoke", ["roasted"]),
    ("earth", "Toprak / mineral", "Earth / mineral", ["earth", "chemical", "medicinal"]),
    ("tobacco", "Tütün / deri / et", "Tobacco / leather / meat", ["tea_tobacco", "animal", "meat"]),
    ("tannic", "Tanenli / dolgun", "Tannic / full", ["TANNINS_HIGH", "FULL-BODIED", "DENSE"]),
]


def tl(s: str) -> tuple[float | None, float | None]:
    """"1.225–1.365" → (1225, 1365); "11.000" → (11000, 11000); "" → (None, None)."""
    nums = [float(x.replace(".", "").replace(",", ".")) for x in re.findall(r"[\d.,]+", str(s))]
    return (min(nums), max(nums)) if nums else (None, None)


def r0(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else int(round(x))


def whisky(wheel) -> dict:
    tax = wheel[0]
    d = pd.read_csv(ROOT / "data" / "derived" / "whisky_wheel_dataset.csv")
    key = tax["category"] + "|" + tax["subcategory"]
    sets = {cid: [n for n in tax.index if key[n] in spec or n in spec] for cid, _, _, spec in WHISKY_CHIPS}
    X = pd.DataFrame({c: d.reindex(columns=a, fill_value=0).max(axis=1) for c, a in sets.items()})
    base = X.mean()
    brands = {"johnnie walker": "Johnnie Walker", "chivas": "Chivas Regal", "royal salute": "Royal Salute", "j&b": "J&B", "grant's": "Grant's"}
    alt = "|".join(re.escape(b) for b in brands)
    brand = (d["name"].str.lower().str.replace("’", "'").str.replace(r"^william ", "", regex=True)   # "William Grant’s 25" is a Grant's
             .str.extract(rf"^({alt}|[a-z']+)")[0])
    tr = pd.read_csv(REF / "tr_available.csv", keep_default_na=False)
    bottles = []
    for r in tr.itertuples():
        own = d["name"].str.contains(r.pattern, regex=True) if r.pattern else pd.Series(False, index=d.index)
        if r.distillery:
            group, gname = d["distillery"] == r.distillery, r.distillery
        else:
            b = re.match(rf"({alt})", r.product.lower())
            group, gname = (brand == b.group(1), brands[b.group(1)]) if b else (pd.Series(False, index=d.index), "")
        rest = group & ~own                        # the prior never sees the bottle's own reviews
        prior = (X[rest].sum() + K * base) / (rest.sum() + K)
        n = int(own.sum())
        prof = (X[own].sum() + K * prior) / (n + K)
        # ponytail: pairing style is a rule of thumb on the profile (same idea as data.style_of), not a model
        # smoky at .6, not .5: one review naming "woodsmoke" must not make a light blend smoky (J&B Rare, n=1, is "light, Speyside-style")
        style = ("peated" if prof["smoky"] >= .6 or prof["sea"] >= .5 else "sherried" if prof["sherry"] >= .5
                 else "light" if prof["floral"] >= .6 else "honeyed")
        lo, hi = tl(r.price_tl)
        bottles.append({"id": re.sub(r"\W+", "_", r.product.lower()).strip("_"), "name": r.product, "distillery": r.distillery or None,
                        "style": style, "n_own": n, "n_group": int(group.sum()), "group": gname,
                        "points": r0(d.loc[own, "points"].median()) if n else None,
                        "price": [r0(lo), r0(hi)] if lo else None, "as_of": r.as_of, "source": r.source_name, "source_url": r.source_url,
                        "profile": [round(float(prof[c]), 3) for c in sets]})
    rules = pd.read_csv(REF / "pairing_rules.csv", keep_default_na=False)
    side_rules = pd.read_csv(REF / "side_rules.csv", keep_default_na=False)
    return {"chips": [{"id": c, "tr": t, "en": e} for c, t, e, _ in WHISKY_CHIPS],
            "baseline": [round(float(base[c]), 3) for c in sets], "n_reviews": int(len(d)), "bottles": bottles,
            "cheese_rules": {r.rule_id: {"cheeses": r.cheese_ids.split(";") + (["mavi_damarli"] if "stilton" in r.cheese_ids else []),
                                         "tr": r.rationale_tr, "en": r.rationale_en, "source": r.source_name, "url": r.source_url}
                             for r in rules.itertuples()},
            "side_rules": {r.style: {"sides": r.side_ids.split(";"), "tr": r.rationale_tr, "en": r.rationale_en,
                                     "source": r.source_name, "url": r.source_url} for r in side_rules.itertuples()}}


def wine() -> dict:
    sys.path.insert(0, str(WINEAPP / "python"))
    from wine.pairing import Profile, equivalents, grape_weights, pairing_rule, profile_from_wine  # noqa: E402

    W = json.loads((WINEAPP / "web" / "data" / "wine.json").read_text(encoding="utf-8"))
    ref_tr = pd.concat([pd.DataFrame(W["turkish"]), pd.read_csv(REF / "tr_wines_extra.csv", keep_default_na=False)], ignore_index=True)
    ref_tr["oak_months"] = ref_tr["oak_months"].astype(str).replace({"nan": ""})
    ref = {"turkish": ref_tr.fillna("")}
    desc = W["desc"]
    fam = [x["f"] for x in desc]
    names = [x["a"] for x in desc]
    chip_idx = {c: {i for i in range(len(desc)) if fam[i] in spec or names[i] in spec} for c, _, _, spec in WINE_CHIPS}
    w = W["wines"]
    styles, apps, info = W["styles"], W["appellations"], W["appellation_info"]
    ids = list(ref_tr["id"])
    acc = {i: np.zeros(len(WINE_CHIPS)) for i in ids}
    wsum = {i: 0.0 for i in ids}
    n_contrib = {i: 0 for i in ids}
    by_style = {s: [] for s in styles}
    for k in range(len(w["l"])):
        at = set(w["at"][k])
        st = styles[w["st"][k]]
        ai = info.get(apps[w["ap"][k]], {})
        prof = profile_from_wine(st, ai.get("bank"), ai.get("grapes"), {names[i] for i in at})
        v = np.array([bool(at & chip_idx[c]) for c, *_ in WINE_CHIPS], float)
        by_style[st].append(v)
        for e in equivalents(prof, ref, k=len(ids)):   # every Turkish wine that shares a grape, weighted by score²
            acc[e["id"]] += e["score"] ** 2 * v; wsum[e["id"]] += e["score"] ** 2; n_contrib[e["id"]] += 1
    base = {s: np.mean(v, axis=0).round(3).tolist() for s, v in by_style.items() if v}
    prices = pd.read_csv(REF / "tr_wine_prices.csv", keep_default_na=False, dtype=str).set_index("id")
    rules = {r["rule_id"]: {"cheeses": r["cheese_ids"].split(";") + (["mavi_damarli"] if "roquefort" in r["cheese_ids"] else []),
                            "tr": r["rationale_tr"], "en": r["rationale_en"], "source": r["source_name"], "url": r["source_url"]}
             for r in W["rules"]}
    wines = []
    for r in ref_tr.itertuples():
        p = Profile(style=r.style, bank=None, grapes=grape_weights(r.grapes), body=r.body or None, tannin=None, oak=None)
        pr = prices.loc[r.id] if r.id in prices.index else None
        lo = tl(pr["price_tl"])[0] if pr is not None else None
        wines.append({"id": r.id, "name": r.wine, "producer": r.producer, "style": r.style, "grapes": r.grapes.replace(";", ", "),
                      "body": r.body or None, "region": r.location_tr, "rule": pairing_rule(p), "n_bordeaux": n_contrib[r.id],
                      "profile": (acc[r.id] / wsum[r.id]).round(3).tolist() if wsum[r.id] else None,
                      "price": [r0(lo), r0(lo)] if lo else None, "as_of": pr["as_of"] if pr is not None else None,
                      "source": pr["source_name"] if pr is not None else None, "source_url": pr["source_url"] if pr is not None else r.source_url})
    return {"chips": [{"id": c, "tr": t, "en": e} for c, t, e, _ in WINE_CHIPS], "baseline": base, "wines": wines,
            "cheese_rules": rules, "n_bordeaux": len(w["l"]), "cheeses": W["cheeses"]}


def sides() -> list[dict]:
    cheese = pd.read_csv(REF / "cheeses.csv", keep_default_na=False)
    extra = pd.read_csv(REF / "sides.csv", keep_default_na=False)
    listings = pd.read_csv(REF / "side_prices.csv")
    listings["per_g"] = listings["price_tl"] / listings["grams"]
    out = []
    for r in pd.concat([cheese.assign(portion_g=250), extra.assign(is_turkish=1)], ignore_index=True).itertuples():
        L = listings[listings["side_id"] == r.id]
        port = int(r.portion_g)
        price = None
        if len(L):   # median shelf price per portion, and the cheapest / dearest listing for the range
            price = {"mid": r0(L["per_g"].median() * port), "lo": r0(L["per_g"].min() * port), "hi": r0(L["per_g"].max() * port),
                     "n": int(len(L)), "shop": L["shop"].iloc[0], "date": L["date"].iloc[0]}
        out.append({"id": r.id, "tr": r.name_tr, "en": r.name_en, "kind": r.kind, "turkish": int(r.is_turkish),
                    "portion_g": port, "note_tr": r.note_tr, "note_en": r.note_en, "price": price})
    return out


def wheel_summary() -> dict:
    """Headline numbers of run_wheel.py, so the page never hard-codes them."""
    m = json.loads((ROOT / "results" / "wheel_metrics.json").read_text(encoding="utf-8"))
    B = m["holdout"]["B_after_freeze"]
    mod = pd.read_csv(ROOT / "results" / "wheel_models.csv")
    g = mod[mod["cv"] == "grouped"].sort_values("accuracy").iloc[-1]
    wish = pd.read_csv(ROOT / "results" / "wheel_wishart.csv")
    return {"reviews": m["reviews"], "terms": int(pd.read_csv(REF / "whisky_wheel.csv")["specific"].str.split("|").explode().nunique()),
            "attributes": m["wheel"]["normalized"], "subcategories": m["wheel"]["subcategories"], "categories": m["wheel"]["categories"],
            "holdout_reviews": B["reviews"], "holdout_phrases": B["hand_phrases"], "recall": B["recall"], "precision": B["precision"],
            "best_grouped": {"features": g.features, "model": g.model, "accuracy": round(float(g.accuracy), 4), "auc": round(float(g.auc), 4)},
            "baseline": m["baseline_accuracy"], "ablation_auc": m["ablation_auc"], "wishart_n": m["wishart_distilleries"],
            "wishart": [[r.flavour, r.rho, r.p_holm] for r in wish.itertuples()]}


def check(data: dict) -> None:
    """Fails the build on the mistakes this file has already made once."""
    b = {x["id"]: x for x in data["whisky"]["bottles"]}
    assert b["j_b_rare"]["style"] == "light" and b["lagavulin_16"]["style"] == "peated" and b["aberlour_12"]["style"] == "sherried"
    assert b["grant_s_triple_wood"]["group"] == "Grant's" and b["grant_s_triple_wood"]["n_group"] == 4
    w = {x["id"]: x for x in data["wine"]["wines"]}
    assert w["sarafin_sb"]["price"] == [1460, 1460] and w["kavaklidere_egeo_cs"]["price"] == [1537, 1537]   # "1.460" is TL, not 1.46
    assert w["kavaklidere_egeo_cs"]["profile"] and w["kayra_buzbag_rezerv"]["profile"] is None
    for x in [*b.values(), *w.values()]:
        assert x["profile"] is None or all(0 <= v <= 1 for v in x["profile"]), x["id"]
    for s in data["sides"]:
        assert s["price"] is None or s["price"]["lo"] <= s["price"]["mid"] <= s["price"]["hi"], s["id"]


def main() -> None:
    wheel = load_wheel()
    data = {"generated": pd.Timestamp.now().strftime("%Y-%m-%d"), "wheel": wheel_summary(),
            "whisky": whisky(wheel), "wine": wine(), "sides": sides(),
            "provinces": pd.read_csv(REF / "provinces.csv")[["province", "lat", "lon"]].values.tolist()}
    check(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(OUT, f"{OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
