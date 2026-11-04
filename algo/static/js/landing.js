// Public landing page: product story, live market strip, interactive decision pipeline, leverage and exit-ladder explainers.
import { S, api, n0, n2, pct, toman, esc, $, $$ } from './core.js';
import { background, ART } from '/nova/js/fx.js';

const fa = v => new Intl.NumberFormat('fa-IR').format(v);
const PIPE = [
  ['data', 'داده و بازار', 'کندل‌های بستهٔ والکس در تایم‌فریم ربات؛ نمادهای بی‌معامله یا با تاریخچهٔ ناقص همین‌جا کنار می‌روند.'],
  ['setup', 'ستاپ استراتژی', 'شش استراتژی Smart Money و اندیکاتوری (و استراتژی‌های استودیوی خودتان) هر نماد را بررسی می‌کنند؛ فقط استراتژی‌های سازگار با رژیم بازار فعال‌اند.'],
  ['quality', 'امتیاز کیفیت', 'هر ستاپ از ۱۰۰ امتیاز می‌گیرد: نسبت سود به ریسک، هم‌پوشانی چند استراتژی، هم‌جهتی با روند، تأیید حجم و تناسب با رژیم.'],
  ['ai', 'تأیید هوش مصنوعی', 'مدل زبانی نامزدها را با هم مقایسه می‌کند و برای هر کدام «ورود یا رد»، اطمینان، ضریب اندازه و دلیل فارسی برمی‌گرداند. پاسخ ناقص هرگز مجوز ورود نیست.'],
  ['risk', 'اندازه‌گذاری ریسک', 'اندازهٔ هر ورود کوچک‌ترین مقدار بین بودجهٔ ریسک ÷ حد ضرر، سقف هر دارایی، سقف ناخالص و نقد آزاد است؛ هرگز با کل سرمایه وارد نمی‌شود.'],
  ['order', 'سفارش', 'سفارش لیمیت قابل‌اجرا با سقف قیمت؛ هر درخواست پیش از ارسال ثبت می‌شود و پاسخ نامعلوم فقط با خواندن صرافی روشن می‌شود، هرگز با ارسال دوباره.'],
  ['exit', 'مدیریت خروج', 'سه حد سود با فاصلهٔ برابر و حد ضرر پله‌ای، حد ضرر شناور، حداکثر زمان نگهداری و خروج با برگشت روند؛ هر ۳۰ ثانیه با قیمت زنده.']
];
const FAQ = [
  ['آیا برای استفاده باید برنامه‌نویسی بلد باشم؟', 'نه. نمادها، استراتژی‌ها و پروفایل ریسک را از فرم انتخاب می‌کنید. اگر استراتژی خودتان را می‌خواهید، در «استودیوی استراتژی» با هوش مصنوعی گفت‌وگو کنید تا آن را بسازد و بک‌تست بگیرد.'],
  ['پول من کجا نگه داشته می‌شود؟', 'همیشه در حساب صرافی خودتان. ربات فقط با کلید API و فقط با دسترسی معامله کار می‌کند؛ برداشت ممکن نیست. ربات هم فقط سرمایه‌ای را خرج می‌کند که به آن اختصاص داده‌اید.'],
  ['اجرای آزمایشی چیست؟', 'ربات روی قیمت‌های زندهٔ بازار و با همان قواعد کار می‌کند ولی بدون پول واقعی؛ تمام داشبورد، ژورنال و تصمیم‌ها مثل اجرای واقعی ثبت می‌شوند. اجرای آزمایشی در همهٔ پلن‌ها رایگان است.'],
  ['اجرای واقعی چطور فعال می‌شود؟', 'کلید API صرافی را اضافه می‌کنید (فقط‌خواندنی بررسی می‌شود)، حالت ربات را «واقعی» می‌کنید و درخواست می‌دهید. هر ربات واقعی پیش از اجرا توسط تیم بررسی و تأیید می‌شود و هر تغییر قواعد، تأیید را برمی‌دارد.'],
  ['معامله تعهدی (اهرمی) چقدر ریسک دارد؟', 'زیاد. با اهرم k هر ۱٪ حرکت قیمت k٪ وثیقه را جابه‌جا می‌کند. برای همین ربات هیچ ورودی را که حد ضررش نزدیک قیمت لیکویید باشد باز نمی‌کند و حد ضرر و حد سود را از همان لحظهٔ باز شدن روی خود صرافی ثبت می‌کند.'],
  ['نقش هوش مصنوعی دقیقاً چیست؟', 'هوش مصنوعی سیگنال نمی‌سازد؛ ستاپ‌هایی را که قواعد شفاف پیدا کرده‌اند بررسی، رتبه‌بندی و اندازه‌گذاری می‌کند و دلیلش را می‌نویسد. سقف‌های ریسک، حد ضرر و اندازهٔ سرمایه قطعی‌اند و مدل نمی‌تواند تغییرشان دهد.'],
  ['از کجا بفهمم ربات واقعاً خوب است؟', 'پیش از هر چیز بک‌تست بگیرید: هر تایم‌فریم و بازه، با شارپ، حداکثر افت، Profit Factor، مقایسه با خرید و نگهداری و مونت‌کارلو. «تست سایه» هم نشان می‌دهد ستاپ‌هایی که AI تأیید یا رد کرد بعداً چه شدند. نتیجهٔ گذشته تضمین آینده نیست.'],
  ['می‌توانم ربات را فقط برای یک بازهٔ زمانی اجرا کنم؟', 'بله. برای هر ربات تاریخ شروع و پایان تعیین کنید یا آن را نامحدود بگذارید. در پایان بازه، ربات به انتخاب شما همه چیز را می‌فروشد یا فقط خروج‌ها را مدیریت می‌کند.']
];

