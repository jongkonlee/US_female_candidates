'use strict';
/* 미국 의회 여성 후보 트래커 — data in data/index.json and data/y{year}.json (built by pipeline/site_data.py) */

const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = x => (x === null || x === undefined || x === '' || Number.isNaN(+x)) ? null : +x;
const fmt = (x, d = 1) => num(x) === null ? '–' : (+x).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (a, b, d = 1) => b ? fmt(100 * a / b, d) + '%' : '–';
const mean = a => { const v = a.map(num).filter(x => x !== null); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };
const median = a => { const v = a.map(num).filter(x => x !== null).sort((p, q) => p - q); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };
const groupBy = (a, k) => { const m = {}; for (const x of a) (m[x[k]] = m[x[k]] || []).push(x); return m; };

const STATE_KO = { AL: '앨라배마', AK: '알래스카', AZ: '애리조나', AR: '아칸소', CA: '캘리포니아', CO: '콜로라도', CT: '코네티컷', DE: '델라웨어', FL: '플로리다', GA: '조지아', HI: '하와이', ID: '아이다호', IL: '일리노이', IN: '인디애나', IA: '아이오와', KS: '캔자스', KY: '켄터키', LA: '루이지애나', ME: '메인', MD: '메릴랜드', MA: '매사추세츠', MI: '미시간', MN: '미네소타', MS: '미시시피', MO: '미주리', MT: '몬태나', NE: '네브래스카', NV: '네바다', NH: '뉴햄프셔', NJ: '뉴저지', NM: '뉴멕시코', NY: '뉴욕', NC: '노스캐롤라이나', ND: '노스다코타', OH: '오하이오', OK: '오클라호마', OR: '오리건', PA: '펜실베이니아', RI: '로드아일랜드', SC: '사우스캐롤라이나', SD: '사우스다코타', TN: '테네시', TX: '텍사스', UT: '유타', VT: '버몬트', VA: '버지니아', WA: '워싱턴', WV: '웨스트버지니아', WI: '위스콘신', WY: '와이오밍' };
const REGION = {};
[['북동부', 'CT ME MA NH RI VT NJ NY PA'], ['중서부', 'IL IN MI OH WI IA KS MN MO NE ND SD'], ['남부', 'DE FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX'], ['서부', 'AZ CO ID MT NV NM UT WY AK CA HI OR WA']]
  .forEach(([r, s]) => s.split(' ').forEach(x => { REGION[x] = r; }));
const TILE = { AK: [0, 0], ME: [11, 0], WI: [6, 1], VT: [10, 1], NH: [11, 1], WA: [1, 2], ID: [2, 2], MT: [3, 2], ND: [4, 2], MN: [5, 2], IL: [6, 2], MI: [7, 2], NY: [9, 2], MA: [10, 2],
  OR: [1, 3], NV: [2, 3], WY: [3, 3], SD: [4, 3], IA: [5, 3], IN: [6, 3], OH: [7, 3], PA: [8, 3], NJ: [9, 3], CT: [10, 3], RI: [11, 3], CA: [1, 4], UT: [2, 4], CO: [3, 4], NE: [4, 4], MO: [5, 4], KY: [6, 4],
  WV: [7, 4], VA: [8, 4], MD: [9, 4], DE: [10, 4], AZ: [2, 5], NM: [3, 5], KS: [4, 5], AR: [5, 5], TN: [6, 5], NC: [7, 5], SC: [8, 5], OK: [4, 6], LA: [5, 6], MS: [6, 6], AL: [7, 6], GA: [8, 6], HI: [0, 7], TX: [4, 7], FL: [9, 7] };
const PARTY = { D: '민주', R: '공화', O: '기타' };
const SYSTEM = { party: '정당 경선', blanket: '모든 정당 한 투표용지(정당별 1위)', top2: '상위 2인 경선', top4: '상위 4인 경선', jungle: '루이지애나식 1차 투표' };
const PARTY_PRIMARY = new Set(['contested', 'runoff', 'uncontested', 'convention']);
const CONTEST = { contested: '경쟁 경선', runoff: '경쟁 경선(결선까지)', uncontested: '단독 후보', convention: '전당대회·경선 기록 없음', top2: '상위 2인 경선', top4: '상위 4인 경선', jungle: '루이지애나식' };
const RACE_ETH = { W: '백인', B: '흑인', H: '히스패닉', AP: '아시아·태평양계', MENA: '중동·북아프리카계', NA: '원주민', MU: '여러 인종' };
const QUAL = { 0: '선출직 경험 없음', 1: '선출직 경험 있음', 2: '현직', 3: '전직 하원의원' };
const GSRC = { 'CAWP': 'CAWP 명단', 'not in CAWP': 'CAWP 명단에 없음(남성으로 봄)', 'first name': '이름', 'Wikipedia page (pronouns)': '위키백과 본인 문서(대명사)',
  'member or earlier candidate': '의원 명부·예전 경선 자료', 'CAWP (earlier race)': '예전 CAWP 기록', 'CAWP (other year)': '다른 해 CAWP 기록의 같은 여성', 'research (gender_overrides.csv)': '조사(대명사 등, gender_overrides.csv)', 'unknown': '모름', 'Pettigrew and first name (not in CAWP)': 'Pettigrew 외 자료·이름', 'Pettigrew': 'Pettigrew 외 자료' };
const RSRC = { 'FEC': 'FEC 공식 결과', 'MEDSL': 'MEDSL(MIT 선거연구소가 모은 주 공식 결과)', 'Wikipedia': '위키백과(비공식)', 'Wikipedia overview': '위키백과 전체 표(득표율만)', 'Pettigrew-Owen-Wanless': 'Pettigrew 외(하원 경선)', 'Miller-Camberg': 'Miller·Camberg(하원 경선)', 'CAWP only': 'CAWP(득표 기록 없음)' };
const C = { d: 'var(--d)', r: 'var(--r)', w: 'var(--w)', none: 'var(--none)', na: 'var(--na)', dl: '#b9cfe9', rl: '#f0c1bd', open: '#efe2b0', ff: 'var(--ff)', fm: 'var(--fm)', mf: 'var(--mf)', mm: 'var(--mm)' };

const S = { ch: 'H', year: null, tab: 'summary', period: 'year', partyOnly: false, layer: 'gen', target: 'D', unit: 'district', crit: 'lean',
  q: '', onlyWomen: false, open: null, idx: null, cache: {}, ds: 'candidates', dlScope: 'year', mapKind: 'tile', zoom: null, priorMode: 'map' };
const MAPS = { idx: null, c: {}, s: {} };

/* ---------- data ---------- */
async function getJSON(u) { const r = await fetch(u, { cache: 'no-cache' }); if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); }
function unpack(d) {
  const mk = (f, rows) => rows.map(r => { const o = {}; f.forEach((k, i) => { o[k] = r[i]; }); o.year = d.year; return o; });
  const Y = { year: d.year, c: mk(d.cf, d.c), p: mk(d.pf, d.p), r: mk(d.rf, d.r) };
  Y.rIndex = Object.fromEntries(Y.r.map(x => [x.race_id, x]));
  Y.cBy = groupBy(Y.c, 'race_id');
  Y.pBy = groupBy(Y.p, 'race_id');
  Y.presMed = { H: median(Y.r.filter(x => x.chamber === 'H').map(x => x.pres_d_2party)) };
  return Y;
}
async function loadYear(y) { if (!S.cache[y]) S.cache[y] = unpack(await getJSON(`data/y${y}.json`)); return S.cache[y]; }
function periodYears() {
  if (S.period === 'year') return [S.year];
  if (S.period === 'all') return S.idx.years.slice();
  const d = +S.period; return S.idx.years.filter(y => y >= d && y < d + 10);
}
async function loadPeriod() { const ys = periodYears(); await Promise.all(ys.map(loadYear)); return ys.map(y => S.cache[y]); }
const periodLabel = () => S.period === 'year' ? `${S.year}년` : S.period === 'all' ? `${S.idx.years[0]}~${S.idx.years[S.idx.years.length - 1]}년` : `${S.period}년대`;
const isCurrent = y => y === S.idx.years[S.idx.years.length - 1] && y > S.idx.cawp_last_year;
const listYear = () => (S.idx.cawp_list || {}).year;
function addListLabels() {
  const y = listYear();
  if (!y) return;
  Object.assign(GSRC, {
    [`CAWP ${y} list`]: `CAWP ${y} 후보 목록`, [`not in CAWP ${y} list`]: `CAWP ${y} 목록에 없음(남성으로 봄)`,
    [`Wikipedia page (pronouns); not in CAWP ${y} list`]: `위키백과 본인 문서(대명사), CAWP ${y} 목록에는 없음`,
    [`CAWP (earlier race); not in CAWP ${y} list`]: `예전 CAWP 기록, ${y} 목록에는 없음`,
    [`member or earlier candidate; not in CAWP ${y} list`]: `의원 명부·예전 경선 자료, ${y} 목록에는 없음`,
    [`not in CAWP ${y} list; woman's first name`]: `CAWP ${y} 목록에 없지만 여성 이름이라 모름으로 둠` });
}
const chName = ch => ch === 'H' ? '하원' : '상원';
function raceLabel(r) {
  const sp = r.special ? ' 특별선거' : '';
  return r.chamber === 'H' ? `${r.state}-${r.district === 0 ? 'AL' : r.district} (${STATE_KO[r.state] || r.state} ${r.district === 0 ? '전역구' : r.district + '선거구'})${sp}` : `${STATE_KO[r.state] || r.state} 상원${sp}`;
}
// district lean: Cook-style PVI when available (2008-), otherwise the presidential vote minus that year's median district
function lean(r, Y) {
  if (num(r.pvi) !== null) return +r.pvi;
  if (num(r.pres_d_2party) !== null && r.chamber === 'H' && Y.presMed.H !== null) return r.pres_d_2party - Y.presMed.H;
  return null;
}
const leanLabel = x => x === null ? '' : (Math.round(x) === 0 ? '균형' : x > 0 ? `민주 +${Math.round(x)}` : `공화 +${Math.round(-x)}`);
const gtag = g => g === 'F' ? '<span class="badge f">여성</span>' : g === 'M' ? '<span class="badge">남성</span>' : '<span class="badge">성별 모름</span>';
function primaryOk(p) { return !S.partyOnly || PARTY_PRIMARY.has(p.contest); }

/* ---------- state & controls ---------- */
function writeHash() {
  const p = new URLSearchParams();
  p.set('c', S.ch); p.set('y', S.year); if (S.tab !== 'summary') p.set('t', S.tab); if (S.period !== 'year') p.set('p', S.period);
  if (S.partyOnly) p.set('po', '1'); if (S.layer !== 'gen') p.set('l', S.layer); if (S.target !== 'D') p.set('tg', S.target);
  if (S.unit !== 'district') p.set('u', S.unit); if (S.crit !== 'lean') p.set('k', S.crit); if (S.open) p.set('open', S.open);
  if (S.mapKind !== 'tile') p.set('mk', S.mapKind); if (S.zoom) p.set('z', S.zoom); if (S.priorMode !== 'map') p.set('pm', S.priorMode);
  history.replaceState(null, '', '#' + p.toString());
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get('c')) S.ch = p.get('c') === 'S' ? 'S' : 'H';
  if (p.get('y') && S.idx.years.includes(+p.get('y'))) S.year = +p.get('y');
  if (p.get('t')) S.tab = p.get('t') === 'voters' ? 'prior' : p.get('t'); if (p.get('p')) S.period = p.get('p'); S.partyOnly = p.get('po') === '1';
  if (p.get('l')) S.layer = p.get('l'); if (p.get('tg')) S.target = p.get('tg'); if (p.get('u')) S.unit = p.get('u'); if (p.get('k')) S.crit = p.get('k');
  S.open = p.get('open');
  if (p.get('mk') === 'real') S.mapKind = 'real'; if (p.get('z') && STATE_KO[p.get('z')]) S.zoom = p.get('z'); if (p.get('pm') === 'cum') S.priorMode = 'cum';
}
function syncControls() {
  document.querySelectorAll('#chamberSeg button').forEach(b => b.classList.toggle('on', b.dataset.ch === S.ch));
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === S.tab));
  $('#yearSel').value = S.year; $('#periodSel').value = S.period; $('#partyOnly').checked = S.partyOnly;
}

/* ---------- small charts ---------- */
function lineChart(series, opt) {
  // series: [{name, color, pts:[[x,y]]}], y in %
  const W = 430, H = 220, L = 38, R = 10, T = 10, B = 28;
  const xs = series.flatMap(s => s.pts.map(p => p[0]));
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const ymax = Math.max(10, Math.ceil(Math.max(...series.flatMap(s => s.pts.map(p => p[1]).filter(v => v !== null))) / 10) * 10);
  const sx = x => L + (W - L - R) * (x - x0) / Math.max(1, x1 - x0), sy = y => T + (H - T - B) * (1 - y / ymax);
  let g = '';
  for (let v = 0; v <= ymax; v += ymax > 50 ? 20 : 10) g += `<line x1="${L}" x2="${W - R}" y1="${sy(v)}" y2="${sy(v)}" stroke="var(--line)"/><text x="${L - 6}" y="${sy(v) + 4}" text-anchor="end">${v}%</text>`;
  for (let x = Math.ceil(x0 / 4) * 4; x <= x1; x += 4) g += `<text x="${sx(x)}" y="${H - 10}" text-anchor="middle">${x}</text>`;
  for (const s of series) {
    const pts = s.pts.filter(p => p[1] !== null);
    g += `<polyline fill="none" stroke="${s.color}" stroke-width="2.2" points="${pts.map(p => `${sx(p[0])},${sy(p[1])}`).join(' ')}"/>`;
    g += pts.map(p => `<circle cx="${sx(p[0])}" cy="${sy(p[1])}" r="${p[2] ? 4 : 2.6}" fill="${p[2] ? 'var(--card)' : s.color}" stroke="${s.color}" stroke-width="1.5"><title>${p[0]} ${esc(s.name)}: ${fmt(p[1])}%${p[2] ? ' (개표 중·비공식)' : ''}</title></circle>`).join('');
  }
  const leg = series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('');
  return `<div class="chart-block"><b>${esc(opt.title)}</b><div class="legend">${leg}</div><div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opt.title)}">${g}</svg></div>${opt.cap ? `<div class="cap">${opt.cap}</div>` : ''}</div>`;
}
function bars(items, opt) {
  // items: [{lab, v (0-100 or null), n, color, vt (value text, optional)}]; opt: {max, head (title over the labels), wide}
  const head = opt.head ? `<div class="bar-head">${esc(opt.head)}</div>` : '';
  return head + items.map(it => `<div class="bar${opt.wide ? ' wide' : ''}"><div class="lab" title="${esc(it.lab)}">${esc(it.lab)} <span class="muted">(${it.n})</span></div>
    <div class="track"><div class="fill" style="width:${it.v === null ? 0 : Math.max(0, Math.min(100, it.v * 100 / (opt.max || 100)))}%;background:${it.color || 'var(--w)'}"></div></div>
    <div class="val">${it.vt !== undefined ? esc(it.vt) : it.v === null ? '–' : fmt(it.v) + '%'}</div></div>`).join('');
}

/* ---------- views ---------- */
async function render() {
  if (!S.idx) return;
  syncControls(); writeHash();
  const tab = S.tab;
  $('#main').innerHTML = '<p class="loading">불러오는 중…</p>';
  try {
    const f = { summary: viewSummary, map: viewMap, where: viewWhere, vsmen: viewVsMen, prior: viewPrior, list: viewList, download: viewDownload, about: viewAbout }[tab] || viewSummary;
    const html = await f();
    if (tab !== S.tab) return;
    $('#main').innerHTML = html;
    bindMain();
  } catch (e) { $('#main').innerHTML = `<p>자료를 불러오지 못했습니다: ${esc(e.message)}</p>`; console.error(e); }
}

