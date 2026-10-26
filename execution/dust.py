"""One rule for "unsellable residue" shared by the runtime controller and planner.

A holding is a residue when the quantity the engine may actually sell (after the
journal's fee reservation and the exchange quantity step) is below the exchange
minimum quantity, or its value is below the larger of the exchange minimum
notional and Nova's own minimum order. Such a holding can never be exited by
an order, so it must not occupy a regime position slot.
"""
from decimal import Decimal

from starwallex.domain import floor_step

FEE_BUFFER = Decimal('0.003')


def sellable(qty, m, fee_buffer=FEE_BUFFER):
    return floor_step(Decimal(qty)/(1+Decimal(fee_buffer)), m.qty_step)


def unsellable(qty, m, *, price=None, fx=None, value_tmn=None, min_order_tmn=0, fee_buffer=FEE_BUFFER):
    """True when the holding cannot be sold. ``price`` is in the market's quote
    currency; ``value_tmn`` is an alternative valuation of the whole holding in
    TMN (used when no recent price exists). Unknown valuation -> False (a slot
    is only released on evidence)."""
    qty = Decimal(qty)
    q = sellable(qty, m, fee_buffer)
    if q < m.min_qty:
        return True
    floor_tmn = Decimal(str(min_order_tmn or 0))
    if price is not None:
        price = Decimal(price)
        notional = q*price
        if notional < m.min_notional:
            return True
        if m.quote == 'TMN':
            return notional < floor_tmn
        return fx is not None and notional*Decimal(fx) < floor_tmn
    if value_tmn is not None:
        value = Decimal(value_tmn)*q/qty if qty else Decimal(0)
        minimum = m.min_notional if m.quote == 'TMN' else (m.min_notional*Decimal(fx) if fx is not None else Decimal(0))
        return value < max(minimum, floor_tmn)
    return False
