// Back office: overview and kill switches, bot approvals, users, plans, payments, settings, audit (Nova look).
import { S, api, n0, n2, toman, pct, when, esc, $, $$, botChip } from './core.js';
import { act, modal, toast } from './account.js';

const post = (path, body = {}) => api(path, { body });
const kpi = (l, v, n = '', c = '') => `<div class="panel kpi"><div class="label">${l}</div><div class="value ${c}">${v}</div><div class="note">${n}</div></div>`;

export function ADMIN_PAGES(ctx, q) {
  return {
    admin: root => overview(root, ctx), 'admin-bots': root => bots(root, ctx, q), 'admin-users': root => users(root, ctx, q),
    'admin-plans': root => plans(root, ctx), 'admin-payments': root => payments(root), 'admin-settings': root => settings(root), 'admin-audit': root => audit(root)
  };
}

function overview(root, ctx) {
  root.innerHTML = '<div class="skeleton" style="height:200px"></div>';
  ctx.every(15000, async () => {
    const d = await act(() => api('/api/admin/dashboard')); if (!d) return;
    root.innerHTML = `<section class="grid g4" style="margin-bottom:14px">${kpi('کاربران', n0(d.users), n0(d.new_users_7d) + ' کاربر جدید در ۷ روز')}${kpi('ربات‌ها', n0(d.bots), n0(d.running_paper) + ' آزمایشی فعال')}
      ${kpi('ربات واقعی فعال', n0(d.running_live), 'سرمایه ' + toman(d.live_capital_tmn))}${kpi('در انتظار تأیید', n0(d.pending_approval), d.blocked ? n0(d.blocked) + ' ربات مسدود' : '', d.pending_approval ? 'warn' : '')}
      ${kpi('درآمد ۳۰ روز', toman(d.revenue_tmn_30d), 'فقط پرداخت‌های واقعی')}${kpi('درخواست AI این ماه', n0(d.ai_calls_month), d.ai_configured ? 'کلید پلتفرم تنظیم شده' : '<span class="neg">کلید AI تنظیم نشده</span>')}
      ${kpi('پیامک', d.sms_configured ? 'تنظیم شده' : 'تنظیم نشده', '', d.sms_configured ? 'pos' : 'neg')}${kpi('اعلان بله', d.bale_configured ? 'فعال' : 'غیرفعال', n0(d.bale_linked) + ' کاربر وصل' + (d.notifications_failed ? ' · <span class="neg">' + n0(d.notifications_failed) + ' پیام ناموفق</span>' : ''), d.bale_configured ? 'pos' : 'warn')}${kpi('درگاه', d.payment_sandbox ? 'آزمایشی (sandbox)' : 'واقعی', '', d.payment_sandbox ? 'warn' : 'pos')}</section>
      <section class="panel glow"><div class="head"><h2>کلیدهای توقف سراسری</h2><span class="sub">اثر فوری روی همهٔ ربات‌ها در چرخهٔ بعد</span></div><div class="body form">
        <label class="chk"><input type="checkbox" id="lt" ${d.switches.live_trading_enabled ? 'checked' : ''}> معامله با پول واقعی (خاموش = هیچ سفارش واقعی‌ای ارسال نمی‌شود)</label>
        <label class="chk"><input type="checkbox" id="ne" ${d.switches.new_entries_enabled ? 'checked' : ''}> ورودهای جدید همهٔ ربات‌ها (خاموش = فقط مدیریت خروج)</label>
        <div><button class="primary" id="sw">ذخیره</button></div></div></section>`;
    $('#sw').onclick = () => act(() => post('/api/admin/settings', { values: { 'platform.live_trading_enabled': $('#lt').checked, 'platform.new_entries_enabled': $('#ne').checked } }), 'ذخیره شد');
  });
}

