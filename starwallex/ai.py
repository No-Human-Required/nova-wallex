import json
import time
from .net import request_json
from .strategy import validate_selection
from .util import ROOT, canonical, credential, digest, read_json, redact, write_json


class AvalaiSelector:
    def __init__(self, cfg, cache_dir, *, replay_only=False):
        self.cfg, self.cache_dir, self.replay_only = cfg, cache_dir, replay_only
        self.calls = 0
        self.prompt = (ROOT / "prompts/regime.txt").read_text(encoding="utf-8")
        self.key = None

    def select(self, f):
        payload = {"model": self.cfg["ai_model"], "messages": [{"role":"system", "content":self.prompt}, {"role":"user", "content":canonical({"features":f})}], "response_format":{"type":"json_object"}, "temperature":0, "max_tokens":800}
        key = digest(payload)
        path = self.cache_dir / (key + ".json")
        if path.exists():
            record = read_json(path)
            sealed={k:v for k,v in record.items() if k!='record_sha256'}
            if record.get('record_sha256')!=digest(sealed):
                raise ValueError('AI response integrity mismatch')
            if record["request_hash"] != key or digest(record["request"]) != key:
                raise ValueError("AI cache request hash mismatch")
            if record.get("status") == "ok":
                validate_selection(record["selection"], f)
            return record
        if self.replay_only:
            raise RuntimeError("Missing recorded AI response for replay")
        if self.calls >= self.cfg["ai_max_calls_per_run"]:
            return {"status":"unavailable", "reason":"AI call budget exhausted", "request_hash":key}
        self.calls += 1
        started = time.time()
        record = {"request_hash":key, "request":payload, "requested_at":started, "model_documented_backend":self.cfg["ai_model_documented_backend"]}
        try:
            self.key = self.key or credential("AVALAI_API_KEY")
            raw, meta = request_json("https://api.avalai.ir/v1/chat/completions", headers={"Authorization":"Bearer " + self.key}, body=payload, timeout=self.cfg["ai_timeout_seconds"])
            # Store actual structured output and API metadata, never credentials or hidden chain of thought.
            choice = raw["choices"][0]
            content = choice["message"].get("content", "")
            record.update({"content":redact(content), "finish_reason":choice.get("finish_reason"), "response_model":raw.get("model"), "usage":raw.get("usage"), "estimated_cost":raw.get("estimated_cost"), "meta":meta})
            if choice.get("finish_reason") != "stop":
                raise ValueError("Incomplete model output")
            record.update({"selection":validate_selection(json.loads(content), f), "status":"ok"})
        except Exception as exc:
            record.update({"status":"unavailable", "reason":type(exc).__name__, "http_status":getattr(exc,"status",None)})
        record["completed_at"] = time.time()
        record["latency_seconds"] = record["completed_at"]-started
        record=redact(record)
        record['record_sha256']=digest(record)
        write_json(path, record)
        return record
