"""Download the raw sources for the women candidates tracker (runs on GitHub Actions).

  python pipeline/collect.py --daily   # every day: Wikipedia pages of 2024 and the current cycle, members of Congress,
                                       # CAWP file check, FEC check for a new "Federal Elections" edition
  python pipeline/collect.py --full    # everything, before python pipeline/build_db.py --rebuild-history

Sources
  FEC  "Federal Elections" publications 1990-2022: official primary, runoff and general results by candidate
  FEC  bulk candidate files (cn = candidate master, weball = all-candidate financial summary), 1990-2026
  CAWP Congressional Women Candidates Database 1990-2024 (+ codebook) and the 2026 candidate/result pages
  Wikipedia  House and Senate election pages for 2022 (to check the parser against FEC), 2024 and 2026
  Harvard Dataverse  MEDSL U.S. House / Senate returns; House primary results 1956-2010 (Pettigrew et al.)

  python pipeline/collect.py [--only fec,fecbulk,cawp,wiki,dataverse] [--years 2022 2024 2026]
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
UA = "US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"
STATIC = os.path.join(ROOT, "data", "static")
MANIFEST = []

STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
          "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
          "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
          "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
          "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
          "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def get(url, tries=4, timeout=180, accept=None):
    err = None
    for i in range(tries):
        try:
            h = {"User-Agent": UA, "Accept-Encoding": "identity"}
            if accept:
                h["Accept"] = accept
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.geturl(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (400, 401, 403, 404, 410):
                break
        except Exception as e:  # noqa: BLE001
            err = e
        time.sleep(4 * (i + 1))
    raise err


def save(rel, data, url, note=""):
    p = os.path.join(RAW, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    MANIFEST.append(dict(path=rel, url=url, bytes=len(data), note=note))
    return p


def fail(rel, url, e):
    MANIFEST.append(dict(path=rel, url=url, bytes=0, error=f"{type(e).__name__}: {e}"))
    log("  FAIL", url, e)


def fetch(rel, url, **kw):
    try:
        data, final, ctype = get(url, **kw)
    except Exception as e:  # noqa: BLE001
        fail(rel, url, e)
        return None
    save(rel, data, final, ctype)
    return data


def hrefs(page_html, base):
    out = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', page_html, re.I):
        out.append(urllib.parse.urljoin(base, html.unescape(m.group(1))))
    return out


# ---------------------------------------------------------------- FEC results publications
FEC_LIST = "https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/"


def fec_results(years):
    log("FEC Federal Elections")
    data = fetch("fec_results/index.html", FEC_LIST)
    if not data:
        return
    links = hrefs(data.decode("utf-8", "replace"), FEC_LIST)
    pages, files = {}, {}
    for u in links:
        m = re.search(r"federal-elections-(\d{4})/?$", u)
        if m:
            pages[int(m.group(1))] = u
        m = re.search(r"federalelections(\d{2,4})[^/]*\.(xlsx?)$", u, re.I)
        if m:
            y = int(m.group(1))
            y = y + (1900 if y > 50 else 2000) if y < 100 else y
            files.setdefault(y, set()).add(u)
    for y in years:
        if y in pages:
            pg = fetch(f"fec_results/{y}/page.html", pages[y])
            if pg:
                for u in hrefs(pg.decode("utf-8", "replace"), pages[y]):
                    if re.search(r"\.xlsx?(\?.*)?$", u, re.I) and ("/documents/" in u or "cms-content" in u):
                        files.setdefault(y, set()).add(u)
        for u in sorted(files.get(y, [])):
            name = os.path.basename(urllib.parse.urlparse(u).path)
            log(" ", y, name)
            fetch(f"fec_results/{y}/{name}", u)
        if not files.get(y):
            MANIFEST.append(dict(path=f"fec_results/{y}/", url=pages.get(y, ""), bytes=0, error="no files found"))


# ---------------------------------------------------------------- FEC bulk candidate files
def fec_bulk(years):
    log("FEC bulk candidate files")
    for name in ("cn_header_file.csv", "weball_header_file.csv"):
        fetch(f"fec_bulk/{name}", f"https://www.fec.gov/files/bulk-downloads/data_dictionaries/{name}")
    for y in years:
        yy = f"{y % 100:02d}"
        for name in (f"cn{yy}.zip", f"weball{yy}.zip"):
            fetch(f"fec_bulk/{y}/{name}", f"https://www.fec.gov/files/bulk-downloads/{y}/{name}")


# ---------------------------------------------------------------- CAWP
CAWP_PAGES = {
    "congress_db.html": "https://cawp.rutgers.edu/data/candidates-historic-facts-women-candidates?tab=Congress",
    "databases.html": "https://cawp.rutgers.edu/data/candidates-cawp-candidate-databases",
    "2026_list.html": "https://cawp.rutgers.edu/data/candidates-women-candidates-2026?tab=CandidateList",
    "2026_summary.html": "https://cawp.rutgers.edu/data/candidates-women-candidates-2026?tab=CandidateSummary",
    "results.html": "https://cawp.rutgers.edu/data/candidates-election-results-and-analysis-0",
}
CAWP_MASTER = "https://cawp.rutgers.edu/sites/default/files/2025-10/CONGRESS_MASTER_1990-2024.xlsx"
CAWP_CODEBOOK = "https://cawp.rutgers.edu/sites/default/files/resources/congress_statewide_codebook_external.pdf"


def cawp_master():
    """refresh data/static/cawp_master.xlsx when the CAWP file downloads and differs"""
    data = fetch("cawp/files/CONGRESS_MASTER.xlsx", CAWP_MASTER)
    dest = os.path.join(STATIC, "cawp_master.xlsx")
    if data and len(data) > 100000 and (not os.path.exists(dest) or open(dest, "rb").read() != data):
        with open(dest, "wb") as f:
            f.write(data)
        log("  CAWP file updated")


def legislators():
    log("congress-legislators")
    for f in ("legislators-current.yaml", "legislators-historical.yaml"):
        fetch(f"legislators/{f}", "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/" + f)


def baby_names():
    fetch("names/baby-names.csv", "https://raw.githubusercontent.com/hadley/data-baby-names/master/baby-names.csv")


def cawp():
    log("CAWP")
    found = set()
    follow = set()
    for name, url in CAWP_PAGES.items():
        data = fetch(f"cawp/{name}", url)
        if not data:
            continue
        for u in hrefs(data.decode("utf-8", "replace"), url):
            if re.search(r"\.(xlsx?|csv)(\?.*)?$", u, re.I) or "export" in u.lower() or "_format=csv" in u:
                found.add(u)
            if "cawp.rutgers.edu" in u and "2026" in u and re.search(r"result|primar|candidate", u, re.I):
                follow.add(u.split("#")[0])
    found.add(CAWP_MASTER)
    for u in sorted(found):
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(urllib.parse.urlparse(u).path) or "export")
        if urllib.parse.urlparse(u).query:
            name += "_" + re.sub(r"[^A-Za-z0-9]+", "_", urllib.parse.urlparse(u).query)[:60]
        fetch(f"cawp/files/{name}", u)
    fetch("cawp/codebook.pdf", CAWP_CODEBOOK)
    for i, u in enumerate(sorted(follow)[:40]):
        fetch(f"cawp/2026_pages/{i:02d}_{re.sub(r'[^A-Za-z0-9]+', '_', u.split('cawp.rutgers.edu')[-1])[:90]}.html", u)


# ---------------------------------------------------------------- Wikipedia
WAPI = "https://en.wikipedia.org/w/api.php"
DIST_LINK = re.compile(r"\[\[\s*((\d{4}) ([A-Z][A-Za-z .]+?)'s (\d+(?:st|nd|rd|th)|at-large) congressional district (?:special )?election)\s*[|\]]")
SEN_LINK = re.compile(r"\[\[\s*((\d{4})(?:[–-]\d{2})? United States Senate (?:special )?elections? in [^\]|#]+?)\s*[|\]]")


def wiki_page(title):
    q = dict(action="parse", page=title, prop="wikitext", redirects=1, format="json", formatversion=2, maxlag=5)
    data, _, _ = get(WAPI + "?" + urllib.parse.urlencode(q), tries=5, timeout=60)
    j = json.loads(data)
    if "error" in j:
        return None
    return j["parse"]


def wiki_page_checked(title, state):
    """the page, unless a redirect sent us to a page that is not about this state's House election"""
    try:
        p = wiki_page(title)
    except Exception as e:  # noqa: BLE001
        log("  FAIL", title, e)
        return None
    time.sleep(0.4)
    if not p:
        return None
    t = p["title"]
    if state not in t or not re.search(r"House of Representatives|congressional district", t):
        log("  redirect ignored:", title, "->", t)
        return None
    return p