async function bots(root, ctx, q) {
  const tabs = [['pending_approval', 'در انتظار تأیید'], ['running', 'در حال اجرا'], ['blocked', 'مسدود'], ['', 'همه']];
  const cur = q.s ?? 'pending_approval';
  root.innerHTML = `<div class="tools tabs-inline" style="margin-bottom:14px">${tabs.map(([k, t]) => `<a href="#admin-bots?s=${k}"><button class="${cur === k ? 'on' : ''}">${t}</button></a>`).join('')}</div><section class="panel"><div class="body table-wrap" id="ab"><div class="skeleton" style="height:80px"></div></div></section>`;
  const rows = await act(() => api('/api/admin/bots?status=' + cur)); if (!rows) return;
  $('#ab').innerHTML = rows.length ? `<table><thead><tr><th>ربات</th><th>کاربر</th><th>حالت</th><th>وضعیت</th><th>سرمایه</th><th>ارزش</th><th>نمادها</th><th></th></tr></thead><tbody>${rows.map(b => `<tr><td>${esc(b.name)}</td><td class="mono">${esc(b.phone)}</td><td>${b.mode === 'live' ? 'واقعی' : 'آزمایشی'}${b.live_approved ? ' ✓' : ''}</td><td>${botChip(b.status)}</td><td>${toman(b.config.capital_tmn)}</td><td>${toman(b.equity_tmn)}</td><td style="font-size:12px">${esc(b.config.symbols.join('، '))}</td><td style="white-space:nowrap"><button data-b="${b.id}">بررسی</button> <button data-view="${b.id}" title="داشبورد کامل این ربات (فقط خواندنی)">داشبورد</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty">موردی نیست.</div>';
  $$('[data-b]').forEach(x => x.onclick = () => botModal(x.dataset.b, ctx));
  $$('[data-view]').forEach(x => x.onclick = () => viewBot(x.dataset.view));
}
function viewBot(id) { S.viewing = id; S.bot = id; location.hash = '#live'; }
async function botModal(id, ctx) {
  const b = await act(() => api('/api/admin/bots/' + id)); if (!b) return;
  const c = b.config;
  const m = modal(`<div class="head"><h2>${esc(b.name)} ${botChip(b.status)}</h2></div><div class="body">
    <div class="muted" style="font-size:12.5px">کاربر: <span class="mono">${esc(b.user.phone)}</span> · پلن ${esc(b.user.plan_id || '—')} · ${b.mode === 'live' ? 'واقعی' : 'آزمایشی'} · کلید ${esc(b.key_id || '—')}</div>
    <table style="margin:10px 0"><tr><td class="muted">سرمایه</td><td>${toman(c.capital_tmn)}</td></tr><tr><td class="muted">نمادها</td><td>${esc(c.symbols.join('، '))}</td></tr>
      <tr><td class="muted">تایم‌فریم / استراتژی‌ها</td><td>${esc(c.timeframe)} · ${n0(c.strategies.length)} استراتژی${(c.custom_strategies || []).length ? ' (' + n0(c.custom_strategies.length) + ' از استودیو)' : ''}</td></tr>
      <tr><td class="muted">ریسک</td><td>${pct(c.risk_pct).replace('+', '')} هر معامله · حداکثر ${n0(c.max_positions)} موقعیت · سقف دارایی ${n0(c.max_asset_pct)}٪</td></tr><tr><td class="muted">AI</td><td>${c.ai_filter ? 'فعال، اطمینان ≥ ' + n2(c.ai_min_confidence) : 'خاموش'}</td></tr>
      <tr><td class="muted">ارزش / معاملات</td><td>${toman(b.equity_tmn)} · ${n0(b.trades.length)} معامله</td></tr>${b.last_error ? `<tr><td class="muted">خطا</td><td class="neg">${esc(b.last_error)}</td></tr>` : ''}</table>
    <label class="lf"><span>یادداشت برای کاربر</span><input id="note" maxlength="300" value="${esc(b.review_note || '')}"></label>
    <div class="row" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px">${b.mode === 'live' && !b.live_approved ? '<button class="primary" data-x="approve">تأیید اجرای واقعی</button>' : ''}${b.mode === 'live' ? '<button class="danger" data-x="reject">رد / لغو تأیید</button>' : ''}
      ${b.status === 'running' ? '<button data-x="pause">توقف ورود</button>' : ''}${['running', 'paused'].includes(b.status) ? '<button data-x="stop">توقف</button>' : ''}${b.status === 'blocked' ? '<button data-x="resolve" title="پس از بررسی دستی در صرافی">رفع انسداد</button>' : ''}
      <button data-x="view">داشبورد کامل</button><button data-x="close">بستن</button></div></div>`);
  $$('[data-x]', m).forEach(x => x.onclick = async () => {
    const a = x.dataset.x; if (a === 'close') { m.remove(); return; }
    if (a === 'view') { m.remove(); viewBot(id); return; }
    if (a === 'resolve' && !confirm('سفارش‌های نامعلوم را در صرافی بررسی کرده‌اید و ثبت نشده‌اند؟')) return;
    if (await act(() => post(`/api/admin/bots/${id}/${a}`, { note: $('#note', m).value || null }), 'انجام شد')) { m.remove(); ctx.route(); }
  });
}

