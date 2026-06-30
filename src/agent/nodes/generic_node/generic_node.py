"""Generic processing node - LLM-powered functionality analysis."""

from typing import Dict, Any, List
from pathlib import Path
import os

from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from ...graph import State, FunctionalityAnalysis


def setup_llm():
    """Setup the LLM for functionality analysis."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.1
    )


def create_analysis_prompt():
    """Create the prompt template for functionality analysis."""
    prompt_template = """
You are a code analysis expert. Analyze the following file and extract its main functionalities.

File Path: {file_path}
Programming Language: {language}
File Content:
{file_content}

Please analyze this code and extract the main functionalities. Focus on:
1. Functions and methods defined
2. Classes and their purposes
3. Main algorithms or business logic
4. Database operations or data processing
5. API endpoints or interfaces
6. Configuration or setup code

Return a concise list of functionalities, each on a new line, starting with a dash (-).
Be specific but concise. Limit to the most important functionalities.

Functionalities:
"""
    
    return ChatPromptTemplate.from_template(prompt_template)


def read_file_content(file_path: str, max_chars: int = 10000) -> str:
    """Read file content with size limit."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(max_chars)
            if len(content) == max_chars:
                content += "\n... (file truncated due to size limit)"
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


def parse_functionalities(llm_response: str) -> List[str]:
    """Parse the LLM response to extract functionalities list."""
    lines = llm_response.strip().split('\n')
    functionalities = []
    
    for line in lines:
        line = line.strip()
        if line.startswith('-') or line.startswith('•'):
            # Remove the dash/bullet and clean up
            functionality = line[1:].strip()
            if functionality:
                functionalities.append(functionality)
        elif line and not line.lower().startswith('functionalities'):
            # Also include lines that don't start with dash but aren't the header
            functionalities.append(line)
    
    return functionalities[:10]  # Limit to 10 functionalities max


async def generic_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Generic node that analyzes file functionalities using LLM.
    
    Args:
        state: Current pipeline state
        config: Runtime configuration
        
    Returns:
        Updated state with functionality analysis results
    """
    print("🔍 Hey, my name is GENERIC_NODE! Analyzing functionalities with LLM...")
    
    # Get generic files queue
    generic_files = state.files_to_process_with_generic.copy()
    
    if not generic_files:
        print("  ℹ️  No Generic files to process")
        return {
            "processed_files": [],
            "files_to_process_with_generic": [],
            "functionality_analyses": []
        }
    
    # Process only the first file (index 0)
    file_info = generic_files[0]
    file_path = file_info["file_path"]
    filename = file_info["filename"]
    language = file_info.get("language", "unknown")
    
    print(f"  📄 Analyzing {language} file: {filename}")
    
    try:
        # Setup LLM and prompt
        llm = setup_llm()
        prompt = create_analysis_prompt()
        
        # Read file content
        file_content = read_file_content(file_path)
        print(f"  📖 Read {len(file_content)} characters from file")
        
        # Create the analysis chain
        chain = prompt | llm
        
        # Analyze functionalities
        print("  🤖 Running LLM analysis...")
        response = await chain.ainvoke({
            "file_path": file_path,
            "language": language,
            "file_content": file_content
        })
        
        # Parse functionalities from response
        functionalities = parse_functionalities(response.content)
        print(f"  ✨ Extracted {len(functionalities)} functionalities")
        
        # Create functionality analysis result
        functionality_analysis: FunctionalityAnalysis = {
            "file_path": file_path,
            "filename": filename,
            "language": language,
            "functionalities": functionalities,
            "processing_status": "completed",
            "node_type": "generic_node"
        }
        
        # Create processed file info for backward compatibility
        processed_file_info = {
            "file_path": file_path,
            "node_type": "generic_node",
            "language": language,
            "processing_status": "completed",
            "message": f"Generic file {filename} analyzed successfully! Found {len(functionalities)} functionalities.",
            "functionalities": functionalities,
            "original_info": file_info
        }
        
        print(f"  ✅ GENERIC_NODE analyzed 1 file: {filename}")
        
    except Exception as e:
        print(f"  ❌ Error analyzing file {filename}: {str(e)}")
        
        # Create error result
        functionality_analysis: FunctionalityAnalysis = {
            "file_path": file_path,
            "filename": filename,
            "language": language,
            "functionalities": [],
            "processing_status": "error",
            "node_type": "generic_node"
        }
        
        processed_file_info = {
            "file_path": file_path,
            "node_type": "generic_node",
            "language": language,
            "processing_status": "error",
            "message": f"Error analyzing {filename}: {str(e)}",
            "functionalities": [],
            "original_info": file_info
        }
    
    # Remove the processed file from queue (remove index 0)
    remaining_generic_files = generic_files[1:]
    
    print(f"  📊 Remaining generic files in queue: {len(remaining_generic_files)}")
    
    return {
        "processed_files": [processed_file_info],
        "files_to_process_with_generic": remaining_generic_files,
        "functionality_analyses": [functionality_analysis]
    }