function console_() {
  return `<div class="ld-console" aria-hidden="true">
    <div class="ld-ch"><span class="ld-dots"><i></i><i></i><i></i></span><b>ربات روند SMC</b><span class="chip ok"><span class="dot on"></span> در حال اجرا</span></div>
    <div class="ld-cv"><div><div class="muted" style="font-size:11px">ارزش ربات</div><div class="ld-big" id="ldEq">۱۰٬۰۰۰٬۰۰۰</div></div><div class="ld-up" id="ldPnl">+۰٫۰٪</div></div>
    <svg viewBox="0 0 320 90" class="ld-spark"><defs><linearGradient id="ldg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#34d399" stop-opacity=".35"/><stop offset="1" stop-color="#34d399" stop-opacity="0"/></linearGradient></defs>
      <path class="ld-area" d="M0 70 L20 66 L40 69 L60 58 L80 61 L100 52 L120 55 L140 44 L160 47 L180 38 L200 42 L220 30 L240 33 L260 22 L280 26 L300 14 L320 10 L320 90 L0 90Z" fill="url(#ldg)"/>
      <path class="ld-line" d="M0 70 L20 66 L40 69 L60 58 L80 61 L100 52 L120 55 L140 44 L160 47 L180 38 L200 42 L220 30 L240 33 L260 22 L280 26 L300 14 L320 10" fill="none" stroke="#34d399" stroke-width="2.2"/>
      <circle cx="320" cy="10" r="4" fill="#34d399" class="ld-pulse"/></svg>
    <div class="ld-pos"><span class="mono">BTCTMN</span><span class="chip ok">لانگ</span><span class="ld-tp">TP1 ✓ · حد ضرر روی سربه‌سر</span><b class="pos">+۲٫۸٪</b></div>
    <div class="ld-pos"><span class="mono">ETHTMN</span><span class="chip bad">شورت ×۲</span><span class="ld-tp">حد ضرر روی صرافی ثبت است</span><b class="pos">+۱٫۴٪</b></div>
    <div class="ld-ai"><span class="chip smc">تصمیم AI</span><span id="ldType"></span><i class="ld-caret"></i></div>
  </div>`;
}

