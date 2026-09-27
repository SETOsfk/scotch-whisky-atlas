"""Run with:  pytest python/tests -q"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from whisky.data import FLAVOURS, ROOT, haversine_km, link, load_atlas, parse_price, style_of, text_alignment  # noqa: E402

A = load_atlas()


def test_atlas_shape_and_names():
    assert len(A) == 86 and A[FLAVOURS].isin(range(5)).all().all()
    assert A["islay"].sum() == 7 and {"Balvenie", "Laphroaig", "Cragganmore"} <= set(A["distillery"])
    assert not {"Belvenie", "Laphroig"} & set(A["distillery"])
    assert A["lat"].between(54.6, 59.1).all() and A["lon"].between(-6.5, -2.2).all()


def test_style_rules_fire_in_order():
    row = dict.fromkeys(FLAVOURS, 0)
    assert style_of({**row, "Smoky": 3, "Winey": 4}) == "peated"          # peat wins over sherry
    assert style_of({**row, "Winey": 3, "Body": 1}) == "sherried"
    assert style_of({**row, "Body": 1, "Smoky": 1}) == "light"
    assert style_of({**row, "Body": 2}) == "honeyed"


def test_parse_price():
    assert parse_price("1,500") == 1500 and parse_price("$50/375ml.") == 100
    assert math.isnan(parse_price("60,000/set")) and math.isnan(parse_price("n/a"))


def test_link_takes_earliest_single_malt_distillery():
    df = pd.DataFrame({"name": ["Longmorn-Glenlivet 15 year old, 43%", "Bruichladdich Octomore 08.3, 61.2%",
                                "The Singleton of Glen Ord 12 year old, 40%", "Gordon & MacPhail (distilled at Old Pulteney), 43%",
                                "Johnnie Walker Black Label, 40%"],
                       "category": ["Single Malt Scotch"] * 4 + ["Blended Scotch Whisky"]})
    assert link(df, A) == ["Longmorn", None, "Glen Ord", "Old Pulteney", None]


def test_haversine_edinburgh_glasgow():
    d = haversine_km(np.array([55.953, 55.861]), np.array([-3.189, -4.251]))
    assert 64 < d[0, 1] < 70 and d[0, 0] == 0


def test_text_alignment_detects_shuffle():
    names = [f"brand{c}{c} 12 year old" for c in "abcdefghijkl"] * 30
    texts = [f"a fine {n.split()[0]} dram" for n in names]
    df = pd.DataFrame({"name": names, "description": texts})
    ok = text_alignment(df, head=60)
    assert ok["same_row_rest"] == 1 and ok["shifted_rest"] == 0
    df["description"] = np.random.default_rng(0).permutation(texts)
    bad = text_alignment(df, head=60)
    assert bad["same_row_rest"] < 0.3


def test_web_json_invariants():
    p = ROOT / "web" / "data" / "whisky.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())["d"]
    for i, (nb, alt) in enumerate(zip(d["nb"], d["alt"])):
        assert all(j != i for j, _ in nb) and [x for _, x in nb] == sorted(x for _, x in nb)
        assert all(d["tr"][j] for j, _ in alt)                           # alternatives are on the Turkish shelf
