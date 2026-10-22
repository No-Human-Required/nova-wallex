"""Decimal spot ledger, carrying cost basis through USDT conversions.

Realized TMN profit is recognized when value returns to TMN, not on an asset to
USDT sale. Fees may be paid in base, quote, or an already owned third asset.
"""
from decimal import Decimal
from .contracts import ContractError,asset,dec,number

class Ledger:
    def __init__(self,state):
        self.state={'capital':number(state['capital']),'cash':number(state['cash']),
                    'realized':number(state['realized']),
                    'holdings':{asset(a):{'qty':number(p['qty']),'basis':number(p['basis'])} for a,p in state['holdings'].items()}}
        self.check()

    @classmethod
    def initial(cls,capital):
        if dec(capital)<=0:raise ContractError('Capital must be positive')
        return cls({'capital':capital,'cash':capital,'realized':'0','holdings':{}})

    def quantity(self,a):
        return dec(self.state['cash']) if a=='TMN' else dec(self.state['holdings'].get(a,{}).get('qty','0'))

    def totals(self):return {'TMN':self.state['cash'],**{a:p['qty'] for a,p in self.state['holdings'].items()}}

    def take(self,a,q):
        q=dec(q)
        if q<0 or q>self.quantity(a):raise ContractError('Insufficient spot balance')
        if a=='TMN':
            self.state['cash']=number(self.quantity(a)-q);return q
        if q==0:return Decimal(0)
        p=self.state['holdings'][a];quantity,basis=dec(p['qty']),dec(p['basis'])
        cost=basis*q/quantity
        p.update(qty=number(quantity-q),basis=number(basis-cost))
        if quantity==q:del self.state['holdings'][a]
        return cost

    def put(self,a,q,basis):
        q,basis=dec(q),dec(basis)
        if q<=0 or basis<0:raise ContractError('Invalid acquired quantity/basis')
        if a=='TMN':
            self.state['cash']=number(self.quantity(a)+q)
            self.state['realized']=number(dec(self.state['realized'])+q-basis)
        else:
            p=self.state['holdings'].setdefault(a,{'qty':'0','basis':'0'})
            p.update(qty=number(dec(p['qty'])+q),basis=number(dec(p['basis'])+basis))

    def apply(self,intent,fill):
        q,p,fee=dec(fill['quantity']),dec(fill['price']),dec(fill['fee'])
        base,quote,fa=intent['base'],intent['quote'],fill['feeAsset']
        if base==quote or base=='TMN':raise ContractError('Invalid spot route')
        given,received=(quote,base) if intent['side']=='BUY' else (base,quote)
        spent,gained=(q*p,q) if intent['side']=='BUY' else (q,q*p)
        if fa==given:spent+=fee
        if fa==received:gained-=fee
        if gained<=0:raise ContractError('Fee consumes full proceeds')
        basis=self.take(given,spent)
        if fa not in {given,received}:basis+=self.take(fa,fee)
        self.put(received,gained,basis)
        self.check()

    def check(self):
        if dec(self.state['cash'])<0:raise ContractError('Negative TMN balance')
        basis=Decimal(0)
        for a,p in self.state['holdings'].items():
            if a=='TMN' or dec(p['qty'])<=0 or dec(p['basis'])<0:raise ContractError('Invalid holdings')
            basis+=dec(p['basis'])
        error=dec(self.state['cash'])+basis-dec(self.state['capital'])-dec(self.state['realized'])
        if abs(error)>Decimal('0.000001'):raise ContractError('Cost basis conservation failed')
