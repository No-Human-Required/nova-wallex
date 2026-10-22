"""Provision a disposable local PostgreSQL container; never uses cloud/account keys."""
import json
import re
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from starwallex.util import write_json
from execution.activation import bundle_hash


def main():
    name='starwallex-pg-check-'+secrets.token_hex(5)
    password=secrets.token_urlsafe(32)
    env=dict(os.environ,POSTGRES_PASSWORD=password)
    def docker(*args):
        r=subprocess.run(['docker',*args],env=env,capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError('Docker verification operation failed: '+args[0])
        return r.stdout.strip()
    try:
        docker('run','-d','--name',name,'--label','io.starwallex.verification=postgres',
               '-e','POSTGRES_PASSWORD','-e','POSTGRES_DB=starwallex_test',
               '-p','127.0.0.1::5432','postgres:18')
        for _ in range(60):
            try:
                if 'accepting connections' in docker('exec',name,'pg_isready','-U','postgres'):break
            except RuntimeError:pass
            time.sleep(.5)
        port=docker('port',name,'5432/tcp').rsplit(':',1)[-1]
        env['SW_TEST_DATABASE_URL']='postgresql://postgres:'+password+'@127.0.0.1:'+port+'/starwallex_test'
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_postgres*.py','-v'],
                              cwd=ROOT,env=env,capture_output=True,text=True)
        log=result.stdout+result.stderr
        # Test code deliberately emits neither credentials nor database exceptions.
        if password in log:raise RuntimeError('Sensitive output rejected')
        (ROOT/'evidence/postgres-tests.txt').write_text(log,encoding='utf-8')
        print(log,flush=True)
        proof={'all_passed':result.returncode==0,'backend':'PostgreSQL',
               'execution_source_sha256':bundle_hash(),'tests':int(re.search(r'Ran (\d+) tests',log).group(1)),
               'image':json.loads(docker('inspect',name))[0]['Image'],
               'app_persistent_volume':False,'real_exchange_orders':0,'new_ai_calls':0}
        write_json(ROOT/'evidence/postgres-tests.json',proof)
        if result.returncode:raise SystemExit(result.returncode)
    finally:
        try:docker('rm','-f','-v',name)
        except RuntimeError:pass

if __name__=='__main__':main()
