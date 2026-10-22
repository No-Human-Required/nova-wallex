"""Optional read-only check of the supplied test-account key; no balances persisted."""
import json
from pathlib import Path
from datetime import datetime,timezone
from starwallex.util import credential
from .gateway import WallexGateway
from .contracts import normalize_detail_balances

def main():
    out=Path(__file__).resolve().parent/'evidence'
    out.mkdir(exist_ok=True)
    g=WallexGateway(credential('WALLEX_API_KEY'))
    result={'time_utc':datetime.now(timezone.utc).isoformat(),'mode':'read_only_test_account',
            'challenge_account_verified':False,'writes_enabled':False}
    try:
        body=g.detailed_balances()
        totals,locked=normalize_detail_balances(body)
        result['balances_detail']={'status':'validated','path':'/v1/account/balances-detail',
            'row_keys':sorted(set(k for row in body['result'].values() for k in row)),
            'row_count':len(totals),'arithmetic':'every total == available + freeze',
            'amounts_persisted':False}
    except Exception as exc:
        result['balances_detail']={'status':'unverified','error_type':type(exc).__name__,'http_status':getattr(exc,'status',None)}
    try:
        ids=g.open_order_ids()
        result['open_orders']={'status':'validated','empty':not bool(ids),'identifiers_persisted':False}
    except Exception as exc:
        result['open_orders']={'status':'unverified','error_type':type(exc).__name__,'http_status':getattr(exc,'status',None)}
    (out/'read-only-contract.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
