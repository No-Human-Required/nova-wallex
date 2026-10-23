"""Backtest lab runs and shadow-AI reviews on the PostgreSQL control store."""
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from cryptography.fernet import Fernet

from tests import test_backtest_lab as lab


@unittest.skipUnless(os.environ.get('SW_TEST_DATABASE_URL'), 'set SW_TEST_DATABASE_URL to a disposable PostgreSQL database')
class PostgresLabTests(lab.ApiTests):
    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.pg = patch.dict(os.environ, {'SW_DATABASE_URL': os.environ['SW_TEST_DATABASE_URL'], 'SW_DATA_DIR': self.data.name,
                                          'SW_DB_NAMESPACE': 'lab'+uuid.uuid4().hex[:8], 'SW_VAULT_KEY': Fernet.generate_key().decode(),
                                          'SW_SHADOW_AI': '0'})
        self.pg.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.pg.stop()
        self.data.cleanup()

    def test_shadow_review_rows_replace_only_failures(self):
        from app import shadow_ai
        with self.app.state.store.connect() as db:
            shadow_ai.ensure(db)
            for status in ('unavailable', 'ok', 'unavailable'):
                db.execute('DELETE FROM shadow_ai WHERE run_id=? AND time=? AND status!=?', ('r', 1, 'ok'))
                db.execute('INSERT INTO shadow_ai(run_id,time,source,status,candidates,decisions,record,calls,created) VALUES(?,?,?,?,?,?,?,?,?) '
                           'ON CONFLICT(run_id,time) DO NOTHING', ('r', 1, 'observer', status, '[]', '[]', '{}', 3, 1.0))
        self.assertEqual([(r['status'], r['calls']) for r in shadow_ai.rows(self.app.state.store, 'r')], [('ok', 3)])


if __name__ == '__main__':
    unittest.main()
