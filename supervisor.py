"""Two independent processes in one persistent-volume service, with bounded backoff."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    from app.store import Store, ProcessLock
    from app.live_store import LiveStore
    from app.vault import Vault
    from starwallex.persistence import enabled
    if os.getenv('SW_REQUIRE_POSTGRES')=='1' and not enabled():
        raise RuntimeError('PostgreSQL URL required; no local database fallback')
    data=Path(os.getenv('SW_DATA_DIR',str(root/'var')))
    service_lock=ProcessLock(data/'supervisor-lock')
    store=Store(data);LiveStore(store)
    Vault(store,os.getenv('SW_ENV')=='development')
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
    specs={'web':[sys.executable,'run.py'],'engine':[sys.executable,'-m','app.live_engine']}
    children={};failures={k:0 for k in specs};started={};retry={k:0 for k in specs}
    try:
        while not stopping:
            service_lock.assert_held()
            for name,command in specs.items():
                p=children.get(name)
                if p is not None and p.poll() is not None:
                    failures[name]=0 if time.monotonic()-started[name]>120 else failures[name]+1
                    retry[name]=time.monotonic()+min(30,2**min(failures[name],5));children.pop(name)
                    print(name+' exited; restarting after backoff',flush=True)
                if name not in children and time.monotonic()>=retry[name]:
                    children[name]=subprocess.Popen(command,cwd=root);started[name]=time.monotonic()
            time.sleep(.5)
    finally:
        for p in children.values():
            if p.poll() is None:p.terminate()
        for p in children.values():
            try:p.wait(timeout=20)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        service_lock.close()

if __name__=='__main__':main()
