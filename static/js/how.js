// «نحوهٔ تصمیم‌گیری»: animated pipeline, interactive screener history, money
// management, portfolio weights, TP/SL ladders and the shadow test.
import { api, n0, n2, toman, pct, price, signCls, when, hm, esc, $, $$, sym } from './core.js';

const STAGES = [
  ['universe', 'جفت مجاز', 'همهٔ ۱۲۰ بازار مجاز والکس'],
  ['data', 'دادهٔ کافی', 'کندل بستهٔ ساعت آخر و حداکثر ۱۲ ساعت بی‌معامله'],
  ['liquidity', 'نقدشوندگی', 'گردش ۲۴ساعته ≥ ۵ میلیون و ظرفیت سفارش حداقلی'],
  ['strategy', 'ستاپ استراتژی', 'حداقل یک استراتژی فعال رژیم شرطش برقرار است'],
  ['quality', 'کیفیت ≥ ۵۵', 'نسبت سود به ریسک، هم‌پوشانی، روند، حجم، نقدشوندگی'],
  ['ai', 'تأیید AI', 'مدل: ورود/رد، اطمینان ≥ ۰٫۶۵، ضریب اندازه و دلیل'],
  ['fast', 'تأیید ۱۵ دقیقه', 'EMA8>EMA21 و قیمت بالای EMA8؛ اسپرد و دفتر سفارش'],
  ['risk', 'ریسک و اندازه', 'کوچک‌ترین سقف: رژیم، سفارش، دارایی، بودجهٔ ریسک، ناخالص، نقد'],
  ['order', 'سفارش و مدیریت', 'LIMIT ده‌ثانیه‌ای، سه TP و حد ضرر پله‌ای']
];
const FLOW = ['data', 'liquidity', 'strategy', 'quality', 'ai', 'fast', 'risk', 'order'];
// Number of pipeline nodes a pair has passed (0 = rejected at the data check).
const PASSED = { data: 0, liquidity: 1, strategy: 2, quality: 3, candidate: 4 };
const COLORS = { data: '#3a3f48', liquidity: '#5b4b2a', strategy: '#3d4f6b', quality: '#5a3e6b', ai_skip: '#6b2f3a', ai_enter: '#1f6b52', executed: '#34d399', fast: '#7a5b1f', candidate: '#4a4f7a' };
const LIMIT_FA = { regime_order_cap: 'سقف ورود رژیم', hard_order_cap: 'سقف سخت سفارش', asset_cap: 'سقف ۱۰٪ هر دارایی', risk_budget: 'بودجهٔ ریسک ÷ حد ضرر', gross_room: 'ظرفیت ناخالص ۵۰٪', cash_room: 'نقد آزاد' };
const REJECT_FA = { missing_required_history: 'دادهٔ ساعتی ناکافی', too_many_empty_hours_or_last_hour_without_trade: 'ساعت آخر بی‌معامله یا ساعت‌های خالی زیاد', insufficient_recent_liquidity: 'گردش ۲۴ساعته کم', estimated_capacity_below_minimum: 'ظرفیت کمتر از حداقل سفارش', no_active_strategy_setup: 'هیچ ستاپ فعالی در این رژیم', below_quality: 'امتیاز کیفیت زیر ۵۵', spread_gate: 'اسپرد زیاد', fast_trend_not_confirmed: 'روند ۱۵ دقیقه‌ای تأیید نشد', fast_data_unavailable: 'دادهٔ ۱۵ دقیقه‌ای در دسترس نبود', missing_or_stale_quote: 'قیمت زنده نامعتبر' };

