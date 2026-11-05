"""Build the women candidates database (U.S. House and Senate, 1990 to the current cycle).

  python pipeline/build_db.py                    # daily: cached 1990-2022 rows + fresh 2024/current-cycle pages
  python pipeline/build_db.py --rebuild-history  # re-read every raw source (after python pipeline/collect.py --full)

Output (data/):
  candidates.csv  one row per candidate per race (primary, runoff and general results, gender, sources)
  primaries.csv   one row per party primary (D/R) per race: field size, women, winner, contest type
  races.csv       one row per race: system, incumbent, nominees, winner, women outcomes, previous women members
  coverage.csv    rows by year x chamber x source, unmatched CAWP women, checks

Sources by year (official first, Wikipedia only where nothing official is compiled yet)
  House primaries  1990-2000 Pettigrew-Owen-Wanless (CC0) | 2002-2022 FEC | 2024-2026 Wikipedia
  House generals   1990-2000 MEDSL (state returns, CC0) | 2002-2022 FEC | 2024 MEDSL until FEC publishes | 2026 Wikipedia
  Senate           1990-2000 Wikipedia race pages | 1996 and 2002-2022 FEC | 2024-2026 Wikipedia
  Gender           CAWP women candidates database 1990-2024 and the CAWP 2026 candidate list; after that: earlier
                   CAWP/Pettigrew/members, then first names
"""
import argparse
import collections
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fec_results as F  # noqa: E402
import medsl as M  # noqa: E402
import names as N  # noqa: E402
import wiki as W  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")            # downloaded each run, not kept in git
STATIC = os.path.join(ROOT, "data", "static")  # kept in git: inputs that rarely change + cached history rows
OUT = os.path.join(ROOT, "data")
LAST_HISTORY = 2022                        # FEC "Federal Elections" exists through 2022; later years are read every day
_today = dt.date.today()
LAST_YEAR = _today.year if _today.year % 2 == 0 else _today.year - 1
YEARS = list(range(1990, LAST_YEAR + 2, 2))
FEC_YEARS = list(range(2002, 2024, 2))
UA = "US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"
STATES50 = sorted(W.STATE_ABBR.values())
ABBR_BY_NAME = {k.lower(): v for k, v in W.STATE_ABBR.items()}
PETT_STATES = sorted(W.STATE_ABBR)  # alphabetical, 01 = Alabama ... 50 = Wyoming


def log(*a):
    print(*a, flush=True)


def at_large(st, year):
    return st in ("AK", "DE", "ND", "SD", "VT", "WY") or (st == "MT" and 1992 <= year <= 2020)


def system(st, year):
    if st == "CA" and year >= 2012:
        return "top2"
    if st == "CA" and year in (1998, 2000):
        return "blanket"
    if st == "WA" and year >= 2008:
        return "top2"
    if st == "WA" and year <= 2002:
        return "blanket"
    if st == "AK" and year >= 2022:
        return "top4"
    if st == "AK" and year <= 2000:
        return "blanket"
    if st == "LA" and (year <= 2006 or 2012 <= year <= 2024):
        return "jungle"
    return "party"


def race_id(year, ch, st, d, sp=0):
    return f"{year}-{ch}-{st}-{int(d):02d}" + ("-sp" if sp else "")


def std_name(name):
    """'Last, First Middle' -> 'First Middle Last' (Wikipedia style stays as is)"""
    s = str(name or "").strip()
    if "," in s:
        last, rest = s.split(",", 1)
        rest = re.sub(r"\s+", " ", rest).strip()
        suf = ""
        m = re.search(r"\b(Jr\.?|Sr\.?|II|III|IV)\s*$", rest)
        if m:
            suf, rest = " " + m.group(1), rest[: m.start()].strip(" ,")
        return f"{rest} {last.strip()}{suf}".strip()
    return re.sub(r"\s+", " ", s)


def ok(v):
    return v is not None and not (isinstance(v, float) and pd.isna(v))


def blank(**kw):
    r = dict(year=None, chamber=None, state=None, district=0, special=0, name="", party="O", incumbent=0,
             p_party="", p_votes=None, p_pct=None, p_status="", r_votes=None, r_pct=None, p_won=None,
             g_votes=None, g_pct=None, g_won=None, gr_votes=None, gr_pct=None, fec_id="", src_p="", src_g="",
             gender="", gender_src="", race_eth="", qual=None, office=None, note="", link="")
    r.update(kw)
    return r


# ------------------------------------------------------------------ FEC 2002-2022 (and 1996 Senate)
def from_fec(year):
    p = F.persons(year)
    if p.empty:
        return []
    for c in ("p_pct", "r_pct", "g_pct", "gr_pct"):
        if p[c].dropna().max() <= 1.0001:
            p[c] = p[c] * 100
    rows = []
    has_pwin = (p.pwin_fec.str.len() > 0).any()
    has_gwin = (p.gwin_fec.str.len() > 0).any()
    for rid, g in p.groupby(["chamber", "state", "district", "special"]):
        ch, st, d, sp = rid
        if ch == "H" and sp:
            continue  # unexpired-term House specials held with the general
        if st not in STATES50:
            continue
        sysm = system(st, year)
        recs = g.to_dict("records")
        # primary winners
        pw = {}
        for party in ("D", "R"):
            grp = [r for r in recs if r["p_party"] == party and not r["writein"]]
            if not grp:
                continue
            if has_pwin:
                for r in grp:
                    pw[id(r)] = int(r["pwin_fec"].startswith("W") or r["pwin_fec"] == "*")
                continue
            run = [r for r in grp if ok(r["r_votes"])]
            vot = [r for r in grp if ok(r["p_votes"]) and r["p_status"] == "votes"]
            if sysm in ("top2", "top4"):
                for r in grp:
                    pw[id(r)] = int(ok(r["g_votes"]))
                continue
            if run:
                top = max(run, key=lambda r: r["r_votes"])
                for r in grp:
                    pw[id(r)] = int(r is top)
            elif vot:
                top = max(vot, key=lambda r: r["p_votes"])
                for r in grp:
                    pw[id(r)] = int(r is top) if r["p_status"] == "votes" else int(r["p_status"] in ("unopposed", "convention"))
            else:
                for r in grp:
                    pw[id(r)] = int(r["p_status"] in ("unopposed", "convention"))
        # general votes printed for a primary loser that dwarf everyone else's are a misplaced total (WA 2004);
        # a primary loser can still win the general (Murkowski 2010 write-in), so only far-off values are dropped
        if sysm in ("party", "blanket"):
            for party in ("D", "R"):
                won = [r for r in recs if r["p_party"] == party and pw.get(id(r)) == 1 and ok(r["g_votes"])]
                for r in recs:
                    others = sum(x["g_votes"] for x in recs if x is not r and ok(x["g_votes"]))
                    if r["p_party"] == party and pw.get(id(r)) == 0 and ok(r["g_votes"]) and won and others and r["g_votes"] > 1.5 * others:
                        r["note"] = ("general votes dropped (looks like a total) | " + r["note"]).strip(" |")
                        r["g_votes"], r["g_pct"], r["gwin_fec"] = None, None, ""
        # general winner
        if has_gwin and any(r["gwin_fec"] for r in recs):
            gw = {id(r): int(r["gwin_fec"].startswith("W")) for r in recs}
        else:
            gr = [r for r in recs if ok(r["gr_votes"])]
            gg = [r for r in recs if ok(r["g_votes"])]
            un = [r for r in recs if r.get("g_unopposed")]
            top = max(gr, key=lambda r: r["gr_votes"]) if gr else (max(gg, key=lambda r: r["g_votes"]) if gg else (un[0] if un else None))
            gw = {id(r): int(r is top) for r in recs}
        for r in recs:
            if r["writein"] and not ok(r["g_votes"]):
                continue
            rows.append(blank(year=year, chamber=ch, state=st, district=0 if ch == "S" else d, special=sp,
                              name=std_name(r["name"]), party=r["party"], incumbent=r["incumbent"],
                              p_party=r["p_party"], p_votes=r["p_votes"], p_pct=r["p_pct"], p_status=r["p_status"],
                              r_votes=r["r_votes"], r_pct=r["r_pct"], p_won=pw.get(id(r)),
                              g_votes=r["g_votes"], g_pct=100.0 if r.get("g_unopposed") else r["g_pct"],
                              g_won=gw.get(id(r)) if (ok(r["g_votes"]) or ok(r["gr_votes"]) or r.get("g_unopposed")) else None,
                              gr_votes=r["gr_votes"], gr_pct=r["gr_pct"], fec_id=r["fec_id"],
                              src_p="FEC" if r["p_party"] else "", src_g="FEC" if (ok(r["g_votes"]) or r.get("g_unopposed")) else "",
                              note=("unopposed in general | " if r.get("g_unopposed") else "") + r["note"][:200]))
    return rows