def wiki_save(rel, title):
    try:
        p = wiki_page(title)
    except Exception as e:  # noqa: BLE001
        fail(rel, title, e)
        return None
    time.sleep(0.4)
    if not p:
        return None
    save(rel, json.dumps(p, ensure_ascii=False).encode("utf-8"), f"https://en.wikipedia.org/wiki/{urllib.parse.quote(p['title'].replace(' ', '_'))}")
    return p


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def wiki_overview(years):
    log("Wikipedia overview pages")
    for y in years:
        for t in (f"{y} United States House of Representatives elections", f"{y} United States Senate elections"):
            wiki_save(f"wiki/{y}/overview/{slug(t)}.json", t)


def wiki_senate(years):
    log("Wikipedia Senate race pages")
    for y in years:
        p = wiki_save(f"wiki/{y}/senate/_overview.json", f"{y} United States Senate elections")
        if not p:
            continue
        races = sorted({m.group(1).strip() for m in SEN_LINK.finditer(p["wikitext"]) if int(m.group(2)) == y})
        log(f"  {y}: {len(races)} Senate pages")
        for t in races:
            wiki_save(f"wiki/{y}/senate/{slug(t)}.json", t)


def wiki_people(path):
    """plain-text lead sections of candidate pages (used to tell gender from pronouns when no other source exists)"""
    if not os.path.exists(path):
        return
    titles = [t.strip() for t in open(path, encoding="utf-8") if t.strip()]
    log(f"Wikipedia people pages: {len(titles)}")
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
        q = dict(action="query", prop="extracts", exintro=1, explaintext=1, redirects=1, titles="|".join(chunk),
                 format="json", formatversion=2, maxlag=5)
        try:
            data, _, _ = get(WAPI + "?" + urllib.parse.urlencode(q), tries=5, timeout=60)
        except Exception as e:  # noqa: BLE001
            fail(f"wiki/people/batch_{i // 20:04d}.json", "batch", e)
            continue
        save(f"wiki/people/batch_{i // 20:04d}.json", data, "https://en.wikipedia.org/w/api.php")
        time.sleep(0.5)


