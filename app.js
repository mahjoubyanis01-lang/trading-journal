// ═══════════════════════════════════════════════════════════════
// TRADING JOURNAL — app.js
// ═══════════════════════════════════════════════════════════════

const STORE_KEY = 'tj_trades_v1';
let trades = [];
try { const s = localStorage.getItem(STORE_KEY); if (s) trades = JSON.parse(s); } catch(e){}
function save() { try { localStorage.setItem(STORE_KEY, JSON.stringify(trades)); } catch(e){} }

const fmtPct = (v, d=2) => (v*100).toFixed(d) + '%';
const fmtX   = (v, d=2) => v.toFixed(d) + 'x';
const fmtN   = (v, d=2) => v.toFixed(d);
const clrCls = v => v > 0 ? 'pos' : v < 0 ? 'neg' : '';
const el     = id => document.getElementById(id);

let currentSection = 'dashboard';

function showSection(name) {
  currentSection = name;
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tnav-btn, .bnav-btn').forEach(b => b.classList.toggle('active', b.dataset.section === name));
  el('section-' + name).classList.add('active');
  if (name === 'montecarlo') runMonteCarlo();
}

function computeStats() {
  const n = trades.length;
  if (n === 0) return null;
  const rets = trades.map(t => t.ret);

  const effDates = [];
  let lastDate = null;
  trades.forEach(t => { if (t.date) lastDate = t.date; effDates.push(lastDate); });

  const equity = [];
  let eq = 0;
  rets.forEach(r => { eq = (1+eq)*(1+r)-1; equity.push(eq); });

  const dd = [];
  let peak = 0;
  equity.forEach(e => { if (e > peak) peak = e; dd.push(peak === 0 ? Math.min(0,e) : (1+e)/(1+peak)-1); });

  const tags = rets.map(r => r > 0 ? 'WIN' : r < 0 ? 'SL' : 'BE');
  const nWin = tags.filter(t => t==='WIN').length;
  const nSL  = tags.filter(t => t==='SL').length;
  const nBE  = tags.filter(t => t==='BE').length;

  const streak = [];
  rets.forEach((r, i) => {
    const prev = i > 0 ? streak[i-1] : 0;
    if (r > 0) streak.push(prev > 0 ? prev+1 : 1);
    else if (r < 0) streak.push(prev < 0 ? prev-1 : -1);
    else streak.push(0);
  });

  const mean     = rets.reduce((a,b) => a+b, 0) / n;
  const cumul    = rets.reduce((a,b) => a+b, 0);
  const compound = equity[n-1];
  const best     = Math.max(...rets);
  const worst    = Math.min(...rets);
  const maxDD    = Math.min(...dd);
  const ddNeg    = dd.filter(d => d < 0);
  const avgDD    = ddNeg.length ? ddNeg.reduce((a,b)=>a+b,0)/ddNeg.length : 0;

  const variance = rets.reduce((a,b) => a+(b-mean)**2, 0) / Math.max(n-1,1);
  const std      = Math.sqrt(variance);
  const downVar  = rets.reduce((a,b) => a+Math.min(b,0)**2, 0) / Math.max(n-1,1);
  const downDev  = Math.sqrt(downVar);
  const volAnn   = std * Math.sqrt(252);

  const sorted = [...rets].sort((a,b)=>a-b);
  const median = n%2===0 ? (sorted[n/2-1]+sorted[n/2])/2 : sorted[Math.floor(n/2)];

  const sumPos = rets.filter(r=>r>0).reduce((a,b)=>a+b,0);
  const sumNeg = Math.abs(rets.filter(r=>r<0).reduce((a,b)=>a+b,0));
  const pf     = sumNeg > 0 ? sumPos/sumNeg : null;

  const sharpe  = std > 0 ? mean/std*Math.sqrt(252) : null;
  const sortino = downDev > 0 ? mean/downDev*Math.sqrt(252) : null;
  const calmar  = maxDD < 0 ? compound/Math.abs(maxDD) : null;

  const wrBrut = nWin / n;
  const wrNet  = (nWin+nSL) > 0 ? nWin/(nWin+nSL) : null;
  const avgWin = nWin > 0 ? rets.filter(r=>r>0).reduce((a,b)=>a+b,0)/nWin : 0;
  const avgLoss= nSL  > 0 ? Math.abs(rets.filter(r=>r<0).reduce((a,b)=>a+b,0)/nSL) : 0;
  const kelly  = (wrNet !== null && avgLoss > 0) ? wrNet - (1-wrNet)/(avgWin/avgLoss) : null;
  const cagr   = n > 0 ? (compound/n)*252 : null;

  const maxWinStreak  = Math.max(...streak.filter(s=>s>0), 0);
  const maxLossStreak = Math.abs(Math.min(...streak.filter(s=>s<0), 0));
  const curStreak     = streak[n-1] || 0;

  const wr4s  = wrNet ?? wrBrut;
  const wrPts = wr4s>0.6?25 : wr4s>0.5?18 : wr4s>0.4?10 : 0;
  const pfPts = pf!==null ? (pf>2?20:pf>1.5?14:pf>1?7:0) : 0;
  const shPts = sharpe!==null ? (sharpe>2?20:sharpe>1?14:sharpe>0?7:0) : 0;
  const ddPts = maxDD>-0.05?20:maxDD>-0.10?12:maxDD>-0.20?5:0;
  const exPts = mean>0.01?15:mean>0.005?10:mean>0?5:0;
  const score = Math.min(100, Math.max(0, wrPts+pfPts+shPts+ddPts+exPts));

  return { n, rets, equity, dd, tags, streak, effDates, mean, cumul, compound, best, worst, median,
    std, variance, downDev, volAnn, maxDD, avgDD, sumPos, sumNeg, pf, sharpe, sortino, calmar,
    wrBrut, wrNet, nWin, nSL, nBE, avgWin, avgLoss, kelly, cagr,
    maxWinStreak, maxLossStreak, curStreak, score, wrPts, pfPts, shPts, ddPts, exPts };
}

