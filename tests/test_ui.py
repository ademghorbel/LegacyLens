"""File selection (max files / tests filter) and the Streamlit UI, against the fake Gemini."""

import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest

from agent.graph import State, create_graph
from agent.orchestrator.orchestrator import is_test_file, select_files
from test_pipeline import EXAMPLES, agg_mod, generic_mod, reply

APP = str(Path(__file__).resolve().parents[1] / "streamlit" / "app.py")


def test_test_files_are_detected():
    for path in ["tests/test_api.py", "src/__tests__/App.tsx", "app/user_test.go",
                 "web/Button.spec.ts", "conftest.py"]:
        assert is_test_file(path), path
    for path in ["src/service.py", "contest.py", "latest/main.py", "attestation.py"]:
        assert not is_test_file(path), path


def test_select_files_caps_and_keeps_legacy_first():
    files = ["a.py", "b.py", "tests/test_a.py", "PAYROLL.cbl", "calc.f90"]
    assert select_files(files, max_files=3) == ["calc.f90", "PAYROLL.cbl", "a.py"]
    assert "tests/test_a.py" not in select_files(files)
    assert "tests/test_a.py" in select_files(files, include_tests=True)
    assert len(select_files(files, max_files=0)) == 4  # 0 = no cap


async def test_max_files_is_applied_by_the_pipeline(gemini, monkeypatch, tmp_path):
    monkeypatch.setattr(generic_mod, "_analyzer", None)
    monkeypatch.setattr(agg_mod, "OUTPUT_DIR", tmp_path / "out")
    gemini.respond_with(lambda p, n: reply(p))
    project = tmp_path / "ecommerce_project"
    shutil.copytree(EXAMPLES / "ecommerce_project", project)

    result = await create_graph().ainvoke(
        State(project_path=str(project)),
        {"recursion_limit": 200, "configurable": {"max_files": 2}},
    )
    assert len(result["functionality_analyses"]) == 2


def test_ui_streams_a_local_analysis_and_shows_modules(gemini, monkeypatch, tmp_path):
    monkeypatch.setattr(generic_mod, "_analyzer", None)
    monkeypatch.setattr(agg_mod, "OUTPUT_DIR", tmp_path / "out")
    gemini.respond_with(lambda p, n: reply(p))
    project = tmp_path / "demo_project"
    shutil.copytree(EXAMPLES / "demo_project", project)

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.text_input[0].set_value(str(project)).run()
    at.button[0].click().run()

    assert not at.exception, [e.value for e in at.exception]
    shown = " ".join(m.value for m in at.markdown)
    assert "3 files" in shown
    for name in ["OrderForm.frm", "payroll.f90", "inventory.py"]:
        assert name in shown, name
    assert at.session_state["analysis_results"]["modules"]

    # Results tab renders the module from the aggregation node as a card.
    shown = " ".join(m.value for m in at.markdown)
    assert "inventory-management" in shown
    assert "Raw JSON" not in [e.label for e in at.expander]

    # A card's Details button opens the module pop-up without errors.
    at.button(key="mod_details_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
