"""Streamlit version of the atlas.   streamlit run python/app.py
Reads the same web/data/whisky.json the static site uses (build it with python/build_web.py)."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Scotch Whisky Flavour Atlas", page_icon="🥃", layout="wide")


@st.cache_data
def load():
    return json.loads((ROOT / "web" / "data" / "whisky.json").read_text())


D = load()
d, shelf = D["d"], D["shelf"]
F = np.array(d["f"], float)
tr = st.sidebar.radio("Dil / Language", ["Türkçe", "English"]) == "Türkçe"
T = (lambda a, b: a if tr else b)
FLAV = (["Gövde", "Tatlılık", "Duman", "İyot / tıbbi", "Tütün", "Bal", "Baharat", "Şarapsı / şeri", "Kuruyemiş", "Malt", "Meyve", "Çiçek"]
        if tr else ["Body", "Sweetness", "Smoky", "Medicinal", "Tobacco", "Honey", "Spicy", "Winey / sherry", "Nutty", "Malty", "Fruity", "Floral"])
STYLE = ["dumanlı / iyotlu", "şeri / şarapsı", "hafif", "ballı / dengeli"] if tr else ["smoky / medicinal", "sherried / winey", "light", "honeyed / balanced"]
MAXD = 4 * math.sqrt(12)
match = lambda dist: f"{round(100 * (1 - dist / MAXD))}%"

st.title(T("İskoç viskisinin tadı coğrafyayı izliyor mu?", "Does Scotch whisky taste follow geography?"))
g = D["results"]["geography"]
st.caption(T(f"86 damıtımevi · 12 tat · Mantel ρ {g['mantel_rho']:.2f} → Islay'siz {g['mantel_rho_without_islay']:.2f}",
             f"86 distilleries · 12 flavours · Mantel ρ {g['mantel_rho']:.2f} → without Islay {g['mantel_rho_without_islay']:.2f}"))


def shelf_rows(i):
    return [shelf[k] for k in d["tr"][i]]


def card(i):
    st.subheader(d["n"][i])
    c1, c2, c3 = st.columns(3)
    c1.metric(T("Tarz", "Style"), STYLE[d["st"][i]])
    c2.metric(T("Bölge", "Area"), "Islay" if d["isl"][i] else d["pc"][i])
    wa = d["wa"][i]
    c3.metric("Whisky Advocate", f"{wa[1]:.1f}" if wa else "—", T(f"{wa[0]} inceleme", f"{wa[0]} reviews") if wa else None)
    st.bar_chart(pd.DataFrame({T("Tat", "Flavour"): FLAV, "0–4": d["f"][i]}).set_index(T("Tat", "Flavour")), horizontal=True, sort=False, color="#93520f")
    if d["tr"][i]:
        st.markdown("#### " + T("Türkiye'de satılan şişeleri", "Its bottles sold in Türkiye"))
        st.dataframe([{T("Şişe", "Bottle"): p["product"], "TL": p["price_tl"] or "—", T("Tarih", "As of"): p["as_of"],
                       "WA": p.get("wa_points"), T("Kaynak", "Source"): p["source_url"]} for p in shelf_rows(i)],
                     hide_index=True, width="stretch", column_config={T("Kaynak", "Source"): st.column_config.LinkColumn()})
    st.markdown("#### " + T("Türkiye'de bulabileceğin en yakın tatlar", "Closest tastes you can buy in Türkiye"))
    st.dataframe([{T("Damıtımevi", "Distillery"): d["n"][j], T("Eşleşme", "Match"): match(dist),
                   T("Şişeler", "Bottles"): ", ".join(f"{p['product']} ({p['price_tl'] or '—'} TL)" for p in shelf_rows(j))}
                  for j, dist in d["alt"][i]], hide_index=True, width="stretch")
    st.markdown("#### " + T("Tadı en çok benzeyenler", "Most similar in taste"))
    st.dataframe([{T("Damıtımevi", "Distillery"): d["n"][j], T("Eşleşme", "Match"): match(dist), T("Tarz", "Style"): STYLE[d["st"][j]]}
                  for j, dist in d["nb"][i]], hide_index=True, width="stretch")
    rule = next(r for r in D["rules"] if r["rule_id"] == D["styles"][d["st"][i]])
    ch = {c["id"]: c for c in D["cheeses"]}
    st.markdown("#### " + T("Yanına peynir", "Cheese to pair"))
    st.write((rule["rationale_tr"] if tr else rule["rationale_en"]) + f" — [{rule['source_name']}]({rule['source_url']})")
    st.write(", ".join((ch[c]["name_tr"] if tr else ch[c]["name_en"]) for c in rule["cheese_ids"].split(";")))
    if d["b"][i]:
        st.markdown("#### " + T("En yüksek puanlı şişeler (Whisky Advocate)", "Top-scored bottles (Whisky Advocate)"))
        st.dataframe([{T("Puan", "Points"): p, T("Şişe", "Bottle"): nm, "$": u} for nm, p, u in d["b"][i]], hide_index=True, width="stretch")


def haversine(a, b):
    r = math.pi / 180
    h = math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


@st.cache_data(ttl=3600, show_spinner=False)
def shops(lat, lon):
    for radius in (3000, 10000, 30000):
        q = f'[out:json][timeout:20];(nwr["shop"~"^(alcohol|wine|beverages)$"](around:{radius},{lat},{lon}););out center 80;'
        els = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=30).json()["elements"]
        out = []
        for e in els:
            la, lo = e.get("lat") or e.get("center", {}).get("lat"), e.get("lon") or e.get("center", {}).get("lon")
            tg = e.get("tags", {})
            out.append({"km": round(haversine((lat, lon), (la, lo)), 1), "name": tg.get("name", "—"), "type": tg.get("shop"),
                        "osm": f"https://www.openstreetmap.org/{e['type']}/{e['id']}"})
        if len(out) >= 5 or radius == 30000:
            return sorted(out, key=lambda x: x["km"])[:12]


tab1, tab2, tab3, tab4 = st.tabs([T("Damıtımevi", "Distillery"), T("Tadına göre", "By taste"), T("Harita", "Map"), T("Nereden alırım?", "Where to buy?")])
with tab1:
    card(st.selectbox(T("Damıtımevi", "Distillery"), range(len(d["n"])), format_func=lambda k: d["n"][k], index=d["n"].index("Lagavulin")))
with tab2:
    cols = st.columns(4)
    want = np.array([cols[k % 4].slider(FLAV[k], 0, 4, int(round(F[:, k].mean()))) for k in range(12)], float)
    dist = np.sqrt(((F - want) ** 2).sum(1))
    order = np.argsort(dist, kind="stable")
    st.markdown("#### " + T("Türkiye'de bulabileceklerin", "What you can buy in Türkiye"))
    st.dataframe([{T("Damıtımevi", "Distillery"): d["n"][j], T("Eşleşme", "Match"): match(dist[j]),
                   T("Şişeler", "Bottles"): ", ".join(p["product"] for p in shelf_rows(j))} for j in order if d["tr"][j]][:4],
                 hide_index=True, width="stretch")
    st.markdown("#### " + T("Bu tada en yakın damıtımevleri", "Distilleries closest to this taste"))
    st.dataframe([{T("Damıtımevi", "Distillery"): d["n"][j], T("Eşleşme", "Match"): match(dist[j]), T("Tarz", "Style"): STYLE[d["st"][j]]}
                  for j in order[:8]], hide_index=True, width="stretch")
with tab3:
    peat = F[:, 2] + F[:, 3]
    df = pd.DataFrame({"lat": d["lat"], "lon": d["lon"], "size": 1500 + 700 * peat,
                       "color": [f"#{int(245 - 16 * v):02x}{int(222 - 20 * v):02x}{int(179 - 20 * v):02x}" for v in peat]})
    st.caption(T("Renk ve boyut: turba (duman + iyot). Koordinatlar posta kodu düzeyinde.", "Colour and size: peat (smoky + medicinal). Coordinates are postcode-level."))
    st.map(df, latitude="lat", longitude="lon", size="size", color="color")
with tab4:
    st.caption(T("OpenStreetMap'teki içki satış noktaları. 22.00–06.00 arası perakende satış ve 18 yaş altına satış yasaktır (4250 s. Kanun md. 6).",
                 "Liquor shops from OpenStreetMap. Retail sales are banned 22:00–06:00 and to under-18s (Law 4250, art. 6)."))
    prov = st.selectbox(T("İl", "Province"), D["provinces"], format_func=lambda p: p[0], index=33)
    if st.button(T("Yakındaki satış noktalarını bul", "Find shops nearby")):
        try:
            st.dataframe(shops(prov[1], prov[2]), hide_index=True, width="stretch",
                         column_config={"osm": st.column_config.LinkColumn("OpenStreetMap")})
        except requests.RequestException:
            st.error(T("OpenStreetMap şu an yanıt vermedi.", "OpenStreetMap did not answer."))
    st.caption("© OpenStreetMap contributors (ODbL)")
