"""Same production HTTP/crash checks, using PostgreSQL and disposable app tmpfs."""
import argparse
import secrets
import time
from pathlib import Path
from cryptography.fernet import Fernet
from verify_container import Verification, ROOT, LABEL
from app.version import VERSION


class PostgresVerification(Verification):
    def __init__(self,*args):
        super().__init__(*args)
        self.network=self.ident+'-network'
        self.db_name=self.ident+'-postgres'
        self.db_password=secrets.token_urlsafe(32)
        self.vault_key=Fernet.generate_key().decode()
        self.result.update(database_backend='postgresql',app_persistent_volume=False)

    def run_container(self,envfile,name,publish=True):
        # Ephemeral, private file; none of these values are source/ZIP/log output.
        base=envfile.read_text(encoding='utf-8').replace('SW_REQUIRE_POSTGRES=0','SW_REQUIRE_POSTGRES=1')
        if 'SW_DATABASE_URL=' not in base:
            base+=('SW_DATABASE_URL=postgresql://postgres:'+self.db_password+'@'+self.db_name+':5432/starwallex_test\n'
                   'SW_VAULT_KEY='+self.vault_key+'\n')
            envfile.write_text(base,encoding='utf-8')
        args=['run','-d','--name',name,'--label',LABEL+'='+self.ident,'--network',self.network,
              '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
              '--memory=1g','--cpus=1','--pids-limit=128',
              '--tmpfs','/tmp:rw,noexec,nosuid,size=32m',
              '--tmpfs','/data:rw,noexec,nosuid,size=64m,uid=10001,gid=10001,mode=0700',
              '--env-file',str(envfile),'--health-interval=2s','--health-start-period=10s','--stop-timeout=35']
        if publish:args+=['--publish','127.0.0.1::8080']
        self.docker(*args,self.image);self.containers.append(name)

    def execute(self):
        import os,tempfile
        self.docker('network','create','--label',LABEL+'='+self.ident,self.network)
        with tempfile.TemporaryDirectory() as temp:
            env=Path(temp)/'pg.env'
            env.write_text('POSTGRES_PASSWORD='+self.db_password+'\nPOSTGRES_DB=starwallex_test\n',encoding='utf-8')
            self.docker('run','-d','--name',self.db_name,'--label',LABEL+'='+self.ident,
                        '--network',self.network,'--env-file',str(env),'postgres:18')
        self.containers.append(self.db_name)
        for _ in range(60):
            r=self.docker('exec',self.db_name,'pg_isready','-U','postgres',check=False)
            if r.returncode==0:break
            time.sleep(.5)
        super().execute()

    def cleanup(self):
        # PostgreSQL's implicit test volume is owned by this labelled container.
        if self.db_name in self.containers:
            db=self.inspect(self.db_name)
            if db['Config']['Labels'].get(LABEL)!=self.ident:raise RuntimeError('Wrong test DB owner')
            self.docker('rm','-f','-v',self.db_name);self.containers.remove(self.db_name)
        super().cleanup()
        self.docker('network','rm',self.network)
        for d in self.result.get('failure_diagnostics',[]):
            d['logs']=d['logs'].replace(self.db_password,'[TEST_DB_PASSWORD]').replace(self.vault_key,'[TEST_VAULT_KEY]')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',default='starwallex-control:'+VERSION)
    p.add_argument('--out',default=str(ROOT/('evidence/container-v'+VERSION+'.json')))
    a=p.parse_args();PostgresVerification(a.image,a.out).run()
