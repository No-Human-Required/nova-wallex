"""Keeps the web process and the bot runner alive inside one container."""
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
    while not stopping:
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
