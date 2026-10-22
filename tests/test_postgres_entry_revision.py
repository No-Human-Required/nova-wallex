import unittest
import os
from tests import test_entry_revision as fixture
from tests import test_postgres_history_revision as pgfixture


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'),'Disposable PostgreSQL integration DB not configured')
class PostgresEntryRevisionTests(fixture.EntryRevisionTests):
    setUp=pgfixture.PostgresHistoryRevisionTests.setUp


if __name__=='__main__':unittest.main()
