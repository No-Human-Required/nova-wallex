from .domain import D


def fee_rate(cfg, quote):
    return D(cfg.get('fee_rates', {}).get(quote, cfg['fee_rate']))*D(cfg.get('fee_multiplier', '1'))


def roundtrip_bps(cfg, quote):
    friction = D(cfg['half_spread_bps'])+D(cfg['slippage_bps'])
    asset = fee_rate(cfg, quote)*10000+friction
    fx = fee_rate(cfg, 'TMN')*10000+friction if quote == 'USDT' else 0
    return float(2*(asset+fx))
