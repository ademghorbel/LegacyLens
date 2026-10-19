"""FastAPI endpoints: health, analyse, and chat error mapping (quota -> 429, timeout -> 504)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fake_gemini import DAILY_QUOTA, MINUTE_QUOTA, ok_body

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.main import app  # noqa: E402

client = TestClient(app)
EXAMPLE = str(Path(__file__).resolve().parents[1] / "examples" / "demo_project")
CHAT = {"message": "How do we modernise this?", "analysis_results": {"detected_languages": ["vb6"]}, "history": []}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_ok(gemini):
    gemini.queue((200, ok_body("Rewrite the form in React.")))
    r = client.post("/chat", json=CHAT)
    assert r.status_code == 200 and r.json() == {"reply": "Rewrite the form in React."}


def test_chat_daily_quota_returns_429(gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    gemini.queue((429, DAILY_QUOTA))
    r = client.post("/chat", json=CHAT)
    assert r.status_code == 429
    r = client.post("/chat", json=CHAT)  # breaker: no new API call
    assert r.status_code == 429 and "daily quota" in r.json()["detail"]
    assert len(gemini.requests) == 1


def test_chat_minute_quota_retries_then_answers(gemini):
    gemini.queue((429, MINUTE_QUOTA), (200, ok_body("ok")))
    assert client.post("/chat", json=CHAT).json() == {"reply": "ok"}


def test_chat_timeout_returns_504(gemini, monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "0.5")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    gemini.queue((200, ok_body("late"), 3))
    r = client.post("/chat", json=CHAT)
    assert r.status_code == 504, r.json()


@pytest.mark.parametrize("payload", [
    {},
    {"project_path": EXAMPLE, "github_url": "https://github.com/a/b"},
    {"project_path": "C:/definitely/not/here"},
    {"github_url": "not-a-github-url"},
])
def test_analyse_rejects_bad_input(payload):
    r = client.post("/analyse", json=payload)
    assert r.status_code == 400, r.json()


def test_analyse_runs_pipeline(gemini, monkeypatch):
    import importlib
    monkeypatch.setattr(importlib.import_module("agent.nodes.generic_node.generic_node"), "_analyzer", None)
    gemini.queue((200, ok_body("- does something")))
    r = client.post("/analyse", json={"project_path": EXAMPLE})
    assert r.status_code == 200
    assert {a["filename"] for a in r.json()["functionality_analyses"]} == {"OrderForm.frm", "payroll.f90", "inventory.py"}
