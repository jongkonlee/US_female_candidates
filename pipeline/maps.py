"""Real district map data for the page (docs/data/maps/).

Boundaries: Jeffrey B. Lewis, Brandon DeVine, Lincoln Pitcher, and Kenneth C. Martis. (2013) Digital Boundary
Definitions of U.S. Congressional Districts, 1789-2012 [Data file and code book; updated by the authors through the
119th Congress]. Retrieved from https://github.com/JeffreyBLewis/congressional-district-boundaries (GeoJson folder,
MIT license) on 2026-11-05.

Boundaries do not change from day to day, so this runs by hand, not in the daily job:

  git clone --depth 1 https://github.com/JeffreyBLewis/congressional-district-boundaries.git /tmp/lewis
  npm install mapshaper@0.6
  python pipeline/maps.py --lewis /tmp/lewis/GeoJson

Output
  index.json        frame size, state outlines (119th Congress shapes, used for every year), per state the Congress
                    ranges that have a detail file, states with new 2026 districts that are not in the boundary files yet
  c{congress}.json  whole country for one Congress (1990 election = 102nd ... 2026 election = 120th), light shapes:
                    {"congress", "d": [[state, district, path]], "pending": [...]}
  s/{ST}-{a}-{b}.json  one state's districts in Congresses a..b with fine shapes, loaded when the state is zoomed:
                    {"d": [[district, path]]}, coordinates 10 times finer (draw with scale(0.1))
Paths are SVG path strings in one fixed Albers USA frame (Alaska and Hawaii moved in): integers in 1/10 px at 975 px
width (detail files 1/100 px), first point absolute, the rest relative.
"""
import argparse
import collections
import glob
import json
import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "maps")
FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "12": "FL", "13": "GA",
        "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
        "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ",
        "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC",
        "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}
NAMES = {"Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT",
         "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
         "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
         "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
         "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
         "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
         "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
         "Wisconsin": "WI", "Wyoming": "WY"}
FIRST, LAST = 102, 119  # boundary files: 1990 election (102nd Congress) to 2024 (119th)
# 2026 (120th Congress): states that drew new districts for 2026 (their 2026 Wikipedia election pages use the
# "(2027–)" district maps). The boundary files stop at the 119th Congress, so these states are drawn without districts;
# the other states keep their 119th Congress districts.
NEW_2026 = ["AL", "CA", "FL", "LA", "MO", "NC", "OH", "TN", "TX", "UT"]
WIDTH = 9750                 # 975 px x 10
LIGHT = ["interval=1500", "20km2"]   # metres, smallest island kept: finer than a pixel at country scale
FINE = ["interval=100", "1km2"]      # for a zoomed state (city districts)


def congress_of(year):
    return (year - 1788) // 2 + 1


NEW_DIR = os.path.join(ROOT, "data", "static", "boundaries_2026")  # pipeline/fetch_maps_2026.py


def load_2026():
    """2026 shapes of the states in NEW_2026 that have them: (state, district, 120, 120, geometry)"""
    out = []
    for st in NEW_2026:
        p = os.path.join(NEW_DIR, f"{st}.geojson")
        if os.path.exists(p):
            fs = json.load(open(p))["features"]
            out += [(st, int(ft["properties"]["d"]), LAST + 1, LAST + 1, ft["geometry"]) for ft in fs if ft.get("geometry")]
    return out


def load_features(lewis_dir):
    """every district shape in use in the 102nd-119th Congresses: (state, district, first, last, geometry)"""
    out = []
    for f in sorted(glob.glob(os.path.join(lewis_dir, "*.geojson"))):
        m = re.match(r"(.+)_(\d+)_to_(\d+)\.geojson$", os.path.basename(f))
        if not m or int(m.group(3)) < FIRST or int(m.group(2)) > LAST:
            continue
        for ft in json.load(open(f))["features"]:
            p = ft["properties"]
            st = FIPS.get(str(p.get("statefp") or "").zfill(2)) or NAMES.get(str(p.get("statename") or "").strip())
            a, b = max(FIRST, int(p["startcong"])), min(LAST, int(p["endcong"]))
            if st and a <= b:
                out.append((st, int(float(p["district"] or 0)), a, b, ft["geometry"]))
    return out