let charts = {};
function destroyChart(id) { if(charts[id]){charts[id].destroy();delete charts[id];} }

const isDark  = () => window.matchMedia('(prefers-color-scheme:dark)').matches;
const gridClr = () => isDark() ? 'rgba(255,255,255,.06)' : 'rgba(0,0,0,.05)';
const tickClr = () => isDark() ? '#555550' : '#9c9c96';
const surfClr = () => isDark() ? '#1c1c1a' : '#ffffff';
const bordClr = () => isDark() ? '#2a2a28' : '#e2e2de';
const txtClr  = () => isDark() ? '#f0f0ec' : '#111110';
const bdy     = () => isDark() ? '#a0a09a' : '#5c5c58';

const BLUE='#2563eb',GREEN='#16a34a',RED='#dc2626',AMBER='#d97706';

function baseOpts() {
  return {
    responsive:true, maintainAspectRatio:false, animation:{duration:350},
    plugins:{legend:{display:false},tooltip:{backgroundColor:surfClr(),borderColor:bordClr(),borderWidth:1,titleColor:txtClr(),bodyColor:bdy(),cornerRadius:6,padding:10}},
    scales:{x:{grid:{color:gridClr()},ticks:{color:tickClr(),font:{size:10},maxTicksLimit:12}},y:{grid:{color:gridClr()},ticks:{color:tickClr(),font:{size:10},callback:v=>v.toFixed(1)+'%'}}}
  };
}

