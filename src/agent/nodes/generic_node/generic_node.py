"""Generic node: LangGraph wrapper around the structured code analyser.

The analysis itself lives in `generic_node_with_api` (structured JSON with
role, layer, classes, functions, dependencies and design patterns). This node
feeds it one file per step and stores both the full structured analysis and a
flat functionality list for the UI and the chat.
"""

import asyncio
import os
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from ...graph import FunctionalityAnalysis, State
from ..generic_node_with_api.generic_node import create_generic_node_langchain

_analyzer = None


def _get_analyzer():
    """Create the analyser once and reuse it across files."""
    global _analyzer
    if _analyzer is None:
        _analyzer = create_generic_node_langchain(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    return _analyzer


def functionalities_from_structure(analysis: Dict[str, Any]) -> List[str]:
    """Flatten the structured analysis into short 'name: what it does' lines."""
    structure = analysis.get("structure", {})
    lines = []
    classes = structure.get("classes", [])
    # Real classes before enums/interfaces: they carry the behaviour.
    classes = sorted(classes, key=lambda c: c.get("type") in ("enum", "interface"))
    for cls in classes:
        lines.append(f"{cls.get('name', '?')}: {cls.get('functionality', '')}".strip())
    for fn in structure.get("functions", []):
        lines.append(f"{fn.get('name', '?')}(): {fn.get('functionality', '')}".strip())
    if not lines:
        purpose = analysis.get("file_summary", {}).get("purpose")
        if purpose:
            lines.append(purpose)
    return lines[:15]


async def generic_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Analyse the next file in the generic queue."""
    print("GENERIC_NODE: structured analysis")

    generic_files = state.files_to_process_with_generic.copy()
    if not generic_files:
        return {"processed_files": [], "files_to_process_with_generic": []}

    file_info = generic_files[0]
    file_path = file_info["file_path"]
    filename = file_info["filename"]
    language = file_info.get("language", "unknown")

    structured: Dict[str, Any] = {}
    try:
        # The analyser is synchronous, so run it off the event loop.
        result = await asyncio.to_thread(_get_analyzer().process, file_path, language)
        ok = result.get("status") == "analyzed"
        if ok:
            structured = result["analysis"]
        status = "completed" if ok else "error"
        message = result.get("message", f"{filename} analysed")
    except Exception as e:  # missing key, network, bad JSON...
        status, message = "error", f"Error analysing {filename}: {e}"
        print(f"  {message}")

    functionalities = functionalities_from_structure(structured) if structured else []

    analysis: FunctionalityAnalysis = {
        "file_path": file_path,
        "filename": filename,
        "language": language,
        "functionalities": functionalities,
        "processing_status": status,
        "node_type": "generic_node",
    }
    processed = {
        "file_path": file_path,
        "node_type": "generic_node",
        "language": language,
        "processing_status": status,
        "message": message,
        "functionalities": functionalities,
        "original_info": file_info,
    }

    update: Dict[str, Any] = {
        "processed_files": [processed],
        "files_to_process_with_generic": generic_files[1:],
        "functionality_analyses": [analysis],
    }
    if structured:
        update["structured_analyses"] = [{"file_path": file_path, "filename": filename, **structured}]
    return update
