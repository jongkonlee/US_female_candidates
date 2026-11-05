"""House votes of women and men respondents by district, from the Cooperative Election Study (cumulative file).

Source: Shiro Kuriwaki, "Cumulative CES Common Content", Harvard Dataverse, doi:10.7910/DVN/II2DB6. Runs in GitHub
Actions (the workflow "fetch CES House votes"), because the workspace cannot reach Dataverse. Only counts are kept,
no individual rows:

  data/static/ces/ces_house_cells.csv.gz  year, state, district, gender (F/M), pid3 (D/R/I), vote (D/R/O),
                                          n (respondents), w (sum of the year's survey weights)
  data/static/ces/meta.json               dataset version, license or terms, file used, columns used, rows per year

Respondents count when they reported a House vote after the election (voted_rep_party or the closest column). The
district is the one on the ballot (the "upcoming" district column when the file has one).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "static", "ces")
API = "https://dataverse.harvard.edu/api"
DOI = "doi:10.7910/DVN/II2DB6"
UA = "US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"
TMP = os.environ.get("RUNNER_TEMP", "/tmp")
STATES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT",
          "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
          "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
          "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
          "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
          "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
          "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
          "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC"}


def get(url, path=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                if path is None:
                    return r.read()
                with open(path, "wb") as f:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        f.write(b)
                return path
        except Exception as e:  # noqa: BLE001
            print("  retry", i + 1, type(e).__name__, e, flush=True)
            time.sleep(15 * (i + 1))
    raise RuntimeError("not reachable: " + url)


def pick(files):
    """the cumulative data file: parquet, feather, Stata, R or tab, largest first within a format"""
    order = [r"\.parquet$", r"\.feather$", r"\.dta$", r"\.tab$"]
    for pat in order:
        c = [f for f in files if re.search(pat, f["name"], re.I) and re.search(r"cumulative|cces|ces", f["name"], re.I)]
        if c:
            return max(c, key=lambda f: f["size"] or 0)
    raise SystemExit("no data file found: " + ", ".join(f["name"] for f in files))


def read(path, name, cols=None):
    """the columns asked for, or (cols None) an empty frame with the file's columns, read from the schema only"""
    if name.lower().endswith(".parquet"):
        if cols is None:
            import pyarrow.parquet as pq
            return pd.DataFrame(columns=pq.read_schema(path).names)
        return pd.read_parquet(path, columns=cols)
    if name.lower().endswith(".feather"):
        if cols is None:
            import pyarrow.ipc as ipc
            return pd.DataFrame(columns=ipc.open_file(path).schema.names)
        return pd.read_feather(path, columns=cols)
    if name.lower().endswith(".dta"):
        if cols is None:
            with pd.read_stata(path, iterator=True) as it:
                return it.read(5)
        parts = []
        with pd.read_stata(path, columns=cols, iterator=True, chunksize=200_000) as it:
            for ch in it:
                parts.append(ch)
        return pd.concat(parts, ignore_index=True)
    return pd.read_csv(path, sep="\t", usecols=cols, low_memory=False)


def first(cols, *names):
    for n in names:
        if n in cols:
            return n
    return None


def norm_gender(v):
    s = str(v).strip().lower()
    if s in ("female", "woman", "2", "2.0", "f"):
        return "F"
    if s in ("male", "man", "1", "1.0", "m"):
        return "M"
    return None


def norm_party(v):
    s = str(v).strip().lower()
    if s.startswith("democrat") or s in ("d", "dem"):
        return "D"
    if s.startswith("republican") or s in ("r", "rep"):
        return "R"
    if s in ("", "nan", "none", "<na>") or "not vote" in s or "didn't vote" in s or "did not" in s or "not sure" in s or "skipped" in s or "no one" in s:
        return None
    return "O"


def norm_pid(v):
    s = str(v).strip().lower()
    if s.startswith("democrat"):
        return "D"
    if s.startswith("republican"):
        return "R"
    return "I"


