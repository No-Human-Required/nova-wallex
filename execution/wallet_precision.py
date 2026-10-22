"""A bounded observation policy, not a cash adjustment or exchange guarantee.

The first live fill gave exact fractional notional but balances-detail reported
integer TMN. The official schema does not specify rounding. Preserve the exact
ledger, accept only its integer floor, and use the LOWER reported cash for
spending. The absolute uncertainty must stay below ONE TMN across the entire
account; it is never reset or accumulated per fill. Non-TMN assets remain exact.
"""
from decimal import Decimal, ROUND_FLOOR
from .contracts import ContractError,dec,number

POLICY='integer-tmn-observation-v1'


def check_wallet(totals,expected,*,allow_integer_tmn=False):
    actual={a:dec(v) for a,v in totals.items() if dec(v)!=0}
    expected={a:dec(v) for a,v in expected.items() if dec(v)!=0}
    if actual==expected:return {'exact':True,'tmn_difference':'0'}
    a,e=actual.get('TMN',Decimal(0)),expected.get('TMN',Decimal(0))
    if (allow_integer_tmn and {k:v for k,v in actual.items() if k!='TMN'}==
        {k:v for k,v in expected.items() if k!='TMN'} and
        a==e.to_integral_value(rounding=ROUND_FLOOR) and 0<e-a<1):
        return {'exact':False,'tmn_difference':number(e-a),'policy':POLICY,
                'assumption':'integer-floor reporting; not specified by exchange documentation',
                'ledger_modified':False,'spending_cash_tmn':number(a)}
    raise ContractError('Wallet differs from ledger; no silent resync')
