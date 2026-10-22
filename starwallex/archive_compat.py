"""Narrow, explicit compatibility for legacy AI replies recorded using OS libm.

Only replay-only mode may use this. Model, prompt, order, IDs, liquidity and all
parameters must be exact. Five statistical features may differ by <=1e-9.
Ambiguous matches fail closed; a legacy reply is never called a fresh model call.
"""
import json
import math
from copy import deepcopy

from .util import canonical, digest, read_json

FEATURES = ('r1_bps', 'r6_bps', 'r24_bps', 'vol24_bps', 'z24_logclose')
ABS_TOLERANCE = 1e-9


def differences(current, archived):
    a, b = deepcopy(current), deepcopy(archived)
    try:
        observed = json.loads(a['messages'][1]['content'])
        recorded = json.loads(b['messages'][1]['content'])
        a['messages'][1]['content'] = b['messages'][1]['content']
        if canonical(a) != canonical(b) or set(observed) != set(recorded):
            return None
        rows, old_rows = observed.pop('candidates'), recorded.pop('candidates')
        if canonical(observed) != canonical(recorded) or len(rows) != len(old_rows):
            return None
        changes = []
        for row, old in zip(rows, old_rows):
            if set(row) != set(old):
                return None
            for field in FEATURES:
                x, y = row.pop(field), old.pop(field)
                if x is None or y is None:
                    if x is y: continue
                    return None
                if (isinstance(x, bool) or isinstance(y, bool)
                    or not isinstance(x, (int,float)) or not isinstance(y, (int,float))
                    or not math.isfinite(x) or not math.isfinite(y) or abs(x-y)>ABS_TOLERANCE):
                    return None
                if x != y:
                    changes.append({'id':row['id'], 'feature':field, 'recomputed':x, 'recorded':y, 'absolute_difference':abs(x-y)})
            if canonical(row) != canonical(old):
                return None
        return changes
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def load_archive(cache):
    records = []
    for path in sorted(cache.glob('*.json')):
        if len(path.stem) != 64 or any(c not in '0123456789abcdef' for c in path.stem):
            continue
        record = read_json(path)
        if (record.get('record_sha256') != digest({k:v for k,v in record.items() if k!='record_sha256'})
            or digest(record['request']) != path.stem or record.get('request_hash') != path.stem):
            raise ValueError('AI archive integrity failure')
        records.append(record)
    return records


def match_archive(payload, records):
    matches = [(r,delta) for r in records if (delta:=differences(payload,r['request'])) is not None]
    if not matches:
        raise RuntimeError('Missing recorded portfolio AI output')
    if len(matches) != 1:
        raise RuntimeError('Ambiguous legacy AI archive match')
    archived, delta = matches[0]
    record = deepcopy(archived)
    record['archived_record_sha256'] = record.pop('record_sha256')
    record['replay_compatibility'] = {'method':'legacy_libm_numeric_v1', 'absolute_tolerance':ABS_TOLERANCE,
        'recomputed_request_hash':digest(payload), 'archived_request_hash':archived['request_hash'],
        'differences':delta, 'new_model_call':False}
    record['record_sha256'] = digest(record)
    return record
