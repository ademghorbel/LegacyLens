"""Orchestrator node: routes files by extension, detects frameworks with one LLM call."""

import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from ..graph import State

# Load environment variables
load_dotenv()


@tool
def scan_project_files(project_path: str) -> List[str]:
    """Scan project directory and return list of all source files.
    
    Args:
        project_path: Path to the project directory to scan
        
    Returns:
        List of file paths found in the project
    """
    if not os.path.exists(project_path):
        return []
    
    source_files = []
    
    # Common source file extensions
    source_extensions = {
        '.py', '.java', '.cpp', '.c', '.cs', '.js', '.ts', '.jsx', '.tsx', '.php', '.rb', '.go', '.rs',
        '.cob', '.cbl', '.cpy',  # COBOL
        '.vb', '.bas', '.frm', '.cls',  # VB6
        '.f', '.for', '.f90', '.f95'  # Fortran
    }
    
    try:
        for root, dirs, files in os.walk(project_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.vscode', 'target', 'build', 'dist',
                                                    '.venv', 'venv', '.idea', '.pytest_cache', '.mypy_cache'}]
            
            for file in files:
                file_ext = Path(file).suffix.lower()
                if file_ext in source_extensions:
                    file_path = os.path.join(root, file)
                    source_files.append(file_path)
                    
        return source_files
    except Exception as e:
        print(f"Error scanning directory: {e}")
        return []


LEGACY_EXTENSIONS = {'.cob', '.cbl', '.cpy', '.vb', '.bas', '.frm', '.cls', '.f', '.for', '.f90', '.f95'}


def is_test_file(file_path: str) -> bool:
    p = Path(file_path)
    name = p.name.lower()
    parts = {part.lower() for part in p.parts[:-1]}
    return (bool(parts & {'test', 'tests', '__tests__', 'spec', 'specs'})
            or name.startswith('test_') or p.stem.lower().endswith(('_test', '.test', '.spec'))
            or name == 'conftest.py')


def select_files(files: List[str], max_files: int | None = None, include_tests: bool = False) -> List[str]:
    """Drop test files (unless asked) and cap the count, keeping legacy files first.

    Every selected file costs at least one LLM call, so the cap is what keeps a big
    repo inside the free-tier quota.
    """
    chosen = [f for f in files if include_tests or not is_test_file(f)]
    chosen.sort(key=lambda f: (Path(f).suffix.lower() not in LEGACY_EXTENSIONS, f.lower()))
    if max_files and max_files > 0:
        chosen = chosen[:max_files]
    return chosen


