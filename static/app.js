'use strict';
const $ = id => document.getElementById(id);
const fa = new Intl.NumberFormat('fa-IR', {maximumFractionDigits:0});
const dec = new Intl.NumberFormat('fa-IR', {maximumFractionDigits:2});
const num = (x,d=0) => x===null || x===undefined || !Number.isFinite(Number(x)) ? '—' : (d ? dec : fa).format(Number(x));
const pct = x => x===null || x===undefined ? '—' : `${Number(x)>0?'+':''}${Number(x).toFixed(3)}%`;
const date = (t, full=false) => t ? new Intl.DateTimeFormat('fa-IR',{timeZone:'Asia/Tehran',month:'short',day:'numeric',...(full?{hour:'2-digit',minute:'2-digit'}:{})}).format(new Date(t*1000)) : '—';
const hour = t => new Intl.DateTimeFormat('fa-IR',{timeZone:'Asia/Tehran',hour:'2-digit',minute:'2-digit'}).format(new Date(t*1000));
const esc = x => String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sign = x => Number(x)>0 ? 'positive' : Number(x)<0 ? 'negative':'neutral';
const labels = {guarded_breakout:'V3 محافظت‌شده',guarded_breakout_ai:'V3 محافظت‌شده + AI',breakout48:'نسخه مرجع',breakout48_ai:'نسخه مرجع + AI',cash:'تومان نقد'};
const kinds = {order:'قصد سفارش',fill:'پرشدن شبیه‌سازی',order_cancel:'لغو شبیه‌سازی',allocation:'تخصیص سرمایه',risk:'کنترل ریسک',ai:'تصمیم AI',entry_gate:'فیلتر ورود',regime:'وضعیت کلی بازار',execution_deferred:'تعویق سفارش خرد'};
const reasons = {market_regime_risk_off:'شرایط بازار برای ورود مناسب نیست',portfolio_covariance_budget:'عبور از بودجه نوسان کل پرتفوی',cost_hurdle:'قدرت حرکت نسبت به هزینه کافی نیست',minimum_or_capacity:'کمتر از حداقل یا ظرفیت مجاز؛ موجودی حفظ شد',end_window_entry_cutoff:'نزدیک پایان پنجره؛ ورود جدید بسته است',entry_turnover_cap:'سقف گردش سرمایه مصرف شده',regime_or_window:'شرایط بازار یا زمان اجازه ورود نمی‌دهد',underlying_already_held:'این دارایی قبلاً در پرتفوی است',cooldown:'دوره انتظار پس از خروج',position_limit:'سقف تعداد دارایی',portfolio_halt:'توقف به علت ریسک',open_risk_budget:'سقف ریسک باز',missing_history:'تاریخچه کافی نیست',unknown_correlation:'همبستگی قابل محاسبه نیست',correlated_exposure:'همبستگی زیاد با دارایی موجود',route_minimum_including_fees:'بودجه کمتر از حداقل مسیر و کارمزد',missing_route_quote:'قیمت مسیر در دسترس نیست',trailing_stop:'خروج با توقف متحرک',trend_reversed:'برگشت روند',time_exit:'پایان زمان نگهداری',below_minimum_or_zero_capacity:'زیر حداقل سفارش یا بدون ظرفیت',entry_risk_or_data_changed:'تغییر ریسک یا داده هنگام اجرا',limit_not_crossed:'قیمت خارج از حد سفارش',signal:'سیگنال استراتژی',fund_usdt_route:'تأمین تتر برای مسیر دو مرحله‌ای',residual_fx_to_tmn:'بازگشت تتر باقی‌مانده به تومان'};
const statuses = {queued:'در صف',running:'در حال اجرا',paused:'متوقف',cancelled:'لغو شده',completed:'تکمیل شد',failed:'خطا'};
const state = {csrf:'',report:null,current:null,benchmark:null,markets:null,status:null,jobs:[],page:'overview',chart:'equity',market:'history',selectedJob:null,sequence:0,events:[]};
let toastTimer;
function toast(s){$('toast').textContent=s;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4500);}
function showError(s){$('error').textContent=s;$('error').hidden=!s;}
async function api(path,opts={}){
  const headers = {...(opts.body?{'Content-Type':'application/json','X-CSRF-Token':state.csrf}:{}),...(opts.headers||{})};
  const r = await fetch(path,{...opts,headers,credentials:'same-origin'});
  if(r.status===401){$('login').hidden=false;throw new Error('برای ادامه وارد شوید.');}
  const payload = await r.json();
  if(!r.ok) throw new Error(typeof payload.detail==='string'?payload.detail:`درخواست نامعتبر (${r.status})`);
  return payload;
}
function switchPage(page){
  if(page==='live'&&!state.csrf){$('login').hidden=false;$('password').focus();return;}
  state.page=page;
  $('overview-live').hidden=page!=='overview';
  document.querySelector('.context-bar').hidden=page==='live';
  document.dispatchEvent(new CustomEvent('sw:page',{detail:page}));
  document.querySelectorAll('.page').forEach(e=>e.hidden=e.id!==`page-${page}`);
  document.querySelectorAll('[data-page]').forEach(e=>e.classList.toggle('active',e.dataset.page===page));
  const title={live:'حساب و اجرای واقعی',overview:'مرکز کنترل معاملات',markets:'دیده‌بان بازار',agent:'اتاق عامل پژوهش',portfolio:'پرتفوی و مدیریت ریسک',activity:'دفتر تصمیم و اجرا',evaluation:'آزمایشگاه استراتژی',system:'سلامت و زیرساخت'}[page];
  $('page-title').textContent=title;$('crumb').textContent=title;
  $('page-description').textContent={live:'اتصال حساب اختصاصی، کنترل موتور و بازیابی پایدار سفارش‌ها.',overview:'از داده تا تصمیم؛ با حسابداری شفاف و کنترل ریسک.',markets:'پوشش همهٔ بازارهای مجاز در داده، با تفکیک تاریخچه و قیمت عمومی.',agent:'اجرای مستقل پژوهش، بازپخش AI و مدیریت کارهای پس‌زمینه.',portfolio:'بودجه‌های ریسک قطعی و ردیابی موجودی تا آخرین واحد.',activity:'هر تصمیم یک شاهد دارد؛ داده، دلیل، هزینه و نتیجه.',evaluation:'مقایسهٔ شفاف با خط مبنا، هزینه و شرایط تنش.',system:'پایداری سرویس، نسخهٔ کد و شواهد قابل بازپخش.'}[page];
  if(page==='markets') renderMarkets();
  if(page==='overview') renderChart();
}
function spark(values){
  if(!values.length)return '';
  const lo=Math.min(...values), hi=Math.max(...values), span=hi-lo||1;
  const points=values.map((v,i)=>`${i*70/Math.max(1,values.length-1)},${24-(v-lo)/span*22}`).join(' ');
  return `<svg class="spark" viewBox="0 0 70 26" aria-hidden="true"><polyline points="${points}" fill="none" stroke="#f5c343" stroke-width="1.3"/></svg>`;
}
function metric(label,value,unit,foot,cls='',chart=[]){return `<div class="metric"><div class="metric-top"><span>${label}</span><span class="metric-icon">◈</span></div><div class="metric-number ${cls}">${value} <small>${unit}</small></div><div class="metric-foot"><span>${foot}</span></div>${spark(chart)}</div>`;}
function currentSummary(){const c=state.current;if(!c)return {};const a=c.accounts.at(-1)||{};return c.summary||{final_nav_tmn:a.equity,cash_tmn:a.cash,fees_tmn:a.fees_tmn,fill_count:c.events.filter(e=>e.kind==='fill').length,capital_tmn:5000000,net_return_percent:a.equity?(Number(a.equity)/5000000-1)*100:0};}
function renderCurrent(){
  const c=state.current;if(!c)return;
  const s=currentSummary(), a=c.accounts.at(-1)||{}, risk=c.events.filter(e=>e.kind==='risk').at(-1)?.payload||{};
  const v=Number(s.final_nav_tmn||5000000), cash=Number(s.cash_tmn??5000000), r=s.economic_return_percent??s.liquidation_return_percent;
  $('metrics').innerHTML=metric('ارزش دفتری پرتفوی',num(v),'تومان',`نقد ${num(cash)} تومان`,'',c.accounts.map(a=>Number(a.equity)))+
    metric('بازده تخمینی تسویه پس از هزینه',r===undefined?'در حال اجرا':pct(r),'',s.estimated_ai_cost_tmn?`با هزینه AI: ${num(s.estimated_ai_cost_tmn)} تومان`:'شامل کارمزد و لغزش فرضی',sign(r))+
    metric('بیشترین افت سرمایه',pct(-(s.max_drawdown_percent??Number(risk.drawdown||0)*100)),'','سقف پژوهش: ۵٪','negative')+
    metric('هزینهٔ کارمزد ثبت‌شده',num(s.fees_tmn||0),'تومان',`${num(s.fill_count||0)} پرشدن شبیه‌سازی‌شده`);
  $('agent-status').textContent=c.summary?'بازپخش کامل شد':'بازپخش در حال پیشروی';
  $('agent-subtitle').textContent=c.summary?'همهٔ تصمیم‌ها و وضعیت حساب ثبت شده‌اند.':'ثبت وضعیت در مرز هر کندل انجام می‌شود.';
  const ais=c.events.filter(e=>e.kind==='ai'), gates=c.events.filter(e=>e.kind==='allocation');
  $('pipeline').innerHTML=[['دریافت و اعتبارسنجی داده',`${num(state.status?.pair_count||120)} جفت`],['اسکن و رتبه‌بندی',`${num(c.accounts.length)} ساعت`],['تصمیم AI',ais.length?`${num(ais.length)} تصمیم ثبت‌شده`:'این اجرا بدون AI'],['کنترل ریسک',`${num(gates.length)} ارزیابی تخصیص`],['حسابداری و گزارش',c.summary?'ثبت و تکمیل شده':'در حال ثبت']].map(([l,v])=>`<div class="pipeline-row"><span>${l}</span><b>${esc(v)}</b></div>`).join('');
  const start=c.identity?.config?.start||s.start, end=c.identity?.config?.end||s.end;
  $('case-period').textContent=`${date(start)} — ${date(end)}`;
  renderChart();renderAllocation();renderPortfolio();renderAI();renderEvents();renderRecent();renderProvenance();
}
function curve(c,kind){
  let peak=5000000;
  return (c?.accounts||[]).map(a=>{const nav=Number(a.equity);peak=Math.max(peak,nav);return {t:a.time,v:kind==='equity'?nav:kind==='drawdown'?(nav/peak-1)*100:Number(a.gross_fraction)*100};});
}
function renderChart(){
  $('benchmark-name').textContent=state.benchmarkName||'نسخه مرجع';
  const points=curve(state.current,state.chart), bench=curve(state.benchmark,state.chart);
  if(!points.length){$('equity-chart').innerHTML='<div class="empty">منحنی پس از ثبت اولین کندل نمایش داده می‌شود.</div>';return;}
  const all=[...points,...bench].map(x=>x.v);let lo=Math.min(...all),hi=Math.max(...all);
  const pad=(hi-lo)*.2||(state.chart==='equity'?5000:.5);lo-=pad;hi+=pad;
  const W=760,H=245,L=70,R=20,T=17,B=30,iw=W-L-R,ih=H-T-B;
  const start=points[0].t,end=points.at(-1).t;
  const x=t=>L+(t-start)/Math.max(3600,end-start)*iw,y=v=>T+(hi-v)/(hi-lo)*ih;
  const line=ps=>ps.map((p,i)=>`${i?'L':'M'}${x(p.t).toFixed(2)},${y(p.v).toFixed(2)}`).join(' ');
  const fill=`${line(points)} L${x(end)},${H-B} L${x(start)},${H-B} Z`;
  let grid='';for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,yy=y(v);grid+=`<line class="grid" x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}"/><text x="${L-10}" y="${yy+3}" text-anchor="end">${state.chart==='equity'?num(v/1000000,2)+'م':num(v,2)+'٪'}</text>`;}
  for(let i=0;i<4;i++){const t=start+(end-start)*i/3;grid+=`<text x="${x(t)}" y="${H-9}" text-anchor="${i===0?'start':i===3?'end':'middle'}">${date(t)} · ${hour(t)}</text>`;}
  $('equity-chart').innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="نمودار ${state.chart==='equity'?'ارزش':state.chart==='drawdown'?'افت':'درگیری'} پرتفوی با ${num(points.length)} مشاهده ساعتی"><defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f5c343" stop-opacity=".17"/><stop offset="1" stop-color="#f5c343" stop-opacity="0"/></linearGradient></defs>${grid}<path d="${fill}" fill="url(#area)"/><path class="benchmark" d="${line(bench)}"/><path class="main-line" d="${line(points)}"/><circle cx="${x(end)}" cy="${y(points.at(-1).v)}" r="4" fill="#f5c343"/><line id="crosshair" class="crosshair" y1="${T}" y2="${H-B}" visibility="hidden"/><rect x="${L}" y="${T}" width="${iw}" height="${ih}" fill="transparent" id="chart-hit"/></svg><div class="chart-tooltip" id="chart-tip" hidden></div>`;
  $('chart-unit').textContent=state.chart==='equity'?'میلیون تومان':'درصد';
  $('chart-range').textContent=`${date(start)} — ${date(end)}`;
  const hit=$('chart-hit'),tip=$('chart-tip');
  hit.addEventListener('pointermove',e=>{const svg=hit.ownerSVGElement,r=svg.getBoundingClientRect();const ratio=Math.max(0,Math.min(1,((e.clientX-r.left)/r.width*W-L)/iw));const p=points[Math.round(ratio*(points.length-1))];const ch=$('crosshair');ch.setAttribute('x1',x(p.t));ch.setAttribute('x2',x(p.t));ch.setAttribute('visibility','visible');tip.textContent=`${date(p.t,true)} · ${num(p.v,2)} ${state.chart==='equity'?'تومان':'درصد'}`;tip.hidden=false;tip.style.left=`${Math.max(5,Math.min(r.width-210,e.clientX-r.left-105))}px`;tip.style.top='0px';});
  hit.addEventListener('pointerleave',()=>{tip.hidden=true;$('crosshair').setAttribute('visibility','hidden');});
}
function renderAllocation(){
  const c=state.current,s=currentSummary(),a=c.accounts.at(-1)||{},marks=c.state?.marks||{};
  const parts=[{label:'تومان نقد',value:Number(s.cash_tmn||a.cash||5000000),color:'#f5c343'}];
  const colors=['#709fd0','#d9b879','#a497ce','#61afa6'];
  Object.entries(c.state?.positions||{}).forEach(([base,p],i)=>{const fx=p.symbol.endsWith('USDT')?Number(marks.USDTTMN?.price||0)*.9995:1;const value=Number(p.qty)*Number(marks[p.symbol]?.price||0)*.9995*fx;parts.push({label:base,value,color:colors[i%colors.length]});});
  const fx=Object.values(c.state?.fx_lots||{}).reduce((s,p)=>s+Number(p.qty),0)*Number(marks.USDTTMN?.price||0)*.9995;
  if(fx)parts.push({label:'تتر باقی‌مانده',value:fx,color:'#7c8c9e'});
  const total=parts.reduce((s,p)=>s+p.value,0)||1;let acc=0;
  const stops=parts.map(p=>{const from=acc;acc+=p.value/total*100;return `${p.color} ${from}% ${acc}%`;});
  $('allocation').innerHTML=`<div class="donut" style="background:conic-gradient(${stops.join(',')})"><div class="donut-label">${num(parts[0].value/total*100)}٪<small>نقدینگی</small></div></div><div class="allocation-list">${parts.map(p=>`<div class="allocation-row"><i class="dot" style="background:${p.color}"></i><span>${esc(p.label)}</span><strong>${num(p.value/total*100,2)}٪</strong></div>`).join('')}</div>`;
}
function eventText(e){const p=e.payload;return p.reason?reasons[p.reason]||p.reason:e.kind==='fill'?`${p.side==='BUY'?'خرید':'فروش'} ${esc(p.qty)} · کارمزد ${num(p.fee_tmn)} تومان`:e.kind==='ai'?p.record?.selection?.reason||p.record?.status:e.kind==='allocation'?(p.approved?'عبور از کنترل ریسک':'رد تخصیص'):e.kind==='regime'?(p.risk_on?'اجازه ورود با شرایط بازار':'حفظ نقدینگی در وضعیت نامناسب'):e.kind==='risk'?(p.halt?'توقف ریسک':p.daily_halt?'توقف روزانه':'در محدوده ریسک'):'ثبت شده';}
function eventList(events,n=6){return events.slice(-n).reverse().map(e=>`<div class="event-item"><span class="event-icon ${['execution_deferred','order_cancel','entry_gate'].includes(e.kind)?'warn':''}">${e.kind==='ai'?'✳':e.kind==='fill'?'↗':'◈'}</span><div class="event-item-content"><div><span>${esc(kinds[e.kind]||e.kind)} ${e.payload.symbol?`<span class="pair">${esc(e.payload.symbol)}</span>`:''}</span><span class="event-time">${date(e.time,true)}</span></div><p>${esc(String(eventText(e)).slice(0,150))}</p></div></div>`).join('')||'<div class="empty">رویدادی در این بخش ثبت نشده است.</div>';}
function renderRecent(){const events=state.current.events.filter(e=>!['risk','regime'].includes(e.kind));$('recent-events').innerHTML=eventList(events,4);}
function renderPortfolio(){
  const c=state.current,s=currentSummary(),a=c.accounts.at(-1)||{},st=c.state||{};
  const cfg=state.status?.risk_config||{};
  const gross=Number(a.gross_fraction||0)*100,dd=Number(s.max_drawdown_percent||0),count=Object.keys(st.positions||{}).length;
  const entries=[['درگیری کل سرمایه',gross,Number(cfg.max_gross_fraction||.4)*100,'%'],['تعداد دارایی مستقل',count,cfg.max_positions||4,''],['افت سرمایه',dd,Number(cfg.max_drawdown_fraction||.05)*100,'%']];
  $('risk-budgets').innerHTML=entries.map(([label,v,cap,unit])=>`<div class="risk-item"><div class="risk-label"><span>${label}</span><b>${num(v,2)}${unit} / ${num(cap)}${unit}</b></div><div class="progress"><i style="width:${Math.min(100,v/cap*100)}%;background:${v>=cap?'var(--red)':'var(--lime)'}"></i></div></div>`).join('')+`<div class="risk-item"><div class="risk-label"><span>سقف هر سفارش</span><b>${num(cfg.max_order_tmn||500000)} تومان</b></div></div><div class="risk-item"><div class="risk-label"><span>حد مشارکت در حجم کندل قبلی</span><b>${num(Number(cfg.participation||.005)*100,2)}٪</b></div></div>`;
  $('ledger').innerHTML=[['سرمایه آغازین',s.capital_tmn||5000000],['تومان نقد',s.cash_tmn||a.cash||5000000],['سود / زیان تحقق‌یافته',s.realized_pnl_tmn||st.realized||0],['سود / زیان تحقق‌نیافته',s.unrealized_pnl_tmn],['کارمزد معاملاتی',s.fees_tmn||st.fees||0],['ارزش تخمینی تسویه',s.estimated_liquidation_nav_tmn]].map(([l,v])=>`<div><span>${l}</span><b dir="ltr">${num(v,2)} <small>تومان</small></b></div>`).join('');
  const rows=Object.entries(st.positions||{}).map(([base,p])=>`<tr><td><span class="pair">${esc(p.symbol)}</span></td><td class="numeric">${esc(p.qty)}</td><td class="numeric">${num(p.cost,2)}</td><td class="numeric">${num(Number(p.stop)*100,2)}٪</td><td><span class="pill ${p.exit_reason?'warn':''}">${esc(p.exit_reason?reasons[p.exit_reason]||p.exit_reason:'موقعیت باز')}</span></td></tr>`);
  for(const p of Object.values(st.fx_lots||{}))rows.push(`<tr><td><span class="pair">USDT / TMN</span></td><td class="numeric">${esc(p.qty)}</td><td class="numeric">${num(p.cost,2)}</td><td>—</td><td><span class="pill warn">موجودی مسیر ${esc(p.base)}؛ شامل حساب</span></td></tr>`);
  $('positions').innerHTML=rows.join('')||'<tr><td colspan="5" class="empty">موجودی باز وجود ندارد؛ سرمایه به تومان نگهداری می‌شود.</td></tr>';
  $('risk-events').innerHTML=eventList(c.events.filter(e=>['entry_gate','execution_deferred'].includes(e.kind)||(e.kind==='allocation'&&!e.payload.approved)),10);
}
function renderAI(){
  const ais=state.current?.events.filter(e=>e.kind==='ai')||[], e=ais.filter(e=>e.payload.record?.selection?.reason).at(-1)||ais.at(-1);
  if(!e){$('ai-detail').innerHTML='<div class="empty">در این اجرا AI استفاده نشده است. برای مشاهدهٔ اثر واقعی AI، یک نسخهٔ «+ AI» را انتخاب کنید.</div>';return;}
  const p=e.payload,r=p.record||{},sel=r.selection||{};
  $('ai-detail').innerHTML=`<div class="ledger"><div><span>مدل / حالت</span><b>DeepSeek · بازپخش</b></div><div><span>تصمیم‌های ثبت‌شده</span><b>${num(ais.length)}</b></div><div><span>تغییر مجموعه یا ترتیب پیشنهادها</span><b>${num(ais.filter(x=>x.payload.changed_candidate_order_or_set).length)} بار</b></div><div><span>اطمینان گزارش‌شدهٔ مدل</span><b>${sel.confidence!==undefined?num(sel.confidence*100)+'٪':'—'} <small>کالیبره نشده</small></b></div></div><p class="tiny">آخرین پاسخ دارای دلیل · ${date(e.time,true)}</p><div class="ai-reason" dir="auto">${esc(sel.reason||r.reason||r.status)}</div><p class="tiny">پس از فیلتر AI (پیشنهاد، نه تأیید نهایی ریسک)</p><div class="ai-pairs">${(p.after||[]).map(s=>`<span class="pill">${esc(s)}</span>`).join('')||'<span class="muted">عدم ورود</span>'}</div><button class="text-button" id="ai-proof">مشاهدهٔ داده و پاسخ ثبت‌شده ←</button>`;
  $('ai-proof').onclick=()=>detail(e);
}
function detail(value){$('detail-json').textContent=JSON.stringify(value,null,2);$('detail-dialog').showModal();}
function renderEvents(){
  if(!state.current)return;
  const f=$('event-filter').value;
  const events=state.current.events.filter(e=>f==='all'?e.kind!=='risk':e.kind===f).slice().reverse();state.events=events;
  $('activity-table').innerHTML=events.slice(0,250).map((e,i)=>{const p=e.payload;const value=e.kind==='fill'?`${p.qty} · ${num(p.fee_tmn)} تومان`:p.budget_tmn?`${num(p.budget_tmn)} تومان`:p.qty||'—';return `<tr><td>${date(e.time,true)}</td><td>${esc(kinds[e.kind]||e.kind)}</td><td class="pair">${esc(p.symbol||p.candidate||'—')}</td><td title="${esc(eventText(e))}">${esc(String(eventText(e)).slice(0,76))}</td><td class="numeric">${esc(value)}</td><td><button class="text-button" data-proof="${i}">#${e.seq} ↗</button></td></tr>`;}).join('')||'<tr><td colspan="6" class="empty">رویدادی با این فیلتر وجود ندارد.</td></tr>';
  $('activity-count').textContent=`${num(events.length)} رویداد · حداکثر ۲۵۰ ردیف نمایش داده می‌شود؛ خروجی کار جدید شامل همهٔ رویدادهاست.`;
  document.querySelectorAll('[data-proof]').forEach(b=>b.onclick=()=>detail(state.events[Number(b.dataset.proof)]));
}
function renderMarkets(){
  if(!state.markets)return;
  const query=$('market-search').value.trim().toUpperCase(),q=$('quote-filter').value;
  let rows=state.markets.rows.filter(r=>(r.symbol.includes(query)||r.base.includes(query))&&(q==='all'||r.quote===q));
  const live=state.status?.public_monitor;
  $('monitor-toggle').textContent=live?.enabled?'توقف مانیتور عمومی':'شروع مانیتور عمومی';
  if(state.market==='public'){
    const bySymbol=Object.fromEntries((live?.rows||[]).map(r=>[r.symbol,r]));
    $('market-head').innerHTML='<tr><th>بازار</th><th>آخرین قیمت عمومی</th><th>تغییر ۲۴ ساعت</th><th>وضعیت دریافت</th></tr>';
    $('market-body').innerHTML=rows.map(r=>{const l=bySymbol[r.symbol];return `<tr><td><span class="pair">${esc(r.base)} / ${esc(r.quote)}</span></td><td class="numeric">${num(l?.last_price,2)} ${r.quote}</td><td class="numeric ${sign(l?.change_24h)}">${l?.change_24h!=null?pct(l.change_24h):'—'}</td><td><span class="pill ${!l||live.age_seconds>120?'warn':''}">${l?(live.age_seconds>120?'قدیمی':'دریافت عمومی'):'در انتظار داده'}</span></td></tr>`;}).join('');
    $('market-insight').textContent=`فقط دریافت قیمت عمومی؛ بدون معامله یا پرتفوی سایه. ${live?.received_at?'زمان دریافت در این سرور: '+date(live.received_at,true):'هنوز پاسخی دریافت نشده است.'} ${live?.error?'خطای اتصال: '+live.error:''} زمان دریافت، زمان صرافی نیست.`;
  }else{
    rows.sort((a,b)=>(b.score||-999)-(a.score||-999)||a.symbol.localeCompare(b.symbol));
    $('market-head').innerHTML='<tr><th>بازار</th><th>آخرین بسته‌شدن</th><th>بازده ۲۴ ساعت · تومان</th><th>گردش ۲۴ ساعت · تومان</th><th>نوسان ساعتی</th><th>وضعیت سیگنال مرجع</th></tr>';
    $('market-body').innerHTML=rows.map(r=>`<tr><td><span class="symbol"><span class="coin">${esc(r.base.slice(0,2))}</span><span class="pair">${esc(r.base)} / ${esc(r.quote)}</span></span></td><td class="numeric">${num(r.last_close,2)} <small>${r.quote}</small></td><td class="numeric ${sign(r.features?.r24_bps)}">${r.features?pct(r.features.r24_bps/100):'—'}</td><td class="numeric">${num(r.features?.daily_turnover_tmn)}</td><td class="numeric">${r.features?num(r.features.vol24_bps/100,2)+'٪':'—'}</td><td><span class="pill ${r.signal?'':r.features?'muted':'warn'}">${r.signal?'کاندیدای مرجع':r.features?'بدون سیگنال':'تاریخچه ناقص'}</span></td></tr>`).join('');
    const g=state.markets.regime;$('market-insight').textContent=`آخرین ساعت بستهٔ دیتاست: ${date(state.markets.asof,true)} · سهم دارایی‌های مثبت: ${num(g.positive_fraction*100)}٪ از ${num(g.underlyings)} دارایی نقدشونده · فیلتر V3: ${g.risk_on?'اجازهٔ ارزیابی ورود':'عدم ورود جدید'}. مجاز بودن حساب اختصاصی مسابقه جداگانه باید تأیید شود.`;
  }
  $('market-count').textContent=`${num(rows.length)} / ${num(state.markets.rows.length)} جفت`;
}
function renderEvaluation(){
  if(!state.report)return;
  const group=state.report.aggregates.filter(r=>r.split===$('eval-split').value&&r.scenario===$('eval-scenario').value);
  const scale=Math.max(.05,...group.map(r=>Math.abs(r.mean_economic_return_percent)));
  $('comparison-chart').innerHTML=group.map(r=>{const v=r.mean_economic_return_percent,w=Math.abs(v)/scale*48;return `<div class="compare-row"><span>${labels[r.variant]}</span><div class="compare-bar"><i class="${v>=0?'gain':''}" style="width:${w}%;left:${v>=0?50:50-w}%"></i></div><span class="compare-value ${sign(v)}">${pct(v)}</span></div>`;}).join('')||'<div class="empty">این ترکیب بخش و سناریو اجرا نشده است.</div>';
  $('eval-table').innerHTML=group.map(r=>`<tr><td>${labels[r.variant]}</td><td class="numeric ${sign(r.mean_economic_return_percent)}">${pct(r.mean_economic_return_percent)}</td><td class="numeric ${sign(r.worst_return_percent)}">${pct(r.worst_return_percent)}</td><td class="numeric">${Number(r.max_drawdown_percent).toFixed(3)}%</td><td class="numeric">${num(r.positive_windows)} / ${num(r.windows)}</td><td class="numeric">${num(r.orders)} / ${num(r.fills)}</td><td class="numeric">${num(r.mean_fees_tmn)} تومان</td></tr>`).join('');
  $('research-notes').innerHTML=`<article class="research-note"><h3>چه چیزی در V3 تغییر کرده؟</h3><p>عرض بازار و روند بیت‌کوین برای مجوز ورود؛ سقف ریسک نوسان کل پرتفوی؛ سقف گردش سرمایه؛ فاصلهٔ بیشتر ورودها و حفظ موجودی خرد بدون ارسال مکرر سفارش زیر حداقل. خروج‌های ریسک مستقل باقی می‌مانند.</p></article><article class="research-note"><h3>حدود این شواهد</h3><p>هزینهٔ هر مسیر و تأخیر هر مرحله مدل شده‌اند. دفتر سفارش تاریخی نداریم. بازده تسویه تخمینی است و قانون پایان مسابقه محسوب نمی‌شود. نسخهٔ جدید در تمام پنجره‌ها بهتر نیست؛ نتیجهٔ نقد و شرایط تنش را هم ببینید.</p></article>`;
}
function renderJobs(){
  $('jobs-count').textContent=`${num(state.jobs.length)} کار`;
  $('jobs-list').innerHTML=state.jobs.map(j=>`<div class="job"><span class="event-icon">${j.status==='completed'?'✓':'✳'}</span><div class="job-info"><div class="job-name">${labels[j.spec.variant]} · ${j.spec.start_utc?'بازهٔ دلخواه':'پنجره '+num(j.spec.window)} <span class="pill ${j.status==='failed'?'warn':'muted'}">${statuses[j.status]}</span></div><small>${date(j.created,true)} · ${num(j.progress)} / ${num(j.spec.duration_hours||72)} ساعت ${j.error?'· '+esc(j.error):''}</small><div class="progress"><i style="width:${j.progress/(j.spec.duration_hours||72)*100}%"></i></div></div><div class="job-actions"><button data-job-view="${j.id}">مشاهده</button>${['running','queued'].includes(j.status)?`<button data-job="${j.id}" data-action="pause">توقف</button>`:''}${j.status==='paused'?`<button data-job="${j.id}" data-action="resume">ادامه</button>`:''}${['running','queued','paused'].includes(j.status)?`<button class="danger" data-job="${j.id}" data-action="cancel">لغو</button>`:''}${j.progress?`<button data-export="${j.id}">خروجی JSON</button>`:''}</div></div>`).join('')||'<div class="empty">هنوز کار جدیدی ثبت نشده است. نتایج آرشیوی از انتخاب‌گر بالای صفحه در دسترس‌اند.</div>';
  document.querySelectorAll('[data-job]').forEach(b=>b.onclick=async()=>{try{await api(`/api/jobs/${b.dataset.job}/control`,{method:'POST',body:JSON.stringify({action:b.dataset.action})});toast('فرمان ثبت شد؛ وضعیت در مرز امن کندل اعمال می‌شود.');await refreshStatus();}catch(e){showError(e.message);}});
  document.querySelectorAll('[data-job-view]').forEach(b=>b.onclick=()=>selectJob(b.dataset.jobView));
  document.querySelectorAll('[data-export]').forEach(b=>b.onclick=()=>{window.location.href=`/api/export/${b.dataset.export}`;});
}
async function selectJob(id){
  const seq=++state.sequence;
  try{const j=await api(`/api/jobs/${id}`);const b=j.spec.start_utc?{accounts:(j.snapshot.accounts||[]).map(a=>({time:a.time,equity:5000000,cash:5000000,gross_fraction:0}))}:await api(`/api/cases/w${String(j.spec.window).padStart(2,'0')}-breakout48-base`);state.benchmarkName=j.spec.start_utc?'تومان نقد · همین بازه':'نسخه مرجع';if(seq!==state.sequence)return;state.selectedJob=id;state.current=j.snapshot;state.benchmark=b;$('window-select').value=String(j.spec.window);$('variant-select').value=j.spec.variant;$('source-tag').textContent=`کار جدید · ${statuses[j.status]} · ${j.spec.scenario==='base'?'پایه':'تنش'}`;renderCurrent();switchPage('overview');}catch(e){showError(e.message);}
}
async function selectCase(){
  const seq=++state.sequence;state.selectedJob=null;state.benchmarkName='نسخه مرجع';
  const window=Number($('window-select').value),v=$('variant-select').value;
  if(v.endsWith('_ai')&&window<31){$('variant-select').value=v.replace('_ai','');toast('برای این پنجره پاسخ AI ثبت نشده؛ نسخهٔ بدون AI نمایش داده می‌شود.');}
  const name=`w${String(window).padStart(2,'0')}-${$('variant-select').value}-base`;
  try{const [c,b]=await Promise.all([api(`/api/cases/${name}`),api(`/api/cases/w${String(window).padStart(2,'0')}-breakout48-base`)]);if(seq!==state.sequence)return;state.current=c;state.benchmark=b;$('source-tag').textContent='آرشیو قابل بازپخش';renderCurrent();showError('');}catch(e){showError(e.message);}
}
function renderProvenance(){
  if(!state.status)return;const s=state.status,c=state.current;
  $('provenance').innerHTML=`<label>اثر انگشت هستهٔ فعلی</label><span class="hash">${esc(s.source_sha256)}</span><label>هویت دیتاست</label><span class="hash">${esc(s.dataset_identity)}</span><label>سر زنجیرهٔ حسابرسی اجرای انتخاب‌شده</label><span class="hash">${esc(c?.summary?.audit?.chain_head||'اجرا هنوز نهایی نشده است')}</span><p class="muted">این بخش شواهد تاریخی پژوهش را نمایش می‌دهد. وضعیت و دفتر حساب واقعی در بخش اختصاصی اپراتور قرار دارند.</p>`;
}
function renderSystem(ops){
  const s=state.status;if(!s)return;
  $('health-cards').innerHTML=metric('عامل پژوهش',s.worker_alive?'فعال':'متوقف','',`ضربان ${num(s.worker_heartbeat_age)} ثانیه پیش`,s.worker_alive?'positive':'negative')+metric('زمان کارکرد',num(s.uptime_seconds/60),'دقیقه','مربوط به همین فرایند')+metric('ذخیره‌سازی',s.database_backend==='postgresql'?'PostgreSQL':'SQLite','',s.app_volume_required?'دیسک محلی':'دیتابیس مستقل؛ فضای برنامه موقت است')+metric('اجرای واقعی',s.live_orders_enabled?'فعال':'غیرفعال','',s.live_orders_enabled?'موتور الگوریتمی فعال است':'فعال‌سازی از حساب اپراتور');
  if(!state.csrf)$('operations').innerHTML='<p class="muted">گزارش عملیات مدیریتی در دسترسی اپراتور نمایش داده می‌شود.</p>';
  if(ops)$('operations').innerHTML=ops.slice(0,15).map(o=>`<div class="event-item"><span class="event-icon">⎈</span><div class="event-item-content"><div><span class="mono">${esc(o.action)}</span><span class="event-time">${date(o.at,true)}</span></div><p class="mono">${esc(JSON.stringify(o.detail))}</p></div></div>`).join('');
  renderProvenance();
}
let refreshing=false;
async function refreshStatus(){
  if(refreshing||(!state.csrf&&!state.publicReadonly))return;refreshing=true;
  try{
    const [status,jobs,ops]=await Promise.all([api('/api/status'),api('/api/jobs'),state.csrf?api('/api/operations'):Promise.resolve(null)]);
    state.status=status;state.jobs=jobs;configurePeriod();renderJobs();renderSystem(ops);document.dispatchEvent(new Event('sw:status'));if(state.page==='markets')renderMarkets();
    if(state.selectedJob){const id=state.selectedJob,j=await api(`/api/jobs/${id}`);if(state.selectedJob===id){state.current=j.snapshot;if(j.spec.start_utc)state.benchmark={accounts:(j.snapshot.accounts||[]).map(a=>({time:a.time,equity:5000000,cash:5000000,gross_fraction:0}))};$('source-tag').textContent=`کار جدید · ${statuses[j.status]} · ${j.spec.scenario==='base'?'پایه':'تنش'}`;renderCurrent();}}
    $('connection').classList.remove('off');$('connection').innerHTML='<i></i>اتصال به سرویس برقرار';$('last-sync').textContent=`آخرین همگام‌سازی ${hour(Date.now()/1000)}`;
  }catch(e){$('connection').classList.add('off');$('connection').innerHTML='<i></i>ارتباط قطع است';showError(e.message);}finally{refreshing=false;}
}
async function bootstrap(){
  try{
    const session=await api('/api/session');state.csrf=session.csrf;state.publicReadonly=session.public_readonly;$('login').hidden=true;$('environment').textContent=state.csrf?'دسترسی اپراتور':'نمای عمومی / فقط مشاهده';
    document.dispatchEvent(new Event('sw:session'));
    $('operator-name').textContent=state.csrf?'اپراتور سیستم':'بازدیدکننده';
    $('logout').title=state.csrf?'خروج':'ورود اپراتور';$('logout').setAttribute('aria-label',$('logout').title);
    $('login-dismiss').hidden=!state.publicReadonly;
    for(const id of ['submit-job','monitor-toggle']){$(id).disabled=!state.csrf;$(id).title=state.csrf?'':'نیازمند ورود اپراتور';}
    const [report,markets]=await Promise.all([api('/api/report'),api('/api/markets')]);state.report=report;state.markets=markets;
    const windows=[...new Set(report.cases.map(c=>c.window))].sort((a,b)=>b-a);
    const options=windows.map(w=>`<option value="${w}">پنجره ${num(w)} · ${date(report.cases.find(c=>c.window===w).start)}</option>`).join('');$('window-select').innerHTML=options;$('job-window').innerHTML=options;
    const v3ai=report.cases.some(c=>c.variant==='guarded_breakout_ai');if(!v3ai)$('variant-select').value='guarded_breakout';
    await refreshStatus();await selectCase();renderEvaluation();renderMarkets();
  }catch(e){if($('login').hidden)showError(e.message);}
}
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>switchPage(b.dataset.page));
document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>switchPage(b.dataset.go));
document.querySelectorAll('[data-chart]').forEach(b=>b.onclick=()=>{state.chart=b.dataset.chart;document.querySelectorAll('[data-chart]').forEach(x=>x.classList.toggle('selected',x===b));renderChart();});
document.querySelectorAll('[data-market]').forEach(b=>b.onclick=()=>{state.market=b.dataset.market;document.querySelectorAll('[data-market]').forEach(x=>x.classList.toggle('selected',x===b));renderMarkets();});
$('window-select').onchange=selectCase;$('variant-select').onchange=selectCase;
$('event-filter').onchange=renderEvents;$('market-search').oninput=renderMarkets;$('quote-filter').onchange=renderMarkets;
$('eval-split').onchange=renderEvaluation;$('eval-scenario').onchange=renderEvaluation;
$('new-job').onclick=()=>{switchPage('agent');$('job-variant').focus();};$('refresh').onclick=async()=>{await refreshStatus();toast('وضعیت سرویس به‌روزرسانی شد.');};
$('close-dialog').onclick=()=>$('detail-dialog').close();
$('login-form').onsubmit=async e=>{e.preventDefault();try{const response=await api('/api/login',{method:'POST',body:JSON.stringify({password:$('password').value})});state.csrf=response.csrf;$('password').value='';$('login-error').textContent='';await bootstrap();}catch(err){$('login-error').textContent=err.message;}};
$('logout').onclick=async()=>{if(!state.csrf){$('login').hidden=false;$('password').focus();return;}await api('/api/logout',{method:'POST',body:'{}'});state.csrf='';if(state.publicReadonly){switchPage('overview');await bootstrap();}else $('login').hidden=false;};
$('login-dismiss').onclick=()=>{$('login').hidden=true;$('password').value='';$('login-error').textContent='';};
$('job-form').onsubmit=async e=>{e.preventDefault();$('submit-job').disabled=true;showError('');try{const j=await api('/api/jobs',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(jobSpec())});toast('پژوهش در صف سرور ثبت شد. بستن مرورگر اجرا را متوقف نمی‌کند.');await refreshStatus();}catch(err){showError(err.message);}finally{$('submit-job').disabled=false;}};
$('monitor-toggle').onclick=async()=>{try{await api('/api/monitor',{method:'POST',body:JSON.stringify({enabled:!state.status?.public_monitor?.enabled})});state.market='public';document.querySelectorAll('[data-market]').forEach(b=>b.classList.toggle('selected',b.dataset.market==='public'));await refreshStatus();renderMarkets();toast('فقط مانیتور قیمت عمومی تغییر کرد.');}catch(e){showError(e.message);}};
setInterval(()=>{$('clock').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Tehran',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date())+'  THR';},1000);
setInterval(refreshStatus,5000);
bootstrap();


function configurePeriod(){
  const s=state.status;if(!s)return;
  const fmt=t=>new Date(t*1000+210*60000).toISOString().slice(0,16);
  const lo=s.dataset_start+73*3600,hi=s.dataset_end;
  for(const id of ['job-start','job-end']){$(id).min=fmt(lo);$(id).max=fmt(hi);}
  if(!$('job-start').value)$('job-start').value=fmt(Math.max(lo,hi-168*3600));
  if(!$('job-end').value)$('job-end').value=fmt(hi);
  $('job-dataset-range').textContent='دادهٔ قابل انتخاب: '+date(lo,true)+' تا '+date(hi,true)+' · زمان کندل‌ها در تهران دقیقهٔ ۳۰ است.';
}
function jobSpec(){
  const spec={variant:$('job-variant').value,window:Number($('job-window').value),scenario:$('job-scenario').value};
  if($('job-period-mode').value==='custom'){
    if(spec.variant.endsWith('_ai'))throw new Error('برای بازهٔ دلخواه یک سیاست بدون AI ثبت‌شده انتخاب کنید.');
    const start=new Date($('job-start').value+'+03:30'),end=new Date($('job-end').value+'+03:30');
    if(!Number.isFinite(start.getTime())||!Number.isFinite(end.getTime())||end<=start)throw new Error('شروع و پایان بازه معتبر نیست.');
    spec.start_utc=start.toISOString();spec.end_utc=end.toISOString();
  }
  return spec;
}
$('job-period-mode').onchange=()=>{
  const custom=$('job-period-mode').value==='custom';$('job-custom-range').hidden=!custom;$('job-window').disabled=custom;
  for(const o of $('job-variant').options)o.disabled=custom&&o.value.endsWith('_ai');
  if(custom)$('job-variant').value=$('job-variant').value.replace('_ai','');
};
