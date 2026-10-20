#!/usr/bin/env python3
"""
Module Aggregation Node - AI-Powered Analysis Aggregator
========================================================
A specialized node that reads multiple analysis results from the analysis_outputs folder
and intelligently aggregates them into cohesive modules in RFP format for code generation.

INPUT: analysis_outputs folder with multiple JSON analysis files
OUTPUT: Single RFP-formatted JSON with aggregated modules

Features:
- Reads all analysis results from analysis_outputs folder
- AI-powered aggregation of related functionality into modules
- Tech stack consolidation and inference
- Entity extraction and mapping
- Endpoint identification and grouping
- RFP format output ready for code generation agents
"""

import os
import json
import re
import glob
from typing import Dict, Any, List
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from ...llm import get_llm, invoke as llm_invoke

# Global API key, can be overridden by environment variable  
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

class ModuleAggregationNode:
    """
    AI-Powered Module Aggregation Node
    
    Reads multiple analysis results and aggregates them into cohesive modules
    for code generation in RFP format.
    """
    
    def __init__(self, api_key: str = GEMINI_API_KEY):
        """Initialize the module aggregation node"""
        if not api_key:
            raise ValueError("API key is required. Set GOOGLE_API_KEY (or GEMINI_API_KEY) or pass api_key parameter.")
        
        self.api_key = api_key
        self.node_name = "ModuleAggregationNode"
        
        # Initialize LangChain ChatGoogleGenerativeAI
        # One big call over every analysis: long output, long timeout.
        self.llm = get_llm(temperature=0.1, max_output_tokens=16384, timeout=300, key=api_key, json_mode=True)
        self.last_error = None

        print(f"🎯 {self.node_name} initialized ({self.llm.model})")
    
    def process_analysis_folder(self, analysis_folder: str = None) -> Dict[str, Any]:
        """
        Main processing method - reads all analysis files and aggregates them
        
        Args:
            analysis_folder (str, optional): Path to analysis_outputs folder
            
        Returns:
            Dict[str, Any]: RFP-formatted aggregated modules
        """
        print(f"\n🔬 {self.node_name.upper()} PROCESSING STARTED")
        print(f"{'='*60}")
        
        # Find analysis_outputs folder if not provided
        if not analysis_folder:
            analysis_folder = self._find_analysis_outputs_folder()
        
        if not analysis_folder or not os.path.exists(analysis_folder):
            return {
                'status': 'error',
                'error_type': 'analysis_folder_not_found',
                'message': f'Analysis outputs folder not found: {analysis_folder}'
            }
        
        print(f"📁 Analysis Folder: {analysis_folder}")
        
        # Read all analysis files
        analysis_files = self._read_all_analysis_files(analysis_folder)
        
        if not analysis_files:
            return {
                'status': 'error',
                'error_type': 'no_analysis_files',
                'message': 'No analysis files found in the folder'
            }
        
        print(f"📄 Found {len(analysis_files)} analysis files")
        
        # Perform AI-powered aggregation
        aggregation_result = self._perform_aggregation(analysis_files)
        
        # Add processing metadata
        final_result = self._add_aggregation_metadata(aggregation_result, analysis_folder, len(analysis_files))
        
        # Export clustered RFP format
        json_file = self._export_rfp_format(final_result, analysis_folder)
        final_result['rfp_output_file'] = json_file
        
        # Display aggregation summary
        self._display_aggregation_summary(final_result)
        
        return final_result
    
    def _find_analysis_outputs_folder(self) -> str:
        """Find the analysis_outputs folder dynamically"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = current_dir
        
        # Walk up directories to find project root
        while project_root and project_root != os.path.dirname(project_root):
            if any(os.path.exists(os.path.join(project_root, marker)) 
                   for marker in ['pyproject.toml', 'langgraph.json', '.git', 'Makefile']):
                break
            project_root = os.path.dirname(project_root)
        
        analysis_folder = os.path.join(project_root, "outputs", "analysis")
        return analysis_folder if os.path.exists(analysis_folder) else None
    
    def _read_all_analysis_files(self, analysis_folder: str) -> List[Dict[str, Any]]:
        """Read all JSON analysis files from the folder"""
        analysis_files = []
        
        # Find all JSON files in analysis_outputs
        json_pattern = os.path.join(analysis_folder, "analysis_*.json")
        json_files = glob.glob(json_pattern)
        
        print(f"🔍 Found {len(json_files)} JSON files:")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Only include successfully analyzed files
                    if data.get('status') == 'analyzed' and 'analysis' in data:
                        analysis_files.append({
                            'file_path': json_file,
                            'file_name': os.path.basename(json_file),
                            'data': data
                        })
                        print(f"   ✅ {os.path.basename(json_file)}")
                    else:
                        print(f"   ⏭️  {os.path.basename(json_file)} (skipped - not analyzed)")
                        
            except Exception as e:
                print(f"   ❌ {os.path.basename(json_file)} (error: {e})")
                continue
        
        return analysis_files
    
    def _create_aggregation_prompt(self, analysis_files: List[Dict[str, Any]]) -> str:
        """Create aggregation prompt for AI-powered module extraction"""
        
        # Prepare analysis summaries for the prompt
        file_summaries = []
        for i, file_info in enumerate(analysis_files, 1):
            data = file_info['data']
            analysis = data.get('analysis', {})
            
            # Handle both old and new RFP format
            if 'modules' in analysis:
                # New RFP format - extract module information
                modules = analysis.get('modules', [])
                for j, module in enumerate(modules):
                    summary = f"""
