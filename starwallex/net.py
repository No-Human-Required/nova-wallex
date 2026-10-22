"""Small transport: credential hosts pinned, redirects refused, no exchange writes."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class APIError(RuntimeError):
    def __init__(self, status, label):
        self.status = status
        super().__init__(f"{label}: HTTP {status}; response body omitted")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, *, headers=None, body=None, timeout=25, attempts=2):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"api.wallex.ir", "api.avalai.ir"}:
        raise ValueError("Unapproved API origin")
    if parts.hostname == "api.wallex.ir" and body is not None:
        raise PermissionError("Exchange writes are disabled: shadow-only")
    headers = {"Accept": "application/json", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body, allow_nan=False).encode()
        headers["Content-Type"] = "application/json"
        attempts = 1  # Never repeat a billed request blindly.
    start = time.monotonic()
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
                result = json.load(response)
                return result, {"latency_ms": round((time.monotonic()-start)*1000, 2), "request_id": response.headers.get("x-request-id"), "http_status": response.status, "server_date": response.headers.get("Date")}
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt+1 == attempts:
                raise APIError(exc.code, parts.path) from None
            retry = exc.headers.get("Retry-After", "1")
            time.sleep(min(float(retry) if retry.isdigit() else 1, 5))
        except (TimeoutError, urllib.error.URLError):
            if attempt+1 == attempts:
                raise APIError(0, "network unavailable") from None
            time.sleep(1)
