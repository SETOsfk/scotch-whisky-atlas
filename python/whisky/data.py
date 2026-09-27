"""Load the Scotch whisky flavour atlas (86 distilleries) and the Whisky Advocate score list.

Atlas: Pope, A. (2017) "Scotch Whisky characteristics", Edinburgh DataShare, doi:10.7488/ds/1942, CC BY-SA 3.0.
Flavour scores (0-4, one profile per distillery) come from the University of Strathclyde "Nessie" whisky page;
coordinates are postcode-level (several distilleries share one point).
Whisky Advocate: Kaggle neilcosgrove/scotch-whiskey-reviews-update-2020. Only name, category, points and
price are used — the review texts do not line up with the bottle names (see text_alignment()).
Mirrored in R/whisky_data.R.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "data" / "reference"
KML = ROOT / "data" / "atlas" / "WhiskyOut.kml"
REVIEWS = ROOT / "data" / "raw" / "scotch_review2020.csv"
FLAVOURS = ["Body", "Sweetness", "Smoky", "Medicinal", "Tobacco", "Honey",
            "Spicy", "Winey", "Nutty", "Malty", "Fruity", "Floral"]
ISLAY = tuple(f"PA{n}" for n in range(42, 50))       # Islay postcode districts PA42-PA49
OTHER_BRANDS = r"octomore|port charlotte|ballechin"   # peated brands made at an atlas distillery, not its house style


def load_atlas(path: str | Path = KML) -> pd.DataFrame:
    s = Path(path).read_text(encoding="utf-8")
    rows = []
    for pm in re.findall(r"<Placemark>(.*?)</Placemark>", s, re.S):
        d = dict(re.findall(r'<SimpleData name="([^"]+)">([^<]*)</SimpleData>', pm))
        lon, lat = map(float, re.search(r"<coordinates>([^<]+)</coordinates>", pm).group(1).split(",")[:2])
        rows.append({"raw": d["Distillery"], "postcode": d["Postcode"].strip(), "lat": lat, "lon": lon,
                     **{f: int(d[f]) for f in FLAVOURS}})
    df = pd.DataFrame(rows)
    names = pd.read_csv(REF / "distillery_names.csv", keep_default_na=False)
    df.insert(0, "distillery", df["raw"].map(dict(zip(names["raw"], names["display"]))).fillna(df["raw"]))
    own = dict(zip(names["display"], names["pattern"]))
    df["pattern"] = [own.get(n) or r"\b" + re.escape(n.lower()).replace(r"\ ", " ?") + r"\b" for n in df["distillery"]]
    df["islay"] = df["postcode"].str[:4].isin(ISLAY)
    df["style"] = df.apply(style_of, axis=1)
    return df.sort_values("distillery", key=lambda s: s.str.lower()).reset_index(drop=True)


def style_of(r) -> str:
    """Pairing style, first rule that fires: peated → sherried → light → honeyed (rules of thumb, not a model)."""
    if r["Smoky"] >= 3 or r["Medicinal"] >= 2:
        return "peated"
    if r["Winey"] >= 3:
        return "sherried"
    if r["Body"] <= 1 and r["Smoky"] <= 1:
        return "light"
    return "honeyed"


def haversine_km(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    la, lo = np.radians(lat)[:, None], np.radians(lon)[:, None]
    a = np.sin((la - la.T) / 2) ** 2 + np.cos(la) * np.cos(la.T) * np.sin((lo - lo.T) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def parse_price(s) -> float:
    """"1,500" → 1500; "50/375ml." → 100 (per 75 cl); "60,000/set" → NaN (a set, not a bottle)."""
    s = str(s).replace(",", "").strip()
    m = re.match(r"^\$?(\d+(?:\.\d+)?)", s)
    if "set" in s.lower() or not m:
        return np.nan
    return float(m.group(1)) * (2 if "375" in s else 1)


def load_reviews(path: str | Path = REVIEWS, atlas: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = ["id", "name", "category", "points", "price_raw", "currency", "description"]
    df["name"] = df["name"].str.replace("’", "'").str.strip()
    df["description"] = df["description"].fillna("")
    df["price_usd"] = df["price_raw"].map(parse_price)
    abv = df["name"].str.findall(r"(\d{2}(?:\.\d+)?)\s*%").str[-1].astype(float)   # last "%" ("100% Islay, 50%")
    df["abv"] = abv.where(abv.between(35, 75))
    df["age"] = df["name"].str.extract(r"(\d{1,2})\s*[- ]?year[- ]old", flags=re.I)[0].astype(float)
    df["distillery"] = link(df, load_atlas() if atlas is None else atlas)
    return df


def link(df: pd.DataFrame, atlas: pd.DataFrame) -> list:
    """Atlas distillery named in a single-malt title (earliest mention wins: "Longmorn-Glenlivet" → Longmorn)."""
    pats = [(d, re.compile(p)) for d, p in zip(atlas["distillery"], atlas["pattern"]) if p != "none"]
    out = []
    for name, cat in zip(df["name"].str.lower(), df["category"]):
        hits = [(m.start(), d) for d, p in pats if (m := p.search(name))]
        ok = cat == "Single Malt Scotch" and hits and not re.search(OTHER_BRANDS, name)
        out.append(min(hits)[1] if ok else None)
    return out


def text_alignment(df: pd.DataFrame, head: int = 150) -> dict:
    """Share of reviews whose text names the bottle's own brand word, same row vs rows shifted by ±1..3.

    If texts belonged to their rows, the same-row share would stand far above the shifted ones everywhere.
    """
    brand = [(re.findall(r"distilled at ([a-z']+)", n) or re.findall(r"[a-z']+", n.replace("the ", "", 1)) or [""])[0]
             for n in df["name"].str.lower()]
    text = df["description"].str.lower().tolist()

    def share(rows, shift):
        hit = [brand[i + shift] in text[i] for i in rows
               if 0 <= i + shift < len(df) and len(brand[i + shift]) >= 4 and text[i]]
        return round(float(np.mean(hit)), 4)

    top, rest = range(head), range(head, len(df))
    shifts = [-3, -2, -1, 1, 2, 3]
    return {"rows_top": head, "same_row_top": share(top, 0), "same_row_rest": share(rest, 0),
            "shifted_rest": round(float(np.mean([share(rest, s) for s in shifts])), 4)}