File {i}.{j+1}: {file_info['file_name']} - Module: {module.get('module_name', 'Unknown')}
- Description: {module.get('module_description', 'Unknown')}
- Tech Stack: {module.get('tech_stack', [])}
- Expected Output: {module.get('expected_output', 'Unknown')}
- Endpoints: {len(module.get('endpoints', []))} endpoints
- Entities: {list(module.get('entities', {}).keys())}
- Endpoint Details: {module.get('endpoints', [])}
- Entity Details: {module.get('entities', {})}
"""
                    file_summaries.append(summary)
            else:
                # Old format - handle nested analysis structure
                if 'analysis' in analysis:
                    analysis = analysis['analysis']
                
                file_summary = analysis.get('file_summary', {})
                structure = analysis.get('structure', {})
                
                summary = f"""
File {i}: {file_summary.get('file_name', 'Unknown')}
- Role: {file_summary.get('role', 'Unknown')}
- Purpose: {file_summary.get('purpose', 'Unknown')}
- Language: {file_summary.get('language', 'Unknown')}
- Classes: {len(structure.get('classes', []))}
- Functions: {len(structure.get('functions', []))}
- Dependencies: {[dep.get('name', dep) if isinstance(dep, dict) else dep for dep in structure.get('dependencies', [])]}
"""
                file_summaries.append(summary)
        
        files_content = "\n".join(file_summaries)
        
        return f"""You are an expert software architect tasked with aggregating multiple code analysis results into cohesive modules for code generation.

ANALYSIS RESULTS TO AGGREGATE:
{files_content}

TASK: Analyze these modules/files and intelligently aggregate them into logical modules that represent cohesive business functionality. 

IMPORTANT: Some files may already be in RFP module format. You should:
1. **Consolidate similar modules** that belong together (e.g., user-management + authentication = user-auth-system)
2. **Merge related functionality** from different files into cohesive modules
3. **Avoid duplicating modules** - if multiple files describe the same functionality, create one consolidated module
4. **Enhance module descriptions** by combining insights from all related files
5. **Consolidate tech stacks** and remove duplicates
6. **Merge related endpoints** and entities from similar modules 

OUTPUT REQUIREMENTS:
Return ONLY a JSON response in this EXACT RFP format:
{{
  "modules": [
    {{
      "module_name": "descriptive-module-name-kebab-case",
      "module_description": "Clear description of what this module does and its business purpose",
      "source_files": ["exact file names from the list above that belong to this module"],
      "tech_stack": ["inferred technology stack - Python, FastAPI, PostgreSQL, React, etc."],
      "expected_output": "Detailed description of what this module would produce when implemented",
      "endpoints": [
        {{
          "path": "/api/endpoint-path",
          "method": "GET|POST|PUT|DELETE|PATCH"
        }}
      ],
      "entities": {{
        "EntityName": {{
          "field_name": "field_type",
          "another_field": "field_type"
        }}
      }}
    }}
  ]
}}

AGGREGATION GUIDELINES:
1. **Module Cohesion**: Group related functionality that belongs together (e.g., user management, authentication, file processing)
2. **Business Logic**: Focus on business capabilities rather than technical implementation details
3. **Tech Stack Inference**: Consolidate technology stacks from dependencies and patterns
4. **Entity Extraction**: Identify classes that could become database entities
5. **API Surface**: Extract or suggest REST endpoints based on functionality
6. **Module Naming**: Use descriptive kebab-case names that reflect business purpose
7. **Realistic Grouping**: Don't force unrelated files into the same module

