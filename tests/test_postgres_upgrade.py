import os
import unittest
from tests import test_upgrade_v4 as upgrade
from tests import test_postgres_history_revision as pg


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'), 'Disposable PostgreSQL integration DB not configured')
class PostgresUpgradeTests(upgrade.UpgradeTests):
    setUp = pg.PostgresHistoryRevisionTests.setUp


from tests.legacy_config import apply as _legacy
_legacy(globals())
