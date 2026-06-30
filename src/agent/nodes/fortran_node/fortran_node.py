from typing import Dict, Any
from pathlib import Path
from langchain_core.runnables import RunnableConfig

from ...graph import State, FunctionalityAnalysis
from .parsers.fortran_parser import parse_fortran_file
from .extractor.functionality_extractor import extract_functionalities
from .summarizers.human_summarizer import generate_human_summary
from .summarizers.tech_summarizer import generate_technical_summary
from .writers.summary_writer import save_summaries
from .utils import extract_file_info, print_log, clean_llm_output

async def fortran_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Full Fortran Node Processing: parsing → extracting → summarizing → saving."""
    print("🟢 Hey, my name is FORTRAN_NODE!")

    fortran_files = state.files_to_process_with_fortran.copy()
    if not fortran_files:
        print("  ℹ️  No Fortran files to process")
        return {
            "processed_files": [],
            "files_to_process_with_fortran": [],
            "functionality_analyses": []
        }

    file_info = fortran_files[0]
    file_data = extract_file_info(file_info)
    file_path = file_data["file_path"]
    filename = file_data["filename"]
    language = file_data["language"]

    print_log("Processing Fortran file: " + filename, "📄")

    try:
        # Read file
        code = Path(file_path).read_text(encoding="utf-8")

        # Parse metadata
        metadata = parse_fortran_file(file_path)
        print(f"  🧩 Parsed metadata: {metadata.get('version')}")

        # Extract functionalities
        functionalities = extract_functionalities(metadata)
        print(f"  🔍 Extracted {len(functionalities['functionalities'])} functionalities")

        # Generate summaries
        human_summary = generate_human_summary(code)
        tech_summary = generate_technical_summary(code)

        # Clean the LLM output
        human_summary = clean_llm_output(human_summary)
        tech_summary = clean_llm_output(tech_summary)
        
        # Save summaries
        saved_paths = save_summaries(
            base_path=file_path,
            tech_summary=tech_summary,
            human_summary=human_summary,
            functionality_summary=functionalities
        )
        print(f"  💾 Summaries saved at: {saved_paths}")

        # Create FunctionalityAnalysis entry
        functionality_analysis: FunctionalityAnalysis = {
            "file_path": file_path,
            "filename": filename,
            "language": language,
            "functionalities": functionalities.get("functionalities", []),
            "processing_status": "completed",
            "node_type": "fortran_node"
        }

        # Create processed file info
        processed_file_info = {
            "file_path": file_path,
            "node_type": "fortran_node",
            "language": language,
            "processing_status": "completed",
            "message": f"Processed successfully!",
            "original_info": file_info,
            "summaries": saved_paths,
            "functionalities": functionalities,
            "metadata": metadata
        }

    except Exception as e:
        print(f"  ❌ Error processing {filename}: {str(e)}")
        functionality_analysis: FunctionalityAnalysis = {
            "file_path": file_path,
            "filename": filename,
            "language": language,
            "functionalities": [],
            "processing_status": "error",
            "node_type": "fortran_node"
        }
        processed_file_info = {
            "file_path": file_path,
            "node_type": "fortran_node",
            "language": language,
            "processing_status": "error",
            "message": f"Error processing {filename}: {str(e)}",
            "original_info": file_info,
            "summaries": [],
            "functionalities": [],
            "metadata": {}
        }

    remaining_fortran_files = fortran_files[1:]

    return {
        "processed_files": [processed_file_info],
        "files_to_process_with_fortran": remaining_fortran_files,
        "functionality_analyses": [functionality_analysis]
    }