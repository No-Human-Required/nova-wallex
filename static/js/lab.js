// «آزمایشگاه بک‌تست»: any timeframe and range, one symbol or a portfolio,
// professional metrics, equity vs buy-and-hold, drawdown, monthly returns.
import { S, api, n0, n2, toman, pct, signCls, when, esc, $, $$, sym, download } from './core.js';

const C = { strat: '#c98500', bench: '#3987e5', dd: '#e66767', grid: '#1e2228', mid: [56, 56, 53], pos: [57, 135, 229], neg: [230, 103, 103] };
const DAY = 86400;
const KPI_HELP = {
  sharpe: 'بازده اضافه به ازای هر واحد نوسان، سالانه (نرخ بدون ریسک صفر)', sortino: 'مثل شارپ ولی فقط نوسان منفی را جریمه می‌کند',
  calmar: 'CAGR تقسیم بر حداکثر افت', pf: 'جمع سود معاملات برنده ÷ جمع زیان بازنده‌ها', sqn: 'کیفیت سیستم (Van Tharp): √n × میانگین R ÷ انحراف R',
  ulcer: 'عمق و طول افت‌ها با هم', exposure: 'درصد کندل‌هایی که دست‌کم یک موقعیت باز بود'
};

export function labSection(root, { every, keep, safe }) {
  root.innerHTML = `
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>آزمایشگاه بک‌تست</h2><span class="sub">هر تایم‌فریم، هر بازه، تک‌ارزی یا پرتفویی؛ ورود با همان کد استراتژی موتور</span>
    <div class="tools"><button id="lpreset">تنظیمات موتور واقعی</button><button id="lreset">پیش‌فرض</button></div></div>
    <div class="body form" id="lform"><div class="skeleton" style="height:120px"></div></div></section>
  <section class="panel" style="margin-bottom:14px" id="lres"><div class="head"><h2 id="ltitle">نتیجه</h2><span class="sub" id="lsub">یک تست اجرا یا از فهرست زیر انتخاب کنید</span>
    <div class="tools" id="lexp"></div></div><div class="body" id="lbody"><div class="empty">هنوز نتیجه‌ای انتخاب نشده است.</div></div></section>
  <section class="panel" style="margin-bottom:14px"><div class="head"><h2>تست‌های آزمایشگاه</h2></div><div class="body table-wrap" id="lruns"></div></section>`;
  let meta = null, symbols = ['BTCTMN'], current = null;

  const field = (id, label, value, attrs = '') => `<label class="lf"><span>${label}</span><input id="${id}" value="${value ?? ''}" ${attrs}></label>`;
  const iso = ts => new Date(ts * 1000).toISOString().slice(0, 16);
  function form(d) {
    const tf = meta.timeframes.map(t => `<option value="${t.id}" ${t.id === d.timeframe ? 'selected' : ''}>${t.fa}</option>`).join('');
    const now = Math.floor(Date.now() / 1000);
    $('#lform').innerHTML = `
      <div class="lgrid">
        <label class="lf"><span>منبع داده</span><select id="lsrc"><option value="wallex">کندل‌های عمومی والکس (هر بازه)</option><option value="recorded">دادهٔ ضبط‌شدهٔ مخزن (ساعتی، بازتولیدپذیر)</option></select></label>
        <label class="lf"><span>تایم‌فریم</span><select id="ltf">${tf}</select></label>
        <label class="lf"><span>از (UTC)</span><input id="lstart" type="datetime-local" value="${iso(now - 30 * DAY)}"></label>
        <label class="lf"><span>تا (UTC)</span><input id="lend" type="datetime-local" value="${iso(now)}"></label>
      </div>
      <div class="row" style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0">${[[7, '۷ روز'], [30, '۳۰ روز'], [90, '۹۰ روز'], [180, '۶ ماه'], [365, '۱ سال']].map(([n, t]) => `<button data-days="${n}">${t}</button>`).join('')}
        <span class="faint" id="lspan" style="font-size:11.5px;align-self:center"></span></div>
      <div class="lf"><span>نمادها <b id="lmode" class="chip y"></b></span>
        <div id="lsyms" style="display:flex;gap:6px;flex-wrap:wrap;margin:4px 0"></div>
        <div class="row" style="display:flex;gap:6px;flex-wrap:wrap"><input id="lsearch" list="lmk" placeholder="افزودن نماد، مثلاً ETHTMN" class="ltr" style="width:220px"><datalist id="lmk">${meta.markets.map(m => `<option value="${m.symbol}">`).join('')}</datalist>
          <button id="ladd">افزودن</button><button data-pre="btc">فقط BTC</button><button data-pre="major">BTC + ETH</button><button data-pre="top10">۱۰ بازار پرحجم</button><button data-pre="top25">۲۵ بازار پرحجم</button><button data-pre="clear">پاک کردن</button></div></div>
      <div class="lf"><span>استراتژی‌ها</span><div id="lstrats" style="display:flex;gap:10px;flex-wrap:wrap">${meta.strategies.map(s => `<label class="chk"><input type="checkbox" value="${s.id}" ${d.strategies.includes(s.id) ? 'checked' : ''}> <span class="chip ${s.family === 'smart_money' ? 'smc' : 'ind'}">${s.family === 'smart_money' ? 'SMC' : 'اندیکاتور'}</span> ${esc(s.fa)}</label>`).join('')}</div></div>
      <details open><summary>سرمایه و اندازهٔ موقعیت</summary><div class="lgrid">
        ${field('lcap', 'سرمایه (تومان)', d.capital_tmn, 'type="number" min="100000"')}
        <label class="lf"><span>روش اندازه</span><select id="lsize"><option value="risk" ${d.sizing === 'risk' ? 'selected' : ''}>ریسک ثابت (٪ سرمایه ÷ حد ضرر)</option><option value="fixed" ${d.sizing === 'fixed' ? 'selected' : ''}>درصد ثابت سرمایه</option></select></label>
        ${field('lrisk', 'ریسک هر معامله ٪', d.risk_pct, 'type="number" step="0.05"')}${field('lpos', 'اندازهٔ ثابت ٪', d.position_pct, 'type="number" step="1"')}
        ${field('lasset', 'سقف هر دارایی ٪ (خالی = خودکار)', d.max_asset_pct ?? '', 'type="number" step="1"')}${field('lgross', 'سقف ناخالص ٪', d.max_gross_pct, 'type="number" step="1"')}
        ${field('lmaxp', 'حداکثر موقعیت هم‌زمان', d.max_positions, 'type="number" min="1"')}${field('lmin', 'حداقل سفارش (تومان)', d.min_order_tmn, 'type="number"')}</div></details>
      <details open><summary>خروج و حد ضرر</summary><div class="lgrid">
        <label class="lf"><span>مدل خروج</span><select id="lexit"><option value="ladder" ${d.exit_mode === 'ladder' ? 'selected' : ''}>سه TP با فاصلهٔ برابر + حد ضرر پله‌ای (موتور)</option><option value="single" ${d.exit_mode === 'single' ? 'selected' : ''}>یک TP روی هدف</option></select></label>
        <label class="chk"><input type="checkbox" id="ltrail" ${d.trailing ? 'checked' : ''}> حد ضرر شناور از اوج</label>
        <label class="chk"><input type="checkbox" id="ltrend" ${d.trend_exit ? 'checked' : ''}> خروج با برگشت روند (EMA9&lt;EMA21)</label>
        ${field('lhold', 'حداکثر نگهداری (ساعت، خالی = استراتژی)', d.max_hold_hours ?? '', 'type="number" step="1"')}
        ${field('lsmin', 'حد ضرر کمینه ٪ (خالی = خودکار)', '', 'type="number" step="0.1"')}${field('lsmax', 'حد ضرر بیشینه ٪ (خالی = خودکار)', '', 'type="number" step="0.1"')}
        ${field('latr', 'ضریب ATR حد ضرر', d.stop_atr_multiple, 'type="number" step="0.1"')}${field('lrr', 'حداقل R/R', d.min_reward_risk, 'type="number" step="0.1"')}
        ${field('ltpr', 'TP روندی (برابر R)', d.trend_tp_r, 'type="number" step="0.1"')}${field('lbe', 'حاشیهٔ سربه‌سر ٪', d.breakeven_buffer_pct, 'type="number" step="0.1"')}</div></details>
      <details><summary>فیلتر، اجرا و هزینه</summary><div class="lgrid">
        ${field('lq', 'حداقل کیفیت (۰ تا ۱۰۰)', d.min_quality, 'type="number"')}
        <label class="chk"><input type="checkbox" id="lreg" ${d.regime_filter ? 'checked' : ''}> فیلتر رژیم بازار (پهنای نمادهای انتخابی)</label>
        ${field('lcool', 'مکث پس از خروج (کندل)', d.cooldown_bars, 'type="number" min="0"')}${field('llat', 'تأخیر اجرا (کندل)', d.latency_bars, 'type="number" min="1"')}
        ${field('llook', 'پنجرهٔ نگاه به عقب (کندل)', d.lookback_bars, 'type="number" min="60"')}${field('lmiss', 'حداکثر کندل خالی ٪', d.max_missing_pct, 'type="number"')}
        ${field('lfee', 'کارمزد بازار تومانی (bps هر سمت)', d.fee_tmn_bps, 'type="number" step="1"')}${field('lfeeu', 'کارمزد بازار تتری (bps)', d.fee_usdt_bps, 'type="number" step="1"')}
        ${field('lspr', 'نیم‌اسپرد (bps)', d.half_spread_bps, 'type="number" step="1"')}${field('lslip', 'لغزش (bps)', d.slippage_bps, 'type="number" step="1"')}</div></details>
      <div class="row" style="display:flex;gap:8px;align-items:center;margin-top:10px"><input id="ltitlein" placeholder="نام تست (اختیاری)" style="width:220px"><button class="primary" id="lgo">اجرای بک‌تست</button><span id="lmsg" class="muted"></span></div>`;
    drawSyms();
    $$('#lform [data-days]').forEach(b => b.onclick = () => { const e = Date.parse($('#lend').value + 'Z') / 1000; $('#lstart').value = iso(e - +b.dataset.days * DAY); });
    $('#lsrc').onchange = () => { const rec = $('#lsrc').value === 'recorded'; const [a, b] = meta.recorded_span;
      $('#lspan').textContent = rec ? `دادهٔ ضبط‌شده: ${when(a)} تا ${when(b)}؛ فقط تایم‌فریم ۱ ساعت و بالاتر` : 'کمتر از ۱ ساعت از کندل‌های یک‌دقیقه‌ای ساخته می‌شود (حداکثر ۶۲ روز)';
      if (rec) { $('#lend').value = iso(b); $('#lstart').value = iso(Math.max(a + 5 * DAY, b - 30 * DAY)); if (['1m', '5m', '15m', '30m'].includes($('#ltf').value)) $('#ltf').value = '1h'; } };
    $('#lsrc').onchange();
    $('#ladd').onclick = () => { const s = $('#lsearch').value.trim().toUpperCase(); if (meta.markets.some(m => m.symbol === s) && !symbols.includes(s)) { symbols.push(s); drawSyms(); } $('#lsearch').value = ''; };
    $('#lsearch').onkeydown = e => { if (e.key === 'Enter') $('#ladd').click(); };
    $$('#lform [data-pre]').forEach(b => b.onclick = () => preset(b.dataset.pre));
    $('#lgo').onclick = submit;
  }
  function drawSyms() {
    $('#lsyms').innerHTML = symbols.map(s => `<span class="chip">${esc(s)} <a href="javascript:void 0" data-rm="${s}" style="color:var(--faint)">✕</a></span>`).join('') || '<span class="faint" style="font-size:12px">نمادی انتخاب نشده است</span>';
    $('#lmode').textContent = symbols.length > 1 ? `پرتفویی · ${symbols.length} نماد` : 'تک‌ارزی';
    $$('#lsyms [data-rm]').forEach(a => a.onclick = () => { symbols = symbols.filter(x => x !== a.dataset.rm); drawSyms(); });
  }
  async function preset(kind) {
    if (kind === 'btc') symbols = ['BTCTMN'];
    else if (kind === 'major') symbols = ['BTCTMN', 'ETHTMN'];
    else if (kind === 'clear') symbols = [];
    else {
      const t = await safe(() => api('/api/public/ticker'), $('#lmsg')); if (!t) return;
      const ok = new Set(meta.markets.map(m => m.symbol));
      symbols = t.rows.filter(r => r.quote === 'TMN' && ok.has(r.symbol)).sort((a, b) => (b.volume_tmn_24h || 0) - (a.volume_tmn_24h || 0)).slice(0, kind === 'top25' ? 25 : 10).map(r => r.symbol);
    }
    drawSyms();
  }
  const num = id => { const v = $('#' + id).value; return v === '' ? null : +v; };
  function params() {
    return { symbols, timeframe: $('#ltf').value, source: $('#lsrc').value, start: $('#lstart').value + ':00Z', end: $('#lend').value + ':00Z',
      strategies: $$('#lstrats input:checked').map(x => x.value), capital_tmn: num('lcap'), sizing: $('#lsize').value, risk_pct: num('lrisk'),
      position_pct: num('lpos'), max_asset_pct: num('lasset'), max_gross_pct: num('lgross'), max_positions: num('lmaxp'), min_order_tmn: num('lmin'),
      exit_mode: $('#lexit').value, trailing: $('#ltrail').checked, trend_exit: $('#ltrend').checked, max_hold_hours: num('lhold'),
      min_stop_pct: num('lsmin'), max_stop_pct: num('lsmax'), stop_atr_multiple: num('latr'), min_reward_risk: num('lrr'), trend_tp_r: num('ltpr'),
      breakeven_buffer_pct: num('lbe'), min_quality: num('lq'), regime_filter: $('#lreg').checked, cooldown_bars: num('lcool'), latency_bars: num('llat'),
      lookback_bars: num('llook'), max_missing_pct: num('lmiss'), fee_tmn_bps: num('lfee'), fee_usdt_bps: num('lfeeu'), half_spread_bps: num('lspr'), slippage_bps: num('lslip') };
  }
  async function submit() {
    if (!S.authenticated) { $('#lmsg').textContent = 'برای اجرای بک‌تست وارد «کنترل اپراتور» شوید.'; return; }
    $('#lmsg').textContent = 'در حال ارسال…';
    try { const r = await api('/api/studio/lab/runs', { body: { params: params(), title: $('#ltitlein').value || null } }); $('#lmsg').textContent = 'در صف اجرا'; current = r.id; loadRuns(); }
    catch (e) { $('#lmsg').textContent = e.message; }
  }
  $('#lpreset').onclick = () => { if (!meta) return; form({ ...meta.defaults, min_quality: 55, regime_filter: true, risk_pct: 0.4, max_positions: 4, max_asset_pct: 10, max_gross_pct: 50, timeframe: '1h' }); symbols.length < 3 && preset('top25'); };
  $('#lreset').onclick = () => meta && form(meta.defaults);

  async function loadRuns() {
    const rs = await safe(() => api('/api/studio/lab/runs'), $('#lruns')); if (!rs) return;
    $('#lruns').innerHTML = rs.length ? `<table><thead><tr><th>نام</th><th>نماد</th><th>تایم‌فریم</th><th>بازه</th><th>وضعیت</th><th>بازده</th><th>خرید و نگهداری</th><th>حداکثر افت</th><th>شارپ</th><th>معامله</th><th></th></tr></thead><tbody>${rs.map(r => {
      const pr = r.progress; const st = r.status === 'done' ? '<span class="pos">انجام شد</span>' : r.status === 'failed' ? `<span class="neg" title="${esc(r.error)}">ناموفق</span>` : r.status === 'interrupted' ? '<span class="warn">قطع شد</span>'
        : `<span class="warn">${pr ? (pr.stage === 'data' ? 'دریافت داده ' : 'شبیه‌سازی ') + n0(pr.total ? pr.done / pr.total * 100 : 0) + '٪' : 'در صف'}</span>`;
      const s = r.summary || {};
      return `<tr><td>${esc(r.title)}</td><td style="font-size:11.5px">${esc(r.spec.symbols.length > 3 ? r.spec.symbols.length + ' نماد' : r.spec.symbols.join('، '))}</td><td>${esc(r.spec.timeframe)}</td>
        <td style="font-size:11.5px">${when(r.spec.start_ts)} → ${when(r.spec.end_ts)}</td><td>${st}</td><td class="${signCls(s.total_return_pct)}">${pct(s.total_return_pct)}</td>
        <td class="${signCls(r.benchmark_return_pct)}">${pct(r.benchmark_return_pct)}</td><td>${s.max_drawdown_pct !== undefined ? pct(-s.max_drawdown_pct) : '—'}</td><td>${n2(s.sharpe)}</td><td>${n0(s.trades)}</td>
        <td>${r.status === 'done' || r.status === 'failed' ? `<button data-r="${r.id}">نمایش</button>` : ''}</td></tr>`;
    }).join('')}</tbody></table>` : '<div class="empty">هنوز تستی اجرا نشده است.</div>';
    $$('#lruns [data-r]').forEach(b => b.onclick = () => show(b.dataset.r));
    const mine = rs.find(r => r.id === current);
    if (mine && (mine.status === 'done' || mine.status === 'failed') && $('#lres').dataset.shown !== mine.id) show(mine.id);
  }
  async function show(id) {
    const r = await safe(() => api('/api/studio/lab/runs/' + id), $('#lbody')); if (!r) return;
    $('#lres').dataset.shown = id; $('#ltitle').textContent = r.title || 'نتیجه';
    if (r.status === 'failed') { $('#lsub').textContent = ''; $('#lexp').innerHTML = ''; $('#lbody').innerHTML = `<div class="notice red">${esc(r.error)}</div>`; return; }
    render(r.result, r.title);
    $('#lres').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function render(res, title) {
    const s = res.summary, b = res.benchmark, p = res.params, mc = res.monte_carlo;
    $('#lsub').textContent = `${p.symbols.length > 1 ? 'پرتفوی ' + p.symbols.length + ' نماد' : p.symbols[0]} · ${p.timeframe} · ${when(p.start_ts)} → ${when(p.end_ts)} · ${res.data_source === 'recorded' ? 'دادهٔ ضبط‌شده' : 'والکس'}`;
    $('#lexp').innerHTML = '<button id="lcsv">معاملات CSV</button><button id="lcsv2">منحنی سرمایه CSV</button><button id="ljson">کل نتیجه JSON</button>';
    const kpi = (label, value, note = '', cls = '', help = '') => `<div class="panel kpi"><div class="label" ${help ? `title="${esc(help)}"` : ''}>${label}${help ? ' ⓘ' : ''}</div><div class="value ${cls}" style="font-size:20px">${value}</div><div class="note">${note}</div></div>`;
    const cards = [
      kpi('بازده کل', pct(s.total_return_pct), toman(s.net_profit_tmn), signCls(s.total_return_pct)),
      kpi('خرید و نگهداری', b ? pct(b.total_return_pct) : '—', b ? 'اضافه‌بازده ' + pct(b.excess_return_pct) : '', b ? signCls(b.total_return_pct) : ''),
      kpi('CAGR', pct(s.cagr_pct), s.annualization_note || 'رشد سالانهٔ مرکب', signCls(s.cagr_pct)),
      kpi('حداکثر افت', pct(-s.max_drawdown_pct), `از ${when(s.max_dd_peak)} تا ${when(s.max_dd_trough)}`, 'neg'),
      kpi('شارپ', n2(s.sharpe), 'سالانه', '', KPI_HELP.sharpe), kpi('سورتینو', n2(s.sortino), 'سالانه', '', KPI_HELP.sortino),
      kpi('کالمار', n2(s.calmar), '', '', KPI_HELP.calmar), kpi('نوسان سالانه', pct(s.volatility_pct), 'Ulcer ' + n2(s.ulcer_index), '', KPI_HELP.ulcer),
      kpi('Profit Factor', n2(s.profit_factor), 'SQN ' + n2(s.sqn), '', KPI_HELP.pf), kpi('نرخ برد', pct(s.win_rate_pct, 1), `${n0(s.trades)} معامله`),
      kpi('امید ریاضی', pct(s.expectancy_pct), `${n2(s.avg_r)}R · ${toman(s.expectancy_tmn)}`, signCls(s.expectancy_pct)),
      kpi('میانگین سود / زیان', `${pct(s.avg_win_pct, 1)} / ${pct(s.avg_loss_pct, 1)}`, 'نسبت ' + n2(s.payoff_ratio)),
      kpi('در بازار', pct(s.exposure_pct, 0), 'ناخالص میانگین ' + pct(s.avg_gross_pct, 0), '', KPI_HELP.exposure),
      kpi('کارمزد کل', toman(s.fees_tmn), 'گردش ' + n2(s.turnover_x) + '× سرمایه'),
      kpi('بلندترین افت', n2(s.longest_dd_days) + ' روز', s.max_dd_recovered ? 'جبران: ' + when(s.max_dd_recovered) : 'هنوز جبران نشده'),
      kpi('بتا / آلفا', b ? `${n2(b.beta)} / ${pct(b.alpha_annual_pct, 1)}` : '—', b ? 'همبستگی ' + n2(b.correlation) : '')];
    $('#lbody').innerHTML = `<div class="grid g4" style="margin-bottom:12px">${cards.join('')}</div>
      <div class="legend" style="display:flex;gap:16px;font-size:12px;margin-bottom:4px"><span><i class="sw" style="background:${C.strat}"></i> استراتژی</span>${b ? `<span><i class="sw" style="background:${C.bench}"></i> خرید و نگهداری هم‌وزن</span>` : ''}</div>
      <div id="leq" class="lchart" style="height:300px"></div>
      <div class="muted" style="font-size:12px;margin:10px 0 4px">افت از قله (٪)</div><div id="ldd" class="lchart" style="height:130px"></div>
      <div class="grid g2" style="margin-top:14px"><div><h3 class="lh">بازده ماهانه</h3><div id="lmon" class="table-wrap"></div></div>
        <div><h3 class="lh">مونت‌کارلو (۱۰۰۰ بازچینی معاملات)</h3>${mc ? `<table><tr><td class="muted">بازده — بدبینانه (۵٪)</td><td class="${signCls(mc.return_p5)}">${pct(mc.return_p5)}</td></tr><tr><td class="muted">بازده — میانه</td><td class="${signCls(mc.return_p50)}">${pct(mc.return_p50)}</td></tr>
          <tr><td class="muted">بازده — خوش‌بینانه (۹۵٪)</td><td class="${signCls(mc.return_p95)}">${pct(mc.return_p95)}</td></tr><tr><td class="muted">حداکثر افت — میانه / ۹۵٪</td><td class="neg">${pct(-mc.max_dd_p50)} / ${pct(-mc.max_dd_p95)}</td></tr>
          <tr><td class="muted">احتمال زیان</td><td>${pct(mc.loss_probability, 0).replace('+', '')}</td></tr></table>` : '<div class="faint" style="font-size:12px">کمتر از ۵ معامله؛ مونت‌کارلو معنادار نیست.</div>'}
          <h3 class="lh" style="margin-top:12px">داده و سیگنال‌های اجرا‌نشده</h3><div style="font-size:12px" class="muted">${Object.entries(res.coverage).map(([k, v]) => `${esc(k)}: ${n0(v.bars)} از ${n0(v.of)} کندل`).join(' · ')}<br>
          رد به‌دلیل ظرفیت: ${n0(res.skipped_signals.no_capacity)} · زیر حداقل سفارش: ${n0(res.skipped_signals.below_min_order)} · کندل بی‌معامله هنگام اجرا: ${n0(res.skipped_signals.no_trade_at_fill)}
          ${Object.keys(res.regime_bars || {}).length ? '<br>کندل‌های هر رژیم: ' + Object.entries(res.regime_bars).map(([k, v]) => esc(k) + ' ' + n0(v)).join('، ') : ''}${res.data_requests ? '<br>درخواست تازه به والکس: ' + n0(res.data_requests) : ''}</div></div></div>
      <div class="grid g3" style="margin-top:14px">${[['به تفکیک نماد', res.by_symbol, k => sym(k)], ['به تفکیک استراتژی', res.by_strategy, k => esc(sName(k))], ['به تفکیک دلیل خروج', res.by_exit, k => esc(EXIT(k))]].map(([t, g, f]) => `<div><h3 class="lh">${t}</h3><div class="table-wrap scroll" style="max-height:260px">${breakdown(g, f)}</div></div>`).join('')}</div>
      <h3 class="lh" style="margin-top:14px">معاملات${res.trades_truncated ? ' (۲۰۰۰ مورد آخر)' : ''}</h3><div class="table-wrap scroll" style="max-height:420px">${tradeTable(res.trades)}</div>
      <div class="faint" style="font-size:11.5px;margin-top:8px">${esc(res.method)}</div>`;
    lineChart($('#leq'), res.curve, s, b);
    ddChart($('#ldd'), res.curve);
    $('#lmon').innerHTML = monthly(res.monthly_pct);
    $('#lcsv').onclick = () => { const head = ['symbol', 'strategy', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'qty', 'cost_tmn', 'pnl_tmn', 'return_pct', 'r_multiple', 'mae_pct', 'mfe_pct', 'bars', 'tp_stage', 'exit_reason', 'quality', 'fees_tmn'];
      download('lab-trades.csv', [head.join(','), ...res.trades.map(t => head.map(k => k.endsWith('_time') ? new Date(t[k] * 1000).toISOString() : JSON.stringify(t[k] ?? '')).join(','))].join('\n'), 'text/csv'); };
    $('#lcsv2').onclick = () => download('lab-equity.csv', ['time,equity,drawdown_pct,benchmark', ...res.curve.t.map((t, i) => [new Date(t * 1000).toISOString(), res.curve.equity[i], res.curve.drawdown_pct[i], res.curve.benchmark ? res.curve.benchmark[i] : ''].join(','))].join('\n'), 'text/csv');
    $('#ljson').onclick = () => download('lab-result.json', JSON.stringify(res, null, 2));
  }
  let sName = k => k; let EXIT = k => k;
  function breakdown(g, f) {
    const rows = Object.entries(g || {});
    return rows.length ? `<table><thead><tr><th></th><th>معامله</th><th>برد</th><th>سود/زیان</th><th>میانگین</th></tr></thead><tbody>${rows.map(([k, v]) => `<tr><td>${f(k)}</td><td>${n0(v.trades)}</td><td>${pct(v.win_rate, 0).replace('+', '')}</td><td class="${signCls(v.pnl_tmn)}">${toman(v.pnl_tmn)}</td><td class="${signCls(v.avg_return_pct)}">${pct(v.avg_return_pct)}</td></tr>`).join('')}</tbody></table>` : '<div class="faint">—</div>';
  }
  function tradeTable(ts) {
    if (!ts.length) return '<div class="empty">در این بازه هیچ معامله‌ای انجام نشد؛ شرط ستاپ‌ها برقرار نشد یا فیلترها مانع شدند.</div>';
    return `<table><thead><tr><th>نماد</th><th>استراتژی</th><th>ورود</th><th>خروج</th><th>قیمت ورود → خروج</th><th>بازده</th><th>R</th><th>MAE / MFE</th><th>دلیل خروج</th></tr></thead><tbody>${ts.slice().reverse().map(t => `<tr><td>${sym(t.symbol)}</td><td style="font-size:11.5px">${esc(sName(t.strategy))}</td><td style="font-size:11.5px">${when(t.entry_time)}</td><td style="font-size:11.5px">${when(t.exit_time)}</td>
      <td class="mono" style="font-size:11.5px">${n2(t.entry_price)} → ${n2(t.exit_price)}</td><td class="${signCls(t.return_pct)}">${pct(t.return_pct)}</td><td>${n2(t.r_multiple)}</td><td style="font-size:11.5px">${pct(t.mae_pct, 1)} / ${pct(t.mfe_pct, 1)}</td><td style="font-size:11.5px">${esc(EXIT(t.exit_reason))}${t.tp_stage ? ' · TP' + t.tp_stage : ''}</td></tr>`).join('')}</tbody></table>`;
  }
  function monthly(m) {
    const keys = Object.keys(m || {}); if (!keys.length) return '<div class="faint">—</div>';
    const years = [...new Set(keys.map(k => k.slice(0, 4)))]; const max = Math.max(5, ...keys.map(k => Math.abs(m[k])));
    const cell = v => { if (v === undefined) return '<td></td>'; const a = Math.min(1, Math.abs(v) / max); const to = v >= 0 ? C.pos : C.neg; const c = C.mid.map((x, i) => Math.round(x + (to[i] - x) * a));
      return `<td style="background:rgb(${c.join(',')});text-align:center;font-size:11.5px;border:2px solid var(--panel-solid)" title="${pct(v)}">${pct(v, 1)}</td>`; };
    const sum = y => { const vs = keys.filter(k => k.startsWith(y)).map(k => m[k]); return (vs.reduce((a, v) => a * (1 + v / 100), 1) - 1) * 100; };
    return `<table><thead><tr><th>سال</th>${Array.from({ length: 12 }, (_, i) => `<th style="text-align:center">${i + 1}</th>`).join('')}<th>سال</th></tr></thead><tbody>${years.map(y => `<tr><td>${y}</td>${Array.from({ length: 12 }, (_, i) => cell(m[y + '-' + String(i + 1).padStart(2, '0')])).join('')}<td class="${signCls(sum(y))}" style="font-size:11.5px">${pct(sum(y), 1)}</td></tr>`).join('')}</tbody></table>
      <div class="faint" style="font-size:11px;margin-top:4px">ماه‌های میلادی (UTC). آبی = سود، قرمز = زیان؛ شدت رنگ با اندازهٔ بازده.</div>`;
  }

  safe(async () => {
    meta = await api('/api/studio/lab/meta');
    const names = Object.fromEntries(meta.strategies.map(s => [s.id, s.fa])); sName = k => names[k] || k; EXIT = k => meta.exit_reasons[k] || k;
    form(meta.defaults); loadRuns();
  }, $('#lform'));
  every(4000, loadRuns);
}

// ------------------------------------------------------------------ charts (inline SVG)
function scale(d0, d1, r0, r1) { return v => r0 + (v - d0) / ((d1 - d0) || 1) * (r1 - r0); }
function ticks(min, max, n = 4) { return Array.from({ length: n + 1 }, (_, i) => min + (max - min) * i / n); }
const short = v => Math.abs(v) >= 1e9 ? n2(v / 1e9) + 'B' : Math.abs(v) >= 1e6 ? n2(v / 1e6) + 'M' : n0(v);

function frame(el, t, series, opts) {
  const W = el.clientWidth || 800, H = el.clientHeight || 300, P = { l: 8, r: 70, t: 10, b: 22 };
  const all = series.flatMap(s => s.v); const min = opts.min ?? Math.min(...all), max = opts.max ?? Math.max(...all);
  const X = scale(t[0], t[t.length - 1], P.l, W - P.r), Y = scale(min, max, H - P.b, P.t);
  const grid = ticks(min, max).map(v => `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}"/><text x="${W - P.r + 6}" y="${Y(v) + 4}" fill="var(--faint)" font-size="11">${opts.fmt(v)}</text>`).join('');
  const xs = ticks(t[0], t[t.length - 1], Math.max(2, Math.floor((W - P.l - P.r) / 140)));
  const xt = xs.map((v, k) => `<text x="${X(v)}" y="${H - 6}" fill="var(--faint)" font-size="11" text-anchor="${k === 0 ? 'start' : k === xs.length - 1 ? 'end' : 'middle'}">${new Date(v * 1000).toISOString().slice(0, 10)}</text>`).join('');
  return { W, H, P, X, Y, svg: grid + xt };
}
function hover(el, t, f, rows) {
  const tip = el.querySelector('.ltip'), line = el.querySelector('.lx');
  el.onmousemove = e => {
    const r = el.getBoundingClientRect(); const x = e.clientX - r.left; let i = 0, best = 1e18;
    for (let k = 0; k < t.length; k++) { const d = Math.abs(f.X(t[k]) - x); if (d < best) { best = d; i = k; } }
    line.setAttribute('x1', f.X(t[i])); line.setAttribute('x2', f.X(t[i])); line.style.display = '';
    tip.style.display = ''; tip.innerHTML = `<div class="muted">${when(t[i])}</div>` + rows(i);
    tip.style.left = Math.min(r.width - 190, Math.max(0, x + 12)) + 'px'; tip.style.top = '8px';
  };
  el.onmouseleave = () => { tip.style.display = 'none'; line.style.display = 'none'; };
}
function lineChart(el, c, s, b) {
  const series = [{ v: c.equity, color: C.strat, name: 'استراتژی' }]; if (c.benchmark) series.push({ v: c.benchmark, color: C.bench, name: 'خرید و نگهداری' });
  const f = frame(el, c.t, series, { fmt: short }); const cap = c.equity[0];
  const path = s => s.v.map((v, i) => `${i ? 'L' : 'M'}${f.X(c.t[i]).toFixed(1)},${f.Y(v).toFixed(1)}`).join('');
  const end = s => { const v = s.v[s.v.length - 1]; return `<text x="${f.W - f.P.r - 4}" y="${f.Y(v) - 6}" fill="var(--text)" font-size="11" text-anchor="start" style="direction:rtl;unicode-bidi:plaintext">${s.name}: ${pct((v / cap - 1) * 100, 1)}</text>`; };
  el.innerHTML = `<svg width="${f.W}" height="${f.H}" style="direction:ltr">${f.svg}<line x1="${f.P.l}" x2="${f.W - f.P.r}" y1="${f.Y(cap)}" y2="${f.Y(cap)}" stroke="var(--line2)" stroke-dasharray="4 4"/>
    ${series.map(s => `<path d="${path(s)}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round"/>`).join('')}${series.map(end).join('')}
    <line class="lx" y1="${f.P.t}" y2="${f.H - f.P.b}" stroke="var(--muted)" style="display:none"/></svg><div class="ltip tooltip" style="display:none;position:absolute"></div>`;
  hover(el, c.t, f, i => series.map(x => `<div><i class="sw" style="background:${x.color}"></i> ${x.name}: <b>${toman(x.v[i])}</b> <span class="${signCls(x.v[i] - cap)}">${pct((x.v[i] / cap - 1) * 100)}</span></div>`).join(''));
}
function ddChart(el, c) {
  const f = frame(el, c.t, [{ v: c.drawdown_pct }], { fmt: v => (+v).toFixed(1) + '%', max: 0 });
  const pts = c.drawdown_pct.map((v, i) => `${f.X(c.t[i]).toFixed(1)},${f.Y(v).toFixed(1)}`).join(' L');
  el.innerHTML = `<svg width="${f.W}" height="${f.H}" style="direction:ltr">${f.svg}<path d="M${f.X(c.t[0])},${f.Y(0)} L${pts} L${f.X(c.t[c.t.length - 1])},${f.Y(0)} Z" fill="${C.dd}33" stroke="${C.dd}" stroke-width="1.5"/>
    <line class="lx" y1="${f.P.t}" y2="${f.H - f.P.b}" stroke="var(--muted)" style="display:none"/></svg><div class="ltip tooltip" style="display:none;position:absolute"></div>`;
  hover(el, c.t, f, i => `<div>افت از قله: <b class="neg">${n2(c.drawdown_pct[i])}٪</b></div>`);
}
