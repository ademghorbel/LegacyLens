#!/usr/bin/env python3
"""
Generic Node - Universal Code Analysis Agent (LangChain Version)
==============================================================
A general-purpose code analysis node using LangChain for better reliability.

INPUT: {"file_path": str, "language": str}
OUTPUT: JSON file with comprehensive code analysis

Features:
- Universal compatibility with any orchestrator/pipeline
- LangChain integration for robust API handling
- Comprehensive code analysis (architecture, dependencies, classes, functions)
- LLM-friendly structured output for diagram generation
- Robust error handling and retry mechanisms
- Automatic JSON export with timestamped results
"""

import os
import json
from typing import Dict, Any
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from ...llm import get_llm, invoke as llm_invoke

# Global API key, can be overridden by environment variable  
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

class GenericCodeAnalysisNodeLangChain:
    """
    Universal Code Analysis Node using LangChain
    
    A general-purpose node that can be integrated into any pipeline or orchestrator.
    Receives file path and language, performs comprehensive analysis, exports JSON.
    """
    
    def __init__(self, api_key: str = GEMINI_API_KEY):
        """Initialize the universal code analysis node with LangChain"""
        if not api_key:
            raise ValueError("API key is required. Set GOOGLE_API_KEY (or GEMINI_API_KEY) or pass api_key parameter.")
        
        self.api_key = api_key
        self.node_name = "GenericCodeAnalysisNodeLangChain"
        
        # Initialize LangChain ChatGoogleGenerativeAI
        # Shared factory: model from GEMINI_MODEL, timeout, retries, rate limit.
        # Structured JSON for large files gets long, hence the bigger budget.
        self.llm = get_llm(temperature=0.1, max_output_tokens=16384, timeout=180, key=api_key)
        self.last_error = None

        print(f"🎯 {self.node_name} initialized ({self.llm.model})")
    
    def process(self, file_path: str, language: str) -> Dict[str, Any]:
        """
        Main processing method - Universal interface for any orchestrator
        
        Args:
            file_path (str): Path to the source code file
            language (str): Programming language name
            
        Returns:
            Dict[str, Any]: Complete analysis results with JSON file path
        """
        # Create input format for internal processing
        input_data = {
            "file_path": file_path,
            "language": language
        }
        
        return self.analyze_file(input_data)
    
    def analyze_file(self, input_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Core analysis method
        
        Args:
            input_data: {"file_path": str, "language": str}
            
        Returns:
            Complete analysis results with JSON file creation
        """
        print(f"\n🔬 {self.node_name.upper()} PROCESSING STARTED")
        print(f"{'='*60}")
        
        file_path = input_data.get('file_path', '')
        language = input_data.get('language', '')
        
        print(f"📁 File: {os.path.basename(file_path)}")
        print(f"🔤 Language: {language}")
        print(f"📍 Path: {file_path}")
        
        # Validate inputs
        validation = self._validate_inputs(file_path, language)
        if validation['status'] != 'valid':
            json_file = self._export_to_json(validation, file_path)
            validation['json_output_file'] = json_file
            validation['exported_json'] = json_file
            return validation
        
        # Read file content
        content = self._read_file_content(file_path)
        if not content:
            error_result = {
                'status': 'error',
                'error_type': 'file_read_failed',
                'message': f'Could not read file content: {file_path}',
                'input_data': input_data
            }
            json_file = self._export_to_json(error_result, file_path)
            error_result['json_output_file'] = json_file
            error_result['exported_json'] = json_file
            return error_result
        
        # Perform analysis using LangChain
        analysis_result = self._perform_analysis(content, file_path, language)
        
        # Add processing metadata
        final_result = self._add_processing_metadata(analysis_result, input_data)
        
        # Export to JSON file
        json_file = self._export_to_json(final_result, file_path)
        final_result['json_output_file'] = json_file
        final_result['exported_json'] = json_file
        
        # Display results summary
        self._display_results_summary(final_result)
        
        return final_result
    
    def _validate_inputs(self, file_path: str, language: str) -> Dict[str, Any]:
        """Validate input parameters from orchestrator"""
        if not file_path:
            return {
                'status': 'error',
                'error_type': 'missing_file_path',
                'message': 'file_path parameter is required'
            }
            
        if not language:
            return {
                'status': 'error',
                'error_type': 'missing_language',
                'message': 'language parameter is required'
            }
        
        if not os.path.exists(file_path):
            return {
                'status': 'error',
                'error_type': 'file_not_found',
                'message': f'File does not exist: {file_path}'
            }
        
        return {'status': 'valid'}
    
    def _read_file_content(self, file_path: str) -> str:
        """Read source code file with multiple encoding support"""
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    # Limit content for API processing (100KB max)
                    if len(content) > 100000:
                        content = content[:100000] + "\n... [Content truncated for API processing]"
                    return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"❌ Error reading file with {encoding}: {e}")
                continue
        
        print(f"❌ Could not read file with any supported encoding")
        return ""
    
    def _create_analysis_prompt(self, content: str, file_name: str, language: str) -> str:
        """Create analysis prompt for LangChain"""
        return f"""Analyze this {language} file named "{file_name}" and provide comprehensive structured analysis.

File Content:
```{language}
{content}
```

Provide analysis in this EXACT JSON format for LLM-friendly diagram generation:
{{
  "file_summary": {{
    "file_name": "{file_name}",
    "role": "Determine the architectural role (Controller, Service, Repository, Entity, Utility, Main Entry Point, View, Model, etc.)",
    "language": "{language}",
    "purpose": "Brief description of file's purpose in the system"
  }},
  "structure": {{
    "classes": [
      {{
        "name": "ClassName",
        "type": "class|interface|enum|abstract_class",
        "functionality": "What this class does in the system",
        "methods": [
          {{
            "name": "methodName",
            "functionality": "What this method does",
            "inputs": ["parameter types"],
            "outputs": ["return type"],
            "visibility": "public|private|protected"
          }}
        ],
        "attributes": [
          {{
            "name": "attributeName",
            "type": "data type",
            "visibility": "public|private|protected"
          }}
        ]
      }}
    ],
    "functions": [
      {{
        "name": "functionName",
        "functionality": "What this function does",
        "inputs": ["parameter types"],
        "outputs": ["return type"]
      }}
    ],
    "dependencies": [
      {{
        "name": "dependency name",
        "type": "import|package|library|framework",
        "usage": "how it's used in the code"
      }}
    ],
    "design_patterns": ["detected patterns: Singleton, Factory, Observer, MVC, Repository, etc."]
  }},
  "architecture": {{
    "architectural_role": "How this component fits in the overall system architecture",
    "layer": "presentation|business|data|utility|infrastructure",
    "responsibilities": ["list of main responsibilities"],
    "interactions": ["describes how it interacts with other components"]
  }},
  "functional_description": "Detailed description of the file's role, functionality, and its place in the system architecture"
}}

Focus on extracting information useful for generating architectural diagrams:
1. Every class, interface, method, function, and attribute
2. All dependencies, imports, and external packages
3. Design patterns and architectural patterns
4. Component responsibilities and interactions
5. System layer identification (presentation, business, data, etc.)

Return ONLY the JSON response, no additional text or formatting."""
    
    def _call_langchain_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LangChain LLM with robust error handling"""
        print("🌐 Calling Google Gemini API via LangChain...")
        
        try:
            # Create messages for LangChain
            system_message = SystemMessage(
                content="You are a code analysis assistant specialized in reverse engineering and architectural analysis. Always return valid JSON responses."
            )
            human_message = HumanMessage(content=prompt)
            
            # Call the LLM (text extraction handles string and block replies)
            self.last_error = None
            generated_text = llm_invoke(self.llm, [system_message, human_message])
            
            # Clean and parse JSON response
            if '```json' in generated_text:
                generated_text = generated_text.split('```json')[1].split('```')[0]
            elif '```' in generated_text:
                # Try to extract JSON from code blocks
                parts = generated_text.split('```')
                for part in parts:
                    part = part.strip()
                    if part.startswith('{') and part.endswith('}'):
                        generated_text = part
                        break
            
            # Clean up the text
            generated_text = generated_text.strip()
            
            try:
                return json.loads(generated_text)
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}")
                print(f"Raw response (first 300 chars): {generated_text[:300]}...")
                self.last_error = f"invalid JSON from model: {e}"
                
                # Try to fix common JSON issues
                if generated_text.startswith('{') and generated_text.endswith('}'):
                    # Try to extract just the JSON part
                    lines = generated_text.split('\n')
                    json_lines = []
                    in_json = False
                    
                    for line in lines:
                        if line.strip().startswith('{'):
                            in_json = True
                        if in_json:
                            json_lines.append(line)
                        if line.strip().endswith('}') and in_json:
                            break
                    
                    try:
                        return json.loads('\n'.join(json_lines))
                    except:
                        pass
                
                return None
                
        except Exception as e:
            print(f"❌ LangChain LLM call error: {e}")
            self.last_error = f"{type(e).__name__}: {str(e)[:300]}"
            
            # Provide specific error guidance
            error_str = str(e).lower()
            if 'timeout' in error_str:
                print("💡 The request timed out. This could be due to:")
                print("   • Large file size")
                print("   • Network connectivity issues")
                print("   • Google API server load")
            elif 'authentication' in error_str or 'api key' in error_str or 'unauthorized' in error_str:
                print("💡 Authentication issue. Check your API key.")
                print(f"💡 API key set: {'Yes' if self.api_key else 'No'}")
            elif 'quota' in error_str or 'rate limit' in error_str or '429' in error_str:
                print("💡 API quota exceeded. Wait before trying again.")
                print("💡 Options:")
                print("   • Wait 24 hours for quota reset")
                print("   • Upgrade to paid plan at https://ai.google.dev/")
                print("   • Use a different API key if available")
            elif 'model' in error_str and 'not found' in error_str:
                print("💡 Model not found. Check the model name.")
            else:
                print("💡 Unexpected error. Check your internet connection and API key.")
                print(f"💡 Full error: {str(e)}")
            
            return None
    
    def _perform_analysis(self, content: str, file_path: str, language: str) -> Dict[str, Any]:
        """Perform AI-powered code analysis using LangChain"""
        file_name = os.path.basename(file_path)
        
        # Create analysis prompt
        prompt = self._create_analysis_prompt(content, file_name, language)
        
        # Call LangChain LLM for analysis
        analysis = self._call_langchain_llm(prompt)
        
        if analysis:
            return {
                'status': 'analyzed',
                'analysis': analysis,
                'analysis_method': 'langchain_google_gemini',
                'processed_by': self.node_name
            }
        else:
            return {
                'status': 'error',
                'error_type': 'analysis_failed',
                'message': f"AI analysis failed: {self.last_error or 'unknown error'}",
                'error_detail': self.last_error,
                'processed_by': self.node_name
            }
    
    def _add_processing_metadata(self, result: Dict[str, Any], input_data: Dict[str, str]) -> Dict[str, Any]:
        """Add processing metadata for orchestrator tracking"""
        result['metadata'] = {
            'node_name': self.node_name,
            'node_version': '2.1.0',
            'processed_at': datetime.now().isoformat(),
            'input_data': input_data,
            'processing_engine': f'langchain_{self.llm.model}',
            'orchestrator_compatible': True
        }
        return result
    
    def _export_to_json(self, result: Dict[str, Any], file_path: str) -> str:
        """Export analysis results to JSON file for orchestrator consumption"""
        file_name = os.path.basename(file_path) if file_path else 'unknown_file'
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"analysis_{file_name}_{timestamp}.json"
        
        # Find project root dynamically
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = current_dir
        
        # Walk up directories to find project root
        while project_root and project_root != os.path.dirname(project_root):
            if any(os.path.exists(os.path.join(project_root, marker)) 
                   for marker in ['pyproject.toml', 'langgraph.json', '.git', 'Makefile']):
                break
            project_root = os.path.dirname(project_root)
        
        # Create outputs/analysis directory for orchestrator integration
        outputs_dir = os.path.join(project_root, "outputs", "analysis")
        os.makedirs(outputs_dir, exist_ok=True)
        
        json_filepath = os.path.join(outputs_dir, json_filename)
        
        try:
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Analysis exported to: outputs/analysis/{json_filename}")
            return json_filepath
        except Exception as e:
            print(f"❌ Could not export JSON: {e}")
            return f"ERROR: Could not export {json_filename}"
    
    def _display_results_summary(self, result: Dict[str, Any]):
        """Display processing results summary for orchestrator monitoring"""
        print(f"\n📊 {self.node_name.upper()} PROCESSING COMPLETE")
        print(f"{'='*60}")
        
        if result['status'] != 'analyzed':
            print(f"❌ Status: {result['status']}")
            error_msg = result.get('message', 'Unknown error')
            print(f"❌ Error: {error_msg}")
            
            # Provide specific guidance based on error type
            if 'error_type' in result:
                error_type = result['error_type']
                if error_type == 'analysis_failed':
                    print(f"💡 AI analysis failed - check file content and language parameter")
                elif error_type == 'file_not_found':
                    print(f"💡 File path issue - verify file exists")
                elif error_type == 'file_read_failed':
                    print(f"💡 File encoding issue - check file accessibility")
                elif error_type in ['missing_file_path', 'missing_language']:
                    print(f"💡 Missing required parameters from orchestrator")
            
            return
        
        analysis = result['analysis']
        file_summary = analysis['file_summary']
        structure = analysis['structure']
        architecture = analysis.get('architecture', {})
        
        print(f"✅ Status: SUCCESS")
        print(f"🎯 Role: {file_summary['role']}")
        print(f"📝 Purpose: {file_summary.get('purpose', 'Not specified')}")
        print(f"🔤 Language: {file_summary['language']}")
        print(f"🏗️  Layer: {architecture.get('layer', 'Not specified')}")
        print(f"📦 Classes: {len(structure.get('classes', []))}")
        print(f"⚙️  Functions: {len(structure.get('functions', []))}")
        print(f"🔗 Dependencies: {len(structure.get('dependencies', []))}")
        print(f"🎨 Design Patterns: {len(structure.get('design_patterns', []))}")
        print(f"💾 JSON Exported: {os.path.basename(result['json_output_file'])}")
        
        # Show key classes
        if structure.get('classes'):
            print(f"\n📋 KEY CLASSES:")
            for i, cls in enumerate(structure['classes'][:3], 1):
                print(f"   {i}. {cls['name']} - {cls.get('functionality', 'No description')}")
        
        # Show key functions
        if structure.get('functions'):
            print(f"\n⚙️  KEY FUNCTIONS:")
            for i, func in enumerate(structure['functions'][:3], 1):
                print(f"   {i}. {func['name']} - {func.get('functionality', 'No description')}")
        
        # Show key dependencies  
        if structure.get('dependencies'):
            print(f"\n🔗 KEY DEPENDENCIES:")
            for i, dep in enumerate(structure['dependencies'][:5], 1):
                dep_name = dep if isinstance(dep, str) else dep.get('name', 'Unknown')
                print(f"   {i}. {dep_name}")
        
        # Show responsibilities
        if architecture.get('responsibilities'):
            print(f"\n🎯 RESPONSIBILITIES:")
            for i, resp in enumerate(architecture['responsibilities'][:3], 1):
                print(f"   {i}. {resp}")
        
        print(f"\n🚀 Ready for orchestrator consumption!")
        print(f"📂 JSON available at: outputs/analysis/")