AGGREGATION STRATEGIES:
- Files with similar purposes or roles should be grouped together
- Files that share common dependencies often belong in the same module
- Consider the architectural layers (presentation, business, data) when grouping
- Look for common entity patterns or data models
- Group files that would naturally be deployed together

IMPORTANT:
- If files are too different to cluster meaningfully, create separate modules
- Ensure each module has a clear, focused responsibility
- Infer realistic tech stacks based on actual dependencies found
- Suggest appropriate REST endpoints based on the functionality
- Map data structures to appropriate database field types

Return ONLY the JSON response, no additional text."""
    
    def _perform_aggregation(self, analysis_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform AI-powered aggregation of analysis results"""
        print("🤖 Performing AI-powered module aggregation...")
        
        # Create aggregation prompt
        prompt = self._create_aggregation_prompt(analysis_files)
        
        # Call AI for aggregation
        aggregation_result = self._call_langchain_llm(prompt)
        
        if aggregation_result:
            return {
                'status': 'aggregated',
                'modules': aggregation_result.get('modules', []),
                'aggregation_method': 'langchain_google_gemini'
            }
        else:
            return {
                'status': 'error',
                'error_type': 'aggregation_failed',
                'message': f"AI aggregation failed: {self.last_error or 'unknown error'}"
            }
    
    def _call_langchain_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LangChain LLM for aggregation with robust error handling"""
        print("🌐 Calling Google Gemini API for aggregation...")
        
        try:
            # Create messages for LangChain
            system_message = SystemMessage(
                content="You are a software architecture expert specialized in module extraction and clustering. Always return valid JSON responses in RFP format."
            )
            human_message = HumanMessage(content=prompt)
            
            self.last_error = None
            generated_text = llm_invoke(self.llm, [system_message, human_message])
            
            # Clean and parse JSON response
            if '```json' in generated_text:
                generated_text = generated_text.split('```json')[1].split('```')[0]
            elif '```' in generated_text:
                parts = generated_text.split('```')
                for part in parts:
                    part = part.strip()
                    if part.startswith('{') and part.endswith('}'):
                        generated_text = part
                        break
            
            generated_text = generated_text.strip()
            
            try:
                return json.loads(generated_text)
            except json.JSONDecodeError:
                pass
            # Models sometimes leave trailing commas: {"a": 1,} or [1, 2,]
            try:
                return json.loads(re.sub(r",(\s*[}\]])", r"\1", generated_text))
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}")
                print(f"Raw response (first 500 chars): {generated_text[:500]}...")
                self.last_error = f"invalid JSON from model: {e}"
                return None
                
        except Exception as e:
            print(f"❌ LangChain LLM call error: {e}")
            self.last_error = f"{type(e).__name__}: {str(e)[:300]}"
            
            # Provide specific error guidance
            error_str = str(e).lower()
            if 'quota' in error_str or 'rate limit' in error_str:
                print("💡 API quota exceeded. Wait before trying again.")
            elif 'authentication' in error_str or 'api key' in error_str:
                print("💡 Authentication issue. Check your API key.")
            else:
                print("💡 Unexpected error. Check your internet connection and API key.")
            
            return None
    
    def _add_aggregation_metadata(self, result: Dict[str, Any], analysis_folder: str, file_count: int) -> Dict[str, Any]:
        """Add aggregation metadata"""
        result['metadata'] = {
            'node_name': self.node_name,
            'node_version': '1.0.0',
            'processed_at': datetime.now().isoformat(),
            'analysis_folder': analysis_folder,
            'files_processed': file_count,
            'aggregation_engine': f'langchain_{self.llm.model}'
        }
        return result
    
    def _export_rfp_format(self, result: Dict[str, Any], analysis_folder: str) -> str:
        """Export aggregated modules in RFP format to structured output folder"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rfp_filename = f"rfp_modules_aggregated_{timestamp}.json"
        
        # Create structured output directory
        parent_dir = os.path.dirname(analysis_folder)
        structured_output_dir = os.path.join(parent_dir, "rfp_modules_output")
        
        # Create the output directory if it doesn't exist
        os.makedirs(structured_output_dir, exist_ok=True)
        
        # Main RFP file in structured output directory
        rfp_filepath = os.path.join(structured_output_dir, rfp_filename)
        
        # Also keep a copy in project root for compatibility
        root_rfp_filepath = os.path.join(parent_dir, rfp_filename)
        
        try:
            # Create clean RFP format output
            rfp_output = {
                "modules": result.get('modules', []),
                "metadata": {
                    "generated_at": timestamp,
                    "modules_count": len(result.get('modules', [])),
                    "aggregation_engine": f"LangChain + {self.llm.model}"
                }
            }
            
            # Also save detailed result with metadata
            detailed_filepath = os.path.join(analysis_folder, f"detailed_aggregation_{timestamp}.json")
            
            # Write RFP format to structured output
            with open(rfp_filepath, 'w', encoding='utf-8') as f:
                json.dump(rfp_output, f, indent=2, ensure_ascii=False)
                
            # Write copy to project root for compatibility
            with open(root_rfp_filepath, 'w', encoding='utf-8') as f:
                json.dump(rfp_output, f, indent=2, ensure_ascii=False)
            
            # Write detailed result to analysis folder
            with open(detailed_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"💾 RFP format exported to: outputs/rfp_modules_output/{rfp_filename}")
            print(f"💾 Copy also saved to: outputs/{rfp_filename}")
            print(f"💾 Detailed result exported to: outputs/analysis/detailed_aggregation_{timestamp}.json")
            return rfp_filepath
            
        except Exception as e:
            print(f"❌ Could not export RFP format: {e}")
            return f"ERROR: Could not export {rfp_filename}"
    
    def _display_aggregation_summary(self, result: Dict[str, Any]):
        """Display aggregation results summary"""
        print(f"\n📊 {self.node_name.upper()} PROCESSING COMPLETE")
        print(f"{'='*60}")
        
        if result['status'] != 'aggregated':
            print(f"❌ Status: {result['status']}")
            error_msg = result.get('message', 'Unknown error')
            print(f"❌ Error: {error_msg}")
            return
        
        modules = result.get('modules', [])
        print(f"✅ Status: SUCCESS (Module Aggregation)")
        print(f"📦 Modules Created: {len(modules)}")
        
        for i, module in enumerate(modules, 1):
            print(f"\n🎯 MODULE {i}: {module.get('module_name', 'Unknown')}")
            print(f"   📝 Description: {module.get('module_description', 'No description')[:100]}...")
            print(f"   🔧 Tech Stack: {', '.join(module.get('tech_stack', []))}")
            
            endpoints = module.get('endpoints', [])
            entities = module.get('entities', {})
            
            print(f"   🌐 Endpoints: {len(endpoints)}")
            print(f"   🗃️  Entities: {len(entities)}")
            
            if endpoints:
                for endpoint in endpoints[:2]:  # Show first 2
                    print(f"      • {endpoint.get('method', 'GET')} {endpoint.get('path', '/unknown')}")
            
            if entities:
                for entity_name in list(entities.keys())[:2]:  # Show first 2
                    field_count = len(entities[entity_name]) if isinstance(entities[entity_name], dict) else 0
                    print(f"      • {entity_name} ({field_count} fields)")
        
        print(f"\n🚀 RFP format ready for code generation!")
        print(f"📂 Files exported to outputs/ and outputs/analysis/")


# Factory function for easy instantiation
def create_module_aggregation_node(api_key: str = GEMINI_API_KEY) -> ModuleAggregationNode:
    """Create a module aggregation node instance"""
    return ModuleAggregationNode(api_key)

# Main function for orchestrator integration
def aggregate_analysis_results(analysis_folder: str = None, api_key: str = None) -> Dict[str, Any]:
    """
    Main function to aggregate analysis results into RFP modules
    
    Args:
        analysis_folder (str, optional): Path to analysis_outputs folder
        api_key (str, optional): Google Gemini API key
        
    Returns:
        Dict[str, Any]: Aggregated modules in RFP format
    """
    node = create_module_aggregation_node(api_key) if api_key else create_module_aggregation_node()
    return node.process_analysis_folder(analysis_folder)

if __name__ == "__main__":
    # Test the aggregation node
    print("🧪 Testing Module Aggregation Node")
    
    try:
        result = aggregate_analysis_results()
        print(f"Aggregation Result: {result['status']}")
        
        if result['status'] == 'aggregated':
            modules = result.get('modules', [])
            print(f"Successfully created {len(modules)} modules!")
            
    except Exception as e:
        print(f"Error: {e}")
