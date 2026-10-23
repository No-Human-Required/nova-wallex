import { S, api, loadSession, n0, n2, n4, toman, pct, price, signCls, when, clock, hm, ago, esc, h, $, $$, sym,
  STATUS_FA, REASON_FA, PHASE_FA, SIDE_FA, download, tween, wxButton } from './core.js';
import { LineChart, CandleChart } from './charts.js';
import { background, Radar, ART } from './fx.js';
import { pageHow } from './how.js';
import { pageStudio } from './studio.js';
import { pageSettings } from './settings.js';

const PAGES = [
  ['live', 'اجرای واقعی', '◉'], ['how', 'نحوهٔ تصمیم‌گیری', '⟲'], ['journal', 'ژورنال معاملات', '☰'], ['ai', 'تصمیم‌های AI', '✦'],
  ['strategies', 'استراتژی‌ها', '◇'], ['market', 'بازار زنده', '▦'], ['challenge', 'خواسته‌های چالش', '✓'],
  ['studio', 'استودیوی استراتژی', '✎'], ['research', 'بک‌تست و پژوهش', '∿'], ['settings', 'تنظیمات و کلیدها', '⚿'], ['operator', 'کنترل اپراتور', '⚙']
];
const CTX = { timers: [], disposables: [], live: null, journal: null };
const STRAT = () => (CTX.live && CTX.live.strategies) || { strategies: {}, regimes: {} };
const sName = k => (STRAT().strategies[k] || {}).fa || ({ legacy_trend6: 'روند ۶ساعته (نسخهٔ قبلی)', native_protection: 'محافظ صرافی' }[k] || k || '—');
const famChip = k => { const f = (STRAT().strategies[k] || {}).family; return f ? `<span class="chip ${f === 'smart_money' ? 'smc' : 'ind'}">${f === 'smart_money' ? 'SMC' : 'اندیکاتور'}</span>` : ''; };
const reason = r => REASON_FA[r] || sName(r) || r || '—';

function every(ms, fn) { fn(); const id = setInterval(() => { if (!document.hidden) fn(); }, ms); CTX.timers.push(id); }
function dispose() { CTX.timers.forEach(clearInterval); CTX.timers = []; CTX.disposables.forEach(d => d.destroy && d.destroy()); CTX.disposables = []; }
const keep = x => (CTX.disposables.push(x), x);
async function safe(fn, node) { try { return await fn(); } catch (e) { if (node) node.innerHTML = `<div class="notice red">${esc(e.message)}</div>`; return null; } }

// ------------------------------------------------------------------ shell
function shell() {
  document.body.innerHTML = `<canvas id="fx" aria-hidden="true"></canvas>
  <div class="shell"><aside class="side"><div class="brand"><img src="/static/nova-mark.png" alt=""><div><b>NOVA</b><small>WALLEX ALGORITHMIC ENGINE</small></div></div>
  <nav class="tabs">${PAGES.map(([k, t, i]) => `<a href="#${k}" data-p="${k}"><span class="ico">${i}</span>${t}${k === 'operator' ? '<span class="badge hidden" id="opbadge">!</span>' : ''}</a>`).join('')}</nav>
  <div class="side-foot"><div id="ver"></div><div>فقط اسپات · بدون اهرم · حساب اختصاصی</div></div></aside>
  <main><header class="top"><h1 id="title"></h1><span class="pill" id="engpill"><span class="dot"></span><span>…</span></span>
  <span class="pill" title="پایان مسابقه">⏳ <span class="countdown" id="cd">—</span></span><span class="spacer"></span>
  <span class="pill" id="who">عمومی (فقط‌خواندنی)</span></header><div id="page"></div></main></div>`;
  background($('#fx'));
}

function route() {
  dispose();
  const key = (location.hash || '#live').slice(1);
  const page = PAGES.find(p => p[0] === key) ? key : 'live';
  $$('nav.tabs a').forEach(a => a.classList.toggle('active', a.dataset.p === page));
  $('#title').textContent = PAGES.find(p => p[0] === page)[1];
  const root = $('#page'); root.innerHTML = ''; root.className = 'fade-in';
  ({ live: pageLive, how: r => pageHow(r, { every, keep, safe, sName, famChip, STRAT }), journal: pageJournal, ai: pageAI, strategies: pageStrategies, market: pageMarket,
     challenge: pageChallenge, research: pageResearch, operator: pageOperator,
     studio: r => pageStudio(r, { every, keep, safe }), settings: r => pageSettings(r, { every, keep, safe }) })[page](root);
}