def ssa_names():
    log("SSA baby names")
    fetch("ssa/names.zip", "https://www.ssa.gov/oact/babynames/names.zip")


def subpages(p):
    """titles of the parts a state page is split into: {{main|<page title> (districts 1–26)}}"""
    base = re.escape(p["title"])
    return sorted({m.group(1).strip() for m in re.finditer(r"\{\{\s*main\s*\|\s*(" + base + r"\s*\([^)|}]+\))", p["wikitext"], re.I)})


def wikipedia(years):
    log("Wikipedia")
    for y in years:
        districts = set()
        for st in STATES:
            p = None
            for t in (f"{y} United States House of Representatives elections in {st}",
                      f"{y} United States House of Representatives election in {st}",
                      f"{y} {st}'s at-large congressional district election"):
                p = wiki_page_checked(t, st)
                if p:
                    save(f"wiki/{y}/house/{slug(st)}.json", json.dumps(p, ensure_ascii=False).encode("utf-8"),
                         f"https://en.wikipedia.org/wiki/{urllib.parse.quote(p['title'].replace(' ', '_'))}")
                    break
            if not p:
                MANIFEST.append(dict(path=f"wiki/{y}/house/{slug(st)}.json", url="", bytes=0, error="page not found"))
                continue
            texts = [p["wikitext"]]
            # a state page split into parts ({{main|... in California (districts 1–26)}}): the parts hold the results
            for i, sub in enumerate(subpages(p)):
                q = wiki_page_checked(sub, st)
                if q:
                    save(f"wiki/{y}/house/{slug(st)}__part{i + 1}.json", json.dumps(q, ensure_ascii=False).encode("utf-8"),
                         f"https://en.wikipedia.org/wiki/{urllib.parse.quote(q['title'].replace(' ', '_'))}")
                    texts.append(q["wikitext"])
            for txt in texts:
                for m in DIST_LINK.finditer(txt):
                    if int(m.group(2)) == y:
                        districts.add(m.group(1).strip())
        log(f"  {y}: {len(districts)} district pages")
        for t in sorted(districts):
            wiki_save(f"wiki/{y}/district/{slug(t)}.json", t)
        senate = set()
        for t in (f"{y} United States Senate elections",):
            p = wiki_save(f"wiki/{y}/senate/_overview.json", t)
            if p:
                for m in SEN_LINK.finditer(p["wikitext"]):
                    if int(m.group(2)) == y:
                        senate.add(m.group(1).strip())
        log(f"  {y}: {len(senate)} Senate pages")
        for t in sorted(senate):
            wiki_save(f"wiki/{y}/senate/{slug(t)}.json", t)


# ---------------------------------------------------------------- Harvard Dataverse
DV = "https://dataverse.harvard.edu"
DV_DOIS = {"medsl_house": "doi:10.7910/DVN/IG0UN2", "medsl_senate": "doi:10.7910/DVN/PEJ5QU"}


