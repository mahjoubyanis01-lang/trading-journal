/* Options GEX — heatmap intrajournalière alimentée par les snapshots CBOE
   commités dans data/options/ par le workflow GitHub Actions. */
'use strict';

const FALLBACK_REPO = 'mahjoubyanis01-lang/trading-journal';

// ── Résolution de la source de données ─────────────────────────────
// Sur GitHub Pages, les fichiers data/ servis par Pages peuvent être en retard
// d'un déploiement : on lit raw.githubusercontent.com (CORS ouvert, toujours à
// jour). En local, on lit les fichiers relatifs.
function dataBases() {
  const bases = [];
  const h = location.hostname;
  let repo = FALLBACK_REPO;
  if (h.endsWith('.github.io')) {
    const owner = h.slice(0, -'.github.io'.length);
    const seg = location.pathname.split('/').filter(Boolean)[0];
    if (owner && seg) repo = `${owner}/${seg}`;
    bases.push(`https://raw.githubusercontent.com/${repo}/main/`);
    bases.push('');
  } else {
    bases.push('');
    bases.push(`https://raw.githubusercontent.com/${repo}/main/`);
  }
  return bases;
}
let workingBase = null;
async function fetchJSON(path) {
  const bases = workingBase !== null ? [workingBase] : dataBases();
  let lastErr;
  for (const b of bases) {
    try {
      const r = await fetch(b + path, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      workingBase = b;
      return j;
    } catch (e) { lastErr = e; }
  }
  throw lastErr;
}

// ── État ───────────────────────────────────────────────────────────
const S = {
  manifest: null,
  symbol: null,
  days: [],
  day: null,
  snapshots: [],   // snapshots complets du jour, triés par heure
  selected: -1,    // index du snapshot sélectionné
  grid: null,      // { strikes desc, times, cells[row][col] = snapIdx|-1 }
  hmGeom: null,
  showTable: false,
};

const $ = id => document.getElementById(id);
const cssVar = name => getComputedStyle(document.querySelector('.viz-root')).getPropertyValue(name).trim();
const fmt = (v, d = 0) => v == null ? '—' : Number(v).toLocaleString('fr-FR', { maximumFractionDigits: d, minimumFractionDigits: 0 });
const fmtG = v => v == null ? '—' : (Math.abs(v) >= 1000 ? (v / 1000).toLocaleString('fr-FR', { maximumFractionDigits: 1 }) + ' Md$' : fmt(v) + ' M$');
const hhmm = t => t.slice(0, 2) + ':' + t.slice(2);

// ── Couleurs (divergent bleu ↔ gris ↔ rouge) ───────────────────────
function hexRGB(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function mix(a, b, t) { return a.map((v, i) => Math.round(v + (b[i] - v) * t)); }
function divColor(v, vmax) {
  const mid = hexRGB(cssVar('--viz-mid'));
  const pole = hexRGB(cssVar(v >= 0 ? '--viz-pos' : '--viz-neg'));
  const t = Math.sqrt(Math.min(Math.abs(v) / vmax, 1)); // racine : étale les faibles valeurs
  const [r, g, b] = mix(mid, pole, t);
  return `rgb(${r},${g},${b})`;
}

// ── Chargement ─────────────────────────────────────────────────────
async function init() {
  try {
    S.manifest = await fetchJSON('data/options/manifest.json');
  } catch (e) {
    status(`Impossible de charger les données (${e.message}). Le premier snapshot sera commité par le workflow « Options GEX snapshot ».`);
    return;
  }
  const sel = $('c-symbol');
  sel.innerHTML = S.manifest.symbols.map(s => `<option>${s}</option>`).join('');
  S.symbol = S.manifest.symbols.includes('SPX') ? 'SPX' : S.manifest.symbols[0];
  sel.value = S.symbol;
  $('pill-updated').textContent = 'maj ' + (S.manifest.updated || '').replace('T', ' ').slice(0, 16);
  await loadDays();
}

async function loadDays() {
  const dj = await fetchJSON(`data/options/${S.symbol}/days.json`);
  S.days = dj.days.slice().reverse(); // plus récent en premier
  $('c-day').innerHTML = S.days.map(d => `<option>${d}</option>`).join('');
  S.day = S.manifest.latest_day?.[S.symbol] && S.days.includes(S.manifest.latest_day[S.symbol])
    ? S.manifest.latest_day[S.symbol] : S.days[0];
  $('c-day').value = S.day;
  await loadDay();
}

async function loadDay() {
  status('Chargement…');
  const idx = await fetchJSON(`data/options/${S.symbol}/${S.day}/day.json`);
  const snaps = await Promise.all(
    idx.snapshots.map(s => fetchJSON(`data/options/${S.symbol}/${S.day}/${s.file}`))
  );
  snaps.sort((a, b) => a.time.localeCompare(b.time));
  S.snapshots = snaps;
  S.selected = snaps.length - 1;
  $('c-snap').innerHTML = snaps.map((s, i) => `<option value="${i}">${hhmm(s.time)} NY</option>`).join('');
  $('c-snap').value = S.selected;
  buildGrid();
  status(null);
  renderAll();
}

function status(msg) {
  const el = $('hm-status');
  el.style.display = msg ? '' : 'none';
  el.textContent = msg || '';
}

// ── Grille jour : strikes (desc) × snapshots ───────────────────────
function buildGrid() {
  const set = new Set();
  S.snapshots.forEach(s => s.strikes.forEach(k => set.add(k)));
  const strikes = [...set].sort((a, b) => b - a);
  const rowOf = new Map(strikes.map((k, i) => [k, i]));
  const cells = strikes.map(() => S.snapshots.map(() => null));
  S.snapshots.forEach((s, c) => {
    s.strikes.forEach((k, j) => {
      cells[rowOf.get(k)][c] = {
        net: s.call_gex[j] + s.put_gex[j],
        cg: s.call_gex[j], pg: s.put_gex[j],
        coi: s.call_oi[j], poi: s.put_oi[j],
        cv: s.call_vol[j], pv: s.put_vol[j],
      };
    });
  });
  let vmax = 0;
  const all = [];
  cells.forEach(r => r.forEach(c => { if (c) all.push(Math.abs(c.net)); }));
  all.sort((a, b) => a - b);
  vmax = all.length ? all[Math.floor(all.length * 0.98)] || all[all.length - 1] : 1;
  S.grid = { strikes, cells, vmax: vmax || 1 };
}

// ── Rendu ──────────────────────────────────────────────────────────
function renderAll() {
  renderKPIs();
  drawHeatmap();
  drawProfile();
  renderLegend();
  if (S.showTable) renderTable();
}

function renderKPIs() {
  const s = S.snapshots[S.selected];
  if (!s) return;
  $('k-spot').textContent = fmt(s.spot, 2);
  const g = $('k-gex');
  g.textContent = fmtG(s.summary.net_gex);
  g.className = 'kpi-value ' + (s.summary.net_gex >= 0 ? 'pos' : 'neg');
  $('k-flip').textContent = fmt(s.summary.flip, 0);
  $('k-cwall').textContent = fmt(s.summary.call_wall, 0);
  $('k-pwall').textContent = fmt(s.summary.put_wall, 0);
  $('k-iv').textContent = s.iv30 != null ? s.iv30.toFixed(1) + ' %' : '—';
  $('profile-time').textContent = hhmm(s.time) + ' NY · spot ' + fmt(s.spot, 2);
}

function setupCanvas(cv, cssH) {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.parentElement.clientWidth - 8;
  cv.style.height = cssH + 'px';
  cv.width = Math.round(w * dpr);
  cv.height = Math.round(cssH * dpr);
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h: cssH };
}

function drawHeatmap() {
  const cv = $('heatmap');
  const { ctx, w, h } = setupCanvas(cv, Math.min(560, Math.max(380, S.grid.strikes.length * 3)));
  const M = { l: 58, r: 14, t: 8, b: 30 };
  const pw = w - M.l - M.r, ph = h - M.t - M.b;
  const { strikes, cells, vmax } = S.grid;
  const nC = S.snapshots.length, nR = strikes.length;
  const cw = pw / nC, ch = ph / nR;
  ctx.clearRect(0, 0, w, h);

  // cellules
  for (let r = 0; r < nR; r++) {
    for (let c = 0; c < nC; c++) {
      const cell = cells[r][c];
      if (!cell) continue;
      ctx.fillStyle = divColor(cell.net, vmax);
      ctx.fillRect(M.l + c * cw + 0.5, M.t + r * ch, Math.max(cw - 1, 1), Math.max(ch - (ch > 3 ? 1 : 0), 1));
    }
  }

  // colonne sélectionnée
  if (S.selected >= 0) {
    ctx.strokeStyle = cssVar('--viz-ink2');
    ctx.lineWidth = 1;
    ctx.strokeRect(M.l + S.selected * cw + 0.5, M.t + 0.5, cw - 1, ph - 1);
  }

  const yOf = k => {
    // position dans l'échelle des strikes (lignes régulières) par interpolation
    let i = strikes.findIndex(s => s <= k);
    if (i < 0) i = nR - 1;
    if (i === 0) return M.t + ch / 2;
    const a = strikes[i - 1], b = strikes[i];
    const t = a === b ? 0 : (a - k) / (a - b);
    return M.t + (i - 1 + t) * ch + ch / 2;
  };

  // gamma flip : tirets par colonne
  ctx.strokeStyle = cssVar('--viz-ink');
  ctx.setLineDash([4, 3]);
  ctx.lineWidth = 1.5;
  S.snapshots.forEach((s, c) => {
    if (s.summary.flip == null) return;
    const y = yOf(s.summary.flip);
    ctx.beginPath();
    ctx.moveTo(M.l + c * cw + 2, y);
    ctx.lineTo(M.l + (c + 1) * cw - 2, y);
    ctx.stroke();
  });
  ctx.setLineDash([]);

  // ligne de spot (anneau de surface sous le trait pour rester lisible)
  const spotPts = S.snapshots.map((s, c) => [M.l + c * cw + cw / 2, yOf(s.spot)]);
  ctx.lineJoin = 'round';
  ctx.strokeStyle = cssVar('--viz-ring');
  ctx.lineWidth = 4;
  ctx.beginPath();
  spotPts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.stroke();
  ctx.strokeStyle = cssVar('--viz-ink');
  ctx.lineWidth = 2;
  ctx.beginPath();
  spotPts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.stroke();
  spotPts.forEach(([x, y]) => {
    ctx.fillStyle = cssVar('--viz-ink');
    ctx.strokeStyle = cssVar('--viz-ring');
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(x, y, 3.5, 0, 7); ctx.fill(); ctx.stroke();
  });

  // axes
  ctx.fillStyle = cssVar('--viz-muted');
  ctx.font = '10px system-ui, sans-serif';
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  const step = Math.max(1, Math.round(nR / Math.max(4, Math.floor(ph / 34))));
  for (let r = 0; r < nR; r += step) ctx.fillText(fmt(strikes[r]), M.l - 6, M.t + r * ch + ch / 2);
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  const cStep = Math.max(1, Math.ceil(nC / Math.floor(pw / 52)));
  for (let c = 0; c < nC; c += cStep) ctx.fillText(hhmm(S.snapshots[c].time), M.l + c * cw + cw / 2, h - M.b + 8);

  S.hmGeom = { M, cw, ch, nC, nR };
}

function drawProfile() {
  const s = S.snapshots[S.selected];
  if (!s) return;
  const cv = $('profile');
  const { ctx, w, h } = setupCanvas(cv, Math.min(460, Math.max(320, s.strikes.length * 2.4)));
  const M = { l: 58, r: 14, t: 8, b: 24 };
  const pw = w - M.l - M.r, ph = h - M.t - M.b;
  const strikes = s.strikes.slice().reverse();
  const cg = s.call_gex.slice().reverse(), pg = s.put_gex.slice().reverse();
  const nR = strikes.length, rh = ph / nR;
  const vmax = Math.max(...cg.map(Math.abs), ...pg.map(Math.abs), 1e-9);
  const x0 = M.l + pw * (vmax / (2 * vmax)); // zéro au centre
  const xOf = v => x0 + (v / vmax) * (pw / 2) * 0.96;
  ctx.clearRect(0, 0, w, h);

  // axe zéro
  ctx.strokeStyle = cssVar('--viz-grid');
  ctx.beginPath(); ctx.moveTo(x0, M.t); ctx.lineTo(x0, M.t + ph); ctx.stroke();

  const bh = Math.max(rh - (rh > 3 ? 1 : 0), 1);
  for (let r = 0; r < nR; r++) {
    const y = M.t + r * rh;
    if (cg[r] !== 0) {
      ctx.fillStyle = cssVar('--viz-pos');
      ctx.fillRect(x0, y, xOf(cg[r]) - x0, bh);
    }
    if (pg[r] !== 0) {
      ctx.fillStyle = cssVar('--viz-neg');
      ctx.fillRect(xOf(pg[r]), y, x0 - xOf(pg[r]), bh);
    }
  }

  const yOfK = k => {
    let i = strikes.findIndex(v => v <= k);
    if (i < 0) i = nR - 1;
    if (i === 0) return M.t + rh / 2;
    const a = strikes[i - 1], b = strikes[i];
    const t = a === b ? 0 : (a - k) / (a - b);
    return M.t + (i - 1 + t) * rh + rh / 2;
  };

  // spot
  ctx.strokeStyle = cssVar('--viz-ink');
  ctx.lineWidth = 2;
  const ys = yOfK(s.spot);
  ctx.beginPath(); ctx.moveTo(M.l, ys); ctx.lineTo(M.l + pw, ys); ctx.stroke();
  ctx.fillStyle = cssVar('--viz-ink');
  ctx.font = '10px system-ui, sans-serif';
  ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
  ctx.fillText('spot ' + fmt(s.spot, 1), M.l + 4, ys - 3);

  // flip
  if (s.summary.flip != null) {
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1.5;
    const yf = yOfK(s.summary.flip);
    ctx.beginPath(); ctx.moveTo(M.l, yf); ctx.lineTo(M.l + pw, yf); ctx.stroke();
    ctx.setLineDash([]);
    ctx.textBaseline = 'top';
    ctx.fillText('flip ' + fmt(s.summary.flip), M.l + 4, yf + 3);
  }

  // axe Y
  ctx.fillStyle = cssVar('--viz-muted');
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  const step = Math.max(1, Math.round(nR / Math.max(4, Math.floor(ph / 34))));
  for (let r = 0; r < nR; r += step) ctx.fillText(fmt(strikes[r]), M.l - 6, M.t + r * rh + rh / 2);
  // axe X (M$)
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  [-vmax, 0, vmax].forEach(v => ctx.fillText(fmtG(Math.round(v)), xOf(v), h - M.b + 6));
}

function renderLegend() {
  const { vmax } = S.grid;
  const stops = [];
  for (let i = 0; i <= 10; i++) {
    const v = -vmax + (2 * vmax * i) / 10;
    stops.push(`${divColor(v, vmax)} ${i * 10}%`);
  }
  $('legend-grad').style.background = `linear-gradient(90deg, ${stops.join(',')})`;
  $('legend-grad').title = `échelle : ±${fmtG(Math.round(vmax))}`;
}

function renderTable() {
  const s = S.snapshots[S.selected];
  if (!s) return;
  const rows = [];
  for (let j = s.strikes.length - 1; j >= 0; j--) {
    const net = s.call_gex[j] + s.put_gex[j];
    rows.push(`<tr><td>${fmt(s.strikes[j], 2)}</td><td>${fmt(s.call_gex[j], 1)}</td><td>${fmt(s.put_gex[j], 1)}</td><td>${fmt(net, 1)}</td><td>${fmt(s.call_oi[j])}</td><td>${fmt(s.put_oi[j])}</td><td>${fmt(s.call_vol[j])}</td><td>${fmt(s.put_vol[j])}</td></tr>`);
  }
  $('table-body').innerHTML = rows.join('');
}

// ── Interactions ───────────────────────────────────────────────────
function toggleTable() {
  S.showTable = !S.showTable;
  $('table-card').style.display = S.showTable ? '' : 'none';
  $('c-table-btn').textContent = S.showTable ? 'Masquer tableau' : 'Vue tableau';
  if (S.showTable) renderTable();
}

function exportDay() {
  if (!S.snapshots.length) return;
  const blob = new Blob([JSON.stringify({
    symbol: S.symbol, day: S.day,
    unit: 'GEX en millions USD par mouvement de 1%',
    snapshots: S.snapshots,
  }, null, 1)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `gex_${S.symbol}_${S.day}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

const tooltip = $('tooltip');
$('heatmap').addEventListener('mousemove', ev => {
  if (!S.hmGeom) return;
  const rect = ev.target.getBoundingClientRect();
  const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
  const { M, cw, ch, nC, nR } = S.hmGeom;
  const c = Math.floor((x - M.l) / cw), r = Math.floor((y - M.t) / ch);
  if (c < 0 || c >= nC || r < 0 || r >= nR || !S.grid.cells[r][c]) {
    tooltip.style.display = 'none';
    return;
  }
  const cell = S.grid.cells[r][c];
  const snap = S.snapshots[c];
  tooltip.innerHTML =
    `<b>${fmt(S.grid.strikes[r], 2)}</b> · ${hhmm(snap.time)} NY<br>` +
    `GEX net&nbsp;: <b>${fmt(cell.net, 1)} M$</b><br>` +
    `Calls&nbsp;: ${fmt(cell.cg, 1)} M$ · OI ${fmt(cell.coi)}<br>` +
    `Puts&nbsp;: ${fmt(cell.pg, 1)} M$ · OI ${fmt(cell.poi)}<br>` +
    `Spot&nbsp;: ${fmt(snap.spot, 2)}`;
  tooltip.style.display = 'block';
  const tw = tooltip.offsetWidth;
  tooltip.style.left = Math.min(ev.clientX + 14, window.innerWidth - tw - 8) + 'px';
  tooltip.style.top = (ev.clientY + 14) + 'px';
});
$('heatmap').addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
$('heatmap').addEventListener('click', ev => {
  if (!S.hmGeom) return;
  const rect = ev.target.getBoundingClientRect();
  const c = Math.floor((ev.clientX - rect.left - S.hmGeom.M.l) / S.hmGeom.cw);
  if (c >= 0 && c < S.snapshots.length) {
    S.selected = c;
    $('c-snap').value = c;
    renderAll();
  }
});

$('c-symbol').addEventListener('change', async e => { S.symbol = e.target.value; await loadDays(); });
$('c-day').addEventListener('change', async e => { S.day = e.target.value; await loadDay(); });
$('c-snap').addEventListener('change', e => { S.selected = +e.target.value; renderAll(); });
window.addEventListener('resize', () => { if (S.snapshots.length) { drawHeatmap(); drawProfile(); } });
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (S.snapshots.length) renderAll(); });

init();
