"""How many residents House districts share across elections (for "linked districts" back to the 1990 election).

For every House election from 1990 to 2026 and every district in it, this measures what share of the district's
residents lived in each district of every earlier Congress, from the 101st (in office at the 1990 election) on.

Residents: 2020 census block groups (U.S. Census Bureau, centers of population by block group, public domain;
data/static/cenpop2020_bg.csv.gz from pipeline/fetch_population.py). Each block group's 2020 population is placed at its
population center and counted in the district whose shape contains that point (points that fall outside every shape,
for example on a coastline, go to the nearest district of the same state). The same 2020 population is used for every
year, so shares for older maps are an approximation.

Boundaries: Lewis, DeVine, Pitcher & Martis, Digital Boundary Definitions of U.S. Congressional Districts (GitHub
GeoJson, MIT), 101st-119th Congress. 2026 (120th): the new districts of the states in maps.NEW_2026
(data/static/boundaries_2026, Wikimedia Commons map data, CC0); every other district as in the 119th Congress.

Boundaries do not change, so this runs by hand:
  git clone --depth 1 https://github.com/JeffreyBLewis/congressional-district-boundaries.git /tmp/lewis
  python pipeline/lineage.py --lewis /tmp/lewis/GeoJson

Output data/static/lineage_overlap.csv.gz, one row per (election, district, earlier Congress, earlier district):
  year            election year of the district (1990 ... 2026)
  state, district district in that election (0 = at large)
  pop             2020 residents of the district (block-group approximation)
  congress        earlier Congress (101 ... the one in office at the election)
  prior_district  district of that Congress
  share           % of the district's residents who live in prior_district (rows under 0.5% are left out)
"""
import argparse
import collections
import csv
import glob
import gzip
import json
import os
import re
import sys

import numpy as np
import shapely
from shapely.geometry import shape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maps as MP  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POP = os.path.join(ROOT, "data", "static", "cenpop2020_bg.csv.gz")
OUT = os.path.join(ROOT, "data", "static", "lineage_overlap.csv.gz")
FIRST_C, LAST_LEWIS, LAST_C = 101, 119, 120
YEARS = list(range(1990, 2027, 2))
MIN_SHARE = 0.5


def congress_of(year):
    return (year - 1788) // 2 + 1


def load_points():
    acc = collections.defaultdict(lambda: ([], [], []))
    with gzip.open(POP, "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            st = MP.FIPS.get(r["statefp"])
            p = int(r["pop"])
            if st and p > 0:
                acc[st][0].append(float(r["lon"]))
                acc[st][1].append(float(r["lat"]))
                acc[st][2].append(p)
    return {st: (np.array(x), np.array(y), np.array(w, dtype=np.int64)) for st, (x, y, w) in acc.items()}


def load_lewis(lewis_dir):
    """state -> [(district, first congress, last congress, geometry)] for the 101st-119th Congresses"""
    out = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(lewis_dir, "*.geojson"))):
        m = re.match(r"(.+)_(\d+)_to_(\d+)\.geojson$", os.path.basename(f))
        if not m or int(m.group(3)) < FIRST_C or int(m.group(2)) > LAST_LEWIS:
            continue
        for ft in json.load(open(f))["features"]:
            p = ft["properties"]
            st = MP.FIPS.get(str(p.get("statefp") or "").zfill(2)) or MP.NAMES.get(str(p.get("statename") or "").strip())
            a, b = max(FIRST_C, int(p["startcong"])), min(LAST_LEWIS, int(p["endcong"]))
            if st and a <= b and ft.get("geometry"):
                g = shape(ft["geometry"])
                if not g.is_valid:
                    g = shapely.make_valid(g)
                out[st].append((int(float(p["district"] or 0)), a, b, g))
    return out


def load_new():
    out = collections.defaultdict(list)
    for st, d, _, _, geom in MP.load_2026():
        g = shape(geom)
        out[st].append((d, g if g.is_valid else shapely.make_valid(g)))
    return out


def state_maps(feats, new):
    """congress -> {district: [geometries]} for the 101st-120th Congresses"""
    by = {}
    for c in range(FIRST_C, LAST_LEWIS + 1):
        m = collections.defaultdict(list)
        for d, a, b, g in feats:
            if a <= c <= b:
                m[d].append(g)
        by[c] = dict(m)
    m120 = {d: list(gs) for d, gs in by[LAST_LEWIS].items()}
    redrawn = collections.defaultdict(list)
    for d, g in new:
        redrawn[d].append(g)
    m120.update(redrawn)  # districts redrawn for 2026 replace the 119th shapes; the rest keep them
    by[LAST_C] = m120
    return by


def assign(x, y, dm):
    """district of each point under one map; points outside every shape go to the nearest district"""
    out = np.full(len(x), -1, dtype=np.int32)
    for d in sorted(dm):
        for g in dm[d]:
            shapely.prepare(g)
            hit = (out == -1) & shapely.contains_xy(g, x, y)
            out[hit] = d
    miss = np.where(out == -1)[0]
    if len(miss):
        pts = shapely.points(x[miss], y[miss])
        ds = sorted(dm)
        dist = np.vstack([np.min(np.vstack([shapely.distance(g, pts) for g in dm[d]]), axis=0) for d in ds])
        out[miss] = np.array(ds)[np.argmin(dist, axis=0)]
    return out, len(miss)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lewis", required=True, help="GeoJson folder of the Lewis et al. boundary repository")
    a = ap.parse_args()
    pts = load_points()
    lewis = load_lewis(a.lewis)
    new = load_new()
    rows, log = [], []
    for st in sorted(pts):
        x, y, w = pts[st]
        by = state_maps(lewis.get(st, []), new.get(st, []))
        cache, asg, missed = {}, {}, {}
        for c in range(FIRST_C, LAST_C + 1):
            if not by[c]:
                raise SystemExit(f"{st}: no districts for Congress {c}")
            key = tuple(sorted((d, tuple(id(g) for g in gs)) for d, gs in by[c].items()))
            if key not in cache:
                cache[key] = assign(x, y, by[c])
            asg[c], missed[c] = cache[key]
        for year in YEARS:
            cb = congress_of(year)
            base = asg[cb]
            for d in sorted(set(base.tolist())):
                m = base == d
                pop = int(w[m].sum())
                for k in range(FIRST_C, cb):
                    vals, inv = np.unique(asg[k][m], return_inverse=True)
                    sums = np.bincount(inv, weights=w[m])
                    for v, s in zip(vals.tolist(), sums.tolist()):
                        share = 100 * s / pop
                        if share >= MIN_SHARE:
                            rows.append((year, st, d, pop, k, v, round(share, 2)))
        log.append(f"{st}: {len(x)} block groups, maps {len(cache)}, points outside shapes "
                   + ", ".join(f"{c}:{n}" for c, n in missed.items() if n))
        print(log[-1], flush=True)
    rows.sort()
    with gzip.open(OUT, "wt", encoding="utf-8", compresslevel=9) as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["year", "state", "district", "pop", "congress", "prior_district", "share"])
        wr.writerows(rows)
    print("rows", len(rows), "->", OUT)


if __name__ == "__main__":
    main()
