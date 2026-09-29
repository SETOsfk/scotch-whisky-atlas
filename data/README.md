# Data

## The atlas — `data/atlas/WhiskyOut.kml` (in the repo)

Pope, A. (2017). *Scotch Whisky characteristics* [dataset]. University of Edinburgh, Edinburgh DataShare.
[doi:10.7488/ds/1942](https://doi.org/10.7488/ds/1942). Licence: **Creative Commons Attribution-ShareAlike 3.0**
(stated in the record's `dc.rights`). 86 distilleries, one 0–4 score per flavour, postcode, British National Grid
coordinates; the KML carries the same scores plus WGS84 coordinates, so both languages read this one file.
The scores come from the University of Strathclyde "Nessie" outreach page; the tasting method is not documented there.
Because of ShareAlike, everything derived from the atlas (`results/`, `web/data/`) is CC BY-SA 3.0 as well.

## Whisky Advocate — `data/raw/scotch_review2020.csv` (not in the repo)

Optional. Download from Kaggle — [neilcosgrove/scotch-whiskey-reviews-update-2020](https://www.kaggle.com/datasets/neilcosgrove/scotch-whiskey-reviews-update-2020)
(2,247 reviews; listed as CC0, the review texts are Whisky Advocate's) — into `data/raw/`:

```bash
kaggle datasets download -d neilcosgrove/scotch-whiskey-reviews-update-2020 -p data/raw --unzip
```

Only name, category, points and price are used: after row 150 the review texts do not match the bottle names
(`python/whisky/data.py: text_alignment`). Without this file the atlas analysis and the app still run; the
Whisky Advocate panels are left out.

## Whisky Advocate, original upload — `data/raw/scotch_review.csv` (not in the repo)

Needed for the Computational Whisky Wheel (`run_wheel.py`, `build_finder.py`). The same 2,247 reviews as uploaded to
Kaggle in 2018 — [koki25ando/22000-scotch-whisky-reviews](https://www.kaggle.com/datasets/koki25ando/22000-scotch-whisky-reviews):

```bash
kaggle datasets download -d koki25ando/22000-scotch-whisky-reviews -p data/raw --unzip
sha256sum data/raw/scotch_review.csv   # 4e8eadcdc6088d0a3ad241f2c3fbbcae82e55d06528e1cdca870d165f6b172d6
```

Here the texts do belong to their rows: a text names its own bottle's brand in 50.3 % of rows 151–2,247 against
15.1 % for rows shifted by 1–3 (`text_alignment`). The texts are Whisky Advocate's and are not redistributed; the
repo keeps only the derived attribute flags (`data/derived/whisky_wheel_dataset.csv`) and short hand-marked phrases
for the two hold-out checks.

## `data/reference/` — hand-built, every row sourced

| File | What | Source |
|---|---|---|
| `distillery_names.csv` | atlas typos (`Laphroig` → Laphroaig, `Belvenie` → Balvenie…) and the patterns that link review titles to distilleries | hand-built |
| `tr_available.csv` | 48 Scotch bottles sold in Türkiye (32 single malts from 13 atlas distilleries, 16 blends), TL list price, date, source | habergazetesi.com.tr whisky price list (Sept 2026); Pernod Ricard Türkiye list (Jan 2026); Diageo Türkiye imported brands |
| `pairing_rules.csv`, `cheeses.csv` | 4 pairing styles → 19 cheeses (10 Turkish) | Whisky Advocate "How to pair whisky and cheese"; Master of Malt; Turkish geographical-indication cheeses (Aydın Gastronomy 2020, Hürriyet) |
| `provinces.csv` | 81 province centroids (shop search fallback) | github.com/caglarsarikaya/turkey-geolocations |
| `scotland_outline.json` | map outline | Natural Earth 1:50m admin-0 map units (public domain) |
| `whisky_wheel.csv` | Computational Whisky Wheel: category, subcategory, normalized attribute, pipe-separated specific phrases (3,580 → 270 → 58 → 17) | built for this project on the revised whisky flavour wheel of Lee et al. (2001), following the Computational Wine Wheel (Chen et al.) |
| `wheel_holdout.csv`, `wheel_holdout_b.csv` | 40 + 40 reviews by id with the hand-marked flavour phrases (A: read before the dictionary was written; B: read only after it was frozen) | hand-marked |
| `sides.csv`, `side_rules.csv` | 10 whisky snacks (chocolate, dried fruit, nuts, smoked salmon, Turkish blue cheese) and the style → snack rules | Master of Malt, "What should I pair with whisky?" |
| `side_prices.csv` | 78 dated shelf listings (product, grams, TL) for the cheeses and snacks | Migros Sanal Market, 28.09.2026 |
| `tr_wines_extra.csv`, `tr_wine_prices.csv` | 2 more Turkish wines and TL prices for 5 wines | habergazetesi.com.tr wine price list (09.07.2026) |
