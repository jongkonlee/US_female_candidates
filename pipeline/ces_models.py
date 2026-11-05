"""Individual-level models from the Cooperative Election Study: did women and men voters choose the woman candidate
differently where the district had earlier women (members, or members and general-election candidates)?

Runs in GitHub Actions (workflow 'CES individual models'), because the workspace cannot reach Dataverse. Data:
Shiro Kuriwaki, "Cumulative CES Common Content", Harvard Dataverse, doi:10.7910/DVN/II2DB6 (CC0), the Stata file (its
value labels give the codes), joined to the tracker's races (data/races.csv) and candidates (data/candidates.csv).

Sample: House general elections 2008-2024 (district traits exist from 2008) with one Democratic and one Republican
nominee; respondents who reported voting for one of the two (voted_rep_party), in the district on the ballot after the
election (dist_up_post, else dist_up). The models use the races where exactly one nominee is a woman; races of two women
(ff = 1) or two men (mm = 1) stay in the analysis file, with vote_d and each party's nominee's race, for other uses.
Outcome: vote_woman = 1 voted for the woman, 0 for the man.
Models, separately for races with a Democratic woman and with a Republican woman, for four 'earlier women' measures
(women_members_since_1990 > 0, women_members_since_1990_excl > 0, women_prior_since_1990 > 0,
women_prior_since_1990_excl > 0):
  vote_woman ~ female + prior + female x prior + copart + outpart
               + same_race_w + same_race_m + m_race_unk + w_nonwhite + m_nonwhite
               + respondent race (white = base) + college + age/10 + ideology (moderate = base)
               + pvi + rural + black_nh + hisp + asian_nh + ba_plus + income/10,000 + woman incumbent + man incumbent
               + year fixed effects
  estimated as a linear probability model (weighted least squares) and a logit (weighted pseudo-likelihood), with the
  survey weight (weight_post, else weight) and standard errors clustered by race, small-sample factors as in Stata
  (regress: G/(G-1)*(N-1)/(N-K); logit: G/(G-1)); p values from t(G-1) for the linear model, normal for the logit.
Candidate race, in this order: (1) a woman's CAWP code (race_eth); (2) data/static/nominee_race.csv: published codes
from a file of candidate race codes the user supplied (src 'file'; each row names its original source, e.g. Hassell &
Visalvanich, Grumbach & Sahn, Fraga & Rendleman / FiveThirtyEight, Daily Kos Elections, CAWP, U.S. House Historian),
web research with a cited source (src 'research'), the Reflective Democracy Campaign's classification that the user's file
keeps apart (src 'rdc'), and Hispanic (estimated) from the first name and surname where both point there (src 'surname':
probability >= 0.9 from the Census 2010 surname table and the Tzioumis 2018 first-name table; user's decision
2026-11-06); (3) Wikipedia's lists of minority members of Congress
(data/static/member_race.csv, pipeline/fetch_member_race.py) for anyone who served in Congress (matched within the state
by FEC number, Wikipedia page or name); (4) white when he or she served but is on none of the lists (an inference);
(5) unknown (then the match and non-white variables are 0 and the *_race_unk flag is 1).
Adjusted predictions: the weighted mean prediction with every respondent set to female/male and prior yes/no (other
variables as observed), their differences and the difference in differences, standard errors by the delta method.

Outputs:
  docs/data/ces/ces_models.csv        every coefficient of every model
  docs/data/ces/ces_models_pred.csv   adjusted predictions and differences
  docs/data/ces/ces_models.json       the same for the page
  docs/data/ces/ces_individual.zip    the analysis file ces_individual.dta, zipped (one row per respondent; CES is CC0)
  data/static/ces/models_meta.json    labels and codes found, sample sizes
"""
import collections
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.parse

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_ces as F  # noqa: E402  (download helpers and state names)
import fetch_member_race as MR  # noqa: E402  (congress-legislators)
import names as N  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "ces")
META = os.path.join(ROOT, "data", "static", "ces", "models_meta.json")
YEARS = list(range(2008, 2025, 2))
PRIORS = {
    "women_members_since_1990": "기존 여성 의원(본인 포함)",
    "women_members_since_1990_excl": "기존 여성 의원(본인 제외)",
    "women_prior_since_1990": "기존 여성 의원·후보(본인 포함)",
    "women_prior_since_1990_excl": "기존 여성 의원·후보(본인 제외)",
}
TERMS = [
    ("female", "여성 유권자"), ("prior", "기존 여성 있음"), ("female_x_prior", "여성 유권자 × 기존 여성 있음"),
    ("copart", "여성 후보와 같은 정당 지지(기우는 무당파 포함)"), ("outpart", "여성 후보와 반대 정당 지지"),
    ("same_race_w", "여성 후보와 같은 인종"), ("same_race_m", "남성 후보와 같은 인종"), ("m_race_unk", "남성 후보 인종 모름"),
    ("w_nonwhite", "여성 후보가 백인 아님"), ("m_nonwhite", "남성 후보가 백인 아님"),
    ("r_black", "응답자 흑인(기준: 백인)"), ("r_hisp", "응답자 히스패닉"), ("r_asian", "응답자 아시아계"), ("r_other", "응답자 그 밖 인종"),
    ("college", "4년제 대졸 이상"), ("age10", "나이(10세)"),
    ("lib", "진보(기준: 중도)"), ("con", "보수"), ("ideo_ns", "이념 모름"),
    ("pvi", "당파 지수(+민주)"), ("rural", "농촌 인구 비율(%)"), ("black_nh", "선거구 흑인 비율(%)"), ("hisp_d", "선거구 히스패닉 비율(%)"),
    ("asian_nh", "선거구 아시아계 비율(%)"), ("ba_plus", "선거구 대졸 비율(%)"), ("inc10k", "선거구 가구 소득 중앙값(만 달러)"),
    ("w_inc", "여성 후보가 현직"), ("m_inc", "남성 후보가 현직"),
] + [(f"y{y}", f"{y}년(기준: 2008년)") for y in YEARS[1:]] + [("const", "상수")]
LABEL = dict(TERMS)


