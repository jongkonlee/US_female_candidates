"""Race and ethnicity of members of Congress, from Wikipedia's lists of minority members (for the male candidates of the
CES models; women candidates have CAWP's codes).

Runs in GitHub Actions (workflow 'CES individual models'), because the workspace cannot reach Wikipedia. For each list
the rendered page is read through the MediaWiki API; in every row of its tables only the first four cells are used
(the member's name cell; the notes column, which can name other people, is never read), links are resolved through
redirects and matched to congress-legislators by the Wikipedia page name.

Output: data/static/member_race.csv  bioguide, name, wikipedia, race (CAWP-style codes joined by '/': B, H, AP, NA, MENA),
        lists (where found); data/static/member_race_meta.json (pages read, rows, names not matched).
Members of Congress on none of the lists are treated as white by pipeline/ces_models.py (an inference, marked there).
"""
import collections
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request

import yaml
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "static", "member_race.csv")
META = os.path.join(ROOT, "data", "static", "member_race_meta.json")
API = "https://en.wikipedia.org/w/api.php"
UA = "US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"
LISTS = {  # code -> page names to try (the first that exists is read)
    "B": [["List of African-American United States representatives"], ["List of African-American United States senators"]],
    "H": [["List of Hispanic and Latino Americans in the United States Congress"]],
    "AP": [["List of Asian Americans and Pacific Islands Americans in the United States Congress",
            "List of Asian Americans and Pacific Islanders in the United States Congress"]],
    "NA": [["List of Native Americans in the United States Congress"]],
    "MENA": [["List of Arab and Middle Eastern Americans in the United States Congress",
              "List of Arab and Middle-Eastern Americans in the United States Congress"]],
}
LEGIS = ["legislators-current.yaml", "legislators-historical.yaml"]


def get(params):
    url = API + "?" + urllib.parse.urlencode(dict(params, format="json", formatversion=2, maxlag=5))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.loads(r.read())
            time.sleep(1)  # one request a second: Wikipedia answered 429 (too many requests) to a faster pace
            return out
        except Exception as e:  # noqa: BLE001
            print("  retry", i + 1, type(e).__name__, e, flush=True)
            time.sleep(10 * (i + 1))
    raise RuntimeError("not reachable: " + url)


def legislators():
    folder = os.environ.get("LEGIS_DIR") or os.path.join(ROOT, "data", "raw", "legislators")
    out = []
    for f in LEGIS:
        p = os.path.join(folder, f)
        if not os.path.exists(p):
            os.makedirs(folder, exist_ok=True)
            req = urllib.request.Request("https://raw.githubusercontent.com/unitedstates/congress-legislators/main/" + f, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(p, "wb") as w:
                w.write(r.read())
        out += yaml.load(open(p, encoding="utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    return out


def norm(t):
    t = urllib.parse.unquote(t).replace("_", " ").strip()
    return t[:1].upper() + t[1:] if t else t


def page_links(page):
    """links in the first four cells of every table row of the page"""
    d = get(dict(action="parse", page=page, prop="text", redirects=1))
    if "error" in d:
        return None, d["error"].get("code")
    soup = BeautifulSoup(d["parse"]["text"], "lxml")
    links, rows = [], 0
    for table in soup.find_all("table"):
        if "wikitable" not in (table.get("class") or []):
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"], recursive=False)
            if not cells or all(c.name == "th" and c.get("scope") != "row" for c in cells):
                continue  # header row
            rows += 1
            for c in cells[:4]:
                for a in c.find_all("a", href=True):
                    m = re.match(r"^/wiki/([^#?]+)", a["href"])
                    if m and ":" not in m.group(1):
                        links.append(norm(m.group(1)))
    return dict(page=d["parse"]["title"], rows=rows, links=links), None


def resolve(titles):
    """title -> canonical title after redirects"""
    out = {}
    titles = sorted(set(titles))
    for i in range(0, len(titles), 50):
        d = get(dict(action="query", titles="|".join(titles[i:i + 50]), redirects=1))
        q = d.get("query", {})
        nmap = {x["from"]: x["to"] for x in q.get("normalized", [])}
        rmap = {x["from"]: x["to"] for x in q.get("redirects", [])}
        for t in titles[i:i + 50]:
            u = nmap.get(t, t)
            out[t] = rmap.get(u, u)
    return out


def main():
    legis = legislators()
    by_wiki = {}
    for p in legis:
        w = (p.get("id", {}).get("wikipedia") or "").replace("_", " ").strip()
        if w:
            by_wiki[norm(w)] = p
    meta, found = dict(pages={}, unmatched={}), collections.defaultdict(set)
    allinks = {}
    for code, groups in LISTS.items():
        for names in groups:
            res = None
            for name in names:
                res, err = page_links(name)
                if res:
                    break
                print("  no page", name, err, flush=True)
            if not res:
                meta["pages"][names[0]] = "not found"
                continue
            allinks[(code, res["page"])] = res["links"]
            meta["pages"][res["page"]] = dict(code=code, rows=res["rows"], links=len(res["links"]))
            print(code, res["page"], "rows", res["rows"], "links", len(res["links"]), flush=True)
    canon = resolve([t for v in allinks.values() for t in v])
    # the members' own page names can be old redirects too
    leg_canon = resolve(list(by_wiki))
    by_canon = {leg_canon.get(k, k): p for k, p in by_wiki.items()}
    for (code, page), links in allinks.items():
        miss = []
        for t in dict.fromkeys(links):
            p = by_canon.get(canon.get(t, t)) or by_wiki.get(t)
            if p is None:
                miss.append(t)
                continue
            found[p["id"]["bioguide"]].add((code, page))
        meta["unmatched"][page] = miss  # mostly states, parties, districts and dates linked in the same cells
    rows = []
    for p in legis:
        b = p["id"]["bioguide"]
        if b not in found:
            continue
        nm = p.get("name", {})
        codes = sorted({c for c, _ in found[b]}, key=list(LISTS).index)
        rows.append(dict(bioguide=b, name=nm.get("official_full") or f"{nm.get('first', '')} {nm.get('last', '')}",
                         wikipedia=p["id"].get("wikipedia", ""), race="/".join(codes), lists="; ".join(sorted({pg for _, pg in found[b]}))))
    rows.sort(key=lambda r: r["bioguide"])
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["bioguide", "name", "wikipedia", "race", "lists"])
        w.writeheader()
        w.writerows(rows)
    meta["members"] = len(rows)
    meta["by_code"] = {c: sum(1 for r in rows if c in r["race"].split("/")) for c in LISTS}
    meta["downloaded"] = time.strftime("%Y-%m-%d")
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("members with a code:", len(rows), meta["by_code"], flush=True)


if __name__ == "__main__":
    main()
