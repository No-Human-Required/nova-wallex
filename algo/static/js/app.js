// الگوریتمیک — Nova's dashboard for every user bot, plus bots, account and back office.
import { S, api, loadSession, n0, n2, n4, toman, pct, price, signCls, when, clock, hm, ago, esc, h, $, $$, sym,
  STATUS_FA, REASON_FA, PHASE_FA, SIDE_FA, BOT_STATUS, botChip, download, tween, wxButton } from './core.js';
import { LineChart, CandleChart } from '/nova/js/charts.js';
import { background, Radar, ART } from '/nova/js/fx.js';
import { pageHow } from './how.js';
import { labSection } from './lab.js';
import { pageStudio } from './studio.js';
import { pageLanding } from './landing.js';
import { pageLogin, pageBots, pageBuilder, pageKeys, pageBilling, pageProfile, toast, act, liveRequest, scheduleModal, scheduleText } from './account.js';
import { ADMIN_PAGES } from './admin.js';

// [key, title, icon, needs a bot]
const PAGES = [
  ['live', 'داشبورد ربات', '◉', true], ['how', 'نحوهٔ تصمیم‌گیری', '⟲', true], ['journal', 'ژورنال معاملات', '☰', true], ['ai', 'تصمیم‌های AI', '✦', true],
  ['strategies', 'استراتژی‌ها', '◇'], ['market', 'بازار زنده', '▦'], ['studio', 'استودیوی استراتژی', '✎'], ['research', 'بک‌تست و پژوهش', '∿'],
  ['bots', 'ربات‌های من', '⚙'], ['keys', 'کلیدهای صرافی', '⚿'], ['billing', 'اشتراک', '◈'], ['profile', 'حساب من', '☺']
];
const ADMIN = [['admin', 'نمای کلی', '▤'], ['admin-bots', 'ربات‌ها و تأیید', '✓'], ['admin-users', 'کاربران', '☷'], ['admin-plans', 'پلن‌ها', '◈'],
  ['admin-payments', 'پرداخت‌ها', '₮'], ['admin-settings', 'تنظیمات', '⚙'], ['admin-audit', 'رویدادها', '≡']];
const EXTRA = { new: 'ساخت ربات', edit: 'ویرایش ربات' };
const CTX = { timers: [], disposables: [], live: null, journal: null };
const STRAT = () => (CTX.live && CTX.live.strategies) || CTX.catalog || { strategies: {}, regimes: {} };
const sName = k => (STRAT().strategies[k] || {}).fa || ({ legacy_trend6: 'روند ۶ساعته (نسخهٔ قبلی)', native_protection: 'محافظ صرافی' }[k] || k || '—');
const famChip = k => { const f = (STRAT().strategies[k] || {}).family; return f ? `<span class="chip ${f === 'smart_money' ? 'smc' : 'ind'}">${f === 'smart_money' ? 'SMC' : f === 'hybrid' ? 'ترکیبی' : 'اندیکاتور'}</span>` : ''; };
const reason = r => REASON_FA[r] || sName(r) || r || '—';

function every(ms, fn) { fn(); const id = setInterval(() => { if (!document.hidden) fn(); }, ms); CTX.timers.push(id); }
function dispose() { CTX.timers.forEach(clearInterval); CTX.timers = []; CTX.disposables.forEach(d => d.destroy && d.destroy()); CTX.disposables = []; }
const keep = x => (CTX.disposables.push(x), x);
async function safe(fn, node) { try { return await fn(); } catch (e) { if (node) node.innerHTML = `<div class="notice red">${esc(e.message)}</div>`; return null; } }
const ctx = { every, keep, safe, sName, famChip, STRAT, route: () => route(), refreshBots: () => refreshBots() };

// ------------------------------------------------------------------ shell
function shell() {
  const u = S.user;
  const link = ([k, t, i]) => `<a href="#${k}" data-nav="${k}"><span class="ico">${i}</span>${t}</a>`;
  document.body.innerHTML = `<canvas id="fx" aria-hidden="true"></canvas>
  <div class="shell"><aside class="side"><a class="brand" href="#live"><img src="/assets/mark.svg" alt=""><div><b>${esc(S.meta.site_name)}</b><small>ALGORITHMIC TRADING BOTS</small></div></a>
  <nav class="tabs">${PAGES.slice(0, 8).map(link).join('')}<div class="navsec">حساب</div>${PAGES.slice(8).map(link).join('')}
    ${u.role === 'admin' ? `<div class="navsec">بک‌آفیس</div>${ADMIN.map(link).join('')}` : ''}</nav>
  <div class="side-foot"><div id="ver">نسخهٔ ${esc(S.meta.version)}</div><div>فقط اسپات · بدون اهرم · دارایی در حساب خودتان</div></div></aside>
  <main>${S.meta.notice ? `<div class="notice" style="margin-bottom:12px">${esc(S.meta.notice)}</div>` : ''}<header class="top"><h1 id="title"></h1>
  <span class="pill hidden" id="engpill"><span class="dot"></span><span>…</span></span>
  <span class="pill hidden" id="schedpill" title="بازهٔ زمانی اجرای ربات">⏳ <span id="cdl">…</span> <span class="countdown" id="cd"></span></span>
  <label class="pill botpick hidden" id="botpick" title="رباتی که داشبورد نشان می‌دهد"><span class="faint">ربات</span><select id="botsel"></select></label>
  <span class="spacer"></span><a class="pill" id="who" href="#profile"></a></header><div id="page"></div></main></div><div id="toast" class="toast hidden"></div>`;
  background($('#fx'));
  $('#botsel').onchange = () => { S.viewing = null; selectBot($('#botsel').value); route(); };
  who();
}
function who() {
  const u = S.user; const w = $('#who'); if (!w || !u) return;
  w.innerHTML = `${esc(u.name || u.phone)} · ${esc(u.plan ? u.plan.name : 'بدون پلن')}${u.role === 'admin' ? ' · <b class="warn">ادمین</b>' : ''}`;
}
function selectBot(id) {
  S.bot = id || null; CTX.live = null;
  try { id ? localStorage.setItem('algo.bot', id) : localStorage.removeItem('algo.bot'); } catch (_) { /* optional */ }
}
async function refreshBots() {
  const bots = await api('/api/bots').catch(() => null); if (!bots) return S.bots;
  S.bots = bots.filter(b => b.status !== 'deleted');
  let saved = null; try { saved = localStorage.getItem('algo.bot'); } catch (_) { /* optional */ }
  if (!S.bots.some(b => b.id === S.bot) && S.bot !== S.viewing) selectBot((S.bots.find(b => b.id === saved) || S.bots[0] || {}).id);
  const sel = $('#botsel');
  if (sel) sel.innerHTML = S.bots.map(b => `<option value="${b.id}" ${b.id === S.bot ? 'selected' : ''}>${esc(b.name)} · ${b.mode === 'live' ? 'واقعی' : 'آزمایشی'}</option>`).join('');
  return S.bots;
}

