"""One place to build and call the Gemini model for every node.

Handles what each node used to do (or skip) on its own:
- model name from GEMINI_MODEL, so a deprecated model is a one-line .env change
- request timeout (LLM_TIMEOUT, seconds) so a hung call cannot freeze the pipeline
- retries on 408/429/5xx and network timeouts: LLM_MAX_ATTEMPTS tries (default 4)
  with backoff starting at LLM_RETRY_DELAY seconds (4, 8, 16...), which covers a
  per-minute quota window. Worst case per call ~ attempts x timeout + backoff.
- one shared rate limiter (LLM_RPM requests per minute) to stay under free-tier limits
- daily-quota fallback: free-tier quotas are per model (20 requests/day for
  gemini-3.5-flash), so when one model's daily quota is gone, calls move to the
  next model in GEMINI_FALLBACK_MODELS; once all are gone, calls fail at once
  instead of each one retrying for half a minute
- text extraction that works whether the reply is a string or a list of blocks
"""

from __future__ import annotations

import os
import threading
import warnings
from typing import Any, Optional

from langchain_core.rate_limiters import InMemoryRateLimiter

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_FALLBACKS = "gemini-3.5-flash-lite,gemini-3.1-flash-lite"

# Lite models ignore temperature and warn on every call; the warning is noise.
warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")


class QuotaExhaustedError(RuntimeError):
    """The daily Gemini quota is used up; retrying today will not help."""


_lock = threading.Lock()
_rate_limiter: Optional[InMemoryRateLimiter] = None
_exhausted: dict[str, str] = {}  # model -> quota error message


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def get_rate_limiter() -> InMemoryRateLimiter:
    """Shared by every model instance, so the limit holds across nodes."""
    global _rate_limiter
    with _lock:
        if _rate_limiter is None:
            rpm = max(_env_float("LLM_RPM", 8), 0.1)
            _rate_limiter = InMemoryRateLimiter(
                requests_per_second=rpm / 60, check_every_n_seconds=0.1, max_bucket_size=1
            )
        return _rate_limiter


def model_chain() -> list[str]:
    """Primary model, then fallbacks (GEMINI_FALLBACK_MODELS="" disables them)."""
    chain = [os.getenv("GEMINI_MODEL", DEFAULT_MODEL)]
    for m in os.getenv("GEMINI_FALLBACK_MODELS", DEFAULT_FALLBACKS).split(","):
        if m.strip() and m.strip() not in chain:
            chain.append(m.strip())
    return chain


def active_model() -> str:
    """First model in the chain whose daily quota is not used up."""
    for m in model_chain():
        if m not in _exhausted:
            return m
    raise QuotaExhaustedError(
        "Gemini daily quota exhausted on every model (" + ", ".join(model_chain()) + "); "
        "skipping remaining LLM calls. " + next(iter(_exhausted.values()), "")[:200]
    )


def api_key() -> Optional[str]:
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


def get_llm(temperature: float = 0.1, max_output_tokens: Optional[int] = None,
            timeout: Optional[float] = None, key: Optional[str] = None):
    """Build a Gemini chat model with timeout, retries and rate limiting."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, Any] = {}
    if max_output_tokens:
        kwargs["max_output_tokens"] = max_output_tokens
    if os.getenv("GEMINI_BASE_URL"):  # proxy, or the fake server in tests
        kwargs["base_url"] = os.environ["GEMINI_BASE_URL"]
    return ChatGoogleGenerativeAI(
        model=_safe_active_model(),
        temperature=temperature,
        google_api_key=key or api_key(),
        # LLM_TIMEOUT in .env overrides the per-node defaults when it is set.
        timeout=_env_float("LLM_TIMEOUT", 0) or timeout or 120,
        max_retries=_attempts(),
        rate_limiter=get_rate_limiter(),
        **kwargs,
    )


def _attempts() -> int:
    return max(int(_env_float("LLM_MAX_ATTEMPTS", 4)), 1)


def _retry_http_options():
    """Per-call retry policy (LangChain only exposes the attempt count)."""
    from google.genai.types import HttpOptions, HttpRetryOptions

    delay = max(_env_float("LLM_RETRY_DELAY", 4), 0.01)
    return HttpOptions(retry_options=HttpRetryOptions(
        attempts=_attempts(),
        initial_delay=delay,
        max_delay=60,
        exp_base=2,
        jitter=delay / 4,  # SDK default is a flat 1s, too coarse for small delays
    ))


def response_text(response: Any) -> str:
    """Plain text of a model reply (newer Gemini models return content blocks)."""
    text = getattr(response, "text", None)
    if callable(text) and not isinstance(text, str):  # older langchain-core: .text() method
        text = text()
    if isinstance(text, str):
        return text.strip()
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in content]
        return "".join(parts).strip()
    return str(content).strip()


def is_daily_quota_error(error: BaseException) -> bool:
    """429 RESOURCE_EXHAUSTED on a per-day quota (per-minute ones are retried)."""
    msg = str(error)
    exhausted = "429" in msg or "RESOURCE_EXHAUSTED" in msg
    return exhausted and ("PerDay" in msg or "per day" in msg.lower())


def classify_error(error: BaseException) -> tuple[str, int]:
    """Map an LLM failure to (kind, HTTP status) for API callers and the UI."""
    msg = f"{type(error).__name__} {error}"
    if isinstance(error, QuotaExhaustedError) or is_daily_quota_error(error):
        return "daily_quota", 429
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "RateLimit" in msg:
        return "rate_limited", 429
    if "Timeout" in msg or "timed out" in msg.lower() or "DEADLINE_EXCEEDED" in msg or isinstance(error, TimeoutError):
        return "timeout", 504
    if any(s in msg for s in ("API key", "401", "403", "PERMISSION_DENIED", "Authentication")):
        return "auth", 401
    return "llm_error", 502


def _safe_active_model() -> str:
    try:
        return active_model()
    except QuotaExhaustedError:
        return model_chain()[0]  # building is fine; the call itself will refuse


def check_quota() -> None:
    active_model()


def record_error(error: BaseException, model: str) -> None:
    if is_daily_quota_error(error):
        with _lock:
            _exhausted[model] = str(error)[:300]
        print(f"  [quota] daily quota used up on {model}")


def reset_quota() -> None:
    """Called at the start of each pipeline run: quotas reset daily."""
    with _lock:
        _exhausted.clear()


def reset_state() -> None:
    """Forget quota state and the limiter (new run, new key, or tests)."""
    global _rate_limiter
    with _lock:
        _exhausted.clear()
        _rate_limiter = None


def _on_model(llm, model: str):
    """Same settings, different model (the SDK client is model-agnostic)."""
    return llm if llm.model == model else llm.model_copy(update={"model": model})


def invoke(llm, messages) -> str:
    while True:
        model = active_model()  # raises once every model is exhausted
        try:
            return response_text(_on_model(llm, model).invoke(messages, http_options=_retry_http_options()))
        except Exception as e:
            record_error(e, model)
            if not is_daily_quota_error(e):
                raise


async def ainvoke(llm, messages) -> str:
    while True:
        model = active_model()
        try:
            reply = await _on_model(llm, model).ainvoke(messages, http_options=_retry_http_options())
            return response_text(reply)
        except Exception as e:
            record_error(e, model)
            if not is_daily_quota_error(e):
                raise
