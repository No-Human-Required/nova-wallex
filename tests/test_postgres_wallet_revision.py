import os
import unittest
from tests import test_wallet_revision as fixture
from tests import test_postgres_history_revision as pgfixture
from tests import test_postgres as pgexec
from execution.tests import test_wallet_observation as observations


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'),'Disposable PostgreSQL integration DB not configured')
class PostgresWalletRevisionTests(fixture.WalletRevisionTests):
    setUp=pgfixture.PostgresHistoryRevisionTests.setUp


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'),'Disposable PostgreSQL integration DB not configured')
class PostgresWalletObservationTests(observations.WalletObservationTests):
    setUp=pgexec.PostgresExecutionTests.setUp
    def tearDown(self):
        try:super().tearDown()
        finally:self.env.stop()


if __name__=='__main__':unittest.main()


from tests.legacy_config import apply as _legacy
_legacy(globals())
