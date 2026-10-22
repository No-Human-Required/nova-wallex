"""Build an allowlisted Runflare ZIP with Dockerfile at its root; verify every byte."""
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from starwallex.util import ROOT, canonical, digest, read_json, source_manifest, write_json
from execution.activation import bundle_hash
from app.release import runtime_manifest
from app.version import VERSION

def build():
    report=read_json(ROOT/'seed/report.json')
    if source_manifest()['sha256']!=report['source_sha256']:
        raise ValueError('Results do not match this quant source')
    checks=read_json(ROOT/'evidence/replay-verification.json')
    if checks['exact_replays']!=len(report['cases']) or not checks['all_passed']:
        raise ValueError('Incomplete replay verification')
    linux=read_json(ROOT/'evidence/linux-portable/replay-verification.json')
    if linux['source_sha256']!=report['source_sha256'] or linux['exact_replays']!=153 or not linux['all_passed']:
        raise ValueError('Linux replay evidence missing or stale')
    container=read_json(ROOT/('evidence/container-v'+VERSION+'.json'))
    if not container['all_passed'] or container['runtime_files_sha256']!=runtime_manifest()['sha256']:
        raise ValueError('Container proof does not match packaged runtime')
    live=read_json(ROOT/'seed/live-release.json')
    if live['source_sha256']!=bundle_hash() or not live['offline_fault_tests_passed']:
        raise ValueError('Live runtime proof does not match source')
    postgres=read_json(ROOT/'evidence/postgres-tests.json')
    if not postgres['all_passed'] or not container.get('database_backend')=='postgresql':
        raise ValueError('PostgreSQL persistence proof is required')
    paths=[]
    for folder in ['app','execution','starwallex','config','prompts','data/portfolio','data/portfolio-ai-cache','seed','static','scripts','tests','docs']:
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.tmp'}]
    paths += [ROOT/name for name in ['README.md','run.py','supervisor.py','Dockerfile','requirements.txt','compose.yaml','.dockerignore','.gitignore','.env.example']]
    evidence=['validation.json','replay-verification.json','service-crash-recovery.json','public-monitor-contract.json',
              'tests-current.txt','execution-tests-current.txt','browser-checks.json','linux-dependency-resolution.txt',
              'python-image-manifest.json','panel-preview.jpg','live-panel-preview.jpg',
              'container-v'+VERSION+'.json','container-v'+VERSION+'.txt','postgres-tests.json','postgres-tests.txt',
              'linux-portable/replay-verification.json','linux-portable-replay.txt']
    paths += [ROOT/'evidence'/name for name in evidence]
    entries={}
    secret=re.compile(rb'\baa-[A-Za-z0-9]{28,}|\b\d{3,}\|[A-Za-z0-9]{25,}')
    for p in sorted(set(paths)):
        name=p.relative_to(ROOT).as_posix()
        if p.is_symlink() or any(part in {'.secrets','.venv','.git','private','var','var-preview'} for part in p.parts):
            raise ValueError('Disallowed artifact path')
        content=p.read_bytes()
        if p.suffix not in {'.jpg','.woff2'} and secret.search(content):
            raise ValueError('Potential secret detected in '+name)
        entries[name]=hashlib.sha256(content).hexdigest()
    manifest={'version':VERSION,'built_at_utc':datetime.now(timezone.utc).isoformat(),
              'files':entries,'files_sha256':digest(entries),'quant_source_sha256':report['source_sha256'],
              'dataset_identity':report['dataset_identity'],'mode':'account_bound_control_plane','exchange_writes_default':False,
              'real_orders_sent_during_build':0,'engine_source_sha256':bundle_hash(),
              'runflare_deployed':False,'docker_build_executed':True,'container_image_id':container['image_id']}
    write_json(ROOT/'release.json',manifest)
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    target=out/'starwallex-runflare-v3.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name in entries:archive.write(ROOT/name,name)
        archive.write(ROOT/'release.json','release.json')
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist())==set(entries)|{'release.json'}
        for name,sha in entries.items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==sha,name
        assert 'Dockerfile' in archive.namelist()
    result={'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'files':len(entries)+1,'every_file_hash_verified':True,'no_secrets_detected':True,
            'release_files_sha256':manifest['files_sha256']}
    write_json(out/'package-verification.json',result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':build()