def dv_dataset(key, pid, max_mb=80):
    try:
        data, _, _ = get(f"{DV}/api/datasets/:persistentId/?persistentId={urllib.parse.quote(pid)}")
    except Exception as e:  # noqa: BLE001
        fail(f"dataverse/{key}/", pid, e)
        return
    j = json.loads(data)["data"]
    save(f"dataverse/{key}/_dataset.json", json.dumps(j, ensure_ascii=False).encode("utf-8"), pid)
    for f in j["latestVersion"]["files"]:
        df = f["dataFile"]
        if f.get("restricted") or df.get("filesize", 0) > max_mb * 1e6:
            MANIFEST.append(dict(path=f"dataverse/{key}/{df['filename']}", url=pid, bytes=0, error="restricted or too big"))
            continue
        fmt = "?format=original" if df.get("originalFileFormat") else ""
        name = df.get("originalFileName") or df["filename"]
        log(" ", key, name)
        fetch(f"dataverse/{key}/{name}", f"{DV}/api/access/datafile/{df['id']}{fmt}")


def dataverse():
    log("Dataverse")
    for k, pid in DV_DOIS.items():
        dv_dataset(k, pid)
    # House primary results 1956-2010 (Pettigrew, Owen and Wanless)
    try:
        q = urllib.parse.urlencode(dict(q='"House Primary Election Results"', type="dataset", per_page=20))
        data, _, _ = get(f"{DV}/api/search?{q}")
        items = json.loads(data)["data"]["items"]
        save("dataverse/_search_primaries.json", json.dumps(items, ensure_ascii=False).encode("utf-8"), q)
        for it in items:
            if re.search(r"House Primary Election Results", it.get("name", ""), re.I):
                dv_dataset("house_primaries_" + slug(it["global_id"].split("/")[-1]), it["global_id"])
    except Exception as e:  # noqa: BLE001
        fail("dataverse/_search_primaries.json", "search", e)


def main():
    import datetime as dt
    today = dt.date.today()
    last = today.year if today.year % 2 == 0 else today.year - 1
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--years", nargs="*", type=int, default=[2022, 2024, 2026], help="Wikipedia House/Senate years")
    ap.add_argument("--overview-years", nargs="*", type=int, default=list(range(1990, 2028, 2)))
    ap.add_argument("--senate-years", nargs="*", type=int, default=list(range(1990, 2002, 2)))
    ap.add_argument("--people-file", default=os.path.join(ROOT, "collect_people.txt"))
    a = ap.parse_args()
    only = set(x for x in a.only.split(",") if x)
    if a.daily or a.full:
        a.years = sorted({2024, last})
        only |= {"wiki", "wiki_overview_current", "legislators", "cawp_master", "fec_current"}
    if a.full:
        only |= {"fec", "fecbulk", "dataverse", "wiki_overview", "wiki_senate", "names"}
        a.overview_years = list(range(1990, last + 2, 2))
    if "legislators" in only:
        legislators()
    if "names" in only:
        baby_names()
    if "cawp_master" in only:
        cawp_master()
    if "fec_current" in only and "fec" not in only:
        fec_results(list(range(2024, last + 2, 2)))
    if "wiki_overview_current" in only and "wiki_overview" not in only:
        wiki_overview(a.years)
    if "wiki_people" in only:
        wiki_people(a.people_file)
    if "wiki_overview" in only:
        wiki_overview(a.overview_years)
    if "wiki_senate" in only:
        wiki_senate(a.senate_years)
    if "ssa" in only:
        ssa_names()
    if "fec" in only:
        fec_results(list(range(1990, last + 2, 2)))
    if "fecbulk" in only:
        fec_bulk(list(range(1990, last + 2, 2)))
    if "cawp" in only:
        cawp()
    if "wiki" in only:
        wikipedia(a.years)
    if "dataverse" in only:
        dataverse()
    os.makedirs(RAW, exist_ok=True)
    old = []
    mp = os.path.join(RAW, "manifest.json")
    if os.path.exists(mp):
        old = [m for m in json.load(open(mp)) if m["path"] not in {x["path"] for x in MANIFEST}]
    with open(mp, "w") as f:
        json.dump(old + MANIFEST, f, indent=1)
    bad = [m for m in MANIFEST if m.get("error")]
    log(f"done: {len(MANIFEST) - len(bad)} files, {len(bad)} problems")
    for m in bad:
        log("  problem:", m["path"], m.get("error"))


if __name__ == "__main__":
    sys.exit(main())
