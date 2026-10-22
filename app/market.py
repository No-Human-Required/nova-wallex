"""Public, read-only ticker monitor. No simulated or real portfolio is advanced."""
import threading
import time

from starwallex.net import request_json


class MarketMonitor:
    def __init__(self, history, store):
        self.history, self.store = history, store
        self.enabled = False
        self.data = {'status':'stopped', 'received_at':None, 'rows':[], 'error':None}
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.loop, name='public-market-monitor', daemon=True)

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled = enabled
            self.data['status'] = 'waiting' if enabled else 'stopped'
        self.store.log('public_monitor', {'enabled':enabled, 'exchange_orders':False})

    def snapshot(self):
        with self.lock:
            return {**self.data, 'enabled':self.enabled, 'age_seconds':time.time()-self.data['received_at'] if self.data['received_at'] else None}

    def fetch(self):
        raw, _ = request_json('https://api.wallex.ir/v1/markets', timeout=15, attempts=1)
        symbols = raw['result']['symbols']
        rows = []
        for symbol in self.history.markets:
            item = symbols.get(symbol)
            if item:
                stats = item.get('stats', {})
                rows.append({'symbol':symbol, 'last_price':stats.get('lastPrice'),
                             'change_24h':stats.get('24h_ch'), 'volume_24h':stats.get('24h_volume')})
        if not rows:
            raise ValueError('No allowed markets in public response')
        with self.lock:
            self.data = {'status':'ok' if self.enabled else 'stopped', 'received_at':time.time(),
                         'rows':rows, 'error':None, 'timestamp_kind':'local_receipt_not_exchange_time'}

    def loop(self):
        last = 0
        while not self.stop.is_set():
            if self.enabled and time.monotonic()-last >= 60:
                try:
                    self.fetch()
                except Exception as exc:
                    with self.lock:
                        self.data.update(status='error', error=type(exc).__name__)
                last = time.monotonic()
            self.stop.wait(0.5)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=20)
