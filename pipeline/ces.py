"""Women and men voters' House votes by district (Cooperative Election Study) joined to the tracker's races.

Input: data/static/ces/ces_house_cells.csv.gz and meta.json (pipeline/fetch_ces.py; counts only, CC0).
Output (every day, from site_data.write()):
  docs/data/ces.json            page data: per House race and voter gender, respondents who voted D or R (n), weighted
                                D / R / other votes (d, r, o) and the sum of squared weights of D+R voters (q)
  docs/data/ces/ces_districts.csv/.dta      one row per House race x voter gender
  docs/data/ces/ces_districts_pid.csv/.dta  one row per House race x voter gender x party identification
"""
import datetime as dt
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS = os.path.join(ROOT, "data", "static", "ces", "ces_house_cells.csv.gz")
META = os.path.join(ROOT, "data", "static", "ces", "meta.json")
SITE = os.path.join(ROOT, "docs", "data")
OUT = os.path.join(SITE, "ces")
RACE_COLS = ["race_id", "year", "state", "district", "system", "matchup", "d_nominee", "d_nominee_gender", "r_nominee",
             "r_nominee_gender", "winner_party", "winner_gender", "incumbent_running", "incumbent_party", "pvi", "pres_d_2party"]

LABELS = dict(
    race_id="선거 번호", year="선거 연도", state="주", district="선거구(0 = 주 전체 한 석)", system="경선 방식",
    matchup="본선 대결(민주-공화 성별)", d_nominee="민주 후보", d_nominee_gender="민주 후보 성별", r_nominee="공화 후보",
    r_nominee_gender="공화 후보 성별", winner_party="당선자 정당", winner_gender="당선자 성별", incumbent_running="현직 출마(1)",
    incumbent_party="현직 정당", pvi="당파 지수(+민주, 2008-2024)", pres_d_2party="직전 대선 민주 양당 득표율(하원 1990-2018)",
    voter_gender="응답자 성별(F 여성, M 남성)", pid3="응답자 정당 일체감(D 민주, R 공화, I 무당파·기타)",
    n_dr="민주·공화 후보를 찍은 응답자 수", n_other="다른 후보를 찍은 응답자 수", w_d="민주 후보 표(가중)", w_r="공화 후보 표(가중)",
    w_other="다른 후보 표(가중)", d_share="민주 후보 양당 지지율(%, 가중)", n_eff="유효 표본 수(민주·공화 투표자, 가중치 반영)")


def load():
    if not os.path.exists(CELLS):
        return None, None
    return pd.read_csv(CELLS), json.load(open(META))


def race_id(df):
    return df.year.astype(str) + "-H-" + df.state + "-" + df.district.astype(int).map("{:02d}".format)


def aggregate(cells, keys):
    """per keys: respondents and weighted votes for D, R, other; squared weights of D+R voters"""
    c = cells.copy()
    c["dr"] = c.vote.isin(["D", "R"])
    out = c.groupby(keys).apply(lambda g: pd.Series(dict(
        n_dr=int(g.loc[g.dr, "n"].sum()), n_other=int(g.loc[~g.dr, "n"].sum()),
        w_d=float(g.loc[g.vote == "D", "w"].sum()), w_r=float(g.loc[g.vote == "R", "w"].sum()),
        w_other=float(g.loc[~g.dr, "w"].sum()), q=float(g.loc[g.dr, "w2"].sum()))), include_groups=False).reset_index()
    out["n_dr"] = out.n_dr.astype(int)
    out["n_other"] = out.n_other.astype(int)
    out["d_share"] = (100 * out.w_d / (out.w_d + out.w_r)).where(out.w_d + out.w_r > 0).round(2)
    out["n_eff"] = ((out.w_d + out.w_r) ** 2 / out.q).where(out.q > 0).round(1)
    return out


def write(races):
    cells, meta = load()
    if cells is None:
        return None
    cells["race_id"] = race_id(cells)
    house = races[(races.chamber == "H") & (races.special == 0)][RACE_COLS]
    by_g = aggregate(cells, ["race_id", "gender"])
    by_p = aggregate(cells, ["race_id", "gender", "pid3"])
    # page data: one row per race with both voter genders
    rows = []
    piv = {(r.race_id, r.gender): r for r in by_g.itertuples(index=False)}
    for rid in sorted({r for r, _ in piv}):
        row = [rid]
        for g in ("F", "M"):
            x = piv.get((rid, g))
            row += [int(x.n_dr), round(x.w_d, 2), round(x.w_r, 2), round(x.w_other, 2), round(x.q, 2)] if x is not None else [0, 0, 0, 0, 0]
        rows.append(row)
    years = sorted(int(y) for y in cells.year.unique())
    known = set(house.race_id)
    page = dict(meta=dict(citation=meta.get("citation"), version=meta.get("version"), release=meta.get("release"),
                          license=(meta.get("license") or {}).get("name"), downloaded=meta.get("downloaded"), years=years,
                          respondents=meta.get("rows_by_year"), unmatched=sum(1 for r in rows if r[0] not in known)),
                f=["race_id", "nF", "dF", "rF", "oF", "qF", "nM", "dM", "rM", "oM", "qM"], r=rows)
    with open(os.path.join(SITE, "ces.json"), "w", encoding="utf-8") as f:
        json.dump(page, f, ensure_ascii=False, separators=(",", ":"))
    # downloads
    os.makedirs(OUT, exist_ok=True)
    for name, df, keys in (("ces_districts", by_g, ["race_id", "voter_gender"]), ("ces_districts_pid", by_p, ["race_id", "voter_gender", "pid3"])):
        d = df.rename(columns={"gender": "voter_gender"}).drop(columns=["q"]).merge(house, on="race_id", how="left")
        d = d[RACE_COLS + [k for k in keys if k != "race_id"] + ["n_dr", "n_other", "w_d", "w_r", "w_other", "d_share", "n_eff"]]
        for c in ("w_d", "w_r", "w_other"):
            d[c] = d[c].round(2)
        d = d.sort_values(["year", "state", "district"] + [k for k in keys if k != "race_id"])
        d.to_csv(os.path.join(OUT, name + ".csv"), index=False, encoding="utf-8-sig")
        stata(d, os.path.join(OUT, name + ".dta"), "CES 하원 투표: 선거 x 응답자 성별" + (" x 정당 일체감" if "pid3" in keys else ""))
    return page["meta"]


def stata(df, path, title):
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            if c in ("year", "district", "n_dr", "n_other", "incumbent_running") and df[c].notna().all():
                df[c] = df[c].astype("int32")
        else:
            df[c] = df[c].astype(object).where(df[c].notna(), "").astype(str)
    df.to_stata(path, write_index=False, version=118, variable_labels={k: v[:80] for k, v in LABELS.items() if k in df.columns},
                data_label=title[:80], time_stamp=dt.datetime(2026, 1, 1))


if __name__ == "__main__":
    print(write(pd.read_csv(os.path.join(ROOT, "data", "races.csv"), low_memory=False)))