function buildEquityChart(st) {
  destroyChart('eq');
  const ctx = el('equity-chart'); if(!ctx) return;
  charts['eq'] = new Chart(ctx, {
    type:'line',
    data:{labels:st.equity.map((_,i)=>i+1),datasets:[{data:st.equity.map(v=>+(v*100).toFixed(4)),borderColor:BLUE,borderWidth:2,fill:true,backgroundColor:isDark()?'rgba(37,99,235,.10)':'rgba(37,99,235,.05)',pointRadius:st.n>100?0:2,tension:.4}]},
    options:{...baseOpts(),plugins:{...baseOpts().plugins,tooltip:{...baseOpts().plugins.tooltip,callbacks:{title:i=>'Trade #'+i[0].label,label:i=>'Equity: '+i.raw.toFixed(2)+'%'}}}}
  });
}

function buildDDChart(st) {
  destroyChart('dd');
  const ctx = el('dd-chart'); if(!ctx) return;
  charts['dd'] = new Chart(ctx, {
    type:'line',
    data:{labels:st.dd.map((_,i)=>i+1),datasets:[{data:st.dd.map(v=>+(v*100).toFixed(4)),borderColor:RED,borderWidth:1.5,fill:true,backgroundColor:isDark()?'rgba(220,38,38,.10)':'rgba(220,38,38,.05)',pointRadius:0,tension:.3}]},
    options:{...baseOpts(),plugins:{...baseOpts().plugins,tooltip:{...baseOpts().plugins.tooltip,callbacks:{title:i=>'Trade #'+i[0].label,label:i=>'DD: '+i.raw.toFixed(2)+'%'}}}}
  });
}

function buildDistChart(st) {
  destroyChart('dist');
  const ctx = el('dist-chart'); if(!ctx) return;
  const edges=[-8,-6,-4,-2,0,2,4,6,8];
  const labels=['<-6%','-6%','-4%','-2%','0%','+2%','+4%','+6%','+8%'];
  const counts=edges.map((b,i)=>{const lo=i===0?-Infinity:edges[i-1]/100,hi=b/100;return st.rets.filter(r=>r>lo&&r<=hi).length;});
  charts['dist']=new Chart(ctx,{type:'bar',data:{labels,datasets:[{data:counts,backgroundColor:edges.map(b=>b<=0?RED:GREEN),borderRadius:3,borderSkipped:false}]},options:{...baseOpts(),scales:{x:{grid:{color:gridClr()},ticks:{color:tickClr(),font:{size:9}}},y:{grid:{color:gridClr()},ticks:{color:tickClr(),font:{size:10},callback:v=>v}}},plugins:{...baseOpts().plugins,tooltip:{...baseOpts().plugins.tooltip,callbacks:{label:i=>`${i.raw} trade${i.raw!==1?'s':''}`}}}}});
}

function buildPieChart(st) {
  destroyChart('pie');
  const ctx = el('pie-chart'); if(!ctx) return;
  charts['pie']=new Chart(ctx,{type:'doughnut',data:{labels:['WIN','SL','BE'],datasets:[{data:[st.nWin,st.nSL,st.nBE],backgroundColor:[GREEN,RED,AMBER],borderWidth:0,hoverOffset:4}]},options:{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{legend:{display:false},tooltip:{backgroundColor:surfClr(),titleColor:txtClr(),bodyColor:bdy(),borderColor:bordClr(),borderWidth:1,cornerRadius:6,padding:8}}}});
  const leg=el('pie-legend');
  if(leg){const pct=v=>st.n?Math.round(v/st.n*100):0;leg.innerHTML=[{l:'WIN',v:st.nWin,c:GREEN},{l:'SL',v:st.nSL,c:RED},{l:'BE',v:st.nBE,c:AMBER}].map(({l,v,c})=>`<div style="display:flex;align-items:center;gap:6px"><span style="width:9px;height:9px;border-radius:2px;background:${c};flex-shrink:0"></span><span style="font-size:12px;color:var(--text2)">${l} <strong style="color:var(--text)">${v}</strong> <span style="color:var(--text3)">(${pct(v)}%)</span></span></div>`).join('');}
}

