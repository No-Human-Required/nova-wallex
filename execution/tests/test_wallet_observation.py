import copy
import unittest
from decimal import Decimal
from execution.contracts import ContractError,incremental_fills
from execution.wallet_precision import POLICY,check_wallet
from execution.tests import test_execution as fixture
from execution.tests.test_execution import intent,fill,response,Gateway


class WalletObservationTests(unittest.TestCase):
    setUp=fixture.ExecutionTests.setUp
    tearDown=fixture.ExecutionTests.tearDown
    submit=fixture.ExecutionTests.submit

    def test_post_get_timestamp_rounding_does_not_reapply_fill(self):
        i=intent(self.j);f=fill('1000',ts='2026-10-22T12:34:40.964197Z')
        g=Gateway(response(i,[f],False));self.submit(i,g);ledger=copy.deepcopy(self.j.s['ledger'])
        g.result=response(i,[{**f,'timestamp':'2026-10-22T12:34:41.000000Z'}],False)
        self.j.reconcile(i['client_id'],g,now=102)
        self.assertEqual(self.j.s['ledger'],ledger);self.assertEqual(len(g.sent),1)
        self.assertEqual(len(self.j.s['orders'][i['client_id']]['fills']),1)

    def test_financial_change_or_large_time_change_remains_blocked(self):
        previous=[{'quantity':'0.8','price':'89961','fee':'0.0024','feeAsset':'TRX','timestamp':'2026-10-22T12:34:40.964197Z'}]
        for change in ({'fee':'0.003'},{'quantity':'0.9'},{'price':'89962'},{'timestamp':'2026-10-22T12:34:43Z'}):
            with self.assertRaises(ContractError):incremental_fills(previous,[previous[0]|change])

    def test_identical_fill_multiplicity_survives_timestamp_rounding(self):
        old={'quantity':'0.8','price':'89961','fee':'0.0024','feeAsset':'TRX','timestamp':'2026-10-22T12:34:40.964197Z'}
        new={**old,'timestamp':'2026-10-22T12:34:41.000000Z'}
        self.assertFalse(incremental_fills([old,old],[new,new]))
        self.assertEqual(sum(incremental_fills([old],[new,new]).values()),1)
        with self.assertRaises(ContractError):incremental_fills([old,old],[new])

    def test_integer_reporting_needs_review_and_never_changes_ledger(self):
        state=copy.deepcopy(self.j.s);state['ledger']['cash']='4928031.2'
        state['ledger']['holdings']={'TRX':{'qty':'0.7976','basis':'71968.8'}}
        state['wallet_observation_policy']=POLICY
        self.j.checkpoint('isolated_fixture_review',{},state);before=copy.deepcopy(self.j.s['ledger'])
        totals={'TMN':'4928031','TRX':'0.7976'}
        for t in (101,102):self.j.confirm_balances(totals,{},set(),observed_at=t,now=t)
        self.assertEqual(self.j.s['ledger'],before)
        self.assertEqual(self.j.s['balance_precision']['tmn_difference'],'0.2')
        self.assertEqual(self.j.s['reported_cash_tmn'],'4928031')
        with self.assertRaises(ContractError):check_wallet(totals,{'TMN':'4928031.2','TRX':'0.7976'})

    def test_tolerance_does_not_accumulate_or_cover_crypto_or_credit(self):
        expected={'TMN':'4928031.2','TRX':'0.7976'}
        for actual in ({'TMN':'4928030','TRX':'0.7976'},{'TMN':'4928032','TRX':'0.7976'},
                       {'TMN':'4928031','TRX':'0.7975'},{'TMN':'4928031.1','TRX':'0.7976'}):
            with self.assertRaises(ContractError):check_wallet(actual,expected,allow_integer_tmn=True)
        with self.assertRaises(ContractError):check_wallet({'TMN':'4999999'},{'TMN':'5000000'},allow_integer_tmn=True)

    def test_integer_reporting_rounds_to_nearest_in_either_direction(self):
        # Live 1405/08/01: ledger 4239671.6165, balances-detail 4239672.
        expected={'ADA':'4.985','TMN':'4239671.6165','TRX':'0.7976','USOON':'0.0084745'}
        r=check_wallet({**expected,'TMN':'4239672'},expected,allow_integer_tmn=True)
        self.assertEqual((r['rounding'],r['tmn_difference'],r['spending_cash_tmn']),('up','-0.3835','4239671.6165'))
        for wrong in ('4239671','4239673','4239672.5'):
            with self.assertRaises(ContractError):check_wallet({**expected,'TMN':wrong},expected,allow_integer_tmn=True)
        with self.assertRaises(ContractError):check_wallet({**expected,'TMN':'4239672'},expected)
        with self.assertRaises(ContractError):check_wallet({**expected,'TMN':'4239672','USOON':'0.0085'},expected,allow_integer_tmn=True)
        self.assertEqual(check_wallet({'TMN':'10'},{'TMN':'10.5'},allow_integer_tmn=True)['rounding'],'down')
        self.assertEqual(check_wallet({'TMN':'11'},{'TMN':'10.5'},allow_integer_tmn=True)['rounding'],'up')

    def test_mismatch_evidence_keeps_both_values(self):
        with self.assertRaises(ContractError):self.j.confirm_balances({'TMN':'4999999'},{},set(),observed_at=100,now=100)
        self.assertEqual(self.j.s['ledger']['cash'],'5000000')
        events=self.j.audit.events('wallet_ledger_mismatch')
        self.assertEqual(len(events),1)


if __name__=='__main__':unittest.main()
