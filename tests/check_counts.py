"""Compare women candidates, primary winners and general winners with the CAWP file, by year, chamber and party.

  python tests/check_counts.py
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
c = pd.read_csv(os.path.join(ROOT, "data", "candidates.csv"), low_memory=False)
cw = pd.read_excel(os.path.join(ROOT, "data", "static", "cawp_master.xlsx"))
cw["ch"] = cw.Office.map(lambda s: "S" if "Senator" in s else "H")
w = c[(c.gender == "F") & c.party.isin(["D", "R"])]
last = int(cw.Year.max())


def table(cwmask, ours, label):
    a = cw[cwmask].groupby(["Year", "ch", "Party"]).size()
    t = pd.DataFrame({"cawp": a, "ours": ours.rename_axis(["Year", "ch", "Party"])}).fillna(0).astype(int)
    t = t[t.index.get_level_values(0) <= last]
    t["diff"] = t.ours - t.cawp
    bad = t[t["diff"] != 0]
    print(f"{label}: {len(t)} cells, {len(bad)} differ, total |diff| {int(bad['diff'].abs().sum())}")
    if len(bad):
        print(bad.to_string())


table(cw.GeneralWin == "W", w[w.g_won == 1].groupby(["year", "chamber", "party"]).size(), "general winners")
table((cw.PrimaryWin == "W") & cw.Party.isin(["D", "R"]), w[w.p_won == 1].groupby(["year", "chamber", "party"]).size(), "primary winners")
table(cw.Party.isin(["D", "R"]), w.groupby(["year", "chamber", "party"]).size(), "women candidates")
