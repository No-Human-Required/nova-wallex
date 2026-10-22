import json
import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path

from starwallex.archive_compat import differences, match_archive, load_archive
from starwallex.portable_math import log
from starwallex.util import canonical, digest


def request():
    return {'model':'recorded-model','messages':[{'role':'system','content':'fixed prompt'},
      {'role':'user','content':canonical({'candidates':[{'id':'A1','r1_bps':1.,'r6_bps':389.0226070837477,
        'r24_bps':500.,'vol24_bps':12.,'z24_logclose':1.25,'roundtrip_cost_bps':90.,
        'liquidity':{'daily_turnover_tmn':100000000.,'prior_capacity_tmn':300000.}}],
        'max_positions':4,'max_gross_fraction':'0.40'})}], 'temperature':0}


def change(payload, path, value):
    p=deepcopy(payload); body=json.loads(p['messages'][1]['content'])
    target=body
    for k in path[:-1]: target=target[k]
    target[path[-1]]=value
    p['messages'][1]['content']=canonical(body)
    return p


class PortabilityTests(unittest.TestCase):
    def test_log_independent_of_ambient_decimal_precision(self):
        for value in [1.000001, .924682378, 22138741352., .0000001061]:
            with localcontext() as c:
                c.prec=70
                expected=float(Decimal.from_float(value).ln())
            with localcontext() as c:
                c.prec=8
                self.assertEqual(log(value),expected)
        for bad in [0,-1,float('inf'),float('nan')]:
            with self.assertRaises(ValueError):log(bad)

    def test_observed_cross_os_ulp_difference_is_explicit(self):
        old=request(); new=change(old,['candidates',0,'r6_bps'],389.02260708374763)
        delta=differences(new,old)
        self.assertEqual(len(delta),1)
        self.assertLess(delta[0]['absolute_difference'],1e-9)

    def test_material_signal_model_prompt_and_controls_cannot_match(self):
        old=request()
        mutations=[change(old,['candidates',0,'r6_bps'],389.023),change(old,['candidates',0,'id'],'A2'),
          change(old,['candidates',0,'liquidity','prior_capacity_tmn'],300001.),
          change(old,['candidates',0,'roundtrip_cost_bps'],91.),change(old,['max_positions'],3),
          change(old,['candidates',0,'r1_bps'],True),old|{'model':'other'}]
        altered=deepcopy(old);altered['messages'][0]['content']='other prompt';mutations.append(altered)
        for mutation in mutations:self.assertIsNone(differences(mutation,old))

    def test_missing_and_ambiguous_archives_fail_closed(self):
        p=request(); record={'request':p,'request_hash':digest(p),'record_sha256':'old'}
        with self.assertRaises(RuntimeError):match_archive(p,[])
        with self.assertRaises(RuntimeError):match_archive(p,[record,record])
        adapted=match_archive(change(p,['candidates',0,'r6_bps'],389.02260708374763),[record])
        self.assertFalse(adapted['replay_compatibility']['new_model_call'])
        self.assertEqual(adapted['archived_record_sha256'],'old')
        self.assertEqual(record['record_sha256'],'old')
        self.assertEqual(adapted['record_sha256'],digest({k:v for k,v in adapted.items() if k!='record_sha256'}))

    def test_archive_signature_and_filename_are_verified(self):
        p=request(); r={'request':p,'request_hash':digest(p)};r['record_sha256']=digest(r)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/(digest(p)+'.json');path.write_text(json.dumps(r),encoding='utf-8')
            self.assertEqual(len(load_archive(Path(d))),1)
            r['request']['model']='tampered';path.write_text(json.dumps(r),encoding='utf-8')
            with self.assertRaises(ValueError):load_archive(Path(d))


if __name__=='__main__':unittest.main()
