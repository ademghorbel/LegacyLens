"""Mermaid diagram node: builders and the pipeline wiring."""

import importlib
import json

from test_pipeline import FAKE_ANALYSIS, FAKE_MODULES, reply, run  # noqa: F401  (run is a fixture)
from fake_gemini import ok_body

diag = importlib.import_module("agent.nodes.diagram_node.diagram_node")

ANALYSES = [
    {"filename": "order_service.py", "language": "python", "processing_status": "completed"},
    {"filename": "inventory.py", "language": "python", "processing_status": "completed"},
    {"filename": "OrderForm.frm", "language": "vb6", "processing_status": "completed"},
]
STRUCTURED = [
    {"filename": "order_service.py", "structure": {
        "dependencies": [{"name": "inventory"}, "os"],
        "classes": [{"name": "OrderService", "methods": [{"name": "place"}, {"name": "_check", "visibility": "private"}],
                     "attributes": [{"name": "repo", "type": "Repo"}, {"name": "stock", "type": "Optional[Inventory]"}]}]}},
    {"filename": "inventory.py", "structure": {"classes": [{"name": "Inventory", "type": "class", "methods": ["add"]},
                                                           {"name": "Status", "type": "enum"},
                                                           {"name": "ItemDTO", "attributes": [{"name": "sku"}]}]}},
]
MODULES = [
    {"module_name": "order-processing", "source_files": ["order_service.py", "OrderForm.frm"],
     "entities": {"Order": {"id": "string", "customer_id": "string", "total price": "decimal(10,2)"},
                  "Customer": {"id": "string", "name": "string"}}},
    {"module_name": "inventory", "source_files": ["inventory.py"], "entities": {}},
]


def test_architecture_groups_files_by_module_and_draws_imports():
    code = diag.architecture_diagram(MODULES, ANALYSES, STRUCTURED)
    assert code.startswith("flowchart LR")
    assert 'subgraph m_order_processing["order-processing"]' in code
    assert 'f_inventory_py["inventory.py"]' in code
    assert "f_order_service_py --> f_inventory_py" in code   # import between project files
    assert "m_other" not in code                             # every file is in a module
    assert "class f_OrderForm_frm legacy" in code            # legacy files are highlighted


def test_architecture_without_modules_or_imports_is_skipped():
    assert diag.architecture_diagram([], ANALYSES, []) == ""


def test_architecture_without_modules_keeps_imports():
    code = diag.architecture_diagram([], ANALYSES, STRUCTURED)
    assert 'subgraph m_other["Files"]' in code and "-->" in code


def test_entities_are_sanitised_and_linked():
    code = diag.entity_diagram(MODULES)
    assert code.startswith("erDiagram")
    assert "decimal_10_2 total_price" in code     # no spaces/parentheses in ER attributes
    assert 'Customer ||--o{ Order : "customer_id"' in code


def test_class_diagram():
    code = diag.class_diagram(STRUCTURED)
    assert "class OrderService {" in code and "+place()" in code and "-_check()" in code
    assert "+repo Repo" in code and "OrderService --> Inventory" in code
    assert "Status" not in code and "ItemDTO" not in code  # no behaviour: left to the ER diagram


def test_class_diagram_without_behaviour_keeps_data_classes():
    code = diag.class_diagram([{"structure": {"classes": [{"name": "Status", "type": "enum"}]}}])
    assert "class Status {" in code and "<<enum>>" in code


def test_empty_inputs_build_nothing():
    assert diag.build_diagrams([], [], []) == {}


async def test_pipeline_builds_diagrams(run, gemini, monkeypatch, tmp_path):
    monkeypatch.setattr(diag, "OUTPUT_DIR", tmp_path / "diagrams")
    modules = {"modules": [{**FAKE_MODULES["modules"][0],
                            "source_files": ["inventory.py", "payroll.f90", "made_up.py"]}]}

    def answer(prompt, n):
        if "aggregating multiple code analysis" in prompt:
            return 200, ok_body(json.dumps(modules))
        return reply(prompt)

    gemini.respond_with(answer)
    result = await run()

    assert result["modules"][0]["source_files"] == ["inventory.py", "payroll.f90"]  # invented name dropped
    assert set(result["diagrams"]) == {"architecture", "entities", "classes"}
    assert "f_payroll_f90" in result["diagrams"]["architecture"]
    assert (tmp_path / "diagrams" / "architecture.mmd").read_text(encoding="utf-8") == result["diagrams"]["architecture"]
