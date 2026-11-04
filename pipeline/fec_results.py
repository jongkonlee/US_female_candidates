"""Parse FEC "Federal Elections" result workbooks (2002-2022) into one candidate-row table.

Each row = one candidate on one party line in one race (state, district or Senate), with primary, runoff,
general and general-runoff votes as printed. Totals rows ("Party Votes", "District Votes", ...) are skipped.
"""
import glob
import os
import re
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw", "fec_results")

FILES = {2002: "2002/2002fedresults.xls", 2004: "2004/2004congresults.xls", 2006: "2006/results06.xls",
         2008: "2008/2008congresults.xls", 2010: "2010/results10.xls", 2012: "2012/2012congresults.xls",
         2014: "2014/results14.xls", 2016: "2016/federalelections2016.xlsx", 2018: "2018/federalelections2018.xlsx",
         2020: "2020/federalelections2020.xlsx", 2022: "2022/federalelections2022.xlsx"}


def norm(h):
    return re.sub(r"\s+", " ", str(h)).strip().upper()


def colmap(header):
    m = {}
    for i, h in enumerate(header):
        h = norm(h)
        if h in ("NAN", ""):
            continue
        def put(k):
            m.setdefault(k, i)
        if h == "STATE ABBREVIATION":
            put("st")
        elif h == "STATE":
            put("state")
        elif h in ("DISTRICT", "D"):
            put("dist")
        elif h.startswith("FEC ID"):
            put("fec_id")
        elif "INCUMBENT" in h or h.startswith("(I)"):
            put("inc")
        elif h in ("FIRST NAME", "CANDIDATE NAME (FIRST)"):
            put("first")
        elif h in ("LAST NAME", "CANDIDATE NAME (LAST)"):
            put("last")
        elif h in ("CANDIDATE NAME", "LAST NAME, FIRST", "CANDIDATE NAME (LAST, FIRST)"):
            put("name")
        elif h == "PARTY":
            put("party")
        elif h in ("PRIMARY", "PRIMARY VOTES", "PRIMARY RESULTS"):
            put("pv")
        elif h == "PRIMARY %":
            put("pp")
        elif h in ("RUNOFF", "RUNOFF VOTES", "RUNOFF RESULTS"):
            put("rv")
        elif h == "RUNOFF %":
            put("rp")
        elif h in ("GENERAL", "GENERAL VOTES", "GENERAL RESULTS"):
            put("gv")
        elif h == "GENERAL %":
            put("gp")
        elif (h.startswith("GE RUNOFF") or h.startswith("GENERAL RUNOFF")) and "%" not in h:
            put("grv")
        elif (h.startswith("GE RUNOFF") or h.startswith("GENERAL RUNOFF")) and "%" in h:
            put("grp")
        elif h.startswith("COMBINED") and "%" not in h:
            put("cv")
        elif h.startswith("COMBINED") and "%" in h:
            put("cp")
        elif h.startswith("PE WINNER"):
            put("pwin")
        elif h.startswith("GE WINNER"):
            put("gwin")
        elif "NOTE" in h:
            put("note")
        elif h == "TOTAL VOTES":
            put("total")
    return m


def result_sheets(path):
    x = pd.ExcelFile(path)
    out = []
    for sh in x.sheet_names:
        s = sh.lower()
        if ("house" in s or "senate" in s) and "result" in s and "pres" not in s:
            out.append(sh)
    return out


def fec_file(year):
    """the year's results workbook: known file names through 2022, any 'federalelections' workbook after that"""
    if year in FILES:
        return os.path.join(RAW, FILES[year]) if os.path.exists(os.path.join(RAW, FILES[year])) else None
    if year <= 2022:  # older editions are PDFs (or partial workbooks) and are not read
        return None
    hits = sorted(glob.glob(os.path.join(RAW, str(year), "*.xls*")))
    pref = [h for h in hits if "federalelections" in os.path.basename(h).lower() or "results" in os.path.basename(h).lower()]
    return (pref or hits or [None])[0]


