"""Recorded AI entry decisions for the adaptive strategy set.

The full request, every attempt (including the provider's reasoning excerpt,
finish reason, token usage and latency), the validated decision and the reason
for each candidate are stored. A failed or incomplete answer never authorizes
an entry. Reasoning-model token exhaustion is handled by a bounded, recorded
request ladder instead of silently retrying the same request.
"""
import json
import time

from starwallex.net import request_json
from starwallex.persistence import file_exists
from starwallex.util import ROOT, canonical, credential, digest, read_json, redact, write_json

ENDPOINT = 'https://api.avalai.ir/v1/chat/completions'
ASSESSMENTS = {'agree', 'more_cautious', 'more_aggressive'}


def ladder(cfg):
    limit = int(cfg.get('ai_max_output_tokens', 12000))
    return [
        {'name': 'reasoning_low', 'extra': {'reasoning_effort': cfg.get('ai_reasoning_effort', 'low')}, 'max_tokens': limit},
        {'name': 'thinking_disabled', 'extra': {'thinking': {'type': 'disabled'}}, 'max_tokens': min(limit, 4000)},
        {'name': 'plain_large_budget', 'extra': {}, 'max_tokens': max(limit, 16000)},
    ]


def _num(x, nd=2):
    return None if x is None else round(float(x), nd)


def candidate_items(candidates):
    from .strategies import STRATEGIES
    mapping, items = {}, []
    for i, c in enumerate(candidates):
        ident = f'A{i+1}'
        mapping[ident] = c
        f, p = c['features'], c['plan']
        entry = p['entry_ref_tmn']
        items.append({
            'id': ident, 'pair': c['symbol'], 'strategy': c['strategy'], 'strategy_name': STRATEGIES[c['strategy']]['fa'],
            'family': c['family'],
            'stop_pct': _num(p['stop_fraction']*100), 'target_pct': _num((p['target_price_tmn']/entry-1)*100) if p.get('target_price_tmn') else None,
            'reward_risk_after_cost': _num(p['reward_risk']), 'max_holding_hours': p['max_holding_hours'],
            'r1_bps': _num(f['r1_bps']), 'r6_bps': _num(f['r6_bps']), 'r24_bps': _num(f['r24_bps']), 'vol24_bps': _num(f['vol24_bps']),
            'z24': _num(f.get('z24_logclose')), 'rsi14': _num(c['indicators'].get('rsi14')), 'atr_pct': _num(c['indicators'].get('atr_pct'), 3),
            'ema9_above_ema21': c['indicators'].get('ema9_above_ema21'),
            'roundtrip_cost_bps': _num(c['roundtrip_cost_bps']),
            'quality_score': c.get('quality'), 'confluence': c.get('confluence'),
            'trend_aligned': c['indicators'].get('trend_aligned'), 'volume_ratio': _num(c['indicators'].get('volume_ratio')),
            'missing_hours_of_72': c['indicators'].get('missing_hours'),
            'daily_turnover_million_tmn': _num(f['daily_turnover_tmn']/1e6),
            'setup': {k: (_num(v, 6) if isinstance(v, float) else v) for k, v in c['evidence'].items()}})
    return mapping, items


def validate(decision, ids):
    if not isinstance(decision, dict):
        raise ValueError('AI answer is not an object')
    missing = {'market_view', 'regime_assessment', 'decisions', 'priority'}-set(decision)
    if missing:
        raise ValueError('AI answer misses '+','.join(sorted(missing)))
    if decision['regime_assessment'] not in ASSESSMENTS:
        raise ValueError('Invalid regime assessment')
    if not isinstance(decision['market_view'], str) or len(decision['market_view']) > 1500:
        raise ValueError('Invalid market view')
    rows, seen = [], set()
    if not isinstance(decision['decisions'], list):
        raise ValueError('Decisions must be a list')
    for d in decision['decisions']:
        if not isinstance(d, dict) or d.get('id') not in ids or d['id'] in seen:
            raise ValueError('Unknown or duplicate candidate id')
        seen.add(d['id'])
        if d.get('action') not in {'enter', 'skip'}:
            raise ValueError('Invalid action')
        conf, size = d.get('confidence'), d.get('size', 1)
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            raise ValueError('Invalid confidence')
        if isinstance(size, bool) or not isinstance(size, (int, float)) or not 0 <= size <= 1:
            raise ValueError('Invalid size')
        reason = d.get('reason')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 800:
            raise ValueError('Missing reason')
        size_reason = d.get('size_reason')
        if size_reason is not None and (not isinstance(size_reason, str) or len(size_reason) > 800):
            raise ValueError('Invalid size reason')
        rows.append({'id': d['id'], 'action': d['action'], 'confidence': float(conf), 'size': float(size), 'reason': reason.strip(),
                     'size_reason': size_reason.strip() if size_reason else None})
    for ident in sorted(set(ids)-seen):
        rows.append({'id': ident, 'action': 'skip', 'confidence': 0.0, 'size': 0.0, 'reason': 'مدل برای این نامزد تصمیم صریحی برنگرداند؛ ورود انجام نمی‌شود.', 'implicit': True})
    priority = decision['priority']
    if not isinstance(priority, list) or any(p not in ids for p in priority) or len(set(priority)) != len(priority):
        raise ValueError('Invalid priority')
    return {'market_view': decision['market_view'], 'regime_assessment': decision['regime_assessment'],
            'decisions': rows, 'priority': priority}


