// Strategy Studio: chat with the LLM agent, see the draft, backtest, tune, save and approve.
import { S, api, esc, $, $$, n0, n2, pct, when, toman } from './core.js';

const ROLE = { user: 'شما', assistant: 'عامل Nova', tool: 'ابزار', event: 'نتیجه', error: 'خطا' };
const TOOL_FA = { propose: 'پیش‌نویس', backtest: 'بک‌تست', tune: 'بهینه‌سازی ضرایب', save: 'ذخیره', none: 'گفت‌وگو' };
const STATUS = { draft: ['پیش‌نویس', ''], tested: ['آزموده', 'y'], approved: ['تأییدشده؛ منتظر ارتقا', 'ok'], live: ['فعال در موتور', 'ok'], retired: ['بازنشسته', 'bad'] };
const REGIME_FA = { bull: 'صعودی', range: 'رنج', bear: 'نزولی', crash: 'ریزش' };
const IDEAS = ['یک استراتژی شکار نقدینگی برای بازار رنج بساز و بک‌تست بگیر',
  'استراتژی پولبک به EMA21 در روند صعودی با تأیید حجم طراحی کن',
  'حد ضرر و ضریب TP را بهینه کن و نسخهٔ پایدارتر را پیشنهاد بده',
  'نتیجهٔ بک‌تست را تحلیل کن؛ چرا خروج‌ها با حد ضرر بوده؟'];

