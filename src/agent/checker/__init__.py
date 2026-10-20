"""Checker node to verify if all processing is complete."""

from typing import Dict, Any
from langchain_core.runnables import RunnableConfig


async def checker_node(state, config: RunnableConfig) -> Dict[str, Any]:
    """Check if all files have been processed and decide if we need to continue.
    
    Args:
        state: Current pipeline state
        config: Runtime configuration
        
    Returns:
        Updated state with processing completion status
    """
    print("🔍 Hey, my name is CHECKER_NODE!")
    print("🔄 Checking processing status...")
    
    # Check if there are still files to process
    remaining_cobol = len(state.files_to_process_with_cobol)
    remaining_vb6 = len(state.files_to_process_with_vb6)
    remaining_fortran = len(state.files_to_process_with_fortran)
    remaining_generic = len(state.files_to_process_with_generic)
    
    total_remaining = remaining_cobol + remaining_vb6 + remaining_fortran + remaining_generic
    
    print(f"📊 Remaining files to process:")
    print(f"  COBOL: {remaining_cobol}")
    print(f"  VB6: {remaining_vb6}")
    print(f"  Fortran: {remaining_fortran}")
    print(f"  Generic: {remaining_generic}")
    print(f"  Total: {total_remaining}")
    
    if total_remaining == 0:
        print("✅ All files have been processed!")
        return {"processing_complete": True}
    else:
        print("🔄 Still have files to process, continuing...")
        return {"processing_complete": False}


def route_from_checker(state) -> str:
    """Route from checker based on processing completion.
    
    Priority order: COBOL → VB6 → Fortran → Generic
    """
    if state.processing_complete:
        return "aggregation_node"
    else:
        # Route to the next processor that has files, in priority order
        if state.files_to_process_with_cobol:
            print("  🔄 Routing to COBOL_NODE for next file...")
            return "cobol_node"
        elif state.files_to_process_with_vb6:
            print("  🔄 Routing to VB6_NODE for next file...")
            return "vb6_node"
        elif state.files_to_process_with_fortran:
            print("  🔄 Routing to FORTRAN_NODE for next file...")
            return "fortran_node"
        elif state.files_to_process_with_generic:
            print("  🔄 Routing to GENERIC_NODE for next file...")
            return "generic_node"
        else:
            # No files to process, end the pipeline
            print("  ✅ No more files to process, aggregating modules...")
            return "aggregation_node"
