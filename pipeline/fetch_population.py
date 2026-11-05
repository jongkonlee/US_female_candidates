"""Fetch the 2020 census block-group centers of population (U.S. Census Bureau, public domain).

Each row is one block group with its 2020 population and its population-weighted center. pipeline/lineage.py uses these
points to measure how many residents two House districts share (the same 2020 population is used for every year).
Runs in GitHub Actions (the workflow "fetch census population points"); saves data/static/cenpop2020_bg.csv.gz plus a
small manifest.
"""
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "static", "cenpop2020_bg.csv.gz")
URL = "https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG.txt"
PAGE = "https://www.census.gov/geographies/reference-files/time-series/geo/centers-population.html"
UA = "US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print("  retry", i + 1, type(e).__name__, e)
            time.sleep(10 * (i + 1))
    raise RuntimeError("census.gov not reachable")


def main():
    raw = get(URL)
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    need = {"STATEFP", "COUNTYFP", "TRACTCE", "BLKGRPCE", "POPULATION", "LATITUDE", "LONGITUDE"}
    if not rows or not need <= set(rows[0]):
        raise SystemExit(f"unexpected columns: {list(rows[0]) if rows else 'no rows'}")
    pop = sum(int(r["POPULATION"]) for r in rows if r["STATEFP"] != "72")
    print("block groups", len(rows), "population (50 states + DC)", pop)
    if len(rows) < 200000 or not 330_000_000 < pop < 332_000_000:
        raise SystemExit("row count or population looks wrong")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["statefp", "countyfp", "tractce", "blkgrpce", "pop", "lat", "lon"])
    for r in rows:
        w.writerow([r["STATEFP"], r["COUNTYFP"], r["TRACTCE"], r["BLKGRPCE"], r["POPULATION"], r["LATITUDE"], r["LONGITUDE"]])
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(buf.getvalue())
    man = dict(source=URL, page=PAGE, publisher="U.S. Census Bureau, 2020 Census centers of population by block group",
               downloaded=dt.date.today().isoformat(), md5_original=hashlib.md5(raw).hexdigest(), rows=len(rows),
               population_states_dc=pop)
    with open(OUT.replace(".csv.gz", ".json"), "w") as f:
        json.dump(man, f, indent=1)
    print(man)


if __name__ == "__main__":
    main()
