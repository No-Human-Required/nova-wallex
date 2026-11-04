// الگوریتمیک — user panel and back office (single page, no external dependencies).
const S = { user: null, csrf: '', meta: null, timers: [] };
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nf = new Intl.NumberFormat('fa-IR'), nf2 = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 });
const n0 = v => v === null || v === undefined || isNaN(+v) ? '—' : nf.format(Math.round(+v));
const n2 = v => v === null || v === undefined || isNaN(+v) ? '—' : nf2.format(+v);
const toman = v => v === null || v === undefined || isNaN(+v) ? '—' : nf.format(Math.round(+v)) + ' تومان';
const pct = (v, d = 2) => v === null || v === undefined || isNaN(+v) ? '—' : (+v > 0 ? '+' : '') + new Intl.NumberFormat('fa-IR', { maximumFractionDigits: d }).format(+v) + '٪';
const sign = v => +v > 0 ? 'pos' : +v < 0 ? 'neg' : '';
const dtf = new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Tehran' });
const when = s => s ? dtf.format(new Date(s * 1000)) : '—';
const iso = ts => new Date(ts * 1000).toISOString().slice(0, 10);
const STATUS = { running: ['در حال اجرا', 'ok'], paused: ['فقط مدیریت خروج', 'y'], stopped: ['متوقف', ''], closing: ['در حال بستن موقعیت‌ها', 'y'],
  pending_approval: ['در انتظار تأیید ادمین', 'v'], blocked: ['مسدود — نیاز به بررسی', 'bad'], deleted: ['حذف‌شده', 'bad'] };
const EXIT = { stop: 'حد ضرر', trailing_stop: 'حد ضرر شناور', breakeven_stop: 'سربه‌سر', stepped_stop: 'حد ضرر پله‌ای', tp3: 'TP3', take_profit: 'حد سود',
  time_exit: 'پایان زمان نگهداری', trend_exit: 'برگشت روند', manual_close: 'بستن دستی', end_of_test: 'پایان بازه' };
const chip = st => { const [t, c] = STATUS[st] || [st, '']; return `<span class="chip ${c}">${esc(t)}</span>`; };

async function api(path, body) {
  const init = { method: body === undefined ? 'GET' : 'POST', headers: { Accept: 'application/json' }, credentials: 'same-origin' };
  if (body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.headers['X-CSRF-Token'] = S.csrf; init.body = JSON.stringify(body); }
  const r = await fetch(path, init);
  let data = null; try { data = await r.json(); } catch (e) { /* empty */ }
  if (r.status === 401 && S.user) { S.user = null; location.hash = '#login'; }
  if (!r.ok) throw new Error((data && (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))) || ('خطای ' + r.status));
  return data;
}
function toast(msg, err = false) { const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); clearTimeout(t._h); t._h = setTimeout(() => t.classList.add('hidden'), 4200); }
async function act(fn, ok) { try { const r = await fn(); if (ok) toast(ok); return r; } catch (e) { toast(e.message, true); return null; } }
function every(ms, fn) { fn(); S.timers.push(setInterval(() => { if (!document.hidden) fn(); }, ms)); }
function modal(html) { const m = document.createElement('div'); m.className = 'modal'; m.innerHTML = `<div>${html}</div>`; m.onclick = e => { if (e.target === m) m.remove(); }; document.body.appendChild(m); return m; }
function download(name, text, type = 'text/csv') { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); }

// ------------------------------------------------------------------ routing
const ROUTES = {
  home: pageHome, login: pageLogin, dashboard: pageDashboard, new: pageBuilder, bot: pageBot, edit: pageBuilder, backtests: pageBacktests,
  keys: pageKeys, billing: pageBilling, profile: pageProfile,
  admin: pageAdmin, 'admin-users': pageAdminUsers, 'admin-bots': pageAdminBots, 'admin-plans': pageAdminPlans, 'admin-settings': pageAdminSettings,
  'admin-payments': pageAdminPayments, 'admin-audit': pageAdminAudit
};
async function route() {
  S.timers.forEach(clearInterval); S.timers = [];
  $$('.modal').forEach(m => m.remove());
  const [raw, query] = (location.hash.slice(1) || '').split('?');
  const [name, arg] = raw.split('/');
  const q = Object.fromEntries(new URLSearchParams(query || ''));
  const page = name || (S.user ? 'dashboard' : 'home');
  if (!S.user && !['home', 'login'].includes(page)) { location.hash = '#login'; return; }
  if (page.startsWith('admin') && (!S.user || S.user.role !== 'admin')) { location.hash = '#dashboard'; return; }
  (ROUTES[page] || pageHome)(arg, q);
}
window.addEventListener('hashchange', route);

function shell(title, body, tools = '') {
  const u = S.user; const cur = (location.hash.slice(1) || 'dashboard').split(/[/?]/)[0];
  const link = (h, t, i) => `<a href="#${h}" class="${cur === h ? 'on' : ''}">${i} ${t}</a>`;
  $('#app').innerHTML = `<div class="shell"><aside class="side" id="side"><div class="brand"><img src="/assets/mark.svg" alt=""><div><b>${esc(S.meta.site_name)}</b><div class="faint" style="font-size:11px">ربات معامله‌گر خودت</div></div></div>
    <nav class="nav">${link('dashboard', 'داشبورد', '◧')}${link('new', 'ساخت ربات', '＋')}${link('backtests', 'بک‌تست', '∿')}${link('keys', 'کلیدهای صرافی', '⚿')}${link('billing', 'اشتراک', '◈')}${link('profile', 'حساب من', '☺')}
    ${u.role === 'admin' ? `<div class="sec">بک‌آفیس</div>${link('admin', 'نمای کلی', '▤')}${link('admin-bots', 'ربات‌ها و تأیید', '✓')}${link('admin-users', 'کاربران', '☷')}${link('admin-plans', 'پلن‌ها', '◈')}${link('admin-payments', 'پرداخت‌ها', '₮')}${link('admin-settings', 'تنظیمات', '⚙')}${link('admin-audit', 'رویدادها', '≡')}` : ''}</nav>
    <div class="faint" style="font-size:11px;padding:18px 12px">نسخهٔ ${esc(S.meta.version)}</div></aside>
    <main class="main">${S.meta.notice ? `<div class="notice y mb">${esc(S.meta.notice)}</div>` : ''}<div class="top"><div class="row"><button class="burger ghost" id="burger">☰</button><h1>${title}</h1></div><div class="row">${tools}</div></div><div id="page">${body}</div></main></div>`;
  $('#burger').onclick = () => $('#side').classList.toggle('open');
  $$('#side a').forEach(a => a.onclick = () => $('#side').classList.remove('open'));
}

// ------------------------------------------------------------------ public
function pageHome() {
  const plans = S.meta.plans.map(p => `<div class="panel plan"><b>${esc(p.name)}</b><div class="price">${+p.price_tmn ? toman(p.price_tmn) : 'رایگان'}</div><div class="faint">${+p.price_tmn ? n0(p.days) + ' روز' : ''}</div>
    <div class="muted" style="font-size:13px">${esc(p.description || '')}</div><div style="font-size:12.5px">${n0(p.max_bots)} ربات · ${+p.max_live_bots ? n0(p.max_live_bots) + ' ربات واقعی' : 'فقط اجرای آزمایشی'} · ${n0(p.ai_calls_month)} درخواست AI در ماه</div></div>`).join('');
  $('#app').innerHTML = `<div class="land"><header><div class="brand"><img src="/assets/mark.svg" alt=""><b>${esc(S.meta.site_name)}</b></div><a href="#login"><button class="primary">${S.user ? 'ورود به پنل' : 'ورود / ثبت‌نام'}</button></a></header>
    <section class="hero"><div><h1>ربات معامله‌گر <span>خودت</span> را بساز، بسنج و به کار بینداز</h1>
      <p>استراتژی‌های Smart Money و اندیکاتوری، فیلتر هوش مصنوعی و مدیریت ریسک حرفه‌ای؛ اول روی گذشته بک‌تست بگیر، بعد آزمایشی اجرا کن و وقتی مطمئن شدی روی حساب والکس خودت فعالش کن. دارایی همیشه در حساب خودت می‌ماند.</p>
      <div class="row" style="margin-top:18px"><a href="#login"><button class="primary">شروع رایگان</button></a><span class="faint">ورود فقط با شمارهٔ موبایل</span></div></div>
      <div class="art"><div class="grid g2">${[['۶', 'استراتژی آماده'], ['۱۰', 'تایم‌فریم بک‌تست'], ['۳', 'حد سود پله‌ای'], ['AI', 'فیلتر ورود']].map(([a, b]) => `<div class="panel kpi"><div class="v">${a}</div><div class="l">${b}</div></div>`).join('')}</div></div></section>
    <section class="grid g3 mb">${[['بدون نیاز به کدنویسی', 'نمادها، استراتژی‌ها و پروفایل ریسک را انتخاب کن؛ بقیه را سیستم انجام می‌دهد.'], ['بک‌تست حرفه‌ای', 'شارپ، حداکثر افت، Profit Factor، مقایسه با خرید و نگهداری و مونت‌کارلو، روی هر تایم‌فریم و بازه.'],
      ['اجرای آزمایشی', 'ربات روی قیمت‌های لحظه‌ای بازار بدون پول واقعی کار می‌کند تا رفتارش را ببینی.'], ['فیلتر هوش مصنوعی', 'هر ستاپ پیش از ورود توسط مدل زبانی بررسی و با دلیل ثبت می‌شود.'],
      ['مدیریت ریسک', 'ریسک ثابت هر معامله، سقف هر دارایی، حد ضرر شناور و سه حد سود با حد ضرر پله‌ای.'], ['امنیت دارایی', 'کلید API فقط با دسترسی معامله؛ برداشت ممکن نیست و هر ربات واقعی پیش از اجرا بررسی می‌شود.']]
      .map(([a, b]) => `<div class="panel feat"><b>${a}</b><p>${b}</p></div>`).join('')}</section>
    <h2>پلن‌ها</h2><section class="grid g3">${plans}</section>
    <p class="faint" style="margin-top:30px;font-size:12px">معامله در بازار رمزارز ریسک دارد و بازده گذشته یا بک‌تست سود آینده را تضمین نمی‌کند.</p></div>`;
}

