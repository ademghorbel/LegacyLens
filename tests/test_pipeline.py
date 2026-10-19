"""End-to-end pipeline runs against the local fake Gemini (real SDK, no quota used)."""

import importlib
import json
import shutil
import time
from pathlib import Path

import pytest

from agent.graph import State, create_graph
from fake_gemini import DAILY_QUOTA, ok_body

# Package __init__ files re-export functions under the module names, so load the modules directly.
generic_mod = importlib.import_module("agent.nodes.generic_node.generic_node")
agg_mod = importlib.import_module("agent.nodes.module_aggregation_node.aggregation_node")
from agent.nodes.generic_node_with_api.generic_node import GenericCodeAnalysisNodeLangChain  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

FAKE_ANALYSIS = {
    "file_summary": {"file_name": "x", "role": "Service", "language": "python", "purpose": "Handles stock"},
    "structure": {
        "classes": [{"name": "Inventory", "functionality": "Tracks stock levels"}],
        "functions": [{"name": "restock", "functionality": "Adds items to stock"}],
        "dependencies": [{"name": "sqlite3", "type": "library", "usage": "storage"}],
        "design_patterns": ["Repository"],
    },
    "architecture": {"layer": "business", "responsibilities": ["stock"]},
    "functional_description": "Inventory service",
}
FAKE_MODULES = {"modules": [{"module_name": "inventory-management", "module_description": "Stock",
                             "tech_stack": ["Python"], "expected_output": "API",
                             "endpoints": [{"path": "/stock", "method": "GET"}],
                             "entities": {"Item": {"id": "int"}}}]}


def reply(prompt: str):
    """Answer like Gemini would, based on which node is asking."""
    if "frameworks and major libraries" in prompt:
        return 200, ok_body(json.dumps({"frameworks": ["FastAPI"]}))
    if "comprehensive structured analysis" in prompt:
        return 200, ok_body("```json\n" + json.dumps(FAKE_ANALYSIS) + "\n```")
    if "aggregating multiple code analysis" in prompt:
        return 200, ok_body(json.dumps(FAKE_MODULES))
    if "VB6 code analysis expert" in prompt:
        return 200, ok_body("- Validates order form input\n- Saves the order")
    return 200, ok_body("Computes payroll totals.")  # Fortran summaries


@pytest.fixture
def run(gemini, monkeypatch, tmp_path):
    """Run the whole graph on a copy of an example project."""
    monkeypatch.setattr(generic_mod, "_analyzer", None)  # rebuild with the fake URL
    monkeypatch.setattr(agg_mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(GenericCodeAnalysisNodeLangChain, "_export_to_json",
                        lambda self, r, f: str(tmp_path / "a.json"))

    async def _run(example="demo_project"):
        project = tmp_path / example
        shutil.copytree(EXAMPLES / example, project)
        start = time.monotonic()
        result = await create_graph().ainvoke(State(project_path=str(project)), {"recursion_limit": 200})
        result["_elapsed"] = time.monotonic() - start
        return result
    return _run


def by_name(result):
    return {a["filename"]: a for a in result["functionality_analyses"]}


async def test_full_run_on_demo_project(run, gemini):
    gemini.respond_with(lambda p, n: reply(p))
    result = await run()

    files = by_name(result)
    assert set(files) == {"OrderForm.frm", "payroll.f90", "inventory.py"}
    assert all(a["processing_status"] == "completed" for a in files.values()), files
    assert files["OrderForm.frm"]["functionalities"] == ["Validates order form input", "Saves the order"]
    assert all(isinstance(f, str) for f in files["payroll.f90"]["functionalities"])
    assert "Inventory: Tracks stock levels" in files["inventory.py"]["functionalities"]
    assert files["payroll.f90"]["functionalities"], "program-only Fortran falls back to its summary"

    assert result["detected_frameworks"] == ["FastAPI"]
    assert len(result["structured_analyses"]) == 1
    assert result["aggregation_status"] == "aggregated"
    assert result["modules"] == FAKE_MODULES["modules"]

    agg_prompt = next(p for p in gemini.prompts if "aggregating multiple code analysis" in p)
    assert "payroll.f90" in agg_prompt and "OrderForm.frm" in agg_prompt, "legacy files must reach aggregation"
    assert sum("frameworks and major libraries" in p for p in gemini.prompts) == 1, "one routing call per project"


async def test_ecommerce_project_all_files_analysed(run, gemini):
    gemini.respond_with(lambda p, n: reply(p))
    result = await run("ecommerce_project")

    py_js = [p for p in (EXAMPLES / "ecommerce_project").iterdir() if p.suffix in {".py", ".js", ".ts", ".tsx", ".jsx"}]
    assert len(result["structured_analyses"]) == len(py_js)
    assert result["aggregation_status"] == "aggregated"


async def test_one_slow_file_times_out_without_breaking_the_run(run, gemini, monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "0.5")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "2")

    def slow_inventory(prompt, n):
        if "comprehensive structured analysis" in prompt and "inventory.py" in prompt:
            return (*reply(prompt), 3)  # longer than the timeout
        return reply(prompt)
    gemini.respond_with(slow_inventory)
    result = await run()

    files = by_name(result)
    assert files["inventory.py"]["processing_status"] == "error"
    assert files["OrderForm.frm"]["processing_status"] == "completed"
    assert files["payroll.f90"]["processing_status"] == "completed"
    assert result["aggregation_status"] == "aggregated"  # still built from the files that worked
    assert result["_elapsed"] < 15


async def test_daily_quota_at_start_stops_llm_calls_fast(run, gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "2")
    gemini.respond_with(lambda p, n: (429, DAILY_QUOTA))
    result = await run()

    assert len(gemini.requests) == 2, "only the first call's attempts reach the API"
    assert all(a["processing_status"] == "error" for a in result["functionality_analyses"])
    assert set(by_name(result)) == {"OrderForm.frm", "payroll.f90", "inventory.py"}, "files still routed"
    assert result["aggregation_status"].startswith("skipped")
    assert result["_elapsed"] < 5


async def test_quota_runs_out_mid_run(run, gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "2")
    # Calls 1-2 work (frameworks, VB6 file), then the daily quota is gone.
    gemini.respond_with(lambda p, n: reply(p) if n <= 2 else (429, DAILY_QUOTA))
    result = await run()

    files = by_name(result)
    assert files["OrderForm.frm"]["processing_status"] == "completed"
    assert files["payroll.f90"]["processing_status"] == "error"
    assert files["inventory.py"]["processing_status"] == "error"
    assert len(gemini.requests) == 4, "2 good calls + 2 attempts, then the breaker holds"
    assert "quota" in result["aggregation_status"].lower()


async def test_missing_api_key_fails_cleanly(run, gemini, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini.respond_with(lambda p, n: reply(p))
    result = await run()

    assert len(gemini.requests) == 0
    assert all(a["processing_status"] == "error" for a in result["functionality_analyses"])
    assert result["aggregation_status"].startswith("skipped")


async def test_daily_quota_mid_run_falls_back_and_finishes(run, gemini, monkeypatch):
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-lite")

    def respond(prompt, n):
        on_primary = "gemini-3.5-flash:" in gemini.last_path
        return (429, DAILY_QUOTA) if on_primary and n > 2 else reply(prompt)
    gemini.respond_with(respond)
    result = await run()

    assert all(a["processing_status"] == "completed" for a in result["functionality_analyses"])
    assert result["aggregation_status"] == "aggregated"
    assert any("gemini-lite" in p for _, p in gemini.requests)