function addTrade() {
  const retRaw = parseFloat(el('f-ret').value);
  const errEl  = el('add-error');
  if (isNaN(retRaw)) { errEl.style.display='inline'; return; }
  errEl.style.display='none';
  trades.push({date:el('f-date').value||'',ret:retRaw/100,link:el('f-link').value.trim(),comment:el('f-comment').value.trim(),id:Date.now()+Math.random()});
  save(); refresh();
  el('f-ret').value=''; el('f-link').value=''; el('f-comment').value='';
  el('f-ret').focus();
}

function deleteTrade(id) {
  if(!confirm('Supprimer ce trade ?')) return;
  trades=trades.filter(t=>t.id!==id); save(); refresh();
}

document.addEventListener('keydown', e => {
  if (e.key==='Enter' && document.activeElement.closest('#add-form')) addTrade();
  if (e.key==='F9') { e.preventDefault(); runMonteCarlo(); }
});

function renderTrades(st) {
  const tbody=el('trades-tbody');
  el('trades-count').textContent=`${trades.length} trade${trades.length!==1?'s':''}`;
  if(!trades.length){tbody.innerHTML='<tr><td colspan="11" class="empty">Aucun trade · Ajoutez votre premier trade ci-dessus</td></tr>';return;}
  tbody.innerHTML=[...trades].reverse().map((t,ri)=>{
    const i=trades.length-1-ri;
    const eq=st?st.equity[i]:null,ddv=st?st.dd[i]:null,stk=st?st.streak[i]:null,tag=st?st.tags[i]:null;
    const pct=(t.ret*100).toFixed(2);
    return `<tr>
      <td class="mono" style="color:var(--text3)">${i+1}</td>
      <td style="color:var(--text2);font-size:11px">${t.date||'<span style="color:var(--text3)">—</span>'}</td>
      <td class="mono ${clrCls(t.ret)}">${pct}%</td>
      <td><span style="background:${t.ret>0?'var(--green-bg)':t.ret<0?'var(--red-bg)':'var(--amber-bg)'};color:${t.ret>0?'var(--green)':t.ret<0?'var(--red)':'var(--amber)'};padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600">${t.ret>0?'+':''}${pct}%</span></td>
      <td class="mono ${eq!==null?clrCls(eq):''}">${eq!==null?fmtPct(eq):'—'}</td>
      <td class="mono ${ddv!==null&&ddv<-0.05?'neg':ddv!==null&&ddv<0?'amber':''}">${ddv!==null?fmtPct(ddv):'—'}</td>
      <td class="mono" style="color:${stk!==null&&stk>0?'var(--green)':stk!==null&&stk<0?'var(--red)':'var(--text3)'}">${stk!==null?(stk>0?'+'+stk:stk):0}</td>
      <td>${tag?`<span class="tag tag-${tag.toLowerCase()}">${tag}</span>`:'—'}</td>
      <td>${t.link?`<a href="${t.link}" target="_blank" rel="noopener" style="color:var(--blue);font-size:11px">📈</a>`:'—'}</td>
      <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;font-size:11px;color:var(--text2)">${t.comment||'—'}</td>
      <td><button class="btn btn-danger btn-sm" onclick="deleteTrade(${t.id})">×</button></td>
    </tr>`;
  }).join('');
}

