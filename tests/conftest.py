import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fake_gemini import FakeGemini  # noqa: E402

from agent import llm as llm_mod  # noqa: E402


@pytest.fixture(autouse=True)
def clean_llm_state(monkeypatch, tmp_path):
    """Isolate tests from the real .env, the real outputs/ folder and each other."""
    import importlib
    diagram_mod = importlib.import_module("agent.nodes.diagram_node.diagram_node")
    monkeypatch.setattr(diagram_mod, "OUTPUT_DIR", tmp_path / "diagrams")
    for var in ("GEMINI_BASE_URL", "GEMINI_MODEL", "LLM_TIMEOUT", "LLM_MAX_ATTEMPTS",
                "LLM_RETRY_DELAY", "LLM_RPM", "LANGCHAIN_TRACING_V2", "GEMINI_FALLBACK_MODELS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")  # tests opt in to fallbacks
    llm_mod.reset_state()
    yield
    llm_mod.reset_state()


@pytest.fixture
def gemini(monkeypatch):
    """Point every LLM call at a local fake Gemini, with fast retries."""
    fake = FakeGemini()
    monkeypatch.setenv("GEMINI_BASE_URL", fake.url)
    monkeypatch.setenv("LLM_RETRY_DELAY", "0.05")
    monkeypatch.setenv("LLM_RPM", "6000")
    yield fake
    fake.close()
