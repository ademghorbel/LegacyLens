"""Aggregation node: LangGraph wrapper around ModuleAggregationNode.

Runs once after every file is processed. Takes the analyses from state (no
folder scanning) and groups them into business modules in RFP format.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from .module_aggregation_node import create_module_aggregation_node

OUTPUT_DIR = Path(__file__).resolve().parents[4] / "outputs" / "analysis"


def build_aggregation_inputs(state) -> List[Dict[str, Any]]:
    """Shape every analysis the way the aggregation prompt expects."""
    inputs = []
    structured_paths = set()

    for item in state.structured_analyses:
        structured_paths.add(item["file_path"])
        summary = {**item.get("file_summary", {}), "file_name": item["filename"]}  # trust our name, not the LLM's
        inputs.append({"file_name": item["filename"],
                       "data": {"status": "analyzed", "analysis": {**item, "file_summary": summary}}})

    # Language nodes (COBOL, VB6, Fortran) only give a functionality list.
    for fa in state.functionality_analyses:
        if fa["file_path"] in structured_paths or fa.get("processing_status") != "completed":
            continue
        if not fa.get("functionalities"):
            continue
        inputs.append({
            "file_name": fa["filename"],
            "data": {"status": "analyzed", "analysis": {
                "file_summary": {
                    "file_name": fa["filename"],
                    "role": f"{fa['language']} program",
                    "language": fa["language"],
                    "purpose": "; ".join(str(f) for f in fa["functionalities"]),
                },
                "structure": {},
            }},
        })
    return inputs


def _aggregate(inputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    node = create_module_aggregation_node(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    result = node._perform_aggregation(inputs)
    result = node._add_aggregation_metadata(result, str(OUTPUT_DIR), len(inputs))
    if result.get("status") == "aggregated":
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        result["rfp_output_file"] = node._export_rfp_format(result, str(OUTPUT_DIR))
    return result


async def aggregation_node(state, config: RunnableConfig) -> Dict[str, Any]:
    """Group all file analyses into modules (RFP format)."""
    print("AGGREGATION_NODE: grouping analyses into modules")
    inputs = build_aggregation_inputs(state)
    if not inputs:
        return {"modules": [], "aggregation_status": "skipped: no successful analyses"}

    try:
        result = await asyncio.to_thread(_aggregate, inputs)
    except Exception as e:
        print(f"  Aggregation failed: {e}")
        return {"modules": [], "aggregation_status": f"error: {e}"}

    # Keep only file names we actually analysed (the model may invent some).
    known = {i["file_name"] for i in inputs}
    for m in result.get("modules", []):
        if isinstance(m, dict) and "source_files" in m:
            m["source_files"] = [f for f in m.get("source_files") or [] if f in known]

    return {
        "modules": result.get("modules", []),
        "aggregation_status": result.get("status") if result.get("status") == "aggregated"
        else f"error: {result.get('message', 'unknown')}",
    }
