"""Verify the actual Linux production image using disposable, labelled resources.

Only the internal HTTP hop is tested; HTTPS termination belongs to the host.
No exchange credentials, live orders, shadow runs or new AI calls are used.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.release import runtime_manifest
ORIGIN = 'https://container-test.example'
LABEL = 'io.starwallex.verification'


class Verification:
    def __init__(self, image, output, source_root=ROOT):
        self.image, self.output = image, Path(output)
        self.source_root = Path(source_root)
        self.ident = 'starwallex-check-' + secrets.token_hex(6)
        self.volume = self.ident + '-data'
        self.containers = []
        self.volume_created = False
        self.cookie = self.csrf = ''
        self.base = ''
        self.password = ''
        self.result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                       'image_tag': image, 'checks': {}, 'real_exchange_orders': 0,
                       'external_ai_calls': 0, 'runflare_deployed': False,
                       'transport': 'loopback HTTP behind simulated HTTPS origin; host TLS not tested'}

    def docker(self, *args, check=True, timeout=120):
        r = subprocess.run(['docker', *args], capture_output=True, text=True,
                           timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if check and r.returncode:
            # Command output can contain environment data: never print it on failure.
            raise RuntimeError('Docker operation failed: ' + args[0])
        return r

    def inspect(self, name, kind='container'):
        return json.loads(self.docker(kind, 'inspect', name).stdout)[0]

    def mark(self, name, passed):
        self.result['checks'][name] = bool(passed)
        if not passed:
            raise AssertionError(name)
        print('PASS ' + name, flush=True)

    def request(self, path, body=None, headers=None, expected=200, authenticated=True):
        h = {'Host': 'container-test.example', 'Origin': ORIGIN, 'Content-Type': 'application/json'}
        if authenticated and self.cookie:
            # A real TLS reverse proxy forwards the Secure cookie on its internal HTTP hop.
            h.update(Cookie=self.cookie, **{'X-CSRF-Token': self.csrf})
        h.update(headers or {})
        req = urllib.request.Request(self.base+path, data=json.dumps(body).encode() if body is not None else None, headers=h)
        try:
            response = urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if response.status != expected:
                raise AssertionError(f'{path}: expected HTTP {expected}, got {response.status}')
            content = response.read()
            parsed = json.loads(content) if response.headers.get_content_type() == 'application/json' else None
            return parsed, dict(response.headers)

    def ready(self):
        deadline = time.monotonic()+60
        while time.monotonic() < deadline:
            try:
                if self.request('/readyz', authenticated=False)[0]['ready']:
                    return
            except (OSError, AssertionError):
                pass
            time.sleep(.25)
        raise TimeoutError('Container readiness')

    def discover_port(self, name):
        port = self.docker('port', name, '8080/tcp').stdout.strip()
        if not re.fullmatch(r'127\.0\.0\.1:\d+', port):
            raise AssertionError('Container must bind loopback only')
        self.base = 'http://'+port

    def login(self, password):
        body, headers = self.request('/api/login', {'password': password}, authenticated=False)
        cookie = SimpleCookie(); cookie.load(headers['set-cookie'] if 'set-cookie' in headers else headers['Set-Cookie'])
        morsel = cookie['sw_session']
        self.mark('secure_httponly_samesite_session', bool(morsel['secure'] and morsel['httponly'] and morsel['samesite'].lower() == 'strict'))
        self.cookie, self.csrf = 'sw_session='+morsel.value, body['csrf']

    def run_container(self, envfile, name, publish=True):
        args = ['run', '-d', '--name', name, '--label', LABEL+'='+self.ident,
                '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                '--memory=1g', '--cpus=1', '--pids-limit=128', '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m',
                '--env-file', str(envfile), '--mount', 'type=volume,src='+self.volume+',dst=/data',
                '--health-interval=2s', '--health-start-period=10s', '--stop-timeout=35']
        if publish:
            args += ['--publish', '127.0.0.1::8080']
        self.docker(*args, self.image)
        self.containers.append(name)

    def execute(self):
        metadata = self.inspect(self.image, 'image')
        self.result['image_id'] = metadata['Id']
        self.result['platform'] = metadata['Os']+'/'+metadata['Architecture']
        self.mark('linux_amd64_image', self.result['platform'] == 'linux/amd64')
        self.mark('nonroot_image_user', metadata['Config']['User'] == '10001:10001')
        self.docker('volume', 'create', '--label', LABEL+'='+self.ident, self.volume)
        self.volume_created = True
        with tempfile.TemporaryDirectory(prefix='starwallex-container-') as tmp:
            password = secrets.token_urlsafe(40)
            self.password = password
            envfile = Path(tmp)/'test.env'
            envfile.write_text(f'SW_ENV=production\nSW_PUBLIC_ORIGIN={ORIGIN}\nSW_ADMIN_PASSWORD={password}\nSW_DATA_DIR=/data\nPORT=8080\nSW_REQUIRE_POSTGRES=0\n', encoding='utf-8')
            name = self.ident+'-primary'
            self.run_container(envfile, name)
            self.discover_port(name)
            started = time.monotonic(); self.ready()
            self.result['cold_start_seconds'] = round(time.monotonic()-started, 3)
            self.mark('production_ready', True)
            inside = json.loads(self.docker('exec',name,'python','-c',
                'import json; from app.release import runtime_manifest; print(json.dumps(runtime_manifest()))').stdout)
            expected_files = runtime_manifest(self.source_root)
            self.mark('image_runtime_files_match_source', inside == expected_files)
            self.result['runtime_files_sha256'] = inside['sha256']
            self.result['runtime_file_count'] = len(inside['files'])
            for path in ['/api/live/status','/api/operations']:
                self.request(path, expected=401, authenticated=False)
            for path in ['/api/status', '/api/report', '/api/jobs', '/api/markets']:
                self.request(path, authenticated=False)
            public_session=self.request('/api/session',authenticated=False)[0]
            self.mark('public_research_without_account_or_control_access',not public_session['authenticated'] and not public_session['csrf'])
            self.request('/api/live/control',{'action':'resume'},expected=401,authenticated=False)
            self.request('/api/jobs',{'variant':'cash','window':1},expected=401,authenticated=False)
            self.login(password)
            status = self.request('/api/status')[0]
            self.result.update(source_sha256=status['source_sha256'], dataset_identity=status['dataset_identity'])
            self.mark('no_live_shadow_model_or_monitor_activity', not any(status[k] for k in ['live_orders_enabled','shadow_running','new_ai_calls_enabled']) and not status['public_monitor']['enabled'])
            self.mark('runtime_scratch_writable', status['storage_writable'])
            if self.result.get('database_backend')=='postgresql':
                self.mark('postgresql_authoritative_without_app_volume',status['database_backend']=='postgresql' and not status['app_volume_required'])
            live=self.request('/api/live/status')[0]
            self.mark('engine_idle_no_keys_no_account',live['state']['desired']=='stopped' and live['state']['run_id'] is None and all(not live['credentials'][k]['present'] for k in ['wallex','avalai']))
            self.mark('independent_engine_heartbeat',live['state']['heartbeat'] is not None and time.time()-live['state']['heartbeat']<20)
            self.mark('all_pairs_and_cases_available', status['pair_count'] == 120 and len(self.request('/api/report')[0]['cases']) == 153)
            for headers in [{'Origin':'https://other.example'}, {'X-CSRF-Token':'wrong'}]:
                self.request('/api/jobs', {'variant':'cash','window':1}, headers=headers, expected=403)
            self.request('/api/orders', {}, expected=404)
            self.mark('csrf_origin_and_no_order_route', True)
            replica = self.ident+'-replica'
            self.run_container(envfile, replica, publish=False)
            code = self.docker('wait', replica, timeout=30).stdout.strip()
            log = self.docker('logs', replica).stderr
            self.mark('second_writer_refused', code != '0' and ('Only one service replica/worker' in log or 'already holds the database lock' in log))

            spec = {'variant':'guarded_breakout_ai','window':32,'scenario':'base'}
            key = {'Idempotency-Key':'container-restart-001'}
            job = self.request('/api/jobs', spec, key, expected=202)[0]
            duplicate = self.request('/api/jobs', spec, key, expected=202)[0]
            self.mark('duplicate_request_one_job', job['id'] == duplicate['id'])
            deadline = time.monotonic()+90
            while time.monotonic() < deadline:
                j = self.request('/api/jobs')[0][0]
                if j['status']=='failed':
                    self.result['failed_job'] = j
                    raise AssertionError('Research job failed')
                if 12 <= j['progress'] < 72: break
                time.sleep(.03)
            else: raise TimeoutError('Cannot find checkpoint before completion')
            self.result['killed_after_committed_hours'] = j['progress']
            self.docker('kill', name)
            old_address = self.base
            self.docker('start', name); self.discover_port(name); self.ready()
            self.result['ephemeral_port_changed_on_restart'] = old_address != self.base
            j = self.request('/api/jobs')[0][0]
            self.mark('restart_preserves_session_and_pauses_job', j['id']==job['id'] and j['status']=='paused' and j['progress']>=12)
            self.request('/api/jobs/'+job['id']+'/control', {'action':'resume'})
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                j = self.request('/api/jobs')[0][0]
                if j['status']=='completed': break
                if j['status']=='failed':
                    self.result['failed_job'] = j
                    raise AssertionError('Resumed job failed')
                time.sleep(.1)
            else: raise TimeoutError('Resumed job did not complete')
            actual = self.request('/api/jobs/'+job['id'])[0]['snapshot']['summary']
            expected = json.loads((self.source_root/'seed/cases/w32-guarded_breakout_ai-base.json').read_text(encoding='utf-8'))['summary']
            fields = ['audit','cash_tmn','final_nav_tmn','realized_pnl_tmn','unrealized_pnl_tmn','fees_tmn','fill_count','positions','fx_lots','pending_orders']
            self.mark('linux_restart_exact_accounting_and_audit', all(actual[k]==expected[k] for k in fields))
            self.result['chain_head'] = actual['audit']['chain_head']
            self.mark('export_matches_job', self.request('/api/export/'+job['id'])[0]['summary'] == actual)
            def sample(_):
                t = time.monotonic(); self.request('/api/jobs'); return (time.monotonic()-t)*1000
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                latency = sorted(pool.map(sample, range(40)))
            self.result['api_40_reads_p95_ms'] = round(latency[37], 2)
            self.result['container_memory'] = self.docker('stats','--no-stream','--format','{{.MemUsage}}',name).stdout.strip()
            info = self.inspect(name)
            if self.result.get('database_backend')=='postgresql':
                self.mark('no_persistent_app_mount_after_restart', all(m['Type']=='tmpfs' for m in info['Mounts']))
            self.mark('read_only_root_and_one_cpu_one_gb_limit', info['HostConfig']['ReadonlyRootfs'] and info['HostConfig']['Memory']==1073741824 and info['HostConfig']['NanoCpus']==1000000000)
            self.mark('docker_healthcheck_healthy', info['State']['Health']['Status']=='healthy')
            self.request('/api/logout', {})
            self.request('/api/live/status', expected=401)
            self.request('/api/jobs')
            self.mark('logout_invalidates_session', True)

    def cleanup(self):
        for name in reversed(self.containers):
            info = self.inspect(name)
            if info['Config']['Labels'].get(LABEL) != self.ident:
                raise RuntimeError('Refusing to remove unowned container')
            self.docker('rm','-f',name)
        if self.volume_created:
            info = self.inspect(self.volume, 'volume')
            if info['Labels'].get(LABEL) != self.ident:
                raise RuntimeError('Refusing to remove unowned volume')
            self.docker('volume','rm',self.volume)
        self.result['temporary_resources_removed'] = True

    def run(self):
        try:
            self.execute()
            self.result['all_passed'] = True
        except Exception as error:
            self.result.update(all_passed=False, failure_type=type(error).__name__)
            for name in self.containers:
                try:
                    info = self.inspect(name)
                    state = info['State']
                    logs = self.docker('logs','--tail','35',name,check=False)
                    self.result.setdefault('failure_diagnostics',[]).append({
                        'name':name, 'status':state['Status'], 'exit_code':state['ExitCode'],
                        'port':self.docker('port',name,'8080/tcp',check=False).stdout.strip(),
                        'logs':(logs.stdout+logs.stderr).replace(self.password,'[TEST_PASSWORD]') if self.password else ''})
                except Exception:
                    pass
            raise
        finally:
            try:
                self.cleanup()
            finally:
                self.output.parent.mkdir(parents=True,exist_ok=True)
                self.output.write_text(json.dumps(self.result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--image', default='starwallex-control:3.1.0')
    p.add_argument('--out', default=str(ROOT/'evidence/container-verification.json'))
    p.add_argument('--source-root', type=Path, default=ROOT)
    args=p.parse_args()
    Verification(args.image,args.out,args.source_root).run()
