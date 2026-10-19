# Generic Code Analyzer Node

## Overview
A standalone generic code analysis node that uses Google Gemini API to analyze source code files and extract architectural information, dependencies, classes, functions, and design patterns.

## Purpose
- Analyzes source code files for architectural insights
- Extracts LLM-friendly structured data for diagram generation
- Provides comprehensive code analysis without orchestrator dependencies

## Input Format
```python
{
    "file_path": str,    # Path to the source code file
    "language": str      # Programming language (python, java, javascript, etc.)
}
```

## Output
- **Status**: `analyzed` or `error`
- **JSON File**: Timestamped analysis results saved to `analysis_results/`
- **Structured Data**: Architecture, dependencies, classes, functions, design patterns

## JSON Output Structure
```json
{
  "status": "analyzed",
  "analysis": {
    "file_summary": {
      "file_name": "example.py",
      "role": "Controller|Service|Repository|Entity|Utility|etc.",
      "language": "python",
      "purpose": "Brief description of file's purpose"
    },
    "structure": {
      "classes": [...],
      "functions": [...],
      "dependencies": [...],
      "design_patterns": [...]
    },
    "architecture": {
      "architectural_role": "Component's role in system",
      "layer": "presentation|business|data|utility|infrastructure",
      "responsibilities": [...],
      "interactions": [...]
    },
    "functional_description": "Detailed description..."
  },
  "metadata": {
    "agent_name": "GenericCodeAnalyzer",
    "timestamp": "2025-07-29T15:26:36.123456",
    "input_data": {...}
  },
  "json_output_file": "path/to/analysis.json"
}
```

## Usage Examples

### Basic Usage
```python
from generic_node import analyze_code_file

# Analyze a Python file
result = analyze_code_file({
    "file_path": "/path/to/code.py",
    "language": "python"
})

if result['status'] == 'analyzed':
    print(f"Analysis successful: {result['json_output_file']}")
else:
    print(f"Analysis failed: {result['message']}")
```

### Pipeline Integration
```python
from generic_node import GenericCodeAnalyzer

# Create analyzer instance
analyzer = GenericCodeAnalyzer()

# Analyze file
result = analyzer.analyze_file({
    "file_path": "/path/to/code.java",
    "language": "java"
})
```

## Features

### ✅ **Comprehensive Analysis**
- Architecture role identification
- Class and method extraction
- Dependency analysis
- Design pattern detection
- System layer identification

### ✅ **LLM-Friendly Output** 
- Structured JSON format
- Ready for diagram generation
- Detailed architectural insights
- Component relationships

### ✅ **Robust Error Handling**
- API retry mechanisms
- Clear error messages
- Fallback strategies
- Troubleshooting guidance

### ✅ **Language Support**
- Python, Java, JavaScript, HTML, CSS
- C++, C#, PHP, Ruby, Go, Rust
- And many more...

## Configuration

### API Key
Set your Google Gemini API key:
```python
from generic_node import GenericCodeAnalyzer

analyzer = GenericCodeAnalyzer(api_key="your-api-key-here")
```

### Output Directory
Analysis results are saved to `analysis_results/` in the project root.

## Testing
Run the built-in test:
```bash
python generic_node.py
```

Or use the example:
```bash
python example_usage.py
```

## Error Handling
- **File Not Found**: Validates file existence
- **API Failures**: Automatic retries with exponential backoff
- **JSON Parsing**: Handles malformed API responses
- **Encoding Issues**: Multiple encoding fallbacks

## Dependencies
- `requests`: For Google Gemini API calls
- `json`: For data serialization
- `os`: For file operations
- `datetime`: For timestamps
- `typing`: For type hints

## Integration Notes
- No orchestrator dependencies
- Standalone operation
- Clean input/output interface
- Ready for pipeline integration
- LLM-friendly structured output