export function pageLanding() {
  const m = S.meta; const maxLev = (m.margin || {}).max_leverage || 5;
  const plans = m.plans || [];
  const popular = plans.length >= 3 ? plans[1].id : null;
  const sec = (id, kicker, title, sub, body) => `<section class="ld-sec ld-reveal" id="${id}"><div class="ld-kick">${kicker}</div><h2>${title}</h2>${sub ? `<p class="ld-sub">${sub}</p>` : ''}${body}</section>`;
  document.body.className = 'land-body';
  document.body.innerHTML = `<canvas id="fx" aria-hidden="true"></canvas><div class="ld">
  <header class="ld-nav"><a class="brand" href="#home"><img src="/assets/mark.svg" alt=""><div><b>${esc(m.site_name)}</b><small>ALGORITHMIC TRADING BOTS</small></div></a>
    <nav>${[['features', 'امکانات'], ['how', 'روند کار'], ['pipeline', 'تصمیم‌گیری'], ['margin', 'اهرمی'], ['security', 'امنیت'], ['plans', 'پلن‌ها'], ['faq', 'پرسش‌ها']].map(([k, t]) => `<button class="ld-link" data-go="${k}">${t}</button>`).join('')}</nav>
    <a href="#login"><button class="primary">ورود / ثبت‌نام</button></a></header>

  <section class="ld-hero">
    <div class="ld-hero-text ld-reveal">
      <span class="ld-eyebrow"><span class="dot on"></span> همان موتوری که در چالش معاملات الگوریتمی والکس زنده معامله کرد</span>
      <h1>ربات معامله‌گرِ <em>خودت</em> را بساز؛<br>با منطق شفاف، ریسک کنترل‌شده و هوش مصنوعی</h1>
      <p>استراتژی انتخاب کن یا با AI بساز، روی هر بازه بک‌تست بگیر، آزمایشی اجرا کن و وقتی مطمئن شدی روی حساب والکس خودت فعالش کن؛ اسپات یا تعهدی، لانگ یا شورت. تک‌تک تصمیم‌ها، از دادهٔ خام تا سفارش، جلوی چشم توست.</p>
      <div class="ld-cta"><a href="#login"><button class="primary ld-btn">شروع رایگان</button></a><button class="ld-btn ghost" data-go="pipeline">ببین چطور تصمیم می‌گیرد ↓</button></div>
      <div class="ld-trust"><span>✓ بدون کدنویسی</span><span>✓ اجرای آزمایشی رایگان</span><span>✓ دارایی همیشه در حساب خودت</span></div>
    </div>
    <div class="ld-reveal ld-hero-art">${console_()}</div>
  </section>

  <div class="ld-ticker" id="ldTicker" hidden><div class="ld-track" id="ldTrack"></div></div>

  <section class="ld-stats ld-reveal">${[[fa(m.strategies.length), 'استراتژی آماده', 'Smart Money و اندیکاتوری'], [fa((m.lab_timeframes || []).length || 10), 'تایم‌فریم بک‌تست', 'از ۱ دقیقه تا ۱ روز'],
    ['۳', 'حد سود پله‌ای', 'با حد ضرر بالارونده'], ['×' + fa(maxLev), 'اهرم لانگ و شورت', 'معامله تعهدی والکس'], ['۳۰ث', 'چرخهٔ کنترل', 'حد ضرر و سود با قیمت زنده']]
    .map(([a, b, c]) => `<div><b>${a}</b><span>${b}</span><i>${c}</i></div>`).join('')}</section>

  ${sec('how', 'روند کار', 'از ایده تا اجرای واقعی، در چهار قدم', 'هیچ رباتی بدون آزمون به پول واقعی نمی‌رسد؛ هر قدم ابزار سنجش خودش را دارد.',
    `<div class="ld-steps">${[['بساز', 'نمادها، استراتژی‌ها، تایم‌فریم و پروفایل ریسک را انتخاب کن؛ یا استراتژی خودت را در استودیو با AI طراحی کن.', '✎'],
      ['بسنج', 'بک‌تست روی هر بازه و تایم‌فریم: منحنی سرمایه در برابر خرید و نگهداری، افت، شارپ، سورتینو، Profit Factor و مونت‌کارلو.', '∿'],
      ['آزمایشی اجرا کن', 'ربات روی قیمت‌های زنده و بدون پول واقعی کار می‌کند؛ داشبورد، ژورنال و تصمیم‌های AI مثل اجرای واقعی.', '◉'],
      ['واقعی کن', 'کلید API والکس را اضافه کن و درخواست بده؛ پس از بررسی و تأیید، ربات روی حساب خودت معامله می‌کند.', '⚡']]
      .map(([t, d, i], k) => `<div class="ld-step"><span class="ld-num">${fa(k + 1)}</span><span class="ld-ico">${i}</span><b>${t}</b><p>${d}</p></div>`).join('')}</div>`)}

  ${sec('pipeline', 'شفافیت کامل', 'هر تصمیم، مرحله به مرحله', 'روی هر مرحله بزن تا ببینی ربات آنجا دقیقاً چه می‌کند. همین جریان را در پنل برای ربات خودت، کندل به کندل، با پخش تاریخچه می‌بینی.',
    `<div class="ld-pipe" id="ldPipe">${PIPE.map(([k, t], i) => `${i ? '<span class="ld-edge"><i></i></span>' : ''}<button class="ld-node ${k === 'ai' ? 'ai' : ''}" data-k="${k}"><small>${fa(i + 1)}</small>${t}</button>`).join('')}</div>
     <div class="ld-pipe-info panel" id="ldPipeInfo"></div>`)}

  ${sec('features', 'امکانات', 'همهٔ ابزارهای یک میز معاملهٔ حرفه‌ای', 'آنچه یک تیم معاملاتی برای ساخت، سنجش و پایش استراتژی لازم دارد، در یک پنل.',
    `<div class="ld-bento">
      <div class="panel ld-tile wide"><span class="chip y">داشبورد زنده</span><h3>هر ربات، داشبورد کامل خودش</h3><p>منحنی ارزش با نقاط خرید و فروش، رادار اسکنر و رژیم بازار، نمودار دقیقه‌ای هر موقعیت با خط ورود، حد ضرر فعال و سه حد سود، آخرین تصمیم AI و رویدادهای زنده.</p>
        <svg viewBox="0 0 400 110" class="ld-mini"><path d="M0 80 C40 70 60 90 100 72 S160 40 200 55 S270 20 310 34 S370 12 400 18" fill="none" stroke="#f5c343" stroke-width="2"/>
        <line x1="0" x2="400" y1="62" y2="62" stroke="#f5c343" stroke-dasharray="4 5" opacity=".6"/><line x1="0" x2="400" y1="92" y2="92" stroke="#fb7185" stroke-dasharray="4 5" opacity=".7"/>
        <line x1="0" x2="400" y1="30" y2="30" stroke="#34d399" stroke-dasharray="4 5" opacity=".7"/><line x1="0" x2="400" y1="12" y2="12" stroke="#34d399" stroke-dasharray="4 5" opacity=".5"/>
        <text x="6" y="58" fill="#f5c343" font-size="10">ورود</text><text x="6" y="104" fill="#fb7185" font-size="10">حد ضرر</text><text x="6" y="26" fill="#34d399" font-size="10">TP1</text></svg></div>
      <div class="panel ld-tile"><span class="chip smc">استودیوی استراتژی</span><h3>استراتژی‌ات را با AI بساز</h3>
        <div class="ld-chat"><div class="me">یک استراتژی پولبک به EMA21 در روند صعودی بساز</div><div class="bot">پیش‌نویس ساختم و روی ۶ هفته بک‌تست گرفتم: ۴۱ معامله، نرخ برد ۵۴٪. حد ضرر را به ۲٫۲ATR ببرم؟</div></div></div>
      <div class="panel ld-tile"><span class="chip ind">آزمایشگاه بک‌تست</span><h3>بک‌تست در سطح حرفه‌ای</h3><p>هر تایم‌فریم و بازه، تک‌ارزی یا پرتفوی، با کارمزد، اسپرد، لغزش و تأخیر اجرا.</p>
        <div class="ld-chips">${['شارپ', 'سورتینو', 'کالمار', 'حداکثر افت', 'Profit Factor', 'SQN', 'مونت‌کارلو', 'بازده ماهانه'].map(x => `<span class="chip">${x}</span>`).join('')}</div></div>
      <div class="panel ld-tile"><span class="chip">تست سایه</span><h3>اثر واقعی هوش مصنوعی را بسنج</h3><p>هر ستاپی که ربات دید، چه AI تأیید کرد چه رد، بدون سفارش دنبال می‌شود تا ببینی فیلتر AI واقعاً سود می‌سازد یا نه.</p></div>
      <div class="panel ld-tile"><span class="chip">ژورنال شفاف</span><h3>دلیل تک‌تک معاملات</h3><p>هر سفارش با استراتژی، دلیل ورود، تصمیم AI و قاعدهٔ خروج ثبت می‌شود؛ خروجی CSV و JSON.</p></div>
      <div class="panel ld-tile"><span class="chip">زمان‌بندی</span><h3>از کِی تا کِی؟ تو تعیین می‌کنی</h3><p>شروع خودکار در زمان دلخواه، پایان مشخص یا نامحدود، و انتخاب رفتار ربات در پایان بازه.</p></div>
    </div>`)}

  ${sec('ladder', 'مدیریت خروج', 'سود را نگه می‌دارد، ضرر را کوچک', 'کل موقعیت تا رسیدن به هدف نگه داشته می‌شود و با رسیدن به هر حد سود، حد ضرر یک پله بالا می‌آید.',
    `<div class="ld-split"><svg viewBox="0 0 520 260" class="ld-ladder" aria-hidden="true">
       ${[['TP3 · خروج کامل', 40, '#34d399'], ['TP2', 88, '#34d399'], ['TP1', 136, '#34d399'], ['ورود', 184, '#98a0ab']].map(([t, y, c]) => `<line x1="40" x2="500" y1="${y}" y2="${y}" stroke="${c}" stroke-dasharray="5 5" opacity=".7"/><text x="504" y="${y + 4}" fill="${c}" font-size="11" text-anchor="end" dx="-6" dy="-6">${t}</text>`).join('')}
       <path class="ld-ladder-path" d="M40 200 L90 190 L130 170 L170 150 L200 132 L240 140 L280 110 L320 92 L350 100 L390 70 L430 52 L470 42 L500 38" fill="none" stroke="#f5c343" stroke-width="2.5"/>
       <path class="ld-stop" d="M40 222 L200 222 L200 184 L320 184 L320 136 L500 136" fill="none" stroke="#fb7185" stroke-width="2"/>
       <text x="44" y="240" fill="#fb7185" font-size="11">حد ضرر پله‌ای</text></svg>
     <ul class="ld-list"><li><b>TP1</b> همان هدف ساختاری استراتژی است (هرگز کمتر از 1R و دو برابر هزینهٔ معامله).</li><li><b>TP2 و TP3</b> با همان فاصله بالاتر قرار می‌گیرند؛ TP3 خروج کامل است.</li>
       <li>پس از <b>+1R یا TP1</b> حد ضرر به سربه‌سر می‌رود و پس از <b>TP2</b> روی TP1.</li><li><b>حد ضرر شناور</b>، حداکثر زمان نگهداری و خروج با برگشت روند هم برقرارند.</li></ul></div>`)}

  ${sec('margin', 'معامله تعهدی والکس', 'لانگ و شورت با اهرم؛ با ترمز ایمنی', 'در بازار نزولی هم فرصت هست. ربات همان استراتژی‌ها را روی قیمت معکوس اجرا می‌کند تا ستاپ‌های فروش (شورت) را پیدا کند.',
    `<div class="ld-split"><div class="panel ld-lev"><div class="ld-lev-head"><b>ماشین‌حساب اهرم</b><span class="chip y" id="ldLevV">×۲</span></div>
       <input type="range" id="ldLev" min="1" max="${maxLev}" step="1" value="2" aria-label="اهرم">
       <div class="ld-lev-grid"><div><span>۱٪ حرکت قیمت</span><b id="ldLevMove">۲٪ وثیقه</b></div><div><span>فاصلهٔ تقریبی تا لیکویید</span><b class="neg" id="ldLevLiq">۴۵٪</b></div><div><span>بیشترین حد ضرر مجاز ربات</span><b class="warn" id="ldLevStop">۳۶٪</b></div></div>
       <div class="faint" style="font-size:11.5px">با فرض حاشیهٔ لیکویید ۱۰٪؛ مقدار واقعی هر بازار را ربات از پیش‌نمایش والکس می‌گیرد.</div></div>
     <ul class="ld-list"><li>هیچ ورودی که <b>حد ضررش نزدیک قیمت لیکویید</b> باشد باز نمی‌شود.</li><li><b>حد ضرر و حد سود روی خود صرافی</b> ثبت می‌شوند؛ اگر سرور هم قطع شود محافظت برقرار است.</li>
       <li>با رسیدن به هر TP، <b>حد ضرر روی صرافی هم بالا می‌آید</b>.</li><li>سقف اهرم را مدیریت پلتفرم تعیین می‌کند و معاملات تعهدی واقعی کلید توقف جداگانه دارد.</li></ul></div>`)}

  ${sec('strategies', 'استراتژی‌ها', 'شش استراتژی آماده، با قواعد روشن', 'هر استراتژی فقط در رژیم بازار مناسبش فعال است؛ ستاپ‌ها امتیاز کیفیت می‌گیرند و بهترین‌ها به مرحلهٔ بعد می‌روند.',
    `<div class="grid g2">${m.strategies.map(s => `<div class="panel strategy">${ART[s.id] || ''}<div><h3>${esc(s.fa)} <span class="chip ${s.family === 'smart_money' ? 'smc' : 'ind'}">${s.family === 'smart_money' ? 'SMC' : 'اندیکاتور'}</span></h3><div class="muted" style="font-size:12.5px">${esc(s.thesis)}</div></div></div>`).join('')}</div>`)}

  ${sec('security', 'امنیت و کنترل', 'سرمایه‌ات زیر کنترل خودت', '',
    `<div class="ld-sec-grid">${[['⚿', 'کلید رمزنگاری‌شده', 'کلید API رمزنگاری‌شده ذخیره می‌شود و فقط موتور اجرا آن را باز می‌کند؛ پس از ذخیره دیگر نمایش داده نمی‌شود.'],
      ['⛔', 'بدون دسترسی برداشت', 'ربات فقط سفارش معاملاتی ثبت می‌کند؛ هیچ مسیر برداشتی در سیستم وجود ندارد.'], ['✓', 'تأیید پیش از اجرای واقعی', 'هر ربات واقعی پیش از شروع بررسی می‌شود و هر تغییر قواعدش، تأیید را برمی‌دارد.'],
      ['⟲', 'بدون سفارش تکراری', 'هر درخواست پیش از ارسال ثبت می‌شود؛ پاسخ نامعلوم فقط با خواندن صرافی روشن می‌شود، هرگز با ارسال دوباره.'],
      ['■', 'کلیدهای توقف', 'توقف سراسری معاملات واقعی، ورودهای جدید و معاملات تعهدی؛ و برای هر ربات: توقف، فقط مدیریت خروج یا فروش همه.'],
      ['◎', 'سرمایهٔ اختصاصی', 'هر ربات فقط سرمایهٔ خودش را خرج می‌کند و فقط دارایی‌ای را می‌فروشد که خودش خریده است.']]
      .map(([i, t, d]) => `<div class="panel ld-seci"><span class="ld-ico">${i}</span><b>${t}</b><p>${d}</p></div>`).join('')}</div>`)}

  ${sec('plans', 'پلن‌ها', 'از رایگان شروع کن', 'اجرای آزمایشی و بک‌تست در همهٔ پلن‌ها هست؛ برای ربات واقعی و سهمیهٔ بیشتر AI پلن را ارتقا بده.',
    `<div class="ld-plans">${plans.map(p => `<div class="panel ld-plan ${p.id === popular ? 'hot' : ''}">${p.id === popular ? '<span class="ld-badge">محبوب‌ترین</span>' : ''}<b>${esc(p.name)}</b>
      <div class="ld-price">${+p.price_tmn ? toman(p.price_tmn) : 'رایگان'}</div><div class="faint">${+p.price_tmn ? fa(p.days) + ' روز' : 'همیشه'}</div><p class="muted">${esc(p.description || '')}</p>
      <ul><li>${fa(p.max_bots)} ربات</li><li>${+p.max_live_bots ? fa(p.max_live_bots) + ' ربات واقعی هم‌زمان' : 'فقط اجرای آزمایشی'}</li>${+p.max_capital_tmn ? `<li>سرمایهٔ هر ربات واقعی تا ${toman(p.max_capital_tmn)}</li>` : ''}<li>${fa(p.ai_calls_month)} درخواست AI در ماه</li><li>بک‌تست و استودیو</li></ul>
      <a href="#login"><button class="${p.id === popular ? 'primary' : ''}" style="width:100%">${+p.price_tmn ? 'انتخاب پلن' : 'شروع رایگان'}</button></a></div>`).join('')}</div>`)}

  ${sec('faq', 'پرسش‌های پرتکرار', 'جواب سؤال‌هایت', '', `<div class="ld-faq">${FAQ.map(([q, a]) => `<details class="panel"><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>`)}

  <section class="ld-final ld-reveal panel glow"><h2>اولین رباتت را همین امروز بساز</h2><p class="muted">ثبت‌نام فقط با شمارهٔ موبایل؛ اجرای آزمایشی و بک‌تست رایگان.</p><a href="#login"><button class="primary ld-btn">شروع رایگان</button></a></section>

  <footer class="ld-foot"><div class="brand"><img src="/assets/mark.svg" alt=""><div><b>${esc(m.site_name)}</b><small>نسخهٔ ${esc(m.version)}</small></div></div>
    <p>معامله در بازار رمزارز، به‌ویژه معامله تعهدی با اهرم، ریسک بالایی دارد و ممکن است بخشی یا همهٔ سرمایه از دست برود. بازده گذشته، بک‌تست یا اجرای آزمایشی سود آینده را تضمین نمی‌کند. الگوریتمیک مشاور سرمایه‌گذاری نیست و تصمیم اجرای هر ربات با کاربر است.</p>
    ${m.support ? `<p class="faint">${esc(m.support)}</p>` : ''}</footer>
  </div><div id="toast" class="toast hidden"></div>`;
  background($('#fx'));
  wire(maxLev);
}

function wire(maxLev) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  // smooth section navigation without touching the router's hash
  $$('[data-go]').forEach(b => b.onclick = () => { const t = document.getElementById(b.dataset.go); if (t) t.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }); });
  // reveal on scroll
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: 0.12 }) : null;
  $$('.ld-reveal').forEach(el => io ? io.observe(el) : el.classList.add('in'));
  // hero console: counter and AI typing
  const eq = $('#ldEq'), pnl = $('#ldPnl'); let v = 10_000_000, t0 = performance.now();
  const tick = now => { if (!document.body.contains(eq)) return; const k = Math.min(1, (now - t0) / 2600); const val = 10_000_000 * (1 + 0.0412 * (1 - Math.pow(1 - k, 3)));
    eq.textContent = fa(Math.round(val)); pnl.textContent = '+' + new Intl.NumberFormat('fa-IR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format((val / 1e7 - 1) * 100) + '٪'; if (k < 1) requestAnimationFrame(tick); };
  reduce ? (eq.textContent = fa(10_412_000), pnl.textContent = '+۴٫۱٪') : requestAnimationFrame(tick);
  const lines = ['ساختار صعودی با حجم تأییدشده؛ اطمینان ۰٫۷۸ — ورود با ۸۰٪ اندازه', 'هم‌جهتی با بیت‌کوین ضعیف است؛ رد', 'شکست ساختار روی ۴ساعته؛ اطمینان ۰٫۷۱ — ورود'];
  let li = 0, ci = 0; const typer = $('#ldType');
  const type = () => { if (!document.body.contains(typer)) return; const s = lines[li]; typer.textContent = s.slice(0, ci); ci++;
    if (ci > s.length + 40) { ci = 0; li = (li + 1) % lines.length; } setTimeout(type, ci > s.length ? 50 : 38); };
  reduce ? (typer.textContent = lines[0]) : type();
  // decision pipeline: click or auto-advance
  const info = $('#ldPipeInfo'); let cur = 0, auto = null;
  const show = i => { cur = i; const [k, t, d] = PIPE[i]; $$('#ldPipe .ld-node').forEach((n, j) => { n.classList.toggle('on', j === i); n.classList.toggle('done', j < i); });
    $$('#ldPipe .ld-edge').forEach((e, j) => e.classList.toggle('live', j < i)); info.innerHTML = `<div class="ld-kick">مرحلهٔ ${fa(i + 1)} از ${fa(PIPE.length)}</div><b>${t}</b><p>${d}</p>`; };
  $$('#ldPipe .ld-node').forEach((n, i) => n.onclick = () => { clearInterval(auto); auto = null; show(i); });
  show(0); if (!reduce) auto = setInterval(() => { if (!document.body.contains(info)) return clearInterval(auto); show((cur + 1) % PIPE.length); }, 3200);
  // leverage calculator
  const lev = $('#ldLev'); const upd = () => { const k = +lev.value; const liq = (1 - 0.1) / k;
    $('#ldLevV').textContent = '×' + fa(k); $('#ldLevMove').textContent = fa(k) + '٪ وثیقه';
    $('#ldLevLiq').textContent = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 1 }).format(liq * 100) + '٪'; $('#ldLevStop').textContent = 'کمتر از ' + new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 1 }).format(liq * 80) + '٪'; };
  lev.oninput = upd; upd();
  // live market strip (public Wallex prices)
  api('/api/landing').then(d => {
    if (!d || !d.ticker || !d.ticker.length) return;
    const item = r => `<span class="ld-tk"><b>${esc(r.base)}</b><span>${fa(Math.round(r.last))}</span><i class="${r.change_24h >= 0 ? 'pos' : 'neg'}">${r.change_24h >= 0 ? '▲' : '▼'} ${new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 }).format(Math.abs(r.change_24h || 0))}٪</i></span>`;
    $('#ldTrack').innerHTML = d.ticker.map(item).join('') + d.ticker.map(item).join('');
    $('#ldTicker').hidden = false;
  }).catch(() => null);
}