function renderKPIs(st) {
  el('pill-count').textContent=`${trades.length} trade${trades.length!==1?'s':''}`;
  if(!st){['k-trades','k-compound','k-cumul','k-wr-brut','k-wr-net','k-maxdd','k-pf','k-exp'].forEach(id=>{el(id).textContent='—';el(id).className='kpi-value';});el('alerts').innerHTML='';el('score-big').textContent='0';el('score-bar').style.width='0%';el('score-badge-main').className='score-badge s3';el('score-badge-main').textContent='—/100';return;}
  const set=(id,val,cls='')=>{const e=el(id);if(!e)return;e.textContent=val;e.className='kpi-value'+(cls?' '+cls:'');};
  set('k-trades',st.n,'');
  set('k-compound',fmtPct(st.compound),clrCls(st.compound));
  set('k-cumul',fmtPct(st.cumul),clrCls(st.cumul));
  set('k-wr-brut',fmtPct(st.wrBrut),st.wrBrut>=0.5?'pos':'neg');
  set('k-wr-net',st.wrNet!==null?fmtPct(st.wrNet):'—',st.wrNet!==null?(st.wrNet>=0.5?'pos':'neg'):'');
  set('k-maxdd',fmtPct(st.maxDD),'neg');
  set('k-pf',st.pf!==null?fmtX(st.pf):'—',st.pf!==null?(st.pf>=1?'pos':'neg'):'');
  set('k-exp',fmtPct(st.mean),clrCls(st.mean));
  const score=st.score;
  el('score-big').textContent=score;
  el('score-bar').style.cssText=`width:${score}%;background:${score>=65?GREEN:score>=50?AMBER:score>=35?'#f97316':RED};height:100%;border-radius:3px;transition:width .5s ease`;
  const sClass=score>=80?'s5':score>=65?'s4':score>=50?'s3':score>=35?'s2':'s1';
  const sLabel=score>=80?'Excellent':score>=65?'Profitable':score>=50?'Correct':score>=35?'Fragile':'Non rentable';
  el('score-badge-main').className='score-badge '+sClass;
  el('score-badge-main').textContent=`${score}/100 · ${sLabel}`;
  ['wr','pf','sh','dd','ex'].forEach(k=>{const e=el('sp-'+k);if(e)e.textContent=st[k+'Pts'];});

  const alerts=[];
  const a=(cls,txt)=>alerts.push({cls,txt});
  if(st.maxDD<-0.10)a('danger',`🔴  Max Drawdown ${fmtPct(st.maxDD)} — Critique`);
  else if(st.maxDD<-0.05)a('warn',`🟡  Drawdown ${fmtPct(st.maxDD)} — Attention`);
  else a('ok',`🟢  Drawdown OK (${fmtPct(st.maxDD)})`);
  const wr=st.wrNet??st.wrBrut;
  if(wr<0.4)a('danger',`🔴  Winrate net ${fmtPct(wr)} — En danger`);
  else if(wr<0.5)a('warn',`🟡  Winrate net ${fmtPct(wr)}`);
  else a('ok',`🟢  Winrate net OK (${fmtPct(wr)})`);
  if(st.pf!==null){if(st.pf<1)a('danger',`🔴  Profit Factor ${fmtX(st.pf)} — Perdant`);else if(st.pf<1.5)a('warn',`🟡  Profit Factor ${fmtX(st.pf)}`);else a('ok',`🟢  Profit Factor OK (${fmtX(st.pf)})`);}
  if(st.sharpe!==null){if(st.sharpe<0)a('danger',`🔴  Sharpe ${fmtN(st.sharpe)}`);else if(st.sharpe<1)a('warn',`🟡  Sharpe ${fmtN(st.sharpe)}`);else a('ok',`🟢  Sharpe OK (${fmtN(st.sharpe)})`);}
  if(score<35)a('danger',`🔴  Score ${score}/100 — Non rentable`);
  else if(score<50)a('warn',`🟠  Score ${score}/100 — Fragile`);
  else a('ok',`🟢  Score ${score}/100`);
  el('alerts').innerHTML=alerts.map(x=>`<div class="alert alert-${x.cls}">${x.txt}</div>`).join('');
}

function statRow(label, value) {
  return `<div class="stat-row"><span class="stat-key">${label}</span><span class="stat-val">${value??'—'}</span></div>`;
}

