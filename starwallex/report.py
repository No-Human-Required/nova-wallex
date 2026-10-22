import html
import json
from pathlib import Path
from .util import ROOT, read_json


def evidence_panel(directory):
    sections=[]
    run=directory/'BTCTMN-holdout-ai'
    if (run/'events.json').exists():
        events=read_json(run/'events.json')
        changes=[e['payload'] for e in events if e['kind']=='decision' and e['payload'].get('ai_changed_action')]
        details=[]
        for d in changes:
            details.append('<p><b>'+html.escape(str(d['at']))+' UTC epoch · '+html.escape(d['action'])+'</b> — '+html.escape(d['reason'])+'<br>قاعده روند در همان وضعیت: '+html.escape(d['without_ai_action'])+'؛ انتخاب مدل: '+html.escape(d['policy'])+'</p>')
        sections.append('<details><summary>شاهد نقش AI: تصمیم‌های تغییرکرده و دلیل واقعی مدل</summary>'+''.join(details)+'<p>این مقایسهٔ محلی اثر بر اقدام را نشان می‌دهد؛ سود اضافهٔ علّی را اثبات نمی‌کند. بازده کل با اجرای مستقل قاعده روند مقایسه می‌شود.</p><a href="BTCTMN-holdout-ai/events.json">دفتر کامل تصمیم، ریسک و حسابداری</a> · <a href="BTCTMN-holdout-ai/manifest.json">نسخه کد و تنظیمات</a></details>')
    curves=[]; legend=[]
    colors={'flat':'#afbec7','buy_hold':'#d99e48','trend':'#53c4d9','ai':'#bb9df0'}
    series={}
    for policy in colors:
        path=directory/f'BTCTMN-holdout-{policy}'
        if (path/'events.json').exists():
            points=[float(e['payload']['equity_tmn']) for e in read_json(path/'events.json') if e['kind']=='account']
            summary=read_json(path/'summary.json')
            points.append(float(summary['final_equity']))
            series[policy]=[(x/float(summary['initial_capital'])-1)*100 for x in points]
    if series:
        lo=min(min(v) for v in series.values());hi=max(max(v) for v in series.values());span=max(hi-lo,.01)
        for policy,values in series.items():
            pts=' '.join(f'{40+i*920/max(1,len(values)-1):.2f},{20+(hi-y)*180/span:.2f}' for i,y in enumerate(values))
            curves.append(f'<polyline fill="none" stroke="{colors[policy]}" stroke-width="2" points="{pts}"/>')
            legend.append(f'<span style="color:{colors[policy]}">{policy}</span>')
        chart=f'<svg viewBox="0 0 1000 230" role="img" aria-label="Sampled BTC equity paths"><text x="2" y="15" fill="#ccd" font-size="12">{hi:.3f}%</text><text x="2" y="220" fill="#ccd" font-size="12">{lo:.3f}%</text>'+''.join(curves)+'</svg>'
        sections.append('<h2>مسیر ارزش حساب در ۷۲ ساعت پایانی BTC</h2><p dir="ltr">'+' · '.join(legend)+'</p>'+chart)
    shadow=ROOT/'runs/final-shadow/summary.json'
    if shadow.exists():
        s=read_json(shadow)
        sections.append('<h2>آزمایش محدود با داده زنده</h2><p>'+f"{s['sample_count']} مشاهدهٔ حساب مجازی، {s['fill_count']} پرشدن شبیه‌سازی‌شده، {s['error_count']} خطای ثبت‌شده، {s['exchange_orders_sent']} سفارش ارسالی به صرافی. بازده ارزش‌گذاری‌شده: {float(s['net_return_percent']):.4f}٪. این اجرای کوتاه شاهد پایداری سه‌روزه نیست."+'</p><a href="../final-shadow/summary.json">خلاصه اجرای سایه</a> · <a href="../final-shadow/events.json">شواهد اجرای سایه</a>')
    return ''.join(sections)


