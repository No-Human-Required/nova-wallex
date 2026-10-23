"""Per-pair screener detail rebuilt from the immutable hourly observations."""
import os
import tempfile
import unittest
from pathlib import Path

from starwallex.util import ROOT
from starwallex.portfolio_run import validated_config
from execution.adaptive import AdaptiveHistory, adaptive_config
from app import screener


@unittest.skipIf(os.environ.get('SW_DATABASE_URL'), 'observation symlink needs the file backend')
class ScreenerReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = AdaptiveHistory(ROOT/'data/portfolio')
        cls.cfg = adaptive_config(validated_config())
        cls.t = cls.h.universe['requested_start']+200*3600
        _, cls.coverage = cls.h.scan(cls.t, cls.cfg, 'adaptive')
        cls.pairs = cls.h.pairs[cls.t]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name)
        (self.run_dir/'observations').mkdir()
        os.symlink(ROOT/'data/portfolio', self.run_dir/'observations'/str(self.t))
        screener._done.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def test_replay_reproduces_recorded_counts_and_every_pair_stage(self):
        r = screener.replay_one(self.run_dir, self.t, self.cfg, self.coverage)
        self.assertEqual(r['pairs'], self.pairs)
        self.assertEqual(sum(1 for p in r['pairs'].values() if p.get('stage') == 'candidate'), self.coverage['signal']-self.coverage.get('below_quality', 0))

    def test_replay_that_differs_from_the_recorded_counts_is_not_used(self):
        tampered = {**self.coverage, 'signal': self.coverage['signal']+1}
        r = screener.replay_one(self.run_dir, self.t, self.cfg, tampered)
        self.assertNotIn('pairs', r)
        self.assertIn('mismatch', r)
        self.assertEqual(screener.replay_one(self.run_dir, self.t+3600*5000, self.cfg, self.coverage), {'unavailable': 'observation_missing'})

    def test_scans_without_pairs_are_replayed_in_the_background(self):
        scans = [{'time': self.t, 'coverage': self.coverage, 'regime': {'regime': 'x'}, 'pairs': {}},
                 {'time': self.t+3600, 'coverage': {}, 'regime': {'regime': 'x'}, 'pairs': {'AAATMN': {'stage': 'data'}}}]
        first = screener.pairs_for(self.run_dir, 'run', self.cfg, scans)
        self.assertEqual(first[self.t+3600][0], 'recorded')
        self.assertEqual(first[self.t][0], 'pending')
        worker = screener._worker
        if worker is not None:
            worker.join(60)
        again = screener.pairs_for(self.run_dir, 'run', self.cfg, scans)
        self.assertEqual(again[self.t], ('replayed', self.pairs))


if __name__ == '__main__':
    unittest.main()
