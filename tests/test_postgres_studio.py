"""Settings vault staging and Strategy Studio storage on real PostgreSQL."""
import os
import secrets
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

from tests import test_studio


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'), 'Disposable PostgreSQL integration DB not configured')
class PostgresStudioTests(test_studio.StudioApiTests):
    VAULT = Fernet.generate_key().decode()

    def setUp(self):
        self.pg = patch.dict(os.environ, {'SW_DATABASE_URL': os.environ['SW_TEST_DATABASE_URL'],
                                          'SW_DB_NAMESPACE': 'test_'+secrets.token_hex(5)})
        self.pg.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.pg.stop()

    def test_vault_promotes_staged_key_atomically(self):
        v = self.app.state.vault
        with self.app.state.store.connect() as db:
            v.put('wallex', 'offline-old-wallex-key', db)
            v.put('wallex_next', 'offline-new-wallex-key', db)
        self.assertTrue(v.overview()['wallex']['staged'])
        with self.app.state.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            v.promote('wallex', db)
        self.assertEqual(v.get('wallex'), 'offline-new-wallex-key')
        self.assertFalse(v.overview()['wallex']['staged'])


if __name__ == '__main__':
    unittest.main()
