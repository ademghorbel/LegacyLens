"""
Language identifier agent package.

Initializes the module and makes its components importable.
Defines key classes and functions for external use.
"""

from .agent import LanguageIdentifierAgent
from .config import LanguageIdentifierConfig, get_language_identifier_config
from .schemas import (
    LanguageHint,
    FileAnalysisInput,
    ProjectAnalysisInput,
    LanguageAnalysis,
    ProjectLanguageStats,
    AgentResponse
)
from .tools import (
    StaticAnalyzer,
    ContentAnalyzer,
    KeywordDetector,
    FrameworkDetector,
    FileAnalysisTools
)
from .prompts import get_prompt, get_all_prompts, reload_prompts

# Export main components
__all__ = [
    # Main agent class
    "LanguageIdentifierAgent",
    
    # Configuration
    "LanguageIdentifierConfig",
    "get_language_identifier_config",
    
    # Schemas
    "LanguageHint",
    "FileAnalysisInput", 
    "ProjectAnalysisInput",
    "LanguageAnalysis",
    "ProjectLanguageStats",
    "AgentResponse",
    
    # Tools
    "StaticAnalyzer",
    "ContentAnalyzer", 
    "KeywordDetector",
    "FrameworkDetector",
    "FileAnalysisTools",
    
    # Prompts
    "get_prompt",
    "get_all_prompts",
    "reload_prompts"
]

# Version info
__version__ = "1.0.0"
__author__ = "Reverse Engineering Pipeline"
__description__ = "Language identification agent for programming language detection"
