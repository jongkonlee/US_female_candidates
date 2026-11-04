"""Write Stata (.dta, version 118) copies of the data tables with Korean variable labels."""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data")

LABELS = {
    "race_id": "선거 ID(연도-원-주-선거구, 특별선거 -sp)", "year": "선거 연도", "chamber": "원(H 하원, S 상원)", "state": "주",
    "district": "선거구(0 = 전역구·상원)", "special": "특별선거(1)", "system": "경선 방식(party/blanket/top2/top4/jungle)",
    "name": "후보 이름", "party": "정당(D/R/O)", "gender": "성별(F/M, 빈칸 = 모름)", "gender_src": "성별 출처",
    "race_eth": "인종(CAWP, 여성 후보만, 2004년부터)", "incumbent": "현직(1)", "p_party": "경선 정당", "p_status": "경선 상태",
    "p_votes": "경선 득표수", "p_pct": "경선 득표율(%)", "r_votes": "경선 결선 득표수", "r_pct": "경선 결선 득표율(%)",
    "p_won": "경선 승리(정당 후보 지명, 1)", "g_votes": "본선 득표수", "g_pct": "본선 득표율(%)", "g_won": "본선 당선(1)",
    "gr_votes": "본선 결선 득표수(GA·LA 등)", "gr_pct": "본선 결선 득표율(%)", "qual": "후보 자질(Pettigrew 코드)",
    "office": "이전 경력(Pettigrew 코드)", "fec_id": "FEC 후보 번호", "src_p": "경선 자료 출처", "src_g": "본선 자료 출처",
    "cawp_primary": "CAWP 경선 결과", "cawp_general": "CAWP 본선 결과", "cawp_seat": "CAWP 경선 때 위치(I/C/O 등)",
    "link": "위키백과 문서", "note": "메모",
    "contest": "경선 종류", "n_cand": "후보 수", "n_women": "여성 후보 수", "n_men": "남성 후보 수", "n_unknown": "성별 모름 후보 수",
    "incumbent_running": "현직 출마(1)", "incumbent_gender": "현직 성별", "winner": "승자", "winner_gender": "승자 성별",
    "winner_pct": "승자 득표율(%)", "woman_won": "여성이 이김(1)", "top_woman_pct": "여성 최고 득표율(%)",
    "top_man_pct": "남성 최고 득표율(%)", "mixed": "남녀 함께 출마(1)", "src": "출처",
    "n_general": "본선 후보 수", "incumbent_party": "현직 정당", "open_seat": "현직 없는 선거(1)",
    "seat_member_on_eday": "선거일 의원(같은 번호 선거구)", "seat_member_female": "선거일 의원이 여성(1)",
    "women_members_same_map": "같은 선거구 지도 안 이전 여성 의원 수", "d_primary_women": "민주 경선 여성 수",
    "r_primary_women": "공화 경선 여성 수", "d_primary_woman_won": "민주 경선 여성 승리(1)", "r_primary_woman_won": "공화 경선 여성 승리(1)",
    "d_nominee": "민주 후보", "d_nominee_gender": "민주 후보 성별", "r_nominee": "공화 후보", "r_nominee_gender": "공화 후보 성별",
    "matchup": "본선 대결(민주-공화 성별)", "winner_party": "당선자 정당", "woman_won_general": "여성 당선(1)",
    "d_share_2party": "본선 민주 양당 득표율(%)", "pres_d_2party": "직전 대선 민주 양당 득표율(%, 하원 1990-2018)",
    "pvi": "당파 지수(+민주, 2008-2024)", "rural": "농촌 인구 비율(%)", "white_nh": "비히스패닉 백인(%)", "black_nh": "흑인(%)",
    "hisp": "히스패닉(%)", "asian_nh": "아시아계(%)", "ba_plus": "대졸(%)", "med_income": "가구 소득 중앙값(달러)",
    "src_general": "본선 자료 출처",
}


def to_dta(name):
    d = pd.read_csv(os.path.join(OUT, f"{name}.csv"), low_memory=False)
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].fillna("").astype(str).str.slice(0, 2000)
    d.to_stata(os.path.join(OUT, f"{name}.dta"), write_index=False, version=118,
               variable_labels={c: LABELS.get(c, c)[:80] for c in d.columns}, data_label=f"women candidates {name}")
    return len(d)


if __name__ == "__main__":
    for n in ("candidates", "primaries", "races"):
        print(n, to_dta(n))
