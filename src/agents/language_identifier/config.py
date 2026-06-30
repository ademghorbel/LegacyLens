"""
Configuration settings specific to the LanguageIdentifier agent.

Loads settings from config/agents/ using YAML and environment variables,
and defines defaults or validation rules for the language identification process.
"""

import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field


def get_config_value(env_var: str, default_value: Any, value_type: type = str) -> Any:
    """Get configuration value from environment variable with type conversion."""
    value = os.getenv(env_var, default_value)
    
    if value_type == bool:
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    elif value_type == int:
        return int(value)
    elif value_type == float:
        return float(value)
    else:
        return value


@dataclass
class LanguageIdentifierConfig:
    """Configuration for the Language Identifier Agent."""
    
    # LLM Configuration
    llm_provider: str = field(default="gemini")
    llm_model: str = field(default="gemini-2.5-flash")
    llm_temperature: float = field(default=0.1)
    llm_max_tokens: int = field(default=1000)
    llm_timeout: int = field(default=30)
    
    # Analysis Configuration
    max_file_size: int = field(default=1024 * 1024)  # 1MB
    max_content_analysis: int = field(default=10000)  # First 10KB for LLM
    enable_llm_analysis: bool = field(default=True)
    enable_framework_detection: bool = field(default=True)
    enable_confidence_scoring: bool = field(default=True)
    
    # File Processing
    supported_extensions: List[str] = field(default_factory=lambda: [
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.php',
        '.rb', '.swift', '.kt', '.cs', '.sh', '.ps1', '.sql', '.html',
        '.css', '.json', '.xml', '.yaml', '.yml', '.md'
    ])
    
    exclude_patterns: List[str] = field(default_factory=lambda: [
        '__pycache__', '.git', '.svn', '.hg', 'node_modules', '.venv',
        '*.pyc', '*.pyo', '*.class', '*.o', '*.so', '*.dll'
    ])
    
    # Detection Weights
    extension_weight: float = field(default=0.3)
    shebang_weight: float = field(default=0.4)
    keyword_weight: float = field(default=0.2)
    llm_weight: float = field(default=0.4)
    
    # Confidence Thresholds
    high_confidence_threshold: float = field(default=0.8)
    medium_confidence_threshold: float = field(default=0.6)
    low_confidence_threshold: float = field(default=0.4)
    
    # Performance Settings
    parallel_processing: bool = field(default=True)
    max_workers: int = field(default=4)
    batch_size: int = field(default=10)
    
    # Caching
    enable_cache: bool = field(default=True)
    cache_ttl: int = field(default=3600)  # 1 hour


class ConfigLoader:
    """Loads and validates configuration for the Language Identifier Agent."""
    
    @staticmethod
    def load_from_env() -> LanguageIdentifierConfig:
        """Load configuration from environment variables."""
        config = LanguageIdentifierConfig()
        
        # LLM Configuration from environment
        config.llm_provider = get_config_value("LANGUAGE_IDENTIFIER_LLM_PROVIDER", config.llm_provider)
        config.llm_model = get_config_value("LANGUAGE_IDENTIFIER_LLM_MODEL", config.llm_model)
        config.llm_temperature = float(get_config_value("LANGUAGE_IDENTIFIER_LLM_TEMPERATURE", config.llm_temperature))
        config.llm_max_tokens = int(get_config_value("LANGUAGE_IDENTIFIER_LLM_MAX_TOKENS", config.llm_max_tokens))
        config.llm_timeout = int(get_config_value("LANGUAGE_IDENTIFIER_LLM_TIMEOUT", config.llm_timeout))
        
        # Analysis settings
        config.max_file_size = int(get_config_value("LANGUAGE_IDENTIFIER_MAX_FILE_SIZE", config.max_file_size))
        config.max_content_analysis = int(get_config_value("LANGUAGE_IDENTIFIER_MAX_CONTENT", config.max_content_analysis))
        config.enable_llm_analysis = get_config_value("LANGUAGE_IDENTIFIER_ENABLE_LLM", config.enable_llm_analysis, bool)
        
        # Performance settings
        config.parallel_processing = get_config_value("LANGUAGE_IDENTIFIER_PARALLEL", config.parallel_processing, bool)
        config.max_workers = int(get_config_value("LANGUAGE_IDENTIFIER_MAX_WORKERS", config.max_workers))
        
        return config
    
    @staticmethod
    def load_from_yaml(yaml_path: Optional[str] = None) -> LanguageIdentifierConfig:
        """Load configuration from YAML file."""
        if yaml_path is None:
            # Read from config/agents/language_identifier.yaml
            yaml_path = str(Path(__file__).parent.parent.parent.parent.parent / "config" / "agents" / "language_identifier.yaml")
        
        config = LanguageIdentifierConfig()
        
        try:
            import yaml
            if yaml_path is not None:
                with open(yaml_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
            
            # Update config from YAML
            for key, value in yaml_config.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        except Exception as e:
            # If YAML loading fails, use defaults
            print(f"Warning: Could not load YAML config from {yaml_path}: {e}")
        
        return config
    
    @staticmethod
    def get_default_config() -> LanguageIdentifierConfig:
        """Get default configuration."""
        return LanguageIdentifierConfig()
    
    @staticmethod
    def validate_config(config: LanguageIdentifierConfig) -> bool:
        """Validate configuration settings."""
        try:
            # Validate weights sum to reasonable value
            total_weight = (config.extension_weight + config.shebang_weight + 
                          config.keyword_weight + config.llm_weight)
            
            if total_weight <= 0:
                raise ValueError("Total detection weights must be positive")
            
            # Validate thresholds
            if not (0 <= config.low_confidence_threshold <= 
                   config.medium_confidence_threshold <= 
                   config.high_confidence_threshold <= 1):
                raise ValueError("Confidence thresholds must be in order: 0 <= low <= medium <= high <= 1")
            
            # Validate file size limits
            if config.max_file_size <= 0 or config.max_content_analysis <= 0:
                raise ValueError("File size limits must be positive")
            
            # Validate performance settings
            if config.max_workers <= 0:
                raise ValueError("Max workers must be positive")
            
            return True
            
        except Exception as e:
            print(f"Config validation error: {e}")
            return False


# Global configuration instance
_config_instance: Optional[LanguageIdentifierConfig] = None

def get_language_identifier_config() -> LanguageIdentifierConfig:
    """Get the global configuration instance."""
    global _config_instance
    
    if _config_instance is None:
        # Try to load from YAML first, then environment, finally defaults
        try:
            _config_instance = ConfigLoader.load_from_yaml()
        except Exception:
            try:
                _config_instance = ConfigLoader.load_from_env()
            except Exception:
                _config_instance = ConfigLoader.get_default_config()
        
        # Validate the configuration
        if not ConfigLoader.validate_config(_config_instance):
            print("Warning: Invalid configuration detected, using defaults")
            _config_instance = ConfigLoader.get_default_config()
    
    return _config_instance

def reset_config():
    """Reset the global configuration instance."""
    global _config_instance
    _config_instance = None
