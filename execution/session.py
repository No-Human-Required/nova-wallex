"""Version and configuration binding for the unactivated execution journal."""
import hashlib
from pathlib import Path
from starwallex.audit import Audit
from starwallex.util import digest
from starwallex.persistence import file_exists, read_bytes, write_bytes
from .contracts import number
from .journal import ExecutionJournal

ROOT=Path(__file__).resolve().parent

def source_manifest():
    files={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted([*ROOT.glob('*.py'),*ROOT.glob('tests/*.py')])}
    return {'files':files,'sha256':digest(files)}

def open_journal(directory,markets,*,capital='5000000',max_order_tmn='500000',fee_buffer='0.003',max_age=10,session_binding=None):
    source=source_manifest()
    limits={'capital':number(capital),'max_order_tmn':number(max_order_tmn),'fee_buffer':number(fee_buffer),'max_age':max_age}
    cfg={'runtime_source':source,'runtime_limits':limits,
         'session_binding_sha256':digest(session_binding) if session_binding is not None else None,
         'market_contract':{s:{k:str(v) for k,v in vars(m).items()} for s,m in sorted(markets.items())}}
    label='wallex-account-runtime' if session_binding and session_binding.get('enabled') is True else 'unactivated-execution-contract-lab'
    audit=Audit(directory,cfg,label=label)
    try:
        for name,h in source['files'].items():
            dest=Path(directory)/'runtime_source'/name
            dest.parent.mkdir(exist_ok=True,parents=True)
            if file_exists(dest) and hashlib.sha256(read_bytes(dest)).hexdigest()!=h:raise ValueError('Runtime source snapshot changed')
            if not file_exists(dest):write_bytes(dest,(ROOT/name).read_bytes())
        return ExecutionJournal(audit,markets,**limits)
    except Exception:
        audit.close();raise