function pageLogin() {
  if (S.user) { location.hash = '#dashboard'; return; }
  let phone = '', timer = null;
  $('#app').innerHTML = `<div class="land"><div class="panel login"><div class="head"><h2>ورود / ثبت‌نام</h2><a href="#home" class="faint">بازگشت</a></div><div class="body form" id="lf">
    <label class="f">شمارهٔ موبایل<input id="ph" class="ltr" inputmode="tel" placeholder="09121234567" autocomplete="tel"></label>
    <button class="primary" id="send">دریافت کد</button><div class="faint" style="font-size:12px">کد ۶ رقمی با پیامک ارسال می‌شود.</div></div></div></div>`;
  const step2 = r => {
    $('#lf').innerHTML = `<div class="muted">کد ارسال‌شده به <b class="mono">${esc(r.phone)}</b> را وارد کنید${r.dev_code ? ` <span class="chip y">حالت توسعه: ${esc(r.dev_code)}</span>` : ''}</div>
      <input id="code" class="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code"><button class="primary" id="verify">ورود</button>
      <div class="row"><button class="ghost" id="resend" disabled>ارسال دوباره</button><span class="faint" id="cd"></span><a href="#login" id="chg" class="faint" style="margin-right:auto">تغییر شماره</a></div>`;
    let left = r.resend_after; clearInterval(timer);
    timer = setInterval(() => { left--; $('#cd') && ($('#cd').textContent = left > 0 ? left + ' ثانیه' : ''); if (left <= 0) { clearInterval(timer); $('#resend') && ($('#resend').disabled = false); } }, 1000);
    $('#code').focus();
    const go = async () => { const v = await act(() => api('/api/auth/verify', { phone, code: $('#code').value })); if (v) { S.user = v.user; S.csrf = v.csrf; clearInterval(timer); location.hash = '#dashboard'; } };
    $('#verify').onclick = go; $('#code').oninput = () => { if ($('#code').value.length === 6) go(); };
    $('#resend').onclick = send; $('#chg').onclick = () => { clearInterval(timer); pageLogin(); };
  };
  async function send() { phone = phone || $('#ph').value; const r = await act(() => api('/api/auth/request', { phone })); if (r) { phone = r.phone; step2(r); } }
  $('#send').onclick = send; $('#ph').onkeydown = e => { if (e.key === 'Enter') send(); }; $('#ph').focus();
}

// ------------------------------------------------------------------ user
async function refreshMe() { const r = await api('/api/auth/me'); S.user = r.user; S.csrf = r.csrf || ''; }

async function pageDashboard() {
  shell('داشبورد', '<div class="skeleton"></div>', '<a href="#new"><button class="primary">＋ ربات جدید</button></a>');
  every(15000, async () => {
    const [bots] = await Promise.all([api('/api/bots').catch(e => { toast(e.message, true); return []; }), refreshMe().catch(() => null)]);
    const u = S.user; const live = bots.filter(b => b.mode === 'live'), paper = bots.filter(b => b.mode === 'paper');
    const total = l => l.reduce((a, b) => a + (+b.equity_tmn || 0), 0);
    $('#page').innerHTML = `<div class="grid g4 mb">
      <div class="panel kpi"><div class="l">پلن</div><div class="v">${esc(u.plan ? u.plan.name : 'بدون پلن')}</div><div class="n">${u.plan_active ? (u.plan_expires ? 'تا ' + when(u.plan_expires) : '') : '<a href="#billing">فعال‌سازی پلن</a>'}</div></div>
      <div class="panel kpi"><div class="l">سهمیهٔ AI این ماه</div><div class="v">${n0(u.ai_quota.used)} / ${n0(u.ai_quota.limit)}</div><div class="n">درخواست</div></div>
      <div class="panel kpi"><div class="l">ربات‌های واقعی</div><div class="v">${n0(live.length)}</div><div class="n">ارزش: ${toman(total(live))}</div></div>
      <div class="panel kpi"><div class="l">ربات‌های آزمایشی</div><div class="v">${n0(paper.length)}</div><div class="n">ارزش مجازی: ${toman(total(paper))}</div></div></div>
      ${bots.length ? `<div class="grid g3">${bots.filter(b => b.status !== 'deleted').map(botCard).join('')}</div>` : `<div class="panel"><div class="empty">هنوز رباتی نساخته‌اید.<br><br><a href="#new"><button class="primary">ساخت اولین ربات</button></a></div></div>`}`;
  });
}
function botCard(b) {
  const pnl = (+b.equity_tmn) - (+b.config.capital_tmn);
  return `<a href="#bot/${b.id}" class="panel bot" style="color:inherit"><div class="t"><b>${esc(b.name)}</b>${chip(b.status)}</div>
    <div class="row" style="font-size:12px"><span class="chip ${b.mode === 'live' ? 'a' : ''}">${b.mode === 'live' ? 'واقعی' : 'آزمایشی'}</span><span class="chip">${esc(b.exchange === 'wallex' ? 'والکس' : b.exchange)}</span><span class="chip">${esc(b.config.timeframe)}</span><span class="faint">${b.config.symbols.length} نماد</span></div>
    <div class="row" style="justify-content:space-between"><span class="muted">ارزش</span><b>${toman(b.equity_tmn)}</b></div>
    <div class="row" style="justify-content:space-between"><span class="muted">سود/زیان</span><b class="${sign(pnl)}">${toman(pnl)} (${pct(pnl / b.config.capital_tmn * 100)})</b></div>
    <div class="faint" style="font-size:12px">${Object.keys(b.positions).length} موقعیت باز${b.last_error ? ` · <span class="neg">${esc(b.last_error)}</span>` : ''}</div></a>`;
}

