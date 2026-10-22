from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    raise TypeError(type(value).__name__)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=json_default, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write_json(path, value):
    from .persistence import write_bytes
    write_bytes(path, json.dumps(value, ensure_ascii=False, indent=2, default=json_default, allow_nan=False).encode('utf-8'))


def read_json(path):
    from .persistence import read_bytes
    return json.loads(read_bytes(path).decode('utf-8-sig'))


def credential(name):
    if name not in {"AVALAI_API_KEY", "WALLEX_API_KEY"}:
        raise ValueError("Unrecognized credential")
    if os.environ.get(name):
        return os.environ[name].strip()
    path = ROOT / ".secrets" / (name + ".dpapi")
    if os.name != "nt" or not path.is_file():
        raise RuntimeError(f"Set {name} in the process environment")
    env = dict(os.environ, STARWALLEX_CREDENTIAL_FILE=str(path))
    command = "$ErrorActionPreference='Stop'; $s=(Get-Content -LiteralPath $env:STARWALLEX_CREDENTIAL_FILE -Raw).Trim() | ConvertTo-SecureString; $p=[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try {[System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($p)} finally {[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}"
    result = subprocess.run([shutil.which("pwsh") or "powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, env=env)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("Credential unavailable in this Windows profile; use your normal user or environment variable")
    return result.stdout.strip()


def redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if re.search(r"api.?key|authorization|password|secret|access.token", k, re.I) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"\baa-[A-Za-z0-9]{20,}|\b\d{3,}\|[A-Za-z0-9]{20,}|Bearer\s+\S+", "[REDACTED]", value)
    return value


def source_manifest():
    # Quant identity is independent of presentation/server code. The complete
    # deployable app has its own release manifest in scripts/package.py.
    paths = [*ROOT.glob("starwallex/*.py"), *ROOT.glob("config/*.json"), *ROOT.glob("config/*.txt"), *ROOT.glob("prompts/*.txt"), ROOT/'app/research.py', ROOT/'scripts/evaluate.py']
    files = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.is_file()}
    return {"sha256": digest(files), "files": files}