async function users(root, ctx, q) {
  root.innerHTML = `<div class="row" style="display:flex;gap:8px;margin-bottom:14px"><input id="uq" placeholder="جست‌وجوی شماره یا نام" value="${esc(q.q || '')}" style="width:300px"><button id="us">جست‌وجو</button></div><section class="panel"><div class="body table-wrap" id="ul"><div class="skeleton" style="height:80px"></div></div></section>`;
  $('#us').onclick = () => { location.hash = '#admin-users?q=' + encodeURIComponent($('#uq').value); };
  $('#uq').onkeydown = e => { if (e.key === 'Enter') $('#us').click(); };
  const [rows, plans] = await Promise.all([api('/api/admin/users?q=' + encodeURIComponent(q.q || '')), api('/api/admin/plans')]);
  $('#ul').innerHTML = `<table><thead><tr><th>موبایل</th><th>نام</th><th>نقش</th><th>وضعیت</th><th>پلن</th><th>ربات</th><th>AI</th><th>عضویت</th><th></th></tr></thead><tbody>${rows.map(u => `<tr><td class="mono">${esc(u.phone)}</td><td>${esc(u.name || '—')}</td><td>${u.role === 'admin' ? '<span class="chip y">ادمین</span>' : 'کاربر'}</td><td>${u.status === 'active' ? '<span class="pos">فعال</span>' : '<span class="neg">مسدود</span>'}</td><td>${esc(u.plan_id || '—')} <span class="faint" style="font-size:11.5px">${u.plan_expires ? when(u.plan_expires) : ''}</span></td><td>${n0(u.bots)}</td><td>${n0(u.ai_quota.used)}/${n0(u.ai_quota.limit)}</td><td style="font-size:12px">${when(u.created)}</td><td><button data-u="${u.id}">ویرایش</button></td></tr>`).join('')}</tbody></table>`;
  $$('[data-u]').forEach(b => b.onclick = () => {
    const u = rows.find(x => x.id === b.dataset.u);
    const m = modal(`<div class="head"><h2 class="mono">${esc(u.phone)}</h2></div><div class="body form"><label class="lf"><span>نام</span><input id="mn" value="${esc(u.name || '')}"></label>
      <div class="lgrid" style="grid-template-columns:1fr 1fr"><label class="lf"><span>نقش</span><select id="mr"><option value="user" ${u.role === 'user' ? 'selected' : ''}>کاربر</option><option value="admin" ${u.role === 'admin' ? 'selected' : ''}>ادمین</option></select></label>
      <label class="lf"><span>وضعیت</span><select id="ms"><option value="active" ${u.status === 'active' ? 'selected' : ''}>فعال</option><option value="blocked" ${u.status === 'blocked' ? 'selected' : ''}>مسدود</option></select></label>
      <label class="lf"><span>پلن</span><select id="mp"><option value="">بدون تغییر</option>${plans.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></label><label class="lf"><span>مدت (روز)</span><input id="md" type="number" placeholder="پیش‌فرض پلن"></label></div>
      <label class="lf"><span>سهمیهٔ AI اختصاصی در ماه (خالی = طبق پلن)</span><input id="ma" type="number" value="${u.ai_quota_override ?? ''}"></label><div class="row"><button class="primary" id="msv">ذخیره</button><button id="mc">انصراف</button></div></div>`);
    $('#mc', m).onclick = () => m.remove();
    $('#msv', m).onclick = async () => { const body = { name: $('#mn', m).value, role: $('#mr', m).value, status: $('#ms', m).value };
      if ($('#mp', m).value) { body.plan_id = $('#mp', m).value; if ($('#md', m).value) body.plan_days = +$('#md', m).value; }
      if ($('#ma', m).value === '') body.clear_ai_override = true; else body.ai_quota_override = +$('#ma', m).value;
      if (await act(() => post('/api/admin/users/' + u.id, body), 'ذخیره شد')) { m.remove(); ctx.route(); } };
  });
}

