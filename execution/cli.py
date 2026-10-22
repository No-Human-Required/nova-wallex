"""Account-bound runtime, disabled unless explicit approval evidence is supplied.

No live run was authorized or executed during development. `describe` is offline.
The separate inspect_contract command is read-only. The run command additionally
requires a completed, source-bound activation file and --execute-real.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import time
from pathlib import Path

from starwallex.portfolio_run import validated_config
from starwallex.portfolio_ai import PortfolioAI
from starwallex.util import ROOT,read_json,write_json,credential,digest
from starwallex.net import APIError
from .activation import bundle_hash,validate_binding,WriteGuard
from .contracts import ContractError,dec
from .feed import PublicFeed
from .gateway import WallexGateway
from .session import open_journal
from .controller import PortfolioController
from .journal import TERMINAL

def example():
    cfg=validated_config();universe=read_json(ROOT/'data/portfolio/universe.json')
    return {'enabled':False,'human_approval_recorded':False,'challenge_account_confirmed':False,
        'risk_limits_approved':False,'permitted_markets_confirmed':False,
        'account_label':None,'key_sha256':None,'approval_reference':None,
        'organizer_time_reference':None,'organizer_settlement_reference':None,
        'start_utc':None,'end_utc':None,'settlement_rule':None,
        'source_sha256':bundle_hash(),'risk_config_sha256':digest(cfg),
        'symbols_sha256':digest(sorted(universe['markets'])),
        'entry_stop_before_end_seconds':3600,'unwind_before_end_seconds':1800,
        'note':'Do not set confirmations until the user actually approves this dedicated account, schedule, settlement rule and risk configuration.'}

def check_fees(response,markets,cfg):
    if response.get('success') is not True or not isinstance(response.get('result'),dict):raise ContractError('Fee contract unavailable')
    for symbol,m in markets.items():
        r=response['result'].get(symbol,{})
        if dec(r.get('takerFeeRate'))!=dec(cfg['fee_rates'][m.quote]):
            raise ContractError('Account fee differs from evaluated configuration: '+symbol)
    return {'checked_pairs':len(markets),'rates':cfg['fee_rates']}

def run(args):
    raise PermissionError('Use the account-bound panel activation and independent engine; legacy live CLI is disabled')


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('describe');d.add_argument('--write-disabled-example',type=Path)
    r=sub.add_parser('run');r.add_argument('--activation',type=Path,required=True);r.add_argument('--run-dir',type=Path,required=True)
    r.add_argument('--execute-real',action='store_true')
    a=p.parse_args()
    if a.command=='describe':
        value=example()
        if a.write_disabled_example:
            if a.write_disabled_example.exists():raise SystemExit('Refusing to overwrite an activation file')
            write_json(a.write_disabled_example,value)
        print(json.dumps(value,ensure_ascii=False,indent=2))
    else:run(a)

if __name__=='__main__':main()
