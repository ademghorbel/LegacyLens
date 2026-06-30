"""Orchestrator node avec Gemini 2.5 Flash pour l'analyse de projets."""

import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
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
        '.py', '.java', '.cpp', '.c', '.cs', '.js', '.ts', '.php', '.rb', '.go', '.rs',
        '.cob', '.cbl', '.cpy',  # COBOL
        '.vb', '.bas', '.frm', '.cls',  # VB6
        '.f', '.for', '.f90', '.f95'  # Fortran
    }
    
    try:
        for root, dirs, files in os.walk(project_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.vscode', 'target', 'build', 'dist'}]
            
            for file in files:
                file_ext = Path(file).suffix.lower()
                if file_ext in source_extensions:
                    file_path = os.path.join(root, file)
                    source_files.append(file_path)
                    
        return source_files
    except Exception as e:
        print(f"Error scanning directory: {e}")
        return []


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
    print("🚀 Starting intelligent project analysis with Gemini 2.5 Flash...")
    
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
    
    # Initialize Gemini 2.5 Flash
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.1,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        print("✅ Gemini 2.5 Flash initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing Gemini: {e}")
        return {
            "analysis_complete": False,
            "files_to_process_with_cobol": [],
            "files_to_process_with_vb6": [],
            "files_to_process_with_fortran": [],
            "files_to_process_with_generic": [],
        }
    
    # Scan project files
    source_files = scan_project_files.invoke({"project_path": project_path})
    
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
    
    # Initialize file queues
    files_cobol = []
    files_vb6 = []
    files_fortran = []
    files_generic = []
    detected_languages = set()
    detected_frameworks = set()
    
    # System message for the LLM
    system_message = SystemMessage(content="""
Tu es un expert en analyse de code source et détection de langages de programmation.
Ton rôle est d'analyser chaque fichier source et de déterminer:

1. **Langage de programmation** (COBOL, VB6, Fortran, Python, Java, C++, C#, JavaScript, etc.)
2. **Framework utilisé** (Django, Flask, Spring, React, Angular, etc.) si identifiable
3. **Routing décision**: Vers quel nœud de traitement envoyer ce fichier:
   - `cobol_node` pour les fichiers COBOL (.cob, .cbl, .cpy)
   - `vb6_node` pour les fichiers VB6 (.vb, .bas, .frm, .cls)
   - `fortran_node` pour les fichiers Fortran (.f, .for, .f90, .f95)
   - `generic_node` pour tous les autres langages modernes

Réponds TOUJOURS au format JSON suivant:
{
    "language": "nom_du_langage",
    "framework": "nom_du_framework_ou_null",
    "target_node": "nom_du_noeud",
    "confidence": "high|medium|low"
}
""")
    
    # Process each file with the LLM
    for i, file_path in enumerate(source_files):
        filename = Path(file_path).name
        file_ext = Path(file_path).suffix.lower()
        
        print(f"🔍 Analyzing file {i+1}/{len(source_files)}: {filename}")
        
        # Read file content
        file_content = read_file_content.invoke({"file_path": file_path, "max_chars": 1500})
        
        # Prepare analysis prompt
        analysis_prompt = f"""
Analyse ce fichier source:

**Nom du fichier**: {filename}
**Extension**: {file_ext}
**Chemin**: {file_path}

**Contenu du fichier**:
```
{file_content}
```

Détermine le langage, le framework (si applicable) et le nœud de traitement approprié.
"""
        
        try:
            # Invoke LLM
            messages = [system_message, HumanMessage(content=analysis_prompt)]
            response = await llm.ainvoke(messages)
            
            # Parse LLM response (basic JSON extraction)
            response_text = response.content.strip()
            
            # Try to extract JSON from response
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    analysis_result = json.loads(json_match.group())
                except:
                    # Fallback to extension-based detection
                    analysis_result = fallback_analysis(file_path, file_ext)
            else:
                analysis_result = fallback_analysis(file_path, file_ext)
            
            # Extract information
            language = analysis_result.get("language", "unknown")
            framework = analysis_result.get("framework", None)
            target_node = analysis_result.get("target_node", "generic_node")
            
            detected_languages.add(language)
            if framework:
                detected_frameworks.add(framework)
            
            # Create file info dict
            file_info = {
                "file_path": file_path,
                "filename": filename,
                "language": language,
                "framework": framework,
                "target_node": target_node,
                "analysis_result": analysis_result
            }
            
            # Route to appropriate queue
            if target_node == "cobol_node":
                files_cobol.append(file_info)
                print(f"  📄 {filename} → COBOL_NODE ({language})")
            elif target_node == "vb6_node":
                files_vb6.append(file_info)
                print(f"  📄 {filename} → VB6_NODE ({language})")
            elif target_node == "fortran_node":
                files_fortran.append(file_info)
                print(f"  📄 {filename} → FORTRAN_NODE ({language})")
            else:
                files_generic.append(file_info)
                print(f"  📄 {filename} → GENERIC_NODE ({language})")
                
        except Exception as e:
            print(f"  ❌ Error analyzing {filename}: {e}")
            # Fallback routing
            file_info = {
                "file_path": file_path,
                "filename": filename,
                "language": "unknown",
                "framework": None,
                "target_node": "generic_node",
                "error": str(e)
            }
            files_generic.append(file_info)
    
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
    }
    
    language, target_node = ext_mapping.get(file_ext, ('unknown', 'generic_node'))
    
    return {
        "language": language,
        "framework": None,
        "target_node": target_node,
        "confidence": "medium"
    }
