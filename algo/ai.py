"""AI entry filter for user bots: platform LLM key, per-user monthly quota.

The candidates, prompt, request ladder and answer validation are Nova's
``AdaptiveAI``. Each request attempt counts against the user's monthly quota
(plan ``ai_calls_month``, or a per-user override set in the back office). When
the filter is unavailable or the quota is spent the bot makes no entry that
bar: it never trades around a missing AI decision.
"""
import json
import time

from execution import ai_decision
from .db import new_id

_lock = __import__('threading').Lock()


def month(now=None):
    return time.strftime('%Y-%m', time.gmtime(now or time.time()))


def quota(db, user_id, now=None):
    u = db.one('SELECT * FROM users WHERE id=?', (user_id,))
    plan = db.one('SELECT * FROM plans WHERE id=?', (u['plan_id'],)) if u and u['plan_id'] else None
    active = plan and (u['plan_expires'] is None or u['plan_expires'] > (now or time.time()))
    limit = u['ai_quota_override'] if u and u['ai_quota_override'] is not None else (plan['ai_calls_month'] if active else 0)
    used = (db.one('SELECT calls FROM ai_usage WHERE user_id=? AND month=?', (user_id, month(now))) or {}).get('calls', 0)
    return int(limit or 0), int(used)


class AIFilter:
    def __init__(self, db, settings, cache, transport=None, clock=time.time):
        self.db, self.s, self.cache, self.transport, self.clock = db, settings, cache, transport, clock

    def event(self, bot, kind, detail):
        self.db.run('INSERT INTO bot_events(id,bot_id,at,kind,detail) VALUES(?,?,?,?,?)',
                    (new_id(), bot['id'], self.clock(), kind, json.dumps(detail, ensure_ascii=False, default=str)))

    def __call__(self, bot, candidates, regime, cfg):
        key = self.s.get('llm.api_key')
        if not self.s.get('llm.enabled') or not key:
            self.event(bot, 'ai_unavailable', {'reason': 'platform_ai_not_configured'})
            return []
        limit, used = quota(self.db, bot['user_id'], self.clock())
        if used >= limit:
            self.event(bot, 'ai_quota_exhausted', {'limit': limit, 'used': used})
            return []
        state = json.loads(bot['state'])
        ai_cfg = {'ai_model': self.s.get('llm.model'), 'ai_provider': self.s.get('llm.provider'),
                  'ai_base_url': self.s.get('llm.base_url') or None, 'ai_timeout_seconds': 60, 'ai_max_calls': 10**9,
                  'ai_min_confidence': cfg['ai_min_confidence']}
        ctx = {'time': int(self.clock())//3600*3600,
               'regime': {'regime': regime or 'unfiltered', 'max_positions': cfg['max_positions']},
               'portfolio': {'cash_tmn': state['cash_tmn'],
                             'positions': [{'asset': s, 'qty': p['qty'], 'basis_tmn': p['cost'], 'strategy': p.get('strategy')}
                                           for s, p in state['positions'].items()]},
               'hours_to_deadline': None, 'max_new_positions': max(0, cfg['max_positions']-len(state['positions']))}
        ai = ai_decision.AdaptiveAI(self.cache, **({'transport': self.transport} if self.transport else {}))
        with _lock:
            original = ai_decision.api_key
            ai_decision.api_key = lambda: key
            try:
                ranked, record = ai.select(candidates, ai_cfg, ctx)
            except Exception as exc:
                ranked, record = [], {'status': 'unavailable', 'reason': type(exc).__name__, 'actual_api_calls': 0}
            finally:
                ai_decision.api_key = original
        calls = 0 if record.get('replayed') else int(record.get('actual_api_calls') or 0)
        if calls:
            self.db.run('INSERT INTO ai_usage(user_id,month,calls) VALUES(?,?,?) ON CONFLICT(user_id,month) DO UPDATE SET calls=ai_usage.calls+excluded.calls',
                        (bot['user_id'], month(self.clock()), calls))
        decision = record.get('decision') or {}
        self.event(bot, 'ai_decision', {'status': record.get('status'), 'calls': calls, 'market_view': decision.get('market_view'),
                                        'decisions': [{k: d.get(k) for k in ('id', 'action', 'confidence', 'size', 'reason')} for d in decision.get('decisions') or []],
                                        'candidates': [c['symbol'] for c in candidates]})
        return ranked
