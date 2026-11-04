"""Read election results from Wikipedia wikitext saved by collect.py.

Two kinds of tables:
  * "Election box" templates (state/district/Senate race pages): primary, runoff and general results with votes
  * the district table of the national overview page ("{year} United States House of Representatives elections"):
    general election candidates with percentages only (used for 1990-2000 House general elections)

Every output row: year, chamber, state, district, stage (P primary, R primary runoff, G general, GR general runoff,
C convention), box_party (party named in the box title, D/R/O or ''), system ('' or 'open' for top-two/jungle/blanket
boxes), name, party (D/R/O), party_raw, votes, pct, won (winning-candidate template or Aye mark), incumbent, writein,
title, page.
"""
import glob
import json
import os
import re

import mwparserfromhell as mwp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = os.path.join(ROOT, "raw", "wiki")

STATE_ABBR = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
              "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
              "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
              "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
              "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
              "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
              "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
              "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
              "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
              "Wisconsin": "WI", "Wyoming": "WY"}
AT_LARGE = {"AK", "DE", "MT", "ND", "SD", "VT", "WY"}  # (MT had two seats 1983-1993 and again from 2023)

ORD = r"(\d+)(?:st|nd|rd|th)"


def party_code(s):
    s = (s or "").lower()
    if "democrat" in s and "republican" not in s:
        return "D"
    if "republican" in s:
        return "R"
    return "O"


def clean_name(s):
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s or "", flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{\s*(?:nowrap|nobr)\s*\|([^{}]*)\}\}", r"\1", s, flags=re.I)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("'''", "").replace("''", "")
    inc = bool(re.search(r"\(\s*(?:incumbent|inc\.?)\s*\)", s, re.I))
    s = re.sub(r"\((?:[^()]*\b(?:incumbent|write-in|inc\.?)\b[^()]*)\)", "", s, flags=re.I)
    s = re.sub(r"\s*\*+\s*$", "", s)
    s = re.sub(r"\((?:withdrew|withdrawn|disqualified|deceased|died)[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,;")
    if re.fullmatch(r"(?i)(tbd|tba|vacant|none|n/a|no candidate|unopposed)", s):
        s = ""
    return s, inc


def num(s):
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", str(s or ""), flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"[^\d.\-]", "", s.replace(",", ""))
    try:
        return float(s) if s not in ("", ".", "-") else None
    except ValueError:
        return None


def pval(t, *names):
    for n in names:
        if t.has(n):
            return str(t.get(n).value).strip()
    return ""


def heading_district(text, st):
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    m = re.search(r"district\s*(\d+)\b", t, re.I) or re.search(r"\b" + ORD + r"\s+(?:congressional\s+)?district", t, re.I)
    if m:
        return int(m.group(1))
    if re.search(r"at[- ]large", t, re.I):
        return 0
    return None


def box_stage(title, heads):
    """stage, box party, open-primary flag from the box title (falls back to the section headings)"""
    t = (title or "").lower()
    h = " / ".join(x.lower() for x in heads[-3:])
    src = t if re.search(r"primary|runoff|convention|general|election|caucus", t) else (t + " / " + h)
    special = "special" in t and "general" not in t
    last = heads[-1].lower() if heads else ""
    if "runoff" in src or "run-off" in src or "runoff" in last or "run-off" in last:
        party_named = re.search(r"democratic|republican|libertarian|green|conservative", t)
        stage = "R" if ("primary" in src or "primary" in last or party_named) else "GR"
    elif "convention" in src or "caucus" in src:
        stage = "C"
    elif "primary" in src:
        stage = "P"
    else:
        stage = "G"
    is_open = bool(re.search(r"nonpartisan|blanket|top[- ]two|top[- ]four|jungle|open primary|all-party|unified primary", src))
    bp = ""
    m = re.search(r"(democratic[-–— ]*(?:farmer[-–— ]*labor|npl)?|republican|libertarian|green|conservative|working families|independence|reform)\s+(?:party\s+)?(?:primary|convention|caucus|runoff)", src)
    if m and stage in ("P", "R", "C"):
        bp = party_code(m.group(1)) if party_code(m.group(1)) != "O" else "O"
    return stage, bp, is_open, special


RAW_ROW = re.compile(r"class=\"?org\"?[^|\n]*\|\s*(?P<party>[^\n]*?)\n.*?class=\"?fn\"?[^|\n]*\|\s*(?P<name>[^\n]*?)\n"
                     r"\s*\|[^|\n]*\|\s*(?P<votes>[^\n]*?)\n\s*\|[^|\n]*\|\s*(?P<pct>[^\n]*?)\n", re.S)


def raw_rows(text):
    """candidate rows written as plain table markup inside an election box (substituted templates)"""
    out = []
    for chunk in re.split(r"\n\|-", text):
        m = RAW_ROW.search(chunk + "\n")
        if not m:
            continue
        name_raw = m.group("name")
        nm, inc = clean_name(name_raw)
        if not nm or re.search(r"^(total|majority|turnout|plurality)", nm, re.I):
            continue
        out.append(dict(party=clean_name(m.group("party"))[0], name=nm, inc=inc, votes=num(m.group("votes")),
                        pct=num(m.group("pct")), won="'''" in name_raw))
    return out