def log(*a):
    print(*a, flush=True)


# ---------- CES respondents ----------
def download():
    q = urllib.parse.quote(F.DOI, safe="")
    meta = json.loads(F.get(f"{F.API}/datasets/:persistentId/?persistentId={q}"))["data"]
    ver = meta["latestVersion"]
    files = [dict(id=f["dataFile"]["id"], name=f["dataFile"].get("filename") or f.get("label"), size=f["dataFile"].get("filesize"))
             for f in ver["files"]]
    dta = [f for f in files if f["name"].lower().endswith(".dta") and "cumulative" in f["name"].lower()]
    if not dta:
        raise SystemExit("no Stata file: " + ", ".join(f["name"] for f in files))
    f = max(dta, key=lambda x: x["size"] or 0)
    path = os.path.join(F.TMP, f["name"])
    if not os.path.exists(path):
        log("downloading", f["name"], f["size"])
        F.get(f"{F.API}/access/datafile/{f['id']}", path)
    return path, dict(version=f"{ver.get('versionNumber')}.{ver.get('versionMinorNumber')}", release=ver.get("releaseTime"), file=f["name"])


COLS = ["year", "case_id", "weight_post", "weight", "st_post", "st", "dist_up_post", "dist_up", "gender", "voted_rep_party",
        "pid7", "ideo5", "race_h", "race", "hispanic", "educ", "age", "birthyr"]


def read_ces(path):
    """the columns used, with value labels turned into their text (codes without a label kept as numbers)"""
    with pd.read_stata(path, iterator=True) as rd:
        have = list(rd.variable_labels())
        vl = rd.value_labels()
        try:
            lab_of = dict(zip(rd._varlist, rd._lbllist))  # variable -> its value label set
        except AttributeError:
            lab_of = {}
    cols = [c for c in COLS if c in have]
    log("columns used:", cols)
    parts = []
    with pd.read_stata(path, columns=cols, iterator=True, chunksize=200_000, convert_categoricals=False) as it:
        for ch in it:
            parts.append(ch[pd.to_numeric(ch["year"], errors="coerce").isin(YEARS)])
    df = pd.concat(parts, ignore_index=True)
    used = {}
    for c in cols:
        lab = vl.get(lab_of.get(c) or c)
        if lab and c not in ("year", "case_id", "weight_post", "weight", "dist_up_post", "dist_up", "age", "birthyr"):
            used[c] = {str(k): str(v) for k, v in lab.items()}
            df[c] = df[c].map(lambda v, lab=lab: None if pd.isna(v) else lab.get(v, lab.get(int(v), v) if float(v).is_integer() else v))
    return df, used


def text(v):
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip().lower()


def pid_side(v):
    """Democrat side (strong, not very strong, lean), Republican side, or independent / not sure"""
    s = text(v)
    if "democrat" in s:
        return "D"
    if "republican" in s:
        return "R"
    return "I" if s else None


def ideo(v):
    s = text(v)
    if "liberal" in s:
        return "L"
    if "conservative" in s:
        return "C"
    if "moderate" in s or "middle" in s:
        return "M"
    return "NS" if s else None


def race_code(v):
    """respondent race (race_h: Hispanic origin counted as Hispanic) in CAWP's codes"""
    s = text(v)
    for key, code in (("white", "W"), ("black", "B"), ("hispanic", "H"), ("latin", "H"), ("asian", "AP"), ("native", "NA"),
                      ("middle eastern", "MENA"), ("mixed", "MU"), ("two or more", "MU")):
        if key in s:
            return code
    return "OTHER" if s else None


def college(v):
    s = text(v)
    if not s:
        return None
    return int("4-year" in s or "4 year" in s or "post" in s or ("graduate" in s and "high school" not in s))