function renderStats(st) {
  const ids=['stats-perf','stats-ratios','stats-wr','stats-dd'];
  if(!st){ids.forEach(id=>{el(id).innerHTML='<div class="empty">Aucune donnée</div>';});return;}
  el('stats-perf').innerHTML=[statRow('Total trades',st.n),statRow('Rendement composé',fmtPct(st.compound)),statRow('Rendement cumulé',fmtPct(st.cumul)),statRow('Rendement moyen',fmtPct(st.mean)),statRow('Médiane',fmtPct(st.median)),statRow('Meilleur trade',`<span class="pos">${fmtPct(st.best)}</span>`),statRow('Pire trade',`<span class="neg">${fmtPct(st.worst)}</span>`),statRow('Écart-type (σ)',fmtPct(st.std)),statRow('Downside deviation',fmtPct(st.downDev)),statRow('CAGR approx.',st.cagr!==null?fmtPct(st.cagr):null),statRow('Volatilité annualisée',fmtPct(st.volAnn))].join('');
  el('stats-ratios').innerHTML=[statRow('Sharpe Ratio',st.sharpe!==null?`<span class="${clrCls(st.sharpe)}">${fmtX(st.sharpe)}</span>`:null),statRow('Sortino Ratio',st.sortino!==null?`<span class="${clrCls(st.sortino)}">${fmtX(st.sortino)}</span>`:null),statRow('Calmar Ratio',st.calmar!==null?fmtX(st.calmar):null),statRow('Profit Factor',st.pf!==null?`<span class="${st.pf>=1?'pos':'neg'}">${fmtX(st.pf)}</span>`:null),statRow('Expectancy',fmtPct(st.mean)),statRow('Kelly Criterion',st.kelly!==null?fmtPct(st.kelly):null),statRow('Série max gains',`<span class="pos">+${st.maxWinStreak}</span>`),statRow('Série max pertes',`<span class="neg">-${st.maxLossStreak}</span>`),statRow('Série actuelle',`<span class="${st.curStreak>0?'pos':st.curStreak<0?'neg':''}">${st.curStreak>0?'+':''}${st.curStreak}</span>`),statRow('Recovery Factor',st.calmar!==null?fmtX(st.calmar):null)].join('');
  el('stats-wr').innerHTML=[statRow('Trades WIN',`<span class="pos">${st.nWin}</span>`),statRow('Trades SL',`<span class="neg">${st.nSL}</span>`),statRow('Trades BE',`<span style="color:var(--amber)">${st.nBE}</span>`),statRow('Winrate brut (WIN/N)',fmtPct(st.wrBrut)),statRow('Winrate net (WIN/WIN+SL)',st.wrNet!==null?`<strong>${fmtPct(st.wrNet)}</strong>`:null),statRow('SL rate',fmtPct(st.nSL/st.n)),statRow('BE rate',fmtPct(st.nBE/st.n)),statRow('Avg WIN',`<span class="pos">${fmtPct(st.avgWin)}</span>`),statRow('Avg SL',`<span class="neg">${fmtPct(-st.avgLoss)}</span>`)].join('');
  el('stats-dd').innerHTML=[statRow('Max Drawdown',`<span class="neg">${fmtPct(st.maxDD)}</span>`),statRow('Drawdown moyen',`<span class="neg">${fmtPct(st.avgDD)}</span>`),statRow('Recovery Factor',st.calmar!==null?fmtX(st.calmar):null),statRow('Nb trades en DD',st.dd.filter(d=>d<0).length)].join('');
}

const MONTHS=['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc'];
const YEARS=[2020,2021,2022,2023,2024,2025,2026,2027,2028,2029,2030];