HEAD = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.M)
BOX_BEGIN = re.compile(r"\{\{\s*Election[ _]box[ _](?:open[ _]primary[ _])?begin", re.I)
BOX_END = re.compile(r"\{\{\s*Election[ _]box[ _]end\s*\}\}|\n\|\}", re.I)


class _Box:
    def __init__(self, start, text):
        self._s, self._t = start, text

    def start(self):
        return self._s

    def group(self, i=0):
        return self._t


def find_boxes(w):
    """each election box from its begin template to {{Election box end}}, a table close, the next box or heading"""
    begins = [m.start() for m in BOX_BEGIN.finditer(w)]
    heads = [m.start() for m in HEAD.finditer(w)]
    out = []
    for i, b in enumerate(begins):
        stop = len(w)
        if i + 1 < len(begins):
            stop = begins[i + 1]
        nh = next((h for h in heads if h > b), None)
        if nh is not None:
            stop = min(stop, nh)
        e = BOX_END.search(w, b, stop)
        end = e.end() if e else stop
        out.append(_Box(b, w[b:end]))
    return out


def election_boxes(wikitext, year, chamber, st, page, default_district=None):
    """Scan headings and election boxes in document order (each box is parsed on its own, so broken markup
    elsewhere on the page cannot hide it)."""
    events = [(m.start(), "h", m) for m in HEAD.finditer(wikitext)] + [(m.start(), "b", m) for m in find_boxes(wikitext)]
    events.sort(key=lambda x: x[0])
    rows = []
    heads, district = [], default_district
    for _, kind, m in events:
        if kind == "h":
            level, txt = len(m.group(1)), m.group(2).strip()
            d = heading_district(txt, st) if chamber == "H" else None
            if level <= 2:
                heads = [txt]
                if chamber == "H":
                    district = d if d is not None else default_district
            else:
                heads = heads[: max(1, level - 2)] + [txt]
                if chamber == "H" and d is not None and re.search(r"^(district|at-large)|congressional district", txt, re.I):
                    district = d
            continue
        code = mwp.parse(m.group(0))
        box = None
        for node in code.nodes:
            name = re.sub(r"[\s_]+", " ", str(node.name).strip().lower()) if isinstance(node, mwp.nodes.Template) else ""
            if not name.startswith("election box"):
                if box is not None:
                    box["buf"].append(str(node))
                continue
            if name.startswith("election box begin") or name.startswith("election box open primary begin"):
                title = pval(node, "title")
                stage, bp, is_open, special = box_stage(clean_name(title)[0], heads)
                if "open primary" in name:
                    stage, is_open = "P", True
                dd = district
                if chamber == "H":
                    dt = heading_district(clean_name(title)[0], st)
                    if dt is not None and re.search(r"congressional district|district \d", title, re.I):
                        dd = dt
                box = dict(title=clean_name(title)[0], stage=stage, bp=bp, open=is_open, special=special, district=dd,
                           buf=[], n=0, rows=[])
                continue
            if box is None:
                continue
            if name.startswith("election box end"):
                break
            if name.startswith("election box open primary general election"):
                if box["n"] == 0:
                    for r in raw_rows("".join(box["buf"])):
                        box["rows"].append((box["stage"], box["open"], r["name"], r["inc"], r["party"], r["votes"], r["pct"], r["won"], False))
                box["buf"], box["stage"], box["open"] = [], "G", False
                continue
            if "candidate" in name or "write-in" in name or "winning candidate" in name:
                rawc = pval(node, "candidate")
                cand, inc = clean_name(rawc)
                if not cand:
                    continue
                lk = re.search(r"\[\[\s*([^|\]#]+)", rawc)
                praw = clean_name(pval(node, "party"))[0]
                box["n"] += 1
                box["rows"].append((box["stage"], box["open"], cand, inc, praw, num(pval(node, "votes")),
                                    num(pval(node, "percentage")), "winning" in name, "write-in" in name or "write in" in name,
                                    lk.group(1).strip() if lk else ""))
        if box is None:
            continue
        if box["n"] == 0:
            for r in raw_rows("".join(box["buf"])):
                box["rows"].append((box["stage"], box["open"], r["name"], r["inc"], r["party"], r["votes"], r["pct"], r["won"], False, ""))
        for stg, op, cand, inc, praw, votes, pct, won, wi, lk in box["rows"]:
            rows.append(dict(year=year, chamber=chamber, state=st, district=box["district"] if chamber == "H" else 0,
                             stage=stg, box_party=box["bp"], open=int(op), special=int(box["special"]),
                             name=cand, party=party_code(praw), party_raw=praw, votes=votes, pct=pct, won=int(won),
                             incumbent=int(inc), writein=int(wi), title=box["title"], page=page, link=lk))
    return rows


