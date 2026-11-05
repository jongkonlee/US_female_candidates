"""House votes of women and men respondents by district, from the ANES Time Series Cumulative Data File.

ANES (American National Election Studies, electionstudies.org). Runs in GitHub Actions (the workflow "fetch ANES House
votes"), because the workspace cannot reach electionstudies.org. It
  1. reads the cumulative file's page and finds the Stata download (logs every link, so a login wall would show),
  2. downloads it and records the labels and codes of the variables used, and in which years the respondent's
     congressional district is filled in,
  3. keeps only counts, no individual rows: data/static/anes/anes_house_cells.csv.gz with year, state, district,
     gender (F/M), pid3 (D/R/I), vote (D/R/O), n, w (sum of weights), w2 (sum of squared weights),
     and data/static/anes/meta.json.
ANES terms: use for research or statistical purposes only, not to investigate specific respondents; cite ANES.
"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "static", "anes")
PAGE = "https://electionstudies.org/data-center/anes-time-series-cumulative-data-file/"
UA = "Mozilla/5.0 (X11; Linux x86_64) US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"
TMP = os.environ.get("RUNNER_TEMP", "/tmp")
VARS = dict(year="VCF0004", gender="VCF0104", state="VCF0901b", fips="VCF0901a", district="VCF0900", vote="VCF0736",
            vote2="VCF0707", pid3="VCF0303", weight="VCF0009z", weight_x="VCF0009x")


def get(url, binary=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read(), r.headers.get("Content-Type", ""), r.geturl()
        except Exception as e:  # noqa: BLE001
            print("  retry", i + 1, type(e).__name__, e, flush=True)
            time.sleep(10 * (i + 1))
    raise RuntimeError("not reachable: " + url)


def links(html, base):
    out = []
    for m in re.finditer(r'href="([^"]+)"', html):
        u = urllib.parse.urljoin(base, m.group(1))
        if u not in out:
            out.append(u)
    return out


def find_stata(meta):
    html, ctype, final = get(PAGE)
    html = html.decode("utf-8", "replace")
    ls = links(html, final)
    cand = [u for u in ls if re.search(r"cdf", u, re.I)]
    meta["page_links_cdf"] = cand
    print("links mentioning cdf:", *cand, sep="\n  ", flush=True)
    order = [u for u in cand if re.search(r"stata|dta", u, re.I)] + [u for u in cand if re.search(r"\.zip|csv", u, re.I)]
    for u in order:
        body, ctype, final = get(u)
        print("try", u, "->", final, ctype, len(body), flush=True)
        if body[:2] == b"PK":
            return u, final, body
        # an attachment page may link to the file itself
        sub = [x for x in links(body.decode("utf-8", "replace"), final) if re.search(r"\.zip($|\?)", x, re.I)]
        for x in sub:
            b2, c2, f2 = get(x)
            print("  try", x, "->", f2, c2, len(b2), flush=True)
            if b2[:2] == b"PK":
                return x, f2, b2
        meta.setdefault("not_files", []).append(dict(url=u, final=final, type=ctype, head=body[:300].decode("utf-8", "replace")))
    return None, None, None


def label_map(labels, code_words):
    """value -> D/R/O (or F/M) from the Stata value labels"""
    out = {}
    for v, lab in labels.items():
        s = str(lab).lower()
        for key, words in code_words:
            if any(w in s for w in words):
                out[v] = key
                break
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = dict(source="ANES Time Series Cumulative Data File", page=PAGE, downloaded=time.strftime("%Y-%m-%d"),
                terms="Use solely for research or statistical purposes and not for investigation of specific survey respondents; cite ANES data and documentation.")
    url, final, body = find_stata(meta)
    if body is None:
        json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
        raise SystemExit("no downloadable Stata file found (see the log and meta.json)")
    meta["file_url"] = final
    z = zipfile.ZipFile(io.BytesIO(body))
    names = z.namelist()
    meta["zip_files"] = names
    dta = [n for n in names if n.lower().endswith(".dta")]
    if not dta:
        json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
        raise SystemExit("no .dta in the zip: " + ", ".join(names))
    path = os.path.join(TMP, os.path.basename(dta[0]))
    open(path, "wb").write(z.read(dta[0]))
    meta["file"] = os.path.basename(dta[0])
    with pd.read_stata(path, iterator=True, convert_categoricals=False) as rd:
        vlab = rd.variable_labels()
        vals = rd.value_labels()
        lab_of = rd._lbllist if hasattr(rd, "_lbllist") else None
        cols = list(vlab)
    use = {k: v for k, v in VARS.items() if v in cols}
    meta["variables"] = {k: dict(name=v, label=vlab.get(v)) for k, v in use.items()}
    # value labels of the variables used (Stata label set names usually equal the variable names)
    meta["value_labels"] = {v: {str(a): str(b) for a, b in vals.get(v, {}).items()} for v in use.values() if v in vals}
    print(json.dumps(meta["variables"], indent=1), flush=True)
    print(json.dumps(meta["value_labels"], indent=1)[:6000], flush=True)
    need = ["year", "gender", "district", "vote"]
    if any(k not in use for k in need) or ("state" not in use and "fips" not in use):
        json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
        raise SystemExit("variables missing: " + ", ".join(k for k in need if k not in use))
    df = pd.read_stata(path, columns=list(use.values()), convert_categoricals=False)
    yr = pd.to_numeric(df[use["year"]], errors="coerce")
    dist = pd.to_numeric(df[use["district"]], errors="coerce")
    meta["district_filled_by_year"] = {int(y): int(((dist.notna()) & (~dist.isin([0, 98, 99])))[yr == y].sum()) for y in sorted(yr.dropna().unique())}
    print("district filled by year:", meta["district_filled_by_year"], flush=True)
    vl = meta["value_labels"]
    gmap = label_map(vl.get(use["gender"], {}), [("F", ["female"]), ("M", ["male"])]) or {"1": "M", "2": "F"}
    vmap = label_map(vl.get(use["vote"], {}), [("D", ["democrat"]), ("R", ["republican"]), ("O", ["other", "minor", "third"])])
    pmap = label_map(vl.get(use.get("pid3", ""), {}), [("D", ["democrat"]), ("R", ["republican"]), ("I", ["independent"])])
    meta["maps"] = dict(gender=gmap, vote=vmap, pid3=pmap)
    st = df[use["state"]].astype(str).str.strip().str.upper() if "state" in use else None
    w = pd.to_numeric(df[use["weight"]], errors="coerce") if "weight" in use else pd.Series(1.0, index=df.index)
    if "weight_x" in use:
        w = w.fillna(pd.to_numeric(df[use["weight_x"]], errors="coerce"))
    cells = pd.DataFrame(dict(
        year=yr, state=st, district=dist,
        gender=pd.to_numeric(df[use["gender"]], errors="coerce").map(lambda v: gmap.get(str(int(v))) if pd.notna(v) else None),
        vote=pd.to_numeric(df[use["vote"]], errors="coerce").map(lambda v: vmap.get(str(int(v))) if pd.notna(v) else None),
        pid3=(pd.to_numeric(df[use["pid3"]], errors="coerce").map(lambda v: pmap.get(str(int(v)), "I") if pd.notna(v) else "I") if "pid3" in use else "I"),
        w=w.fillna(1.0)))
    cells = cells.dropna(subset=["year", "state", "district", "gender", "vote"])
    cells = cells[(cells.year >= 1990) & (cells.year % 2 == 0) & (~cells.district.isin([98, 99])) & (cells.state.str.len() == 2)]
    cells["year"] = cells.year.astype(int)
    cells["district"] = cells.district.astype(int)
    ones = cells.groupby(["year", "state"]).district.transform("max") <= 1  # at large: the tracker uses 0
    cells.loc[ones, "district"] = 0
    cells["w2"] = cells.w ** 2
    agg = (cells.groupby(["year", "state", "district", "gender", "pid3", "vote"]).agg(n=("w", "size"), w=("w", "sum"), w2=("w2", "sum"))
           .reset_index())
    agg["w"] = agg.w.round(4)
    agg["w2"] = agg.w2.round(4)
    agg.to_csv(os.path.join(OUT, "anes_house_cells.csv.gz"), index=False, compression="gzip")
    meta["rows_by_year"] = {int(y): int(n) for y, n in cells.groupby("year").size().items()}
    meta["cells"] = len(agg)
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    print("respondents with a House vote and a district, by year:", meta["rows_by_year"], flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
