"""Ballot-line labels in the FEC "Federal Elections" workbooks (2002-2022) for candidates with no Democratic or Republican
line (third party, independent, write-in, nonpartisan).

Why: the 1990-2022 rows in data/static/history_rows.json.gz were built with build_db.fill_party_from_fec_id, which gives
a candidate whose ballot line is not D or R the party of his or her FEC registration. That is right for write-in and
nonpartisan lines (Murkowski 2010, the 2018 Mississippi special) but not for a third-party or independent line. The
history file keeps no ballot labels, so this script records them; build_db.third_party_lines uses the table.

Runs in GitHub Actions (workflow 'fetch FEC ballot labels'), because the workspace cannot reach fec.gov.
Output: data/static/fec_ballot_labels.csv  year, chamber, state, district, special, name, fec_id, lines (all ballot labels
of the candidate, '/'), writein (1 = every line is a write-in), g_votes, g_pct
        data/static/fec_line_votes.csv  candidates on two or more lines (e.g. a D or R primary line and a third-party general
line): one row per line with year, chamber, state, district, special, name, fec_id, line, writein, p_status, p_votes,
g_votes, g_unopposed
"""
import os

import pandas as pd

import collect
import fec_results

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "static", "fec_ballot_labels.csv")
OUT_LINES = os.path.join(ROOT, "data", "static", "fec_line_votes.csv")
YEARS = list(range(2002, 2024, 2))


def main():
    collect.fec_results(YEARS)
    out = []
    for y in YEARS:
        p = fec_results.persons(y)
        if p.empty:
            raise SystemExit(f"no FEC rows for {y}")
        o = p[(p.party == "O") & (p.fec_id.fillna("") != "")]
        print(y, "candidates", len(p), "| no D/R line, with FEC id", len(o), flush=True)
        out.append(o[["year", "chamber", "state", "district", "special", "name", "fec_id", "lines", "writein", "g_votes", "g_pct"]])
    t = pd.concat(out, ignore_index=True)
    t.to_csv(OUT, index=False, encoding="utf-8")
    print("rows", len(t), "| labels:", t["lines"].value_counts().head(40).to_dict(), flush=True)
    multi = []
    for y in YEARS:
        x = fec_results.line_records(y)
        k = ["year", "chamber", "state", "district", "special", "key"]
        n = x.groupby(k)["line"].transform("nunique")
        x = x[n >= 2]
        multi.append(x[["year", "chamber", "state", "district", "special", "name", "fec_id", "line", "writein", "pst", "pv", "gv", "gunopp"]]
                     .rename(columns={"pst": "p_status", "pv": "p_votes", "gv": "g_votes", "gunopp": "g_unopposed"}))
    m = pd.concat(multi, ignore_index=True)
    m.to_csv(OUT_LINES, index=False, encoding="utf-8")
    print("multi-line rows", len(m), flush=True)


if __name__ == "__main__":
    main()
