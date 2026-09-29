"""Computational Whisky Wheel: review text -> normalized flavour attributes (+ subcategory / category counts).

The Computational Wine Wheel method (Chen et al. 2014, 2016; Dong, Atkison & Chen 2021) moved to whisky.
Tiers follow the revised Scotch whisky flavour wheel of Lee, Paterson, Piggott & Richardson (2001),
J. Inst. Brewing 107(5):287-313, plus the CWW's non-flavour OVERALL tiers (body, finish, balance, descriptors).
Dictionary: data/reference/whisky_wheel.csv (category, subcategory, normalized, specific terms), written from
the 2,207 development reviews only; the 40 hold-out reviews in wheel_holdout.csv were not read while writing it.

Matching, as in the CWW: longest phrase first and matched text is used up, so "dark chocolate" never also counts
as "chocolate". Added here: cask/process, colour and brand phrases are blanked before matching ("oloroso sherry
casks" is a production fact, not a taste), and a match is dropped when a negator stands in the 3 words before it
in the same clause ("not dominated by wood").
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REF = Path(__file__).resolve().parents[2] / "data" / "reference"
NEG = {"no", "not", "without", "never", "nor", "lacks", "lacking", "lack", "hardly", "barely", "scarcely", "devoid", "absent"}
_CASKWORD = (r"(?:ex|first|second|third|refill|fresh|virgin|new|charred|re|toasted|american|european|spanish|french|japanese|"
             r"mizunara|oak|white|red|oloroso|sherry|px|pedro|ximenez|ximénez|ximinez|fino|manzanilla|amontillado|palo|cortado|"
             r"bourbon|port|tawny|ruby|wine|rum|madeira|marsala|sauternes|cognac|armagnac|brandy|beer|stout|ipa|tokaji|burgundy|"
             r"bordeaux|barolo|cabernet|sauvignon|chardonnay|single|double|triple|quarter|small|large|fill|wood|in|from|of|the|a|"
             r"and|\d+)")
_COLOUR = r"(?:gold|golden|amber|straw|copper|mahogany|chestnut|ruby|bronze|tawny|brown|yellow|orange|red|russet|caramel|honey|walnut)"
STOP = [re.compile(p) for p in [
    rf"\b(?:{_CASKWORD} ){{0,5}}(?:casks?|butts?|barrels?|hogsheads?|hoggies?|hoggie|puncheons?|barriques?|octaves?|pipes|port pipe)\b",
    rf"\b(?:matured|aged|finished|finishing|maturation|maturing|filled|spent|transferred|racked|married|seasoned)"
    rf"(?: (?:entirely|initially|fully|exclusively|further|then|originally))? (?:in|into|with)(?: {_CASKWORD})+\b",
    r"\b(?:sherry|bourbon|port|wine|rum|madeira|marsala|sauternes|oloroso|px|cognac|beer|stout|ipa|tokaji|burgundy|barolo|cask|barrel) "
    r"(?:finish|finished|finishing|matured|maturation|aged|seasoned|wood|influenced)\b",
    r"\b(?:cask|barrel|natural|full|higher|high|bottling) strength\b|\bbottled at\b|\b(?:non |not )?chill filter(?:ed|ing)\b|"
    r"\b(?:no )?age statement\b|\bsingle cask\b|\bsmall batch\b|\blimited edition\b|\btravel retail\b|\bduty free\b|"
    r"\bspecial releases?\b|\bdistillers edition\b|\bcore range\b|\beditor's choice\b",
    rf"\b(?:(?:very|quite|light|pale|bright|deep|dark|full|antique|old|rich|burnished|reddish|brilliant|amber|golden|gold) )*{_COLOUR} "
    r"(?:colou?r(?:ed)?|hue|hues|tint|tinted|tones?)\b|\bcolou?r(?:ed)?\b|"
    r"\b(?:very )?(?:pale|light|bright|deep|full|antique|old|amber|golden|straw) (?:straw|gold|amber)\b",
    r"\b(?:port (?:ellen|charlotte|askaig|dundas|wemyss)|glen [a-z]+|highland park|great king street|oak cross|spice tree|"
    r"peat monster|big peat|smokehead|rock oyster|sheep dip|scallywag|talisker storm|vanilla summer|spice king|peat chimney|"
    r"honey pot|kiln embers|smooth gentleman|velvet fig|the hive|(?:black|blue|gold|green|red|double black) label|white horse|"
    r"famous grouse|monkey shoulder|cutty sark|black bottle|(?:single|blended|vatted|pure) malts?|malt (?:whisk(?:y|ies)|scotch)|"
    r"(?:single|blended) grain|grain (?:whisk(?:y|ies)|scotch)|malts|mash ?bill|(?:copper )?pot stills?|column still|"
    r"long (?:time|ago|before|since|been|awaited|gone|overdue)|as long as|how long|so long|no longer)\b",
]]


def norm(text: str) -> str:
    """Lower-case, curly apostrophes straightened, hyphens and '&' spelled out, whitespace collapsed."""
    t = str(text).lower().replace("’", "'").replace("‘", "'").replace("-", " ").replace("&", " and ")
    return re.sub(r"\s+", " ", t).strip()


def _plurals(w: str) -> list[str]:
    out = [w + "s"]
    if w.endswith(("s", "x", "z", "ch", "sh", "o")):
        out.append(w + "es")
    if len(w) > 2 and w.endswith("y") and w[-2] not in "aeiou":
        out.append(w[:-1] + "ies")
    return out


def load_wheel(path: str | Path = REF / "whisky_wheel.csv"):
    """(taxonomy: normalized -> category/subcategory, forms: surface form -> normalized, compiled matcher)."""
    w = pd.read_csv(path)
    forms: dict[str, str] = {}
    for r in w.itertuples():                       # explicit terms first, so they win over generated plurals
        for s in r.specific.split("|"):
            forms.setdefault(norm(s), r.normalized)
    adjectival = set(w.loc[w["category"].isin(["OVERALL", "MOUTHFEEL", "TASTE", "PUNGENT"]), "normalized"])
    for s, n in list(forms.items()):
        if n in adjectival:                        # no "goods", "rich es": plurals only for nouns
            continue
        head, _, last = s.rpartition(" ")
        for p in _plurals(last):
            forms.setdefault(f"{head} {p}".strip(), n)
    alts = "|".join(sorted(map(re.escape, forms), key=len, reverse=True))
    pat = re.compile(rf"(?<![\w'])({alts})(?![\w'])")
    return w.set_index("normalized")[["category", "subcategory"]], forms, pat


def extract(text: str, forms: dict, pat: re.Pattern) -> list[tuple[str, int, int]]:
    """[(normalized, start, end)] with offsets into norm(text); leftmost-longest, stop phrases blanked, negation dropped."""
    t = norm(text)
    for s in STOP:
        t = s.sub(lambda m: " " * len(m.group()), t)
    out = []
    for m in pat.finditer(t):
        clause = re.split(r"[,.;:!?()\"]", t[: m.start()])[-1].split()
        if NEG & set(clause[-3:]) or clause[-1:] == ["less"]:
            continue
        out.append((forms[m.group(1)], m.start(), m.end()))
    return out


def features(texts, wheel=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Binary normalized attributes, subcategory counts and category counts (distinct attributes per tier), one row per text."""
    tax, forms, pat = wheel or load_wheel()
    found = [sorted({n for n, _, _ in extract(t, forms, pat)}) for t in texts]
    N = pd.DataFrame([{n: 1 for n in f} for f in found], columns=tax.index).fillna(0).astype(int)
    S = N.T.groupby(tax["category"] + "|" + tax["subcategory"]).sum().T
    C = N.T.groupby(tax["category"]).sum().T
    return N, S, C


if __name__ == "__main__":   # smallest check that fails if matching, negation or stop phrases break
    tax, forms, pat = load_wheel()
    got = [n for n, _, _ in extract("Not dominated by wood; dark chocolate, sea salt. Matured in oloroso sherry casks. Long finish.", forms, pat)]
    assert got == ["DARK CHOCOLATE", "SALT", "LONG FINISH"], got
    assert [n for n, _, _ in extract("Less complex, but peachy fruit and a malty foundation.", forms, pat)] == ["PEACH", "FRUIT", "MALT"]
    print("ok", len(tax), "attributes", len(forms), "forms")
