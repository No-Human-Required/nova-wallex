import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from app.custom_research import period, setup
from app.research import finish
from test_portfolio import fixture_history, T0


def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).isoformat()


class CustomPeriodTests(unittest.TestCase):
    def setUp(self):
        self.h=SimpleNamespace(universe={'requested_start':T0,'requested_end':T0+1200*3600})

    def test_archive_identity_unchanged(self):
        self.assertEqual(period(self.h,32),(T0+2304*3600,T0+2376*3600))

    def test_custom_day_and_week(self):
        for hours in (24,168,744):
            start=T0+80*3600;end=start+hours*3600
            self.assertEqual(period(self.h,1,iso(start),iso(end)),(start,end))

    def test_invalid_boundaries_fail_closed(self):
        for start,end in [(T0,T0+80*3600),(T0+80*3600,T0+81*3600),(T0+80*3600,T0+79*3600),(T0+80*3600,T0+1300*3600),(T0+80*3600+1,T0+104*3600)]:
            with self.assertRaises(ValueError):period(self.h,1,iso(start),iso(end))
        with self.assertRaises(ValueError):period(self.h,1,'2026-10-01T00:00:00','2026-10-02T00:00:00')

    def test_missing_end_rejected(self):
        with self.assertRaises(ValueError):period(self.h,1,iso(T0+80*3600),None)

    def test_custom_ai_cannot_claim_unrecorded_responses(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):setup(self.h,'guarded_breakout_ai',32,'base',Path(d),iso(T0+80*3600),iso(T0+104*3600))

    def test_custom_24_hour_cash_accounting(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);h=fixture_history(root/'data',rising=True)
            e,a,start,end=setup(h,'cash',1,'base',root/'run',iso(T0+80*3600),iso(T0+104*3600))
            try:
                for t in range(start,end,3600):e.tick(t,start)
                result=finish(e,end,root/'run',{'start':start,'end':end})
                self.assertEqual(float(result['final_nav_tmn']),5000000)
                self.assertEqual(end-start,24*3600)
            finally:a.close()
