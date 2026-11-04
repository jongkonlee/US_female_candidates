"""MIT Election Data and Science Lab, "U.S. House 1976–2024" (Harvard Dataverse, doi:10.7910/DVN/IG0UN2, CC0).

General election returns compiled from official state results. The Dataverse file sits behind a guestbook, so it is
not downloaded automatically: the copy in data/static (version 15.0, 2026-03-09, file 1976-2024-house.tab, gzipped)
was downloaded by hand.

races(year) -> {(state, district): dict(people=[...], placeholder=bool, skip="", kind="")}
  people: one dict per person with the first round (votes, pct) and, if there was one, the runoff (r_votes, r_pct)
  placeholder: the state printed no vote for an unopposed winner (MEDSL stores 1 or -1)
  skip: a reason not to use the race (a majority was needed and the runoff is not in the file)
"""
import collections
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "static", "medsl_house_1976-2024.csv.gz")

NONVOTE = re.compile(r"^(BLANK|VOID|OVER ?VOTES?|UNDER ?VOTES?|EXHAUSTED)", re.I)   # not votes for anyone: left out of totals
NONPERSON = re.compile(r"^(WRITE[- ]?INS?|SCATTER(ING)?|ALL OTHERS|OTHERS?|OTHER WRITE[- ]?INS?|MISCELLANEOUS|NA|)$", re.I)
# a fusion line reported under the party's name instead of the candidate's (Connecticut, New York 2024)
PARTY_LINE = {"WORKING FAMILIES", "INDEPENDENT", "INDEPENDENT PARTY", "CONSERVATIVE", "LIBERAL", "RIGHT TO LIFE",
              "COMMON SENSE", "GREEN", "LIBERTARIAN", "REFORM"}
D_LABELS = {"DEMOCRAT", "DEMOCRATIC", "DEMOCRATIC-FARMER-LABOR", "DEMOCRATIC-NONPARTISAN LEAGUE", "DEM"}
R_LABELS = {"REPUBLICAN", "INDEPENDENT-REPUBLICAN", "REP", "RE"}  # 'RE': cut short in the file (Indiana 1998)
MAJORITY_STATES = {"GA"}          # a general election winner needs a majority (runoff otherwise)
_DATA = None


def available():
    return os.path.exists(PATH)


def data():
    global _DATA
    if _DATA is None:
        d = pd.read_csv(PATH, dtype=str, keep_default_na=False)
        d["year"] = d.year.astype(int)
        d["district"] = d.district.astype(int)
        d["votes"] = pd.to_numeric(d.candidatevotes, errors="coerce").fillna(0)
        _DATA = d
    return _DATA


def years():
    return sorted(data().year.unique()) if available() else []


def line_party(p):
    p = str(p or "").strip().upper()
    head = p.split(",")[0].strip()
    if p in D_LABELS or head in D_LABELS:
        return "D"
    if p in R_LABELS or head in R_LABELS:
        return "R"
    return "O"


def clean(s):
    s = str(s or "").replace('\\"', '"').replace("\\", "")
    s = re.sub(r",\s*(JR|SR|II|III|IV)\b\.?", r" \1", s, flags=re.I)  # 'DONALD S. BEYER, JR.' (a comma reads as 'Last, First')
    return re.sub(r"\s+", " ", s).strip()


def _cap(w):
    m = re.match(r"^([\"'(“‘]*)(.*?)([\"')”’.,]*)$", w)
    pre, core, post = m.groups()
    lw = core.lower()
    if lw in ("ii", "iii", "iv"):
        core = lw.upper()
    elif core:
        core = lw[0].upper() + lw[1:]
        core = re.sub(r"^(Mc)([a-z])", lambda x: x.group(1) + x.group(2).upper(), core)
        core = re.sub(r"^([OD]['’])([a-z])", lambda x: x.group(1) + x.group(2).upper(), core)
    return pre + core + post


def nice(s):
    """'W J "BILLY" TAUZIN' -> 'W J "Billy" Tauzin', 'ANTHONY D’ESPOSITO' -> 'Anthony D’Esposito'"""
    s = clean(s)
    if s != s.upper():
        return s
    return " ".join("-".join(_cap(p) for p in tok.split("-")) for tok in s.split(" "))