def fec_parties():
    """FEC candidate master files: candidate ID -> party (DEM/REP/...)"""
    import zipfile
    out = {}
    for y in range(1990, 2028, 2):
        p = os.path.join(RAW, "fec_bulk", str(y), f"cn{y % 100:02d}.zip")
        if not os.path.exists(p):
            continue
        with zipfile.ZipFile(p) as z:
            for line in z.read(z.namelist()[0]).decode("latin-1").splitlines():
                f = line.split("|")
                if len(f) > 2:
                    out[f[0]] = f[2]
    return out


def fill_party_from_fec_id(rows, parties):
    """non-partisan or write-in lines in the results (MS 2018 special, Murkowski 2010 write-in): use the FEC party"""
    n = 0
    for r in rows:
        if r["party"] == "O" and r.get("fec_id"):
            p = parties.get(r["fec_id"], "")
            m = "D" if p in ("DEM", "DFL") else ("R" if p == "REP" else None)
            if m:
                r["party"] = m
                r["note"] = (str(r["note"] or "") + f" | party from FEC candidate file ({p})").strip(" |")
                n += 1
    return n


def nominated_without_primary(rows):
    """party candidate on the general ballot but no primary record for that party (convention, no primary held,
    missing in the primary source): count as the party's nominee"""
    by = collections.defaultdict(list)
    for r in rows:
        by[r["race_id"]].append(r)
    n = 0
    for rid, rs in by.items():
        if system(rs[0]["state"], rs[0]["year"]) in ("top2", "top4", "jungle"):
            continue
        for party in ("D", "R"):
            if any(r["party"] == party and r.get("p_won") == 1 for r in rs):
                continue
            gen = [r for r in rs if r["party"] == party and (ok(r["g_votes"]) or ok(r["g_pct"]) or r.get("g_won") is not None)]
            if len(gen) == 1:
                r = gen[0]
                r["p_party"] = party
                r["p_won"] = 1
                r["p_status"] = r["p_status"] or "nominated (no primary record)"
                n += 1
    return n


# ------------------------------------------------------------------ Pettigrew House primaries 1990-2018
def pett_name(s):
    t = [x for x in str(s).split("_") if x]
    if not t:
        return ""
    last = t[0].replace("-", " ").title().replace(" ", "-") if "-" in t[0] else t[0].title()
    rest = " ".join(x.title() for x in t[1:])
    return f"{rest} {last}".strip()


PETT_COMPACT = os.path.join(STATIC, "pettigrew_compact.csv.gz")


def load_pettigrew(raw=False):
    """House primaries 1990-2018. raw=True reads the Dataverse files (history rebuild) and refreshes the compact copy
    kept in data/static (names, gender and presidential vote, used every day)."""
    if not raw:
        return pd.read_csv(PETT_COMPACT, dtype={"candidate": str})
    a = pd.read_stata(os.path.join(RAW, "dataverse/house_primaries_26448/House primary elections (1956-2010) data.dta"), convert_categoricals=False)
    b = pd.read_stata(os.path.join(RAW, "dataverse/house_primaries_CXVMSY/house_primary_2012_2018.dta"), convert_categoricals=False)
    a["src"], b["src"] = "Pettigrew-Owen-Wanless", "Miller-Camberg"
    d = pd.concat([a[a.year >= 1990], b], ignore_index=True)
    d["st"] = d.stcd.astype(str).str[:2].astype(int).map(lambda i: W.STATE_ABBR[PETT_STATES[i - 1]])
    d["dist"] = d.stcd.astype(str).str[2:].astype(int)
    d["dist"] = [0 if at_large(s, int(y)) else x for s, y, x in zip(d.st, d.year, d.dist)]
    d["pparty"] = d.party.map({0: "R", 1: "D"})
    d["rid"] = d.raceid.astype(str)
    d[["year", "st", "dist", "pparty", "candidate", "gender", "prez"]].to_csv(PETT_COMPACT, index=False)
    return d


def from_pettigrew(d, year):
    rows = []
    x = d[(d.year == year) & (d.type != 3)]
    for (st, dist, party), g in x.groupby(["st", "dist", "pparty"]):
        main = g[~g.rid.str.endswith("_r")]
        run = g[g.rid.str.endswith("_r")]
        has_run = len(run) > 0
        for _, r in main.iterrows():
            nm = pett_name(r["candidate"])
            rr = run[run.candidate == r["candidate"]]
            unopp = int(r["type"]) == 0
            conv = int(r["type"]) == 2
            won = int(rr.iloc[0]["winner"]) if (has_run and len(rr)) else (0 if has_run else int(r["winner"]))
            rows.append(blank(year=year, chamber="H", state=st, district=int(dist), name=nm, party=party,
                              incumbent=int(r["inc"] == 1), p_party=party,
                              p_votes=None if unopp else r["candvotes"], p_pct=None if unopp else r["candpct"] * 100,
                              p_status="unopposed" if unopp else ("convention" if conv else "votes"),
                              r_votes=rr.iloc[0]["candvotes"] if len(rr) else None, r_pct=rr.iloc[0]["candpct"] * 100 if len(rr) else None,
                              p_won=won, src_p=r["src"], gender="F" if r["gender"] == 1 else ("M" if r["gender"] == 0 else ""),
                              gender_src="Pettigrew" if ok(r["gender"]) else "", qual=r["qual"], office=r["office"]))
        for _, r in run[~run.candidate.isin(main.candidate)].iterrows():  # in the runoff only (rare)
            rows.append(blank(year=year, chamber="H", state=st, district=int(dist), name=pett_name(r["candidate"]), party=party,
                              p_party=party, r_votes=r["candvotes"], r_pct=r["candpct"] * 100, p_won=int(r["winner"]),
                              src_p=r["src"], gender="F" if r["gender"] == 1 else "M", gender_src="Pettigrew"))
    return rows


