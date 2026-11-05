"""Write the page's data files (docs/data): one compact JSON per election year plus index.json with trend counts."""
import datetime as dt
import json
import math
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "docs", "data")

CAND = ["race_id", "chamber", "state", "district", "special", "system", "name", "party", "gender", "gender_src", "race_eth",
        "incumbent", "p_party", "p_status", "p_votes", "p_pct", "r_votes", "r_pct", "p_won", "g_votes", "g_pct", "g_won",
        "gr_votes", "gr_pct", "qual", "office", "fec_id", "src_p", "src_g", "cawp_primary", "cawp_general", "cawp_seat", "link"]
PRIM = ["race_id", "chamber", "state", "district", "special", "system", "party", "contest", "n_cand", "n_women", "n_men",
        "n_unknown", "incumbent_running", "incumbent_gender", "winner", "winner_gender", "winner_pct", "woman_won",
        "top_woman_pct", "top_man_pct", "mixed", "src"]
RACE = ["race_id", "chamber", "state", "district", "special", "system", "n_general", "incumbent_running", "incumbent_party",
        "incumbent_gender", "open_seat", "seat_member_on_eday", "seat_member_female", "women_members_same_map", "women_members_since_1990",
        "d_primary_women", "r_primary_women", "d_primary_woman_won", "r_primary_woman_won", "d_nominee", "d_nominee_gender",
        "r_nominee", "r_nominee_gender", "matchup", "winner", "winner_party", "winner_gender", "woman_won_general",
        "d_share_2party", "pres_d_2party", "pvi", "rural", "white_nh", "black_nh", "hisp", "asian_nh", "ba_plus", "med_income",
        "src_general"]
PARTY_PRIMARY = ("contested", "runoff", "uncontested", "convention")


def clean(v):
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return None
        if v.is_integer() and abs(v) < 1e15:
            return int(v)
        return round(v, 2)
    if hasattr(v, "item"):
        return clean(v.item())
    return v


def rows(df, cols):
    out = []
    for rec in df[cols].itertuples(index=False):
        out.append([clean(x) if not (isinstance(x, str) and x == "") else None for x in rec])
    return out


def trends(cand, prim, races):
    t = []
    for (y, ch), r in races.groupby(["year", "chamber"]):
        p = prim[(prim.year == y) & (prim.chamber == ch)]
        c = cand[(cand.year == y) & (cand.chamber == ch)]
        row = dict(year=int(y), chamber=ch, races=len(r), decided=int(r.winner.fillna("").ne("").sum()),
                   women_won=int((r.woman_won_general == 1).sum()))
        for party in ("D", "R"):
            pp = p[(p.party == party) & p.contest.isin(PARTY_PRIMARY)]
            row[party] = dict(
                primaries=len(pp), with_woman=int((pp.n_women > 0).sum()), woman_won=int((pp.woman_won == 1).sum()),
                contested=int(pp.contest.isin(["contested", "runoff"]).sum()),
                contested_with_woman=int((pp.contest.isin(["contested", "runoff"]) & (pp.n_women > 0)).sum()),
                contested_woman_won=int((pp.contest.isin(["contested", "runoff"]) & (pp.woman_won == 1)).sum()),
                mixed=int((pp.mixed == 1).sum()), mixed_woman_won=int(((pp.mixed == 1) & (pp.woman_won == 1)).sum()),
                women_candidates=int(((c.party == party) & (c.gender == "F")).sum()),
                candidates=int((c.party == party).sum()),
                nominees=int(r[f"{party.lower()}_nominee"].fillna("").ne("").sum()),
                women_nominees=int((r[f"{party.lower()}_nominee_gender"] == "F").sum()),
                seats=int((r.winner_party == party).sum()),
                women_seats=int(((r.winner_party == party) & (r.winner_gender == "F")).sum()))
        t.append(row)
    return t


def write(extra=None):
    os.makedirs(SITE, exist_ok=True)
    cand = pd.read_csv(os.path.join(DATA, "candidates.csv"), low_memory=False)
    prim = pd.read_csv(os.path.join(DATA, "primaries.csv"), low_memory=False)
    races = pd.read_csv(os.path.join(DATA, "races.csv"), low_memory=False)
    cov = pd.read_csv(os.path.join(DATA, "coverage.csv"))
    for df in (cand, prim, races):
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].fillna("")
    years = sorted(int(y) for y in races.year.unique())
    for y in years:
        d = dict(year=y, cf=CAND, c=rows(cand[cand.year == y], CAND), pf=PRIM, p=rows(prim[prim.year == y], PRIM),
                 rf=RACE, r=rows(races[races.year == y], RACE))
        p = os.path.join(SITE, f"y{y}.json")
        new = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        old = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        if new != old:
            with open(p, "w", encoding="utf-8") as f:
                f.write(new)
    cawp = pd.read_excel(os.path.join(DATA, "static", "cawp_master.xlsx"), usecols=["Year"])
    idx = dict(generated=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), years=years,
               cawp_last_year=int(cawp.Year.max()), coverage=cov.to_dict("records"), trends=trends(cand, prim, races),
               counts=dict(candidates=len(cand), primaries=len(prim), races=len(races)))
    idx.update(extra or {})
    with open(os.path.join(SITE, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    import codebook
    codebook.write()  # docs/data/codebook.json and .csv (variable meanings for the downloads)
    print("site data:", len(years), "years")


if __name__ == "__main__":
    write()