async function viewSummary() {
  const Y = await loadYear(S.year);
  const R = Y.r.filter(r => r.chamber === S.ch), P = Y.p.filter(p => p.chamber === S.ch && primaryOk(p)), Cn = Y.c.filter(c => c.chamber === S.ch);
  const cur = isCurrent(S.year);
  const card = (k, v, sub) => `<div class="card"><div class="k">${k}</div><div class="v">${v}</div>${sub ? `<div class="muted" style="font-size:.8rem">${sub}</div>` : ''}</div>`;
  const by = party => ({
    women: Cn.filter(c => c.gender === 'F' && (c.party === party)).length,
    pw: P.filter(p => p.party === party && p.woman_won === 1).length, pn: P.filter(p => p.party === party).length,
    nom: R.filter(r => r[party.toLowerCase() + '_nominee_gender'] === 'F').length, nomN: R.filter(r => r[party.toLowerCase() + '_nominee']).length,
    won: R.filter(r => r.winner_party === party && r.winner_gender === 'F').length, seats: R.filter(r => r.winner_party === party).length });
  const d = by('D'), r = by('R');
  const decided = R.filter(x => x.winner).length;
  let h = `<p class="muted">${S.year}년 ${chName(S.ch)} 선거 ${R.length}곳${cur ? ` · <span class="prov">개표 중: 당선이 확인된 곳 ${decided}곳(위키백과 기준, 비공식)</span>` : ''}${S.year === listYear() ? ` · 성별: CAWP ${S.year} 후보 목록(${esc(S.idx.cawp_list.downloaded)} 내려받음) 기준(설명 탭)` : (S.year > S.idx.cawp_last_year ? ' · 성별은 CAWP 명단이 나오기 전이라 다른 방법으로 정함(설명 탭)' : '')}</p>
  <div class="cards">
    ${card('여성 후보', `<span class="pD">${d.women}</span> / <span class="pR">${r.women}</span>`, '민주 / 공화 (경선·본선에 이름을 올린 사람)')}
    ${card('여성이 이긴 경선', `<span class="pD">${d.pw}</span> / <span class="pR">${r.pw}</span>`, `민주 ${pct(d.pw, d.pn, 0)} · 공화 ${pct(r.pw, r.pn, 0)}`)}
    ${card('여성 본선 후보', `<span class="pD">${d.nom}</span> / <span class="pR">${r.nom}</span>`, `민주 ${pct(d.nom, d.nomN, 0)} · 공화 ${pct(r.nom, r.nomN, 0)}`)}
    ${card('여성 당선', `<span class="pD">${d.won}</span> / <span class="pR">${r.won}</span>`, `${cur ? '확인된 당선 기준 · ' : ''}의석의 ${pct(d.won + r.won, decided, 0)}`)}
  </div>`;
  const T = S.idx.trends.filter(t => t.chamber === S.ch);
  const ser = (name, color, fn) => ({ name, color, pts: T.map(t => [t.year, fn(t), isCurrent(t.year)]) });
  const rate = (a, b) => b ? 100 * a / b : null;
  h += `<h2>1990년부터의 흐름 (${chName(S.ch)})</h2><div class="grid2">
  ${lineChart([ser('민주', C.d, t => rate(t.D.woman_won, t.D.primaries)), ser('공화', C.r, t => rate(t.R.woman_won, t.R.primaries))], { title: '정당 경선에서 여성이 이긴 비율', cap: '정당 경선(단독 후보·전당대회 포함) 가운데 여성이 이긴 비율. 상위 2인 경선 등은 뺐습니다.' })}
  ${lineChart([ser('민주', C.d, t => rate(t.D.with_woman, t.D.primaries)), ser('공화', C.r, t => rate(t.R.with_woman, t.R.primaries))], { title: '여성이 한 명이라도 출마한 경선의 비율', cap: '여성이 이긴 비율은 "출마"와 "출마했을 때 이기기"가 합쳐진 결과라 둘을 나눠 봅니다.' })}
  ${lineChart([ser('민주', C.d, t => rate(t.D.contested_woman_won, t.D.contested_with_woman)), ser('공화', C.r, t => rate(t.R.contested_woman_won, t.R.contested_with_woman))], { title: '여성이 출마한 경쟁 경선에서 여성이 이긴 비율', cap: '후보가 2명 이상인 경선 가운데 여성이 출마한 곳만 봅니다(단독 후보 제외).' })}
  ${lineChart([ser('민주', C.d, t => rate(t.D.women_seats, t.D.seats)), ser('공화', C.r, t => rate(t.R.women_seats, t.R.seats)), ser('전체', C.w, t => rate(t.women_won, t.decided))], { title: '당선자 가운데 여성 비율', cap: '빈 점은 개표 중이거나 비공식(위키백과) 자료가 섞인 해입니다.' })}
  </div>`;
  return h;
}

/* --- state tile map of districts --- */
const LAYERS = {
  gen: { label: '본선 당선', legend: [['여성(민주) 당선', C.d], ['여성(공화) 당선', C.r], ['남성 당선', C.none], ['아직 모름', C.na]] },
  D: { label: '민주당 경선', legend: [['여성이 이김', C.d], ['여성이 나왔지만 짐', C.dl], ['여성 없음', C.none], ['정당 경선 아님', C.open], ['경선 기록 없음', C.na]] },
  R: { label: '공화당 경선', legend: [['여성이 이김', C.r], ['여성이 나왔지만 짐', C.rl], ['여성 없음', C.none], ['정당 경선 아님', C.open], ['경선 기록 없음', C.na]] },
  match: { label: '본선 대결(민주-공화 후보 성별)', legend: [['여성 대 여성', C.ff], ['여성(민주) 대 남성', C.fm], ['남성 대 여성(공화)', C.mf], ['남성 대 남성', C.mm], ['한 당만', C.na]] },
  ran: { label: '여성 출마(경선·본선 어디든)', legend: [['여성 출마', C.w], ['여성 없음', C.none]] },
};
function cellColor(r, Y) {
  const L = S.layer;
  if (L === 'gen') {
    if (!r.winner) return C.na;
    return r.winner_gender === 'F' ? (r.winner_party === 'R' ? C.r : C.d) : C.none;
  }
  if (L === 'D' || L === 'R') {
    const p = (Y.pBy[r.race_id] || []).find(x => x.party === L);
    if (!p) return C.na;
    if (!PARTY_PRIMARY.has(p.contest)) return C.open;
    if (p.woman_won === 1) return L === 'D' ? C.d : C.r;
    if (p.n_women > 0) return L === 'D' ? C.dl : C.rl;
    return C.none;
  }
  if (L === 'match') {
    const k = `${r.d_nominee_gender || ''}-${r.r_nominee_gender || ''}`;
    return { 'F-F': C.ff, 'F-M': C.fm, 'M-F': C.mf, 'M-M': C.mm }[k] || C.na;
  }
  return (Y.cBy[r.race_id] || []).some(c => c.gender === 'F' && (c.party === 'D' || c.party === 'R')) ? C.w : C.none;
}
async function viewMap() {
  const Y = await loadYear(S.year);
  const kind = `<div class="seg" role="group" aria-label="지도 종류"><button data-mk="tile" class="${S.mapKind === 'tile' ? 'on' : ''}">칸 지도</button><button data-mk="real" class="${S.mapKind === 'real' ? 'on' : ''}">실제 지도</button></div>`;
  const layerSel = `<label class="fld">보기 <select data-layer>${Object.entries(LAYERS).map(([k, v]) => `<option value="${k}" ${S.layer === k ? 'selected' : ''}>${v.label}</option>`).join('')}</select></label>`;
  const lg = `<div class="legend">${LAYERS[S.layer].legend.map(([t, c]) => `<span><i style="background:${c}"></i>${t}</span>`).join('')}</div>`;
  return S.mapKind === 'real' ? await viewRealMap(Y, kind, layerSel, lg) : viewTileMap(Y, kind, layerSel, lg);
}
function viewTileMap(Y, kind, layerSel, lg) {
  const R = Y.r.filter(r => r.chamber === S.ch);
  const byState = groupBy(R, 'state');
  const sq = S.ch === 'H' ? 11 : 24, per = S.ch === 'H' ? 8 : 2, cw = per * (sq + 1) + 12;
  const rowH = Array(8).fill(0);
  for (const [st, [, cy]] of Object.entries(TILE)) rowH[cy] = Math.max(rowH[cy], 18 + Math.ceil(((byState[st] || []).length || 1) / per) * (sq + 1) + 8);
  const rowY = rowH.map((_, i) => rowH.slice(0, i).reduce((a, b) => a + b, 4));
  let g = '';
  for (const [st, [cx, cy]] of Object.entries(TILE)) {
    const x0 = cx * cw + 4, y0 = rowY[cy];
    const rs = (byState[st] || []).sort((a, b) => a.district - b.district || a.special - b.special);
    g += `<text x="${x0}" y="${y0 + 11}" font-weight="600">${st}</text>`;
    rs.forEach((r, i) => {
      const x = x0 + (i % per) * (sq + 1), y = y0 + 16 + Math.floor(i / per) * (sq + 1);
      const tip = `${raceLabel(r)} · 당선: ${r.winner || '아직 모름'}${r.winner_gender === 'F' ? ' (여성)' : ''}`;
      g += `<rect class="d" data-open="race:${esc(r.race_id)}" x="${x}" y="${y}" width="${sq}" height="${sq}" rx="1.5" fill="${cellColor(r, Y)}"><title>${esc(tip)}</title></rect>`;
    });
  }
  return `<div class="btns" style="align-items:center">${kind}${layerSel}
    <span class="muted">${S.year}년 ${chName(S.ch)} · 칸 하나가 ${S.ch === 'H' ? '선거구 하나(번호 순)' : '상원 선거 하나'}입니다. 누르면 후보와 결과가 열립니다.</span></div>
  ${lg}
  <div class="map-wrap"><svg viewBox="0 0 ${12 * cw + 8} ${rowY[7] + rowH[7] + 4}" role="img" aria-label="주별 선거구 지도">${g}</svg></div>
  <p class="note">지리 모양이 아니라 주 위치만 맞춘 칸 지도입니다. 같은 번호 선거구라도 선거구를 다시 그린 해(1992·2002·2012·2022년 등)에는 같은 지역이 아닙니다.${isCurrent(S.year) ? ' 올해 본선은 개표 중이라 당선이 확인된 곳만 칠했습니다.' : ''}</p>`;
}

