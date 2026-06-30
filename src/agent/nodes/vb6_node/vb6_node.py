from typing import Dict, Any, List
from pathlib import Path
import os

from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from ...graph import State, FunctionalityAnalysis

def setup_llm():
    """Setup the LLM for VB6 functionality analysis."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.1
    )

def create_vb6_analysis_prompt():
    """Create the prompt template for VB6 functionality analysis."""
    prompt_template = """
You are a VB6 code analysis expert. Analyze the following VB6 file and extract its main functionalities, focusing on:
1. Forms and their controls (e.g., buttons, textboxes, labels)
2. Procedures and functions defined (e.g., Sub, Function)
3. Event handlers (e.g., Button_Click, Form_Load)
4. Main business logic or calculations
5. External dependencies or API calls

File Path: {file_path}
File Name: {filename}
Programming Language: VB6
File Content:
{file_content}

Return a concise list of functionalities, each on a new line, starting with a dash (-).
If no specific functionalities are found, return '- No specific functionalities detected'.
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
            functionality = line[1:].strip()
            if functionality:
                functionalities.append(functionality)
    if not functionalities and 'No specific functionalities detected' in llm_response:
        functionalities.append('No specific functionalities detected')
    return functionalities[:10]  # Limit to 10 functionalities max

async def vb6_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """VB6 node that analyzes file functionalities using LLM.
    
    Args:
        state: Current pipeline state
        config: Runtime configuration
        
    Returns:
        Updated state with functionality analysis results
    """
    print("🟡 Hey, my name is VB6_NODE! Analyzing functionalities with LLM...")
    
    # Get VB6 files queue
    vb6_files = state.files_to_process_with_vb6.copy()
    
    if not vb6_files:
        print("  ℹ️  No VB6 files to process")
        return {
            "processed_files": [],
            "files_to_process_with_vb6": [],
            "functionality_analyses": []
        }
    
    # Process only the first file (index 0)
    file_info = vb6_files[0]
    file_path = file_info["file_path"]
    filename = file_info["filename"]
    language = file_info.get("language", "unknown")
    
    print(f"  📄 Analyzing {language} file: {filename}")
    
    try:
        # Setup LLM and prompt
        llm = setup_llm()
        prompt = create_vb6_analysis_prompt()
        
        # Read file content
        file_content = read_file_content(file_path)
        print(f"  📖 Read {len(file_content)} characters from file")
        
        # Create the analysis chain
        chain = prompt | llm
        
        # Analyze functionalities
        print("  🤖 Running LLM analysis...")
        response = await chain.ainvoke({
            "file_path": file_path,
            "filename": filename,
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
            "node_type": "vb6_node"
        }
        
        # Create processed file info for backward compatibility
        processed_file_info = {
            "file_path": file_path,
            "node_type": "vb6_node",
            "language": language,
            "processing_status": "completed",
            "message": f"VB6 file {filename} analyzed successfully! Found {len(functionalities)} functionalities.",
            "functionalities": functionalities,
            "original_info": file_info
        }
        
        print(f"  ✅ VB6_NODE analyzed 1 file: {filename}")
        
    except Exception as e:
        print(f"  ❌ Error analyzing file {filename}: {str(e)}")
        
        # Create error result
        functionality_analysis: FunctionalityAnalysis = {
            "file_path": file_path,
            "filename": filename,
            "language": language,
            "functionalities": [],
            "processing_status": "error",
            "node_type": "vb6_node"
        }
        
        processed_file_info = {
            "file_path": file_path,
            "node_type": "vb6_node",
            "language": language,
            "processing_status": "error",
            "message": f"Error analyzing {filename}: {str(e)}",
            "functionalities": [],
            "original_info": file_info
        }
    
    # Remove the processed file from queue (remove index 0)
    remaining_vb6_files = vb6_files[1:]
    
    print(f"  📊 Remaining VB6 files in queue: {len(remaining_vb6_files)}")
    
    return {
        "processed_files": [processed_file_info],
        "files_to_process_with_vb6": remaining_vb6_files,
        "functionality_analyses": [functionality_analysis]
    }