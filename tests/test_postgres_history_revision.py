"""The source-revision protocol against a disposable real PostgreSQL server."""
import os
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.main import create_app
from execution.tests.test_controller import SyntheticHistory
from tests import test_history_revision as revision_tests


@unittest.skipUnless(os.getenv('SW_TEST_DATABASE_URL'),'Disposable PostgreSQL integration DB not configured')
class PostgresHistoryRevisionTests(revision_tests.HistoryRevisionTests):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'SW_DATABASE_URL':os.environ['SW_TEST_DATABASE_URL'],
            'SW_DB_NAMESPACE':'rev_'+secrets.token_hex(5),'SW_DATA_DIR':str(self.root),
            'SW_PUBLIC_ORIGIN':'http://127.0.0.1:8787','SW_VAULT_KEY':Fernet.generate_key().decode()})
        self.env.start();self.h=SyntheticHistory('AAATMN')
        self.app=create_app(directory=self.root,history=self.h,development=True,start_worker=False)
        self.client=TestClient(self.app,base_url='http://127.0.0.1:8787');self.client.__enter__()
        self.headers={'Origin':'http://127.0.0.1:8787','X-CSRF-Token':self.client.get('/api/session').json()['csrf']}


if __name__=='__main__':unittest.main()


from tests.legacy_config import apply as _legacy
_legacy(globals())
