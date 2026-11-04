// Landing, sign-in, bots, bot builder, exchange keys, subscription and profile (Nova look).
import { S, api, n0, n2, toman, pct, signCls, when, esc, h, $, $$, botChip, download } from './core.js';
import { background } from '/nova/js/fx.js';

export function toast(msg, err = false) {
  const t = $('#toast') || document.body.appendChild(h('<div id="toast" class="toast hidden"></div>'));
  t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); clearTimeout(t._h); t._h = setTimeout(() => t.classList.add('hidden'), 4200);
}
export async function act(fn, ok) { try { const r = await fn(); if (ok) toast(ok); return r; } catch (e) { toast(e.message, true); return null; } }
export function modal(html) {
  const m = h(`<div class="modal"><div class="panel">${html}</div></div>`);
  m.onclick = e => { if (e.target === m) m.remove(); }; document.body.appendChild(m); return m;
}
const post = (path, body = {}) => api(path, { body });

// ------------------------------------------------------------------ run window (schedule)
const localInput = ts => ts ? new Date(ts * 1000 - new Date(ts * 1000).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
const fromInput = v => v ? Math.floor(new Date(v).getTime() / 1000) : null;
export function scheduleText(s, status) {
  s = s || {}; const now = Date.now() / 1000;
  if (status === 'scheduled' && s.from && s.from > now) return 'شروع خودکار ' + when(s.from) + (s.until ? ' · پایان ' + when(s.until) : ' · بدون پایان');
  if (s.until) return (s.until > now ? 'پایان ' : 'بازه تمام شد ') + when(s.until) + (s.from ? ' · شروع ' + when(s.from) : '');
  return s.from && s.from > now ? 'شروع ' + when(s.from) + ' · بدون پایان' : 'نامحدود (تا وقتی متوقفش کنید)';
}
export function scheduleFields(s) {
  s = s || {}; const acts = S.meta.end_actions || {};
  return `<div class="lgrid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      <label class="lf"><span>شروع (به وقت شما؛ خالی = همان لحظهٔ «شروع»)</span><input type="datetime-local" data-s="from" value="${localInput(s.from)}"></label>
      <label class="lf"><span>پایان</span><input type="datetime-local" data-s="until" value="${localInput(s.until)}" ${s.until ? '' : 'disabled'}></label>
      <label class="chk" style="align-self:end;padding-bottom:8px"><input type="checkbox" data-s="unlimited" ${s.until ? '' : 'checked'}> نامحدود (بدون تاریخ پایان)</label></div>
    <div class="prov" data-s="actions">${Object.entries(acts).map(([k, t]) => `<div class="pcard ${(s.end_action || 'close') === k ? 'on' : ''}" data-act="${k}"><b>${k === 'close' ? 'در پایان: فروش و توقف' : 'در پایان: فقط مدیریت خروج'}</b><span class="faint">${esc(t)}</span></div>`).join('')}</div>
    <div class="faint" style="font-size:11.5px">در پایان بازه ورود جدید انجام نمی‌شود و ربات طبق انتخاب بالا موقعیت‌ها را می‌بندد. زمان‌ها به وقت مرورگر شما (تهران) هستند.</div>`;
}
export function bindSchedule(root) {
  const un = root.querySelector('[data-s=unlimited]'), until = root.querySelector('[data-s=until]');
  un.onchange = () => { until.disabled = un.checked; if (!un.checked && !until.value) until.value = localInput(Math.floor(Date.now() / 1000) + 7 * 86400); };
  root.querySelectorAll('[data-act]').forEach(c => c.onclick = () => root.querySelectorAll('[data-act]').forEach(x => x.classList.toggle('on', x === c)));
  return () => ({ from: fromInput(root.querySelector('[data-s=from]').value), until: un.checked ? null : fromInput(until.value),
    end_action: (root.querySelector('[data-act].on') || {}).dataset ? root.querySelector('[data-act].on').dataset.act : 'close' });
}
export function scheduleModal(bot, done) {
  const m = modal(`<div class="head"><h2>بازهٔ زمانی اجرای «${esc(bot.name)}»</h2></div><div class="body form" id="schf">${scheduleFields(bot.config.schedule)}
    <div class="row"><button class="primary" id="schsave">ذخیره</button><button id="schc">انصراف</button></div>
    <div class="faint" style="font-size:11.5px">تغییر بازه قواعد ربات را عوض نمی‌کند و تأیید اجرای واقعی سر جایش می‌ماند.</div></div>`);
  const read = bindSchedule($('#schf', m));
  $('#schc', m).onclick = () => m.remove();
  $('#schsave', m).onclick = async () => { if (await act(() => post(`/api/bots/${bot.id}/schedule`, { schedule: read() }), 'بازهٔ زمانی ذخیره شد')) { m.remove(); done && done(); } };
}
const PRESET_TXT = p => `ریسک ${pct(p.risk_pct, 1).replace('+', '')} هر معامله · حداکثر ${n0(p.max_positions)} موقعیت · کیفیت ≥ ${n0(p.min_quality)}`;
const famChip = f => `<span class="chip ${f === 'smart_money' ? 'smc' : 'ind'}">${f === 'smart_money' ? 'SMC' : f === 'hybrid' ? 'ترکیبی' : 'اندیکاتور'}</span>`;

// ------------------------------------------------------------------ public (the landing page lives in landing.js)
export function pageLogin(done) {
  let phone = '', timer = null;
  document.body.innerHTML = `<canvas id="fx" aria-hidden="true"></canvas><div class="land"><header class="top"><a class="brand" href="#home"><img src="/assets/mark.svg" alt=""><div><b>${esc(S.meta.site_name)}</b><small>ALGORITHMIC TRADING BOTS</small></div></a></header>
    <section class="panel glow login"><div class="head"><h2>ورود / ثبت‌نام</h2><a class="tools" href="#home">بازگشت</a></div><div class="body form" id="lf">
      <label>شمارهٔ موبایل<input id="ph" class="ltr" inputmode="tel" placeholder="09121234567" autocomplete="tel" style="width:100%"></label>
      <button class="primary" id="send">دریافت کد</button><div class="faint" style="font-size:12px">کد ۶ رقمی با پیامک ارسال می‌شود. حساب در اولین ورود ساخته می‌شود.</div></div></section></div><div id="toast" class="toast hidden"></div>`;
  background($('#fx'));
  const step2 = r => {
    $('#lf').innerHTML = `<div class="muted">کد ارسال‌شده به <b class="mono">${esc(r.phone)}</b> را وارد کنید${r.dev_code ? ` <span class="chip y">حالت توسعه: ${esc(r.dev_code)}</span>` : ''}</div>
      <input id="code" class="code ltr" inputmode="numeric" maxlength="6" autocomplete="one-time-code"><button class="primary" id="verify">ورود</button>
      <div class="row"><button id="resend" disabled>ارسال دوباره</button><span class="faint" id="cd"></span><a href="#login" id="chg" class="faint" style="margin-inline-start:auto">تغییر شماره</a></div>`;
    let left = r.resend_after; clearInterval(timer);
    timer = setInterval(() => { left--; if ($('#cd')) $('#cd').textContent = left > 0 ? n0(left) + ' ثانیه' : ''; if (left <= 0) { clearInterval(timer); if ($('#resend')) $('#resend').disabled = false; } }, 1000);
    $('#code').focus();
    const go = async () => { const v = await act(() => post('/api/auth/verify', { phone, code: $('#code').value })); if (v) { S.user = v.user; S.csrf = v.csrf; S.authenticated = true; clearInterval(timer); location.hash = '#live'; done(); } };
    $('#verify').onclick = go; $('#code').oninput = () => { if ($('#code').value.length === 6) go(); };
    $('#resend').onclick = send; $('#chg').onclick = () => { clearInterval(timer); pageLogin(done); };
  };
  async function send() { phone = phone || $('#ph').value; const r = await act(() => post('/api/auth/request', { phone })); if (r) { phone = r.phone; step2(r); } }
  $('#send').onclick = send; $('#ph').onkeydown = e => { if (e.key === 'Enter') send(); }; $('#ph').focus();
}

async function refreshMe() { const r = await api('/api/auth/me'); S.user = r.user; S.csrf = r.csrf || S.csrf; return S.user; }

// ------------------------------------------------------------------ bots
export function pageBots(root, ctx) {
  root.innerHTML = `<section class="grid g4" id="bk" style="margin-bottom:14px"></section>
    <div class="row" style="display:flex;gap:8px;margin-bottom:14px"><a href="#new"><button class="primary">＋ ربات جدید</button></a><a href="#research"><button>بک‌تست</button></a><a href="#studio"><button>استودیوی استراتژی</button></a></div>
    <section class="grid g3" id="blist"><div class="skeleton" style="height:160px"></div></section>`;
  ctx.every(15000, async () => {
    const bots = await ctx.refreshBots(); await refreshMe().catch(() => null);
    const u = S.user; if (!u) return;
    const live = bots.filter(b => b.mode === 'live'), paper = bots.filter(b => b.mode === 'paper');
    const total = l => l.reduce((a, b) => a + (+b.equity_tmn || 0), 0);
    const k = (a, b, c) => `<div class="panel kpi"><div class="label">${a}</div><div class="value">${b}</div><div class="note">${c}</div></div>`;
    $('#bk').innerHTML = k('پلن', esc(u.plan ? u.plan.name : 'بدون پلن'), u.plan_active ? (u.plan_expires ? 'تا ' + when(u.plan_expires) : '') : '<a href="#billing">فعال‌سازی پلن</a>')
      + k('سهمیهٔ AI این ماه', n0(u.ai_quota.used) + ' / ' + n0(u.ai_quota.limit), 'درخواست')
      + k('ربات‌های واقعی', n0(live.length), 'ارزش: ' + toman(total(live))) + k('ربات‌های آزمایشی', n0(paper.length), 'ارزش مجازی: ' + toman(total(paper)));
    $('#blist').innerHTML = bots.length ? bots.map(botCard).join('') : `<div class="panel span2"><div class="empty">هنوز رباتی نساخته‌اید.<br><br><a href="#new"><button class="primary">ساخت اولین ربات</button></a></div></div>`;
    $$('#blist [data-open]').forEach(x => x.onclick = e => { if (e.target.closest('a,button')) return; S.bot = x.dataset.open; try { localStorage.setItem('algo.bot', S.bot); } catch (_) { /* optional */ } location.hash = '#live'; });
  });
}
function botCard(b) {
  const pnl = (+b.equity_tmn) - (+b.config.capital_tmn);
  return `<div class="panel botcard" data-open="${b.id}"><div class="body">
    <div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><b style="font-size:15px">${esc(b.name)}</b>${botChip(b.status)}</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0"><span class="chip ${b.mode === 'live' ? 'y' : ''}">${b.mode === 'live' ? 'واقعی' : 'آزمایشی'}</span><span class="chip">${b.exchange === 'wallex' ? 'والکس' : esc(b.exchange)}</span><span class="chip">${esc(b.config.timeframe)}</span>${b.config.market_type === 'margin' ? `<span class="chip smc">تعهدی ×${n0(b.config.leverage)} · ${({ long: 'لانگ', short: 'شورت', both: 'لانگ و شورت' })[b.config.sides] || ''}</span>` : ''}<span class="chip">${n0(b.config.symbols.length)} نماد</span>${b.config.ai_filter ? '<span class="chip smc">AI</span>' : ''}</div>
    <table><tr><td class="muted">ارزش</td><td><b>${toman(b.equity_tmn)}</b></td></tr><tr><td class="muted">سود/زیان</td><td class="${signCls(pnl)}">${toman(pnl)} (${pct(pnl / b.config.capital_tmn * 100)})</td></tr>
    <tr><td class="muted">موقعیت باز</td><td>${n0(Object.keys(b.positions).length)}</td></tr><tr><td class="muted">زمان اجرا</td><td style="font-size:12px">${esc(scheduleText(b.config.schedule, b.status))}</td></tr></table>
    ${b.last_error ? `<div class="faint neg" style="font-size:12px">${esc(b.last_error)}</div>` : ''}
    <div style="display:flex;gap:6px;margin-top:8px"><button class="primary" style="flex:1">داشبورد ←</button>${['stopped', 'blocked'].includes(b.status) ? `<a href="#edit/${b.id}"><button>ویرایش</button></a>` : ''}</div></div></div>`;
}

// The live-approval request box (key choice) for a live bot.
export async function liveRequest(node, b, done) {
  if (b.status === 'pending_approval') { node.innerHTML = '<div class="notice" style="font-size:12px">درخواست اجرای واقعی در انتظار بررسی ادمین است.</div>'; return; }
  const keys = (await api('/api/keys').catch(() => [])).filter(k => k.exchange === b.exchange && k.status === 'verified');
  node.innerHTML = `${b.review_note ? `<div class="notice red" style="font-size:12px;margin-bottom:6px">${esc(b.review_note)}</div>` : ''}<div class="row" style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
    <select id="lkey" style="max-width:220px">${keys.map(k => `<option value="${k.id}">${esc(k.label || 'کلید')} …${esc(k.last4)}</option>`).join('') || '<option value="">کلید تأییدشده ندارید</option>'}</select>
    <button class="primary" id="lreq">درخواست اجرای واقعی</button><a href="#keys" class="faint">کلیدها</a></div>`;
  $('#lreq', node).onclick = async () => { if (!$('#lkey', node).value) return toast('اول یک کلید API تأییدشده اضافه کنید', true); if (await act(() => post(`/api/bots/${b.id}/request-live`, { key_id: $('#lkey', node).value }), 'درخواست ثبت شد')) done(); };
}

// ------------------------------------------------------------------ builder
export async function pageBuilder(root, ctx, id) {
  const bot = id ? await act(() => api('/api/bots/' + id)) : null;
  if (id && !bot) return;
  const m = S.meta; const strategies = await api('/api/me/strategies').catch(() => m.strategies);
  const { fa: _fa, ...balanced } = m.presets.balanced;
  const d = bot ? { ...bot.config } : { ...m.defaults, ...balanced, preset: 'balanced', ai_filter: true, ai_min_confidence: 0.65, symbols: ['BTCTMN', 'ETHTMN', 'SOLTMN', 'XRPTMN', 'DOGETMN'], capital_tmn: 10000000 };
  let mode = bot ? bot.mode : 'paper', exchange = bot ? bot.exchange : 'wallex', symbols = [...d.symbols], preset = d.preset || 'balanced';
  let mtype = d.market_type || 'spot', sides = d.sides && d.market_type === 'margin' ? d.sides : 'both';
  const num = (key, label, v, step) => `<label class="lf"><span>${label}</span><input id="${key}" type="number" step="${step}" value="${v ?? ''}"></label>`;
  root.innerHTML = `
    <section class="panel" style="margin-bottom:14px"><div class="head"><h2>۱. صرافی و حالت اجرا</h2></div><div class="body form">
      <label class="lf" style="max-width:360px"><span>نام ربات</span><input id="bn" value="${esc(bot ? bot.name : 'ربات من')}" maxlength="60"></label>
      <div class="prov" id="exch">${m.exchanges.map(e => `<div class="pcard ${e.enabled ? '' : 'off'}" data-x="${e.id}"><b>${esc(e.fa)}</b><span class="faint">${e.enabled ? 'فعال' : 'به‌زودی'}</span></div>`).join('')}</div>
      <div class="prov" id="mode"><div class="pcard" data-m="paper"><b>آزمایشی (کاغذی)</b><span class="faint">قیمت‌های زندهٔ بازار، بدون پول واقعی</span></div><div class="pcard" data-m="live"><b>واقعی</b><span class="faint">روی حساب صرافی خودت؛ پس از تأیید ادمین</span></div></div>
      <div class="prov" id="mtype"><div class="pcard" data-t="spot"><b>اسپات</b><span class="faint">خرید و فروش خود دارایی، بدون اهرم</span></div><div class="pcard" data-t="margin"><b>تعهدی (اهرمی)</b><span class="faint">معامله تعهدی والکس: لانگ و شورت با نسبت اعتبار</span></div></div>
      <div id="marginbox" class="form hidden"><div class="lgrid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
        <label class="lf"><span>نسبت اعتبار (اهرم) — حداکثر ${n0((m.margin || {}).max_leverage || 5)} برابر</span><input id="lev" type="number" min="1" max="${(m.margin || {}).max_leverage || 5}" step="1" value="${d.market_type === 'margin' ? d.leverage : 2}"></label>
        <div class="lf"><span>سمت معامله</span><div class="prov" id="sides" style="grid-template-columns:repeat(3,minmax(0,1fr))">${[['long', 'فقط لانگ'], ['short', 'فقط شورت'], ['both', 'هر دو']].map(([k, t]) => `<div class="pcard ${(d.sides || 'both') === k ? 'on' : ''}" data-side="${k}"><b>${t}</b></div>`).join('')}</div></div></div>
        <div class="notice red" style="font-size:12px">معامله تعهدی پرریسک است: با اهرم k، هر ۱٪ حرکت قیمت k٪ وثیقه را جابه‌جا می‌کند و در حرکت مخالف موقعیت لیکویید می‌شود. ربات هیچ ورودی را که حد ضررش بعد از قیمت لیکویید باشد باز نمی‌کند، حد ضرر و حد سود را از همان لحظهٔ باز شدن روی صرافی ثبت می‌کند و موقعیت حداکثر ۲۱ روز (عمر موقعیت در والکس) باز می‌ماند. شورت‌ها با همان استراتژی‌ها روی قیمت معکوس پیدا می‌شوند. کارمزد فعال‌سازی و تمدید ۴ساعته از وثیقه کسر می‌شود.</div></div></div></section>
    <section class="panel" style="margin-bottom:14px"><div class="head"><h2>۲. بازار و استراتژی</h2></div><div class="body form">
      <div class="lf"><span>نمادها <b id="symc" class="chip y"></b></span><div id="syms" style="display:flex;gap:6px;flex-wrap:wrap;margin:4px 0"></div>
        <div class="row"><input id="sq" list="mk" class="ltr" placeholder="افزودن نماد، مثلاً ADATMN" style="width:220px"><datalist id="mk">${m.markets.map(x => `<option value="${x.symbol}">`).join('')}</datalist>
        <button id="sadd">افزودن</button><button data-pre="major">BTC + ETH</button><button data-pre="top10">۱۰ بازار بزرگ</button><button data-pre="clear">پاک کردن</button></div></div>
      <label class="lf" style="max-width:260px"><span>تایم‌فریم سیگنال</span><select id="tf">${m.timeframes.map(t => `<option value="${t.id}" ${t.id === d.timeframe ? 'selected' : ''}>${t.fa}</option>`).join('')}</select></label>
      <div class="lf"><span>استراتژی‌ها</span><div id="lstrats" style="display:flex;gap:10px;flex-wrap:wrap">${strategies.map(s => `<label class="chk" title="${esc(s.thesis)}"><input type="checkbox" value="${s.id}" ${d.strategies.includes(s.id) ? 'checked' : ''}> ${famChip(s.family)}${s.custom ? ' <span class="chip y">استودیو</span>' : ''} ${esc(s.fa)}</label>`).join('')}</div>
        <div class="faint" style="font-size:11.5px">استراتژی‌های «استودیو» پس از آزمون کامل و تأیید در استودیوی استراتژی اینجا ظاهر می‌شوند.</div></div></div></section>
    <section class="panel" style="margin-bottom:14px"><div class="head"><h2>۳. سرمایه و ریسک</h2></div><div class="body form">
      <label class="lf" style="max-width:260px"><span>سرمایهٔ ربات (تومان)</span><input id="cap" type="number" min="500000" step="100000" value="${d.capital_tmn}"></label>
      <div class="prov" id="pre">${Object.entries(m.presets).map(([k, p]) => `<div class="pcard" data-p="${k}"><b>${esc(p.fa)}</b><span class="faint">${PRESET_TXT(p)}</span></div>`).join('')}<div class="pcard" data-p="custom"><b>سفارشی</b><span class="faint">همهٔ پارامترها دست خودت</span></div></div>
      <details id="adv"><summary>تنظیمات پیشرفته</summary><div class="lgrid">
        ${num('risk_pct', 'ریسک هر معامله ٪', d.risk_pct, 0.05)}${num('max_positions', 'حداکثر موقعیت هم‌زمان', d.max_positions, 1)}${num('min_quality', 'حداقل کیفیت ستاپ (۰ تا ۱۰۰)', d.min_quality, 1)}
        ${num('max_asset_pct', 'سقف هر دارایی ٪ (خالی = خودکار)', d.max_asset_pct, 1)}${num('max_gross_pct', 'سقف ناخالص ٪', d.max_gross_pct, 1)}${num('min_stop_pct', 'حد ضرر کمینه ٪ (خالی = خودکار)', d.min_stop_pct, 0.1)}
        ${num('max_stop_pct', 'حد ضرر بیشینه ٪', d.max_stop_pct, 0.1)}${num('trend_tp_r', 'TP1 روندی (برابر R)', d.trend_tp_r, 0.1)}${num('max_hold_hours', 'حداکثر نگهداری (ساعت، خالی = استراتژی)', d.max_hold_hours, 1)}
        ${num('cooldown_bars', 'مکث پس از خروج (کندل)', d.cooldown_bars, 1)}${num('breakeven_buffer_pct', 'حاشیهٔ سربه‌سر ٪', d.breakeven_buffer_pct, 0.1)}
        <label class="lf"><span>مدل خروج</span><select id="exit_mode"><option value="ladder" ${d.exit_mode === 'ladder' ? 'selected' : ''}>سه TP با فاصلهٔ برابر + حد ضرر پله‌ای</option><option value="single" ${d.exit_mode === 'single' ? 'selected' : ''}>یک حد سود</option></select></label></div>
        <div style="display:flex;gap:16px;flex-wrap:wrap"><label class="chk"><input type="checkbox" id="trailing" ${d.trailing ? 'checked' : ''}> حد ضرر شناور از اوج</label><label class="chk"><input type="checkbox" id="trend_exit" ${d.trend_exit ? 'checked' : ''}> خروج با برگشت روند</label>
        <label class="chk"><input type="checkbox" id="regime_filter" ${d.regime_filter ? 'checked' : ''}> فیلتر رژیم بازار (≥ ۳ نماد)</label></div></details></div></section>
    <section class="panel" style="margin-bottom:14px"><div class="head"><h2>۴. زمان اجرا</h2><span class="sub">ربات از چه تاریخی تا کی کار کند؛ یا نامحدود</span></div><div class="body form" id="sched">${scheduleFields(d.schedule)}</div></section>
    <section class="panel" style="margin-bottom:14px"><div class="head"><h2>۵. هوش مصنوعی</h2><span class="sub">هر درخواست از سهمیهٔ ماهانهٔ پلن شما کم می‌شود</span></div><div class="body form">
      <label class="chk"><input type="checkbox" id="ai" ${d.ai_filter ? 'checked' : ''}> هر ورود پیش از ارسال سفارش توسط AI تأیید، رتبه‌بندی و اندازه‌گذاری شود</label>
      <label class="lf" style="max-width:260px"><span>حداقل اطمینان مدل</span><input id="aic" type="number" step="0.05" min="0.3" max="0.95" value="${d.ai_min_confidence}"></label></div></section>
    <div class="row" style="display:flex;gap:8px;align-items:center"><button class="primary" id="save">${bot ? 'ذخیرهٔ تغییرات' : 'ساخت ربات'}</button><button id="bt">بک‌تست ۹۰ روزهٔ همین تنظیمات</button><span id="msg" class="muted"></span></div>
    <div id="btres" style="margin-top:14px"></div>`;
  const paint = () => {
    $$('#exch .pcard').forEach(c => c.classList.toggle('on', c.dataset.x === exchange));
    $$('#mode .pcard').forEach(c => c.classList.toggle('on', c.dataset.m === mode));
    $$('#mtype .pcard').forEach(c => c.classList.toggle('on', c.dataset.t === mtype));
    $$('#sides .pcard').forEach(c => c.classList.toggle('on', c.dataset.side === sides));
    $('#marginbox').classList.toggle('hidden', mtype !== 'margin');
    $$('#pre .pcard').forEach(c => c.classList.toggle('on', c.dataset.p === preset));
    $('#syms').innerHTML = symbols.map(s => `<span class="chip">${esc(s)} <a href="javascript:void 0" data-rm="${s}" style="color:var(--faint)">✕</a></span>`).join('') || '<span class="faint" style="font-size:12px">نمادی انتخاب نشده</span>';
    $('#symc').textContent = symbols.length > 1 ? 'پرتفوی ' + n0(symbols.length) + ' نماد' : 'تک‌ارزی';
    $$('#syms [data-rm]').forEach(a => a.onclick = () => { symbols = symbols.filter(x => x !== a.dataset.rm); paint(); });
  };
  $$('#exch .pcard').forEach(c => c.onclick = () => { if (!c.classList.contains('off')) { exchange = c.dataset.x; paint(); } });
  $$('#mode .pcard').forEach(c => c.onclick = () => { mode = c.dataset.m; paint(); });
  $$('#mtype .pcard').forEach(c => c.onclick = () => { mtype = c.dataset.t; paint(); });
  $$('#sides .pcard').forEach(c => c.onclick = () => { sides = c.dataset.side; paint(); });
  $$('#pre .pcard').forEach(c => c.onclick = () => { preset = c.dataset.p; const p = m.presets[preset]; if (p) { ['risk_pct', 'max_positions', 'min_quality'].forEach(k => $('#' + k).value = p[k]); $('#regime_filter').checked = p.regime_filter; } if (preset === 'custom') $('#adv').open = true; paint(); });
  $('#sadd').onclick = () => { const s = $('#sq').value.trim().toUpperCase(); if (m.markets.some(x => x.symbol === s) && !symbols.includes(s) && symbols.length < 25) symbols.push(s); $('#sq').value = ''; paint(); };
  $('#sq').onkeydown = e => { if (e.key === 'Enter') $('#sadd').click(); };
  $$('[data-pre]').forEach(b => b.onclick = async () => {
    const k = b.dataset.pre;
    if (k === 'top10') {
      const t = await api('/api/public/ticker').catch(() => null); const ok = new Set(m.markets.map(x => x.symbol));
      symbols = t ? t.rows.filter(r => r.quote === 'TMN' && ok.has(r.symbol) && r.symbol !== 'USDTTMN' && r.symbol !== 'USDCTMN').sort((a, c) => (c.volume_tmn_24h || 0) - (a.volume_tmn_24h || 0)).slice(0, 10).map(r => r.symbol)
        : ['BTCTMN', 'ETHTMN', 'SOLTMN', 'XRPTMN', 'DOGETMN', 'TRXTMN', 'ADATMN', 'BNBTMN', 'TONTMN', 'LINKTMN'].filter(s => ok.has(s));
    } else symbols = k === 'major' ? ['BTCTMN', 'ETHTMN'] : [];
    paint();
  });
  const readSchedule = bindSchedule($('#sched'));
  const val = k => { const v = $('#' + k).value; return v === '' ? null : +v; };
  const config = () => ({ schedule: readSchedule(), market_type: mtype, leverage: mtype === 'margin' ? val('lev') : 1, sides: mtype === 'margin' ? sides : 'long', symbols, timeframe: $('#tf').value, strategies: $$('#lstrats input:checked').map(x => x.value), capital_tmn: val('cap'), preset,
    risk_pct: val('risk_pct'), max_positions: val('max_positions'), min_quality: val('min_quality'), max_asset_pct: val('max_asset_pct'), max_gross_pct: val('max_gross_pct'),
    min_stop_pct: val('min_stop_pct'), max_stop_pct: val('max_stop_pct'), trend_tp_r: val('trend_tp_r'), max_hold_hours: val('max_hold_hours'), cooldown_bars: val('cooldown_bars'),
    breakeven_buffer_pct: val('breakeven_buffer_pct'), exit_mode: $('#exit_mode').value, trailing: $('#trailing').checked, trend_exit: $('#trend_exit').checked,
    regime_filter: $('#regime_filter').checked, ai_filter: $('#ai').checked, ai_min_confidence: val('aic') });
  $('#save').onclick = async () => {
    const body = { name: $('#bn').value, config: config(), mode };
    const r = bot ? await act(() => post('/api/bots/' + id + '/update', body), 'ذخیره شد') : await act(() => post('/api/bots', { ...body, exchange }), 'ربات ساخته شد');
    if (r) { S.bot = r.id; try { localStorage.setItem('algo.bot', r.id); } catch (_) { /* optional */ } await ctx.refreshBots(); location.hash = '#live'; }
  };
  $('#bt').onclick = async () => {
    const end = Math.floor(Date.now() / 1000); const iso = t => new Date(t * 1000).toISOString();
    const r = await act(() => post('/api/backtests', { config: config(), start: iso(end - 90 * 86400), end: iso(end), title: $('#bn').value + ' (پیش‌نمایش)' }));
    if (r) { $('#btres').innerHTML = `<div class="notice">بک‌تست در صف اجرا قرار گرفت. نتیجهٔ کامل (منحنی، افت، معاملات و مونت‌کارلو) در <a href="#research">«بک‌تست و پژوهش»</a> نمایش داده می‌شود.</div>`; }
  };
  paint();
}

// ------------------------------------------------------------------ keys
export function pageKeys(root) {
  const ex = S.meta.exchanges.filter(e => e.enabled);
  root.innerHTML = `<section class="grid g2"><div class="panel"><div class="head"><h2>افزودن کلید API</h2></div><div class="body form">
    <label class="lf"><span>صرافی</span><select id="kx">${ex.map(e => `<option value="${e.id}">${esc(e.fa)}</option>`).join('')}</select></label>
    <label class="lf"><span>نام دلخواه</span><input id="kl" maxlength="40" placeholder="مثلاً حساب اصلی"></label><label class="lf"><span>کلید API</span><input id="kk" class="ltr" autocomplete="off" style="width:100%"></label>
    <div class="notice" style="font-size:12.5px">${esc(ex[0] ? ex[0].key_help : '')} کلید رمزنگاری‌شده ذخیره می‌شود، فقط موتور اجرا آن را باز می‌کند و پس از ذخیره دیگر نمایش داده نمی‌شود.</div>
    <div class="notice red" style="font-size:12.5px">مهم: از حسابی که ربات واقعی روی آن کار می‌کند <b>دستی معامله نکنید</b> و دارایی‌هایی را که ربات خریده جابه‌جا نکنید. هر ۱۰ دقیقه موجودی صرافی با دفتر ربات تطبیق داده می‌شود و اگر کمتر باشد، ورود جدید متوقف و به شما خبر داده می‌شود. بهتر است برای ربات‌ها یک حساب یا زیرحساب جدا داشته باشید.</div>
    <div><button class="primary" id="ka">ذخیره و بررسی فقط‌خواندنی</button></div></div></div>
    <div class="panel"><div class="head"><h2>کلیدهای من</h2></div><div class="body table-wrap" id="kl2"></div></div></section>`;
  const load = async () => { const ks = await api('/api/keys').catch(() => []);
    $('#kl2').innerHTML = ks.length ? `<table><thead><tr><th>صرافی</th><th>نام</th><th>کلید</th><th>وضعیت</th><th></th></tr></thead><tbody>${ks.map(k => `<tr><td>${k.exchange === 'wallex' ? 'والکس' : esc(k.exchange)}</td><td>${esc(k.label || '—')}</td><td class="mono">…${esc(k.last4)}</td>
      <td>${k.status === 'verified' ? '<span class="chip ok">تأیید شد</span>' : k.status === 'failed' ? '<span class="chip bad">نامعتبر</span>' : '<span class="chip y">بررسی نشد</span>'}</td><td style="white-space:nowrap"><button data-v="${k.id}">بررسی</button> <button class="danger" data-d="${k.id}">حذف</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty">کلیدی ثبت نشده است.</div>';
    $$('[data-v]').forEach(b => b.onclick = async () => { const r = await act(() => post(`/api/keys/${b.dataset.v}/verify`)); if (r) toast(r.status === 'verified' ? 'کلید معتبر است' : (r.check.error || 'نامعتبر'), r.status !== 'verified'); load(); });
    $$('[data-d]').forEach(b => b.onclick = async () => { if (confirm('کلید حذف شود؟')) { await act(() => post(`/api/keys/${b.dataset.d}/delete`), 'حذف شد'); load(); } });
  };
  $('#ka').onclick = async () => { const r = await act(() => post('/api/keys', { exchange: $('#kx').value, label: $('#kl').value || null, api_key: $('#kk').value }));
    if (r) { $('#kk').value = ''; toast(r.status === 'verified' ? 'کلید ذخیره و تأیید شد' : 'کلید ذخیره شد ولی بررسی نشد: ' + ((r.check && r.check.error) || ''), r.status !== 'verified'); load(); } };
  load();
}

// ------------------------------------------------------------------ billing and profile
export async function pageBilling(root, ctx, q) {
  await refreshMe().catch(() => null);
  const u = S.user;
  root.innerHTML = `${q.status === 'paid' ? '<div class="notice green" style="margin-bottom:14px">پرداخت موفق بود و پلن فعال شد.</div>' : q.status ? '<div class="notice red" style="margin-bottom:14px">پرداخت انجام نشد یا لغو شد.</div>' : ''}
    <section class="grid g3" style="margin-bottom:14px"><div class="panel kpi"><div class="label">پلن فعلی</div><div class="value">${esc(u.plan ? u.plan.name : '—')}</div><div class="note">${u.plan_active ? (u.plan_expires ? 'تا ' + when(u.plan_expires) : '') : '<span class="neg">منقضی</span>'}</div></div>
      <div class="panel kpi"><div class="label">سهمیهٔ AI این ماه</div><div class="value">${n0(u.ai_quota.used)} / ${n0(u.ai_quota.limit)}</div><div class="note">فیلتر ربات‌ها و استودیو</div></div>
      <div class="panel kpi"><div class="label">ربات واقعی</div><div class="value">${n0(u.plan ? u.plan.max_live_bots : 0)}</div><div class="note">سقف سرمایه ${toman(u.plan ? u.plan.max_capital_tmn : 0)}</div></div></section>
    <section class="grid g3" style="margin-bottom:14px">${S.meta.plans.map(p => `<div class="panel plan ${u.plan && u.plan.id === p.id ? 'glow' : ''}"><div class="body"><b style="font-size:16px">${esc(p.name)}</b><div class="big" style="font-size:24px;margin:6px 0">${+p.price_tmn ? toman(p.price_tmn) : 'رایگان'}</div><div class="faint">${+p.price_tmn ? n0(p.days) + ' روز' : ''}</div>
      <div class="muted" style="font-size:13px;margin:6px 0">${esc(p.description || '')}</div><div style="font-size:12.5px">${n0(p.max_bots)} ربات · ${+p.max_live_bots ? n0(p.max_live_bots) + ' واقعی تا ' + toman(p.max_capital_tmn) : 'فقط آزمایشی'} · AI ${n0(p.ai_calls_month)} در ماه</div>
      ${+p.price_tmn ? `<button class="primary" style="margin-top:10px" data-p="${p.id}">${u.plan && u.plan.id === p.id ? 'تمدید' : 'خرید'}</button>` : ''}</div></div>`).join('')}</section>
    <section class="panel"><div class="head"><h2>پرداخت‌ها</h2></div><div class="body table-wrap" id="pays"></div></section>`;
  $$('button[data-p]', root).forEach(b => b.onclick = async () => { const r = await act(() => post('/api/pay', { plan_id: b.dataset.p })); if (r) location.href = r.url; });
  const ps = await api('/api/payments').catch(() => []);
  $('#pays').innerHTML = ps.length ? `<table><thead><tr><th>زمان</th><th>پلن</th><th>مبلغ</th><th>وضعیت</th><th>کد پیگیری</th></tr></thead><tbody>${ps.map(p => `<tr><td>${when(p.created)}</td><td>${esc(p.plan_id)}</td><td>${toman(p.amount_rial / 10)}</td><td>${{ paid: '<span class="pos">موفق</span>', pending: 'در انتظار', cancelled: 'لغو', failed: '<span class="neg">ناموفق</span>' }[p.status] || esc(p.status)}${p.sandbox ? ' <span class="chip y">آزمایشی</span>' : ''}</td><td class="mono">${esc(p.ref_id || '—')}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">پرداختی ثبت نشده.</div>';
}

export function pageProfile(root, ctx, onLogout) {
  const u = S.user;
  root.innerHTML = `<section class="grid g2" style="align-items:start"><div class="panel"><div class="head"><h2>حساب</h2></div><div class="body form"><label class="lf"><span>نام</span><input id="nm" value="${esc(u.name || '')}" maxlength="60"></label>
    <div class="muted">موبایل: <span class="mono">${esc(u.phone)}</span></div>
    <div class="row"><button class="primary" id="sv">ذخیره</button><button class="danger" id="out">خروج از حساب</button></div>${S.meta.support ? `<div class="faint">${esc(S.meta.support)}</div>` : ''}</div></div>
    <div class="panel"><div class="head"><h2>اعلان‌ها در بله</h2><span class="sub">ورود و خروج معاملات، هشدارها و وضعیت ربات‌ها</span></div><div class="body form" id="bale"><div class="skeleton" style="height:90px"></div></div></div></section>`;
  $('#sv').onclick = () => act(() => post('/api/me/profile', { name: $('#nm').value }), 'ذخیره شد').then(refreshMe);
  $('#out').onclick = async () => { await post('/api/auth/logout').catch(() => null); onLogout(); };
  baleBox($('#bale'));
}

async function baleBox(box) {
  const b = await api('/api/me/bale').catch(e => ({ error: e.message })); if (!box.isConnected) return;
  if (b.error) { box.innerHTML = `<div class="notice red">${esc(b.error)}</div>`; return; }
  const bot = b.bot_username ? `<a href="https://ble.ir/${encodeURIComponent(b.bot_username)}" target="_blank" rel="noopener noreferrer" class="mono">@${esc(b.bot_username)}</a>` : 'ربات بله';
  if (!b.available) { box.innerHTML = '<div class="muted">اعلان‌های بله هنوز توسط مدیریت فعال نشده است.</div>'; return; }
  if (b.linked) {
    box.innerHTML = `<div class="notice green" style="font-size:12.5px">✓ حساب شما به ${bot} وصل است${b.linked_at ? ' (از ' + when(b.linked_at) + ')' : ''}. هشدارهای مهم (مسدود شدن ربات، ناهمخوانی موجودی، لیکویید شدن) همیشه ارسال می‌شوند.</div>
      <label class="chk"><input type="checkbox" id="bmute" ${b.muted ? '' : 'checked'}> پیام ورود و خروج هر معامله</label>
      <div class="row"><button id="btest">ارسال پیام آزمایشی</button><button class="danger" id="bunlink">قطع اتصال</button></div>
      <div class="faint" style="font-size:11.5px">در خود بله هم: /status وضعیت ربات‌ها · /mute و /unmute · /unlink</div>`;
    $('#bmute', box).onchange = async () => { await act(() => post('/api/me/bale/prefs', { muted: !$('#bmute', box).checked }), 'ذخیره شد'); };
    $('#btest', box).onclick = () => act(() => post('/api/me/bale/test'), 'پیام آزمایشی در صف ارسال است');
    $('#bunlink', box).onclick = async () => { if (confirm('اتصال بله قطع شود؟')) { await act(() => post('/api/me/bale/unlink')); baleBox(box); } };
    return;
  }
  box.innerHTML = `<div class="muted" style="font-size:13px">۱. «دریافت کد اتصال» را بزنید. ۲. در پیام‌رسان بله ${bot} را باز کنید و «شروع» را بزنید. ۳. کد ۶ رقمی را برای ربات بفرستید.</div>
    <div class="row"><button class="primary" id="bcode">دریافت کد اتصال</button><button id="bcheck">بررسی اتصال</button></div><div id="bcodebox"></div>`;
  $('#bcode', box).onclick = async () => {
    const r = await act(() => post('/api/me/bale/code')); if (!r) return;
    $('#bcodebox', box).innerHTML = `<div class="notice" style="text-align:center"><div class="muted" style="font-size:12px">این کد را تا ۱۵ دقیقه برای ${bot} بفرستید</div><div class="code mono" style="font-size:30px;letter-spacing:10px">${esc(r.code)}</div>
      ${r.bot_username ? `<a href="https://ble.ir/${encodeURIComponent(r.bot_username)}" target="_blank" rel="noopener noreferrer"><button class="primary">باز کردن ربات در بله ↗</button></a>` : ''}</div>`;
  };
  $('#bcheck', box).onclick = () => baleBox(box);
}

export { download };