/* --- real district map (boundaries: Lewis et al., docs/data/maps, built by pipeline/maps.py) --- */
const congressOf = y => Math.floor((y - 1788) / 2) + 1;
async function getStatic(u) { const r = await fetch(u); if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); }
async function mapIndex() { if (!MAPS.idx) MAPS.idx = await getStatic('data/maps/index.json'); return MAPS.idx; }
async function mapCongress(c) { if (!MAPS.c[c]) MAPS.c[c] = await getStatic(`data/maps/c${c}.json`); return MAPS.c[c]; }
async function mapDetail(st, c) {
  const idx = await mapIndex();
  const spans = idx.detail[st] || [];
  let span = spans.find(([a, b]) => a <= c && c <= b);
  if (!span && c === idx.last && !idx.new_2026.includes(st)) span = spans.find(([a, b]) => a <= c - 1 && c - 1 <= b);  // 2026 keeps the 119th districts
  if (!span) return null;
  const k = `${st}-${span[0]}-${span[1]}`;
  if (!MAPS.s[k]) MAPS.s[k] = await getStatic(`data/maps/s/${k}.json`);
  return MAPS.s[k];
}
const ridH = (y, st, d) => `${y}-H-${st}-${String(d).padStart(2, '0')}`;
async function viewRealMap(Y, kind, layerSel, lg) {
  const c = congressOf(S.year);
  const [idx, M] = await Promise.all([mapIndex(), mapCongress(c)]);
  if (S.zoom && !idx.s.some(([st]) => st === S.zoom)) S.zoom = null;
  const R = Y.r.filter(r => r.chamber === S.ch);
  const tipOf = r => `${raceLabel(r)} · 당선: ${r.winner || '아직 모름'}${r.winner_gender === 'F' ? ' (여성)' : ''}`;
  let g = '', note = '';
  const pending = new Set(M.pending || []);
  if (S.ch === 'H') {
    const drawn = new Set();
    for (const [st, d, p] of M.d) {
      const rid = ridH(S.year, st, d), r = Y.rIndex[rid];
      drawn.add(rid);
      g += `<path class="rd" d="${p}" data-st="${st}" data-d="${d}" data-rid="${r ? rid : ''}" fill="${r ? cellColor(r, Y) : C.na}"><title>${esc(r ? tipOf(r) : `${st}-${d === 0 ? 'AL' : d}`)}</title></path>`;
    }
    const missing = R.filter(r => !r.special && !drawn.has(r.race_id) && !pending.has(r.state)).map(r => `${r.state}-${r.district === 0 ? 'AL' : r.district}`);
    if (missing.length) note += ` 경계 자료에 없어 그리지 못한 선거구: ${esc(missing.join(', '))}.`;
    if (pending.size) note += ` ${S.year}년에 선거구를 새로 그린 ${pending.size}개 주(${[...pending].map(st => STATE_KO[st]).join('·')})는 새 경계 자료가 아직 없어 빗금으로 두었습니다. 이 주들은 칸 지도에서 보세요.`;
    const fresh = c === idx.last ? (idx.new_2026_shapes || []) : [];
    if (fresh.length) note += ` ${S.year}년에 선거구를 새로 그린 ${fresh.length}개 주(${fresh.map(st => STATE_KO[st]).join('·')})의 새 경계는 위키미디어 공용의 지도 자료(각 주 정부·의회가 낸 원본을 옮긴 것, CC0)를 썼습니다.`;
  } else {
    for (const [st, p] of idx.s) {
      const rs = R.filter(r => r.state === st).sort((a, b) => a.special - b.special);
      const r = rs[0];
      const tip = rs.length ? rs.map(tipOf).join(' / ') : `${STATE_KO[st]}: ${S.year}년 상원 선거 없음`;
      g += `<path class="rd" d="${p}" data-st="${st}" data-d="0" data-rid="${r ? r.race_id : ''}" data-one="1" fill="${r ? cellColor(r, Y) : 'var(--soft)'}"><title>${esc(tip)}</title></path>`;
    }
    note += ' 한 해에 정규·특별선거가 함께 있으면 정규 선거 색을 칠했고, 누르면 정규 선거가 열립니다(특별선거는 선거 목록에서).';
  }
  let out = '';
  for (const [st, p] of idx.s) {
    if (S.ch === 'H' && pending.has(st)) g += `<path class="pend" d="${p}" data-st="${st}"><title>${esc(`${STATE_KO[st]}: ${S.year}년 새 선거구 경계 자료가 아직 없음`)}</title></path>`;
    out += `<path d="${p}" data-st="${st}"/>`;
  }
  const one = st => S.ch === 'S' || M.d.filter(x => x[0] === st).length <= 1;
  MAPS.view = { w: idx.w, h: idx.h, one };
  return `<div class="btns" style="align-items:center">${kind}${layerSel}
    <button class="btn" data-zoomout ${S.zoom ? '' : 'hidden'}>전국 보기</button>
    <span class="muted">${S.year}년 ${chName(S.ch)} · ${S.ch === 'H' ? '주를 누르면 그 주가 크게 보이고, 크게 본 상태에서 선거구를 누르면 후보와 결과가 열립니다.' : '주를 누르면 후보와 결과가 열립니다.'}</span></div>
  ${lg}
  <div class="rmap-wrap"><svg id="rmap" viewBox="0 0 ${idx.w} ${idx.h}" role="img" aria-label="${S.year}년 ${chName(S.ch)} 선거구 실제 지도">
    <defs><pattern id="hatch" width="60" height="60" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="60" height="60" fill="var(--soft)"/><line x1="0" y1="0" x2="0" y2="60" stroke="var(--muted)" stroke-width="14" opacity=".35"/></pattern></defs>
    <g class="dist">${g}</g><g class="outl">${out}</g></svg></div>
  <p class="note">선거구 경계: Lewis, DeVine, Pitcher &amp; Martis, <i>Digital Boundary Definitions of U.S. Congressional Districts</i>(GitHub, 2026-11-05 내려받음). 알래스카·하와이는 옮겨 그렸습니다. 넓은 농촌 선거구가 넓게 보이고 도시 선거구는 작게 보여서, 전국 단위 비율은 칸 지도가 더 정확하게 보여 줍니다.${note}${isCurrent(S.year) ? ' 올해 본선은 개표 중이라 당선이 확인된 곳만 칠했습니다.' : ''}</p>`;
}
function setView(box, animate) {
  const svg = $('#rmap'); if (!svg) return;
  const cur = svg.viewBox.baseVal, from = [cur.x, cur.y, cur.width, cur.height], to = [box.x, box.y, box.width, box.height];
  if (!animate || matchMedia('(prefers-reduced-motion: reduce)').matches) { svg.setAttribute('viewBox', to.join(' ')); return; }
  const t0 = performance.now(), dur = 420;
  const step = now => {
    const t = Math.min(1, (now - t0) / dur), e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    svg.setAttribute('viewBox', from.map((v, i) => v + (to[i] - v) * e).join(' '));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function stateBox(st) {
  const svg = $('#rmap'), el = svg && svg.querySelector(`.outl path[data-st="${st}"]`);
  if (!el) return null;
  const b = el.getBBox(), W = MAPS.view.w, H = MAPS.view.h, ar = W / H;
  let w = b.width * 1.12, h = b.height * 1.12;
  if (w / h > ar) h = w / ar; else w = h * ar;
  w = Math.max(w, W / 40); h = w / ar;
  return { x: b.x + b.width / 2 - w / 2, y: b.y + b.height / 2 - h / 2, width: w, height: h };
}
async function zoomTo(st, animate = true) {
  const box = stateBox(st); if (!box) return;
  S.zoom = st; writeHash();
  const svg = $('#rmap');
  svg.classList.add('zoomed');
  svg.querySelectorAll('.dist path').forEach(p => p.classList.toggle('dim', p.dataset.st !== st));
  const zo = $('[data-zoomout]'); if (zo) zo.hidden = false;
  setView(box, animate);
  if (animate) { const r = svg.getBoundingClientRect(); if (r.top < 0 || r.bottom > innerHeight) svg.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
  if (S.ch !== 'H') return;
  const det = await mapDetail(st, congressOf(S.year));
  if (!det || S.zoom !== st || !$('#rmap')) return;
  const byD = Object.fromEntries(det.d.map(([d, p]) => [d, p]));
  $('#rmap').querySelectorAll(`.dist path.rd[data-st="${st}"]`).forEach(el => {
    const p = byD[el.dataset.d];
    if (p && !el.dataset.fine) { el.setAttribute('d', p); el.setAttribute('transform', 'scale(0.1)'); el.dataset.fine = '1'; }
  });
}
function zoomOut() {
  S.zoom = null; writeHash();
  const svg = $('#rmap'); if (!svg) return;
  svg.classList.remove('zoomed');
  svg.querySelectorAll('.dist path').forEach(p => p.classList.remove('dim'));
  const zo = $('[data-zoomout]'); if (zo) zo.hidden = true;
  setView({ x: 0, y: 0, width: MAPS.view.w, height: MAPS.view.h }, true);
}
function bindRealMap() {
  const svg = $('#rmap'); if (!svg) return;
  svg.querySelectorAll('.dist path.rd').forEach(el => el.addEventListener('click', () => {
    const st = el.dataset.st;
    if (S.zoom !== st && !MAPS.view.one(st)) { zoomTo(st); return; }
    if (el.dataset.rid) openPanel('race:' + el.dataset.rid);
  }));
  if (S.zoom) zoomTo(S.zoom, false);
}

/* --- comparisons --- */
function tertiles(vals) { const v = vals.map(num).filter(x => x !== null).sort((a, b) => a - b); if (v.length < 6) return null; return [v[Math.floor(v.length / 3)], v[Math.floor(2 * v.length / 3)]]; }
function tert(x, cut, unit) { if (num(x) === null || !cut) return '자료 없음'; return x < cut[0] ? `하위 1/3 (${fmt(cut[0], 0)}${unit} 미만)` : x < cut[1] ? '중간 1/3' : `상위 1/3 (${fmt(cut[1], 0)}${unit} 이상)`; }
const LEAN_ORDER = ['민주 강세 (+15 이상)', '민주 우세 (+5~15)', '경합 (±5 이내)', '공화 우세 (+5~15)', '공화 강세 (+15 이상)', '자료 없음'];
function leanBin(x) { if (x === null) return '자료 없음'; return x >= 15 ? LEAN_ORDER[0] : x >= 5 ? LEAN_ORDER[1] : x > -5 ? LEAN_ORDER[2] : x > -15 ? LEAN_ORDER[3] : LEAN_ORDER[4]; }
// first House election under a new census map: there is no earlier member "within the same map" to count
const MAP_FIRST = new Set([1992, 2002, 2012, 2022]);
const PRIOR_ORDER = ['없음', '1명', '2명 이상', '새 지도의 첫 선거', '자료 없음'];
const CUM_ORDER = ['없음', '1명', '2명', '3명 이상', '자료 없음'];
function priorMap(u) {
  if (u.r.chamber === 'H' && MAP_FIRST.has(u.Y.year)) return '새 지도의 첫 선거';
  const v = num(u.r.women_members_same_map);
  return v === null ? '자료 없음' : v === 0 ? '없음' : v === 1 ? '1명' : '2명 이상';
}
function priorCum(u) {
  const v = u.r.chamber === 'H' ? num(u.r.women_members_since_1990) : null;
  return v === null ? '자료 없음' : v === 0 ? '없음' : v === 1 ? '1명' : v === 2 ? '2명' : '3명 이상';
}
function priorCaution(mode) {
  const house = S.ch === 'H';
  if (house && mode === 'cum') return `<div class="note caution"><b>이 항목을 볼 때 주의할 점: 선거구를 이은 방법</b><ol>
    <li>그해 선거구를 기준으로, 그 주민의 2/3 이상이 살던 예전 선거구를 같은 선거구로 봅니다. 주민은 2020년 인구조사 블록그룹(약 1,500명 단위) 인구로 재고, 1990년 선거 때 의회(101대, 1989년 1월~)부터 선거일의 의회까지 의회마다 따로 찾습니다.</li>
    <li>2/3을 넘는 예전 선거구가 없으면, 그 예전 선거구의 의원이 이번 선거에 나왔을 때(경선·본선, 낙선 포함) 그 의원의 선거구를 같은 선거구로 봅니다. 의원이 다른 곳으로 옮겨 나오면 주민이 거의 겹치지 않아도 이어집니다(예: 1992년 조지아 6구의 깅리치).</li>
    <li>둘 다 없으면 그 의회에는 이어지는 선거구가 없어 세지 않습니다. 예전 의회로 갈수록 이렇게 빠지는 경우가 많습니다.</li>
    <li>'1명', '2명'은 이어진 선거구들을 맡은 서로 다른 여성 의원 수입니다. 같은 여성이 여러 번 당선돼도 1명이고, 지금 의원도 들어갑니다. 10년마다 0으로 돌아가지 않고 1990년부터 계속 쌓입니다.</li>
    <li>주민 겹침은 블록그룹의 인구 중심점으로 잰 근사값이고, 1990년대 지도에도 2020년 인구 분포를 씁니다. 1990년 뉴욕 33구는 경계 자료가 없어 빠집니다. 선거구별로 어느 선거구와 이었는지는 '내려받기'의 '선거구 정렬 자료'에 있습니다.</li></ol></div>`;
  return `<div class="note caution"><b>이 항목을 볼 때 주의할 점</b><ol>
    <li>'1명', '2명 이상'은 서로 다른 사람의 수입니다. 같은 여성이 여러 번 당선돼도 1명으로 셉니다. 지금 의원도 들어갑니다.</li>
    ${house ? `<li>선거구를 인구조사에 따라 10년마다 다시 그리기 때문에, 이 항목은 새 지도를 쓰기 시작할 때(1993·2003·2013·2023년 1월)마다 0부터 다시 셉니다. 그래서 같은 '1명'이라도 10년 가운데 몇 번째 선거인지에 따라 뜻이 다릅니다. 첫 선거(1992·2002·2012·2022년)는 셀 의원이 없어 '새 지도의 첫 선거'로 따로 묶었고, 두 번째 선거의 '1명'은 대부분 지금 의원입니다. 10년을 넘어 이어 세려면 위의 '1990년부터 누적'을 누르세요.</li>
    <li>10년 중간에 선거구를 다시 그린 주에서는 번호만 같은 다른 지역의 의원이 섞일 수 있습니다(예: 2020년 펜실베이니아 7구, 2026년에 새 지도를 쓴 10개 주).</li>`
    : `<li>상원은 주 전체가 선거구라 다시 그리지 않으므로, 1985년부터 그 주의 두 자리를 맡은 여성 의원을 끊지 않고 셉니다.</li>`}</ol></div>`;
}
function priorToggle() {
  if (S.ch !== 'H') return '';
  return `<div class="seg" style="margin:6px 0">${[['map', '같은 지도 안(10년마다 새로 셈)'], ['cum', '1990년부터 누적(이어지는 선거구)']].map(([k, l]) => `<button data-pm="${k}" class="${S.priorMode === k ? 'on' : ''}">${l}</button>`).join('')}</div>`;
}
function raceEth(code) {
  if (!code) return '자료 없음';
  const parts = String(code).split('/');
  return parts.length > 1 ? '여러 인종' : (RACE_ETH[parts[0]] || code);
}
const CRIT = {
  district: {
    lean: { label: '지역구 당파 성향', order: LEAN_ORDER, f: u => leanBin(lean(u.r, u.Y)) },
    prior_map: { label: '같은 선거구 지도 안에서 기존 여성 의원', head: '기존 여성 의원 수', order: PRIOR_ORDER, f: priorMap },
    prior_cum: { label: '이어지는 선거구의 기존 여성 의원(1990년부터 누적)', head: '기존 여성 의원 수', order: CUM_ORDER, f: priorCum, house: true },
    seat_female: { label: '현직자가 여성', head: '현직자 성별', order: ['여성', '남성', '자료 없음'], f: u => u.r.seat_member_female === 1 ? '여성' : u.r.seat_member_female === 0 ? '남성' : '자료 없음' },
    incumbent: { label: '현직 출마', order: ['여성 현직 출마', '남성 현직 출마', '현직 없음'], f: u => {
      const run = u.p ? u.p.incumbent_running : u.r.incumbent_running, g = u.p ? u.p.incumbent_gender : u.r.incumbent_gender;
      return run === 1 ? (g === 'F' ? '여성 현직 출마' : '남성 현직 출마') : '현직 없음'; } },
    field: { label: '경선 후보 수', order: ['1명', '2명', '3명', '4명 이상'], only: 'primary', f: u => { const n = num(u.p.n_cand); return n >= 4 ? '4명 이상' : `${n}명`; } },
    rural: { label: '농촌 인구 비율', order: ['도시형 (10% 미만)', '중간 (10~30%)', '농촌형 (30% 이상)', '자료 없음'], f: u => { const v = num(u.r.rural); return v === null ? '자료 없음' : v < 10 ? '도시형 (10% 미만)' : v < 30 ? '중간 (10~30%)' : '농촌형 (30% 이상)'; } },
    region: { label: '지역(인구조사국 4대 권역)', order: ['북동부', '중서부', '남부', '서부'], f: u => REGION[u.r.state] || '기타' },
    white: { label: '비히스패닉 백인 비율', tert: 'white_nh', unit: '%' },
    ba: { label: '대졸 비율(25세 이상)', tert: 'ba_plus', unit: '%' },
    inc: { label: '가구 소득 중앙값', tert: 'med_income', unit: '달러' },
    system: { label: '경선 방식', f: u => SYSTEM[u.r.system] || u.r.system },
  },
  woman: {
    status: { label: '여성 후보의 위치', order: ['현직', '같은 당 현직에 도전', '현직 없는 경선', '상대 당 현직 지역구', '현직 없는 선거'], f: u => {
      if (u.c.incumbent === 1) return '현직';
      if (u.kind === 'primary') return u.p && u.p.incumbent_running === 1 ? '같은 당 현직에 도전' : '현직 없는 경선';
      return u.r.incumbent_running === 1 ? '상대 당 현직 지역구' : '현직 없는 선거'; } },
    race_eth: { label: '인종(CAWP, 2004년부터)', order: ['백인', '흑인', '히스패닉', '아시아·태평양계', '원주민', '중동·북아프리카계', '여러 인종', '자료 없음'], f: u => raceEth(u.c.race_eth) },
    qual: { label: '이전 경력(하원 경선 1990–2018)', order: ['현직', '전직 하원의원', '선출직 경험 있음', '선출직 경험 없음', '자료 없음'], only: 'primary', f: u => QUAL[u.c.qual] || '자료 없음' },
    field: { label: '경선 후보 수', order: ['1명', '2명', '3명', '4명 이상'], only: 'primary', f: u => { const n = num(u.p && u.p.n_cand); return n === null ? '자료 없음' : n >= 4 ? '4명 이상' : `${n}명`; } },
    rivals: { label: '같은 경선의 다른 여성', order: ['여성은 혼자', '다른 여성도 출마'], only: 'primary', f: u => (u.p && u.p.n_women > 1) ? '다른 여성도 출마' : '여성은 혼자' },
    lean: { label: '지역구 당파 성향', order: LEAN_ORDER, f: u => leanBin(lean(u.r, u.Y)) },
    prior_map: { label: '같은 선거구 지도 안에서 기존 여성 의원', head: '기존 여성 의원 수', order: PRIOR_ORDER, f: priorMap },
    prior_cum: { label: '이어지는 선거구의 기존 여성 의원(1990년부터 누적)', head: '기존 여성 의원 수', order: CUM_ORDER, f: priorCum, house: true },
  },
};
function units(Ys, target, unit) {
  // district unit: primaries of a party (target D/R) or decided races (target G); woman unit: women candidates
  const out = [];
  for (const Y of Ys) {
    for (const r of Y.r) {
      if (r.chamber !== S.ch) continue;
      if (S.partyOnly && target === 'G' && r.system !== 'party' && r.system !== 'blanket') continue;
      const ps = Y.pBy[r.race_id] || [];
      if (unit === 'district') {
        if (target === 'G') { if (r.winner && r.winner_gender) out.push({ Y, r, kind: 'general' }); continue; }
        const p = ps.find(x => x.party === target);
        if (p && primaryOk(p) && (p.woman_won !== null || p.n_women === 0)) out.push({ Y, r, p, kind: 'primary' });
      } else {
        for (const c of (Y.cBy[r.race_id] || [])) {
          if (c.gender !== 'F') continue;
          if (target === 'G') { if (c.g_won !== null && r.winner && (c.party === 'D' || c.party === 'R')) out.push({ Y, r, c, kind: 'general', p: ps.find(x => x.party === c.party) }); continue; }
          if (c.p_party !== target || c.p_won === null) continue;
          const p = ps.find(x => x.party === target);
          if (p && primaryOk(p)) out.push({ Y, r, c, p, kind: 'primary' });
        }
      }
    }
  }
  return out;
}
function womanInGeneral(u) {
  // a Democratic or Republican woman on the general ballot; in top-two, top-four and Louisiana-style races both
  // finalists can come from one party (D vs D), so every general candidate is checked there, not just one per party
  const r = u.r;
  if (r.woman_won_general === 1 || r.d_nominee_gender === 'F' || r.r_nominee_gender === 'F') return true;
  if (r.system === 'party' || r.system === 'blanket') return false;
  return (u.Y.cBy[r.race_id] || []).some(c => c.gender === 'F' && (c.party === 'D' || c.party === 'R') && (c.g_won !== null || num(c.g_votes) !== null || num(c.g_pct) !== null));
}
function compare(us, crit, unit, target) {
  const def = CRIT[unit][crit];
  let fn = def.f;
  if (def.tert) { const cut = tertiles(us.map(u => u.r[def.tert])); fn = u => tert(u.r[def.tert], cut, def.unit); }
  const g = {};
  for (const u of us) { const k = fn(u); (g[k] = g[k] || []).push(u); }
  let keys = Object.keys(g);
  const ord = def.order;
  keys.sort((a, b) => { const ia = ord ? ord.indexOf(a) : -1, ib = ord ? ord.indexOf(b) : -1; if (ia !== -1 || ib !== -1) return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    if (a.startsWith('하위')) return -1; if (b.startsWith('하위')) return 1; if (a === '자료 없음') return 1; if (b === '자료 없음') return -1; return a.localeCompare(b, 'ko'); });
  return keys.map(k => {
    const l = g[k];
    if (unit === 'woman') { const won = l.filter(u => (target === 'G' ? u.c.g_won : u.c.p_won) === 1).length; return { k, n: l.length, won, rate: 100 * won / l.length }; }
    if (target === 'G') {
      const ran = l.filter(womanInGeneral).length, won = l.filter(u => u.r.woman_won_general === 1).length;
      return { k, n: l.length, ran, won, rRan: 100 * ran / l.length, rWon: 100 * won / l.length, rCond: ran ? 100 * won / ran : null };
    }
    const ran = l.filter(u => u.p.n_women > 0).length, won = l.filter(u => u.p.woman_won === 1).length;
    return { k, n: l.length, ran, won, rRan: 100 * ran / l.length, rWon: 100 * won / l.length, rCond: ran ? 100 * won / ran : null };
  });
}
function compareBlock(Ys, target, unit, crit, title) {
  const us = units(Ys, target, unit);
  const def = CRIT[unit][crit];
  if (def.only === 'primary' && target === 'G') return `<p class="muted">이 기준은 경선에만 있습니다.</p>`;
  const res = compare(us, crit, unit, target);
  const color = target === 'D' ? C.d : target === 'R' ? C.r : C.w;
  const tname = target === 'D' ? '민주당 경선' : target === 'R' ? '공화당 경선' : '본선';
  if (!us.length) return `<p class="muted">해당하는 선거가 없습니다.</p>`;
  const head = def.head || def.label;
  if (unit === 'woman') {
    return `<div class="chart-block"><b>${esc(title || def.label)}: 여성 후보가 ${target === 'G' ? '본선에서 당선된' : '경선에서 이긴'} 비율</b>
      <div class="cap top">${periodLabel()} ${chName(S.ch)} ${tname}의 여성 후보 ${us.length}명. 괄호는 여성 후보 수입니다.</div>
      ${bars(res.map(x => ({ lab: x.k, n: x.n, v: x.rate, color })), { head })}</div>`;
  }
  const W = target === 'G' ? '선거' : '경선';
  const what = [target === 'G' ? '여성 후보가 본선에 나간 비율' : '여성이 출마한 비율', '전체 지역구 중 이긴 비율', '여성이 출마한 지역구에서 여성이 이긴 비율'];
  const cond = x => x.rCond === null ? '–' : `${fmt(x.rCond)}% (${x.won}/${x.ran})`;
  const tbl = `<div class="tbl-wrap"><table><thead><tr><th>${esc(head)}</th><th class="num">${W}</th><th class="num">${what[0]}</th><th class="num">${what[1]}</th><th class="num">${what[2]}</th></tr></thead><tbody>
    ${res.map(x => `<tr><td>${esc(x.k)}</td><td class="num">${x.n}</td><td class="num">${fmt(x.rRan)}% <span class="muted">(${x.ran})</span></td><td class="num">${fmt(x.rWon)}% <span class="muted">(${x.won})</span></td><td class="num">${cond(x)}</td></tr>`).join('')}</tbody></table></div>`;
  const why = [target === 'G' && Ys.some(Y => isCurrent(Y.year)) ? '올해는 당선이 확인된 곳만' : '', target !== 'G' ? '그 당 후보가 없던 곳 등은 빠짐' : '',
    S.partyOnly ? '정당 경선을 하지 않는 주는 뺌' : ''].filter(Boolean).join(', ');
  const cnt = `${periodLabel()} ${chName(S.ch)} ${tname} ${us.length}곳${why ? `(${why})` : ''}. 괄호는 ${W} 수입니다.`;
  return `<div class="grid2"><div class="chart-block"><b>${what[1]}</b><div class="cap top">${cnt}</div>${bars(res.map(x => ({ lab: x.k, n: x.n, v: x.rWon, color })), { head })}</div>
    <div class="chart-block"><b>${what[2]}</b><div class="cap top">이름 옆 괄호는 여성이 출마한 ${W} 수, 값 옆 괄호는 (여성이 이긴 곳/여성이 출마한 곳)입니다.</div>${bars(res.map(x => ({ lab: x.k, n: x.ran, v: x.rCond, color, vt: cond(x) })), { head, wide: true })}</div></div>${tbl}`;
}
async function viewWhere() {
  const Ys = await loadPeriod();
  const opts = Object.entries(CRIT[S.unit]).filter(([k, v]) => !(v.only === 'primary' && S.target === 'G') && !(v.house && S.ch !== 'H'));
  if (!opts.some(([k]) => k === S.crit)) S.crit = opts[0][0];
  return `<div class="btns" style="align-items:center">
    <div class="seg">${[['D', '민주당 경선'], ['R', '공화당 경선'], ['G', '본선']].map(([k, l]) => `<button data-target="${k}" class="${S.target === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    <div class="seg">${[['district', '선거구 기준'], ['woman', '여성 후보 기준']].map(([k, l]) => `<button data-unit="${k}" class="${S.unit === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    <label class="fld">기준 <select data-crit>${opts.map(([k, v]) => `<option value="${k}" ${S.crit === k ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</select></label></div>
    <p class="muted">${periodLabel()} · ${chName(S.ch)}. 기간은 위쪽 '비교 기간'에서 바꿉니다. ${S.unit === 'district' ? '선거구 기준은 "여성이 나왔는지(출마)"와 "나왔을 때 이겼는지(성공)"를 나눠 봅니다.' : '여성 후보 기준은 여성 후보 한 명 한 명이 이겼는지를 봅니다.'}</p>
    ${S.crit === 'prior_map' ? priorCaution('map') : S.crit === 'prior_cum' ? priorCaution('cum') : ''}${compareBlock(Ys, S.target, S.unit, S.crit)}
    <p class="note">집단 사이의 단순 비교입니다. 예를 들어 여성은 이기기 쉬운 곳에 더 많이 출마할 수 있어서(선택 효과), 차이를 원인으로 읽으면 안 됩니다. 회귀분석은 '내려받기'의 자료로 하실 수 있습니다. 당파 성향은 2008년부터 Cook 방식 당파 지수, 그 전 하원은 직전 대선 득표율을 그해 선거구 중앙값과 비교한 값입니다. 2026년 선거구의 당파 성향·인구 자료는 아직 없어 '자료 없음'으로 들어갑니다. 괄호 안 수가 작은 집단은 비율이 크게 흔들립니다.</p>`;
}

/* --- women vs men --- */
function pearson(xs, ys) {
  const n = xs.length; if (n < 3) return null;
  const mx = xs.reduce((t, v) => t + v, 0) / n, my = ys.reduce((t, v) => t + v, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) { const dx = xs[i] - mx, dy = ys[i] - my; sxy += dx * dy; sxx += dx * dx; syy += dy * dy; }
  return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null;
}
function ols(X, y) {
  // X: rows of predictors (with leading 1); returns coefficients via normal equations
  const k = X[0].length, A = Array.from({ length: k }, () => Array(k).fill(0)), b = Array(k).fill(0);
  X.forEach((row, i) => { for (let a = 0; a < k; a++) { b[a] += row[a] * y[i]; for (let c = 0; c < k; c++) A[a][c] += row[a] * row[c]; } });
  for (let i = 0; i < k; i++) { let p = i; for (let r = i + 1; r < k; r++) if (Math.abs(A[r][i]) > Math.abs(A[p][i])) p = r; [A[i], A[p]] = [A[p], A[i]]; [b[i], b[p]] = [b[p], b[i]];
    for (let r = 0; r < k; r++) if (r !== i) { const f = A[r][i] / A[i][i]; for (let c = i; c < k; c++) A[r][c] -= f * A[i][c]; b[r] -= f * b[i]; } }
  return b.map((v, i) => v / A[i][i]);
}
async function viewVsMen() {
  const Ys = await loadPeriod();
  // primaries with both women and men, two or more candidates
  const rows = [];
  for (const party of ['D', 'R']) {
    const grp = {};
    for (const Y of Ys) for (const p of Y.p) {
      if (p.chamber !== S.ch || p.party !== party || p.mixed !== 1 || !['contested', 'runoff'].includes(p.contest)) continue;
      const key = S.period === 'year' ? String(Y.year) : `${Math.floor(Y.year / 10) * 10}년대`;
      const cs = (Y.cBy[p.race_id] || []).filter(c => c.p_party === party && num(c.p_pct) !== null);
      (grp[key] = grp[key] || []).push({ p, w: cs.filter(c => c.gender === 'F').map(c => c.p_pct), m: cs.filter(c => c.gender === 'M').map(c => c.p_pct) });
    }
    for (const [k, l] of Object.entries(grp).sort()) rows.push({ party, k, n: l.length, won: l.filter(x => x.p.woman_won === 1).length,
      exp: mean(l.map(x => x.p.n_women / x.p.n_cand)) * 100, ws: mean(l.flatMap(x => x.w)), ms: mean(l.flatMap(x => x.m)) });
  }
  let h = `<h2>경선: 여성과 남성이 함께 나온 경쟁 경선</h2>
  <div class="tbl-wrap"><table><thead><tr><th>정당</th><th>시기</th><th class="num">경선 수</th><th class="num">여성이 이긴 비율</th><th class="num">같은 조건이면 기대되는 비율</th><th class="num">여성 후보 평균 득표율</th><th class="num">남성 후보 평균 득표율</th></tr></thead><tbody>
  ${rows.map(x => `<tr><td class="p${x.party}">${PARTY[x.party]}</td><td>${x.k}</td><td class="num">${x.n}</td><td class="num">${pct(x.won, x.n)}</td><td class="num">${fmt(x.exp)}%</td><td class="num">${fmt(x.ws)}%</td><td class="num">${fmt(x.ms)}%</td></tr>`).join('') || '<tr><td colspan="7" class="muted">해당 경선이 없습니다.</td></tr>'}</tbody></table></div>
  <p class="note">'기대되는 비율'은 후보마다 이길 가능성이 같다고 볼 때의 값(경선마다 여성 후보 수 ÷ 전체 후보 수의 평균)입니다. 여성이 이긴 비율이 이보다 높으면 같은 경선의 남성보다 잘했다는 뜻입니다. 득표율은 1차 경선 기준입니다.</p>`;
  // general elections: D two-party share vs district lean, by nominee genders
  const pts = [];
  for (const Y of Ys) for (const r of Y.r) {
    if (r.chamber !== S.ch || num(r.d_share_2party) === null || !['F-F', 'F-M', 'M-F', 'M-M'].includes(`${r.d_nominee_gender}-${r.r_nominee_gender}`)) continue;
    const x = lean(r, Y); if (x === null) continue;
    const inc = r.incumbent_running === 1 ? (r.incumbent_party === 'D' ? 1 : r.incumbent_party === 'R' ? -1 : 0) : 0;
    pts.push({ r, x, y: +r.d_share_2party, inc, m: `${r.d_nominee_gender}-${r.r_nominee_gender}` });
  }
  h += `<h2>본선: 같은 성향의 지역구에서 여성 후보는 얼마나 얻었나</h2>`;
  if (pts.length < 20) return h + `<p class="muted">비교할 본선이 충분하지 않습니다(당파 성향 자료는 하원 1990–2024, 상원 2008–2024).</p>`;
  const b = ols(pts.map(p => [1, p.x, p.inc]), pts.map(p => p.y));
  pts.forEach(p => { p.res = p.y - (b[0] + b[1] * p.x + b[2] * p.inc); });
  const M = { 'F-M': ['여성(민주) 대 남성(공화)', C.fm, 1], 'M-F': ['남성(민주) 대 여성(공화)', C.mf, -1], 'F-F': ['여성 대 여성', C.ff, 0], 'M-M': ['남성 대 남성', C.mm, 0] };
  const W = 640, H = 340, L = 44, R = 12, T = 12, B = 34;
  const xs = pts.map(p => p.x), xmin = Math.max(-50, Math.min(...xs)), xmax = Math.min(50, Math.max(...xs));
  const sx = x => L + (W - L - R) * (x - xmin) / (xmax - xmin), sy = y => T + (H - T - B) * (1 - y / 100);
  let g = '';
  for (let v = 0; v <= 100; v += 25) g += `<line x1="${L}" x2="${W - R}" y1="${sy(v)}" y2="${sy(v)}" stroke="var(--line)"/><text x="${L - 6}" y="${sy(v) + 4}" text-anchor="end">${v}%</text>`;
  for (let v = Math.ceil(xmin / 10) * 10; v <= xmax; v += 10) g += `<text x="${sx(v)}" y="${H - 14}" text-anchor="middle">${v > 0 ? 'D+' + v : v < 0 ? 'R+' + (-v) : '0'}</text>`;
  for (const m of ['M-M', 'F-F', 'F-M', 'M-F']) g += pts.filter(p => p.m === m).map(p => `<circle cx="${sx(Math.max(xmin, Math.min(xmax, p.x)))}" cy="${sy(p.y)}" r="${m === 'M-M' ? 2 : 3}" fill="${M[m][1]}" fill-opacity="${m === 'M-M' ? .35 : .8}" data-open="race:${esc(p.r.race_id)}" style="cursor:pointer"><title>${esc(p.r.year + ' ' + raceLabel(p.r))} · 민주 ${fmt(p.y)}%</title></circle>`).join('');
  const b0 = ols(pts.map(p => [1, p.x]), pts.map(p => p.y));
  g += `<line x1="${sx(xmin)}" y1="${sy(b0[0] + b0[1] * xmin)}" x2="${sx(xmax)}" y2="${sy(b0[0] + b0[1] * xmax)}" stroke="var(--fg)" stroke-dasharray="4 3"/>`;
  // Pearson r of district lean and Democratic two-party share, all plotted races (actual values, not the clipped x);
  // placed bottom right, where D-leaning districts with a low Democratic share are rare
  const pr = pearson(pts.map(p => p.x), pts.map(p => p.y));
  if (pr !== null) g += `<rect x="${W - R - 214}" y="${sy(9) - 17}" width="210" height="24" rx="5" fill="var(--card)" fill-opacity=".9" stroke="var(--line)"/>
    <text x="${W - R - 10}" y="${sy(9)}" text-anchor="end" style="fill:var(--fg);font-weight:600;font-size:13px">Pearson r = ${fmt(pr, 2)} (n = ${pts.length.toLocaleString('ko-KR')})</text>`;
  const tab = Object.entries(M).map(([m, [lab, col, sign]]) => { const l = pts.filter(p => p.m === m); const res = mean(l.map(p => p.res));
    return `<tr><td><span class="legend" style="margin:0"><span><i style="background:${col}"></i>${lab}</span></span></td><td class="num">${l.length}</td><td class="num">${fmt(mean(l.map(p => p.y)))}%</td><td class="num">${res === null ? '–' : (res > 0 ? '+' : '') + fmt(res)}%p</td><td class="num">${sign && res !== null ? (sign * res > 0 ? '+' : '') + fmt(sign * res) + '%p' : '–'}</td></tr>`; }).join('');
  h += `<div class="chart-block"><b>본선 민주 후보 양당 득표율과 지역구 당파 성향</b><div class="chart"><svg viewBox="0 0 ${W} ${H}">${g}</svg></div>
    <div class="cap">점 하나가 선거 하나입니다(누르면 결과가 열립니다). 점선은 당파 성향만으로 본 평균선이고, 아래 표의 차이는 현직 출마까지 감안한 값입니다. Pearson r은 지역구 당파 성향과 민주 후보 양당 득표율의 상관계수(점 전체)입니다. ${periodLabel()} ${chName(S.ch)} 본선 ${pts.length}곳.</div></div>
  <div class="tbl-wrap"><table><thead><tr><th>본선 대결</th><th class="num">선거</th><th class="num">민주 후보 평균 득표율</th><th class="num">평균선과의 차이(민주 쪽)</th><th class="num">여성 후보 쪽 차이</th></tr></thead><tbody>${tab}</tbody></table></div>
  <p class="note">'평균선과의 차이'는 같은 당파 성향과 현직 조건에서 예상되는 민주 득표율보다 얼마나 많이(+) 또는 적게(−) 얻었는지입니다. '여성 후보 쪽'은 여성 후보 입장에서 다시 적은 값입니다(공화 여성은 부호를 바꿈). 후보의 경력·선거자금은 감안하지 않았습니다.</p>`;
  return h;
}

async function viewPrior() {
  const Ys = await loadPeriod();
  let h = `<p class="muted">${periodLabel()} · ${chName(S.ch)}. 기존에 여성 의원이 있었던 선거구와 아닌 선거구를 비교합니다.</p>`;
  const mode = S.ch === 'H' ? S.priorMode : 'map';
  const first = mode === 'cum' ? ['prior_cum', '이어지는 선거구의 기존 여성 의원(1990년부터 누적)'] : ['prior_map', '같은 선거구 지도 안에서 기존 여성 의원(인구조사 주기 기준)'];
  for (const [crit, title] of [first, ['seat_female', S.ch === 'S' ? '현직자가 여성이었나(그 주 상원의원 두 명 중 한 명이라도)' : '현직자가 여성이었나'], ['incumbent', '현직이 출마했나']]) {
    h += `<h2>${esc(title)}</h2>${crit === first[0] ? priorToggle() + priorCaution(mode) : ''}`;
    for (const [t, l] of [['D', '민주당 경선'], ['R', '공화당 경선'], ['G', '본선']]) h += `<h3>${l}</h3>${compareBlock(Ys, t, 'district', crit)}`;
  }
  return h + `<div class="note note-row"><span>선거구를 다시 그린 해에는 같은 번호라도 다른 지역입니다.</span><button type="button" class="ghost-btn" data-xwopen aria-label="더 보기">⋯</button></div>`;
}

/* --- women and men voters (CES): a window opened from the small grey button at the bottom of '기존 여성 의원' --- */
// The button and the password only keep the window out of casual view; data/ces.json and this code are public files.
const XW_SALT = 'uswc-xw-2026|', XW_HASH = 'b63e035e302e543f80ffaceb4638e73c1cd055a8d8d1f2d6c957043266895002';
const XW = { ok: false, year: 'all', basis: 'any', excl: false, lean: 'all' };
async function loadCes() {
  if (S.cesIdx) return S.cesIdx;
  const d = await getJSON('data/ces.json');
  const ix = {};
  for (const row of d.r) {
    const o = {}; d.f.forEach((k, i) => { o[k] = row[i]; });
    ix[o.race_id] = { F: { n: o.nF, d: o.dF, r: o.rF, o: o.oF, q: o.qF }, M: { n: o.nM, d: o.dM, r: o.rM, o: o.oM, q: o.qM } };
  }
  S.cesMeta = d.meta;
  return (S.cesIdx = ix);
}
function shareStats(list, g, side) {
  // weighted share of voters of gender g who chose side(u) (D or R) out of the two parties, pooled over races; the
  // standard error treats each race as a cluster (respondents of one race are not independent draws)
  let Y = 0, X = 0, n = 0; const rows = [];
  for (const u of list) {
    const x = u.c[g]; if (!x || !x.n) continue;
    const yv = side(u) === 'D' ? x.d : x.r, xv = x.d + x.r; if (!(xv > 0)) continue;
    Y += yv; X += xv; n += x.n; rows.push([u, yv, xv]);
  }
  if (rows.length < 2) return null;
  const p = Y / X, G = rows.length; let v = 0;
  for (const [, yv, xv] of rows) v += (yv - p * xv) ** 2;
  return { p: 100 * p, se: 100 * Math.sqrt(v * G / (G - 1)) / X, n, races: G, X, rows };
}
function gapStats(list, side) {
  // women minus men in the same races: both shares come from the same races, so their errors are combined race by race
  const f = shareStats(list, 'F', side), m = shareStats(list, 'M', side);
  if (!f || !m) return null;
  const pf = f.p / 100, pm = m.p / 100, z = new Map();
  for (const [u, yv, xv] of f.rows) z.set(u, (yv - pf * xv) / f.X);
  for (const [u, yv, xv] of m.rows) z.set(u, (z.get(u) || 0) - (yv - pm * xv) / m.X);
  const G = z.size; let v = 0; for (const t of z.values()) v += t * t;
  return { f, m, gap: f.p - m.p, se: 100 * Math.sqrt(v * G / (G - 1)), races: G };
}
function share1(u, g, P) { const x = u.c[g]; return x && x.d + x.r > 0 ? 100 * (P === 'D' ? x.d : x.r) / (x.d + x.r) : null; }
const pp = (x, d = 1) => { if (x === null || x === undefined) return '–'; const r = +x.toFixed(d); return (r > 0 ? '+' : r < 0 ? '−' : '') + fmt(Math.abs(r), d) + '%p'; };
const ppS = (v, se) => v === null || v === undefined ? '–' : pp(v) + (se > 0 && Math.abs(v) > 1.96 * se ? '*' : '');
function xwPrior(u) {
  // earlier women of the linked districts (number), or null when the race has no linked-district count
  const v = num(u.r[(XW.basis === 'member' ? 'women_members_since_1990' : 'women_prior_since_1990') + (XW.excl ? '_excl' : '')]);
  return v === undefined ? null : v;
}
function xwStudy(units, P) {
  const L = units.filter(u => u.m === (P === 'D' ? 'F-M' : 'M-F') && xwPrior(u) !== null), side = () => P;
  const all = gapStats(L, side), yes = gapStats(L.filter(u => xwPrior(u) > 0), side), no = gapStats(L.filter(u => xwPrior(u) === 0), side);
  const cell = s => s ? `${fmt(s.p)}%<div class="sub">${s.n.toLocaleString('ko-KR')}명</div>` : '–';
  const row = (lab, g) => `<tr><td>${lab}${g ? `<div class="sub">선거 ${g.races.toLocaleString('ko-KR')}곳</div>` : ''}</td><td class="num">${g ? cell(g.f) : '–'}</td><td class="num">${g ? cell(g.m) : '–'}</td><td class="num">${g ? ppS(g.gap, g.se) : '–'}</td></tr>`;
  const both = yes && no;
  const dF = both ? ppS(yes.f.p - no.f.p, Math.hypot(yes.f.se, no.f.se)) : '–', dM = both ? ppS(yes.m.p - no.m.p, Math.hypot(yes.m.se, no.m.se)) : '–';
  const did = both ? ppS(yes.gap - no.gap, Math.hypot(yes.se, no.se)) : '–';
  const nm = { D: '민주당', R: '공화당' }, other = { D: '공화당', R: '민주당' };
  return `<div class="chart-block"><b><span class="p${P}">${nm[P]} 여성 후보</span> 대 ${other[P]} 남성 후보</b>
    <div class="cap top">칸: 그 여성 후보를 찍은 비율(양당 표 중)과 응답자 수</div>
    <div class="tbl-wrap"><table class="study"><thead><tr><th></th><th class="num">여성 유권자</th><th class="num">남성 유권자</th><th class="num">차이(여 − 남)</th></tr></thead><tbody>
    ${row('전체', all)}${row('기존 여성 있음', yes)}${row('기존 여성 없음', no)}
    <tr class="dif"><td>차이(있음 − 없음)</td><td class="num">${dF}</td><td class="num">${dM}</td><td class="num"><b>${did}</b></td></tr></tbody></table></div></div>`;
}
async function xwHtml() {
  const CI = await loadCes(), meta = S.cesMeta || {}, cy = meta.years || [];
  if (!cy.length) return '<p class="muted">CES 자료가 아직 없습니다.</p>';
  const ys = XW.year === 'all' ? cy.slice() : [+XW.year];
  await Promise.all(ys.map(loadYear));
  const LEAN = { all: ['전체', null], d: ['민주 쪽(+5 이상)', x => x >= 5], c: ['경합(±5 이내)', x => x > -5 && x < 5], r: ['공화 쪽(+5 이상)', x => x <= -5] };
  let units = [];
  for (const y of ys) for (const r of S.cache[y].r) {
    if (r.chamber !== 'H' || r.special) continue;
    const m = `${r.d_nominee_gender}-${r.r_nominee_gender}`, c = CI[r.race_id];
    if (!['F-F', 'F-M', 'M-F', 'M-M'].includes(m) || !c || !c.F.n || !c.M.n) continue;
    units.push({ Y: S.cache[y], r, c, m, x: lean(r, S.cache[y]) });
  }
  const lf = LEAN[XW.lean][1];
  if (lf) units = units.filter(u => u.x !== null && lf(u.x));
  const opt = (v, l, cur) => `<option value="${v}" ${String(cur) === String(v) ? 'selected' : ''}>${l}</option>`;
  const label = ys.length === 1 ? `${ys[0]}년` : `${ys[0]}–${ys[ys.length - 1]}년(${ys.length}번)`;
  let h = `<h2>남녀 유권자의 여성 후보 선택(CES)</h2>
  <p class="muted">기존에 여성 의원이나 여성 후보가 있었던 선거구에서, 이번 선거의 여성 후보를 여성 유권자와 남성 유권자가 각각 얼마나 찍었는지 비교합니다. CES 응답자의 하원 투표, ${label}.</p>
  <div class="row small">
    <label class="fld">연도 <select data-xwc="year">${opt('all', `${cy[0]}–${cy[cy.length - 1]} 전체`, XW.year)}${cy.slice().reverse().map(y => opt(y, y + '년', XW.year)).join('')}</select></label>
    <label class="fld">기존 여성 <select data-xwc="basis">${opt('any', '의원 또는 본선 후보', XW.basis)}${opt('member', '의원만', XW.basis)}</select></label>
    <label class="fld">지역구 성향 <select data-xwc="lean">${Object.entries(LEAN).map(([k, v]) => opt(k, v[0], XW.lean)).join('')}</select></label>
    <label class="chk"><input type="checkbox" data-xwc="excl" ${XW.excl ? 'checked' : ''}> 이번 여성 후보 본인은 빼고 세기</label></div>`;
  if (!units.some(u => u.r.women_prior_since_1990 !== undefined)) return h + '<p class="muted">기존 여성 수 자료를 아직 만들고 있습니다. 잠시 뒤 다시 열어 주세요.</p>';
  h += `${xwStudy(units, 'D')}${xwStudy(units, 'R')}
  <p class="note">오른쪽 아래 칸은 '있음'의 남녀 차이에서 '없음'의 남녀 차이를 뺀 값입니다. +면 기존 여성이 있던 선거구에서 여성 유권자가 남성 유권자보다 여성 후보를 더 찍는 쪽으로, −면 남성 유권자가 상대적으로 더 찍는 쪽으로 차이가 움직였다는 뜻입니다. * = p &lt; .05.</p>
  <div class="note caution"><b>볼 때 주의할 점</b><ol>
    <li>투표는 정당의 영향이 커서(여성 유권자가 민주당을 더 찍음) 민주당 여성 후보와 공화당 여성 후보를 나눠 봅니다. 여성 대 남성 선거만 쓰고, 둘 다 여성인 선거와 한 당 후보만 나온 선거는 뺐습니다.</li>
    <li>'기존 여성'은 이어지는 선거구(주민 2/3 이상이 겹치는 예전 선거구, 없으면 같은 의원의 선거구) 기준입니다. '의원 또는 본선 후보'는 1990년 선거 때 의회부터 선거일까지 여성 의원이 있었거나, 1990년부터 직전 선거까지 본선에 민주·공화 여성 후보(당락 무관)가 나왔던 곳입니다. 1990년 이후 여성 후보가 한 번이라도 나온 곳이 대부분이라 '없음' 묶음이 작고, 뒤 연도일수록 '있음'이 많아집니다.</li>
    <li>'본인은 빼고 세기'를 켜면 이번 선거에 나온 여성 후보 자신은 세지 않습니다. 끄면 재선에 나온 현직 여성 의원의 선거구가 '있음'에 들어가 현직 효과가 섞입니다.</li>
    <li>단순 비교입니다. '있음'과 '없음' 선거구는 당파 성향·현직 여부 등도 다릅니다(위 '지역구 성향'으로 나눠 볼 수 있음). 같은 선거구 안의 남녀를 비교하는 '차이(여 − 남)'와 그 차이를 다시 비교한 오른쪽 아래 칸은 이런 차이의 영향을 덜 받습니다.</li>
    <li>* = p &lt; .05(95% 범위가 0을 포함하지 않음). 같은 선거의 응답자끼리 닮은 점을 감안해 선거 단위로 묶어 계산한 표준오차입니다. 응답자가 직접 답한 투표이고, 가중치는 CES 선거 뒤 가중치(없는 해는 선거 전 가중치)입니다. 당파 성향은 2008년부터 Cook 방식 당파 지수, 그 전은 직전 대선 득표율입니다.</li></ol></div>`;
  h += await xwModelsHtml();
  // districts (one year)
  if (ys.length === 1) {
    const L = units.filter(u => u.m === 'F-M' || u.m === 'M-F').sort((a, b) => a.r.state.localeCompare(b.r.state) || a.r.district - b.r.district);
    const nTd = n => `<td class="num${n < 30 ? ' muted' : ''}">${n}</td>`;
    const tr = u => {
      const P = u.m === 'M-F' ? 'R' : 'D', name = P === 'D' ? u.r.d_nominee : u.r.r_nominee, a = share1(u, 'F', P), b = share1(u, 'M', P), k = xwPrior(u);
      return `<tr><td>${esc(raceLabel(u.r))}</td><td>${esc(name)} <span class="p${P}">(${PARTY[P]})</span></td><td class="num">${k === null ? '–' : k + '명'}</td>${nTd(u.c.F.n)}<td class="num">${a === null ? '–' : fmt(a) + '%'}</td>${nTd(u.c.M.n)}<td class="num">${b === null ? '–' : fmt(b) + '%'}</td><td class="num">${a !== null && b !== null ? pp(a - b) : '–'}</td></tr>`;
    };
    const tbl = list => list.length ? `<div class="tbl-wrap"><table><thead><tr><th>선거구</th><th>여성 후보</th><th class="num">기존 여성</th><th class="num">여성 유권자</th><th class="num">여성 유권자의 여성 후보 지지율</th><th class="num">남성 유권자</th><th class="num">남성 유권자의 여성 후보 지지율</th><th class="num">차이(여 − 남)</th></tr></thead><tbody>${list.map(tr).join('')}</tbody></table></div>` : '<p class="muted" style="padding:0 12px">없음</p>';
    const yes = L.filter(u => xwPrior(u) > 0), no = L.filter(u => xwPrior(u) === 0);
    h += `<h3>선거구별(${ys[0]}년)</h3><p class="muted">여성 대 남성 선거만 보여 줍니다. 응답자가 30명 미만인 칸은 회색이고, 선거구 하나의 비율은 오차가 큽니다.</p>
    <details class="cb" open><summary><b>기존 여성 있음</b> <span class="muted">${yes.length}곳</span></summary>${tbl(yes)}</details>
    <details class="cb" open><summary><b>기존 여성 없음</b> <span class="muted">${no.length}곳</span></summary>${tbl(no)}</details>`;
  } else h += `<p class="muted">선거구별 표는 위 '연도'에서 한 해를 고르면 나옵니다.</p>`;
  // reference: the same party's candidate, woman or man
  const nameP = { D: '민주당', R: '공화당' };
  const isF = (u, P) => (P === 'D' ? u.r.d_nominee_gender : u.r.r_nominee_gender) === 'F';
  let rows = '';
  for (const P of ['D', 'R']) {
    const side = () => P, gF = gapStats(units.filter(u => isF(u, P)), side), gM = gapStats(units.filter(u => !isF(u, P)), side);
    const row = (lab, g) => g ? `<tr><td>${lab}</td><td class="num">${g.races}</td><td class="num">${fmt(g.f.p)}%</td><td class="num">${fmt(g.m.p)}%</td><td class="num">${ppS(g.gap, g.se)}</td></tr>`
      : `<tr><td>${lab}</td><td class="num" colspan="4">해당 선거구 없음</td></tr>`;
    rows += `<tr class="grp"><td colspan="5"><b class="p${P}">${nameP[P]} 후보 지지율</b></td></tr>${row(`${nameP[P]} 후보가 여성`, gF)}${row(`${nameP[P]} 후보가 남성`, gM)}
      <tr class="did"><td>차이의 차이(여성 후보 − 남성 후보)</td><td colspan="3"></td><td class="num"><b>${gF && gM ? ppS(gF.gap - gM.gap, Math.hypot(gF.se, gM.se)) : '–'}</b></td></tr>`;
  }
  h += `<details class="cb"><summary><b>참고: 그 당 후보가 여성일 때와 남성일 때</b> <span class="muted">기존 여성과 상관없이 같은 당 후보 지지율의 남녀 차이</span></summary>
    <div class="tbl-wrap"><table><thead><tr><th></th><th class="num">선거구</th><th class="num">여성 유권자</th><th class="num">남성 유권자</th><th class="num">차이(여 − 남)</th></tr></thead><tbody>${rows}</tbody></table></div></details>
  <h3>내려받기</h3>
  <div class="btns"><a class="btn" href="data/ces/ces_districts.csv" download>선거 × 응답자 성별 CSV</a><a class="btn" href="data/ces/ces_districts.dta" download>Stata (.dta)</a>
    <a class="btn" href="data/ces/ces_districts_pid.csv" download>× 정당 일체감 CSV</a><a class="btn" href="data/ces/ces_districts_pid.dta" download>Stata (.dta)</a></div>
  <p class="muted">응답자 한 사람씩이 아니라 선거 × 응답자 성별로 센 수입니다. 기존 여성 수(women_prior_since_1990 등)도 들어 있어 위 표를 Stata에서 다시 만들 수 있습니다.</p>
  ${await codebookHtml('data/ces/codebook.json', 'data/ces/codebook.csv', false)}
  <p class="note">자료: ${esc(meta.citation)} (${esc(meta.version)}판, ${esc(meta.license)}, ${esc(meta.downloaded)} 받음).</p>`;
  return h;
}
async function xwModelsHtml() {
  // individual-level models (pipeline/ces_models.py, workflow 'CES individual models'): the same 'earlier women' choice
  // as the tables above; the year and lean choices do not apply (always 2008-2024)
  let M;
  try { M = S.cesModels || (S.cesModels = await getJSON('data/ces/ces_models.json')); }
  catch (e) { return '<h3>개인 단위 회귀분석</h3><p class="muted">회귀분석 결과를 아직 만들고 있습니다.</p>'; }
  const prior = (XW.basis === 'member' ? 'women_members_since_1990' : 'women_prior_since_1990') + (XW.excl ? '_excl' : '');
  const get = (wp, est) => M.models.find(m => m.wp === wp && m.prior === prior && m.est === est);
  const yrs = M.meta.years, nm = { D: '민주당', R: '공화당' }, other = { D: '공화당', R: '민주당' };
  const sig = p => p !== null && p !== undefined && p < 0.05 ? '*' : '';
  const pct = x => x ? `${fmt(x[0])}%` : '–';
  const dp = x => x ? pp(x[0]) + sig(x[2]) : '–';
  const adj = wp => {
    const m = get(wp, 'lpm');
    if (!m) return '';
    const P = m.pred;
    return `<div class="chart-block"><b><span class="p${wp}">${nm[wp]} 여성 후보</span> 대 ${other[wp]} 남성 후보: 통제한 뒤의 표</b>
      <div class="cap top">칸: 여성 후보를 찍을 확률(선형확률모형, 다른 변수는 실제 값 그대로 두고 성별·기존 여성만 바꿔 평균). 선거 ${m.races.toLocaleString('ko-KR')}곳(기존 여성 있음 ${m.prior_races.toLocaleString('ko-KR')}곳), 응답자 ${m.n.toLocaleString('ko-KR')}명</div>
      <div class="tbl-wrap"><table class="study"><thead><tr><th></th><th class="num">여성 유권자</th><th class="num">남성 유권자</th><th class="num">차이(여 − 남)</th></tr></thead><tbody>
      <tr><td>기존 여성 있음</td><td class="num">${pct(P.F1)}</td><td class="num">${pct(P.M1)}</td><td class="num">${dp(P.gap1)}</td></tr>
      <tr><td>기존 여성 없음</td><td class="num">${pct(P.F0)}</td><td class="num">${pct(P.M0)}</td><td class="num">${dp(P.gap0)}</td></tr>
      <tr class="dif"><td>차이(있음 − 없음)</td><td class="num">${dp(P.dF)}</td><td class="num">${dp(P.dM)}</td><td class="num"><b>${dp(P.did)}</b></td></tr></tbody></table></div></div>`;
  };
  const cf = (m, t, scale = 100) => {
    const c = m && m.coef[t];
    if (!c) return '–';
    const v = c[0] * scale, se = c[1] * scale;
    return `${scale === 100 ? pp(v) : (v > 0 ? '+' : v < 0 ? '−' : '') + fmt(Math.abs(v), 3)}${sig(c[2])} <span class="muted">(${fmt(se, scale === 100 ? 1 : 3)})</span>`;
  };
  const rowsDef = [['female_x_prior', '여성 유권자 × 기존 여성'], ['female', '여성 유권자'], ['prior', '기존 여성 있음'], ['copart', '여성 후보와 같은 정당 지지'], ['outpart', '여성 후보와 반대 정당 지지'],
    ['same_race_w', '여성 후보와 같은 인종'], ['same_race_m', '남성 후보와 같은 인종'], ['w_nonwhite', '여성 후보가 백인 아님'], ['m_nonwhite', '남성 후보가 백인 아님'],
    ['m_race_unk', '남성 후보 인종 모름'], ['w_inc', '여성 후보가 현직'], ['m_inc', '남성 후보가 현직']];
  const L = { D: get('D', 'lpm'), R: get('R', 'lpm') }, G = { D: get('D', 'logit'), R: get('R', 'logit') };
  let rows = rowsDef.map(([t, lab]) => `<tr${t === 'female_x_prior' ? ' class="grp"' : ''}><td>${lab}</td><td class="num">${cf(L.D, t)}</td><td class="num">${cf(L.R, t)}</td></tr>`).join('');
  rows += `<tr class="dif"><td>로짓: 여성 유권자 × 기존 여성(계수)</td><td class="num">${cf(G.D, 'female_x_prior', 1)}</td><td class="num">${cf(G.R, 'female_x_prior', 1)}</td></tr>
    <tr><td>로짓: 확률로 바꾼 차이의 차이</td><td class="num">${G.D ? dp(G.D.pred.did) : '–'}</td><td class="num">${G.R ? dp(G.R.pred.did) : '–'}</td></tr>
    <tr><td class="muted">응답자 / 선거 · R²(선형)</td><td class="num muted">${L.D ? `${L.D.n.toLocaleString('ko-KR')} / ${L.D.races} · ${fmt(L.D.fit, 2)}` : '–'}</td><td class="num muted">${L.R ? `${L.R.n.toLocaleString('ko-KR')} / ${L.R.races} · ${fmt(L.R.fit, 2)}` : '–'}</td></tr>`;
  const wq = '"';
  const ctrl = 'copart outpart same_race_w same_race_m m_race_unk w_nonwhite m_nonwhite r_black r_hisp r_asian r_other college age10 lib con ideo_ns pvi rural black_nh hisp_d asian_nh ba_plus inc10k w_inc m_inc';
  return `<h3>개인 단위 회귀분석(${yrs[0]}–${yrs[yrs.length - 1]})</h3>
  <p class="muted">CES 응답자 한 명이 한 줄인 자료로, 여성 후보를 찍었는지(1/0)를 '여성 유권자 × 기존 여성'과 통제변수로 설명합니다. 위의 '기존 여성'과 '본인은 빼고 세기' 선택을 따르고, 연도·지역구 성향 선택은 적용되지 않습니다(${yrs[0]}–${yrs[yrs.length - 1]}년 전체, 지역구 특징 자료가 2008년부터 있음).</p>
  ${adj('D')}${adj('R')}
  <div class="tbl-wrap"><table><thead><tr><th>변수(선형확률모형, %p)</th><th class="num pD">민주당 여성 후보</th><th class="num pR">공화당 여성 후보</th></tr></thead><tbody>${rows}</tbody></table></div>
  <div class="note"><b>모형</b>: 여성 후보 선택(1/0) = 여성 유권자 + 기존 여성 + 여성 유권자 × 기존 여성 + 같은 정당·반대 정당 지지(기우는 무당파 포함, 기준: 무당파) + 여성 후보와 같은 인종 + 남성 후보와 같은 인종 + 남성 후보 인종 모름 + 여성·남성 후보가 백인 아님 + 응답자 인종·4년제 대졸·나이·이념 + 선거구 당파 지수·농촌·흑인·히스패닉·아시아계·대졸 비율·소득 중앙값 + 여성·남성 후보 현직 + 연도 고정효과.
    CES 가중치, 표준오차는 선거 단위로 묶음(Stata의 vce(cluster)와 같은 보정). 괄호는 표준오차, * = p &lt; .05. 선형확률모형 계수는 확률 차이(%p), 로짓 계수는 로그 오즈입니다.
    후보 인종은 순서대로 ① 여성은 CAWP 코드 ② 출판된 후보 인종 코드 모음(Hassell & Visalvanich, Fraga & Rendleman/FiveThirtyEight, Daily Kos Elections, Grumbach & Sahn, Lempert, CandiData, 하원 역사실 등) ③ 출처를 남긴 웹 조사 ④ Reflective Democracy Campaign의 공표 분류(사용자 파일에 따로 표시된 것, 개별 기록의 조사·추정 방식은 구분되지 않음) ⑤ 성과 이름이 모두 히스패닉 쪽인 사람은 히스패닉(추정)(확률 0.9 이상, 미국 인구조사 2010 성씨표와 Tzioumis 2018 이름표) ⑥ 의회에 있었던 사람은 위키백과의 흑인·히스패닉·아시아계·원주민·중동계 의원 명단 ⑦ 명단에 없는 의원은 백인(추정)으로 정합니다. 그래도 모르면 '인종 모름'을 1로, 같은 인종·백인 아님은 0으로 넣습니다${M.meta.man_race ? `(남성 후보 선거 수: ${Object.entries(M.meta.man_race).map(([k, v]) => `${esc({ file: '출판 코드', research: '웹 조사', rdc: '기관 분류(RDC)', surname: '히스패닉(추정)', list: '의원 명단', member: '명단에 없는 의원(백인으로 봄)', none: '모름' }[k] || k)} ${v}`).join(', ')})` : ''}. '남성 후보 인종 모름'은 어느 자료에도 없는 남성(대개 약한 도전자)이라는 뜻도 함께 담고 있어, 이 계수는 인종보다 후보 경쟁력 차이로 읽는 것이 맞습니다. 응답자 인종은 CES race_h(히스패닉이면 히스패닉)입니다. 정당 지지는 선거 전 조사의 7점 척도(pid7)입니다.</div>
  <div class="btns"><a class="btn" href="data/ces/ces_models.csv" download>계수 전체 CSV</a><a class="btn" href="data/ces/ces_models_pred.csv" download>보정 예측 CSV</a><a class="btn" href="data/ces/ces_individual.zip" download>분석 자료(.dta, zip)</a></div>
  <div class="btns"><a class="btn" href="data/ces/nominee_race.csv" download>후보 인종 자료 CSV</a><a class="btn" href="data/ces/nominee_race.dta" download>Stata (.dta)</a></div>
  <p class="muted">후보 인종 자료는 후보 한 명이 한 줄입니다(선거 번호, 의회, 대결, 정당, 이름, 성별, 현직, 인종 코드, 근거 race_src, 출처와 주소, 메모). 2008–2024년은 하원에서 민주·공화 후보가 모두 나온 선거(분석 대상)이고, 2026년은 하원·상원의 민주·공화 후보 전부입니다(분석에는 안 들어감). race_src가 rdc인 줄은 Reflective Democracy Campaign의 분류, surname인 줄은 이름으로 본 히스패닉(추정)이라 따로 거를 수 있고, none은 아직 모르는 후보입니다.</p>
  <p class="muted">분석 자료는 응답자 한 명이 한 줄인 Stata 파일을 zip으로 묶은 것입니다. 모형은 여성 대 남성 선거만 쓰지만, 자료에는 민주·공화 후보가 둘 다 여성인 선거(ff = 1)와 둘 다 남성인 선거(mm = 1)의 응답자도 들어 있습니다(여성 대 남성은 mixed = 1). 이런 선거에는 민주 후보 투표(vote_d)와 정당별 후보의 성별·인종·현직, 응답자와의 같은 인종 여부(same_race_d, same_race_r)가 있고, 여성 후보 기준 변수(vote_woman, wparty 등)는 비어 있습니다.</p>
  <details class="cb"><summary><b>Stata로 다시 돌리기</b> <span class="muted">zip을 풀어 ces_individual.dta를 연 뒤, 지금 고른 모형</span></summary><div style="padding:8px 12px">
  <pre class="code">gen prior = ${prior} > 0 if ${prior} &lt; .
global X ${ctrl}
reg vote_woman i.female##i.prior $X i.year if wparty==${wq}D${wq} & weight>0 [pw=weight], vce(cluster race_n)
reg vote_woman i.female##i.prior $X i.year if wparty==${wq}R${wq} & weight>0 [pw=weight], vce(cluster race_n)
logit vote_woman i.female##i.prior $X i.year if wparty==${wq}R${wq} & weight>0 [pw=weight], vce(cluster race_n)</pre></div></details>`;
}
function xwOk() { if (XW.ok) return true; try { return sessionStorage.getItem('uswc-xw') === '1'; } catch (e) { return false; } }
async function sha256hex(s) { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join(''); }
async function xwRender() {
  const body = $('#panelBody'), box = $('#panel .panel-in'), top = $('#panel').hidden ? 0 : box.scrollTop;
  if (!body.querySelector('[data-xwc]')) body.innerHTML = '<p class="loading">불러오는 중…</p>';
  $('#panel').hidden = false;
  try {
    body.innerHTML = await xwHtml();
    body.querySelectorAll('[data-xwc]').forEach(el => el.addEventListener('change', e => {
      const k = e.target.dataset.xwc;
      XW[k] = k === 'excl' ? e.target.checked : e.target.value;
      xwRender();
    }));
    box.scrollTop = top;
  } catch (e) { body.innerHTML = `<p>자료를 불러오지 못했습니다: ${esc(e.message)}</p>`; console.error(e); }
}
function xwOpen() {
  if (xwOk()) { $('#panel .panel-in').scrollTop = 0; $('#panel').hidden = true; return xwRender(); }
  $('#panelBody').innerHTML = `<form class="xw-lock" id="xwForm"><p>비밀번호(숫자 5자리)</p>
    <input id="xwPin" type="password" inputmode="numeric" maxlength="5" autocomplete="off" aria-label="비밀번호"> <button class="btn" type="submit">확인</button>
    <p class="muted" id="xwMsg"></p></form>`;
  $('#panel').hidden = false; $('#panel .panel-in').scrollTop = 0;
  setTimeout(() => $('#xwPin').focus(), 0);
  $('#xwForm').addEventListener('submit', async e => {
    e.preventDefault();
    let ok = false;
    try { ok = (await sha256hex(XW_SALT + $('#xwPin').value.trim())) === XW_HASH; }
    catch (err) { $('#xwMsg').textContent = '이 브라우저에서는 열 수 없습니다.'; return; }
    if (!ok) { $('#xwMsg').textContent = '비밀번호가 맞지 않습니다.'; $('#xwPin').select(); return; }
    XW.ok = true;
    try { sessionStorage.setItem('uswc-xw', '1'); } catch (err) { /* private window: ask again next time */ }
    xwRender();
  });
}

async function viewList() {
  const Y = await loadYear(S.year);
  let R = Y.r.filter(r => r.chamber === S.ch);
  if (S.onlyWomen) R = R.filter(r => (Y.cBy[r.race_id] || []).some(c => c.gender === 'F'));
  if (S.q) { const q = S.q.toLowerCase(); R = R.filter(r => (r.race_id + ' ' + (STATE_KO[r.state] || '') + ' ' + (Y.cBy[r.race_id] || []).map(c => c.name).join(' ')).toLowerCase().includes(q)); }
  const nm = (n, g) => n ? `${esc(n)} ${g === 'F' ? '<span class="badge f">여</span>' : ''}` : '<span class="muted">–</span>';
  const pw = (r, party) => { const p = (Y.pBy[r.race_id] || []).find(x => x.party === party); return p ? `${p.n_women}/${p.n_cand}${p.woman_won === 1 ? ' <span class="badge f">여성 승</span>' : ''}` : '–'; };
  return `<div class="btns" style="align-items:center"><input type="search" data-q placeholder="주·선거구(예: CA-12)나 후보 이름" value="${esc(S.q)}" style="font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:8px;min-width:240px;background:var(--card);color:var(--fg)">
    <label class="chk"><input type="checkbox" data-onlywomen ${S.onlyWomen ? 'checked' : ''}> 여성 후보가 있는 선거만</label><span class="muted">${R.length}곳</span></div>
  <div class="tbl-wrap"><table><thead><tr><th>선거</th><th>민주 후보</th><th>공화 후보</th><th>당선</th><th class="num">민주 경선 여성/후보</th><th class="num">공화 경선 여성/후보</th><th class="num">민주 양당 득표율</th><th>당파 성향</th></tr></thead><tbody>
  ${R.sort((a, b) => a.state.localeCompare(b.state) || a.district - b.district || a.special - b.special).map(r => `<tr class="click" data-open="race:${esc(r.race_id)}"><td>${esc(raceLabel(r))}</td><td>${nm(r.d_nominee, r.d_nominee_gender)}</td><td>${nm(r.r_nominee, r.r_nominee_gender)}</td>
    <td>${r.winner ? `<span class="p${r.winner_party || 'I'}">${esc(r.winner)}</span>${r.winner_gender === 'F' ? ' <span class="badge f">여</span>' : ''}` : '<span class="muted">아직 모름</span>'}</td><td class="num">${pw(r, 'D')}</td><td class="num">${pw(r, 'R')}</td><td class="num">${fmt(r.d_share_2party)}</td><td>${esc(leanLabel(lean(r, Y)))}</td></tr>`).join('')}
  </tbody></table></div>`;
}

/* --- race panel --- */
function racePanel(id) {
  const y = +id.slice(0, 4), Y = S.cache[y];
  if (!Y) return '<p>불러오는 중…</p>';
  const r = Y.rIndex[id]; if (!r) return '<p>선거를 찾을 수 없습니다.</p>';
  const cs = Y.cBy[id] || [], ps = Y.pBy[id] || [];
  const link = c => c.link ? `<a href="https://en.wikipedia.org/wiki/${encodeURIComponent(String(c.link).replace(/ /g, '_'))}" target="_blank" rel="noopener">${esc(c.name)}</a>` : esc(c.name);
  const lx = lean(r, Y);
  let h = `<h2>${y}년 ${esc(raceLabel(r))}</h2>
  <div class="kv"><div>경선 방식</div><div>${esc(SYSTEM[r.system] || r.system)}</div>
  <div>현직</div><div>${r.incumbent_running === 1 ? `${PARTY[r.incumbent_party] || ''} ${r.incumbent_gender === 'F' ? '여성' : '남성'} 현직 출마` : '현직 없음'}</div>
  <div>현직자</div><div>${esc(r.seat_member_on_eday || '–')}${r.seat_member_female === 1 ? ' (여성)' : ''}</div>
  <div>기존 여성 의원</div><div>같은 지도 안 ${r.women_members_same_map ?? '–'}명${r.chamber === 'H' ? ` · 이어지는 선거구 1990년부터 누적 ${r.women_members_since_1990 ?? '–'}명` : ''}</div>
  <div>지역구</div><div>당파 성향 ${esc(leanLabel(lx) || '–')}${num(r.rural) !== null ? ` · 농촌 ${fmt(r.rural)}%` : ''}${num(r.white_nh) !== null ? ` · 비히스패닉 백인 ${fmt(r.white_nh)}% · 흑인 ${fmt(r.black_nh)}% · 히스패닉 ${fmt(r.hisp)}% · 대졸 ${fmt(r.ba_plus)}%` : ''}</div>
  <div>당선</div><div>${r.winner ? `${esc(r.winner)} (${PARTY[r.winner_party] || '?'}${r.winner_gender === 'F' ? ', 여성' : ''})` : '<span class="prov">아직 모름</span>'}</div></div>`;
  for (const p of ps.sort((a, b) => a.party.localeCompare(b.party))) {
    const cc = cs.filter(c => c.p_party === p.party).sort((a, b) => (num(b.p_votes) ?? -1) - (num(a.p_votes) ?? -1));
    h += `<h3>${PARTY[p.party]}당 ${PARTY_PRIMARY.has(p.contest) ? '경선' : '1차 투표'} <span class="muted">(${esc(CONTEST[p.contest] || p.contest)})</span></h3>
    <div class="tbl-wrap"><table><thead><tr><th>후보</th><th>성별</th><th class="num">득표</th><th class="num">득표율</th><th class="num">결선</th><th>결과</th></tr></thead><tbody>
    ${cc.map(c => `<tr><td>${link(c)}${c.incumbent === 1 ? ' <span class="badge">현직</span>' : ''}</td><td>${gtag(c.gender)}</td><td class="num">${num(c.p_votes) === null ? '–' : (+c.p_votes).toLocaleString()}</td><td class="num">${fmt(c.p_pct)}</td><td class="num">${fmt(c.r_pct)}</td>
      <td>${c.p_won === 1 ? '<span class="win">승리</span>' : c.p_won === 0 ? '패배' : ''} <span class="muted">${esc(c.p_status && c.p_status !== 'votes' ? c.p_status : '')}</span></td></tr>`).join('')}</tbody></table></div>`;
  }
  const gen = cs.filter(c => num(c.g_votes) !== null || num(c.g_pct) !== null || c.g_won !== null).sort((a, b) => (num(b.g_pct) ?? -1) - (num(a.g_pct) ?? -1));
  if (gen.length) h += `<h3>본선</h3><div class="tbl-wrap"><table><thead><tr><th>후보</th><th>정당</th><th>성별</th><th class="num">득표</th><th class="num">득표율</th><th class="num">결선</th><th>결과</th></tr></thead><tbody>
    ${gen.map(c => `<tr><td>${link(c)}${c.incumbent === 1 ? ' <span class="badge">현직</span>' : ''}</td><td class="p${c.party === 'O' ? 'I' : c.party}">${PARTY[c.party]}</td><td>${gtag(c.gender)}</td><td class="num">${num(c.g_votes) === null ? '–' : (+c.g_votes).toLocaleString()}</td><td class="num">${fmt(c.g_pct)}</td><td class="num">${fmt(c.gr_pct)}</td><td>${c.g_won === 1 ? '<span class="win">당선</span>' : ''}</td></tr>`).join('')}</tbody></table></div>`;
  const srcs = [...new Set(cs.flatMap(c => [c.src_p, c.src_g]).filter(Boolean))];
  const gsrc = [...new Set(cs.map(c => c.gender_src).filter(Boolean))];
  h += `<p class="muted" style="font-size:.84rem">결과 출처: ${esc(srcs.map(x => RSRC[x] || x).join(', ') || '–')} · 성별 출처: ${esc(gsrc.map(x => GSRC[x] || x).join(', ') || '–')}</p>`;
  return h;
}
async function openPanel(key) {
  S.open = key; writeHash();
  const id = key.slice(key.indexOf(':') + 1);
  await loadYear(+id.slice(0, 4));
  $('#panelBody').innerHTML = racePanel(id);
  $('#panel').hidden = false; $('#panel .panel-in').scrollTop = 0;
}
function closePanel() { S.open = null; $('#panel').hidden = true; writeHash(); }

/* --- downloads --- */
const LABELS = { race_id: '선거 ID', year: '선거 연도', chamber: '원(H 하원, S 상원)', state: '주', district: '선거구(0 = 전역구·상원)', special: '특별선거(1)', system: '경선 방식',
  name: '후보 이름', party: '정당(D/R/O)', gender: '성별(F/M)', gender_src: '성별 출처', race_eth: '인종(CAWP, 여성 후보)', incumbent: '현직(1)', p_party: '경선 정당', p_status: '경선 상태',
  p_votes: '경선 득표수', p_pct: '경선 득표율(%)', r_votes: '경선 결선 득표수', r_pct: '경선 결선 득표율(%)', p_won: '경선 승리(1)', g_votes: '본선 득표수', g_pct: '본선 득표율(%)', g_won: '본선 당선(1)',
  gr_votes: '본선 결선 득표수', gr_pct: '본선 결선 득표율(%)', qual: '후보 자질(Pettigrew 코드)', office: '이전 경력(Pettigrew 코드)', fec_id: 'FEC 후보 번호', src_p: '경선 자료 출처', src_g: '본선 자료 출처',
  cawp_primary: 'CAWP 경선 결과', cawp_general: 'CAWP 본선 결과', cawp_seat: 'CAWP 경선 위치', link: '위키백과 문서', contest: '경선 종류', n_cand: '후보 수', n_women: '여성 후보 수', n_men: '남성 후보 수',
  n_unknown: '성별 모름 후보 수', incumbent_running: '현직 출마(1)', incumbent_gender: '현직 성별', winner: '승자', winner_gender: '승자 성별', winner_pct: '승자 득표율(%)', woman_won: '여성이 이김(1)',
  top_woman_pct: '여성 최고 득표율(%)', top_man_pct: '남성 최고 득표율(%)', mixed: '남녀 함께 출마(1)', src: '출처', n_general: '본선 후보 수', incumbent_party: '현직 정당', open_seat: '현직 없는 선거(1)',
  seat_member_on_eday: '현직자(선거일에 그 선거구 의원)', seat_member_female: '현직자가 여성(1)', women_members_same_map: '같은 지도 안 기존 여성 의원 수', women_members_since_1990: '이어지는 선거구의 기존 여성 의원 수(1990년부터)', women_members_since_1990_excl: '위와 같되 이번 본선 여성 후보 본인 제외',
  women_prior_since_1990: '이어지는 선거구의 기존 여성(의원 또는 1990년부터 본선 후보) 수', women_prior_since_1990_excl: '위와 같되 이번 본선 여성 후보 본인 제외', d_primary_women: '민주 경선 여성 수', r_primary_women: '공화 경선 여성 수',
  d_primary_woman_won: '민주 경선 여성 승리(1)', r_primary_woman_won: '공화 경선 여성 승리(1)', d_nominee: '민주 후보', d_nominee_gender: '민주 후보 성별', r_nominee: '공화 후보', r_nominee_gender: '공화 후보 성별',
  matchup: '본선 대결(민주-공화 성별)', winner_party: '당선자 정당', woman_won_general: '여성 당선(1)', d_share_2party: '본선 민주 양당 득표율(%)', pres_d_2party: '직전 대선 민주 양당 득표율(%)',
  pvi: '당파 지수(+민주)', rural: '농촌 인구 비율(%)', white_nh: '비히스패닉 백인(%)', black_nh: '흑인(%)', hisp: '히스패닉(%)', asian_nh: '아시아계(%)', ba_plus: '대졸(%)', med_income: '가구 소득 중앙값(달러)', src_general: '본선 자료 출처' };
const STR = new Set(['race_id', 'chamber', 'state', 'system', 'name', 'party', 'gender', 'gender_src', 'race_eth', 'p_party', 'p_status', 'fec_id', 'src_p', 'src_g', 'cawp_primary', 'cawp_general', 'cawp_seat', 'link',
  'contest', 'incumbent_gender', 'winner', 'winner_gender', 'src', 'incumbent_party', 'seat_member_on_eday', 'd_nominee', 'd_nominee_gender', 'r_nominee', 'r_nominee_gender', 'matchup', 'winner_party', 'src_general']);
function dataset(name, Ys) {
  const key = { candidates: 'c', primaries: 'p', races: 'r' }[name];
  const rows = Ys.flatMap(Y => Y[key].filter(x => x.chamber === S.ch || S.dlBoth));
  const f = ['year'].concat(Object.keys(rows[0] || {}).filter(k => k !== 'year'));
  return { cols: f.map(k => ({ name: k, label: LABELS[k] || k, type: STR.has(k) ? 'str' : 'double' })), rows: rows.map(o => f.map(k => o[k] ?? null)) };
}
function csvText(cols, rows) {
  const q = v => { if (v === null || v === undefined) return ''; const s = String(v); return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  return '﻿' + [cols.map(c => c.name).join(',')].concat(rows.map(r => r.map(q).join(','))).join('\r\n');
}
async function download(kind) {
  const ys = S.dlScope === 'all' ? S.idx.years : S.dlScope === 'period' ? periodYears() : [S.year];
  const btn = document.querySelector(`[data-dl="${kind}"]`); if (btn) btn.textContent = '만드는 중…';
  await Promise.all(ys.map(loadYear));
  const ds = dataset(S.ds, ys.map(y => S.cache[y]));
  const tag = `${S.dlBoth ? 'HS' : S.ch}_${ys.length === 1 ? ys[0] : ys[0] + '-' + ys[ys.length - 1]}`;
  let blob, fn;
  if (kind === 'csv') { blob = new Blob([csvText(ds.cols, ds.rows)], { type: 'text/csv;charset=utf-8' }); fn = `wc_${S.ds}_${tag}.csv`; }
  else {
    ds.cols.forEach(c => { if (c.type === 'double' && ds.rows.every(r => r[ds.cols.indexOf(c)] === null || Number.isInteger(r[ds.cols.indexOf(c)]))) c.type = 'long'; });
    blob = new Blob([writeDta(ds.cols, ds.rows, `여성 후보 ${S.ds} ${tag}`)], { type: 'application/x-stata-dta' }); fn = `wc_${S.ds}_${tag}.dta`;
  }
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = fn; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  if (btn) btn.textContent = kind === 'csv' ? 'CSV' : 'Stata (.dta)';
}
async function codebookHtml(url = 'data/codebook.json', csvUrl = 'data/codebook.csv', full = true) {
  let cb;
  S.codebooks = S.codebooks || {};
  try { cb = S.codebooks[url] || (S.codebooks[url] = await getJSON(url)); } catch (e) { return ''; }
  const tbl = rows => `<div class="tbl-wrap"><table class="codebook"><thead><tr><th>변수</th><th>뜻</th><th>값·단위</th></tr></thead><tbody>
    ${rows.map(v => `<tr><td><code>${esc(v.name)}</code></td><td>${esc(v.label)}</td><td>${esc(v.values)}</td></tr>`).join('')}</tbody></table></div>`;
  let h = full ? `<h2>변수 설명(코드북)</h2>
  <p>위 자료들의 변수 이름이 무엇을 뜻하는지, 값은 어떻게 적었는지 정리했습니다. .dta 파일에는 변수마다 짧은 한글 설명도 붙어 있습니다.</p>
  <div class="btns"><a class="btn" href="${csvUrl}" download>코드북 CSV</a></div>` : `<p class="muted">변수 설명 <a href="${csvUrl}" download>코드북 CSV</a></p>`;
  for (const t of cb.tables) h += `<details class="cb"><summary><b>${esc(t.title)}</b> <span class="muted">${esc(t.unit)}</span></summary>${tbl(cb.vars.filter(v => v.table === t.table))}</details>`;
  if (full && cb.office && cb.office.length) h += `<details class="cb"><summary><b>이전 경력 코드</b> <span class="muted">후보의 office(하원 경선 후보, 1990–2018)</span></summary>${tbl(cb.office.map(o => ({ name: o.code, label: o.meaning, values: '' })))}</details>`;
  return h;
}
async function viewDownload() {
  const base = 'https://github.com/jongkonlee/US_female_candidates/raw/main/data/';
  return `<h2>후보 데이터 내려받기</h2>
  <div class="btns" style="align-items:center">
    <label class="fld">자료 <select data-ds><option value="candidates" ${S.ds === 'candidates' ? 'selected' : ''}>후보(한 줄 = 선거 × 후보)</option><option value="primaries" ${S.ds === 'primaries' ? 'selected' : ''}>경선(한 줄 = 선거 × 정당 경선)</option><option value="races" ${S.ds === 'races' ? 'selected' : ''}>선거(한 줄 = 선거)</option></select></label>
    <label class="fld">범위 <select data-dlscope><option value="year" ${S.dlScope === 'year' ? 'selected' : ''}>${S.year}년</option><option value="period" ${S.dlScope === 'period' ? 'selected' : ''}>비교 기간(${periodLabel()})</option><option value="all" ${S.dlScope === 'all' ? 'selected' : ''}>전체 연도</option></select></label>
    <label class="chk"><input type="checkbox" data-dlboth ${S.dlBoth ? 'checked' : ''}> 하원·상원 모두</label></div>
  <div class="btns"><button class="btn" data-dl="csv">CSV</button><button class="btn" data-dl="dta">Stata (.dta)</button></div>
  <p class="note">CSV는 UTF-8(BOM)이라 엑셀에서 한글이 그대로 보입니다. .dta는 Stata 14 이상에서 열리며 변수 설명이 한글로 붙어 있습니다. 메모(note) 열은 아래 전체 파일에만 있습니다.</p>
  <h2>선거구 정렬 자료(이어지는 선거구)</h2>
  <p>하원 선거구를 1990년 선거까지 거슬러 이은 표입니다. '기존 여성 의원' 탭의 '1990년부터 누적'이 이 표로 셉니다.</p>
  <div class="grid2">
    <div class="chart-block"><b>2026년 선거구 기준</b> <span class="muted">(한 줄 = 2026년 선거구, 435줄)</span>
      <div class="cap top">2024년부터 1988년까지 선거마다 이어지는 선거구 번호(d연도), 2026년 선거구 주민 중 그 선거구에 살던 비율(s연도), 이은 방법(r연도), 이어진 의회 수, 서로 다른 여성 의원 수와 이름</div>
      <div class="btns"><a class="btn" href="data/lineage/lineage_2026.csv" download>CSV</a><a class="btn" href="data/lineage/lineage_2026.dta" download>Stata (.dta)</a></div></div>
    <div class="chart-block"><b>모든 하원 선거(1990–2026)</b> <span class="muted">(한 줄 = 선거 × 예전 의회, 약 8만 줄)</span>
      <div class="cap top">예전 선거 연도·의회 대수, 이어지는 선거구와 선거 번호, 주민 겹침 비율, 이은 방법, 주민이 가장 많이 겹친 선거구, 그 의회의 의원과 여성 의원, 여기까지 쌓인 여성 의원 수</div>
      <div class="btns"><a class="btn" href="data/lineage/lineage_all.csv" download>CSV</a><a class="btn" href="data/lineage/lineage_all.dta" download>Stata (.dta)</a></div></div>
  </div>
  <p class="note">이은 방법: ① 그해 선거구 주민(2020년 인구조사 블록그룹 인구)의 2/3 이상이 살던 예전 선거구('인구 2/3') ② 그런 선거구가 없으면, 예전 선거구의 의원이 이번 선거에 나왔을 때 그 의원의 선거구('같은 의원') ③ 둘 다 없으면 빈칸. 선거구 번호 0은 주 전체가 한 석인 곳입니다. 1988년 줄은 1990년 선거 때 의원(101대 의회)이고, 각 예전 선거 연도는 그 선거로 뽑힌 의회(다음 해 1월부터 2년)를 뜻합니다. 자세한 설명은 <a href="https://github.com/jongkonlee/US_female_candidates/blob/main/data/README.md">data/README.md</a>.</p>
  ${await codebookHtml()}
  <h2>전체 파일(저장소)</h2>
  <ul><li><a href="${base}candidates.csv">candidates.csv</a> — 후보 전체(메모 포함)</li><li><a href="${base}primaries.csv">primaries.csv</a> — 경선 전체</li><li><a href="${base}races.csv">races.csv</a> — 선거 전체</li>
  <li><a href="${base}cawp_unmatched.csv">cawp_unmatched.csv</a> — 득표 자료에서 짝을 찾지 못한 CAWP 여성 후보</li><li><a href="https://github.com/jongkonlee/US_female_candidates/blob/main/data/README.md">data/README.md</a> — 변수 설명과 규칙</li></ul>`;
}

function viewAbout() {
  const gen = S.idx.generated ? S.idx.generated.replace('T', ' ').replace('Z', ' UTC') : '';
  const cov = S.idx.coverage.map(c => `${c.year} ${c.chamber === 'H' ? '하원' : '상원'}: ${c.source}`).join(' · ');
  return `<div class="about">
  <h2>무엇을 보여 주나</h2><p>미국 하원·상원 선거(1990년~)의 정당 경선, 결선, 본선 결과를 후보별로 모으고, 여성 후보가 어느 지역구에서 경선과 본선을 이겼는지를 후보·지역구 특징에 따라 비교합니다. 매일 한 번 GitHub Actions가 자료를 다시 받아 만듭니다.</p>
  <h2>자료</h2><ul>
  <li>2002–2022년: 연방선거관리위원회(FEC) <i>Federal Elections</i> 공식 결과(경선·결선·본선)</li>
  <li>1990–2000년 하원 경선: Pettigrew, Owen &amp; Wanless, "U.S. House Primary Election Results (1956–2010)", Harvard Dataverse(CC0). 후보 이전 경력 코드는 Miller &amp; Camberg(2012–2018, CC0)도 씀</li>
  <li>1990–2000년과 2024년 하원 본선: MIT Election Data and Science Lab(MEDSL), "U.S. House 1976–2024", Harvard Dataverse, doi:10.7910/DVN/IG0UN2(CC0). 주 정부 공식 결과를 모은 자료로, 득표수가 있습니다. 2024년은 FEC 2024년판이 나오면 FEC로 바뀝니다</li>
  <li>1990–2000년 상원, 2024년 이후 하원 경선과 상원, 2026년 하원 본선: 위키백과 선거 문서(비공식, CC BY-SA)</li>
  <li>여성 후보: Center for American Women and Politics(CAWP), Eagleton Institute of Politics, Rutgers University, Congressional Women Candidates Database ${S.idx.years[0]}–${S.idx.cawp_last_year}${listYear() ? ` · CAWP "Women Candidates ${listYear()}" 후보 목록(Congress and Statewide, ${esc(S.idx.cawp_list.downloaded)}에 내려받은 판)` : ''}</li>
  <li>의원 성별·임기: congress-legislators(unitedstates 프로젝트) · 지역구 특징(2008–2024): 인구조사국 원본 파일과 Cook 방식으로 계산한 당파 지수(여성정책 트래커와 같은 값)</li>
  <li>실제 지도의 선거구 경계: Jeffrey B. Lewis, Brandon DeVine, Lincoln Pitcher, Kenneth C. Martis, "Digital Boundary Definitions of U.S. Congressional Districts, 1789–2012"(저자들이 119대 의회까지 갱신, GitHub, MIT 사용 허가, 2026-11-05 내려받음). 2026년에 선거구를 새로 그린 주는 위키미디어 공용 지도 자료 "Data:…congressional district (2027–).map"(CC0)</li>
  <li>선거구를 이을 때의 주민 수: 미국 인구조사국, 2020년 인구조사 블록그룹별 인구 중심점(Centers of Population by Block Group, 2020, 2026-11-05 내려받음)</li></ul>
  <h2>성별을 정한 방법</h2><ul>
  <li>${S.idx.cawp_last_year}년까지: CAWP 명단에 있으면 여성, 없는 민주·공화 후보는 남성(CAWP는 주요 정당 경선에 이름을 올린 여성을 모두 실음)</li>
  ${listYear() ? `<li>${listYear()}년: 같은 방식으로 CAWP ${listYear()} 후보 목록을 씁니다. 다만 이 목록은 경선 기간 내내 고쳐지는 목록이라 빠진 사람이 있을 수 있어서, 목록에 없는 민주·공화 후보라도 위키백과 본인 문서가 '그녀(she)'로 쓰거나 예전 CAWP·의원 명부에 여성으로 나오면 여성으로, 이름만 여성 이름이면 '모름'으로 둡니다. 민주·공화 밖 후보는 아래 방법으로 정합니다</li>` : ''}
  <li>CAWP 자료가 없는 해와 민주·공화 밖 후보: ① 위키백과 본인 문서의 대명사 ② 예전 CAWP 기록 ③ 의원 명부·예전 경선 자료 ④ 이름(미국 출생 기록에서 95% 이상 한쪽 성별) 순서로 정하고, 모르면 빈칸</li></ul>
  <h2>규칙</h2><ul>
  <li>경선 승리: 결선이 있으면 결선 승자, 없으면 최다 득표자. 단독 후보·전당대회·경선 기록이 없으면 본선에 나간 그 당 후보</li>
  <li>'정당 경선만'은 처음에 꺼져 있습니다. 켜면 정당별 경선을 하지 않는 캘리포니아·워싱턴(상위 2인 경선), 알래스카(상위 4인 경선, 2022년부터), 루이지애나(정당 구분 없는 1차 투표를 한 해)를 경선과 본선 비교에서 모두 뺍니다. 끈 상태에서 이런 곳의 '그 당 경선 승리'는 그 당 후보 가운데 본선에 나간 사람(둘 이상 나가면 1차 투표 득표가 가장 많은 사람, 루이지애나는 그 당 최다 득표자)이 여성인지로 봅니다. '여성 후보가 본선에 나감'은 본선에 오른 민주·공화 후보를 모두 봅니다(민주 대 민주처럼 같은 당끼리 붙은 본선 포함)</li>
  <li>하원 특별선거(잔여 임기)는 뺐고, 상원은 본선 날 치른 특별선거를 따로 셉니다</li>
  <li>기존 여성 의원(하원): '같은 지도 안'은 지금 선거구 지도가 쓰인 뒤 선거일까지 그 번호 선거구를 맡은 서로 다른 여성 의원 수로, 10년마다 0부터 다시 셉니다. '1990년부터 누적'은 이어지는 선거구를 맡은 서로 다른 여성 의원 수입니다. 이어지는 선거구는 의회마다 ① 그해 선거구 주민(2020년 인구 기준)의 2/3 이상이 살던 예전 선거구, ② 없으면 이번 선거에 나온 예전 의원의 선거구, ③ 둘 다 없으면 없음으로 정합니다(1990년 선거 때 의회부터). 상원은 1985년부터 그 주의 두 자리를 셉니다</li>
  <li>당파 성향: 2008년부터는 Cook 방식 당파 지수, 그 전 하원은 직전 대선 민주 양당 득표율에서 그해 선거구 중앙값을 뺀 값</li></ul>
  <h2>점검</h2><ul><li>여성 당선자 수는 1990–2024년 하원·상원 모두 CAWP 집계와 같습니다(CAWP 파일의 정당 표기가 다른 2명 제외)</li>
  <li>2024년 하원 본선 승자는 위키백과와 MEDSL이 435곳 모두 같았습니다. 1990–2000년은 MEDSL로 바꾸면서 위키백과 전체 표의 잘못 2곳(1992년 뉴욕 17구, 1996년 테네시 7구 당선자)을 바로잡았습니다</li>
  <li>위키백과 읽기 점검: 2022년 하원을 위키백과로 읽어 FEC와 대조해 승자 99%가 일치했습니다(나머지는 FEC 철자 오류). 뉴욕 경선 득표수는 위키백과가 1~10% 적었습니다</li></ul>
  <h2>주의</h2><ul>
  <li>올해 본선은 개표 중입니다. 위키백과 선거 상자에 득표와 함께 당선이 표시된 곳, 또는 득표가 아직 없으면 위키백과 전체 개요 표에 당선(언론 판정)이 표시된 곳을 당선으로 셉니다. 선거 직후 위키백과에는 빈칸이나 장난 편집이 있을 수 있습니다. 2026-11-04 대조: CAWP 목록이 당선으로 적은 여성 하원 후보 116명 중 115명이 여기서도 당선이고(1명은 득표만 있고 당선 표시 전), CAWP가 낙선으로 적은 108명은 모두 낙선이었습니다. 상원은 위키백과 상자에 득표가 들어가야 당선으로 셉니다</li>
  <li>루이지애나 1990–1996년은 10월 1차 투표에서 과반이 나오면 11월 선거가 없었습니다. 이런 곳은 10월 1차 투표 득표율(위키백과 전체 표)을 본선으로, 11월까지 간 곳은 11월 결과(MEDSL)를 본선으로 넣었습니다. 1996년 텍사스 13개 선거구는 선거구를 다시 그려 11월 정당 구분 없는 특별선거와 12월 결선으로 치렀습니다</li>
  <li>남성 후보의 인종과 후보 나이는 없습니다. 지역구 특징(농촌 비율·인구 구성)은 2008–2024년만 있습니다</li>
  <li>비교는 단순 비교라 원인으로 읽으면 안 됩니다</li></ul>
  <p class="muted">자료별 출처: ${esc(cov)}</p>
  <p class="muted">마지막 갱신: ${esc(gen)} · 코드와 자료: <a href="https://github.com/jongkonlee/US_female_candidates">github.com/jongkonlee/US_female_candidates</a></p></div>`;
}

/* ---------- events ---------- */
function bindMain() {
  const m = $('#main');
  m.querySelectorAll('[data-open]').forEach(el => el.addEventListener('click', e => { e.preventDefault(); openPanel(el.dataset.open); }));
  const on = (sel, ev, fn) => m.querySelectorAll(sel).forEach(el => el.addEventListener(ev, fn));
  on('[data-layer]', 'change', e => { S.layer = e.target.value; render(); });
  on('[data-mk]', 'click', e => { S.mapKind = e.currentTarget.dataset.mk; if (S.mapKind === 'tile') S.zoom = null; render(); });
  on('[data-zoomout]', 'click', zoomOut);
  bindRealMap();
  on('[data-target]', 'click', e => { S.target = e.currentTarget.dataset.target; render(); });
  on('[data-unit]', 'click', e => { S.unit = e.currentTarget.dataset.unit; render(); });
  on('[data-pm]', 'click', e => { S.priorMode = e.currentTarget.dataset.pm; render(); });
  on('[data-xwopen]', 'click', xwOpen);
  on('[data-crit]', 'change', e => { S.crit = e.target.value; render(); });
  on('[data-onlywomen]', 'change', e => { S.onlyWomen = e.target.checked; render(); });
  on('[data-q]', 'change', e => { S.q = e.target.value.trim(); render(); });
  on('[data-ds]', 'change', e => { S.ds = e.target.value; });
  on('[data-dlscope]', 'change', e => { S.dlScope = e.target.value; });
  on('[data-dlboth]', 'change', e => { S.dlBoth = e.target.checked; });
  on('[data-dl]', 'click', e => download(e.currentTarget.dataset.dl));
}

async function init() {
  try { S.idx = await getJSON('data/index.json'); }
  catch (e) { $('#main').innerHTML = '<p>자료를 아직 만들고 있습니다. 잠시 뒤 다시 열어 주세요.</p>'; return; }
  addListLabels();
  S.year = S.idx.years[S.idx.years.length - 1];
  $('#yearSel').innerHTML = S.idx.years.slice().reverse().map(y => `<option value="${y}">${y}년${isCurrent(y) ? ' (개표 중)' : ''}</option>`).join('');
  readHash();
  document.querySelectorAll('#chamberSeg button').forEach(b => b.addEventListener('click', () => { S.ch = b.dataset.ch; render(); }));
  document.querySelectorAll('#tabs button').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.tab; render(); }));
  $('#yearSel').addEventListener('change', e => { S.year = +e.target.value; render(); });
  $('#periodSel').addEventListener('change', e => { S.period = e.target.value; render(); });
  $('#partyOnly').addEventListener('change', e => { S.partyOnly = e.target.checked; render(); });
  $('#panelClose').addEventListener('click', closePanel);
  $('#panel').addEventListener('click', e => { if (e.target.id === 'panel') closePanel(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#panel').hidden) closePanel(); });
  $('#foot').innerHTML = `마지막 갱신 ${esc((S.idx.generated || '').replace('T', ' ').replace('Z', ' UTC'))} · 자료: FEC, MEDSL(MIT), CAWP(Rutgers), 위키백과, Pettigrew 외(Harvard Dataverse), congress-legislators · <a href="https://github.com/jongkonlee/US_female_candidates">GitHub</a>`;
  await render();
  if (S.open) openPanel(S.open);
}
init();
