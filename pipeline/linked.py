"""Linked House districts back to the 1990 election, and the women who held them ("since 1990" count on the page).

For a House race in year Y (district d), the linked district in an earlier Congress k (101st, in office at the 1990
election, up to the Congress in office at Y's election) is:
  1. the district of Congress k where at least 2/3 of d's residents lived (2020 census block groups, from
     data/static/lineage_overlap.csv.gz, pipeline/lineage.py); at most one district can hold 2/3, so this is unique
  2. if no district holds 2/3: the district that a member of Congress k represented, when that member ran in this race
     (primary or general); with several such members, the one whose district holds more of d's residents
  3. otherwise none for that Congress.
women_members_since_1990 = number of different women (one person counts once however often elected) who represented the
linked districts in those Congresses before Y's election day, the member in office included.

Output: the race column above, plus the district alignment lists for download (docs/data/lineage/):
  lineage_2026.csv/.dta  one row per 2026 district, the linked district of every earlier election (wide)
  lineage_all.csv/.dta   one row per House race (1990-2026) x earlier Congress (long)
"""
import collections
import gzip
import csv
import os

import pandas as pd

import names as N

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERLAP = os.path.join(ROOT, "data", "static", "lineage_overlap.csv.gz")
OUT = os.path.join(ROOT, "docs", "data", "lineage")
FIRST_C = 101
THRESH = 200 / 3
RULE = {"pop": "인구 2/3", "member": "같은 의원"}


def congress_of(year):
    return (year - 1788) // 2 + 1


def election_year_of(k):
    return 1788 + 2 * (k - 1)


def congress_start(k):
    return f"{1789 + 2 * (k - 1)}-01-03"


