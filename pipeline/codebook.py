"""Variable codebook for the downloads: docs/data/codebook.json (shown on the page) and docs/data/codebook.csv.

One entry per (table, variable): what the variable means and its codes or units. Run by site_data.write() every day,
or by hand: python pipeline/codebook.py
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data")

TABLES = [
    ("candidates", "후보", "한 줄 = 선거 하나의 후보 한 명. 페이지 '후보 데이터 내려받기'의 후보, 저장소 data/candidates.csv"),
    ("primaries", "경선", "한 줄 = 선거 하나의 민주당 또는 공화당 경선 하나. data/primaries.csv"),
    ("races", "선거", "한 줄 = 선거 하나(연도·원·주·선거구). data/races.csv"),
    ("lineage_2026", "선거구 정렬: 2026년 기준", "한 줄 = 2026년 하원 선거구 하나. docs/data/lineage/lineage_2026.csv·.dta"),
    ("lineage_all", "선거구 정렬: 모든 하원 선거", "한 줄 = 하원 선거 하나 × 예전 의회 하나(1990–2026). docs/data/lineage/lineage_all.csv·.dta"),
    ("ces_districts", "CES 유권자: 선거 × 응답자 성별", "한 줄 = 하원 선거 하나 × 응답자 성별(2006–2024 짝수 해). docs/data/ces/ces_districts.csv·.dta"),
    ("ces_districts_pid", "CES 유권자: 선거 × 응답자 성별 × 정당 일체감", "한 줄 = 하원 선거 하나 × 응답자 성별 × 정당 일체감. docs/data/ces/ces_districts_pid.csv·.dta"),
    ("ces_individual", "CES 개인 분석 자료", "한 줄 = 응답자 한 명(2008–2024 민주·공화 후보가 모두 나온 하원 선거에서 둘 중 한 명을 찍은 사람; 여성 대 남성 mixed, 둘 다 여성 ff, 둘 다 남성 mm). docs/data/ces/ces_individual.zip 안의 ces_individual.dta"),
    ("ces_models", "CES 회귀계수", "한 줄 = 모형 하나의 변수 하나. docs/data/ces/ces_models.csv"),
    ("ces_models_pred", "CES 보정 예측", "한 줄 = 모형 하나의 예측값 또는 차이 하나. docs/data/ces/ces_models_pred.csv"),
    ("ces_nominee_race", "후보 인종 자료", "한 줄 = 후보 한 명(정당마다 1명): 2008–2024 하원에서 민주·공화 후보가 모두 나온 선거(분석 대상)와 2026 하원·상원의 민주·공화 후보. docs/data/ces/nominee_race.csv·.dta"),
]

COMMON = [
    ("race_id", "선거 번호", "연도-원-주-선거구(예: 2026-H-CA-11). 선거구 00 = 주 전체가 한 석인 하원 선거구와 상원. 상원 특별선거는 끝에 -sp"),
    ("year", "선거 연도", "본선이 있는 해(짝수 해)"),
    ("chamber", "원", "H = 하원, S = 상원"),
    ("state", "주", "두 글자 약어(예: CA)"),
    ("district", "선거구 번호", "0 = 주 전체가 한 석인 곳(하원)과 상원"),
    ("special", "특별선거", "1 = 특별선거(잔여 임기), 0 = 정기 선거. 하원 특별선거는 뺐고 상원은 본선 날 치른 것만 넣음"),
    ("system", "경선 방식", "party = 정당별 경선 / blanket = 모든 정당 후보가 한 투표용지, 정당별 1위가 그 당 후보(CA 1998·2000, WA ~2002, AK ~2000) / "
     "top2 = 정당 구분 없이 상위 2명이 본선(CA 2012~, WA 2008~) / top4 = 상위 4명이 본선(AK 2022~) / "
     "jungle = 루이지애나식, 본선 날 정당 구분 없는 투표 뒤 과반이 없으면 결선(LA ~2006, 2012~2024)"),
]

CANDIDATES = [
    ("name", "후보 이름", "자료 출처의 표기 그대로"),
    ("party", "정당", "D = 민주, R = 공화, O = 그 밖(무소속·제3당). 본선 투표용지 기준이라 경선 정당(p_party)과 다를 수 있음. FEC에 민주·공화로 등록했어도 투표용지에 제3당·무소속으로 나오면 O. 정당 표시 없는 기명 후보와 미시시피 2008·2018 무정당 특별선거만 FEC 등록 정당"),
    ("gender", "성별", "F = 여성, M = 남성, 빈칸 = 모름"),
    ("gender_src", "성별을 정한 근거", "CAWP = CAWP 데이터베이스에 있음(여성) / not in CAWP = 민주·공화 후보인데 CAWP에 없음(남성으로 봄) / "
     "CAWP 2026 list, not in CAWP 2026 list = 2026년은 CAWP 후보 목록으로 같은 규칙 / Wikipedia page (pronouns) = 위키백과 본인 문서의 대명사 / "
     "CAWP (earlier race) = 예전 선거의 CAWP 기록 / CAWP (other year) = 그해 CAWP엔 없지만 다른 해 CAWP에 같은 주·같은 이름의 여성이 있음 / "
     "research (gender_overrides.csv) = 조사로 확인한 여성(투표용지에 없는 기명 후보 등, 근거는 data/static/gender_overrides.csv) / member or earlier candidate = 의원 명부나 예전 경선 자료의 같은 사람 / "
     "first name = 이름(미국 출생 기록에서 95% 이상 한쪽 성별) / Pettigrew = Pettigrew 외 자료의 성별 / "
     "...; woman's first name = 2026 목록에 없지만 여성 이름이라 모름으로 둠 / unknown·빈칸 = 정하지 못함(대부분 민주·공화 밖 후보)"),
    ("race_eth", "인종·민족(여성 후보만)", "CAWP 코드, 2004년부터: W = 백인, B = 흑인, H = 히스패닉·라티나, AP = 아시아계·태평양 섬 주민, "
     "MENA = 중동·북아프리카계, NA = 미국 원주민·알래스카 원주민, MU = 여러 인종. 둘 이상이면 /로 이음(예: B/W)"),
    ("incumbent", "현직 의원", "1 = 자료 출처가 현직으로 표시한 후보, 0 = 아님. 선거구 조정으로 다른 번호에 나온 현직은 출처에 따라 1 또는 0(예: 2022 IL-6 Newman 1, NY-10 Mondaire Jones 0)"),
    ("p_party", "경선 정당", "D, R, O. 빈칸 = 경선 기록이 없는 후보(본선에만 나옴)"),
    ("p_status", "경선 상태", "votes = 득표 기록 있음 / unopposed = 단독 후보(투표 없이 지명) / convention = 전당대회 지명 / convention_lost = 전당대회에서 짐 / "
     "no contest = 경선을 치르지 않음(루이지애나식 등) / nominated (no primary record) = 경선 기록 없이 본선 후보가 됨 / "
     "lost (CAWP; no vote record) = CAWP에는 경선 낙선으로 있으나 득표 기록 없음 / replacement = 경선 뒤 바뀐 후보 / withdrew = 사퇴 / other:… = 원자료 표기"),
    ("p_votes", "경선 득표수", "표"),
    ("p_pct", "경선 득표율", "%, 그 당 경선 안에서(상위 2인 경선 등은 전체 1차 투표 안에서)"),
    ("r_votes", "경선 결선 득표수", "표. 1위가 과반을 못 넘으면 결선을 하는 주(남부 등)"),
    ("r_pct", "경선 결선 득표율", "%"),
    ("p_won", "경선 승리", "1 = 이김, 0 = 짐, 빈칸 = 경선 기록 없음. 결선이 있으면 결선 승자, 단독·전당대회·기록 없음은 본선에 나간 그 당 후보. "
     "상위 2·4인 경선은 본선 진출, 루이지애나식은 그 당 최다 득표자"),
    ("g_votes", "본선 득표수", "표. 루이지애나식은 본선 날 1차 투표, 알래스카(2022~)는 첫 개표, 메인(2018~)은 마지막 선호투표 집계. 무투표 당선은 빈칸일 수 있음"),
    ("g_pct", "본선 득표율", "%. 무투표 당선은 100"),
    ("g_won", "본선 당선", "1 = 당선, 0 = 낙선, 빈칸 = 본선에 나가지 않음(또는 올해 개표 중)"),
    ("gr_votes", "본선 결선 득표수", "표. 조지아 본선 결선, 루이지애나 12월 결선, 1996 텍사스 12월 결선 등"),
    ("gr_pct", "본선 결선 득표율", "%"),
    ("qual", "후보 자질(하원 경선 후보, 1990–2018)", "Pettigrew 외(1990–2010)·Miller & Camberg(2012–2018) 코드북: 0 = 선출직을 지낸 적 없음, "
     "1 = 선출직을 지낸 적 있음, 2 = 현직, 3 = 전직 하원의원인 도전자"),
    ("office", "이전 경력(하원 경선 후보, 1990–2018)", "같은 코드북의 0~30 코드(30 = 현직, 27 = 주 하원의원, 0 = 선출직 경험 없음 등). 전체 뜻은 아래 '이전 경력 코드'"),
    ("fec_id", "FEC 후보 번호", "2002–2022년 FEC 자료"),
    ("src_p", "경선 자료 출처", "FEC = FEC 공식 결과 / Pettigrew-Owen-Wanless = 하원 경선 1990–2000 / Wikipedia = 위키백과(비공식) / "
     "CAWP only = 득표 기록 없이 CAWP 명단에서만 넣은 여성 경선 낙선자"),
    ("src_g", "본선 자료 출처", "FEC / MEDSL = MIT 선거연구소가 모은 주 공식 결과 / Wikipedia / Wikipedia overview = 위키백과 전체 표(득표율만)"),
    ("cawp_primary", "CAWP의 경선 결과(여성 후보만)", "W = 이김, L = 짐, WD = 선거일 전에 사퇴했으나 투표용지에 있음"),
    ("cawp_general", "CAWP의 본선 결과(여성 후보만)", "W = 당선, L = 낙선, WD = 사퇴, TCTC = 개표 중(2026 목록), RO = 결선으로 감(2026 목록)"),
    ("cawp_seat", "CAWP의 경선 때 위치(여성 후보만)", "CAWP 코드북: I = 현직(Incumbent), IU = 현직, 상대 없음(Incumbent Unopposed), IvI = 현직끼리 대결(선거구 조정), "
     "C = 도전자(Challenger), CP = 경선 도전자(Challenger in the Primary, 같은 당 현직에 경선에서 도전), O = 현직 없는 선거(Open), WD = 사퇴"),
    ("link", "위키백과 문서", "위키백과 문서 제목(있을 때)"),
    ("note", "메모(저장소 파일만)", "자료를 손본 기록(예: 본선 투표용지 정당이 경선과 다름, 무투표 당선)"),
]

PRIMARIES = [
    ("party", "경선 정당", "D = 민주, R = 공화"),
    ("contest", "경선 종류", "contested = 후보 둘 이상이 득표로 겨룸 / runoff = 결선까지 감 / uncontested = 단독 후보 / convention = 전당대회 지명 또는 경선 기록 없음 / "
     "top2, top4, jungle = 정당 경선이 아닌 방식에서 그 당 후보만 모은 줄"),
    ("n_cand", "후보 수", "명"),
    ("n_women", "여성 후보 수", "명"),
    ("n_men", "남성 후보 수", "명"),
    ("n_unknown", "성별 모름 후보 수", "명"),
    ("incumbent_running", "그 당 경선에 현직이 나옴", "1 = 예, 0 = 아니오"),
    ("incumbent_gender", "그 현직의 성별", "F, M, 빈칸 = 현직 없음"),
    ("winner", "경선 승자", "이름(p_won 규칙)"),
    ("winner_gender", "승자 성별", "F, M, 빈칸 = 모름·승자 없음"),
    ("winner_pct", "승자 득표율", "%, 결선이 있으면 결선 득표율"),
    ("woman_won", "여성이 이김", "1 = 승자가 여성, 0 = 남성, 빈칸 = 승자 성별 모름·승자 없음"),
    ("top_woman_pct", "여성 후보 최고 득표율", "%"),
    ("top_man_pct", "남성 후보 최고 득표율", "%"),
    ("mixed", "남녀가 함께 나옴", "1 = 예"),
    ("src", "경선 자료 출처", "src_p와 같은 값, 여럿이면 ;로 이음"),
]

RACES = [
    ("n_general", "본선 후보 수", "명(본선 결과가 있는 후보)"),
    ("incumbent_running", "현직 출마", "1 = 현직 의원이 이 선거(경선 포함)에 나옴"),
    ("incumbent_party", "현직의 정당", "D, R, O, 빈칸 = 현직이 나오지 않음"),
    ("incumbent_gender", "현직의 성별", "F, M, 빈칸"),
    ("open_seat", "현직 없는 선거", "1 = 현직 의원이 후보로 나오지 않음"),
    ("seat_member_on_eday", "현직자", "선거일에 같은 번호 선거구를 맡던 의원(상원은 그 주의 상원의원 두 명), 여럿이면 ;. 선거구를 다시 그린 해에는 번호만 같은 옛 선거구의 의원"),
    ("seat_member_female", "현직자가 여성", "1 = 선거일의 현직자가 여성(상원은 두 명 중 한 명이라도), 0 = 아님"),
    ("women_members_same_map", "같은 지도 안 기존 여성 의원 수", "하원: 지금 지도가 쓰이기 시작한 때(1993·2003·2013·2023년 1월)부터 선거일까지 같은 번호 선거구를 맡은 "
     "서로 다른 여성 의원 수(지금 의원 포함, 같은 사람은 1명). 10년마다 0부터 다시 셈, 1992·2002·2012·2022년은 정의상 0. 상원: 1985년부터 그 주 두 자리"),
    ("women_members_since_1990", "이어지는 선거구의 기존 여성 의원 수(하원)", "1990년 선거 때 의회(101대)부터 선거일까지, 의회마다 이어지는 선거구(주민 2/3 이상, 없으면 같은 의원)를 "
     "맡은 서로 다른 여성 의원 수(지금 의원 포함). 10년마다 0으로 돌아가지 않음. 정한 방법은 선거구 정렬 자료 참고"),
    ("women_members_since_1990_excl", "기존 여성 의원 수(하원, 이번 본선 여성 후보 본인 제외)", "women_members_since_1990과 같되, 이번 선거 본선에 나온 민주·공화 "
     "여성 후보 자신은 세지 않음(재선에 나온 현직 여성 의원은 자기 선거구의 '기존 여성'이 아님)"),
    ("women_prior_since_1990", "이어지는 선거구의 기존 여성 수(의원 또는 본선 후보, 하원)", "이어지는 선거구에서 여성 의원이었거나(women_members_since_1990과 같은 기준), "
     "1990년부터 직전 선거까지 본선에 나온 민주·공화 여성 후보(당락 무관, 상위 2인 경선 등은 본선에 나간 여성 모두)인 서로 다른 사람 수. "
     "의원과 후보가 같은 사람인지는 FEC 번호·위키백과 문서·이름으로 맞춤"),
    ("women_prior_since_1990_excl", "기존 여성 수(의원 또는 본선 후보, 이번 본선 여성 후보 본인 제외)", "women_prior_since_1990과 같되 이번 선거 본선의 민주·공화 여성 후보 자신은 세지 않음"),
    ("d_primary_women", "민주 경선 여성 후보 수", "명"),
    ("r_primary_women", "공화 경선 여성 후보 수", "명"),
    ("d_primary_woman_won", "민주 경선에서 여성이 이김", "1, 0, 빈칸 = 모름·경선 없음"),
    ("r_primary_woman_won", "공화 경선에서 여성이 이김", "1, 0, 빈칸"),
    ("d_nominee", "본선 민주 후보", "이름. 같은 당 후보가 둘 이상이면(상위 2인 경선 등) 득표가 많은 쪽"),
    ("d_nominee_gender", "본선 민주 후보 성별", "F, M, 빈칸"),
    ("r_nominee", "본선 공화 후보", "이름(같은 규칙)"),
    ("r_nominee_gender", "본선 공화 후보 성별", "F, M, 빈칸"),
    ("matchup", "본선 대결(민주-공화 성별)", "F-M = 민주 여성 대 공화 남성, M-F = 민주 남성 대 공화 여성, F-F, M-M / D only = 공화 후보 없음(민주 대 민주 포함) / "
     "R only = 민주 후보 없음 / ? = 성별 모름"),
    ("winner", "본선 당선자", "이름. 올해는 당선이 확인된 곳만"),
    ("winner_party", "당선자 정당", "D, R, O"),
    ("winner_gender", "당선자 성별", "F, M, 빈칸"),
    ("woman_won_general", "여성 당선", "1 = 여성 당선, 0 = 남성, 빈칸 = 아직 모름"),
    ("d_share_2party", "본선 민주 양당 득표율", "%, 민주 ÷ (민주 + 공화)"),
    ("pres_d_2party", "직전 대선 민주 양당 득표율(하원)", "%, 선거구 단위(Pettigrew 외 자료, 1990–2018)"),
    ("pvi", "당파 지수", "Cook 방식, + = 민주 쪽, − = 공화 쪽(여성정책 트래커에서 계산, 2008–2024)"),
    ("rural", "농촌 인구 비율", "%(인구조사국, 2008–2024 선거)"),
    ("white_nh", "비히스패닉 백인 비율", "%"),
    ("black_nh", "흑인 비율", "%(비히스패닉)"),
    ("hisp", "히스패닉 비율", "%"),
    ("asian_nh", "아시아계 비율", "%(비히스패닉)"),
    ("ba_plus", "대졸 비율", "%, 25세 이상 중 학사 이상"),
    ("med_income", "가구 소득 중앙값", "달러"),
    ("src_general", "본선 자료 출처", "src_g와 같은 값, 여럿이면 ;"),
]

LINEAGE_RULE = ("이은 방법: 그해 선거구 주민(2020년 인구조사 블록그룹 인구)의 2/3 이상이 살던 예전 선거구(인구 2/3). 그런 선거구가 없으면, "
                "그 예전 선거구의 의원이 이번 선거에 나왔을 때 그 의원의 선거구(같은 의원). 둘 다 없으면 빈칸")

LINEAGE_2026 = [
    ("race_id", "2026년 선거 번호", "예: 2026-H-CA-11"),
    ("year", "선거 연도", "2026"),
    ("state", "주", "두 글자 약어"),
    ("district", "2026년 선거구 번호", "0 = 주 전체 한 석"),
    ("n_linked", "이어지는 선거구가 있는 예전 의회 수", "101~119대 중(최대 19)"),
    ("women_since_1990", "서로 다른 여성 의원 수", "이어진 선거구들을 맡은 여성(1990년 선거 때 의회부터, 같은 사람은 1명) = races의 women_members_since_1990"),
    ("women_names", "그 여성 의원 이름", ";로 이음"),
    ("women_prior_since_1990", "기존 여성 수(의원 또는 본선 후보)", "여성 의원이었거나 1990–2024년 본선에 나온 민주·공화 여성 후보인 서로 다른 사람 수 = races의 women_prior_since_1990"),
    ("women_prior_names", "그 여성 이름", ";로 이음(의원 먼저)"),
    ("d1988 … d2024", "그해 선거의 이어지는 선거구 번호", "d2024 = 2024년 선거(119대 의회) … d1988 = 1990년 선거 때 의원(101대). 빈칸 = 없음. " + LINEAGE_RULE),
    ("s1988 … s2024", "주민 겹침 비율", "%, 2026년 선거구 주민 중 그 선거구에 살던 비율(2020년 인구). 같은 의원으로 이은 경우 작을 수 있음"),
    ("r1988 … r2024", "이은 방법", "인구 2/3, 같은 의원, 빈칸"),
]

LINEAGE_ALL = [
    ("race_id", "선거 번호", "기준이 되는 하원 선거(1990–2026)"),
    ("year", "선거 연도", ""),
    ("state", "주", ""),
    ("district", "선거구 번호", "0 = 주 전체 한 석"),
    ("prior_year", "예전 선거 연도", "그 의회를 뽑은 선거(다음 해 1월부터 2년). 1988 = 1990년 선거 때 의원(101대)"),
    ("congress", "예전 의회 대수", "101 … 선거일의 의회"),
    ("prior_district", "이어지는 예전 선거구 번호", "빈칸 = 없음. " + LINEAGE_RULE),
    ("prior_race_id", "이어지는 예전 선거 번호", "예: 2020-H-CA-12"),
    ("share", "주민 겹침 비율", "%, 이 선거구 주민 중 이어지는 선거구에 살던 비율(2020년 인구)"),
    ("rule", "이은 방법", "인구 2/3, 같은 의원, 빈칸"),
    ("best_district", "주민이 가장 많이 겹친 예전 선거구", "이어지지 않았거나 같은 의원으로 이었을 때 비교용"),
    ("best_share", "그 겹친 비율", "%"),
    ("members", "그 의회에서 이어지는 선거구를 맡은 의원", ";로 이음(중간에 바뀌면 둘 이상)"),
    ("women", "그중 여성 의원", ";로 이음"),
    ("women_cum", "여기까지 쌓인 여성 의원 수", "101대부터 이 줄의 의회까지 서로 다른 여성 의원 수"),
    ("women_cands", "그 예전 선거 본선의 여성 후보", "이어지는 예전 선거구의 본선에 나온 민주·공화 여성 후보(당락 무관), ;로 이음. 1988년 줄은 후보 자료가 없어 빈칸"),
]

# prior-office codes: Pettigrew, Owen & Wanless codebook (doi:10.7910/DVN/26448) and Miller & Camberg codebook
# (doi:10.7910/DVN/CXVMSY) list the same codes (copies in data/static/codebooks/); there is no code 1
CES_RACE = [
    ("race_id", "선거 번호", "트래커의 하원 선거 번호(예: 2020-H-CA-12)"),
    ("year", "선거 연도", "2006–2024 짝수 해"),
    ("state", "주", ""),
    ("district", "선거구 번호", "0 = 주 전체 한 석"),
    ("system", "경선 방식", "races와 같음"),
    ("matchup", "본선 대결(민주-공화 성별)", "F-M, M-F, F-F, M-M, D only, R only(races와 같음)"),
    ("d_nominee", "본선 민주 후보", ""), ("d_nominee_gender", "민주 후보 성별", "F, M"),
    ("r_nominee", "본선 공화 후보", ""), ("r_nominee_gender", "공화 후보 성별", "F, M"),
    ("winner_party", "당선자 정당", "D, R, O"), ("winner_gender", "당선자 성별", "F, M"),
    ("incumbent_running", "현직 출마", "1 = 현직 의원이 나옴"), ("incumbent_party", "현직 정당", "D, R, O"),
    ("pvi", "당파 지수", "Cook 방식, + = 민주 쪽(2008–2024)"), ("pres_d_2party", "직전 대선 민주 양당 득표율(하원)", "%, 1990–2018"),
    ("women_members_since_1990", "기존 여성 의원 수", "races와 같음(이어지는 선거구, 1990년 선거 때 의회부터, 지금 의원 포함)"),
    ("women_members_since_1990_excl", "기존 여성 의원 수(이번 본선 여성 후보 본인 제외)", "races와 같음"),
    ("women_prior_since_1990", "기존 여성 수(의원 또는 1990년부터 본선 후보)", "races와 같음"),
    ("women_prior_since_1990_excl", "기존 여성 수(의원 또는 본선 후보, 본인 제외)", "races와 같음"),
    ("voter_gender", "응답자 성별", "F = 여성, M = 남성(CES gender: 2 = 여성, 1 = 남성)"),
]
CES_VOTES = [
    ("n_dr", "민주·공화 후보를 찍은 응답자 수", "명(가중치 없이 센 수)"),
    ("n_other", "다른 후보를 찍은 응답자 수", "명"),
    ("w_d", "민주 후보 표(가중)", "CES 선거 뒤 가중치(weight_post)의 합. 그 가중치가 없는 해(2006–2010, 2014, 2024)는 선거 전 가중치(weight)"),
    ("w_r", "공화 후보 표(가중)", "같은 방식"),
    ("w_other", "다른 후보 표(가중)", "같은 방식"),
    ("d_share", "민주 후보 양당 지지율", "%, w_d ÷ (w_d + w_r)"),
    ("n_eff", "유효 표본 수", "민주·공화 투표자의 (가중치 합)² ÷ (가중치 제곱합). 비율의 오차를 어림할 때 씀"),
]

CES_INDIVIDUAL = [
    ("case_id", "CES 응답자 번호", "CES 누적 파일의 case_id"), ("year", "선거 연도", "2008–2024 짝수 해"), ("race_id", "선거 번호", "트래커의 하원 선거 번호"),
    ("race_n", "선거 번호(숫자)", "묶음 표준오차용(vce(cluster race_n))"), ("state", "주", ""), ("district", "선거구", "0 = 주 전체 한 석"),
    ("matchup", "본선 대결(민주-공화 성별)", "F-M 민주 여성 대 공화 남성, M-F 민주 남성 대 공화 여성, F-F 둘 다 여성, M-M 둘 다 남성"),
    ("mixed", "여성 대 남성 선거", "1 = F-M 또는 M-F(회귀모형은 이 선거만 씀)"), ("ff", "둘 다 여성인 선거", "1 = F-F(거를 때 쓰는 더미)"), ("mm", "둘 다 남성인 선거", "1 = M-M(거를 때 쓰는 더미)"),
    ("vote_d", "민주 후보를 찍음", "1 = 민주 후보, 0 = 공화 후보(모든 선거)"),
    ("d_female", "민주 후보가 여성", "1/0"), ("r_female", "공화 후보가 여성", "1/0"),
    ("d_race", "민주 후보 인종", "순서대로 ① 여성은 CAWP 코드 ② 출판된 후보 인종 코드 모음(사용자 제공 파일, 원출처는 data/static/nominee_race.csv) ③ 출처를 남긴 웹 조사 ④ Reflective Democracy Campaign 공표 분류(사용자 파일에 따로 표시) ⑤ 의회에 있었으면 소수 인종 의원 명단의 코드 ⑥ 명단에 없는 의원은 W(추정). 빈칸 = 모름"),
    ("r_race", "공화 후보 인종", "같은 방식"),
    ("d_race_src", "민주 후보 인종의 근거", "cawp = CAWP, file = 출판 코드 모음, research = 웹 조사, user = 사용자가 직접 채운 코드(근거는 note), rdc = Reflective Democracy Campaign 공표 분류(개별 기록의 조사·추정 방식 구분 안 됨), surname = 히스패닉(추정): 성과 이름이 모두 히스패닉 쪽인 경우(확률 0.9 이상, 미국 인구조사 2010 성씨표 × Tzioumis 2018 이름표), list = 소수 인종 의원 명단, member = 의원이었고 명단에 없음(백인으로 봄), none = 모름"),
    ("r_race_src", "공화 후보 인종의 근거", "같은 코드"),
    ("same_race_d", "민주 후보와 같은 인종", "1 = 응답자 인종이 민주 후보의 코드 가운데 하나. 후보 인종을 모르면 0"),
    ("same_race_r", "공화 후보와 같은 인종", "같은 방식"), ("d_race_unk", "민주 후보 인종 모름", "1/0"), ("r_race_unk", "공화 후보 인종 모름", "1/0"),
    ("d_nonwhite", "민주 후보가 백인 아님", "1/0, 모르면 0"), ("r_nonwhite", "공화 후보가 백인 아님", "1/0, 모르면 0"),
    ("d_inc", "민주 후보가 현직", "1/0"), ("r_inc", "공화 후보가 현직", "1/0"),
    ("wparty", "여성 후보의 정당", "D = 민주당 여성 대 공화당 남성, R = 공화당 여성 대 민주당 남성(여성 대 남성 선거만, 그 밖은 빈칸)"),
    ("vote_woman", "여성 후보를 찍음", "1 = 여성 후보, 0 = 남성 후보(CES voted_rep_party, 선거 뒤 조사; 여성 대 남성 선거만)"), ("female", "여성 유권자", "1 = 여성, 0 = 남성(CES gender)"),
    ("weight", "CES 가중치", "선거 뒤 가중치(weight_post), 없는 해(2008·2010·2014·2024)는 선거 전 가중치(weight)"),
    ("pid", "정당 일체감", "D = 민주 쪽(강한·약한·기우는), R = 공화 쪽, I = 무당파·모름(CES pid7)"),
    ("copart", "여성 후보와 같은 정당 지지", "1 = pid가 여성 후보의 정당(여성 대 남성 선거만)"), ("outpart", "여성 후보와 반대 정당 지지", "1 = pid가 상대 정당(기준: 무당파·모름; 여성 대 남성 선거만)"),
    ("rrace", "응답자 인종", "CES race_h(히스패닉이면 H)를 CAWP 코드로: W 백인, B 흑인, H 히스패닉, AP 아시아계, NA 원주민, MENA 중동계, MU 여러 인종, OTHER 그 밖"),
    ("w_race", "여성 후보 인종", "d_race 또는 r_race 가운데 여성 쪽(여성 대 남성 선거만; 빈칸 = 모름)"),
    ("m_race", "남성 후보 인종", "d_race 또는 r_race 가운데 남성 쪽(여성 대 남성 선거만; 빈칸 = 모름)"),
    ("m_race_src", "남성 후보 인종의 근거", "file, research, user, rdc, surname, list, member, none(d_race_src와 같은 코드)"),
    ("same_race_w", "여성 후보와 같은 인종", "1 = 응답자 인종이 여성 후보의 코드 가운데 하나. 여성 후보 인종을 모르면 빈칸(모형에서 빠짐)"),
    ("same_race_m", "남성 후보와 같은 인종", "1 = 응답자 인종이 남성 후보의 코드 가운데 하나. 남성 후보 인종을 모르면 0"),
    ("m_race_unk", "남성 후보 인종 모름", "1 = 어느 자료에서도 인종을 찾지 못한 남성 후보(대개 약한 도전자라 후보 경쟁력도 함께 담김)"),
    ("w_nonwhite", "여성 후보가 백인 아님", "1 = 코드가 W 하나만이 아님"), ("m_nonwhite", "남성 후보가 백인 아님", "1 = 코드가 W 하나만이 아님. 모르면 0"),
    ("r_black", "응답자 흑인", "1/0(기준: 백인)"), ("r_hisp", "응답자 히스패닉", "1/0"), ("r_asian", "응답자 아시아계", "1/0"), ("r_other", "응답자 그 밖 인종", "1/0(원주민·중동계·여러 인종·그 밖)"),
    ("college", "4년제 대졸 이상", "1 = CES educ 4-Year 또는 Post-Grad"), ("age", "나이", "세(CES age, 없으면 연도 − 출생 연도)"), ("age10", "나이/10", ""),
    ("ideo", "이념", "L 진보(매우 진보 포함), M 중도, C 보수(매우 보수 포함), NS 모름(CES ideo5)"), ("lib", "진보", "1/0(기준: 중도)"), ("con", "보수", "1/0"), ("ideo_ns", "이념 모름", "1/0"),
    ("pvi", "당파 지수", "Cook 방식, + = 민주 쪽"), ("rural", "농촌 인구 비율", "%"), ("black_nh", "선거구 흑인 비율", "%"), ("hisp_d", "선거구 히스패닉 비율", "%"),
    ("asian_nh", "선거구 아시아계 비율", "%"), ("ba_plus", "선거구 대졸 비율", "%"), ("inc10k", "선거구 가구 소득 중앙값", "만 달러"),
    ("w_inc", "여성 후보가 현직", "1/0(여성 대 남성 선거만)"), ("m_inc", "남성 후보가 현직", "1/0(여성 대 남성 선거만)"),
    ("women_members_since_1990", "기존 여성 의원 수(본인 포함)", "races와 같음"), ("women_members_since_1990_excl", "기존 여성 의원 수(본인 제외)", "races와 같음"),
    ("women_prior_since_1990", "기존 여성 의원·후보 수(본인 포함)", "races와 같음"), ("women_prior_since_1990_excl", "기존 여성 의원·후보 수(본인 제외)", "races와 같음"),
]
CES_NOMINEE = [
    ("race_id", "선거 번호", "트래커의 선거 번호"), ("year", "선거 연도", "2008–2024 짝수 해(하원 분석 대상), 2026"), ("chamber", "의회", "H = 하원, S = 상원(2026만)"),
    ("state", "주", ""), ("district", "선거구", "0 = 주 전체 한 석, 상원"),
    ("matchup", "본선 대결(민주-공화 성별)", "F-M, M-F, F-F, M-M; 2026은 D only·R only(한 정당 후보만)도 있음"), ("party", "정당", "D = 민주, R = 공화(본선 투표용지 기준)"), ("name", "후보 이름", ""),
    ("female", "여성 후보", "1/0"), ("incumbent", "현직", "1/0"),
    ("race", "후보 인종", "CAWP 코드(W, B, H, AP, NA, MENA, MU, OTHER), 여럿이면 /로 이음. 빈칸 = 모름. 정하는 순서는 ces_individual의 d_race와 같음"),
    ("race_src", "인종 근거", "cawp, file, research, user, rdc, surname, list, member, none(ces_individual의 d_race_src와 같은 코드)"),
    ("source", "인종 출처", "file·research·rdc는 원출처 이름(예: Hassell & Visalvanich, 웹 조사), user는 사용자 입력과 날짜, surname은 쓴 이름표, cawp는 CAWP, list·member는 의원 명단 설명"),
    ("source_url", "출처 주소", "여럿이면 ' ; ' 또는 ' | '로 이음"), ("note", "메모", "웹 조사는 근거 문장, 다른 해 자료·연결 자료의 같은 사람, surname은 확률 등"),
    ("bioguide", "의회 인명록 번호", "의원이었던 사람만(congress-legislators)"),
]
CES_MODELS = [
    ("model", "모형 이름", "여성 후보 정당_기존 여성 변수_추정 방법"), ("woman_party", "여성 후보의 정당", "D, R"),
    ("prior_var", "기존 여성 변수", "이 변수가 0보다 크면 '기존 여성 있음'(prior = 1)"), ("estimator", "추정 방법", "lpm = 선형확률모형(가중 최소제곱), logit = 로짓(가중 의사가능도)"),
    ("term", "변수", "female, prior, female_x_prior(교호작용), 통제변수, y연도(기준 2008), const"), ("label", "변수 설명", ""),
    ("coef", "계수", "선형확률모형은 확률(0–1), 로짓은 로그 오즈"), ("se", "표준오차", "선거 단위로 묶음(Stata vce(cluster)와 같은 보정)"),
    ("stat", "t 또는 z", ""), ("p", "p 값", "선형확률모형 t(선거 수 − 1), 로짓 정규분포"), ("ci_lo", "95% 범위 아래", ""), ("ci_hi", "95% 범위 위", ""),
    ("n", "응답자 수", ""), ("n_races", "선거 수", ""), ("fit", "설명력", "선형확률모형 R², 로짓 McFadden 의사 R²"),
]
CES_PRED = [
    ("model", "모형 이름", "ces_models와 같음"), ("woman_party", "여성 후보의 정당", ""), ("prior_var", "기존 여성 변수", ""), ("estimator", "추정 방법", ""),
    ("quantity", "값", "F1·M1·F0·M0 = 여성·남성 유권자 × 기존 여성 있음(1)·없음(0)의 예측 확률, gap1·gap0 = 여 − 남, dF·dM = 있음 − 없음, did = 차이의 차이"),
    ("label", "값 설명", ""), ("est", "추정값", "%(예측 확률) 또는 %p(차이). 모든 응답자를 그 성별·기존 여성으로 바꾼 뒤 다른 변수는 실제 값 그대로 둔 가중 평균"),
    ("se", "표준오차", "델타 방법, 선거 단위 묶음"), ("p", "p 값", ""), ("ci_lo", "95% 범위 아래", ""), ("ci_hi", "95% 범위 위", ""), ("n", "응답자 수", ""), ("n_races", "선거 수", ""),
]

OFFICE = [
    ("30", "현직 하원의원(current incumbent)"), ("29", "주 전체 선출직(주지사·부지사 등)"), ("28", "주 상원의원"), ("27", "주 하원의원"),
    ("26", "시장"), ("25", "판사(선출)"), ("24", "지방검사(district or prosecuting attorney)"), ("23", "시의회 의원(city council)"),
    ("22", "그 밖의 선출직"), ("21", "직전 의회의 현직이었다가 낙선한 사람"), ("20", "전직 하원의원(직전 의회가 아님)"), ("19", "전직 상원의원"),
    ("18", "법무장관(attorney general)"), ("17", "주 검사(state's attorney)"), ("16", "주 위원(state commissioner)"), ("15", "시의원(alderman)"),
    ("14", "보안관(sheriff)"), ("13", "재무관(treasurer)"), ("12", "기업인·사업주"), ("11", "언론인"), ("10", "변호사"), ("9", "판사(임명)"),
    ("8", "성직자"), ("7", "농장·목장주"), ("6", "군인"), ("5", "지역 정당 간부·활동가"), ("4", "의사·치과의사·수의사"), ("3", "교사·교수·교육자"),
    ("2", "그 밖의 비선출 공직, 전 의회 보좌관·자문"), ("0", "선출직 경험 없음"),
]


def entries():
    out = []
    for t, _, _ in TABLES:
        rows = {"candidates": COMMON + CANDIDATES, "primaries": COMMON + PRIMARIES, "races": COMMON + RACES,
                "lineage_2026": LINEAGE_2026, "lineage_all": LINEAGE_ALL, "ces_districts": CES_RACE + CES_VOTES,
                "ces_individual": CES_INDIVIDUAL, "ces_models": CES_MODELS, "ces_models_pred": CES_PRED, "ces_nominee_race": CES_NOMINEE,
                "ces_districts_pid": CES_RACE + [("pid3", "응답자 정당 일체감", "D = 민주당, R = 공화당, I = 무당파·기타·잘 모름(CES pid3: 1 민주, 2 공화, 3 무당파, 4 기타, 5 잘 모름)")] + CES_VOTES}[t]
        out += [dict(table=t, name=n, label=l, values=v) for n, l, v in rows]
    return out


def write():
    """docs/data/codebook.json/.csv for the public tables; the CES tables go to docs/data/ces/codebook.json/.csv,
    which only the CES window opens"""
    titles = {t: ti for t, ti, _ in TABLES}
    allv = entries()
    for folder, keep, office in ((OUT, lambda t: not t.startswith("ces_"), True), (os.path.join(OUT, "ces"), lambda t: t.startswith("ces_"), False)):
        os.makedirs(folder, exist_ok=True)
        data = dict(tables=[dict(table=t, title=ti, unit=u) for t, ti, u in TABLES if keep(t)], vars=[e for e in allv if keep(e["table"])],
                    office=[dict(code=c, meaning=m) for c, m in OFFICE] if office else [])
        with open(os.path.join(folder, "codebook.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
        with open(os.path.join(folder, "codebook.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["자료", "변수", "뜻", "값·단위"])
            for e in data["vars"]:
                w.writerow([titles[e["table"]], e["name"], e["label"], e["values"]])
            for o in data["office"]:
                w.writerow(["후보: office(이전 경력) 코드", o["code"], o["meaning"], "Pettigrew 외·Miller & Camberg 코드북"])


if __name__ == "__main__":
    write()
    print("codebook:", len(entries()), "variables")
