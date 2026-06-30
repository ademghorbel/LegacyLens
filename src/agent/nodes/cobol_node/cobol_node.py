"""Cobol specialized processing node - Simplified version."""

from typing import Dict, Any
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from ...graph import State


async def cobol_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Simple COBOL node that processes only the first file in queue.
    
    Args:
        state: Current pipeline state
        config: Runtime configuration
        
    Returns:
        Updated state with processed COBOL file information
    """
    print("🔵 Hey, my name is COBOL_NODE!")
    
    # Get COBOL files queue
    cobol_files = state.files_to_process_with_cobol.copy()
    
    if not cobol_files:
        print("  ℹ️  No COBOL files to process")
        return {
            "processed_files": [],  # Return empty list for operator.add
            "files_to_process_with_cobol": []
        }
    
    # Process only the first file (index 0)
    file_info = cobol_files[0]
    file_path = file_info["file_path"]
    filename = file_info["filename"]
    language = file_info["language"]
    
    print(f"  📄 Processing COBOL file: {filename} ({language})")
    
    # Simple processing - just mark as completed
    processed_file_info = {
        "file_path": file_path,
        "node_type": "cobol_node",
        "language": language,
        "processing_status": "completed",
        "message": f"COBOL file {filename} processed successfully!",
        "original_info": file_info
    }
    
    print(f"  ✅ COBOL_NODE processed 1 file: {filename}")
    
    # Remove the processed file from queue (remove index 0)
    remaining_cobol_files = cobol_files[1:]  # Remove first element
    
    print(f"  📊 Remaining COBOL files in queue: {len(remaining_cobol_files)}")
    
    return {
        "processed_files": [processed_file_info],  # Return list with one item for operator.add
        "files_to_process_with_cobol": remaining_cobol_files
    }
