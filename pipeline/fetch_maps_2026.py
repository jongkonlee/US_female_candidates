"""Fetch the 2026 (120th Congress) district shapes for the states that drew new districts for 2026.

The boundary files used for 1990-2024 (Lewis et al.) stop at the 119th Congress. Wikipedia's 2026 election pages
draw the new districts from Wikimedia Commons map data pages, "Data:<State>'s <n>th congressional district (2027–).map".
This saves each page's GeoJSON with its license and sources in data/static/boundaries_2026/ (one file per state plus
manifest.json). Runs in GitHub Actions (the workflow "fetch 2026 district maps"); then run pipeline/maps.py.
"""
import json
import os
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "static", "boundaries_2026")
API = "https://commons.wikimedia.org/w/api.php"
UA = "US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"
SEATS = {"AL": ("Alabama", 7), "CA": ("California", 52), "FL": ("Florida", 28), "LA": ("Louisiana", 6), "MO": ("Missouri", 8),
         "NC": ("North Carolina", 14), "OH": ("Ohio", 15), "TN": ("Tennessee", 9), "TX": ("Texas", 38), "UT": ("Utah", 4)}


def ordinal(n):
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def title(name, n):
    return f"Data:{name}'s {ordinal(n)} congressional district (2027–).map"


def get(titles):
    q = dict(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main", format="json", formatversion=2,
             titles="|".join(titles), maxlag=5)
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers={"User-Agent": UA})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            print("  retry", i + 1, type(e).__name__, e)
            time.sleep(5 * (i + 1))
    raise RuntimeError("Commons API not reachable")


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = {}
    for st, (name, n) in SEATS.items():
        want = {title(name, d): d for d in range(1, n + 1)}
        feats, missing = [], []
        titles = list(want)
        for i in range(0, len(titles), 25):
            j = get(titles[i:i + 25])
            norm = {x["to"]: x["from"] for x in j.get("query", {}).get("normalized", [])}
            for pg in j.get("query", {}).get("pages", []):
                t = norm.get(pg["title"], pg["title"])
                d = want.get(t) or want.get(pg["title"])
                if pg.get("missing") or not pg.get("revisions"):
                    missing.append(d)
                    continue
                rev = pg["revisions"][0]
                body = json.loads(rev["slots"]["main"]["content"])
                data = body.get("data") or {}
                geoms = [f.get("geometry") for f in data.get("features", [])] if data.get("type") == "FeatureCollection" else [data.get("geometry") if data.get("type") == "Feature" else data]
                for g in geoms:
                    if g and g.get("type") in ("Polygon", "MultiPolygon"):
                        feats.append(dict(type="Feature", geometry=g, properties=dict(st=st, d=d)))
                manifest[f"{st}-{d}"] = dict(title=pg["title"], license=body.get("license"), sources=body.get("sources"),
                                             timestamp=rev.get("timestamp"))
            time.sleep(1)
        with open(os.path.join(OUT, f"{st}.geojson"), "w") as f:
            json.dump(dict(type="FeatureCollection", features=feats), f)
        print(st, len(feats), "shapes", "missing", sorted(x for x in missing if x))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
    lic = {}
    for v in manifest.values():
        lic[v["license"]] = lic.get(v["license"], 0) + 1
    print("licenses", lic)


if __name__ == "__main__":
    main()