def report(directory):
    directory=Path(directory)
    rows=read_json(directory/"comparison.json")
    table=[]
    for r in rows:
        table.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [r['symbol'],r['split'],r['policy'],f"{float(r['net_return_percent']):.3f}%",f"{float(r['max_drawdown_percent']):.3f}%",r['fill_count'],f"{float(r['fees']):,.0f}",r['ai_changed_actions']])+'</tr>')
    ai=[x for x in rows if x['policy']=='ai']
    note='نتیجه DeepSeek ثبت نشده است.' if not ai else f"DeepSeek: {ai[0]['decision_count']} تصمیم، {ai[0]['ai_changed_actions']} تغییر اقدام نسبت به قاعده روند در همان وضعیت حساب، {ai[0]['ai_unavailable_decisions']} تصمیم با AI ناموجود."
    body='''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wallex — شواهد پژوهش</title><style>body{font-family:Tahoma,Arial,sans-serif;background:#101923;color:#e3ecf3;margin:0;padding:32px;line-height:1.9}main{max-width:1200px;margin:auto}h1{font-size:28px}p{max-width:950px}.badge{background:#18473f;color:#adf6dc;padding:6px 15px;border-radius:20px;display:inline-block}.warn{border-right:4px solid #e4b75a;padding:12px 18px;background:#262b32}table{border-collapse:collapse;width:100%;direction:ltr;font-size:14px}th,td{border-bottom:1px solid #344353;text-align:left;padding:10px}th{color:#8fd6c6}a{color:#8fd6c6}.scroll{overflow:auto}details{margin:20px 0}code{direction:ltr;display:inline-block}</style><main><span class="badge">فقط سایه • سفارش واقعی: صفر</span><h1>والکس | دفتر شواهد موتور معاملاتی</h1><p class="warn">اعداد زیر حاصل بک‌تست و اجرای شبیه‌سازی‌شده‌اند؛ بازدهی حساب مسابقه نیستند. تاریخ پایان و قاعده تسویه هنوز تعیین نشده است. هیچ سودی تضمین نشده و مجوز معامله واقعی صادر نشده است.</p><p>سرمایه مجازی: ۵٬۰۰۰٬۰۰۰ تومان. داده تاریخی واقعی والکس، تصمیم فقط با کندل بسته، اجرای سفارش با تأخیر و قیمت بازشدن آینده. کارمزد پایه ۰٫۳۰٪ در هر سمت، لغزش ۱۰ و نیم‌اسپرد ۵ نقطه پایه؛ این هزینه‌ها برای حساب نهایی چالش هنوز تأیید نشده‌اند.</p><p>NOTE</p><div class="scroll"><table><thead><tr><th>Market</th><th>Split</th><th>Policy</th><th>Net return</th><th>Sampled max DD</th><th>Fills</th><th>Fees / TMN</th><th>AI action changes</th></tr></thead><tbody>TABLE</tbody></table></div><details open><summary>معنای مقایسه</summary><p>validation: سه روز قبل از بازه پایانی؛ holdout: سه روز پایانی داده؛ stress: دوبرابر کارمزد، سه‌برابر لغزش و دو کندل تأخیر. flat خط مبنای نقد، buy_hold نگهداری با همان سقف سرمایه و ریسک، trend روند و mean_reversion بازگشت به میانگین است. سیاست‌ها و آستانه‌ها پیش از گزارش ثابت‌اند؛ این نمونه برای اثبات سودآوری کافی نیست.</p></details><details><summary>محدودیت‌ها و بازاجرا</summary><p>عمق تاریخی سفارش نداریم؛ ظرفیت پرشدن از حجم کندل قبلی برآورد می‌شود. ریسک و افت در نقاط مشاهده سنجیده شده‌اند. دارایی باز و سود تحقق‌یافته جدا گزارش شده و خروج اجباری در پایان فرض نشده است. پاسخ‌های مدل ذخیره شده‌اند؛ تولید مجدد مدل ممکن است متفاوت باشد.</p><p>هر پوشه اجرا شامل summary.json، events.json، audit.sqlite، manifest.json و تصویر دقیق سورس همان اجراست.</p></details><p><a href="comparison.json">داده کامل مقایسه</a></p></main></html>'''
    body=body.replace('سه‌برابر لغزش و دو کندل تأخیر','سه‌برابر لغزش و نیم‌اسپرد و دو کندل تأخیر')
    body=body.replace('سیاست‌ها و آستانه‌ها پیش از گزارش ثابت‌اند؛ این نمونه برای اثبات سودآوری کافی نیست.','قواعد ثابت‌اند و جست‌وجوی پارامتر برای بیشینه‌کردن نتیجه انجام نشده است؛ این بازه اکنون مشاهده شده و دیگر آزمون آیندهٔ دست‌نخورده نیست. این نمونه برای اثبات سودآوری کافی نیست.')
    body=body.replace('buy_hold نگهداری با همان سقف سرمایه و ریسک','buy_hold نگهداری با همان سقف سرمایه، خروج زمانی و حد ضرر (نه خرید و نگهداری منفعل کلاسیک)')
    body=body.replace('</main>',evidence_panel(directory)+'<p>کارمزد معامله در بازده کم شده است؛ هزینه سرویس AI و هزینه احتمالی طرح اعتباری جدا هستند و از این بازده کم نشده‌اند. نیم‌اسپرد تاریخی فرض شده است و اندازه‌گیری تاریخی دفتر سفارش نداریم.</p></main>')
    path=directory/"report.html"
    path.write_text(body.replace('NOTE',html.escape(note)).replace('TABLE',''.join(table)),encoding='utf-8')
    return path
