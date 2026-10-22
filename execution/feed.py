"""Public-only immutable hourly observations, plus short-lived executable quotes."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from starwallex.data import WallexPublic
from starwallex.portfolio_data import Instrument
from .history import TradingHistory as History
from starwallex.util import read_json,write_json,digest
from starwallex.persistence import file_exists

class PublicFeed:
    def __init__(self,universe,directory,*,api_factory=WallexPublic,workers=3):
        self.universe=universe;self.directory=Path(directory);self.api_factory=api_factory
        self.markets={s:Instrument.parse(m) for s,m in universe['markets'].items()}
        if 'USDTTMN' not in self.markets:raise ValueError('FX funding market is required')
        if not 1<=workers<=4:raise ValueError('Bounded worker count required')
        self.workers=workers;self.cached={}

    def verify_markets(self):
        api=self.api_factory();legacy,lm=api.get('/v1/markets');active,am=api.get('/hector/web/v1/markets')
        live={m['symbol']:m for m in active['result']['markets']}
        for s,expected in self.markets.items():
            if not live.get(s,{}).get('is_spot') or Instrument.parse(legacy['result']['symbols'][s])!=expected:
                raise ValueError('Permitted market became inactive or its precision/minimum changed: '+s)
        return {'sources':[lm,am],'verified_pairs':len(self.markets),'symbols_sha256':digest(sorted(self.markets))}

    def history(self,t):
        if t%3600:raise ValueError('Hourly decision boundary required')
        if t in self.cached:return self.cached[t]
        directory=self.directory/str(t);directory.mkdir(exist_ok=True,parents=True)
        universe={**self.universe,'requested_start':t-73*3600,'requested_end':t,
                  'interval_seconds':3600,'runtime_snapshot':True,'historical_membership':'current permitted universe'}
        if file_exists(directory/'universe.json') and read_json(directory/'universe.json')!=universe:
            raise ValueError('Existing observation universe differs')
        write_json(directory/'universe.json',universe)
        def one(symbol):
            path=directory/(symbol+'.json')
            if file_exists(path):return symbol,{'status':'cached'}
            try:
                data=self.api_factory().history(symbol,t-73*3600,t,quarantine=True)
                write_json(path,data);return symbol,{'status':'ok','quality':data['quality']}
            except Exception as exc:return symbol,{'status':'unavailable','error_type':type(exc).__name__}
        # Once coverage is written the observation is immutable, including gaps.
        if not file_exists(directory/'coverage.json'):
            results={}
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                for f in as_completed([pool.submit(one,s) for s in sorted(self.markets)]):
                    s,result=f.result();results[s]=result
            write_json(directory/'coverage.json',results)
        h=getattr(self,'history_type',History)(directory);self.cached={t:h};return h

    def quotes(self,symbols):
        if not set(symbols)<=set(self.markets):raise ValueError('Quote symbol outside permitted universe')
        def one(s):
            try:
                x=self.api_factory().depth(s)
                return s,{'bid':str(x['bids'][0][0]),'ask':str(x['asks'][0][0]),
                    'bids':[[str(p),str(q)] for p,q in x['bids']],
                    'asks':[[str(p),str(q)] for p,q in x['asks']],
                    'observed_at':int(x['observed_at']),'source':x['meta'],
                    'exchange_timestamp_available':False}
            except Exception as exc:return s,{'status':'unavailable','error_type':type(exc).__name__}
        result={}
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for f in as_completed([pool.submit(one,s) for s in sorted(set(symbols))]):
                s,q=f.result()
                if 'observed_at' in q:result[s]=q
        return result
