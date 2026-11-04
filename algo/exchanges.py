"""Exchanges the platform can serve. Wallex is live; others are listed as coming soon.

A new exchange needs: a market list with precision/minimums, public candles and
order book, and an order adapter with the same narrow contract as
``execution.gateway.WallexGateway`` (submit/lookup/cancel/balances).
"""
from functools import lru_cache

from starwallex.portfolio_data import Instrument
from starwallex.util import ROOT, read_json

EXCHANGES = {
    'wallex': {'fa': 'والکس', 'site': 'https://wallex.ir', 'key_help': 'در والکس: پروفایل ← API ← ساخت کلید با دسترسی «معامله» و بدون «برداشت».'},
    'nobitex': {'fa': 'نوبیتکس', 'site': 'https://nobitex.ir', 'key_help': ''},
}


def available(settings):
    return [{'id': k, 'fa': v['fa'], 'enabled': bool(settings.get(f'exchange.{k}.enabled')) and k == 'wallex',
             'coming_soon': k != 'wallex', 'key_help': v['key_help']} for k, v in EXCHANGES.items()]


@lru_cache(maxsize=1)
def wallex_markets():
    u = read_json(ROOT/'data/portfolio/universe.json')
    return {s: Instrument.parse(m) for s, m in u['markets'].items()}


def markets(exchange):
    if exchange != 'wallex':
        raise ValueError('این صرافی هنوز پشتیبانی نمی‌شود')
    return wallex_markets()


def gateway(exchange, key):
    if exchange != 'wallex':
        raise ValueError('این صرافی هنوز پشتیبانی نمی‌شود')
    from execution.gateway import WallexGateway
    return WallexGateway(key)


def check_key(exchange, key):
    """Read-only check: the key can read balances. Never places an order."""
    g = gateway(exchange, key)
    r = g.main_balances()
    if r.get('success') is not True:
        raise ValueError('کلید API پذیرفته نشد')
    balances = (r.get('result') or {}).get('balances') or {}
    tmn = balances.get('TMN') or {}
    return {'tmn_value': str(tmn.get('value', '0')), 'assets': len(balances)}
