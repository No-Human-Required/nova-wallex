"""Keeps the web process and the bot runner alive inside one container."""
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUNG_AFTER = 180  # seconds without a runner heartbeat: the runner is stuck, restart it
SPECS = {'web': [sys.executable, '-m', 'algo.serve'], 'runner': [sys.executable, '-m', 'algo.runner']}


def main():
    children, started, stopping = {}, {}, False

    def stop(*_):
        nonlocal stopping
        stopping = True
        for p in children.values():
            p.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    from .db import data_dir
    from .runner import HEARTBEAT_FILE
    beat = data_dir()/HEARTBEAT_FILE
    while not stopping:
        # A runner that is alive but stuck (no heartbeat) is restarted like a crashed one.
        p = children.get('runner')
        if p is not None and p.poll() is None and time.monotonic()-started.get('runner', 0) > HUNG_AFTER:
            try:
                hung = time.time()-beat.stat().st_mtime > HUNG_AFTER
            except OSError:
                hung = False
            if hung:
                p.kill()
                p.wait(timeout=10)
        for name, command in SPECS.items():
            p = children.get(name)
            if p is None or p.poll() is not None:
                if p is not None and time.monotonic()-started.get(name, 0) < 10:
                    time.sleep(5)  # crash loop: back off
                children[name] = subprocess.Popen(command, cwd=ROOT)
                started[name] = time.monotonic()
        time.sleep(2)
    for p in children.values():
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()


if __name__ == '__main__':
    main()