export function pageHow(root, ctx) {
  const { every, keep, safe, sName, famChip, STRAT } = ctx;
  root.innerHTML = `
  <section class="panel glow" style="margin-bottom:14px"><div class="head"><h2>جریان تصمیم از داده تا سفارش</h2><span class="sub">ذرات، جفت‌هایی‌اند که در اسکن آخر از هر مرحله عبور کرده‌اند؛ گرهٔ بنفش جایی است که AI تصمیم می‌گیرد</span>
    <div class="tools tabs-inline" id="hs"></div></div><div class="body"><div class="flow" id="flow"></div><div id="flowinfo" class="muted" style="font-size:12.5px;margin-top:8px"></div></div></section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>اسکرینر زنده و تاریخچه</h2><span class="sub" id="scanlbl"></span>
    <div class="tools"><button id="play">▶ پخش تاریخچه</button></div></div>
    <div class="body"><input type="range" id="slider" min="0" max="0" value="0" style="width:100%">
      <div class="grid g2" style="margin-top:10px"><div><div id="funnel"></div></div><div><div class="heat" id="pairs" style="grid-template-columns:repeat(auto-fill,minmax(70px,1fr))"></div>
      <div class="faint" style="font-size:11px;margin-top:6px" id="legend"></div></div></div>
      <div id="pairinfo" style="margin-top:12px"></div></div></section>
  <section class="grid g2" style="margin-bottom:14px">
    <div class="panel"><div class="head"><h2>مدیریت سرمایه: اندازهٔ هر ورود چطور ساخته می‌شود</h2></div><div class="body"><select id="allocsel" style="width:100%"></select><div id="alloc" style="margin-top:10px"></div></div></div>
    <div class="panel"><div class="head"><h2>پرتفو و وزن‌ها</h2><span class="sub">سهم هر دارایی از ارزش حساب در برابر سقف‌ها</span></div><div class="body"><div class="grid g2"><div id="donut"></div><div id="weights"></div></div><div id="riskbars" style="margin-top:10px"></div></div></div>
  </section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>نقشهٔ خروج هر موقعیت: سه TP و حد ضرر پله‌ای</h2><span class="sub">در هر TP یک‌سوم فروخته می‌شود (اگر از حداقل سفارش بیشتر باشد) و حد ضرر یک پله بالا می‌آید</span></div><div class="body grid g2" id="ladders"></div></section>
  <section class="panel"><div class="head"><h2>تست سایه و خط مبنای AI</h2><span class="sub">بدون سفارش واقعی: همهٔ نامزدها با همان برنامه روی کندل‌های ۵ دقیقه‌ای دنبال می‌شوند</span></div><div class="body" id="shadow"><div class="skeleton" style="height:60px"></div></div></section>`;

  let data = null, idx = 0, playing = null, selected = null, strat = 'all';
  let cat = STRAT();
  const chips = () => { $('#hs').innerHTML = `<button data-s="all" class="on">همه</button>` + Object.entries(cat.strategies || {}).map(([k, s]) => `<button data-s="${k}">${esc(s.fa.split(' (')[0])}</button>`).join(''); };
  chips();
  if (!Object.keys(cat.strategies || {}).length) safe(async () => { cat = await api('/api/public/strategies'); chips(); drawFlow(); });
  $('#hs').onclick = e => { const b = e.target.closest('button'); if (!b) return; strat = b.dataset.s; $$('#hs button').forEach(x => x.classList.toggle('on', x === b)); drawFlow(); };

  function scanAt(i) { return data && data.scans[i]; }
  function stageOf(sym, scan) {
    const p = (scan.pairs || {})[sym] || {};
    const dec = data.decisions.find(d => d.time === scan.time);
    const a = dec && (dec.decisions || []).find(x => x.symbol === sym);
    const alloc = data.allocations.filter(x => x.time === scan.time && x.candidate === sym);
    const gate = data.gates.filter(g => g.time === scan.time).flatMap(g => g.rejected || []).filter(r => r.symbol === sym);
    let level = PASSED[p.stage] ?? 0, color = COLORS[p.stage] || '#2a2e35', label = REJECT_FA[p.reason] || p.reason || '';
    if (p.stage === 'candidate') { color = COLORS.candidate; label = 'نامزد ارسالی به AI'; }
    if (a) { level = a.action === 'enter' ? 5 : 4; color = a.action === 'enter' ? COLORS.ai_enter : COLORS.ai_skip; label = a.action === 'enter' ? 'تأیید AI' : 'رد AI'; }
    if (level >= 5 && alloc.length) level = 6;
    if (gate.length && level >= 5 && !alloc.length) { color = COLORS.fast; label = REJECT_FA[gate[gate.length - 1].reason] || gate[gate.length - 1].reason; }
    const done = alloc.find(x => x.approved);
    if (done) { level = 8; color = COLORS.executed; label = 'اندازه‌گذاری و ارسال سفارش'; }
    else if (alloc.length) { label = 'رد در اندازه‌گذاری: ' + (alloc[alloc.length - 1].reason || ''); }
    return { p, a, alloc, gate, level, color, label };
  }
  function drawFlow() {
    const scan = scanAt(idx); const pairs = scan ? Object.keys(scan.pairs || {}) : [];
    const counts = FLOW.map((_, i) => pairs.filter(s => stageOf(s, scan).level >= i + 1 && (strat === 'all' || i < 2 || (scan.pairs[s].strategies || []).includes(strat))).length);
    const s = cat.strategies && cat.strategies[strat];
    $('#flow').innerHTML = STAGES.map(([k, t, d], i) => {
      const n = i === 0 ? 120 : counts[i - 1];
      const ai = k === 'ai';
      return `${i ? `<div class="edge ${n ? 'live' : ''}"><i></i><i></i><i></i></div>` : ''}<div class="node ${ai ? 'ai' : ''}" title="${esc(d)}"><b>${esc(t)}</b><span>${scan || i === 0 ? n0(n) : '—'}</span>${ai ? '<em>LLM</em>' : ''}</div>`;
    }).join('');
    $('#flowinfo').innerHTML = s ? `<b>${esc(s.fa)}</b>: ${esc(s.thesis)}<br><span class="faint">ورود: ${esc(s.entry)} · حد ضرر: ${esc(s.stop)} · هدف: ${esc(s.target)}</span><br><span style="color:var(--violet)">نقش AI: نامزد این استراتژی با بقیهٔ نامزدها به مدل می‌رود؛ مدل با دیدن کیفیت، هم‌پوشانی، نقدشوندگی و پرتفو تصمیم ورود، اولویت و ضریب اندازه را می‌گیرد.</span>`
      : 'هر مرحله را با نشانگر ببینید. شمارها از اسکن انتخاب‌شده در اسلایدر هستند.';
  }
  function drawScan() {
    const scan = scanAt(idx);
    if (!scan) { $('#funnel').innerHTML = '<div class="empty">پس از اولین اسکن نسخهٔ جدید، جزئیات هر جفت اینجا نمایش داده می‌شود.</div>'; drawFlow(); return; }
    $('#scanlbl').textContent = `اسکن ${when(scan.time)} · رژیم ${scan.regime ? scan.regime.fa : '—'} · ${idx + 1} از ${data.scans.length}`;
    const pairs = Object.keys(scan.pairs || {});
    const st = pairs.map(s => [s, stageOf(s, scan)]);
    const rows = [['جفت‌های بررسی‌شده', st.length], ['دادهٔ کافی', st.filter(x => x[1].level >= 1).length], ['نقدشونده', st.filter(x => x[1].level >= 2).length],
      ['ستاپ استراتژی', st.filter(x => x[1].level >= 3).length], ['کیفیت ≥ ۵۵', st.filter(x => x[1].level >= 4).length], ['تأیید AI', st.filter(x => x[1].level >= 5).length], ['سفارش', st.filter(x => x[1].level >= 8).length]];
    const max = rows[0][1] || 1;
    $('#funnel').innerHTML = rows.map(([t, n], i) => `<div style="display:grid;grid-template-columns:110px 1fr 40px;gap:8px;align-items:center;margin:4px 0;font-size:12.5px"><span>${t}</span>
      <div style="height:16px;background:#1a1d22;border-radius:6px;overflow:hidden"><i style="display:block;height:100%;width:${n / max * 100}%;background:${['#565c66', '#6b7280', '#a07f3c', '#5f7fb3', '#8b6bb3', '#b49cff', '#34d399'][i]};transition:width .8s"></i></div><b>${n0(n)}</b></div>`).join('');
    $('#pairs').innerHTML = st.sort((a, b) => b[1].level - a[1].level).map(([s, x]) => `<div class="tile ${s === selected ? 'cand' : ''}" data-s="${s}" style="background:${x.color};padding:5px 6px"><b style="font-size:10.5px">${esc(s.replace(/(TMN|USDT)$/, ''))}<small class="faint">/${s.endsWith('USDT') ? 'USDT' : 'TMN'}</small></b><span style="font-size:10px">${x.p.quality !== undefined ? 'Q ' + n0(x.p.quality) : '&nbsp;'}</span></div>`).join('');
    $('#legend').innerHTML = [['data', 'داده'], ['liquidity', 'نقدشوندگی'], ['strategy', 'بدون ستاپ'], ['quality', 'زیر حد کیفیت'], ['candidate', 'نامزد AI'], ['ai_skip', 'رد AI'], ['fast', 'رد اجرایی/۱۵ دقیقه'], ['ai_enter', 'تأیید AI'], ['executed', 'سفارش']].map(([k, t]) => `<span style="display:inline-flex;align-items:center;gap:4px;margin-left:10px"><i style="width:10px;height:10px;border-radius:3px;background:${COLORS[k]}"></i>${t}</span>`).join('');
    drawFlow(); if (selected) info(selected);
  }
  function info(s) {
    const scan = scanAt(idx); if (!scan) return; selected = s; const x = stageOf(s, scan); const p = x.p;
    const cand = (scan.top || []).find(c => c.symbol === s);
    const al = x.alloc[x.alloc.length - 1];
    $('#pairinfo').innerHTML = `<div class="decision"><div class="meta"><b class="mono" style="font-size:14px">${esc(s)}</b><span class="chip">${esc(x.label || 'بررسی شد')}</span>${p.strategy ? famChip(p.strategy) + ' ' + esc(sName(p.strategy)) : ''}${p.quality !== undefined ? `<span class="chip y">کیفیت ${n0(p.quality)}</span>` : ''}</div>
      <div class="grid g3" style="margin-top:8px;font-size:12.5px">
        <div><div class="muted">اسکرینر</div>گردش ۲۴س: ${n2(p.turnover_m)} میلیون · بازده ۲۴س: ${n2((p.r24_bps || 0) / 100)}٪ · ساعت خالی: ${n0(p.missing_hours || 0)}<br>${(p.strategies || []).length ? 'استراتژی‌ها: ' + p.strategies.map(sName).join('، ') : esc(REJECT_FA[p.reason] || '')}</div>
        <div><div class="muted">تصمیم AI</div>${x.a ? `${x.a.action === 'enter' ? '<span class="pos">ورود</span>' : '<span class="neg">رد</span>'} · اطمینان ${n2(x.a.confidence)} · اندازه ${n2(x.a.size)}<br>${esc(x.a.reason)}${x.a.size_reason ? '<br><span style="color:var(--violet)">اندازه: ' + esc(x.a.size_reason) + '</span>' : ''}` : '<span class="faint">به مدل نرسید</span>'}</div>
        <div><div class="muted">برنامهٔ معامله</div>${cand && cand.plan ? `ورود مرجع ${price(cand.plan.entry_ref_tmn)} · حد ضرر ${pct(cand.plan.stop_fraction * 100, 1)} (${price(cand.plan.stop_price_tmn)})<br>R/R ${n2(cand.plan.reward_risk)} · هدف ساختاری ${price(cand.plan.target_price_tmn)}` : '—'}${al ? `<br>اندازه: <b>${toman(al.budget_tmn)}</b> (${esc(LIMIT_FA[al.sizing && al.sizing.binding_limit] || '')})${al.approved ? '' : ' · رد: ' + esc(al.reason)}` : ''}</div>
      </div>${x.gate.length ? `<div class="faint" style="font-size:12px;margin-top:6px">رد اجرایی: ${x.gate.map(g => esc(REJECT_FA[g.reason] || g.reason)).join('، ')}</div>` : ''}</div>`;
    $$('#pairs .tile').forEach(t => t.classList.toggle('cand', t.dataset.s === s));
  }
  $('#pairs').onclick = e => { const t = e.target.closest('.tile'); if (t) info(t.dataset.s); };
  $('#slider').oninput = e => { idx = +e.target.value; drawScan(); };
  $('#play').onclick = () => {
    if (playing) { clearInterval(playing); playing = null; $('#play').textContent = '▶ پخش تاریخچه'; return; }
    idx = 0; $('#play').textContent = '❚❚ توقف';
    playing = setInterval(() => { if (!data || idx >= data.scans.length - 1) { clearInterval(playing); playing = null; $('#play').textContent = '▶ پخش تاریخچه'; return; } idx++; $('#slider').value = idx; drawScan(); }, 1400);
  };
  keep({ destroy: () => playing && clearInterval(playing) });

  function drawAlloc() {
    const list = data.allocations.slice().reverse();
    if (!list.length) { $('#alloc').innerHTML = '<div class="empty">هنوز تخصیصی با جزئیات اندازه ثبت نشده است.</div>'; return; }
    const sel = $('#allocsel');
    if (!sel.options.length) {
      sel.innerHTML = list.map((a, i) => `<option value="${i}">${hm(a.observed_at || a.time)} · ${esc(a.candidate)} · ${a.approved ? 'تأیید' : 'رد: ' + esc(a.reason)}</option>`).join('');
      sel.onchange = drawAlloc;
    }
    const a = list[+sel.value || 0]; const z = a.sizing;
    if (!z) { $('#alloc').innerHTML = '<div class="faint">این تخصیص پیش از ثبت جزئیات اندازه انجام شده است.</div>'; return; }
    const keys = Object.keys(LIMIT_FA); const max = Math.max(...keys.map(k => +z[k] || 0), 1);
    $('#alloc').innerHTML = `<div class="muted" style="font-size:12px;margin-bottom:6px">ارزش حساب ${toman(z.equity)} · حد ضرر ${pct(z.stop_fraction * 100, 1)} · ریسک مجاز ${pct(z.risk_fraction * 100, 2)} از حساب</div>
      ${keys.map(k => `<div style="display:grid;grid-template-columns:150px 1fr 110px;gap:8px;align-items:center;margin:5px 0;font-size:12.5px"><span>${LIMIT_FA[k]}</span>
        <div style="height:14px;background:#1a1d22;border-radius:6px;overflow:hidden"><i class="grow" style="display:block;height:100%;width:${(+z[k]) / max * 100}%;background:${k === z.binding_limit ? 'var(--accent)' : '#46505e'}"></i></div><span class="${k === z.binding_limit ? 'warn' : 'faint'}">${toman(z[k])}</span></div>`).join('')}
      <div style="margin-top:10px;font-size:13px">کوچک‌ترین سقف: <b class="warn">${esc(LIMIT_FA[z.binding_limit])}</b> × ضریب AI <b style="color:var(--violet)">${n2(z.ai_size)}</b> × ذخیرهٔ کارمزد ۰٫۹۹ = <b>${toman(z.budget)}</b></div>
      <div class="decision" style="margin-top:8px"><div class="meta"><span class="chip" style="color:var(--violet);border-color:#4d3f7a">توضیح مدل (Gen AI)</span>${a.quality ? `<span class="chip y">کیفیت ${n0(a.quality)}</span>` : ''}</div>
      <div class="view">${esc(a.ai_size_reason || a.ai_reason || 'مدل برای این تخصیص توضیح اندازه ثبت نکرده است.')}</div></div>`;
  }
  function drawPortfolio() {
    const snap = data.snapshot || {}; const lim = data.limits || {};
    const hold = (snap.holdings || []).filter(h => h.asset !== 'TMN');
    const cash = +snap.cash_tmn || 0; const vals = hold.map(h => [h.asset, +(h.value_tmn || h.basis || 0)]);
    const eq = cash + vals.reduce((a, b) => a + b[1], 0) || 1;
    const slices = [['نقد تومان', cash, '#5b6470'], ...vals.map((v, i) => [v[0], v[1], ['#f5c343', '#34d399', '#b49cff', '#7aa7ff', '#5eead4'][i % 5]])];
    let acc = 0; const R = 54, C = 2 * Math.PI * R;
    $('#donut').innerHTML = `<svg viewBox="0 0 140 140" style="width:100%;max-width:200px"><g transform="rotate(-90 70 70)">${slices.map(([n, v, c]) => { const f = v / eq; const seg = `<circle cx="70" cy="70" r="${R}" fill="none" stroke="${c}" stroke-width="18" stroke-dasharray="${f * C} ${C}" stroke-dashoffset="${-acc * C}"><animate attributeName="stroke-dasharray" from="0 ${C}" to="${f * C} ${C}" dur="1s" fill="freeze"/></circle>`; acc += f; return seg; }).join('')}</g>
      <text x="70" y="66" text-anchor="middle" fill="#f1f3f5" font-size="11">ارزش حساب</text><text x="70" y="82" text-anchor="middle" fill="#f5c343" font-size="11">${n0(eq)}</text></svg>
      ${slices.map(([n, v, c]) => `<div style="font-size:12px"><i style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${c}"></i> ${esc(n)}: ${pct(v / eq * 100, 1)}</div>`).join('')}`;
    const cap = +(lim.max_asset_fraction || 0.1) * 100, gcap = +(lim.max_gross_fraction || 0.5) * 100;
    const gross = vals.reduce((a, b) => a + b[1], 0) / eq * 100;
    $('#weights').innerHTML = vals.map(([n, v]) => bar(n + ' (وزن)', v / eq * 100, cap)).join('') + bar('ناخالص کل', gross, gcap) +
      `<div class="faint" style="font-size:11.5px;margin-top:6px">هر دارایی حداکثر ${n0(cap)}٪ و مجموع دارایی‌ها حداکثر ${n0(gcap)}٪ ارزش حساب. بقیه نقد می‌ماند تا هیچ‌گاه با کل سرمایه وارد نشویم.</div>`;
    const pos = data.positions || {};
    const risk = hold.map(h => { const m = pos[h.asset] || {}; const v = +(h.value_tmn || h.basis); const floor = m.sl_floor ? +m.sl_floor * (+h.qty) : null; const trail = m.peak_unit && m.stop ? +m.peak_unit * (1 - +m.stop) * (+h.qty) : null; const stopValue = Math.max(floor || 0, trail || 0); return [h.asset, Math.max(0, v - stopValue)]; });
    const openRisk = risk.reduce((a, b) => a + b[1], 0) / eq * 100;
    $('#riskbars').innerHTML = bar('ریسک باز تا حد ضرر', openRisk, +(lim.max_open_risk_fraction || 0.016) * 100) +
      `<div class="faint" style="font-size:11.5px">ریسک باز = مجموع زیان ممکن تا حد ضرر فعلی هر موقعیت. سقف زیان روزانه ${pct((lim.max_daily_loss_fraction || 0.02) * 100, 0)} و افت از قله ${pct((lim.max_drawdown_fraction || 0.05) * 100, 0)}؛ عبور از هرکدام ورود جدید را می‌بندد و خروج‌ها را فعال می‌کند.</div>`;
  }
  function bar(label, value, cap) {
    const w = Math.min(100, value / (cap || 1) * 100);
    return `<div style="margin:6px 0;font-size:12.5px"><div style="display:flex;justify-content:space-between"><span>${esc(label)}</span><span class="${value > cap ? 'neg' : 'faint'}">${pct(value, 2)} از سقف ${pct(cap, 1)}</span></div>
      <div style="height:9px;background:#1a1d22;border-radius:6px;overflow:hidden"><i class="grow" style="display:block;height:100%;width:${w}%;background:${w > 85 ? 'var(--red)' : 'var(--green)'}"></i></div></div>`;
  }
  function drawLadders() {
    const pos = data.positions || {}; const snap = data.snapshot || {};
    const items = Object.entries(pos);
    if (!items.length) { $('#ladders').innerHTML = '<div class="empty">موقعیت بازی وجود ندارد.</div>'; return; }
    $('#ladders').innerHTML = items.map(([asset, m]) => {
      const h = (snap.holdings || []).find(x => x.asset === asset) || {}; const basis = m.basis_unit ? +m.basis_unit : (+h.basis / +h.qty);
      const now = h.value_tmn ? +h.value_tmn / +h.qty : basis; const tps = (m.tp || []).map(Number);
      const trail = m.peak_unit && m.stop ? +m.peak_unit * (1 - +m.stop) : null; const floor = m.sl_floor ? +m.sl_floor : null; const sl = Math.max(trail || 0, floor || 0);
      const levels = [['TP3', tps[2], '#34d399'], ['TP2', tps[1], '#34d399'], ['TP1', tps[0], '#34d399'], ['قیمت فعلی', now, '#f5c343'], ['ورود', basis, '#98a0ab'], ['حد ضرر فعال', sl, '#fb7185']].filter(x => x[1]);
      const hi = Math.max(...levels.map(x => x[1])), lo = Math.min(...levels.map(x => x[1])); const Y = v => 12 + (hi - v) / ((hi - lo) || 1) * 176;
      const stage = +m.tp_stage || 0;
      return `<div><div style="font-weight:700">${sym(m.symbol)} ${famChip(m.strategy)} <span class="chip">مرحله ${n0(stage)} از ۳</span></div>
        <svg viewBox="0 0 320 200" style="width:100%;height:210px">${levels.map(([n, v, c], i) => `<line x1="20" x2="250" y1="${Y(v)}" y2="${Y(v)}" stroke="${c}" stroke-dasharray="${n === 'قیمت فعلی' ? '0' : '5 4'}" stroke-width="${n === 'قیمت فعلی' ? 2 : 1.2}"><animate attributeName="x2" from="20" to="250" dur="${0.6 + i * 0.15}s" fill="freeze"/></line>
          <text x="256" y="${Y(v) + 4}" fill="${c}" font-size="10">${n} ${price(v)}</text>${n.startsWith('TP') ? `<text x="24" y="${Y(v) - 3}" fill="${stage >= +n[2] ? '#34d399' : '#98a0ab'}" font-size="9">${stage >= +n[2] ? '✓ فروخته/پله شد' : 'فروش ۱/۳'}</text>` : ''}`).join('')}
          <circle cx="140" cy="${Y(now)}" r="5" fill="#f5c343"><animate attributeName="r" values="4;8;4" dur="1.6s" repeatCount="indefinite"/></circle></svg>
        <div class="faint" style="font-size:11.5px">مقدار اولیه ${n2(m.initial_qty)} · پله‌ها: TP1 → حد ضرر به سربه‌سر، TP2 → حد ضرر به TP1، TP3 → خروج کامل. حد ضرر شناور ${pct(+m.stop * 100, 1)} زیر اوج همیشه فعال است.</div></div>`;
    }).join('');
  }
  async function drawShadow() {
    const d = await safe(() => api('/api/public/shadow'), $('#shadow')); if (!d) return;
    const s = d.summary || {}; const card = (t, x, c) => `<div class="panel kpi"><div class="label">${t}</div><div class="value ${signCls(x && x.mean_return_percent)}">${x && x.count ? pct(x.mean_return_percent, 2) : '—'}</div><div class="note">${x ? n0(x.count) + ' نامزد · برد ' + (x.win_rate !== null && x.win_rate !== undefined ? pct(x.win_rate * 100, 0) : '—') : ''}</div></div>`;
    $('#shadow').innerHTML = `<div class="grid g3" style="margin-bottom:10px">${card('تأییدشده توسط AI', s.ai_enter, '')}${card('ردشده توسط AI', s.ai_skip, '')}${card('همهٔ نامزدهای قواعد', s.all_rules, '')}</div>
      <div class="faint" style="font-size:11.5px;margin-bottom:8px">${esc(d.method)} اختلاف «تأیید» و «رد» اثر واقعی فیلتر AI را نشان می‌دهد؛ نمونه کوچک است و با گذشت زمان کامل‌تر می‌شود.</div>
      ${d.rows.length ? `<div class="table-wrap scroll" style="max-height:320px"><table><thead><tr><th>زمان</th><th>جفت</th><th>استراتژی</th><th>کیفیت</th><th>AI</th><th>نتیجهٔ سایه</th><th>پایان</th><th>دلیل AI</th></tr></thead><tbody>${d.rows.map(r => `<tr><td>${when(r.time)}</td><td>${sym(r.symbol)}</td><td>${esc(sName(r.strategy))}</td><td>${n0(r.quality)}</td><td>${r.ai_action === 'enter' ? '<span class="pos">ورود</span>' : r.ai_action === 'skip' ? '<span class="neg">رد</span>' : '<span class="faint">بدون درخواست</span>'}</td><td class="${signCls(r.return_percent)}">${pct(r.return_percent)}</td><td>${esc({ tp3: 'TP3', stop: 'حد ضرر', stepped_stop: 'حد ضرر پله‌ای', time_exit: 'پایان زمان', open_marked: 'هنوز باز' }[r.reason] || r.reason)} · مرحله ${n0(r.tp_stage)}</td><td style="font-size:11.5px;max-width:260px">${esc(r.ai_reason || '')}</td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">هنوز نامزدی برای تست سایه ثبت نشده است.</div>'}`;
  }
  every(15000, async () => {
    const d = await safe(() => api('/api/public/explain'), $('#funnel')); if (!d) return;
    const atEnd = !data || idx >= data.scans.length - 1; data = d;
    $('#slider').max = Math.max(0, d.scans.length - 1); if (atEnd && !playing) { idx = Math.max(0, d.scans.length - 1); $('#slider').value = idx; }
    drawScan(); drawAlloc(); drawPortfolio(); drawLadders();
  });
  every(60000, drawShadow);
}