def mapshaper(src, dst, cmds):
    r = subprocess.run(["npx", "--no-install", "mapshaper", "-i", src] + cmds + ["-o", dst, "format=geojson", "precision=1"],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise RuntimeError("mapshaper failed: " + r.stderr[-2000:])


def rings(geom):
    if geom is None:
        return []
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    if geom["type"] == "MultiPolygon":
        return [r for poly in geom["coordinates"] for r in poly]
    return []


def path(geom, frame, fine=False):
    minx, maxy, k = frame
    if fine:
        k = k * 10
    out = []
    for ring in rings(geom):
        pts, last = [], None
        for x, y in ring:
            p = (round((x - minx) * k), round((maxy - y) * k))
            if p != last:
                pts.append(p)
                last = p
        if len(pts) > 1 and pts[-1] == pts[0]:
            pts = pts[:-1]
        if len(pts) < 3:
            continue
        rel, prev = [], pts[0]
        for p in pts[1:]:
            rel.append(f"{p[0] - prev[0]} {p[1] - prev[1]}")
            prev = p
        out.append(f"M{pts[0][0]} {pts[0][1]}l" + " ".join(rel).replace(" -", "-") + "z")
    return "".join(out)


def project(feats, tmp, name, simplify, extra=()):
    src, dst = os.path.join(tmp, name + "_in.json"), os.path.join(tmp, name + ".json")
    json.dump(dict(type="FeatureCollection", features=feats), open(src, "w"))
    # clean before simplifying: older shapes do not share exact borders, and simplifying them one by one leaves many
    # short arcs (3 times the points) and slivers
    mapshaper(src, dst, ["-filter-islands", f"min-area={simplify[1]}", "-proj", "albersusa", "-clean", "-simplify", simplify[0],
                         "keep-shapes", "-clean"] + list(extra))
    return json.load(open(dst))["features"]


def save(rel, obj):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, separators=(",", ":"))
    return os.path.getsize(p)


def build(lewis_dir):
    feats = load_features(lewis_dir)
    new = load_2026()
    have_new = sorted({x[0] for x in new})
    # a state that redrew only some districts (North Carolina, Florida 2026): its pages keep the earlier map for the
    # others, so those keep their 119th Congress shapes
    new_ds = {(x[0], x[1]) for x in new}
    fill = [(st, d, LAST + 1, LAST + 1, g) for st, d, a, b, g in feats if a <= LAST <= b and st in have_new and (st, d) not in new_ds]
    feats += new + fill
    print(len(feats), "district shapes; 2026 shapes for", have_new, "| kept from 2024:", sorted({f"{x[0]}-{x[1]}" for x in fill}))
    gj = lambda st, d, g: dict(type="Feature", geometry=g, properties=dict(st=st, d=d))  # noqa: E731
    with tempfile.TemporaryDirectory() as tmp:
        # one frame for every file, and one set of state outlines for every year, from the 119th Congress (Census shapes)
        base = project([gj(st, d, g) for st, d, a, b, g in feats if a <= LAST <= b], tmp, "frame", LIGHT, ["-dissolve", "st"])
        xs = [x for ft in base for r in rings(ft["geometry"]) for x, _ in r]
        ys = [y for ft in base for r in rings(ft["geometry"]) for _, y in r]
        pad = (max(xs) - min(xs)) * 0.01
        minx, maxx, miny, maxy = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
        k = WIDTH / (maxx - minx)
        frame, height = (minx, maxy, k), round((maxy - miny) * k)
        outlines = sorted([ft["properties"]["st"], path(ft["geometry"], frame)] for ft in base)
        total = 0
        for c in range(FIRST, LAST + 2):
            if c <= LAST:
                fs = [gj(st, d, g) for st, d, a, b, g in feats if a <= c <= b]
            else:  # 2026: new shapes where they exist; the 119th Congress districts elsewhere; outline only if missing
                fs = [gj(st, d, g) for st, d, a, b, g in feats if a == b == c]
                fs += [gj(st, -1 if st in NEW_2026 else d, g) for st, d, a, b, g in feats
                       if a <= LAST <= b and st not in have_new]
            dist = project(fs, tmp, f"c{c}", LIGHT)
            d = sorted([ft["properties"]["st"], ft["properties"]["d"], path(ft["geometry"], frame)] for ft in dist
                       if ft["properties"]["d"] >= 0)
            pending = sorted({ft["properties"]["st"] for ft in dist if ft["properties"]["d"] < 0})
            n = save(f"c{c}.json", dict(congress=c, d=d, pending=pending))
            total += n
            print(c, len(d), "districts", f"{n / 1024:.0f} KB", "pending", pending)
        periods = collections.defaultdict(set)
        for st, d, a, b, g in feats:
            periods[st].add((a, b))
        detail = {}
        for st in sorted(periods):
            # split overlapping ranges into pieces where the set of shapes is the same
            cuts = sorted({a for a, b in periods[st]} | {b + 1 for a, b in periods[st]})
            spans = [(cuts[i], cuts[i + 1] - 1) for i in range(len(cuts) - 1)]
            detail[st] = []
            for a, b in spans:
                fs = [gj(st, dd, g) for s2, dd, a2, b2, g in feats if s2 == st and a2 <= a and b <= b2]
                if not fs:
                    continue
                out = project(fs, tmp, f"{st}{a}", FINE)
                n = save(f"s/{st}-{a}-{b}.json", dict(d=sorted([ft["properties"]["d"], path(ft["geometry"], frame, fine=True)] for ft in out)))
                total += n
                detail[st].append([a, b])
        save("index.json", dict(w=WIDTH, h=height, first=FIRST, last=LAST + 1, detail=detail, s=outlines,
                                new_2026=[st for st in NEW_2026 if st not in have_new], new_2026_shapes=have_new,
                                source="Lewis, DeVine, Pitcher and Martis, Digital Boundary Definitions of U.S. Congressional Districts (GitHub, 2026-11-05)"))
        print("total", f"{total / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lewis", required=True, help="the GeoJson folder of congressional-district-boundaries")
    build(ap.parse_args().lewis)
