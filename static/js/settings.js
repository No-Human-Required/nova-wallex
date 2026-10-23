// Settings: API keys (Wallex + LLM providers) and LLM provider/model selection.
import { S, api, esc, $, $$, n2, ago } from './core.js';

const KEY_FA = { wallex: 'والکس (Wallex)', avalai: 'AvalAI', metisai: 'MetisAI', boxapi: 'BoxAPI' };

export function pageSettings(root, ctx) {
  if (!S.authenticated) { root.innerHTML = `<section class="panel" style="max-width:520px"><div class="body"><div class="notice">برای تغییر تنظیمات ابتدا در «کنترل اپراتور» وارد شوید.</div><p><a href="#operator">ورود اپراتور ←</a></p></div></section>`; return; }
  root.innerHTML = `<div id="setnote"></div>
  <section class="grid g2" style="margin-bottom:14px">
    <div class="panel glow"><div class="head"><h2>سرویس‌دهندهٔ هوش مصنوعی (LLM)</h2><span class="sub">مدل تصمیم‌گیر موتور و عامل استودیو</span></div><div class="body" id="llmbox"></div></div>
    <div class="panel"><div class="head"><h2>کلیدهای API</h2><span class="sub">رمزنگاری‌شده در گاوصندوق سرور؛ هرگز نمایش داده نمی‌شوند</span></div><div class="body" id="keybox"></div></div>
  </section>
  <section class="panel"><div class="head"><h2>ایمنی تغییرات در اجرای واقعی</h2></div><div class="body muted" style="font-size:12.5px">
    <div class="flow-steps">
      <div class="fs"><b>۱. ذخیره</b><span>کلید یا سرویس‌دهنده ذخیره می‌شود. کلیدی که اجرای فعلی به آن متصل است «در صف» می‌ماند و موتور با کلید قبلی ادامه می‌دهد.</span></div>
      <div class="fs"><b>۲. آزمون</b><span>دکمهٔ آزمون فقط درخواست خواندنی می‌فرستد: فهرست حساب‌های والکس یا یک پیام کوتاه به LLM. هیچ سفارشی ارسال نمی‌شود.</span></div>
      <div class="fs"><b>۳. ارتقای ممیزی‌شده</b><span>در «کنترل اپراتور»: توقف ← ارتقا. ارتقا همهٔ سفارش‌ها و کیف پول را با GET تطبیق می‌دهد، تغییرات را در رسید v7 ثبت و کلید در صف را جایگزین می‌کند.</span></div>
      <div class="fs"><b>۴. ادامه</b><span>«درخواست ادامه»؛ موتور با سرویس‌دهنده، مدل و کلید جدید کار می‌کند. دفتر و موقعیت‌ها دست نمی‌خورند.</span></div>
    </div></div></section>`;
  let D = null, M = { list: [] };
  async function models(refresh) {
    const provider = D.llm.provider, base = ($('#base') && $('#base').value.trim()) || D.llm.base_url;
    $('#mcount').textContent = '(در حال دریافت فهرست…)';
    const r = await ctx.safe(() => api(`/api/settings/models?provider=${encodeURIComponent(provider)}&base_url=${encodeURIComponent(base)}${refresh ? '&refresh=true' : ''}`));
    if (!r || D.llm.provider !== provider) return;
    M = { list: r.models, listed: r.listed.length };
    $('#mcount').innerHTML = r.listed.length ? `(${r.models.length} مدل از سرویس‌دهنده)` : `(${r.models.length} پیشنهاد${r.error ? ' · ' + esc(r.error) : ''})`;
  }
  function combo(input) {
    const box = document.createElement('div'); box.className = 'combo-list hidden'; input.after(box);
    let idx = -1;
    const items = () => { const q = input.value.trim().toLowerCase(); return M.list.filter(m => !q || m.toLowerCase().includes(q)).slice(0, 100); };
    const show = () => { const xs = items(); idx = -1;
      box.innerHTML = xs.length ? xs.map(m => `<div data-m="${esc(m)}">${esc(m)}</div>`).join('') : '<div class="faint">در فهرست نیست؛ همین نام دلخواه هم پذیرفته می‌شود</div>';
      box.classList.remove('hidden'); };
    input.addEventListener('focus', () => { const v = input.value; input.dataset.prev = v; show(); });
    input.addEventListener('input', show);
    input.addEventListener('keydown', e => { const rows = [...box.querySelectorAll('[data-m]')]; if (!rows.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); idx = (idx + (e.key === 'ArrowDown' ? 1 : -1) + rows.length) % rows.length; rows.forEach((r, i) => r.classList.toggle('on', i === idx)); rows[idx].scrollIntoView({ block: 'nearest' }); }
      else if (e.key === 'Enter' && idx >= 0) { e.preventDefault(); input.value = rows[idx].dataset.m; box.classList.add('hidden'); }
      else if (e.key === 'Escape') box.classList.add('hidden'); });
    input.addEventListener('blur', () => setTimeout(() => box.classList.add('hidden'), 150));
    box.addEventListener('mousedown', e => { const m = e.target.closest('[data-m]'); if (m) { input.value = m.dataset.m; box.classList.add('hidden'); e.preventDefault(); } });
  }
  async function load() {
    D = await ctx.safe(() => api('/api/settings'), $('#llmbox')); if (!D) return;
    render();
  }
  function render() {
    if (!D.saved) D.saved = { ...D.llm };
    const L = D.llm, P = D.providers, B = D.bound, SV = D.saved;
    $('#setnote').innerHTML = D.run_active && D.upgrade_needed ? `<div class="notice" style="margin-bottom:14px">تغییرات ذخیره‌شده هنوز روی اجرای واقعی اعمال نشده‌اند. برای اعمال: «کنترل اپراتور» ← توقف موتور ← ارتقا ← درخواست ادامه. <a href="#operator">رفتن به کنترل اپراتور ←</a></div>` : '';
    const presets = p => P[p].presets ? Object.entries(P[p].presets).map(([k, v]) => `<option value="${esc(v)}">${esc(k)}</option>`).join('') : `<option value="${esc(P[p].base_url)}">`;
    $('#llmbox').innerHTML = `
      <div class="prov">${Object.entries(P).map(([k, v]) => `<label class="pcard ${L.provider === k ? 'on' : ''}"><input type="radio" name="prov" value="${k}" ${L.provider === k ? 'checked' : ''}><b>${esc(v.fa)}</b><span class="mono faint">${esc(v.hosts.join(' · '))}</span>
        <span class="chip ${D.credentials[k].present ? 'ok' : 'bad'}">${D.credentials[k].present ? 'کلید ✓' : 'بدون کلید'}</span></label>`).join('')}</div>
      <div class="form" style="margin-top:12px">
        <label class="muted">آدرس پایهٔ API <span class="faint">(فقط روی ${esc(P[L.provider].hosts.join('، '))}؛ مسیر قابل ویرایش)</span></label><input id="base" class="mono" value="${esc(L.base_url || P[L.provider].base_url)}">
        ${P[L.provider].presets ? `<div class="presets">${Object.entries(P[L.provider].presets).map(([k, v]) => `<button class="chip ${v === (L.base_url || P[L.provider].base_url) ? 'y' : ''}" data-base="${esc(v)}">${esc(k)}</button>`).join('')}</div>` : ''}
        <label class="muted">مدل تصمیم‌گیری موتور <span class="faint" id="mcount"></span> <button class="chip" id="mref" title="دریافت دوباره از سرویس‌دهنده">↻</button></label><div class="combo"><input id="model" class="mono" autocomplete="off" value="${esc(L.model)}" placeholder="جست‌وجوی مدل…"></div>
        <label class="muted">مدل عامل استودیو (اختیاری؛ خالی = همان مدل)</label><div class="combo"><input id="smodel" class="mono" autocomplete="off" value="${esc(L.studio_model || '')}" placeholder="جست‌وجوی مدل…"></div>
        <div class="row" style="display:flex;gap:8px;flex-wrap:wrap"><button class="primary" id="savellm">ذخیرهٔ انتخاب</button><button id="testllm">آزمون اتصال LLM</button><span id="llmmsg" class="muted"></span></div>
      </div>
      <table style="margin-top:12px"><tr><td class="muted">انتخاب ذخیره‌شده</td><td>${esc(P[SV.provider].fa)} · <span class="mono">${esc(SV.model)}</span>${SV.saved ? '' : ' <span class="chip">پیش‌فرض</span>'}${SV.provider !== L.provider ? ' <span class="chip y">تغییر ذخیره نشده</span>' : ''}</td></tr>
      <tr><td class="muted">در حال استفادهٔ موتور</td><td>${B ? `${esc((P[B.provider] || {}).fa || B.provider)} · <span class="mono">${esc(B.model || '—')}</span> · اثر کلید <span class="mono">${esc(B.ai_fingerprint || '—')}</span>` : '<span class="faint">اجرای فعالی وجود ندارد</span>'}</td></tr></table>`;
    $$('input[name=prov]').forEach(r => r.onchange = () => { D.llm = { ...D.llm, provider: r.value, base_url: P[r.value].base_url, model: P[r.value].models[0] }; render(); });
    $$('#llmbox button[data-base]').forEach(b => b.onclick = () => { const pm = (P[L.provider].preset_models || {})[b.dataset.base]; D.llm = { ...D.llm, base_url: b.dataset.base, model: pm ? pm[0] : $('#model').value.trim(), studio_model: $('#smodel').value.trim() || null }; render(); });
    combo($('#model')); combo($('#smodel'));
    let timer = null; $('#base').oninput = () => { clearTimeout(timer); timer = setTimeout(() => models(false), 700); };
    $('#mref').onclick = e => { e.preventDefault(); models(true); };
    models(false);
    $('#savellm').onclick = async () => { try { D = await api('/api/settings/llm', { body: { provider: D.llm.provider, model: $('#model').value.trim(), base_url: $('#base').value.trim(), studio_model: $('#smodel').value.trim() || null } }); render(); $('#llmmsg').textContent = 'ذخیره شد'; } catch (e) { $('#llmmsg').textContent = e.message; } };
    $('#testllm').onclick = async () => { $('#llmmsg').textContent = 'در حال آزمون…'; try { const r = await api('/api/settings/test', { body: { target: 'llm', provider: D.llm.provider } }); $('#llmmsg').innerHTML = r.ok ? `<span class="pos">پاسخ دریافت شد</span> · ${esc(r.model)} · ${n2(r.latency_seconds)} ثانیه` : `<span class="neg">${esc(r.error)}</span>`; } catch (e) { $('#llmmsg').textContent = e.message; } };
    $('#keybox').innerHTML = Object.entries(D.credentials).map(([k, c]) => {
      const bound = B && (k === 'wallex' || k === B.provider);
      return `<div class="keyrow"><div><b>${esc(KEY_FA[k] || k)}</b> ${bound ? '<span class="chip y">متصل به اجرای واقعی</span>' : ''}
        <div class="faint" style="font-size:11.5px">${c.present ? `ثبت‌شده · اثر <span class="mono">${esc(c.fingerprint)}</span>` : 'ثبت نشده'}${c.staged ? ` · <span class="warn">کلید جدید در صف ارتقا (${esc(c.staged_fingerprint)})</span>` : ''}</div></div>
        <div class="row" style="display:flex;gap:6px;flex-wrap:wrap;align-items:center"><input type="password" autocomplete="off" data-k="${k}" placeholder="${bound ? 'کلید جدید (در صف ارتقا)' : 'کلید API'}" style="width:210px">
        <button data-save="${k}">ذخیره</button>${k === 'wallex' ? `<button data-testw="${c.staged ? 1 : 0}">آزمون خواندنی</button>` : ''}${c.staged ? `<button class="danger" data-discard="${k}">لغو صف</button>` : ''}</div>
        <div class="muted" id="km-${k}" style="font-size:12px"></div></div>`; }).join('') + `<div class="faint" style="font-size:11px;margin-top:8px">${D.vault_ready ? 'گاوصندوق سرور فعال است.' : '<span class="neg">کلید رمزنگاری سرور (SW_VAULT_KEY) تنظیم نشده است.</span>'}</div>`;
    $$('#keybox button[data-save]').forEach(b => b.onclick = async () => { const k = b.dataset.save; const v = $(`#keybox input[data-k=${k}]`).value.trim(); if (!v) return; try { D = await api('/api/settings/key', { body: { name: k, value: v } }); const st = D.saved && D.saved.staged; render(); $('#km-' + k).textContent = st ? 'ذخیره شد و تا ارتقای بعدی در صف می‌ماند.' : 'ذخیره شد.'; } catch (e) { $('#km-' + k).textContent = e.message; } });
    $$('#keybox button[data-discard]').forEach(b => b.onclick = async () => { try { D = await api('/api/settings/key/discard', { body: { name: b.dataset.discard } }); render(); } catch (e) { $('#km-' + b.dataset.discard).textContent = e.message; } });
    $$('#keybox button[data-testw]').forEach(b => b.onclick = async () => { const m = $('#km-wallex'); m.textContent = 'در حال آزمون…'; try { const r = await api('/api/settings/test', { body: { target: 'wallex', staged: b.dataset.testw === '1' } }); m.innerHTML = r.ok ? `<span class="pos">معتبر</span> · ${r.accounts} حساب (${r.eligible} فعال)${r.bound_account_visible === null ? '' : r.bound_account_visible ? ' · حساب مسابقه دیده می‌شود ✓' : ' · <span class="neg">حساب مسابقه با این کلید دیده نمی‌شود</span>'} · هیچ سفارشی ارسال نشد` : `<span class="neg">${esc(r.error)}</span>`; } catch (e) { m.textContent = e.message; } });
  }
  load();
}
