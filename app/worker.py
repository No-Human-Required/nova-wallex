import threading
import time

from .research import finish
from .custom_research import setup
from starwallex.util import source_manifest


class Worker:
    def __init__(self, store, history):
        self.store, self.history = store, history
        self.stop = threading.Event()
        self.heartbeat = time.time()
        self.current = None
        self.thread = threading.Thread(target=self.loop, name='research-worker', daemon=True)

    def loop(self):
        while not self.stop.is_set():
            self.heartbeat = time.time()
            job = self.store.claim()
            if not job:
                self.stop.wait(0.3)
                continue
            self.current = job['id']
            audit = None
            try:
                spec = job['spec']
                if spec['source_sha256'] != source_manifest()['sha256'] or spec['dataset_identity'] != self.history.identity:
                    raise ValueError('Source or dataset changed; create a new job')
                directory = self.store.directory/'jobs'/job['id']
                engine, audit, start, end = setup(self.history, spec['variant'], spec['window'], spec['scenario'], directory, spec.get('start_utc'), spec.get('end_utc'))
                for step, t in enumerate(range(start, end, 3600)):
                    self.heartbeat = time.time()
                    if self.stop.is_set() or self.store.get(job['id'])['status'] != 'running':
                        break
                    engine.tick(t, start)
                    self.store.progress(job['id'], step+1)
                else:
                    finish(engine, end, directory, spec | {'start':start, 'end':end, 'case':job['id']})
                    self.store.terminal(job['id'], 'completed')
            except Exception as exc:
                # Never persist credential/HTTP bodies or arbitrary exception text.
                self.store.terminal(job['id'], 'failed', type(exc).__name__)
            finally:
                if audit:
                    audit.close()
                self.current = None

    def close(self):
        self.stop.set()
        self.thread.join(timeout=30)
        if self.thread.is_alive():
            raise RuntimeError('Worker did not reach a safe checkpoint')
