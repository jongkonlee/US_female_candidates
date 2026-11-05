"""Fetch the documentation of the House primary datasets (Harvard Dataverse) so the page codebook can explain their codes.

Saves, for Pettigrew, Owen & Wanless (doi:10.7910/DVN/26448) and Miller & Camberg (doi:10.7910/DVN/CXVMSY):
the file list, the DDI codebook export (variable and value labels of the data files), and any documentation file
(PDF, Word, text, README, codebook) into data/static/codebooks/<name>/. Runs in GitHub Actions (the workflow
"fetch source codebooks"), because the workspace cannot reach Dataverse.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "static", "codebooks")
API = "https://dataverse.harvard.edu/api"
UA = "US_female_candidates-tracker/1.0 (+https://github.com/jongkonlee/US_female_candidates)"
SETS = {"pettigrew": "doi:10.7910/DVN/26448", "miller_camberg": "doi:10.7910/DVN/CXVMSY"}
DOC_TYPES = ("application/pdf", "text/plain", "text/markdown", "application/rtf", "application/msword",
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print("  retry", i + 1, type(e).__name__, e)
            time.sleep(10 * (i + 1))
    raise RuntimeError("not reachable: " + url)


def main():
    for name, doi in SETS.items():
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        q = urllib.parse.quote(doi, safe="")
        meta = json.loads(get(f"{API}/datasets/:persistentId/?persistentId={q}"))
        files = meta["data"]["latestVersion"]["files"]
        lst = [dict(id=f["dataFile"]["id"], name=f["dataFile"].get("filename") or f.get("label"),
                    type=f["dataFile"].get("contentType"), size=f["dataFile"].get("filesize")) for f in files]
        json.dump(lst, open(os.path.join(d, "files.json"), "w"), indent=1)
        print(name, [(x["name"], x["type"]) for x in lst])
        try:
            open(os.path.join(d, "ddi.xml"), "wb").write(get(f"{API}/datasets/export?exporter=ddi&persistentId={q}"))
        except Exception as e:  # noqa: BLE001
            print("  no DDI export:", e)
        for x in lst:
            nm = x["name"] or str(x["id"])
            if x["type"] in DOC_TYPES or re.search(r"codebook|readme|documentation|variables", nm, re.I):
                if (x["size"] or 0) > 30_000_000:
                    continue
                open(os.path.join(d, re.sub(r"[^\w.\-]+", "_", nm)), "wb").write(get(f"{API}/access/datafile/{x['id']}"))
                print("  saved", nm)
            time.sleep(1)


if __name__ == "__main__":
    main()
