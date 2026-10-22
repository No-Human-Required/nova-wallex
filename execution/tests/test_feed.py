import tempfile
import unittest
from decimal import Decimal as D

from starwallex.util import digest
from execution.feed import PublicFeed

MARKET={'symbol':'USDTTMN','baseAsset':'USDT','quoteAsset':'TMN','stepSize':2,'tickSize':0,'minQty':'0.01','minNotional':'50000'}
UNIVERSE={'markets':{'USDTTMN':MARKET},'exclusions_sha256':'fixture'}

class PublicFixture:
    requests=0
    def get(self,path):
        if path=='/v1/markets':return {'result':{'symbols':{'USDTTMN':MARKET}}},{'source':'unit_fixture'}
        if path=='/hector/web/v1/markets':return {'result':{'markets':[{'symbol':'USDTTMN','is_spot':True}]}},{'source':'unit_fixture'}
        raise AssertionError('Unexpected path')
    def history(self,s,start,end,quarantine):
        type(self).requests+=1
        bars=[{'ts':t,'open':'100','high':'100','low':'100','close':'100','volume':'1000000'} for t in range(start,end,3600)]
        return {'symbol':s,'requested_start':start,'requested_end':end,'bars':bars,'bars_sha256':digest(bars),
                'quality':{'status':'synthetic_unit_fixture'}}
    def depth(self,s):
        return {'bids':[(D(99),D(100))],'asks':[(D(101),D(100))],'observed_at':123.99,'meta':{'source':'unit_fixture'}}

class FeedTests(unittest.TestCase):
    def test_exact_closed_history_cutoff_and_immutable_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            PublicFixture.requests=0
            f=PublicFeed(UNIVERSE,temp,api_factory=PublicFixture,workers=1)
            self.assertEqual(f.verify_markets()['verified_pairs'],1)
            h=f.history(360000)
            self.assertEqual(len(h.rows['USDTTMN']),73)
            self.assertIsNone(h.bar('USDTTMN',360000))
            again=PublicFeed(UNIVERSE,temp,api_factory=PublicFixture,workers=1).history(360000)
            self.assertEqual(h.identity,again.identity);self.assertEqual(PublicFixture.requests,1)
    def test_no_exchange_timestamp_is_fabricated(self):
        with tempfile.TemporaryDirectory() as temp:
            f=PublicFeed(UNIVERSE,temp,api_factory=PublicFixture,workers=1)
            q=f.quotes({'USDTTMN'})['USDTTMN']
            self.assertEqual(q['observed_at'],123)
            self.assertFalse(q['exchange_timestamp_available'])
            with self.assertRaises(ValueError):f.quotes({'BLOCKED'})

if __name__=='__main__':unittest.main()
