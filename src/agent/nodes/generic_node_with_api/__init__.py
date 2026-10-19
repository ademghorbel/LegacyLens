#!/usr/bin/env python3
"""
Generic Node - Universal Code Analysis Agent
===========================================

A professional code analysis system with LangChain integration for reliable,
comprehensive analysis of source code files across multiple programming languages.

Main Components:
- GenericCodeAnalysisNodeLangChain: Core analysis engine
- analyze_code_file: Main entry point function

Usage:
    from generic_node import analyze_code_file
    
    result = analyze_code_file("path/to/file.py", "python")
    if result['status'] == 'analyzed':
        print(f"Analysis complete: {result['json_output_file']}")

Requirements:
- GOOGLE_API_KEY (or GEMINI_API_KEY) environment variable must be set
- langchain-google-genai package must be installed
"""

from .generic_node import (
    GenericCodeAnalysisNodeLangChain,
    analyze_code_file,
    create_generic_node_langchain
)

__version__ = "2.1.0"
__author__ = "Generic Node Development Team"

__all__ = [
    "GenericCodeAnalysisNodeLangChain",
    "analyze_code_file", 
    "create_generic_node_langchain"
]
