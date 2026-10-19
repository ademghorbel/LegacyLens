"""LangGraph multi-node system for analyzing software projects.

This system detects programming languages and routes files to specialized processing nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, TypedDict, Annotated
import operator

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph


class FunctionalityAnalysis(TypedDict):
    """Structure for storing functionality analysis results."""
    file_path: str
    filename: str
    language: str
    functionalities: List[str]
    processing_status: str
    node_type: str


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries for LangGraph state updates."""
    return {**left, **right}


class Configuration(TypedDict):
    """Configurable parameters for the agent.

    Set these when creating assistants OR when invoking the graph.
    """

    project_path: str


@dataclass
class State:
    """State for the multi-node analysis pipeline.

    Manages project analysis and file routing between specialized nodes.
    """

    project_path: str = ""
    detected_languages: List[str] = field(default_factory=list)
    detected_frameworks: List[str] = field(default_factory=list)
    files_to_process_with_cobol: List[Dict[str, Any]] = field(default_factory=list)
    files_to_process_with_vb6: List[Dict[str, Any]] = field(default_factory=list)
    files_to_process_with_fortran: List[Dict[str, Any]] = field(default_factory=list)
    files_to_process_with_generic: List[Dict[str, Any]] = field(default_factory=list)
    processed_files: Annotated[List[Dict[str, Any]], operator.add] = field(default_factory=list)
    
    # Results from processing nodes
    cobol_results: List[Dict[str, Any]] = field(default_factory=list)
    vb6_results: List[Dict[str, Any]] = field(default_factory=list)
    fortran_results: List[Dict[str, Any]] = field(default_factory=list)
    generic_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Functionality analysis results
    functionality_analyses: Annotated[List[FunctionalityAnalysis], operator.add] = field(default_factory=list)
    
    # Status flags
    analysis_complete: bool = False
    processing_complete: bool = False
    output_vb6_agent: Dict[str, Any] = field(default_factory=dict)

    # Structured per-file analyses from the generic analyser
    structured_analyses: Annotated[List[Dict[str, Any]], operator.add] = field(default_factory=list)

    # Business modules (RFP format) from the aggregation node
    modules: List[Dict[str, Any]] = field(default_factory=list)
    aggregation_status: str = ""

async def call_model(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Legacy function kept for compatibility. Use the orchestrator instead."""
    return {"analysis_complete": False}


def route_to_processors(state: State) -> List[str]:
    """Route processing to appropriate nodes based on detected languages."""
    if not state.analysis_complete:
        return ["__end__"]
    
    # Process nodes sequentially, one at a time
    # Priority order: COBOL → VB6 → Fortran → Generic → Checker
    if state.files_to_process_with_cobol:
        return ["cobol_node"]
    elif state.files_to_process_with_vb6:
        return ["vb6_node"]
    elif state.files_to_process_with_fortran:
        return ["fortran_node"]
    elif state.files_to_process_with_generic:
        return ["generic_node"]
    else:
        # No files to process, go to checker
        return ["checker_node"]


# Import the processing nodes
from .orchestrator.orchestrator import orchestrator_node
from .nodes.cobol_node.cobol_node import cobol_node
from .nodes.vb6_node.vb6_node import vb6_node
from .nodes.fortran_node.fortran_node import fortran_node
from .nodes.generic_node.generic_node import generic_node
from .nodes.module_aggregation_node.aggregation_node import aggregation_node


# Define the graph
def create_graph():
    """Create and return the LangGraph pipeline."""
    # Import checker functions here to avoid circular imports
    from .checker import checker_node, route_from_checker
    
    return (
        StateGraph(State, config_schema=Configuration)
        .add_node("orchestrator", orchestrator_node)
        .add_node("cobol_node", cobol_node)
        .add_node("vb6_node", vb6_node)
        .add_node("fortran_node", fortran_node)
        .add_node("generic_node", generic_node)
        .add_node("checker_node", checker_node)
        .add_node("aggregation_node", aggregation_node)
        .add_edge("__start__", "orchestrator")
        .add_conditional_edges("orchestrator", route_to_processors)
        .add_edge("cobol_node", "checker_node")
        .add_edge("vb6_node", "checker_node")
        .add_edge("fortran_node", "checker_node")
        .add_edge("generic_node", "checker_node")
        .add_conditional_edges("checker_node", route_from_checker)
        .add_edge("aggregation_node", "__end__")
        .compile(name="Multi-Node Analysis Pipeline")
    )


# Create the default graph instance
graph = create_graph()
