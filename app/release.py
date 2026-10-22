"""Fingerprint the files actually copied into the production container."""
import hashlib
from pathlib import Path

from starwallex.util import ROOT, digest

RUNTIME_DIRS = ('app', 'execution', 'starwallex', 'config', 'prompts', 'data', 'seed', 'static', 'scripts')


def runtime_manifest(root=ROOT):
    root = Path(root)
    paths = [root/'run.py', root/'supervisor.py', root/'requirements.txt']
    for folder in RUNTIME_DIRS:
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(paths)}
    return {'files': files, 'sha256': digest(files)}