function parse() {
  const [raw, query] = (location.hash.slice(1) || '').split('?');
  const [name, arg] = raw.split('/');
  return { name, arg, q: Object.fromEntries(new URLSearchParams(query || '')) };
}

async function route() {
  dispose();
  const { name, arg, q } = parse();
  if (!S.user) {
    document.body.className = 'land-body';
    if (name === 'login') return pageLogin(onLogin);
    return pageLanding();
  }
  if (name === 'login' || name === 'home' || !name) { location.hash = '#live'; return; }
  if (!$('#page')) shell();
  document.body.className = '';
  const page = name;
  const def = PAGES.find(p => p[0] === page) || ADMIN.find(p => p[0] === page);
  if (!def && !EXTRA[page]) { location.hash = '#live'; return; }
  if (page.startsWith('admin') && S.user.role !== 'admin') { location.hash = '#live'; return; }
  $$('nav.tabs a').forEach(a => a.classList.toggle('active', a.dataset.nav === page || (page in EXTRA && a.dataset.nav === 'bots')));
  $('#title').textContent = def ? def[1] : EXTRA[page];
  const needsBot = def && def[3];
  $('#botpick').classList.toggle('hidden', !needsBot || !S.bots.length);
  $('#engpill').classList.toggle('hidden', !needsBot || !S.bot);
  $('#schedpill').classList.toggle('hidden', !needsBot || !S.bot);
  const root = $('#page'); root.innerHTML = ''; root.className = 'fade-in';
  if (needsBot && !S.bot) {
    root.innerHTML = `<section class="panel glow" style="max-width:640px"><div class="body" style="padding:26px">
      <h2 style="margin-top:0">هنوز رباتی ندارید</h2><p class="muted">داشبورد، جریان تصمیم، ژورنال و تصمیم‌های AI برای هر ربات شما ساخته می‌شوند. یک ربات بسازید، آزمایشی اجرا کنید و همه‌چیز را همین‌جا زنده ببینید.</p>
      <div class="row" style="display:flex;gap:8px"><a href="#new"><button class="primary">＋ ساخت اولین ربات</button></a><a href="#research"><button>بک‌تست بدون ربات</button></a><a href="#studio"><button>استودیوی استراتژی</button></a></div></div></section>`;
    return;
  }
  const pages = { live: pageLive, how: r => pageHow(r, ctx), journal: pageJournal, ai: pageAI, strategies: pageStrategies, market: pageMarket,
    studio: r => pageStudio(r, ctx), research: pageResearch, bots: r => pageBots(r, ctx), new: r => pageBuilder(r, ctx, null), edit: r => pageBuilder(r, ctx, arg),
    keys: r => pageKeys(r, ctx), billing: r => pageBilling(r, ctx, q), profile: r => pageProfile(r, ctx, onLogout), ...ADMIN_PAGES(ctx, q) };
  pages[page](root);
}

async function onLogin() { await refreshBots(); safe(async () => { CTX.catalog = await api('/api/public/strategies'); }); shell(); route(); }
function onLogout() { S.user = null; S.bot = null; S.bots = []; location.hash = '#home'; route(); }

async function pollLive() {
  if (!S.bot) return null;
  const d = await api('/api/public/live');
  CTX.live = d;
  const e = d.engine || {}; const running = e.desired === 'running' && e.status !== 'blocked' && (e.heartbeat_age ?? 99) < 90;
  const pill = $('#engpill');
  if (pill) pill.innerHTML = `<span class="dot ${running ? 'on' : e.status === 'blocked' || e.last_error ? 'off' : 'warn'}"></span><span>${esc(d.bot.name)}: ${esc((BOT_STATUS[d.bot.status] || [d.bot.status])[0])}</span>`;
  return d;
}

// Start / pause / stop / close / edit for the selected bot, inside the live hero.
function botControls(node, d) {
  if (S.viewing === d.bot.id && !S.bots.some(b => b.id === d.bot.id)) { node.innerHTML = '<span class="chip y">نمای ادمین · فقط خواندنی</span> ' + botChip(d.bot.status); return; }
  const b = (S.bots.find(x => x.id === d.bot.id)) || {}; const st = d.bot.status; const hasPos = (d.snapshot.holdings || []).some(x => +x.basis > 0);
  const can = { start: ['stopped', 'paused', 'blocked'].includes(st), pause: st === 'running', stop: ['running', 'paused', 'pending_approval', 'closing', 'scheduled'].includes(st),
    close: hasPos && ['running', 'paused', 'stopped'].includes(st), edit: ['stopped', 'blocked'].includes(st) };
  const key = JSON.stringify([st, hasPos, b.live_approved, d.bot.schedule]);
  if (node.dataset.k === key) return; node.dataset.k = key;
  node.innerHTML = `<div class="muted" style="margin-bottom:4px">${botChip(st)} <span class="chip ${d.bot.mode === 'live' ? 'y' : ''}">${d.bot.mode === 'live' ? 'واقعی' : 'آزمایشی'}</span> <span class="chip">${esc(d.bot.timeframe)}</span></div>
    <div class="faint" style="font-size:11.5px;margin-bottom:6px">⏳ ${esc(scheduleText(d.bot.schedule, st))} · <a href="javascript:void 0" id="schedit">تغییر بازه</a></div>
    <div class="row" style="display:flex;gap:6px;flex-wrap:wrap">${can.start ? '<button class="primary" data-a="start">▶ شروع</button>' : ''}${can.pause ? '<button data-a="pause" title="ورود جدید نه؛ خروج‌ها مدیریت می‌شوند">❚❚ توقف ورود</button>' : ''}${can.stop ? '<button data-a="stop">■ توقف</button>' : ''}${can.close ? '<button class="danger" data-a="close">فروش همه</button>' : ''}${can.edit ? `<a href="#edit/${d.bot.id}"><button>ویرایش</button></a>` : ''}</div>
    ${d.bot.mode === 'live' && !b.live_approved ? `<div id="livereq" style="margin-top:6px"></div>` : ''}`;
  $$('[data-a]', node).forEach(x => x.onclick = async () => {
    const a = x.dataset.a;
    const ask = { close: 'همهٔ موقعیت‌ها با قیمت بازار فروخته شوند؟', stop: d.bot.mode === 'live' ? 'ربات متوقف شود؟ موقعیت‌های باز در حساب صرافی می‌مانند و دیگر مدیریت نمی‌شوند.' : 'ربات متوقف شود؟' }[a];
    if (ask && !confirm(ask)) return;
    if (await act(() => api(`/api/bots/${d.bot.id}/${a}`, { body: {} }), 'انجام شد')) { node.dataset.k = ''; await refreshBots(); safe(pollLive); }
  });
  $('#schedit', node).onclick = () => b.id && scheduleModal(b, async () => { node.dataset.k = ''; await refreshBots(); safe(pollLive); });
  if ($('#livereq', node)) liveRequest($('#livereq', node), b, () => { node.dataset.k = ''; refreshBots(); });
}