export function pageStudio(root, ctx) {
  if (!S.authenticated) { root.innerHTML = `<section class="panel" style="max-width:520px"><div class="body"><div class="notice">استودیوی استراتژی فقط برای اپراتور است.</div><p><a href="#operator">ورود اپراتور ←</a></p></div></section>`; return; }
  root.innerHTML = `<section class="panel" style="margin-bottom:14px"><div class="body studio-top">
      <div><b>استودیوی استراتژی عامل‌محور</b><div class="muted" style="font-size:12px">با LLM گفت‌وگو کنید؛ عامل پیش‌نویس می‌سازد، بک‌تست می‌گیرد، ضرایب حد ضرر و حد سود را بهینه می‌کند و ذخیره می‌کند. افزودن به اجرای واقعی فقط با تأیید شما و ارتقای ممیزی‌شده.</div></div>
      <span class="spacer"></span><select id="sess"></select><button class="primary" id="newsess">گفت‌وگوی جدید</button><span class="chip" id="llmchip"></span></div></section>
    <section class="studio">
      <div class="panel chatp"><div class="head"><h2>گفت‌وگو با عامل</h2><span class="sub" id="jobl"></span></div>
        <div class="body"><div class="chat" id="chat"></div><div class="jobbar hidden" id="jobbar"><i></i></div>
        <div class="ideas" id="ideas">${IDEAS.map(x => `<button class="chip" data-idea="${esc(x)}">${esc(x)}</button>`).join('')}</div>
        <div class="composer"><textarea id="msg" rows="2" placeholder="ایده یا دستور خود را بنویسید… (Ctrl+Enter)"></textarea><button class="primary" id="send">ارسال</button></div></div></div>
      <div class="side-col">
        <div class="panel"><div class="head"><h2>پیش‌نویس فعلی</h2><div class="tools"><button id="bt6">بک‌تست ۶ پنجره</button><button id="bts">آزمون تنش</button><button id="save">ذخیره</button></div></div><div class="body" id="draft"></div></div>
        <div class="panel"><div class="head"><h2>نتیجهٔ بک‌تست</h2><span class="sub" id="btsub"></span></div><div class="body" id="test"></div></div>
      </div>
    </section>
    <section class="panel" style="margin-top:14px"><div class="head"><h2>استراتژی‌های ساخته‌شده</h2><span class="sub">آزمون کامل ← افزودن به اجرای واقعی ← ارتقا در کنترل اپراتور</span></div><div class="body" id="lib"></div></section>`;
  let O = null, sid = null, V = null, bound = [];
  const store = k => { try { return localStorage.getItem(k); } catch (_) { return null; } };
  const keep = (k, v) => { try { localStorage.setItem(k, v); } catch (_) { /* optional */ } };

  async function overview() {
    O = await ctx.safe(() => api('/api/studio'), $('#lib')); if (!O) return;
    const st = await ctx.safe(() => api('/api/settings')); bound = (st && st.bound && st.bound.custom_strategies) || [];
    $('#llmchip').textContent = 'LLM: ' + O.llm.provider + ' · ' + O.llm.model;
    $('#sess').innerHTML = O.sessions.map(s => `<option value="${s.id}">${esc(s.title)} — ${when(s.updated)}</option>`).join('') || '<option value="">—</option>';
    if (!sid) sid = (O.sessions.find(s => s.id === store('studio.sid')) || O.sessions[0] || {}).id || null;
    if (sid) $('#sess').value = sid;
    library();
  }
  async function session() {
    if (!sid) { V = null; $('#chat').innerHTML = '<div class="empty">برای شروع «گفت‌وگوی جدید» را بزنید یا یکی از ایده‌ها را انتخاب کنید.</div>'; drawDraft(); drawTest(); return; }
    V = await ctx.safe(() => api('/api/studio/sessions/' + sid), $('#chat')); if (!V) return;
    drawChat(); drawDraft(); drawTest(); drawJob();
  }
  function drawJob() {
    const j = V && V.job; $('#jobbar').classList.toggle('hidden', !j); $('#send').disabled = !!j;
    $('#jobl').innerHTML = j ? `<span class="dot on"></span> ${esc(j.label)}…` : '';
    if (j) $('#jobbar i').style.width = Math.round((j.progress || 0.05) * 100) + '%';
  }
  function toolCard(m) {
    const r = m.result || {};
    if (!r.ok) return `<div class="tool bad">✕ ${esc(TOOL_FA[m.tool] || m.tool)}: ${esc(r.error || 'ناموفق')}</div>`;
    if (m.tool === 'propose') return `<div class="tool ok">✓ پیش‌نویس معتبر شد <span class="mono faint">${esc((r.draft_sha256 || '').slice(0, 10))}</span></div>`;
    if (m.tool === 'save') return `<div class="tool ok">✓ ذخیره شد: <span class="mono">${esc(r.strategy_id)}</span></div>`;
    if (m.tool === 'backtest') return `<div class="tool ok">✓ بک‌تست: میانگین ${pct(r.custom.mean_return_percent)} · ${n0(r.custom.trades)} معامله · نرخ برد ${r.custom.win_rate === null ? '—' : pct(r.custom.win_rate * 100, 0)} · مبنا ${pct(r.builtin_baseline.mean_return_percent)}</div>`;
    if (m.tool === 'tune') return `<div class="tool ok">✓ ${n0((r.ranked || []).length)} ترکیب ضرایب آزموده شد</div>`;
    return '';
  }
  function eventCard(m) {
    if (m.kind === 'tune') return `<div class="tool"><b>جدول بهینه‌سازی</b> (${n0(m.windows)} پنجره)<div class="table-wrap"><table><thead><tr><th>ضرایب</th><th>میانگین</th><th>بدترین</th><th>معامله</th><th>برد</th><th>PF</th></tr></thead><tbody>
      ${m.rows.map((r, i) => `<tr${i === 0 ? ' class="best"' : ''}><td class="mono">${esc(Object.entries(r.params).map(([k, v]) => k.split('.').pop() + '=' + v).join(' '))}</td><td class="${r.mean_return_percent >= 0 ? 'pos' : 'neg'}">${pct(r.mean_return_percent)}</td><td>${pct(r.worst_return_percent)}</td><td>${n0(r.trades)}</td><td>${r.win_rate === null ? '—' : pct(r.win_rate * 100, 0)}</td><td>${r.profit_factor === null ? '—' : n2(r.profit_factor)}</td></tr>`).join('')}</tbody></table></div></div>`;
    if (m.kind === 'manual_edit') return `<div class="tool">✎ ویرایش دستی ضرایب: حد ضرر ${esc(m.summary.stop)} · TP1 ${esc(m.summary.tp1)} · نگهداری ${n0(m.summary.hold)} ساعت</div>`;
    if (m.kind === 'backtest') return `<div class="tool">∿ بک‌تست ${n0(m.windows)} پنجره (${m.scenario === 'stress' ? 'تنش' : 'پایه'}) ثبت شد</div>`;
    return '';
  }
  function drawChat() {
    const box = $('#chat'); const atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
    box.innerHTML = V.messages.length ? V.messages.map(m => {
      if (m.role === 'tool') return toolCard(m);
      if (m.role === 'event') return eventCard(m);
      const act = m.action && m.action.type && m.action.type !== 'none' ? `<span class="chip smc">⚙ ${esc(TOOL_FA[m.action.type] || m.action.type)}</span>` : '';
      return `<div class="bubble ${m.role}"><div class="who">${esc(ROLE[m.role] || m.role)} ${act}</div><div class="txt">${esc(m.text || '')}</div>${m.meta && m.meta.model ? `<div class="faint mono" style="font-size:10px">${esc(m.meta.model)} · ${n0(m.meta.latency_ms)}ms</div>` : ''}</div>`;
    }).join('') : '<div class="empty">ایده‌تان را بنویسید؛ مثلاً «در بازار رنج روی شکار نقدینگی با تأیید RSI کار کن».</div>';
    if (atEnd || V.job) box.scrollTop = box.scrollHeight;
  }
  function drawDraft() {
    const d = V && V.draft, sm = V && V.draft_summary;
    if (!d) { $('#draft').innerHTML = '<div class="empty">هنوز پیش‌نویسی نیست. از عامل بخواهید یکی بسازد.</div>'; return; }
    const st = d.stop, tp = d.take_profit;
    const num = (path, v, step) => `<label><span>${path}</span><input type="number" step="${step}" data-p="${path}" value="${v}"></label>`;
    $('#draft').innerHTML = `<div class="dname"><b>${esc(d.name_fa)}</b> <span class="chip ${d.family === 'smart_money' ? 'smc' : 'ind'}">${d.family === 'smart_money' ? 'SMC' : d.family === 'hybrid' ? 'ترکیبی' : 'اندیکاتور'}</span>
      ${d.regimes.map(r => `<span class="chip">${REGIME_FA[r]}</span>`).join('')}</div>
      ${d.thesis_fa ? `<div class="muted" style="font-size:12.5px;margin:4px 0 8px">${esc(d.thesis_fa)}</div>` : ''}
      <div class="conds"><div class="ct">همهٔ شرط‌ها</div>${sm.all.map(x => `<div class="cond mono">${esc(x)}</div>`).join('')}
      ${sm.any.length ? `<div class="ct">حداقل یکی</div>${sm.any.map(x => `<div class="cond mono">${esc(x)}</div>`).join('')}` : ''}</div>
      <div class="ladder-mini"><span class="neg">SL ${esc(sm.stop)}</span><span>ورود</span><span class="pos">TP1 ${esc(sm.tp1)}</span><span class="pos">TP2 = TP1+d</span><span class="pos">TP3 = TP1+2d</span></div>
      <div class="faint" style="font-size:11.5px">نگهداری حداکثر ${n0(sm.hold)} ساعت · خروج روند: ${esc(sm.trend_exit)} · سقف‌های حساب و تأیید AI در اجرا برقرارند</div>
      <div class="coefs">${st.method === 'atr' ? num('stop.atr_multiple', st.atr_multiple, 0.1) : st.method === 'percent' ? num('stop.percent', st.percent, 0.1) : num('stop.lookback', st.lookback, 1) + num('stop.buffer_percent', st.buffer_percent, 0.1)}
        ${tp.method === 'r_multiple' ? num('take_profit.r_multiple', tp.r_multiple, 0.1) : tp.method === 'percent' ? num('take_profit.percent', tp.percent, 0.1) : tp.method === 'swing_high' ? num('take_profit.lookback', tp.lookback, 1) : ''}
        ${num('max_holding_hours', d.max_holding_hours, 1)}<button id="applyc">اعمال ضرایب</button></div>
      <details><summary>مشخصات JSON (داده، نه کد)</summary><pre class="reasoning">${esc(JSON.stringify(d, null, 1))}</pre></details>`;
    $('#applyc').onclick = async () => {
      const spec = JSON.parse(JSON.stringify(d));
      $$('#draft input[data-p]').forEach(i => { const [a, b] = i.dataset.p.split('.'); if (b) spec[a][b] = +i.value; else spec[a] = +i.value; });
      try { V = await api(`/api/studio/sessions/${sid}/draft`, { body: { spec } }); drawChat(); drawDraft(); drawTest(); } catch (e) { alertIn($('#draft'), e.message); }
    };
  }
  function bars(rows, base) {
    if (!rows || !rows.length) return '';
    const all = rows.map(r => r.return_percent).concat((base || []).map(r => r.return_percent));
    const m = Math.max(1, ...all.map(Math.abs)); const W = 300, H = 120, bw = W / rows.length;
    const y = v => H / 2 - v / m * (H / 2 - 8);
    return `<svg viewBox="0 0 ${W} ${H}" class="btbars"><line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" stroke="#353a43"/>
      ${rows.map((r, i) => { const b = (base || [])[i]; const v = r.return_percent; return `<rect x="${i * bw + bw * 0.15}" width="${bw * 0.38}" y="${Math.min(y(v), H / 2)}" height="${Math.abs(y(v) - H / 2) || 1}" rx="2" fill="${v >= 0 ? '#34d399' : '#fb7185'}"><title>پنجره ${i + 1}: ${v.toFixed(2)}%</title></rect>
        ${b ? `<rect x="${i * bw + bw * 0.55}" width="${bw * 0.3}" y="${Math.min(y(b.return_percent), H / 2)}" height="${Math.abs(y(b.return_percent) - H / 2) || 1}" rx="2" fill="#646b76"><title>مبنا: ${b.return_percent.toFixed(2)}%</title></rect>` : ''}`; }).join('')}</svg>
      <div class="faint" style="font-size:11px"><span class="pos">■</span>/<span class="neg">■</span> این استراتژی (تنها) · <span style="color:#646b76">■</span> مجموعهٔ استراتژی‌های فعلی موتور، همان پنجره‌ها</div>`;
  }
  const kpis = (c, b) => `<div class="mini-kpis">
      <div><span>میانگین پنجره</span><b class="${c.mean_return_percent >= 0 ? 'pos' : 'neg'}">${pct(c.mean_return_percent)}</b><i>مبنا ${pct(b ? b.mean_return_percent : null)}</i></div>
      <div><span>بدترین پنجره</span><b>${pct(c.worst_return_percent)}</b><i>بهترین ${pct(c.best_return_percent)}</i></div>
      <div><span>معاملات</span><b>${n0(c.trades)}</b><i>سیگنال ${n0(c.signals)}</i></div>
      <div><span>نرخ برد</span><b>${c.win_rate === null ? '—' : pct(c.win_rate * 100, 0)}</b><i>PF ${c.profit_factor === null ? (c.no_losing_trades ? '∞' : '—') : n2(c.profit_factor)}</i></div>
      <div><span>بیشینهٔ افت</span><b>${pct(-c.max_drawdown_percent)}</b><i>کارمزد ${toman(c.fees_tmn)}</i></div></div>
    <div class="reasons">${Object.entries(c.exit_reasons || {}).map(([k, v]) => `<span class="chip">${esc(k)} × ${n0(v)}</span>`).join('')}</div>`;
  function drawTest() {
    const t = V && V.last_test;
    $('#btsub').textContent = t ? `${n0(t.windows)} پنجرهٔ ۷۲ساعته · ${t.scenario === 'stress' ? 'تنش هزینه' : 'پایه'}${t.current ? '' : ' · مربوط به نسخهٔ قبلی پیش‌نویس'}` : '';
    if (!t) { $('#test').innerHTML = '<div class="empty">بک‌تستی انجام نشده است.</div>'; return; }
    $('#test').innerHTML = kpis(t.custom, t.baseline) + bars(t.rows, t.baseline_rows) +
      (t.trades.length ? `<details><summary>${n0(t.trades.length)} معاملهٔ آخر</summary><div class="table-wrap scroll" style="max-height:220px"><table><thead><tr><th>جفت</th><th>خروج</th><th>TP</th><th>ساعت</th><th>بازده</th></tr></thead><tbody>
      ${t.trades.slice().reverse().map(x => `<tr><td class="mono">${esc(x.symbol)}</td><td>${esc(x.reason)}</td><td>${n0(x.tp_stage)}</td><td>${n0(x.held_hours)}</td><td class="${x.pnl_tmn >= 0 ? 'pos' : 'neg'}">${pct(x.return_percent)}</td></tr>`).join('')}</tbody></table></div></details>` : '') +
      `<div class="faint" style="font-size:11px;margin-top:6px">داده‌های ساعتی ثبت‌شدهٔ والکس، بدون AI (هر پیشنهاد با اندازهٔ کامل)، همان هزینه‌ها و نردبان سه‌TP موتور. این پنجره‌ها قبلاً دیده شده‌اند و سود آینده را تضمین نمی‌کنند.</div>`;
  }
  function library() {
    const rows = O.strategies;
    $('#lib').innerHTML = rows.length ? rows.map(r => {
      const status = bound.includes(r.id) && r.status !== 'retired' ? 'live' : r.status; const [fa, cls] = STATUS[status] || [status, ''];
      const rep = r.report && r.report.spec_sha256 === r.spec_sha256 ? r.report : null;
      return `<div class="libitem"><div class="lh"><b>${esc(r.name)}</b> <span class="chip ${cls}">${esc(fa)}</span> <span class="mono faint">${esc(r.id)}</span>
        <span class="spacer"></span>${['draft', 'tested'].includes(r.status) ? `<button data-test="${r.id}">آزمون کامل</button>` : ''}${rep && r.status === 'tested' ? `<button class="primary" data-ok="${r.id}" ${rep.eligible ? '' : 'disabled'}>افزودن به اجرای واقعی</button>` : ''}${r.status !== 'retired' ? `<button class="danger" data-ret="${r.id}">بازنشستگی</button>` : ''}</div>
        <div class="faint" style="font-size:12px">${esc(r.summary.all.join(' · '))}${r.summary.any.length ? ' · یکی از: ' + esc(r.summary.any.join(' / ')) : ''} · SL ${esc(r.summary.stop)} · TP1 ${esc(r.summary.tp1)} · ${r.summary.regimes.map(x => REGIME_FA[x]).join('، ')}</div>
        ${rep ? `<div class="repgrid"><div><b>این استراتژی (۶ پنجره)</b>${kpis(rep.custom, rep.baseline)}</div><div><b>همراه استراتژی‌های فعلی</b><div class="muted" style="font-size:12px">میانگین ${pct(rep.combined.mean_return_percent)} در برابر ${pct(rep.baseline.mean_return_percent)} بدون آن · تنش هزینه: ${pct(rep.stress.mean_return_percent)}</div>
          ${rep.eligible ? '<div class="notice green" style="margin-top:6px;font-size:12px">شرط حداقلی افزودن برقرار است.</div>' : `<div class="notice red" style="margin-top:6px;font-size:12px">شرط حداقلی برقرار نیست (حداقل ${n0(rep.criteria.min_trades)} معامله و بدترین پنجره بهتر از ۵٪-).</div>`}</div></div>` : (r.report ? '<div class="faint" style="font-size:11.5px">آزمون کامل برای نسخهٔ قبلی است؛ دوباره اجرا کنید.</div>' : '')}
        <div id="lm-${r.id}" class="muted" style="font-size:12px"></div></div>`; }).join('') : '<div class="empty">هنوز استراتژی‌ای ذخیره نشده است.</div>';
    $$('#lib button[data-test]').forEach(b => b.onclick = async () => { try { await api(`/api/studio/strategies/${b.dataset.test}/test`, { body: {} }); $('#lm-' + b.dataset.test).textContent = 'آزمون کامل در صف اجرا قرار گرفت (۱ تا ۳ دقیقه)…'; } catch (e) { $('#lm-' + b.dataset.test).textContent = e.message; } });
    $$('#lib button[data-ret]').forEach(b => b.onclick = async () => { if (!confirm2(b)) return; try { await api(`/api/studio/strategies/${b.dataset.ret}/retire`, { body: {} }); overview(); } catch (e) { $('#lm-' + b.dataset.ret).textContent = e.message; } });
    $$('#lib button[data-ok]').forEach(b => b.onclick = () => {
      const box = $('#lm-' + b.dataset.ok);
      box.innerHTML = `<div class="form" style="margin-top:6px"><label>برای تأیید بنویسید: <b>${esc(O.approve_phrase)}</b></label><input id="ap-${b.dataset.ok}"><button class="primary" id="apgo-${b.dataset.ok}">تأیید نهایی</button></div>`;
      $('#apgo-' + b.dataset.ok).onclick = async () => { try { const r = await api(`/api/studio/strategies/${b.dataset.ok}/approve`, { body: { confirmation: $('#ap-' + b.dataset.ok).value } }); box.innerHTML = `<div class="notice green">تأیید شد. برای ورود به موتور: ${esc(r.next)} — <a href="#operator">کنترل اپراتور</a></div>`; overview(); } catch (e) { box.textContent = e.message; } };
    });
  }
  function confirm2(b) { if (b.dataset.armed) return true; b.dataset.armed = 1; b.textContent = 'مطمئنید؟'; setTimeout(() => { delete b.dataset.armed; b.textContent = 'بازنشستگی'; }, 3500); return false; }
  function alertIn(node, msg) { const d = document.createElement('div'); d.className = 'notice red'; d.textContent = msg; node.prepend(d); setTimeout(() => d.remove(), 5000); }

  async function send(text) {
    text = (text || $('#msg').value).trim(); if (!text) return;
    if (!sid) { const s = await api('/api/studio/sessions', { body: { title: text.slice(0, 40) } }); sid = s.id; keep('studio.sid', sid); await overview(); }
    try { V = await api(`/api/studio/sessions/${sid}/message`, { body: { text } }); $('#msg').value = ''; drawChat(); drawJob(); } catch (e) { alertIn($('#chat'), e.message); }
  }
  $('#send').onclick = () => send();
  $('#msg').onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send(); };
  $$('#ideas button').forEach(b => b.onclick = () => send(b.dataset.idea));
  $('#newsess').onclick = async () => { const s = await api('/api/studio/sessions', { body: {} }); sid = s.id; keep('studio.sid', sid); await overview(); session(); };
  $('#sess').onchange = () => { sid = $('#sess').value; keep('studio.sid', sid); session(); };
  $('#bt6').onclick = async () => { if (!sid) return; try { V = await api(`/api/studio/sessions/${sid}/backtest`, { body: { windows: 6, scenario: 'base' } }); drawJob(); } catch (e) { alertIn($('#draft'), e.message); } };
  $('#bts').onclick = async () => { if (!sid) return; try { V = await api(`/api/studio/sessions/${sid}/backtest`, { body: { windows: 3, scenario: 'stress' } }); drawJob(); } catch (e) { alertIn($('#draft'), e.message); } };
  $('#save').onclick = async () => { if (!sid) return; try { V = await api(`/api/studio/sessions/${sid}/save`, { body: {} }); overview(); } catch (e) { alertIn($('#draft'), e.message); } };

  (async () => { await overview(); await session(); })();
  let wasBusy = false;
  ctx.every(1500, async () => {
    if (!sid) return;
    const busy = V && V.job;
    if (busy || wasBusy) { const n = await ctx.safe(() => api('/api/studio/sessions/' + sid)); if (n) {
      const changed = !V || n.messages.length !== V.messages.length; const dchg = !V || n.draft_sha256 !== V.draft_sha256;
      const tchg = !V || JSON.stringify(n.last_test && n.last_test.custom) !== JSON.stringify(V.last_test && V.last_test.custom) || (n.last_test && V.last_test && n.last_test.current !== V.last_test.current);
      V = n; if (changed) drawChat(); if (dchg) drawDraft(); if (tchg) drawTest(); drawJob(); } }
    wasBusy = !!busy;
  });
  ctx.every(5000, async () => { if (O && O.jobs.some(j => j.status === 'running' || j.status === 'queued')) overview(); else if (O) { const n = await ctx.safe(() => api('/api/studio')); if (n && JSON.stringify(n.strategies.map(s => [s.id, s.status, !!s.report])) !== JSON.stringify(O.strategies.map(s => [s.id, s.status, !!s.report]))) { O = n; library(); } } });
}
