# 미국 의회 여성 후보 트래커

미국 하원·상원 선거(1990년~)에서 여성 후보가 민주당·공화당 경선과 본선에서 어느 지역구에서 이겼는지 보여 주고, 후보·지역구 특징에 따라 무엇이 다른지 비교하는 페이지와 데이터베이스입니다.

- 페이지: https://jongkonlee.github.io/US_female_candidates/
- 갱신: GitHub Actions가 매일 한 번(한국 시간 07:37) 자료를 다시 받아 만듭니다. 컴퓨터가 꺼져 있어도 됩니다.
- 데이터: [`data/`](data/) — 후보·경선·선거 단위 CSV. 변수 설명과 규칙은 [`data/README.md`](data/README.md)에 있습니다. 페이지의 '내려받기' 탭에서 원하는 연도만 CSV나 Stata(.dta)로 받을 수도 있습니다.

## 페이지에서 볼 수 있는 것

| 탭 | 내용 |
|---|---|
| 요약 | 그해 여성 후보·경선 승자·본선 후보·당선자 수, 1990년부터의 흐름 |
| 지역구 지도 | 선거구마다 민주·공화 경선과 본선 결과를 색으로 표시. 주 위치에 맞춘 칸 지도와 실제 선거구 모양 지도(주를 누르면 확대) 두 가지 |
| 어디서 이기나 | 지역구 당파 성향, 현직 출마, 이전 여성 의원, 농촌 비율, 인구 구성, 후보 수, 여성 후보의 위치·인종·이전 경력별 비교. '출마한 비율'과 '출마했을 때 이긴 비율'을 나눠 봅니다 |
| 남성과 맞붙을 때 | 남녀가 함께 나온 경쟁 경선에서 여성의 승률과 득표율, 본선에서 같은 성향 지역구 대비 여성 후보의 득표 |
| 이전 여성 의원 | 이전에 여성 의원이 있었던 선거구와 없었던 선거구 비교 |
| 선거 목록 | 선거별 양당 후보, 당선자, 경선의 여성 후보 수 |

## 자료와 출처

- 연방선거관리위원회(FEC), *Federal Elections* 2002–2022 (공식 경선·결선·본선 결과)
- MIT Election Data and Science Lab, "U.S. House 1976–2024." Harvard Dataverse, doi:10.7910/DVN/IG0UN2 (CC0): 1990–2000년과 2024년 하원 본선(주 공식 결과). 방명록 때문에 손으로 받은 사본을 `data/static/`에 둡니다
- Pettigrew, Stephen, Karen Owen, and Emily Wanless. "U.S. House Primary Election Results (1956–2010)." Harvard Dataverse, doi:10.7910/DVN/26448 (CC0)
- Miller, Michael G., and Nicki Camberg. "U.S. House Primary Election Results (2012–2018)." Harvard Dataverse, doi:10.7910/DVN/CXVMSY (CC0)
- Center for American Women and Politics (CAWP), Eagleton Institute of Politics, Rutgers University. Congressional Women Candidates Database 1990–2024, 그리고 "Women Candidates 2026" 후보 목록(2026-11-05에 받은 판). CAWP 자료는 비상업적 이용을 권장하며 출처를 밝혀야 합니다(상업적 이용은 CAWP의 서면 허락 필요).
- 위키백과 선거 문서(1990–2000년 상원, 2024년 이후 하원 경선과 상원, 2026년 하원 본선, 루이지애나 1990–1996년 일부): 비공식 자료, CC BY-SA. FEC 2024년판이 나오면 자동으로 공식 결과로 바뀝니다.
- congress-legislators (unitedstates 프로젝트): 의원 성별·임기
- 선거구 경계(실제 지도): Jeffrey B. Lewis, Brandon DeVine, Lincoln Pitcher, and Kenneth C. Martis. (2013) Digital Boundary Definitions of U.S. Congressional Districts, 1789-2012 (저자들이 119대 의회까지 갱신). https://github.com/JeffreyBLewis/congressional-district-boundaries (MIT), 2026-11-05 내려받음. 2026년에 선거구를 새로 그린 10개 주는 위키미디어 공용의 지도 자료("Data:{주}'s {n}th congressional district (2027–).map", CC0, 각 주 정부·의회 원본에서 옮긴 것)를 `pipeline/fetch_maps_2026.py`로 받아 `data/static/boundaries_2026/`에 둡니다(일부만 새로 그린 노스캐롤라이나·플로리다의 나머지 선거구는 2024년 경계)
- 지역구 특징(2008–2024): 미국 인구조사국 원본 파일과 Cook 방식으로 계산한 당파 지수([여성정책 트래커](https://github.com/jongkonlee/US_gender_policy)와 같은 값)

## 구조

| 위치 | 내용 |
|---|---|
| `pipeline/collect.py` | 자료 받기. 매일(`--daily`): 2024년과 올해 위키백과 문서, 의원 명부, CAWP·FEC 새 판 확인. 전체(`--full`): 모든 원자료 |
| `pipeline/build_db.py` | 데이터베이스 만들기. 1990–2022년은 `data/static/history_rows.json.gz`에 저장해 두고 매일은 2024년 이후만 새로 읽습니다 |
| `pipeline/site_data.py` | 페이지용 자료(`docs/data/`) |
| `pipeline/fec_results.py`, `wiki.py`, `names.py` | FEC 엑셀, 위키백과 결과 표, 이름 맞추기 |
| `pipeline/medsl.py` | MEDSL 하원 본선 결과 읽기(정당 줄 합치기, 무투표·결선 처리) |
| `pipeline/maps.py` | 실제 지도 자료(`docs/data/maps/`) 만들기. 경계는 날마다 바뀌지 않아 손으로 한 번 돌립니다(파일 첫머리에 방법) |
| `data/static/` | 자주 바뀌지 않는 입력: CAWP 파일과 2026 후보 목록, MEDSL 하원 결과, 하원 경선 자료 요약, 지역구 특징, 이름 성별표, 위키 문서 대명사 확인 결과 |
| `docs/` | 페이지 |

1990–2022년 자료를 원자료부터 다시 만들려면 Actions의 'update data and site'를 수동으로 실행하면서 `full_rebuild`를 켭니다(30분 안팎).
