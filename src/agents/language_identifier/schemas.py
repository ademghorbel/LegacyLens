"""
Pydantic schemas for language identifier agent.

Defines input/output data structures for language detection and analysis.
"""

from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum

from ...core.types import LanguageType


class LanguageHint(BaseModel):
    """Hint about potential language for a file."""
    
    language: LanguageType = Field(..., description="Detected programming language")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    method: str = Field(..., description="Detection method used")
    details: Optional[Dict[str, str]] = Field(default=None, description="Additional detection details")


class FileAnalysisInput(BaseModel):
    """Input schema for analyzing a single file."""
    
    file_path: str = Field(..., description="Path to the file to analyze")
    content: Optional[str] = Field(default=None, description="File content (optional, will read if not provided)")
    max_content_size: int = Field(default=10000, description="Maximum content size to analyze in bytes")


class ProjectAnalysisInput(BaseModel):
    """Input schema for analyzing a project directory."""
    
    project_path: str = Field(..., description="Path to the project directory")
    include_extensions: Optional[List[str]] = Field(default=None, description="File extensions to include")
    exclude_patterns: Optional[List[str]] = Field(default=None, description="Patterns to exclude")
    max_files: int = Field(default=1000, description="Maximum number of files to analyze")


class LanguageAnalysis(BaseModel):
    """Complete analysis result for a file."""
    
    file_path: str = Field(..., description="Path to the analyzed file")
    detected_language: LanguageType = Field(..., description="Primary detected language")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    detection_methods: List[str] = Field(..., description="Methods used for detection")
    alternative_languages: List[LanguageHint] = Field(default_factory=list, description="Alternative language suggestions")
    file_size: int = Field(..., description="File size in bytes")
    analysis_time: float = Field(..., description="Time taken for analysis in seconds")
    frameworks_detected: Optional[List[str]] = Field(default=None, description="Detected frameworks or libraries")
    metadata: Optional[Dict[str, Union[str, int, float]]] = Field(default=None, description="Additional metadata")


class ProjectLanguageStats(BaseModel):
    """Statistics about languages in a project."""
    
    total_files: int = Field(..., description="Total number of files analyzed")
    languages: Dict[LanguageType, Dict[str, Union[int, float]]] = Field(..., description="Language statistics")
    primary_language: Optional[LanguageType] = Field(default=None, description="Most prevalent language")
    file_types: Dict[str, int] = Field(default_factory=dict, description="File extension counts")
    analysis_duration: float = Field(..., description="Total analysis time in seconds")


class AgentResponse(BaseModel):
    """Standard response from the language identifier agent."""
    
    success: bool = Field(..., description="Whether the analysis was successful")
    files_analyzed: int = Field(..., description="Number of files analyzed")
    files_failed: int = Field(default=0, description="Number of files that failed analysis")
    detections: List[LanguageAnalysis] = Field(..., description="Individual file analysis results")
    statistics: Optional[ProjectLanguageStats] = Field(default=None, description="Project-level statistics")
    error_message: Optional[str] = Field(default=None, description="Error message if analysis failed")
    warnings: List[str] = Field(default_factory=list, description="Analysis warnings")
