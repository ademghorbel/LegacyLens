"""Quota, retry, timeout and rate-limit behaviour, run through the real
google-genai SDK against a local fake Gemini server."""

import time

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent import llm as llm_mod
from agent.llm import QuotaExhaustedError, get_llm, invoke, ainvoke, response_text
from fake_gemini import DAILY_QUOTA, MINUTE_QUOTA, error_body, ok_body

MSG = [HumanMessage(content="hi")]


# ── reply parsing ────────────────────────────────────────────────────────────

def test_response_text_handles_string_and_block_replies():
    assert response_text(AIMessage(content="  plain ")) == "plain"
    blocks = [{"type": "text", "text": "a", "extras": {"signature": "x"}}, {"type": "text", "text": "b"}]
    assert response_text(AIMessage(content=blocks)) == "ab"


def test_daily_vs_minute_quota_detection():
    assert llm_mod.is_daily_quota_error(Exception(f"429 {DAILY_QUOTA}"))
    assert not llm_mod.is_daily_quota_error(Exception(f"429 {MINUTE_QUOTA}"))
    assert not llm_mod.is_daily_quota_error(Exception("500 internal"))


# ── retries ──────────────────────────────────────────────────────────────────

def test_per_minute_429_is_retried_then_succeeds(gemini):
    gemini.queue((429, MINUTE_QUOTA), (429, MINUTE_QUOTA), (200, ok_body("recovered")))
    assert invoke(get_llm(), MSG) == "recovered"
    assert len(gemini.requests) == 3


def test_backoff_grows_between_attempts(gemini, monkeypatch):
    monkeypatch.setenv("LLM_RETRY_DELAY", "0.3")
    gemini.queue((503, error_body(503, "UNAVAILABLE", "overloaded")),
                 (503, error_body(503, "UNAVAILABLE", "overloaded")),
                 (200, ok_body("OK")))
    invoke(get_llm(), MSG)
    t = [r[0] for r in gemini.requests]
    gap1, gap2 = t[1] - t[0], t[2] - t[1]
    assert 0.28 <= gap1 < 0.6, gap1     # 0.3s + up to 25% jitter
    assert 0.58 <= gap2 < 1.0, gap2     # 0.6s: doubled


def test_gives_up_after_max_attempts(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "3")
    gemini.queue((503, error_body(503, "UNAVAILABLE", "overloaded")))
    with pytest.raises(Exception, match="503"):
        invoke(get_llm(), MSG)
    assert len(gemini.requests) == 3


def test_auth_error_is_not_retried(gemini):
    gemini.queue((400, error_body(400, "INVALID_ARGUMENT", "API key not valid")))
    with pytest.raises(Exception, match="API key not valid"):
        invoke(get_llm(), MSG)
    assert len(gemini.requests) == 1


# ── timeouts ─────────────────────────────────────────────────────────────────

def test_timeout_is_enforced_and_retried(gemini, monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "0.5")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "2")
    gemini.queue((200, ok_body("too late"), 3))
    start = time.monotonic()
    with pytest.raises(Exception):
        invoke(get_llm(), MSG)
    elapsed = time.monotonic() - start
    assert len(gemini.requests) == 2
    assert elapsed < 2.5, f"timeout not enforced, took {elapsed:.1f}s"


def test_slow_first_attempt_recovers_on_retry(gemini, monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "0.5")
    gemini.queue((200, ok_body("late"), 2), (200, ok_body("fast")))
    assert invoke(get_llm(), MSG) == "fast"


async def test_async_path_has_the_same_timeout(gemini, monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "0.5")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    gemini.queue((200, ok_body("too late"), 3))
    start = time.monotonic()
    with pytest.raises(Exception):
        await ainvoke(get_llm(), MSG)
    assert time.monotonic() - start < 2


# ── daily quota breaker ──────────────────────────────────────────────────────

def test_daily_quota_trips_breaker_and_later_calls_fail_fast(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "2")
    gemini.queue((429, DAILY_QUOTA))
    with pytest.raises(Exception, match="429"):
        invoke(get_llm(), MSG)
    sent = len(gemini.requests)

    start = time.monotonic()
    with pytest.raises(QuotaExhaustedError):
        invoke(get_llm(), MSG)
    assert len(gemini.requests) == sent, "breaker should not hit the API again"
    assert time.monotonic() - start < 0.1