// ---------------------------------------------------------------- builder
async function pageBuilder(id) {
  const editing = location.hash.startsWith('#edit');
  const bot = editing ? await act(() => api('/api/bots/' + id)) : null;
  if (editing && !bot) return;
  const m = S.meta; const { fa: _fa, ...balanced } = m.presets.balanced;
  const d = bot ? { ...bot.config } : { ...m.defaults, ...balanced, preset: 'balanced', ai_filter: true, ai_min_confidence: 0.65, symbols: ['BTCTMN', 'ETHTMN', 'SOLTMN', 'XRPTMN', 'DOGETMN'], capital_tmn: 10000000 };
  let mode = bot ? bot.mode : 'paper', exchange = bot ? bot.exchange : 'wallex', symbols = [...d.symbols], preset = d.preset || 'balanced';
  shell(editing ? 'ویرایش ربات' : 'ساخت ربات', `
    <div class="panel mb"><div class="head"><h2>۱. صرافی و حالت اجرا</h2></div><div class="body form">
      <label class="f">نام ربات<input id="bn" value="${esc(bot ? bot.name : 'ربات من')}" maxlength="60"></label>
      <div class="cards" id="exch">${m.exchanges.map(e => `<div class="card ${e.enabled ? (e.id === exchange ? 'on' : '') : 'off'}" data-x="${e.id}"><b>${esc(e.fa)}</b><span class="faint">${e.enabled ? 'فعال' : 'به‌زودی'}</span></div>`).join('')}</div>
      <div class="cards" id="mode"><div class="card" data-m="paper"><b>آزمایشی (کاغذی)</b><span class="faint">قیمت‌های واقعی، بدون پول واقعی</span></div><div class="card" data-m="live"><b>واقعی</b><span class="faint">روی حساب صرافی خودت؛ پس از تأیید ادمین</span></div></div></div></div>
    <div class="panel mb"><div class="head"><h2>۲. بازار و استراتژی</h2></div><div class="body form">
      <div class="f">نمادها <span id="symc" class="chip a"></span><div id="syms" class="row" style="margin:4px 0"></div>
        <div class="row"><input id="sq" list="mk" class="ltr" placeholder="افزودن نماد، مثلاً ADATMN" style="max-width:240px"><datalist id="mk">${m.markets.map(x => `<option value="${x.symbol}">`).join('')}</datalist>
        <button id="sadd">افزودن</button><button data-pre="major">BTC + ETH</button><button data-pre="top10">۱۰ بازار بزرگ</button><button data-pre="clear">پاک کردن</button></div></div>
      <label class="f">تایم‌فریم سیگنال<select id="tf">${m.timeframes.map(t => `<option value="${t.id}" ${t.id === d.timeframe ? 'selected' : ''}>${t.fa}</option>`).join('')}</select></label>
      <div class="f">استراتژی‌ها<div class="grid g2" id="st">${m.strategies.map(s => `<label class="chk" title="${esc(s.thesis)}"><input type="checkbox" value="${s.id}" ${d.strategies.includes(s.id) ? 'checked' : ''}> <span class="chip ${s.family === 'smart_money' ? 'v' : 'a'}">${s.family === 'smart_money' ? 'SMC' : 'اندیکاتور'}</span> ${esc(s.fa)}</label>`).join('')}</div></div></div></div>
    <div class="panel mb"><div class="head"><h2>۳. سرمایه و ریسک</h2></div><div class="body form">
      <label class="f">سرمایهٔ ربات (تومان)<input id="cap" type="number" min="500000" step="100000" value="${d.capital_tmn}"></label>
      <div class="cards" id="pre">${Object.entries(m.presets).map(([k, p]) => `<div class="card" data-p="${k}"><b>${esc(p.fa)}</b><span class="faint">ریسک ${pct(p.risk_pct, 1).replace('+', '')} هر معامله · حداکثر ${n0(p.max_positions)} موقعیت · کیفیت ≥ ${n0(p.min_quality)}</span></div>`).join('')}<div class="card" data-p="custom"><b>سفارشی</b><span class="faint">همهٔ پارامترها دست خودت</span></div></div>
      <details id="adv"><summary class="muted">تنظیمات پیشرفته</summary><div class="grid g3" style="margin-top:10px">
        ${num('risk_pct', 'ریسک هر معامله ٪', d.risk_pct, 0.05)}${num('max_positions', 'حداکثر موقعیت هم‌زمان', d.max_positions, 1)}${num('min_quality', 'حداقل کیفیت ستاپ (۰ تا ۱۰۰)', d.min_quality, 1)}
        ${num('max_asset_pct', 'سقف هر دارایی ٪ (خالی = خودکار)', d.max_asset_pct ?? '', 1)}${num('min_stop_pct', 'حد ضرر کمینه ٪ (خالی = خودکار)', d.min_stop_pct ?? '', 0.1)}${num('max_stop_pct', 'حد ضرر بیشینه ٪', d.max_stop_pct ?? '', 0.1)}
        ${num('trend_tp_r', 'TP1 روندی (برابر R)', d.trend_tp_r, 0.1)}${num('max_hold_hours', 'حداکثر نگهداری (ساعت، خالی = استراتژی)', d.max_hold_hours ?? '', 1)}${num('cooldown_bars', 'مکث پس از خروج (کندل)', d.cooldown_bars, 1)}
        <label class="f">مدل خروج<select id="exit_mode"><option value="ladder" ${d.exit_mode === 'ladder' ? 'selected' : ''}>سه TP با فاصلهٔ برابر + حد ضرر پله‌ای</option><option value="single" ${d.exit_mode === 'single' ? 'selected' : ''}>یک حد سود</option></select></label>
        <label class="chk"><input type="checkbox" id="trailing" ${d.trailing ? 'checked' : ''}> حد ضرر شناور از اوج</label><label class="chk"><input type="checkbox" id="trend_exit" ${d.trend_exit ? 'checked' : ''}> خروج با برگشت روند</label>
        <label class="chk"><input type="checkbox" id="regime_filter" ${d.regime_filter ? 'checked' : ''}> فیلتر رژیم بازار (≥ ۳ نماد)</label></div></details></div></div>
    <div class="panel mb"><div class="head"><h2>۴. هوش مصنوعی</h2></div><div class="body form">
      <label class="chk"><input type="checkbox" id="ai" ${d.ai_filter ? 'checked' : ''}> هر ورود پیش از ارسال سفارش توسط AI تأیید شود (از سهمیهٔ ماهانهٔ پلن)</label>
      <label class="f">حداقل اطمینان مدل<input id="aic" type="number" step="0.05" min="0.3" max="0.95" value="${d.ai_min_confidence}"></label></div></div>
    <div class="row"><button class="primary" id="save">${editing ? 'ذخیرهٔ تغییرات' : 'ساخت ربات'}</button><button id="bt">بک‌تست ۹۰ روزهٔ همین تنظیمات</button><span id="msg" class="muted"></span></div>
    <div id="btres" style="margin-top:14px"></div>`);
  function num(id, label, v, step) { return `<label class="f">${label}<input id="${id}" type="number" step="${step}" value="${v}"></label>`; }
  const paint = () => {
    $$('#exch .card').forEach(c => c.classList.toggle('on', c.dataset.x === exchange));
    $$('#mode .card').forEach(c => c.classList.toggle('on', c.dataset.m === mode));
    $$('#pre .card').forEach(c => c.classList.toggle('on', c.dataset.p === preset));
    $('#syms').innerHTML = symbols.map(s => `<span class="chip">${esc(s)} <a href="javascript:void 0" data-rm="${s}" class="faint">✕</a></span>`).join('') || '<span class="faint">نمادی انتخاب نشده</span>';
    $('#symc').textContent = symbols.length > 1 ? 'پرتفوی ' + symbols.length + ' نماد' : 'تک‌ارزی';
    $$('#syms [data-rm]').forEach(a => a.onclick = () => { symbols = symbols.filter(x => x !== a.dataset.rm); paint(); });
  };
  $$('#exch .card').forEach(c => c.onclick = () => { if (!c.classList.contains('off')) { exchange = c.dataset.x; paint(); } });
  $$('#mode .card').forEach(c => c.onclick = () => { mode = c.dataset.m; paint(); });
  $$('#pre .card').forEach(c => c.onclick = () => { preset = c.dataset.p; const p = m.presets[preset]; if (p) { ['risk_pct', 'max_positions', 'min_quality'].forEach(k => $('#' + k).value = p[k]); $('#regime_filter').checked = p.regime_filter; } if (preset === 'custom') $('#adv').open = true; paint(); });
  $('#sadd').onclick = () => { const s = $('#sq').value.trim().toUpperCase(); if (m.markets.some(x => x.symbol === s) && !symbols.includes(s) && symbols.length < 25) symbols.push(s); $('#sq').value = ''; paint(); };
  $$('[data-pre]').forEach(b => b.onclick = () => { const k = b.dataset.pre; symbols = k === 'major' ? ['BTCTMN', 'ETHTMN'] : k === 'clear' ? [] : ['BTCTMN', 'ETHTMN', 'USDTTMN', 'SOLTMN', 'XRPTMN', 'DOGETMN', 'TRXTMN', 'ADATMN', 'BNBTMN', 'TONTMN', 'LINKTMN'].filter(s => s !== 'USDTTMN' && m.markets.some(x => x.symbol === s)).slice(0, 10); paint(); });
  const val = id => { const v = $('#' + id).value; return v === '' ? null : +v; };
  const config = () => ({ symbols, timeframe: $('#tf').value, strategies: $$('#st input:checked').map(x => x.value), capital_tmn: val('cap'), preset,
    risk_pct: val('risk_pct'), max_positions: val('max_positions'), min_quality: val('min_quality'), max_asset_pct: val('max_asset_pct'), min_stop_pct: val('min_stop_pct'),
    max_stop_pct: val('max_stop_pct'), trend_tp_r: val('trend_tp_r'), max_hold_hours: val('max_hold_hours'), cooldown_bars: val('cooldown_bars'), exit_mode: $('#exit_mode').value,
    trailing: $('#trailing').checked, trend_exit: $('#trend_exit').checked, regime_filter: $('#regime_filter').checked, ai_filter: $('#ai').checked, ai_min_confidence: val('aic') });
  $('#save').onclick = async () => {
    const body = { name: $('#bn').value, config: config(), mode };
    const r = editing ? await act(() => api('/api/bots/' + id + '/update', body), 'ذخیره شد') : await act(() => api('/api/bots', { ...body, exchange }), 'ربات ساخته شد');
    if (r) location.hash = '#bot/' + r.id;
  };
  $('#bt').onclick = async () => {
    const end = Math.floor(Date.now() / 1000); const r = await act(() => api('/api/backtests', { config: config(), start: iso(end - 90 * 86400) + 'T00:00:00Z', end: new Date(end * 1000).toISOString(), title: $('#bn').value + ' (پیش‌نمایش)' }));
    if (r) watchBacktest(r.id, $('#btres'));
  };
  paint();
}