def main():
    os.makedirs(OUT, exist_ok=True)
    q = urllib.parse.quote(DOI, safe="")
    meta = json.loads(get(f"{API}/datasets/:persistentId/?persistentId={q}"))["data"]
    ver = meta["latestVersion"]
    files = [dict(id=f["dataFile"]["id"], name=f["dataFile"].get("filename") or f.get("label"), size=f["dataFile"].get("filesize"),
                  type=f["dataFile"].get("contentType"), md5=(f["dataFile"].get("checksum") or {}).get("value")) for f in ver["files"]]
    info = dict(source=DOI, citation="Kuriwaki, Shiro. Cumulative CES Common Content. Harvard Dataverse. https://doi.org/10.7910/DVN/II2DB6",
                version=f"{ver.get('versionNumber')}.{ver.get('versionMinorNumber')}", release=ver.get("releaseTime"),
                license=ver.get("license"), terms=ver.get("termsOfUse"), files=files, downloaded=time.strftime("%Y-%m-%d"))
    f = pick(files)
    print("dataset version", info["version"], "license", info["license"], "| using", f["name"], f["size"], flush=True)
    path = os.path.join(TMP, f["name"])
    url = f"{API}/access/datafile/{f['id']}" + ("?format=original" if f["name"].lower().endswith(".tab") else "")
    get(url, path)
    head = read(path, f["name"])
    cols = list(head.columns)
    info["file"] = f["name"]
    info["columns"] = cols
    c = dict(year=first(cols, "year"), weight=first(cols, "weight", "weight_cumulative"), st=first(cols, "st", "state"),
             dist=first(cols, "dist_up", "dist"), cd=first(cols, "cd_up", "cd"), gender=first(cols, "gender", "gender4"),
             vote=first(cols, "voted_rep_party", "voted_rep"), pid=first(cols, "pid3"))
    info["used"] = c
    print("columns used", c, flush=True)
    missing = [k for k in ("year", "weight", "gender", "vote") if not c[k]] + ([] if c["dist"] or c["cd"] else ["district"])
    if missing:
        json.dump(info, open(os.path.join(OUT, "meta.json"), "w"), indent=1, default=str)
        raise SystemExit(f"columns not found: {missing}; all columns saved to meta.json")
    use = sorted({v for v in c.values() if v})
    df = read(path, f["name"], use)
    df = df[pd.to_numeric(df[c["year"]], errors="coerce") % 2 == 0].copy()  # House elections
    df["year_"] = pd.to_numeric(df[c["year"]], errors="coerce").astype(int)
    if c["st"]:
        s = df[c["st"]].astype(str).str.strip()
        df["st_"] = s.map(lambda x: STATES.get(x, x if len(x) == 2 else None))
    if c["dist"]:
        df["dist_"] = pd.to_numeric(df[c["dist"]], errors="coerce")
    else:
        df["dist_"] = None
    if c["cd"]:  # "CA-12" strings fill state and district where the numeric columns are empty
        m = df[c["cd"]].astype(str).str.extract(r"^([A-Z]{2})-?(\d+)")
        if not c["st"]:
            df["st_"] = m[0]
        df["dist_"] = df["dist_"].fillna(pd.to_numeric(m[1], errors="coerce"))
    df["gender_"] = df[c["gender"]].map(norm_gender)
    df["vote_"] = df[c["vote"]].map(norm_party)
    df["pid_"] = df[c["pid"]].map(norm_pid) if c["pid"] else "I"
    df["w_"] = pd.to_numeric(df[c["weight"]], errors="coerce")
    info["values"] = {k: {str(a): int(b) for a, b in df[v].astype(str).value_counts().head(25).items()} for k, v in c.items() if v and k in ("gender", "vote", "pid")}
    ok = df.dropna(subset=["st_", "dist_", "gender_", "vote_", "w_"])
    ok = ok[ok.st_.str.len() == 2]
    ok["dist_"] = ok.dist_.astype(int)
    # at-large districts: the file may code them 1; the tracker uses 0
    ones = ok.groupby(["year_", "st_"]).dist_.transform("max") == 1
    ok.loc[ones, "dist_"] = 0
    cells = (ok.groupby(["year_", "st_", "dist_", "gender_", "pid_", "vote_"]).agg(n=("w_", "size"), w=("w_", "sum")).reset_index()
             .rename(columns={"year_": "year", "st_": "state", "dist_": "district", "gender_": "gender", "pid_": "pid3", "vote_": "vote"}))
    cells["w"] = cells.w.round(3)
    cells.to_csv(os.path.join(OUT, "ces_house_cells.csv.gz"), index=False, compression="gzip")
    info["rows_by_year"] = {int(y): int(n) for y, n in ok.groupby("year_").size().items()}
    info["cells"] = len(cells)
    json.dump(info, open(os.path.join(OUT, "meta.json"), "w"), indent=1, default=str)
    print("respondents with a House vote by year:", info["rows_by_year"], "| cells", len(cells), flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
