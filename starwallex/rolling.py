"""Six fixed, non-overlapping 72h windows; no model training or parameter search.

Only the last window has recorded LLM responses. No billed/network calls are made.
Each window starts with the same capital; window averages are not compounded returns.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

from .ai import AvalaiSelector
from .data import load_bars
from .domain import D, Market, load_config
from .evaluate import backtest
from .util import ROOT, canonical, read_json, write_json


def rolling(outdir):
    cfg=load_config()
    outdir=Path(outdir)
    metadata=read_json(ROOT/'data/markets.json')['markets']
    rows=[]
    for symbol in ['BTCTMN','ETHTMN']:
        data,bars=load_bars(ROOT/f'data/{symbol}-1h.json')
        if len(bars)!=504 or data['quality']['gaps']:
            raise ValueError('This frozen protocol requires 504 contiguous hourly observations')
        market=Market.parse(metadata[symbol])
        base=deepcopy(cfg);base['symbol']=symbol
        for window in range(6):
            start=72+window*72;end=start+72
            for scenario in ['base','stress']:
                config=deepcopy(base)
                if scenario=='stress':
                    config.update(fee_rate=str(D(base['fee_rate'])*2),slippage_bps=str(D(base['slippage_bps'])*3),assumed_half_spread_bps=str(D(base['assumed_half_spread_bps'])*3),latency_bars=2)
                policies=['flat','buy_hold','trend','mean_reversion'] if scenario=='base' else ['trend','mean_reversion']
                for policy in policies:
                    directory=outdir/f'{symbol}-w{window+1}-{scenario}-{policy}'
                    result=backtest(config,bars,market,start,end,policy,directory,data_hash=data['bars_sha256'])
                    result.update(symbol=symbol,window=window+1,scenario=scenario)
                    rows.append(result)
        if symbol==cfg['symbol']:
            selector=AvalaiSelector(base,ROOT/'data/ai-cache',replay_only=True)
            result=backtest(base,bars,market,432,504,'ai',outdir/f'{symbol}-w6-base-ai',selector=selector,data_hash=data['bars_sha256'])
            result.update(symbol=symbol,window=6,scenario='base')
            rows.append(result)
    aggregates=[]
    for symbol,scenario,policy in sorted({(r['symbol'],r['scenario'],r['policy']) for r in rows}):
        group=[r for r in rows if (r['symbol'],r['scenario'],r['policy'])==(symbol,scenario,policy)]
        returns=[float(r['net_return_percent']) for r in group]
        aggregates.append({'symbol':symbol,'scenario':scenario,'policy':policy,'windows':len(group),'positive_windows':sum(x>0 for x in returns),'mean_return_percent':mean(returns),'median_return_percent':median(returns),'worst_return_percent':min(returns),'best_return_percent':max(returns),'max_sampled_drawdown_percent':max(float(r['max_drawdown_percent']) for r in group),'fill_count':sum(r['fill_count'] for r in group),'windows_with_no_fills':sum(r['fill_count']==0 for r in group),'total_realized_pnl_tmn':str(sum((D(r['realized_pnl']) for r in group),D(0))),'total_fees_tmn':str(sum((D(r['fees']) for r in group),D(0)))})
    protocol={'windows':6,'hours_per_window':72,'warmup_hours':72,'initial_capital_each_window_tmn':cfg['capital_tmn'],'overlap':False,'model_training':False,'parameter_search':False,'data_previously_downloaded_and_inspected':True,'historical_ai_windows':1,'network_requests':0,'cost_stress_changes_entry_thresholds':True,'terminal_forced_sale':False,'limitations':['Independent resets; aggregate means are not one continuous compounded return','AI has only one recorded window and cannot be ranked against six-window means','Historical availability is reconstructed, not a point-in-time archive','Realized PnL and open inventory are separate; contest settlement remains unresolved','Fixed-rule stress changes both friction and entry thresholds; no claim of fixed-intent execution stress','No historical order-book queues or intrabar drawdown visibility']}
    write_json(outdir/'comparison.json',rows)
    write_json(outdir/'rolling-summary.json',{'protocol':protocol,'aggregates':aggregates})
    lines=['# بک‌تست شش پنجرهٔ سه‌روزه','', '۶ پنجرهٔ غیرهم‌پوشان؛ هرکدام با سرمایهٔ مجازی ۵ میلیون تومان از نو شروع می‌شود. ۷۲ ساعت اول warm-up است. جست‌وجوی پارامتر، آموزش مدل یا درخواست شبکه انجام نشده است. میانگین‌ها بازده مرکب یک حساب پیوسته نیستند.','', '| بازار | سناریو | سیاست | پنجره | مثبت | میانگین٪ | میانه٪ | بدترین٪ | fill | realized مجموع / تومان |','|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for a in aggregates:
        lines.append(f"| {a['symbol']} | {a['scenario']} | {a['policy']} | {a['windows']} | {a['positive_windows']} | {a['mean_return_percent']:.5f} | {a['median_return_percent']:.5f} | {a['worst_return_percent']:.5f} | {a['fill_count']} | {float(a['total_realized_pnl_tmn']):,.2f} |")
    lines+=['','AI فقط برای پنجرهٔ آخر، با ۱۸ پاسخ واقعی ذخیره‌شده سنجیده شده و نباید با میانگین شش پنجره رتبه‌بندی شود. `buy_hold` نگهداری با همان حد ضرر، سقف سرمایه و خروج زمانی است؛ نگهداری منفعل کلاسیک نیست.','', 'سناریوی stress کارمزد را دوبرابر، لغزش و نیم‌اسپرد را سه‌برابر و تأخیر را دوکندلی می‌کند؛ چون هزینه وارد شرط ورود نیز می‌شود، این آزمون هم انتخاب معامله و هم اجرا را تغییر می‌دهد.','', 'اعداد بازده از ارزش نقد به‌علاوه دارایی باز به قیمت bid برآوردی می‌آیند. سود تحقق‌یافته جداست؛ قاعدهٔ تسویهٔ مسابقه معلوم نیست و فروش اجباری پایان فرض نشده است. هزینهٔ تخمینی ۱۸ درخواست AI برابر ۲۰۵۱٫۴۰ تومان است و در بازده معاملاتی کم نشده.','', '## بازه‌های زمانی UTC','']
    for r in rows:
        if r['symbol']=='BTCTMN' and r['scenario']=='base' and r['policy']=='flat':
            lines.append(f"- پنجره {r['window']}: {r['start_utc']} تا {r['end_utc']}")
    lines+=['','این داده‌ها قبلاً دانلود شده‌اند؛ شش پنجره آزمون تاریخی‌اند، نه شش آزمایش آیندهٔ دست‌نخورده. نتیجهٔ قابل اتکا نیازمند شواهد بیشتر است. جزئیات تک‌تک پنجره‌ها در comparison.json و پوشهٔ هر اجرا قرار دارد.','']
    (outdir/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return aggregates


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(canonical(rolling(args.out)))