// ---------------------------------------------------------------- bot detail
async function pageBot(id) {
  shell('ربات', '<div class="empty">در حال بارگذاری…</div>');
  let keys = [];
  every(10000, async () => {
    const b = await act(() => api('/api/bots/' + id)); if (!b) return;
    if (!keys.length && b.mode === 'live') keys = await api('/api/keys').catch(() => []);
    const pnl = (+b.equity_tmn) - (+b.config.capital_tmn);
    const can = { start: ['stopped', 'paused', 'blocked'].includes(b.status), pause: b.status === 'running', stop: ['running', 'paused', 'pending_approval', 'closing'].includes(b.status),
      close: Object.keys(b.positions).length > 0 && ['running', 'paused', 'stopped'].includes(b.status), edit: ['stopped', 'blocked'].includes(b.status) };
    $('.top h1').innerHTML = `${esc(b.name)} ${chip(b.status)} <span class="chip ${b.mode === 'live' ? 'a' : ''}">${b.mode === 'live' ? 'واقعی' : 'آزمایشی'}</span>`;
    $('.top .row:last-child').innerHTML = `${can.start ? '<button class="primary" data-a="start">شروع</button>' : ''}${can.pause ? '<button data-a="pause" title="ورود جدید نه؛ خروج‌ها مدیریت می‌شوند">توقف ورود</button>' : ''}${can.stop ? '<button data-a="stop">توقف</button>' : ''}${can.close ? '<button class="danger" data-a="close">فروش همهٔ موقعیت‌ها</button>' : ''}${can.edit ? `<a href="#edit/${b.id}"><button>ویرایش</button></a>` : ''}<button data-a="backtest">بک‌تست</button>${can.edit && !Object.keys(b.positions).length ? '<button class="ghost danger" data-a="delete">حذف</button>' : ''}`;
    $$('.top [data-a]').forEach(x => x.onclick = async () => {
      const a = x.dataset.a;
      if (a === 'backtest') { location.hash = '#backtests?bot=' + b.id; return; }
      if (['close', 'delete', 'stop'].includes(a) && !confirm({ close: 'همهٔ موقعیت‌ها با قیمت بازار فروخته شوند؟', delete: 'ربات حذف شود؟', stop: b.mode === 'live' ? 'ربات متوقف شود؟ موقعیت‌های باز در حساب صرافی شما می‌مانند و دیگر مدیریت نمی‌شوند.' : 'ربات متوقف شود؟' }[a])) return;
      const r = await act(() => api(`/api/bots/${b.id}/${a}`, {}), 'انجام شد'); if (r && a === 'delete') location.hash = '#dashboard';
    });
    const livePanel = b.mode !== 'live' ? '' : `<div class="panel mb"><div class="head"><h2>اجرای واقعی</h2></div><div class="body">
      ${b.live_approved ? '<div class="notice">اجرای واقعی تأیید شده است.' + (b.review_note ? ' یادداشت: ' + esc(b.review_note) : '') + '</div>' : b.status === 'pending_approval' ? '<div class="notice y">درخواست شما در انتظار بررسی ادمین است.</div>'
      : `${b.review_note ? `<div class="notice red mb">${esc(b.review_note)}</div>` : ''}<div class="row"><select id="key" style="max-width:280px">${keys.filter(k => k.exchange === b.exchange && k.status === 'verified').map(k => `<option value="${k.id}">${esc(k.label || 'کلید')} …${esc(k.last4)}</option>`).join('') || '<option value="">کلید تأییدشده ندارید</option>'}</select><button class="primary" id="req">درخواست اجرای واقعی</button><a href="#keys">مدیریت کلیدها</a></div>`}</div></div>`;
    const pos = Object.entries(b.positions);
    $('#page').innerHTML = `${b.last_error ? `<div class="notice red mb">${esc(b.last_error)}</div>` : ''}${livePanel}
      <div class="grid g4 mb"><div class="panel kpi"><div class="l">ارزش ربات</div><div class="v">${toman(b.equity_tmn)}</div><div class="n">سرمایهٔ اولیه ${toman(b.config.capital_tmn)}</div></div>
        <div class="panel kpi"><div class="l">سود/زیان کل</div><div class="v ${sign(pnl)}">${pct(pnl / b.config.capital_tmn * 100)}</div><div class="n">${toman(pnl)}</div></div>
        <div class="panel kpi"><div class="l">سود محقق‌شده</div><div class="v ${sign(b.realized_tmn)}">${toman(b.realized_tmn)}</div><div class="n">${b.trades.length} معاملهٔ بسته</div></div>
        <div class="panel kpi"><div class="l">نقد ربات</div><div class="v">${toman(b.cash_tmn)}</div><div class="n">${pos.length} موقعیت باز</div></div></div>
      <div class="panel mb"><div class="head"><h2>منحنی ارزش</h2><span class="faint">${esc(b.config.timeframe)} · ${b.config.symbols.length} نماد · ${b.config.ai_filter ? 'با فیلتر AI' : 'بدون AI'}</span></div><div class="body"><div class="chart" id="eq"></div></div></div>
      <div class="panel mb"><div class="head"><h2>موقعیت‌های باز</h2></div><div class="body table-wrap">${pos.length ? `<table><thead><tr><th>نماد</th><th>استراتژی</th><th>مقدار</th><th>ورود</th><th>TP1 / TP2 / TP3</th><th>حد ضرر فعال</th><th>مرحله</th><th>باز شده</th></tr></thead><tbody>${pos.map(([s, p]) => `<tr><td class="mono">${esc(s)}</td><td>${esc(stratName(p.strategy))}</td><td>${n2(p.qty)}</td><td>${n0(p.entry)}</td><td>${p.tp.map(n0).join(' / ')}</td><td>${n0(Math.max(+p.floor, b.config.trailing ? +p.peak * (1 - +p.stop) : 0))}</td><td>${n0(p.stage)} از ۳</td><td>${when(p.opened_at)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">موقعیت بازی نیست.</div>'}</div></div>
      <div class="grid g2"><div class="panel"><div class="head"><h2>معاملات بسته</h2><button id="csv">CSV</button></div><div class="body table-wrap" style="max-height:420px;overflow:auto">${b.trades.length ? `<table><thead><tr><th>نماد</th><th>ورود → خروج</th><th>سود/زیان</th><th>دلیل</th><th>زمان</th></tr></thead><tbody>${b.trades.map(t => `<tr><td class="mono">${esc(t.symbol)}</td><td>${n0(t.entry_price)} → ${n0(t.exit_price)}</td><td class="${sign(t.pnl_tmn)}">${toman(t.pnl_tmn)}</td><td>${esc(EXIT[t.reason] || t.reason)}</td><td style="font-size:12px">${when(t.exit_time)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">هنوز معامله‌ای بسته نشده.</div>'}</div></div>
        <div class="panel"><div class="head"><h2>رویدادها و تصمیم‌های AI</h2></div><div class="body" style="max-height:420px;overflow:auto">${b.events.length ? b.events.map(eventRow).join('') : '<div class="empty">رویدادی ثبت نشده.</div>'}</div></div></div>`;
    lineChart($('#eq'), b.equity.map(x => [x.at, +x.equity]), null, +b.config.capital_tmn);
    if ($('#req')) $('#req').onclick = async () => { if (!$('#key').value) return toast('اول یک کلید API تأییدشده اضافه کنید', true); await act(() => api(`/api/bots/${b.id}/request-live`, { key_id: $('#key').value }), 'درخواست ثبت شد'); };
    $('#csv').onclick = () => download('trades.csv', ['symbol,entry_time,exit_time,entry_price,exit_price,qty,pnl_tmn,reason', ...b.trades.map(t => [t.symbol, new Date(t.entry_time * 1000).toISOString(), new Date(t.exit_time * 1000).toISOString(), t.entry_price, t.exit_price, t.qty, t.pnl_tmn, t.reason].join(','))].join('\n'));
  });
}
function stratName(id) { const s = S.meta.strategies.find(x => x.id === id); return s ? s.fa : (id || '—'); }
function eventRow(e) {
  const d = e.detail || {}; let text = e.kind;
  if (e.kind === 'ai_decision') text = `تصمیم AI: ${(d.decisions || []).map(x => `${x.action === 'enter' ? '✓' : '✕'} ${esc(x.reason || '')}`).join(' · ') || esc(d.status)}`;
  else if (e.kind === 'trade_closed') text = `معامله بسته شد ${esc(d.symbol)}: <span class="${sign(d.pnl_tmn)}">${toman(d.pnl_tmn)}</span> (${esc(EXIT[d.reason] || d.reason)})`;
  else if (e.kind === 'take_profit_reached') text = `${esc(d.symbol)} به TP${d.level} رسید؛ حد ضرر بالا آمد`;
  else if (e.kind === 'entry_skipped') text = `ورود ${esc(d.symbol)} انجام نشد (کمتر از حداقل سفارش)`;
  else if (e.kind === 'ai_quota_exhausted') text = 'سهمیهٔ AI این ماه تمام شده؛ ورود جدید انجام نمی‌شود';
  else if (e.kind === 'ai_unavailable') text = 'فیلتر AI در دسترس نبود؛ ورودی انجام نشد';
  else if (e.kind.startsWith('order_')) text = `سفارش ${esc(d.client_id || '')}: ${esc(e.kind.slice(6))}`;
  else if (e.kind.startsWith('bot_')) text = `وضعیت ربات: ${esc(STATUS[e.kind.slice(4)] ? STATUS[e.kind.slice(4)][0] : e.kind)} ${d.reason ? '— ' + esc(d.reason) : ''}`;
  return `<div style="padding:6px 0;border-bottom:1px solid #172027;font-size:12.5px"><span class="faint">${when(e.at)}</span><div>${text}</div></div>`;
}

// ---------------------------------------------------------------- backtests
async function pageBacktests(_, q) {
  shell('بک‌تست', `<div class="panel mb"><div class="head"><h2>بک‌تست جدید</h2></div><div class="body form">
    <div class="grid g3"><label class="f">ربات<select id="bb"></select></label><label class="f">از (UTC)<input id="bs" type="date"></label><label class="f">تا (UTC)<input id="be" type="date"></label></div>
    <label class="f">تایم‌فریم (خالی = تایم‌فریم ربات)<select id="btf"><option value="">همان ربات</option>${S.meta.lab_timeframes.map(t => `<option value="${t.id}">${t.fa}</option>`).join('')}</select></label>
    <div class="row"><button class="primary" id="go">اجرا</button><span class="faint">کندل‌های عمومی والکس؛ تایم‌فریم زیر یک ساعت حداکثر ۶۲ روز</span></div></div></div>
    <div id="res" class="mb"></div><div class="panel"><div class="head"><h2>تست‌های من</h2></div><div class="body table-wrap" id="list"></div></div>`);
  const bots = await api('/api/bots').catch(() => []);
  $('#bb').innerHTML = bots.filter(b => b.status !== 'deleted').map(b => `<option value="${b.id}" ${q.bot === b.id ? 'selected' : ''}>${esc(b.name)}</option>`).join('') || '<option value="">اول یک ربات بسازید</option>';
  const now = Math.floor(Date.now() / 1000); $('#be').value = iso(now); $('#bs').value = iso(now - 90 * 86400);
  $('#go').onclick = async () => {
    if (!$('#bb').value) return toast('اول یک ربات بسازید', true);
    const body = { bot_id: $('#bb').value, start: $('#bs').value + 'T00:00:00Z', end: $('#be').value + 'T23:59:00Z' };
    if ($('#btf').value) body.config = { timeframe: $('#btf').value };
    const r = await act(() => api('/api/backtests', body)); if (r) watchBacktest(r.id, $('#res'));
  };
  every(5000, async () => {
    const rows = await api('/api/backtests').catch(() => []);
    $('#list').innerHTML = rows.length ? `<table><thead><tr><th>نام</th><th>نماد</th><th>تایم‌فریم</th><th>بازه</th><th>وضعیت</th><th></th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.title || '—')}</td><td style="font-size:12px">${esc(r.spec.symbols.length > 3 ? r.spec.symbols.length + ' نماد' : r.spec.symbols.join('، '))}</td><td>${esc(r.spec.timeframe)}</td><td style="font-size:12px">${esc(String(r.spec.start).slice(0, 10))} → ${esc(String(r.spec.end).slice(0, 10))}</td>
      <td>${r.status === 'done' ? '<span class="pos">انجام شد</span>' : r.status === 'failed' ? `<span class="neg" title="${esc(r.error)}">ناموفق</span>` : `<span class="warn">${r.progress ? (r.progress.stage === 'data' ? 'دریافت داده ' : 'شبیه‌سازی ') + n0(r.progress.total ? r.progress.done / r.progress.total * 100 : 0) + '٪' : 'در صف'}</span>`}</td>
      <td>${['done', 'failed'].includes(r.status) ? `<button data-r="${r.id}">نمایش</button>` : ''}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">هنوز بک‌تستی اجرا نکرده‌اید.</div>';
    $$('#list [data-r]').forEach(b => b.onclick = () => watchBacktest(b.dataset.r, $('#res')));
  });
}
function watchBacktest(id, box) {
  box.innerHTML = '<div class="panel"><div class="body empty">در حال اجرای بک‌تست…</div></div>';
  const tick = async () => {
    const r = await api('/api/backtests/' + id).catch(e => ({ status: 'failed', error: e.message }));
    if (r.status === 'done') { renderResult(box, r.result); return; }
    if (r.status === 'failed' || r.status === 'interrupted') { box.innerHTML = `<div class="notice red">${esc(r.error || 'ناموفق')}</div>`; return; }
    setTimeout(tick, 2500);
  };
  tick();
}
function renderResult(box, res) {
  const s = res.summary, b = res.benchmark || {}, mc = res.monte_carlo;
  const k = (l, v, n = '', c = '') => `<div class="panel kpi"><div class="l">${l}</div><div class="v ${c}" style="font-size:18px">${v}</div><div class="n">${n}</div></div>`;
  box.innerHTML = `<div class="panel"><div class="head"><h2>نتیجهٔ بک‌تست</h2><span class="faint">${esc(res.params.symbols.length > 1 ? 'پرتفوی ' + res.params.symbols.length + ' نماد' : res.params.symbols[0])} · ${esc(res.params.timeframe)} · ${when(res.params.start_ts)} → ${when(res.params.end_ts)}</span><button id="rcsv">معاملات CSV</button></div><div class="body">
    <div class="grid g4 mb">${k('بازده کل', pct(s.total_return_pct), toman(s.net_profit_tmn), sign(s.total_return_pct))}${k('خرید و نگهداری', pct(b.total_return_pct), 'اضافه‌بازده ' + pct(b.excess_return_pct), sign(b.total_return_pct))}
      ${k('حداکثر افت', pct(-s.max_drawdown_pct), n2(s.longest_dd_days) + ' روز طولانی‌ترین افت', 'neg')}${k('شارپ / سورتینو', n2(s.sharpe) + ' / ' + n2(s.sortino), 'کالمار ' + n2(s.calmar))}
      ${k('نرخ برد', pct(s.win_rate_pct, 1).replace('+', ''), n0(s.trades) + ' معامله')}${k('Profit Factor', n2(s.profit_factor), 'SQN ' + n2(s.sqn))}${k('امید ریاضی', pct(s.expectancy_pct), n2(s.avg_r) + 'R', sign(s.expectancy_pct))}${k('کارمزد', toman(s.fees_tmn), 'در بازار ' + pct(s.exposure_pct, 0).replace('+', ''))}</div>
    <div class="row faint" style="font-size:12px;gap:14px"><span><i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:#c98500"></i> ربات</span><span><i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:#3987e5"></i> خرید و نگهداری</span></div>
    <div class="chart" id="rc"></div>
    ${mc ? `<div class="faint" style="font-size:12.5px;margin-top:8px">مونت‌کارلو (۱۰۰۰ بازچینی معاملات): بازدهٔ میانه ${pct(mc.return_p50)} · بدبینانه ${pct(mc.return_p5)} · احتمال زیان ${n0(mc.loss_probability)}٪ · افت ۹۵٪ ${pct(-mc.max_dd_p95)}</div>` : ''}
    <div class="faint" style="font-size:11.5px;margin-top:8px">${esc(res.method)}</div></div></div>`;
  lineChart($('#rc', box), res.curve.t.map((t, i) => [t, res.curve.equity[i]]), res.curve.benchmark ? res.curve.t.map((t, i) => [t, res.curve.benchmark[i]]) : null, res.curve.equity[0]);
  $('#rcsv', box).onclick = () => download('backtest-trades.csv', ['symbol,strategy,entry_time,exit_time,entry_price,exit_price,return_pct,r_multiple,exit_reason', ...res.trades.map(t => [t.symbol, t.strategy, new Date(t.entry_time * 1000).toISOString(), new Date(t.exit_time * 1000).toISOString(), t.entry_price, t.exit_price, t.return_pct, t.r_multiple, t.exit_reason].join(','))].join('\n'));
}

// equity line (validated palette: bot #c98500, buy-and-hold #3987e5)
function lineChart(el, pts, bench, base) {
  if (!el) return;
  if (pts.length < 2) { el.innerHTML = '<div class="empty">پس از چند دقیقه اجرا منحنی ارزش اینجا رسم می‌شود.</div>'; return; }
  const W = el.clientWidth || 700, H = el.clientHeight || 260, P = { l: 8, r: 70, t: 10, b: 22 };
  const all = pts.map(p => p[1]).concat(bench ? bench.map(p => p[1]) : []); const min = Math.min(...all, base), max = Math.max(...all, base);
  const t0 = pts[0][0], t1 = pts[pts.length - 1][0];
  const X = t => P.l + (t - t0) / ((t1 - t0) || 1) * (W - P.l - P.r), Y = v => H - P.b - (v - min) / ((max - min) || 1) * (H - P.t - P.b);
  const path = s => s.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');
  const grid = [0, .25, .5, .75, 1].map(f => { const v = min + (max - min) * f; return `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="#1d272d"/><text x="${W - P.r + 6}" y="${Y(v) + 4}" fill="#5f6d75" font-size="11">${Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(2) + 'M' : Math.round(v)}</text>`; }).join('');
  const xt = [0, .5, 1].map((f, k) => { const t = t0 + (t1 - t0) * f; return `<text x="${X(t)}" y="${H - 6}" fill="#5f6d75" font-size="11" text-anchor="${['start', 'middle', 'end'][k]}">${new Date(t * 1000).toISOString().slice(0, 10)}</text>`; }).join('');
  el.innerHTML = `<svg width="${W}" height="${H}">${grid}${xt}<line x1="${P.l}" x2="${W - P.r}" y1="${Y(base)}" y2="${Y(base)}" stroke="#3a4850" stroke-dasharray="4 4"/>
    ${bench ? `<path d="${path(bench)}" fill="none" stroke="#3987e5" stroke-width="2"/>` : ''}<path d="${path(pts)}" fill="none" stroke="#c98500" stroke-width="2"/>
    <line class="x" y1="${P.t}" y2="${H - P.b}" stroke="#95a3ab" style="display:none"/></svg><div class="tip" style="display:none"></div>`;
  const tip = $('.tip', el), line = $('.x', el);
  el.onmousemove = e => { const r = el.getBoundingClientRect(); const x = e.clientX - r.left; let i = 0, best = 1e18; pts.forEach((p, k) => { const d = Math.abs(X(p[0]) - x); if (d < best) { best = d; i = k; } });
    line.setAttribute('x1', X(pts[i][0])); line.setAttribute('x2', X(pts[i][0])); line.style.display = ''; tip.style.display = '';
    tip.style.left = Math.min(r.width - 180, Math.max(0, x + 10)) + 'px'; tip.style.top = '6px';
    tip.innerHTML = `<div class="faint">${when(pts[i][0])}</div><div>ربات: <b>${toman(pts[i][1])}</b> <span class="${sign(pts[i][1] - base)}">${pct((pts[i][1] / base - 1) * 100)}</span></div>${bench && bench[i] ? `<div>خرید و نگهداری: ${toman(bench[i][1])}</div>` : ''}`; };
  el.onmouseleave = () => { tip.style.display = 'none'; line.style.display = 'none'; };
}

// ---------------------------------------------------------------- keys, billing, profile
async function pageKeys() {
  const ex = S.meta.exchanges.filter(e => e.enabled);
  shell('کلیدهای صرافی', `<div class="grid g2"><div class="panel"><div class="head"><h2>افزودن کلید</h2></div><div class="body form">
    <label class="f">صرافی<select id="kx">${ex.map(e => `<option value="${e.id}">${esc(e.fa)}</option>`).join('')}</select></label>
    <label class="f">نام دلخواه<input id="kl" maxlength="40" placeholder="مثلاً حساب اصلی"></label><label class="f">کلید API<input id="kk" class="ltr" autocomplete="off"></label>
    <div class="notice" style="font-size:12.5px">${esc(ex[0] ? ex[0].key_help : '')} کلید رمزنگاری‌شده ذخیره می‌شود، فقط موتور اجرا آن را باز می‌کند و پس از ذخیره دیگر نمایش داده نمی‌شود.</div>
    <button class="primary" id="ka">ذخیره و بررسی</button></div></div>
    <div class="panel"><div class="head"><h2>کلیدهای من</h2></div><div class="body table-wrap" id="kl2"></div></div></div>`);
  const load = async () => { const ks = await api('/api/keys').catch(() => []);
    $('#kl2').innerHTML = ks.length ? `<table><thead><tr><th>صرافی</th><th>نام</th><th>کلید</th><th>وضعیت</th><th></th></tr></thead><tbody>${ks.map(k => `<tr><td>${esc(k.exchange === 'wallex' ? 'والکس' : k.exchange)}</td><td>${esc(k.label || '—')}</td><td class="mono">…${esc(k.last4)}</td>
      <td>${k.status === 'verified' ? '<span class="chip ok">تأیید شد</span>' : k.status === 'failed' ? '<span class="chip bad">نامعتبر</span>' : '<span class="chip y">بررسی نشد</span>'}</td><td class="row"><button data-v="${k.id}">بررسی</button><button class="ghost danger" data-d="${k.id}">حذف</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty">کلیدی ثبت نشده است.</div>';
    $$('[data-v]').forEach(b => b.onclick = async () => { const r = await act(() => api(`/api/keys/${b.dataset.v}/verify`, {})); if (r) toast(r.status === 'verified' ? 'کلید معتبر است' : (r.check.error || 'نامعتبر'), r.status !== 'verified'); load(); });
    $$('[data-d]').forEach(b => b.onclick = async () => { if (confirm('کلید حذف شود؟')) { await act(() => api(`/api/keys/${b.dataset.d}/delete`, {}), 'حذف شد'); load(); } });
  };
  $('#ka').onclick = async () => { const r = await act(() => api('/api/keys', { exchange: $('#kx').value, label: $('#kl').value || null, api_key: $('#kk').value }));
    if (r) { $('#kk').value = ''; toast(r.status === 'verified' ? 'کلید ذخیره و تأیید شد' : 'کلید ذخیره شد ولی بررسی نشد: ' + ((r.check && r.check.error) || ''), r.status !== 'verified'); load(); } };
  load();
}

async function pageBilling(_, q) {
  await refreshMe().catch(() => null);
  const u = S.user;
  shell('اشتراک', `${q.status === 'paid' ? '<div class="notice mb">پرداخت موفق بود و پلن فعال شد.</div>' : q.status ? '<div class="notice red mb">پرداخت انجام نشد یا لغو شد.</div>' : ''}
    <div class="panel mb"><div class="body row" style="justify-content:space-between"><div>پلن فعلی: <b>${esc(u.plan ? u.plan.name : '—')}</b> ${u.plan_active ? '' : '<span class="chip bad">منقضی</span>'} <span class="faint">${u.plan_expires ? 'تا ' + when(u.plan_expires) : ''}</span></div><div class="faint">AI این ماه: ${n0(u.ai_quota.used)} از ${n0(u.ai_quota.limit)}</div></div></div>
    <div class="grid g3 mb">${S.meta.plans.map(p => `<div class="panel plan"><b>${esc(p.name)}</b><div class="price">${+p.price_tmn ? toman(p.price_tmn) : 'رایگان'}</div><div class="faint">${+p.price_tmn ? n0(p.days) + ' روز' : ''}</div><div class="muted" style="font-size:13px">${esc(p.description || '')}</div>
      <div style="font-size:12.5px">${n0(p.max_bots)} ربات · ${+p.max_live_bots ? n0(p.max_live_bots) + ' واقعی تا ' + toman(p.max_capital_tmn) : 'فقط آزمایشی'} · AI ${n0(p.ai_calls_month)} در ماه</div>
      ${+p.price_tmn ? `<button class="primary" data-p="${p.id}">${u.plan && u.plan.id === p.id ? 'تمدید' : 'خرید'}</button>` : ''}</div>`).join('')}</div>
    <div class="panel"><div class="head"><h2>پرداخت‌ها</h2></div><div class="body table-wrap" id="pays"></div></div>`);
  $$('[data-p]').forEach(b => b.onclick = async () => { const r = await act(() => api('/api/pay', { plan_id: b.dataset.p })); if (r) location.href = r.url; });
  const ps = await api('/api/payments').catch(() => []);
  $('#pays').innerHTML = ps.length ? `<table><thead><tr><th>زمان</th><th>پلن</th><th>مبلغ</th><th>وضعیت</th><th>کد پیگیری</th></tr></thead><tbody>${ps.map(p => `<tr><td>${when(p.created)}</td><td>${esc(p.plan_id)}</td><td>${toman(p.amount_rial / 10)}</td><td>${{ paid: '<span class="pos">موفق</span>', pending: 'در انتظار', cancelled: 'لغو', failed: '<span class="neg">ناموفق</span>' }[p.status] || esc(p.status)}${p.sandbox ? ' <span class="chip y">آزمایشی</span>' : ''}</td><td class="mono">${esc(p.ref_id || '—')}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">پرداختی ثبت نشده.</div>';
}

function pageProfile() {
  const u = S.user;
  shell('حساب من', `<div class="panel" style="max-width:520px"><div class="body form"><label class="f">نام<input id="nm" value="${esc(u.name || '')}" maxlength="60"></label><div class="muted">موبایل: <span class="mono">${esc(u.phone)}</span></div>
    <div class="row"><button class="primary" id="sv">ذخیره</button><button class="danger" id="out">خروج</button></div>${S.meta.support ? `<div class="faint">${esc(S.meta.support)}</div>` : ''}</div></div>`);
  $('#sv').onclick = () => act(() => api('/api/me/profile', { name: $('#nm').value }), 'ذخیره شد').then(refreshMe);
  $('#out').onclick = async () => { await api('/api/auth/logout', {}).catch(() => null); S.user = null; location.hash = '#home'; };
}

// ---------------------------------------------------------------- back office
async function pageAdmin() {
  shell('بک‌آفیس — نمای کلی', '<div class="empty">…</div>');
  every(15000, async () => {
    const d = await act(() => api('/api/admin/dashboard')); if (!d) return;
    const k = (l, v, n = '', c = '') => `<div class="panel kpi"><div class="l">${l}</div><div class="v ${c}">${v}</div><div class="n">${n}</div></div>`;
    $('#page').innerHTML = `<div class="grid g4 mb">${k('کاربران', n0(d.users), n0(d.new_users_7d) + ' کاربر جدید در ۷ روز')}${k('ربات‌ها', n0(d.bots), n0(d.running_paper) + ' آزمایشی فعال')}${k('ربات واقعی فعال', n0(d.running_live), 'سرمایه ' + toman(d.live_capital_tmn))}${k('در انتظار تأیید', n0(d.pending_approval), d.blocked ? n0(d.blocked) + ' ربات مسدود' : '', d.pending_approval ? 'warn' : '')}
      ${k('درآمد ۳۰ روز', toman(d.revenue_tmn_30d), 'فقط پرداخت‌های واقعی')}${k('درخواست AI این ماه', n0(d.ai_calls_month))}${k('پیامک', d.sms_configured ? 'تنظیم شده' : 'تنظیم نشده', '', d.sms_configured ? 'pos' : 'neg')}${k('درگاه', d.payment_sandbox ? 'آزمایشی (sandbox)' : 'واقعی', '', d.payment_sandbox ? 'warn' : 'pos')}</div>
      <div class="panel"><div class="head"><h2>کلیدهای توقف سراسری</h2></div><div class="body form">
        <label class="chk"><input type="checkbox" id="lt" ${d.switches.live_trading_enabled ? 'checked' : ''}> معامله با پول واقعی (خاموش = هیچ سفارش واقعی‌ای ارسال نمی‌شود)</label>
        <label class="chk"><input type="checkbox" id="ne" ${d.switches.new_entries_enabled ? 'checked' : ''}> ورودهای جدید همهٔ ربات‌ها (خاموش = فقط مدیریت خروج)</label>
        <div><button class="primary" id="sw">ذخیره</button></div></div></div>`;
    $('#sw').onclick = () => act(() => api('/api/admin/settings', { values: { 'platform.live_trading_enabled': $('#lt').checked, 'platform.new_entries_enabled': $('#ne').checked } }), 'ذخیره شد');
  });
}

async function pageAdminBots(_, q) {
  const tabs = [['pending_approval', 'در انتظار تأیید'], ['running', 'در حال اجرا'], ['blocked', 'مسدود'], ['', 'همه']];
  const cur = q.s ?? 'pending_approval';
  shell('بک‌آفیس — ربات‌ها', `<div class="row mb">${tabs.map(([k, t]) => `<a href="#admin-bots?s=${k}"><button class="${cur === k ? 'primary' : ''}">${t}</button></a>`).join('')}</div><div class="panel"><div class="body table-wrap" id="ab"></div></div>`);
  const rows = await act(() => api('/api/admin/bots?status=' + cur)); if (!rows) return;
  $('#ab').innerHTML = rows.length ? `<table><thead><tr><th>ربات</th><th>کاربر</th><th>حالت</th><th>وضعیت</th><th>سرمایه</th><th>ارزش</th><th>نمادها</th><th></th></tr></thead><tbody>${rows.map(b => `<tr><td>${esc(b.name)}</td><td class="mono">${esc(b.phone)}</td><td>${b.mode === 'live' ? 'واقعی' : 'آزمایشی'}${b.live_approved ? ' ✓' : ''}</td><td>${chip(b.status)}</td><td>${toman(b.config.capital_tmn)}</td><td>${toman(b.equity_tmn)}</td><td style="font-size:12px">${esc(b.config.symbols.join('، '))}</td><td><button data-b="${b.id}">بررسی</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty">موردی نیست.</div>';
  $$('[data-b]').forEach(x => x.onclick = () => adminBotModal(x.dataset.b));
}
async function adminBotModal(id) {
  const b = await act(() => api('/api/admin/bots/' + id)); if (!b) return;
  const c = b.config;
  const m = modal(`<div class="head" style="padding:12px 16px;border-bottom:1px solid var(--line)"><h2 style="margin:0;font-size:15px">${esc(b.name)} ${chip(b.status)}</h2></div><div class="body" style="padding:14px 16px">
    <div class="muted" style="font-size:12.5px">کاربر: <span class="mono">${esc(b.user.phone)}</span> · پلن ${esc(b.user.plan_id || '—')} · ${b.mode === 'live' ? 'واقعی' : 'آزمایشی'} · کلید ${esc(b.key_id || '—')}</div>
    <table style="margin:10px 0"><tr><td class="muted">سرمایه</td><td>${toman(c.capital_tmn)}</td></tr><tr><td class="muted">نمادها</td><td>${esc(c.symbols.join('، '))}</td></tr><tr><td class="muted">تایم‌فریم / استراتژی‌ها</td><td>${esc(c.timeframe)} · ${c.strategies.length} استراتژی</td></tr>
      <tr><td class="muted">ریسک</td><td>${pct(c.risk_pct).replace('+', '')} هر معامله · حداکثر ${n0(c.max_positions)} موقعیت · سقف دارایی ${n0(c.max_asset_pct)}٪</td></tr><tr><td class="muted">AI</td><td>${c.ai_filter ? 'فعال، اطمینان ≥ ' + n2(c.ai_min_confidence) : 'خاموش'}</td></tr>
      <tr><td class="muted">ارزش / معاملات</td><td>${toman(b.equity_tmn)} · ${b.trades.length} معامله</td></tr>${b.last_error ? `<tr><td class="muted">خطا</td><td class="neg">${esc(b.last_error)}</td></tr>` : ''}</table>
    <label class="f">یادداشت برای کاربر<input id="note" maxlength="300" value="${esc(b.review_note || '')}"></label>
    <div class="row" style="margin-top:10px">${b.mode === 'live' && !b.live_approved ? '<button class="primary" data-x="approve">تأیید اجرای واقعی</button>' : ''}${b.mode === 'live' ? '<button class="danger" data-x="reject">رد / لغو تأیید</button>' : ''}
      ${b.status === 'running' ? '<button data-x="pause">توقف ورود</button>' : ''}${['running', 'paused'].includes(b.status) ? '<button data-x="stop">توقف</button>' : ''}${b.status === 'blocked' ? '<button data-x="resolve" title="پس از بررسی دستی در صرافی">رفع انسداد</button>' : ''}<button class="ghost" data-x="close">بستن</button></div></div>`);
  $$('[data-x]', m).forEach(x => x.onclick = async () => {
    const a = x.dataset.x; if (a === 'close') { m.remove(); return; }
    if (a === 'resolve' && !confirm('سفارش‌های نامعلوم را در صرافی بررسی کرده‌اید و ثبت نشده‌اند؟')) return;
    if (await act(() => api(`/api/admin/bots/${id}/${a}`, { note: $('#note', m).value || null }), 'انجام شد')) { m.remove(); route(); }
  });
}

async function pageAdminUsers(_, q) {
  shell('بک‌آفیس — کاربران', `<div class="row mb"><input id="uq" placeholder="جست‌وجوی شماره یا نام" value="${esc(q.q || '')}" style="max-width:300px"><button id="us">جست‌وجو</button></div><div class="panel"><div class="body table-wrap" id="ul"></div></div>`);
  $('#us').onclick = () => { location.hash = '#admin-users?q=' + encodeURIComponent($('#uq').value); };
  const [rows, plans] = await Promise.all([api('/api/admin/users?q=' + encodeURIComponent(q.q || '')), api('/api/admin/plans')]);
  $('#ul').innerHTML = `<table><thead><tr><th>موبایل</th><th>نام</th><th>نقش</th><th>وضعیت</th><th>پلن</th><th>ربات</th><th>AI</th><th>عضویت</th><th></th></tr></thead><tbody>${rows.map(u => `<tr><td class="mono">${esc(u.phone)}</td><td>${esc(u.name || '—')}</td><td>${u.role === 'admin' ? '<span class="chip a">ادمین</span>' : 'کاربر'}</td><td>${u.status === 'active' ? '<span class="pos">فعال</span>' : '<span class="neg">مسدود</span>'}</td><td>${esc(u.plan_id || '—')} <span class="faint" style="font-size:11.5px">${u.plan_expires ? when(u.plan_expires) : ''}</span></td><td>${n0(u.bots)}</td><td>${n0(u.ai_quota.used)}/${n0(u.ai_quota.limit)}</td><td style="font-size:12px">${when(u.created)}</td><td><button data-u="${u.id}">ویرایش</button></td></tr>`).join('')}</tbody></table>`;
  $$('[data-u]').forEach(b => b.onclick = () => {
    const u = rows.find(x => x.id === b.dataset.u);
    const m = modal(`<div class="body form" style="padding:16px"><h2 style="margin:0;font-size:15px">${esc(u.phone)}</h2><label class="f">نام<input id="mn" value="${esc(u.name || '')}"></label>
      <div class="grid g2"><label class="f">نقش<select id="mr"><option value="user" ${u.role === 'user' ? 'selected' : ''}>کاربر</option><option value="admin" ${u.role === 'admin' ? 'selected' : ''}>ادمین</option></select></label><label class="f">وضعیت<select id="ms"><option value="active" ${u.status === 'active' ? 'selected' : ''}>فعال</option><option value="blocked" ${u.status === 'blocked' ? 'selected' : ''}>مسدود</option></select></label></div>
      <div class="grid g2"><label class="f">پلن<select id="mp"><option value="">بدون تغییر</option>${plans.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></label><label class="f">مدت (روز)<input id="md" type="number" placeholder="پیش‌فرض پلن"></label></div>
      <label class="f">سهمیهٔ AI اختصاصی در ماه (خالی = طبق پلن)<input id="ma" type="number" value="${u.ai_quota_override ?? ''}"></label><div class="row"><button class="primary" id="msv">ذخیره</button><button class="ghost" id="mc">انصراف</button></div></div>`);
    $('#mc', m).onclick = () => m.remove();
    $('#msv', m).onclick = async () => { const body = { name: $('#mn', m).value, role: $('#mr', m).value, status: $('#ms', m).value };
      if ($('#mp', m).value) { body.plan_id = $('#mp', m).value; if ($('#md', m).value) body.plan_days = +$('#md', m).value; }
      if ($('#ma', m).value === '') body.clear_ai_override = true; else body.ai_quota_override = +$('#ma', m).value;
      if (await act(() => api('/api/admin/users/' + u.id, body), 'ذخیره شد')) { m.remove(); route(); } };
  });
}

async function pageAdminPlans() {
  shell('بک‌آفیس — پلن‌ها', '<div class="panel"><div class="body table-wrap" id="pl"></div></div>', '<button class="primary" id="np">پلن جدید</button>');
  const plans = await api('/api/admin/plans');
  $('#pl').innerHTML = `<table><thead><tr><th>شناسه</th><th>نام</th><th>قیمت</th><th>مدت</th><th>ربات</th><th>واقعی</th><th>سقف سرمایه</th><th>AI/ماه</th><th>فعال</th><th></th></tr></thead><tbody>${plans.map(p => `<tr><td class="mono">${esc(p.id)}</td><td>${esc(p.name)}</td><td>${toman(p.price_tmn)}</td><td>${n0(p.days)} روز</td><td>${n0(p.max_bots)}</td><td>${n0(p.max_live_bots)}</td><td>${toman(p.max_capital_tmn)}</td><td>${n0(p.ai_calls_month)}</td><td>${p.active ? '✓' : '—'}</td><td><button data-p="${p.id}">ویرایش</button></td></tr>`).join('')}</tbody></table>`;
  const edit = p => {
    p = p || { id: '', name: '', price_tmn: 0, days: 30, max_bots: 3, max_live_bots: 1, max_capital_tmn: 50000000, ai_calls_month: 300, active: 1, sort: plans.length, description: '' };
    const f = (k, l, t = 'number') => `<label class="f">${l}<input id="p_${k}" type="${t}" value="${esc(p[k])}"></label>`;
    const m = modal(`<div class="body form" style="padding:16px"><h2 style="margin:0;font-size:15px">${p.id ? 'ویرایش پلن' : 'پلن جدید'}</h2><div class="grid g2">${f('id', 'شناسه (لاتین)', 'text')}${f('name', 'نام', 'text')}${f('price_tmn', 'قیمت (تومان)')}${f('days', 'مدت (روز)')}${f('max_bots', 'حداکثر ربات')}${f('max_live_bots', 'حداکثر ربات واقعی')}${f('max_capital_tmn', 'سقف سرمایهٔ هر ربات واقعی')}${f('ai_calls_month', 'درخواست AI در ماه')}${f('sort', 'ترتیب')}</div>
      ${f('description', 'توضیح', 'text')}<label class="chk"><input type="checkbox" id="p_active" ${p.active ? 'checked' : ''}> فعال</label><div class="row"><button class="primary" id="ps">ذخیره</button><button class="ghost" id="pc">انصراف</button></div></div>`);
    $('#pc', m).onclick = () => m.remove();
    $('#ps', m).onclick = async () => { const v = k => $('#p_' + k, m).value; const body = { id: v('id') || null, name: v('name'), description: v('description'), active: $('#p_active', m).checked };
      ['price_tmn', 'days', 'max_bots', 'max_live_bots', 'max_capital_tmn', 'ai_calls_month', 'sort'].forEach(k => body[k] = +v(k));
      if (await act(() => api('/api/admin/plans', body), 'ذخیره شد')) { m.remove(); route(); } };
  };
  $('#np').onclick = () => edit(null);
  $$('[data-p]').forEach(b => b.onclick = () => edit(plans.find(p => p.id === b.dataset.p)));
}

async function pageAdminSettings() {
  shell('بک‌آفیس — تنظیمات', '<div id="sets"></div>');
  const d = await act(() => api('/api/admin/settings')); if (!d) return;
  const groups = {};
  d.settings.forEach(s => (groups[s.key.split('.')[0]] = groups[s.key.split('.')[0]] || []).push(s));
  const input = s => {
    if (s.kind === 'bool') return `<label class="chk"><input type="checkbox" data-k="${s.key}" ${s.value ? 'checked' : ''}> ${esc(s.label)}</label>`;
    if (s.secret) return `<label class="f">${esc(s.label)} ${s.value.set ? `<span class="chip ok">تنظیم شده …${esc(s.value.last4)}</span>` : '<span class="chip bad">تنظیم نشده</span>'}<input data-k="${s.key}" data-secret="1" class="ltr" placeholder="برای تغییر وارد کنید" autocomplete="off"></label>`;
    if (s.kind.startsWith('choice:')) return `<label class="f">${esc(s.label)}<select data-k="${s.key}">${s.kind.slice(7).split(',').map(o => `<option ${o === s.value ? 'selected' : ''}>${o}</option>`).join('')}</select></label>`;
    if (s.key === 'llm.provider') return `<label class="f">${esc(s.label)}<select data-k="${s.key}">${Object.entries(d.llm_providers).map(([k, p]) => `<option value="${k}" ${k === s.value ? 'selected' : ''}>${esc(p.fa)}</option>`).join('')}</select></label>`;
    const ltr = /url|key|sender|pattern|merchant|model|variable|plan_id/.test(s.key) ? 'ltr' : '';
    return `<label class="f">${esc(s.label)}<input data-k="${s.key}" class="${ltr}" ${s.kind === 'int' ? 'type="number"' : ''} value="${esc(s.value)}"></label>`;
  };
  $('#sets').innerHTML = Object.entries(groups).map(([g, list]) => `<div class="panel mb"><div class="head"><h2>${esc(d.groups[g] || g)}</h2>${g === 'sms' ? '<div class="row"><input id="tp" class="ltr" placeholder="09..." style="width:150px"><button id="tsend">ارسال پیامک آزمایشی</button></div>' : ''}</div><div class="body grid g2">${list.map(input).join('')}</div></div>`).join('')
    + '<div class="row"><button class="primary" id="save">ذخیرهٔ همهٔ تنظیمات</button><span class="faint">فیلدهای کلید خالی یعنی «بدون تغییر».</span></div>';
  $('#save').onclick = async () => {
    const values = {};
    $$('[data-k]').forEach(i => { const s = d.settings.find(x => x.key === i.dataset.k); values[i.dataset.k] = s.kind === 'bool' ? i.checked : s.kind === 'int' ? +i.value : i.value; });
    if (await act(() => api('/api/admin/settings', { values }), 'تنظیمات ذخیره شد')) { S.meta = await api('/api/meta'); route(); }
  };
  if ($('#tsend')) $('#tsend').onclick = () => act(() => api('/api/admin/sms-test', { phone: $('#tp').value }), 'پیامک آزمایشی (کد 123456) ارسال شد');
}

async function pageAdminPayments() {
  shell('بک‌آفیس — پرداخت‌ها', '<div class="panel"><div class="body table-wrap" id="ap"></div></div>');
  const rows = await act(() => api('/api/admin/payments')); if (!rows) return;
  $('#ap').innerHTML = rows.length ? `<table><thead><tr><th>زمان</th><th>کاربر</th><th>پلن</th><th>مبلغ</th><th>وضعیت</th><th>کد پیگیری</th><th>کارت</th></tr></thead><tbody>${rows.map(p => `<tr><td>${when(p.created)}</td><td class="mono">${esc(p.phone)}</td><td>${esc(p.plan_id)}</td><td>${toman(p.amount_rial / 10)}</td><td>${esc(p.status)}${p.sandbox ? ' <span class="chip y">آزمایشی</span>' : ''}</td><td class="mono">${esc(p.ref_id || '—')}</td><td class="mono">${esc(p.card_pan || '—')}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">پرداختی نیست.</div>';
}
async function pageAdminAudit() {
  shell('بک‌آفیس — رویدادها', '<div class="panel"><div class="body table-wrap" id="au"></div></div>');
  const rows = await act(() => api('/api/admin/audit')); if (!rows) return;
  $('#au').innerHTML = `<table><thead><tr><th>زمان</th><th>کاربر</th><th>رویداد</th><th>جزئیات</th></tr></thead><tbody>${rows.map(r => `<tr><td style="font-size:12px">${when(r.at)}</td><td class="mono" style="font-size:12px">${esc(r.actor || '—')}</td><td>${esc(r.action)}</td><td class="mono" style="font-size:11.5px;max-width:480px;overflow-wrap:anywhere">${esc(JSON.stringify(r.detail))}</td></tr>`).join('')}</tbody></table>`;
}

// ---------------------------------------------------------------- boot
(async () => {
  try { [S.meta] = await Promise.all([api('/api/meta'), refreshMe().catch(() => null)]); }
  catch (e) { $('#app').innerHTML = `<div class="boot">اتصال به سرور برقرار نشد</div>`; return; }
  document.title = S.meta.site_name + ' — ربات معامله‌گر خودت را بساز';
  route();
})();
