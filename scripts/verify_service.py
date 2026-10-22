"""Real subprocess crash/restart test, HTTP controls and independent replay parity."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from starwallex.util import ROOT, read_json, write_json


def request(path,body=None,csrf=None):
    headers={'Origin':'http://127.0.0.1:8789','Content-Type':'application/json','Idempotency-Key':'crash-recovery-test'}
    if csrf:headers['X-CSRF-Token']=csrf
    req=urllib.request.Request('http://127.0.0.1:8789'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)


def boot(directory, log):
    env=dict(os.environ,SW_ENV='development',SW_PUBLIC_ORIGIN='http://127.0.0.1:8789',SW_DATA_DIR=str(directory),PYTHONHASHSEED='17')
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8789','--no-access-log'],
            cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        for _ in range(200):
            if process.poll() is not None:raise RuntimeError('Service exited during startup')
            try:
                if request('/readyz')['ready']:return process
            except Exception:pass
            time.sleep(.1)
        raise RuntimeError('Service startup timed out')
    except BaseException:
        process.terminate();process.wait(timeout=10);raise


def verify():
    result={}
    with tempfile.TemporaryDirectory(prefix='starwallex-http-') as tmp:
        root=Path(tmp);proc=None
        with open(root/'service.log','w',encoding='utf-8') as log:
            try:
                started=time.monotonic();proc=boot(root/'state',log)
                result['cold_start_seconds']=round(time.monotonic()-started,3)
                csrf=request('/api/session')['csrf']
                job=request('/api/jobs',{'variant':'guarded_breakout_ai','window':32,'scenario':'base'},csrf)
                duplicate=request('/api/jobs',{'variant':'guarded_breakout_ai','window':32,'scenario':'base'},csrf)
                assert job['id']==duplicate['id']
                for _ in range(400):
                    status=request('/api/jobs')[0]
                    if status['progress']>=12:break
                    if status['status']=='failed':raise AssertionError(status)
                    time.sleep(.025)
                assert 0<status['progress']<72,status
                result['killed_after_committed_hours']=status['progress']
                # Abrupt OS termination, not a graceful shutdown or a DB-only reopen.
                proc.kill();proc.wait(timeout=10);proc=None
                proc=boot(root/'state',log)
                paused=request('/api/jobs')[0]
                assert paused['status']=='paused',paused
                result['restart_state']=paused['status']
                csrf=request('/api/session')['csrf']
                request(f'/api/jobs/{job["id"]}/control',{'action':'resume'},csrf)
                for _ in range(600):
                    status=request('/api/jobs')[0]
                    if status['status']=='completed':break
                    if status['status']=='failed':raise AssertionError(status)
                    time.sleep(.1)
                assert status['status']=='completed',status
                actual=request(f'/api/jobs/{job["id"]}')['snapshot']['summary']
                expected=read_json(ROOT/'seed/cases/w32-guarded_breakout_ai-base.json')['summary']
                keys=['audit','cash_tmn','final_nav_tmn','realized_pnl_tmn','unrealized_pnl_tmn','fees_tmn','fill_count','positions','fx_lots','pending_orders']
                for k in keys:assert actual[k]==expected[k],k
                result.update(exact_financial_and_audit_parity=True,chain_head=actual['audit']['chain_head'],
                              duplicate_request_one_job=True,hours=72,real_exchange_orders=0,
                              test='abrupt_process_kill_restart_resume_via_http',all_passed=True)
            finally:
                if proc:proc.terminate();proc.wait(timeout=15)
    write_json(ROOT/'evidence/service-crash-recovery.json',result)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':verify()
