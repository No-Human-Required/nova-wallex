"""Offline Persian evidence dashboard and machine-readable research statistics."""
import argparse
import html
import json
import random
import sqlite3
from collections import Counter
from pathlib import Path
from statistics import mean

from .domain import D
from .util import ROOT, read_json, write_json


def block_interval(values, draws=5000):
    rng = random.Random(20261022)
    samples = []
    n = len(values)
    for _ in range(draws):
        sample = []
        while len(sample) < n:
            i = rng.randrange(n)
            sample.extend([values[i],values[(i+1)%n]])
        samples.append(mean(sample[:n]))
    samples.sort()
    return [samples[int(draws*.025)],samples[int(draws*.975)]]


def events(directory, kind):
    with sqlite3.connect(f'file:{(directory/"audit.sqlite").as_posix()}?mode=ro', uri=True) as db:
        return [json.loads(x[0]) for x in db.execute('SELECT payload FROM events WHERE kind=? ORDER BY seq',(kind,))]


def number(x, digits=4):
    return 'نامعلوم' if x is None else f'{float(x):,.{digits}f}'


def build(directory):
    directory = Path(directory)
    rows = read_json(directory/'comparison.json')
    aggregates = read_json(directory/'aggregates.json')
    selection = read_json(directory/'selection.json')
    protocol = read_json(directory/'protocol.json')
    coverage = read_json(ROOT/'data/portfolio/coverage.json')['markets']
    ai_rows = read_json(directory/'ai-comparison.json') if (directory/'ai-comparison.json').exists() else []
    selected = selection['selected_policy']
    group = [r for r in rows if r['split']=='test' and r['scenario']=='base' and r['policy']==selected]
    values = [float(r['liquidation_return_percent']) for r in group]
    stats = {'selected_policy':selected,'selected_test_mean_percent':mean(values),
             'descriptive_block_bootstrap_95_interval_percent':block_interval(values),
             'test_windows':len(values),'positive_test_windows':sum(v>0 for v in values),
             'data_pairs':len(coverage),'valid_bars':sum(r['count'] for r in coverage.values()),
             'zero_volume_bars':sum(r['zero_volume_bars'] for r in coverage.values()),
             'quarantined_rows':sum(r.get('quarantined_count',0) for r in coverage.values()),
             'source_sha256':protocol['source']['sha256'],
             'interpretation':'Descriptive uncertainty only; current survivor universe, repeated historical inspection, no guarantee of future performance'}
    paired = []
    for r in ai_rows:
        base = next(x for x in rows if x['window']==r['window'] and x['policy']==r['policy'] and x['scenario']=='base')
        sig = lambda f:(f['time'],f['symbol'],f['side'],f['qty'],f['price'])
        before = [sig(f) for f in events(directory/base['case'],'fill')]
        after = [sig(f) for f in events(directory/r['case'],'fill')]
        paired.append({'window':r['window'],'baseline_return_percent':float(base['liquidation_return_percent']),
                       'ai_return_percent':float(r['liquidation_return_percent']),
                       'ai_economic_return_percent':float(r['economic_liquidation_return_percent']) if r['economic_liquidation_return_percent'] is not None else None,
                       'estimated_ai_cost_tmn':r['estimated_ai_cost_tmn'],
                       'recorded_responses':r['unique_recorded_responses'],'fills_differ':before!=after,
                       'baseline_fills':len(before),'ai_fills':len(after),'ai_failures':r['ai_failures']})
    stats['ai_paired_windows']=paired
    if paired:
        stats['ai_mean_trading_return_percent']=mean(x['ai_return_percent'] for x in paired)
        economic=[x['ai_economic_return_percent'] for x in paired]
        stats['ai_mean_economic_return_percent']=mean(economic) if all(x is not None for x in economic) else None
        stats['ai_mean_paired_trading_difference_percent']=mean(x['ai_return_percent']-x['baseline_return_percent'] for x in paired)
    write_json(directory/'research-statistics.json',stats)
    cases={}
    for r in [x for x in rows if x['split']=='test' and x['scenario']=='base']+ai_rows:
        accounts=events(directory/r['case'],'account')
        cases[r['case']]={'equity':[float(x['equity']) for x in accounts],
                           'labels':[x['time'] for x in accounts],
                           'terminal':float(r['estimated_liquidation_nav_tmn']),
                           'summary':{k:r[k] for k in ['cash_tmn','realized_pnl_tmn','unrealized_pnl_tmn','fees_tmn','fill_count','max_drawdown_percent','positions','fx_lots']}}
    table=[]
    for a in aggregates:
        if a['split'] not in {'validation','test'}: continue
        table.append('<tr>'+''.join(f'<td>{html.escape(str(x))}</td>' for x in [a['split'],a['scenario'],a['policy'],a['windows'],number(a['mean_liquidation_return_percent']),
                    number(a['median_liquidation_return_percent']),f"{a['positive_windows']}/{a['windows']}",number(a['worst_liquidation_return_percent']),number(a['max_drawdown_percent']),a['fills']])+'</tr>')
    ai_table=[]
    for a in paired:
        ai_table.append('<tr>'+''.join(f'<td>{html.escape(str(x))}</td>' for x in [a['window'],number(a['baseline_return_percent']),number(a['ai_return_percent']),
                    number(a['ai_economic_return_percent']),number(a['estimated_ai_cost_tmn'],2),a['recorded_responses'],f"{a['baseline_fills']} ← {a['ai_fills']}",a['fills_differ']])+'</tr>')
    market_table=[]
    for s,q in sorted(coverage.items()):
        market_table.append(f'<tr><td>{s}</td><td>{q["count"]}</td><td>{q["expected_count"]-q["count"]}</td><td>{q["zero_volume_bars"]}</td><td>{q.get("quarantined_count",0)}</td></tr>')
    escaped_json=json.dumps(cases,ensure_ascii=False).replace('<','\\u003c')
    text=f'''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>StarWallex — گزارش پرتفوی</title>
<style>body{{font-family:Tahoma,Arial,sans-serif;background:#0c1423;color:#e8edf6;margin:0;line-height:1.9}}main{{max-width:1250px;margin:auto;padding:32px}}h1,h2{{color:#7ee0ce}}.muted{{color:#a8b6ca}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}.card,section{{background:#172338;border:1px solid #2d405c;border-radius:12px;padding:20px;margin:18px 0}}.n{{font-size:28px;direction:ltr;text-align:right}}.warn{{border-right:5px solid #f2c66d;padding:12px;background:#2b2830}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid #31425c;padding:8px;text-align:right}}.scroll{{overflow:auto}}select,input{{background:#0c1423;color:white;padding:9px;border:1px solid #51627c;border-radius:6px;max-width:100%}}code,pre{{direction:ltr;text-align:left;unicode-bidi:plaintext;white-space:pre-wrap;overflow-wrap:anywhere}}a{{color:#7ee0ce}}svg{{width:100%;height:280px}}small{{color:#a8b6ca}}</style>
<main><div class="muted">STARWALLEX / آزمایش تاریخی / بدون سفارش واقعی</div><h1>بک‌تست پرتفوی با سرمایهٔ مشترک</h1>
<p>پایش تاریخی تمام ۱۲۰ جفت مجاز فعلی، حسابداری تومان و مسیرهای مستقل تبدیل تتر؛ ۳۹ پنجرهٔ غیرهم‌پوشان سه‌روزه با سرمایهٔ تازهٔ ۵ میلیون تومان در هر پنجره.</p>
<div class="grid"><div class="card">جفت / کندل معتبر<div class="n">120 / {stats['valid_bars']:,}</div></div><div class="card">منتخب دورهٔ انتخاب<div class="n">{selected}</div></div><div class="card">میانگین آزمون پس از هزینهٔ تخمینی خروج<div class="n">{number(stats['selected_test_mean_percent'])}%</div></div><div class="card">پنجره‌های مثبت آزمون<div class="n">{stats['positive_test_windows']} / 9</div></div></div>
<p class="warn">این نتیجهٔ شبیه‌سازی است. سود پایدار یا مناسب‌بودن برای اجرای واقعی اثبات نشده است. هزینهٔ تسویهٔ انتهای پنجره برآورد شده؛ قاعدهٔ تسویهٔ مسابقه هنوز معلوم نیست.</p>
<section><h2>روش انتخاب و هزینه‌ها</h2><p>۲۰ پنجرهٔ توسعه، ۱۰ پنجرهٔ انتخاب و ۹ پنجرهٔ آزمون زمانی. انتخاب پیش از محاسبهٔ نتایج آزمون ذخیره شد. آخرین ۲۱ روز BTC/ETH قبلاً بررسی شده و نسخهٔ مقدماتی این آزمایش نیز نگهداری شده است؛ این آزمایش را کاملاً دست‌نخورده نمی‌نامیم.</p>
<p>کارمزد هر سمت: تومان ۰٫۳۰٪ و تتر ۰٫۱۳٪، از حساب غیر اصلیِ فعلی؛ لغزش ۱۰ و نیم‌اسپرد ۵ واحد پایه در هر مرحله، تأخیر یک ساعت در هر مرحله، ظرفیت حداکثر ۰٫۵٪ حجم گزارش‌شدهٔ کندل قبلی. هزینهٔ تقریبی رفت‌وبرگشت مستقیم ۰٫۹٪ و مسیر تتری ۱٫۴۶٪ مبلغ موقعیت است. حجم پایه‌بودن v فرض مدل ظرفیت است؛ آرشیو دفتر سفارش و صف نداریم.</p>
<p>چهار موقعیت، سقف ورود ۱۰٪ برای هر دارایی و مجموع ۴۰٪، بودجهٔ زیان هر موقعیت ۰٫۳٪ سرمایه و جمع ۱٫۲٪؛ همبستگی مثبت بیش از ۰٫۸ مانع ورود هم‌زمان است. توقف افت ۵٪ و زیان روزانهٔ UTC برابر ۲٪ است. قیمت می‌تواند بین مشاهده‌ها از حد عبور کند و خروج تأخیر دارد. افزایش قیمت دارایی می‌تواند نسبت مواجهه را بعد از ورود بالاتر ببرد.</p>
<p>بازهٔ توصیفی ۹۵٪ میانگین منتخب با بازنمونه‌گیری بلوک‌های دوپنجره‌ای: <b dir="ltr">{number(stats['descriptive_block_bootstrap_95_interval_percent'][0])}% … {number(stats['descriptive_block_bootstrap_95_interval_percent'][1])}%</b>. تنها ۹ پنجره داریم؛ این بازه اثر همهٔ سوگیری‌های انتخاب و بقا را برطرف نمی‌کند.</p></section>
<section><h2>مقایسهٔ زمانی</h2><p class="muted">اعداد درصد کل سرمایه‌اند. میانگین پنجره‌های مستقل، سود مرکب یک حساب پیوسته نیست. btc_hold نگهداری تا پایان با سقف ۴۰٪ و liquid_basket سبد ابتدایی بازارهای نقدشونده با سقف ۴×۱۰٪ است؛ این دو خط مبنا توقف فعال استراتژی‌ها را ندارند.</p><div class="scroll"><table><thead><tr><th>بخش</th><th>سناریو</th><th>سیاست</th><th>پنجره</th><th>میانگین٪</th><th>میانه٪</th><th>مثبت</th><th>بدترین٪</th><th>افت٪</th><th>پرشدن</th></tr></thead><tbody>{''.join(table)}</tbody></table></div></section>
<section><h2>اثر واقعی AI و هزینهٔ آن</h2><p>DeepSeek فقط ورودهای جدید را از فهرست نامزدها حذف یا مرتب می‌کند. مقدار، همبستگی، سقف ریسک و خروج در کد اعمال می‌شوند. ورودی شامل پنج ویژگی قیمت، نقدشوندگی و هزینه است؛ نام دارایی و تاریخ از مدل پنهان است. پاسخ واقعی ذخیره می‌شود؛ هیچ خروجی مدل برای تکمیل جدول ساخته نشده است.</p><div class="scroll"><table><thead><tr><th>پنجره</th><th>بدون AI٪</th><th>با AI٪</th><th>با کسر API٪</th><th>API تخمینی / تومان</th><th>پاسخ ثبت‌شده</th><th>پرشدن قبل ← بعد</th><th>تفاوت معاملات</th></tr></thead><tbody>{''.join(ai_table) or '<tr><td colspan="8">آزمون AI هنوز ثبت نشده است.</td></tr>'}</tbody></table></div><small>IRT گزارش‌شدهٔ سرویس به‌عنوان تومان لحاظ شده است؛ این برآورد جای صورتحساب قطعی نیست. بازپخش از پاسخ‌های ذخیره‌شده، هزینهٔ API تازه ندارد.</small></section>
<section><h2>مسیر حساب و دارایی باز</h2><label>اجرای مورد بررسی <select id="case"></select></label><svg id="chart" viewBox="0 0 1100 280" role="img" aria-label="ارزش حساب طی ۷۲ ساعت"></svg><p id="chartText"></p><pre id="details"></pre><small>خط سبز ارزش حساب در مشاهده‌های ساعتی است؛ نقطهٔ طلایی برآورد نقدشدن انتهای دوره است و معاملهٔ واقعی انجام‌شده نیست.</small></section>
<section><h2>کیفیت تمام بازارها</h2><p>{stats['zero_volume_bars']:,} کندل حجم صفر دارند؛ دو کندل نامعتبر قرنطینه شده‌اند. دادهٔ مفقود پر نشده است. هر ساعت، دادهٔ پیوسته و نقدشوندگی هر جفت دوباره بررسی می‌شود. یک دارایی در دو بازار تومانی/تتری، دو موقعیت مستقل شمرده نمی‌شود. USDTTMN برای تأمین و تخلیهٔ وجه تتری پایش می‌شود و در این نسخه نامزد آلفای مستقل نیست.</p><input id="search" placeholder="جست‌وجوی نماد" aria-label="جست‌وجوی نماد"><div class="scroll" style="max-height:420px"><table><thead><tr><th>نماد</th><th>کندل معتبر</th><th>کمبود</th><th>حجم صفر</th><th>قرنطینه</th></tr></thead><tbody id="markets">{''.join(market_table)}</tbody></table></div></section>
<section><h2>ردیابی و محدودیت‌های تحویل</h2><p>منبع، تنظیمات، داده، تصمیم AI، نتیجهٔ ریسک، سفارش شبیه‌سازی، کارمزد و وضعیت حساب در هر اجرا قابل ردیابی‌اند. دفتر SQLite زنجیرهٔ هش و checkpoint دارد. اسرار در بسته قرار نمی‌گیرند.</p><p>عضویت و حداقل سفارش مربوط به فهرست فعلی است؛ بازارهای حذف‌شدهٔ تاریخی در اختیار نیستند. تاریخچه از API امروز بازسازی شده و آرشیو انتشار هم‌زمان نیست. افت داخل کندل، صف، عمق تاریخی و هزینهٔ طرح اعتباری معلوم نیستند. نرخ کارمزد حساب مسابقه، زمان رسمی و قانون سود محقق‌شده/دارایی باز باید پیش از اجرای واقعی روشن شوند.</p><code>{stats['source_sha256']}</code><p><a href="research-statistics.json">آمار قابل پردازش</a> · <a href="selection.json">شاهد انتخاب قبل از آزمون</a> · <a href="verification.json">شاهد بازپخش</a></p></section></main>
<script>const data={escaped_json};const sel=document.getElementById('case');Object.keys(data).forEach(k=>{{let o=document.createElement('option');o.value=k;o.textContent=k;sel.appendChild(o)}});function draw(){{const d=data[sel.value];if(!d)return;const v=d.equity.concat([d.terminal,5000000]);let lo=Math.min(...v),hi=Math.max(...v);if(hi===lo){{lo-=1;hi+=1}}const y=x=>245-(x-lo)/(hi-lo)*210;let pts=d.equity.map((x,i)=>`${{55+i*1000/Math.max(1,d.equity.length-1)}},${{y(x)}}`).join(' ');document.getElementById('chart').innerHTML=`<line x1="55" y1="${{y(5000000)}}" x2="1055" y2="${{y(5000000)}}" stroke="#68788e" stroke-dasharray="4"/><polyline points="${{pts}}" fill="none" stroke="#7ee0ce" stroke-width="3"/><circle cx="1055" cy="${{y(d.terminal)}}" r="5" fill="#f2c66d"/><text x="1055" y="20" text-anchor="end" fill="#b9c9dd">${{Math.round(hi).toLocaleString()}} TMN</text><text x="1055" y="274" text-anchor="end" fill="#b9c9dd">${{Math.round(lo).toLocaleString()}} TMN</text>`;document.getElementById('details').textContent=JSON.stringify(d.summary,null,2);document.getElementById('chartText').textContent='نقدشدن تخمینی انتها: '+Math.round(d.terminal).toLocaleString()+' تومان';}}sel.onchange=draw;sel.value=Object.keys(data).find(k=>k.includes('w39')&&k.includes('{selected}')&&!k.endsWith('-ai'))||Object.keys(data)[0];draw();document.getElementById('search').oninput=e=>{{let q=e.target.value.toUpperCase();document.querySelectorAll('#markets tr').forEach(r=>r.hidden=!r.firstChild.textContent.includes(q))}};</script></html>'''
    (directory/'report.html').write_text(text,encoding='utf-8')
    lines=['# نتیجهٔ بک‌تست پرتفوی والکس','',f"منتخب دورهٔ انتخاب: `{selected}`. میانگین ۹ پنجرهٔ آزمون پس از هزینهٔ تخمینی نقدشدن: **{number(mean(values))}٪**؛ پنجرهٔ مثبت: {stats['positive_test_windows']}/۹.",
           '', 'این آزمایش سود آینده را اثبات نمی‌کند. نسخهٔ مقدماتی و اصلاح هزینه/کنترل ریسک ثبت شده‌اند؛ دورهٔ آزمون را کاملاً دست‌نخورده نمی‌نامیم.', '',
           '| بخش | سناریو | سیاست | میانگین بازده٪ | بدترین٪ | افت٪ | مثبت |', '|---|---|---|---:|---:|---:|---:|']
    for a in aggregates:
        if a['split'] in {'test','validation'}:
            lines.append(f"| {a['split']} | {a['scenario']} | {a['policy']} | {number(a['mean_liquidation_return_percent'])} | {number(a['worst_liquidation_return_percent'])} | {number(a['max_drawdown_percent'])} | {a['positive_windows']}/{a['windows']} |")
    lines += ['', '## اثر AI', '', '| پنجره | بدون AI٪ | با AI٪ | با کسر هزینه API٪ | تفاوت معاملات |', '|---|---:|---:|---:|---|']
    for a in paired: lines.append(f"| {a['window']} | {number(a['baseline_return_percent'])} | {number(a['ai_return_percent'])} | {number(a['ai_economic_return_percent'])} | {a['fills_differ']} |")
    lines += ['', '## روش و حدود اعتبار', '', 'همهٔ ۱۲۰ جفت فعلی، ۱۲۰ روز، ۳۹ پنجرهٔ مستقل ۷۲ساعته با سرمایهٔ ۵ میلیون تومان؛ ۲۰ توسعه، ۱۰ انتخاب و ۹ آزمون. کارمزد ۰٫۳۰٪ تومان و ۰٫۱۳٪ تتر، لغزش ۱۰bps و نیم‌اسپرد ۵bps هر مرحله، تأخیر ۱ ساعت در هر مرحله، سقف ظرفیت ۰٫۵٪ حجم پایهٔ فرض‌شدهٔ کندل قبلی. مسیر تتری هزینه و تأخیر تبدیل رفت‌وبرگشت مستقل دارد.', '',
             'سقف ورود هر دارایی ۱۰٪ و جمع ۴۰٪، چهار دارایی، بودجه زیان ۰٫۳٪ هر موقعیت و ۱٫۲٪ مجموع، همبستگی مثبت حداکثر ۰٫۸. حدود پژوهشی‌اند؛ افت بین مشاهدات و تأخیر خروج می‌تواند از آستانه بیشتر باشد. خطوط مبنای نگهداری توقف فعال ندارند.', '',
             'بازده جدول شامل برآورد هزینهٔ فروش دارایی باز است، نه فروش انجام‌شده یا قانون مسابقه. realized PnL، نقد، دارایی باز، کارمزد و ارزش پایان جدا در summary هر اجرا آمده‌اند. میانگین پنجره‌ها سود مرکب نیست. صفر ناشی از عدم معامله نیز در میانگین لحاظ شده است.', '',
             'فهرست فعلی بازارها و قوانین فعلی سفارش، سوگیری بقا ایجاد می‌کنند. کندل‌های خراب و مفقود پر نشده‌اند. دفتر سفارش تاریخی، صف، تأخیر واقعی و هزینهٔ طرح اعتباری نداریم. شرح حجم در مستند رسمی واحد پایه را صریح نمی‌کند؛ مدل ظرفیت این فرض را به کار می‌برد. API هزینهٔ AI را برآورد می‌کند، نه صورتحساب قطعی.', '',
             'شاخهٔ stress فقط فرض اجرای سفارش را تغییر می‌دهد و آستانهٔ سیگنال ثابت است؛ مسیر واقعی معاملات ممکن است بر اثر رد/تأخیر/پرشدن عوض شود. قطعی مصنوعی سه‌ساعته در هر ۹۷ ساعت از پیش تعیین شده است و بر اساس نتیجه انتخاب نشده.', '',
             f"هش منبع: `{stats['source_sha256']}`", '', '[داشبورد](report.html) · [انتخاب](selection.json) · [آمار](research-statistics.json) · [بازپخش](verification.json)', '']
    (directory/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return stats


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    print(json.dumps(build(p.parse_args().out),ensure_ascii=True,default=str))
