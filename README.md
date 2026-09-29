# Does Scotch whisky taste follow geography? — a flavour atlas of 86 distilleries

**Live app:** [setosfk.github.io/projects/scotch-whisky](https://setosfk.github.io/projects/scotch-whisky/) ·
**Whisky & wine finder:** [setosfk.github.io/projects/scotch-whisky/finder](https://setosfk.github.io/projects/scotch-whisky/finder/) ·
Python + R · [Türkçe özet ↓](#türkçe-özet)

86 Scotch malt distilleries, each scored 0–4 on 12 flavours (body, sweetness, smoky, medicinal, tobacco, honey,
spicy, winey, nutty, malty, fruity, floral) and placed on the map by postcode. Three questions:
**what shape does flavour have, is taste really regional — or is it just Islay — and does a critic reward any
flavour?** The app turns the atlas into something useful in Türkiye: similar distilleries, the closest taste you
can actually buy here (with TL list prices), a cheese to pair and the nearest shop.

## Results

| Question | Answer | Against |
|---|---|---|
| What shape does flavour have? | Two axes carry 49 %: **PC1 (30 %)** smoke-iodine-body vs floral-sweet-fruity, **PC2 (19 %)** sherry, body, honey | 12 dimensions |
| Are there flavour "families"? | Only one split: silhouette **0.38 at k = 2** (6 heavily peated distilleries vs the other 80) | ≤ 0.15 for every k = 3–8 |
| Is taste regional? | Mantel ρ **0.195**, p = 0.001 (flavour distance vs km, 9,999 permutations) | **without Islay: ρ 0.072, p = 0.15** |
| Can location predict a flavour? | The 5 nearest distilleries beat the plain average for **medicinal (skill +0.30)** and **smoky (+0.15)**, Holm p = 0.012 | 8 of 12 flavours predicted *worse* than the average |
| Do points rise with price? | **+0.65 points per price doubling** (95 % CI 0.58–0.71), Spearman 0.36, n = 2,242 Whisky Advocate reviews | +0.61 adjusted for age |
| Does the critic reward a flavour? | **No attribute survives correction** (72 distilleries with ≥ 5 reviews; strongest medicinal ρ 0.23, Holm p = 0.63) | 12 tests, Holm |

![Where the peat is](docs/atlas_map.png)

**"Regional style" is mostly Islay's smoke.** Take the 7 Islay distilleries out and the link between distance and
flavour is no longer distinguishable from chance. Neighbours on the map predict iodine and smoke; for body, honey,
spice, sherry or fruit, knowing the five nearest distilleries is worse than knowing nothing. So the app recommends
by flavour distance, never by region or cluster.

![Location predicts peat and iodine — little else](docs/geography_skill.png)

## A data-quality finding: in the 2020 re-upload the review texts don't belong to their rows

The Whisky Advocate file used by the atlas (Kaggle 2020 re-upload, 2,247 reviews) also has review texts. They look usable, but:

| Check | Rows 1–150 | Rows 151–2,247 |
|---|---|---|
| Text names the bottle's own brand | 32 % | **2.3 %** |
| Text names the brand of a row 1–3 places away | — | **2.2 %** |

After row 150 a text is as likely to mention a neighbouring bottle as its own — the texts were shuffled against the
names in this release. Names, scores and prices *are* consistent (age in the name tracks price, Spearman 0.82), so
the project uses **name, category, points and price only**; the text is never analysed or shown. Bottle names are
linked to atlas distilleries by rules in `data/reference/distillery_names.csv` (1,529 of 1,835 single malts, 83
distilleries); peated side-brands made at an atlas distillery (Octomore, Port Charlotte, Ballechin) are not linked
to the house profile.

The original 2018 upload of the same reviews (Kaggle `koki25ando/22000-scotch-whisky-reviews`) passes the same
check — its text names the bottle's own brand in **50.3 %** of rows 151–2,247 against **15.1 %** for rows shifted by
1–3 — so the Computational Whisky Wheel below reads the texts from that file only.

## Computational Whisky Wheel

The Computational Wine Wheel (Chen et al. 2014, 2016; used on 14,349 Bordeaux reviews by Dong et al. 2020, 2021 and
Le et al. 2023) turns a tasting note into binary attributes: *specific phrase → normalized attribute → subcategory →
category*. No published, validated equivalent for whisky reviews was found, so this project builds one on the
skeleton of the revised Scotch whisky flavour wheel (Lee et al. 2001) and applies it to the 2,247 Whisky Advocate
reviews.

| | |
|---|---|
| Dictionary (`data/reference/whisky_wheel.csv`) | **3,580 phrases → 270 attributes → 58 subcategories → 17 categories** (14 flavour categories on Lee et al.'s wheel, plus taste, mouthfeel and overall) |
| Matching (`python/whisky/wheel.py`) | longest phrase first; cask, colour, strength and brand phrases blanked ("sherry butt", "amber", "Glen…"); a phrase within 3 words after *no / not / without / lacks…* is dropped |
| Check A — 40 reviews read *before* the dictionary was written (`wheel_holdout.csv`) | recall 98.6 %, precision 93.2 % — optimistic: these reviews shaped the dictionary |
| **Check B — 40 reviews read only *after* it was frozen** (`wheel_holdout_b.csv`) | **recall 94.7 % (556 / 587 hand-marked phrases), precision 94.5 % (579 / 613)** |
| Dataset (`data/derived/whisky_wheel_dataset.csv`) | 2,247 reviews × 270 binary attributes + 58 subcategory and 17 category counts, with name, points, price, distillery; 14.9 attributes per review; **no review text** |

**Can the attributes predict a 90+ score?** Barely. With the papers' setup (naive Bayes, linear SVM, logistic
regression; 90+ vs 89−) the best model — naive Bayes on the attribute flags — reaches **78.3 %** accuracy under random
5-fold CV and **77.8 % (AUC 0.765)** when folds are grouped by distillery or brand, against **74.6 %** for always
answering "89 or below". Wine words do much better on Bordeaux (87 %). As on the wine side, the critic's verdict
words carry most of the signal: grouped AUC 0.730 with verdict words only, 0.652 with flavour and structure only.
Among flavours, rancio, marmalade, dried fruit and smoked fish lean 90+; sap, mash, heat and acidity lean lower.

**Do the review profiles agree with a tasting panel?** For the 71 atlas distilleries with at least 5 reviews, the share of
reviews carrying each Wishart flavour (attribute mapping fixed before any correlation was computed) is compared with
Wishart's 0–4 panel score: **3 of 12 flavours agree after Holm correction** — medicinal ρ 0.75, smoky ρ 0.58, fruity
ρ 0.40. Body, winey and floral are positive but not significant; sweetness and tobacco show nothing. Reviews and the
panel agree on peat, not on much else.

## Whisky & wine finder

[`web/finder/`](web/finder/) — one page for both drinks, built by `python/build_finder.py` from the wheel dataset,
the wine app and the tables in `data/reference/`:

- **Whisky:** every bottle on the Turkish shelf (48) gets a profile from its own reviews, shrunk toward the other
  reviews of its distillery or brand (prior weight 2 reviews; the prior never sees the bottle's own reviews).
  Tick flavours → bottles ranked by how often those flavours appear against the average. Pairing style is a
  threshold on the profile (smoky ≥ 0.6 or iodine/sea ≥ 0.5 → smoky/maritime; sherry ≥ 0.5; floral ≥ 0.6 → light;
  else honeyed) — 0.6 rather than 0.5 for smoke so that one review mentioning "woodsmoke" does not make J&B Rare
  (reviewed as a "light, Speyside-style blend") smoky.
- **Wine:** the 25 Turkish wines of the wine app borrow the profile of the same-style Bordeaux wines that share at
  least one of their grapes, weighted by the wine app's similarity score squared (grape 60 % · body 25 % · oak 15 %).
  Reds from the same Bordeaux grapes come out nearly identical — the page says so. Wines with no Bordeaux grape
  (Öküzgözü–Boğazkere, Muscat) have no profile.
- **Sides:** cheese rules as before (Whisky Advocate, Master of Malt; CIVB and Wine Folly for wine) plus snacks for
  whisky from Master of Malt — dark chocolate with smoky, dried figs / dates / sultanas with sherried, milk chocolate
  and smoked salmon with light, nuts with any dram.
- **Prices:** whisky habergazetesi.com.tr (Sept 2026; Royal Salute 21 from the Pernod Ricard Türkiye list, Jan 2026); wine habergazetesi.com.tr
  (09.07.2026; 5 of 25 wines); cheese and snacks Migros Sanal Market shelf prices (28.09.2026), median per portion,
  range = cheapest and dearest listing. Missing prices are shown as missing, never guessed.
- **Basket and shops:** add the suggestions to a basket (kept in the browser) for an average total and a
  cheapest–dearest range; the nearest liquor/wine shops, cheese shops/delis and supermarkets/nut shops for what is in
  it come from OpenStreetMap (Overpass), with a coordinate rounded to ~100 m, on a Leaflet map. No sale links.

## The app

- **Map and search** — colour the 86 distilleries by peat, pairing style or any flavour; click for the profile against the average.
- **By taste** — twelve sliders or four style presets → the closest distilleries, and the closest ones you can buy in Türkiye.
- **Closest taste in Türkiye** — Scotch can only be made in Scotland, so the "equivalent" is the nearest profile among the 13 atlas distilleries on the Turkish shelf (32 single-malt bottles; 16 blends are listed too), with TL list prices (habergazetesi.com.tr, September 2026; Diageo and Pernod Ricard Türkiye). Match = 100 × (1 − distance / largest possible distance).
- **The Turkish shelf** — every bottle with its price and Whisky Advocate score (median of matching reviews), blends included.
- **Cheese pairing** — four rules from Whisky Advocate and Master of Malt, Turkish cheeses first: smoky/medicinal → blue (Divle obruk tulumu, Erzurum küflü civil, Stilton); sherried → aged hard (eski kaşar, Kars gravyeri, Gouda); light → fresh and creamy (Ezine, fresh goat's cheese, Brie); honeyed → aged kaşar or cheddar.
- **Where to buy** — liquor shops nearest to you from OpenStreetMap (Overpass API), queried only when you ask, with a coordinate rounded to ~100 m. No online-shop links: in Türkiye alcohol may not be sold by mail, to under-18s, or at retail between 22:00 and 06:00 (Law 4250, art. 6).

## Run it

```bash
pip install -r python/requirements.txt
# optional Whisky Advocate part: see data/README.md
cd python && python run_analysis.py && python build_web.py && pytest -q tests && cd ..
cd python && python -m whisky.wheel && python run_wheel.py && python build_finder.py ../../wineapp && cd ..   # wheel + finder (needs the 2018 file, see data/README.md)
streamlit run python/app.py                          # Python app

Rscript R/install.R && Rscript R/run_analysis.R      # same statistics in R + parity report
Rscript -e 'shiny::runApp("R")'                      # R app

python -m http.server -d web                         # static app at localhost:8000
```

**Python ↔ R parity:** PCA variances and loadings, Mantel ρ, neighbour skills, the price slope, every Spearman ρ,
the text check and the 1,529 linked reviews agree to 4 decimals. Permutation p-values differ only by their random
draws. Silhouettes for k ≥ 3 differ by up to 0.03: the integer scores give only 66 distinct pairwise distances,
11 of 85 Ward merges tie, and SciPy and R break ties differently — both give 0.3836 at k = 2 and pick it.

## Read with care

- One profile per distillery, from an undocumented tasting: peated and unpeated lines of the same distillery, and change over the years, are invisible. Newer distilleries (e.g. Kilchoman) are missing.
- Coordinates are postcode-level: 86 distilleries sit on 77 points; 12 share a point (fanned out on the map).
- Whisky Advocate is one publication; its prices are US prices at review time. Turkish prices are a news site's compiled list prices and vary by shop.
- Associations only. Pairing styles are rules of thumb (`python/whisky/data.py: style_of`), not a model.

## Layout

```
python/whisky/data.py   load the atlas (KML) and the review list, link names, text check
python/whisky/wheel.py  Computational Whisky Wheel: dictionary loader, phrase matcher, features
python/                 run_analysis.py · build_web.py · app.py (Streamlit) · tests/ · run_wheel.py · build_finder.py
R/                      whisky_data.R · run_analysis.R · app.R (Shiny) · install.R
data/atlas/             WhiskyOut.kml (the atlas, CC BY-SA 3.0)
data/reference/         hand-built, sourced tables (see data/README.md)
data/derived/           whisky_wheel_dataset.csv (attribute flags, no text)
results/                every number above · web/ static app · web/finder/ finder · docs/ figures
```

**Data & licence.** Atlas: Pope, A. (2017). *Scotch Whisky characteristics* [dataset]. University of Edinburgh,
Edinburgh DataShare. [doi:10.7488/ds/1942](https://doi.org/10.7488/ds/1942) — CC BY-SA 3.0; flavour scores as published on the University of
Strathclyde "Nessie" outreach page. The atlas file and everything derived from it (`results/`, `web/data/`) are
shared under **CC BY-SA 3.0**; code is MIT. Map outline: Natural Earth (public domain). Whisky Advocate list:
Kaggle `neilcosgrove/scotch-whiskey-reviews-update-2020`, not redistributed; review texts for the wheel: Kaggle
`koki25ando/22000-scotch-whisky-reviews` (2018), not redistributed — the texts belong to Whisky Advocate, only
derived attribute flags are published. Leaflet (BSD-2) is vendored in `web/finder/leaflet/`; map data © OpenStreetMap
contributors (ODbL).

**References.** Chen, B., Rhodes, C., Crawford, A., Hambuchen, L. (2014). Wineinformatics: Applying data mining on
wine sensory reviews processed by the Computational Wine Wheel. *IEEE ICDM Workshops*, doi:10.1109/ICDMW.2014.149 ·
Chen, B. et al. (2016). The Computational Wine Wheel 2.0 and the TriMax triclustering in Wineinformatics. *Advances
in Data Mining*, Springer, doi:10.1007/978-3-319-41561-1_17 · Dong, Z., Guo, X., Rajana, S., Chen, B. (2020).
Understanding 21st century Bordeaux wines from wine reviews using naïve Bayes classifier. *Beverages* 6(1), 5 ·
Dong, Z., Atkison, T., Chen, B. (2021). Wineinformatics: Using the full power of the Computational Wine Wheel to
understand 21st century Bordeaux wines from the reviews. *Beverages* 7(1), 3 · Le, L., Hurtado, P. N., Lawrence, I.,
Tian, Q., Chen, B. (2023). Applying neural networks in Wineinformatics with the new Computational Wine Wheel.
*Fermentation* 9(7), 629 · Lee, K.-Y. M., Paterson, A., Piggott, J. R., Richardson, G. D. (2001). Origins of flavour
in whiskies and a revised flavour wheel: a review. *Journal of the Institute of Brewing* 107(5), 287–313.

---

## Türkçe özet

**Soru:** 86 İskoç damıtımevinin 12 boyutlu tat profilinde nasıl bir yapı var, tat gerçekten bölgeye mi bağlı, ve eleştirmen bir tadı ödüllendiriyor mu?

- **İki eksen yeterli:** tat farklarının %49'u iki eksende — biri duman-iyot-gövde, diğeri şeri-gövde-bal.
- **"Aile" yok, tek ayrım turba:** siluet k = 2'de 0,38 (6 yoğun turbalı damıtımevi ve kalan 80); k = 3–8 için en fazla 0,15. Uygulama bu yüzden bölgeye ya da kümeye göre değil, tat uzaklığına göre öneriyor.
- **"Bölge tadı" büyük ölçüde Islay'in dumanı:** coğrafya–tat ilişkisi (Mantel ρ 0,195, p 0,001) Islay çıkınca ρ 0,072 düzeyine iniyor, p 0,15. En yakın 5 damıtımevi yalnız iyot ve dumanı ortalamadan iyi tahmin ediyor; 12 tattan 8 tanesinde ortalamadan kötü.
- **Fiyat puanı az açıklıyor:** fiyat iki katına çıkınca +0,65 puan (%95 GA 0,58–0,71). Hiçbir tat boyutu damıtımevinin medyan puanıyla anlamlı ilişkili değil.
- **Veri bulgusu:** Whisky Advocate dosyasının 2020 sürümünde inceleme metinleri 150. satırdan sonra şişe adlarıyla eşleşmiyor (kendi markasını anma %2,3; komşu satırın markası %2,2). Atlas bu yüzden yalnız ad, kategori, puan ve fiyatı kullanıyor. 2018 sürümünde metinler kendi satırına ait (%50,3'e karşı %15,1); viski çarkı metinleri oradan okuyor.
- **Computational Whisky Wheel:** Computational Wine Wheel yöntemi (Chen ve ark.) Lee ve ark.'nın (2001) viski tat çarkı iskeletiyle viskiye taşındı: 3.580 ifade → 270 özellik → 58 alt kategori → 17 kategori. Sözlük dondurulduktan sonra okunan 40 incelemede elle işaretlenen 587 ifadede yakalama %94,7, isabet %94,5. Sonuç: 2.247 incelemelik, metinsiz bir özellik veri seti.
- **90+ tahmini zayıf:** en iyi model (naive Bayes) damıtımevine göre gruplu doğrulamada %77,8 doğruluk; hep "89 ve altı" demek %74,6. Sinyali çoğunlukla övgü kelimeleri taşıyor. Wishart panel puanlarıyla 12 tattan 3'ü uyumlu (iyot ρ 0,75, duman 0,58, meyve 0,40).
- **Viski ve şarap bulucu:** tadı seç → Türkiye'de satılan şişeler sıralanır → yanına peynir ya da atıştırmalık (bitter çikolata, kuru incir, hurma, kuruyemiş, füme somon) → sepet, ortalama toplam ve en yakın mağazalar (OpenStreetMap). Fiyatlar tarihli: viski habergazetesi.com.tr (Eylül 2026), şarap habergazetesi.com.tr (09.07.2026), peynir ve atıştırmalık Migros Sanal Market (28.09.2026).
- Her damıtımevi için: **Türkiye'de alınabilecek en yakın tat** (13 damıtımevinden 32 tek malt şişe, TL liste fiyatıyla; ayrıca 16 harman), **peynir eşleşmesi** (Divle obruk, Erzurum küflü civil, eski kaşar, Kars gravyeri, Ezine…) ve **en yakın satış noktaları** (OpenStreetMap). Türkiye'de alkollü içkinin posta ile satışı, 18 yaş altına satışı ve 22.00–06.00 arası perakende satışı yasak; bu yüzden çevrimiçi satış bağlantısı yok.