def load_overlap():
    """(year, state, district) -> {congress: [(prior district, share)] largest first}"""
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    if not os.path.exists(OVERLAP):
        return {}
    with gzip.open(OVERLAP, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[(int(r["year"]), r["state"], int(r["district"]))][int(r["congress"])].append((int(r["prior_district"]), float(r["share"])))
    for v in out.values():
        for lst in v.values():
            lst.sort(key=lambda x: -x[1])
    return out


def member_terms(legis, at_large):
    """(state, congress) -> [member dicts with district, start, end] for House terms from the 101st Congress on.
    At-large seats are district 0 (the member list sometimes codes them 1, as Montana 1993-1997)"""
    by = collections.defaultdict(list)
    for p in legis:
        ids = p.get("id", {})
        nm = p.get("name", {})
        full = nm.get("official_full") or f"{nm.get('first', '')} {nm.get('last', '')}"
        variants = {full, f"{nm.get('first', '')} {nm.get('last', '')}"}
        if nm.get("nickname"):
            variants.add(f"{nm['nickname']} {nm.get('last', '')}")
        person = dict(bioguide=ids.get("bioguide") or full, name=full, gender=p.get("bio", {}).get("gender"),
                      fec=set(ids.get("fec", []) or []), wiki=(ids.get("wikipedia") or "").replace("_", " ").strip().lower(),
                      variants=[v.strip() for v in variants if v.strip()], last=last_tokens(nm.get("last", "")) or last_tokens(full))
        for t in p.get("terms", []):
            if t["type"] != "rep" or t["end"] <= congress_start(FIRST_C):
                continue
            for k in range(FIRST_C, congress_of(int(t["end"][:4])) + 2):
                if t["start"] < congress_start(k + 1) and t["end"] > congress_start(k):
                    dist = 0 if at_large(t["state"], election_year_of(k)) else int(t.get("district", 0) or 0)
                    by[(t["state"], k)].append(dict(person, district=dist, start=t["start"], end=t["end"]))
    return by


def last_tokens(s):
    return {t.strip(",'-") for t in N.tokens(s) if len(t.strip(",'-")) > 1}


_RAN = {}


def ran_here(member, rid, cands):
    """did this member run in the race (FEC number, Wikipedia page, or the same name)?"""
    key = (member["bioguide"], rid)
    if key in _RAN:
        return _RAN[key]
    hit = False
    for c in cands:
        if (c["fec_id"] and c["fec_id"] in member["fec"]) or (c["link"] and member["wiki"] and c["link"] == member["wiki"]):
            hit = True
        elif member["last"] & c["tokens"] and any(N.same_person(v, c["name"]) for v in member["variants"]):
            hit = True
        if hit:
            break
    _RAN[key] = hit
    return hit


def compute(races, cand, legis, election_day, at_large):
    """returns ({race_id: count}, long rows, wide rows)"""
    ov = load_overlap()
    if not ov:
        return {}, [], []
    terms = member_terms(legis, at_large)
    cby = collections.defaultdict(list)
    for r in cand[(cand.chamber == "H")][["race_id", "name", "fec_id", "link"]].itertuples(index=False):
        link = str(r.link).replace("https://en.wikipedia.org/wiki/", "").replace("_", " ").strip().lower() if isinstance(r.link, str) else ""
        cby[r.race_id].append(dict(name=str(r.name), fec_id=r.fec_id if isinstance(r.fec_id, str) else "", link=link,
                                   tokens=last_tokens(str(r.name))))
    counts, long_rows, wide = {}, [], []
    h = races[(races.chamber == "H") & (races.special == 0)]
    for r in h.itertuples(index=False):
        y, st, d, rid = int(r.year), r.state, int(r.district), r.race_id
        info = ov.get((y, st, d))
        if info is None:
            continue
        cb, eday = congress_of(y), election_day(y)
        women, wrow = {}, dict(race_id=rid, year=y, state=st, district=d)
        for k in range(FIRST_C, cb):
            lst = info.get(k, [])
            share_of = dict(lst)
            best_d, best_s = (lst[0] if lst else (None, None))
            link, rule = None, ""
            if lst and best_s >= THRESH:
                link, rule = best_d, "pop"
            else:
                movers = {m["district"] for m in terms.get((st, k), []) if ran_here(m, rid, cby.get(rid, []))}
                if movers:
                    link, rule = max(movers, key=lambda x: (share_of.get(x, 0), -x)), "member"
            held = []
            if link is not None:
                held = [m for m in terms.get((st, k), []) if m["district"] == link and m["start"] < eday]
                for m in held:
                    if m["gender"] == "F":
                        women.setdefault(m["bioguide"], m["name"])
            py = election_year_of(k)
            long_rows.append(dict(
                race_id=rid, year=y, state=st, district=d, prior_year=py, congress=k,
                prior_district=link, prior_race_id=f"{py}-H-{st}-{link:02d}" if link is not None else "",
                share=share_of.get(link) if link is not None else None, rule=RULE.get(rule, ""),
                best_district=best_d, best_share=best_s,
                members=";".join(dict.fromkeys(m["name"] for m in held)),
                women=";".join(dict.fromkeys(m["name"] for m in held if m["gender"] == "F")),
                women_cum=len(women)))
            wrow[f"d{py}"] = link
            wrow[f"s{py}"] = share_of.get(link) if link is not None else None
            wrow[f"r{py}"] = RULE.get(rule, "")
        counts[rid] = len(women)
        if y == 2026:
            wrow["n_linked"] = sum(1 for k in range(FIRST_C, cb) if wrow.get(f"d{election_year_of(k)}") is not None)
            wrow["women_since_1990"] = len(women)
            wrow["women_names"] = ";".join(women.values())
            wide.append(wrow)
    return counts, long_rows, wide


LONG_LABELS = dict(
    race_id="선거 번호(연도-원-주-선거구)", year="선거 연도", state="주", district="선거구(0 = 주 전체 한 석)",
    prior_year="예전 선거 연도(그 의회를 뽑은 선거)", congress="예전 의회 대수", prior_district="이어지는 예전 선거구(비면 없음)",
    prior_race_id="이어지는 예전 선거 번호", share="이 선거구 주민 중 이어지는 선거구에 살던 비율(%, 2020년 인구)",
    rule="이은 방법(인구 2/3 또는 같은 의원)", best_district="주민이 가장 많이 겹친 예전 선거구", best_share="그 겹친 비율(%)",
    members="그 의회에서 이어지는 선거구를 맡은 의원", women="그중 여성 의원", women_cum="1990년 선거 때부터 여기까지 서로 다른 여성 의원 수")


def write(long_rows, wide):
    if not long_rows:
        return
    os.makedirs(OUT, exist_ok=True)
    lg = ints(pd.DataFrame(long_rows).sort_values(["year", "state", "district", "congress"]))
    lg.to_csv(os.path.join(OUT, "lineage_all.csv"), index=False, encoding="utf-8-sig")
    stata(lg, os.path.join(OUT, "lineage_all.dta"), LONG_LABELS, "선거구 이어 보기: 모든 하원 선거 x 예전 의회(1990-2026)",
          strl=("members", "women"))
    wd = ints(pd.DataFrame(wide).sort_values(["state", "district"]))
    years = sorted({int(c[1:]) for c in wd.columns if c[:1] == "d" and c[1:].isdigit()}, reverse=True)
    cols = ["race_id", "year", "state", "district", "n_linked", "women_since_1990", "women_names"]
    labels = dict(race_id="2026년 선거 번호", year="선거 연도", state="주", district="2026년 선거구(0 = 주 전체 한 석)",
                  n_linked="이어지는 선거구가 있는 예전 의회 수(101~119대, 최대 19)",
                  women_since_1990="이어지는 선거구의 서로 다른 여성 의원 수(1990년 선거 때부터)", women_names="그 여성 의원")
    for py in years:
        cols += [f"d{py}", f"s{py}", f"r{py}"]
        labels[f"d{py}"] = f"{py}년 선거의 이어지는 선거구(비면 없음)"
        labels[f"s{py}"] = f"{py}년: 2026년 선거구 주민 중 그 선거구에 살던 비율(%)"
        labels[f"r{py}"] = f"{py}년: 이은 방법"
    wd = wd[cols]
    wd.to_csv(os.path.join(OUT, "lineage_2026.csv"), index=False, encoding="utf-8-sig")
    stata(wd, os.path.join(OUT, "lineage_2026.dta"), labels, "선거구 이어 보기: 2026년 하원 선거구 기준")


INT_COLS = ("year", "district", "prior_year", "congress", "prior_district", "best_district", "women_cum", "women_since_1990", "n_linked")


def ints(df):
    """whole-number columns as nullable integers (CSV shows 11, not 11.0)"""
    for c in df.columns:
        if c in INT_COLS or (c[:1] == "d" and c[1:].isdigit()):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df


def stata(df, path, labels, title, strl=()):
    """Stata 14+ file with Korean variable labels; long name lists as strL (smaller file)"""
    df = df.copy()
    for c in df.columns:
        if str(df[c].dtype) == "Int64":
            df[c] = df[c].astype("float64")
            if df[c].isna().sum() == 0:
                df[c] = df[c].astype("int32")
        elif not pd.api.types.is_numeric_dtype(df[c]):  # object or the string dtype of pandas 3
            df[c] = df[c].astype(object).where(df[c].notna(), "").astype(str)
    df.to_stata(path, write_index=False, version=118, variable_labels={k: v[:80] for k, v in labels.items() if k in df.columns},
                data_label=title[:80], convert_strl=[c for c in strl if c in df.columns])
