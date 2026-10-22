import os
import secrets
import unittest
from unittest.mock import patch
from tests import test_native_protection as api
from tests import test_postgres_history_revision as pg
from execution.tests import test_native_stop as native

@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'),'Disposable PostgreSQL integration DB not configured')
class PostgresNativeRevisionTests(api.NativeRevisionTests):
    setUp=pg.PostgresHistoryRevisionTests.setUp

@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'),'Disposable PostgreSQL integration DB not configured')
class PostgresNativePanelTests(api.NativePanelTests):
    setUp=pg.PostgresHistoryRevisionTests.setUp

@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'),'Disposable PostgreSQL integration DB not configured')
class PostgresNativeStopTests(native.NativeStopTests):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SW_DATABASE_URL':os.environ['SW_TEST_DATABASE_URL'],'SW_DB_NAMESPACE':'native_'+secrets.token_hex(6)})
        self.env.start();self.addCleanup(self.env.stop);super().setUp()

if __name__=='__main__':unittest.main()