def respondents(df, meta):
    out = pd.DataFrame(index=df.index)
    out["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    out["case_id"] = df["case_id"].astype(str) if "case_id" in df else ""
    st = df["st_post"] if "st_post" in df else df["st"]
    st = st.astype(object).where(st.notna(), None)
    if "st" in df:
        st = st.where(st.notna(), df["st"])
    out["state"] = st.map(lambda x: F.STATES.get(str(x).strip(), str(x).strip() if len(str(x).strip()) == 2 else None) if x is not None else None)
    dist = pd.to_numeric(df.get("dist_up_post"), errors="coerce") if "dist_up_post" in df else pd.Series(np.nan, index=df.index)
    if "dist_up" in df:
        dist = dist.fillna(pd.to_numeric(df["dist_up"], errors="coerce"))
    out["district"] = dist
    out["female"] = df["gender"].map(lambda v: F.norm_gender(v))
    out["vote"] = df["voted_rep_party"].map(F.norm_party)
    w = pd.to_numeric(df["weight_post"], errors="coerce") if "weight_post" in df else pd.Series(np.nan, index=df.index)
    out["weight"] = w.fillna(pd.to_numeric(df["weight"], errors="coerce"))
    out["pid"] = df["pid7"].map(pid_side) if "pid7" in df else None
    out["ideo"] = df["ideo5"].map(ideo) if "ideo5" in df else None
    rc = df["race_h"] if "race_h" in df else df["race"]
    out["rrace"] = rc.map(race_code)
    out["college"] = df["educ"].map(college) if "educ" in df else None
    age = pd.to_numeric(df.get("age"), errors="coerce") if "age" in df else pd.Series(np.nan, index=df.index)
    if "birthyr" in df:
        age = age.fillna(out["year"] - pd.to_numeric(df["birthyr"], errors="coerce"))
    out["age"] = age.where((age >= 17) & (age <= 105))
    # what the labels looked like, for checking the codes
    meta["labels"] = {c: {str(k): int(v) for k, v in df[c].astype(str).value_counts().head(30).items()}
                      for c in ("gender", "voted_rep_party", "pid7", "ideo5", "race_h", "race", "educ") if c in df}
    meta["coded"] = {c: {str(k): int(v) for k, v in out[c].astype(str).value_counts().items()} for c in ("female", "vote", "pid", "ideo", "rrace", "college")}
    out = out.dropna(subset=["state", "district", "female", "vote", "weight"])
    out = out[out.state.str.len() == 2].copy()
    out["district"] = out.district.astype(int)
    ones = out.groupby(["year", "state"]).district.transform("max") == 1  # at large: the tracker uses 0
    out.loc[ones, "district"] = 0
    out["female"] = (out.female == "F").astype(int)
    out["race_id"] = out.year.astype(str) + "-H-" + out.state + "-" + out.district.map("{:02d}".format)
    return out


# ---------- races ----------
MATCHUPS = ["F-M", "M-F", "F-F", "M-M"]  # one Democratic and one Republican nominee of known gender


def races():
    """House races 2008-2024 with a Democratic and a Republican nominee: woman vs man (the models) and both women (ff)
    or both men (mm, kept in the analysis file with their flags). Each nominee's race: CAWP's code for women; otherwise,
    for anyone who served in Congress, the minority lists (white when on none of them); otherwise unknown"""
    r, c = tracker()
    h = with_nominees(r[(r.chamber == "H") & (r.special == 0) & r.matchup.isin(MATCHUPS) & r.year.isin(YEARS)].copy(), c[c.chamber == "H"])
    h["ff"] = (h.matchup == "F-F").astype(int)
    h["mm"] = (h.matchup == "M-M").astype(int)
    h["mixed"] = h.matchup.isin(["F-M", "M-F"]).astype(int)
    h["wparty"] = h.matchup.map({"F-M": "D", "M-F": "R"})
    # the woman and the man of a woman-vs-man race
    isd = h.wparty == "D"
    for k in ("race", "race_src", "inc"):
        h[f"w_{k}"] = h[f"d_{k}"].where(isd, h[f"r_{k}"]).where(h.mixed == 1)
        h[f"m_{k}"] = h[f"r_{k}"].where(isd, h[f"d_{k}"]).where(h.mixed == 1)
    keep = ["race_id", "matchup", "mixed", "ff", "mm", "wparty", "d_nominee", "r_nominee", "d_female", "r_female", "d_race", "r_race", "d_race_src",
            "r_race_src", "d_bioguide", "r_bioguide", "d_inc", "r_inc", "w_race", "m_race", "m_race_src", "w_inc", "m_inc", "pvi", "rural", "black_nh", "hisp", "asian_nh",
            "ba_plus", "med_income"] + list(PRIORS)
    return h[keep]


def tracker():
    r = pd.read_csv(os.path.join(ROOT, "data", "races.csv"), low_memory=False)
    c = pd.read_csv(os.path.join(ROOT, "data", "candidates.csv"), low_memory=False, keep_default_na=False, na_values=[""])  # race code NA = Native American
    return r, c


def with_nominees(h, c):
    """races + each party's nominee: gender, CAWP race code, incumbency, FEC number, link, and the race (cand_race)"""
    cw = c[["race_id", "name", "party", "gender", "race_eth", "incumbent", "fec_id", "link"]]
    for p, P in (("d", "D"), ("r", "R")):
        x = cw[cw.party == P].rename(columns={"name": f"{p}_nominee", "gender": f"{p}_gen", "race_eth": f"{p}_cawp", "incumbent": f"{p}_inc",
                                              "fec_id": f"{p}_fec", "link": f"{p}_link"}).drop(columns="party")
        h = h.merge(x.drop_duplicates(["race_id", f"{p}_nominee"]), on=["race_id", f"{p}_nominee"], how="left")
    h = h.drop_duplicates("race_id")
    idx, mrace = member_index()
    nrace = nominee_race()
    for p in ("d", "r"):
        found = [cand_race(row, p, idx, mrace, nrace) for row in h.itertuples(index=False)]
        h[f"{p}_bioguide"] = [f[0] for f in found]
        h[f"{p}_race"] = [f[1] for f in found]
        h[f"{p}_race_src"] = [f[2] for f in found]
        h[f"{p}_female"] = (h[f"{p}_gen"] == "F").astype(int)
    return h


NOW = 2026


def nominees_now():
    """the current cycle (not in the analysis): House races (regular) and Senate races with a Democratic or a Republican
    nominee, each nominee's race found the same way"""
    r, c = tracker()
    h = r[(r.year == NOW) & r.chamber.isin(["H", "S"]) & (r.d_nominee.notna() | r.r_nominee.notna())].copy()
    return with_nominees(h, c)


def member_index():
    """state -> people who served in Congress (any term there), and bioguide -> race codes from the minority lists"""
    mrace = {}
    p = os.path.join(ROOT, "data", "static", "member_race.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            mrace = {r["bioguide"]: r["race"] for r in csv.DictReader(f)}
    if not mrace:
        raise SystemExit("data/static/member_race.csv is missing: run pipeline/fetch_member_race.py first")
    idx = collections.defaultdict(list)
    for x in MR.legislators():
        ids, nm = x.get("id", {}), x.get("name", {})
        full = nm.get("official_full") or f"{nm.get('first', '')} {nm.get('last', '')}"
        variants = {full, f"{nm.get('first', '')} {nm.get('last', '')}"} | ({f"{nm['nickname']} {nm.get('last', '')}"} if nm.get("nickname") else set())
        person = dict(bioguide=ids.get("bioguide"), gender=x.get("bio", {}).get("gender"), fec=set(ids.get("fec", []) or []),
                      wiki=(ids.get("wikipedia") or "").replace("_", " ").strip().lower(),
                      variants=[v.strip() for v in variants if v.strip()], last={t for t in N.tokens(nm.get("last", "")) if len(t) > 1})
        for st in {t["state"] for t in x.get("terms", [])}:
            idx[st].append(person)
    return idx, mrace


def nominee_race():
    """(race_id, party) -> (codes, source tag, name) from data/static/nominee_race.csv"""
    out = {}
    p = os.path.join(ROOT, "data", "static", "nominee_race.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["race"]:
                    out[(r["race_id"], r["party"])] = (r["race"], r["src"], r["name"])
    return out


def cand_race(r, p, idx, mrace, nrace):
    """(bioguide, race codes, source) of the party's nominee: cawp = CAWP's code (women), file = published codes from
    the user's file, research = web research with a source, rdc = Reflective Democracy Campaign's published
    classification (kept apart in the user's file), surname = Hispanic (estimated) from the first name and surname,
    list = the minority lists, member = served in Congress but on none of the lists (white, an inference), none = unknown"""
    name = getattr(r, f"{p}_nominee")
    name = name if isinstance(name, str) else ""
    gender, cawp = getattr(r, f"{p}_gen"), getattr(r, f"{p}_cawp")
    fec = getattr(r, f"{p}_fec") if isinstance(getattr(r, f"{p}_fec"), str) else ""
    link = getattr(r, f"{p}_link")
    link = str(link).replace("https://en.wikipedia.org/wiki/", "").replace("_", " ").strip().lower() if isinstance(link, str) else ""
    st = r.race_id.split("-")[2]
    toks = {t for t in N.tokens(name) if len(t) > 1}
    b = ""
    for m in idx.get(st, []):
        if m["gender"] != gender:
            continue
        if (fec and fec in m["fec"]) or (link and m["wiki"] and link == m["wiki"]) or \
                (m["last"] & toks and any(N.same_person(v, name) for v in m["variants"])):
            b = m["bioguide"]
            break
    if gender == "F" and isinstance(cawp, str) and cawp and cawp != "unavailable":
        return b, cawp, "cawp"
    f = nrace.get((r.race_id, p.upper()))
    if f and (N.same_person(f[2], name) or ({t for t in N.tokens(f[2]) if len(t) > 1} & toks)):
        return b, f[0], f[1]
    if b:
        return (b, mrace[b], "list") if b in mrace else (b, "W", "member")
    return "", None, "none"


def codes(series):
    return series.map(lambda s: set(str(s).split("/")) if isinstance(s, str) and s else None)


def build(resp, rc):
    d = resp.merge(rc, on="race_id", how="inner")
    d = d[d.vote.isin(["D", "R"])].copy()
    mix = d.mixed == 1
    d["vote_d"] = (d.vote == "D").astype(int)
    d["vote_woman"] = (d.vote == d.wparty).astype(float).where(mix)  # woman-vs-man races only
    d["copart"] = (d.pid == d.wparty).astype(float).where(d.pid.notna() & mix)
    d["outpart"] = ((d.pid != d.wparty) & d.pid.isin(["D", "R"])).astype(float).where(d.pid.notna() & mix)
    # each party's nominee: same race as the respondent, unknown race (then match and non-white are 0), non-white
    for p in ("d", "r"):
        cs = codes(d[f"{p}_race"])
        d[f"same_race_{p}"] = [(float(a in b) if b is not None else 0.0) if a is not None else np.nan for a, b in zip(d.rrace, cs)]
        d[f"{p}_race_unk"] = cs.map(lambda x: float(x is None))
        d[f"{p}_nonwhite"] = cs.map(lambda x: 0.0 if x is None else float(x != {"W"}))
    # the woman and the man (woman-vs-man races): an unknown woman's race drops the respondent from the models
    wset, mset = codes(d.w_race), codes(d.m_race)
    d["same_race_w"] = pd.Series([float(a in b) if b is not None and a is not None else np.nan for a, b in zip(d.rrace, wset)], index=d.index).where(mix)
    d["m_race_unk"] = mset.map(lambda x: float(x is None)).where(mix)
    d["same_race_m"] = pd.Series([(float(a in b) if b is not None else 0.0) if a is not None else np.nan for a, b in zip(d.rrace, mset)], index=d.index).where(mix)
    d["w_nonwhite"] = wset.map(lambda x: np.nan if x is None else float(x != {"W"})).where(mix)
    d["m_nonwhite"] = mset.map(lambda x: 0.0 if x is None else float(x != {"W"})).where(mix)
    for k, code in (("r_black", "B"), ("r_hisp", "H"), ("r_asian", "AP")):
        d[k] = (d.rrace == code).astype(float).where(d.rrace.notna())
    d["r_other"] = d.rrace.isin(["NA", "MENA", "MU", "OTHER"]).astype(float).where(d.rrace.notna())
    d["age10"] = d.age / 10
    for k, code in (("lib", "L"), ("con", "C"), ("ideo_ns", "NS")):
        d[k] = (d.ideo == code).astype(float).where(d.ideo.notna())
    d["hisp_d"] = d.hisp
    d["inc10k"] = d.med_income / 10000
    for y in YEARS[1:]:
        d[f"y{y}"] = (d.year == y).astype(int)
    d["const"] = 1.0
    return d


# ---------- estimation ----------
def cluster_cov(score, bread, groups, qc):
    """sandwich: bread @ (sum over clusters of summed scores, outer product) @ bread * qc"""
    s = pd.DataFrame(score).groupby(groups).sum().to_numpy()
    return qc * bread @ (s.T @ s) @ bread


def fit_lpm(y, X, w, g):
    XtW = X.T * w
    bread = np.linalg.pinv(XtW @ X)
    b = bread @ (XtW @ y)
    e = y - X @ b
    n, k = X.shape
    G = len(np.unique(g))
    V = cluster_cov(X * (w * e)[:, None], bread, g, G / (G - 1) * (n - 1) / (n - k))
    ybar = np.average(y, weights=w)
    r2 = 1 - np.sum(w * e ** 2) / np.sum(w * (y - ybar) ** 2)
    return b, V, dict(n=n, k=k, G=G, fit=r2, dof=G - 1)


def fit_logit(y, X, w, g):
    b = np.zeros(X.shape[1])
    for _ in range(100):  # Newton-Raphson on the weighted log likelihood
        p = 1 / (1 + np.exp(-(X @ b)))
        H = (X.T * (w * p * (1 - p))) @ X
        step = np.linalg.solve(H, X.T @ (w * (y - p)))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    p = 1 / (1 + np.exp(-(X @ b)))
    bread = np.linalg.pinv((X.T * (w * p * (1 - p))) @ X)
    G = len(np.unique(g))
    V = cluster_cov(X * (w * (y - p))[:, None], bread, g, G / (G - 1))
    ll = np.sum(w * (y * np.log(p) + (1 - y) * np.log(1 - p)))
    p0 = np.average(y, weights=w)
    ll0 = np.sum(w * (y * np.log(p0) + (1 - y) * np.log(1 - p0)))
    return b, V, dict(n=X.shape[0], k=X.shape[1], G=G, fit=1 - ll / ll0, dof=None)


def pvalue(z, dof):
    return float(2 * (stats.t.sf(abs(z), dof) if dof else stats.norm.sf(abs(z))))


def predictions(b, V, X, w, names, logit, dof):
    """adjusted predictions for female/male x prior yes/no and their differences (delta method)"""
    i_f, i_p, i_fp = names.index("female"), names.index("prior"), names.index("female_x_prior")
    pts, grads = {}, {}
    for f in (0, 1):
        for pr in (0, 1):
            Z = X.copy()
            Z[:, i_f], Z[:, i_p], Z[:, i_fp] = f, pr, f * pr
            eta = Z @ b
            if logit:
                p = 1 / (1 + np.exp(-eta))
                pts[(f, pr)] = np.average(p, weights=w)
                grads[(f, pr)] = (Z * (w * p * (1 - p))[:, None]).sum(0) / w.sum()
            else:
                pts[(f, pr)] = np.average(eta, weights=w)
                grads[(f, pr)] = (Z * w[:, None]).sum(0) / w.sum()
    def q(comb):
        est = sum(c * pts[k] for k, c in comb)
        g = sum(c * grads[k] for k, c in comb)
        se = float(np.sqrt(g @ V @ g))
        return est, se
    out = []
    for key, lab, comb in (
            ("F1", "여성 유권자 · 기존 여성 있음", [((1, 1), 1)]), ("M1", "남성 유권자 · 기존 여성 있음", [((0, 1), 1)]),
            ("F0", "여성 유권자 · 기존 여성 없음", [((1, 0), 1)]), ("M0", "남성 유권자 · 기존 여성 없음", [((0, 0), 1)]),
            ("gap1", "차이(여 − 남) · 기존 여성 있음", [((1, 1), 1), ((0, 1), -1)]),
            ("gap0", "차이(여 − 남) · 기존 여성 없음", [((1, 0), 1), ((0, 0), -1)]),
            ("dF", "여성 유권자 · 차이(있음 − 없음)", [((1, 1), 1), ((1, 0), -1)]),
            ("dM", "남성 유권자 · 차이(있음 − 없음)", [((0, 1), 1), ((0, 0), -1)]),
            ("did", "차이의 차이", [((1, 1), 1), ((0, 1), -1), ((1, 0), -1), ((0, 0), 1)])):
        est, se = q(comb)
        z = est / se if se > 0 else np.nan
        out.append(dict(quantity=key, label=lab, est=100 * est, se=100 * se, p=pvalue(z, dof) if se > 0 else None,
                        ci_lo=100 * (est - 1.96 * se), ci_hi=100 * (est + 1.96 * se)))
    return out


def run(d):
    names = [t for t, _ in TERMS]
    coef_rows, pred_rows, models = [], [], []
    for wp in ("D", "R"):
        for prior in PRIORS:
            s = d[d.wparty == wp].copy()
            s["prior"] = (s[prior] > 0).astype(float).where(s[prior].notna())
            s["female_x_prior"] = s.female * s.prior
            s = s.dropna(subset=names + ["vote_woman", "weight"])
            s = s[s.weight > 0]
            y, X, w = s.vote_woman.to_numpy(float), s[names].to_numpy(float), s.weight.to_numpy(float)
            w = w / w.mean()
            g = s.race_id.to_numpy()
            keep = [j for j in range(X.shape[1]) if names[j] == "const" or np.ptp(X[:, j]) > 0]  # e.g. a year with no race
            nm = [names[j] for j in keep]
            X = X[:, keep]
            for est, fitter in (("lpm", fit_lpm), ("logit", fit_logit)):
                b, V, info = fitter(y, X, w, g)
                se = np.sqrt(np.diag(V))
                mid = f"{wp}_{prior}_{est}"
                cf = {}
                for j, t in enumerate(nm):
                    z = b[j] / se[j] if se[j] > 0 else np.nan
                    p = pvalue(z, info["dof"]) if se[j] > 0 else None
                    lo_hi = stats.t.ppf(0.975, info["dof"]) if info["dof"] else 1.959964
                    coef_rows.append(dict(model=mid, woman_party=wp, prior_var=prior, estimator=est, term=t, label=LABEL[t],
                                          coef=b[j], se=se[j], stat=z, p=p, ci_lo=b[j] - lo_hi * se[j], ci_hi=b[j] + lo_hi * se[j],
                                          n=info["n"], n_races=info["G"], fit=info["fit"]))
                    cf[t] = [round(float(b[j]), 6), round(float(se[j]), 6), None if p is None else round(p, 6)]
                pr = predictions(b, V, X, w, nm, est == "logit", info["dof"])
                for row in pr:
                    pred_rows.append(dict(model=mid, woman_party=wp, prior_var=prior, estimator=est, **row, n=info["n"], n_races=info["G"]))
                models.append(dict(id=mid, wp=wp, prior=prior, est=est, n=info["n"], races=info["G"],
                                   women=int(s.female.sum()), prior_races=int(s.loc[s.prior == 1, "race_id"].nunique()),
                                   fit=round(float(info["fit"]), 4), coef=cf,
                                   pred={r["quantity"]: [round(r["est"], 3), round(r["se"], 3), None if r["p"] is None else round(r["p"], 6)] for r in pr}))
                log(mid, "n", info["n"], "races", info["G"], "female x prior", round(b[nm.index("female_x_prior")], 4), "se", round(se[nm.index("female_x_prior")], 4))
    return pd.DataFrame(coef_rows), pd.DataFrame(pred_rows), models


IND_LABELS = dict(
    case_id="CES 응답자 번호(case_id)", year="선거 연도", race_id="선거 번호", race_n="선거 번호(숫자, 묶음 표준오차용)", state="주", district="선거구",
    matchup="본선 대결(민주-공화 성별): F-M, M-F, F-F, M-M", mixed="여성 대 남성 선거(1)", ff="둘 다 여성인 선거(1)", mm="둘 다 남성인 선거(1)",
    vote_d="민주 후보를 찍음(1) / 공화 후보(0)", female="여성 유권자(1)", weight="CES 가중치(선거 뒤, 없으면 선거 전)",
    pid="정당 일체감(D/R 쪽, 기우는 무당파 포함; I = 무당파·모름)",
    d_female="민주 후보가 여성(1)", r_female="공화 후보가 여성(1)",
    d_race="민주 후보 인종(빈칸 = 모름)", r_race="공화 후보 인종(빈칸 = 모름)",
    d_race_src="민주 후보 인종 근거: cawp, file 출판 코드 모음, research 웹 조사, rdc 기관 분류, surname 히스패닉(추정), list 의원 명단, member 의원(백인으로 봄), none", r_race_src="공화 후보 인종 근거(같은 코드)",
    same_race_d="민주 후보와 같은 인종(1, 모르면 0)", same_race_r="공화 후보와 같은 인종(1, 모르면 0)",
    d_race_unk="민주 후보 인종 모름(1)", r_race_unk="공화 후보 인종 모름(1)", d_nonwhite="민주 후보가 백인 아님(1, 모르면 0)", r_nonwhite="공화 후보가 백인 아님(1, 모르면 0)",
    d_inc="민주 후보가 현직(1)", r_inc="공화 후보가 현직(1)",
    rrace="응답자 인종(CAWP 코드: W B H AP NA MENA MU OTHER)",
    wparty="여성 후보의 정당(D/R, 여성 대 남성 선거만)", vote_woman="여성 후보를 찍음(1) / 남성 후보(0), 여성 대 남성 선거만",
    copart="여성 후보와 같은 정당 지지(1, 여성 대 남성 선거만)", outpart="여성 후보와 반대 정당 지지(1, 여성 대 남성 선거만)",
    w_race="여성 후보 인종(여성 대 남성 선거만)", m_race="남성 후보 인종(여성 대 남성 선거만, 빈칸 = 모름)",
    m_race_src="남성 후보 인종 근거(file, research, rdc, surname, list, member, none; 여성 대 남성 선거만)",
    same_race_w="여성 후보와 같은 인종(1, 여성 대 남성 선거만)", same_race_m="남성 후보와 같은 인종(1, 모르면 0, 여성 대 남성 선거만)",
    m_race_unk="남성 후보 인종 모름(1, 여성 대 남성 선거만)", w_nonwhite="여성 후보가 백인 아님(1, 여성 대 남성 선거만)",
    m_nonwhite="남성 후보가 백인 아님(1, 모르면 0, 여성 대 남성 선거만)", w_inc="여성 후보가 현직(1, 여성 대 남성 선거만)", m_inc="남성 후보가 현직(1, 여성 대 남성 선거만)",
    r_black="응답자 흑인(1)", r_hisp="응답자 히스패닉(1)", r_asian="응답자 아시아계(1)", r_other="응답자 그 밖 인종(1)", college="4년제 대졸 이상(1)",
    age="나이", age10="나이/10", ideo="이념(L 진보, M 중도, C 보수, NS 모름)", lib="진보(1)", con="보수(1)", ideo_ns="이념 모름(1)",
    pvi="당파 지수(+민주)", rural="농촌 인구 비율(%)", black_nh="선거구 흑인 비율(%)", hisp_d="선거구 히스패닉 비율(%)", asian_nh="선거구 아시아계 비율(%)",
    ba_plus="선거구 대졸 비율(%)", inc10k="선거구 가구 소득 중앙값(만 달러)",
    women_members_since_1990="기존 여성 의원 수(본인 포함)", women_members_since_1990_excl="기존 여성 의원 수(본인 제외)",
    women_prior_since_1990="기존 여성 의원·후보 수(본인 포함)", women_prior_since_1990_excl="기존 여성 의원·후보 수(본인 제외)")


NOMINEE_LABELS = dict(
    race_id="선거 번호", year="선거 연도", chamber="의회(H 하원, S 상원)", state="주", district="선거구(0 = 주 전체 한 석, 상원)",
    matchup="본선 대결(민주-공화 성별)", party="정당(D 민주, R 공화)", name="후보 이름", female="여성 후보", incumbent="현직",
    race="후보 인종(CAWP 코드, 여럿이면 /)", race_src="인종 근거(cawp/file/research/rdc/surname/list/member/none)",
    source="인종 출처", source_url="출처 주소", note="메모", bioguide="의회 인명록 번호(의원이었던 사람)")
SRC_TEXT = {"cawp": "CAWP", "list": "Wikipedia lists of minority members of Congress",
            "member": "served in Congress, on none of the minority lists (white, an inference)", "none": ""}


def write_nominees(rc):
    """docs/data/ces/nominee_race.csv/.dta: every Democratic and Republican nominee of the races in the analysis (2008-2024
    House, one nominee of each party) and of the current cycle (2026 House and Senate, nominees_now), with the race code,
    its source tag and the source itself"""
    nr = {}
    p = os.path.join(ROOT, "data", "static", "nominee_race.csv")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                nr[(r["race_id"], r["party"])] = r
    rows = []
    for x in pd.concat([rc.assign(chamber="H"), nominees_now()], ignore_index=True).itertuples(index=False):
        st, dist = x.race_id.split("-")[2], int(x.race_id.split("-")[3])
        for p_, P in (("d", "D"), ("r", "R")):
            name = getattr(x, f"{p_}_nominee")
            if not isinstance(name, str) or not name:  # one-party races of the current cycle
                continue
            src = getattr(x, f"{p_}_race_src")
            o = nr.get((x.race_id, P), {}) if src in ("file", "research", "rdc", "surname") else {}
            rows.append(dict(race_id=x.race_id, year=int(x.race_id[:4]), chamber=x.chamber, state=st, district=dist, matchup=x.matchup,
                             party=P, name=name, female=int(getattr(x, f"{p_}_female")),
                             incumbent=getattr(x, f"{p_}_inc"), race=getattr(x, f"{p_}_race") or "", race_src=src,
                             source=o.get("source") or SRC_TEXT.get(src, ""), source_url=o.get("source_url") or "",
                             note=o.get("note") or "", bioguide=getattr(x, f"{p_}_bioguide") or ""))
    t = pd.DataFrame(rows).sort_values(["year", "chamber", "state", "district", "party"])
    t["incumbent"] = pd.to_numeric(t["incumbent"], errors="coerce")
    t.to_csv(os.path.join(OUT, "nominee_race.csv"), index=False, encoding="utf-8-sig")
    st = t.copy()
    for c in st.columns:
        if c in ("year", "district", "female"):
            st[c] = st[c].astype("int16")
        elif c == "incumbent":
            st[c] = st[c].astype("float32")
        else:
            st[c] = st[c].astype(object).where(st[c].notna(), "").astype(str)
    st.to_stata(os.path.join(OUT, "nominee_race.dta"), write_index=False, version=118, variable_labels=NOMINEE_LABELS,
                data_label="후보 인종: 2008-2024 하원(분석 대상), 2026 하원·상원 민주·공화 후보", time_stamp=dt.datetime(2026, 1, 1))
    log("nominee race table", len(t), "rows", t.race_src.value_counts().to_dict())
    return {k: int(v) for k, v in t.race_src.value_counts().items()}


def write_individual(d):
    """the analysis file as Stata, zipped (ces_individual.zip holds ces_individual.dta): every respondent of a race with
    a Democratic and a Republican nominee, with the ff / mm flags for the same-gender races"""
    import zipfile
    cols = list(IND_LABELS)
    x = d.copy()
    x["race_n"] = pd.factorize(x.race_id, sort=True)[0] + 1
    x = x[cols].sort_values(["year", "state", "district", "case_id"])
    for c in x.columns:
        if pd.api.types.is_numeric_dtype(x[c]):
            if c in ("year", "district", "race_n") or (x[c].dropna().isin([0, 1]).all() and c not in ("weight",)):
                x[c] = x[c].astype("float64")
                if x[c].notna().all():
                    x[c] = x[c].astype("int32" if c in ("year", "race_n") else "int8")
            else:
                x[c] = x[c].astype("float32")
        else:
            x[c] = x[c].astype(object).where(x[c].notna(), "").astype(str)
    tmp = os.path.join(F.TMP, "ces_individual.dta")
    x.to_stata(tmp, write_index=False, version=118, variable_labels={k: v[:80] for k, v in IND_LABELS.items()},
               data_label="CES 개인 자료: 하원 선거 2008-2024(ff·mm = 같은 성별끼리)", time_stamp=dt.datetime(2026, 1, 1))
    zp = os.path.join(OUT, "ces_individual.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        info = zipfile.ZipInfo("ces_individual.dta", date_time=(2026, 1, 1, 0, 0, 0))  # fixed date: same data, same file
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(tmp, "rb") as f:
            z.writestr(info, f.read())
    old = os.path.join(OUT, "ces_individual.dta")
    if os.path.exists(old):
        os.remove(old)
    log("analysis file", len(x), "rows,", round(os.path.getsize(tmp) / 1e6, 1), "MB as .dta,", round(os.path.getsize(zp) / 1e6, 1), "MB zipped")
    return dict(rows=len(x), by_matchup={k: int(v) for k, v in x.matchup.value_counts().items()})


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    meta = dict(source=F.DOI, citation="Kuriwaki, Shiro. Cumulative CES Common Content. Harvard Dataverse. https://doi.org/10.7910/DVN/II2DB6",
                run=time.strftime("%Y-%m-%d"), years=YEARS)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path is None:
        path, info = download()
        meta.update(info)
    df, meta["value_labels"] = read_ces(path)
    log("respondents read", len(df), round(time.time() - t0), "s")
    resp = respondents(df, meta)
    log(json.dumps(meta["labels"], ensure_ascii=False)[:3000])
    log(json.dumps(meta["coded"], ensure_ascii=False))
    rc = races()
    meta["nominee_table"] = write_nominees(rc)
    d = build(resp, rc)
    mx = rc[rc.mixed == 1]
    meta["sample"] = dict(respondents=int(len(d)), races=int(d.race_id.nunique()),
                          by_matchup={k: dict(respondents=int((d.matchup == k).sum()), races=int(d.loc[d.matchup == k, "race_id"].nunique())) for k in MATCHUPS},
                          by_party={wp: dict(respondents=int((d.wparty == wp).sum()), races=int(d.loc[d.wparty == wp, "race_id"].nunique())) for wp in ("D", "R")},
                          missing={c: int(d.loc[d.mixed == 1, c].isna().sum()) for c in ("copart", "same_race_w", "rrace", "college", "age", "lib", "pvi", "rural", "med_income")},
                          man_race_races={k: int(v) for k, v in mx.m_race_src.value_counts().items()},
                          man_race_codes={k: int(v) for k, v in mx.m_race.fillna("모름").value_counts().items()},
                          woman_race_codes={k: int(v) for k, v in mx.w_race.fillna("모름").value_counts().items()},
                          nominee_race_src={k: int(v) for k, v in pd.concat([rc.d_race_src, rc.r_race_src]).value_counts().items()})
    log("analysis sample", json.dumps(meta["sample"], ensure_ascii=False))
    coefs, preds, models = run(d)
    coefs.to_csv(os.path.join(OUT, "ces_models.csv"), index=False, encoding="utf-8-sig", float_format="%.6g")
    preds.to_csv(os.path.join(OUT, "ces_models_pred.csv"), index=False, encoding="utf-8-sig", float_format="%.6g")
    page = dict(meta=dict(years=YEARS, version=meta.get("version"), run=meta["run"], priors=PRIORS, terms=TERMS,
                          spec="vote_woman ~ female*prior + copart + outpart + same_race_w + same_race_m + m_race_unk + w_nonwhite + m_nonwhite + 응답자·선거구·후보 통제 + 연도",
                          man_race=meta["sample"]["man_race_races"]),
                models=models)
    with open(os.path.join(OUT, "ces_models.json"), "w", encoding="utf-8") as f:
        json.dump(page, f, ensure_ascii=False, separators=(",", ":"))
    meta["individual"] = write_individual(d)
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    log("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--nominees":  # only the nominee race table (no CES file needed)
        os.makedirs(OUT, exist_ok=True)
        write_nominees(races())
    else:
        main()