async function pollLive() {
  const d = await api('/api/public/live');
  CTX.live = d;
  const e = d.engine || {}; const running = e.desired === 'running' && e.status !== 'blocked' && (e.heartbeat_age ?? 99) < 30;
  const pill = $('#engpill');
  pill.innerHTML = `<span class="dot ${running ? 'on' : e.status === 'blocked' || e.last_error ? 'off' : 'warn'}"></span><span>موتور: ${esc(STATUS_FA[e.status] || e.status || '—')}</span>`;
  $('#ver').textContent = 'نسخهٔ ' + (d.version || '') + ' · ' + (d.installed_source_sha256 || '').slice(0, 10);
  CTX.end = Date.parse(d.contest_end_utc) / 1000;
  $('#opbadge') && $('#opbadge').classList.toggle('hidden', !(d.run && (d.run.upgrade_required || d.run.settings_upgrade_pending)));
  return d;
}
function countdown() {
  const node = $('#cd'); if (!node || !CTX.end) return;
  let s = Math.max(0, Math.floor(CTX.end - Date.now() / 1000));
  const d = Math.floor(s / 86400); s %= 86400; const hh = Math.floor(s / 3600); s %= 3600; const mm = Math.floor(s / 60); const ss = s % 60;
  node.textContent = `${d}d ${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}

// ------------------------------------------------------------------ live
function pageLive(root) {
  root.innerHTML = `
  <div id="upgradeNote"></div>
  <section class="panel glow" style="margin-bottom:14px"><div class="hero">
    <div><div class="muted">ارزش لحظه‌ای حساب مسابقه</div><div class="big" id="eq">—</div><div class="muted" id="eqnote"></div></div>
    <div><div class="muted">سود / زیان نسبت به ۵ میلیون</div><div class="delta" id="pnl">—</div></div>
    <div><div class="muted">سود محقق‌شده</div><div class="delta" id="real">—</div></div>
    <div><div class="muted">پایان مسابقه</div><div id="endfa" class="warn"></div></div>
  </div></section>
  <section class="grid g6" style="margin-bottom:14px" id="kpis"></section>
  <section class="grid g3" style="margin-bottom:14px">
    <div class="panel span2"><div class="head"><h2>منحنی ارزش حساب</h2><span class="sub">بازسازی از دفتر سفارش‌ها × کندل‌های عمومی والکس؛ مستقل از روشن بودن موتور</span>
      <div class="tools tabs-inline" id="eqres"><button data-r="auto" class="on">خودکار</button><button data-r="1">۱ دقیقه</button><button data-r="5">۵ دقیقه</button><button data-r="15">۱۵ دقیقه</button></div></div>
      <div class="body"><canvas class="chart tall" id="eqchart"></canvas><div class="faint" id="eqmeta" style="font-size:11px"></div></div></div>
    <div class="panel"><div class="head"><h2>اسکنر بازار</h2><span class="sub" id="scanmeta"></span></div><div class="body"><canvas class="radar" id="radar"></canvas><div id="regime"></div></div></div>
  </section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>موقعیت‌های باز</h2><span class="sub">قیمت دقیقه‌ای زنده، ورود، حد ضرر شناور و هدف</span></div><div class="body" id="positions"><div class="skeleton" style="height:120px"></div></div></section>
  <section class="grid g2" style="margin-bottom:14px">
    <div class="panel"><div class="head"><h2>آخرین تصمیم موتور AI</h2><a class="tools" href="#ai">همهٔ تصمیم‌ها ←</a></div><div class="body" id="lastai"></div></div>
    <div class="panel"><div class="head"><h2>نامزدهای این ساعت</h2><span class="sub">ستاپ‌های معتبر پیش از تأیید AI</span></div><div class="body table-wrap" id="cands"></div></div>
  </section>
  <section class="grid g2">
    <div class="panel"><div class="head"><h2>معاملات اخیر</h2><a class="tools" href="#journal">ژورنال کامل ←</a></div><div class="body table-wrap" id="recent"></div></div>
    <div class="panel"><div class="head"><h2>رویدادهای موتور</h2></div><div class="body feed scroll" id="feed" style="max-height:340px"></div></div>
  </section>`;
  const eq = keep(new LineChart($('#eqchart'), { baseline: 5000000, baselineLabel: 'سرمایهٔ اولیه ۵٬۰۰۰٬۰۰۰', fmt: n0, relative: true }));
  const radar = keep(new Radar($('#radar')));
  let res = 'auto';
  $('#eqres').onclick = e => { const b = e.target.closest('button'); if (!b) return; res = b.dataset.r; $$('#eqres button').forEach(x => x.classList.toggle('on', x === b)); loadEq(); };
  async function loadEq() {
    const d = await safe(() => api('/api/public/equity?resolution=' + res), $('#eqmeta'));
    if (!d) return;
    eq.set(d.points.map(p => [p[0], p[1]]), { markers: d.fills, baseline: d.capital_tmn || 5000000 });
    $('#eqmeta').textContent = `${n0(d.points.length)} نقطه · تفکیک ${d.resolution} دقیقه · ${d.method === undefined ? '' : 'ارزش‌گذاری با Close کندل؛ در شکاف کندل آخرین قیمت حفظ می‌شود'}`;
  }
  every(30000, loadEq);
  const charts = {};
  every(5000, async () => {
    const d = await safe(pollLive); if (!d) return;
    const s = d.snapshot || {}; const run = d.run;
    $('#endfa').textContent = d.contest_end_fa || '';
    $('#upgradeNote').innerHTML = run && run.upgrade_required ? `<div class="notice" style="margin-bottom:14px">نسخهٔ جدید موتور نصب شده است. اجرای فعلی تا تأیید ارتقا در «کنترل اپراتور» متوقف می‌ماند؛ دفتر، موقعیت‌ها و سفارش‌ها حفظ شده‌اند. <a href="#operator">بررسی و ارتقا ←</a></div>` : (d.engine.last_error ? `<div class="notice red" style="margin-bottom:14px">خطای موتور: ${esc(d.engine.last_error)}</div>` : '');
    const capital = +(run && run.limits && run.limits.capital_tmn) || 5000000;
    let equity = s.equity_tmn !== null && s.equity_tmn !== undefined ? +s.equity_tmn : null;
    if (equity === null) { equity = +s.cash_tmn || capital; for (const x of s.holdings || []) equity += +(x.value_tmn || x.basis || 0); }
    tween($('#eq'), equity, v => toman(v));
    $('#eqnote').textContent = s.at ? 'آخرین تصویر حساب: ' + ago(s.at) + (s.equity_tmn === null ? ' (ارزش‌گذاری تقریبی)' : '') : '';
    const p = equity - capital; $('#pnl').innerHTML = `<span class="${signCls(p)}">${toman(p)} (${pct(p / capital * 100, 3)})</span>`;
    $('#real').innerHTML = `<span class="${signCls(s.realized_pnl_tmn)}">${toman(s.realized_pnl_tmn)}</span>`;
    const fees = Object.entries(s.fees_by_asset || {}).map(([a, v]) => n4(v) + ' ' + a).join(' + ') || '۰';
    const k = [
      ['وضعیت موتور', STATUS_FA[d.engine.status] || d.engine.status, d.engine.heartbeat_age !== null ? 'ضربان ' + n0(d.engine.heartbeat_age) + ' ثانیه' : ''],
      ['رژیم بازار', d.latest_scan && d.latest_scan.regime ? d.latest_scan.regime.fa : '—', d.latest_scan && d.latest_scan.regime ? 'پهنا ' + pct(d.latest_scan.regime.breadth * 100, 0) : ''],
      ['نقد تومانی', toman(s.cash_tmn), 'گزارش صرافی: ' + toman(s.reported_cash_tmn)],
      ['حداکثر افت', n4(s.max_drawdown_percent) + '٪', 'سقف ' + pct((run && run.limits ? run.limits.max_drawdown_fraction : 0.05) * 100, 0)],
      ['تعداد پرشدن', n0(s.fill_count), 'کارمزد: ' + fees],
      ['فراخوانی AI', n0(d.ai_calls_used) + ' / ' + n0(run && run.limits ? run.limits.ai_max_calls : 0), run ? (run.policy === 'adaptive_ai' ? 'سیاست تطبیقی SMC/اندیکاتور' : 'سیاست قبلی: ' + (run.policy || '')) : '']
    ];
    $('#kpis').innerHTML = k.map(([a, b, c]) => `<div class="panel kpi"><div class="label">${a}</div><div class="value">${esc(b)}</div><div class="note">${esc(c)}</div></div>`).join('');
    // regime + radar
    const sc = d.latest_scan;
    radar.set(sc ? sc.top : [], 120);
    $('#scanmeta').textContent = sc ? 'اسکن ساعت ' + hm(sc.time) : '';
    if (sc && sc.regime) {
      const r = sc.regime;
      $('#regime').innerHTML = `<div class="row" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px"><span class="chip y">${esc(r.fa)}</span><span class="chip">BTC ۲۴س: ${pct((r.btc_r24_bps || 0) / 100)}</span><span class="chip">حداکثر ${n0(r.max_positions)} موقعیت</span></div>
        <div style="margin-top:8px;font-size:12px">${(r.strategies || []).map(x => `<div>${famChip(x)} ${esc(sName(x))}</div>`).join('')}</div>`;
    } else $('#regime').innerHTML = `<div class="faint" style="font-size:12px">رژیم پس از اولین اسکن نسخهٔ جدید نمایش داده می‌شود.</div>`;
    // positions
    const meta = d.positions_meta || {}; const holds = (s.holdings || []).filter(x => x.asset !== 'TMN');
    const pos = $('#positions');
    if (!holds.length) pos.innerHTML = '<div class="empty">موقعیت بازی وجود ندارد؛ سرمایه به تومان نگهداری می‌شود.</div>';
    else {
      for (const x of holds) {
        const m = meta[x.asset] || {}; const id = 'pos-' + x.asset;
        if (!$('#' + id)) {
          if (!pos.querySelector('.pos-row')) pos.innerHTML = '';
          pos.appendChild(h(`<div class="pos-row grid g3" id="${id}" style="margin-bottom:12px"><div class="span2"><canvas class="chart" id="${id}-c"></canvas></div><div id="${id}-i"></div></div>`));
          charts[x.asset] = keep(new CandleChart($('#' + id + '-c'), {}));
        }
        const unit = +x.basis / +x.qty; const value = +(x.value_tmn || 0); const pnl = value ? value - +x.basis : null;
        const stop = m.peak_unit && m.stop ? +m.peak_unit * (1 - +m.stop) : null;
        $('#' + id + '-i').innerHTML = `<div style="font-size:18px;font-weight:700">${sym(m.symbol || x.asset)} ${famChip(m.strategy)} ${wxButton(m.symbol)}</div>
          <div class="muted" style="font-size:12px">${esc(sName(m.strategy || 'legacy_trend6'))}</div>
          <table style="margin-top:8px"><tr><td class="muted">مقدار</td><td>${n4(x.qty)} ${esc(x.asset)}</td></tr>
          <tr><td class="muted">بهای تمام‌شده</td><td>${toman(x.basis)} <span class="faint">(${price(unit)})</span></td></tr>
          <tr><td class="muted">ارزش فعلی</td><td>${toman(value)}</td></tr>
          <tr><td class="muted">سود/زیان باز</td><td class="${signCls(pnl)}">${pnl === null ? '—' : toman(pnl) + ' (' + pct(pnl / +x.basis * 100) + ')'}</td></tr>
          <tr><td class="muted">حد ضرر شناور</td><td>${stop ? price(stop) + ' <span class="faint">(' + pct(+m.stop * 100, 1) + ' زیر اوج)</span>' : '—'}</td></tr>
          <tr><td class="muted">سه حد سود</td><td>${m.tp ? m.tp.map((v, i) => `<span class="${(+m.tp_stage || 0) > i ? 'pos' : ''}">TP${i + 1} ${price(v)} <span class="faint">(${pct((+v / unit - 1) * 100, 1)})</span></span>`).join('<br>') : 'در چرخهٔ بعدی تعیین می‌شود'}</td></tr>
          <tr><td class="muted">حد ضرر پله‌ای</td><td>${m.sl_floor ? '<span class="pos">' + price(m.sl_floor) + '</span> <span class="faint">(مرحله ' + n0(m.tp_stage) + ')</span>' : 'پس از +1R یا TP1 به سربه‌سر می‌رود'}</td></tr>
          <tr><td class="muted">روند ۱۵ دقیقه‌ای</td><td>${fastCell(d.fast, m.symbol)}</td></tr>
          <tr><td class="muted">زمان ورود</td><td>${when(m.opened_at)}</td></tr>
          <tr><td class="muted">دلیل خروج معلق</td><td>${m.exit_reason ? esc(reason(m.exit_reason)) : '—'}</td></tr></table>`;
        if (m.symbol) { const first = !charts[x.asset].pending; charts[x.asset].pending = { symbol: m.symbol, entry: unit, stop: Math.max(stop || 0, m.sl_floor ? +m.sl_floor : 0) || stop, tp: (m.tp || (m.target ? [m.target] : [])).map(Number) }; if (first) loadCandles(charts[x.asset]); }
      }
    }
    // last AI + candidates
    $('#lastai').innerHTML = d.latest_decision ? decisionCard(d.latest_decision, true) : '<div class="empty">هنوز تصمیمی ثبت نشده است.</div>';
    const cov = (sc && sc.coverage) || {}; const scanned = (cov.signal || 0) + (cov.eligible_no_signal || 0);
    $('#cands').innerHTML = (sc ? `<div class="faint" style="font-size:11px;margin-bottom:6px">${n0(scanned)} جفت با دادهٔ کافی ارزیابی شد · ${n0(cov.missing_required_history || 0)} بدون معاملهٔ ساعت آخر یا دادهٔ کافی · ${n0((cov.insufficient_recent_liquidity || 0) + (cov.estimated_capacity_below_minimum || 0))} کم‌نقدشونده · ${n0(cov.below_quality || 0)} زیر حد کیفیت</div>` : '') + (sc && sc.top && sc.top.length ? `<table><thead><tr><th>جفت</th><th>استراتژی</th><th>کیفیت</th><th>R/R</th><th>حد ضرر</th><th>TP</th><th>RSI</th><th>۱۵ دقیقه</th></tr></thead><tbody>${sc.top.map(c => `<tr><td>${sym(c.symbol)}</td><td>${famChip(c.strategy)} ${esc(sName(c.strategy))}${c.confluence && c.confluence.length > 1 ? `<div class="faint" style="font-size:11px">هم‌پوشانی: ${c.confluence.map(sName).join('، ')}</div>` : ''}</td><td><b>${n0(c.quality)}</b></td><td>${n2(c.plan && c.plan.reward_risk)}</td><td>${pct(c.plan && c.plan.stop_fraction * 100, 1)}</td><td>${c.plan && c.plan.target_price_tmn ? price(c.plan.target_price_tmn) : '—'}</td><td>${n0(c.indicators && c.indicators.rsi14)}</td><td style="font-size:11px">${d.fast && d.fast.symbols && d.fast.symbols[c.symbol] ? (d.fast.symbols[c.symbol].trend_up ? '<span class="pos">تأیید</span>' : '<span class="warn">منتظر</span>') : '—'}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">در اسکن آخر هیچ ستاپ باکیفیتی پیدا نشد؛ نبود معامله تصمیم معتبر است.</div>');
  });
  async function loadCandles(c) {
    const q = c.pending; const d = await safe(() => api(`/api/public/candles?symbol=${q.symbol}&resolution=1&minutes=360`));
    if (d) c.set(d, { lines: [{ y: q.entry, label: 'ورود', color: '#f5c343' }, { y: q.stop, label: 'حد ضرر', color: '#fb7185' }, ...q.tp.map((y, i) => ({ y, label: 'TP' + (i + 1), color: '#34d399' }))] });
  }
  every(20000, () => { for (const c of Object.values(charts)) if (c.pending) loadCandles(c); });
  every(15000, async () => {
    const j = await safe(() => api('/api/public/journal')); if (!j) return; CTX.journal = j;
    $('#recent').innerHTML = ordersTable(j.orders.filter(o => o.fill_count).slice(-8).reverse(), true);
    $('#feed').innerHTML = feedItems(j).slice(0, 40).join('') || '<div class="empty">رویدادی نیست</div>';
  });
}

function fastCell(fast, symbol) {
  const x = fast && fast.symbols && fast.symbols[symbol];
  if (!x) return '<span class="faint">در انتظار کندل ۱۵ دقیقه‌ای</span>';
  const st = x.structure_break ? '<span class="neg">شکست ساختار</span>' : x.trend_up ? '<span class="pos">صعودی</span>' : '<span class="warn">خنثی/ضعیف</span>';
  return `${st} <span class="faint" style="font-size:11px">EMA8 ${price(x.ema8)} · EMA21 ${price(x.ema21)} · کف ۲س ${price(x.swing_low)} · ${hm(x.bucket_end)}</span>`;
}

function feedItems(j) {
  const rows = [];
  for (const p of j.plans || []) {
    const parts = [];
    for (const o of p.orders || []) parts.push(`سفارش ${SIDE_FA[o.side] || o.side} ${sym(o.symbol)} — ${esc(reason(o.reason))}`);
    for (const [k, v] of p.events || []) {
      if (k === 'strategy_exit') parts.push(`خروج ${esc(v.base)}: ${esc(reason(v.reason))}`);
      else if (k === 'trx_trend_exit_hold') parts.push('نگهداری روندی TRX: خروج برگشت روند معلق ماند');
      else if (k === 'fast_trend_break') parts.push(`شکست روند ۱۵ دقیقه‌ای ${sym(v.symbol)}: بسته شدن زیر کف ۲ ساعته`);
      else if (k === 'take_profit_set') parts.push(`TP برای ${esc(v.base)} روی ${price(v.target)} تنظیم شد`);
      else if (k === 'take_profit_ladder_set') parts.push(`سه TP${v.policy ? ' با فاصلهٔ برابر' : ''} برای ${esc(v.base)}: ${(v.tp || []).map(price).join(' / ')}`);
      else if (k === 'take_profit_reached') parts.push(`${esc(v.base)} به TP${v.level} رسید؛ حد ضرر به ${price(v.stop_raised_to)} رفت`);
      else if (k === 'take_profit_partial') parts.push(`فروش بخشی ${esc(v.base)} در ${esc(String(v.reason).toUpperCase())}`);
      else if (k === 'allocation' && v.approved) parts.push(`تخصیص ${sym(v.candidate)} ${toman(v.budget_tmn)}`);
      else if (k === 'allocation') parts.push(`رد تخصیص ${sym(v.candidate)}: ${esc(v.reason)}`);
      else if (k === 'entry_quote_gate') parts.push('رد اجرایی: ' + (v.rejected || []).map(x => x.symbol + ' (' + reason(x.reason) + ')').join('، '));
    }
    if (parts.length) rows.push([p.observed_at || p.time, parts.join(' · ')]);
  }
  for (const d of j.decisions || []) rows.push([d.time, `تصمیم AI: ${d.status === 'ok' ? 'موفق' : esc(reason(d.reason) || d.status)} · انتخاب: ${(d.selected || []).filter(Boolean).map(sym).join('، ') || 'هیچ'}`]);
  for (const s of j.system || []) rows.push([s.detail && (s.detail.time || s.detail.observed_at), 'سیستم: ' + esc(s.kind)]);
  return rows.filter(r => r[0]).sort((a, b) => b[0] - a[0]).map(([t, x]) => `<div class="item"><span class="t">${clock(t)}</span><span>${x}</span></div>`);
}

function decisionCard(d, compact = false) {
  const ok = d.status === 'ok';
  const attempts = (d.attempts || []).map(a => `<span class="chip ${a.status === 'ok' ? 'ok' : 'bad'}">${esc(a.variant)} · ${esc(a.finish_reason || a.http_status || a.status)}${a.usage && a.usage.completion_tokens ? ' · ' + n0(a.usage.completion_tokens) + ' توکن' : ''}</span>`).join(' ');
  const rows = (d.decisions || []).map(x => `<div class="cand"><div class="sym">${x.symbol ? sym(x.symbol) : esc(x.id)}</div>
      <div>${x.action === 'enter' ? '<span class="chip ok">ورود</span>' : '<span class="chip">رد</span>'} <span>${esc(x.reason)}</span></div>
      <div><span class="faint" style="font-size:11px">اطمینان ${n2(x.confidence)} · اندازه ${n2(x.size)}</span><div class="conf"><i style="width:${Math.round((x.confidence || 0) * 100)}%"></i></div></div></div>`).join('');
  const legacy = d.legacy ? `<div class="view">${esc(d.legacy.reason)} <span class="faint">(اطمینان ${n2(d.legacy.confidence)})</span></div>` : '';
  return `<div class="decision"><div class="meta"><span class="chip ${ok ? 'ok' : 'bad'}">${ok ? 'پاسخ معتبر' : 'بدون مجوز ورود'}</span><span>${when(d.time)}</span>
    ${d.regime ? `<span class="chip y">${esc(d.regime.fa || d.regime.regime || '')}</span>` : ''}${d.model ? `<span class="mono">${esc(d.model)}</span>` : ''}
    ${d.latency_seconds ? `<span>${n2(d.latency_seconds)} ثانیه</span>` : ''}${d.regime_assessment ? `<span class="chip">ارزیابی رژیم: ${esc({ agree: 'موافق', more_cautious: 'محتاط‌تر', more_aggressive: 'تهاجمی‌تر' }[d.regime_assessment])}</span>` : ''}</div>
    ${d.market_view ? `<div class="view">${esc(d.market_view)}</div>` : ''}${legacy}
    ${!ok ? `<div class="faint" style="font-size:12px">${esc(reason(d.reason) || d.validation_error || d.finish_reason || '')}</div>` : ''}
    ${rows}${attempts ? `<div style="margin-top:8px">${attempts}</div>` : ''}
    ${!compact && d.reasoning_excerpt ? `<details style="margin-top:8px"><summary>استدلال ثبت‌شدهٔ مدل (${n0((d.reasoning_excerpt || '').length)} نویسه)</summary><div class="reasoning">${esc(d.reasoning_excerpt)}</div></details>` : ''}</div>`;
}

function ordersTable(orders, compact = false) {
  if (!orders.length) return '<div class="empty">هنوز سفارشی ثبت نشده است.</div>';
  return `<table><thead><tr><th>زمان</th><th>جفت</th><th>سمت</th>${compact ? '' : '<th>نوع</th>'}<th>قیمت میانگین</th><th>مقدار</th><th>ارزش</th>${compact ? '' : '<th>کارمزد</th>'}<th>استراتژی / دلیل</th>${compact ? '' : '<th>وضعیت</th><th>تصمیم AI</th>'}</tr></thead><tbody>
  ${orders.map(o => `<tr><td>${when(o.time)}</td><td>${sym(o.symbol)}</td><td class="${o.side === 'BUY' ? 'pos' : 'neg'}">${SIDE_FA[o.side]}</td>${compact ? '' : `<td class="mono">${esc(o.type)}</td>`}
    <td>${price(o.avg_price || o.limit_price)}</td><td>${n4(o.executed_qty)} <span class="faint">/ ${n4(o.quantity)}</span></td><td>${toman(o.notional)}</td>
    ${compact ? '' : `<td>${Object.entries(o.fees || {}).map(([a, v]) => n4(v) + ' ' + a).join('، ') || '—'}</td>`}
    <td>${famChip(o.strategy)} ${esc(sName(o.strategy))}<div class="faint" style="font-size:11px">${esc(reason(o.reason))}</div></td>
    ${compact ? '' : `<td>${esc(PHASE_FA[o.phase] || o.phase)}</td><td style="max-width:260px;font-size:12px">${o.ai ? esc(o.ai.reason || '') + (o.ai.confidence !== undefined ? ` <span class="faint">(${n2(o.ai.confidence)})</span>` : '') : '—'}</td>`}</tr>`).join('')}</tbody></table>`;
}

// ------------------------------------------------------------------ journal
function pageJournal(root) {
  root.innerHTML = `<section class="grid g4" id="jk" style="margin-bottom:14px"></section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>معاملات رفت‌وبرگشت</h2><span class="sub">هر ورود با دلیل استراتژی و AI، و هر خروج با قاعدهٔ قطعی ثبت می‌شود</span>
    <div class="tools"><button id="csv">خروجی CSV</button><button id="json">خروجی JSON</button></div></div><div class="body table-wrap" id="trades"></div></section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>همهٔ سفارش‌های صرافی</h2><span class="sub">شامل سفارش‌های پرشده، لغوشده و محافظ</span></div><div class="body table-wrap scroll" id="orders"></div></section>
  <section class="grid g2"><div class="panel"><div class="head"><h2>دفتر تصمیم موتور</h2><span class="sub">برنامه‌ها، خروج‌ها، تخصیص‌ها و ردها</span></div><div class="body feed scroll" id="plans"></div></div>
  <div class="panel"><div class="head"><h2>رویدادهای سیستمی و ممیزی</h2></div><div class="body feed scroll" id="sys"></div></div></section>`;
  every(15000, async () => {
    const j = await safe(() => api('/api/public/journal'), $('#trades')); if (!j) return; CTX.journal = j;
    const closed = j.trades.filter(t => t.status === 'closed'); const wins = closed.filter(t => +t.pnl_tmn > 0);
    const total = j.trades.reduce((a, t) => a + (+t.pnl_tmn || 0), 0);
    $('#jk').innerHTML = [['تعداد معاملات', n0(j.trades.length), 'باز: ' + n0(j.trades.length - closed.length)], ['نرخ برد (بسته‌شده)', closed.length ? pct(wins.length / closed.length * 100, 0) : '—', n0(wins.length) + ' برد از ' + n0(closed.length)],
      ['سود/زیان کل معاملات', toman(total), 'شامل ارزش باز موقعیت‌ها'], ['سفارش‌ها', n0(j.orders.length), 'آخرین رویداد #' + n0(j.last_seq)]]
      .map(([a, b, c]) => `<div class="panel kpi"><div class="label">${a}</div><div class="value">${b}</div><div class="note">${c}</div></div>`).join('');
    $('#trades').innerHTML = j.trades.length ? `<table><thead><tr><th>جفت</th><th>استراتژی</th><th>ورود</th><th>خروج</th><th>قیمت ورود</th><th>قیمت خروج</th><th>سود/زیان</th><th>دلیل ورود (AI)</th><th>دلیل خروج</th><th>وضعیت</th></tr></thead><tbody>
      ${j.trades.map(t => `<tr><td>${sym(t.symbol)}</td><td>${famChip(t.strategy)} ${esc(sName(t.strategy))}</td><td>${when(t.opened_at)}</td><td>${t.closed_at ? when(t.closed_at) : '—'}</td><td>${price(t.entry_avg)}</td><td>${price(t.exit_avg)}</td>
      <td class="${signCls(t.pnl_tmn)}">${toman(t.pnl_tmn)}<div style="font-size:11px">${pct(t.pnl_percent)}</div></td><td style="max-width:280px;font-size:12px">${esc(t.entry_reason || '—')}${t.ai_confidence !== undefined && t.ai_confidence !== null ? ` <span class="faint">(${n2(t.ai_confidence)})</span>` : ''}</td>
      <td>${esc(reason(t.exit_reason))}</td><td>${t.status === 'open' ? '<span class="chip y">باز</span>' : '<span class="chip">بسته</span>'}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">هنوز معامله‌ای انجام نشده است.</div>';
    $('#orders').innerHTML = ordersTable(j.orders.slice().reverse());
    $('#plans').innerHTML = feedItems({ plans: j.plans }).join('') || '<div class="empty">—</div>';
    $('#sys').innerHTML = (j.system || []).map(s => `<div class="item"><span class="t">#${s.seq}</span><span><b>${esc(s.kind)}</b> <span class="faint mono" style="font-size:11px;word-break:break-all;display:block;text-align:left">${esc(JSON.stringify(s.detail).slice(0, 220))}</span></span></div>`).join('') || '<div class="empty">—</div>';
    $('#csv').onclick = () => { const head = ['symbol', 'strategy', 'opened_at', 'closed_at', 'entry_avg', 'exit_avg', 'pnl_tmn', 'pnl_percent', 'entry_reason', 'exit_reason', 'status'];
      download('nova-trades.csv', [head.join(','), ...j.trades.map(t => head.map(k => JSON.stringify(t[k] ?? '')).join(','))].join('\n'), 'text/csv'); };
    $('#json').onclick = () => download('nova-journal.json', JSON.stringify(j, null, 2));
  });
}

// ------------------------------------------------------------------ AI
function pageAI(root) {
  root.innerHTML = `<div class="notice" style="margin-bottom:14px">در هر ساعت، اسکنر همهٔ جفت‌های مجاز را با استراتژی‌های فعال رژیم بررسی می‌کند. مدل برای هر نامزد «ورود/رد»، اطمینان، ضریب اندازه و دلیل فارسی برمی‌گرداند. درخواست، پاسخ، استدلال ثبت‌شدهٔ مدل، توکن‌ها، زمان پاسخ و هر تلاش ناموفق در دفتر ممیزی ذخیره می‌شود. پاسخ ناقص هرگز مجوز ورود نیست.</div>
  <section class="grid g4" id="aik" style="margin-bottom:14px"></section><div id="dlist"></div>`;
  every(20000, async () => {
    const j = await safe(() => api('/api/public/journal'), $('#dlist')); if (!j) return;
    const ds = j.decisions || []; const ok = ds.filter(d => d.status === 'ok');
    const enters = ds.reduce((a, d) => a + (d.decisions || []).filter(x => x.action === 'enter').length, 0);
    const tok = ds.reduce((a, d) => a + ((d.usage && d.usage.completion_tokens) || 0), 0);
    $('#aik').innerHTML = [['تصمیم‌های ثبت‌شده', n0(ds.length), ''], ['پاسخ معتبر', n0(ok.length), ds.length ? pct(ok.length / ds.length * 100, 0) : ''], ['پیشنهاد ورود', n0(enters), 'پس از کنترل ریسک قطعی'], ['توکن خروجی', n0(tok), 'مجموع پاسخ‌ها']]
      .map(([a, b, c]) => `<div class="panel kpi"><div class="label">${a}</div><div class="value">${b}</div><div class="note">${c}</div></div>`).join('');
    $('#dlist').innerHTML = ds.length ? ds.map(d => `<div class="panel" style="margin-bottom:12px"><div class="body">${decisionCard(d)}
      ${d.candidates && d.candidates.length ? `<details><summary>${n0(d.candidates.length)} نامزد ارسالی به مدل</summary><div class="table-wrap"><table><thead><tr><th>جفت</th><th>استراتژی</th><th>کیفیت</th><th>R/R</th><th>حد ضرر</th><th>TP</th></tr></thead><tbody>${d.candidates.map(c => `<tr><td>${sym(c.symbol)}</td><td>${esc(sName(c.strategy))}</td><td>${n0(c.quality)}</td><td>${n2(c.score)}</td><td>${c.plan ? pct(c.plan.stop_fraction * 100, 1) : '—'}</td><td>${c.plan && c.plan.target_price_tmn ? price(c.plan.target_price_tmn) : '—'}</td></tr>`).join('')}</tbody></table></div></details>` : ''}</div></div>`).join('') : '<div class="empty">هنوز تصمیمی ثبت نشده است.</div>';
  });
}

// ------------------------------------------------------------------ strategies
function pageStrategies(root) {
  root.innerHTML = `<div id="sintro"></div><h2 style="font-size:16px">۱. تشخیص رژیم بازار</h2><section class="grid g4" id="regimes" style="margin-bottom:18px"></section>
  <h2 style="font-size:16px">۲. استراتژی‌ها (همه با تأیید و رتبه‌بندی AI)</h2><section class="grid g2" id="strats" style="margin-bottom:18px"></section>
  <h2 style="font-size:16px">۳. شواهد بک‌تست قواعد (بدون AI)</h2><section class="panel" id="bt"><div class="body"><div class="skeleton" style="height:80px"></div></div></section>`;
  (async () => {
    const live = CTX.live || await safe(pollLive); const cat = live ? live.strategies : await api('/api/public/strategies');
    const cur = live && live.latest_scan && live.latest_scan.regime ? live.latest_scan.regime.regime : null;
    $('#sintro').innerHTML = `<div class="notice green" style="margin-bottom:14px">${esc(cat.ai_role)}<br>${esc(cat.quality_role || '')}<br>${esc(cat.fast_role || '')}<br>${esc(cat.exit_role || '')}<br>${esc(cat.hard_limits_role)}</div>`;
    $('#regimes').innerHTML = Object.entries(cat.regimes).map(([k, r]) => `<div class="regime ${k === cur ? 'current' : ''}"><b style="font-size:15px">${esc(r.fa)}</b><div class="muted" style="font-size:12px;margin:4px 0 8px">${esc(r.description)}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px"><span class="chip">حداکثر ${n0(r.max_positions)} موقعیت</span><span class="chip">سقف ورود ${toman(r.order_cap_tmn)}</span><span class="chip">ریسک هر ورود ${pct(r.risk_fraction * 100, 1)}</span></div>
      ${r.strategies.map(s => `<div style="font-size:12.5px">${famChip(s)} ${esc(cat.strategies[s].fa)}</div>`).join('')}</div>`).join('');
    const active = cur ? cat.regimes[cur].strategies : [];
    $('#strats').innerHTML = Object.entries(cat.strategies).map(([k, s]) => `<div class="panel strategy ${active.includes(k) ? 'active' : ''}">${ART[k] || ART.custom || ''}
      <div><h3>${esc(s.fa)} ${s.family === 'smart_money' ? '<span class="chip smc">Smart Money</span>' : s.family === 'hybrid' ? '<span class="chip smc">Hybrid</span>' : '<span class="chip ind">Indicator</span>'} ${s.custom ? '<span class="chip y">ساخت استودیو</span>' : ''} ${active.includes(k) ? '<span class="chip y">فعال در رژیم فعلی</span>' : ''}</h3>
      <div class="muted" style="font-size:12.5px">${esc(s.thesis)}</div><dl><dt>ورود</dt><dd>${esc(s.entry)}</dd><dt>حد ضرر</dt><dd>${esc(s.stop)}</dd><dt>هدف</dt><dd>${esc(s.target)}</dd><dt>خروج</dt><dd>${esc(s.exit)}</dd></dl></div></div>`).join('');
    const rep = await safe(() => api('/api/public/adaptive-report'), $('#bt .body'));
    if (rep) $('#bt .body').innerHTML = rep.pending ? '<div class="empty">گزارش هنوز تولید نشده است.</div>' : `<div class="muted" style="font-size:12px;margin-bottom:8px">همهٔ ۳۹ پنجرهٔ ۷۲ساعته قبلاً دیده شده‌اند و آزمون مستقل نیستند. هر پیشنهاد قاعده بدون فیلتر AI با اندازهٔ کامل پذیرفته شده؛ پس این عدد لایهٔ قطعی را می‌سنجد، نه تصمیم مدل. کارمزد، اسپرد، لغزش و تأخیر لحاظ شده‌اند.</div>
      <div class="table-wrap"><table><thead><tr><th>بخش</th><th>سناریو</th><th>پنجره</th><th>میانگین بازده</th><th>میانه</th><th>بهترین</th><th>بدترین</th><th>پنجرهٔ مثبت</th><th>حداکثر افت</th><th>پرشدن</th></tr></thead><tbody>
      ${rep.aggregates.map(a => `<tr><td>${{ selection: 'انتخاب ۱–۳۰', validation: 'اعتبارسنجی ۳۱–۳۹', all: 'همه' }[a.split] || a.split}</td><td>${a.scenario === 'base' ? 'پایه' : 'تنش هزینه/تأخیر'}</td><td>${n0(a.windows)}</td><td class="${signCls(a.mean_return_percent)}">${pct(a.mean_return_percent, 3)}</td><td class="${signCls(a.median_return_percent)}">${pct(a.median_return_percent, 3)}</td><td>${pct(a.best_return_percent)}</td><td>${pct(a.worst_return_percent)}</td><td>${n0(a.positive_windows)}</td><td>${pct(a.max_drawdown_percent)}</td><td>${n0(a.fills)}</td></tr>`).join('')}</tbody></table></div>`;
  })();
}

// ------------------------------------------------------------------ market
function pageMarket(root) {
  root.innerHTML = `<section class="grid g3" style="margin-bottom:14px"><div class="panel span2"><div class="head"><h2 id="mtitle">نمودار دقیقه‌ای</h2>
    <div class="tools tabs-inline" id="mres"><button data-m="180">۳ ساعت</button><button data-m="720" class="on">۱۲ ساعت</button><button data-m="1440">۱ روز</button><button data-m="4320" data-r="5">۳ روز</button></div></div><div class="body"><canvas class="chart tall" id="mchart"></canvas></div></div>
    <div class="panel"><div class="head"><h2>جزئیات</h2></div><div class="body" id="mdet"></div></div></section>
  <section class="panel"><div class="head"><h2>نقشهٔ حرارتی ۱۲۰ جفت مجاز</h2><span class="sub" id="hmeta"></span><div class="tools tabs-inline" id="hq"><button data-q="all" class="on">همه</button><button data-q="TMN">تومانی</button><button data-q="USDT">تتری</button></div></div><div class="body"><div class="heat" id="heat"></div></div></section>`;
  const ch = keep(new CandleChart($('#mchart'), { fitLines: false }));
  let symbol = 'BTCTMN', minutes = 720, resn = '1', q = 'all', rows = [], prev = {};
  $('#mres').onclick = e => { const b = e.target.closest('button'); if (!b) return; minutes = +b.dataset.m; resn = b.dataset.r || '1'; $$('#mres button').forEach(x => x.classList.toggle('on', x === b)); loadC(); };
  $('#hq').onclick = e => { const b = e.target.closest('button'); if (!b) return; q = b.dataset.q; $$('#hq button').forEach(x => x.classList.toggle('on', x === b)); paint(); };
  async function loadC() {
    const d = await safe(() => api(`/api/public/candles?symbol=${symbol}&resolution=${resn}&minutes=${minutes}`)); if (!d) return;
    $('#mtitle').innerHTML = `نمودار ${resn === '1' ? 'دقیقه‌ای' : resn + ' دقیقه‌ای'} ${sym(symbol)} ${wxButton(symbol)}`; ch.set(d);
    const r = rows.find(x => x.symbol === symbol) || {}; const cand = ((CTX.live && CTX.live.latest_scan && CTX.live.latest_scan.top) || []).find(c => c.symbol === symbol);
    $('#mdet').innerHTML = `<table><tr><td class="muted">آخرین قیمت</td><td>${price(r.last)}</td></tr><tr><td class="muted">خرید / فروش</td><td>${price(r.bid)} / ${price(r.ask)}</td></tr>
      <tr><td class="muted">اسپرد</td><td>${r.bid && r.ask ? n0((r.ask / r.bid - 1) * 10000) + ' واحد پایه' : '—'}</td></tr><tr><td class="muted">تغییر ۲۴ساعته</td><td class="${signCls(r.change_24h)}">${pct(r.change_24h)}</td></tr>
      <tr><td class="muted">حجم ۲۴ساعته</td><td>${toman(r.volume_tmn_24h)}</td></tr><tr><td class="muted">ستاپ فعلی</td><td>${cand ? famChip(cand.strategy) + ' ' + esc(sName(cand.strategy)) : 'ندارد'}</td></tr></table>`;
  }
  function paint() {
    const cands = new Set(((CTX.live && CTX.live.latest_scan && CTX.live.latest_scan.top) || []).map(c => c.symbol));
    const list = rows.filter(r => q === 'all' || r.quote === q).sort((a, b) => (b.volume_tmn_24h || 0) - (a.volume_tmn_24h || 0));
    $('#heat').innerHTML = list.map(r => { const c = Math.max(-8, Math.min(8, r.change_24h || 0)); const a = Math.abs(c) / 8 * .55 + .06;
      const bg = c >= 0 ? `rgba(52,211,153,${a})` : `rgba(251,113,133,${a})`; const tick = prev[r.symbol] !== undefined && prev[r.symbol] !== r.last;
      return `<div class="tile ${cands.has(r.symbol) ? 'cand' : ''} ${tick ? 'tick' : ''}" data-s="${r.symbol}" style="background:${bg}"><b>${esc(r.base)}<small class="faint">/${esc(r.quote)}</small></b><span>${price(r.last)}</span><span>${pct(r.change_24h)}</span></div>`; }).join('');
    rows.forEach(r => prev[r.symbol] = r.last);
  }
  $('#heat').onclick = e => { const t = e.target.closest('.tile'); if (t) { symbol = t.dataset.s; loadC(); scrollTo({ top: 0, behavior: 'smooth' }); } };
  every(15000, async () => { const d = await safe(() => api('/api/public/ticker'), $('#heat')); if (!d) return; rows = d.rows; $('#hmeta').textContent = 'به‌روزرسانی ' + clock(d.received_at) + ' · کادر زرد = ستاپ فعال در اسکن آخر'; paint(); });
  every(20000, loadC);
}

// ------------------------------------------------------------------ challenge
function pageChallenge(root) {
  const live = CTX.live || {}; const s = live.snapshot || {}; const run = live.run || {};
  const score = [['سود نهایی محقق‌شده به تومان', 90, 'perf', 'ارزش حساب، سود محقق‌شده و تسویهٔ نهایی به تومان در صفحهٔ «اجرای واقعی»'],
    ['کنترل ضرر و افت سرمایه', 30, 'perf', 'حد ضرر شناور، سقف زیان روزانه ۲٪ و افت ۵٪، توقف خودکار'], ['فعالیت منطقی', 15, 'perf', 'اسکن ساعتی ۱۲۰ جفت؛ بدون معاملهٔ اجباری'],
    ['پایداری و بازیابی', 15, 'perf', 'دفتر ماندگار PostgreSQL، تطبیق پس از قطع، عدم ارسال دوباره'], ['استراتژی و منطق', 40, 'tech', 'رژیم بازار + ۶ استراتژی SMC و اندیکاتوری با قواعد شفاف'],
    ['نقش واقعی AI', 35, 'tech', 'تأیید، رتبه و اندازهٔ هر ورود با دلیل ثبت‌شده؛ نردبان درخواست برای پاسخ ناقص'], ['مدیریت ریسک', 30, 'tech', 'سقف سفارش، دارایی، ناخالص، ریسک باز، اسپرد و عمق دفتر سفارش'],
    ['تکرارپذیری و بازاجرا', 25, 'tech', 'هش سورس در هر مجوز، زنجیرهٔ ممیزی، Docker و بازپخش'], ['بک‌تست و سایه', 20, 'tech', 'بک‌تست ۳۹ پنجره با هزینه و تنش؛ نتایج منفی نیز گزارش شده‌اند']];
  const rules = [['فقط بازار اسپات و بدون اهرم', 'ok', 'موتور فقط سفارش LIMIT اسپات و محافظ STOP_LIMIT می‌سازد'], ['یک حساب اختصاصی با ۵ میلیون تومان', run.id ? 'ok' : 'wait', 'حساب اعتباری اختصاصی؛ شناسه در نمای عمومی منتشر نمی‌شود'],
    ['بدون خریدوفروش دستی', 'ok', 'هیچ دکمهٔ خرید/فروش دستی وجود ندارد؛ وب سفارش ارسال نمی‌کند'], ['تسویهٔ نهایی به تومان', s.fully_realized_tmn ? 'ok' : 'wait', 'خروج تطبیقی پیش از ' + (live.contest_end_fa || 'پایان')],
    ['ثبت دلیل تک‌تک معاملات', 'ok', 'ژورنال معاملات و تصمیم‌های AI؛ خروجی CSV/JSON'], ['مهلت تمدیدشده', 'ok', live.contest_end_fa || ''],
    ['کد تحویلی همان کد اجراشده', run.upgrade_required ? 'wait' : 'ok', 'هش نسخهٔ نصب‌شده: ' + (live.installed_source_sha256 || '').slice(0, 16)],
    ['بک‌تست با هزینه و تأخیر', 'ok', 'صفحهٔ «استراتژی‌ها» و «بک‌تست و پژوهش»؛ ۳۹ پنجره و سناریوی تنش'],
    ['تست سایه روی بازار زنده', 'ok', 'صفحهٔ «نحوهٔ تصمیم‌گیری»: همهٔ نامزدها بدون سفارش واقعی دنبال می‌شوند'],
    ['سنجش نقش AI با خط مبنا', 'ok', 'مقایسهٔ نتیجهٔ سایهٔ نامزدهای تأییدشده و ردشده توسط AI'],
    ['تعریف استراتژی با گفت‌وگو و آزمون پیش از اجرا', 'ok', 'صفحهٔ «استودیوی استراتژی»: پیش‌نویس، بک‌تست، بهینه‌سازی، آزمون کامل، تأیید و ارتقا'],
    ['سورس روی GitHub و سند Markdown', 'wait', 'مخزن No-Human-Required/nova-wallex؛ پس از استقرار به‌روزرسانی می‌شود'], ['ویدیوی دموی حدود ۵ دقیقه با صدا', 'no', 'هنوز ضبط نشده؛ نبود ویدیو موجب حذف از داوری است']];
  root.innerHTML = `<section class="panel" style="margin-bottom:14px"><div class="head"><h2>بارم داوری ۳۰۰ امتیاز</h2><span class="sub">عملکرد معاملاتی ۱۵۰ + کیفیت فنی ۱۵۰ (طبق متن «پیشنهاد امتیازدهی» بریف)</span></div>
    <div class="body"><div class="score-bar" style="margin-bottom:12px"><i style="width:50%;background:var(--accent)"></i><i style="width:50%;background:var(--blue)"></i></div>
    ${score.map(([t, p, g, e]) => `<div class="req"><span class="st ${g === 'perf' ? 'wait' : 'ok'}">${n0(p)}</span><div><b>${t}</b><div class="muted" style="font-size:12px">${e}</div></div><span class="chip">${g === 'perf' ? 'عملکرد' : 'فنی'}</span></div>`).join('')}</div></section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>کجا امتیاز بیشتری می‌گیریم</h2><span class="sub">جمع‌بندی بریف و کارهای انجام‌شده برای هر ردیف</span></div><div class="body">${[
    ['استفادهٔ واقعی از AI (۳۵)', 'AI نه فقط اسم: هر ورود، اولویت و اندازه را تعیین می‌کند؛ پاسخ ناقص ورود را می‌بندد؛ تست سایه اثر تأیید/رد AI را با خط مبنای قواعد مقایسه می‌کند. در دمو صفحهٔ «تصمیم‌های AI» و جریان متحرک را نشان دهید.'],
    ['منطق استراتژی (۴۰)', 'شش استراتژی SMC و اندیکاتوری، رژیم بازار، امتیاز کیفیت، لایهٔ ۱۵ دقیقه‌ای و سه TP با فاصلهٔ برابر و حد ضرر پله‌ای؛ اسکرینر تعاملی نشان می‌دهد هر جفت کجا رد یا انتخاب شد.'],
    ['مدیریت ریسک و سرمایه (۳۰)', 'نمودار سقف‌ها و سقف تعیین‌کننده برای هر ورود، وزن‌های پرتفو، ریسک باز و حد ضرر پله‌ای؛ هرگز ورود با کل سرمایه.'],
    ['بک‌تست و تست سایه (۲۰)', 'هر دو اجرا و نمایش داده شده‌اند؛ نتایج منفی هم صادقانه گزارش شده‌اند.'],
    ['قابلیت اجرای مجدد (۲۵)', 'README، STRATEGIES.md، Docker، هش سورس در هر مجوز، آزمون‌ها (SQLite و PostgreSQL) و بازپخش آرشیو. سورس GitHub باید با نسخهٔ اجراشده یکی باشد: پس از هر استقرار push کنید.'],
    ['کنترل ضرر (۳۰) و پایداری (۱۵)', 'سقف زیان روزانه ۲٪ و افت ۵٪، تطبیق سفارش‌ها پس از قطع، بدون ارسال دوباره؛ افت فعلی در صفحهٔ اجرا دیده می‌شود.'],
    ['عامل هوشمند (Agentic) استودیو', 'گفت‌وگو با LLM برای طراحی استراتژی؛ عامل خودش پیش‌نویس می‌سازد، بک‌تست می‌گیرد، ضرایب حد ضرر و TP را بهینه می‌کند و ذخیره می‌کند. افزودن به اجرای واقعی فقط با تأیید انسانی و ارتقای ممیزی‌شده؛ مشخصات داده است نه کد، پس نمی‌تواند سقف‌های ریسک را دور بزند.'],
    ['سرویس‌دهندهٔ قابل‌تعویض AI', 'AvalAI، MetisAI یا BoxAPI (اینترنت ملی/بین‌الملل) با آدرس‌های پین‌شده؛ تعویض کلید والکس یا LLM در اجرای فعال در صف می‌ماند و با ارتقای v7 ثبت می‌شود.'],
    ['ویدیوی دمو (الزامی)', 'حدود ۵ دقیقه با صدا: اجرای واقعی → نحوهٔ تصمیم‌گیری (جریان، اسکرینر با پخش تاریخچه، مدیریت سرمایه، TP/SL) → تصمیم‌های AI → ژورنال → تست سایه → خواسته‌های چالش.']
  ].map(([t, e]) => `<div class="req"><span class="st ok">★</span><div><b>${t}</b><div class="muted" style="font-size:12px">${e}</div></div><span></span></div>`).join('')}</div></section>
  <section class="panel"><div class="head"><h2>قوانین و تحویلی‌ها</h2></div><div class="body">${rules.map(([t, st, e]) => `<div class="req"><span class="st ${st}">${st === 'ok' ? '✓' : st === 'wait' ? '…' : '✕'}</span><div><b>${t}</b><div class="muted" style="font-size:12px">${esc(e)}</div></div><span></span></div>`).join('')}</div></section>`;
}

// ------------------------------------------------------------------ research
function pageResearch(root) {
  root.innerHTML = `<section class="grid g2" style="margin-bottom:14px"><div class="panel"><div class="head"><h2>بک‌تست جدید</h2><span class="sub">نیازمند ورود اپراتور</span></div><div class="body form">
    <div class="row"><label>استراتژی</label><select id="bv"><option value="adaptive_smc">تطبیقی SMC + اندیکاتور (نسخهٔ ۴)</option><option value="guarded_breakout">شکست محافظت‌شده (نسخهٔ ۳)</option><option value="guarded_breakout_ai">شکست + AI آرشیوی (۳۱–۳۹)</option><option value="breakout48">شکست ۴۸ساعته</option><option value="cash">نگهداری تومان</option></select></div>
    <div class="row"><label>پنجرهٔ ۷۲ساعته</label><input id="bw" type="number" min="1" max="39" value="35" style="width:90px"><label>سناریو</label><select id="bs"><option value="base">پایه</option><option value="cost_delay_stress">تنش هزینه و تأخیر</option></select></div>
    <div class="row"><label>یا بازهٔ دلخواه UTC</label><input id="b1" placeholder="2026-09-01T00:00:00Z" class="ltr" style="width:200px"><input id="b2" placeholder="2026-09-05T00:00:00Z" class="ltr" style="width:200px"></div>
    <div class="row"><button class="primary" id="bgo">اجرای بک‌تست</button><span id="bmsg" class="muted"></span></div></div></div>
    <div class="panel"><div class="head"><h2>نتیجهٔ انتخاب‌شده</h2><span class="sub" id="jsel"></span></div><div class="body"><canvas class="chart" id="jchart"></canvas><div id="jsum"></div></div></div></section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>صف بک‌تست‌ها</h2></div><div class="body table-wrap" id="jobs"></div></section>
  <section class="panel"><div class="head"><h2>مقایسهٔ آرشیوی نسخهٔ ۳</h2><span class="sub">۱۵۳ سناریو؛ دوره‌ها قبلاً دیده شده‌اند</span></div><div class="body table-wrap" id="agg"></div></section>`;
  const ch = keep(new LineChart($('#jchart'), { baseline: 5000000, fmt: n0, relative: true, live: false }));
  $('#bgo').onclick = async () => {
    if (!S.authenticated) { $('#bmsg').textContent = 'برای اجرای بک‌تست وارد «کنترل اپراتور» شوید.'; return; }
    const body = { variant: $('#bv').value, window: +$('#bw').value, scenario: $('#bs').value };
    if ($('#b1').value && $('#b2').value) { body.start_utc = $('#b1').value; body.end_utc = $('#b2').value; }
    try { await api('/api/jobs', { body, headers: { 'Idempotency-Key': 'ui' + Date.now() + Math.random().toString(36).slice(2, 8) } }); $('#bmsg').textContent = 'در صف قرار گرفت'; loadJobs(); } catch (e) { $('#bmsg').textContent = e.message; }
  };
  async function show(id) {
    const j = await safe(() => api('/api/jobs/' + id), $('#jsum')); if (!j) return; const sn = j.snapshot || {};
    $('#jsel').textContent = j.spec.variant + ' · ' + (j.spec.start_utc ? 'بازهٔ دلخواه' : 'پنجرهٔ ' + j.spec.window);
    ch.set((sn.accounts || []).map(a => [a.time, +a.equity]));
    const r = sn.summary; $('#jsum').innerHTML = r ? `<div class="grid g4" style="margin-top:8px">${[['بازده تسویه', pct(r.liquidation_return_percent, 3)], ['حداکثر افت', pct(r.max_drawdown_percent)], ['پرشدن', n0(r.fill_count)], ['کارمزد', toman(r.fees_tmn)]].map(([a, b]) => `<div class="kpi" style="padding:6px"><div class="label">${a}</div><div class="value" style="font-size:17px">${b}</div></div>`).join('')}</div>` : '<div class="muted">در حال اجرا…</div>';
  }
  async function loadJobs() {
    const js = await safe(() => api('/api/jobs'), $('#jobs')); if (!js) return;
    $('#jobs').innerHTML = js.length ? `<table><thead><tr><th>شناسه</th><th>استراتژی</th><th>بازه</th><th>وضعیت</th><th>پیشرفت</th><th></th></tr></thead><tbody>${js.map(j => `<tr><td class="mono">${j.id.slice(0, 8)}</td><td>${esc(j.spec.variant)}</td><td>${j.spec.start_utc ? esc(j.spec.start_utc + ' → ' + j.spec.end_utc) : 'پنجرهٔ ' + n0(j.spec.window)} · ${j.spec.scenario === 'base' ? 'پایه' : 'تنش'}</td><td>${esc(j.status)}</td><td>${n0(j.progress)}</td><td><button data-j="${j.id}">نمایش</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty">بک‌تستی در صف نیست.</div>';
    $$('#jobs button[data-j]').forEach(b => b.onclick = () => show(b.dataset.j));
  }
  every(5000, loadJobs);
  safe(async () => { const r = await api('/api/report'); $('#agg').innerHTML = `<table><thead><tr><th>بخش</th><th>استراتژی</th><th>سناریو</th><th>پنجره</th><th>میانگین</th><th>بدترین</th><th>مثبت</th><th>حداکثر افت</th></tr></thead><tbody>${(r.aggregates || []).map(a => `<tr><td>${esc(a.split)}</td><td>${esc(a.variant)}</td><td>${esc(a.scenario)}</td><td>${n0(a.windows)}</td><td class="${signCls(a.mean_return_percent)}">${pct(a.mean_return_percent, 3)}</td><td>${pct(a.worst_return_percent)}</td><td>${n0(a.positive_windows)}</td><td>${pct(a.max_drawdown_percent)}</td></tr>`).join('')}</tbody></table>`; }, $('#agg'));
}

// ------------------------------------------------------------------ operator
function pageOperator(root) {
  if (!S.authenticated) {
    root.innerHTML = `<section class="panel" style="max-width:440px"><div class="head"><h2>ورود اپراتور</h2></div><div class="body form"><input type="password" id="pw" placeholder="رمز اپراتور" autocomplete="current-password"><div class="row"><button class="primary" id="login">ورود</button><span id="lmsg" class="muted"></span></div></div></section>`;
    const go = async () => { try { const r = await api('/api/login', { body: { password: $('#pw').value } }); S.csrf = r.csrf; S.authenticated = true; who(); route(); } catch (e) { $('#lmsg').textContent = e.message; } };
    $('#login').onclick = go; $('#pw').onkeydown = e => { if (e.key === 'Enter') go(); }; return;
  }
  root.innerHTML = `<section class="grid g2" style="margin-bottom:14px">
    <div class="panel"><div class="head"><h2>کنترل موتور</h2><div class="tools"><button id="logout">خروج</button></div></div><div class="body" id="ctl"></div></div>
    <div class="panel"><div class="head"><h2>ارتقای اجرای فعلی</h2><span class="sub">فقط خواندنی از صرافی؛ دفتر و موقعیت‌ها حفظ می‌شوند</span></div><div class="body" id="upg"></div></div></section>
  <section class="grid g2" style="margin-bottom:14px"><div class="panel"><div class="head"><h2>محافظ حد ضرر TRX در صرافی</h2></div><div class="body" id="nat"></div></div>
    <div class="panel"><div class="head"><h2>اتصال و فعال‌سازی</h2></div><div class="body" id="setup"></div></div></section>
  <section class="panel"><div class="head"><h2>لاگ کامل ممیزی</h2><span class="sub">۲۰۰ رویداد آخر</span></div><div class="body feed scroll" id="audit"></div></section>`;
  $('#logout').onclick = async () => { await safe(() => api('/api/logout', { body: {} })); S.authenticated = false; S.csrf = ''; who(); route(); };
  async function refresh() {
    const st = await safe(() => api('/api/live/status'), $('#ctl')); if (!st) return;
    const state = st.state; const snap = st.last_snapshot || {};
    $('#ctl').innerHTML = `<table><tr><td class="muted">درخواست / وضعیت</td><td>${esc(state.desired)} / ${esc(STATUS_FA[state.status] || state.status)}</td></tr><tr><td class="muted">خطا</td><td>${esc(state.last_error || '—')}</td></tr>
      <tr><td class="muted">ضربان</td><td>${ago(state.heartbeat)}</td></tr><tr><td class="muted">کلیدها</td><td>والکس ${st.credentials.wallex.present ? '✓' : '✕'} · LLM ${esc((st.risk_config && st.risk_config.ai_provider) || 'avalai')} · <a href="#settings">تنظیمات</a></td></tr>
      <tr><td class="muted">پایان</td><td>${esc(st.contest_end_fa || '')}</td></tr><tr><td class="muted">سفارش حل‌نشده</td><td>${n0((snap.unresolved || []).length)}</td></tr></table>
      ${st.code_upgrade_required ? '<div class="notice" style="margin-top:10px">نسخهٔ نصب‌شده با اجرای حساب یکسان نیست. اول «ارتقای اجرای فعلی» را تأیید کنید؛ «ادامه» پیش از آن موتور را دوباره مسدود می‌کند.</div>' : st.upgrade_available ? '<div class="notice" style="margin-top:10px">تغییرات تنظیمات (کلید، سرویس‌دهندهٔ LLM یا استراتژی استودیو) منتظر ارتقاست. برای اعمال: توقف ← ارتقا ← ادامه. ادامه بدون ارتقا با تنظیمات قبلی کار می‌کند.</div>' : ''}
      <div class="row" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="primary" data-a="resume" ${st.code_upgrade_required ? 'disabled' : ''}>درخواست ادامه</button><button data-a="reduce_only">فقط کاهش موقعیت</button><button class="danger" data-a="stop">توقف موتور</button></div>
      <div class="faint" style="font-size:11px;margin-top:6px">«توقف» سفارش‌های باز خود موتور را لغو می‌کند اما موجودی را نمی‌فروشد. «ادامه» همان دفتر را باز می‌کند.</div><div id="cmsg" class="muted"></div>`;
    $$('#ctl button[data-a]').forEach(b => b.onclick = async () => { if (!confirmInline(b)) return; try { await api('/api/live/control', { body: { action: b.dataset.a } }); $('#cmsg').textContent = 'ثبت شد'; refresh(); } catch (e) { $('#cmsg').textContent = e.message; } });
    const up = await safe(() => api('/api/live/upgrade'), $('#upg'));
    if (up) {
      $('#upg').innerHTML = up.applied ? '<div class="notice green">اجرای فعلی با نسخهٔ نصب‌شده یکسان است.</div>' : `
        ${up.blockers.length ? `<div class="notice red">${up.blockers.map(esc).join('<br>')}</div>` : ''}
        <div class="muted" style="font-size:12px;margin:8px 0">نسخهٔ اجرا <span class="mono">${esc(up.run_source_sha256.slice(0, 12))}</span> → نصب‌شده <span class="mono">${esc(up.installed_source_sha256.slice(0, 12))}</span></div>
        ${up.staged_credentials && (up.staged_credentials.wallex || up.staged_credentials.llm) ? `<div class="notice" style="font-size:12px;margin-bottom:8px">کلید در صف: ${up.staged_credentials.wallex ? 'والکس ' : ''}${up.staged_credentials.llm ? esc(up.staged_credentials.provider) : ''} — پس از تطبیق فقط‌خواندنی جایگزین می‌شود.</div>` : ''}
        <details open><summary>${n0(Object.keys(up.config_changes).length)} تغییر تنظیمات و ${n0(Object.keys(up.binding_changes).length)} تغییر مجوز</summary><div class="table-wrap"><table><thead><tr><th>کلید</th><th>قبلی</th><th>جدید</th></tr></thead><tbody>
        ${Object.entries({ ...up.binding_changes, ...up.config_changes }).map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td class="mono">${esc(JSON.stringify(v.from))}</td><td class="mono">${esc(JSON.stringify(v.to))}</td></tr>`).join('')}</tbody></table></div></details>
        <div class="form" style="margin-top:10px"><label>برای تأیید بنویسید: <b>${esc(up.confirmation)}</b></label><input id="upc"><div class="row"><button class="primary" id="upgo">تطبیق فقط‌خواندنی و ارتقا</button><span id="upmsg" class="muted"></span></div>
        <div class="faint" style="font-size:11px">ارتقا سفارشی ارسال نمی‌کند و موتور را روشن نمی‌کند؛ پس از موفقیت «درخواست ادامه» را بزنید.</div></div>`;
      const go = $('#upgo'); if (go) go.onclick = async () => { try { const r = await api('/api/live/upgrade', { body: { confirmation: $('#upc').value } }); $('#upmsg').textContent = r.already_applied ? 'قبلاً اعمال شده' : 'ارتقا ثبت شد؛ اکنون می‌توانید «درخواست ادامه» را بزنید.'; refresh(); } catch (e) { $('#upmsg').textContent = e.message; } };
    }
    const np = snap.native_protection || {};
    $('#nat').innerHTML = `<div class="muted" style="font-size:12px">وضعیت: ${esc(np.status || 'ندارد')} · تأیید صرافی: ${np.exchange_confirmed ? 'بله' : 'خیر'}${np.stop_price ? ` · ماشه <span class="mono">${esc(np.stop_price)}</span> · کف فروش <span class="mono">${esc(np.price)}</span> (${pct((np.price / np.stop_price - 1) * 100, 1)})` : ''}${np.exit_requested ? ' · <span class="warn">در حال لغو برای جایگزینی/خروج</span>' : ''}</div>
      <div class="faint" style="font-size:11px;margin-top:4px">محافظ فروش سریع: پس از فعال شدن ماشه، سفارش با کف ۵٪ زیر ماشه فوراً با بهترین خریدهای دفتر سفارش پر می‌شود (مثل Stop-Market، با کف قیمت).</div>
      <div class="row" style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap"><button id="npv">پیش‌نمایش محافظ</button>${np.exchange_confirmed && !np.exit_requested ? '<button id="nprep">جایگزینی با محافظ فروش سریع</button>' : ''}</div><div id="npbox"></div>`;
    if ($('#nprep')) $('#nprep').onclick = () => { $('#npbox').innerHTML = `<div class="form" style="margin-top:8px"><div class="muted" style="font-size:12px">موتور محافظ فعلی را لغو می‌کند (فقط با تطبیق GET)؛ سپس «پیش‌نمایش محافظ» محافظ جدید با کف عمیق‌تر را پیشنهاد می‌دهد و با تأیید شما ثبت می‌شود. در این فاصله حد ضرر نرم‌افزاری هر ۳۰ ثانیه فعال است.</div><label>تأیید: <b>جایگزینی محافظ TRX با فروش سریع</b></label><input id="nprc"><button class="primary" id="nprgo">ثبت درخواست</button><span id="nprm" class="muted"></span></div>`;
      $('#nprgo').onclick = async () => { try { const r = await api('/api/live/native-stop/replace', { body: { confirmation: $('#nprc').value } }); $('#nprm').textContent = r.next; } catch (e) { $('#nprm').textContent = e.message; } }; };
    $('#npv').onclick = async () => { try { const p = await api('/api/live/native-stop/preview', { body: {} }); $('#npbox').innerHTML = `<pre class="reasoning">${esc(JSON.stringify(p.preview, null, 2))}</pre><div class="form"><label>تأیید: <b>${esc(p.confirmation)}</b></label><input id="npc"><button class="primary" id="npa">ثبت محافظ</button><span id="npm" class="muted"></span></div>`;
      $('#npa').onclick = async () => { try { await api('/api/live/native-stop/approve', { body: { preview_id: p.preview_id, confirmation: $('#npc').value } }); $('#npm').textContent = 'تأیید ثبت شد؛ موتور در چرخهٔ بعد ارسال می‌کند.'; } catch (e) { $('#npm').textContent = e.message; } }; } catch (e) { $('#npbox').innerHTML = `<div class="notice red">${esc(e.message)}</div>`; } };
    $('#setup').innerHTML = state.run_id ? `<div class="muted" style="font-size:12.5px">یک اجرای فعال حساب وجود دارد؛ کلیدها و حساب به آن متصل‌اند. کلید جدید، سرویس‌دهندهٔ LLM و مدل را در <a href="#settings">«تنظیمات و کلیدها»</a> ثبت کنید؛ با «ارتقای اجرای فعلی» اعمال می‌شوند. شروع اجرای تازه فقط برای حساب بدون دارایی ممکن است.</div>` :
      `<div class="form"><input id="kw" type="password" placeholder="کلید API والکس"><input id="ka" type="password" placeholder="کلید AvalAI"><button id="ks">ذخیرهٔ کلیدها</button><button id="kpf">بررسی فقط‌خواندنی</button><span id="kmsg" class="muted"></span></div>`;
    if ($('#ks')) { $('#ks').onclick = async () => { try { await api('/api/live/credentials', { body: { wallex: $('#kw').value || null, avalai: $('#ka').value || null } }); $('#kmsg').textContent = 'ذخیره شد'; } catch (e) { $('#kmsg').textContent = e.message; } };
      $('#kpf').onclick = async () => { try { const r = await api('/api/live/preflight', { body: {} }); $('#kmsg').textContent = r.ok ? 'بررسی موفق' : r.blocking_reasons.join('؛ '); } catch (e) { $('#kmsg').textContent = e.message; } }; }
    const ev = await safe(() => api('/api/live/evidence?tail=true'));
    if (ev) $('#audit').innerHTML = ev.events.slice().reverse().map(e => `<div class="item"><span class="t">#${e.seq}</span><span><b>${esc(e.kind)}</b> <span class="faint mono" style="font-size:11px;word-break:break-all;display:block;text-align:left">${esc(JSON.stringify(e.payload).slice(0, 260))}</span></span></div>`).join('');
  }
  every(10000, refresh);
}
function confirmInline(b) { if (b.dataset.armed) { delete b.dataset.armed; return true; } b.dataset.armed = '1'; const t = b.textContent; b.textContent = 'تأیید؟ دوباره بزنید'; setTimeout(() => { if (b.dataset.armed) { delete b.dataset.armed; b.textContent = t; } }, 4000); return false; }
function who() { const w = $('#who'); if (w) w.textContent = S.authenticated ? 'اپراتور وارد شده' : 'عمومی (فقط‌خواندنی)'; }

// ------------------------------------------------------------------ boot
(async function boot() {
  shell(); await loadSession(); who();
  safe(pollLive);
  setInterval(countdown, 1000); setInterval(() => { if (!document.hidden) safe(pollLive); }, 10000);
  addEventListener('hashchange', route); route();
})();