def nickname_alt(s):
    """'W J "BILLY" TAUZIN' -> 'BILLY TAUZIN' (second spelling for matching), or ''"""
    m = re.search(r"[\"“]([^\"”]+)[\"”]", s)
    if not m:
        return ""
    rest = re.sub(r"[\"“][^\"”]+[\"”]", " ", s).split()
    rest = [t for t in rest if t.strip(".,").lower() not in ("jr", "sr", "ii", "iii", "iv")]
    return f"{m.group(1)} {rest[-1]}" if rest else ""


def _people(lines):
    """lines of one race and round -> (people, total, party_lines, exhausted). Fusion lines (one person on several
    party lines) are added up; the person's party is the major party (D/R) line with more votes. party_lines: fusion
    lines that carry a party name instead of a candidate name, [(label, votes)]."""
    per = collections.OrderedDict()
    total = 0.0
    party_lines, exhausted = [], False
    for ln in lines.itertuples(index=False):
        nm = clean(ln.candidate)
        up = nm.upper()
        if NONVOTE.match(up):
            exhausted = exhausted or up.startswith("EXHAUSTED")
            continue
        total += ln.votes
        if NONPERSON.match(up):
            continue
        if up in PARTY_LINE:
            party_lines.append((nm, ln.votes))
            continue
        key = re.sub(r"[^A-Z]", "", up)
        p = per.setdefault(key, dict(name=nm, nice=nice(nm), alt=nickname_alt(nm), votes=0.0, pv=collections.Counter(), writein=True,
                                     labels=set()))
        p["votes"] += ln.votes
        p["pv"][line_party(ln.party)] += ln.votes
        if str(ln.party).strip().upper() not in ("", "NA"):
            p["labels"].add(str(ln.party).strip().upper())
        p["writein"] = p["writein"] and ln.writein == "TRUE"
    out = []
    for p in per.values():
        dr = {k: v for k, v in p.pop("pv").items() if k in ("D", "R")}
        p["party"] = max(dr, key=dr.get) if dr else "O"
        p["pct"] = 100.0 * p["votes"] / total if total > 1 else None
        out.append(p)
    return out, total, party_lines, exhausted


def races(year):
    if not available():
        return {}
    d = data()
    x = d[d.year == year]
    out = {}
    for (st, dist), g in x.groupby(["state_po", "district"]):
        sp = g.special == "TRUE"
        run = g[g.runoff == "TRUE"]
        first = g[(g.stage == "GEN") & ~sp & (g.runoff != "TRUE")]
        kind = ""
        if year == 1996 and st == "TX" and (sp & (g.stage == "PRI")).any():
            # redrawn districts (Bush v. Vera): open special election on election day for the full term, December runoff
            first, kind = g[sp & (g.stage == "PRI")], "tx1996"
        if first.empty and run.empty:
            continue  # only an unexpired-term special election
        fp, ftot, plines, exhausted = _people(first)
        rp, _, _, _ = _people(run)
        placeholder = bool(fp) and ftot <= 1 and not rp
        skip = ""
        if rp:
            win = max(rp, key=lambda p: p["votes"])
        elif placeholder:
            win = max(fp, key=lambda p: p["votes"])
        elif fp:
            win = max(fp, key=lambda p: p["votes"])
            open_ballot = kind == "tx1996" or (st == "LA" and year >= 1998)
            if (open_ballot or st in MAJORITY_STATES) and (win["pct"] or 0) < 50:
                win, skip = None, "no majority and the runoff is not in the MEDSL file"
        else:
            win = None
        people = {re.sub(r"[^A-Z]", "", p["name"].upper()): dict(p, r_votes=None, r_pct=None) for p in fp}
        for p in rp:
            k = re.sub(r"[^A-Z]", "", p["name"].upper())
            q = people.setdefault(k, dict(p, votes=None, pct=None))
            q["r_votes"], q["r_pct"] = p["votes"], p["pct"]
        for q in people.values():
            q["won"] = int(win is not None and re.sub(r"[^A-Z]", "", q["name"].upper()) == re.sub(r"[^A-Z]", "", win["name"].upper()))
        out[(st, int(dist))] = dict(people=list(people.values()), placeholder=placeholder, skip=skip, kind=kind, total=ftot,
                                    party_lines=plines, rcv_final=exhausted)
    return out