@tool
def read_file_content(file_path: str, max_chars: int = 2000) -> str:
    """Read file content with a character limit.
    
    Args:
        file_path: Path to the file to read
        max_chars: Maximum number of characters to read
        
    Returns:
        File content (truncated if necessary)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(max_chars)
        return content
    except Exception as e:
        return f"Error reading file: {e}"


async def orchestrator_node(state: State, config: RunnableConfig) -> Dict[str, Any]:
    """Orchestrateur principal qui analyse les fichiers avec Gemini 2.5 Flash.
    
    Args:
        state: État actuel du pipeline
        config: Configuration d'exécution
        
    Returns:
        État mis à jour avec l'analyse et le routage des fichiers
    """
    print("🔴 Hey, my name is ORCHESTRATOR_NODE!")
    print("🚀 Starting project analysis...")
    
    project_path = state.project_path or config.get("configurable", {}).get("project_path", "")
    
    if not project_path:
        print("❌ No project path provided!")
        return {
            "analysis_complete": False,
            "files_to_process_with_cobol": [],
            "files_to_process_with_vb6": [],
            "files_to_process_with_fortran": [],
            "files_to_process_with_generic": [],
        }
    
    print(f"📁 Analyzing project at: {project_path}")
    
    from ..llm import ainvoke as llm_ainvoke, get_llm, reset_quota
    import json
    import re

    reset_quota()  # quotas reset daily; give each run a fresh chance

    # Scan project files
    source_files = scan_project_files.invoke({"project_path": project_path})
    opts = config.get("configurable", {}) if config else {}
    found = len(source_files)
    source_files = select_files(source_files, opts.get("max_files"), bool(opts.get("include_tests", False)))
    if len(source_files) < found:
        print(f"✂️ Kept {len(source_files)} of {found} files (max_files / test filter)")

    if not source_files:
        print("📭 No source files found in the project")
        return {
            "analysis_complete": True,
            "files_to_process_with_cobol": [],
            "files_to_process_with_vb6": [],
            "files_to_process_with_fortran": [],
            "files_to_process_with_generic": [],
        }

    print(f"📄 Found {len(source_files)} source files to analyze")

    # Route by extension. The scanner only returns known extensions, so this is
    # exact and free; the LLM is kept for what extensions can't tell (frameworks).
    files_cobol, files_vb6, files_fortran, files_generic = [], [], [], []
    queues = {"cobol_node": files_cobol, "vb6_node": files_vb6, "fortran_node": files_fortran}
    detected_languages = set()
    snippets = []

    for file_path in source_files:
        filename = Path(file_path).name
        file_ext = Path(file_path).suffix.lower()
        fb = fallback_analysis(file_path, file_ext)
        detected_languages.add(fb["language"])
        file_info = {
            "file_path": file_path,
            "filename": filename,
            "language": fb["language"],
            "framework": None,
            "target_node": fb["target_node"],
        }
        queues.get(fb["target_node"], files_generic).append(file_info)
        print(f"  📄 {filename} → {fb['target_node'].upper()} ({fb['language']})")
        if len(snippets) < 25:
            head = read_file_content.invoke({"file_path": file_path, "max_chars": 400})
            snippets.append(f"### {filename}\n{head}")

    # One LLM call for the whole project: which frameworks are in use?
    detected_frameworks = set()
    try:
        llm = get_llm(temperature=0.1, timeout=90)
        prompt = (
            "These are the first lines of each source file in a project.\n"
            "List the frameworks and major libraries in use (e.g. Django, Spring, React, "
            "CICS, MFC). Reply with JSON only: {\"frameworks\": [\"...\"]}\n\n"
            + "\n\n".join(snippets)
        )
        reply = await llm_ainvoke(llm, [HumanMessage(content=prompt)])
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        if match:
            detected_frameworks.update(json.loads(match.group()).get("frameworks", []))
    except Exception as e:
        print(f"  [warn] framework detection skipped: {type(e).__name__}: {str(e)[:150]}")

    # Summary
    print(f"\n📊 Analysis Summary:")
    print(f"  🌐 Detected languages: {list(detected_languages)}")
    print(f"  🏗️ Detected frameworks: {list(detected_frameworks)}")
    print(f"  📂 File distribution:")
    print(f"    COBOL: {len(files_cobol)} files")
    print(f"    VB6: {len(files_vb6)} files")
    print(f"    Fortran: {len(files_fortran)} files")
    print(f"    Generic: {len(files_generic)} files")
    
    return {
        "project_path": project_path,
        "detected_languages": list(detected_languages),
        "detected_frameworks": list(detected_frameworks),
        "files_to_process_with_cobol": files_cobol,
        "files_to_process_with_vb6": files_vb6,
        "files_to_process_with_fortran": files_fortran,
        "files_to_process_with_generic": files_generic,
        "analysis_complete": True,
    }


def fallback_analysis(file_path: str, file_ext: str) -> Dict[str, Any]:
    """Fallback analysis based on file extension."""
    ext_mapping = {
        '.cob': ('cobol', 'cobol_node'),
        '.cbl': ('cobol', 'cobol_node'),
        '.cpy': ('cobol', 'cobol_node'),
        '.vb': ('vb6', 'vb6_node'),
        '.bas': ('vb6', 'vb6_node'),
        '.frm': ('vb6', 'vb6_node'),
        '.cls': ('vb6', 'vb6_node'),
        '.f': ('fortran', 'fortran_node'),
        '.for': ('fortran', 'fortran_node'),
        '.f90': ('fortran', 'fortran_node'),
        '.f95': ('fortran', 'fortran_node'),
        '.py': ('python', 'generic_node'),
        '.java': ('java', 'generic_node'),
        '.cpp': ('cpp', 'generic_node'),
        '.c': ('c', 'generic_node'),
        '.cs': ('csharp', 'generic_node'),
        '.js': ('javascript', 'generic_node'),
        '.ts': ('typescript', 'generic_node'),
        '.jsx': ('javascript', 'generic_node'),
        '.tsx': ('typescript', 'generic_node'),
    }
    
    language, target_node = ext_mapping.get(file_ext, ('unknown', 'generic_node'))
    
    return {
        "language": language,
        "framework": None,
        "target_node": target_node,
        "confidence": "medium"
    }
