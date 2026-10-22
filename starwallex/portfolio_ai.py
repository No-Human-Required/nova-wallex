"""Recorded, schema-checked AvalAI entry selection; no exchange connectivity."""
import json
import time

from .net import request_json
from .archive_compat import load_archive, match_archive
from .util import ROOT, canonical, credential, digest, read_json, redact, write_json
from .persistence import file_exists


def validate_selection(selection, ids):
    if not isinstance(selection, dict) or set(selection) != {'allowed_ids', 'confidence', 'reason', 'evidence'}:
        raise ValueError('Invalid portfolio AI schema')
    allowed = selection['allowed_ids']
    if not isinstance(allowed, list) or any(not isinstance(i, str) for i in allowed) or len(set(allowed)) != len(allowed) or not set(allowed) <= set(ids):
        raise ValueError('Unknown or duplicate asset ID')
    confidence = selection['confidence']
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError('Invalid confidence')
    if not isinstance(selection['reason'], str) or not 1 <= len(selection['reason']) <= 2000:
        raise ValueError('Missing concise reason')
    evidence = selection['evidence']
    if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) for x in evidence) or not set(evidence) <= {'r1_bps', 'r6_bps', 'r24_bps', 'vol24_bps', 'z24_logclose', 'roundtrip_cost_bps', 'liquidity'}:
        raise ValueError('Unsupported evidence')
    return selection


class PortfolioAI:
    def __init__(self, cache, *, replay_only=False):
        self.cache, self.replay_only, self.calls = cache, replay_only, 0
        self.prompt = (ROOT/'prompts/portfolio.txt').read_text(encoding='utf-8')
        self.records = {}
        self.archive_records = None

    def select(self, candidates, cfg):
        if not candidates:
            return [], {'status': 'no_candidates', 'selection': {'allowed_ids': []}, 'actual_api_call': False}
        mapping = {f'A{i+1}': c for i, c in enumerate(candidates)}
        items = []
        for ident, c in mapping.items():
            f = c['features']
            items.append({'id': ident, **{k: f[k] for k in ['r1_bps', 'r6_bps', 'r24_bps', 'vol24_bps', 'z24_logclose']},
                          'roundtrip_cost_bps': c['roundtrip_cost_bps'],
                          'liquidity': {'daily_turnover_tmn': f['daily_turnover_tmn'],
                                        'prior_capacity_tmn': f['prior_capacity_tmn']*float(cfg['participation'])}})
        payload = {'model': cfg['ai_model'], 'messages': [{'role': 'system', 'content': self.prompt},
                    {'role': 'user', 'content': canonical({'candidates': items, 'max_positions': cfg['max_positions'],
                    'max_gross_fraction': cfg['max_gross_fraction']})}],
                   'response_format': {'type': 'json_object'}, 'temperature': 0,
                   'max_tokens': cfg['ai_max_output_tokens']}
        key = digest(payload)
        path = self.cache/(key+'.json')
        if file_exists(path):
            record = read_json(path)
            if record.get('record_sha256') != digest({k:v for k,v in record.items() if k != 'record_sha256'}) or digest(record['request']) != key:
                raise ValueError('AI cache integrity failure')
            if record['status'] == 'ok': validate_selection(record['selection'], mapping)
        elif self.replay_only:
            if self.archive_records is None:
                self.archive_records = load_archive(self.cache)
            record = match_archive(payload, self.archive_records)
            if record['status'] == 'ok': validate_selection(record['selection'], mapping)
        else:
            if self.calls >= cfg['ai_max_calls']:
                return [], {'status': 'unavailable', 'reason': 'call_budget', 'request_hash': key}
            self.calls += 1
            started = time.time()
            record = {'request': payload, 'request_hash': key, 'requested_at': started,
                      'documented_backend': cfg['ai_model_documented_backend']}
            try:
                raw, meta = request_json('https://api.avalai.ir/v1/chat/completions',
                    headers={'Authorization': 'Bearer '+credential('AVALAI_API_KEY')}, body=payload,
                    timeout=cfg['ai_timeout_seconds'])
                choice = raw['choices'][0]
                content = choice['message'].get('content', '')
                record.update(content=redact(content), response_model=raw.get('model'), usage=raw.get('usage'),
                              estimated_cost=raw.get('estimated_cost'), meta=meta, finish_reason=choice.get('finish_reason'))
                if choice.get('finish_reason') != 'stop': raise ValueError('Incomplete AI output')
                record['selection'] = validate_selection(json.loads(content), mapping)
                record['status'] = 'ok'
            except Exception as exc:
                record.update(status='unavailable', reason=type(exc).__name__,
                              validation_error=str(exc) if isinstance(exc, (ValueError, KeyError)) else None,
                              http_status=getattr(exc, 'status', None))
            record['latency_seconds'] = time.time()-started
            record = redact(record)
            record['record_sha256'] = digest(record)
            write_json(path, record)
        self.records[key] = record
        if record['status'] != 'ok' or record['selection']['confidence'] < cfg['ai_min_confidence']:
            return [], record
        return [mapping[i] for i in record['selection']['allowed_ids']], record
