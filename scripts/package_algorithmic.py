"""Runflare ZIP for the Algorithmic platform: algo/Dockerfile becomes the root Dockerfile.

Only committed files are packaged (git ls-files), every file hash is re-read
from the archive, and a secret pattern scan refuses the build.
"""
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from algo import VERSION  # noqa: E402

FOLDERS = ('algo', 'app', 'execution', 'starwallex', 'config', 'prompts', 'static/fonts')
FILES = ('requirements.txt', 'data/portfolio/universe.json')
SECRET = re.compile(rb'\baa-[A-Za-z0-9]{28,}|\b\d{3,}\|[A-Za-z0-9]{25,}')


def build():
    if subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True).stdout.strip():
        raise SystemExit('Commit your changes first: the package is built from committed files')
    tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files'], capture_output=True, text=True, check=True).stdout.split('\n')
    names = sorted(n for n in tracked if n and (n in FILES or any(n.startswith(f+'/') for f in FOLDERS)) and '__pycache__' not in n)
    entries = {}
    for n in names:
        data = (ROOT/n).read_bytes()
        if not n.endswith(('.woff2', '.png', '.svg')) and SECRET.search(data):
            raise SystemExit('Potential secret in '+n)
        entries[n] = hashlib.sha256(data).hexdigest()
    entries['Dockerfile'] = hashlib.sha256((ROOT/'algo/Dockerfile').read_bytes()).hexdigest()
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    manifest = {'app': 'algorithmic', 'version': VERSION, 'git_commit': head, 'built_at_utc': datetime.now(timezone.utc).isoformat(), 'files': entries}
    dist = ROOT/'dist'
    dist.mkdir(exist_ok=True)
    target = dist/f'algorithmic-runflare-v{VERSION}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n in names:
            z.write(ROOT/n, n)
        z.write(ROOT/'algo/Dockerfile', 'Dockerfile')
        z.writestr('release.json', json.dumps(manifest, indent=2))
    with zipfile.ZipFile(target) as z:
        for n, sha in entries.items():
            assert hashlib.sha256(z.read(n)).hexdigest() == sha, n
    out = {'file': str(target.relative_to(ROOT)), 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
           'files': len(entries)+1, 'git_commit': head}
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    build()
