'use strict';

/* Live UI is separate from the historical report and never starts by itself. */
(() => {
  const root = document.getElementById('page-live');
  if (!root) return;
  const el = id => document.getElementById(id);
  const phrase = 'فعال‌سازی معاملات واقعی';
  const live = { data: null, preview: null, previewInput: '', busy: false, polling: false, request: 0, transportError: false };
  const label = {
    inactive: 'غیرفعال', stopped: 'متوقف', stopping: 'در حال توقف', running: 'در حال اجرا',
    active: 'فعال', starting: 'در حال شروع', reconciling: 'در حال تطبیق حساب',
    paused: 'متوقف موقت', blocked: 'متوقف به‌علت مانع', error: 'خطا', failed: 'خطای اجرا',
    reduce_only: 'فقط کاهش موقعیت', stopped_safely: 'متوقف', completed: 'پایان‌یافته',
    idle: 'آماده و غیرفعال', disabled: 'غیرفعال', stopped_by_operator: 'متوقف توسط اپراتور',
    policy_reviewed_stopped: 'سیاست جدید ثبت شد · منتظر ادامهٔ اپراتور',
    cash_tmn: 'تومان نقد', equity_tmn: 'ارزش حساب · تومان', realized_pnl_tmn: 'سود و زیان محقق‌شده · تومان',
    fees_tmn: 'کارمزد · تومان', net_return_pct: 'بازده خالص · درصد', drawdown_pct: 'افت سرمایه · درصد',
    max_drawdown_pct: 'سقف افت سرمایه · درصد', max_position_pct: 'سقف هر موقعیت · درصد',
    max_order_tmn: 'سقف هر سفارش · تومان', max_exposure_pct: 'سقف تخصیص سرمایه · درصد',
    capital_tmn: 'سرمایه مبنا · تومان', reserve_pct: 'ذخیره نقد · درصد', max_positions: 'سقف تعداد موقعیت',
    max_daily_loss_pct: 'حد زیان روزانه · درصد', min_order_tmn: 'حداقل سفارش · تومان',
    model: 'مدل هوش مصنوعی', strategy: 'استراتژی', run_id: 'شناسه اجرا', mode: 'حالت', status: 'وضعیت',
    start_utc: 'شروع · UTC', end_utc: 'پایان · UTC', timestamp: 'زمان ثبت', updated_at: 'آخرین به‌روزرسانی',
    observed_at: 'زمان مشاهده', heartbeat: 'ضربان موتور', account_label: 'نام حساب', quote: 'واحد حساب',
    at: 'زمان ثبت · تهران', phase: 'مرحله موتور', halt: 'دلیل توقف', chain_hash: 'اثر انگشت زنجیرهٔ ثبت',
    symbol: 'بازار', asset: 'دارایی', currency: 'ارز', amount: 'مقدار', quantity: 'مقدار', balance: 'موجودی',
    side: 'جهت', price: 'قیمت', order_id: 'شناسه سفارش', client_order_id: 'شناسه سفارش داخلی',
    filled_quantity: 'مقدار پرشده', remaining_quantity: 'مقدار باقی‌مانده', value_tmn: 'ارزش · تومان'
  };
  const asText = value => value === null || value === undefined ? '—' : String(value);
  const stateName = value => label[value] || asText(value);
  const knownTime = value => {
    if (value === null || value === undefined || value === '') return null;
    const t = typeof value === 'number' ? (value < 1e12 ? value * 1000 : value) : Date.parse(value);
    return Number.isFinite(t) ? t : null;
  };
  const tehranTime = value => {
    const t = knownTime(value);
    if (t === null) return '—';
    return new Intl.DateTimeFormat('fa-IR', { timeZone: 'Asia/Tehran', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(t));
  };
  function safeEvidence(value, depth = 0) {
    if (depth > 14) return '[nested data]';
    if (Array.isArray(value)) return value.map(item => safeEvidence(item, depth + 1));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, /password|secret|api[_-]?key|authorization|token|credential/i.test(key) ? '[REDACTED]' : safeEvidence(item, depth + 1)]));
    return value;
  }
  const json = value => JSON.stringify(safeEvidence(value), null, 2);
  function showError(message) {
    el('live-error').textContent = message || '';
    el('live-error').hidden = !message;
  }
  function reasonsOf(value) {
    const reasons = value?.blocking_reasons ?? value?.blockers;
    const translated = {
      'A successful read-only preflight less than five minutes old is required': 'بررسی حساب معتبر نیست یا بیش از پنج دقیقه گذشته است؛ «بررسی نهایی پیکربندی» را دوباره بزنید تا اتصال تازه بررسی شود.'
    };
    return Array.isArray(reasons) ? reasons.map(item => typeof item === 'string' ? translated[item] || item : json(item)) : [];
  }
  function renderReasons(id, reasons) {
    el(id).replaceChildren(...reasons.map(reason => {
      const li = document.createElement('li');
      li.className = 'blocked';
      li.textContent = '• ' + reason;
      return li;
    }));
  }
  function scalarText(key, value) {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'boolean') return value ? 'بله' : 'خیر';
    if (['at', 'updated_at', 'observed_at', 'heartbeat'].includes(key)) return tehranTime(value);
    if (typeof value === 'number') return num(value, Number.isInteger(value) ? 0 : 2);
    if (key === 'status' || key === 'mode') return stateName(value);
    return asText(value);
  }
  function snapshotItems(id, value, empty) {
    const box = el(id); box.replaceChildren();
    if (value === null || value === undefined) { const p = document.createElement('p'); p.className = 'muted'; p.textContent = 'ثبت نشده است.'; box.append(p); return; }
    const items = Array.isArray(value) ? value : typeof value === 'object' ? Object.entries(value).map(([asset, data]) => data && typeof data === 'object' ? { asset, ...data } : { asset, amount: data }) : [];
    if (!items.length) { const p = document.createElement('p'); p.className = 'muted'; p.textContent = empty; box.append(p); return; }
    const normalized = items.map(item => item && typeof item === 'object' ? safeEvidence(item) : { value: item });
    const keys = [...new Set(normalized.flatMap(item => Object.keys(item)))].filter(key => normalized.some(item => item[key] === null || typeof item[key] !== 'object')).slice(0, 8);
    const table = document.createElement('table'); const head = document.createElement('thead'); const header = document.createElement('tr');
    for (const key of keys) { const th = document.createElement('th'); th.textContent = label[key] || key; header.append(th); }
    head.append(header); const body = document.createElement('tbody');
    for (const item of normalized) { const tr = document.createElement('tr'); for (const key of keys) { const td = document.createElement('td'); td.textContent = typeof item[key] === 'object' && item[key] !== null ? 'در شاهد کامل' : scalarText(key, item[key]); tr.append(td); } body.append(tr); }
    table.append(head, body); const scroll = document.createElement('div'); scroll.className = 'table-scroll'; scroll.append(table); box.append(scroll);
  }
  function rows(id, value, empty) {
    const box = el(id);
    box.replaceChildren();
    if (!value || typeof value !== 'object') { const p = document.createElement('p'); p.className = 'muted'; p.textContent = empty; box.append(p); return; }
    const safe = safeEvidence(value);
    Object.entries(safe).filter(([, item]) => item === null || typeof item !== 'object').forEach(([key, item]) => {
      const row = document.createElement('div');
      const name = document.createElement('span'); name.textContent = label[key] || key;
      const val = document.createElement('b'); val.textContent = scalarText(key, item); val.dir = 'auto';
      row.append(name, val); box.append(row);
    });
    const nested = Object.entries(safe).filter(([, item]) => item && typeof item === 'object');
    if (nested.length) {
      const details = document.createElement('details');
      const summary = document.createElement('summary'); summary.textContent = 'جزئیات تنظیمات';
      const pre = document.createElement('pre'); pre.dir = 'ltr'; pre.textContent = JSON.stringify(Object.fromEntries(nested), null, 2);
      details.append(summary, pre); box.append(details);
    }
    if (!box.childElementCount) { const p = document.createElement('p'); p.className = 'muted'; p.textContent = empty; box.append(p); }
  }
  function configPayload() {
    const start = el('live-start').value;
    const end = el('live-end').value;
    const toUTC = value => value ? new Date(value + '+03:30').toISOString() : '';
    return {
      account_label: el('live-account-label').value.trim(), start_utc: toUTC(start), end_utc: toUTC(end),
      challenge_account_confirmed: el('live-confirm-account').checked,
      permitted_markets_confirmed: el('live-confirm-markets').checked,
      risk_limits_approved: el('live-confirm-risk').checked,
      settlement_confirmed: el('live-confirm-settlement').checked
    };
  }
  function validPreview() {
    const p = live.preview;
    if (!p?.preview_id || !Array.isArray(p.blocking_reasons) || p.blocking_reasons.length) return false;
    const expiry = knownTime(p.expires_at);
    if (expiry === null || expiry <= Date.now()) return false;
    try { return JSON.stringify(configPayload()) === live.previewInput; } catch { return false; }
  }
  function invalidatePreview() {
    live.preview = null; live.previewInput = '';
    el('live-activation-phrase').value = '';
    el('live-preview-result').hidden = true;
    el('live-preview-empty').hidden = false;
    syncButtons();
  }
  function syncButtons() {
    const signedIn = Boolean(state.csrf);
    const ready = signedIn && Boolean(live.data?.vault_ready) && !live.busy;
    const credentials = live.data?.credentials;
    el('live-save-keys').disabled = !ready;
    const selectedAccount = Boolean(credentials?.subaccount_client_id);
    el('live-check-account').disabled = !ready || !credentials?.wallex?.present || !selectedAccount || Boolean(live.data?.state?.run_id);
    el('live-load-accounts').disabled = !ready || !credentials?.wallex?.present;
    el('live-account-select').disabled = !ready || el('live-account-select').options.length < 2;
    el('live-save-account').disabled = !ready || !el('live-account-select').value;
    el('live-preview').disabled = !ready || !credentials?.wallex?.present || !credentials?.avalai?.present || !selectedAccount;
    el('live-refresh').disabled = !signedIn || live.busy;
    const permitted = ready && validPreview();
    el('live-activation-phrase').disabled = !permitted;
    el('live-activate').disabled = !permitted || el('live-activation-phrase').value.trim() !== phrase;
    for (const id of ['live-reduce-only', 'live-stop', 'live-resume']) el(id).disabled = !signedIn || live.busy || !live.data?.state?.run_id;
    el('live-entry-apply').disabled = !ready || !live.data?.entry_policy_review?.available || live.data?.state?.desired !== 'stopped' || !el('live-entry-accept').checked;
    if(live.data?.entry_policy_review?.available)el('live-resume').disabled=true;
    if (live.preview && !validPreview()) el('live-preview-expiry').textContent = 'این پیش‌نمایش معتبر نیست یا منقضی شده است؛ بررسی نهایی را دوباره انجام دهید.';
  }
  function render(data) {
    live.data = data;
    renderOverview(data);
    const engine = data.state || {};
    root.querySelector('.live-activation-panel').hidden = Boolean(engine.run_id);
    if(engine.run_id && state.page==='live') api('/api/live/evidence').then(ev=>{
      el('live-events-json').textContent=json(ev.events);
      const box=el('live-equity-chart'), pts=ev.equity;
      if(!pts.length){box.textContent='هنوز مشاهدهٔ حسابی ثبت نشده است.';return;}
      const valid=pts.filter(p=>p.equity!==null);
      if(!valid.length){box.textContent='ارزش حساب به‌علت نبود قیمت تازه قابل محاسبه نیست.';return;}
      const values=valid.map(p=>Number(p.equity)),lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1;
      const t0=pts[0].at,t1=pts.at(-1).at,dt=t1-t0||1;
      let path='',gap=true;
      for(const p of pts){if(p.equity===null){gap=true;continue;}path+=(gap?'M':'L')+(28+(p.at-t0)/dt*744)+','+(160-(Number(p.equity)-lo)/span*130);gap=false;}
      box.innerHTML='<svg viewBox="0 0 800 200" role="img" aria-label="ارزش حساب واقعی به تومان"><path d="'+path+'" fill="none" stroke="#f5c343" stroke-width="2"/><text x="25" y="190" fill="#a3a3a3" font-size="12">'+esc(num(lo))+' — '+esc(num(hi))+' TMN</text></svg>';
    }).catch(()=>{});
    el('live-engine-status').textContent = stateName(engine.status);
    el('live-engine-detail').textContent = data.release_ready===false ? 'پنل آمادهٔ دریافت کلید است؛ فعال‌سازی تا تکمیل آزمون نسخهٔ موتور بسته می‌ماند.' : engine.last_error ? 'پیام موتور: ' + engine.last_error : 'وضعیت از موتور واقعی همین سرور دریافت شده است؛ بستن پنل، فرمان توقف موتور نیست.';
    el('live-desired').textContent = stateName(engine.desired);
    el('live-heartbeat').textContent = tehranTime(engine.heartbeat);
    el('live-run-id').textContent = engine.run_id || 'اجرای واقعی ثبت نشده';
    el('live-synced').textContent = tehranTime(Date.now());
    el('live-vault-badge').textContent = data.vault_ready ? '◈ خزانهٔ رمزگذاری آماده است' : '◈ خزانهٔ رمزگذاری سرور آماده نیست';
    el('live-account-current').textContent = data.credentials?.subaccount_client_id ? 'شناسه: ' + data.credentials.subaccount_client_id : 'حساب اعتباری انتخاب نشده';
    for (const name of ['wallex', 'avalai']) {
      const credential = data.credentials?.[name];
      const fingerprint = credential?.fingerprint ? String(credential.fingerprint).slice(0, 20) : '';
      el(`live-${name}-state`).textContent = credential?.present ? 'کلید ثبت‌شده' + (fingerprint ? ` · اثرانگشت: ${fingerprint}` : '') : 'کلیدی ثبت نشده است.';
    }
    const preflight = data.preflight, reconciliation=data.last_snapshot;
    if(engine.run_id){
      const fresh=reconciliation?.balance_confirmed_at && Date.now()/1000-reconciliation.balance_confirmed_at<=90;
      el('live-preflight-status').textContent=fresh && !reconciliation.halt && !reconciliation.unresolved?.length ? 'دفتر حساب اخیراً تطبیق داده شد' : 'تطبیق حساب را از وضعیت موتور دنبال کنید';
      renderReasons('live-preflight-reasons',[]);
      el('live-preflight-json').textContent=json({balance_confirmed_at:reconciliation?.balance_confirmed_at,halt:reconciliation?.halt,unresolved:reconciliation?.unresolved,initial_activation_preflight:preflight});
    }else{
      el('live-preflight-status').textContent = !preflight ? 'هنوز بررسی نشده' : (reasonsOf(preflight).length || preflight.ok === false || preflight.ready === false) ? 'نیازمند بررسی' : preflight.ok === true ? 'بررسی حساب موفق' : 'بررسی ثبت شده';
      renderReasons('live-preflight-reasons', reasonsOf(preflight));
      el('live-preflight-json').textContent = preflight ? json(preflight) : 'هنوز شاهدی دریافت نشده است.';
    }
    const cfg=data.risk_config||{};
    const localInput=d=>new Date(d.getTime()+210*60000).toISOString().slice(0,16);
    if(!el('live-end').value && cfg.contest_end_utc)el('live-end').value=localInput(new Date(cfg.contest_end_utc));
    if(!el('live-start').value)el('live-start').value=localInput(new Date());
    rows('live-risk-config', {
      capital_tmn:cfg.capital_tmn, max_order_tmn:cfg.max_order_tmn, 'ورود نزدیک پایان': 'بر اساس فرصت خروج و نقدشوندگی', 'قطع ثابت ورود': 'ندارد',
      max_position_pct:cfg.max_asset_fraction==null?null:Number(cfg.max_asset_fraction)*100,
      max_exposure_pct:cfg.max_gross_fraction==null?null:Number(cfg.max_gross_fraction)*100,
      max_daily_loss_pct:cfg.max_daily_loss_fraction==null?null:Number(cfg.max_daily_loss_fraction)*100,
      max_drawdown_pct:cfg.max_drawdown_fraction==null?null:Number(cfg.max_drawdown_fraction)*100,
      max_positions:cfg.max_positions, model:cfg.ai_model_documented_backend,
      'فاصلهٔ بررسی ورود':cfg.entry_every_hours+' ساعت',
      'سیاست ورود':cfg.runtime_policy==='hourly_opportunity_ai'?'روند کوتاه‌مدت · آزمایشی':'شکست سقف ۴۸ ساعت',
      'تاریخچهٔ لازم برای سیگنال':data.history_policy ? data.history_policy.required_closed_hours+' کندل بستهٔ ساعتی' : '—',
      'کندل با حجم صفر':data.history_policy ? 'پذیرفته؛ کنترل نقدشوندگی برقرار است' : '—',
      'تنظیمات کامل برای بررسی':cfg
    }, 'تنظیمات ریسک هنوز دریافت نشده است.');
    const entryReview=data.entry_policy_review;
    el('live-entry-review').hidden=!(entryReview?.available || entryReview?.applied);
    el('live-entry-status').textContent=entryReview?.applied?'سیاست ساعتی ثبت شده است؛ وضعیت اجرای آن در بالای صفحه نمایش داده می‌شود.':'این سیاست هنوز اعمال نشده است. برای بررسی و ثبت، موتور باید متوقف باشد.';
    el('live-entry-accept').disabled=Boolean(entryReview?.applied);
    const globalStatus=el('global-live-status'), globalDetail=el('global-live-detail');
    if(globalStatus)globalStatus.textContent=stateName(engine.status);
    if(globalDetail)globalDetail.textContent=engine.run_id?'اجرای اختصاصی ثبت شده':'اجرای واقعی فعال نشده است';
    const snapshot = data.last_snapshot;
    const hasSnapshot = snapshot && typeof snapshot === 'object' && Object.keys(snapshot).length > 0;
    el('live-snapshot-empty').hidden = Boolean(hasSnapshot);
    el('live-snapshot-content').hidden = !hasSnapshot;
    if (hasSnapshot) {
      const summary = Object.fromEntries(Object.entries(snapshot).filter(([key]) => !['holdings', 'orders'].includes(key)));
      rows('live-snapshot-summary', summary, 'جزئیات در شاهد ثبت‌شده موجود است.');
      snapshotItems('live-holdings', snapshot.holdings, 'در این تصویر حساب، دارایی بازی ثبت نشده است.');
      snapshotItems('live-orders', snapshot.orders, 'در این تصویر حساب، سفارشی ثبت نشده است.');
      el('live-snapshot-json').textContent = json(snapshot);
    }
    syncButtons();
  }
  async function refresh({ notify = false } = {}) {
    if (!state.csrf) { renderOverview(null); return; }
    if (live.polling) return;
    live.polling = true;
    const request = ++live.request;
    try {
      const data = await api('/api/live/status');
      if (request !== live.request || !state.csrf) return;
      render(data);
      if (live.transportError) { showError(''); live.transportError = false; }
      if (notify) toast('وضعیت اجرای واقعی به‌روزرسانی شد.');
    } catch (error) { renderOverview(live.data, true); if (state.page === 'live') { live.transportError = true; showError('دریافت وضعیت واقعی ناموفق بود: ' + error.message); } }
    finally { live.polling = false; syncButtons(); }
  }
  async function action(work) {
    if (live.busy || !state.csrf) return;
    live.busy = true; live.transportError = false; showError(''); syncButtons();
    try { await work(); }
    catch (error) { showError(error.message || 'درخواست انجام نشد. وضعیت موتور را بررسی کنید.'); }
    finally { live.busy = false; syncButtons(); }
  }
  const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) });
  el('live-key-form').addEventListener('submit', event => {
    event.preventDefault();
    action(async () => {
      const keys = {};
      if (el('live-wallex-key').value.trim()) keys.wallex = el('live-wallex-key').value.trim();
      if (el('live-avalai-key').value.trim()) keys.avalai = el('live-avalai-key').value.trim();
      el('live-wallex-key').value = ''; el('live-avalai-key').value = '';
      if (!Object.keys(keys).length) throw new Error('حداقل یک کلید جدید وارد کنید.');
      invalidatePreview();
      el('live-account-select').replaceChildren(new Option('ابتدا فهرست حساب‌ها را دریافت کنید', ''));
      try { await post('/api/live/credentials', keys); }
      finally { delete keys.wallex; delete keys.avalai; }
      toast('کلیدها ذخیره شدند؛ اجرای واقعی هنوز با این عمل فعال نمی‌شود.');
      await refresh();
    });
  });
  el('live-load-accounts').addEventListener('click', () => action(async () => {
    const response = await api('/api/live/accounts');
    const accounts = Array.isArray(response) ? response : response.accounts;
    if (!Array.isArray(accounts)) throw new Error('فهرست حساب‌های دریافتی معتبر نیست.');
    const select = el('live-account-select');
    select.replaceChildren(new Option(accounts.length ? 'حساب اختصاصی چالش را انتخاب کنید' : 'حساب قابل انتخاب دریافت نشد', ''));
    for (const account of accounts) {
      if (account.client_id === null || account.client_id === undefined) continue;
      const clientId = String(account.client_id);
      const option = new Option((account.title || 'حساب اعتباری') + ' · ' + clientId + (account.eligible === true ? '' : ' · غیرمجاز'), clientId);
      option.disabled = account.eligible !== true;
      select.append(option);
    }
    if (live.data?.credentials?.subaccount_client_id) select.value = String(live.data.credentials.subaccount_client_id);
    if (!accounts.length) toast('حسابی برای انتخاب دریافت نشد.');
  }));
  el('live-account-select').addEventListener('change', () => { invalidatePreview(); syncButtons(); });
  el('live-save-account').addEventListener('click', () => action(async () => {
    const select = el('live-account-select');
    if (!select.value || select.selectedOptions[0]?.disabled) throw new Error('یک حساب فعال از فهرست رسمی انتخاب کنید.');
    invalidatePreview();
    await post('/api/live/account', { client_id: select.value });
    toast('حساب اعتباری ثبت شد. اکنون اتصال و موجودی را بررسی کنید.');
    await refresh();
  }));
  el('live-check-account').addEventListener('click', () => action(async () => {
    invalidatePreview();
    await post('/api/live/preflight', {});
    await refresh();
    toast('بررسی اتصال و حساب انجام شد. نتیجه را بررسی کنید.');
  }));
  el('live-config-form').addEventListener('submit', event => {
    event.preventDefault();
    action(async () => {
      invalidatePreview();
      if (!el('live-config-form').reportValidity()) return;
      const payload = configPayload();
      if (!payload.account_label) throw new Error('نام حساب اختصاصی چالش را وارد کنید.');
      if (!payload.start_utc || !payload.end_utc || Date.parse(payload.end_utc) <= Date.parse(payload.start_utc)) throw new Error('زمان شروع و پایان را به‌ترتیب و به وقت تهران وارد کنید.');
      if (Date.parse(payload.end_utc) <= Date.now()) throw new Error('پایان پنجرهٔ معامله باید در آینده باشد.');
      if (![payload.challenge_account_confirmed, payload.permitted_markets_confirmed, payload.risk_limits_approved, payload.settlement_confirmed].every(Boolean)) throw new Error('تأیید حساب، بازارها، حدود ریسک و تسویه برای بررسی نهایی لازم است.');
      toast('در حال بررسی تازهٔ اتصال و حساب؛ هیچ سفارشی ارسال نمی‌شود.');
      const preflight = await post('/api/live/preflight', {});
      await refresh();
      if (preflight.ok !== true || reasonsOf(preflight).length) {
        throw new Error(reasonsOf(preflight).join('؛ ') || 'بررسی تازهٔ حساب موفق نبود؛ فعال‌سازی بسته می‌ماند.');
      }
      const preview = await post('/api/live/preview', payload);
      live.preview = preview; live.previewInput = JSON.stringify(payload);
      el('live-preview-empty').hidden = true;
      el('live-preview-result').hidden = false;
      const blockers = reasonsOf(preview);
      el('live-preview-title').textContent = blockers.length ? 'فعال‌سازی مسدود است' : 'پیکربندی آمادهٔ تأیید نهایی است';
      el('live-preview-expiry').textContent = 'اعتبار این پیش‌نمایش تا ' + tehranTime(preview.expires_at) + ' به وقت تهران';
      renderReasons('live-preview-reasons', blockers);
      el('live-preview-binding').textContent = json({ binding: preview.binding, risk_config: preview.risk_config });
      syncButtons();
    });
  });
  for (const input of el('live-config-form').querySelectorAll('input')) {
    if (input.id === 'live-activation-phrase') input.addEventListener('input', syncButtons);
    else { input.addEventListener('input', invalidatePreview); input.addEventListener('change', invalidatePreview); }
  }
  el('live-activate').addEventListener('click', event => {
    event.preventDefault();
    if (!validPreview() || el('live-activation-phrase').value.trim() !== phrase) return;
    const previewId = live.preview.preview_id;
    action(async () => {
      invalidatePreview();
      await post('/api/live/activate', { preview_id: previewId, confirmation: phrase });
      toast('درخواست فعال‌سازی ثبت شد. وضعیت موتور را دنبال کنید.');
      await refresh();
    });
  });
  for (const [id, command] of [['live-reduce-only', 'reduce_only'], ['live-stop', 'stop'], ['live-resume', 'resume']]) {
    el(id).addEventListener('click', () => action(async () => {
      invalidatePreview();
      await post('/api/live/control', { action: command });
      toast('فرمان ثبت شد؛ نتیجهٔ اعمال آن در وضعیت موتور نمایش داده می‌شود.');
      await refresh();
    }));
  }
  el('live-refresh').addEventListener('click', () => refresh({ notify: true }));
  el('live-entry-accept').addEventListener('change',syncButtons);
  el('live-entry-apply').addEventListener('click',()=>action(async()=>{
    if(!el('live-entry-accept').checked)throw new Error('ابتدا نتیجهٔ ارزیابی و حدود را بررسی کنید.');
    await post('/api/live/entry-revision',{confirmation:'Apply reviewed hourly experimental policy; keep execution stopped',approval_reference:'authenticated_panel_hourly_policy_review'});
    toast('سیاست ثبت شد و موتور متوقف است. برای آغاز، «درخواست ادامه» را انتخاب کنید.');
    await refresh();
  }));
  function renderOverview(data, failed = false) {
    const authorized = Boolean(state.csrf);
    const engine = authorized ? data?.state : null;
    const snapshot = authorized && engine?.run_id ? data?.last_snapshot : null;
    const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
    const value = key => finite(snapshot?.[key]) ? Number(snapshot[key]) : null;
    const at = knownTime(snapshot?.at);
    const stale = failed || (at !== null && (Date.now() - at > 90000 || at > Date.now() + 15000));
    const pnl = value('realized_pnl_tmn'), ret = value('realized_return_percent');
    const equity = value('equity_tmn'), fills = value('fill_count');
    el('overview-live-status').textContent = stale ? 'آخرین داده · نیازمند به‌روزرسانی' : stateName(engine?.status || state.status?.live_state || 'idle');
    el('overview-live-updated').textContent = !authorized ? 'جزئیات حساب · دسترسی اپراتور' : at !== null ? 'آخرین مشاهده · ' + tehranTime(snapshot.at) : 'هنوز دادهٔ معاملاتی ثبت نشده';
    el('overview-live-note').textContent = !authorized
      ? 'وضعیت موتور عمومی است؛ اعداد حساب واقعی پس از ورود اپراتور نمایش داده می‌شوند.'
      : !engine?.run_id ? data?.credentials?.subaccount_client_id
        ? 'حساب اختصاصی انتخاب شده است؛ اجرای واقعی هنوز فعال نشده است.'
        : data?.credentials?.wallex?.present ? 'کلید ثبت شده است؛ حساب اختصاصی را انتخاب و بررسی کنید.'
        : 'اجرای واقعی هنوز شروع نشده است؛ در انتظار کلید حساب مسابقه و فعال‌سازی.'
      : !snapshot ? 'اجرا ثبت شده؛ در انتظار نخستین تصویر معتبر حساب.'
      : stale ? 'این اعداد آخرین تصویر ثبت‌شده‌اند؛ اتصال یا تازگی داده را بررسی کنید.'
      : 'منبع: دفتر اجرای واقعی؛ بازده محقق‌شده از ارزش روز دارایی‌های باز جداست.';
    el('overview-live-metrics').innerHTML =
      metric('بازده محقق‌شدهٔ واقعی', ret === null ? '—' : pct(ret), '', 'نتیجهٔ ثبت‌شده به تومان', ret === null ? '' : sign(ret)) +
      metric('سود و زیان محقق‌شده', num(pnl), 'تومان', 'فقط حساب اجرای واقعی', pnl === null ? '' : sign(pnl)) +
      metric('ارزش روز حساب واقعی', num(equity), 'تومان', equity === null ? 'ارزش‌گذاری در دسترس نیست' : 'شامل ارزش روز دارایی‌های باز') +
      metric('پرشدن سفارش واقعی', num(fills), '', fills === null ? 'دادهٔ معامله موجود نیست' : 'تعداد پرشدن‌های ثبت‌شده');
  }
  document.addEventListener('sw:session', () => { live.data = null; live.request++; renderOverview(null); if (state.csrf) refresh(); });
  document.addEventListener('sw:status', () => { if (!state.csrf) renderOverview(null); });
  el('logout').addEventListener('click', () => { if (state.csrf) { live.data = null; live.request++; renderOverview(null); } });
  document.addEventListener('sw:page', event => { if (event.detail === 'live') refresh(); });
  window.addEventListener('pagehide', () => { el('live-wallex-key').value = ''; el('live-avalai-key').value = ''; });
  setInterval(() => { syncButtons(); if (state.csrf && !live.busy) refresh(); }, 5000);
  syncButtons();
  renderOverview(null);
  if (state.csrf) refresh();
})();