class AdaptiveAI:
    def __init__(self, cache, *, replay_only=False, transport=request_json):
        self.cache, self.replay_only, self.calls, self.transport = cache, replay_only, 0, transport
        self.prompt = (ROOT/'prompts/adaptive-v4.md').read_text(encoding='utf-8')

    def preferred(self):
        path = self.cache/'ladder.json'
        try:
            return int(read_json(path).get('index', 0)) if file_exists(path) else 0
        except (OSError, ValueError):
            return 0

    def remember(self, index):
        write_json(self.cache/'ladder.json', {'index': index, 'at': time.time()})

    def select(self, candidates, cfg, context):
        if not candidates:
            return [], {'status': 'no_candidates', 'actual_api_call': False, 'decision': None}
        mapping, items = candidate_items(candidates)
        user = {'decision_time_utc': context.get('time'), 'regime': context.get('regime'),
                'portfolio': context.get('portfolio'), 'hours_to_deadline': context.get('hours_to_deadline'),
                'candidates': items, 'max_new_positions': context.get('max_new_positions')}
        base = {'model': cfg['ai_model'], 'messages': [{'role': 'system', 'content': self.prompt},
                {'role': 'user', 'content': canonical(user)}], 'response_format': {'type': 'json_object'}, 'temperature': 0}
        key = digest(base)
        path = self.cache/(key+'.json')
        if file_exists(path):
            record = read_json(path)
            if record.get('record_sha256') != digest({k: v for k, v in record.items() if k != 'record_sha256'}):
                raise ValueError('AI decision cache integrity failure')
            record['replayed'] = True
        elif self.replay_only:
            raise RuntimeError('No recorded AI decision for replay')
        else:
            record = self.request(base, key, cfg, mapping)
            write_json(path, record)
        return self.apply(record, mapping, cfg), record

    def request(self, base, key, cfg, mapping):
        record = {'request': base, 'request_hash': key, 'requested_at': time.time(), 'attempts': [],
                  'documented_backend': cfg.get('ai_model_documented_backend'), 'status': 'unavailable'}
        steps = ladder(cfg)
        start = min(self.preferred(), len(steps)-1)
        order = list(range(start, len(steps)))+list(range(0, start))
        for index in order[:3]:
            if self.calls >= cfg['ai_max_calls']:
                record['reason'] = 'call_budget'
                break
            step = steps[index]
            payload = {**base, **step['extra'], 'max_tokens': step['max_tokens']}
            attempt = {'variant': step['name'], 'max_tokens': step['max_tokens'], 'started_at': time.time()}
            self.calls += 1
            try:
                raw, meta = self.transport(ENDPOINT, headers={'Authorization': 'Bearer '+credential('AVALAI_API_KEY')},
                                           body=payload, timeout=cfg['ai_timeout_seconds'])
                choice = raw['choices'][0]
                message = choice.get('message') or {}
                content = message.get('content') or ''
                reasoning = message.get('reasoning_content') or message.get('reasoning') or ''
                attempt.update(http_status=meta.get('http_status'), finish_reason=choice.get('finish_reason'),
                               usage=raw.get('usage'), response_model=raw.get('model'), request_id=meta.get('request_id'),
                               content=redact(content[:12000]), reasoning_excerpt=redact(str(reasoning)[:6000]),
                               reasoning_chars=len(str(reasoning)), estimated_cost=raw.get('estimated_cost'))
                if choice.get('finish_reason') != 'stop' or not content.strip():
                    raise ValueError('Incomplete AI output ('+str(choice.get('finish_reason'))+')')
                text = content.strip()
                if text.startswith('```'):
                    text = text.strip('`')
                    text = text[text.find('{'):]
                decision = validate(json.loads(text[text.find('{'):text.rfind('}')+1]), mapping)
                attempt['status'] = 'ok'
                record.update(status='ok', decision=decision, variant=step['name'], response_model=raw.get('model'),
                              usage=raw.get('usage'), reasoning_excerpt=attempt['reasoning_excerpt'])
                record['attempts'].append(attempt)
                if index != self.preferred():
                    self.remember(index)
                break
            except Exception as exc:
                attempt.update(status='failed', error_type=type(exc).__name__,
                               error=str(exc)[:300] if isinstance(exc, (ValueError, KeyError, TypeError)) else None,
                               http_status=getattr(exc, 'status', attempt.get('http_status')))
                record['attempts'].append(attempt)
                status = getattr(exc, 'status', None)
                # Transport outage: do not burn more budget in this hour.
                if status == 0 or status in {401, 403, 429}:
                    break
            finally:
                attempt['latency_seconds'] = time.time()-attempt['started_at']
        record['latency_seconds'] = time.time()-record['requested_at']
        record['actual_api_calls'] = len(record['attempts'])
        record = redact(record)
        record['record_sha256'] = digest(record)
        return record

    def apply(self, record, mapping, cfg):
        if record.get('status') != 'ok':
            return []
        d = record['decision']
        caution = D_CAUTION.get(d['regime_assessment'], 1.0)
        by_id = {x['id']: x for x in d['decisions']}
        order = [i for i in d['priority'] if by_id.get(i, {}).get('action') == 'enter']
        order += sorted((x['id'] for x in d['decisions'] if x['action'] == 'enter' and x['id'] not in order),
                        key=lambda i: -by_id[i]['confidence'])
        chosen = []
        for i in order:
            row = by_id[i]
            if row['confidence'] < cfg['ai_min_confidence']:
                continue
            c = dict(mapping[i])
            c['ai_size'] = max(0.25, min(1.0, row['size']*caution))
            c['ai_confidence'] = row['confidence']
            c['ai_reason'] = row['reason']
            c['ai_size_reason'] = row.get('size_reason')
            c['ai_id'] = i
            chosen.append(c)
        return chosen


D_CAUTION = {'agree': 1.0, 'more_cautious': 0.5, 'more_aggressive': 1.0}