const SYS_FA = { entry_skipped: 'ورود انجام نشد', ai_unavailable: 'AI در دسترس نبود', ai_quota_exhausted: 'سهمیهٔ AI تمام شد', data_unavailable: 'دادهٔ کندل در دسترس نبود',
  order_unknown: 'سفارش با پاسخ نامعلوم', order_rejected: 'سفارش رد شد', bot_blocked: 'ربات مسدود شد', bot_stopped: 'ربات متوقف شد', bot_paused: 'ربات فقط مدیریت خروج' };
function systemText(s) {
  const d = s.detail || {};
  const extra = d.reason ? ' — ' + esc(REASON_FA[d.reason] || d.reason) : d.symbol ? ' — ' + sym(d.symbol) : '';
  return 'سیستم: ' + esc(SYS_FA[s.kind] || s.kind) + extra;
}

// ------------------------------------------------------------------ live
function pageLive(root) {
  root.innerHTML = `
  <div id="upgradeNote"></div>
  <section class="panel glow" style="margin-bottom:14px"><div class="hero">
    <div><div class="muted" id="eqlabel">ارزش لحظه‌ای ربات</div><div class="big" id="eq">—</div><div class="muted" id="eqnote"></div></div>
    <div><div class="muted">سود / زیان نسبت به سرمایهٔ ربات</div><div class="delta" id="pnl">—</div></div>
    <div><div class="muted">سود محقق‌شده</div><div class="delta" id="real">—</div></div>
    <div style="margin-inline-start:auto"><div id="botctl"></div></div>
  </div></section>
  <section class="grid g6" style="margin-bottom:14px" id="kpis"></section>
  <section class="grid g3" style="margin-bottom:14px">
    <div class="panel span2"><div class="head"><h2>منحنی ارزش حساب</h2><span class="sub">ارزش ربات در هر چرخهٔ اجرا (نقد + موجودی به بهترین قیمت خرید)؛ مثلث‌ها خرید و فروش‌اند</span>
      <div class="tools tabs-inline" id="eqres"><button data-r="auto" class="on">خودکار</button><button data-r="5">۵ دقیقه</button><button data-r="15">۱۵ دقیقه</button></div></div>
      <div class="body"><canvas class="chart tall" id="eqchart"></canvas><div class="faint" id="eqmeta" style="font-size:11px"></div></div></div>
    <div class="panel"><div class="head"><h2>اسکنر بازار</h2><span class="sub" id="scanmeta"></span></div><div class="body"><canvas class="radar" id="radar"></canvas><div id="regime"></div></div></div>
  </section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>موقعیت‌های باز</h2><span class="sub">نمودار دقیقه‌ای زنده، ورود، حد ضرر فعال و سه حد سود</span></div><div class="body" id="positions"><div class="skeleton" style="height:120px"></div></div></section>
  <section class="grid g2" style="margin-bottom:14px">
    <div class="panel"><div class="head"><h2>آخرین تصمیم موتور AI</h2><a class="tools" href="#ai">همهٔ تصمیم‌ها ←</a></div><div class="body" id="lastai"></div></div>
    <div class="panel"><div class="head"><h2>نامزدهای آخرین کندل</h2><span class="sub">ستاپ‌های معتبر پیش از تأیید AI</span></div><div class="body table-wrap" id="cands"></div></div>
  </section>
  <section class="grid g2">
    <div class="panel"><div class="head"><h2>معاملات اخیر</h2><a class="tools" href="#journal">ژورنال کامل ←</a></div><div class="body table-wrap" id="recent"></div></div>
    <div class="panel"><div class="head"><h2>رویدادهای ربات</h2></div><div class="body feed scroll" id="feed" style="max-height:340px"></div></div>
  </section>`;
  const eq = keep(new LineChart($('#eqchart'), { baseline: 5000000, baselineLabel: 'سرمایهٔ اولیه', fmt: n0, relative: true }));
  const radar = keep(new Radar($('#radar')));
  let res = 'auto';
  $('#eqres').onclick = e => { const b = e.target.closest('button'); if (!b) return; res = b.dataset.r; $$('#eqres button').forEach(x => x.classList.toggle('on', x === b)); loadEq(); };
  async function loadEq() {
    const d = await safe(() => api('/api/public/equity?resolution=' + res), $('#eqmeta'));
    if (!d) return;
    if (d.points.length < 2) { $('#eqmeta').textContent = 'منحنی پس از چند چرخهٔ اجرای ربات رسم می‌شود.'; return; }
    eq.o.baselineLabel = 'سرمایهٔ اولیه ' + n0(d.capital_tmn);
    eq.set(d.points.map(p => [p[0], p[1]]), { markers: d.fills, baseline: d.capital_tmn || 5000000 });
    $('#eqmeta').textContent = `${n0(d.points.length)} نقطه · تفکیک ${n0(d.resolution)} دقیقه · ${d.method || ''}`;
  }
  every(30000, loadEq);
  const charts = {};
  every(5000, async () => {
    const d = await safe(pollLive); if (!d) return;
    const s = d.snapshot || {}; const run = d.run;
    botControls($('#botctl'), d);
    $('#eqlabel').textContent = 'ارزش لحظه‌ای ربات «' + d.bot.name + '»' + (d.bot.mode === 'paper' ? ' (آزمایشی)' : ' (واقعی)');
    $('#upgradeNote').innerHTML = false ? `<div class="notice" style="margin-bottom:14px">نسخهٔ جدید موتور نصب شده است. اجرای فعلی تا تأیید ارتقا در «کنترل اپراتور» متوقف می‌ماند؛ دفتر، موقعیت‌ها و سفارش‌ها حفظ شده‌اند. <a href="#operator">بررسی و ارتقا ←</a></div>` : (d.engine.last_error ? `<div class="notice red" style="margin-bottom:14px">${esc(d.engine.last_error)}</div>` : '');
    const capital = +(run && run.limits && run.limits.capital_tmn) || 5000000;
    let equity = s.equity_tmn !== null && s.equity_tmn !== undefined ? +s.equity_tmn : null;
    if (equity === null) { equity = +s.cash_tmn || capital; for (const x of s.holdings || []) equity += +(x.value_tmn || x.basis || 0); }
    tween($('#eq'), equity, v => toman(v));
    $('#eqnote').textContent = s.at ? 'آخرین چرخهٔ ربات: ' + ago(s.at) + (s.valuation === 'live_bid' ? ' · ارزش با قیمت لحظه‌ای' : ' · ارزش آخرین چرخه') : '';
    const p = equity - capital; $('#pnl').innerHTML = `<span class="${signCls(p)}">${toman(p)} (${pct(p / capital * 100, 3)})</span>`;
    $('#real').innerHTML = `<span class="${signCls(s.realized_pnl_tmn)}">${toman(s.realized_pnl_tmn)}</span>`;
    const fees = Object.entries(s.fees_by_asset || {}).map(([a, v]) => n4(v) + ' ' + a).join(' + ') || '۰';
    const k = [
      ['وضعیت ربات', (BOT_STATUS[d.bot.status] || [d.bot.status])[0], d.engine.heartbeat_age !== null ? 'آخرین چرخه ' + n0(d.engine.heartbeat_age) + ' ثانیه پیش' : (d.bot.mode === 'live' ? 'واقعی' : 'آزمایشی')],
      ['رژیم بازار', d.latest_scan && d.latest_scan.regime ? d.latest_scan.regime.fa : '—', d.latest_scan && d.latest_scan.regime ? 'پهنا ' + pct(d.latest_scan.regime.breadth * 100, 0) : 'پس از اولین کندل'],
      ['نقد ربات', toman(s.cash_tmn), 'سرمایهٔ اولیه ' + toman(capital)],
      ['حداکثر افت', n2(s.max_drawdown_percent) + '٪', 'از اوج منحنی ارزش'],
      ['تعداد پرشدن', n0(s.fill_count), 'کارمزد: ' + fees],
      ['سهمیهٔ AI این ماه', n0(d.ai_calls_used) + ' / ' + n0(run && run.limits ? run.limits.ai_max_calls : 0), run && run.policy === 'adaptive_ai' ? 'فیلتر AI روشن' : 'فیلتر AI این ربات خاموش']
    ];
    $('#kpis').innerHTML = k.map(([a, b, c]) => `<div class="panel kpi"><div class="label">${a}</div><div class="value">${esc(b)}</div><div class="note">${esc(c)}</div></div>`).join('');
    // regime + radar
    const sc = d.latest_scan;
    radar.set(sc ? sc.top : [], d.bot.symbols.length);
    $('#scanmeta').textContent = sc ? 'اسکن کندل ' + hm(sc.time) + ' · ' + d.bot.timeframe + ' · ' + n0(d.bot.symbols.length) + ' نماد' : '';
    if (sc && sc.regime) {
      const r = sc.regime;
      $('#regime').innerHTML = `<div class="row" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px"><span class="chip y">${esc(r.fa)}</span><span class="chip">BTC ۲۴س: ${pct((r.btc_r24_bps || 0) / 100)}</span><span class="chip">حداکثر ${n0(r.max_positions)} موقعیت</span></div>
        <div style="margin-top:8px;font-size:12px">${(r.strategies || []).map(x => `<div>${famChip(x)} ${esc(sName(x))}</div>`).join('')}</div>`;
    } else $('#regime').innerHTML = `<div class="faint" style="font-size:12px">رژیم و نامزدها پس از بسته شدن اولین کندل در حال اجرای ربات نمایش داده می‌شوند.</div>`;
    // positions
    const meta = d.positions_meta || {}; const holds = (s.holdings || []).filter(x => x.asset !== 'TMN');
    const pos = $('#positions');
    if (!holds.length) { pos.innerHTML = '<div class="empty">موقعیت بازی وجود ندارد؛ سرمایهٔ ربات به تومان نگهداری می‌شود.</div>'; for (const k in charts) delete charts[k]; }
    else {
      for (const x of holds) {
        const m = meta[x.asset] || {}; const id = 'pos-' + x.asset;
        const dust = (d.dust || {})[x.asset];
        const value0 = +(x.value_tmn || 0);
        if ($('#' + id) && !!$('#' + id).closest('.dustrow') !== !!dust) { const old = $('#' + id).closest('.dustrow') || $('#' + id); old.remove(); delete charts[x.asset]; }
        if (!$('#' + id)) {
          if (!pos.querySelector('.pos-row')) pos.innerHTML = '';
          const row = `<div class="pos-row grid g3" id="${id}" style="margin-bottom:12px"><div class="span2"><canvas class="chart" id="${id}-c"></canvas></div><div id="${id}-i"></div></div>`;
          if (dust) {
            // Unsellable residue: one compact line, expanded on demand.
            let list = $('#dustlist'); if (!list) { list = h('<div id="dustlist"></div>'); pos.appendChild(list); }
            const box = h(`<details class="dustrow" id="dust-${x.asset}"><summary><span class="arrow">▸</span> <b>ریزهٔ ${esc(x.asset)}</b> <span class="mono">${n4(x.qty)}</span> · <span id="dustv-${x.asset}">${toman(value0)}</span> <span class="faint">· زیر حداقل سفارش والکس؛ قابل فروش نیست و جای موقعیت نمی‌گیرد</span></summary>${row}</details>`);
            list.appendChild(box);
            box.addEventListener('toggle', () => {
              box.querySelector('.arrow').textContent = box.open ? '▾' : '▸';
              if (box.open && !charts[x.asset]) { charts[x.asset] = keep(new CandleChart($('#' + id + '-c'), {})); const q = box._pending; if (q) { charts[x.asset].pending = q; loadCandles(charts[x.asset]); } }
            });
          } else {
            const list = $('#dustlist'); const node = h(row); list ? pos.insertBefore(node, list) : pos.appendChild(node);
            charts[x.asset] = keep(new CandleChart($('#' + id + '-c'), {}));
          }
        }
        if (dust && $('#dustv-' + x.asset)) $('#dustv-' + x.asset).textContent = toman(value0);
        const unit = m.basis_unit ? +m.basis_unit : +x.basis / +x.qty; const value = value0; const pnl = value ? value - +x.basis : null;
        const stop = m.stop_price ? +m.stop_price : m.peak_unit && m.stop ? +m.peak_unit * (1 - +m.stop) : null;
        $('#' + id + '-i').innerHTML = `<div style="font-size:18px;font-weight:700">${sym(m.symbol || x.asset)} ${m.margin ? `<span class="chip ${m.side === 'short' ? 'bad' : 'ok'}">${m.side === 'short' ? 'شورت' : 'لانگ'} ×${n0(m.leverage)}</span>` : ''} ${famChip(m.strategy)} ${wxButton(m.symbol)}</div>
          ${dust ? `<div class="notice" style="margin:8px 0;font-size:12px">ریزهٔ باقی‌مانده پس از فروش: ارزش ${toman(value)} کمتر از حداقل سفارش صرافی (${toman(dust.min_notional_tmn)}) است و قابل فروش نیست؛ جای موقعیت جدید را نمی‌گیرد.</div>` : ''}
          <div class="muted" style="font-size:12px">${esc(sName(m.strategy || 'legacy_trend6'))}</div>
          <table style="margin-top:8px"><tr><td class="muted">مقدار</td><td>${n4(x.qty)} ${esc(x.asset)}</td></tr>
          <tr><td class="muted">${m.margin ? 'وثیقه / ارزش موقعیت' : 'بهای تمام‌شده'}</td><td>${toman(x.basis)} ${m.margin ? '/ ' + toman(m.notional) : ''} <span class="faint">(ورود ${price(unit)})</span></td></tr>
          ${m.margin ? `<tr><td class="muted">قیمت لیکویید</td><td class="neg">${m.liq_price && +m.liq_price ? price(m.liq_price) + ' <span class="faint">(' + pct((+m.liq_price / unit - 1) * 100, 1) + ')</span>' : '—'}</td></tr>` : ''}
          <tr><td class="muted">ارزش فعلی</td><td>${toman(value)}</td></tr>
          <tr><td class="muted">سود/زیان باز</td><td class="${signCls(pnl)}">${pnl === null ? '—' : toman(pnl) + ' (' + pct(pnl / +x.basis * 100) + ')'}</td></tr>
          <tr><td class="muted">${m.margin ? 'حد ضرر فعال' : 'حد ضرر شناور'}</td><td>${stop ? price(stop) + ' <span class="faint">(' + (m.margin ? pct((stop / unit - 1) * 100, 1) + ' از ورود؛ روی صرافی هم ثبت است' : pct(+m.stop * 100, 1) + ' زیر اوج') + ')</span>' : '—'}</td></tr>
          <tr><td class="muted">سه حد سود</td><td>${m.tp ? m.tp.map((v, i) => `<span class="${(+m.tp_stage || 0) > i ? 'pos' : ''}">TP${i + 1} ${price(v)} <span class="faint">(${pct((+v / unit - 1) * 100, 1)})</span></span>`).join('<br>') : 'در چرخهٔ بعدی تعیین می‌شود'}</td></tr>
          <tr><td class="muted">حد ضرر پله‌ای</td><td>${m.sl_floor ? '<span class="pos">' + price(m.sl_floor) + '</span> <span class="faint">(مرحله ' + n0(m.tp_stage) + ')</span>' : 'پس از +1R یا TP1 به سربه‌سر می‌رود'}</td></tr>
          ${m.ai && m.ai.ai_reason ? `<tr><td class="muted">دلیل AI</td><td style="font-size:12px">${esc(m.ai.ai_reason)} <span class="faint">(${n2(m.ai.ai_confidence)})</span></td></tr>` : ''}
          <tr><td class="muted">زمان ورود</td><td>${when(m.opened_at)}</td></tr>
          <tr><td class="muted">دلیل خروج معلق</td><td>${m.exit_reason ? esc(reason(m.exit_reason)) : '—'}</td></tr></table>`;
        if (dust && m.symbol) { const box = $('#dust-' + x.asset); if (box) box._pending = { symbol: m.symbol, entry: unit, stop: Math.max(stop || 0, m.sl_floor ? +m.sl_floor : 0) || stop, tp: (m.tp || (m.target ? [m.target] : [])).map(Number) }; }
        if (m.symbol && charts[x.asset]) { const first = !charts[x.asset].pending; charts[x.asset].pending = { symbol: m.symbol, entry: unit, stop: Math.max(stop || 0, m.sl_floor ? +m.sl_floor : 0) || stop, tp: (m.tp || (m.target ? [m.target] : [])).map(Number) }; if (first) loadCandles(charts[x.asset]); }
      }
    }
    // last AI + candidates
    $('#lastai').innerHTML = d.latest_decision ? decisionCard(d.latest_decision, true) : `<div class="empty">${d.bot.ai_filter ? 'هنوز تصمیمی ثبت نشده است.' : 'فیلتر AI برای این ربات خاموش است؛ ستاپ‌های بالای حد کیفیت مستقیم وارد می‌شوند.'}</div>`;
    const cov = (sc && sc.coverage) || {}; const scanned = (cov.signal || 0) + (cov.eligible_no_signal || 0);
    const scanNote = !['running', 'paused'].includes(d.bot.status) && sc ? `<div class="notice" style="font-size:12px;margin-bottom:8px">ربات اکنون اجرا نمی‌شود؛ این آخرین اسکن ثبت‌شدهٔ آن است (${when(sc.time)}).</div>` : false ? `<div class="notice" style="font-size:12px;margin-bottom:8px">موتور در این ساعت اسکن نکرده است (متوقف/مسدود). این فهرست «اسکن ناظر» است: همان اسکرینر روی همان دادهٔ عمومی ساعت ${hm(sc.time)}، بدون درخواست AI و بدون سفارش. با اجرای دوبارهٔ موتور، اسکن خود موتور جایگزین می‌شود.</div>`
      : d.scan_status === 'observer_running' ? '<div class="notice" style="font-size:12px;margin-bottom:8px">موتور این ساعت را اسکن نکرده است؛ اسکن ناظر ساعت جاری در حال اجراست…</div>' : '';
    $('#cands').innerHTML = scanNote + (sc ? `<div class="faint" style="font-size:11px;margin-bottom:6px">${n0(scanned)} نماد با دادهٔ کافی ارزیابی شد · ${n0(cov.missing_required_history || 0)} بدون دادهٔ کافی یا دارای موقعیت · ${n0(cov.below_quality || 0)} زیر حد کیفیت</div>` : '') + (sc && sc.top && sc.top.length ? `<table><thead><tr><th>جفت</th><th>استراتژی</th><th>کیفیت</th><th>R/R</th><th>حد ضرر</th><th>TP</th><th>RSI</th></tr></thead><tbody>${sc.top.map(c => `<tr><td>${sym(c.symbol)}</td><td>${c.side === 'short' ? '<span class="chip bad">شورت</span> ' : ''}${famChip(c.strategy)} ${esc(sName(c.strategy))}${c.confluence && c.confluence.length > 1 ? `<div class="faint" style="font-size:11px">هم‌پوشانی: ${c.confluence.map(sName).join('، ')}</div>` : ''}</td><td><b>${n0(c.quality)}</b></td><td>${n2(c.plan && c.plan.reward_risk)}</td><td>${pct(c.plan && c.plan.stop_fraction * 100, 1)}</td><td>${c.plan && c.plan.target_price_tmn ? price(c.plan.target_price_tmn) : '—'}</td><td>${n0(c.indicators && c.indicators.rsi14)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">' + (sc ? 'در اسکن آخر هیچ ستاپ باکیفیتی پیدا نشد؛ نبود معامله تصمیم معتبر است.' : 'هنوز اسکنی ثبت نشده است.') + '</div>');
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
      if (k === 'strategy_exit') parts.push(`خروج ${sym(v.base)}: ${esc(reason(v.reason))}${v.pnl_tmn !== undefined ? ` · <span class="${signCls(v.pnl_tmn)}">${toman(v.pnl_tmn)}</span>` : ''}`);
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
  for (const s of j.system || []) rows.push([s.detail && (s.detail.time || s.detail.observed_at), systemText(s)]);
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
  <section class="grid g2"><div class="panel"><div class="head"><h2>دفتر تصمیم ربات</h2><span class="sub">برنامه‌ها، خروج‌ها، تخصیص‌ها و ردها</span></div><div class="body feed scroll" id="plans"></div></div>
  <div class="panel"><div class="head"><h2>رویدادهای سیستمی و ممیزی</h2></div><div class="body feed scroll" id="sys"></div></div></section>`;
  every(15000, async () => {
    const j = await safe(() => api('/api/public/journal'), $('#trades')); if (!j) return; CTX.journal = j;
    const closed = j.trades.filter(t => t.status === 'closed'); const wins = closed.filter(t => +t.pnl_tmn > 0);
    const total = j.trades.reduce((a, t) => a + (+t.pnl_tmn || 0), 0);
    $('#jk').innerHTML = [['تعداد معاملات', n0(j.trades.length), 'باز: ' + n0(j.trades.length - closed.length)], ['نرخ برد (بسته‌شده)', closed.length ? pct(wins.length / closed.length * 100, 0) : '—', n0(wins.length) + ' برد از ' + n0(closed.length)],
      ['سود/زیان کل معاملات', toman(total), 'شامل ارزش باز موقعیت‌ها'], ['سفارش‌ها', n0(j.orders.length), 'آخرین رویداد #' + n0(j.last_seq)]]
      .map(([a, b, c]) => `<div class="panel kpi"><div class="label">${a}</div><div class="value">${b}</div><div class="note">${c}</div></div>`).join('');
    $('#trades').innerHTML = j.trades.length ? `<table><thead><tr><th>جفت</th><th>استراتژی</th><th>ورود</th><th>خروج</th><th>قیمت ورود</th><th>قیمت خروج</th><th>سود/زیان</th><th>دلیل ورود (AI)</th><th>دلیل خروج</th><th>وضعیت</th></tr></thead><tbody>
      ${j.trades.map(t => `<tr><td>${sym(t.symbol)}${t.side === 'short' ? ' <span class="chip bad">شورت</span>' : ''}${t.leverage && +t.leverage > 1 ? ` <span class="chip">×${n0(t.leverage)}</span>` : ''}</td><td>${famChip(t.strategy)} ${esc(sName(t.strategy))}</td><td>${when(t.opened_at)}</td><td>${t.closed_at ? when(t.closed_at) : '—'}</td><td>${price(t.entry_avg)}</td><td>${price(t.exit_avg)}</td>
      <td class="${signCls(t.pnl_tmn)}">${toman(t.pnl_tmn)}<div style="font-size:11px">${pct(t.pnl_percent)}</div></td><td style="max-width:280px;font-size:12px">${esc(t.entry_reason || '—')}${t.ai_confidence !== undefined && t.ai_confidence !== null ? ` <span class="faint">(${n2(t.ai_confidence)})</span>` : ''}</td>
      <td>${esc(reason(t.exit_reason))}</td><td>${t.status === 'open' ? '<span class="chip y">باز</span>' : '<span class="chip">بسته</span>'}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">هنوز معامله‌ای انجام نشده است.</div>';
    $('#orders').innerHTML = ordersTable(j.orders.slice().reverse());
    $('#plans').innerHTML = feedItems({ plans: j.plans }).join('') || '<div class="empty">—</div>';
    $('#sys').innerHTML = (j.system || []).map(s => `<div class="item"><span class="t">#${s.seq}</span><span><b>${esc(s.kind)}</b> <span class="faint mono" style="font-size:11px;word-break:break-all;display:block;text-align:left">${esc(JSON.stringify(s.detail).slice(0, 220))}</span></span></div>`).join('') || '<div class="empty">—</div>';
    $('#csv').onclick = () => { const head = ['symbol', 'strategy', 'opened_at', 'closed_at', 'entry_avg', 'exit_avg', 'pnl_tmn', 'pnl_percent', 'entry_reason', 'exit_reason', 'status'];
      download('algorithmic-trades.csv', [head.join(','), ...j.trades.map(t => head.map(k => JSON.stringify(t[k] ?? '')).join(','))].join('\n'), 'text/csv'); };
    $('#json').onclick = () => download('algorithmic-journal.json', JSON.stringify(j, null, 2));
  });
}

// ------------------------------------------------------------------ AI
function pageAI(root) {
  root.innerHTML = `<div class="notice" style="margin-bottom:14px">در بسته‌شدن هر کندل، اسکنر ربات نمادهای انتخابی را با استراتژی‌های فعال رژیم بررسی می‌کند. اگر فیلتر AI روشن باشد، مدل برای هر نامزد «ورود/رد»، اطمینان، ضریب اندازه و دلیل فارسی برمی‌گرداند. پاسخ، استدلال ثبت‌شدهٔ مدل، توکن‌ها، زمان پاسخ و هر تلاش ناموفق ذخیره می‌شود. پاسخ ناقص یا تمام شدن سهمیه هرگز مجوز ورود نیست.</div>
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
  root.innerHTML = `<div id="sintro"></div><h2 style="font-size:16px">۱. تشخیص رژیم بازار</h2><div class="muted" style="font-size:12.5px;margin:-4px 0 10px">با «فیلتر رژیم» روشن، ربات رژیم را از پهنای نمادهای خودش و بازده ۲۴ساعتهٔ بیت‌کوین می‌سازد و فقط استراتژی‌های همان رژیم را اجرا می‌کند.</div><section class="grid g4" id="regimes" style="margin-bottom:18px"></section>
  <h2 style="font-size:16px">۲. استراتژی‌ها (همه با تأیید و رتبه‌بندی AI)</h2><section class="grid g2" id="strats" style="margin-bottom:18px"></section>
  <h2 style="font-size:16px">۳. شواهد بک‌تست قواعد (بدون AI)</h2><section class="panel" id="bt"><div class="body"><div class="skeleton" style="height:80px"></div></div></section>`;
  (async () => {
    const live = CTX.live || (S.bot ? await safe(pollLive) : null); const cat = live ? live.strategies : await api('/api/public/strategies');
    const cur = live && live.latest_scan && live.latest_scan.regime ? live.latest_scan.regime.regime : null;
    $('#sintro').innerHTML = `<div class="notice green" style="margin-bottom:14px">${esc(cat.ai_role)}<br>${esc(cat.quality_role || '')}<br>${esc(cat.fast_role || '')}<br>${esc(cat.exit_role || '')}<br>${esc(cat.hard_limits_role)}</div>`;
    $('#regimes').innerHTML = Object.entries(cat.regimes).map(([k, r]) => `<div class="regime ${k === cur ? 'current' : ''}"><b style="font-size:15px">${esc(r.fa)}</b><div class="muted" style="font-size:12px;margin:4px 0 8px">${esc(r.description)}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px"><span class="chip">${r.strategies.length ? n0(r.strategies.length) + ' استراتژی فعال' : 'بدون ورود'}</span></div>
      ${r.strategies.map(s => `<div style="font-size:12.5px">${famChip(s)} ${esc(cat.strategies[s].fa)}</div>`).join('')}</div>`).join('');
    const active = cur && cat.regimes[cur] ? cat.regimes[cur].strategies : cur === 'unfiltered' ? Object.keys(cat.strategies) : [];
    $('#strats').innerHTML = Object.entries(cat.strategies).map(([k, s]) => `<div class="panel strategy ${active.includes(k) ? 'active' : ''}">${ART[k] || ART.custom || ''}
      <div><h3>${esc(s.fa)} ${s.family === 'smart_money' ? '<span class="chip smc">Smart Money</span>' : s.family === 'hybrid' ? '<span class="chip smc">Hybrid</span>' : '<span class="chip ind">Indicator</span>'} ${s.custom ? '<span class="chip y">ساخت استودیو</span>' : ''} ${active.includes(k) ? '<span class="chip y">فعال در رژیم فعلی</span>' : ''}</h3>
      <div class="muted" style="font-size:12.5px">${esc(s.thesis)}</div><dl><dt>ورود</dt><dd>${esc(s.entry)}</dd><dt>حد ضرر</dt><dd>${esc(s.stop)}</dd><dt>هدف</dt><dd>${esc(s.target)}</dd><dt>خروج</dt><dd>${esc(s.exit)}</dd></dl></div></div>`).join('');
    const rep = await safe(() => api('/api/public/adaptive-report'), $('#bt .body'));
    if (!rep) return;
    if (rep.pending) { $('#bt .body').innerHTML = '<div class="empty">گزارش هنوز تولید نشده است.</div>'; return; }
    const agg = (split, sc) => rep.aggregates.find(a => a.split === split && a.scenario === sc) || {};
    const all = agg('all', 'base'), val = agg('validation', 'base'), st = agg('validation', 'cost_delay_stress');
    const base = rep.rows.filter(r => r.scenario === 'base').sort((a, b) => a.window - b.window);
    const stress = Object.fromEntries(rep.rows.filter(r => r.scenario !== 'base').map(r => [r.window, r]));
    $('#bt .body').innerHTML = `
      <div class="notice" style="font-size:12.5px;line-height:1.9;margin-bottom:10px"><b>این بخش چیست؟</b> قواعد ورود و خروج همان شش استراتژی آمادهٔ ربات‌ها (با فیلتر کیفیت ۵۵ و نردبان TP) <b>بدون AI</b> روی ۳۹ دورهٔ ۷۲ساعته از داده‌های ساعتی ضبط‌شدهٔ والکس اجرا شده‌اند؛ هر دوره با ۵ میلیون تومان شروع و در پایان به تومان تسویه می‌شود.
        دوره‌های ۱ تا ۳۰ برای انتخاب پارامترها به کار رفتند («انتخاب») و ۹ دورهٔ آخر فقط برای سنجش («اعتبارسنجی»). «تنش» یعنی همان ۹ دوره با کارمزد دو برابر، اسپرد و لغزش بیشتر و دو کندل تأخیر.
        چون هر پیشنهاد قاعده با اندازهٔ کامل پذیرفته شده، این عدد <b>کف</b> سیستم را نشان می‌دهد؛ کار AI و لایهٔ ۱۵ دقیقه‌ای حذف همین معاملات ضعیف است و اثرشان در «تست سایه» سنجیده می‌شود.</div>
      <div class="grid g4" style="margin-bottom:10px">
        <div class="panel kpi"><div class="label">دوره‌های سودده</div><div class="value">${n0(all.positive_windows)} از ${n0(all.windows)}</div><div class="note">همهٔ ۳۹ دوره، سناریوی پایه</div></div>
        <div class="panel kpi"><div class="label">میانگین بازدهٔ هر دوره</div><div class="value ${signCls(all.mean_return_percent)}">${pct(all.mean_return_percent, 2)}</div><div class="note">میانه ${pct(all.median_return_percent, 2)} · تقریباً سربه‌سر</div></div>
        <div class="panel kpi"><div class="label">بدترین دوره / بیشترین افت</div><div class="value neg">${pct(all.worst_return_percent, 2)}</div><div class="note">افت درون‌دوره‌ای هیچ‌گاه بیش از ${pct(Math.max(all.max_drawdown_percent || 0, st.max_drawdown_percent || 0), 1).replace('+', '')} نشد</div></div>
        <div class="panel kpi"><div class="label">اعتبارسنجی پایه / تنش</div><div class="value ${signCls(val.mean_return_percent)}">${pct(val.mean_return_percent, 2)}</div><div class="note">با هزینهٔ سنگین‌تر ${pct(st.mean_return_percent, 2)}</div></div></div>
      <div class="muted" style="font-size:12px;margin-bottom:4px">بازدهٔ هر دوره (٪، سناریوی پایه) — آبی سود، قرمز زیان؛ خط‌چین مرز انتخاب و اعتبارسنجی</div>
      <div id="btbars" class="lchart" style="height:200px"></div>
      <div class="muted" style="font-size:12px;margin:8px 0 6px">خلاصهٔ آماری: <b>جمع‌بندی سالم این است</b> که قواعد به‌تنهایی ریسک را محدود نگه می‌دارند (بدترین دوره ${pct(all.worst_return_percent, 1)}) ولی سود پایدار نمی‌سازند؛ نتایج منفی عمداً پنهان نشده‌اند. سودآوری آینده تضمین نمی‌شود.</div>
      <details><summary>جدول کامل</summary><div class="table-wrap"><table><thead><tr><th>بخش</th><th>سناریو</th><th title="تعداد دوره‌های ۷۲ساعته">دوره</th><th title="میانگین بازدهٔ تسویه‌شدهٔ هر دوره">میانگین</th><th>میانه</th><th>بهترین</th><th>بدترین</th><th>دورهٔ مثبت</th><th title="بیشترین افت از قله در هر دوره">حداکثر افت</th><th title="تعداد سفارش‌های پرشده">پرشدن</th></tr></thead><tbody>
      ${rep.aggregates.map(a => `<tr><td>${{ selection: 'انتخاب ۱–۳۰', validation: 'اعتبارسنجی ۳۱–۳۹', all: 'همه' }[a.split] || a.split}</td><td>${a.scenario === 'base' ? 'پایه' : 'تنش هزینه/تأخیر'}</td><td>${n0(a.windows)}</td><td class="${signCls(a.mean_return_percent)}">${pct(a.mean_return_percent, 3)}</td><td class="${signCls(a.median_return_percent)}">${pct(a.median_return_percent, 3)}</td><td>${pct(a.best_return_percent)}</td><td>${pct(a.worst_return_percent)}</td><td>${n0(a.positive_windows)}</td><td>${pct(-a.max_drawdown_percent)}</td><td>${n0(a.fills)}</td></tr>`).join('')}</tbody></table></div></details>`;
    windowBars($('#btbars'), base, stress);
  })();
}

// ------------------------------------------------------------------ market
function pageMarket(root) {
  root.innerHTML = `<section class="grid g3" style="margin-bottom:14px"><div class="panel span2"><div class="head"><h2 id="mtitle">نمودار دقیقه‌ای</h2>
    <div class="tools tabs-inline" id="mres"><button data-m="180">۳ ساعت</button><button data-m="720" class="on">۱۲ ساعت</button><button data-m="1440">۱ روز</button><button data-m="4320" data-r="5">۳ روز</button></div></div><div class="body"><canvas class="chart tall" id="mchart"></canvas></div></div>
    <div class="panel"><div class="head"><h2>جزئیات</h2></div><div class="body" id="mdet"></div></div></section>
  <section class="panel"><div class="head"><h2>نقشهٔ حرارتی بازارهای والکس</h2><span class="sub" id="hmeta"></span><div class="tools tabs-inline" id="hq"><button data-q="all" class="on">همه</button><button data-q="TMN">تومانی</button><button data-q="USDT">تتری</button></div></div><div class="body"><div class="heat" id="heat"></div></div></section>`;
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

// 39-window returns: one bar per window, diverging colour by sign, selection/validation split.
function windowBars(el, rows, stress) {
  const W = el.clientWidth || 800, H = el.clientHeight || 200, P = { l: 8, r: 46, t: 24, b: 22 };
  const vals = rows.map(r => +r.liquidation_return_percent); const lim = Math.max(1, ...vals.map(Math.abs)) * 1.1;
  const bw = (W - P.l - P.r) / rows.length; const Y = v => P.t + (lim - v) / (2 * lim) * (H - P.t - P.b);
  const x = i => P.l + i * bw;
  const split = rows.findIndex(r => r.window >= 31);
  const grid = [lim, lim / 2, 0, -lim / 2, -lim].map(v => `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0 ? '#353a43' : '#1e2228'}"/><text x="${W - P.r + 6}" y="${Y(v) + 4}" fill="var(--faint)" font-size="11">${v > 0 ? '+' : ''}${v.toFixed(1)}%</text>`).join('');
  const bars = rows.map((r, i) => { const v = vals[i]; const y0 = Y(Math.max(v, 0)), y1 = Y(Math.min(v, 0));
    return `<rect data-i="${i}" x="${x(i) + 1}" y="${y0}" width="${Math.max(1, bw - 2)}" height="${Math.max(1, y1 - y0)}" rx="2" fill="${v >= 0 ? '#3987e5' : '#e66767'}"/>`; }).join('');
  const labels = rows.map((r, i) => (r.window % 5 === 0 || r.window === 1 || r.window === 39) ? `<text x="${x(i) + bw / 2}" y="${H - 6}" fill="var(--faint)" font-size="10.5" text-anchor="middle">${r.window}</text>` : '').join('');
  const sep = split > 0 ? `<line x1="${x(split)}" x2="${x(split)}" y1="${P.t}" y2="${H - P.b}" stroke="var(--muted)" stroke-dasharray="4 4"/><text x="${(P.l + x(split)) / 2}" y="${P.t - 8}" fill="var(--muted)" font-size="11" text-anchor="middle">انتخاب (دوره‌های ۱ تا ۳۰)</text><text x="${(x(split) + x(rows.length)) / 2}" y="${P.t - 8}" fill="var(--muted)" font-size="11" text-anchor="middle">اعتبارسنجی (۳۱ تا ۳۹)</text>` : '';
  el.innerHTML = `<svg width="${W}" height="${H}" style="direction:ltr">${grid}${bars}${labels}${sep}</svg><div class="ltip tooltip" style="display:none;position:absolute"></div>`;
  const tip = el.querySelector('.ltip');
  el.onmousemove = e => { const r = el.getBoundingClientRect(); const i = Math.floor((e.clientX - r.left - P.l) / bw); const row = rows[i];
    if (!row) { tip.style.display = 'none'; return; } const s = stress[row.window];
    tip.style.display = ''; tip.style.left = Math.min(r.width - 180, Math.max(0, e.clientX - r.left + 10)) + 'px'; tip.style.top = '6px';
    tip.innerHTML = `<div class="muted">دورهٔ ${row.window} (${row.window <= 30 ? 'انتخاب' : 'اعتبارسنجی'})</div><div>بازده: <b class="${signCls(vals[i])}">${pct(vals[i])}</b></div><div>حداکثر افت: <span class="neg">${pct(-row.max_drawdown_percent)}</span></div><div>پرشدن: ${n0(row.fill_count)}</div>${s ? `<div>در تنش: <span class="${signCls(+s.liquidation_return_percent)}">${pct(+s.liquidation_return_percent)}</span></div>` : ''}`; };
  el.onmouseleave = () => { tip.style.display = 'none'; };
}

// Header countdown: time to the bot's scheduled start or end (Nova's contest clock, per bot).
function countdown() {
  const node = $('#cd'); const d = CTX.live; if (!node || !d || !d.bot || d.bot.id !== S.bot) return;
  const s = d.bot.schedule || {}; const now = Date.now() / 1000;
  const fmt = sec => { sec = Math.max(0, Math.floor(sec)); const dd = Math.floor(sec / 86400); sec %= 86400; const hh = Math.floor(sec / 3600); sec %= 3600;
    return `${dd}d ${String(hh).padStart(2, '0')}:${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`; };
  const [label, value] = d.bot.status === 'scheduled' && s.from > now ? ['شروع تا', fmt(s.from - now)] : s.until && s.until > now ? ['پایان تا', fmt(s.until - now)]
    : s.until ? ['بازه تمام شد', ''] : ['نامحدود', '∞'];
  $('#cdl').textContent = label; node.textContent = value;
}

// ------------------------------------------------------------------ research
function pageResearch(root) {
  const lab = document.createElement('div'); root.appendChild(lab); labSection(lab, { every, keep, safe });
  const note = h(`<section class="panel"><div class="head"><h2>شواهد بک‌تست شش استراتژی</h2><span class="sub">۳۹ دورهٔ ۷۲ساعته روی دادهٔ ساعتی ضبط‌شدهٔ والکس</span></div>
    <div class="body muted" style="font-size:12.5px">نتیجهٔ کامل این آزمون (پایه، اعتبارسنجی و تنش هزینه) در صفحهٔ <a href="#strategies">«استراتژی‌ها»</a> آمده است. هر ربات را هم می‌توانید از فهرست بالای فرم بارگذاری کنید تا دقیقاً قواعد همان ربات آزموده شود.</div></section>`);
  root.appendChild(note);
}

// ------------------------------------------------------------------ boot
(async function boot() {
  try { S.meta = await api('/api/meta'); } catch (e) { document.body.innerHTML = '<div class="empty" style="padding:60px">اتصال به سرور برقرار نشد</div>'; return; }
  document.title = S.meta.site_name + ' · ربات معامله‌گر خودت را بساز';
  await loadSession();
  if (S.user) await refreshBots();
  safe(async () => { CTX.catalog = await api('/api/public/strategies'); });
  setInterval(() => { if (!document.hidden && S.user && S.bot && $('#engpill') && !$('#engpill').classList.contains('hidden')) safe(pollLive); }, 10000);
  setInterval(() => { if (!document.hidden && S.user) refreshBots(); }, 30000);
  setInterval(countdown, 1000);
  addEventListener('hashchange', route); route();
})();
