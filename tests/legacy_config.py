"""Pre-3.4 suites exercise runs activated with the legacy guarded policy."""
import unittest
from unittest import mock


def apply(namespace):
    import app.live_api as live_api
    for value in list(namespace.values()):
        if isinstance(value, type) and issubclass(value, unittest.TestCase):
            original = value.setUp

            def setUp(self, _original=original):
                patcher = mock.patch.object(live_api, 'risk_config', live_api.legacy_risk_config)
                patcher.start()
                self.addCleanup(patcher.stop)
                _original(self)
            value.setUp = setUp