# Universal factory function for orchestrator integration
def create_generic_node_langchain(api_key: str = GEMINI_API_KEY) -> GenericCodeAnalysisNodeLangChain:
    """Create a generic code analysis node instance using LangChain for orchestrator use"""
    return GenericCodeAnalysisNodeLangChain(api_key)

# Main function for orchestrator integration
def analyze_code_file(file_path: str, language: str, api_key: str = None) -> Dict[str, Any]:
    """
    Universal function for orchestrator integration
    
    Args:
        file_path (str): Path to the source code file
        language (str): Programming language name
        api_key (str, optional): Google Gemini API key
        
    Returns:
        Dict[str, Any]: Complete analysis with JSON export path
    """
    node = create_generic_node_langchain(api_key) if api_key else create_generic_node_langchain()
    return node.process(file_path, language)

if __name__ == "__main__":
    # Quick test
    print("🧪 Testing LangChain Generic Node")
    
    # Test with a simple file
    test_file = "test_langchain.py"
    test_content = '''def hello_world():
    """Simple test function"""
    return "Hello, World!"

class TestClass:
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value
'''
    
    with open(test_file, 'w') as f:
        f.write(test_content)
    
    try:
        result = analyze_code_file(test_file, "python")
        print(f"Result: {result['status']}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
