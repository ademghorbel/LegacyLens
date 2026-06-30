"""
Outils pour l'analyse du code VB6
"""
import re
import json
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from pathlib import Path

# --- PATTERNS ---
_VB6_PATTERNS = {
    'form': re.compile(r'VERSION\s+\d+\.\d+', re.IGNORECASE),
    'module': re.compile(r'Attribute\s+VB_Name\s*=\s*"([^"]+)"', re.IGNORECASE),
    'procedure': re.compile(r'(Public|Private|Friend)?\s*(Sub|Function)\s+(\w+)\s*\((.*?)\)', re.IGNORECASE),
    'control': re.compile(r'Begin\s+(\w+\.\w+|\w+)\s+(\w+)', re.IGNORECASE),
    'event': re.compile(r'(Private\s+)?Sub\s+(\w+)_(\w+)\(', re.IGNORECASE),
    'api_declare': re.compile(r'Declare\s+(Function|Sub)', re.IGNORECASE),
    'class': re.compile(r'VERSION\s+1\.0\s+CLASS', re.IGNORECASE),
    'call': re.compile(r'\b(Call\s+)?(\w+)\s*\(', re.IGNORECASE),
}

# --- UTILITY FUNCTIONS ---
def _determine_file_type(code_content: str, file_path: Optional[str] = None) -> str:
    if file_path:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".cls":
            return "Class"
        elif suffix == ".bas":
            return "Module"
        elif suffix == ".frm":
            return "Form"
        elif suffix == ".ctl":
            return "UserControl"

    # fallback sur le contenu
    if _VB6_PATTERNS['form'].search(code_content):
        return "Form"
    elif _VB6_PATTERNS['class'].search(code_content):
        return "Class"
    elif 'Attribute VB_Name' in code_content:
        return "Module"
    else:
        return "Other type"

def _extract_procedures(code_content: str) -> List[Dict[str, str]]:
    procedures = []
    matches = _VB6_PATTERNS['procedure'].finditer(code_content)
    for match in matches:
        visibility = match.group(1) or "Public"
        proc_type = match.group(2)
        name = match.group(3)
        procedures.append({"name": name, "type": proc_type, "visibility": visibility})
    return procedures

def _extract_controls(code_content: str) -> list:
    controls = []
    matches = _VB6_PATTERNS['control'].finditer(code_content)
    for match in matches:
        control_type = match.group(1)
        control_name = match.group(2)
        controls.append({"name": control_name, "type": control_type})
    return controls

def _extract_events(code_content: str) -> list:
    events = []
    matches = _VB6_PATTERNS['event'].finditer(code_content)
    for match in matches:
        control_name = match.group(2)
        event_name = match.group(3)
        events.append({"control": control_name, "event": event_name})
    return events

def _extract_api_declarations(code_content: str) -> list:
    try:
        api_declarations = _VB6_PATTERNS['api_declare'].findall(code_content)
        return [match.strip() for match in api_declarations]
    except Exception as e:
        raise ValueError(f"Erreur lors de l'extraction des déclarations API : {e}")

def _analyze_module_dependencies(code_content: str) -> List[str]:
    """
    Analyze dependencies between modules by identifying calls to external modules or classes.

    Args:
        code_content (str): The content of the VB6 code to analyze.

    Returns:
        List[str]: A list of module or class names that are referenced in the code.
    """
    dependencies = []
    matches = _VB6_PATTERNS['call'].finditer(code_content)
    for match in matches:
        called_function = match.group(2)
        if called_function and called_function not in dependencies:
            dependencies.append(called_function)
    return dependencies

def _extract_comments(code_content: str) -> List[str]:
    """
    Extract comments from the VB6 code.

    Args:
        code_content (str): The content of the VB6 code to analyze.

    Returns:
        List[str]: A list of comments found in the code.
    """
    comments = []
    lines = code_content.split('\n')
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("'"):
            comments.append(stripped_line)
    return comments

def _map_events_to_controls(events: List[Dict[str, str]], controls: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Map events to their corresponding controls.

    Args:
        events (List[Dict[str, str]]): A list of events extracted from the code.
        controls (List[Dict[str, str]]): A list of controls extracted from the code.

    Returns:
        List[Dict[str, str]]: A list of mappings between controls and their events.
    """
    mapping = []
    for event in events:
        for control in controls:
            if event['control'] == control['name']:
                mapping.append({"control": control['name'], "event": event['event']})
    return mapping


# --- OUTILS PRINCIPAUX POUR LANGCHAIN ---
@tool("analyze_vb6_code_structure", return_direct=False)
def analyze_vb6_code_structure(code_content: str) -> dict:
    """
    Analyze the structure of VB6 code and extract key components.

    Args:
        code_content (str): The content of the VB6 code to analyze.

    Returns:
        dict: A dictionary containing the following information:
            - file_type (str): The type of the VB6 file (e.g., Form, Module, Class).
            - total_lines (int): The total number of lines in the code.
            - code_lines (int): The number of lines containing actual code (excluding comments and empty lines).
            - comment_lines (int): The number of lines containing comments.
            - procedures (list): A list of procedures (name, type, visibility).
            - variables (list): A list of variables (name, type).
            - controls (list): A list of controls (name, type).
            - events (list): A list of events (control, event).
            - api_declarations (list): A list of API declarations.
            - dependencies (list): A list of module or class names that are referenced in the code.
            - comments (list): A list of comments found in the code.
            - event_control_mapping (list): A list of mappings between controls and their events.
    Raises:
        ValueError: If the code content is empty or invalid, or if an error occurs during analysis.
    """
    if not code_content.strip():
        raise ValueError("The code content is empty or invalid.")

    try:
        lines = code_content.split('\n')
        total_lines = len(lines)
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith("'")])
        file_type = _determine_file_type(code_content)
        procedures = _extract_procedures(code_content)
        controls = _extract_controls(code_content)
        events = _extract_events(code_content)
        api_declarations = _extract_api_declarations(code_content)
        dependencies = _analyze_module_dependencies(code_content)
        comments = _extract_comments(code_content)
        event_control_mapping = _map_events_to_controls(events, controls)

        return {
            "file_type": file_type,
            "total_lines": total_lines,
            "code_lines": code_lines,
            "comment_lines": total_lines - code_lines,
            "procedures": procedures,
            "controls": controls,
            "events": events,
            "api_declarations": api_declarations,
            "dependencies": dependencies,
            "comments": comments,
            "event_control_mapping": event_control_mapping,
        }
    except Exception as e:
        raise ValueError(f"Error while analyzing the VB6 code structure: {e}")

@tool("is_vb6_binary", return_direct=True)
def is_vb6_binary(file_path: str) -> bool:
    """
    Check if a VB6 file contains binary content.

    Args:
        file_path (str): The path to the VB6 file.

    Returns:
        bool: True if the file contains binary content, False otherwise.
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            # Check for non-text characters in the file
            if b'\x00' in content or any(byte > 127 for byte in content):
                print(f"  ⚠️  File {file_path} contains binary content. Ignoring for LLM processing.")
                return True
            return False
    except Exception as e:
        raise ValueError(f"Error while checking binary content of the file {file_path}: {e}")