function renderMonthly(st) {
  const tbody=el('heatmap-body');
  if(!st||!st.n){tbody.innerHTML='<tr><td colspan="14" class="empty">Aucune donnée</td></tr>';return;}
  const byYM={};
  trades.forEach((t,i)=>{const ed=st.effDates[i];if(!ed)return;const d=new Date(ed);if(isNaN(d))return;const key=`${d.getFullYear()}-${d.getMonth()}`;if(!byYM[key])byYM[key]=[];byYM[key].push(t.ret);});
  const cpd=rets=>rets.reduce((acc,r)=>(1+acc)*(1+r)-1,0);
  const hBg=v=>{if(v===null)return'transparent';if(v>=0.06)return isDark()?'#14532d':'rgba(22,163,74,.25)';if(v>=0.02)return isDark()?'#166534':'rgba(22,163,74,.12)';if(v>0)return isDark()?'#1a3020':'rgba(22,163,74,.06)';if(v<=-0.06)return isDark()?'#7f1d1d':'rgba(220,38,38,.25)';if(v<=-0.02)return isDark()?'#991b1b':'rgba(220,38,38,.12)';if(v<0)return isDark()?'#2a1010':'rgba(220,38,38,.06)';return isDark()?'var(--surface2)':'var(--surface2)';};
  const hTx=v=>{if(v===null)return'var(--text3)';return v>0?(isDark()?'#4ade80':'#15803d'):(isDark()?'#f87171':'#b91c1c');};
  let rows='';
  YEARS.forEach(yr=>{
    const annual=[];
    let row=`<tr><td class="hm-year">${yr}</td>`;
    for(let m=0;m<12;m++){const key=`${yr}-${m}`;const rets=byYM[key]||[];const val=rets.length?cpd(rets):null;if(rets.length)annual.push(...rets);row+=`<td style="background:${hBg(val)};color:${hTx(val)}">${val!==null?(val*100).toFixed(1)+'%':''}</td>`;}
    const tot=annual.length?cpd(annual):null;
    row+=`<td style="background:${hBg(tot)};color:${hTx(tot)};font-weight:700">${tot!==null?(tot*100).toFixed(1)+'%':''}</td></tr>`;
    rows+=row;
  });
  tbody.innerHTML=rows;
}

