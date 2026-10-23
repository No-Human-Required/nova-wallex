"""A bounded observation policy, not a cash adjustment or exchange guarantee.

Live fills give exact fractional notional while balances-detail reports integer
TMN. The official schema does not specify rounding; live observations show
round-to-nearest (4928031.2 -> 4928031 on 1405/07/30, 4239671.6165 -> 4239672
on 1405/08/01). Preserve the exact ledger, accept only the nearest integer, and
spend the LOWER of the reported and ledger cash. The absolute uncertainty stays
at most half a TMN across the entire account; it is never reset or accumulated
per fill. Non-TMN assets remain exact.
"""
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from .contracts import ContractError,dec,number

POLICY='integer-tmn-observation-v1'


def check_wallet(totals,expected,*,allow_integer_tmn=False):
    actual={a:dec(v) for a,v in totals.items() if dec(v)!=0}
    expected={a:dec(v) for a,v in expected.items() if dec(v)!=0}
    if actual==expected:return {'exact':True,'tmn_difference':'0'}
    a,e=actual.get('TMN',Decimal(0)),expected.get('TMN',Decimal(0))
    nearest={e.quantize(Decimal(1),rounding=ROUND_HALF_UP),e.quantize(Decimal(1),rounding=ROUND_HALF_EVEN)}
    if (allow_integer_tmn and {k:v for k,v in actual.items() if k!='TMN'}==
        {k:v for k,v in expected.items() if k!='TMN'} and a in nearest and a!=e):
        return {'exact':False,'tmn_difference':number(e-a),'policy':POLICY,'rounding':'down' if a<e else 'up',
                'assumption':'nearest-integer reporting; not specified by exchange documentation',
                'ledger_modified':False,'spending_cash_tmn':number(min(a,e))}
    raise ContractError('Wallet differs from ledger; no silent resync')