async function plans(root, ctx) {
  root.innerHTML = `<div style="margin-bottom:14px"><button class="primary" id="np">＋ پلن جدید</button></div><section class="panel"><div class="body table-wrap" id="pl"></div></section>`;
  const list = await api('/api/admin/plans');
  $('#pl').innerHTML = `<table><thead><tr><th>شناسه</th><th>نام</th><th>قیمت</th><th>مدت</th><th>ربات</th><th>واقعی</th><th>سقف سرمایه</th><th>AI/ماه</th><th>فعال</th><th></th></tr></thead><tbody>${list.map(p => `<tr><td class="mono">${esc(p.id)}</td><td>${esc(p.name)}</td><td>${toman(p.price_tmn)}</td><td>${n0(p.days)} روز</td><td>${n0(p.max_bots)}</td><td>${n0(p.max_live_bots)}</td><td>${toman(p.max_capital_tmn)}</td><td>${n0(p.ai_calls_month)}</td><td>${p.active ? '✓' : '—'}</td><td><button data-p="${p.id}">ویرایش</button></td></tr>`).join('')}</tbody></table>`;
  const edit = p => {
    p = p || { id: '', name: '', price_tmn: 0, days: 30, max_bots: 3, max_live_bots: 1, max_capital_tmn: 50000000, ai_calls_month: 300, active: 1, sort: list.length, description: '' };
    const f = (k, l, t = 'number') => `<label class="lf"><span>${l}</span><input id="p_${k}" type="${t}" value="${esc(p[k])}"></label>`;
    const m = modal(`<div class="head"><h2>${p.id ? 'ویرایش پلن' : 'پلن جدید'}</h2></div><div class="body form"><div class="lgrid" style="grid-template-columns:1fr 1fr">${f('id', 'شناسه (لاتین)', 'text')}${f('name', 'نام', 'text')}${f('price_tmn', 'قیمت (تومان)')}${f('days', 'مدت (روز)')}${f('max_bots', 'حداکثر ربات')}${f('max_live_bots', 'حداکثر ربات واقعی')}${f('max_capital_tmn', 'سقف سرمایهٔ هر ربات واقعی')}${f('ai_calls_month', 'درخواست AI در ماه')}${f('sort', 'ترتیب')}</div>
      ${f('description', 'توضیح', 'text')}<label class="chk"><input type="checkbox" id="p_active" ${p.active ? 'checked' : ''}> فعال</label><div class="row"><button class="primary" id="ps">ذخیره</button><button id="pc">انصراف</button></div></div>`);
    $('#pc', m).onclick = () => m.remove();
    $('#ps', m).onclick = async () => { const v = k => $('#p_' + k, m).value; const body = { id: v('id') || null, name: v('name'), description: v('description'), active: $('#p_active', m).checked };
      ['price_tmn', 'days', 'max_bots', 'max_live_bots', 'max_capital_tmn', 'ai_calls_month', 'sort'].forEach(k => body[k] = +v(k));
      if (await act(() => post('/api/admin/plans', body), 'ذخیره شد')) { m.remove(); ctx.route(); } };
  };
  $('#np').onclick = () => edit(null);
  $$('#pl button[data-p]').forEach(b => b.onclick = () => edit(list.find(p => p.id === b.dataset.p)));
}

