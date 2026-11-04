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
  'member or earlier candidate': '의원 명부·예전 경선 자료', 'CAWP (earlier race)': '예전 CAWP 기록', 'unknown': '모름', 'Pettigrew and first name (not in CAWP)': 'Pettigrew 외 자료·이름', 'Pettigrew': 'Pettigrew 외 자료' };
const RSRC = { 'FEC': 'FEC 공식 결과', 'Wikipedia': '위키백과(비공식)', 'Wikipedia overview': '위키백과 전체 표(득표율만)', 'Pettigrew-Owen-Wanless': 'Pettigrew 외(하원 경선)', 'Miller-Camberg': 'Miller·Camberg(하원 경선)', 'CAWP only': 'CAWP(득표 기록 없음)' };
const C = { d: 'var(--d)', r: 'var(--r)', w: 'var(--w)', none: 'var(--none)', na: 'var(--na)', dl: '#b9cfe9', rl: '#f0c1bd', open: '#efe2b0', ff: 'var(--ff)', fm: 'var(--fm)', mf: 'var(--mf)', mm: 'var(--mm)' };

const S = { ch: 'H', year: null, tab: 'summary', period: 'year', partyOnly: true, layer: 'gen', target: 'D', unit: 'district', crit: 'lean',
  q: '', onlyWomen: false, open: null, idx: null, cache: {}, ds: 'candidates', dlScope: 'year' };

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
  if (!S.partyOnly) p.set('po', '0'); if (S.layer !== 'gen') p.set('l', S.layer); if (S.target !== 'D') p.set('tg', S.target);
  if (S.unit !== 'district') p.set('u', S.unit); if (S.crit !== 'lean') p.set('k', S.crit); if (S.open) p.set('open', S.open);
  history.replaceState(null, '', '#' + p.toString());
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get('c')) S.ch = p.get('c') === 'S' ? 'S' : 'H';
  if (p.get('y') && S.idx.years.includes(+p.get('y'))) S.year = +p.get('y');
  if (p.get('t')) S.tab = p.get('t'); if (p.get('p')) S.period = p.get('p'); S.partyOnly = p.get('po') !== '0';
  if (p.get('l')) S.layer = p.get('l'); if (p.get('tg')) S.target = p.get('tg'); if (p.get('u')) S.unit = p.get('u'); if (p.get('k')) S.crit = p.get('k');
  S.open = p.get('open');
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
  // items: [{lab, v (0-100 or null), n, sub, color}]
  return items.map(it => `<div class="bar"><div class="lab" title="${esc(it.lab)}">${esc(it.lab)} <span class="muted">(${it.n})</span></div>
    <div class="track"><div class="fill" style="width:${it.v === null ? 0 : Math.max(0, Math.min(100, it.v * 100 / (opt.max || 100)))}%;background:${it.color || 'var(--w)'}"></div></div>
    <div class="val">${it.v === null ? '–' : fmt(it.v) + '%'}</div></div>`).join('');
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
  let h = `<p class="muted">${S.year}년 ${chName(S.ch)} 선거 ${R.length}곳${cur ? ` · <span class="prov">개표 중: 당선이 확인된 곳 ${decided}곳(위키백과 기준, 비공식)</span>` : ''}${S.year > S.idx.cawp_last_year ? ' · 성별은 CAWP 명단이 나오기 전이라 다른 방법으로 정함(설명 탭)' : ''}</p>
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
  const lg = LAYERS[S.layer].legend.map(([t, c]) => `<span><i style="background:${c}"></i>${t}</span>`).join('');
  return `<div class="btns" style="align-items:center"><label class="fld">보기 <select data-layer>${Object.entries(LAYERS).map(([k, v]) => `<option value="${k}" ${S.layer === k ? 'selected' : ''}>${v.label}</option>`).join('')}</select></label>
    <span class="muted">${S.year}년 ${chName(S.ch)} · 칸 하나가 ${S.ch === 'H' ? '선거구 하나(번호 순)' : '상원 선거 하나'}입니다. 누르면 후보와 결과가 열립니다.</span></div>
  <div class="legend">${lg}</div>
  <div class="map-wrap"><svg viewBox="0 0 ${12 * cw + 8} ${rowY[7] + rowH[7] + 4}" role="img" aria-label="주별 선거구 지도">${g}</svg></div>
  <p class="note">지리 모양이 아니라 주 위치만 맞춘 칸 지도입니다. 같은 번호 선거구라도 선거구를 다시 그린 해(1992·2002·2012·2022년 등)에는 같은 지역이 아닙니다.${isCurrent(S.year) ? ' 올해 본선은 개표 중이라 당선이 확인된 곳만 칠했습니다.' : ''}</p>`;
}

/* --- comparisons --- */
function tertiles(vals) { const v = vals.map(num).filter(x => x !== null).sort((a, b) => a - b); if (v.length < 6) return null; return [v[Math.floor(v.length / 3)], v[Math.floor(2 * v.length / 3)]]; }
function tert(x, cut, unit) { if (num(x) === null || !cut) return '자료 없음'; return x < cut[0] ? `하위 1/3 (${fmt(cut[0], 0)}${unit} 미만)` : x < cut[1] ? '중간 1/3' : `상위 1/3 (${fmt(cut[1], 0)}${unit} 이상)`; }
const LEAN_ORDER = ['민주 강세 (+15 이상)', '민주 우세 (+5~15)', '경합 (±5 이내)', '공화 우세 (+5~15)', '공화 강세 (+15 이상)', '자료 없음'];
function leanBin(x) { if (x === null) return '자료 없음'; return x >= 15 ? LEAN_ORDER[0] : x >= 5 ? LEAN_ORDER[1] : x > -5 ? LEAN_ORDER[2] : x > -15 ? LEAN_ORDER[3] : LEAN_ORDER[4]; }
function raceEth(code) {
  if (!code) return '자료 없음';
  const parts = String(code).split('/');
  return parts.length > 1 ? '여러 인종' : (RACE_ETH[parts[0]] || code);
}
const CRIT = {
  district: {
    lean: { label: '지역구 당파 성향', order: LEAN_ORDER, f: u => leanBin(lean(u.r, u.Y)) },
    prior_map: { label: '같은 선거구 지도 안에서 이전 여성 의원', order: ['없음', '1명', '2명 이상', '자료 없음'], f: u => { const v = num(u.r.women_members_same_map); return v === null ? '자료 없음' : v === 0 ? '없음' : v === 1 ? '1명' : '2명 이상'; } },
    seat_female: { label: '선거일에 그 선거구 의원이 여성', order: ['여성', '남성', '자료 없음'], f: u => u.r.seat_member_female === 1 ? '여성' : u.r.seat_member_female === 0 ? '남성' : '자료 없음' },
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
    prior_map: { label: '같은 선거구 지도 안에서 이전 여성 의원', order: ['없음', '1명', '2명 이상', '자료 없음'], f: u => { const v = num(u.r.women_members_same_map); return v === null ? '자료 없음' : v === 0 ? '없음' : v === 1 ? '1명' : '2명 이상'; } },
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
      const ran = l.filter(u => u.r.d_nominee_gender === 'F' || u.r.r_nominee_gender === 'F').length, won = l.filter(u => u.r.woman_won_general === 1).length;
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
  if (unit === 'woman') {
    return `<div class="chart-block"><b>${esc(title || def.label)}: 여성 후보가 ${target === 'G' ? '본선에서 당선된' : '경선에서 이긴'} 비율</b>
      ${bars(res.map(x => ({ lab: x.k, n: x.n, v: x.rate, color })), {})}
      <div class="cap">${periodLabel()} ${chName(S.ch)} ${tname}의 여성 후보 ${us.length}명. 괄호는 여성 후보 수입니다.</div></div>`;
  }
  const what = target === 'G' ? ['여성 후보가 본선에 나간 비율', '여성이 당선된 비율', '여성 후보가 나간 선거에서 여성이 이긴 비율'] : ['여성이 출마한 비율', '여성이 이긴 비율', '여성이 출마했을 때 이긴 비율'];
  const tbl = `<div class="tbl-wrap"><table><thead><tr><th>${esc(def.label)}</th><th class="num">${target === 'G' ? '선거' : '경선'}</th><th class="num">${what[0]}</th><th class="num">${what[1]}</th><th class="num">${what[2]}</th></tr></thead><tbody>
    ${res.map(x => `<tr><td>${esc(x.k)}</td><td class="num">${x.n}</td><td class="num">${fmt(x.rRan)}% <span class="muted">(${x.ran})</span></td><td class="num">${fmt(x.rWon)}% <span class="muted">(${x.won})</span></td><td class="num">${x.rCond === null ? '–' : fmt(x.rCond) + '%'}</td></tr>`).join('')}</tbody></table></div>`;
  return `<div class="grid2"><div class="chart-block"><b>${what[1]}</b>${bars(res.map(x => ({ lab: x.k, n: x.n, v: x.rWon, color })), {})}</div>
    <div class="chart-block"><b>${what[2]}</b>${bars(res.map(x => ({ lab: x.k, n: x.ran, v: x.rCond, color })), {})}<div class="cap">괄호는 여성이 출마한 ${target === 'G' ? '선거' : '경선'} 수입니다.</div></div></div>${tbl}`;
}
async function viewWhere() {
  const Ys = await loadPeriod();
  const opts = Object.entries(CRIT[S.unit]).filter(([k, v]) => !(v.only === 'primary' && S.target === 'G'));
  if (!opts.some(([k]) => k === S.crit)) S.crit = opts[0][0];
  return `<div class="btns" style="align-items:center">
    <div class="seg">${[['D', '민주당 경선'], ['R', '공화당 경선'], ['G', '본선']].map(([k, l]) => `<button data-target="${k}" class="${S.target === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    <div class="seg">${[['district', '선거구 기준'], ['woman', '여성 후보 기준']].map(([k, l]) => `<button data-unit="${k}" class="${S.unit === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    <label class="fld">기준 <select data-crit>${opts.map(([k, v]) => `<option value="${k}" ${S.crit === k ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</select></label></div>
    <p class="muted">${periodLabel()} · ${chName(S.ch)}. 기간은 위쪽 '비교 기간'에서 바꿉니다. ${S.unit === 'district' ? '선거구 기준은 "여성이 나왔는지(출마)"와 "나왔을 때 이겼는지(성공)"를 나눠 봅니다.' : '여성 후보 기준은 여성 후보 한 명 한 명이 이겼는지를 봅니다.'}</p>
    ${compareBlock(Ys, S.target, S.unit, S.crit)}
    <p class="note">집단 사이의 단순 비교입니다. 예를 들어 여성은 이기기 쉬운 곳에 더 많이 출마할 수 있어서(선택 효과), 차이를 원인으로 읽으면 안 됩니다. 회귀분석은 '내려받기'의 자료로 하실 수 있습니다. 당파 성향은 2008년부터 Cook 방식 당파 지수, 그 전 하원은 직전 대선 득표율을 그해 선거구 중앙값과 비교한 값입니다. 2026년 선거구의 당파 성향·인구 자료는 아직 없어 '자료 없음'으로 들어갑니다. 괄호 안 수가 작은 집단은 비율이 크게 흔들립니다.</p>`;
}

/* --- women vs men --- */
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
  const tab = Object.entries(M).map(([m, [lab, col, sign]]) => { const l = pts.filter(p => p.m === m); const res = mean(l.map(p => p.res));
    return `<tr><td><span class="legend" style="margin:0"><span><i style="background:${col}"></i>${lab}</span></span></td><td class="num">${l.length}</td><td class="num">${fmt(mean(l.map(p => p.y)))}%</td><td class="num">${res === null ? '–' : (res > 0 ? '+' : '') + fmt(res)}%p</td><td class="num">${sign && res !== null ? (sign * res > 0 ? '+' : '') + fmt(sign * res) + '%p' : '–'}</td></tr>`; }).join('');
  h += `<div class="chart-block"><b>본선 민주 후보 양당 득표율과 지역구 당파 성향</b><div class="chart"><svg viewBox="0 0 ${W} ${H}">${g}</svg></div>
    <div class="cap">점 하나가 선거 하나입니다(누르면 결과가 열립니다). 점선은 당파 성향만으로 본 평균선이고, 아래 표의 차이는 현직 출마까지 감안한 값입니다. ${periodLabel()} ${chName(S.ch)} 본선 ${pts.length}곳.</div></div>
  <div class="tbl-wrap"><table><thead><tr><th>본선 대결</th><th class="num">선거</th><th class="num">민주 후보 평균 득표율</th><th class="num">평균선과의 차이(민주 쪽)</th><th class="num">여성 후보 쪽 차이</th></tr></thead><tbody>${tab}</tbody></table></div>
  <p class="note">'평균선과의 차이'는 같은 당파 성향과 현직 조건에서 예상되는 민주 득표율보다 얼마나 많이(+) 또는 적게(−) 얻었는지입니다. '여성 후보 쪽'은 여성 후보 입장에서 다시 적은 값입니다(공화 여성은 부호를 바꿈). 후보의 경력·선거자금은 감안하지 않았습니다.</p>`;
  return h;
}

async function viewPrior() {
  const Ys = await loadPeriod();
  let h = `<p class="muted">${periodLabel()} · ${chName(S.ch)}. 이전에 여성 의원이 있었던 선거구와 아닌 선거구를 비교합니다.</p>`;
  for (const [crit, title] of [['prior_map', '같은 선거구 지도 안에서 이전 여성 의원(인구조사 주기 기준)'], ['seat_female', '선거일에 그 선거구 의원이 여성이었나'], ['incumbent', '현직이 출마했나']]) {
    h += `<h2>${esc(title)}</h2>`;
    for (const [t, l] of [['D', '민주당 경선'], ['R', '공화당 경선'], ['G', '본선']]) h += `<h3>${l}</h3>${compareBlock(Ys, t, 'district', crit)}`;
  }
  return h + `<p class="note">선거구를 다시 그린 해에는 같은 번호라도 다른 지역입니다. '같은 지도 안' 기준은 1992·2002·2012·2022년 지도를 한 묶음으로 보므로, 10년 중간에 선거구를 바꾼 주에서는 부정확합니다.</p>`;
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
  <div>선거일 의원</div><div>${esc(r.seat_member_on_eday || '–')}${r.seat_member_female === 1 ? ' (여성)' : ''}</div>
  <div>이전 여성 의원</div><div>같은 지도 안 ${r.women_members_same_map ?? '–'}명</div>
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
  seat_member_on_eday: '선거일 의원', seat_member_female: '선거일 의원이 여성(1)', women_members_same_map: '같은 지도 안 이전 여성 의원 수', d_primary_women: '민주 경선 여성 수', r_primary_women: '공화 경선 여성 수',
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
async function viewDownload() {
  const base = 'https://github.com/jongkonlee/US_female_candidates/raw/main/data/';
  return `<h2>골라서 내려받기</h2>
  <div class="btns" style="align-items:center">
    <label class="fld">자료 <select data-ds><option value="candidates" ${S.ds === 'candidates' ? 'selected' : ''}>후보(한 줄 = 선거 × 후보)</option><option value="primaries" ${S.ds === 'primaries' ? 'selected' : ''}>경선(한 줄 = 선거 × 정당 경선)</option><option value="races" ${S.ds === 'races' ? 'selected' : ''}>선거(한 줄 = 선거)</option></select></label>
    <label class="fld">범위 <select data-dlscope><option value="year" ${S.dlScope === 'year' ? 'selected' : ''}>${S.year}년</option><option value="period" ${S.dlScope === 'period' ? 'selected' : ''}>비교 기간(${periodLabel()})</option><option value="all" ${S.dlScope === 'all' ? 'selected' : ''}>전체 연도</option></select></label>
    <label class="chk"><input type="checkbox" data-dlboth ${S.dlBoth ? 'checked' : ''}> 하원·상원 모두</label></div>
  <div class="btns"><button class="btn" data-dl="csv">CSV</button><button class="btn" data-dl="dta">Stata (.dta)</button></div>
  <p class="note">CSV는 UTF-8(BOM)이라 엑셀에서 한글이 그대로 보입니다. .dta는 Stata 14 이상에서 열리며 변수 설명이 한글로 붙어 있습니다. 메모(note) 열은 아래 전체 파일에만 있습니다.</p>
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
  <li>1990–2000년 하원 본선(득표율만)·1990–2000년 상원·2024년 이후 전부: 위키백과 선거 문서(비공식, CC BY-SA). FEC 2024년판이 나오면 자동으로 공식 결과로 바뀝니다</li>
  <li>여성 후보: Center for American Women and Politics(CAWP), Eagleton Institute of Politics, Rutgers University, Congressional Women Candidates Database ${S.idx.years[0]}–${S.idx.cawp_last_year}</li>
  <li>의원 성별·임기: congress-legislators(unitedstates 프로젝트) · 지역구 특징(2008–2024): 인구조사국 원본 파일과 Cook 방식으로 계산한 당파 지수(여성정책 트래커와 같은 값)</li></ul>
  <h2>성별을 정한 방법</h2><ul>
  <li>${S.idx.cawp_last_year}년까지: CAWP 명단에 있으면 여성, 없는 민주·공화 후보는 남성(CAWP는 주요 정당 경선에 이름을 올린 여성을 모두 실음)</li>
  <li>그 뒤: CAWP 명단이 나오기 전이라 ① 위키백과 본인 문서의 대명사 ② 예전 CAWP 기록 ③ 의원 명부·예전 경선 자료 ④ 이름(미국 출생 기록에서 95% 이상 한쪽 성별) 순서로 정하고, 모르면 빈칸</li></ul>
  <h2>규칙</h2><ul>
  <li>경선 승리: 결선이 있으면 결선 승자, 없으면 최다 득표자. 단독 후보·전당대회·경선 기록이 없으면 본선에 나간 그 당 후보</li>
  <li>'정당 경선만'을 켜면 캘리포니아·워싱턴(상위 2인), 알래스카(상위 4인, 2022~), 루이지애나식(정당 구분 없는 1차 투표)을 뺍니다</li>
  <li>하원 특별선거(잔여 임기)는 뺐고, 상원은 본선 날 치른 특별선거를 따로 셉니다</li>
  <li>당파 성향: 2008년부터는 Cook 방식 당파 지수, 그 전 하원은 직전 대선 민주 양당 득표율에서 그해 선거구 중앙값을 뺀 값</li></ul>
  <h2>점검</h2><ul><li>여성 당선자 수는 1990–2024년 하원·상원 모두 CAWP 집계와 같습니다</li>
  <li>위키백과 읽기 점검: 2022년 하원을 위키백과로 읽어 FEC와 대조해 승자 99%가 일치했습니다(나머지는 FEC 철자 오류). 뉴욕 경선 득표수는 위키백과가 1~10% 적었습니다</li></ul>
  <h2>주의</h2><ul>
  <li>올해 본선은 개표 중입니다. 위키백과에 득표와 함께 당선이 표시된 곳만 당선으로 셉니다. 선거 직후 위키백과에는 빈칸이나 장난 편집이 있을 수 있습니다</li>
  <li>1990–2000년 하원 본선은 득표율만 있습니다. 남성 후보의 인종과 후보 나이는 없습니다. 지역구 특징(농촌 비율·인구 구성)은 2008–2024년만 있습니다</li>
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
  on('[data-target]', 'click', e => { S.target = e.currentTarget.dataset.target; render(); });
  on('[data-unit]', 'click', e => { S.unit = e.currentTarget.dataset.unit; render(); });
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
  $('#foot').innerHTML = `마지막 갱신 ${esc((S.idx.generated || '').replace('T', ' ').replace('Z', ' UTC'))} · 자료: FEC, CAWP(Rutgers), 위키백과, Pettigrew 외(Harvard Dataverse), congress-legislators · <a href="https://github.com/jongkonlee/US_female_candidates">GitHub</a>`;
  await render();
  if (S.open) openPanel(S.open);
}
init();