def test_minute_quota_does_not_trip_breaker(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    gemini.queue((429, MINUTE_QUOTA), (200, ok_body("OK")))
    with pytest.raises(Exception):
        invoke(get_llm(), MSG)
    assert invoke(get_llm(), MSG) == "OK"


def test_reset_quota_reopens_breaker(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    gemini.queue((429, DAILY_QUOTA), (200, ok_body("OK")))
    with pytest.raises(Exception):
        invoke(get_llm(), MSG)
    llm_mod.reset_quota()
    assert invoke(get_llm(), MSG) == "OK"


# ── rate limiting ────────────────────────────────────────────────────────────

def test_rate_limiter_is_shared_and_spaces_calls(gemini, monkeypatch):
    monkeypatch.setenv("LLM_RPM", "240")  # one call every 0.25s
    llm_mod.reset_state()
    gemini.queue((200, ok_body("OK")))
    a, b = get_llm(), get_llm()
    assert a.rate_limiter is b.rate_limiter
    for model in (a, b, a, b):
        invoke(model, MSG)
    t = [r[0] for r in gemini.requests]
    assert t[-1] - t[0] >= 0.6  # 3 gaps of ~0.25s


@pytest.mark.parametrize("error,expected", [
    (QuotaExhaustedError("x"), ("daily_quota", 429)),
    (Exception(f"429 {DAILY_QUOTA}"), ("daily_quota", 429)),
    (Exception(f"429 {MINUTE_QUOTA}"), ("rate_limited", 429)),
    (TimeoutError(), ("timeout", 504)),
    (type("ReadTimeout", (Exception,), {})(""), ("timeout", 504)),
    (Exception("504 DEADLINE_EXCEEDED"), ("timeout", 504)),
    (Exception("400 API key not valid"), ("auth", 401)),
    (Exception("500 internal"), ("llm_error", 502)),
])
def test_classify_error(error, expected):
    assert llm_mod.classify_error(error) == expected


def test_model_and_settings_come_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("LLM_TIMEOUT", "42")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "3")
    model = get_llm()
    assert (model.model, model.timeout, model.max_retries) == ("gemini-test", 42, 3)
    assert get_llm(timeout=7).timeout == 42, ".env wins over node defaults"
    monkeypatch.delenv("LLM_TIMEOUT")
    assert get_llm(timeout=7).timeout == 7
    assert get_llm().timeout == 120


# ── per-model daily quota fallback ───────────────────────────────────────────

def _quota_on(gemini, *dead_models):
    """Daily quota is gone on these models; others answer with their own name."""
    def respond(prompt, n):
        model = gemini.last_path.split("models/")[-1].split(":")[0]
        return (429, DAILY_QUOTA) if model in dead_models else (200, ok_body(model))
    gemini.respond_with(respond)


def _models_hit(gemini):
    return [p.split("models/")[-1].split(":")[0] for _, p in gemini.requests]


def test_daily_quota_falls_back_to_next_model(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "lite-a,lite-b")
    _quota_on(gemini, "gemini-3.5-flash")

    assert invoke(get_llm(), MSG) == "lite-a"
    assert invoke(get_llm(), MSG) == "lite-a"
    assert _models_hit(gemini) == ["gemini-3.5-flash", "lite-a", "lite-a"], "primary is not retried once dead"


async def test_fallback_walks_the_whole_chain_then_stops(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "lite-a,lite-b")
    _quota_on(gemini, "gemini-3.5-flash", "lite-a")
    assert await ainvoke(get_llm(), MSG) == "lite-b"

    _quota_on(gemini, "gemini-3.5-flash", "lite-a", "lite-b")
    with pytest.raises(QuotaExhaustedError, match="every model"):
        await ainvoke(get_llm(), MSG)
    assert _models_hit(gemini) == ["lite-b"]
    with pytest.raises(QuotaExhaustedError):
        invoke(get_llm(), MSG)
    assert len(gemini.requests) == 1, "nothing left to try: no more API calls"


def test_minute_quota_does_not_switch_model(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "lite-a")
    gemini.queue((429, MINUTE_QUOTA))
    with pytest.raises(Exception, match="429"):
        invoke(get_llm(), MSG)
    assert _models_hit(gemini) == ["gemini-3.5-flash"]


def test_new_models_start_on_the_first_live_model(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "lite-a")
    _quota_on(gemini, "gemini-3.5-flash")
    invoke(get_llm(), MSG)
    assert get_llm().model == "lite-a"
    llm_mod.reset_quota()
    assert get_llm().model == "gemini-3.5-flash"
