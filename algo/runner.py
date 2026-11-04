"""Bot runner: one process, every running bot cycled about every 30 seconds.

A bot runs only while its owner is active. A live bot additionally needs admin
approval, the global "live trading" switch, an active plan that allows live
bots and a verified exchange key. New entries also need the global "new
entries" switch and a bot status of ``running`` (``paused`` manages exits
only). Any contract or ledger doubt blocks the bot for review instead of
guessing.
"""
import json
import os
import signal
import threading
import time

from .db import Database, data_dir
from .crypto import Secrets
from .settings import Settings
from .executor import Executor, PaperGateway, MarketData, BotBlocked
from .ai import AIFilter
from . import exchanges

CYCLE_SECONDS = 30
ACTIVE = ('running', 'paused', 'closing', 'scheduled')


def plan_allows_live(db, user, now):
    plan = db.one('SELECT * FROM plans WHERE id=?', (user['plan_id'],)) if user['plan_id'] else None
    return bool(plan and plan['max_live_bots'] > 0 and (user['plan_expires'] is None or user['plan_expires'] > now))


class Runner:
    def __init__(self, db, settings, secrets, market, ai=None, clock=time.time):
        self.db, self.s, self.secrets, self.market, self.clock = db, settings, secrets, market, clock
        self.executor = Executor(db, market, ai=ai, clock=clock)
        self.next = {}

    def gateway(self, bot):
        if bot['mode'] == 'paper':
            cfg = json.loads(bot['config'])
            return PaperGateway(self.market, cfg['fee_tmn_bps']/10000)
        key = self.db.one('SELECT * FROM exchange_keys WHERE id=? AND user_id=?', (bot['key_id'], bot['user_id']))
        if not key or key['status'] != 'verified':
            raise BotBlocked('کلید API صرافی برای این ربات معتبر نیست')
        g = exchanges.gateway(bot['exchange'], self.secrets.decrypt(key['cipher']))
        bot_id = bot['id']

        def authorize(method, path, body):
            # Only an order row this bot wrote as SUBMITTING (or a cancel of its own open order) may be sent.
            if method == 'POST' and path == '/v1/account/orders' and isinstance(body, dict):
                row = self.db.one('SELECT phase FROM bot_orders WHERE client_id=? AND bot_id=?', (body.get('client_id'), bot_id))
                return bool(row and row['phase'] == 'SUBMITTING') and self.s.get('platform.live_trading_enabled')
            if method == 'DELETE' and path.startswith('/v1/account/orders/'):
                row = self.db.one('SELECT phase FROM bot_orders WHERE client_id=? AND bot_id=?', (path.rsplit('/', 1)[-1], bot_id))
                return bool(row and row['phase'] in ('OPEN', 'PARTIAL'))
            return False
        g._authorizer = authorize
        return g

    def schedule(self, bot, now):
        """Apply the bot's run window; returns the (possibly updated) bot row or None when nothing runs now."""
        sched = json.loads(bot['config']).get('schedule') or {}
        start, until = sched.get('from'), sched.get('until')
        if bot['status'] == 'scheduled':
            if until and now >= until:
                self.stop(bot, 'stopped', 'بازهٔ زمانی ربات پیش از شروع تمام شد')
                return None
            if start and now < start:
                return None
            self.db.run("UPDATE bots SET status='running',started=COALESCE(started,?),updated=? WHERE id=? AND status='scheduled'", (now, now, bot['id']))
            self.executor.event(bot, 'schedule_started', {'from': start})
            return self.db.one('SELECT * FROM bots WHERE id=?', (bot['id'],))
        if until and now >= until and bot['status'] == 'running':
            action = sched.get('end_action') or 'close'
            state = json.loads(bot['state'])
            if not state['positions'] and not self.executor.orders(bot, ('SUBMITTING', 'UNKNOWN', 'OPEN', 'PARTIAL')):
                self.stop(bot, 'stopped', None)
                self.executor.event(bot, 'schedule_ended', {'until': until, 'action': 'stopped_flat'})
                return None
            status = 'closing' if action == 'close' else 'paused'
            self.db.run('UPDATE bots SET status=?,updated=? WHERE id=?', (status, now, bot['id']))
            self.executor.event(bot, 'schedule_ended', {'until': until, 'action': action})
            return self.db.one('SELECT * FROM bots WHERE id=?', (bot['id'],))
        return bot

    def run_bot(self, bot):
        now = self.clock()
        user = self.db.one('SELECT * FROM users WHERE id=?', (bot['user_id'],))
        if not user or user['status'] != 'active':
            self.stop(bot, 'stopped', 'حساب کاربر فعال نیست')
            return
        bot = self.schedule(bot, now)
        if bot is None:
            return
        if bot['mode'] == 'live':
            if not bot['live_approved']:
                self.stop(bot, 'stopped', 'اجرای واقعی تأیید ادمین ندارد')
                return
            if not self.s.get('platform.live_trading_enabled'):
                return  # global switch: nothing is sent; positions stay at the exchange
            if not plan_allows_live(self.db, user, now) and bot['status'] == 'running':
                self.db.run("UPDATE bots SET status='paused',last_error=? WHERE id=?", ('پلن فعال برای اجرای واقعی ندارد؛ فقط مدیریت خروج', bot['id']))
                bot = self.db.one('SELECT * FROM bots WHERE id=?', (bot['id'],))
        entries = bot['status'] == 'running' and self.s.get('platform.new_entries_enabled')
        try:
            result = self.executor.cycle(bot, self.gateway(bot), entries_allowed=entries, flatten=bot['status'] == 'closing')
        except BotBlocked as exc:
            self.stop(bot, 'blocked', str(exc))
            return
        until = (json.loads(bot['config']).get('schedule') or {}).get('until')
        if bot['status'] == 'closing' or (bot['status'] == 'paused' and until and now >= until):
            state = json.loads(self.db.one('SELECT state FROM bots WHERE id=?', (bot['id'],))['state'])
            if not state['positions'] and not self.executor.orders(bot, ('SUBMITTING', 'UNKNOWN', 'OPEN', 'PARTIAL')):
                self.stop(bot, 'stopped', None)
        elif result.get('status') == 'ok':
            self.db.run('UPDATE bots SET last_error=NULL WHERE id=? AND last_error IS NOT NULL', (bot['id'],))

    def stop(self, bot, status, error):
        self.db.run('UPDATE bots SET status=?,last_error=?,updated=? WHERE id=?', (status, error, self.clock(), bot['id']))
        self.executor.event(bot, 'bot_'+status, {'reason': error})

    def tick(self):
        now = self.clock()
        marks = ','.join('?'*len(ACTIVE))
        for bot in self.db.all(f'SELECT * FROM bots WHERE status IN ({marks})', ACTIVE):
            if self.next.get(bot['id'], 0) > now:
                continue
            self.next[bot['id']] = now+CYCLE_SECONDS
            try:
                self.run_bot(bot)
            except Exception as exc:  # network or data: retry next cycle, keep the bot
                self.db.run('UPDATE bots SET last_error=? WHERE id=?', ('خطای موقت: '+type(exc).__name__, bot['id']))


def main():
    from app.store import ProcessLock
    from app.lab_data import WallexCandles
    from app.screener import cache_root
    directory = data_dir()
    lock = ProcessLock(directory/'runner')
    db = Database(directory)
    secrets = Secrets()
    settings = Settings(db, secrets)
    market = MarketData(WallexCandles(cache_root()/'candles'))
    runner = Runner(db, settings, secrets, market, ai=AIFilter(db, settings, cache_root()/'algo-ai'))
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        while not stop.is_set():
            runner.tick()
            stop.wait(5)
    finally:
        lock.close()


if __name__ == '__main__':
    main()