def read_year(year):
    path = fec_file(year)
    rows = []
    for sh in result_sheets(path):
        d = pd.read_excel(path, sheet_name=sh, header=None, dtype=object)
        hi = None
        for i in range(min(15, len(d))):
            vals = [norm(v) for v in d.iloc[i].tolist()]
            if "PARTY" in vals and any(v.startswith("PRIMARY") for v in vals):
                hi = i
                break
        if hi is None:
            raise ValueError(f"no header in {path} {sh}")
        cm = colmap(d.iloc[hi].tolist())
        chamber_hint = "S" if "senate" in sh.lower() and "house" not in sh.lower() else ("H" if "house" in sh.lower() and "senate" not in sh.lower() else None)
        for i in range(hi + 1, len(d)):
            r = d.iloc[i].tolist()
            g = lambda k: r[cm[k]] if k in cm and cm[k] < len(r) else None  # noqa: E731
            party = g("party")
            name = g("name")
            if name is None or (isinstance(name, float) and pd.isna(name)):
                fn, ln = g("first"), g("last")
                name = ", ".join(str(x) for x in (ln, fn) if x is not None and not (isinstance(x, float) and pd.isna(x)))
            name = "" if name is None or (isinstance(name, float) and pd.isna(name)) else str(name).strip()
            if party is None or (isinstance(party, float) and pd.isna(party)) or not name:
                continue
            if re.search(r"(party|district|state|total)\s+votes", name, re.I) or name.lower().startswith("total"):
                continue
            rows.append(dict(year=year, sheet=sh, row=i, chamber_hint=chamber_hint,
                             **{k: g(k) for k in ("st", "state", "dist", "fec_id", "inc", "first", "last", "party", "pv", "pp",
                                                   "rv", "rp", "gv", "gp", "grv", "grp", "cv", "cp", "pwin", "gwin", "note", "total")},
                             name=name))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    for y in FILES:
        df = read_year(y)
        print(y, len(df), "rows | sheets", df.sheet.unique().tolist())
        print("   dist sample:", sorted(map(str, df.dist.dropna().unique()))[:12], "... n=", df.dist.nunique())
        print("   pv non-numeric:", df.pv[pd.to_numeric(df.pv, errors="coerce").isna() & df.pv.notna()].astype(str).value_counts().head(8).to_dict())


# ---------------------------------------------------------------- one row per person per race
STATES2 = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA "
              "RI SC SD TN TX UT VT VA WA WV WI WY DC".split())


def num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.]", "", str(v).replace(",", ""))
    try:
        return float(s) if s not in ("", ".") else None
    except ValueError:
        return None


