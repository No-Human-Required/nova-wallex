"""Generic operator upgrade (receipt v7) of a real-shaped run with a held TRX position."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from tests import test_native_cancel_recovery as cancel
from app.live_native_recovery import recover
from app import live_upgrade
from execution.session import open_journal
from execution.revision import read_identity
from execution.activation import bundle_hash

NEW = 'f'*64


def installed(value=NEW):
    return [patch('app.live_upgrade.bundle_hash', return_value=value), patch('execution.activation.bundle_hash', return_value=value),
            patch('app.live_api.bundle_hash', return_value=value)]


class UpgradeTests(unittest.TestCase):
    setUp = cancel.NativeCancelRecoveryTests.setUp
    tearDown = cancel.NativeCancelRecoveryTests.tearDown
    post = cancel.NativeCancelRecoveryTests.post
    configure = cancel.NativeCancelRecoveryTests.configure
    preview = cancel.NativeCancelRecoveryTests.preview

    def prepare(self):
        cancel.NativeCancelRecoveryTests.prepare(self)
        recover(self.app, hold_trx_trend_exit=True)
        self.v6 = self.app.state.live.run(self.ident)
        self.state6 = read_identity(self.directory)[1]
        self.patches = installed()
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_upgrade_records_changes_keeps_ledger_and_stays_stopped(self):
        self.prepare()
        view = live_upgrade.preview(self.app)
        self.assertTrue(view['available'])
        self.assertIn('end_utc', view['binding_changes'])
        self.assertEqual(view['config_changes']['runtime_policy']['to'], 'adaptive_ai')
        with self.assertRaises(ValueError):
            live_upgrade.apply(self.app, 'wrong phrase')
        r = live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)
        self.assertTrue(r['ok'])
        self.assertFalse(r['execution_resumed'])
        self.assertEqual(r['exchange_orders_sent'], 0)
        run = self.app.state.live.run(self.ident)
        identity, s = read_identity(self.directory)
        self.assertEqual(identity, self.original_identity)
        self.assertEqual(s['ledger'], self.state6['ledger'])
        self.assertEqual(s['strategy']['positions'], self.state6['strategy']['positions'])
        self.assertEqual(run['revision']['version'], 7)
        self.assertEqual(run['binding']['source_sha256'], NEW)
        self.assertEqual(run['binding']['end_utc'], '2026-10-26T20:29:00+00:00')
        self.assertEqual(run['config']['runtime_policy'], 'adaptive_ai')
        self.assertTrue(run['config']['trx_trend_exit_hold'])
        self.assertEqual(run['config']['max_daily_loss_fraction'], self.v6['config']['max_daily_loss_fraction'])
        self.assertEqual(run['config']['max_drawdown_fraction'], self.v6['config']['max_drawdown_fraction'])
        self.assertEqual(self.app.state.live.state()['desired'], 'stopped')
        j = open_journal(self.directory, self.h.markets, session_binding=run['binding'], revision=run['revision'])
        self.assertTrue(j.audit.verify())
        self.assertFalse(j.unresolved())
        j.audit.close()
        self.assertTrue(live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)['already_applied'])

    def test_second_upgrade_chains_to_the_first_receipt(self):
        self.prepare()
        live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)
        first = self.app.state.live.run(self.ident)
        state = read_identity(self.directory)[1]
        newer = installed('e'*64)
        for p in newer:
            p.start()
            self.addCleanup(p.stop)
        view = live_upgrade.preview(self.app)
        self.assertTrue(view['available'])
        r = live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)
        self.assertTrue(r['ok'])
        run = self.app.state.live.run(self.ident)
        self.assertEqual(run['revision']['version'], 7)
        self.assertEqual(run['revision']['previous_revision'], first['revision'])
        self.assertEqual(run['binding']['source_sha256'], 'e'*64)
        self.assertEqual(read_identity(self.directory)[1]['ledger'], state['ledger'])
        j = open_journal(self.directory, self.h.markets, session_binding=run['binding'], revision=run['revision'])
        self.assertTrue(j.audit.verify())
        j.audit.close()

    def test_running_engine_new_fill_or_wallet_mismatch_refuse_without_mutation(self):
        self.prepare()
        self.app.state.live.control('resume')
        with self.assertRaises(ValueError):
            live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)
        self.app.state.live.stopped('blocked', 'Trading code changed; reviewed migration required')
        good = deepcopy(self.fake.detailed_balances())
        self.fake.detailed_balances = lambda: {'success': True, 'result': {'TMN': {'symbol': 'TMN', 'total': '1', 'available': '1', 'freeze': '0'}}}
        with self.assertRaises(ValueError):
            live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)
        self.assertEqual(read_identity(self.directory)[1], self.state6)
        self.assertEqual(self.app.state.live.run(self.ident)['binding'], self.v6['binding'])
        self.fake.detailed_balances = lambda: deepcopy(good)
        self.fake.open_order_ids = lambda: {'foreign'}
        with self.assertRaises(ValueError):
            live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)
        self.assertEqual(read_identity(self.directory)[1], self.state6)

    def test_tampered_receipt_is_rejected_by_journal(self):
        self.prepare()
        live_upgrade.apply(self.app, live_upgrade.CONFIRMATION)
        run = self.app.state.live.run(self.ident)
        bad = deepcopy(run['revision'])
        bad['exchange_orders_sent'] = 1
        with self.assertRaises(ValueError):
            open_journal(self.directory, self.h.markets, session_binding=run['binding'], revision=bad)
        bad = deepcopy(run['revision'])
        bad['previous_revision']['config_changes'] = {}
        with self.assertRaises(ValueError):
            open_journal(self.directory, self.h.markets, session_binding=run['binding'], revision=bad)

    def test_upgrade_route_requires_csrf_and_public_view_hides_identifiers(self):
        self.prepare()
        r = self.client.post('/api/live/upgrade', json={'confirmation': live_upgrade.CONFIRMATION}, headers={'Origin': 'http://127.0.0.1:8787', 'X-CSRF-Token': 'forged'})
        self.assertEqual(r.status_code, 403)
        text = json.dumps(self.client.get('/api/public/live').json())
        run = self.app.state.live.run(self.ident)
        for secret in (run['binding']['subaccount_client_id'], run['binding']['key_sha256'], run['binding']['avalai_fingerprint']):
            self.assertNotIn(secret, text)
        j = self.client.get('/api/public/journal').json()
        self.assertIn('orders', j)


from tests.legacy_config import apply as _legacy
_legacy(globals())

if __name__ == '__main__':
    unittest.main()