async function settings(root) {
  root.innerHTML = '<div id="sets"><div class="skeleton" style="height:200px"></div></div>';
  const d = await act(() => api('/api/admin/settings')); if (!d) return;
  const groups = {};
  d.settings.forEach(s => (groups[s.key.split('.')[0]] = groups[s.key.split('.')[0]] || []).push(s));
  const src = s => s.source === 'env' ? ` <span class="chip y" title="${esc(s.env)}">از متغیر محیطی</span>` : '';
  const input = s => {
    if (s.kind === 'bool') return `<label class="chk"><input type="checkbox" data-k="${s.key}" ${s.value ? 'checked' : ''}> ${esc(s.label)}${src(s)}</label>`;
    if (s.secret) return `<label class="lf"><span>${esc(s.label)} ${s.value.set ? `<span class="chip ok">تنظیم شده …${esc(s.value.last4)}</span>` : '<span class="chip bad">تنظیم نشده</span>'}${src(s)}</span><input data-k="${s.key}" class="ltr" placeholder="برای تغییر وارد کنید" autocomplete="off"></label>`;
    if (s.kind.startsWith('choice:')) return `<label class="lf"><span>${esc(s.label)}${src(s)}</span><select data-k="${s.key}">${s.kind.slice(7).split(',').map(o => `<option ${o === s.value ? 'selected' : ''}>${o}</option>`).join('')}</select></label>`;
    if (s.key === 'llm.provider') return `<label class="lf"><span>${esc(s.label)}${src(s)}</span><select data-k="${s.key}">${Object.entries(d.llm_providers).map(([k, p]) => `<option value="${k}" ${k === s.value ? 'selected' : ''}>${esc(p.fa)}</option>`).join('')}</select></label>`;
    const ltr = /url|key|sender|pattern|merchant|model|variable|plan_id/.test(s.key) ? 'ltr' : '';
    return `<label class="lf"><span>${esc(s.label)}${src(s)}</span><input data-k="${s.key}" class="${ltr}" ${s.kind === 'int' ? 'type="number"' : ''} value="${esc(s.value)}"></label>`;
  };
  $('#sets').innerHTML = Object.entries(groups).map(([g, list]) => `<section class="panel" style="margin-bottom:14px"><div class="head"><h2>${esc(d.groups[g] || g)}</h2>${g === 'sms' ? '<div class="tools"><input id="tp" class="ltr" placeholder="09..." style="width:150px"> <button id="tsend">ارسال پیامک آزمایشی</button></div>' : ''}</div><div class="body lgrid" style="grid-template-columns:repeat(2,minmax(0,1fr))">${list.map(input).join('')}</div></section>`).join('')
    + '<div class="row" style="display:flex;gap:8px;align-items:center"><button class="primary" id="save">ذخیرهٔ همهٔ تنظیمات</button><span class="faint">فیلدهای کلید خالی یعنی «بدون تغییر».</span></div>';
  $('#save').onclick = async () => {
    const values = {};
    $$('[data-k]').forEach(i => { const s = d.settings.find(x => x.key === i.dataset.k); values[i.dataset.k] = s.kind === 'bool' ? i.checked : s.kind === 'int' ? +i.value : i.value; });
    if (await act(() => post('/api/admin/settings', { values }), 'تنظیمات ذخیره شد')) { S.meta = await api('/api/meta'); settings(root); }
  };
  if ($('#tsend')) $('#tsend').onclick = () => act(() => post('/api/admin/sms-test', { phone: $('#tp').value }), 'پیامک آزمایشی (کد 123456) ارسال شد');
}

async function payments(root) {
  root.innerHTML = '<section class="panel"><div class="body table-wrap" id="ap"><div class="skeleton" style="height:80px"></div></div></section>';
  const rows = await act(() => api('/api/admin/payments')); if (!rows) return;
  $('#ap').innerHTML = rows.length ? `<table><thead><tr><th>زمان</th><th>کاربر</th><th>پلن</th><th>مبلغ</th><th>وضعیت</th><th>کد پیگیری</th><th>کارت</th></tr></thead><tbody>${rows.map(p => `<tr><td>${when(p.created)}</td><td class="mono">${esc(p.phone)}</td><td>${esc(p.plan_id)}</td><td>${toman(p.amount_rial / 10)}</td><td>${esc(p.status)}${p.sandbox ? ' <span class="chip y">آزمایشی</span>' : ''}</td><td class="mono">${esc(p.ref_id || '—')}</td><td class="mono">${esc(p.card_pan || '—')}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">پرداختی نیست.</div>';
}

async function audit(root) {
  root.innerHTML = '<section class="panel"><div class="body feed scroll" id="au" style="max-height:none"><div class="skeleton" style="height:80px"></div></div></section>';
  const rows = await act(() => api('/api/admin/audit')); if (!rows) return;
  $('#au').innerHTML = rows.map(r => `<div class="item"><span class="t">${when(r.at)}</span><span><b>${esc(r.action)}</b> <span class="faint mono">${esc(r.actor || '—')}</span><span class="faint mono" style="font-size:11px;word-break:break-all;display:block;text-align:left">${esc(JSON.stringify(r.detail)).slice(0, 400)}</span></span></div>`).join('') || '<div class="empty">—</div>';
}

export { toast };
