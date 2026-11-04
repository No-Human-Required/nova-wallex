"""Bot configuration: the backtest lab's parameters plus AI and live-trading rules.

A bot is configured with exactly the parameters the backtest lab accepts, so a
backtest of a bot is the same rule set the bot runs. Live mode is restricted to
TMN-quoted pairs (no USDT funding leg) and to the plan's capital cap.
"""
import time

from app import lab_engine as le
from .exchanges import markets

PRESETS = {
    'conservative': {'fa': 'محتاط', 'risk_pct': 0.3, 'max_positions': 2, 'min_quality': 60, 'regime_filter': True},
    'balanced': {'fa': 'متعادل', 'risk_pct': 0.5, 'max_positions': 3, 'min_quality': 55, 'regime_filter': True},
    'aggressive': {'fa': 'جسورانه', 'risk_pct': 1.0, 'max_positions': 5, 'min_quality': 45, 'regime_filter': False},
}
BOT_TIMEFRAMES = ('15m', '30m', '1h', '4h')
EXTRA = {'ai_filter': True, 'ai_min_confidence': 0.65, 'preset': 'balanced'}


def validate(raw, exchange, mode, plan_cap_tmn=None):
    raw = dict(raw or {})
    preset = raw.get('preset') or 'balanced'
    if preset not in PRESETS and preset != 'custom':
        raise ValueError('پروفایل ریسک نامعتبر است')
    base = {k: v for k, v in PRESETS.get(preset, {}).items() if k != 'fa'}
    if 'regime_filter' not in raw and len(raw.get('symbols') or []) < 3:
        base['regime_filter'] = False  # breadth needs at least 3 symbols
    lab_raw = {**base, **{k: v for k, v in raw.items() if k in le.DEFAULTS}}
    lab_raw.update(start=0, end=30*86400, source='wallex')  # placeholders: a bot has no fixed range
    if lab_raw.get('timeframe', '1h') not in BOT_TIMEFRAMES:
        raise ValueError('تایم‌فریم ربات یکی از ۱۵ و ۳۰ دقیقه، ۱ و ۴ ساعت است')
    p = le.validate(lab_raw, markets(exchange), now=31*86400)
    if mode == 'live':
        usdt = [s for s in p['symbols'] if markets(exchange)[s].quote != 'TMN']
        if usdt:
            raise ValueError('ربات واقعی فعلاً فقط بازارهای تومانی را معامله می‌کند: '+'، '.join(usdt))
    if plan_cap_tmn is not None and p['capital_tmn'] > plan_cap_tmn:
        raise ValueError(f'سرمایهٔ ربات از سقف پلن شما ({plan_cap_tmn:,} تومان) بیشتر است')
    ai = bool(raw.get('ai_filter', EXTRA['ai_filter']))
    conf = float(raw.get('ai_min_confidence', EXTRA['ai_min_confidence']))
    if not 0.3 <= conf <= 0.95:
        raise ValueError('حداقل اطمینان AI باید بین ۰٫۳ و ۰٫۹۵ باشد')
    cfg = {k: p[k] for k in le.DEFAULTS if k not in {'start', 'end', 'source'}}
    cfg.update(ai_filter=ai, ai_min_confidence=conf, preset=preset)
    return cfg


def lab_params(cfg, start, end, source='wallex'):
    """Backtest the bot's own rules over [start, end)."""
    return {**{k: v for k, v in cfg.items() if k in le.DEFAULTS}, 'start': start, 'end': end, 'source': source}


def initial_state(cfg):
    return {'cash_tmn': str(cfg['capital_tmn']), 'positions': {}, 'last_bar': None, 'cooldown': {}, 'seq': 0,
            'realized_tmn': '0', 'created': time.time()}