function runMonteCarlo() {
  destroyChart('mc');
  const st=computeStats();
  if(!st||st.n<5){['mc-p10','mc-med','mc-p90','mc-pct'].forEach(id=>{el(id).textContent='—';});el('mc-interp').textContent='Saisir au moins 5 trades pour lancer les simulations.';return;}
  const{n,mean:mu,std:sigma}=st;
  const SIMS=100;
  const rN=()=>{let u=0,v=0;while(!u)u=Math.random();while(!v)v=Math.random();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);};
  const results=[];
  for(let s=0;s<SIMS;s++){let eq=0;for(let i=0;i<n;i++)eq=(1+eq)*(1+mu+sigma*rN())-1;results.push(eq);}
  results.sort((a,b)=>a-b);
  const p10=results[Math.floor(SIMS*0.1)],med=results[Math.floor(SIMS*0.5)],p90=results[Math.floor(SIMS*0.9)],pct=results.filter(r=>r>0).length/SIMS;
  el('mc-p10').textContent=fmtPct(p10);el('mc-p10').className='kpi-value '+(p10>0?'pos':'neg');
  el('mc-med').textContent=fmtPct(med);el('mc-med').className='kpi-value '+(med>0?'pos':'neg');
  el('mc-p90').textContent=fmtPct(p90);el('mc-p90').className='kpi-value pos';
  el('mc-pct').textContent=Math.round(pct*100)+'%';el('mc-pct').className='kpi-value '+(pct>=0.5?'pos':'neg');
  const BINS=20,minV=results[0],maxV=results[SIMS-1],step=(maxV-minV)/BINS;
  const counts=Array(BINS).fill(0),labels=[];
  for(let i=0;i<BINS;i++){const lo=minV+i*step,hi=minV+(i+1)*step;results.forEach(r=>{if(r>=lo&&r<hi)counts[i]++;});labels.push((lo*100).toFixed(1)+'%');}
  const ctx=el('mc-chart');
  if(ctx)charts['mc']=new Chart(ctx,{type:'bar',data:{labels,datasets:[{data:counts,backgroundColor:labels.map(l=>parseFloat(l)<0?'rgba(220,38,38,.7)':'rgba(22,163,74,.7)'),borderRadius:2,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,animation:{duration:300},plugins:{legend:{display:false},tooltip:{backgroundColor:surfClr(),titleColor:txtClr(),bodyColor:bdy(),borderColor:bordClr(),borderWidth:1,cornerRadius:6,padding:8,callbacks:{title:i=>i[0].label,label:i=>`${i.raw} sim${i.raw!==1?'s':''}`}}},scales:{x:{grid:{color:gridClr()},ticks:{color:tickClr(),font:{size:9},maxRotation:45,maxTicksLimit:10}},y:{grid:{color:gridClr()},ticks:{color:tickClr(),font:{size:10}}}}}});
  let interp='';
  if(pct>=0.7)interp=`✅  Robuste — ${Math.round(pct*100)}% profitables.`;
  else if(pct>=0.5)interp=`⚠️  Correct — ${Math.round(pct*100)}% profitables, incertitude élevée.`;
  else if(pct>=0.3)interp=`🟠  Fragile — ${Math.round(pct*100)}% profitables seulement.`;
  else interp=`🔴  Non robuste — ${Math.round(pct*100)}% de simulations profitables.`;
  interp+=` P10: ${fmtPct(p10)} · Médiane: ${fmtPct(med)} · P90: ${fmtPct(p90)}. Basé sur μ=${fmtPct(mu)}, σ=${fmtPct(sigma)}, ${n} trades.`;
  el('mc-interp').textContent=interp;
}

function exportCSV(){if(!trades.length)return;const hdr='id,date,rendement_pct,link,comment\n';const rows=trades.map((t,i)=>`${i+1},${t.date||''},${(t.ret*100).toFixed(4)},"${(t.link||'').replace(/"/g,'""')}","${(t.comment||'').replace(/"/g,'""')}"`).join('\n');const blob=new Blob([hdr+rows],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`tj_${new Date().toISOString().slice(0,10)}.csv`;a.click();URL.revokeObjectURL(url);}
function importCSV(){el('csv-input').click();}
function handleCSV(e){const file=e.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=ev=>{const lines=ev.target.result.split('\n').filter(l=>l.trim());const start=lines[0].toLowerCase().includes('rendement')?1:0;let added=0;lines.slice(start).forEach(line=>{const parts=line.match(/(".*?"|[^,]+)(?=,|$)/g)?.map(p=>p.replace(/^"|"$/g,'').trim());if(!parts||parts.length<3)return;const ret=parseFloat(parts[2]);if(isNaN(ret))return;trades.push({date:parts[1]||'',ret:ret/100,link:parts[3]||'',comment:parts[4]||'',id:Date.now()+Math.random()});added++;});save();refresh();alert(`${added} trade${added!==1?'s':''} importé${added!==1?'s':''}`);};reader.readAsText(file);e.target.value='';}
function exportJSON(){const blob=new Blob([JSON.stringify({v:1,trades,exported:new Date().toISOString()},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`tj_backup_${new Date().toISOString().slice(0,10)}.json`;a.click();URL.revokeObjectURL(url);}
function importJSON(){el('json-input').click();}
function handleJSON(e){const file=e.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=ev=>{try{const data=JSON.parse(ev.target.result);if(data.trades&&Array.isArray(data.trades)){if(confirm(`Importer ${data.trades.length} trades ? Les données actuelles seront remplacées.`)){trades=data.trades;save();refresh();alert(`${trades.length} trades importés.`);}}else alert('Fichier JSON invalide.');}catch(err){alert('Erreur lecture JSON.');}};reader.readAsText(file);e.target.value='';}

function refresh(){const st=computeStats();renderKPIs(st);renderTrades(st);renderStats(st);renderMonthly(st);if(st&&st.n>0){buildEquityChart(st);buildDDChart(st);buildDistChart(st);buildPieChart(st);}else{['eq','dd','dist','pie'].forEach(id=>destroyChart(id));}}

if('serviceWorker'in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('/trading-journal/sw.js').catch(()=>{}));

refresh();