# ------------------------------------------------------------------ Wikipedia (boxes) -> one row per person
def cached(kind, year, fn):
    import glob
    import hashlib
    files = sorted(glob.glob(os.path.join(RAW, "wiki", str(year), "**", "*.json"), recursive=True))
    code = "".join(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiki.py")).read())
    h = hashlib.md5((code + "".join(f"{f}:{os.path.getsize(f)}:{os.path.getmtime(f)}" for f in files)).encode()).hexdigest()
    p = os.path.join(ROOT, "cache", f"wiki_{kind}_{year}_{h[:12]}.json")
    if os.path.exists(p):
        return json.load(open(p))
    rows = fn(year)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(rows, open(p, "w"))
    return rows


def merge_people(wrows, year, chamber):
    """Wikipedia box rows of one year -> candidate rows (one per person per race)."""
    out = []
    df = pd.DataFrame(wrows)
    if df.empty:
        return out
    df = df[(df.special == 0) | (chamber == "S")]
    df = df[df.district.notna()]
    for (st, d, sp), g in df.groupby(["state", "district", "special"]):
        if st not in STATES50:
            continue
        sysm = system(st, year)
        people = []  # dicts with name, party, boxes

        def find(name, party):
            for p in people:
                if p["name"] == name:
                    return p
            for p in people:
                if (p["party"] == party or "O" in (p["party"], party)) and N.score(p["name"], name, strict=True) >= 2.5:
                    return p
            return None

        for r in g.to_dict("records"):
            if r["writein"] and not r["votes"]:
                continue
            p = find(r["name"], r["party"])
            if p is None:
                p = dict(name=r["name"], party=r["party"], inc=0, rows=[], link="")
                people.append(p)
            if r.get("link") and not p["link"]:
                p["link"] = r["link"]
            if r["party"] in ("D", "R") and p["party"] == "O":
                p["party"] = r["party"]
            p["inc"] = max(p["inc"], r["incumbent"])
            p["rows"].append(r)
        recs = []
        for p in people:
            rec = blank(year=year, chamber=chamber, state=st, district=int(d) if chamber == "H" else 0, special=int(sp),
                        name=p["name"], party=p["party"], incumbent=p["inc"], link=p["link"])
            for r in p["rows"]:
                bp = r["box_party"] or (r["party"] if r["party"] in ("D", "R") else "")
                if r["stage"] == "P" and not r["open"]:
                    if rec["p_party"] and bp and bp != rec["p_party"] and bp != p["party"]:
                        continue
                    rec.update(p_party=bp or p["party"], p_votes=r["votes"], p_pct=r["pct"], p_status="votes", src_p="Wikipedia")
                    rec["_pwon"] = r["won"]
                elif r["stage"] == "P" and r["open"]:
                    rec.update(p_party=p["party"], p_votes=r["votes"], p_pct=r["pct"], p_status="votes", src_p="Wikipedia")
                    rec["_pwon"] = r["won"]
                    rec["_open"] = 1
                elif r["stage"] == "R":
                    rec.update(r_votes=r["votes"], r_pct=r["pct"])
                    rec["_rwon"] = r["won"]
                    if not rec["p_party"]:
                        rec["p_party"] = bp or p["party"]
                elif r["stage"] == "C":
                    rec.update(p_party=rec["p_party"] or bp or p["party"], p_status=rec["p_status"] or "convention", src_p="Wikipedia")
                    rec["_cwon"] = r["won"]
                elif r["stage"] == "G":
                    rec.update(g_votes=r["votes"], g_pct=r["pct"], src_g="Wikipedia")
                    rec["_gwon"] = r["won"]
                elif r["stage"] == "GR":
                    rec.update(gr_votes=r["votes"], gr_pct=r["pct"])
                    rec["_grwon"] = r["won"]
            recs.append(rec)
        # primary winners per party
        for party in ("D", "R"):
            grp = [r for r in recs if r["p_party"] == party or (not r["p_party"] and r["party"] == party and ok(r["g_votes"]))]
            if not grp:
                continue
            if sysm in ("top2", "top4") or any(r.get("_open") for r in grp):
                for r in grp:
                    r["p_won"] = int(ok(r["g_votes"]) or bool(r.get("_pwon")))
                continue
            run = [r for r in grp if ok(r["r_votes"])]
            vot = [r for r in grp if ok(r["p_votes"])]
            conv = [r for r in grp if r.get("_cwon") is not None]
            if run:
                win = [r for r in run if r.get("_rwon")] or [max(run, key=lambda r: r["r_votes"])]
            elif vot:
                win = [r for r in vot if r.get("_pwon")]
                win = win[:1] if len(win) == 1 else [max(vot, key=lambda r: r["p_votes"])]
            elif conv:
                win = [r for r in conv if r.get("_cwon")]
            else:
                win = [r for r in grp if ok(r["g_votes"])][:1]
            for r in grp:
                r["p_won"] = int(any(r is w for w in win))
                if not r["p_party"]:
                    r["p_party"], r["p_status"] = party, "no contest"
        # general winner (the current cycle needs votes: right after election day, pages carry placeholder
        # winner marks with empty vote fields)
        if year >= 2026:
            for r in recs:
                if r.get("_gwon") and not ok(r["g_votes"]) and not ok(r["g_pct"]):
                    r["_gwon"] = 0
                if r.get("_grwon") and not ok(r["gr_votes"]):
                    r["_grwon"] = 0
        gr = [r for r in recs if ok(r["gr_votes"])]
        gg = [r for r in recs if ok(r["g_votes"]) or r.get("_gwon")]
        if gr:
            win = [r for r in gr if r.get("_grwon")] or [max(gr, key=lambda r: r["gr_votes"])]
        elif gg:
            win = [r for r in gg if r.get("_gwon")]
            if len(win) != 1:
                vv = [r for r in gg if ok(r["g_votes"])]
                win = [max(vv, key=lambda r: r["g_votes"])] if vv and (year < 2026) else win[:1]
        else:
            win = []
        for r in recs:
            if ok(r["g_votes"]) or ok(r["gr_votes"]) or r.get("_gwon") is not None:
                r["g_won"] = int(any(r is w for w in win))
            for k in [k for k in r if k.startswith("_")]:
                r.pop(k)
        out += recs
    return out


# ------------------------------------------------------------------ overview table: general results (% only)
def add_overview_generals(rows, year):
    """fill House general results from the overview table for districts without any general result (a district whose
    general box lists the candidates with no votes yet, as right after election day, takes the table's winner mark)"""
    have = {(r["state"], r["district"]) for r in rows if ok(r["g_pct"]) or ok(r["g_votes"]) or r["g_won"] == 1}
    ov = pd.DataFrame(W.overview_house(year))
    if ov.empty:
        return rows, 0
    added = 0
    for (st, d), g in ov.groupby(["state", "district"]):
        if (st, d) in have or st not in STATES50:
            continue
        for r in g.to_dict("records"):
            cand = [x for x in rows if x["state"] == st and x["district"] == d and x["chamber"] == "H"]
            i = N.best(r["name"], [x["name"] for x in cand], min_score=2.5)
            if i is not None:
                x = cand[i]
                x.update(g_pct=r["pct"], g_won=r["won"], src_g="Wikipedia overview")
                x["incumbent"] = max(x["incumbent"], r["incumbent"])
            else:
                rows.append(blank(year=year, chamber="H", state=st, district=int(d), name=r["name"], party=r["party"],
                                  incumbent=r["incumbent"], g_pct=r["pct"], g_won=r["won"], src_g="Wikipedia overview"))
            added += 1
    return rows, added


def merge_general_into_primary(prim, gen):
    """1990-2000 House: Pettigrew primary rows + Wikipedia general rows of the same race"""
    by = collections.defaultdict(list)
    for r in prim:
        by[(r["state"], r["district"])].append(r)
    out = list(prim)
    for g in gen:
        cand = by.get((g["state"], g["district"]), [])
        idx = N.best(g["name"], [c["name"] for c in cand], min_score=2.5, strict=True)
        if idx is None:
            same_party_winner = [c for c in cand if c["p_party"] == g["party"] and c["p_won"] == 1]
            same_party_gen = [x for x in gen if x["state"] == g["state"] and x["district"] == g["district"] and x["party"] == g["party"]]
            if g["party"] in ("D", "R") and len(same_party_winner) == 1 and (
                    N.score(g["name"], same_party_winner[0]["name"]) >= 2 or len(same_party_gen) == 1):
                idx = cand.index(same_party_winner[0])
                if N.score(g["name"], same_party_winner[0]["name"]) < 2:
                    same_party_winner[0]["note"] = (same_party_winner[0]["note"] + f" | general listed as {g['name']}").strip(" |")
        if idx is not None:
            c = cand[idx]
            c.update(g_votes=g["g_votes"], g_pct=g["g_pct"], g_won=g["g_won"], src_g=g["src_g"])
            c["incumbent"] = max(c["incumbent"], g["incumbent"])
        else:
            out.append(g)
    return out


# ------------------------------------------------------------------ House general results (MEDSL)
def medsl_years():
    """years whose House general results come from MEDSL: 1990-2000, and later years until the FEC workbook exists"""
    have = set(M.years())
    return [y for y in YEARS if y in have and (y <= 2000 or (y > LAST_HISTORY and not F.fec_file(y)))]


def medsl_match(p, cand, used, people, sysm):
    """index of the row in cand that is MEDSL person p, or None"""
    names_ = [p["name"]] + ([p["alt"]] if p["alt"] else [])
    m = re.match(r"^[A-Za-z]\.?\s+(\S.*)$", p["name"])  # 'W. GREGORY STEUBE' is also 'GREGORY STEUBE'
    if m and len(m.group(1).split()) >= 2:
        names_.append(m.group(1))
    sc = []
    for k, c in enumerate(cand):
        if k in used:
            continue
        s = max(N.score(n, c["name"], strict=True) for n in names_)
        if s < 2.5 and any(N.same_person(n, c["name"]) for n in names_):
            s = 2.5
        if s < 2.5:
            continue
        if c["party"] == p["party"]:
            s += 0.5
        elif "O" not in (c["party"], p["party"]):
            s -= 1
        if c.get("src_p"):  # the same person can also sit in a general-only row from Wikipedia: prefer the primary row
            s += 0.75
        sc.append((s, k))
    if sc:
        sc.sort(reverse=True)
        if len(sc) == 1 or sc[0][0] > sc[1][0]:
            return sc[0][1]
    if p["party"] in ("D", "R"):
        w = [k for k, c in enumerate(cand) if k not in used and c.get("p_party") == p["party"] and c.get("p_won") == 1 and c.get("src_p")]
        same = [q for q in people if q["party"] == p["party"]]
        if len(w) == 1:
            s = max(N.score(n, cand[w[0]]["name"]) for n in names_)
            if s >= 2 or (len(same) == 1 and sysm in ("party", "blanket")):
                if s < 2:
                    c = cand[w[0]]
                    c["note"] = (str(c["note"] or "") + f" | general listed as {p['nice']}").strip(" |")
                return w[0]
    return None


def apply_medsl(rows, year):
    """House general results of one year from MEDSL. Replaces the Wikipedia overview shares (1990-2000) and the
    Wikipedia general results (2024). Primary rows stay; each MEDSL candidate is matched to a row of the same race by
    name (else the party's only primary winner); unmatched candidates become general-only rows; general-only rows
    from Wikipedia that MEDSL does not list are dropped (other spellings, or not on the November ballot)."""
    races_ = M.races(year)
    if not races_:
        return 0
    by = collections.defaultdict(list)
    for r in rows:
        if r["year"] == year and r["chamber"] == "H" and not r.get("special"):
            by[(r["state"], int(r["district"]))].append(r)
    drop, n_races, skipped, added, kept_la = set(), 0, [], 0, []
    for (st, d), info in sorted(races_.items()):
        if st not in STATES50:
            continue
        if info["skip"]:
            skipped.append(f"{st}-{d}")
            continue
        cand = by.get((st, d), [])
        sysm = system(st, year)
        had_g = [ok(c["g_votes"]) or ok(c["g_pct"]) or ok(c.get("g_won")) for c in cand]
        if info["placeholder"] and st == "LA" and year <= 1996:
            # decided in the October open primary: MEDSL has only the winner; the overview table has the October shares
            prev = [c for c, h in zip(cand, had_g) if h and ok(c["g_pct"])]
            prev_w = [c for c in prev if c.get("g_won") == 1]
            mw = [p for p in info["people"] if p["won"]]
            if len(prev) >= 2 and len(prev_w) == 1 and mw and N.score(mw[0]["name"], prev_w[0]["name"]) >= 2:
                for c in prev:
                    c["note"] = (str(c["note"] or "") + " | general = October open primary shares (Wikipedia overview);"
                                 " no November vote").strip(" |")
                kept_la.append(f"{st}-{d}")
                continue
        wiki_votes = [c["g_votes"] if ok(c["g_votes"]) else None for c in cand]
        for c in cand:
            c.update(g_votes=None, g_pct=None, g_won=None, gr_votes=None, gr_pct=None, src_g="")
        people = [dict(p) for p in sorted(info["people"], key=lambda p: -((p["votes"] or 0) + (p["r_votes"] or 0)))]
        used = {}
        for p in people:
            i = medsl_match(p, cand, used, people, sysm)
            if i is None:
                x = blank(year=year, chamber="H", state=st, district=d, name=p["nice"], party=p["party"])
                x["race_id"] = race_id(year, "H", st, d)
                rows.append(x)
                cand.append(x)
                had_g.append(False)
                wiki_votes.append(None)
                i = len(cand) - 1
                added += 1
            used[i] = p
        for label, v in info["party_lines"]:
            # a fusion line under the party's name: give it to the candidate whose Wikipedia total is higher by exactly that
            hit = [p for i, p in used.items() if wiki_votes[i] is not None and p["votes"] is not None
                   and abs(wiki_votes[i] - p["votes"] - v) <= max(2, 0.001 * v)]
            if len(hit) == 1:
                hit[0]["votes"] += v
                hit[0]["pct"] = 100.0 * hit[0]["votes"] / info["total"] if info["total"] > 1 else None
                hit[0].setdefault("fused", []).append(label)
        for i, p in used.items():
            x = cand[i]
            notes = []
            if info["placeholder"]:
                x.update(g_votes=None, g_pct=100.0)
                notes.append("unopposed in general (no vote count printed)")
            else:
                x.update(g_votes=p["votes"], g_pct=p["pct"])
            x.update(gr_votes=p["r_votes"], gr_pct=p["r_pct"], g_won=p["won"], src_g="MEDSL")
            if x["party"] == "O" and p["party"] in ("D", "R"):
                x["party"] = p["party"]
            elif x["party"] in ("D", "R") and p["party"] == "O" and p["labels"] and not p["writein"]:
                # in that party's primary, but on the November ballot under another label (Sanders, Vermont)
                notes.append(f"general ballot label: {'/'.join(sorted(p['labels']))} (primary: {x['party']})")
                x["party"] = "O"
            if p["writein"]:
                notes.append("write-in")
            if p.get("fused"):
                notes.append("includes the " + ", ".join(p["fused"]) + " line")
            if info["kind"] == "tx1996":
                notes.append("Nov. 1996 open special election in a redrawn district (+ Dec. runoff)")
            if st == "AK" and year >= 2022:
                notes.append("first-round votes (ranked-choice count decided the winner)")
            if info["rcv_final"]:
                notes.append("final ranked-choice round (exhausted ballots left out)")
            if notes:
                x["note"] = (str(x["note"] or "") + " | " + "; ".join(notes)).strip(" |")
        for k, c in enumerate(cand):
            if k in used or not had_g[k] or c.get("src_p"):
                continue
            for j in used:  # keep what the dropped row knew about the same person
                if N.score(c["name"], cand[j]["name"]) >= 2:
                    cand[j]["incumbent"] = max(cand[j]["incumbent"] or 0, c["incumbent"] or 0)
                    cand[j]["link"] = cand[j].get("link") or c.get("link", "")
            drop.add(id(c))
        n_races += 1
    rows[:] = [r for r in rows if id(r) not in drop]
    log(f"  MEDSL {year}: {n_races} House races, {added} candidates added, {len(drop)} Wikipedia general-only rows dropped,"
        f" Wikipedia kept for {len(skipped)}{(' (' + ', '.join(skipped) + ')') if skipped else ''}"
        f"{(', October open-primary shares kept for ' + ', '.join(kept_la)) if kept_la else ''}")
    return n_races


# ------------------------------------------------------------------ CAWP and gender
# CAWP's page "Women Candidates 2026" > Candidate List > Congress and Statewide > "Export Table Data", saved by hand
# on 2026-11-05 (the page refuses automated downloads). In that export the column "Primary Date" holds the primary
# result (W, L, WD; a date when the primary is still to come) and "General Election Result" the general result
# (W, L, TCTC = too close to call, RO = runoff).
CAWP_LIST = os.path.join(STATIC, "cawp_2026_candidate_list.csv")
CAWP_LIST_YEAR, CAWP_LIST_DATE = 2026, "2026-11-05"
CAWP_LIST_SRC = f"CAWP {CAWP_LIST_YEAR} list"


def load_cawp_list():
    if not os.path.exists(CAWP_LIST):
        return None
    raw = open(CAWP_LIST, "rb").read()
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = raw.decode("latin-1")
    d = pd.read_csv(io.StringIO(txt), dtype=str, keep_default_na=False)
    d.columns = [c.strip() for c in d.columns]
    d = d.apply(lambda s: s.str.strip())
    d = d[d.Office.isin(["U.S. Rep.", "U.S. Sen."])]
    none = lambda s: s.where(s != "", None)  # noqa: E731
    return pd.DataFrame(dict(
        State=d.State, Office=d.Office.map({"U.S. Rep.": "U.S. Representative", "U.S. Sen.": "U.S. Senator"}),
        District=none(d["Dist."]), FName=d["First Name"], MName=none(d["Middle Name"]), LName=d["Last Name"], Party=d.Party,
        PrimarySeat=none(d["General Seat Status"]), GeneralSeat=none(d["General Seat Status"]),
        PrimaryWin=d["Primary Date"].where(d["Primary Date"].isin(["W", "L", "WD"]), None),
        GeneralWin=d["General Election Result"].where(~d["General Election Result"].isin(["", "NA"]), None),
        Race=None, Year=CAWP_LIST_YEAR))


def load_cawp():
    c = pd.read_excel(os.path.join(STATIC, "cawp_master.xlsx"))
    c["cawp_src"] = "CAWP"
    lst = load_cawp_list()
    if lst is not None and int(c.Year.max()) < CAWP_LIST_YEAR:  # the database itself covers the year once CAWP adds it
        lst["cawp_src"] = CAWP_LIST_SRC
        c = pd.concat([c, lst], ignore_index=True)
    c["chamber"] = c.Office.map(lambda s: "S" if "Senator" in s else "H")
    c["district"] = c.District.map(lambda v: 0 if (pd.isna(v) or str(v).strip().upper() == "AL") else int(float(v)))
    c["district"] = [0 if (ch == "H" and at_large(st, int(y))) else d for ch, st, y, d in zip(c.chamber, c.State, c.Year, c.district)]
    c["name_swapped"] = (c.LName.fillna("") + " " + c.FName.fillna("")).str.strip()
    c["name"] = (c.FName.fillna("") + " " + c.MName.fillna("") + " " + c.LName.fillna("")).str.replace(r"\s+", " ", regex=True).str.strip()
    c["name_short"] = (c.FName.fillna("") + " " + c.LName.fillna("")).str.strip()
    return c


def is_cawp(x):
    return x.get("gender_src") in ("CAWP", CAWP_LIST_SRC)


def apply_cawp(rows, cawp):
    """women = CAWP women candidates matched by race and name; other D/R candidates of the race = men"""
    idx = collections.defaultdict(list)
    for r in rows:
        idx[(r["year"], r["chamber"], r["state"], r["district"])].append(r)
    unmatched = []
    for c in cawp.to_dict("records"):
        key = (int(c["Year"]), c["chamber"], c["State"], c["district"])
        csrc = c.get("cawp_src") or "CAWP"
        cand = idx.get(key, [])
        i, best_s = None, -1
        for k, x in enumerate(cand):
            if N.same_person(c["name"], x["name"]) or N.same_person(c["name_short"], x["name"]):
                s_ = N.score(c["name"], x["name"], strict=True) + (0.5 if x["party"] == c["Party"] else 0)
                if s_ > best_s:
                    i, best_s = k, s_
        if i is None:  # first and last name swapped in the CAWP file
            for k, x in enumerate(cand):
                if N.same_person(c["name_swapped"], x["name"]):
                    i = k
                    break
        if i is None:  # wrong district in the CAWP file: same person elsewhere in the state that year
            pool = [x for kk, xs in idx.items() if kk[0] == key[0] and kk[1] == key[1] and kk[2] == key[2] and kk != key for x in xs]
            hits = [x for x in pool if N.same_person(c["name"], x["name"]) and not is_cawp(x)]
            if len(hits) == 1:
                cand = cand + hits
                i = len(cand) - 1
        if i is None:  # name changed or spelled differently: CAWP says she won, and only one candidate of her party did
            if c["PrimaryWin"] == "W":
                hits = [k for k, x in enumerate(cand) if x["party"] == c["Party"] and x.get("p_won") == 1 and not is_cawp(x)]
                if len(hits) == 1:
                    i = hits[0]
            if i is None and c["GeneralWin"] == "W":
                hits = [k for k, x in enumerate(cand) if x.get("g_won") == 1 and not is_cawp(x)]
                if len(hits) == 1:
                    i = hits[0]
            if i is not None:
                cand[i]["note"] = (str(cand[i]["note"] or "") + f" | CAWP name: {c['name']}").strip(" |")
        if i is None:  # last name only, if unique in the race and same party
            ln = N.split_name(c["LName"] + ", x")[1]
            hits = [k for k, x in enumerate(cand) if N.split_name(x["name"])[1] == ln and x["party"] == c["Party"]]
            if len(hits) == 1:
                i = hits[0]
        if i is None:  # both names spelled a little differently, same party, only one such candidate in the race
            hits = [k for k, x in enumerate(cand) if x["party"] == c["Party"] and not is_cawp(x) and N.fuzzy_same(c["name"], x["name"])]
            if len(hits) == 1:
                i = hits[0]
                cand[i]["note"] = (str(cand[i]["note"] or "") + f" | CAWP name: {c['name']}").strip(" |")
        if i is None:
            unmatched.append(dict(year=key[0], chamber=key[1], state=key[2], district=key[3], cawp_name=c["name"], party=c["Party"],
                                  primary=c["PrimaryWin"], general=c["GeneralWin"], source=csrc))
            if c["PrimaryWin"] in ("L", "WD") and c["Party"] in ("D", "R"):  # a woman who lost the primary but is missing from the vote source
                sp = 0
                rid = race_id(key[0], key[1], key[2], key[3])
                if rid in {x["race_id"] for x in rows if x["year"] == key[0] and x["state"] == key[2]}:
                    new_row = blank(year=key[0], chamber=key[1], state=key[2], district=key[3], special=sp, name=c["name"],
                                    party=c["Party"], p_party=c["Party"], p_status="lost (CAWP; no vote record)", p_won=0,
                                    gender="F", gender_src=csrc, race_eth=str(c["Race"]) if ok(c["Race"]) and str(c["Race"]) != "unavailable" else "",
                                    src_p="CAWP only", cawp_primary=c["PrimaryWin"], cawp_general=c["GeneralWin"], cawp_seat=c["PrimarySeat"])
                    new_row["race_id"] = rid
                    rows.append(new_row)
                    idx[key].append(new_row)
            continue
        x = cand[i]
        x["gender"], x["gender_src"] = "F", csrc
        if x["party"] == "O" and c["Party"] in ("D", "R"):
            x["party"] = c["Party"]
            x["note"] = (str(x["note"] or "") + " | party from CAWP").strip(" |")
        race = str(c["Race"]) if ok(c["Race"]) and str(c["Race"]) != "unavailable" else ""
        x["race_eth"] = race
        x["cawp_primary"], x["cawp_general"], x["cawp_seat"] = c["PrimaryWin"], c["GeneralWin"], c["PrimarySeat"]
    fn = first_name_table()
    cawp_max = int(cawp.Year.max())
    list_years = set(cawp[cawp.cawp_src != "CAWP"].Year.astype(int))
    women_in = collections.defaultdict(list)
    for r in rows:
        if is_cawp(r):
            women_in[r["race_id"]].append(r)
    for r in rows:
        if r["year"] <= cawp_max and not is_cawp(r) and r["party"] in ("D", "R"):
            # the same woman listed twice in a race (e.g. write-in votes in the other party's primary, Vermont)
            twin = [w for w in women_in.get(r["race_id"], []) if w is not r and N.same_person(w["name"], r["name"])]
            if twin:
                r["gender"], r["gender_src"] = "F", twin[0]["gender_src"]
                r["note"] = (str(r["note"] or "") + " | same woman as another row of this race").strip(" |")
                continue
        if r["year"] <= cawp_max and not is_cawp(r):
            if r["party"] in ("D", "R"):
                pf = fn.get(N.split_name(r["name"])[0])
                if r["gender"] == "F" and r["gender_src"] == "Pettigrew" and pf is not None and pf >= 0.95:
                    r["gender_src"] = "Pettigrew and first name (not in CAWP)"
                else:
                    r["gender"], r["gender_src"] = "M", ("not in " + CAWP_LIST_SRC) if r["year"] in list_years else "not in CAWP"
    return pd.DataFrame(unmatched)


FIRST_NAMES = os.path.join(STATIC, "first_names.csv.gz")


def first_name_table():
    """first name -> share of girls among U.S. births 1920-2005 (top-1000 names, hadley/data-baby-names)"""
    if not os.path.exists(FIRST_NAMES):
        d = pd.read_csv(os.path.join(RAW, "names/baby-names.csv"))
        d = d[(d.year >= 1920) & (d.year <= 2005)]
        t = d.groupby(["name", "sex"]).percent.sum().unstack(fill_value=0)
        t["pf"] = t.get("girl", 0) / (t.get("girl", 0) + t.get("boy", 0))
        t[["pf"]].reset_index().assign(name=lambda x: x.name.str.lower()).to_csv(FIRST_NAMES, index=False)
    d = pd.read_csv(FIRST_NAMES)
    return dict(zip(d.name, d.pf))


PRONOUNS = os.path.join(STATIC, "people_pronouns.json")


def fetch_people(titles):
    """lead sections of candidate pages (Wikipedia API, 20 titles per request); quietly does nothing offline"""
    if not titles:
        return 0
    os.makedirs(os.path.join(RAW, "wiki", "people"), exist_ok=True)
    got = 0
    for i in range(0, len(titles), 20):
        q = dict(action="query", prop="extracts", exintro=1, explaintext=1, redirects=1, titles="|".join(titles[i:i + 20]),
                 format="json", formatversion=2, maxlag=5)
        try:
            req = urllib.request.Request("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(q), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
        except Exception as e:  # noqa: BLE001
            log("  people pages not fetched:", type(e).__name__)
            return got
        with open(os.path.join(RAW, "wiki", "people", f"fetched_{dt.datetime.now():%H%M%S}_{i // 20:04d}.json"), "wb") as f:
            f.write(data)
        got += 1
    return got


def pronoun_gender():
    """candidate page lead -> 'F'/'M' when pronouns are clear (only one kind, or at least 2 and 3 to 1).
    Results are kept in data/static/people_pronouns.json so a page is read once."""
    import glob
    out = {k: tuple(v) for k, v in (json.load(open(PRONOUNS)) if os.path.exists(PRONOUNS) else {}).items()}
    for f in sorted(glob.glob(os.path.join(RAW, "wiki", "people", "*.json"))):
        q = json.load(open(f)).get("query", {})
        back = {}
        for k in ("normalized", "redirects"):
            for m in q.get(k, []):
                back.setdefault(m["to"], []).append(m["from"])
        for pg in q.get("pages", []):
            t = (pg.get("extract") or "").lower()
            fe = len(re.findall(r"\b(she|her|hers|herself)\b", t))
            ma = len(re.findall(r"\b(he|him|his|himself)\b", t))
            g = "F" if ((fe >= 2 and fe >= 3 * ma) or (fe >= 1 and ma == 0)) else \
                ("M" if ((ma >= 2 and ma >= 3 * fe) or (ma >= 1 and fe == 0)) else "")
            if not g:
                continue
            names_ = [pg["title"]] + back.get(pg["title"], [])
            for n in list(names_):
                names_ += back.get(n, [])
            for n in names_:
                out[n] = (g, pg["title"] + " " + (pg.get("extract") or "")[:300])
    with open(PRONOUNS, "w") as f:
        json.dump(dict(sorted(out.items())), f, ensure_ascii=False, indent=0)
    return out


def gender_after_cawp(rows, cawp, legis_people, pett):
    """Years after the last CAWP database year. With a CAWP candidate list for the year (2026), the list decides for
    Democrats and Republicans (apply_cawp); this only rechecks those it left out: a clear 'she' on their own page or
    an earlier CAWP record -> F, a woman's first name alone -> unknown, otherwise they stay men.
    Without a list, and for other parties: own Wikipedia page (pronouns) -> F/M; same person in an earlier CAWP year
    (same state) -> F; member of Congress or earlier Pettigrew/Miller-Camberg candidate -> their gender; first name
    (>=95% one sex); otherwise unknown."""
    cawp_max = int(cawp[cawp.cawp_src == "CAWP"].Year.max())
    women = collections.defaultdict(list)
    for c in cawp.to_dict("records"):
        women[c["State"]].append((int(c["Year"]), c["name"]))
    known = collections.defaultdict(list)
    for p in legis_people:
        g = p.get("bio", {}).get("gender")
        nm = p.get("name", {})
        full = f"{nm.get('first', '')} {nm.get('last', '')}"
        for t in p.get("terms", []):
            known[t.get("state")].append((full, g))
            if nm.get("nickname"):
                known[t.get("state")].append((f"{nm['nickname']} {nm.get('last', '')}", g))
            if nm.get("middle") and len(nm.get("first", "").strip(".")) <= 1:  # 'J. Luis Correa' goes by his middle name
                known[t.get("state")].append((f"{nm['middle']} {nm.get('last', '')}", g))
    for _, r in pett.iterrows():
        known[r["st"]].append((pett_name(r["candidate"]), "F" if r["gender"] == 1 else "M"))
    fn = first_name_table()
    pron = pronoun_gender()
    want = sorted({r["link"] for r in rows if r["year"] > cawp_max and r.get("link") and r["link"] not in pron
                   and r["party"] in ("D", "R")})
    if want and fetch_people(want):
        pron = pronoun_gender()
    def own_page(r):
        if r.get("link") and r["link"] in pron:
            g, head = pron[r["link"]]
            last = re.sub(r"[^a-z]", "", N.split_name(r["name"])[1])
            if last and last in re.sub(r"[^a-z]", "", N.fold(head)):  # the link really is this person's page
                return g
        return ""

    def earlier_cawp(r):
        return any(y < r["year"] and N.score(r["name"], w, strict=True) >= 3 for y, w in women[r["state"]])

    for r in rows:
        if r["year"] <= cawp_max:
            continue
        if r["gender_src"] == "not in " + CAWP_LIST_SRC:
            # CAWP's list is the rule, but it can miss a candidate (it is updated through the primary season): a clear
            # 'she' on the candidate's own page or an earlier CAWP record wins; a woman's first name alone leaves it open
            g = own_page(r)
            if g:
                if g == "F":
                    r["gender"], r["gender_src"] = "F", "Wikipedia page (pronouns); not in " + CAWP_LIST_SRC
                continue
            hit = {gg for n, gg in known[r["state"]] if gg and N.score(r["name"], n, strict=True) >= 3}
            if len(hit) == 1:
                if hit == {"F"}:
                    r["gender"], r["gender_src"] = "F", "member or earlier candidate; not in " + CAWP_LIST_SRC
                continue
            pf = fn.get(N.split_name(r["name"])[0])
            if earlier_cawp(r):
                r["gender"], r["gender_src"] = "F", "CAWP (earlier race); not in " + CAWP_LIST_SRC
            elif pf is not None and pf >= 0.95:
                r["gender"], r["gender_src"] = "", "not in " + CAWP_LIST_SRC + "; woman's first name"
            continue
        if r["gender"]:
            continue
        g = own_page(r)
        if g:
            r["gender"], r["gender_src"] = g, "Wikipedia page (pronouns)"
            continue
        st = r["state"]
        if earlier_cawp(r):
            r["gender"], r["gender_src"] = "F", "CAWP (earlier race)"
            continue
        hit = [g for n, g in known[st] if N.score(r["name"], n, strict=True) >= 3]
        if hit and len(set(hit)) == 1:
            r["gender"], r["gender_src"] = hit[0], "member or earlier candidate"
            continue
        f = N.split_name(r["name"])[0]
        pf = fn.get(f)
        if pf is not None and (pf >= 0.95 or pf <= 0.05):
            r["gender"], r["gender_src"] = ("F" if pf >= 0.95 else "M"), "first name"
        else:
            r["gender"], r["gender_src"] = "", "unknown"


# ------------------------------------------------------------------ members of Congress (incumbents, past women)
def load_legislators():
    out = []
    for f in ("legislators-current.yaml", "legislators-historical.yaml"):
        p = os.path.join(RAW, "legislators", f)
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            req = urllib.request.Request("https://raw.githubusercontent.com/unitedstates/congress-legislators/main/" + f,
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(p, "wb") as fh:
                fh.write(r.read())
        with open(p, encoding="utf-8") as fh:
            out += yaml.load(fh, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    return out


def house_seat_history(people):
    """(state, district) -> list of (start, end, gender, name)"""
    h = collections.defaultdict(list)
    for p in people:
        g = p.get("bio", {}).get("gender")
        nm = p.get("name", {}).get("official_full") or f"{p['name'].get('first', '')} {p['name'].get('last', '')}"
        for t in p.get("terms", []):
            if t["type"] == "rep" and t["end"] >= "1985-01-01":
                h[(t["state"], int(t.get("district", 0) or 0))].append((t["start"], t["end"], g, nm))
    return h


def senate_seat_history(people):
    h = collections.defaultdict(list)
    for p in people:
        g = p.get("bio", {}).get("gender")
        nm = p.get("name", {}).get("official_full") or f"{p['name'].get('first', '')} {p['name'].get('last', '')}"
        for t in p.get("terms", []):
            if t["type"] == "sen" and t["end"] >= "1985-01-01":
                h[t["state"]].append((t["start"], t["end"], g, nm))
    return h


# ------------------------------------------------------------------ rows by year
HISTORY = os.path.join(STATIC, "history_rows.json.gz")


def year_rows(y, pett=None):
    """House and Senate candidate rows of one year, before gender coding. Official FEC workbook when there is one,
    otherwise the sources described at the top of this file."""
    if y <= 2000:
        prim = from_pettigrew(pett, y)
        gen = [blank(year=r["year"], chamber="H", state=r["state"], district=r["district"], name=r["name"], party=r["party"],
                     incumbent=r["incumbent"], g_pct=r["pct"], g_won=r["won"], src_g="Wikipedia overview", link=r.get("link", ""))
               for r in cached("overview", y, W.overview_house) if r["state"] in STATES50]
        h, hsrc = merge_general_into_primary(prim, gen), "Pettigrew + Wikipedia overview"
    elif F.fec_file(y):
        h, hsrc = [r for r in from_fec(y) if r["chamber"] == "H"], "FEC"
    else:
        h = merge_people(cached("house", y, W.house_pages), y, "H")
        h, _ = add_overview_generals(h, y)
        hsrc = "Wikipedia"
    if y != 1996 and F.fec_file(y):
        s, ssrc = [r for r in from_fec(y) if r["chamber"] == "S"], "FEC"
    else:
        s, ssrc = merge_people(cached("senate", y, W.senate_pages), y, "S"), "Wikipedia"
    for r in h:
        r["race_id"] = race_id(y, "H", r["state"], r["district"])
    for r in s:
        r["race_id"] = race_id(y, "S", r["state"], 0, r["special"])
    log(y, "House", len(h), hsrc, "| Senate", len(s), ssrc)
    cov = [dict(year=y, chamber="H", source=hsrc, rows=len(h), races=len({r["race_id"] for r in h})),
           dict(year=y, chamber="S", source=ssrc, rows=len(s), races=len({r["race_id"] for r in s}))]
    return h + s, cov


def history_rows(rebuild=False):
    """1990-2022 rows. Read from data/static/history_rows.json.gz; rebuild re-reads the raw sources and rewrites it."""
    if not rebuild and os.path.exists(HISTORY):
        with gzip.open(HISTORY, "rt", encoding="utf-8") as f:
            d = json.load(f)
        return d["rows"], d["coverage"]
    pett = load_pettigrew(raw=True)
    rows, cov = [], []
    for y in [y for y in YEARS if y <= LAST_HISTORY]:
        r, c = year_rows(y, pett)
        rows += r
        cov += c
    log("party from FEC IDs:", fill_party_from_fec_id(rows, fec_parties()))
    with gzip.open(HISTORY, "wt", encoding="utf-8") as f:
        json.dump(dict(built=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), rows=rows, coverage=cov), f,
                  ensure_ascii=False, separators=(",", ":"), default=lambda v: None)
    return rows, cov


CAND_COLS = ["race_id", "year", "chamber", "state", "district", "special", "system", "name", "party", "gender", "gender_src",
             "race_eth", "incumbent", "p_party", "p_status", "p_votes", "p_pct", "r_votes", "r_pct", "p_won", "g_votes", "g_pct",
             "g_won", "gr_votes", "gr_pct", "qual", "office", "fec_id", "src_p", "src_g", "cawp_primary", "cawp_general",
             "cawp_seat", "link", "note"]


def build(rebuild_history=False):
    os.makedirs(OUT, exist_ok=True)
    allrows, cov = history_rows(rebuild_history)
    allrows = [dict(r) for r in allrows]
    for y in [y for y in YEARS if y > LAST_HISTORY]:
        r, c = year_rows(y)
        allrows += r
        cov += c
    for y in medsl_years():
        if apply_medsl(allrows, y):
            for c in cov:
                if c["year"] == y and c["chamber"] == "H":
                    c["source"] = ("Pettigrew (primaries) + MEDSL (general)" if y <= 2000
                                   else "Wikipedia (primaries) + MEDSL (general)")
                    c["rows"] = sum(1 for r in allrows if r["year"] == y and r["chamber"] == "H")
    one_winner(allrows)
    log("nominees without primary record:", nominated_without_primary(allrows))
    cawp = load_cawp()
    unmatched = apply_cawp(allrows, cawp)
    legis = load_legislators()
    gender_after_cawp(allrows, cawp, legis, load_pettigrew())
    for r in allrows:
        r["system"] = system(r["state"], r["year"])
    cand = pd.DataFrame(allrows)
    for c in CAND_COLS:
        if c not in cand:
            cand[c] = None
    cand = cand[CAND_COLS].sort_values(["year", "chamber", "state", "district", "special", "party", "p_votes"],
                                       ascending=[True] * 6 + [False])
    cand.to_csv(os.path.join(OUT, "candidates.csv"), index=False)
    unmatched.to_csv(os.path.join(OUT, "cawp_unmatched.csv"), index=False)
    pd.DataFrame(cov).to_csv(os.path.join(OUT, "coverage.csv"), index=False)
    log("candidates", len(cand), "| CAWP women", len(cawp), "unmatched", len(unmatched))
    return cand, legis


# ------------------------------------------------------------------ derived tables
MAP_START = [(1982, "1983-01-03"), (1992, "1993-01-03"), (2002, "2003-01-03"), (2012, "2013-01-03"), (2022, "2023-01-03")]


def map_start(year):
    s = MAP_START[0][1]
    for y, d in MAP_START:
        if year >= y:
            s = d
    return s


def district_attrs():
    out = {}
    for f in sorted(os.listdir(os.path.join(STATIC, "districts"))):
        c = int(f.split(".")[0])
        d = json.load(open(os.path.join(STATIC, "districts", f)))
        out[c] = d
    return out


def election_day(y):
    import datetime as dt
    d = dt.date(y, 11, 2)
    while d.weekday() != 1:
        d += dt.timedelta(days=1)
    return d.isoformat()


def one_winner(rows):
    """keep a single general winner per race (overview tables sometimes mark special-election winners too);
    where no winner is marked: highest general share (before 2026), or the open-primary winner in Louisiana-style
    races decided in the first round"""
    races = collections.defaultdict(list)
    for r in rows:
        races[r["race_id"]].append(r)
    for rid, rs in races.items():
        if rs[0]["year"] >= 2026 or rid == "2018-H-NC-09":  # 2026 still counting; NC-9 2018 was never certified
            continue
        if any(r.get("g_won") == 1 for r in rs):
            continue
        gp = [r for r in rs if ok(r["gr_pct"]) or ok(r["gr_votes"]) or ok(r["g_pct"]) or ok(r["g_votes"])]
        if gp:
            top = max(gp, key=lambda r: (r["gr_votes"] or 0, r["gr_pct"] or 0, r["g_votes"] or 0, r["g_pct"] or 0))
            top["g_won"] = 1
            top["note"] = (str(top["note"] or "") + " | winner = highest general share (no mark in source)").strip(" |")
        elif system(rs[0]["state"], rs[0]["year"]) == "jungle":
            pw = [r for r in rs if r.get("p_won") == 1]
            if len(pw) == 1:
                pw[0]["g_won"] = 1
                pw[0]["note"] = (str(pw[0]["note"] or "") + " | elected in the open primary").strip(" |")
    by = collections.defaultdict(list)
    for r in rows:
        if r.get("g_won") == 1:
            by[r["race_id"]].append(r)
    for rid, ws in by.items():
        if len(ws) > 1:
            top = max(ws, key=lambda r: (r["gr_votes"] or 0, r["g_votes"] or 0, r["g_pct"] or 0))
            for r in ws:
                if r is not top:
                    r["g_won"] = 0
                    r["note"] = (r["note"] + " | second winner mark dropped").strip(" |")


def derive(cand, legis):
    hist_h = house_seat_history(legis)
    hist_s = senate_seat_history(legis)
    dattr = district_attrs()
    pett = load_pettigrew()
    prez = {}
    for _, r in pett.iterrows():
        if ok(r["prez"]) and r["prez"] > 0:
            prez[(int(r["year"]), r["st"], int(r["dist"]))] = r["prez"] if r["pparty"] == "D" else 100 - r["prez"]
    prim_rows, race_rows = [], []
    for rid, g in cand.groupby("race_id", sort=False):
        g = g.copy()
        y, ch, st, d, sp, sysm = int(g.year.iloc[0]), g.chamber.iloc[0], g.state.iloc[0], int(g.district.iloc[0]), int(g.special.iloc[0]), g.system.iloc[0]
        base = dict(race_id=rid, year=y, chamber=ch, state=st, district=d, special=sp, system=sysm)
        out_p = {}
        for party in ("D", "R"):
            pg = g[(g.p_party == party) | ((g.p_party.isna() | (g.p_party == "")) & (g.party == party) & g.g_won.notna())]
            pg = pg[pg.party.isin([party]) | (pg.p_party == party)]
            if pg.empty:
                out_p[party] = None
                continue
            nw, nm = int((pg.gender == "F").sum()), int((pg.gender == "M").sum())
            voted = pg.p_votes.notna().sum()
            ctype = "runoff" if pg.r_votes.notna().any() else ("contested" if voted >= 2 else
                    ("convention" if (pg.p_status == "convention").any() else "uncontested"))
            if sysm in ("top2", "top4", "jungle"):
                ctype = sysm
            win = pg[pg.p_won == 1]
            w = win.iloc[0] if len(win) else None
            top_w = pg[pg.gender == "F"].p_pct.max() if nw else None
            top_m = pg[pg.gender == "M"].p_pct.max() if nm else None
            row = dict(base, party=party, contest=ctype, n_cand=len(pg), n_women=nw, n_men=nm, n_unknown=len(pg) - nw - nm,
                       incumbent_running=int((pg.incumbent == 1).any()), incumbent_gender=(pg[pg.incumbent == 1].gender.iloc[0] if (pg.incumbent == 1).any() else ""),
                       winner=w["name"] if w is not None else "", winner_gender=w["gender"] if w is not None else "",
                       winner_pct=w["r_pct"] if (w is not None and ok(w["r_pct"])) else (w["p_pct"] if w is not None else None),
                       woman_won=(int(w["gender"] == "F") if w is not None and w["gender"] in ("F", "M") else None),
                       top_woman_pct=top_w, top_man_pct=top_m, mixed=int(nw > 0 and nm > 0), src=";".join(sorted(set(pg.src_p.dropna()) - {""})))
            prim_rows.append(row)
            out_p[party] = row
        # nominees (on the general ballot) and winner
        gen = g[g.g_votes.notna() | g.g_pct.notna() | g.g_won.notna()]
        def nominee(party):
            x = gen[gen.party == party]
            if x.empty:
                return None
            key = x.g_votes.fillna(-1) if x.g_votes.notna().any() else x.g_pct.fillna(-1)
            return x.loc[key.idxmax()]
        dn, rn = nominee("D"), nominee("R")
        win = gen[gen.g_won == 1]
        wr = win.iloc[0] if len(win) else None
        if wr is None and y < 2026 and rid != "2018-H-NC-09":  # no result anywhere: the member who took the seat in January
            hist0 = hist_h.get((st, d), []) if ch == "H" else hist_s.get(st, [])
            took = [h for h in hist0 if f"{y + 1}-01-01" <= h[0] <= f"{y + 1}-01-31"]
            if len(took) == 1 or (ch == "S" and took):
                wr = dict(name=took[0][3], party="", gender=took[0][2] or "")
        def share(a, b):
            if a is None or b is None:
                return None
            va, vb = (a["g_votes"], b["g_votes"]) if ok(a["g_votes"]) and ok(b["g_votes"]) else (a["g_pct"], b["g_pct"])
            return 100 * va / (va + vb) if ok(va) and ok(vb) and (va + vb) > 0 else None
        # members holding the seat on election day and earlier in the same map
        eday = election_day(y)
        hist = hist_h.get((st, d), []) if ch == "H" else hist_s.get(st, [])
        if ch == "H" and d == 0:
            hist = hist + hist_h.get((st, 1), []) if st in ("MT",) else hist
        on_day = [h for h in hist if h[0] <= eday <= h[1]]
        ms = map_start(y) if ch == "H" else "1985-01-03"
        before = [h for h in hist if h[1] > ms and h[0] < eday]
        inc_g = g[g.incumbent == 1]
        attrs = (dattr.get((y - 1788) // 2 + 1) or {}).get("cd" if ch == "H" else "state", {})  # districts/{c}.json = Congress elected in y
        a = attrs.get(f"{st}-{d}" if ch == "H" else st, {}) if attrs else {}
        race_rows.append(dict(base,
            n_general=len(gen),
            incumbent_running=int(len(inc_g) > 0), incumbent_party=inc_g.party.iloc[0] if len(inc_g) else "",
            incumbent_gender=inc_g.gender.iloc[0] if len(inc_g) else "", open_seat=int(len(inc_g) == 0),
            seat_member_on_eday=";".join(h[3] for h in on_day), seat_member_female=int(any(h[2] == "F" for h in on_day)) if on_day else None,
            women_members_same_map=sum(1 for h in {(h[3], h[2]) for h in before} if h[1] == "F"),
            d_primary_women=out_p["D"]["n_women"] if out_p.get("D") else None, r_primary_women=out_p["R"]["n_women"] if out_p.get("R") else None,
            d_primary_woman_won=out_p["D"]["woman_won"] if out_p.get("D") else None, r_primary_woman_won=out_p["R"]["woman_won"] if out_p.get("R") else None,
            d_nominee=dn["name"] if dn is not None else "", d_nominee_gender=dn["gender"] if dn is not None else "",
            r_nominee=rn["name"] if rn is not None else "", r_nominee_gender=rn["gender"] if rn is not None else "",
            matchup=(f"{dn['gender'] or '?'}-{rn['gender'] or '?'}" if dn is not None and rn is not None else ("D only" if dn is not None else ("R only" if rn is not None else ""))),
            winner=wr["name"] if wr is not None else "", winner_party=wr["party"] if wr is not None else "", winner_gender=wr["gender"] if wr is not None else "",
            woman_won_general=(int(wr["gender"] == "F") if wr is not None and wr["gender"] in ("F", "M") else None),
            d_share_2party=share(dn, rn),
            pres_d_2party=prez.get((y, st, d)) if ch == "H" else None,
            pvi=a.get("pvi"), rural=a.get("rural"), white_nh=a.get("white_nh"), black_nh=a.get("black_nh"), hisp=a.get("hisp"),
            asian_nh=a.get("asian_nh"), ba_plus=a.get("ba_plus"), med_income=a.get("med_income"),
            src_general=";".join(sorted(set(gen.src_g.dropna()) - {""}))))
    prim = pd.DataFrame(prim_rows)
    races = pd.DataFrame(race_rows)
    # linked districts back to the 1990 election (2/3 of residents, or the same member) and the women who held them
    import linked
    counts, long_rows, wide = linked.compute(races, cand, legis, election_day, at_large)
    races["women_members_since_1990"] = races.race_id.map(counts)
    linked.write(long_rows, wide)
    log("linked districts:", len(counts), "House races,", sum(1 for r in long_rows if r["rule"]), "links of", len(long_rows))
    prim.to_csv(os.path.join(OUT, "primaries.csv"), index=False)
    races.to_csv(os.path.join(OUT, "races.csv"), index=False)
    log("primaries", len(prim), "races", len(races))
    return prim, races


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-history", action="store_true", help="re-read all raw sources for 1990-2022")
    a = ap.parse_args()
    cand, legis = build(a.rebuild_history)
    derive(cand, legis)
    import site_data
    lst = load_cawp_list()
    used = lst is not None and int(pd.read_excel(os.path.join(STATIC, "cawp_master.xlsx"), usecols=["Year"]).Year.max()) < CAWP_LIST_YEAR
    site_data.write(dict(cawp_list=dict(year=CAWP_LIST_YEAR, downloaded=CAWP_LIST_DATE, women=len(lst)) if used else None))
