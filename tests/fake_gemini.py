"""A tiny local stand-in for the Gemini REST API.

Each test queues the responses it wants (status code, delay, text), so the
real google-genai SDK retry, backoff and timeout code runs against it.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def ok_body(text: str) -> dict:
    return {
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
    }


def error_body(code: int, status: str, message: str) -> dict:
    return {"error": {"code": code, "status": status, "message": message}}


DAILY_QUOTA = error_body(
    429, "RESOURCE_EXHAUSTED",
    "You exceeded your current quota. Quota exceeded for metric: generate_content_free_tier_requests, "
    "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit: 250",
)
MINUTE_QUOTA = error_body(
    429, "RESOURCE_EXHAUSTED",
    "Quota exceeded for quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier, limit: 10",
)


def _prompt_text(raw: bytes) -> str:
    """All text parts of a generateContent request, joined."""
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        return ""
    texts = []
    for content in data.get("contents", []) + [data.get("systemInstruction") or {}]:
        for part in content.get("parts", []):
            texts.append(part.get("text", ""))
    return "\n".join(texts)


class FakeGemini:
    def __init__(self):
        self.script = []          # list of (status, body, delay); last entry repeats
        self.responder = None     # optional fn(prompt_text, n) -> (status, body[, delay])
        self.requests = []        # (time, path)
        self.prompts = []         # prompt text per request (responder mode)
        self.last_path = ""       # e.g. /v1beta/models/gemini-3.5-flash:generateContent
        self._lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                with fake._lock:
                    fake.requests.append((time.monotonic(), self.path))
                    n = len(fake.requests)
                    fake.last_path = self.path
                    if fake.responder:
                        prompt = _prompt_text(raw)
                        fake.prompts.append(prompt)
                        step = fake.responder(prompt, n)
                        status, body, delay = step if len(step) == 3 else (*step, 0)
                    else:
                        idx = min(n - 1, len(fake.script) - 1)
                        status, body, delay = fake.script[idx] if fake.script else (200, ok_body("OK"), 0)
                if delay:
                    time.sleep(delay)
                payload = json.dumps(body).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass  # client gave up (timeout test)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def queue(self, *steps):
        """steps: (status, body) or (status, body, delay_seconds)."""
        self.script = [s if len(s) == 3 else (*s, 0) for s in steps]
        self.requests.clear()

    def respond_with(self, fn):
        """fn(prompt_text, request_number) -> (status, body) or (status, body, delay)."""
        self.responder = fn
        self.requests.clear()
        self.prompts.clear()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