def state_of_title(title):
    for s, a in sorted(STATE_ABBR.items(), key=lambda x: -len(x[0])):
        if re.search(r"\b" + re.escape(s) + r"\b", title):
            return a
    return None


def house_pages(year):
    out = []
    for f in sorted(glob.glob(os.path.join(WIKI, str(year), "house", "*.json"))) + \
            sorted(glob.glob(os.path.join(WIKI, str(year), "district", "*.json"))):
        p = json.load(open(f))
        st = state_of_title(p["title"].replace("Washington, D.C.", ""))
        if not st:
            continue
        default = 0 if st in AT_LARGE or " election in " in p["title"] else None
        if "/district/" in f:
            m = re.search(ORD + r" congressional district", p["title"]) or re.search(r"(at-large)", p["title"])
            default = 0 if (m and m.group(1) == "at-large") else (int(m.group(1)) if m else None)
            if "special" in p["title"].lower():
                continue
        out += election_boxes(p["wikitext"], year, "H", st, p["title"], default)
    return out


def senate_pages(year):
    out = []
    for f in sorted(glob.glob(os.path.join(WIKI, str(year), "senate", "*.json"))):
        if f.endswith("_overview.json"):
            continue
        p = json.load(open(f))
        st = state_of_title(p["title"])
        if not st:
            continue
        sp = int("special election" in p["title"].lower())
        rows = election_boxes(p["wikitext"], year, "S", st, p["title"], 0)
        for r in rows:
            r["special"] = max(r["special"], sp)
        out += rows
    return out


# ------------------------------------------------------------- overview district table (general, % only)
USHR = re.compile(r"^\s*[!|](?:[^{\n|]*\|)?\s*\{\{\s*ushr\s*\|\s*([^|}]+?)\s*\|\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}", re.I | re.M)
ITEM = re.compile(r"^\*\s*(.*)$")


def overview_house(year):
    f = os.path.join(WIKI, str(year), "overview", f"{year}_United_States_House_of_Representatives_elections.json")
    if not os.path.exists(f):
        return []
    w = json.load(open(f))["wikitext"]
    rows = []
    for m in USHR.finditer(w):
        stname, dist = m.group(1).strip(), m.group(2).strip()
        st = STATE_ABBR.get(stname) or (stname.upper() if stname.upper() in STATE_ABBR.values() else None)
        if not st:
            continue
        d = 0 if re.match(r"(?i)a\.?l\.?|at[- ]large", dist) else (int(dist) if dist.isdigit() else None)
        if d is None:
            continue
        end = w.find("\n|-", m.end())
        block = w[m.end(): end if end > 0 else m.end() + 4000]
        items = [im.group(1) for im in (ITEM.match(line.strip()) for line in block.split("\n")) if im]
        if not items:  # single candidate written in the cell itself, without a list
            items = [m2.group(0) for m2 in re.finditer(r"\{\{\s*Party stripe[^}]*\}\}[^\n]*", block, re.I)]
        for t in items:
            won = int(bool(re.search(r"\{\{\s*(?:aye|yes|check)", t, re.I)))
            pm = re.search(r"\(([^()]*)\)\s*([\d.]+)\s*%", t)
            if not pm:
                pm2 = re.search(r"\(([^()]*)\)\s*(?:'')?\s*(?:Unopposed|unopposed|Uncontested|uncontested)", t) or \
                    re.search(r"\(([^()]*)\)\s*(?:'+)?\s*$", t)
                if not pm2 or re.match(r"(?i)\s*(?:'+)?\s*(uncontested|unopposed)", t):
                    continue
                praw, pct = pm2.group(1), (100.0 if won else None)
            else:
                praw, pct = pm.group(1), float(pm.group(2))
            namepart = t[: (pm.start() if pm else pm2.start())]
            nm, inc = clean_name(namepart)
            if not nm:
                continue
            lk = re.search(r"\[\[\s*([^|\]#]+)", namepart)
            rows.append(dict(year=year, chamber="H", state=st, district=d, stage="G", box_party="", open=0, special=0,
                             name=nm, party=party_code(praw), party_raw=praw, votes=None, pct=pct, won=won, incumbent=int(inc),
                             writein=0, title="overview table", page=f"{year} United States House of Representatives elections",
                             link=lk.group(1).strip() if lk else ""))
    return rows


if __name__ == "__main__":
    import collections
    for y in (2022, 2024, 2026):
        h = house_pages(y)
        s = senate_pages(y)
        c = collections.Counter((r["stage"], r["box_party"]) for r in h)
        nd = len({(r["state"], r["district"]) for r in h if r["stage"] == "G" and r["district"] is not None})
        nonedist = sum(1 for r in h if r["district"] is None)
        print(y, "house rows", len(h), dict(c.most_common(8)), "districts with general:", nd, "rows without district:", nonedist)
        print("   senate rows", len(s), dict(collections.Counter((r["stage"], r["box_party"]) for r in s).most_common(6)))
    for y in (1990, 2000):
        o = overview_house(y)
        print(y, "overview rows", len(o), "districts", len({(r['state'], r['district']) for r in o}), "winners", sum(r["won"] for r in o))
