import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from starwallex.portfolio_run import validated_config
from starwallex.util import digest
from execution.activation import bundle_hash,validate_binding,WriteGuard
from execution.cli import run,check_fees
from execution.contracts import ContractError
from execution.gateway import WallexGateway
from execution.session import open_journal
from test_execution import MARKETS,intent,ALLOW

def binding(cfg,key='offline_fixture_key'):
    iso=lambda ts:datetime.fromtimestamp(ts,timezone.utc).isoformat()
    return {'enabled':True,'human_approval_recorded':True,'challenge_account_confirmed':True,
        'risk_limits_approved':True,'permitted_markets_confirmed':True,'account_label':'offline fixture, not a real account',
        'approval_reference':'unit fixture only','organizer_time_reference':'unit fixture only','organizer_settlement_reference':'unit fixture only',
        'key_sha256':hashlib.sha256(key.encode()).hexdigest(),'source_sha256':bundle_hash(),'risk_config_sha256':digest(cfg),
        'symbols_sha256':digest(sorted(MARKETS)),'start_utc':iso(90),'end_utc':iso(90+72*3600),
        'settlement_rule':'mark_open_assets','entry_stop_before_end_seconds':3600,'unwind_before_end_seconds':1800}

class ActivationTests(unittest.TestCase):
    def test_no_activation_from_key_or_enabled_flag_alone(self):
        cfg=validated_config();b=binding(cfg)
        for key in ['enabled','human_approval_recorded','challenge_account_confirmed','risk_limits_approved','permitted_markets_confirmed']:
            candidate={**b,key:False}
            with self.assertRaises(ContractError):validate_binding(candidate,'offline_fixture_key',MARKETS,cfg)
    def test_binding_detects_wrong_key_source_config_and_universe(self):
        cfg=validated_config();b=binding(cfg)
        for key in ['key_sha256','source_sha256','risk_config_sha256','symbols_sha256']:
            with self.assertRaises(ContractError):validate_binding({**b,key:'wrong'},'offline_fixture_key',MARKETS,cfg)
    def test_undefined_settlement_or_naive_time_not_invented(self):
        cfg=validated_config();b=binding(cfg)
        for update in [{'settlement_rule':None},{'start_utc':'2026-10-22T08:00:00'},{'organizer_time_reference':None}]:
            with self.assertRaises(ContractError):validate_binding({**b,**update},'offline_fixture_key',MARKETS,cfg)
    def test_slow_processing_expiry_denied_at_last_network_boundary(self):
        cfg=validated_config()
        with tempfile.TemporaryDirectory() as temp:
            j=open_journal(temp,MARKETS)
            try:
                j.confirm_balances({'TMN':'5000000'},{},set(),observed_at=100,now=100)
                guard=WriteGuard(binding(cfg),'offline_fixture_key',j,cfg,temp,clock=lambda:111)
                class NeverOpen:
                    def open(self,*a,**k):raise AssertionError('Expired decision reached network')
                g=WallexGateway('offline_fixture_key',write_authorizer=guard,opener=NeverOpen())
                self.assertEqual(j.submit(intent(j),g,now=100,risk_authorizer=ALLOW),'LOCAL_REJECTED')
                self.assertEqual(j.s['ledger']['cash'],'5000000')
            finally:j.audit.close()
    def test_account_binding_changes_prevent_journal_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            j=open_journal(temp,MARKETS,session_binding={'account':'fixture_A'});j.audit.close()
            with self.assertRaises(ValueError):open_journal(temp,MARKETS,session_binding={'account':'fixture_B'})
    def test_real_flag_and_disabled_config_fail_before_credentials(self):
        with patch('execution.cli.credential',side_effect=AssertionError('Must not read key')):
            with self.assertRaises(PermissionError):run(SimpleNamespace(execute_real=False))
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'disabled.json';path.write_text('{"enabled":false}',encoding='utf-8')
                with self.assertRaises(PermissionError):run(SimpleNamespace(execute_real=True,activation=path))
    def test_account_fees_must_match_evaluated_rates(self):
        cfg=validated_config();response={'success':True,'result':{s:{'takerFeeRate':cfg['fee_rates'][m.quote]} for s,m in MARKETS.items()}}
        self.assertEqual(check_fees(response,MARKETS,cfg)['checked_pairs'],3)
        response['result']['AAATMN']['takerFeeRate']='0.004'
        with self.assertRaises(ContractError):check_fees(response,MARKETS,cfg)

if __name__=='__main__':unittest.main()