def pstatus(v):
    """what a non-numeric primary cell means"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, (int, float)):
        return "votes"
    s = str(v).strip().lower()
    if not s:
        return ""
    if re.match(r"^[\d,]+", s):
        return "votes"
    if s.startswith("unopposed"):
        return "unopposed"
    if s in ("*", "**", "c", "winner"):
        return "convention"
    if s == "loser":
        return "convention_lost"
    if s.startswith("#"):
        return "replacement"
    if s.startswith("withdr"):
        return "withdrew"
    return "other:" + s[:20]


def main_party(p):
    p = str(p or "").strip().upper()
    for tok in re.split(r"[/,;]+", p):
        tok = tok.strip()
        if tok in ("D", "DFL", "DEM", "D-NPL", "DNL", "NPL", "DEMOCRATIC") or tok.startswith("DEM"):
            return "D"
        if tok in ("R", "REP", "GOP", "REPUBLICAN") or tok.startswith("REP"):
            return "R"
    return "O"


def race_of(row, year):
    st = row["st"] if isinstance(row["st"], str) and row["st"].strip().upper() in STATES2 else row["state"]
    st = str(st or "").strip().upper()
    dist = str(row["dist"] if row["dist"] is not None and not (isinstance(row["dist"], float) and pd.isna(row["dist"])) else "").strip().upper()
    sheet = str(row["sheet"]).lower()
    chamber = "S" if (dist.startswith("S") or ("senate" in sheet and "house" not in sheet)) else "H"
    special = int("UNEXPIRED" in dist or bool(re.match(r"^S\s*-?\s*UN", dist)) or bool(re.match(r"^\d+\s*\*", dist)))
    if chamber == "H":
        m = re.match(r"(\d+)", dist)
        d = int(m.group(1)) if m else None
    else:
        d = 0
    return st, chamber, d, special


def persons(year):
    df = read_year(year)
    recs = []
    for _, r in df.iterrows():
        party = re.sub(r"[*#]+", "", str(r["party"] or "")).strip()
        name = str(r["name"]).strip()
        if not party or party.lower().startswith("combined") or name.lower() in ("scattered", "none of these candidates", "blank votes", "void votes", "over votes", "under votes", "write-in", "write-ins", "other write-ins") or name.lower().startswith(("scattered", "blank", "void", "none of")):
            continue
        st, ch, d, sp = race_of(r, year)
        if st not in STATES2 or (ch == "H" and d is None):
            continue
        recs.append(dict(year=year, chamber=ch, state=st, district=d, special=sp, name=re.sub(r"\s*[#*]+\s*$", "", name).strip(),
                         first=str(r["first"] or "").strip() if r["first"] is not None and not (isinstance(r["first"], float) and pd.isna(r["first"])) else "",
                         last=str(r["last"] or "").strip() if r["last"] is not None and not (isinstance(r["last"], float) and pd.isna(r["last"])) else "",
                         fec_id=str(r["fec_id"]).strip() if r["fec_id"] is not None and not (isinstance(r["fec_id"], float) and pd.isna(r["fec_id"])) and str(r["fec_id"]).strip() not in ("", "n/a") else "",
                         inc=int("(I)" in str(r["inc"] or "")), line=party, mp=main_party(re.sub(r"^W\((.*)\)$", r"\1", party)),
                         writein=int(party.upper() == "W" or party.upper().startswith("W(")),
                         pv=num(r["pv"]), pst=pstatus(r["pv"]), pp=num(r["pp"]), rv=num(r["rv"]), rp=num(r["rp"]),
                         gv=num(r["gv"]), gp=num(r["gp"]), gunopp=int(str(r["gv"]).strip().lower().startswith("unopposed")), grv=num(r["grv"]), grp=num(r["grp"]), cv=num(r["cv"]), cp=num(r["cp"]),
                         pwin=str(r["pwin"] or "").strip() if r["pwin"] is not None and not (isinstance(r["pwin"], float) and pd.isna(r["pwin"])) else "",
                         gwin=str(r["gwin"] or "").strip() if r["gwin"] is not None and not (isinstance(r["gwin"], float) and pd.isna(r["gwin"])) else "",
                         note=str(r["note"])[:300] if r["note"] is not None and not (isinstance(r["note"], float) and pd.isna(r["note"])) else ""))
    t = pd.DataFrame(recs)
    if t.empty:
        return t
    t["key"] = t.apply(lambda x: x["fec_id"] if x["fec_id"] else re.sub(r"[^a-z]", "", x["name"].lower()), axis=1)
    out = []
    ok = lambda v: v is not None and not (isinstance(v, float) and pd.isna(v))  # noqa: E731
    for (y, ch, st, d, sp, key), g in t.groupby(["year", "chamber", "state", "district", "special", "key"], sort=False):
        lines = [{k: (v if ok(v) else None) for k, v in l.items()} for l in g.to_dict("records")]
        major = [l for l in lines if l["mp"] in ("D", "R") and not l["writein"]]
        main = major[0] if major else lines[0]
        prim = [l for l in lines if l["pst"] or l["pv"] is not None]
        pl = next((l for l in prim if l["mp"] in ("D", "R")), prim[0] if prim else main)
        gvals = [l["gv"] for l in lines if l["gv"] is not None]
        cv = next((l["cv"] for l in lines if l["cv"] is not None), None)
        cp = next((l["cp"] for l in lines if l["cp"] is not None), None)
        out.append(dict(year=y, chamber=ch, state=st, district=d, special=sp, name=main["name"], first=main["first"],
                        last=main["last"], fec_id=main["fec_id"], incumbent=max(l["inc"] for l in lines),
                        party=main["mp"], party_line=main["line"], lines="/".join(sorted({l["line"] for l in lines})),
                        writein=int(all(l["writein"] for l in lines)),
                        p_party=pl["mp"] if (pl["pst"] or pl["pv"] is not None) else "", p_line=pl["line"] if (pl["pst"] or pl["pv"] is not None) else "",
                        p_votes=pl["pv"], p_pct=pl["pp"], p_status=pl["pst"], r_votes=pl["rv"], r_pct=pl["rp"],
                        g_votes=cv if cv is not None else (sum(gvals) if gvals else None), g_pct=cp if cp is not None else main["gp"] if main["gp"] is not None else next((l["gp"] for l in lines if l["gp"] is not None), None),
                        gr_votes=next((l["grv"] for l in lines if l["grv"] is not None), None), gr_pct=next((l["grp"] for l in lines if l["grp"] is not None), None),
                        g_unopposed=max(l["gunopp"] or 0 for l in lines),
                        pwin_fec=next((l["pwin"] for l in lines if l["pwin"]), ""), gwin_fec=next((l["gwin"] for l in lines if l["gwin"]), ""),
                        note=" | ".join(sorted({l["note"] for l in lines if l["note"]}))[:400], source="FEC"))
    return pd.DataFrame(out)
