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
BALANCE_CHECK_SECONDS = 600
FAILING_ALERT_SECONDS = 900   # a bot that errors this long without one good cycle is reported
HOUSEKEEPING_SECONDS = 6*3600
HEARTBEAT_FILE = 'runner.heartbeat'
BALANCE_TOLERANCE = 0.995
ACTIVE = ('running', 'paused', 'closing', 'scheduled')


def plan_allows_live(db, user, now):
    plan = db.one('SELECT * FROM plans WHERE id=?', (user['plan_id'],)) if user['plan_id'] else None
    return bool(plan and plan['max_live_bots'] > 0 and (user['plan_expires'] is None or user['plan_expires'] > now))


class Runner:
    def __init__(self, db, settings, secrets, market, ai=None, clock=time.time, notifier=None, workers=0, heartbeat=None):
        self.db, self.s, self.secrets, self.market, self.clock = db, settings, secrets, market, clock
        self.notifier = notifier
        # workers > 0: bots cycle in parallel (one slow AI or exchange call never delays another bot's stops);
        # a bot never has two cycles at once.
        from concurrent.futures import ThreadPoolExecutor
        self.pool = ThreadPoolExecutor(workers, thread_name_prefix='bot') if workers else None
        self.inflight, self.failing, self.heartbeat = {}, {}, heartbeat
        self.housekept = 0
        self.executor = Executor(db, market, ai=ai, clock=clock, notify=notifier.on_event if notifier else None)
        if ai is not None and notifier is not None:
            ai.notify = notifier.on_event
        self.next = {}
        self.balance_checked = 0

    def gateway(self, bot):
        cfg = json.loads(bot['config'])
        margin = cfg.get('market_type') == 'margin'
        if bot['mode'] == 'paper':
            if margin:
                from .margin import PaperMargin
                return PaperMargin(self.db, bot['id'], self.market, cfg, clock=self.clock)
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
        if margin:
            from .margin import MarginGateway, MarginLive, PREFIX
            secret = self.secrets.decrypt(key['cipher'])

            def margin_authorize(method, path, body):
                # Opens only for this bot's own SUBMITTING row; closes and stop moves only for its own positions.
                if not (self.s.get('platform.live_trading_enabled') and self.s.get('platform.margin_enabled')) and method == 'POST':
                    return False
                if method == 'POST' and path == PREFIX+'/positions' and isinstance(body, dict):
                    rows = self.db.all("SELECT intent FROM bot_orders WHERE bot_id=? AND phase='SUBMITTING' AND symbol=?", (bot_id, body.get('market')))
                    return any(json.loads(r['intent']).get('kind') == 'margin_open' and not json.loads(r['intent']).get('pid') for r in rows)
                if method == 'PATCH' and path.startswith(PREFIX+'/positions/') and path.endswith(('/close', '/sltp')):
                    pid = path[len(PREFIX+'/positions/'):].rsplit('/', 1)[0]
                    state = json.loads(self.db.one('SELECT state FROM bots WHERE id=?', (bot_id,))['state'])
                    if any(str(p.get('pid')) == pid for p in state['positions'].values()):
                        return True
                    return any(str(json.loads(r['intent']).get('pid')) == pid for r in
                               self.db.all("SELECT intent FROM bot_orders WHERE bot_id=? AND phase IN ('SUBMITTING','OPEN','UNKNOWN')", (bot_id,)))
                return False
            g._authorizer = lambda *a: False  # the spot key is only read (free TMN balance)
            return MarginLive(MarginGateway(secret, write_authorizer=margin_authorize), g)
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
        if bot['mode'] == 'live' and json.loads(bot['config']).get('market_type') == 'margin' and not self.s.get('platform.margin_enabled'):
            entries = False  # margin switch off: live margin bots only manage their exits
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
            from .notify import PAUSED_BY_BALE
            self.db.run('UPDATE bots SET last_error=NULL WHERE id=? AND last_error IS NOT NULL AND last_error!=?', (bot['id'], PAUSED_BY_BALE))

    def stop(self, bot, status, error):
        self.db.run('UPDATE bots SET status=?,last_error=?,updated=? WHERE id=?', (status, error, self.clock(), bot['id']))
        self.executor.event(bot, 'bot_'+status, {'reason': error})

    def reconcile_balances(self):
        """Live spot bots: the exchange must hold at least what the bots' own ledgers say they hold.

        Bots sharing one API key are checked together. A shortfall (manual
        trading, a transfer, a bot on the same account outside the platform)
        stops new entries of those bots and alerts the user and the admins;
        nothing is sold automatically.
        """
        now = self.clock()
        if now-self.balance_checked < BALANCE_CHECK_SECONDS:
            return []
        self.balance_checked = now
        groups = {}
        for b in self.db.all("SELECT * FROM bots WHERE mode='live' AND status IN ('running','paused','closing') AND key_id IS NOT NULL"):
            if json.loads(b['config']).get('market_type') != 'margin':
                groups.setdefault(b['key_id'], []).append(b)
        markets = exchanges.wallex_markets()
        flagged = []
        for key_id, bots in groups.items():
            expected = {}
            for b in bots:
                for sym, p in json.loads(b['state'])['positions'].items():
                    base = markets[sym].base if sym in markets else sym
                    expected[base] = expected.get(base, 0)+float(p['qty'])
            if not expected:
                continue
            try:
                r = self.gateway(bots[0]).main_balances()
                balances = ((r or {}).get('result') or {}).get('balances') or {}
            except Exception:
                continue
            short = {a: (q, float((balances.get(a) or {}).get('value') or 0)) for a, q in expected.items()
                     if float((balances.get(a) or {}).get('value') or 0) < q*BALANCE_TOLERANCE}
            if not short:
                continue
            detail = '، '.join(f'{a}: دفتر ربات {q:.8g} / صرافی {have:.8g}' for a, (q, have) in short.items())
            for b in bots:
                if b['status'] != 'running':
                    continue  # already exits-only: alert once, when entries are stopped
                self.db.run("UPDATE bots SET status='paused',last_error=?,updated=? WHERE id=?",
                            ('موجودی صرافی کمتر از دفتر ربات است؛ ورود جدید متوقف شد', now, b['id']))
                self.executor.event(b, 'balance_mismatch', {'detail': detail, 'key_id': key_id})
                flagged.append(b['id'])
        return flagged

    def cycle(self, bot):
        """One bot cycle with error bookkeeping: transient errors retry next cycle; a long streak is reported once."""
        try:
            self.run_bot(bot)
            self.failing.pop(bot['id'], None)
        except Exception as exc:  # network or data: retry next cycle, keep the bot
            reason = 'خطای موقت: '+type(exc).__name__
            self.db.run('UPDATE bots SET last_error=? WHERE id=?', (reason, bot['id']))
            first, alerted = self.failing.get(bot['id'], (self.clock(), False))
            if not alerted and self.clock()-first >= FAILING_ALERT_SECONDS:
                self.executor.event(bot, 'bot_failing', {'reason': reason, 'since': first})
                alerted = True
            self.failing[bot['id']] = (first, alerted)

    def housekeeping(self):
        """Drop rows nobody reads any more (sent messages, old login logs, expired sessions and codes)."""
        now = self.clock()
        if now-self.housekept < HOUSEKEEPING_SECONDS:
            return
        self.housekept = now
        for sql, args in (('DELETE FROM notifications WHERE sent IS NOT NULL AND sent<?', (now-30*86400,)),
                          ('DELETE FROM notifications WHERE sent IS NULL AND attempts>=6 AND created<?', (now-30*86400,)),
                          ('DELETE FROM otp_log WHERE at<?', (now-30*86400,)), ('DELETE FROM sessions WHERE expires<?', (now,)),
                          ('DELETE FROM bale_codes WHERE expires<?', (now,)), ('DELETE FROM otp_codes WHERE expires<?', (now-86400,)),
                          ("DELETE FROM bot_events WHERE at<? AND kind NOT IN ('trade_closed','bot_blocked','balance_mismatch')", (now-180*86400,))):
            self.db.run(sql, args)

    def beat(self):
        now = self.clock()
        self.db.run('INSERT INTO settings(key,value,updated,updated_by) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated=excluded.updated',
                    ('runner._heartbeat', json.dumps(now), now, 'runner'))
        if self.heartbeat:
            self.heartbeat.touch()

    def tick(self):
        now = self.clock()
        for step in (self.reconcile_balances, self.housekeeping, self.notifier.tick if self.notifier else None):
            if step:
                try:
                    step()
                except Exception:
                    pass
        marks = ','.join('?'*len(ACTIVE))
        for bot in self.db.all(f'SELECT * FROM bots WHERE status IN ({marks})', ACTIVE):
            if self.next.get(bot['id'], 0) > now:
                continue
            busy = self.inflight.get(bot['id'])
            if busy is not None and not busy.done():
                continue  # its previous cycle is still running (slow AI or exchange): never two at once
            self.next[bot['id']] = now+CYCLE_SECONDS
            if self.pool:
                self.inflight[bot['id']] = self.pool.submit(self.cycle, bot)
            else:
                self.cycle(bot)
        try:
            self.beat()
        except Exception:
            pass


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
    from .notify import Notifier
    runner = Runner(db, settings, secrets, market, ai=AIFilter(db, settings, cache_root()/'algo-ai'), notifier=Notifier(db, settings, secrets),
                    workers=int(os.getenv('ALGO_RUNNER_WORKERS', '6')), heartbeat=directory/HEARTBEAT_FILE)
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
