// Shared helpers: API, session, Persian formatting and small DOM utilities.
export const S = { csrf: '', authenticated: false, publicReadonly: true, development: false };

export async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: { Accept: 'application/json' }, credentials: 'same-origin' };
  if (opts.body !== undefined) {
    init.method = opts.method || 'POST';
    init.headers['Content-Type'] = 'application/json';
    init.headers['X-CSRF-Token'] = S.csrf;
    init.body = JSON.stringify(opts.body);
  }
  if (opts.headers) Object.assign(init.headers, opts.headers);
  const r = await fetch(path, init);
  let data = null;
  try { data = await r.json(); } catch (_) { data = null; }
  if (!r.ok) {
    const msg = data && (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
    const err = new Error(msg || ('HTTP ' + r.status)); err.status = r.status; throw err;
  }
  return data;
}

export async function loadSession() {
  try { Object.assign(S, await api('/api/session'), {}); S.authenticated = !!S.authenticated; } catch (_) { /* public */ }
  return S;
}

const nf = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 });
const nf4 = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 4 });
export const n0 = v => v === null || v === undefined || isNaN(+v) ? '—' : nf.format(+v);
export const n2 = v => v === null || v === undefined || isNaN(+v) ? '—' : nf2.format(+v);
export const n4 = v => v === null || v === undefined || isNaN(+v) ? '—' : nf4.format(+v);
export const toman = v => v === null || v === undefined || isNaN(+v) ? '—' : nf.format(Math.round(+v)) + ' تومان';
export const pct = (v, d = 2) => v === null || v === undefined || isNaN(+v) ? '—' : (+v > 0 ? '+' : '') + new Intl.NumberFormat('fa-IR', { maximumFractionDigits: d, minimumFractionDigits: d }).format(+v) + '٪';
export const signCls = v => +v > 0 ? 'pos' : +v < 0 ? 'neg' : '';
export function price(v) {
  if (v === null || v === undefined || isNaN(+v)) return '—';
  const x = +v; const d = x >= 1000 ? 0 : x >= 1 ? 3 : 6;
  return new Intl.NumberFormat('fa-IR', { maximumFractionDigits: d }).format(x);
}
const dtf = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { timeZone: 'Asia/Tehran', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
const tf = new Intl.DateTimeFormat('fa-IR', { timeZone: 'Asia/Tehran', hour: '2-digit', minute: '2-digit', second: '2-digit' });
const hf = new Intl.DateTimeFormat('fa-IR', { timeZone: 'Asia/Tehran', hour: '2-digit', minute: '2-digit' });
export const when = s => s ? dtf.format(new Date(s * 1000)) : '—';
export const clock = s => s ? tf.format(new Date(s * 1000)) : '—';
export const hm = s => s ? hf.format(new Date(s * 1000)) : '—';
export function ago(s) {
  if (!s) return '—';
  const d = Math.max(0, Date.now() / 1000 - s);
  if (d < 60) return n0(d) + ' ثانیه پیش';
  if (d < 3600) return n0(d / 60) + ' دقیقه پیش';
  if (d < 86400) return n0(d / 3600) + ' ساعت پیش';
  return n0(d / 86400) + ' روز پیش';
}
export function esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
export function h(html) { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; }
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const sym = s => `<span class="mono">${esc(s)}</span>`;

export const STATUS_FA = {
  running: 'در حال اجرا', observing: 'رصد بازار', ai_decision: 'تصمیم AI', reconciling: 'تطبیق حساب', reconciled: 'تطبیق شد',
  checking_market_contracts: 'بررسی بازارها', stopped: 'متوقف', blocked: 'مسدود', halted: 'توقف ریسک', idle: 'بیکار',
  network_pause: 'مکث شبکه', operator_stopped: 'توقف اپراتور', waiting_start: 'منتظر شروع', window_ended: 'پایان مسابقه',
  upgrade_reviewed_stopped: 'ارتقا تأیید شد؛ منتظر ادامه', native_cancel_reviewed_stopped: 'تطبیق شد؛ متوقف',
  activation_pending: 'در انتظار شروع', not_configured: 'پیکربندی نشده', stopping: 'در حال توقف', reduce_only: 'فقط کاهش'
};
export const REASON_FA = {
  trailing_stop: 'حد ضرر شناور', target_reached: 'رسیدن به هدف', tp1: 'TP1 (فروش یک‌سوم، نسخهٔ ۴٫۳)', tp2: 'TP2 (فروش یک‌سوم، نسخهٔ ۴٫۳)', tp3: 'TP3 (خروج کامل)', stepped_stop: 'حد ضرر پله‌ای', breakeven_stop: 'سربه‌سر', fast_trend_break: 'شکست روند ۱۵ دقیقه‌ای', time_exit: 'پایان زمان نگهداری', trend_reversed: 'برگشت روند',
  portfolio_halt: 'توقف ریسک پرتفوی', reversion_complete: 'بازگشت کامل', funded_usdt_leg: 'پای دوم تتر', fund_usdt_route: 'تأمین تتر',
  confirmed_funding: 'خرید پس از تأمین', residual_fx_to_tmn: 'تبدیل ماندهٔ تتر', sale_proceeds_to_tmn: 'تبدیل فروش به تومان',
  native_stop_protection: 'محافظ حد ضرر صرافی', signal: 'سیگنال', spread_gate: 'اسپرد زیاد', regime_position_capacity_full: 'ظرفیت رژیم پر است',
  no_strategy_setup: 'هیچ ستاپ معتبری نبود', not_requested: 'درخواست نشد', allocation_already_reserved: 'ظرفیت پر بود',
  interrupted_attempt_not_repeated: 'تلاش قطع‌شده تکرار نشد', persistent_call_budget: 'سقف بودجهٔ AI'
};
export const PHASE_FA = { FILLED: 'پر شد', CLOSED: 'بسته/لغو', OPEN: 'باز', PARTIAL: 'نیمه‌پر', SUBMITTING: 'در حال ارسال', UNKNOWN: 'نامعلوم', LOCAL_REJECTED: 'رد محلی' };
export const SIDE_FA = { BUY: 'خرید', SELL: 'فروش' };

export function download(name, text, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
}

export function tween(node, to, fmt, ms = 900) {
  const from = +(node.dataset.v ?? to);
  node.dataset.v = to;
  if (!isFinite(from) || !isFinite(to) || from === to || matchMedia('(prefers-reduced-motion: reduce)').matches) { node.textContent = fmt(to); return; }
  const t0 = performance.now();
  const step = t => { const k = Math.min(1, (t - t0) / ms); const e = 1 - Math.pow(1 - k, 3); node.textContent = fmt(from + (to - from) * e); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
