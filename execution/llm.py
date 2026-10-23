"""OpenAI-compatible LLM providers the operator may select.

Only the listed HTTPS hosts can ever receive an API key: a base URL edited in
the settings page is accepted only when its host is one of the provider's
pinned hosts. Redirects are refused and a billed request is never repeated
blindly. The live engine uses the provider recorded in its approved config;
switching provider, model or key is applied through the audited operator
upgrade, never silently.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

PROVIDERS = {
    'avalai': {'fa': 'AvalAI', 'base_url': 'https://api.avalai.ir/v1', 'hosts': ['api.avalai.ir'],
               'models': ['deepseek-v4.1-flash', 'gpt-5.4-mini', 'gpt-4.1-mini', 'gemini-2.5-flash'],
               'ladder': ['reasoning_low', 'thinking_disabled', 'plain_large_budget'],
               'docs': 'https://docs.avalai.ir'},
    'metisai': {'fa': 'MetisAI', 'base_url': 'https://api.metisai.ir/openai/v1', 'hosts': ['api.metisai.ir'],
                'models': ['gpt-4o-mini', 'gpt-4.1-mini', 'gpt-4o', 'deepseek-v4-flash', 'deepseek-v4-pro', 'grok-4-fast', 'metis-gpt'],
                'ladder': ['plain_large_budget', 'reasoning_low'],
                # docs.metisai.ir: each vendor has its own OpenAI-compatible base path.
                'presets': {'OpenAI (GPT)': 'https://api.metisai.ir/openai/v1', 'DeepSeek': 'https://api.metisai.ir/deepseek/v1',
                            'Grok (xAI)': 'https://api.metisai.ir/api/v1/wrapper/grok', 'اینترنت ملی (metis-gpt)': 'https://api.metisai.ir/api/v1/wrapper/metis'},
                'preset_models': {'https://api.metisai.ir/deepseek/v1': ['deepseek-v4-flash', 'deepseek-v4-pro'],
                                  'https://api.metisai.ir/api/v1/wrapper/metis': ['metis-gpt'],
                                  'https://api.metisai.ir/api/v1/wrapper/grok': ['grok-4-fast', 'grok-4', 'grok-3-mini']},
                'docs': 'https://docs.metisai.ir/api/wrapper/openai'},
    'boxapi': {'fa': 'BoxAPI', 'base_url': 'https://ai.boxapi.ir/ai/v1', 'hosts': ['ai.boxapi.ir', 'irai.boxapi.ir'],
               'models': ['gpt-5.4-mini', 'gpt-4o-mini', 'gpt-4o'],
               'ladder': ['plain_large_budget', 'reasoning_low'],
               'presets': {'اینترنت بین‌الملل': 'https://ai.boxapi.ir/ai/v1', 'اینترنت ملی': 'https://irai.boxapi.ir/api/v1'},
               'docs': 'https://boxapi.ir/docs/ai/ir-chatgpt/'},
}
DEFAULT = 'avalai'


class LLMError(RuntimeError):
    def __init__(self, status, label):
        self.status = status
        super().__init__(f'{label}: HTTP {status}; response body omitted')


def provider(name):
    if name not in PROVIDERS:
        raise ValueError('Unknown LLM provider')
    return PROVIDERS[name]


def base_url(name, url=None):
    p = provider(name)
    url = (url or p['base_url']).strip().rstrip('/')
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in p['hosts'] or parts.username or parts.password or parts.query or parts.fragment or parts.port:
        raise ValueError('Base URL must be HTTPS on '+', '.join(p['hosts']))
    return url


def endpoint(cfg):
    name = cfg.get('ai_provider') or DEFAULT
    return base_url(name, cfg.get('ai_base_url'))+'/chat/completions'


def hosts():
    return {h for p in PROVIDERS.values() for h in p['hosts']}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_json(url, *, headers=None, body=None, timeout=60):
    """Single POST to a pinned provider host; same contract as starwallex.net.request_json."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in hosts():
        raise ValueError('Unapproved API origin')
    data = json.dumps(body, allow_nan=False).encode()
    req = urllib.request.Request(url, data=data, headers={'Accept': 'application/json', 'Content-Type': 'application/json', **(headers or {})})
    start = time.monotonic()
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout) as response:
            result = json.load(response)
            return result, {'latency_ms': round((time.monotonic()-start)*1000, 2), 'request_id': response.headers.get('x-request-id'),
                            'http_status': response.status, 'server_date': response.headers.get('Date')}
    except urllib.error.HTTPError as exc:
        raise LLMError(exc.code, parts.path) from None
    except (TimeoutError, urllib.error.URLError):
        raise LLMError(0, 'network unavailable') from None


def get_json(url, *, headers=None, timeout=20):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in hosts():
        raise ValueError('Unapproved API origin')
    req = urllib.request.Request(url, headers={'Accept': 'application/json', **(headers or {})})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise LLMError(exc.code, parts.path) from None
    except (TimeoutError, urllib.error.URLError):
        raise LLMError(0, 'network unavailable') from None


def model_ids(raw):
    """Model identifiers from an OpenAI-style /models listing (tolerant of variants)."""
    rows = raw.get('data') if isinstance(raw, dict) else raw
    if isinstance(rows, dict):
        rows = rows.get('models') or rows.get('data')
    out = []
    for r in rows or []:
        ident = (r.get('id') or r.get('name') or r.get('model')) if isinstance(r, dict) else r
        if isinstance(ident, str) and 1 < len(ident) <= 120 and not any(c.isspace() for c in ident):
            out.append(ident)
    return sorted(set(out))


def text_of(raw):
    choice = raw['choices'][0]
    message = choice.get('message') or {}
    return message.get('content') or '', choice.get('finish_reason'), message.get('reasoning_content') or message.get('reasoning') or ''


def parse_json(text):
    text = (text or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        raise ValueError('Model answer contains no JSON object')
    return json.loads(text[start:end+1])
